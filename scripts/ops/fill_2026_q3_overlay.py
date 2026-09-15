#!/usr/bin/env python3
"""Build a writable overlay + wrapper around the archive DuckDB.

Does NOT copy or mutate the archive. Requires:

  FQ_ARCHIVE_DUCKDB   read-only archive path (ATTACH only)
  FQ_DUCKDB_WRAPPER   new wrapper path (created/replaced)

Copies 2023-07-06..2023-09-15 orders/visitors into fill_* tables with
+3 years so 2026-07-06..2026-09-15 has synthetic rows. Point DUCKDB_PATH
at the wrapper and FQ_ARCHIVE_DUCKDB at the archive.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb


def quote_duckdb_literal(value: str) -> str:
    return value.replace("'", "''")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


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
    print("copying 2023-07-06..2023-09-15 orders → 2026 (+3 years) ...")
    con.execute(
        """
        CREATE TABLE fill_orders AS
        SELECT * REPLACE (
            ('SYN26-' || CAST(order_id AS VARCHAR)) AS order_id,
            order_time + INTERVAL 3 YEAR AS order_time,
            pay_time + INTERVAL 3 YEAR AS pay_time,
            ship_time + INTERVAL 3 YEAR AS ship_time
        )
        FROM src.orders
        WHERE pay_time >= TIMESTAMP '2023-07-06'
          AND pay_time < TIMESTAMP '2023-09-16'
        """
    )
    n_orders = con.execute("SELECT count(*) FROM fill_orders").fetchone()[0]
    print(f"fill_orders={n_orders}")
    con.execute(
        """
        CREATE TABLE fill_daily_visitors AS
        SELECT
            date + INTERVAL 3 YEAR AS date,
            visitors,
            new_members,
            member_join_rate
        FROM src.daily_visitors
        WHERE date >= DATE '2023-07-06' AND date < DATE '2023-09-16'
        """
    )
    n_vis = con.execute("SELECT count(*) FROM fill_daily_visitors").fetchone()[0]
    print(f"fill_daily_visitors={n_vis}")
    tables = [
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src' AND internal = false"
        ).fetchall()
    ]
    for table in tables:
        if table in {"orders", "daily_visitors"}:
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
    con.execute(
        """
        CREATE OR REPLACE VIEW daily_visitors AS
        SELECT * FROM src.daily_visitors
        UNION ALL BY NAME
        SELECT * FROM fill_daily_visitors
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
