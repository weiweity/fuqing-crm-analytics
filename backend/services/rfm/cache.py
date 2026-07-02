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
- ⑦ Sprint 18 #123: 启动时 check_manifest_version_and_invalidate() 主动对齐 manifest version,
   跨进程持久化 last_seen_version 到 w5kv_manifest_state.json, 解决改 ratio/契约后
   必须手动 invalidate 12 keys 的痛点 (Sprint 14.5 留).

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
    check_manifest_version_and_invalidate()  # 启动 hook (Sprint 18 #123)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
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

# Sprint 18 #123: 跨进程持久化 manifest version 跟踪 (跟 _ManifestTracker 互补)
# 进程内 _ManifestTracker 检测本进程内 manifest 变化, 启动 hook 检测跨进程
# (uvicorn 重启 / ETL 跑批后) 的 manifest 变化. 状态文件用 OS env 覆盖
# 方便 test 用 tmp_path, 默认放 data/cache/ 跟 ETL 缓存同目录.
W5KV_STATE_FILENAME = "w5kv_manifest_state.json"
W5KV_STATE_ENV = "FQ_W5KV_STATE_PATH"


def _read_only_request_active() -> bool:
    """Return True inside Sprint 201 read-only request routing."""

    try:
        from backend.services.dual_conn import get_query_type

        return get_query_type() == "read"
    except Exception:  # noqa: BLE001
        return False


def _default_state_path() -> Path:
    """默认状态文件路径: data/cache/w5kv_manifest_state.json.

    跟 data/processed/manifest.json 同根目录的 data/cache/, 避免污染 W2 manifest.
    """
    env = os.environ.get(W5KV_STATE_ENV)
    if env:
        return Path(env)
    # data/ 跟 manifest.py 的 DEFAULT_MANIFEST_PATH 的 parent 同级
    # manifest 默认是 data/processed/manifest.json → parent.parent = data/
    return DEFAULT_MANIFEST_PATH.parent.parent / "cache" / W5KV_STATE_FILENAME


# ─────────────────────────────────────────────────────────────
# SHA-256 key derivation
# ─────────────────────────────────────────────────────────────
def _canonical_params(params: dict) -> str:
    """规范化参数 (排序 key + 转 JSON), 保证等价请求生成同一 hash.

    例: {"a": 1, "b": 2} 和 {"b": 2, "a": 1} 应生成同一 hash.
    """
    return json.dumps(params, sort_keys=True, default=str, ensure_ascii=False)


