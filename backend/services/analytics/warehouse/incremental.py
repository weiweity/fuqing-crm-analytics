"""True incremental warehouse updates: hash/PK affected set, then rewrite those facts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.services.analytics.warehouse.contract import (
    WarehouseContractError,
    normalize_rules,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.facts import fact_row_counts


def _naive_utc(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_naive_instant(value)


@dataclass(frozen=True)
class PreviousMeta:
    as_of: datetime
    content_hash: str
    rule_version: str
    rules: dict


@dataclass(frozen=True)
class AffectedStats:
    affected_order_keys: int
    new_or_changed_records: int
    unchanged_records: int
    rules_changed: bool
    as_of_unchanged: bool
    content_hash_compared: bool = True
    used_global_max_pay_time: bool = False
    used_mtime_as_incremental_cursor: bool = False
    full_table_rebuild: bool = False

    def to_extra(self) -> dict:
        return {
            "affected_order_keys": self.affected_order_keys,
            "new_or_changed_records": self.new_or_changed_records,
            "unchanged_records": self.unchanged_records,
            "rules_changed": self.rules_changed,
            "as_of_unchanged": self.as_of_unchanged,
            "content_hash_compared": self.content_hash_compared,
            "used_global_max_pay_time": self.used_global_max_pay_time,
            "used_mtime_as_incremental_cursor": self.used_mtime_as_incremental_cursor,
            "full_table_rebuild": self.full_table_rebuild,
        }


def read_previous_meta(connection) -> PreviousMeta | None:
    row = connection.execute(
        """
        SELECT as_of, content_hash, rule_version, rules_json
        FROM warehouse_meta
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return PreviousMeta(
        as_of=_naive_utc(row[0]),
        content_hash=row[1],
        rule_version=row[2],
        rules=normalize_rules(json.loads(row[3]) if row[3] else None),
    )


def install_rules(connection, rules: dict) -> None:
    normalized = normalize_rules(rules)
    connection.execute("DROP TABLE IF EXISTS rule_valid_status")
    connection.execute("DROP TABLE IF EXISTS rule_channel_map")
    connection.execute("DROP TABLE IF EXISTS rule_refund_class")
    connection.execute("DROP TABLE IF EXISTS rule_flags")
    connection.execute(
        "CREATE TABLE rule_valid_status (status VARCHAR COLLATE C NOT NULL PRIMARY KEY)"
    )
    connection.execute(
        "CREATE TABLE rule_channel_map (source VARCHAR COLLATE C NOT NULL PRIMARY KEY, mapped VARCHAR COLLATE C NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE rule_refund_class (refund_class VARCHAR COLLATE C NOT NULL PRIMARY KEY)"
    )
    connection.execute("CREATE TABLE rule_flags (refund_class_filter BOOLEAN NOT NULL)")
    connection.executemany(
        "INSERT INTO rule_valid_status VALUES (?)",
        [(status,) for status in normalized["valid_statuses"]],
    )
    if normalized["channel_map"]:
        connection.executemany(
            "INSERT INTO rule_channel_map VALUES (?, ?)",
            list(normalized["channel_map"].items()),
        )
    classes = normalized["counted_refund_classes"]
    connection.execute("INSERT INTO rule_flags VALUES (?)", [classes is not None])
    if classes:
        connection.executemany(
            "INSERT INTO rule_refund_class VALUES (?)",
            [(item,) for item in classes],
        )


def _insert_affected(connection, sql: str, params=None) -> None:
    connection.execute(
        f"""
        INSERT INTO stg_affected_order
        {sql}
        ON CONFLICT (synthetic_user_id, order_id) DO NOTHING
        """,
        params or [],
    )


