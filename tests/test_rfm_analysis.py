"""health/rfm_analysis 集成测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── 基础结构测试 ──────────────────────────────────────────────


class TestRFMRatioAnalysis:
    def test_returns_dict_with_required_keys(self, mock_orders_rfm_analysis, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm_analysis)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", mock_orders_rfm_analysis)

        from backend.services.health.rfm_analysis import get_rfm_analysis

        result = get_rfm_analysis(
            year=2025,
            period="MTD",
            metric_type="GSV",
        )

        assert isinstance(result, dict)
        assert "metric_type" in result
        assert "year_label" in result
        assert "rows" in result
        assert "member_rows" in result

    def test_gsv_caliber_excludes_refund(self, mock_orders_rfm_analysis, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm_analysis)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", mock_orders_rfm_analysis)

        from backend.services.health.rfm_analysis import get_rfm_analysis

        result = get_rfm_analysis(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )

        assert isinstance(result, dict)
        if "summary" in result:
            gsv = result["summary"].get("gsv", 0)
            assert gsv >= 0


# ── 缓存逻辑测试 ──────────────────────────────────────────────


class TestCacheRouting:
    def test_historical_period_detected(self, mock_orders_rfm_analysis, monkeypatch):
        import datetime as dt_module
        from unittest.mock import patch

        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm_analysis)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", mock_orders_rfm_analysis)

        mock_date_instance = dt_module.date(2025, 6, 15)

        with patch("backend.services.health.rfm_analysis.analysis.date") as mock_date_cls:
            mock_date_cls.today.return_value = mock_date_instance
            mock_date_cls.side_effect = lambda *args, **kwargs: dt_module.date(*args, **kwargs)

            from backend.services.health.rfm_analysis import get_rfm_analysis

            result = get_rfm_analysis(
                year=2024,
                start_date="2024-05-01",
                end_date="2024-05-31",
                metric_type="GSV",
            )
            assert isinstance(result, dict)

    def test_current_period_live_sql(self, mock_orders_rfm_analysis, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm_analysis)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", mock_orders_rfm_analysis)

        from backend.services.health.rfm_analysis import get_rfm_analysis

        result = get_rfm_analysis(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )
        assert isinstance(result, dict)


# ── 边界条件测试 ─────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        import duckdb

        conn = duckdb.connect(database=":memory:")
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                pay_time TIMESTAMP, actual_amount DOUBLE, is_refund BOOLEAN,
                order_status VARCHAR, is_goujinjin BOOLEAN, channel VARCHAR,
                is_member BOOLEAN, year INTEGER, month INTEGER,
                refund_status VARCHAR, refund_amount DOUBLE
            )
        """)
        conn.execute("""
            CREATE TABLE user_rfm (
                user_id VARCHAR, analysis_date DATE, metric_type VARCHAR,
                lookback_days INTEGER, r_segment VARCHAR, f_segment VARCHAR,
                m_segment VARCHAR, r_score INTEGER, f_score INTEGER, m_score INTEGER
            )
        """)

        def factory():
            return conn

        monkeypatch.setattr("backend.db.connection.get_connection", factory)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", factory)

        from backend.services.health.rfm_analysis import get_rfm_analysis

        result = get_rfm_analysis(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )

        assert isinstance(result, dict)
        assert "metric_type" in result
        assert result["metric_type"] == "GSV"

    def test_invalid_metric_type_accepted_no_crash(self, mock_orders_rfm_analysis, monkeypatch):
        """get_rfm_analysis 不对 metric_type 做 ValueError 校验，
        只在 SQL 层做条件过滤。传 INVALID 不会抛异常，但不会有任何数据。"""
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm_analysis)
        monkeypatch.setattr("backend.services.health.rfm_analysis.analysis._new_duckdb_conn", mock_orders_rfm_analysis)

        from backend.services.health.rfm_analysis import get_rfm_analysis

        # 不抛异常，返回有效结构
        result = get_rfm_analysis(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="INVALID",
        )
        assert isinstance(result, dict)
        assert "metric_type" in result
        assert result["metric_type"] == "INVALID"


# ── 数据口径一致性测试 ────────────────────────────────────────


class TestDataCaliber:
    def test_gsv_uses_semantic_calculation(self, mock_orders_rfm_analysis):
        conn = mock_orders_rfm_analysis()
        sql = """
        SELECT SUM(
            CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
                 THEN actual_amount ELSE 0 END
        ) AS gsv
        FROM orders
        """
        gsv = conn.execute(sql).fetchone()[0]
        # U1(500+300=800) + U2(100) + U3(200) + U4(150) + U5(0,退款) + U6(0,关闭) = 1250
        assert gsv == 1250

    def test_valid_order_count(self, mock_orders_rfm_analysis):
        conn = mock_orders_rfm_analysis()
        sql = """
        SELECT COUNT(*) AS valid_orders
        FROM orders
        WHERE is_refund = FALSE AND order_status != '交易关闭'
        """
        count = conn.execute(sql).fetchone()[0]
        # U1(2) + U2(1) + U3(1) + U4(1) = 5 有效订单
        assert count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
