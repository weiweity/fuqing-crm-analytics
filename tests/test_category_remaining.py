"""category_service/distribution.py + churn.py + basket.py 单元测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _empty_db_factory():
    import duckdb
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
    c.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR, analysis_date DATE, metric_type VARCHAR,
            lookback_days INTEGER, r_score INTEGER, f_score INTEGER,
            m_score INTEGER, rfm_score VARCHAR, r_segment VARCHAR,
            f_segment VARCHAR, m_segment VARCHAR, segment VARCHAR,
            last_pay_date DATE, first_pay_date DATE,
            total_orders INTEGER, total_amount DOUBLE,
            PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days)
        )
    """)
    return c


class TestDistributionEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.category_service.distribution.get_connection",
            _empty_db_factory,
        )
        from backend.services.category_service.distribution import get_category_distribution

        result = get_category_distribution(date="2025-06-15", lookback_days=90, level="category")

        assert isinstance(result, dict)
        assert "distribution" in result
        assert "total_gmv" in result
        assert result["distribution"] == []
        assert result["total_gmv"] == 0


class TestChurnEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.category_service.churn.get_connection",
            _empty_db_factory,
        )
        from backend.services.category_service.churn import get_category_churn

        result = get_category_churn(start_date="2025-06-01", end_date="2025-06-15", level="class")

        assert isinstance(result, dict)
        # churn 返回 bar_data/scatter_data 等结构
        assert "bar_data" in result or "scatter_data" in result or "data" in result


class TestBasketEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.category_service.basket.get_connection",
            _empty_db_factory,
        )
        from backend.services.category_service.basket import get_market_basket

        result = get_market_basket(
            start_date="2025-06-01",
            end_date="2025-06-15",
            target_category="护肤",
            level="class",
        )

        assert isinstance(result, dict)
        assert "items" in result
        assert "period_label" in result
        assert result["items"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