def _hash_key(endpoint: str, params: dict) -> str:
    """生成 W5 DuckDB-KV cache key (namespace prefix `w5kv_` + SHA-256 hex).

    Sprint 14.5 P1.4: 含 FLOW_ALGO_VERSION, 算法改动 → key 变 → miss → 重算.
    Sprint 16.5 P2.7 (Codex audit): 加 namespace prefix `w5kv_` 防跟
    _flow_cache_key (file cache, prefix `flow_`) 误命名空间冲突.
    不依赖 manifest (manifest 只跟数据变化同步, 不跟算法同步).
    """
    raw = f"{endpoint}|{FLOW_ALGO_VERSION}|{_canonical_params(params)}"
    return f"w5kv_{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


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
        if _read_only_request_active():
            return
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
        if not _read_only_request_active():
            self.ensure_table()
        # 每次读都检查 manifest (廉价, < 1ms)
        conn = get_connection()
        if not _read_only_request_active():
            self._tracker.check_and_invalidate(conn)

        key = _hash_key(endpoint, params)
        # ThreadSafeCursor.execute() 已在锁内预取, fetchone() 安全
        try:
            rows = conn.execute(
                f"SELECT value FROM {CACHE_TABLE} "
                f"WHERE key = ? AND expire_at > now()",
                [key],
            ).fetchall()
        except Exception as e:  # noqa: BLE001
            logger.debug("W5 cache read miss/fallback: %s", e)
            return None
        if not rows:
            return None
        try:
            # DuckDB JSON 列返回 str (我们存的是 json.dumps 出的 str)
            return json.loads(rows[0][0])
        except (TypeError, json.JSONDecodeError):
            return None

    def set(self, endpoint: str, params: dict, value: Any) -> None:
        """写 cache (INSERT OR REPLACE)."""
        if _read_only_request_active():
            logger.debug("W5 cache set skipped in read-only request")
            return
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
        if _read_only_request_active():
            logger.debug("W5 cache invalidate skipped in read-only request")
            return 0
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
        if _read_only_request_active():
            logger.debug("W5 cache cleanup skipped in read-only request")
            return 0
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
        if not _read_only_request_active():
            self.ensure_table()
        conn = get_connection()
        try:
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
        except Exception as e:  # noqa: BLE001
            logger.debug("W5 cache list_keys fallback: %s", e)
            return []
        return [
            {"key": r[0], "endpoint": r[1], "expire_at": str(r[2]), "created_at": str(r[3])}
            for r in rows
        ]

    def stats(self) -> dict:
        """调试用: cache 统计."""
        if not _read_only_request_active():
            self.ensure_table()
        conn = get_connection()
        try:
            row = conn.execute(
                f"SELECT COUNT(*), "
                f"SUM(CASE WHEN expire_at > now() THEN 1 ELSE 0 END) "
                f"FROM {CACHE_TABLE}"
            ).fetchone()
        except Exception as e:  # noqa: BLE001
            logger.debug("W5 cache stats fallback: %s", e)
            return {"total": 0, "valid": 0, "expired": 0}
        total = int(row[0]) if row and row[0] is not None else 0
        valid = int(row[1]) if row and row[1] is not None else 0
        return {"total": total, "valid": valid, "expired": total - valid}


# ─────────────────────────────────────────────────────────────
# 进程内单例 (避免每次 new 重建 tracker 状态)
# ─────────────────────────────────────────────────────────────
_manifest_tracker_singleton = _ManifestTracker()


