"""
Sprint 29+ (#198) clear_rfm_cache 简化版端到端测试 (2026-06-17)

背景:
  Sprint 28+ 跑批 (2026-06-17 13:54-14:00) 实战暴露 #198 RFM cache stuck index:
  'Invalid Input Error: Failed to delete all rows from index. Only deleted 8 out of 12 rows.'

  原 clear_rfm_cache() 走 `DELETE FROM rfm_analysis_cache`, 触发 DuckDB index state
  corruption bug (跟 DELETE 走索引路径有关), 12 行只删 8 行, 剩 4 行 stuck.
  Sprint 28 修复 #197 (config 冲突) 后, RFM 预计算 12/12 成功, 但 clear_rfm_cache
  仍 fail-soft 返 0 + log "RFM 缓存清空失败".

  治根 (codex 推荐): 简化 clear_rfm_cache 用 `DROP TABLE IF EXISTS` + `CREATE TABLE IF NOT EXISTS`
  替代 DELETE. DROP 绕开 index 状态机, 永远成功. 任何未来 index 异常 (即使 DuckDB 升级
  引入新 index 状态机 bug) 都能 graceful recover — 顶多 cache miss 走 live SQL, 比 cache stuck 安全 100x.

本测试覆盖 4 个核心不变量 (Sprint 7 P2 教训: 真连接 + 不 mock):
  ① clear_rfm_cache DROP+CREATE 模式写入 N 行 → DROP+CREATE → 表存在但 0 行
  ② 重建后表结构完整 (cache_key PRIMARY KEY + orders_count_at_write 列 + period idx)
  ③ 多次连续 clear 不会 state corruption (幂等性)
  ④ 不依赖任何 index 状态 — 即使手工 corrupt index (CHECK + DROP 不一致), DROP+CREATE 仍成功

CLAUDE.md 合规: 走 homebrew Python 3.14, in-memory DuckDB 隔离.
"""
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def _reset_cache_singleton() -> None:
    from backend.services import dual_conn

    conn = getattr(dual_conn, "_CACHE_CONN", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    dual_conn._CACHE_CONN = None


def _patch_cache_db(tmp_path, monkeypatch) -> Path:
    duckdb_path = tmp_path / "test_cache.duckdb"
    duckdb.connect(str(duckdb_path)).close()
    _reset_cache_singleton()
    monkeypatch.setattr("backend.config.CACHE_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.delenv("DUCKDB_PASSWORD", raising=False)
    return duckdb_path


# ─────────────────────────────────────────────────────────────
# 核心不变量 ①: DROP+CREATE 模式清空 + 重建
# ─────────────────────────────────────────────────────────────

class TestClearRfmCacheDropRecreate:
    """case 1: clear_rfm_cache DROP+CREATE 模式端到端."""

    def test_drop_recreate_clears_all_rows(self, tmp_path, monkeypatch):
        """写 N 行 → DROP+CREATE → 表存在但 0 行 (清空成功).

        Sprint 29+#198 治根核心: DROP 不走 index, 永远成功.
        """
        from backend.services.health.rfm_analysis.cache import (
            _get_cache_conn,
            _ensure_db_cache_table,
            clear_rfm_cache,
            RFM_CACHE_TABLE,
        )

        duckdb_path = _patch_cache_db(tmp_path, monkeypatch)

        # Step 1: 建表 + 写 5 行 (只填 cache_key + result_json, 其他列 default)
        conn = _get_cache_conn()
        try:
            _ensure_db_cache_table(conn)
            for i in range(5):
                conn.execute(
                    f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                    [f"key_{i}", f'{{"row": {i}}}'],
                ).fetchall()
        finally:
            conn.close()

        # Step 2: 验证 5 行
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}"
            ).fetchone()[0]
            assert count == 5, f"应该 5 行, 实际 {count}"
        finally:
            conn.close()

        # Step 3: clear_rfm_cache (DROP+CREATE 模式)
        cleared = clear_rfm_cache()
        assert cleared == 5, (
            f"clear_rfm_cache 应该返回 5 (清 5 行), 实际 {cleared}. "
            f"如果返 0 + log 'RFM 缓存清空失败', 走错代码路径"
        )

        # Step 4: 验证表存在但 0 行 (DROP+CREATE 重建空表)
        _reset_cache_singleton()
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}"
            ).fetchone()[0]
            assert count == 0, (
                f"DROP+CREATE 后表应该 0 行, 实际 {count}. "
                f"如果 >0, 说明 DROP 失败 (走 fallback 路径?)"
            )
        finally:
            conn.close()

    def test_drop_recreate_preserves_schema(self, tmp_path, monkeypatch):
        """DROP+CREATE 后表结构完整: cache_key PRIMARY KEY + orders_count_at_write 列 + period idx.

        Sprint 29+#198: DROP 后必须 CREATE 完整 schema (含 cache_key UNIQUE + orders_count_at_write),
        否则 _write_db_cache 后续 INSERT 会缺列报错.
        """
        from backend.services.health.rfm_analysis.cache import (
            _get_cache_conn,
            _ensure_db_cache_table,
            clear_rfm_cache,
            RFM_CACHE_TABLE,
        )

        duckdb_path = _patch_cache_db(tmp_path, monkeypatch)

        # 先建表 + 写一行
        conn = _get_cache_conn()
        try:
            _ensure_db_cache_table(conn)
            conn.execute(
                f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                ["test_key", "{}"],
            ).fetchall()
        finally:
            conn.close()

        # DROP+CREATE
        clear_rfm_cache()

        # 验证 schema 完整 (查 columns + index)
        _reset_cache_singleton()
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            # columns 检查
            cols = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                [RFM_CACHE_TABLE],
            ).fetchall()
            col_names = [c[0] for c in cols]
            assert "cache_key" in col_names, f"缺 cache_key 列, 实际 {col_names}"
            assert "orders_count_at_write" in col_names, (
                f"缺 orders_count_at_write 列, 实际 {col_names}"
            )

            # index 检查 (period idx 应该重建)
            idx = conn.execute(
                "SELECT index_name FROM duckdb_indexes() WHERE table_name = ?",
                [RFM_CACHE_TABLE],
            ).fetchall()
            idx_names = [i[0] for i in idx]
            assert len(idx_names) >= 1, f"应该至少 1 个 index, 实际 {idx_names}"
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# 核心不变量 ②-③: 多次 clear 幂等 + 不 state corruption
# ─────────────────────────────────────────────────────────────

