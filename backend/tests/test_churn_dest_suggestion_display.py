"""QA coverage: churn dest lookup + 挽回建议 use display names."""

from __future__ import annotations

import duckdb

from backend.services.category_display import lookup_display_name
from backend.services.category_service.churn import get_category_churn


def _orders_ddl() -> str:
    return """
    CREATE TABLE orders (
        order_id VARCHAR,
        user_id VARCHAR,
        pay_time TIMESTAMP,
        channel VARCHAR,
        is_goujinjin BOOLEAN,
        order_status VARCHAR,
        is_refund BOOLEAN,
        spu_product_class VARCHAR,
        actual_amount DOUBLE,
        is_member BOOLEAN
    )
    """


def _rfm_ddl() -> str:
    return """
    CREATE TABLE user_rfm (
        user_id VARCHAR,
        analysis_date DATE,
        metric_type VARCHAR,
        lookback_days INTEGER,
        segment_id INTEGER
    )
    """


def _patch_conn(monkeypatch, con):
    class _Conn:
        def execute(self, query, parameters=None):
            if parameters is not None:
                return con.execute(query, parameters)
            return con.execute(query)

        def close(self):
            pass

    fake = _Conn()
    monkeypatch.setattr("backend.services.category_service.churn.get_connection", lambda: fake)
    monkeypatch.setattr("backend.db.connection.get_connection", lambda: fake)


def test_lookup_display_name_empty_and_miss():
    assert lookup_display_name({}, "") == ""
    assert lookup_display_name({}, None) == ""
    assert lookup_display_name({"洁面": "爆款洁面A"}, "洁面") == "爆款洁面A"
    assert lookup_display_name({}, "洁面") == "爆款洁面"


def test_churn_suggestion_uses_looked_up_dest_not_raw(monkeypatch):
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(_rfm_ddl())
    con.execute(
        """
        INSERT INTO orders VALUES
        ('p1', 'silent', TIMESTAMP '2026-06-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('p2', 'move', TIMESTAMP '2026-06-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('c2', 'move', TIMESTAMP '2026-07-10', '直播',
         FALSE, '交易成功', FALSE, '洁面', 100, FALSE)
        """
    )
    _patch_conn(monkeypatch, con)
    row = next(
        r
        for r in get_category_churn("2026-07-01", "2026-07-31", level="class")["table"]
        if r["category_name"] == "面膜"
    )
    assert row["top_churn_dest1"] == "爆款洁面"
    assert "洁面" not in row["挽回建议"] or "爆款洁面" in row["挽回建议"]
    assert "迁移去向 爆款洁面" in row["挽回建议"]
    assert "迁移去向 洁面" not in row["挽回建议"]
    con.close()


def test_churn_high_hazard_suggestion_has_no_raw_dest(monkeypatch):
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(_rfm_ddl())
    con.execute(
        """
        INSERT INTO orders VALUES
        ('p1', 'silent', TIMESTAMP '2026-06-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE)
        """
    )
    con.execute(
        "INSERT INTO user_rfm VALUES ('silent', DATE '2026-07-31', 'GMV', 90, 4)"
    )
    _patch_conn(monkeypatch, con)
    row = next(
        r
        for r in get_category_churn("2026-07-01", "2026-07-31", level="class")["table"]
        if r["category_name"] == "面膜"
    )
    assert row["mean_hazard"] >= 0.5
    assert row["rfm_at_risk_users"] > 0
    assert row["挽回建议"] == "优先触达 RFM 挽留象限，按回购周期召回"
    con.close()
