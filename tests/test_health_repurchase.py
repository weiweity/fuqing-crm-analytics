"""health/repurchase.py + health/channel_scores.py 单元测试"""
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
    return c


class TestRepurchaseCycleEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.health.repurchase.get_connection",
            _empty_db_factory,
        )
        from backend.services.health.repurchase import get_repurchase_cycle

        result = get_repurchase_cycle(start_date="2025-06-01", end_date="2025-06-15")

        assert isinstance(result, dict)
        assert "all_store_median_days" in result
        assert "all_store_avg_days" in result


class TestChannelScoresEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.health.channel_scores.get_connection",
            _empty_db_factory,
        )
        from backend.services.health.channel_scores import get_channel_health_scores

        result = get_channel_health_scores(analysis_date="2025-06-15", period_days=30)

        assert isinstance(result, dict)
        assert "scores" in result
        assert isinstance(result["scores"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
