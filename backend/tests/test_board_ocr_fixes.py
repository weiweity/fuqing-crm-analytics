"""OCR ship-review follow-ups: wool score, churn hazard, daily-trend placeholders."""

from __future__ import annotations

import duckdb

from backend.services.category_service.churn import (
    _build_daily_trend_filter,
    get_category_churn,
    get_category_daily_trend,
)
from backend.services.category_service.overview import _compute_wool_party_breakdown


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


def test_wool_never_converted_scores_high():
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(
        """
        INSERT INTO orders VALUES
        ('s1', 'new_sample', TIMESTAMP '2026-07-10', 'U先派样',
         FALSE, '交易成功', FALSE, '面膜', 1, FALSE)
        """
    )
    result = _compute_wool_party_breakdown(
        con, "2026-07-01", "2026-07-31", "class", None, None,
    )
    row = result["面膜"]
    assert row["never_converted_count"] == 1
    assert row["mean_score"] >= 0.70
    assert row["high_risk_count"] == 1
    con.close()


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


def test_churn_repurchase_has_zero_hazard(monkeypatch):
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(_rfm_ddl())
    con.execute(
        """
        INSERT INTO orders VALUES
        ('p1', 'u1', TIMESTAMP '2026-06-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('c1', 'u1', TIMESTAMP '2026-07-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE)
        """
    )
    _patch_conn(monkeypatch, con)
    out = get_category_churn("2026-07-01", "2026-07-31", level="class")
    rows = [r for r in out["table"] if r["category_name"] == "面膜"]
    assert rows
    assert rows[0]["mean_hazard"] == 0.0
    con.close()


def test_daily_trend_placeholder_count_matches_params():
    where_sql, where_params = _build_daily_trend_filter(
        "2026-07-01", "2026-07-31", "面膜", "daily",
    )
    body = f"""
    SELECT COUNT(DISTINCT CASE WHEN u.first_pay_date >= ?::DATE THEN o.user_id END)
    FROM orders o
    LEFT JOIN user_first_purchase u ON o.user_id = u.user_id
    WHERE {where_sql}
    """
    params = ["2026-06-30"] + list(where_params)
    assert body.count("?") == len(params)
    assert params[0] == "2026-06-30"
    assert "2026-07-01 00:00:00" in params


def test_daily_trend_ratio_uses_all_buyers(monkeypatch):
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute("CREATE TABLE user_first_purchase (user_id VARCHAR, first_pay_date DATE)")
    con.execute(
        """
        INSERT INTO orders VALUES
        ('n1', 'newu', TIMESTAMP '2026-07-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 50, FALSE),
        ('o1', 'oldu', TIMESTAMP '2026-07-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 50, FALSE)
        """
    )
    con.execute(
        """
        INSERT INTO user_first_purchase VALUES
        ('newu', DATE '2026-07-10'),
        ('oldu', DATE '2025-01-01')
        """
    )
    _patch_conn(monkeypatch, con)
    out = get_category_daily_trend("面膜", "2026-07-01", "2026-07-31")
    assert out["user_count"] == [2]
    assert out["new_customer_ratio"] == [0.5]
    con.close()


def test_wool_converted_then_sample_and_lifetime_cutoff():
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(
        """
        INSERT INTO orders VALUES
        ('f1', 'conv', TIMESTAMP '2026-01-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('s1', 'conv', TIMESTAMP '2026-07-10', 'U先派样',
         FALSE, '交易成功', FALSE, '面膜', 1, FALSE),
        ('s2', 'late', TIMESTAMP '2026-07-10', 'U先派样',
         FALSE, '交易成功', FALSE, '面膜', 1, FALSE),
        ('f2', 'late', TIMESTAMP '2026-08-01', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('s3', 'mix', TIMESTAMP '2026-07-10', 'U先派样',
         FALSE, '交易成功', FALSE, '面膜', 1, FALSE),
        ('f3', 'mix', TIMESTAMP '2026-07-20', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE)
        """
    )
    result = _compute_wool_party_breakdown(
        con, "2026-07-01", "2026-07-31", "class", None, None,
    )
    row = result["面膜"]
    assert row["converted_then_sample_count"] == 1
    assert row["never_converted_count"] == 1
    assert row["high_risk_count"] == 2
    con.close()


