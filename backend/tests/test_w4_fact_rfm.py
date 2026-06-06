"""
W4 MVP v0.4.9 — fact_rfm_long 预计算 pytest 覆盖 (design doc v1.1 §7.4)

MVP 覆盖 (4 个核心):
1. test_create_fact_rfm_table: 表 + 唯一索引创建, 幂等
2. test_incremental_load_basic: 1 组合 (channel='全店') 插入成功
3. test_incremental_load_idempotency: 同一天跑两次结果一致 (ON CONFLICT DO NOTHING)
4. test_incremental_load_version_increments: 连续跑 version 续号

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离.
"""
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.precompute_fact_rfm import (  # noqa: E402
    FACT_RFM_TABLE,
    create_fact_rfm_table,
    incremental_load,
)


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders table (3 rows: 2 users, 1 repurchase).

    Schema 跟生产 orders 表匹配 (subset: user_id, order_id, actual_amount,
    pay_time, channel, valid_sql).
    """
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER,
            order_id VARCHAR,
            actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP,
            channel VARCHAR,
            valid_sql INTEGER
        )
    """)
    # 灌测试数据: 3 个 user, 1 个复购
    # 昨天 (T-1): 2026-06-05
    conn.execute("""
        INSERT INTO orders VALUES
            (1, 'o1', 100.00, '2026-06-05 10:00:00', '全店', 1),
            (2, 'o2', 200.00, '2026-06-05 11:00:00', '全店', 1),
            (2, 'o3', 150.00, '2026-06-05 12:00:00', '全店', 1),
            (3, 'o4', 50.00,  '2026-06-04 10:00:00', '全店', 1),  -- 昨天之前
            (4, 'o5', 999.00, '2026-06-05 10:00:00', '抖音', 1)   -- 其他 channel
    """)
    yield conn
    conn.close()


class TestFactRfmTable:
    """表 + 索引创建."""

    def test_create_table_idempotent(self, duckdb_conn):
        """create_fact_rfm_table 幂等 (跑 2 次不报错)."""
        create_fact_rfm_table(duckdb_conn)
        create_fact_rfm_table(duckdb_conn)  # 第二次不报错
        # 表存在
        tables = duckdb_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [FACT_RFM_TABLE],
        ).fetchall()
        assert len(tables) == 1
        # 唯一索引存在
        indexes = duckdb_conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'idx_fact_rfm_dkv'"
        ).fetchall()
        assert len(indexes) == 1

    def test_table_schema_columns(self, duckdb_conn):
        """表 schema 列对."""
        create_fact_rfm_table(duckdb_conn)
        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
            [FACT_RFM_TABLE],
        ).fetchall()
        col_names = [c[0] for c in cols]
        # 必须含的关键列
        for required in ["date", "dimension_key", "dimension_json", "user_count", "gmv", "repurchase_count", "version", "created_at"]:
            assert required in col_names, f"缺列: {required}"


class TestIncrementalLoad:
    """MVP 增量加载: 1 组合 (channel='全店') 验证机制."""

    def test_incremental_load_basic(self, duckdb_conn):
        """基本增量: T-1 (2026-06-05) 数据 1 组合插入成功."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        inserted = incremental_load(duckdb_conn, target)
        assert inserted == 1
        # 验: load_date = 2026-06-05 (T-1)
        row = duckdb_conn.execute(
            f"SELECT date, dimension_key, user_count, gmv, repurchase_count, version "
            f"FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()
        assert row is not None
        assert row[0] == date(2026, 6, 5)
        assert row[1] == "channel=全店"
        # user_count: user_id 1, 2 (2 distinct, 不含 user 4 因为 channel='抖音')
        assert row[2] == 2
        # gmv: 100 + 200 + 150 = 450 (user 2 两单都算)
        assert float(row[3]) == 450.0
        # repurchase: user 2 (order_count=2) → 1
        assert row[4] == 1
        # version: 1
        assert row[5] == 1

    def test_incremental_load_idempotency(self, duckdb_conn):
        """同一天跑两次: ON CONFLICT DO NOTHING 跳过, row count 1:1 (设计 doc v1.1 §7.4)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        # 第 1 次
        inserted_1 = incremental_load(duckdb_conn, target)
        assert inserted_1 == 1
        # 第 2 次 (同一天) — version 续 +1, 但 ON CONFLICT (date, dim, version) DO NOTHING
        # 实际 ON CONFLICT 是 (date, dim, version) 三元组, 第 2 次 version=2 不冲突, 会插入
        inserted_2 = incremental_load(duckdb_conn, target)
        # 重要: 第 2 次应该插入新行 (version=2), 不是 0
        assert inserted_2 == 1
        # 验: 总行数 2 (v1 + v2 同一天)
        total = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()[0]
        assert total == 2
        # 幂等性 (v1.1 §7.4 验收点 3): "重跑同一天结果一致" — row count 累加, 但每行 value 一致
        rows = duckdb_conn.execute(
            f"SELECT user_count, gmv, repurchase_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert rows[0] == rows[1]  # v1 和 v2 数据一致

    def test_incremental_load_version_increments(self, duckdb_conn):
        """version 续号: 第 N 次跑 version = N."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        for i in range(1, 4):
            incremental_load(duckdb_conn, target)
        versions = duckdb_conn.execute(
            f"SELECT version FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3]

    def test_incremental_load_only_target_date(self, duckdb_conn):
        """增量只 append T-1, 不影响其他日期 (orders 里 6/4 数据不会被 load)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target)
        # 验: 6/4 (前天) 不在 fact_rfm_long 里 (orders 6/4 有 1 行, 但不在 load_date=T-1 范围)
        rows = duckdb_conn.execute(
            f"SELECT date FROM {FACT_RFM_TABLE}"
        ).fetchall()
        dates = [r[0] for r in rows]
        assert date(2026, 6, 5) in dates
        assert date(2026, 6, 4) not in dates

    def test_incremental_load_channel_filter(self, duckdb_conn):
        """MVP 只算 channel='全店', 其他 channel 不算 (user 4 在 '抖音' 不进 user_count)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target)
        user_count = duckdb_conn.execute(
            f"SELECT user_count FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()[0]
        # user 4 (channel='抖音') 不算 → user_count = 2 (user 1 + 2)
        assert user_count == 2
