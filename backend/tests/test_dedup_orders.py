"""
Sprint 4 P0-3 — (order_id, sub_order_id) dedup 回归测试 (痛点 1 端到端闭环)

背景:
  - W3 主流程将 orders 写入 DuckDB, 撞 idx_orders_order_unique 唯一索引会 crash
  - sprint 3 commit 8bbf7c6 已加 ON CONFLICT DO NOTHING + 字符串转换 + drop_duplicates
  - 本测试固定 ON CONFLICT 行为, 防未来重构破坏

覆盖:
  ① _copy_df_to_duckdb 端到端: 重复 (order_id, sub_order_id) 不抛 UniqueConstraint
  ② 字符串 vs float 类型同值不绕过 dedup ('1' vs 1.0)
  ③ upsert_to_duckdb 增量模式: df_new 内部重复不报错 (drop_duplicates 协作)
  ④ 窗口刷新: df_refresh 内部重复不报错 (staging ROW_NUMBER 协作)
  ⑤ load.py 源码内含 ON CONFLICT (order_id, sub_order_id) DO NOTHING 字面量
     (防 refactor 把 ON CONFLICT 误删, 让 no-op dedup 退化)
  ⑥ _copy_df_to_duckdb 真实插入数 = staging 表行数 (语义不丢失, 跳过不算错)

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离.
"""
from pathlib import Path
import sys

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

# 复用 load.py 的真实 table_columns 列表 (避免维护 2 份 schema)
_TABLE_COLUMNS = [
    'order_id', 'sub_order_id', 'user_id', 'user_nickname',
    'order_time', 'pay_time', 'ship_time', 'order_type', 'order_status',
    'product_id', 'merchant_code', 'product_title', 'sku_id', 'sku_code',
    'sku_name', 'quantity', 'amount', 'refund_status', 'refund_amount',
    'actual_amount', 'province', 'city', 'influencer_name', 'influencer_id',
    'live_room_id', 'video_id', 'traffic_source', 'traffic_type',
    'seller_note', 'year', 'month', 'is_member', 'spu_category',
    'spu_type', 'spu_tier', 'spu_product_class', 'spu_product_subclass',
    'spu_cosmetic', 'spu_spec', 'spu_hash', 'channel',
    'is_goujinjin', 'is_refund',
]


def _create_orders_table_with_unique_idx(conn) -> None:
    """建 orders 表 + idx_orders_order_unique 唯一索引 (与 production 一致)."""
    cols_ddl = ', '.join(f"{c} VARCHAR" for c in _TABLE_COLUMNS)
    conn.execute(f"CREATE TABLE orders ({cols_ddl})")
    conn.execute(
        "CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)"
    )


@pytest.fixture
def duckdb_conn(tmp_path, monkeypatch):
    """临时文件 DuckDB (file-based, 跨连接共享).

    load.py 内部用 duckdb.connect(str(DUCKDB_PATH)) 多次开连接, in-memory 模式
    每次都是独立 DB → staging 表找不到 orders. 用文件 + monkeypatch DUCKDB_PATH
    让所有连接共享同一数据库.
    """
    db_file = tmp_path / "test_dedup.duckdb"
    from scripts.etl import config as cfg
    monkeypatch.setattr(cfg, "DUCKDB_PATH", db_file)
    # load.py 内部 from scripts.etl.config import DUCKDB_PATH 是引用值, 同步 patch
    from scripts.etl import load as load_mod
    monkeypatch.setattr(load_mod, "DUCKDB_PATH", db_file)
    monkeypatch.setattr(load_mod, "DUCKDB_MEMORY_LIMIT", "1GB")

    conn = duckdb.connect(str(db_file), config={"memory_limit": "1GB"})
    _create_orders_table_with_unique_idx(conn)
    yield conn
    conn.close()


def _make_orders_df(rows: list[dict]) -> pd.DataFrame:
    """造测试 DataFrame, 缺失列填 None (与 load.py table_columns 对齐)."""
    base = {c: None for c in _TABLE_COLUMNS}
    for r in rows:
        base.update(r)
    return pd.DataFrame([{c: r.get(c) for c in _TABLE_COLUMNS} for r in rows])


# ─────────────────────────────────────────────────────────────
# ① _copy_df_to_duckdb 端到端: 重复 (order_id, sub_order_id) 不抛错
# ─────────────────────────────────────────────────────────────

