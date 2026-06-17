"""
Sprint 28+ (#197) RFM 缓存 _open_write_conn DuckDB config 冲突治根 (2026-06-17)

背景:
  Sprint 24+ P3 (v0.4.14.95, commit ebcc8a4) 修了 cli.py L310/424/688/859 4 处
  read_only=True → 默认 READ_WRITE, 但漏了 cache.py._open_write_conn().
  QW2 Phase 2 注释说 "uvicorn 永远 read_only", 但 Sprint 24+ P3 后 uvicorn
  实际是默认 READ_WRITE.

  bug 复现路径: cache.py._open_write_conn() 显式加 access_mode="READ_WRITE"
  字段 → DuckDB 1.5+ strict mode 判定本 conn config ({memory_limit, access_mode})
  ≠ cli.py sibling conn config ({memory_limit}) → 抛 "Can't open a connection
  to same database file with a different configuration" → RFM 缓存清空 +
  RFM 预计算 失败, 但 ETL exit 0 (fail-soft).

  治根: 跟 cli.py._c0 严格一致, 删 cfg["access_mode"] = "READ_WRITE" 行.
  DuckDB 默认 access_mode=READ_WRITE, 不传字段时 config dict 跟 cli.py 匹配.

Sprint 11 S11-3 + Sprint 24+ P3 + Sprint 28+ (#197) 同根因第三处:
  - Sprint 11: config dict 缺省 (memory_limit 不一致)
  - Sprint 24+ P3: access_mode 不一致 (read_only=True)
  - Sprint 28+ (#197): access_mode 字段多传 (即使值都是 READ_WRITE, strict mode
    按 config dict 严格匹配)

Sprint 7 P2 教训: 单连接测试不能推广生产, 必须新连接 + commit/close 模式模拟生产
ETL. 本测试用真 duckdb connection (in-memory 隔离) 验证 _open_write_conn 跟
cli.py sibling style config 严格一致后, 真连接不抛错.
"""
import inspect
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# 核心不变量 ①: 源码 verify — access_mode 字段被删
# ─────────────────────────────────────────────────────────────

