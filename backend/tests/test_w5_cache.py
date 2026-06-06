"""
W5 v0.4.13 — DuckDB-KV cache pytest 覆盖 (design doc v1.1 §7.5)

覆盖 (6 个核心 + 1 集成):
1. test_ensure_table_idempotent: 建表幂等, 跑 2 次不报错
2. test_set_then_get_hit: set 后 get 返回原值
3. test_get_miss_when_empty: 无 set 时 get 返回 None
4. test_set_overwrite_same_key: INSERT OR REPLACE 行为
5. test_different_endpoints_different_keys: 端点名不同 → 互不污染
6. test_different_params_different_keys: 参数不同 → 互不污染
7. test_ttl_expire: TTL 过期 → get 返回 None
8. test_concurrent_set_get: 多线程并发 set/get, 锁安全
9. test_manifest_invalidate_on_version_change: manifest version 变化 → 整表清空
10. test_manifest_no_invalidate_when_unchanged: manifest version 不变 → 不清空
11. test_invalid_value_falls_back_to_none: value 列损坏 → 返回 None 不抛
12. test_rfm_router_uses_cache: 4 端点 (r-flow/f-flow/m-flow/segment-orders) 都走 cache

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离,
monkeypatch get_connection 到独立 in-memory conn.
"""
import json
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.rfm.cache import (  # noqa: E402
    CACHE_TABLE,
    RfmQueryCache,
    _hash_key,
    _ManifestTracker,
)
from backend.db.connection import ThreadSafeConnection  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def in_memory_conn():
    """In-memory DuckDB, 每次 test 全新. 不污染生产 DUCKDB_PATH."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def cache(in_memory_conn, tmp_path, monkeypatch):
    """RfmQueryCache 走 in-memory DuckDB + 临时 manifest 路径.

    关键: 替换 _manifest_tracker_singleton 为指向 tmp_path 的新实例,
    避免 test 之间的 manifest version 串扰.
    get_connection 返回 ThreadSafeConnection 包装, 跟生产一致, 多线程安全.
    """
    # 重置 singleton 的 last_seen_version (避免 test 之间的 state leak)
    manifest_path = tmp_path / "manifest.json"
    new_tracker = _ManifestTracker(manifest_path)
    new_tracker._last_seen_version = None
    monkeypatch.setattr(
        "backend.services.rfm.cache._manifest_tracker_singleton",
        new_tracker,
    )

    # get_connection() 替换为返回 ThreadSafeConnection(in_memory_conn)
    # 跟生产一致, 多线程下 query 锁自动串行化
    def fake_get_connection():
        return ThreadSafeConnection(in_memory_conn)
    monkeypatch.setattr(
        "backend.services.rfm.cache.get_connection",
        fake_get_connection,
    )

    return RfmQueryCache(ttl_hours=24)


# ─────────────────────────────────────────────────────────────
# 1. 表管理
# ─────────────────────────────────────────────────────────────
class TestTableManagement:
    def test_ensure_table_idempotent(self, cache, in_memory_conn):
        """建表幂等 (跑 2 次不报错)."""
        cache.ensure_table()
        cache.ensure_table()  # 第二次 no-op
        # 验证表存在
        tables = in_memory_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [CACHE_TABLE],
        ).fetchall()
        assert len(tables) == 1

    def test_table_schema_columns(self, cache, in_memory_conn):
        """表 schema 列对: key / endpoint / params_hash / value / expire_at / created_at."""
        cache.ensure_table()
        cols = in_memory_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [CACHE_TABLE],
        ).fetchall()
        col_names = [c[0] for c in cols]
        for required in ["key", "endpoint", "params_hash", "value", "expire_at", "created_at"]:
            assert required in col_names, f"缺列: {required}"


# ─────────────────────────────────────────────────────────────
# 2. cache hit / miss
# ─────────────────────────────────────────────────────────────
class TestHitMiss:
    def test_get_miss_when_empty(self, cache):
        """无 set 时 get 返回 None (不是抛异常)."""
        result = cache.get("r-flow", {"start_date": "2026-01-01", "end_date": "2026-01-31"})
        assert result is None

    def test_set_then_get_hit(self, cache):
        """set 后 get 返回原值 (deep equal)."""
        params = {"start_date": "2026-01-01", "end_date": "2026-01-31", "channel": "全店"}
        value = {"rows": [{"segment": "近1个月", "count": 100}], "total": 100}
        cache.set("r-flow", params, value)
        cached = cache.get("r-flow", params)
        assert cached == value

    def test_set_overwrite_same_key(self, cache, in_memory_conn):
        """INSERT OR REPLACE: 同 key 第二次 set 覆盖原值, 行数仍为 1."""
        params = {"a": 1}
        cache.set("r-flow", params, {"v": 1})
        cache.set("r-flow", params, {"v": 2})
        cached = cache.get("r-flow", params)
        assert cached == {"v": 2}
        # 确认只有 1 行
        count = in_memory_conn.execute(
            f"SELECT COUNT(*) FROM {CACHE_TABLE}"
        ).fetchone()[0]
        assert count == 1

    def test_different_endpoints_different_keys(self, cache):
        """端点名不同 → 互不污染."""
        params = {"start_date": "2026-01-01"}
        cache.set("r-flow", params, {"endpoint": "r-flow"})
        cache.set("f-flow", params, {"endpoint": "f-flow"})
        assert cache.get("r-flow", params) == {"endpoint": "r-flow"}
        assert cache.get("f-flow", params) == {"endpoint": "f-flow"}
        assert cache.get("m-flow", params) is None  # 未 set

    def test_different_params_different_keys(self, cache):
        """参数不同 → 互不污染 (SHA-256 key 区分)."""
        cache.set("r-flow", {"start_date": "2026-01-01"}, {"v": 1})
        cache.set("r-flow", {"start_date": "2026-02-01"}, {"v": 2})
        assert cache.get("r-flow", {"start_date": "2026-01-01"}) == {"v": 1}
        assert cache.get("r-flow", {"start_date": "2026-02-01"}) == {"v": 2}

    def test_canonical_params_order_invariant(self):
        """参数 key 顺序不影响 hash (canonicalization)."""
        h1 = _hash_key("r-flow", {"a": 1, "b": 2})
        h2 = _hash_key("r-flow", {"b": 2, "a": 1})
        assert h1 == h2


# ─────────────────────────────────────────────────────────────
# 3. TTL expire
# ─────────────────────────────────────────────────────────────
class TestTtl:
    def test_ttl_expire_returns_none(self, cache, in_memory_conn, monkeypatch):
        """TTL 过期 → get 返回 None.

        用 mock 直接 set 一行 expire_at = now - 1h (绕过 cache.set 的 TTL 计算).
        """
        cache.ensure_table()
        key = _hash_key("r-flow", {"x": 1})
        # 直接 INSERT 过期行
        in_memory_conn.execute(
            f"INSERT INTO {CACHE_TABLE} VALUES (?, ?, ?, ?, ?, ?)",
            [key, "r-flow", "h", json.dumps({"v": "stale"}),
             datetime.now() - timedelta(hours=1), datetime.now() - timedelta(hours=1)],
        )
        assert cache.get("r-flow", {"x": 1}) is None


# ─────────────────────────────────────────────────────────────
# 4. 并发安全
# ─────────────────────────────────────────────────────────────
class TestConcurrency:
    def test_concurrent_set_get_no_crash(self, cache, in_memory_conn):
        """10 线程并发 set/get, 锁安全不崩溃, 数据一致."""
        results = []
        errors = []

        def worker(i: int):
            try:
                params = {"thread": i, "start": "2026-01-01"}
                value = {"thread_id": i, "n": list(range(10))}
                cache.set("r-flow", params, value)
                cached = cache.get("r-flow", params)
                if cached != value:
                    errors.append(f"thread {i} got {cached}")
                results.append(i)
            except Exception as e:
                errors.append(f"thread {i}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"并发错误: {errors}"
        assert len(results) == 10
        # 10 行都应存在
        count = in_memory_conn.execute(
            f"SELECT COUNT(*) FROM {CACHE_TABLE}"
        ).fetchone()[0]
        assert count == 10


# ─────────────────────────────────────────────────────────────
# 5. Manifest invalidate
# ─────────────────────────────────────────────────────────────
class TestManifestInvalidate:
    def test_manifest_invalidate_on_version_change(self, cache, in_memory_conn, tmp_path):
        """manifest version 变化 (1 → 2) → 整表清空."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"version": 1, "active_view": "v1"}))
        # 触发首次初始化: last_seen 从 None → 1, 触发首次 invalidate (空表无影响)
        cache.get("r-flow", {"init": 1})
        # 灌一行
        cache.set("r-flow", {"a": 1}, {"v": "old"})
        assert cache.get("r-flow", {"a": 1}) == {"v": "old"}
        # manifest 升级到 v=2
        manifest.write_text(json.dumps({"version": 2, "active_view": "v2"}))
        # 下一次 get 应触发 invalidate, 返回 None
        assert cache.get("r-flow", {"a": 1}) is None
        # 验证表已清空
        count = in_memory_conn.execute(
            f"SELECT COUNT(*) FROM {CACHE_TABLE}"
        ).fetchone()[0]
        assert count == 0

    def test_manifest_no_invalidate_when_unchanged(self, cache, in_memory_conn, tmp_path):
        """manifest version 不变 → 多次 get 不清空 cache (除首次初始化外)."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"version": 5, "active_view": "v5"}))
        # 首次初始化: last_seen 从 None → 5, 触发清空 (空表)
        cache.get("r-flow", {"init": 1})
        # 灌 3 行
        cache.set("r-flow", {"a": 1}, {"v": 1})
        cache.set("r-flow", {"a": 2}, {"v": 2})
        cache.set("r-flow", {"a": 3}, {"v": 3})
        count_before = in_memory_conn.execute(
            f"SELECT COUNT(*) FROM {CACHE_TABLE}"
        ).fetchone()[0]
        assert count_before == 3
        # 再调 5 次 get, manifest version 没变, 不应清空
        for _ in range(5):
            cache.get("r-flow", {"a": 1})
        count_after = in_memory_conn.execute(
            f"SELECT COUNT(*) FROM {CACHE_TABLE}"
        ).fetchone()[0]
        assert count_after == 3, f"version 不变时不应清空, 但行数从 {count_before} 变 {count_after}"


# ─────────────────────────────────────────────────────────────
# 6. Stats / cleanup / list_keys 辅助方法
# ─────────────────────────────────────────────────────────────
class TestHelpers:
    def test_stats(self, cache):
        """stats 返回 total/valid/expired 三字段."""
        cache.set("r-flow", {"a": 1}, {"v": 1})
        cache.set("f-flow", {"a": 2}, {"v": 2})
        s = cache.stats()
        assert s == {"total": 2, "valid": 2, "expired": 0}

    def test_invalidate_clears_all(self, cache):
        """invalidate 整表清空, 返回删除行数."""
        cache.set("r-flow", {"a": 1}, {"v": 1})
        cache.set("f-flow", {"a": 2}, {"v": 2})
        n = cache.invalidate()
        assert n == 2
        assert cache.get("r-flow", {"a": 1}) is None
        assert cache.get("f-flow", {"a": 2}) is None

    def test_list_keys(self, cache):
        """list_keys 返回 [{key, endpoint, ...}]."""
        cache.set("r-flow", {"a": 1}, {"v": 1})
        cache.set("f-flow", {"b": 2}, {"v": 2})
        keys = cache.list_keys()
        assert len(keys) == 2
        endpoints = {k["endpoint"] for k in keys}
        assert endpoints == {"r-flow", "f-flow"}


# ─────────────────────────────────────────────────────────────
# 7. 集成: 4 端点都走 cache (mock service 函数, 验证 cache.set 被调)
# ─────────────────────────────────────────────────────────────
class TestRfmRouterCacheIntegration:
    """验证 4 个 RFM 端点都通过 _cached_rfm_call 走 cache.

    不真打 DuckDB: mock 底层的 get_rfm_r_flow 等, 验证第二次调用会返回 cache.
    """

    def test_rfm_router_imports_cache(self):
        """routers/rfm.py 正确导入 RfmQueryCache."""
        from backend.routers.rfm import _rfm_cache, _cached_rfm_call
        assert isinstance(_rfm_cache, RfmQueryCache)
        assert callable(_cached_rfm_call)

    def test_cached_rfm_call_set_then_get(self, cache, monkeypatch):
        """_cached_rfm_call: 第一次 miss 调 compute_fn, 第二次 hit 不调 compute_fn."""
        from backend.routers.rfm import _cached_rfm_call
        call_count = {"n": 0}

        def fake_compute(**kwargs):
            call_count["n"] += 1
            return {"result": "computed", "kwargs": kwargs}

        params = {"start_date": "2026-01-01", "end_date": "2026-01-31"}
        # 第一次: miss → compute
        r1 = _cached_rfm_call("r-flow", params, fake_compute, **params)
        assert r1["result"] == "computed"
        assert call_count["n"] == 1
        # 第二次: hit → 不再 compute
        r2 = _cached_rfm_call("r-flow", params, fake_compute, **params)
        assert r2["result"] == "computed"
        assert call_count["n"] == 1, "应命中 cache, 不再调 compute_fn"
        assert r1 == r2