def test_churn_dest_ratio_uses_inter_churn_and_rfm_bump(monkeypatch):
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
    con.execute(
        "INSERT INTO user_rfm VALUES ('silent', DATE '2026-07-31', 'GMV', 90, 4)"
    )
    _patch_conn(monkeypatch, con)
    row = next(
        r
        for r in get_category_churn("2026-07-01", "2026-07-31", level="class")["table"]
        if r["category_name"] == "面膜"
    )
    assert row["silent_churn"] == 1
    assert row["inter_churn"] == 1
    assert row["top_churn_dest1_ratio"] == 1.0
    assert row["mean_hazard"] > 0
    assert row["rfm_at_risk_users"] == 1
    con.close()


def test_churn_dest_ratio_excludes_retained_multi_category(monkeypatch):
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
         FALSE, '交易成功', FALSE, '洁面', 100, FALSE),
        ('p3', 'keep', TIMESTAMP '2026-06-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('c3a', 'keep', TIMESTAMP '2026-07-10', '直播',
         FALSE, '交易成功', FALSE, '面膜', 100, FALSE),
        ('c3b', 'keep', TIMESTAMP '2026-07-11', '直播',
         FALSE, '交易成功', FALSE, '洁面', 80, FALSE)
        """
    )
    _patch_conn(monkeypatch, con)
    row = next(
        r
        for r in get_category_churn("2026-07-01", "2026-07-31", level="class")["table"]
        if r["category_name"] == "面膜"
    )
    assert row["silent_churn"] == 1
    assert row["inter_churn"] == 1
    assert row["top_churn_dest1_ratio"] <= 1.0
    assert row["top_churn_dest1_ratio"] == 1.0
    con.close()


def test_rfm_asof_cte_picks_latest_on_or_before_end():
    from backend.services.category_service._shared import rfm_asof_cte

    con = duckdb.connect(":memory:")
    con.execute(_rfm_ddl())
    con.execute(
        """
        INSERT INTO user_rfm VALUES
        ('u1', DATE '2026-08-01', 'GMV', 90, 1),
        ('u1', DATE '2026-06-01', 'GMV', 90, 8),
        ('u1', DATE '2026-01-01', 'GMV', 90, 2),
        ('u1', DATE '2026-07-31', 'GMV', 365, 1),
        ('u2', DATE '2026-06-01', 'GMV', 90, 1)
        """
    )
    cte, params = rfm_asof_cte("2026-07-31", "window_users")
    rows = {
        r[0]: r[1]
        for r in con.execute(
            f"""
            WITH window_users AS (SELECT 'u1' AS user_id),
            {cte}
            SELECT user_id, segment_id FROM rfm_asof
            """,
            params,
        ).fetchall()
    }
    assert rows == {"u1": 8}
    con.close()


def test_rfm_asof_cte_rejects_unknown_users_cte():
    from backend.services.category_service._shared import rfm_asof_cte

    try:
        rfm_asof_cte("2026-07-31", "orders; DROP TABLE user_rfm")
    except ValueError as exc:
        assert "unsupported rfm users cte" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_daily_trend_cutoff_binds_before_where_and_uses_month_start(monkeypatch):
    import inspect
    from backend.services.category_service.churn import get_category_daily_trend

    src = inspect.getsource(get_category_daily_trend)
    assert "params = [cutoff_date] + list(where_params)" in src
    con = duckdb.connect(":memory:")
    con.execute(_orders_ddl())
    con.execute(
        "CREATE TABLE user_first_purchase (user_id VARCHAR, first_pay_date DATE)"
    )
    con.execute(
        """
        INSERT INTO orders VALUES
        ('o1', 'u1', TIMESTAMP '2026-07-20', '直播',
         FALSE, '交易成功', FALSE, '面膜', 50, FALSE)
        """
    )
    con.execute("INSERT INTO user_first_purchase VALUES ('u1', DATE '2026-07-10')")
    _patch_conn(monkeypatch, con)
    out = get_category_daily_trend("面膜", "2026-07-15", "2026-07-31")
    assert out["user_count"] == [1]
    assert out["new_customer_ratio"] == [1.0]
    con.close()