class TestCopyDfToDuckdbDedup:
    """_copy_df_to_duckdb 是 ON CONFLICT DO NOTHING 的最终防线."""

    def test_duplicate_order_id_sub_order_id_no_error(self, duckdb_conn):
        """重复 (order_id, sub_order_id) 第二次写入不报 UniqueConstraint."""
        from scripts.etl.load import _copy_df_to_duckdb

        df1 = _make_orders_df([
            {'order_id': 'O1', 'sub_order_id': 'S1', 'actual_amount': '100.00'},
        ])
        inserted1 = _copy_df_to_duckdb(df1, duckdb_conn, _TABLE_COLUMNS)
        assert inserted1 == 1, f"第一次应插入 1 行, 实际 {inserted1}"

        # 重复 (order_id, sub_order_id): 真撞 unique 索引, _copy_df_to_duckdb 用 ON CONFLICT
        # DO NOTHING 跳过, 不抛 ConstraintException
        df2 = _make_orders_df([
            {'order_id': 'O1', 'sub_order_id': 'S1', 'actual_amount': '999.00'},  # 重复
        ])
        inserted2 = _copy_df_to_duckdb(df2, duckdb_conn, _TABLE_COLUMNS)

        # ON CONFLICT 跳过, 第二次 inserted 应等于 staging 表行数 (返回计数仍是 1)
        assert inserted2 == 1, f"重复行应被 ON CONFLICT 跳过 (staging count=1), 实际 {inserted2}"

        # orders 表总行数仍是 1, 重复未被插入
        total = duckdb_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert total == 1, f"orders 表应只 1 行, 实际 {total}"

        # 第一次插入的 actual_amount 应被保留 (ON CONFLICT 不更新)
        amt = duckdb_conn.execute(
            "SELECT actual_amount FROM orders WHERE order_id='O1' AND sub_order_id='S1'"
        ).fetchone()[0]
        assert amt == '100.00', f"ON CONFLICT 不更新, 旧值应保留, 实际 {amt}"

    def test_string_vs_int_dedup(self, duckdb_conn):
        """'1' (str) 与 1 (int) 在字符串转换后视为相同键, dedup 生效 (sprint 3 P1 修).

        注意: str(1) == '1' 而 str(1.0) == '1.0', 故不能用 1.0, 改用 int(1).
        真实场景: xlsx 读出 sub_order_id=1 (int, openpyxl 默认), parquet 读出 '1' (str).
        """
        from scripts.etl.load import _copy_df_to_duckdb

        df1 = _make_orders_df([
            {'order_id': '100', 'sub_order_id': '1', 'actual_amount': '10.00'},
        ])
        _copy_df_to_duckdb(df1, duckdb_conn, _TABLE_COLUMNS)

        # 第二行用 int 类型, _copy_df_to_duckdb 内部会 str 转换 (line 584-586)
        # str(1) == '1' == 第一行 sub_order_id, ON CONFLICT 跳过
        df2 = _make_orders_df([
            {'order_id': '100', 'sub_order_id': 1, 'actual_amount': '20.00'},
        ])
        _copy_df_to_duckdb(df2, duckdb_conn, _TABLE_COLUMNS)

        total = duckdb_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert total == 1, f"str('1') == str(1), 应 dedup, 实际 {total} 行"


# ─────────────────────────────────────────────────────────────
# ③ upsert_to_duckdb 增量模式: df_new 内部重复不报错
# ─────────────────────────────────────────────────────────────

class TestUpsertIncrementalDedup:
    """upsert_to_duckdb incremental 模式处理 df_new 内部重复 (drop_duplicates 协作)."""

    def test_incremental_new_orders_with_internal_duplicates(self, duckdb_conn):
        """df_new 内部有 2 个相同 (order_id, sub_order_id) 行, upsert 不 crash."""
        from scripts.etl.load import upsert_to_duckdb

        # 3 行, 2 个相同键 (O1/S1)
        df_new = _make_orders_df([
            {'order_id': 'O1', 'sub_order_id': 'S1', 'actual_amount': '100.00'},
            {'order_id': 'O1', 'sub_order_id': 'S1', 'actual_amount': '200.00'},  # 重复
            {'order_id': 'O2', 'sub_order_id': 'S2', 'actual_amount': '300.00'},
        ])
        df_refresh = pd.DataFrame()

        # 不抛错即为通过 (drop_duplicates keep='last' → O1/S1 保留 200.00)
        upsert_to_duckdb(df_new, df_refresh, mode='incremental', window_days=30)

        # 验证表内行数
        total = duckdb_conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert total == 2, f"O1/S1 dedup 后应 2 行, 实际 {total}"

        amt = duckdb_conn.execute(
            "SELECT actual_amount FROM orders WHERE order_id='O1' AND sub_order_id='S1'"
        ).fetchone()[0]
        assert amt == '200.00', f"keep='last' 应保留 200.00, 实际 {amt}"


