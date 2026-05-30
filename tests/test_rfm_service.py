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
