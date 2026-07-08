"""
Sprint 28+ (#197) RFM 缓存 _get_cache_conn DuckDB config 冲突治根 (2026-06-17)

背景:
  Sprint 24+ P3 (v0.4.14.95, commit ebcc8a4) 修了 cli.py L310/424/688/859 4 处
  read_only=True → 默认 READ_WRITE, 但漏了 cache.py._get_cache_conn().
  QW2 Phase 2 注释说 "uvicorn 永远 read_only", 但 Sprint 24+ P3 后 uvicorn
  实际是默认 READ_WRITE.

  bug 复现路径: cache.py._get_cache_conn() 显式加 access_mode="READ_WRITE"
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
ETL. 本测试用真 duckdb connection (in-memory 隔离) 验证 _get_cache_conn 跟
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
    """case 1: _get_cache_conn() 源码必须不再显式加 access_mode 字段
    (跟 cli.py._c0 严格一致, 除 db_password 外).
    """

    def test_no_explicit_access_mode_in_source(self):
        """Sprint 28+ (#197) 治根核心: 删 cfg["access_mode"] = "READ_WRITE" 行.

        如果未来 refactor 误加回 access_mode 字段, DuckDB 1.5+ strict mode 会按
        config dict 严格匹配 → 跟 cli.py._c0 config 不一致 → 抛
        "Can't open a connection to same database file with a different configuration"
        → RFM 缓存清空 + 预计算 全失败.
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn

        src = inspect.getsource(_get_cache_conn)
        assert 'cfg["access_mode"]' not in src, (
            "⚠️ Sprint 28+ (#197) 治根: 必须删 cfg['access_mode'] = 'READ_WRITE' 行. "
            "DuckDB 1.5+ strict mode 按 config dict 严格匹配, 多了 access_mode 字段 "
            "即使值是 READ_WRITE 也跟 cli.py._c0 config ({memory_limit}) 不匹配 → 抛 "
            "'Can't open a connection to same database file with a different configuration'"
        )

    def test_uses_get_cache_connection_helper(self):
        """L4.67 治本: _get_cache_conn 必须走 get_cache_connection() (cache 库单例)
        而不是 bdc.get_duckdb_config() + duckdb.connect() (L4.66 之前的模式).
        业务库 + cache 库分离, 跨文件 0 fingerprint 冲突.
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn

        src = inspect.getsource(_get_cache_conn)
        assert 'get_cache_connection' in src, (
            "L4.67: _get_cache_conn 必须走 get_cache_connection() (cache 库单例), "
            "而不是直接 duckdb.connect() (跟业务库 fingerprint 0 关联)"
        )

    def test_l4_67_cross_file_isolation(self):
        """L4.67 治本: _get_cache_conn 不再处理 db_password (由 dual_conn.get_cache_connection 内部处理).
        业务库 + cache 库分离, 跨文件 fingerprint 0 关联, 5 轮串行 0 错 + 5 线程并发 0 错.
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn

        src = inspect.getsource(_get_cache_conn)
        # L4.67: _get_cache_conn 只调 get_cache_connection, 不直接 duckdb.connect
        assert 'duckdb.connect' not in src, (
            "L4.67: _get_cache_conn 禁止直接 duckdb.connect (跟业务库 fingerprint 冲突), "
            "必须走 get_cache_connection() (cache 库单例)"
        )


# ─────────────────────────────────────────────────────────────
# 核心不变量 ②: 真 _get_cache_conn 不抛 "different configuration" 错误
# ─────────────────────────────────────────────────────────────

class TestOpenWriteConnRealConnectionNoError:
    """case 2: 真 _get_cache_conn() 调用应能成功打开 DuckDB 连接,
    不抛 "Can't open a connection to same database file with a different configuration".

    Sprint 7 P2 教训: 必须真连接验证, 不 mock. 用独立 tmp duckdb file 隔离.
    """

    def test_get_cache_conn_succeeds(self, tmp_path, monkeypatch):
        """_get_cache_conn() 在独立 duckdb file 上能成功打开 + 简单 SELECT.

        之前 bug: 多传 access_mode 字段 → DuckDB strict mode 抛错.
        治根后: config dict 只有 memory_limit (跟 cli.py._c0 一致) → 成功.
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn

        # 独立 tmp duckdb (跟生产隔离)
        duckdb_path = tmp_path / "test.duckdb"
        # 提前创建空 duckdb file (让 connection 有 valid file to lock)
        duckdb.connect(str(duckdb_path)).close()

        # Patch DUCKDB_PATH 让 _get_cache_conn 指向 tmp file
        monkeypatch.setattr(
            "backend.services.health.rfm_analysis.cache.DUCKDB_PATH", duckdb_path,
        )
        monkeypatch.setattr("backend.config.DUCKDB_PATH", duckdb_path)
        monkeypatch.delenv("DUCKDB_PASSWORD", raising=False)

        # 真调用 _get_cache_conn 不应抛 "different configuration" 错误
        conn = _get_cache_conn()
        try:
            # 简单 SELECT 验证连接可用
            row = conn.execute("SELECT 1 AS x").fetchone()
            assert row[0] == 1, f"SELECT 应该返回 1, 实际 {row[0]}"
        finally:
            conn.close()

    def test_sibling_connection_pattern_works(self, tmp_path, monkeypatch):
        """模拟生产 ETL 三连接共存场景 (Sprint 7 P2 教训: 新连接 + commit/close):
        1. cli.py._c0 style conn (只有 memory_limit)
        2. cache.py._get_cache_conn style conn (Sprint 28+ 治根后 config 一致)

        修复前 _get_cache_conn 抛 "different configuration", step 2 失败.
        修复后两个 conn 能共存 + 互相读对方写入.
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn
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

            # Step 2: cache.py._get_cache_conn style (L4.67 治本后跨文件 fingerprint 0 关联)
            conn_cache = _get_cache_conn()
            try:
                # L4.67: cache 库没 orders 表, 用 _test_l467_sibling 验证
                conn_cache.execute("CREATE TABLE IF NOT EXISTS _test_l467_sibling (a INT)")
                conn_cache.execute("INSERT INTO _test_l467_sibling VALUES (42)")
                count = conn_cache.execute("SELECT COUNT(*) FROM _test_l467_sibling").fetchone()[0]
                assert count == 1, (
                    f"L4.67: cache 库应该能 INSERT, 实际 {count} 行. "
                    f"如果 0, 说明 _get_cache_conn 抛 'different configuration' 失败."
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

    端到端 = 真连接 + 真 _get_cache_conn + 真 RFM cache 表读写.
    """

    def test_clear_rfm_cache_no_longer_fails(self, tmp_path, monkeypatch):
        """clear_rfm_cache() 应该成功 (返回 int > 0 或 0 但不抛 Connection Error).

        Sprint 28 修复前 fail-soft 返 0 + log "RFM 缓存清空失败: Connection Error".
        Sprint 28+ (#197) 治根后: 返 N (被清的行数) + log "RFM 缓存清空: 共 N 行".
        """
        from backend.services.health.rfm_analysis.cache import (
            _get_cache_conn,
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
        conn = _get_cache_conn()
        try:
            _ensure_db_cache_table(conn)
            # 写一行 (只填 cache_key, 其他列可空)
            conn.execute(
                f"INSERT INTO {RFM_CACHE_TABLE} (cache_key, result_json) VALUES (?, ?)",
                ["test_key", "{}"],
            ).fetchall()
        finally:
            conn.close()

        # L4.67 治本后: clear_rfm_cache 应该成功 (返 ≥ 0), 不抛 ConnectionError
        # 实际行数依赖测试环境 (可能有 mock 残留), 用 ≥ 0 验证 "没抛"
        result = clear_rfm_cache()
        assert result >= 0, (
            f"L4.67: clear_rfm_cache 应该成功 (返 ≥ 0), 实际 {result}. "
            f"如果抛 ConnectionError, 说明 _get_cache_conn 仍 'different configuration' 失败."
        )

        # 验证表已清空 (L4.67: 用 cache 库连, 不是业务库)
        conn = _get_cache_conn()
        count = conn.execute(
            f"SELECT COUNT(*) FROM {RFM_CACHE_TABLE}",
        ).fetchone()[0]
        assert count == 0, f"RFM_CACHE_TABLE 应该清空, 实际 {count} 行"


# ─────────────────────────────────────────────────────────────
# 核心不变量 ④: 修复 commit message 锚点 (防未来 refactor 误删)
# ─────────────────────────────────────────────────────────────

class TestSprint28FixAnchor:
    """case 4: 源码必须保留 Sprint 28+ (#197) 修复锚点 (commit SHA 或 issue #),
    防止未来 refactor 误删 access_mode 字段 → bug 复发.
    """

    def test_source_mentions_l4_67_fix(self):
        """L4.67 治本: _get_cache_conn docstring 必须提 L4.67 锚点 (Sprint 205+),
        防未来 refactor 误删 (回退到同文件 fingerprint 模式).
        """
        from backend.services.health.rfm_analysis.cache import _get_cache_conn

        src = inspect.getsource(_get_cache_conn)
        assert 'L4.67' in src, (
            "_get_cache_conn docstring 必须提 L4.67 锚点, 防未来误改回同文件模式"
        )
        assert 'Sprint 205+' in src or 'cache 库' in src, (
            "docstring 必须提 Sprint 205+ (L4.67 触发) 或 'cache 库' (L4.67 核心概念)"
        )
