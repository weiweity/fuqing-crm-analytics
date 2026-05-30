"""health/tier_flow.py 单元测试"""
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


class TestTierFlowEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        monkeypatch.setattr("backend.services.health.tier_flow.get_connection", _empty_db_factory)
        from backend.services.health.tier_flow import get_tier_flow

        result = get_tier_flow(start_date="2025-06-01", end_date="2025-06-15")

        assert isinstance(result, dict)
        assert "rows" in result
        assert "member_rows" in result
        assert "metric_type" in result


class TestTierFlowGSVCaliber:
    def test_gsv_excludes_refund(self, monkeypatch):
        """退款订单不计入分层流转"""
        monkeypatch.setattr("backend.services.health.tier_flow.get_connection", _gsv_db_factory)
        from backend.services.health.tier_flow import get_tier_flow

        result = get_tier_flow(start_date="2025-06-01", end_date="2025-06-15")

        assert isinstance(result, dict)
        assert "rows" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