class TestOpenWriteConnConfigMatchesCliStyle:
    """case 1: _open_write_conn() 源码必须不再显式加 access_mode 字段
    (跟 cli.py._c0 严格一致, 除 db_password 外).
    """

    def test_no_explicit_access_mode_in_source(self):
        """Sprint 28+ (#197) 治根核心: 删 cfg["access_mode"] = "READ_WRITE" 行.

        如果未来 refactor 误加回 access_mode 字段, DuckDB 1.5+ strict mode 会按
        config dict 严格匹配 → 跟 cli.py._c0 config 不一致 → 抛
        "Can't open a connection to same database file with a different configuration"
        → RFM 缓存清空 + 预计算 全失败.
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn

        src = inspect.getsource(_open_write_conn)
        assert 'cfg["access_mode"]' not in src, (
            "⚠️ Sprint 28+ (#197) 治根: 必须删 cfg['access_mode'] = 'READ_WRITE' 行. "
            "DuckDB 1.5+ strict mode 按 config dict 严格匹配, 多了 access_mode 字段 "
            "即使值是 READ_WRITE 也跟 cli.py._c0 config ({memory_limit}) 不匹配 → 抛 "
            "'Can't open a connection to same database file with a different configuration'"
        )

    def test_uses_get_duckdb_config_helper(self):
        """_open_write_conn 必须用 bdc.get_duckdb_config() 拿基础 config
        (跟 cli.py._c0 / pipeline.py 同模式: 走 backend.db.connection helper
        而不是硬编码 memory_limit).
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn

        src = inspect.getsource(_open_write_conn)
        assert 'bdc.get_duckdb_config()' in src, (
            "_open_write_conn 应该用 bdc.get_duckdb_config() 拿基础 config "
            "(跟 cli.py._c0 模式一致: 走 backend.db.connection helper, 不硬编码 memory_limit)"
        )

    def test_supports_db_password_env_var(self):
        """db_password env var 支持必须保留 (跟 cli.py sibling 同模式, Sprint 24 P3 同期).
        没有 password env 时 config 只有 memory_limit, 跟 cli.py._c0 完全一致.
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn

        src = inspect.getsource(_open_write_conn)
        assert 'db_password' in src, (
            "_open_write_conn 必须支持 db_password env var (跟 cli.py sibling 同模式)"
        )
        assert 'DUCKDB_PASSWORD' in src, (
            "_open_write_conn 必须读 DUCKDB_PASSWORD env var"
        )


# ─────────────────────────────────────────────────────────────
# 核心不变量 ②: 真 _open_write_conn 不抛 "different configuration" 错误
# ─────────────────────────────────────────────────────────────

class TestOpenWriteConnRealConnectionNoError:
    """case 2: 真 _open_write_conn() 调用应能成功打开 DuckDB 连接,
    不抛 "Can't open a connection to same database file with a different configuration".

    Sprint 7 P2 教训: 必须真连接验证, 不 mock. 用独立 tmp duckdb file 隔离.
    """

    def test_open_write_conn_succeeds(self, tmp_path, monkeypatch):
        """_open_write_conn() 在独立 duckdb file 上能成功打开 + 简单 SELECT.

        之前 bug: 多传 access_mode 字段 → DuckDB strict mode 抛错.
        治根后: config dict 只有 memory_limit (跟 cli.py._c0 一致) → 成功.
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn

        # 独立 tmp duckdb (跟生产隔离)
        duckdb_path = tmp_path / "test.duckdb"
        # 提前创建空 duckdb file (让 connection 有 valid file to lock)
        duckdb.connect(str(duckdb_path)).close()

        # Patch DUCKDB_PATH 让 _open_write_conn 指向 tmp file
        monkeypatch.setattr(
            "backend.services.health.rfm_analysis.cache.DUCKDB_PATH", duckdb_path,
        )
        monkeypatch.setattr("backend.config.DUCKDB_PATH", duckdb_path)
        monkeypatch.delenv("DUCKDB_PASSWORD", raising=False)

        # 真调用 _open_write_conn 不应抛 "different configuration" 错误
        conn = _open_write_conn()
        try:
            # 简单 SELECT 验证连接可用
            row = conn.execute("SELECT 1 AS x").fetchone()
            assert row[0] == 1, f"SELECT 应该返回 1, 实际 {row[0]}"
        finally:
            conn.close()

    def test_sibling_connection_pattern_works(self, tmp_path, monkeypatch):
        """模拟生产 ETL 三连接共存场景 (Sprint 7 P2 教训: 新连接 + commit/close):
        1. cli.py._c0 style conn (只有 memory_limit)
        2. cache.py._open_write_conn style conn (Sprint 28+ 治根后 config 一致)

        修复前 _open_write_conn 抛 "different configuration", step 2 失败.
        修复后两个 conn 能共存 + 互相读对方写入.
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn
        from backend.config import DUCKDB_MEMORY_LIMIT

        duckdb_path = tmp_path / "test.duckdb"
        duckdb.connect(str(duckdb_path)).close()
        monkeypatch.setattr(
            "backend.services.health.rfm_analysis.cache.DUCKDB_PATH", duckdb_path,
        )
        monkeypatch.setattr("backend.config.DUCKDB_PATH", duckdb_path)
        monkeypatch.delenv("DUCKDB_PASSWORD", raising=False)

        # Step 1: cli.py._c0 style (只有 memory_limit)
        conn_cli = duckdb.connect(
            str(duckdb_path), config={"memory_limit": DUCKDB_MEMORY_LIMIT},
        )
        try:
            conn_cli.execute("CREATE TABLE orders (x INT)").fetchall()

            # Step 2: cache.py._open_write_conn style (Sprint 28+ 治根后 config 一致)
            conn_cache = _open_write_conn()
            try:
                # 两个 conn 共存, 都能读写
                conn_cache.execute("INSERT INTO orders VALUES (42)").fetchall()
                count = conn_cli.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                assert count == 1, (
                    f"cli conn 应该看到 cache conn 写入的 1 行, 实际 {count}. "
                    f"如果 0, 说明 _open_write_conn 抛 'different configuration' 失败."
                )
            finally:
                conn_cache.close()
        finally:
            conn_cli.close()


# ─────────────────────────────────────────────────────────────
# 核心不变量 ③: clear_rfm_cache() + precompute_rfm_cache() 端到端走通
# ─────────────────────────────────────────────────────────────

class TestClearRfmCacheEndToEnd:
    """case 3: Sprint 28+ (#197) 治根后, clear_rfm_cache() + precompute_rfm_cache()
    端到端走通. Sprint 28 修复前 RFM 缓存清空 + 预计算 fail (Connection Error).

    端到端 = 真连接 + 真 _open_write_conn + 真 RFM cache 表读写.
    """

    def test_clear_rfm_cache_no_longer_fails(self, tmp_path, monkeypatch):
        """clear_rfm_cache() 应该成功 (返回 int > 0 或 0 但不抛 Connection Error).

        Sprint 28 修复前 fail-soft 返 0 + log "RFM 缓存清空失败: Connection Error".
        Sprint 28+ (#197) 治根后: 返 N (被清的行数) + log "RFM 缓存清空: 共 N 行".
        """
        from backend.services.health.rfm_analysis.cache import (
            _open_write_conn,
            _ensure_db_cache_table,
            clear_rfm_cache,
            RFM_CACHE_TABLE,
        )

        duckdb_path = tmp_path / "test.duckdb"
        duckdb.connect(str(duckdb_path)).close()
        monkeypatch.setattr(
            "backend.services.health.rfm_analysis.cache.DUCKDB_PATH", duckdb_path,
        )
        monkeypatch.setattr("backend.config.DUCKDB_PATH", duckdb_path)
        monkeypatch.delenv("DUCKDB_PASSWORD", raising=False)

        # 用 _ensure_db_cache_table 建完整 schema (避免手建缺列)
        conn = _open_write_conn()
        try:
            _ensure_db_cache_table(conn)
            # 写一行 (只填 cache_key, 其他列可空)
            conn.execute(
                f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                ["test_key", "{}"],
            ).fetchall()
        finally:
            conn.close()

        # Sprint 28+ (#197) 治根后: clear_rfm_cache 应该返回 1 (清 1 行), 不抛
        # 之前 fail: 抛 ConnectionError 或返 0 + log error
        result = clear_rfm_cache()
        assert result == 1, (
            f"clear_rfm_cache 应该返回 1 (清 1 行), 实际 {result}. "
            f"如果 0 + 之前 log 'RFM 缓存清空失败: Connection Error', "
            f"说明 _open_write_conn 仍抛 'different configuration'."
        )

        # 验证表已清空
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}",
            ).fetchone()[0]
            assert count == 0, f"RFM_CACHE_TABLE 应该清空, 实际 {count} 行"
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────
# 核心不变量 ④: 修复 commit message 锚点 (防未来 refactor 误删)
# ─────────────────────────────────────────────────────────────

class TestSprint28FixAnchor:
    """case 4: 源码必须保留 Sprint 28+ (#197) 修复锚点 (commit SHA 或 issue #),
    防止未来 refactor 误删 access_mode 字段 → bug 复发.
    """

    def test_source_mentions_sprint28_fix(self):
        """_open_write_conn docstring 必须提 Sprint 28+ 修复 (跟 cli.py._c0
        Sprint 24+ P3 锚点一致模式), 防未来误删.
        """
        from backend.services.health.rfm_analysis.cache import _open_write_conn

        src = inspect.getsource(_open_write_conn)
        assert 'Sprint 28+' in src, (
            "_open_write_conn docstring 必须提 Sprint 28+ 修复锚点, "
            "跟 cli.py._c0 Sprint 24+ P3 锚点一致, 防未来误删 access_mode 字段"
        )
        assert '#197' in src or '197' in src, (
            "docstring 必须提 issue #197 (TECH-DEBT.md 债号), 防止未来 refactor 误删"
        )
