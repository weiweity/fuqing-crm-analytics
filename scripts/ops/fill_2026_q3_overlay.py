#!/usr/bin/env python3
"""Build a writable overlay + wrapper around the archive DuckDB.

Does NOT copy or mutate the archive. Requires:

  FQ_ARCHIVE_DUCKDB   read-only archive path (ATTACH only)
  FQ_DUCKDB_WRAPPER   new wrapper path (created/replaced)

Copies 2023-07-06..2023-09-15 orders into fill_* tables with +3 years and
synthetic user_ids so 2026-07-06..2026-09-15 keeps the source-year new/old
mix. Visitors copy 2025-07-06..2025-09-15 +1 year. Point DUCKDB_PATH at the
wrapper and FQ_ARCHIVE_DUCKDB at the archive.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb


FILL_USER_PREFIX = "SYN26-U-"
SRC_ORDER_START = "2023-07-06"
SRC_ORDER_END_EXCL = "2023-09-16"
SRC_VISITOR_START = "2025-07-06"
SRC_VISITOR_END_EXCL = "2025-09-16"
# Archive user_rfm_precompute has no as_of <= 2023-07-06; nearest 3650 snapshot is 2023-07-09.
SRC_PRECOMPUTE_ASOF = "2023-07-09"
PRECOMPUTE_LOOKBACK_DAYS = 3650
# Health RFM as_of = period start. Q3 2026 starts 2026-07-01; fill window starts 2026-07-06.
HEALTH_PRECOMPUTE_ASOFS = ("2026-07-01", "2026-07-06")
RFM_LOOKBACK_DAYS = 90
# GMV/90 as-of = last day of the source order window (exclusive end - 1).
RFM_ASOF = (date.fromisoformat(SRC_ORDER_END_EXCL) - timedelta(days=1)).isoformat()
RFM_LOOKBACK_START = (
    date.fromisoformat(RFM_ASOF) - timedelta(days=RFM_LOOKBACK_DAYS)
).isoformat()


def quote_duckdb_literal(value: str) -> str:
    return value.replace("'", "''")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def compute_gmv90_fill_user_rfm_sql() -> str:
    """GMV/90 from src.orders for fill users. Scores match semantic.segments SSOT.

    Used when archive user_rfm has no analysis_date <= source window end.
    Do not copy 2026 RFM onto SYN26 users.
    """
    return f"""
            CREATE TABLE fill_user_rfm AS
            WITH fill_users AS (
                SELECT DISTINCT CAST(user_id AS VARCHAR) AS user_id
                FROM src.orders
                WHERE pay_time >= TIMESTAMP '{SRC_ORDER_START}'
                  AND pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
            ),
            stats AS (
                SELECT
                    CAST(o.user_id AS VARCHAR) AS user_id,
                    DATEDIFF('day', MAX(o.pay_time)::DATE, DATE '{RFM_ASOF}') AS recency_days,
                    COUNT(DISTINCT o.order_id)::INTEGER AS frequency,
                    COALESCE(SUM(o.actual_amount), 0) AS monetary,
                    MIN(o.pay_time)::DATE AS first_order_date,
                    MAX(o.pay_time)::DATE AS last_order_date,
                    BOOL_OR(o.is_member) AS is_member
                FROM src.orders o
                INNER JOIN fill_users f
                  ON CAST(o.user_id AS VARCHAR) = f.user_id
                WHERE o.pay_time >= TIMESTAMP '{RFM_LOOKBACK_START}'
                  AND o.pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
                  AND o.is_goujinjin = FALSE
                  AND o.order_status != '交易关闭'
                GROUP BY CAST(o.user_id AS VARCHAR)
            ),
            scored AS (
                SELECT
                    user_id,
                    recency_days,
                    frequency,
                    monetary,
                    CASE
                        WHEN recency_days < 30 THEN 5
                        WHEN recency_days < 90 THEN 4
                        WHEN recency_days < 180 THEN 3
                        WHEN recency_days < 365 THEN 2
                        ELSE 1
                    END AS r_score,
                    CASE
                        WHEN frequency >= 5 THEN 5
                        WHEN frequency >= 4 THEN 4
                        WHEN frequency = 3 THEN 3
                        WHEN frequency = 2 THEN 2
                        ELSE 1
                    END AS f_score,
                    CASE
                        WHEN monetary >= 1000 THEN 5
                        WHEN monetary >= 500 THEN 4
                        WHEN monetary >= 300 THEN 3
                        WHEN monetary >= 100 THEN 2
                        ELSE 1
                    END AS m_score,
                    first_order_date,
                    last_order_date,
                    is_member
                FROM stats
            )
            SELECT
                ('{FILL_USER_PREFIX}' || user_id) AS user_id,
                CAST(NULL AS VARCHAR) AS user_nickname,
                DATE '{RFM_ASOF}' + INTERVAL 3 YEAR AS analysis_date,
                'GMV' AS metric_type,
                {RFM_LOOKBACK_DAYS} AS lookback_days,
                '全店' AS channel,
                recency_days,
                frequency,
                CAST(monetary AS DECIMAL(12,2)) AS monetary,
                r_score,
                f_score,
                m_score,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
                    WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
                    WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN '重要发展客户'
                    WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN '重要挽留客户'
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN '一般价值客户'
                    WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN '一般保持客户'
                    WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN '一般发展客户'
                    ELSE '一般挽留客户'
                END AS rfm_tier,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
                    WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN 'Loyal Customers'
                    WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN 'Potential Loyalists'
                    WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN 'At Risk'
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN 'New Customers'
                    WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN 'Promising'
                    WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN 'Need Attention'
                    ELSE 'About to Sleep'
                END AS rfm_tier_en,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 1
                    WHEN r_score < 4 AND f_score >= 4 AND m_score >= 4 THEN 2
                    WHEN r_score >= 4 AND f_score < 4 AND m_score >= 4 THEN 3
                    WHEN r_score < 4 AND f_score < 4 AND m_score >= 4 THEN 4
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score < 4 THEN 5
                    WHEN r_score < 4 AND f_score >= 4 AND m_score < 4 THEN 6
                    WHEN r_score >= 4 AND f_score < 4 AND m_score < 4 THEN 7
                    ELSE 8
                END AS segment_id,
                first_order_date + INTERVAL 3 YEAR AS first_order_date,
                last_order_date + INTERVAL 3 YEAR AS last_order_date,
                CURRENT_TIMESTAMP AS created_at,
                is_member
            FROM scored
            """


def required_path(env_name: str) -> Path:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        print(f"ERROR: set {env_name} to an absolute path", file=sys.stderr)
        raise SystemExit(2)
    return Path(raw)


def main() -> int:
    archive = required_path("FQ_ARCHIVE_DUCKDB")
    wrapper = required_path("FQ_DUCKDB_WRAPPER")
    if not archive.is_file():
        print(f"ERROR: archive missing: {archive}", file=sys.stderr)
        return 1
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    if wrapper.exists():
        wrapper.unlink()
    print(f"archive={archive}")
    print(f"wrapper={wrapper}")
    con = duckdb.connect(str(wrapper))
    con.execute(
        f"ATTACH '{quote_duckdb_literal(str(archive))}' AS src (READ_ONLY)"
    )
    print("copying 2023-07-06..2023-09-15 orders → 2026 (+3 years, synthetic users) ...")
    con.execute(
        f"""
        CREATE TABLE fill_orders AS
        SELECT * REPLACE (
            ('SYN26-' || CAST(order_id AS VARCHAR)) AS order_id,
            ('{FILL_USER_PREFIX}' || CAST(user_id AS VARCHAR)) AS user_id,
            order_time + INTERVAL 3 YEAR AS order_time,
            pay_time + INTERVAL 3 YEAR AS pay_time,
            ship_time + INTERVAL 3 YEAR AS ship_time
        )
        FROM src.orders
        WHERE pay_time >= TIMESTAMP '{SRC_ORDER_START}'
          AND pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
        """
    )
    n_orders = con.execute("SELECT count(*) FROM fill_orders").fetchone()[0]
    print(f"fill_orders={n_orders}")

    src_tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src' AND internal = false"
        ).fetchall()
    }

    print("overlay user_first_purchase for synthetic fill users (+3 years) ...")
    if "user_first_purchase" in src_tables:
        con.execute(
            f"""
            CREATE TABLE fill_user_first_purchase AS
            WITH fill_users AS (
                SELECT DISTINCT user_id,
                       MIN(CAST(pay_time AS DATE)) AS min_src_pay
                FROM src.orders
                WHERE pay_time >= TIMESTAMP '{SRC_ORDER_START}'
                  AND pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
                GROUP BY user_id
            )
            SELECT
                ('{FILL_USER_PREFIX}' || CAST(f.user_id AS VARCHAR)) AS user_id,
                COALESCE(u.first_pay_date, f.min_src_pay) + INTERVAL 3 YEAR AS first_pay_date
            FROM fill_users f
            LEFT JOIN src.user_first_purchase u
              ON CAST(u.user_id AS VARCHAR) = CAST(f.user_id AS VARCHAR)
            """
        )
    else:
        con.execute(
            """
            CREATE TABLE fill_user_first_purchase AS
            SELECT user_id, MIN(CAST(pay_time AS DATE)) AS first_pay_date
            FROM fill_orders
            GROUP BY user_id
            """
        )
    n_ufp = con.execute("SELECT count(*) FROM fill_user_first_purchase").fetchone()[0]
    print(f"fill_user_first_purchase={n_ufp}")

    print("copying 2025-07-06..2025-09-15 visitors → 2026 (+1 year) ...")
    if "daily_visitors" in src_tables:
        con.execute(
            f"""
            CREATE TABLE fill_daily_visitors AS
            SELECT
                CAST(date + INTERVAL 1 YEAR AS DATE) AS date,
                visitors,
                new_members,
                member_join_rate
            FROM src.daily_visitors
            WHERE date >= DATE '{SRC_VISITOR_START}' AND date < DATE '{SRC_VISITOR_END_EXCL}'
            """
        )
    else:
        con.execute(
            """
            CREATE TABLE fill_daily_visitors AS
            SELECT
                CAST(NULL AS DATE) AS date,
                CAST(NULL AS BIGINT) AS visitors,
                CAST(NULL AS BIGINT) AS new_members,
                CAST(NULL AS DOUBLE) AS member_join_rate
            WHERE 1 = 0
            """
        )
    n_vis = con.execute("SELECT count(*) FROM fill_daily_visitors").fetchone()[0]
    print(f"fill_daily_visitors={n_vis}")

    print("overlay user_rfm for synthetic fill users (as-of source window, +3 years) ...")
    if "user_rfm" in src_tables:
        con.execute(
            f"""
            CREATE TABLE fill_user_rfm AS
            WITH fill_users AS (
                SELECT DISTINCT CAST(user_id AS VARCHAR) AS user_id
                FROM src.orders
                WHERE pay_time >= TIMESTAMP '{SRC_ORDER_START}'
                  AND pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
            ),
            ranked AS (
                SELECT u.*,
                       ROW_NUMBER() OVER (
                         PARTITION BY CAST(u.user_id AS VARCHAR), u.metric_type,
                                      u.lookback_days, COALESCE(u.channel, '')
                         ORDER BY u.analysis_date DESC
                       ) AS rn
                FROM src.user_rfm u
                INNER JOIN fill_users f
                  ON CAST(u.user_id AS VARCHAR) = f.user_id
                WHERE u.analysis_date <= DATE '{SRC_ORDER_END_EXCL}' - INTERVAL 1 DAY
            )
            SELECT * EXCLUDE (rn) REPLACE (
                ('{FILL_USER_PREFIX}' || CAST(user_id AS VARCHAR)) AS user_id,
                analysis_date + INTERVAL 3 YEAR AS analysis_date,
                CASE WHEN first_order_date IS NOT NULL
                     THEN first_order_date + INTERVAL 3 YEAR END AS first_order_date,
                CASE WHEN last_order_date IS NOT NULL
                     THEN last_order_date + INTERVAL 3 YEAR END AS last_order_date
            )
            FROM ranked
            WHERE rn = 1
            """
        )
        n_rfm = con.execute("SELECT count(*) FROM fill_user_rfm").fetchone()[0]
        n_gmv90 = con.execute(
            """
            SELECT count(*) FROM fill_user_rfm
            WHERE metric_type = 'GMV' AND lookback_days = 90
            """
        ).fetchone()[0]
        if n_gmv90 == 0:
            print(
                "src.user_rfm has no GMV/90 as-of source window; "
                "computing from src.orders (not copying 2026 RFM) ..."
            )
            con.execute("DROP TABLE fill_user_rfm")
            con.execute(compute_gmv90_fill_user_rfm_sql())
            n_rfm = con.execute("SELECT count(*) FROM fill_user_rfm").fetchone()[0]
            print(f"fill_user_rfm={n_rfm} (computed GMV/90 as-of {RFM_ASOF} +3y)")
        else:
            print(f"fill_user_rfm={n_rfm}")
    else:
        n_rfm = 0
        print("fill_user_rfm=0 (src.user_rfm missing)")

    print(
        "overlay user_rfm_precompute for health RFM "
        f"(src as_of {SRC_PRECOMPUTE_ASOF} lookback {PRECOMPUTE_LOOKBACK_DAYS} "
        f"→ {', '.join(HEALTH_PRECOMPUTE_ASOFS)}; not copying 2026 RFM) ..."
    )
    if "user_rfm_precompute" in src_tables:
        asof_selects = " UNION ALL ".join(
            f"""
            SELECT
                DATE '{asof}' AS as_of_date,
                lookback_days,
                ('{FILL_USER_PREFIX}' || user_id) AS user_id,
                last_pay_time + INTERVAL 3 YEAR AS last_pay_time,
                order_count,
                gsv,
                is_member,
                r_score,
                f_score,
                m_score,
                r_interval,
                rfm_segment,
                CURRENT_TIMESTAMP AS updated_at
            FROM snap
            """
            for asof in HEALTH_PRECOMPUTE_ASOFS
        )
        con.execute(
            f"""
            CREATE TABLE fill_user_rfm_precompute AS
            WITH fill_users AS (
                SELECT DISTINCT CAST(user_id AS VARCHAR) AS user_id
                FROM src.orders
                WHERE pay_time >= TIMESTAMP '{SRC_ORDER_START}'
                  AND pay_time < TIMESTAMP '{SRC_ORDER_END_EXCL}'
            ),
            snap AS (
                SELECT
                    CAST(u.user_id AS VARCHAR) AS user_id,
                    u.lookback_days,
                    u.last_pay_time,
                    u.order_count,
                    u.gsv,
                    u.is_member,
                    u.r_score,
                    u.f_score,
                    u.m_score,
                    u.r_interval,
                    u.rfm_segment
                FROM src.user_rfm_precompute u
                INNER JOIN fill_users f
                  ON CAST(u.user_id AS VARCHAR) = f.user_id
                WHERE u.as_of_date = DATE '{SRC_PRECOMPUTE_ASOF}'
                  AND u.lookback_days = {PRECOMPUTE_LOOKBACK_DAYS}
            )
            {asof_selects}
            """
        )
        n_pre = con.execute("SELECT count(*) FROM fill_user_rfm_precompute").fetchone()[0]
        print(f"fill_user_rfm_precompute={n_pre}")
    else:
        n_pre = 0
        print("fill_user_rfm_precompute=0 (src.user_rfm_precompute missing)")

    skip = {"orders", "daily_visitors", "user_first_purchase", "user_rfm", "user_rfm_precompute"}
    for table in sorted(src_tables):
        if table in skip:
            continue
        ident = quote_ident(table)
        con.execute(f"CREATE OR REPLACE VIEW {ident} AS SELECT * FROM src.{ident}")

    con.execute(
        """
        CREATE OR REPLACE VIEW orders AS
        SELECT * FROM src.orders
        UNION ALL BY NAME
        SELECT * FROM fill_orders
        """
    )
    if "daily_visitors" in src_tables:
        con.execute(
            """
            CREATE OR REPLACE VIEW daily_visitors AS
            SELECT * FROM src.daily_visitors
            UNION ALL BY NAME
            SELECT * FROM fill_daily_visitors
            """
        )
    else:
        con.execute(
            "CREATE OR REPLACE VIEW daily_visitors AS SELECT * FROM fill_daily_visitors"
        )
    if "user_first_purchase" in src_tables:
        con.execute(
            """
            CREATE OR REPLACE VIEW user_first_purchase AS
            SELECT * FROM src.user_first_purchase
            UNION ALL BY NAME
            SELECT * FROM fill_user_first_purchase
            """
        )
    else:
        con.execute(
            """
            CREATE OR REPLACE VIEW user_first_purchase AS
            SELECT * FROM fill_user_first_purchase
            """
        )
    if "user_rfm" in src_tables:
        con.execute(
            """
            CREATE OR REPLACE VIEW user_rfm AS
            SELECT * FROM src.user_rfm
            UNION ALL BY NAME
            SELECT * FROM fill_user_rfm
            """
        )
    if "user_rfm_precompute" in src_tables:
        con.execute(
            """
            CREATE OR REPLACE VIEW user_rfm_precompute AS
            SELECT * FROM src.user_rfm_precompute
            UNION ALL BY NAME
            SELECT * FROM fill_user_rfm_precompute
            """
        )
    con.execute(
        """
        CREATE OR REPLACE VIEW v_category_daily AS
        SELECT CAST(pay_time AS DATE) AS order_date,
               COALESCE(trim(spu_product_subclass), '未知') AS category,
               count(DISTINCT user_id) AS user_count,
               count(DISTINCT order_id) AS order_count,
               sum(actual_amount) AS gsv,
               sum(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv,
               count(DISTINCT CASE WHEN is_member THEN user_id ELSE NULL END) AS member_count
        FROM orders
        WHERE is_goujinjin = FALSE
          AND order_status != '交易关闭'
          AND is_refund = FALSE
        GROUP BY 1, 2
        """
    )
    con.close()
    print("OK: wrapper ready. Start API with:")
    print(f"  DUCKDB_PATH={wrapper}")
    print(f"  FQ_ARCHIVE_DUCKDB={archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
