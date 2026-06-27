"""
Sprint 18 #123 — W5 cache invalidation 启动 hook 测试

覆盖 (4 个核心 + 1 集成):
1. test_no_manifest: 没 manifest → hook 不报错 + 不写 state
2. test_manifest_first_run: 第一次跑 (state 缺失) → invalidate + 写 state
3. test_manifest_unchanged: 第二次跑 (state 一致) → 不 invalidate
4. test_manifest_changed: 改 manifest → invalidate + 更新 state
5. (bonus) test_hook_failure_does_not_block_startup: hook 抛异常不阻塞
6. (bonus) test_hook_after_get_compat: hook 不影响后续 cache.get() 行为

CLAUDE.md 合规: in-memory DuckDB + tmp_path manifest 隔离, 不污染生产 DUCKDB_PATH.
"""
import json
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.rfm.cache import (  # noqa: E402, F401
    CACHE_TABLE,
    RfmQueryCache,
    _ManifestTracker,
    _manifest_tracker_singleton,
    _default_state_path,
    _read_state_file,
    _write_state_file,
    check_manifest_version_and_invalidate,
    W5KV_STATE_FILENAME,
)
from backend.db.connection import ThreadSafeConnection  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def in_memory_conn():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def cache_with_state(in_memory_conn, tmp_path, monkeypatch):
    """RfmQueryCache 走 in-memory DuckDB + tmp_path 状态文件.

    关键: 替换进程内 _manifest_tracker_singleton, 避免跨 test state leak.
    state 文件路径用 tmp_path / w5kv_manifest_state.json, 不污染生产.
    """
    manifest_path = tmp_path / "manifest.json"
    state_path = tmp_path / W5KV_STATE_FILENAME

    # 替换 manifest tracker 指向 tmp manifest
    new_tracker = _ManifestTracker(manifest_path)
    new_tracker._last_seen_version = None
    monkeypatch.setattr(
        "backend.services.rfm.cache._manifest_tracker_singleton",
        new_tracker,
    )

    # 替换 get_connection 走 in-memory DuckDB
    def fake_get_connection():
        return ThreadSafeConnection(in_memory_conn)
    monkeypatch.setattr(
        "backend.services.rfm.cache.get_connection",
        fake_get_connection,
    )

    cache = RfmQueryCache(ttl_hours=24)
    return cache, state_path, manifest_path, in_memory_conn


# ─────────────────────────────────────────────────────────────
# 1. 没 manifest → hook 不报错
# ─────────────────────────────────────────────────────────────
class TestNoManifest:
    def test_no_manifest_hook_silent(self, cache_with_state, monkeypatch):
        """没 manifest 文件 → hook 不报错, 不写 state, 返回 False."""
        cache, state_path, manifest_path, conn = cache_with_state
        # 显式确认 manifest 不存在
        assert not manifest_path.exists()
        # hook 调一次
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is False, "没 manifest 应返回 False, 不触发 invalidate"
        # state 文件不应被创建
        assert not state_path.exists(), "没 manifest 时不应写 state"
        # cache 表也没建 (因为没调过 ensure_table)
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [CACHE_TABLE],
        ).fetchall()
        assert len(tables) == 0, "没 manifest 时 cache 表应保持空 (没触发 ensure_table)"


# ─────────────────────────────────────────────────────────────
# 2. 第一次跑 (state 缺失) → invalidate + 写 state
# ─────────────────────────────────────────────────────────────
class TestFirstRun:
    def test_manifest_first_run_invalidate(self, cache_with_state):
        """第一次跑 (state 缺失, manifest v=1 存在) → invalidate + 写 state.

        场景: 全新部署, uvicorn 第一次启动, manifest v=1 已由 ETL 写入,
        state 文件还没创建. hook 应触发 invalidate (虽然表是空) + 写 state.
        """
        cache, state_path, manifest_path, conn = cache_with_state
        # ETL 跑过, manifest v=1
        manifest_path.write_text(json.dumps({"version": 1, "active_view": "v1"}))
        # 灌 5 行模拟旧 cache (e.g. 来自上一次部署的 DuckDB 备份)
        cache.ensure_table()
        for i in range(5):
            cache.set("r-flow", {"i": i}, {"v": i})
        # 确认有 5 行
        count = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count == 5
        # state 缺失
        assert not state_path.exists()
        # 调 hook
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is True, "首次跑应返回 True (触发 invalidate)"
        # 5 行应被清空
        count = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count == 0, f"首次跑后 cache 应清空, 残留 {count} 行"
        # state 文件应被创建, 含 manifest v=1
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["last_seen_manifest_version"] == 1
        assert "ts" in state

    def test_manifest_first_run_empty_cache_safe(self, cache_with_state):
        """首次跑 + cache 空 → 仍触发 invalidate (no-op) + 写 state.

        场景: 全新部署, manifest v=1 + 空 cache 表. hook 应安全 no-op 清空
        + 写 state. 不能 crash.
        """
        cache, state_path, manifest_path, conn = cache_with_state
        manifest_path.write_text(json.dumps({"version": 1, "active_view": "v1"}))
        cache.ensure_table()
        # cache 表空, 直接调 hook
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is True
        # state 文件存在
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["last_seen_manifest_version"] == 1


