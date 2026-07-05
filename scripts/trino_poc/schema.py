"""Shared schema definitions for the Sprint N+2 Trino POC."""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa


@dataclass(frozen=True)
class OrderColumn:
    name: str
    trino_type: str
    arrow_type: pa.DataType


ORDER_COLUMNS: tuple[OrderColumn, ...] = (
    OrderColumn("order_id", "VARCHAR", pa.string()),
    OrderColumn("sub_order_id", "VARCHAR", pa.string()),
    OrderColumn("user_id", "VARCHAR", pa.string()),
    OrderColumn("user_nickname", "VARCHAR", pa.string()),
    OrderColumn("order_time", "TIMESTAMP(6)", pa.timestamp("us")),
    OrderColumn("pay_time", "TIMESTAMP(6)", pa.timestamp("us")),
    OrderColumn("ship_time", "TIMESTAMP(6)", pa.timestamp("us")),
    OrderColumn("order_type", "VARCHAR", pa.string()),
    OrderColumn("order_status", "VARCHAR", pa.string()),
    OrderColumn("product_id", "VARCHAR", pa.string()),
    OrderColumn("merchant_code", "VARCHAR", pa.string()),
    OrderColumn("product_title", "VARCHAR", pa.string()),
    OrderColumn("sku_id", "VARCHAR", pa.string()),
    OrderColumn("sku_code", "VARCHAR", pa.string()),
    OrderColumn("sku_name", "VARCHAR", pa.string()),
    OrderColumn("quantity", "INTEGER", pa.int32()),
    OrderColumn("amount", "DECIMAL(12,2)", pa.decimal128(12, 2)),
    OrderColumn("refund_status", "VARCHAR", pa.string()),
    OrderColumn("refund_amount", "DECIMAL(12,2)", pa.decimal128(12, 2)),
    OrderColumn("actual_amount", "DECIMAL(12,2)", pa.decimal128(12, 2)),
    OrderColumn("province", "VARCHAR", pa.string()),
    OrderColumn("city", "VARCHAR", pa.string()),
    OrderColumn("influencer_name", "VARCHAR", pa.string()),
    OrderColumn("influencer_id", "VARCHAR", pa.string()),
    OrderColumn("live_room_id", "VARCHAR", pa.string()),
    OrderColumn("video_id", "VARCHAR", pa.string()),
    OrderColumn("traffic_source", "VARCHAR", pa.string()),
    OrderColumn("traffic_type", "VARCHAR", pa.string()),
    OrderColumn("seller_note", "VARCHAR", pa.string()),
    OrderColumn("year", "INTEGER", pa.int32()),
    OrderColumn("month", "INTEGER", pa.int32()),
    OrderColumn("is_member", "BOOLEAN", pa.bool_()),
    OrderColumn("spu_category", "VARCHAR", pa.string()),
    OrderColumn("spu_type", "VARCHAR", pa.string()),
    OrderColumn("spu_tier", "VARCHAR", pa.string()),
    OrderColumn("spu_product_class", "VARCHAR", pa.string()),
    OrderColumn("spu_product_subclass", "VARCHAR", pa.string()),
    OrderColumn("spu_cosmetic", "VARCHAR", pa.string()),
    OrderColumn("spu_spec", "VARCHAR", pa.string()),
    OrderColumn("spu_hash", "VARCHAR", pa.string()),
    OrderColumn("channel", "VARCHAR", pa.string()),
    OrderColumn("is_goujinjin", "BOOLEAN", pa.bool_()),
    OrderColumn("is_refund", "BOOLEAN", pa.bool_()),
)


R_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("近1个月已购客", 0, 30),
    ("近2-3个月已购客", 31, 90),
    ("近4-6月已购客", 91, 180),
    ("近7-12个月已购客", 181, 365),
    ("近13个月-近24个月已购客", 366, 730),
    ("2年外已购客", 731, 99999),
)


def parquet_schema() -> pa.Schema:
    return pa.schema([(column.name, column.arrow_type) for column in ORDER_COLUMNS])


def trino_columns_sql(indent: str = "    ") -> str:
    return ",\n".join(
        f"{indent}{column.name} {column.trino_type}" for column in ORDER_COLUMNS
    )


def orders_column_names() -> list[str]:
    return [column.name for column in ORDER_COLUMNS]

