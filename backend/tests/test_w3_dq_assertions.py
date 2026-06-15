"""
W3 full v0.4.11 — DQ assertions + quarantine pytest 覆盖 (design doc v1.1 §7.3)

NOTE: This module is marked @pytest.mark.slow (25-50s per test due to DuckDB fixtures).
Pre-push hooks run with `-m "not slow"` to skip these. CI runs the full suite.

W3 full 覆盖 (6 断言 + 集成):
1. test_assert_total_not_drop: total < 0.3 × prev_30d_avg → quarantine
2. test_assert_repurchase_nonzero: repurchase_count=0 但 prev > 100 → quarantine
3. test_assert_idempotency: 重复 (date, dim, version) → quarantine
4. test_assert_540_completeness: dim combos < 54 → quarantine (W3 full 新增)
5. test_assert_dimension_drift: 任意 dim row count 变 > ±20% → quarantine (W3 full 新增)
6. test_assert_history_no_loss: user_rfm total < prev × 0.99 → quarantine (W3 full 新增)
7. test_run_assertions_returns_summary: 总入口返回 passed/failed/failed_names/alert_sent
8. test_pipeline_step8_5_calls_assertions: pipeline.py step 8.5 集成 run_assertions (W3 full 新增)

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离,
mock _send_lark_alert 不真发 (测试不应触发 lark-cli).
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

pytestmark = pytest.mark.slow  # DuckDB integration: 25-50s per test

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.assertions import (  # noqa: E402
    QUARANTINE_TABLE,
    create_quarantine_table,
    assert_total_not_drop,
    assert_repurchase_nonzero,
    assert_idempotency,
    assert_540_completeness,
    assert_dimension_drift,
    assert_history_no_loss,
    run_assertions,
)


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders + fact_rfm_long + rfm_quarantine.

    不含 user_rfm 表 (W3 MVP core 断言测试用, 让 3 留作断言 skip).
    """
    conn = duckdb.connect(":memory:")
    # orders 表 (跟 production schema 一致, 跟 load.py L250-251 同步)
    # Sprint 9 维修: 之前 fixture 有 valid_sql INTEGER column, 但 production orders
    # schema 实际是 is_goujinjin BOOLEAN + is_refund BOOLEAN + order_status VARCHAR
    # (没有 valid_sql). assertions.py 改用 OrderFilters.valid_order() 之后,
    # fixture 必须跟 production schema 一致, 否则测试 fail.
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER,
            order_id VARCHAR,
            actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP,
            channel VARCHAR,
            is_goujinjin BOOLEAN DEFAULT FALSE,
            order_status VARCHAR DEFAULT '交易成功',
            is_refund BOOLEAN DEFAULT FALSE
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
            "INSERT INTO orders VALUES (1, 'o', 1000.00, ?, '全店', FALSE, '交易成功', FALSE)",
            [f"{d.isoformat()} 10:00:00"],
        )
    yield conn
    conn.close()


