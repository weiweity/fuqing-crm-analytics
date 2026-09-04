#!/usr/bin/env python3
"""Build the deterministic, synthetic-only commerce dataset used by the public demo.

The generator never reads the private CRM database or derives identifiers from real
``user_id`` values.  A customer gets one stable ``SYN-U-*`` identifier that is reused
across relationship events and every sales channel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import duckdb


DATASET_VERSION = "syn-commerce-1.0.0"
GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20260904
DEFAULT_ANALYSIS_DATE = date(2026, 8, 31)
DEFAULT_USERS = 8_000
DEFAULT_ORDERS = 28_000
MAX_ORDERS_PER_USER = 12

RELATIONSHIP_CHANNELS = ("货架", "直播", "淘客", "小样")
PAID_CHANNELS = ("货架", "直播", "淘客")


@dataclass(frozen=True)
class ProductSeed:
    code: str
    generic_name: str
    category_code: str
    list_price: Decimal
    synthetic_unit_cost: Decimal
    replenishment_cycle_days: int


PRODUCTS = (
    ProductSeed("SYN-P-001", "清洁体验装", "CARE", Decimal("39.00"), Decimal("9.00"), 21),
    ProductSeed("SYN-P-002", "舒缓体验装", "CARE", Decimal("49.00"), Decimal("12.00"), 28),
    ProductSeed("SYN-P-003", "修护精华", "SERUM", Decimal("169.00"), Decimal("46.00"), 35),
    ProductSeed("SYN-P-004", "舒缓面膜", "MASK", Decimal("129.00"), Decimal("31.00"), 30),
    ProductSeed("SYN-P-005", "长效保湿乳", "MOISTURE", Decimal("199.00"), Decimal("58.00"), 55),
    ProductSeed("SYN-P-006", "夜间修护套装", "BUNDLE", Decimal("299.00"), Decimal("96.00"), 60),
    ProductSeed("SYN-P-007", "便携护理包", "CARE", Decimal("79.00"), Decimal("18.00"), 25),
    ProductSeed("SYN-P-008", "屏障修护霜", "MOISTURE", Decimal("239.00"), Decimal("71.00"), 50),
)
PRODUCT_BY_CODE = {product.code: product for product in PRODUCTS}

TABLE_ORDER = {
    "synthetic_users": "synthetic_user_id",
    "synthetic_relationship_events": "synthetic_event_id",
    "synthetic_orders": "synthetic_order_id",
    "synthetic_products": "product_code",
    "synthetic_channel_costs": "period, channel",
}
SEMANTIC_VIEWS = (
    "sem_customer_origin",
    "sem_customer_lifecycle_snapshot",
    "sem_channel_customer_quality",
)
INSERT_ORDER = (
    "synthetic_users",
    "synthetic_products",
    "synthetic_relationship_events",
    "synthetic_orders",
    "synthetic_channel_costs",
)

FORBIDDEN_COLUMN_NAMES = {
    "user_id",
    "real_user_id",
    "user_nickname",
    "nickname",
    "name",
    "phone",
    "mobile",
    "email",
    "address",
    "receiver_name",
    "identity_card",
    "platform_open_id",
}
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _dataset_namespace(seed: int) -> str:
    payload = f"{DATASET_VERSION}:{seed}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:6].upper()


def _weighted_choice(
    rng: random.Random,
    values: tuple[str, ...] | list[str],
    weights: tuple[float, ...] | list[float],
) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def _month_start(base: date, delta: int) -> date:
    month_index = base.year * 12 + base.month - 1 + delta
    return date(month_index // 12, month_index % 12 + 1, 1)


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def compute_dataset_content_sha256(conn: duckdb.DuckDBPyConnection) -> str:
    """Hash canonical table content so runtime can reject a tampered demo DB."""
    digest = hashlib.sha256()
    for table, order_by in TABLE_ORDER.items():
        cursor = conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')
        columns = [item[0] for item in cursor.description]
        digest.update(table.encode("utf-8"))
        digest.update(json.dumps(columns, separators=(",", ":")).encode("utf-8"))
        for row in cursor.fetchall():
            payload = [_canonical(value) for value in row]
            digest.update(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
    return f"sha256:{digest.hexdigest()}"


def _create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE synthetic_users (
            synthetic_user_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            synthetic BOOLEAN NOT NULL CHECK (synthetic)
        );

        CREATE TABLE synthetic_relationship_events (
            synthetic_event_id VARCHAR PRIMARY KEY,
            synthetic_user_id VARCHAR NOT NULL REFERENCES synthetic_users(synthetic_user_id),
            event_time TIMESTAMP NOT NULL,
            event_type VARCHAR NOT NULL,
            event_priority INTEGER NOT NULL,
            channel VARCHAR NOT NULL,
            product_code VARCHAR,
            synthetic_campaign_id VARCHAR,
            synthetic BOOLEAN NOT NULL CHECK (synthetic)
        );

        CREATE TABLE synthetic_products (
            product_code VARCHAR PRIMARY KEY,
            generic_product_name VARCHAR NOT NULL,
            category_code VARCHAR NOT NULL,
            list_price DECIMAL(12, 2) NOT NULL,
            synthetic_unit_cost DECIMAL(12, 2) NOT NULL,
            replenishment_cycle_days INTEGER NOT NULL,
            synthetic BOOLEAN NOT NULL CHECK (synthetic)
        );

        CREATE TABLE synthetic_orders (
            synthetic_order_id VARCHAR PRIMARY KEY,
            synthetic_user_id VARCHAR NOT NULL REFERENCES synthetic_users(synthetic_user_id),
            pay_time TIMESTAMP NOT NULL,
            channel VARCHAR NOT NULL,
            product_code VARCHAR NOT NULL REFERENCES synthetic_products(product_code),
            quantity INTEGER NOT NULL,
            gross_amount DECIMAL(12, 2) NOT NULL,
            discount_amount DECIMAL(12, 2) NOT NULL,
            refund_amount DECIMAL(12, 2) NOT NULL,
            synthetic_cost DECIMAL(12, 2) NOT NULL,
            order_status VARCHAR NOT NULL,
            synthetic BOOLEAN NOT NULL CHECK (synthetic)
        );

        CREATE TABLE synthetic_channel_costs (
            period DATE NOT NULL,
            channel VARCHAR NOT NULL,
            synthetic_campaign_id VARCHAR NOT NULL,
            synthetic_spend DECIMAL(12, 2) NOT NULL,
            synthetic_contact_cost DECIMAL(12, 4) NOT NULL,
            synthetic BOOLEAN NOT NULL CHECK (synthetic),
            PRIMARY KEY (period, channel)
        );

        CREATE INDEX idx_syn_orders_user_time
            ON synthetic_orders (synthetic_user_id, pay_time);
        CREATE INDEX idx_syn_orders_channel_time
            ON synthetic_orders (channel, pay_time);
        """
    )


