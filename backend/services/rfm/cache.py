"""
W5 DuckDB-KV 缓存 (v0.4.13) — design doc v1.1 §W5 + §7.5

痛点 3 部分修复: RFM 端点选历史日期范围时直接走 cache, 命中 < 5ms (miss < 200ms).

设计要点 (CLAUDE.md 合规):
- ① ThreadSafeCursor 包装: 锁内预取全部结果到内存 (reference 2026-05-31 教训)
- ② SHA-256 hash key: 几乎不可能碰撞 (防 cache poisoning)
- ③ TTL 24h, 过期自动失效 (不依赖后台 cleanup)
- ④ manifest 变更触发整表失效 (与 W2 atomic snapshot 配套)
- ⑤ key 不含 value 字段, 只含 date_range + dims + endpoint + algo_version, 避免用户/数据耦合
- ⑥ Sprint 14.5 P1.4: key 含 algo_version, 算法改动 → key 变 → miss → 重算 (防 24h 内返旧值)

schema:
    rfm_query_cache(
        key VARCHAR PRIMARY KEY,        -- SHA-256 hex (含 algo_version)
        endpoint VARCHAR NOT NULL,      -- 'r-flow' / 'f-flow' / 'm-flow' / 'segment-orders'
        params_hash VARCHAR NOT NULL,   -- SHA-256 hex of canonical params
        value JSON NOT NULL,            -- 序列化结果
        expire_at TIMESTAMP NOT NULL,   -- > now() 才算 hit
        created_at TIMESTAMP NOT NULL
    )

API:
    cache = RfmQueryCache()
    cached = cache.get(endpoint, params_dict)  # None if miss/expire
    cache.set(endpoint, params_dict, result)
    cache.invalidate()  # manifest 变更时全表清空
    cache.list_keys()  # 调试
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from backend.db.connection import get_connection
from scripts.etl.manifest import DEFAULT_MANIFEST_PATH
from backend.services.rfm._shared import FLOW_ALGO_VERSION  # Sprint 14.5 P1.4

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────
CACHE_TABLE = "rfm_query_cache"
DEFAULT_TTL_HOURS = 24


# ─────────────────────────────────────────────────────────────
# SHA-256 key derivation
# ─────────────────────────────────────────────────────────────
def _canonical_params(params: dict) -> str:
    """规范化参数 (排序 key + 转 JSON), 保证等价请求生成同一 hash.

    例: {"a": 1, "b": 2} 和 {"b": 2, "a": 1} 应生成同一 hash.
    """
    return json.dumps(params, sort_keys=True, default=str, ensure_ascii=False)


def _hash_key(endpoint: str, params: dict) -> str:
    """生成 cache key (endpoint + params + algo_version 的 SHA-256 hex).

    Sprint 14.5 P1.4: 含 FLOW_ALGO_VERSION, 算法改动 → key 变 → miss → 重算.
    不依赖 manifest (manifest 只跟数据变化同步, 不跟算法同步).
    """
    raw = f"{endpoint}|{FLOW_ALGO_VERSION}|{_canonical_params(params)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────
# Manifest change tracker
# ─────────────────────────────────────────────────────────────
class _ManifestTracker:
    """跟踪 manifest version 变化, 触发 cache 整表失效 (W5 manifest 集成).

    线程安全: 所有访问都加锁.
    设计: 进程内单例, 应用启动时建表 + 初始化 last_seen_version.
    """

    def __init__(self, manifest_path: Optional[Path] = None):
        self._path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
        self._lock = threading.Lock()
        self._last_seen_version: Optional[int] = None

    def current_version(self) -> Optional[int]:
        """读 manifest 当前 version (manifest 不存在返回 None)."""
        if not self._path.exists():
            return None
        try:
            with open(self._path) as f:
                return int(json.load(f).get("version", 0))
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            return None

    def check_and_invalidate(self, conn) -> bool:
        """检查 manifest version, 变化则全表清空. 返回是否触发失效.

        性能: 单次 read JSON < 1ms, 比每次查询都读一次开销小.
        """
        with self._lock:
            current = self.current_version()
            if current == self._last_seen_version:
                return False
            # version 变化 (含 None -> int) → 整表失效
            # DuckDB DELETE 返回单行 (count, ), 需 rows[0][0] 取数
            deleted = conn.execute(
                f"DELETE FROM {CACHE_TABLE}"
            ).fetchall()
            n = int(deleted[0][0]) if deleted and deleted[0][0] is not None else 0
            self._last_seen_version = current
            logger.info(
                "W5 manifest version changed (%s -> %s), invalidated %d cache rows",
                self._last_seen_version, current, n,
            )
            return True


# ─────────────────────────────────────────────────────────────
# RfmQueryCache 主类
# ─────────────────────────────────────────────────────────────
class RfmQueryCache:
    """RFM DuckDB-KV 缓存 (v0.4.13 W5).

    用法 (API 层集成):
        cache = RfmQueryCache()
        cached = cache.get('r-flow', {'start_date': '2026-01-01', ...})
        if cached is not None:
            return cached  # ~1ms
        result = compute_xxx(...)
        cache.set('r-flow', params, result)
        return result
    """

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        self.ttl = timedelta(hours=ttl_hours)
        self._init_lock = threading.Lock()
        self._initialized = False
        # 单进程内单例 manifest tracker
        self._tracker = _manifest_tracker_singleton

    # ── 表管理 ──
    def ensure_table(self) -> None:
        """幂等建表 (W5 完成标志第 1 条). 首次调用建表, 后续 no-op."""
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            conn = get_connection()
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                    key VARCHAR PRIMARY KEY,
                    endpoint VARCHAR NOT NULL,
                    params_hash VARCHAR NOT NULL,
                    value JSON NOT NULL,
                    expire_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            # 启动时初始化 last_seen_version (不触发 invalidate)
            if self._tracker._last_seen_version is None:
                self._tracker._last_seen_version = self._tracker.current_version()
            self._initialized = True

    # ── 核心: get / set / invalidate ──
    def get(self, endpoint: str, params: dict) -> Optional[Any]:
        """读 cache. None = miss/expire/不存在. 调用方必须能处理 None.

        流程: ensure_table → manifest 变化检测 → SELECT (锁内预取)
        """
        self.ensure_table()
        # 每次读都检查 manifest (廉价, < 1ms)
        conn = get_connection()
        self._tracker.check_and_invalidate(conn)

        key = _hash_key(endpoint, params)
        # ThreadSafeCursor.execute() 已在锁内预取, fetchone() 安全
        rows = conn.execute(
            f"SELECT value FROM {CACHE_TABLE} "
            f"WHERE key = ? AND expire_at > now()",
            [key],
        ).fetchall()
        if not rows:
            return None
        try:
            # DuckDB JSON 列返回 str (我们存的是 json.dumps 出的 str)
            return json.loads(rows[0][0])
        except (TypeError, json.JSONDecodeError):
            return None

    def set(self, endpoint: str, params: dict, value: Any) -> None:
        """写 cache (INSERT OR REPLACE)."""
        self.ensure_table()
        conn = get_connection()
        key = _hash_key(endpoint, params)
        params_hash = hashlib.sha256(_canonical_params(params).encode("utf-8")).hexdigest()
        now = datetime.now()
        conn.execute(
            f"INSERT OR REPLACE INTO {CACHE_TABLE} "
            f"(key, endpoint, params_hash, value, expire_at, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?)",
            [
                key,
                endpoint,
                params_hash,
                json.dumps(value, default=str, ensure_ascii=False),
                now + self.ttl,
                now,
            ],
        )

    def invalidate(self) -> int:
        """整表失效 (manifest 变化时调用). 返回删除行数.

        DuckDB DELETE 返回单行 (count, ), 不是删除的行. 需 rows[0][0] 取数.
        """
        self.ensure_table()
        conn = get_connection()
        rows = conn.execute(f"DELETE FROM {CACHE_TABLE}").fetchall()
        if not rows:
            return 0
        return int(rows[0][0]) if rows[0][0] is not None else 0

    def cleanup_expired(self) -> int:
        """清理过期行 (可定期调用, 避免表无限增长). 返回删除行数.

        DuckDB DELETE 返回单行 (count, ), 不是删除的行. 需 rows[0][0] 取数.
        """
        self.ensure_table()
        conn = get_connection()
        rows = conn.execute(
            f"DELETE FROM {CACHE_TABLE} WHERE expire_at <= now()"
        ).fetchall()
        if not rows:
            return 0
        return int(rows[0][0]) if rows[0][0] is not None else 0

    def list_keys(self, endpoint: Optional[str] = None, limit: int = 100) -> list[dict]:
        """调试用: 列出 cache 键 (可选 endpoint 过滤)."""
        self.ensure_table()
        conn = get_connection()
        if endpoint:
            rows = conn.execute(
                f"SELECT key, endpoint, expire_at, created_at "
                f"FROM {CACHE_TABLE} WHERE endpoint = ? "
                f"ORDER BY created_at DESC LIMIT ?",
                [endpoint, limit],
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT key, endpoint, expire_at, created_at "
                f"FROM {CACHE_TABLE} ORDER BY created_at DESC LIMIT ?",
                [limit],
            ).fetchall()
        return [
            {"key": r[0], "endpoint": r[1], "expire_at": str(r[2]), "created_at": str(r[3])}
            for r in rows
        ]

    def stats(self) -> dict:
        """调试用: cache 统计."""
        self.ensure_table()
        conn = get_connection()
        row = conn.execute(
            f"SELECT COUNT(*), "
            f"SUM(CASE WHEN expire_at > now() THEN 1 ELSE 0 END) "
            f"FROM {CACHE_TABLE}"
        ).fetchone()
        total = int(row[0]) if row and row[0] is not None else 0
        valid = int(row[1]) if row and row[1] is not None else 0
        return {"total": total, "valid": valid, "expired": total - valid}


# ─────────────────────────────────────────────────────────────
# 进程内单例 (避免每次 new 重建 tracker 状态)
# ─────────────────────────────────────────────────────────────
_manifest_tracker_singleton = _ManifestTracker()
