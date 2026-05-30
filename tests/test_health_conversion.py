"""health/conversion.py 单元测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── _quality_grade 纯函数测试 ────────────────────────────────


class TestQualityGrade:
    def test_grade_a_at_80(self):
        from backend.services.health.conversion import _quality_grade

        assert _quality_grade(80) == "A"
        assert _quality_grade(100) == "A"
        assert _quality_grade(95) == "A"

    def test_grade_b_at_60_to_79(self):
        from backend.services.health.conversion import _quality_grade

        assert _quality_grade(60) == "B"
        assert _quality_grade(79) == "B"
        assert _quality_grade(70) == "B"

    def test_grade_c_at_40_to_59(self):
        from backend.services.health.conversion import _quality_grade

        assert _quality_grade(40) == "C"
        assert _quality_grade(59) == "C"
        assert _quality_grade(50) == "C"

    def test_grade_d_below_40(self):
        from backend.services.health.conversion import _quality_grade

        assert _quality_grade(0) == "D"
        assert _quality_grade(39) == "D"
        assert _quality_grade(20) == "D"

    def test_grade_at_boundary_60(self):
        from backend.services.health.conversion import _quality_grade

        assert _quality_grade(59.9) == "C"
        assert _quality_grade(60.0) == "B"


# ── get_new_customer_conversion 边界测试 ────────────────────


class TestGetNewCustomerConversionEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        """空orders表应返回有效结构，不抛异常"""
        import duckdb

        def empty_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            return c

        monkeypatch.setattr(
            "backend.services.health.conversion.get_connection",
            empty_db_factory,
        )

        from backend.services.health.conversion import get_new_customer_conversion

        result = get_new_customer_conversion(analysis_date="2025-06-15")

        assert isinstance(result, dict)
        assert "analysis_date" in result
        assert "overall_funnel" in result
        assert "cohort_funnels" in result
        assert "channel_quality" in result
        assert "monthly_trend" in result
        # overall funnel 全零
        assert result["overall_funnel"]["total_first_purchase"] == 0
        assert result["overall_funnel"]["day7_repurchase"] == 0
        assert result["overall_funnel"]["day30_repurchase"] == 0
        assert result["overall_funnel"]["day90_repurchase"] == 0


class TestConversionDataCaliber:
    def test_refund_excluded_from_conversion(self, monkeypatch):
        """退款订单应不计入转化统计"""
        import duckdb

        def refund_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            # 插入有效订单（正常用户U1首购）
            c.execute("""
                INSERT INTO orders VALUES
                ('O1', 'S1', 'U1', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P1', 'M1', '产品A', 'SKU1', 'SC1', '名称A',
                 1, 100.0, '无退款', 0.0, 100.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, FALSE)
            """)
            # 插入退款订单（U2首购后退款）
            c.execute("""
                INSERT INTO orders VALUES
                ('O2', 'S2', 'U2', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P2', 'M1', '产品B', 'SKU2', 'SC2', '名称B',
                 1, 100.0, '退款成功', 100.0, 0.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, TRUE)
            """)
            # user_first_purchase 记录U1的首购日期（U2的首购不计入因为已退款）
            c.execute("INSERT INTO user_first_purchase VALUES ('U1', '2025-06-01')")
            return c

        monkeypatch.setattr(
            "backend.services.health.conversion.get_connection",
            refund_db_factory,
        )

        from backend.services.health.conversion import get_new_customer_conversion

        result = get_new_customer_conversion(analysis_date="2025-06-15")

        # U1（正常）计入，U2（退款）不计入
        assert result["overall_funnel"]["total_first_purchase"] == 1
        assert result["overall_funnel"]["day30_repurchase"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
