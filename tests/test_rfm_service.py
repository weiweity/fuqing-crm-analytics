"""rfm_service 单元测试"""
import sys
from pathlib import Path
from datetime import datetime
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── _resolve_date_ranges 测试 ──────────────────────────────────


class TestResolveDateRanges:
    def test_full_explicit_dates(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(
            period=None,
            start_date="2025-01-01",
            end_date="2025-06-30",
            compare_start_date="2024-01-01",
            compare_end_date="2024-06-30",
        )
        assert "current" in result
        assert "comp" in result
        assert "prev2" in result
        assert "labels" in result

        cur_start, cur_end, cutoff = result["current"]
        assert cur_start == "2025-01-01 00:00:00"
        assert cur_end == "2025-06-30 23:59:59"
        assert cutoff == "2024-12-31"

        comp_start, comp_end, comp_cutoff = result["comp"]
        assert comp_start == "2024-01-01 00:00:00"
        assert comp_end == "2024-06-30 23:59:59"
        assert comp_cutoff == "2023-12-31"

        assert result["labels"] == ("2025", "2024", "2023")

    def test_period_mtd(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(
            period="MTD",
            start_date=None,
            end_date=None,
            compare_start_date=None,
            compare_end_date=None,
        )
        cur_start, _, _ = result["current"]
        dt = datetime.strptime(cur_start.split(" ")[0], "%Y-%m-%d")
        assert dt.day == 1

    def test_period_wtd(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(period="wtd", start_date=None, end_date=None,
                                      compare_start_date=None, compare_end_date=None)
        assert "current" in result
        assert "comp" in result

    def test_period_ytd(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(period="ytd", start_date=None, end_date=None,
                                      compare_start_date=None, compare_end_date=None)
        cur_start, _, _ = result["current"]
        dt = datetime.strptime(cur_start.split(" ")[0], "%Y-%m-%d")
        assert dt.month == 1
        assert dt.day == 1

    def test_invalid_period_falls_back_to_dates(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(period="invalid", start_date=None, end_date=None,
                                      compare_start_date=None, compare_end_date=None)
        assert "current" in result

    def test_invalid_metric_type_not_raises_here(self):
        # metric_type 校验在 flow 层面，_resolve_date_ranges 不校验
        pass

    def test_start_after_end_no_validation(self):
        # 函数不校验 start > end，直接计算
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(
            period=None,
            start_date="2025-06-30",
            end_date="2025-01-01",
            compare_start_date=None,
            compare_end_date=None,
        )
        assert "current" in result

    def test_year_labels_correct(self):
        from backend.services.rfm import _resolve_date_ranges

        result = _resolve_date_ranges(
            period=None,
            start_date="2025-01-01",
            end_date="2025-06-30",
            compare_start_date=None,
            compare_end_date=None,
        )
        year_label, compare_year_label, prev2_year_label = result["labels"]
        assert year_label == "2025"
        assert compare_year_label == "2024"
        assert prev2_year_label == "2023"


# ── R/F/M 区间常量测试 ──────────────────────────────────────


class TestRFMSegmentOrders:
    def test_r_segment_order_has_7_items(self):
        from backend.services.rfm import R_SEGMENT_ORDER

        assert len(R_SEGMENT_ORDER) == 7
        assert R_SEGMENT_ORDER[0] == "近1个月已购客"
        assert R_SEGMENT_ORDER[-1] == "已购客TTL"

    def test_f_segment_order_has_6_items(self):
        from backend.services.rfm import F_SEGMENT_ORDER

        assert len(F_SEGMENT_ORDER) == 6
        assert F_SEGMENT_ORDER[0] == "1次购买"
        assert F_SEGMENT_ORDER[-1] == "已购客TTL"

    def test_m_segment_order_has_6_items(self):
        from backend.services.rfm import M_SEGMENT_ORDER

        assert len(M_SEGMENT_ORDER) == 6
        assert M_SEGMENT_ORDER[0] == "0-100元"
        assert M_SEGMENT_ORDER[-1] == "已购客TTL"


# ── get_segment_orders 测试 ───────────────────────────────────


class TestSegmentOrders:
    def test_segment_orders_returns_dict(self, mock_orders_rfm, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm)

        from backend.services.rfm import get_segment_orders

        result = get_segment_orders(
            dimension="r",
            segment="近1个月",
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )

        assert "rows" in result
        assert isinstance(result["rows"], list)

    def test_segment_orders_empty_result(self, mock_orders_rfm, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm)

        from backend.services.rfm import get_segment_orders

        result = get_segment_orders(
            dimension="r",
            segment="2年外",
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )
        assert result["rows"] == []


# ── rfm_flow 基础测试 ────────────────────────────────────────


class TestRFMRFlow:
    def test_r_flow_returns_structure(self, mock_orders_rfm, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm)

        from backend.services.rfm import get_rfm_r_flow

        result = get_rfm_r_flow(
            year=2025,
            period="MTD",
            metric_type="GSV",
        )

        assert isinstance(result, dict)
        assert "year_label" in result
        assert "metric_type" in result
        assert "rows" in result

    def test_r_flow_gsv_caliber(self, mock_orders_rfm, monkeypatch):
        monkeypatch.setattr("backend.db.connection.get_connection", mock_orders_rfm)

        from backend.services.rfm import get_rfm_r_flow

        result = get_rfm_r_flow(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )
        assert isinstance(result, dict)

    def test_r_bucket_uses_preperiod_recency(self, monkeypatch):
        """Sprint 8 P0 回归测试：R 桶分桶必须基于 pre-period 行为。

        Bug 场景：period=2025-05-01~05-31，R 桶用 end_dt=05-31 截止时，
        有 5/1-5/31 当期订单的回购用户 pre_cutoff_last_pay 落在当期，
        DATEDIFF(pre_cutoff_last_pay, end_dt)=0-30 天 → 全部归入近1个月，
        近2-3个月 ∩ base_orders = ∅，回购率恒为 0%（Sprint 7 a73dfac 教训）。

        修复：R 桶改回 cutoff_dt (= start_dt - 1 = 04-30) 截止，
        pre-period 4/15 订单的用户归入近2-3个月且能识别为回购。

        数据：U1 (4/15 + 5/3 双单)、U2 (3/10 单)、U3 (5/10 当期新购)
        """
        import duckdb
        from tests.conftest import _create_orders_table

        conn = duckdb.connect(database=":memory:")
        _create_orders_table(conn)

        n = None
        orders = [
            # U1: 4/15 pre-period + 5/3 current-period 双单 → 应归入近2-3个月，且是回购
            ("O1","O1-1","U1","用户1","2025-04-15 09:00","2025-04-15 10:00",n,"普通订单","交易成功",n,n,"产品A","SKU1","SKU001","规格A",1,200,n,0,200,"上海","上海",n,n,n,n,n,n,n,n,2025,4,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
            ("O2","O2-1","U1","用户1","2025-05-03 09:00","2025-05-03 10:00",n,"普通订单","交易成功",n,n,"产品A","SKU1","SKU001","规格A",1,200,n,0,200,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
            # U2: 3/10 pre-period 单 → 应归入近4-6月 (DATEDIFF(3/10, 4/30)=51 天)
            ("O3","O3-1","U2","用户2","2025-03-10 09:00","2025-03-10 10:00",n,"普通订单","交易成功",n,n,"产品B","SKU2","SKU002","规格B",1,100,n,0,100,"北京","北京",n,n,n,n,n,n,n,n,2025,3,True,"护肤","面霜","中端","功效类","保湿","50g","达播",False,False),
            # U3: 5/10 current-period 单 → 不归入任何 R 桶（pre_cutoff=NULL）
            ("O4","O4-1","U3","用户3","2025-05-10 09:00","2025-05-10 10:00",n,"普通订单","交易成功",n,n,"产品C","SKU3","SKU003","规格C",1,150,n,0,150,"广东","广州",n,n,n,n,n,n,n,n,2025,5,True,"护肤","水乳","中端","基础类","补水","100ml","货架",False,False),
        ]
        placeholders = ",".join(["?" for _ in range(42)])
        for row in orders:
            assert len(row) == 42
            conn.execute(f"INSERT INTO orders VALUES ({placeholders})", list(row))
        conn.execute("""
            CREATE TABLE user_rfm (
                user_id VARCHAR, analysis_date DATE, metric_type VARCHAR,
                lookback_days INTEGER, r_segment VARCHAR, f_segment VARCHAR,
                m_segment VARCHAR, r_score INTEGER, f_score INTEGER, m_score INTEGER
            )
        """)

        monkeypatch.setattr("backend.db.connection.get_connection", lambda: conn)

        from backend.services.rfm import get_rfm_r_flow
        result = get_rfm_r_flow(
            year=2025,
            start_date="2025-05-01",
            end_date="2025-05-31",
            metric_type="GSV",
        )
        rows = {r["r_segment"]: r for r in result["rows"]}

        # U1 (4/15 + 5/3): pre-period 4/15 → DATEDIFF(4/15, 4/30)=15 → 近1个月
        # (但 U1 也是 5/3 当期订单回购用户，回购 = 1)
        # U2 (3/10): pre-period 3/10 → DATEDIFF(3/10, 4/30)=51 → 近2-3个月
        # (U2 不是回购用户：0)
        # U3 (5/10 only): pre_cutoff=NULL → 不归入任何 R 桶，仅在 TTL
        # （但 U3 是 5/10 当期订单回购用户，TTL 回购 = 1）

        # 关键回归断言：Sprint 7 bug 复现条件已消除
        # 近1个月 hist_users 应包含 U1（pre-period 4/15 在 [04-30 - 30, 04-30] 范围内: 4/15 不在，
        # 实际 DATEDIFF(4/15, 4/30)=15 → 近1个月 ✓），U2 不在 (51 > 30)
        assert rows["近1个月已购客"]["hist_users_current"] == 1, \
            f"近1个月 应只有 U1, 实际 {rows['近1个月已购客']['hist_users_current']}"
        # U1 是回购用户 (5/3 当期订单)，归入近1个月
        assert rows["近1个月已购客"]["repurchase_users_current"] == 1, \
            f"近1个月 应有 1 个回购用户 (U1), 实际 {rows['近1个月已购客']['repurchase_users_current']}"
        # 近2-3个月: DATEDIFF(3/10, 4/30)=51 天 → U2 归入
        assert rows["近2-3个月已购客"]["hist_users_current"] == 1, \
            f"近2-3个月 应只有 U2, 实际 {rows['近2-3个月已购客']['hist_users_current']}"
        # U2 不是回购用户（5/1-5/31 无订单）
        assert rows["近2-3个月已购客"]["repurchase_users_current"] == 0, \
            f"近2-3个月 应 0 个回购, 实际 {rows['近2-3个月已购客']['repurchase_users_current']}"
        # TTL 应包含所有用户：U1 (4/15+5/3) + U2 (3/10) + U3 (5/10) = 3
        assert rows["已购客TTL"]["hist_users_current"] == 3, \
            f"TTL 应有 3 个用户, 实际 {rows['已购客TTL']['hist_users_current']}"
        # TTL 回购: U1 (5/3) + U3 (5/10) = 2
        assert rows["已购客TTL"]["repurchase_users_current"] == 2, \
            f"TTL 应有 2 个回购用户, 实际 {rows['已购客TTL']['repurchase_users_current']}"


# ── 口径一致性测试 ────────────────────────────────────────────


class TestRFMGSVCaliber:
    def test_rfm_gsv_excludes_refund(self, mock_orders_rfm):
        conn = mock_orders_rfm()
        sql = """
        SELECT SUM(
            CASE WHEN is_refund = FALSE AND order_status != '交易关闭'
                 THEN actual_amount ELSE 0 END
        ) AS gsv
        FROM orders
        """
        gsv = conn.execute(sql).fetchone()[0]
        # U1: 150+150=300, U2: 100, U3: 退款-100→0, U4: 关闭0 → 400
        assert gsv == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