def _record_change_counts(connection) -> tuple[int, int]:
    row = connection.execute(
        """
        SELECT
            (
                SELECT COUNT(*) FROM stg_order_header s
                LEFT JOIN src_order_header o
                  ON encode(o.synthetic_user_id) = encode(s.synthetic_user_id)
                 AND encode(o.order_id) = encode(s.order_id)
                WHERE o.order_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_order_line s
                LEFT JOIN src_order_line o
                  ON encode(o.line_id) = encode(s.line_id)
                WHERE o.line_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_refund s
                LEFT JOIN src_refund o
                  ON encode(o.refund_id) = encode(s.refund_id)
                WHERE o.refund_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_product_version s
                LEFT JOIN src_product_version o
                  ON encode(o.product_version_id) = encode(s.product_version_id)
                WHERE o.product_version_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
            ),
            (
                SELECT COUNT(*) FROM stg_order_header s
                JOIN src_order_header o
                  ON encode(o.synthetic_user_id) = encode(s.synthetic_user_id)
                 AND encode(o.order_id) = encode(s.order_id)
                WHERE encode(o.content_hash) = encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_order_line s
                JOIN src_order_line o
                  ON encode(o.line_id) = encode(s.line_id)
                WHERE encode(o.content_hash) = encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_refund s
                JOIN src_refund o
                  ON encode(o.refund_id) = encode(s.refund_id)
                WHERE encode(o.content_hash) = encode(s.content_hash)
            ) + (
                SELECT COUNT(*) FROM stg_product_version s
                JOIN src_product_version o
                  ON encode(o.product_version_id) = encode(s.product_version_id)
                WHERE encode(o.content_hash) = encode(s.content_hash)
            )
        """
    ).fetchone()
    return int(row[0]), int(row[1])


def classify_affected_orders(
    connection,
    *,
    previous: PreviousMeta | None,
    new_as_of,
    rules_changed: bool,
) -> AffectedStats:
    connection.execute("DELETE FROM stg_affected_order")
    new_or_changed, unchanged = _record_change_counts(connection)
    _insert_affected(
        connection,
        """
        SELECT s.synthetic_user_id, s.order_id
        FROM stg_order_header s
        LEFT JOIN src_order_header o
          ON encode(o.synthetic_user_id) = encode(s.synthetic_user_id)
         AND encode(o.order_id) = encode(s.order_id)
        WHERE o.order_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
        """,
    )
    _insert_affected(
        connection,
        """
        SELECT s.synthetic_user_id, s.order_id
        FROM stg_order_line s
        LEFT JOIN src_order_line o
          ON encode(o.line_id) = encode(s.line_id)
        WHERE o.line_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
        """,
    )
    _insert_affected(
        connection,
        """
        SELECT s.synthetic_user_id, s.order_id
        FROM stg_refund s
        LEFT JOIN src_refund o
          ON encode(o.refund_id) = encode(s.refund_id)
        WHERE o.refund_id IS NULL OR encode(o.content_hash) <> encode(s.content_hash)
        """,
    )
    # A stable line/refund ID may move to a different order. Invalidate both
    # sides before the source row is replaced.
    for table, key in (("order_line", "line_id"), ("refund", "refund_id")):
        _insert_affected(
            connection,
            f"""
            SELECT o.synthetic_user_id, o.order_id
            FROM src_{table} o JOIN stg_{table} s
              ON encode(o.{key}) = encode(s.{key})
            WHERE encode(o.content_hash) <> encode(s.content_hash)
            """,
        )
    _insert_affected(
        connection,
        """
        SELECT h.synthetic_user_id, h.order_id
        FROM src_order_header h
        JOIN src_order_line l
          ON encode(l.synthetic_user_id) = encode(h.synthetic_user_id)
         AND encode(l.order_id) = encode(h.order_id)
        JOIN stg_product_version v
          ON encode(v.product_id) = encode(l.product_id)
         AND h.paid_at >= v.valid_from
         AND h.paid_at < v.valid_to
        LEFT JOIN src_product_version old
          ON encode(old.product_version_id) = encode(v.product_version_id)
        WHERE old.product_version_id IS NULL
           OR encode(old.content_hash) <> encode(v.content_hash)
        """,
    )
    new_as_of_utc = _naive_utc(new_as_of)
    # Range shrink/move and product correction also invalidate the OLD match.
    _insert_affected(
        connection,
        """
        SELECT h.synthetic_user_id, h.order_id
        FROM src_product_version old
        JOIN stg_product_version v
          ON encode(old.product_version_id) = encode(v.product_version_id)
        JOIN src_order_line l ON encode(l.product_id) = encode(old.product_id)
        JOIN src_order_header h
          ON encode(h.synthetic_user_id) = encode(l.synthetic_user_id)
         AND encode(h.order_id) = encode(l.order_id)
         AND h.paid_at >= old.valid_from AND h.paid_at < old.valid_to
        WHERE encode(old.content_hash) <> encode(v.content_hash)
        """,
    )
    as_of_unchanged = previous is None or previous.as_of == new_as_of_utc
    if previous is not None and previous.as_of != new_as_of_utc:
        lo = previous.as_of if previous.as_of <= new_as_of_utc else new_as_of_utc
        hi = new_as_of_utc if previous.as_of <= new_as_of_utc else previous.as_of
        _insert_affected(
            connection,
            """
            SELECT synthetic_user_id, order_id
            FROM src_order_header
            WHERE paid_at > ? AND paid_at <= ?
            """,
            [lo, hi],
        )
        _insert_affected(
            connection,
            """
            SELECT synthetic_user_id, order_id
            FROM src_refund
            WHERE refunded_at > ? AND refunded_at <= ?
            """,
            [lo, hi],
        )
    if rules_changed:
        _insert_affected(
            connection,
            f"""
            SELECT computed.synthetic_user_id, computed.order_id
            FROM ({_computed_header_sql("src_order_header")}) computed
            LEFT JOIN fact_order_header f
              ON encode(f.synthetic_user_id) = encode(computed.synthetic_user_id)
             AND encode(f.order_id) = encode(computed.order_id)
            WHERE f.order_id IS NULL
               OR encode(f.channel) <> encode(computed.channel)
               OR encode(f.status) <> encode(computed.status)
               OR f.gross_paid_minor <> computed.gross_paid_minor
               OR f.refund_minor_as_of <> computed.refund_minor_as_of
               OR f.net_paid_minor <> computed.net_paid_minor
               OR f.is_valid IS DISTINCT FROM computed.is_valid
            """,
        )
    affected = int(connection.execute("SELECT COUNT(*) FROM stg_affected_order").fetchone()[0])
    return AffectedStats(
        affected_order_keys=affected,
        new_or_changed_records=new_or_changed,
        unchanged_records=unchanged,
        rules_changed=rules_changed,
        as_of_unchanged=as_of_unchanged,
    )


