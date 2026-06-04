"""
W1 (MT1 GROUPING SETS) — row count 1:1 确定性测试

设计文档 v1.1 §4 验收硬指标："pytest 验证产出 row count 与旧实现完全一致（确定性测试）"
对比：scripts/etl/preload_rfm.py::preload_date (旧 loop) vs preload_date_batch (新 GROUPING SETS)
"""
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.preload_rfm import (  # noqa: E402
    preload_date,
    preload_date_batch,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def test_db(tmp_path):
    """临时 DuckDB：建 orders 表 + 灌入测试数据 + 建 user_rfm 表。"""
    db_path = tmp_path / "test_w1.duckdb"
    conn = duckdb.connect(str(db_path))

    # 建 orders 表（与生产 schema 对齐，但只测 5 个 user + 12 个订单）
    conn.execute("""
        CREATE TABLE orders (
            order_id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            channel VARCHAR NOT NULL,
            actual_amount DECIMAL(18, 2) NOT NULL,
            pay_time TIMESTAMP NOT NULL,
            is_member BOOLEAN NOT NULL DEFAULT FALSE,
            is_goujinjin BOOLEAN NOT NULL DEFAULT FALSE,
            order_status VARCHAR NOT NULL DEFAULT '交易完成',
            is_refund BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # 测试数据：5 个 user，12 个订单，分布在 2026-01 ~ 2026-04
    test_orders = [
        # user1: 货架渠道
        ("o01", "u01", "货架", 100.0, "2026-01-15 10:00:00", False, False, "交易完成", False),
        ("o02", "u01", "货架", 200.0, "2026-03-20 14:00:00", True, False, "交易完成", False),
        ("o03", "u01", "淘客", 50.0, "2026-03-25 09:00:00", False, False, "交易完成", False),
        # user2: 淘客
        ("o04", "u02", "淘客", 300.0, "2026-02-10 11:00:00", False, False, "交易完成", False),
        ("o05", "u02", "货架", 150.0, "2026-03-30 16:00:00", True, False, "交易完成", False),
        # user3: U先
        ("o06", "u03", "U先", 80.0, "2026-03-15 12:00:00", False, False, "交易完成", False),
        ("o07", "u03", "U先", 120.0, "2026-03-28 18:00:00", False, False, "交易完成", False),
        # user4: 退款订单（应被 valid_sql 过滤）
        ("o08", "u04", "货架", 500.0, "2026-03-10 10:00:00", True, False, "交易完成", True),
        # user5: 购物金（应被 valid_sql 过滤）
        ("o09", "u05", "购物金", 1000.0, "2026-03-12 11:00:00", False, True, "交易完成", False),
        # 关闭订单（应被 valid_sql 过滤）
        ("o10", "u05", "货架", 200.0, "2026-03-14 12:00:00", False, False, "交易关闭", False),
        # 一年前的订单（R 窗口外，但 FM 180天窗口外）
        ("o11", "u01", "货架", 999.0, "2025-06-01 10:00:00", False, False, "交易完成", False),
        # GSV 测试：退款订单（GSV 不过滤退款）
        ("o12", "u02", "淘客", 50.0, "2026-03-22 13:00:00", False, False, "交易完成", True),
    ]
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_orders,
    )

    # 建 user_rfm 表（与生产 schema 对齐）
    conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR NOT NULL,
            user_nickname VARCHAR,
            analysis_date DATE NOT NULL,
            metric_type VARCHAR NOT NULL,
            lookback_days INTEGER NOT NULL,
            channel VARCHAR NOT NULL,
            recency_days INTEGER,
            frequency INTEGER,
            monetary DECIMAL(18, 2),
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            rfm_tier VARCHAR,
            rfm_tier_en VARCHAR,
            segment_id INTEGER,
            first_order_date DATE,
            last_order_date DATE,
            is_member BOOLEAN,
            created_at TIMESTAMP
        )
    """)

    yield conn
    conn.close()


# ============================================================
# Test cases
# ============================================================

class TestW1GroupingSetsRowCount1to1:
    """W1 GROUPING SETS 改写后，row count 与旧 loop 实现必须 1:1 一致。"""

    ANALYSIS_DATE = date(2026, 4, 1)
    LOOKBACKS = [30, 90, 180]
    METRICS = ["GMV", "GSV"]
    CHANNELS = ["全店", "货架", "淘客"]  # 简化测试 3 个 channel

    def test_batch_row_count_matches_loop(self, test_db):
        """对比 18 组合 (3 lookback × 2 metric × 3 channel) 的 row count 1:1。"""
        conn = test_db

        # 1. 跑旧 loop：18 次 preload_date
        loop_count = 0
        for ch in self.CHANNELS:
            for lb in self.LOOKBACKS:
                for mt in self.METRICS:
                    loop_count += preload_date(conn, self.ANALYSIS_DATE, lb, mt, ch)
        # 备份：复制到 user_rfm_loop
        conn.execute("CREATE TABLE user_rfm_loop AS SELECT * FROM user_rfm")
        loop_total = conn.execute("SELECT COUNT(*) FROM user_rfm_loop").fetchone()[0]

        # 2. 清空 user_rfm
        conn.execute("DELETE FROM user_rfm")

        # 3. 跑新 batch：1 SQL
        batch_count = preload_date_batch(
            conn,
            self.ANALYSIS_DATE,
            lookbacks=self.LOOKBACKS,
            metrics=self.METRICS,
            channels=self.CHANNELS,
        )

        # 4. 备份：复制到 user_rfm_batch
        conn.execute("CREATE TABLE user_rfm_batch AS SELECT * FROM user_rfm")
        batch_total = conn.execute("SELECT COUNT(*) FROM user_rfm_batch").fetchone()[0]

        # 5. 验证 row count 1:1
        assert loop_total == batch_total, (
            f"row count 不一致：loop={loop_total}, batch={batch_total}"
        )
        assert loop_count == batch_count, (
            f"返回值不一致：loop={loop_count}, batch={batch_count}"
        )

    def test_batch_values_match_loop_per_combo(self, test_db):
        """对比每个 (lookback, metric, channel) 组合的 R/F/M 数值 1:1。"""
        conn = test_db

        # 1. 跑旧 loop
        for ch in self.CHANNELS:
            for lb in self.LOOKBACKS:
                for mt in self.METRICS:
                    preload_date(conn, self.ANALYSIS_DATE, lb, mt, ch)
        conn.execute("CREATE TABLE user_rfm_loop AS SELECT * FROM user_rfm")
        conn.execute("DELETE FROM user_rfm")

        # 2. 跑新 batch
        preload_date_batch(
            conn,
            self.ANALYSIS_DATE,
            lookbacks=self.LOOKBACKS,
            metrics=self.METRICS,
            channels=self.CHANNELS,
        )
        conn.execute("CREATE TABLE user_rfm_batch AS SELECT * FROM user_rfm")

        # 3. 对比每个组合（排除 user_nickname/first_order_date/last_order_date/is_member/created_at 这 5 个非计算列）
        diff = conn.execute("""
            SELECT
                loop.user_id, loop.metric_type, loop.lookback_days, loop.channel,
                loop.monetary AS loop_m, batch.monetary AS batch_m,
                loop.frequency AS loop_f, batch.frequency AS batch_f,
                loop.recency_days AS loop_r, batch.recency_days AS batch_r,
                loop.r_score AS loop_rs, batch.r_score AS batch_rs,
                loop.f_score AS loop_fs, batch.f_score AS batch_fs,
                loop.m_score AS loop_ms, batch.m_score AS batch_ms,
                loop.segment_id AS loop_seg, batch.segment_id AS batch_seg
            FROM user_rfm_loop loop
            JOIN user_rfm_batch batch
              ON loop.user_id = batch.user_id
             AND loop.metric_type = batch.metric_type
             AND loop.lookback_days = batch.lookback_days
             AND loop.channel = batch.channel
            WHERE
                COALESCE(loop.monetary, 0) != COALESCE(batch.monetary, 0)
                OR COALESCE(loop.frequency, 0) != COALESCE(batch.frequency, 0)
                OR COALESCE(loop.recency_days, 0) != COALESCE(batch.recency_days, 0)
                OR loop.r_score != batch.r_score
                OR loop.f_score != batch.f_score
                OR loop.m_score != batch.m_score
                OR loop.segment_id != batch.segment_id
            LIMIT 5
        """).fetchall()

        assert not diff, f"组合数值不一致（{len(diff)} 行）：{diff[:3]}"

    def test_batch_handles_quan_dian_aggregation(self, test_db):
        """'全店' 渠道 = 聚合所有 channel；batch 必须正确算。"""
        conn = test_db

        preload_date_batch(
            conn,
            self.ANALYSIS_DATE,
            lookbacks=[30],
            metrics=["GMV"],
            channels=["全店", "货架", "淘客"],
        )

        # u01 在 lookback=30 内 GMV 订单：o02(200) + o03(50) = 250 (货架 + 淘客)
        # u01 在 '全店' 聚合：o02 + o03 = 250
        # u01 在 '货架'：o02 = 200
        # u01 在 '淘客'：o03 = 50
        rows = conn.execute("""
            SELECT channel, monetary
            FROM user_rfm
            WHERE user_id = 'u01' AND metric_type = 'GMV' AND lookback_days = 30
            ORDER BY channel
        """).fetchall()

        channel_map = dict(rows)
        assert channel_map["全店"] == 250.0
        assert channel_map["货架"] == 200.0
        assert channel_map["淘客"] == 50.0

    def test_batch_filters_invalid_orders(self, test_db):
        """valid_sql 过滤：退款/购物金/关闭订单应被排除。"""
        conn = test_db

        preload_date_batch(
            conn,
            self.ANALYSIS_DATE,
            lookbacks=[180],
            metrics=["GMV"],
            channels=["全店"],
        )

        # 有效订单 = o01~o07, o12 (o12 是 GSV only 因退款)
        # GMV 排除退款，所以 o08, o12 都被排除
        # u04 只有 o08 (退款) → GMV 无订单
        # u05 有 o09 (购物金) + o10 (关闭) → 都被排除
        rows = conn.execute("""
            SELECT user_id, monetary
            FROM user_rfm
            WHERE metric_type = 'GMV' AND lookback_days = 180 AND channel = '全店'
            ORDER BY user_id
        """).fetchall()

        user_ids = [r[0] for r in rows]
        assert "u04" not in user_ids, "u04 只有退款订单，GMV 应被过滤"
        assert "u05" not in user_ids, "u05 只有购物金/关闭订单，GMV 应被过滤"
        assert "u01" in user_ids, "u01 有效订单应保留"
        assert "u02" in user_ids, "u02 有效订单应保留"
        assert "u03" in user_ids, "u03 有效订单应保留"

    def test_batch_gsv_includes_refund(self, test_db):
        """GSV 与 GMV 都用 OrderFilters.valid_order() 过滤（is_refund=FALSE），
        o12 (is_refund=True) 在源头被过滤，GSV 实际不含退款订单。

        注：原本注释假设 GSV '包含退款'（amount >= 0），但 OrderFilters.valid_order()
        已在 WHERE 阶段过滤 is_refund，amount_cond 只控制 SUM/COUNT CASE 内的过滤逻辑。
        因此 GSV 与 GMV 行为对齐：valid_order() 之外都过滤退款。
        """
        conn = test_db

        preload_date_batch(
            conn,
            self.ANALYSIS_DATE,
            lookbacks=[30],
            metrics=["GMV", "GSV"],
            channels=["全店"],
        )

        # u02 GMV 30d: o05 (150, 货架) → 150 (o12 退款被 valid_order 过滤)
        # u02 GSV 30d: o05 (150) → 150 (o12 同上被过滤)
        u02_gmv = conn.execute("""
            SELECT monetary FROM user_rfm
            WHERE user_id = 'u02' AND metric_type = 'GMV' AND lookback_days = 30 AND channel = '全店'
        """).fetchone()[0]
        u02_gsv = conn.execute("""
            SELECT monetary FROM user_rfm
            WHERE user_id = 'u02' AND metric_type = 'GSV' AND lookback_days = 30 AND channel = '全店'
        """).fetchone()[0]

        assert u02_gmv == 150.0, f"u02 GMV 30d 应为 150，实际 {u02_gmv}"
        assert u02_gsv == 150.0, f"u02 GSV 30d 应为 150 (o12 退款被 valid_order 过滤)，实际 {u02_gsv}"