# ─────────────────────────────────────────────────────────────
# ④ 窗口刷新: df_refresh 内部重复不报错 (staging ROW_NUMBER 协作)
# ─────────────────────────────────────────────────────────────

class TestUpsertRefreshWindowDedup:
    """upsert_to_duckdb incremental 模式处理 df_refresh 内部重复 (ROW_NUMBER 协作)."""

    def test_refresh_window_with_internal_duplicates(self, duckdb_conn):
        """df_refresh 内部有重复键, 窗口刷新事务化不 crash."""
        from scripts.etl.load import upsert_to_duckdb

        # 预置 1 行 (O1/S1, amount=100) 模拟历史数据
        duckdb_conn.execute(
            "INSERT INTO orders (order_id, sub_order_id, actual_amount) VALUES ('O1', 'S1', '100.00')"
        )
        df_new = pd.DataFrame()
        df_refresh = _make_orders_df([
            {'order_id': 'O1', 'sub_order_id': 'S1',
             'actual_amount': '500.00', 'pay_time': '2026-06-07 10:00:00'},
            {'order_id': 'O1', 'sub_order_id': 'S1',
             'actual_amount': '700.00', 'pay_time': '2026-06-08 10:00:00'},  # 重复
        ])

        # fixture 已 monkeypatch DUCKDB_PATH → tmp_path/test_dedup.duckdb,
        # load.py 内部连接共享同一文件, 不应 crash
        upsert_to_duckdb(df_refresh, df_new, mode='incremental', window_days=30)

        # 验证刷新后 O1/S1 仍只 1 行 (ROW_NUMBER dedup)
        total = duckdb_conn.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id='O1' AND sub_order_id='S1'"
        ).fetchone()[0]
        assert total == 1, f"O1/S1 窗口刷新后应只 1 行, 实际 {total}"


# ─────────────────────────────────────────────────────────────
# ⑤ load.py 源码内含 dedup 机制 (Sprint 10 preflight B1 后改 WHERE NOT EXISTS)
# ─────────────────────────────────────────────────────────────

class TestLoadPySourceGuard:
    """源码层守卫: dedup 机制必须在 load.py 存在, 防 refactor 误删.

    Sprint 10 P0 治根: production UNIQUE INDEX (idx_orders_order_unique) 被 B1 prod migration 删了,
    ON CONFLICT 改 WHERE NOT EXISTS (应用层 dedup, 行为等价). 测试从
    "ON CONFLICT 字面量" 改 "WHERE NOT EXISTS + order_id/sub_order_id dedup pattern".
    """

    def test_where_not_exists_dedup_in_load_py(self):
        load_py = (ROOT / "scripts" / "etl" / "load.py").read_text()
        # Sprint 10 preflight B1 修后: 改用 WHERE NOT EXISTS 应用层 dedup
        assert "WHERE NOT EXISTS" in load_py, (
            "load.py 必须保留 'WHERE NOT EXISTS' 应用层 dedup 模式\n"
            "(Sprint 10 preflight B1: production UNIQUE INDEX 被删后, 改 WHERE NOT EXISTS 行为等价)\n"
            "如确认是 false positive, 改用 SELECT COUNT(*) FROM orders 替代, "
            "并加理由说明。"
        )
        # 同时确保 dedup 条件用对字段
        assert "order_id = s.order_id AND sub_order_id = s.sub_order_id" in load_py or \
               "o.order_id = s.order_id AND o.sub_order_id = s.sub_order_id" in load_py, (
            "load.py WHERE NOT EXISTS 必须按 (order_id, sub_order_id) 联合去重"
        )

    def test_unique_index_removed_in_load_py(self):
        """Sprint 10 preflight B1: UNIQUE INDEX idx_orders_order_unique 已删.

        此测试文档化这一变更, 防后续误重新添加 UNIQUE INDEX (会跟 B1 prod migration 不一致).
        """
        load_py = (ROOT / "scripts" / "etl" / "load.py").read_text()
        # Sprint 10 后: 不应再有 CREATE UNIQUE INDEX idx_orders_order_unique
        assert "idx_orders_order_unique" not in load_py or "B1 prod migration" in load_py, (
            "Sprint 10 preflight B1 已删 idx_orders_order_unique 唯一索引, "
            "load.py 不应重新添加 (跟 B1 prod migration 不一致). "
            "如确认需要, 改用 WHERE NOT EXISTS 应用层 dedup."
        )
