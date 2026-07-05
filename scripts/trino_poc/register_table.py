"""Register the Sprint N+2 Parquet dataset as hive.crm.orders in Trino."""

from __future__ import annotations

import argparse

from scripts.trino_poc.schema import trino_columns_sql
from scripts.trino_poc.trino_client import TrinoRestClient


DEFAULT_LOCATION = "s3://fuqing-crm-poc/orders"


def build_register_sql(data_location: str = DEFAULT_LOCATION, replace: bool = True) -> list[str]:
    statements = [
        "CREATE SCHEMA IF NOT EXISTS hive.crm WITH (location = 's3://fuqing-crm-poc/warehouse/crm')",
    ]
    if replace:
        statements.append("DROP TABLE IF EXISTS hive.crm.orders")
    statements.append(
        "CREATE TABLE IF NOT EXISTS hive.crm.orders (\n"
        f"{trino_columns_sql()}\n"
        ") WITH (\n"
        "    format = 'PARQUET',\n"
        f"    external_location = '{data_location.rstrip('/')}'\n"
        ")"
    )
    return statements


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trino-url", default="http://127.0.0.1:18080")
    parser.add_argument("--data-location", default=DEFAULT_LOCATION)
    parser.add_argument("--no-replace", action="store_true")
    parser.add_argument("--wait", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = TrinoRestClient(base_url=args.trino_url)
    if args.wait:
        client.wait_until_ready()
    for statement in build_register_sql(
        data_location=args.data_location,
        replace=not args.no_replace,
    ):
        client.execute(statement)
    result = client.execute("SELECT COUNT(*) AS rows FROM hive.crm.orders")
    print({"rows": result.rows[0][0] if result.rows else 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