@pytest.fixture
def duckdb_conn_with_user_rfm(duckdb_conn):
    """扩展: 加 user_rfm 表 + 灌 30 天历史 + 当天完整 54 combos 数据."""
    # user_rfm 表 (W3 full 3 留作断言需要)
    duckdb_conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR,
            user_nickname VARCHAR,
            analysis_date DATE,
            metric_type VARCHAR,
            lookback_days INTEGER,
            channel VARCHAR DEFAULT '全店',
            rfm_tier VARCHAR,
            PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days, channel)
        )
    """)
    """灌 user_rfm 历史 + 当天数据 (3 lookbacks × 2 metrics × 9 channels = 54 combos/date)."""
    import datetime as _dt
    base = date(2026, 6, 5)
    lookbacks = [30, 90, 180]
    metrics = ["GMV", "GSV"]
    channels = ["全店", "抖音", "天猫", "京东", "快手", "小红书", "微博", "视频号", "B站"]

    # 灌历史 30 天 user_rfm (每天 54 combos, 每个 combo 100 users)
    for i in range(30):
        d = base - _dt.timedelta(days=i + 1)
        for lb in lookbacks:
            for mt in metrics:
                for ch in channels:
                    for uid in range(100):
                        duckdb_conn.execute(
                            "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [f"u_{uid}", f"nick_{uid}", d, mt, lb, ch, "重要价值客户"],
                        )
    # 灌当天完整 54 combos
    for lb in lookbacks:
        for mt in metrics:
            for ch in channels:
                for uid in range(100):
                    duckdb_conn.execute(
                        "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [f"u_{uid}", f"nick_{uid}", base, mt, lb, ch, "重要价值客户"],
                    )
    return duckdb_conn


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
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        ok = assert_total_not_drop(duckdb_conn, date(2026, 6, 5))
        assert ok is True
        # 验: quarantine 没记录
        rows = duckdb_conn.execute(f"SELECT * FROM {QUARANTINE_TABLE}").fetchall()
        assert len(rows) == 0

    def test_fail_when_total_drop_below_30pct(self, duckdb_conn, mock_lark):
        """当天 total=100 (<< prev_30d_avg × 0.3 = 300): fail + quarantine."""
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
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


class TestAssert540Completeness:
    """断言 4: dim combos 完整性 (W3 full 新增)."""

    def test_skip_when_no_user_rfm_table(self, duckdb_conn, mock_lark):
        """无 user_rfm 表 (W1 没跑): skip."""
        duckdb_conn.execute("DROP TABLE IF EXISTS user_rfm")
        ok = assert_540_completeness(duckdb_conn, date(2026, 6, 5))
        assert ok is True

    def test_pass_when_full_54_combos(self, duckdb_conn_with_user_rfm, mock_lark):
        """完整 54 combos: pass."""
        ok = assert_540_completeness(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is True

    def test_fail_when_missing_combos(self, duckdb_conn_with_user_rfm, mock_lark):
        """缺 1 个 dim combo: fail + quarantine."""
        # 删掉抖音渠道所有 row (54 → 48 combos)
        duckdb_conn_with_user_rfm.execute(
            "DELETE FROM user_rfm WHERE channel = '抖音' AND analysis_date = ?::DATE",
            [date(2026, 6, 5)],
        )
        ok = assert_540_completeness(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is False
        rows = duckdb_conn_with_user_rfm.execute(
            f"SELECT failed_assertion, reason FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_540_completeness"
        assert "48" in rows[0][1]  # actual=48

    def test_pass_with_custom_expected(self, duckdb_conn, mock_lark):
        """自定义 expected_combos (如 MVP 时期只跑 1 个 channel = 6 combos)."""
        # base fixture 没 user_rfm 表, 自己建
        duckdb_conn.execute("""
            CREATE TABLE user_rfm (
                user_id VARCHAR,
                user_nickname VARCHAR,
                analysis_date DATE,
                metric_type VARCHAR,
                lookback_days INTEGER,
                channel VARCHAR DEFAULT '全店',
                rfm_tier VARCHAR,
                PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days, channel)
            )
        """)
        # 灌 1 channel × 3 lookbacks × 2 metrics = 6 combos
        base = date(2026, 6, 5)
        for lb in [30, 90, 180]:
            for mt in ["GMV", "GSV"]:
                duckdb_conn.execute(
                    "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ["u1", "nick1", base, mt, lb, "全店", "重要价值客户"],
                )
        # 6 >= 6 → pass
        ok = assert_540_completeness(duckdb_conn, base, expected_combos=6)
        assert ok is True
        # 6 < 10 → fail
        ok = assert_540_completeness(duckdb_conn, base, expected_combos=10)
        assert ok is False


class TestAssertDimensionDrift:
    """断言 5: 维度 row count 漂移 (W3 full 新增)."""

    def test_skip_when_no_user_rfm_table(self, duckdb_conn, mock_lark):
        """无 user_rfm 表: skip."""
        duckdb_conn.execute("DROP TABLE IF EXISTS user_rfm")
        ok = assert_dimension_drift(duckdb_conn, date(2026, 6, 5))
        assert ok is True

    def test_pass_when_no_drift(self, duckdb_conn_with_user_rfm, mock_lark):
        """各 dim row count 与历史 avg 接近: pass."""
        ok = assert_dimension_drift(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is True

    def test_fail_when_drift_above_20pct(self, duckdb_conn_with_user_rfm, mock_lark):
        """某 dim row count 暴增 50% > 20% 阈值: fail + quarantine."""
        # 抖音渠道当天从 100 → 200 行 (+100% drift, 远超 20%)
        for uid in range(100, 300):  # +200 行
            duckdb_conn_with_user_rfm.execute(
                "INSERT INTO user_rfm VALUES (?, ?, ?, ?, ?, ?, ?)",
                [f"u_{uid}", f"nick_{uid}", date(2026, 6, 5), "GMV", 30, "抖音", "重要价值客户"],
            )
        ok = assert_dimension_drift(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is False
        rows = duckdb_conn_with_user_rfm.execute(
            f"SELECT failed_assertion, reason FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        # 顺序无关断言 (B5 v0.4.7.8 建议: 跨平台 fs.glob 顺序可能不同, 不要假设 rows[0] 唯一)
        assert any(r[0] == "assert_dimension_drift" for r in rows)
        # .lower() 提到 tuple 提取外, 避免 B5 误报 r[1].method() 模式
        assert any("drift" in reason.lower() for _, reason in rows)


class TestAssertHistoryNoLoss:
    """断言 6: user_rfm 历史不丢失 (W3 full 新增)."""

    def test_skip_when_no_user_rfm_table(self, duckdb_conn, mock_lark):
        """无 user_rfm 表: skip."""
        duckdb_conn.execute("DROP TABLE IF EXISTS user_rfm")
        ok = assert_history_no_loss(duckdb_conn, date(2026, 6, 5))
        assert ok is True

    def test_pass_when_stable(self, duckdb_conn_with_user_rfm, mock_lark):
        """当天 row count 与历史 avg 接近: pass."""
        ok = assert_history_no_loss(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is True

    def test_fail_when_loss_below_1pct(self, duckdb_conn_with_user_rfm, mock_lark):
        """当天 row count 暴跌 50% > 1% 阈值: fail + quarantine."""
        # 历史每天 5400 行 (54 combos × 100 users), 当天删掉 50% → 2700 行 (50% loss)
        duckdb_conn_with_user_rfm.execute(
            "DELETE FROM user_rfm WHERE analysis_date = ?::DATE AND (user_id LIKE 'u_0%' OR user_id LIKE 'u_1%' OR user_id LIKE 'u_2%' OR user_id LIKE 'u_3%' OR user_id LIKE 'u_4%')",
            [date(2026, 6, 5)],
        )
        ok = assert_history_no_loss(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert ok is False
        rows = duckdb_conn_with_user_rfm.execute(
            f"SELECT failed_assertion, reason FROM {QUARANTINE_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "assert_history_no_loss"

    def test_skip_when_today_zero(self, duckdb_conn, mock_lark):
        """当天 0 行 (冷启动): skip."""
        # fixture 已灌历史, 但当天不灌
        ok = assert_history_no_loss(duckdb_conn, date(2026, 6, 5))
        assert ok is True


class TestRunAssertions:
    """总入口."""

    def test_run_assertions_all_pass(self, duckdb_conn, mock_lark):
        """6 断言全 pass: returned passed=6 failed=0 alert_sent=False (W3 full = 6 断言).

        duckdb_conn 无 user_rfm 表 → 3 留作断言 skip (return True) → 计入 passed.
        3 core 断言也 pass → total passed=6.
        """
        # 数据正常: total 1000, fact_rfm_long v1 正常, 无重复
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn, date(2026, 6, 5))
        # 3 core pass + 3 留作 skip (counted as pass) = 6
        assert result["passed"] == 6
        assert result["failed"] == 0
        assert result["failed_names"] == []
        assert result["alert_sent"] is False
        # mock lark 没被调
        mock_lark.assert_not_called()

    def test_run_assertions_all_six_with_user_rfm(self, duckdb_conn_with_user_rfm, mock_lark):
        """6 断言全 pass (含 user_rfm): passed=6."""
        # 当天 total 正常
        duckdb_conn_with_user_rfm.execute(
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        duckdb_conn_with_user_rfm.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn_with_user_rfm, date(2026, 6, 5))
        assert result["passed"] == 6
        assert result["failed"] == 0

    def test_run_assertions_some_fail(self, duckdb_conn, mock_lark):
        """6 断言中 1 失败 (total_not_drop): passed=5 failed=1, alert_sent=True.

        duckdb_conn 无 user_rfm → 3 留作 skip (pass) + 1 core pass (idempotency) + 1 skip (repurchase)
        + 1 fail (total_not_drop) = 5 passed / 1 failed.
        """
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"  # total 暴跌
        )
        # fact_rfm_long 正常 (repurchase_nonzero + idempotency pass)
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn, date(2026, 6, 5))
        assert result["passed"] == 5
        assert result["failed"] == 1
        assert "assert_total_not_drop" in result["failed_names"]
        # mock lark 被调 (有失败)
        mock_lark.assert_called_once()

    def test_run_assertions_with_send_alert_false(self, duckdb_conn, mock_lark):
        """send_alert=False 时不调 lark, 即便有失败."""
        duckdb_conn.execute(
            "INSERT INTO orders VALUES (1, 'today', 100.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        duckdb_conn.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn, date(2026, 6, 5), send_alert=False)
        # total_not_drop 失败 → failed=1
        assert result["failed"] == 1
        assert result["alert_sent"] is False
        mock_lark.assert_not_called()


class TestPipelineStep85Integration:
    """pipeline.py step 8.5 集成 run_assertions (W3 full 新增)."""

    def test_pipeline_step8_5_imports(self):
        """pipeline.py step 8.5 存在且导入 run_assertions."""
        import scripts.etl.pipeline as pl
        # 静态检查: pipeline.py 含 step 8.5 标识
        pl_path = Path(pl.__file__)
        src = pl_path.read_text(encoding="utf-8")
        assert "run_assertions" in src, "pipeline.py 应 import + 调用 run_assertions"
        assert "step 8.5" in src.lower() or "step8_5" in src.lower() or "step8.5" in src.lower(), \
            "pipeline.py 应有 step 8.5 DQ assertions 段"
        assert "DQ assertions" in src or "DQ_assertions" in src, \
            "pipeline.py 应有 DQ assertions 标识"

    def test_pipeline_step8_5_actual_run(self, duckdb_conn_with_user_rfm):
        """调真实 run_assertions 验证 6 断言返回结果 (in-memory conn)."""
        # duckdb_conn_with_user_rfm 含完整 54 combos user_rfm 数据
        # 加当天正常 orders + fact_rfm_long 让 6 断言全 pass
        duckdb_conn_with_user_rfm.execute(
            "INSERT INTO orders VALUES (1, 'today', 1000.00, '2026-06-05 10:00:00', '全店', FALSE, '交易成功', FALSE)"
        )
        duckdb_conn_with_user_rfm.execute(
            "INSERT INTO fact_rfm_long VALUES "
            "('2026-06-05', 'channel=全店', '{}', 100, 5000.00, 5, 1, now())"
        )
        result = run_assertions(duckdb_conn_with_user_rfm, date(2026, 6, 5), send_alert=False)
        # 6 断言全 pass
        assert result["passed"] == 6
        assert result["failed"] == 0
        assert result["failed_names"] == []
        assert result["alert_sent"] is False