# ─────────────────────────────────────────────────────────────
# 3. 第二次跑 (state 一致) → 不 invalidate
# ─────────────────────────────────────────────────────────────
class TestUnchanged:
    def test_manifest_unchanged_no_invalidate(self, cache_with_state):
        """第二次跑 (state 一致, manifest v=5) → 不 invalidate, cache 保留.

        场景: 第二次 uvicorn 重启 (间隔 1 天, manifest 没动, 还在 v=5).
        hook 应 no-op, cache 24h 内的行保留 (Sprint 16.5 P2.7 r-flow 1180× 加速).
        """
        cache, state_path, manifest_path, conn = cache_with_state
        # 模拟已对齐 state (跟 manifest 一致)
        manifest_path.write_text(json.dumps({"version": 5, "active_view": "v5"}))
        cache.ensure_table()
        _write_state_file(state_path, 5)
        # 灌 3 行
        for i in range(3):
            cache.set("r-flow", {"i": i}, {"v": i})
        count_before = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count_before == 3
        # 调 hook
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is False, "state 一致应返回 False (不触发 invalidate)"
        # 3 行保留
        count_after = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count_after == 3, f"state 一致时 cache 应保留, 但行数从 {count_before} 变 {count_after}"
        # state 仍为 5 (没变)
        state = json.loads(state_path.read_text())
        assert state["last_seen_manifest_version"] == 5

    def test_manifest_unchanged_5_runs(self, cache_with_state):
        """5 次连续跑 (state 一致) → 5 次都 no-op, cache 保留.

        场景: 频繁重启 (5 次 uvicorn reload), manifest 不变, 5 次 hook 都 no-op.
        验证 hook 不会因重复调而误清空.
        """
        cache, state_path, manifest_path, conn = cache_with_state
        manifest_path.write_text(json.dumps({"version": 7, "active_view": "v7"}))
        cache.ensure_table()
        _write_state_file(state_path, 7)
        cache.set("r-flow", {"a": 1}, {"v": "keep"})
        for i in range(5):
            result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
            assert result is False, f"第 {i+1} 次应 no-op, 但返回 {result}"
        # cache 仍 1 行
        count = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count == 1


# ─────────────────────────────────────────────────────────────
# 4. manifest 改了 → invalidate + 更新 state
# ─────────────────────────────────────────────────────────────
class TestChanged:
    def test_manifest_changed_invalidate(self, cache_with_state):
        """manifest v=3 → v=4 → hook 触发 invalidate + 更新 state.

        场景: 改 ratio/契约后, ETL 跑完 manifest v 升, uvicorn 重启.
        hook 检测到 state(3) ≠ current(4) → 清空 12 keys + 写 state=4.
        """
        cache, state_path, manifest_path, conn = cache_with_state
        # state 记录 v=3
        manifest_path.write_text(json.dumps({"version": 3, "active_view": "v3"}))
        cache.ensure_table()
        _write_state_file(state_path, 3)
        # 灌 12 行 (模拟 Sprint 14.5 留的 12 orphan keys)
        for i in range(12):
            cache.set("r-flow", {"i": i}, {"v": i})
        count_before = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count_before == 12
        # 模拟 ETL 跑完, manifest 升到 v=4
        manifest_path.write_text(json.dumps({"version": 4, "active_view": "v4"}))
        # 调 hook
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is True, "manifest 变化应返回 True (触发 invalidate)"
        # 12 行全清
        count_after = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count_after == 0, f"manifest 变化后 cache 应清空, 残留 {count_after} 行"
        # state 更新到 4
        state = json.loads(state_path.read_text())
        assert state["last_seen_manifest_version"] == 4

    def test_manifest_first_run_then_changed(self, cache_with_state):
        """完整周期: 首次跑 (state 缺失) → 第二次跑 (manifest 升) → 都正确."""
        cache, state_path, manifest_path, conn = cache_with_state
        # 第 1 次: manifest v=1, state 缺失
        manifest_path.write_text(json.dumps({"version": 1, "active_view": "v1"}))
        cache.ensure_table()
        for i in range(3):
            cache.set("r-flow", {"i": i}, {"v": i})
        r1 = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert r1 is True
        assert _read_state_file(state_path) == 1
        # 第 2 次: 同一个 hook call 立即调 (state=1, current=1) → no-op
        cache.set("r-flow", {"a": 1}, {"v": "fresh"})
        r2 = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert r2 is False
        # 第 3 次: manifest 升到 v=2
        manifest_path.write_text(json.dumps({"version": 2, "active_view": "v2"}))
        r3 = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert r3 is True
        assert _read_state_file(state_path) == 2
        # cache 表已清空
        count = conn.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
        assert count == 0