def _build_rows(
    *,
    seed: int,
    analysis_as_of_date: date,
    n_users: int,
    n_orders: int,
) -> dict[str, list[tuple[Any, ...]]]:
    if n_users <= 0:
        raise ValueError("n_users must be positive")
    if n_orders < n_users:
        raise ValueError("n_orders must be at least n_users so every customer can pay once")
    if n_orders > n_users * MAX_ORDERS_PER_USER:
        raise ValueError(f"n_orders exceeds the per-user cap of {MAX_ORDERS_PER_USER}")

    rng = random.Random(seed)
    id_namespace = _dataset_namespace(seed)
    traits: list[dict[str, Any]] = []
    for index in range(1, n_users + 1):
        synthetic_user_id = f"SYN-U-{id_namespace}-{index:06d}"
        relationship_channel = _weighted_choice(
            rng,
            RELATIONSHIP_CHANNELS,
            (0.27, 0.39, 0.20, 0.14),
        )
        paid_channel = relationship_channel
        if relationship_channel == "小样":
            paid_channel = _weighted_choice(rng, PAID_CHANNELS, (0.50, 0.35, 0.15))

        relationship_days_ago = rng.randint(12, 720)
        relationship_date = analysis_as_of_date - timedelta(days=relationship_days_ago)
        paid_lag_days = rng.randint(4, 35) if relationship_channel == "小样" else rng.randint(0, 9)
        first_paid_date = min(
            relationship_date + timedelta(days=paid_lag_days),
            analysis_as_of_date,
        )
        traits.append(
            {
                "synthetic_user_id": synthetic_user_id,
                "relationship_channel": relationship_channel,
                "paid_channel": paid_channel,
                "relationship_date": relationship_date,
                "first_paid_date": first_paid_date,
            }
        )

    repeat_weights = {
        "货架": 1.55,
        "直播": 0.92,
        "淘客": 0.68,
    }
    order_counts = [1] * n_users
    candidate_indices = list(range(n_users))
    weights = [repeat_weights[trait["paid_channel"]] for trait in traits]
    for _ in range(n_orders - n_users):
        while True:
            candidate = rng.choices(candidate_indices, weights=weights, k=1)[0]
            if order_counts[candidate] < MAX_ORDERS_PER_USER:
                order_counts[candidate] += 1
                break

    users: list[tuple[Any, ...]] = []
    relationship_events: list[tuple[Any, ...]] = []
    orders: list[tuple[Any, ...]] = []
    global_order_index = 1

    first_product_choices = {
        "货架": ("SYN-P-001", "SYN-P-002", "SYN-P-003"),
        "直播": ("SYN-P-001", "SYN-P-006", "SYN-P-007"),
        "淘客": ("SYN-P-001", "SYN-P-002", "SYN-P-007"),
    }
    same_channel_probability = {"货架": 0.68, "直播": 0.48, "淘客": 0.36}
    discount_rate = {"货架": Decimal("0.06"), "直播": Decimal("0.18"), "淘客": Decimal("0.26")}
    refund_probability = {"货架": 0.025, "直播": 0.065, "淘客": 0.075}

    for user_index, (trait, order_count) in enumerate(zip(traits, order_counts, strict=True), start=1):
        user_id = trait["synthetic_user_id"]
        relationship_at = datetime.combine(trait["relationship_date"], time(9, user_index % 60))
        users.append((user_id, relationship_at, True))
        relationship_events.append(
            (
                f"SYN-E-{id_namespace}-{user_index:06d}",
                user_id,
                relationship_at,
                "SAMPLE_RECEIVED" if trait["relationship_channel"] == "小样" else "FIRST_TOUCH",
                10 if trait["relationship_channel"] == "小样" else 20,
                trait["relationship_channel"],
                "SYN-P-001" if trait["relationship_channel"] == "小样" else None,
                f"SYN-C-{id_namespace}-REL-{user_index % 12:02d}",
                True,
            )
        )

        available_days = max(0, (analysis_as_of_date - trait["first_paid_date"]).days)
        raw_offsets = [0]
        for sequence in range(1, order_count):
            previous = raw_offsets[-1]
            cycle = rng.randint(16, 62)
            raw_offsets.append(previous + cycle)
        max_raw = raw_offsets[-1] if raw_offsets else 0
        if max_raw > available_days and max_raw > 0:
            offsets = [round(offset * available_days / max_raw) for offset in raw_offsets]
        else:
            offsets = raw_offsets

        for sequence, day_offset in enumerate(offsets):
            if sequence == 0:
                channel = trait["paid_channel"]
                product_code = rng.choice(first_product_choices[channel])
            else:
                origin_channel = trait["paid_channel"]
                if rng.random() < same_channel_probability[origin_channel]:
                    channel = origin_channel
                else:
                    channel = rng.choice([item for item in PAID_CHANNELS if item != origin_channel])
                if sequence == 1:
                    product_code = _weighted_choice(
                        rng,
                        ["SYN-P-003", "SYN-P-004", "SYN-P-005"],
                        [0.44, 0.34, 0.22],
                    )
                else:
                    product_code = _weighted_choice(
                        rng,
                        ["SYN-P-004", "SYN-P-005", "SYN-P-006", "SYN-P-008"],
                        [0.32, 0.30, 0.14, 0.24],
                    )

            product = PRODUCT_BY_CODE[product_code]
            quantity = 2 if rng.random() < 0.08 else 1
            gross_amount = _money(product.list_price * quantity)
            discount_jitter = Decimal(str(rng.uniform(-0.025, 0.025)))
            effective_discount = max(Decimal("0"), discount_rate[channel] + discount_jitter)
            discount_amount = _money(gross_amount * effective_discount)
            net_amount = gross_amount - discount_amount
            # Every synthetic customer has one valid first paid order.  Refund
            # noise is introduced only after that anchor event.
            refunded = sequence > 0 and rng.random() < refund_probability[channel]
            refund_amount = net_amount if refunded else Decimal("0.00")
            pay_time = datetime.combine(
                trait["first_paid_date"] + timedelta(days=day_offset),
                time(10 + sequence % 10, (user_index + sequence) % 60),
            )
            orders.append(
                (
                    f"SYN-O-{id_namespace}-{global_order_index:08d}",
                    user_id,
                    pay_time,
                    channel,
                    product_code,
                    quantity,
                    gross_amount,
                    discount_amount,
                    refund_amount,
                    _money(product.synthetic_unit_cost * quantity),
                    "REFUNDED" if refunded else "PAID",
                    True,
                )
            )
            global_order_index += 1

    products = [
        (
            product.code,
            product.generic_name,
            product.category_code,
            product.list_price,
            product.synthetic_unit_cost,
            product.replenishment_cycle_days,
            True,
        )
        for product in PRODUCTS
    ]

    channel_costs: list[tuple[Any, ...]] = []
    spend_base = {"货架": Decimal("68000"), "直播": Decimal("92000"), "淘客": Decimal("54000"), "小样": Decimal("36000")}
    contact_cost = {"货架": Decimal("0.18"), "直播": Decimal("0.32"), "淘客": Decimal("0.24"), "小样": Decimal("2.80")}
    for month_delta in range(-23, 1):
        period = _month_start(analysis_as_of_date, month_delta)
        seasonal_factor = Decimal(str(0.90 + ((period.month * 7) % 5) * 0.05))
        for channel_index, channel in enumerate(RELATIONSHIP_CHANNELS, start=1):
            channel_costs.append(
                (
                    period,
                    channel,
                    f"SYN-C-{id_namespace}-{period:%Y%m}-{channel_index:02d}",
                    _money(spend_base[channel] * seasonal_factor),
                    contact_cost[channel],
                    True,
                )
            )

    return {
        "synthetic_users": users,
        "synthetic_relationship_events": relationship_events,
        "synthetic_orders": orders,
        "synthetic_products": products,
        "synthetic_channel_costs": channel_costs,
    }


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    rows_by_table: dict[str, list[tuple[Any, ...]]],
) -> None:
    # Parent dimensions must exist before DuckDB validates child foreign keys.
    for table in INSERT_ORDER:
        rows = rows_by_table[table]
        if not rows:
            continue
        placeholders = ",".join("?" for _ in rows[0])
        conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)