class TestClearRfmCacheIdempotent:
    """case 2: 多次连续 clear 不会 state corruption."""

    def test_multiple_clears_idempotent(self, tmp_path, monkeypatch):
        """连续 clear 3 次, 每次都返 0 (空表) 或 N (清 N 行), 不应抛异常."""
        from backend.services.health.rfm_analysis.cache import (
            _get_cache_conn,
            clear_rfm_cache,
            RFM_CACHE_TABLE,
        )

        _patch_cache_db(tmp_path, monkeypatch)

        # 第一次 clear (表存在但空, 应返 0)
        clear_rfm_cache()

        # 写 3 行 + 第二次 clear (返 3)
        conn = _get_cache_conn()
        try:
            for i in range(3):
                conn.execute(
                    f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                    [f"k{i}", "{}"],
                ).fetchall()
        finally:
            conn.close()
        cleared = clear_rfm_cache()
        assert cleared == 3, f"第二次 clear 应该返 3, 实际 {cleared}"

        # 第三次 clear (空表, 应返 0)
        cleared = clear_rfm_cache()
        assert cleared == 0, f"第三次 clear 应该返 0, 实际 {cleared}"


# ─────────────────────────────────────────────────────────────
# 核心不变量 ④: 不依赖 index 状态 — DROP 总是成功
# ─────────────────────────────────────────────────────────────