# ─────────────────────────────────────────────────────────────
# 5. Hook 失败不阻塞启动 (best-effort)
# ─────────────────────────────────────────────────────────────
class TestFailureResilience:
    def test_hook_state_path_unwritable_does_not_raise(self, cache_with_state, monkeypatch):
        """state 文件写失败 → hook 吞异常, 返回 False, 不抛."""
        cache, state_path, manifest_path, conn = cache_with_state
        manifest_path.write_text(json.dumps({"version": 1, "active_view": "v1"}))
        cache.ensure_table()
        # mock _write_state_file 抛异常
        def fail_write(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(
            "backend.services.rfm.cache._write_state_file",
            fail_write,
        )
        # 不应抛
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is False, "state 写失败应返回 False (best-effort, 不阻塞启动)"

    def test_hook_invalid_manifest_json_does_not_raise(self, cache_with_state):
        """manifest JSON 损坏 → hook 吞异常, 返回 False, 不抛.

        场景: manifest 写一半 crash, JSON 不完整. hook 不应阻塞 uvicorn 启动.
        _ManifestTracker.current_version() 已 swallow JSONDecodeError, 所以这个
        case 实际表现为 'manifest 缺失' (current_version 返回 None).
        """
        cache, state_path, manifest_path, conn = cache_with_state
        # 写损坏 JSON
        manifest_path.write_text("{broken json")
        # 不应抛
        result = check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        assert result is False, "manifest 损坏应返回 False (best-effort)"


# ─────────────────────────────────────────────────────────────
# 6. Hook 跟 _ManifestTracker 兼容: 启动后 cache.get() 仍正常工作
# ─────────────────────────────────────────────────────────────
class TestHookAfterGetCompat:
    def test_hook_then_get_works(self, cache_with_state):
        """hook 跑过后, 正常 cache.get() / set() 仍工作.

        验证: hook 不破坏 _ManifestTracker 状态, 启动后第一次 get() 仍按预期.
        """
        cache, state_path, manifest_path, conn = cache_with_state
        # 准备: manifest v=2, state=1 (旧), cache 表有数据
        manifest_path.write_text(json.dumps({"version": 2, "active_view": "v2"}))
        cache.ensure_table()
        _write_state_file(state_path, 1)
        for i in range(3):
            cache.set("r-flow", {"i": i}, {"v": i})
        # 调 hook → invalidate + state → 2
        check_manifest_version_and_invalidate(state_path=state_path, cache=cache)
        # 此时 cache 表空, _ManifestTracker._last_seen_version 应被 hook 同步到 2
        # (实际 hook 用 _manifest_tracker_singleton.current_version() 读,
        #  不改 _last_seen_version, 但 _ManifestTracker.check_and_invalidate 会在
        #  下次 get() 时检测到 last_seen=None → current=2 触发一次 invalidate
        #  (空表 no-op), 然后 last_seen=2)
        # 调 set + get 验证
        cache.set("r-flow", {"x": 1}, {"v": "new"})
        assert cache.get("r-flow", {"x": 1}) == {"v": "new"}


# ─────────────────────────────────────────────────────────────
# 7. Sprint 19 P2-4: etl_post_run_hook 测试
# 跟启动 hook 区别: 启动 hook 在 main.py lifespan startup 调,
# post-run hook 在 scripts/etl/cli.py main() 末尾调, 不依赖 uvicorn 重启
# ─────────────────────────────────────────────────────────────
class TestEtlPostRunHook:
    def test_post_run_hook_manifest_changed_invalidates(self, cache_with_state):
        """manifest version 变化 → post-run hook 触发 invalidate + 更新 state.

        模拟: 跑批前 state 记录 v=1, 跑批写 manifest v=2, 跑批末尾调 hook.
        预期: hook 返回 True, cache 表被清空, state 更新到 v=2.
        """
        from backend.services.rfm.cache import etl_post_run_hook

        cache, state_path, manifest_path, conn = cache_with_state
        # 准备: manifest v=2, state=1 (旧), cache 表有 3 行
        manifest_path.write_text(json.dumps({"version": 2, "active_view": "v2"}))
        _write_state_file(state_path, 1)
        for i in range(3):
            cache.set("r-flow", {"i": i}, {"v": i})
        assert cache.stats()["total"] == 3, "sanity: 3 cache rows"

        # 调 etl_post_run_hook (走默认 _default_state_path, 用 env 覆盖)
        import os
        old_env = os.environ.get("FQ_W5KV_STATE_PATH")
        os.environ["FQ_W5KV_STATE_PATH"] = str(state_path)
        try:
            result = etl_post_run_hook()
        finally:
            if old_env is None:
                os.environ.pop("FQ_W5KV_STATE_PATH", None)
            else:
                os.environ["FQ_W5KV_STATE_PATH"] = old_env

        assert result is True, "manifest 变化应返回 True (invalidate 触发)"
        assert cache.stats()["total"] == 0, "post-run hook 应清空 cache 表"
        last_seen = _read_state_file(state_path)
        assert last_seen == 2, f"state 应更新到 v=2, 实际 {last_seen}"

    def test_post_run_hook_manifest_unchanged_noop(self, cache_with_state):
        """manifest version 一致 → post-run hook 不 invalidate (no-op).

        模拟: 跑批前 state 已是 v=2, 跑批未升 version. 预期: hook 返回 False, cache 保留.
        """
        from backend.services.rfm.cache import etl_post_run_hook

        cache, state_path, manifest_path, conn = cache_with_state
        manifest_path.write_text(json.dumps({"version": 2, "active_view": "v2"}))
        _write_state_file(state_path, 2)  # state 跟 manifest 一致
        cache.set("r-flow", {"x": 1}, {"v": "keep"})

        import os
        old_env = os.environ.get("FQ_W5KV_STATE_PATH")
        os.environ["FQ_W5KV_STATE_PATH"] = str(state_path)
        try:
            result = etl_post_run_hook()
        finally:
            if old_env is None:
                os.environ.pop("FQ_W5KV_STATE_PATH", None)
            else:
                os.environ["FQ_W5KV_STATE_PATH"] = old_env

        assert result is False, "manifest 一致应返回 False (no-op)"
        assert cache.stats()["total"] == 1, "no-op 时 cache 应保留"

    def test_post_run_hook_no_manifest_noop(self, cache_with_state):
        """manifest 缺失 → post-run hook 不报错, 返回 False (跟启动 hook 一致).

        场景: 首次跑 ETL, manifest 还没写, post-run hook 调也安全.
        """
        from backend.services.rfm.cache import etl_post_run_hook

        cache, state_path, manifest_path, conn = cache_with_state
        if manifest_path.exists():
            manifest_path.unlink()
        cache.set("r-flow", {"x": 1}, {"v": "keep"})

        import os
        old_env = os.environ.get("FQ_W5KV_STATE_PATH")
        os.environ["FQ_W5KV_STATE_PATH"] = str(state_path)
        try:
            result = etl_post_run_hook()
        finally:
            if old_env is None:
                os.environ.pop("FQ_W5KV_STATE_PATH", None)
            else:
                os.environ["FQ_W5KV_STATE_PATH"] = old_env

        assert result is False, "manifest 缺失应返回 False (best-effort)"
        assert cache.stats()["total"] == 1, "manifest 缺失时 cache 应保留"

    def test_post_run_hook_exception_does_not_propagate(self, monkeypatch, cache_with_state):
        """hook 内部异常被吞, 不抛 (跟启动 hook 同 best-effort 契约).

        场景: post-run hook 调 check_manifest_version_and_invalidate 时
        抛异常 (e.g. DuckDB connection 故障). post-run hook 应 catch + log + 返 False.
        """
        from backend.services.rfm import cache as cache_mod

        def fail_invalidate(*args, **kwargs):
            raise RuntimeError("simulated DuckDB fault")

        monkeypatch.setattr(cache_mod, "check_manifest_version_and_invalidate", fail_invalidate)

        # 不应抛
        result = cache_mod.etl_post_run_hook()
        assert result is False, "异常应被吞, 返回 False"