def _create_semantic_views(
    conn: duckdb.DuckDBPyConnection,
    *,
    analysis_as_of_date: date,
) -> None:
    as_of = analysis_as_of_date.isoformat()
    conn.execute(
        f"""
        CREATE VIEW sem_customer_origin AS
        WITH relationship_ranked AS (
            SELECT
                synthetic_user_id,
                synthetic_event_id,
                event_time,
                channel,
                product_code,
                row_number() OVER (
                    PARTITION BY synthetic_user_id
                    ORDER BY event_time, event_priority, synthetic_event_id
                ) AS sequence
            FROM synthetic_relationship_events
        ),
        paid_ranked AS (
            SELECT
                synthetic_user_id,
                synthetic_order_id,
                pay_time,
                channel,
                product_code,
                gross_amount - discount_amount - refund_amount AS paid_amount,
                row_number() OVER (
                    PARTITION BY synthetic_user_id
                    ORDER BY pay_time, synthetic_order_id
                ) AS sequence
            FROM synthetic_orders
            WHERE order_status = 'PAID'
        )
        SELECT
            users.synthetic_user_id,
            relationship.synthetic_event_id AS first_relationship_event_id,
            relationship.event_time AS first_relationship_at,
            relationship.channel AS first_relationship_channel,
            relationship.product_code AS first_relationship_product_code,
            paid.synthetic_order_id AS first_paid_order_id,
            paid.pay_time AS first_paid_at,
            paid.channel AS first_paid_channel,
            paid.product_code AS first_paid_product_code,
            paid.paid_amount AS first_paid_amount,
            CAST(paid.pay_time AS DATE) AS paid_cohort_date,
            'customer-origin-v1' AS metric_version
        FROM synthetic_users users
        LEFT JOIN relationship_ranked relationship
            ON users.synthetic_user_id = relationship.synthetic_user_id
           AND relationship.sequence = 1
        LEFT JOIN paid_ranked paid
            ON users.synthetic_user_id = paid.synthetic_user_id
           AND paid.sequence = 1;

        CREATE VIEW sem_customer_lifecycle_snapshot AS
        WITH paid_orders AS (
            SELECT
                orders.synthetic_user_id,
                orders.synthetic_order_id,
                orders.pay_time,
                orders.channel,
                orders.product_code,
                origin.first_paid_at,
                orders.gross_amount - orders.discount_amount - orders.refund_amount AS net_value
            FROM synthetic_orders orders
            JOIN sem_customer_origin origin USING (synthetic_user_id)
            WHERE orders.order_status = 'PAID'
        ),
        rolled AS (
            SELECT
                synthetic_user_id,
                min(first_paid_at) AS first_paid_at,
                min(pay_time) FILTER (WHERE pay_time > first_paid_at) AS second_paid_at,
                max(pay_time) AS last_paid_at,
                count(*) AS paid_order_count,
                count(DISTINCT product_code) AS paid_product_count,
                count(DISTINCT channel) AS paid_channel_count,
                sum(net_value) FILTER (
                    WHERE date_diff('day', first_paid_at, pay_time) BETWEEN 0 AND 30
                ) AS net_value_30d,
                sum(net_value) FILTER (
                    WHERE date_diff('day', first_paid_at, pay_time) BETWEEN 0 AND 90
                ) AS net_value_90d,
                sum(net_value) FILTER (
                    WHERE date_diff('day', first_paid_at, pay_time) BETWEEN 0 AND 180
                ) AS net_value_180d,
                sum(net_value) AS net_value_to_date
            FROM paid_orders
            GROUP BY synthetic_user_id
        )
        SELECT
            rolled.synthetic_user_id,
            DATE '{as_of}' AS analysis_as_of_date,
            rolled.first_paid_at,
            rolled.second_paid_at,
            rolled.last_paid_at,
            date_diff('day', rolled.first_paid_at, rolled.second_paid_at) AS days_to_second_paid,
            date_diff('day', rolled.last_paid_at, DATE '{as_of}') AS recency_days,
            rolled.paid_order_count,
            rolled.paid_product_count,
            rolled.paid_channel_count,
            rolled.paid_channel_count > 1 AS has_cross_channel_purchase,
            coalesce(rolled.net_value_30d, 0) AS net_value_30d,
            coalesce(rolled.net_value_90d, 0) AS net_value_90d,
            coalesce(rolled.net_value_180d, 0) AS net_value_180d,
            coalesce(rolled.net_value_to_date, 0) AS net_value_to_date,
            CASE
                WHEN date_diff('day', rolled.first_paid_at, DATE '{as_of}') <= 30 THEN 'NEW'
                WHEN date_diff('day', rolled.last_paid_at, DATE '{as_of}') <= 45 THEN 'ACTIVE'
                WHEN date_diff('day', rolled.last_paid_at, DATE '{as_of}') <= 90 THEN 'REPLENISHMENT_DUE'
                WHEN date_diff('day', rolled.last_paid_at, DATE '{as_of}') <= 180 THEN 'DORMANT'
                ELSE 'CHURNED'
            END AS lifecycle_stage,
            CASE
                WHEN rolled.first_paid_at <= DATE '{as_of}' - INTERVAL 30 DAY
                THEN 'MATURE' ELSE 'NOT_MATURE'
            END AS maturity_30d,
            CASE
                WHEN rolled.first_paid_at <= DATE '{as_of}' - INTERVAL 90 DAY
                THEN 'MATURE' ELSE 'NOT_MATURE'
            END AS maturity_90d,
            CASE
                WHEN rolled.first_paid_at <= DATE '{as_of}' - INTERVAL 180 DAY
                THEN 'MATURE' ELSE 'NOT_MATURE'
            END AS maturity_180d,
            'customer-lifecycle-v1' AS metric_version
        FROM rolled;

        CREATE VIEW sem_channel_customer_quality AS
        SELECT
            origin.first_paid_channel,
            count(*) AS cohort_customers,
            count(*) FILTER (WHERE lifecycle.maturity_30d = 'MATURE') AS mature_30d_customers,
            count(*) FILTER (WHERE lifecycle.maturity_180d = 'MATURE') AS mature_180d_customers,
            round(
                avg(
                    CASE
                        WHEN lifecycle.second_paid_at <= lifecycle.first_paid_at + INTERVAL 30 DAY
                        THEN 1.0 ELSE 0.0
                    END
                ) FILTER (WHERE lifecycle.maturity_30d = 'MATURE'),
                4
            ) AS second_paid_rate_30d,
            round(median(lifecycle.days_to_second_paid), 1) AS median_days_to_second_paid,
            round(
                avg(CASE WHEN lifecycle.has_cross_channel_purchase THEN 1.0 ELSE 0.0 END),
                4
            ) AS cross_channel_rate,
            round(
                avg(lifecycle.net_value_180d)
                    FILTER (WHERE lifecycle.maturity_180d = 'MATURE'),
                2
            ) AS avg_net_value_180d,
            'channel-customer-quality-v1' AS metric_version
        FROM sem_customer_origin origin
        JOIN sem_customer_lifecycle_snapshot lifecycle USING (synthetic_user_id)
        GROUP BY origin.first_paid_channel;
        """
    )


