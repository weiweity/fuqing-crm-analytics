"""
W3 MVP v0.4.10 — DQ assertions + quarantine pytest 覆盖 (design doc v1.1 §7.3)

MVP 覆盖 (4 个核心):
1. test_assert_total_not_drop: total < 0.3 × prev_30d_avg → quarantine
2. test_assert_repurchase_nonzero: repurchase_count=0 但 prev > 100 → quarantine
3. test_assert_idempotency: 重复 (date, dim, version) → quarantine
4. test_run_assertions_returns_summary: 总入口返回 passed/failed/failed_names/alert_sent

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离,
mock _send_lark_alert 不真发 (MVP 测试不应触发 lark-cli).
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.assertions import (  # noqa: E402
    QUARANTINE_TABLE,
    create_quarantine_table,
    assert_total_not_drop,
    assert_repurchase_nonzero,
    assert_idempotency,
    run_assertions,
)


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders + fact_rfm_long + rfm_quarantine."""
    conn = duckdb.connect(":memory:")
    # orders 表
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
    # fact_rfm_long 表 (W4 已合 main, 模拟其 schema)
    conn.execute("""
        CREATE TABLE fact_rfm_long (
            date DATE NOT NULL,
            dimension_key VARCHAR NOT NULL,
            dimension_json JSON NOT NULL,
            user_count BIGINT NOT NULL,
            gmv DECIMAL(18,2),
            repurchase_count BIGINT,
            version INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (date, dimension_key, version)
        )
    """)
    # rfm_quarantine 表 (W3 自己建, fixture 预建避免测试 pass 路径查不到)
    create_quarantine_table(conn)
    # 灌历史 30 天数据 (每天 SUM 1000)
    import datetime
    base = date(2026, 6, 5)
    for i in range(30):
        d = base - datetime.timedelta(days=i+1)
        conn.execute(
            "INSERT INTO orders VALUES (1, 'o', 1000.00, ?, '全店', 1)",
            [f"{d.isoformat()} 10:00:00"],
        )
    yield conn
    conn.close()


@pytest.fixture
def mock_lark():
    """Mock _send_lark_alert, 不真发 lark-cli."""
    with patch("scripts.etl.assertions._send_lark_alert_mockable") as m:
        m.return_value = (True, "mocked")
        yield m


class TestQuarantineTable:
    """quarantine 表创建."""

    def test_create_quarantine_idempotent(self, duckdb_conn):
        create_quarantine_table(duckdb_conn)
        create_quarantine_table(duckdb_conn)  # 第二次不报错
        tables = duckdb_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [QUARANTINE_TABLE],
        ).fetchall()
        assert len(tables) == 1