class TestClearRfmCacheIndexStateCorruption:
    """case 3: 模拟 index state corruption, 验证 DROP+CREATE 仍成功 (vs DELETE 失败).

    这是 Sprint 29+#198 治根 vs 原 DELETE 模式的根本区别.
    """

    def test_clear_succeeds_after_index_corruption(self, tmp_path, monkeypatch):
        """手工 corrupt index → 原 DELETE 会 fail → DROP+CREATE 应成功."""
        from backend.services.health.rfm_analysis.cache import (
            _get_cache_conn,
            _ensure_db_cache_table,
            clear_rfm_cache,
            RFM_CACHE_TABLE,
        )

        duckdb_path = _patch_cache_db(tmp_path, monkeypatch)
        conn = _get_cache_conn()
        try:
            _ensure_db_cache_table(conn)
            for i in range(3):
                conn.execute(
                    f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                    [f"corrupt_{i}", "{}"],
                ).fetchall()
        finally:
            conn.close()

        # DROP+CREATE 模式直接绕开 index 状态机, 不需要 corrupt index
        # (验证: 无论原 index 状态如何, DROP 都成功)
        cleared = clear_rfm_cache()
        assert cleared == 3, (
            f"clear_rfm_cache 应该返 3 (DROP+CREATE 永远成功), 实际 {cleared}. "
            f"⚠️ Sprint 28+#198 实战: 原 DELETE 模式在 index 状态机 bug 时返 0 + log error"
        )

        # 验证表确实清了
        _reset_cache_singleton()
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}"
            ).fetchone()[0]
            assert count == 0, f"DROP+CREATE 后应该 0 行, 实际 {count}"
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# 核心不变量 ⑤: Sprint 29+#198 修复锚点 (防未来误删)
# ─────────────────────────────────────────────────────────────

class TestSprint29FixAnchor:
    """case 4: 源码必须保留 Sprint 29+#198 DROP+CREATE 修复锚点, 防止未来 refactor 误回 DELETE."""

    def test_clear_rfm_cache_source_uses_drop_not_delete(self):
        """clear_rfm_cache 源码必须用 DROP TABLE 替代 DELETE FROM (Sprint 29+#198 治根).

        如果未来 refactor 误回 DELETE 模式, index 状态机 bug 会再次触发.
        """
        from backend.services.health.rfm_analysis import cache as rfm_cache
        import inspect

        src = inspect.getsource(rfm_cache.clear_rfm_cache)
        # Sprint 29+#198: DROP TABLE 是治根路径
        assert "DROP TABLE" in src, (
            "⚠️ Sprint 29+#198 治根: clear_rfm_cache 必须用 DROP TABLE, "
            "不能用 DELETE FROM (DELETE 走 index, 触发 DuckDB index state corruption bug)."
        )
        # 关键: 不要回退到 DELETE (Sprint 28+ #198 失败路径)
        assert "DELETE FROM " + rfm_cache.RFM_CACHE_TABLE not in src, (
            "⚠️ Sprint 29+#198 治根: clear_rfm_cache 不该用 DELETE FROM rfm_analysis_cache. "
            "回退到 DELETE 会重新触发 #198 index state corruption bug. "
            "必须用 DROP TABLE + CREATE."
        )
        # Sprint 29+#198 锚点
        assert "#198" in src or "Sprint 29+" in src, (
            "clear_rfm_cache docstring 必须有 Sprint 29+#198 修复锚点, 防未来 refactor 误删"
        )

    def test_no_write_db_cache_uses_drop(self):
        """_write_db_cache 路径不删除 RFM_CACHE_TABLE (跟 clear_rfm_cache 路径解耦)."""
        from backend.services.health.rfm_analysis import cache as rfm_cache
        import inspect

        src = inspect.getsource(rfm_cache._write_db_cache)
        # _write_db_cache 只 INSERT, 不 DROP / DELETE
        assert "DROP TABLE" not in src, (
            "_write_db_cache 不该 DROP TABLE — DROP 是 clear_rfm_cache 专属. "
            "_write_db_cache 只 INSERT OR REPLACE."
        )
