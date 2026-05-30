"""breakdown_service 单元测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── 参数校验测试 ──────────────────────────────────────────────


class TestParameterValidation:
    def test_invalid_breakdown_mode_raises(self, mock_orders_breakdown, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_breakdown)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        with pytest.raises(ValueError, match="breakdown_mode must be 'forward' or 'reverse'"):
            calculate_one_click_breakdown(
                target_gmv=100000,
                activity_start="2025-06-15",
                activity_end="2025-06-20",
                breakdown_mode="invalid"
            )


# ── 顺拆模式测试 ─────────────────────────────────────────────


class TestForwardBreakdown:
    def test_forward_mode_returns_valid_structure(self, mock_orders_breakdown, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_breakdown)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        result = calculate_one_click_breakdown(
            target_gmv=50000,
            activity_start="2025-06-15",
            activity_end="2025-06-20",
            breakdown_mode="forward",
        )

        assert result["mode"] == "forward"
        assert "old_customer" in result
        assert "new_customer" in result
        assert "suggestions" in result
        assert "total_gap" in result
        assert "gap_ratio" in result
        assert result["meta"]["metric_type"] == "GSV"

    def test_forward_old_customer_ratio_target(self, mock_orders_breakdown, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_breakdown)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        r60 = calculate_one_click_breakdown(
            target_gmv=50000, activity_start="2025-06-15", activity_end="2025-06-20",
            old_customer_ratio_target=0.6, breakdown_mode="forward",
        )
        r80 = calculate_one_click_breakdown(
            target_gmv=50000, activity_start="2025-06-15", activity_end="2025-06-20",
            old_customer_ratio_target=0.8, breakdown_mode="forward",
        )

        assert r60["old_customer"]["old_gmv_target"] != r80["old_customer"]["old_gmv_target"]
        assert r80["old_customer"]["old_gmv_target"] > r60["old_customer"]["old_gmv_target"]

    def test_forward_with_custom_ly_dates(self, mock_orders_breakdown, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_breakdown)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        result = calculate_one_click_breakdown(
            target_gmv=50000,
            activity_start="2025-06-15",
            activity_end="2025-06-20",
            last_year_start="2024-06-15",
            last_year_end="2024-06-20",
            breakdown_mode="forward",
        )

        assert result["reference_period"]["start"] == "2024-06-15"
        assert result["reference_period"]["end"] == "2024-06-20"


# ── 倒拆模式测试 ─────────────────────────────────────────────


class TestReverseBreakdown:
    def test_reverse_mode_returns_valid_structure(self, mock_orders_breakdown, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_breakdown)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        result = calculate_one_click_breakdown(
            target_gmv=50000,
            activity_start="2025-06-15",
            activity_end="2025-06-20",
            breakdown_mode="reverse",
        )

        assert result["mode"] == "reverse"
        assert "old_customer" in result
        assert "new_customer" in result
        assert "suggestions" in result


# ── 工具函数测试 ─────────────────────────────────────────────


class TestSharedHelpers:
    def test_detect_activity_type(self):
        from backend.services.breakdown_service._shared import _detect_activity_type

        assert _detect_activity_type("2025-11-01", "2025-11-11") == "双11"
        assert _detect_activity_type("2025-06-01", "2025-06-20") == "618"
        assert _detect_activity_type("2025-03-01", "2025-03-08") == "3.8"
        assert _detect_activity_type("2025-01-15", "2025-01-30") == "年货节"
        assert _detect_activity_type("2025-07-01", "2025-07-10") == "大促期"

    def test_get_default_ly_dates(self):
        from backend.services.breakdown_service._shared import _get_default_ly_dates

        ly_start, ly_end = _get_default_ly_dates("2025-06-15", "2025-06-20")
        assert ly_start == "2024-06-15"
        assert ly_end == "2024-06-20"

        ly_start2, ly_end2 = _get_default_ly_dates("2025-12-31", "2026-01-05")
        assert ly_start2 == "2024-12-31"
        assert ly_end2 == "2025-01-05"

    def test_r_interval_sql_format(self):
        from backend.services.breakdown_service._shared import _r_interval_sql

        sql = _r_interval_sql("last_pay_time", "2025-06-15")
        assert "CASE" in sql
        assert "近1个月已购客" in sql
        assert "2年外已购客" in sql
        assert "2025-06-15" in sql
        assert "DATEDIFF" in sql

    def test_parse_date_and_format_date(self):
        from backend.services.breakdown_service._shared import _parse_date, _format_date

        dt = _parse_date("2025-06-15")
        assert _format_date(dt) == "2025-06-15"

    def test_parse_date_invalid_format_raises(self):
        from backend.services.breakdown_service._shared import _parse_date

        with pytest.raises(ValueError):
            _parse_date("2025/06/15")
        with pytest.raises(ValueError):
            _parse_date("06-15-2025")


# ── 口径一致性测试 ────────────────────────────────────────────


class TestGSVCaliber:
    def test_refund_excluded_from_gsv(self, mock_orders_breakdown):
        conn = mock_orders_breakdown()
        sql = """
        SELECT SUM(
            CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
                 THEN actual_amount ELSE 0 END
        ) AS gsv
        FROM orders
        """
        gsv = conn.execute(sql).fetchone()[0]
        assert gsv >= 0


# ── 边界条件测试 ─────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_orders_returns_zero_breakdown(self, monkeypatch):
        """空orders表应返回全零拆解结果（验证边界逻辑）"""
        import duckdb

        def empty_db_factory():
            # 每次调用创建独立的 :memory: 数据库，避免 DuckDB catalog 共享
            c = duckdb.connect(database=":memory:")
            # 使用完整 42 列 schema（与 conftest.py 保持一致），避免漏列导致查询失败
            c.execute("""
                CREATE TABLE orders (
                    order_id             VARCHAR, sub_order_id         VARCHAR,
                    user_id              VARCHAR, user_nickname        VARCHAR,
                    order_time           TIMESTAMP, pay_time           TIMESTAMP,
                    ship_time            TIMESTAMP, order_type         VARCHAR,
                    order_status         VARCHAR, product_id          VARCHAR,
                    merchant_code        VARCHAR, product_title       VARCHAR,
                    sku_id               VARCHAR, sku_code            VARCHAR,
                    sku_name             VARCHAR, quantity            INTEGER,
                    amount               DOUBLE, refund_status        VARCHAR,
                    refund_amount        DOUBLE, actual_amount       DOUBLE,
                    province             VARCHAR, city                VARCHAR,
                    influencer_name      VARCHAR, influencer_id      VARCHAR,
                    live_room_id        VARCHAR, video_id           VARCHAR,
                    traffic_source       VARCHAR, traffic_type        VARCHAR,
                    seller_note          VARCHAR, year               INTEGER,
                    month                INTEGER, is_member           BOOLEAN,
                    spu_category        VARCHAR, spu_type           VARCHAR,
                    spu_tier            VARCHAR, spu_product_class  VARCHAR,
                    spu_product_subclass VARCHAR, spu_cosmetic      VARCHAR,
                    spu_spec            VARCHAR, channel            VARCHAR,
                    is_goujinjin        BOOLEAN, is_refund          BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            return c

        # main.py 用 `from backend.db.connection import get_connection` 把名称绑定到本地
        monkeypatch.setattr("backend.services.breakdown_service.main.get_connection", empty_db_factory)

        from backend.services.breakdown_service import calculate_one_click_breakdown

        result = calculate_one_click_breakdown(
            target_gmv=100000,
            activity_start="2025-06-15",
            activity_end="2025-06-20",
            breakdown_mode="forward",
        )

        assert result["old_customer"]["old_gmv_estimate"] == 0
        assert result["new_customer"]["new_gmv_estimate"] == 0
        assert result["total_estimate"] == 0
        assert result["total_gap"] == result["target_gmv"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