def merge_staging_into_source(connection) -> None:
    connection.execute(
        """
        INSERT INTO src_order_header
        SELECT synthetic_user_id, order_id, paid_at, channel, status, gross_paid_minor, content_hash
        FROM stg_order_header
        ON CONFLICT (synthetic_user_id, order_id) DO UPDATE SET
            paid_at = excluded.paid_at,
            channel = excluded.channel,
            status = excluded.status,
            gross_paid_minor = excluded.gross_paid_minor,
            content_hash = excluded.content_hash
        """
    )
    connection.execute(
        """
        INSERT INTO src_order_line
        SELECT line_id, synthetic_user_id, order_id, product_id, quantity, content_hash
        FROM stg_order_line
        ON CONFLICT (line_id) DO UPDATE SET
            synthetic_user_id = excluded.synthetic_user_id,
            order_id = excluded.order_id,
            product_id = excluded.product_id,
            quantity = excluded.quantity,
            content_hash = excluded.content_hash
        """
    )
    connection.execute(
        """
        INSERT INTO src_refund
        SELECT refund_id, synthetic_user_id, order_id, refunded_at, refund_minor, refund_class, content_hash
        FROM stg_refund
        ON CONFLICT (refund_id) DO UPDATE SET
            synthetic_user_id = excluded.synthetic_user_id,
            order_id = excluded.order_id,
            refunded_at = excluded.refunded_at,
            refund_minor = excluded.refund_minor,
            refund_class = excluded.refund_class,
            content_hash = excluded.content_hash
        """
    )
    connection.execute(
        """
        INSERT INTO src_product_version
        SELECT product_version_id, product_id, valid_from, valid_to, content_hash
        FROM stg_product_version
        ON CONFLICT (product_version_id) DO UPDATE SET
            product_id = excluded.product_id,
            valid_from = excluded.valid_from,
            valid_to = excluded.valid_to,
            content_hash = excluded.content_hash
        """
    )
    overlap = connection.execute(
        """
        SELECT COUNT(*) FROM src_product_version a
        JOIN src_product_version b
          ON encode(a.product_id) = encode(b.product_id)
         AND encode(a.product_version_id) < encode(b.product_version_id)
         AND a.valid_from < b.valid_to
         AND b.valid_from < a.valid_to
        """
    ).fetchone()[0]
    if overlap:
        raise WarehouseContractError("product versions overlap on the same product_id")


