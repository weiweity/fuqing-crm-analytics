"""访客入会率服务必须返回 0-1 raw，禁止在返回前 *100。"""
import duckdb
import pytest

from backend.services import visitor_service


def test_visitor_summary_and_trend_use_raw_ratio(monkeypatch):
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE daily_visitors (
            date DATE,
            visitors INTEGER,
            new_members INTEGER,
            member_join_rate DOUBLE
        )
        """
    )
    conn.execute("INSERT INTO daily_visitors VALUES ('2026-06-01', 10, 5, 0.5)")
    conn.execute("INSERT INTO daily_visitors VALUES ('2025-06-01', 10, 2, 0.2)")
    monkeypatch.setattr(visitor_service, "get_connection", lambda: conn)
    summary = visitor_service.get_visitor_summary("2026-06-01", "2026-06-01")
    assert summary["member_join_rate"] == pytest.approx(0.5)
    assert summary["ly_member_join_rate"] == pytest.approx(0.2)
    assert summary["member_join_rate_yoy"] == pytest.approx(0.3)
    assert summary["member_join_rate"] <= 1
    trend = visitor_service.get_visitor_daily_trend("2026-06-01", "2026-06-01")
    assert trend[0]["member_join_rate"] == pytest.approx(0.5)
    assert trend[0]["ly_member_join_rate"] == pytest.approx(0.2)
    conn.close()


def test_visitor_service_source_does_not_scale_by_100():
    from pathlib import Path
    source = Path(visitor_service.__file__).read_text(encoding="utf8")
    assert "float(row[2]) * 100" not in source
    assert "round(rate * 100" not in source
    assert "round(float(comp_row[3]) * 100" not in source
