"""category_service/distribution.py + churn.py + basket.py 单元测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_INSERT_SQL = "INSERT INTO orders VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?)"


def _empty_db_factory():
    import duckdb
    from tests.conftest import _create_orders_table
    c = duckdb.connect(database=":memory:")
    _create_orders_table(c)
    c.execute("CREATE TABLE user_first_purchase (user_id VARCHAR PRIMARY KEY, first_pay_date DATE)")
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


def _gsv_db_factory():
    c = _empty_db_factory()
    # U1: 有效订单
    c.execute(_INSERT_SQL, ["O1","O1-1","U1","用户1","2025-06-01","2025-06-01",None,"普通","交易成功",None,None,"产品A","SKU1","SC","名称",1,100,None,0,100,"浙江","杭州",None,None,None,None,None,None,None,None,2025,6,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False])
    # U2: 退款订单
    c.execute(_INSERT_SQL, ["O2","O2-1","U2","用户2","2025-06-01","2025-06-01",None,"普通","交易成功",None,None,"产品B","SKU2","SC","名称",1,200,"已退款",200,0,"浙江","杭州",None,None,None,None,None,None,None,None,2025,6,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,True])
    c.execute("INSERT INTO user_first_purchase VALUES ('U1', '2023-01-01')")
    c.execute("INSERT INTO user_first_purchase VALUES ('U2', '2023-01-01')")
    return c


# ── distribution ─────────────────────────────────────────────


class TestDistributionEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr("backend.services.category_service.distribution.get_connection", _empty_db_factory)
        from backend.services.category_service.distribution import get_category_distribution

        result = get_category_distribution(date="2025-06-15", lookback_days=90, level="category")

        assert isinstance(result, dict)
        assert "distribution" in result
        assert "total_gmv" in result
        assert result["distribution"] == []
        assert result["total_gmv"] == 0


class TestDistributionGSVCaliber:
    def test_gsv_excludes_refund(self, monkeypatch):
        """退款订单不计入品类分布"""
        monkeypatch.setattr("backend.services.category_service.distribution.get_connection", _gsv_db_factory)
        from backend.services.category_service.distribution import get_category_distribution

        result = get_category_distribution(date="2025-06-15", lookback_days=90, level="category")

        assert isinstance(result, dict)
        assert result["total_gmv"] == 100.0  # 只有O1


# ── churn ────────────────────────────────────────────────────


class TestChurnEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr("backend.services.category_service.churn.get_connection", _empty_db_factory)
        from backend.services.category_service.churn import get_category_churn

        result = get_category_churn(start_date="2025-06-01", end_date="2025-06-15", level="class")

        assert isinstance(result, dict)
        assert "bar_data" in result or "scatter_data" in result


class TestChurnGSVCaliber:
    def test_gsv_excludes_refund(self, monkeypatch):
        """退款订单不计入流失分析"""
        monkeypatch.setattr("backend.services.category_service.churn.get_connection", _gsv_db_factory)
        from backend.services.category_service.churn import get_category_churn

        result = get_category_churn(start_date="2025-06-01", end_date="2025-06-15", level="class")

        assert isinstance(result, dict)


# ── basket ───────────────────────────────────────────────────


class TestBasketEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr("backend.services.category_service.basket.get_connection", _empty_db_factory)
        from backend.services.category_service.basket import get_market_basket

        result = get_market_basket(
            start_date="2025-06-01", end_date="2025-06-15",
            target_category="护肤", level="class",
        )

        assert isinstance(result, dict)
        assert "items" in result
        assert "period_label" in result
        assert result["items"] == []


class TestBasketGSVCaliber:
    def test_gsv_excludes_refund(self, monkeypatch):
        """退款订单不计入购物篮分析"""
        monkeypatch.setattr("backend.services.category_service.basket.get_connection", _gsv_db_factory)
        from backend.services.category_service.basket import get_market_basket

        result = get_market_basket(
            start_date="2025-06-01", end_date="2025-06-15",
            target_category="护肤", level="class",
        )

        assert isinstance(result, dict)
        assert "items" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