def _refund_filter_sql(alias: str = "r") -> str:
    return f"""
        (
            NOT (SELECT refund_class_filter FROM rule_flags)
            OR EXISTS (
                SELECT 1 FROM rule_refund_class rc
                WHERE encode(rc.refund_class) = encode({alias}.refund_class)
            )
        )
    """


def _computed_header_sql(header_table: str) -> str:
    return f"""
        SELECT
            h.synthetic_user_id,
            h.order_id,
            c.customer_key,
            h.paid_at,
            COALESCE(cm.mapped, h.channel) AS channel,
            h.status,
            c.permission_scope,
            c.identity_domain,
            h.gross_paid_minor,
            COALESCE(r.refund_minor, 0) AS refund_minor_as_of,
            h.gross_paid_minor - COALESCE(r.refund_minor, 0) AS net_paid_minor,
            (
                EXISTS (
                    SELECT 1 FROM rule_valid_status vs
                    WHERE encode(vs.status) = encode(h.status)
                )
                AND h.paid_at <= m.as_of
                AND (h.gross_paid_minor - COALESCE(r.refund_minor, 0)) > 0
            ) AS is_valid
        FROM {header_table} h
        JOIN dim_customer c
          ON encode(c.synthetic_user_id) = encode(h.synthetic_user_id)
        CROSS JOIN warehouse_meta m
        LEFT JOIN rule_channel_map cm
          ON encode(cm.source) = encode(h.channel)
        LEFT JOIN (
            SELECT rr.synthetic_user_id, rr.order_id, SUM(rr.refund_minor) AS refund_minor
            FROM src_refund rr, warehouse_meta
            WHERE rr.refunded_at <= warehouse_meta.as_of
              AND {_refund_filter_sql("rr")}
            GROUP BY encode(rr.synthetic_user_id), encode(rr.order_id), rr.synthetic_user_id, rr.order_id
        ) r
          ON encode(r.synthetic_user_id) = encode(h.synthetic_user_id)
         AND encode(r.order_id) = encode(h.order_id)
    """