# ─────────────────────────────────────────────────────────────
# Sprint 18 #123: 启动 hook — check_manifest_version_and_invalidate
# 跨进程持久化 last_seen_manifest_version, 跟进程内 _ManifestTracker 互补:
#   - 进程内 _ManifestTracker: 检测本进程内 cache.get() 时的 manifest 变化
#   - 启动 hook: 跨进程 (uvicorn 重启 / ETL 跑批后) 启动时对齐
#
# 痛点 (Sprint 14.5 留): 改 ratio/契约后必须手动 invalidate W5 DuckDB-KV cache
# (12 keys). 修法: 启动时自动同步, 改完代码 → 重启 uvicorn → 启动 hook 自动
# 检测到 manifest 变化 (ETL 跑批后 version 升) → 整表清空 12 orphan keys.
# 跨进程持久化用 data/cache/w5kv_manifest_state.json (可用 FQ_W5KV_STATE_PATH
# 覆盖, test 用 tmp_path).
# ─────────────────────────────────────────────────────────────
def _read_state_file(state_path: Path) -> Optional[int]:
    """读状态文件里的 last_seen_version. 缺失/损坏返回 None."""
    if not state_path.exists():
        return None
    try:
        with open(state_path) as f:
            data = json.load(f)
        v = data.get("last_seen_manifest_version")
        return int(v) if v is not None else None
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def _write_state_file(state_path: Path, version: int) -> None:
    """原子写状态文件 (tmp + rename 模式, 跟 W2 manifest 一致)."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_seen_manifest_version": version,
        "ts": datetime.now().isoformat(),
    }
    tmp = state_path.with_suffix(f".tmp.{os.getpid()}.{os.getpid()}")
    try:
        with open(tmp, "w") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, state_path)
    except OSError:
        # 写失败不阻塞启动 (cache 状态是 best-effort)
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def check_manifest_version_and_invalidate(
    state_path: Optional[Path] = None,
    cache: Optional[RfmQueryCache] = None,
) -> bool:
    """启动 hook: 对齐 manifest version, 不一致时自动 invalidate W5 cache.

    设计 (Sprint 18 #123):
    - 读 state_path (默认 data/cache/w5kv_manifest_state.json) 里记录的
      last_seen_manifest_version
    - 读当前 manifest version (manifest.py 同逻辑)
    - 不一致 (含 None -> int, 即首次启动) → 整表 invalidate + 更新状态文件
    - 一致 → no-op (24h 内的 cache 保留)

    时机: main.py lifespan startup 调用, 不在 import 时调 (避免测试 import 触发)
    失败处理: 任何异常被吞掉 + log warning, 不阻塞服务启动 (best-effort)

    Args:
        state_path: 状态文件路径, 默认 data/cache/w5kv_manifest_state.json
                    (FQ_W5KV_STATE_PATH 环境变量可覆盖)
        cache: RfmQueryCache 实例, 默认走模块级单例行为 (新建 RfmQueryCache())

    Returns:
        bool: True = 触发了 invalidate, False = no-op
    """
    sp = Path(state_path) if state_path else _default_state_path()
    c = cache or RfmQueryCache()

    try:
        # 读 manifest 当前 version
        current = _manifest_tracker_singleton.current_version()
        if current is None:
            # manifest 不存在 (没跑过 ETL) → 不做任何事, 等 ETL 跑完首次
            # 写入 manifest 后由 _ManifestTracker 接管
            logger.debug("W5 startup hook: manifest 缺失, 跳过 (等 ETL 跑批)")
            return False

        # 读状态文件
        last_seen = _read_state_file(sp)

        if last_seen == current:
            logger.debug("W5 startup hook: manifest version 一致 (v=%s), 跳过", current)
            return False

        # 不一致 → 整表 invalidate + 持久化新 version
        n = c.invalidate()
        _write_state_file(sp, current)
        logger.info(
            "W5 startup hook: manifest version 变化 (%s -> %s), invalidated %d cache rows",
            last_seen, current, n,
        )
        return True
    except Exception as e:  # noqa: BLE001
        # best-effort: 任何异常不阻塞服务启动
        logger.warning("W5 startup hook 失败 (不阻塞服务): %s", e)
        return False


# ─────────────────────────────────────────────────────────────
# Sprint 19 P2-4: ETL post-run hook — 跑批末尾调, 不依赖 uvicorn 重启
# 也能 invalidate W5 DuckDB-KV cache. 跟启动 hook 互补:
#   - 启动 hook: 跨进程 (uvicorn 重启后) 启动时对齐
#   - post-run hook: ETL 跑批末尾主动调, uvicorn 还没重启也提前清
#
# 痛点 (Sprint 14.5 + Sprint 18 #123 留): 改 ratio/契约后, 12 keys
# 必须 invalidate 才会重算. 启动 hook 解决"uvicorn 重启"路径, 但
# ETL 跑完 uvicorn 未必立刻重启 → 用户访问仍然拿旧值. post-run hook
# 让 ETL 跑完 → 主动 invalidate → 12 keys 失效 → 下次访问 miss 重算.
# ─────────────────────────────────────────────────────────────
def etl_post_run_hook() -> bool:
    """ETL 跑批末尾调, 不依赖 uvicorn 重启也能 invalidate W5 cache.

    跟 check_manifest_version_and_invalidate 共享同一份 state_path,
    调用后状态文件同步 (跟启动 hook 行为一致). 失败被吞 + log warning,
    不阻塞 ETL 跑批结果 (best-effort, ETL 跑完是更重要的结果).

    Returns:
        bool: True = 触发了 invalidate, False = no-op / 失败

    集成位置: scripts/etl/cli.py main() 末尾, ETL 跑批成功后调.
    测试: backend/tests/services/rfm/test_cache_etl_post_run_hook.py
    """
    try:
        return check_manifest_version_and_invalidate()
    except Exception as e:  # noqa: BLE001
        # best-effort: 任何异常不阻塞 ETL 跑批收口
        logger.warning("W5 cache ETL post-run hook 失败 (不阻塞 ETL 收口): %s", e)
        return False