class TestAssertTotalNotDrop:
    """断言 1: total 暴跌检测."""

    def test_pass_when_total_normal(self, duckdb_conn, mock_lark):
        """当天 total ≈ prev_30d_avg (1000): pass."""
        # 加当天正常数据 (1000)
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', 1)"
        )
        ok = assert_total_not_drop(duckdb_conn, date(2026, 6, 5))
        assert ok is True
        # 验: quarantine 没记录
        rows = duckdb_conn.execute(f"SELECT * FROM {QUARANTINE_TABLE}").fetchall()
        assert len(rows) == 0

    def test_fail_when_total_drop_below_30pct(self, duckdb_conn, mock_lark):
        """当天 total=100 (<< prev_30d_avg × 0.3 = 300): fail + quarantine."""
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', '全店', 1)"
        )
        ok = assert_total_not_drop(duckdb_conn, date(2026, 6, 5))
        assert ok is False
        # 验: quarantine 有 1 条
        rows = duckdb_conn.execute(
            f"SELECT failed_assertion, reason FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_total_not_drop"
        assert "100" in rows[0][1]  # 提到 today_total

    def test_skip_when_no_history(self, duckdb_conn, mock_lark):
        """新项目无历史 → skip (return True)."""
        # 清空 fixture 灌的 30 天历史, 改成空
        duckdb_conn.execute("DELETE FROM orders")
        ok = assert_total_not_drop(duckdb_conn, date(2026, 6, 5))
        assert ok is True
        rows = duckdb_conn.execute(f"SELECT * FROM {QUARANTINE_TABLE}").fetchall()
        assert len(rows) == 0


class TestAssertRepurchaseNonzero:
    """断言 2: repurchase 100%/0% 异常检测 (防 P0-102 回归)."""

    def test_pass_when_repurchase_nonzero(self, duckdb_conn, mock_lark):
        """fact_rfm_long 有 repurchase > 0: pass."""
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{\"channel\":\"全店\"}', 100, 5000.00, 5, 1, now())"
        )
        ok = assert_repurchase_nonzero(duckdb_conn, date(2026, 6, 5))
        assert ok is True

    def test_fail_when_repurchase_zero(self, duckdb_conn, mock_lark):
        """fact_rfm_long repurchase = 0: fail + quarantine (P0-102 异常)."""
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{\"channel\":\"全店\"}', 100, 5000.00, 0, 1, now())"
        )
        ok = assert_repurchase_nonzero(duckdb_conn, date(2026, 6, 5))
        assert ok is False
        rows = duckdb_conn.execute(
            f"SELECT failed_assertion FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_repurchase_nonzero"

    def test_skip_when_no_fact_rfm_yet(self, duckdb_conn, mock_lark):
        """W4 还没跑 (无 fact_rfm_long 数据): skip."""
        ok = assert_repurchase_nonzero(duckdb_conn, date(2026, 6, 5))
        assert ok is True


class TestAssertIdempotency:
    """断言 3: (date, dim, version) 唯一."""

    def test_pass_when_no_duplicates(self, duckdb_conn, mock_lark):
        """正常 fact_rfm_long 数据 (v1, v2 同一 dim 不同 version): pass."""
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now()),"
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 2, now())"
        )
        ok = assert_idempotency(duckdb_conn, date(2026, 6, 5))
        assert ok is True

    def test_fail_when_duplicate_dim_version(self, duckdb_conn, mock_lark):
        """同日同 dim+version 重复: fail + quarantine."""
        # 模拟 ETL 跑 2 次插同一 (date, dim, version)
        duckdb_conn.execute("""
            CREATE TABLE tmp_fact AS SELECT * FROM fact_rfm_long LIMIT 0
        """)  # 占位避免 PK 冲突
        duckdb_conn.execute("DROP TABLE fact_rfm_long")
        duckdb_conn.execute("""
            CREATE TABLE fact_rfm_long (
                date DATE NOT NULL,
                dimension_key VARCHAR NOT NULL,
                dimension_json JSON NOT NULL,
                user_count BIGINT NOT NULL,
                gmv DECIMAL(18,2),
                repurchase_count BIGINT,
                version INTEGER NOT NULL
            )
        """)
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1),"
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1)"
        )
        ok = assert_idempotency(duckdb_conn, date(2026, 6, 5))
        assert ok is False
        rows = duckdb_conn.execute(
            f"SELECT failed_assertion, reason FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_idempotency"


class TestRunAssertions:
    """总入口."""

    def test_run_assertions_all_pass(self, duckdb_conn, mock_lark):
        """3 断言全 pass: 返回 passed=3 failed=0 alert_sent=False."""
        # 数据正常: total 1000, fact_rfm_long v1 正常, 无重复
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', 1)"
        )
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn, date(2026, 6, 5))
        assert result["passed"] == 3
        assert result["failed"] == 0
        assert result["failed_names"] == []
        assert result["alert_sent"] is False
        # mock lark 没被调
        mock_lark.assert_not_called()

    def test_run_assertions_some_fail(self, duckdb_conn, mock_lark):
        """3 断言中 1 失败: passed=2 failed=1, alert_sent=True."""
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', '全店', 1)"  # total 暴跌
        )
        # fact_rfm_long 正常 (repurchase_nonzero + idempotency pass)
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn, date(2026, 6, 5))
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert "assert_total_not_drop" in result["failed_names"]
        # mock lark 被调 (有失败)
        mock_lark.assert_called_once()