def rebuild_affected_facts(connection) -> dict[str, int]:
    affected = int(connection.execute("SELECT COUNT(*) FROM stg_affected_order").fetchone()[0])
    if affected == 0:
        return fact_row_counts(connection)
    connection.execute(
        """
        DELETE FROM fact_order_line
        WHERE EXISTS (
            SELECT 1 FROM stg_affected_order a
            WHERE encode(a.synthetic_user_id) = encode(fact_order_line.synthetic_user_id)
              AND encode(a.order_id) = encode(fact_order_line.order_id)
        )
        """
    )
    connection.execute(
        """
        DELETE FROM fact_order_refund
        WHERE EXISTS (
            SELECT 1 FROM stg_affected_order a
            WHERE encode(a.synthetic_user_id) = encode(fact_order_refund.synthetic_user_id)
              AND encode(a.order_id) = encode(fact_order_refund.order_id)
        )
        """
    )
    # Keep parent keys stable: DuckDB cannot delete a referenced parent after
    # deleting its children in the same transaction. Source headers are upserts,
    # so update the affected parents in place and replace only their children.
    connection.execute(
        f"""
        INSERT INTO fact_order_header
        SELECT
            computed.synthetic_user_id,
            computed.order_id,
            computed.customer_key,
            computed.paid_at,
            computed.channel,
            computed.status,
            computed.permission_scope,
            computed.identity_domain,
            computed.gross_paid_minor,
            computed.refund_minor_as_of,
            computed.net_paid_minor,
            computed.is_valid
        FROM ({_computed_header_sql("src_order_header")}) computed
        JOIN stg_affected_order a
          ON encode(a.synthetic_user_id) = encode(computed.synthetic_user_id)
         AND encode(a.order_id) = encode(computed.order_id)
        ON CONFLICT (synthetic_user_id, order_id) DO UPDATE SET
            customer_key = excluded.customer_key,
            paid_at = excluded.paid_at,
            channel = excluded.channel,
            status = excluded.status,
            permission_scope = excluded.permission_scope,
            identity_domain = excluded.identity_domain,
            gross_paid_minor = excluded.gross_paid_minor,
            refund_minor_as_of = excluded.refund_minor_as_of,
            net_paid_minor = excluded.net_paid_minor,
            is_valid = excluded.is_valid
        """
    )
    connection.execute(
        """
        INSERT INTO fact_order_refund
        SELECT r.refund_id, r.synthetic_user_id, r.order_id, r.refunded_at, r.refund_minor
        FROM src_refund r
        JOIN stg_affected_order a
          ON encode(a.synthetic_user_id) = encode(r.synthetic_user_id)
         AND encode(a.order_id) = encode(r.order_id)
        """
    )
    connection.execute(
        """
        INSERT INTO fact_order_line
        SELECT
            l.line_id,
            l.synthetic_user_id,
            l.order_id,
            l.product_id,
            l.quantity,
            v.product_version_id
        FROM src_order_line l
        JOIN src_order_header h
          ON encode(h.synthetic_user_id) = encode(l.synthetic_user_id)
         AND encode(h.order_id) = encode(l.order_id)
        JOIN stg_affected_order a
          ON encode(a.synthetic_user_id) = encode(l.synthetic_user_id)
         AND encode(a.order_id) = encode(l.order_id)
        LEFT JOIN src_product_version v
          ON encode(v.product_id) = encode(l.product_id)
         AND h.paid_at >= v.valid_from
         AND h.paid_at < v.valid_to
        """
    )
    connection.execute(
        """
        DELETE FROM fact_first_purchase_product
        WHERE EXISTS (
            SELECT 1 FROM stg_affected_order a
            WHERE encode(a.synthetic_user_id) = encode(fact_first_purchase_product.synthetic_user_id)
        )
        """
    )
    connection.execute(
        """
        DELETE FROM fact_first_purchase
        WHERE EXISTS (
            SELECT 1 FROM stg_affected_order a
            WHERE encode(a.synthetic_user_id) = encode(fact_first_purchase.synthetic_user_id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO fact_first_purchase
        SELECT
            synthetic_user_id,
            customer_key,
            order_id,
            paid_at,
            channel,
            gross_paid_minor,
            net_paid_minor
        FROM (
            SELECT
                h.synthetic_user_id,
                h.customer_key,
                h.order_id,
                h.paid_at,
                h.channel,
                h.gross_paid_minor,
                h.net_paid_minor,
                ROW_NUMBER() OVER (
                    PARTITION BY encode(h.synthetic_user_id)
                    ORDER BY h.paid_at ASC, encode(h.order_id) ASC
                ) AS rn
            FROM fact_order_header h
            WHERE h.is_valid
              AND EXISTS (
                  SELECT 1 FROM stg_affected_order a
                  WHERE encode(a.synthetic_user_id) = encode(h.synthetic_user_id)
              )
        ) ranked
        WHERE rn = 1
        """
    )
    connection.execute(
        """
        INSERT INTO fact_first_purchase_product
        SELECT DISTINCT f.synthetic_user_id, l.product_id
        FROM fact_first_purchase f
        JOIN fact_order_line l
          ON encode(l.synthetic_user_id) = encode(f.synthetic_user_id)
         AND encode(l.order_id) = encode(f.order_id)
        WHERE EXISTS (
            SELECT 1 FROM stg_affected_order a
            WHERE encode(a.synthetic_user_id) = encode(f.synthetic_user_id)
        )
        """
    )
    return fact_row_counts(connection)


def count_future_refunds(connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) FROM src_refund r, warehouse_meta m
        WHERE r.refunded_at > m.as_of
        """
    ).fetchone()
    return int(row[0])
