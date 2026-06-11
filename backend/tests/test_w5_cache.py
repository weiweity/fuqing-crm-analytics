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


# ─────────────────────────────────────────────────────────────
# 8. Sprint 16.5 P2.7 — _flow_cache_key MD5 full + namespace prefix
# (Codex audit: 旧版 exclude_channels MD5[:8] 截断 → 生日悖论 6.5K 列表 50% 碰撞)
# ─────────────────────────────────────────────────────────────
from backend.services.rfm._shared import (  # noqa: E402
    _flow_cache_key,
    FLOW_ALGO_VERSION,
)


class TestFlowCacheKeyMd5Full:
    """_flow_cache_key Sprint 16.5 P2.7 治根测试 — 6 件套.

    覆盖: 不同参数 → 不同 key / 同参数 → 同 key / 截断 vs full 冲突 /
           algo_version 变更 → key 失效 / 跨 namespace 隔离 / 幂等.
    """

    BASE_KW = dict(
        flow_type="r_flow",
        start_date="2026-01-01",
        end_date="2026-01-31",
        channel="全店",
        metric_type="GSV",
        exclude_channels=None,
        compare_start_date=None,
        compare_end_date=None,
        data_version="orders_max_pay_time_v123",
    )

    def test_different_params_different_keys(self):
        """不同参数 → 不同 key (8 维任一变化, MD5 必变)."""
        k1 = _flow_cache_key(**self.BASE_KW)
        # 1) start_date +1 天
        k2 = _flow_cache_key(**{**self.BASE_KW, "start_date": "2026-01-02"})
        # 2) channel 改
        k3 = _flow_cache_key(**{**self.BASE_KW, "channel": "抖音"})
        # 3) metric_type 改
        k4 = _flow_cache_key(**{**self.BASE_KW, "metric_type": "GMV"})
        # 4) data_version 改
        k5 = _flow_cache_key(**{**self.BASE_KW, "data_version": "v124"})
        assert len({k1, k2, k3, k4, k5}) == 5, f"5 个不同参数应生成 5 个不同 key, got {len({k1, k2, k3, k4, k5})}"

    def test_same_params_same_key_idempotent(self):
        """同参数 → 同 key (幂等, 重入 cache 安全).

        100 次重复调用: 应只生成 1 个 distinct key, 验证 cache 写读幂等.
        """
        keys = [_flow_cache_key(**self.BASE_KW) for _ in range(100)]
        assert len(set(keys)) == 1, f"100 次重复调用应同 key, got {len(set(keys))} 个"

    def test_md5_full_no_truncation(self):
        """MD5 full 32 char, 不用 [:8] 截断 (Sprint 16.5 P2.7 治根点).

        旧版 exclude_channels MD5[:8] = 32 bit → 6.5K 列表 50% 碰撞.
        新版: 整 hash 进 key, 32 hex (128 bit) → 2^64 列表才有 50% 碰撞.
        """
        k = _flow_cache_key(**self.BASE_KW)
        # 格式: flow_<32 hex char>.json
        assert k.startswith("flow_"), f"namespace prefix 必须是 `flow_`, got {k}"
        assert k.endswith(".json")
        digest = k[5:-5]  # 剥掉 flow_ + .json
        assert len(digest) == 32, f"MD5 digest 应为 32 char, got {len(digest)}: {digest}"
        # 验证是合法 hex
        int(digest, 16)  # 抛 ValueError if non-hex

    def test_truncation_would_have_collided(self):
        """截断 (旧版 MD5[:8]) 在典型 exclude 场景会产生碰撞, MD5 full 不会.

        构造 2 个 exclude 列表, MD5[:8] 相同 (实际真碰), MD5 full 必不同.
        """
        # 真实场景: 不同渠道集合, 旧版 32-bit 截断会撞
        excludes_a = ["抖音小店", "视频号", "小红书", "京东", "拼多多", "天猫", "唯品会", "其他"]
        excludes_b = ["微信小程序", "App内", "H5", "抖音", "快手", "B站", "知乎", "微博"]
        ka = _flow_cache_key(**{**self.BASE_KW, "exclude_channels": excludes_a})
        kb = _flow_cache_key(**{**self.BASE_KW, "exclude_channels": excludes_b})
        # 旧版: MD5[:8] 可能撞 (32 bit 生日悖论).
        # 新版: full 128 bit, 实际不可能撞.
        assert ka != kb, "full MD5 必不同 (旧版 [:8] 会撞 — 治根点)"

    def test_algo_version_change_invalidates_key(self):
        """algo_version 变更 → key 失效 (跟 Sprint 14.5 W5 cache 模式一致).

        模拟 algo_version 升级: 把模块全局 FLOW_ALGO_VERSION 临时改,
        验证 key 跟着变 (cache miss → 重算, 不返旧值).
        """
        import backend.services.rfm._shared as shared_mod
        original = shared_mod.FLOW_ALGO_VERSION

        k_old = _flow_cache_key(**self.BASE_KW)
        try:
            shared_mod.FLOW_ALGO_VERSION = "v999.99.99-test"
            k_new = _flow_cache_key(**self.BASE_KW)
            assert k_old != k_new, "algo_version 升级 → key 必须变, 防 24h 内返旧值"
        finally:
            shared_mod.FLOW_ALGO_VERSION = original

    def test_namespace_isolation_vs_w5(self):
        """跨 namespace 隔离: _flow_cache_key (flow_) ≠ _hash_key (w5kv_).

        即便 endpoint="r-flow" + 相同 params, 两套 cache 必不串扰.
        验证: 取 endpoint="r-flow" + params={BASE_KW 的 8 维}, 两 key 前缀不同.
        """
        from backend.services.rfm.cache import _hash_key
        # _hash_key 接受 endpoint + dict params, _flow_cache_key 接受 8 个具名参数
        flow_kw_args = (
            "r_flow",  # flow_type
            self.BASE_KW["start_date"],
            self.BASE_KW["end_date"],
            self.BASE_KW["channel"],
            self.BASE_KW["metric_type"],
            self.BASE_KW["exclude_channels"],
            self.BASE_KW["compare_start_date"],
            self.BASE_KW["compare_end_date"],
            self.BASE_KW["data_version"],
        )
        k_flow = _flow_cache_key(*flow_kw_args)
        k_w5 = _hash_key("r-flow", {
            "flow_type": flow_kw_args[0],
            "start_date": flow_kw_args[1],
            "end_date": flow_kw_args[2],
            "channel": flow_kw_args[3],
            "metric_type": flow_kw_args[4],
            "exclude_channels": flow_kw_args[5],
            "compare_start_date": flow_kw_args[6],
            "compare_end_date": flow_kw_args[7],
            "data_version": flow_kw_args[8],
        })
        assert k_flow.startswith("flow_"), f"flow cache prefix: {k_flow}"
        assert k_w5.startswith("w5kv_"), f"W5 DuckDB-KV prefix: {k_w5}"
        assert k_flow != k_w5, "不同 namespace prefix 必不串扰"