def _iter_text_values(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: Iterable[str],
) -> Iterable[str]:
    for column in columns:
        cursor = conn.execute(
            f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'
        )
        for (value,) in cursor.fetchall():
            yield str(value)


def validate_synthetic_database(db_path: Path) -> dict[str, Any]:
    """Fail closed when the public dataset contains unstable IDs or PII-like data."""
    db_path = Path(db_path)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        missing = set(TABLE_ORDER) - tables
        if missing:
            raise ValueError(f"synthetic dataset missing tables: {sorted(missing)}")

        views = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema='main'"
            ).fetchall()
        }
        missing_views = set(SEMANTIC_VIEWS) - views
        if missing_views:
            raise ValueError(f"synthetic dataset missing semantic views: {sorted(missing_views)}")

        row_counts: dict[str, int] = {}
        for table in TABLE_ORDER:
            columns = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
            column_names = [str(row[1]) for row in columns]
            forbidden = sorted(FORBIDDEN_COLUMN_NAMES.intersection(name.lower() for name in column_names))
            if forbidden:
                raise ValueError(f"forbidden PII columns in {table}: {forbidden}")

            non_synthetic = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE synthetic IS DISTINCT FROM TRUE'
            ).fetchone()[0]
            if non_synthetic:
                raise ValueError(f"{table} contains {non_synthetic} rows without synthetic=true")

            text_columns = [
                str(row[1])
                for row in columns
                if "VARCHAR" in str(row[2]).upper() or "TEXT" in str(row[2]).upper()
            ]
            for value in _iter_text_values(conn, table, text_columns):
                if PHONE_PATTERN.search(value) or EMAIL_PATTERN.search(value):
                    raise ValueError(f"PII-like text detected in {table}")

            row_counts[table] = int(
                conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )

        invalid_users = conn.execute(
            """
            SELECT COUNT(*) FROM synthetic_users
            WHERE NOT regexp_matches(synthetic_user_id, '^SYN-U-[A-F0-9]{6}-[0-9]{6}$')
            """
        ).fetchone()[0]
        invalid_orders = conn.execute(
            """
            SELECT COUNT(*) FROM synthetic_orders
            WHERE NOT regexp_matches(synthetic_order_id, '^SYN-O-[A-F0-9]{6}-[0-9]{8}$')
            """
        ).fetchone()[0]
        orphan_orders = conn.execute(
            """
            SELECT COUNT(*)
            FROM synthetic_orders orders
            LEFT JOIN synthetic_users users USING (synthetic_user_id)
            WHERE users.synthetic_user_id IS NULL
            """
        ).fetchone()[0]
        orphan_events = conn.execute(
            """
            SELECT COUNT(*)
            FROM synthetic_relationship_events events
            LEFT JOIN synthetic_users users USING (synthetic_user_id)
            WHERE users.synthetic_user_id IS NULL
            """
        ).fetchone()[0]
        if invalid_users or invalid_orders or orphan_orders or orphan_events:
            raise ValueError(
                "synthetic identity validation failed: "
                f"users={invalid_users}, orders={invalid_orders}, "
                f"orphan_orders={orphan_orders}, orphan_events={orphan_events}"
            )

        multi_channel_users = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT synthetic_user_id
                    FROM synthetic_orders
                    GROUP BY synthetic_user_id
                    HAVING COUNT(DISTINCT channel) > 1
                )
                """
            ).fetchone()[0]
        )
        if row_counts["synthetic_orders"] > row_counts["synthetic_users"] and multi_channel_users == 0:
            raise ValueError("synthetic dataset has no cross-channel customers")

        return {
            "status": "passed",
            "contains_real_data": False,
            "row_counts": row_counts,
            "multi_channel_users": multi_channel_users,
        }
    finally:
        conn.close()


def generate_dataset(
    output_db: Path,
    *,
    seed: int = DEFAULT_SEED,
    analysis_as_of_date: date = DEFAULT_ANALYSIS_DATE,
    n_users: int = DEFAULT_USERS,
    n_orders: int = DEFAULT_ORDERS,
    force: bool = False,
) -> dict[str, Any]:
    """Generate a validated DuckDB and adjacent manifest without reading private data."""
    output_db = Path(output_db)
    manifest_path = output_db.with_suffix(".manifest.json")
    if not force and (output_db.exists() or manifest_path.exists()):
        raise FileExistsError(f"refusing to overwrite existing synthetic dataset: {output_db}")

    output_db.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".synthetic-build-", dir=output_db.parent))
    temp_db = temp_dir / output_db.name
    temp_manifest = temp_dir / manifest_path.name
    try:
        conn = duckdb.connect(str(temp_db))
        try:
            _create_schema(conn)
            rows_by_table = _build_rows(
                seed=seed,
                analysis_as_of_date=analysis_as_of_date,
                n_users=n_users,
                n_orders=n_orders,
            )
            _insert_rows(conn, rows_by_table)
            _create_semantic_views(conn, analysis_as_of_date=analysis_as_of_date)
            content_sha256 = compute_dataset_content_sha256(conn)
        finally:
            conn.close()

        validation = validate_synthetic_database(temp_db)
        manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "data_profile": "synthetic",
            "dataset_version": DATASET_VERSION,
            "generator_version": GENERATOR_VERSION,
            "seed": seed,
            "id_namespace": _dataset_namespace(seed),
            "analysis_as_of_date": analysis_as_of_date.isoformat(),
            "contains_real_data": False,
            "source": "generated_from_code_only",
            "database_filename": output_db.name,
            "dataset_content_sha256": content_sha256,
            "channels": list(RELATIONSHIP_CHANNELS),
            "semantic_views": list(SEMANTIC_VIEWS),
            "lifecycle_policy": {
                "new_customer_days": 30,
                "active_recency_days": 45,
                "replenishment_due_days": 90,
                "dormant_days": 180,
                "metric_version": "customer-lifecycle-v1",
            },
            "validation": validation,
        }
        manifest_payload = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        manifest["manifest_sha256"] = f"sha256:{hashlib.sha256(manifest_payload).hexdigest()}"
        temp_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        os.replace(temp_db, output_db)
        os.replace(temp_manifest, manifest_path)
        return manifest
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-db",
        type=Path,
        default=Path("data/synthetic") / f"{DATASET_VERSION}.duckdb",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--analysis-as-of-date", type=date.fromisoformat, default=DEFAULT_ANALYSIS_DATE)
    parser.add_argument("--users", type=int, default=DEFAULT_USERS)
    parser.add_argument("--orders", type=int, default=DEFAULT_ORDERS)
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = generate_dataset(
            args.output_db,
            seed=args.seed,
            analysis_as_of_date=args.analysis_as_of_date,
            n_users=args.users,
            n_orders=args.orders,
            force=args.force,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
