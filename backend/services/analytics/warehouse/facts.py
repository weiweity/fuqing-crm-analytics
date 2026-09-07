"""Fact grain, identity keys, valid-order flags, and scoped reads."""

from __future__ import annotations

from backend.services.analytics.warehouse.contract import (
    PermissionScopeDenied,
    WarehouseContractError,
    require_minor,
    require_str_id,
    utc_naive_instant,
)
from backend.services.analytics.warehouse.generate import canonical_record_hash

CREATE_SQL = """
CREATE TABLE dim_customer (
    customer_key BIGINT NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    identity_domain VARCHAR COLLATE C NOT NULL,
    permission_scope VARCHAR COLLATE C NOT NULL,
    UNIQUE (synthetic_user_id),
    UNIQUE (identity_domain, synthetic_user_id)
);
CREATE TABLE map_identity (
    identity_domain VARCHAR COLLATE C NOT NULL,
    source_channel VARCHAR COLLATE C NOT NULL,
    source_user_id VARCHAR COLLATE C NOT NULL,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    permission_scope VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (identity_domain, source_channel, source_user_id)
);
CREATE TABLE fact_order_header (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    customer_key BIGINT NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    permission_scope VARCHAR COLLATE C NOT NULL,
    identity_domain VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    refund_minor_as_of BIGINT NOT NULL,
    net_paid_minor BIGINT NOT NULL,
    is_valid BOOLEAN NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
CREATE TABLE fact_order_line (
    line_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    product_version_id VARCHAR COLLATE C,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES fact_order_header(synthetic_user_id, order_id)
);
CREATE TABLE fact_order_refund (
    refund_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    FOREIGN KEY (synthetic_user_id, order_id)
        REFERENCES fact_order_header(synthetic_user_id, order_id)
);
CREATE TABLE fact_first_purchase (
    synthetic_user_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    customer_key BIGINT NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    header_gross_paid_minor BIGINT NOT NULL,
    header_net_paid_minor BIGINT NOT NULL
);
CREATE TABLE fact_first_purchase_product (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, product_id)
);
CREATE TABLE warehouse_meta (
    schema_version VARCHAR COLLATE C NOT NULL,
    rule_version VARCHAR COLLATE C NOT NULL,
    generator_version VARCHAR COLLATE C NOT NULL,
    pipeline_version VARCHAR COLLATE C NOT NULL,
    as_of TIMESTAMP NOT NULL,
    timezone VARCHAR COLLATE C NOT NULL,
    currency VARCHAR COLLATE C NOT NULL,
    amount_unit VARCHAR COLLATE C NOT NULL,
    amount_precision VARCHAR COLLATE C NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL,
    seed BIGINT,
    contains_real_data BOOLEAN NOT NULL,
    rules_json VARCHAR COLLATE C NOT NULL
);
CREATE TABLE src_order_header (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
CREATE TABLE src_order_line (
    line_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE src_refund (
    refund_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    refund_class VARCHAR COLLATE C NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE src_product_version (
    product_version_id VARCHAR COLLATE C NOT NULL PRIMARY KEY,
    product_id VARCHAR COLLATE C NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
"""

STAGING_SQL = """
CREATE TABLE stg_identity (
    identity_domain VARCHAR COLLATE C NOT NULL,
    source_channel VARCHAR COLLATE C NOT NULL,
    source_user_id VARCHAR COLLATE C NOT NULL,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    permission_scope VARCHAR COLLATE C NOT NULL
);
CREATE TABLE stg_order_header (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    channel VARCHAR COLLATE C NOT NULL,
    status VARCHAR COLLATE C NOT NULL,
    gross_paid_minor BIGINT NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE stg_order_line (
    line_id VARCHAR COLLATE C NOT NULL,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    product_id VARCHAR COLLATE C NOT NULL,
    quantity BIGINT NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE stg_refund (
    refund_id VARCHAR COLLATE C NOT NULL,
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    refunded_at TIMESTAMP NOT NULL,
    refund_minor BIGINT NOT NULL,
    refund_class VARCHAR COLLATE C NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE stg_product_version (
    product_id VARCHAR COLLATE C NOT NULL,
    product_version_id VARCHAR COLLATE C NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    content_hash VARCHAR COLLATE C NOT NULL
);
CREATE TABLE stg_affected_order (
    synthetic_user_id VARCHAR COLLATE C NOT NULL,
    order_id VARCHAR COLLATE C NOT NULL,
    PRIMARY KEY (synthetic_user_id, order_id)
);
"""


def _encode_list_sql(column: str) -> str:
    return (
        f"list_contains(list_transform(?::VARCHAR[], x -> encode(x)), encode({column}))"
    )


def load_identities(connection, identities: list[dict]) -> int:
    if not identities:
        return int(connection.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0])
    rows = []
    for item in identities:
        rows.append((
            require_str_id(item.get("identity_domain"), name="identity_domain"),
            require_str_id(item.get("source_channel"), name="source_channel"),
            require_str_id(item.get("source_user_id"), name="source_user_id"),
            require_str_id(item.get("synthetic_user_id"), name="synthetic_user_id"),
            require_str_id(item.get("permission_scope"), name="permission_scope"),
        ))
    connection.executemany("INSERT INTO stg_identity VALUES (?, ?, ?, ?, ?)", rows)
    mixed = connection.execute(
        """
        SELECT identity_domain
        FROM stg_identity
        GROUP BY encode(identity_domain), identity_domain
        HAVING COUNT(DISTINCT encode(permission_scope)) > 1
        """
    ).fetchall()
    if mixed:
        raise PermissionScopeDenied("identity domain mixes permission_scope values")
    split_users = connection.execute(
        """
        SELECT synthetic_user_id
        FROM stg_identity
        GROUP BY encode(synthetic_user_id), synthetic_user_id
        HAVING COUNT(DISTINCT encode(identity_domain)) > 1
            OR COUNT(DISTINCT encode(permission_scope)) > 1
        """
    ).fetchall()
    if split_users:
        raise WarehouseContractError("synthetic_user_id maps to multiple identity domains or scopes")
    cross_existing = connection.execute(
        """
        SELECT s.identity_domain
        FROM stg_identity s
        JOIN dim_customer c
          ON encode(c.identity_domain) = encode(s.identity_domain)
        WHERE encode(c.permission_scope) <> encode(s.permission_scope)
        """
    ).fetchall()
    if cross_existing:
        raise PermissionScopeDenied("identity domain already bound to another permission_scope")
    remap = connection.execute(
        """
        SELECT s.source_user_id
        FROM stg_identity s
        JOIN map_identity m
          ON encode(m.identity_domain) = encode(s.identity_domain)
         AND encode(m.source_channel) = encode(s.source_channel)
         AND encode(m.source_user_id) = encode(s.source_user_id)
        WHERE encode(m.synthetic_user_id) <> encode(s.synthetic_user_id)
           OR encode(m.permission_scope) <> encode(s.permission_scope)
        """
    ).fetchall()
    if remap:
        raise WarehouseContractError("identity mapping changed for an existing source key")
    connection.execute(
        """
        INSERT INTO map_identity
        SELECT identity_domain, source_channel, source_user_id, synthetic_user_id, permission_scope
        FROM stg_identity
        ON CONFLICT (identity_domain, source_channel, source_user_id) DO NOTHING
        """
    )
    connection.execute(
        """
        INSERT INTO dim_customer
        SELECT
            (SELECT COALESCE(MAX(customer_key), 0) FROM dim_customer)
                + ROW_NUMBER() OVER (
                    ORDER BY encode(identity_domain) ASC, encode(synthetic_user_id) ASC
                ) AS customer_key,
            synthetic_user_id,
            identity_domain,
            permission_scope
        FROM (
            SELECT DISTINCT s.identity_domain, s.synthetic_user_id, s.permission_scope
            FROM stg_identity s
            WHERE NOT EXISTS (
                SELECT 1 FROM dim_customer c
                WHERE encode(c.synthetic_user_id) = encode(s.synthetic_user_id)
            )
        ) new_users
        """
    )
    return int(connection.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0])


def load_staging_orders(connection, orders: list[dict]) -> int:
    rows = []
    seen = set()
    for order in orders:
        user_id = require_str_id(order.get("synthetic_user_id"), name="synthetic_user_id")
        order_id = require_str_id(order.get("order_id"), name="order_id")
        key = (user_id, order_id)
        if key in seen:
            raise WarehouseContractError("duplicate (synthetic_user_id, order_id) in source")
        seen.add(key)
        rows.append((
            user_id,
            order_id,
            utc_naive_instant(order.get("paid_at")),
            require_str_id(order.get("channel"), name="channel"),
            require_str_id(order.get("status"), name="status"),
            require_minor(order.get("gross_paid_minor"), name="gross_paid_minor"),
            canonical_record_hash(order),
        ))
    if rows:
        connection.executemany("INSERT INTO stg_order_header VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    unknown = connection.execute(
        """
        SELECT COUNT(*) FROM stg_order_header h
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_customer c
            WHERE encode(c.synthetic_user_id) = encode(h.synthetic_user_id)
        )
        """
    ).fetchone()[0]
    if unknown:
        raise WarehouseContractError("order references unknown synthetic_user_id")
    return len(rows)


def load_staging_lines(connection, lines: list[dict]) -> int:
    rows = []
    for line in lines:
        quantity = line.get("quantity")
        if type(quantity) is not int or quantity < 1:
            raise WarehouseContractError("quantity must be a positive integer")
        rows.append((
            require_str_id(line.get("line_id"), name="line_id"),
            require_str_id(line.get("synthetic_user_id"), name="synthetic_user_id"),
            require_str_id(line.get("order_id"), name="order_id"),
            require_str_id(line.get("product_id"), name="product_id"),
            quantity,
            canonical_record_hash(line),
        ))
    if rows:
        connection.executemany("INSERT INTO stg_order_line VALUES (?, ?, ?, ?, ?, ?)", rows)
    orphans = connection.execute(
        """
        SELECT COUNT(*) FROM stg_order_line l
        WHERE NOT EXISTS (
            SELECT 1 FROM stg_order_header h
            WHERE encode(h.synthetic_user_id) = encode(l.synthetic_user_id)
              AND encode(h.order_id) = encode(l.order_id)
        )
        AND NOT EXISTS (
            SELECT 1 FROM src_order_header h
            WHERE encode(h.synthetic_user_id) = encode(l.synthetic_user_id)
              AND encode(h.order_id) = encode(l.order_id)
        )
        """
    ).fetchone()[0]
    if orphans:
        raise WarehouseContractError("line references missing order header")
    return len(rows)


def load_staging_refunds(connection, refunds: list[dict]) -> int:
    rows = []
    for refund in refunds:
        refund_class = refund.get("refund_class")
        if refund_class is None:
            refund_class = "standard"
        else:
            refund_class = require_str_id(refund_class, name="refund_class")
        rows.append((
            require_str_id(refund.get("refund_id"), name="refund_id"),
            require_str_id(refund.get("synthetic_user_id"), name="synthetic_user_id"),
            require_str_id(refund.get("order_id"), name="order_id"),
            utc_naive_instant(refund.get("refunded_at")),
            require_minor(refund.get("refund_minor"), name="refund_minor"),
            refund_class,
            canonical_record_hash(refund),
        ))
    if rows:
        connection.executemany("INSERT INTO stg_refund VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    orphans = connection.execute(
        """
        SELECT COUNT(*) FROM stg_refund r
        WHERE NOT EXISTS (
            SELECT 1 FROM stg_order_header h
            WHERE encode(h.synthetic_user_id) = encode(r.synthetic_user_id)
              AND encode(h.order_id) = encode(r.order_id)
        )
        AND NOT EXISTS (
            SELECT 1 FROM src_order_header h
            WHERE encode(h.synthetic_user_id) = encode(r.synthetic_user_id)
              AND encode(h.order_id) = encode(r.order_id)
        )
        """
    ).fetchone()[0]
    if orphans:
        raise WarehouseContractError("refund references missing order header")
    return len(rows)


def load_staging_versions(connection, versions: list[dict]) -> int:
    rows = []
    for version in versions:
        valid_from = utc_naive_instant(version.get("valid_from"))
        valid_to = utc_naive_instant(version.get("valid_to"))
        if valid_to <= valid_from:
            raise WarehouseContractError("product version valid_to must be exclusive and after valid_from")
        rows.append((
            require_str_id(version.get("product_id"), name="product_id"),
            require_str_id(version.get("product_version_id"), name="product_version_id"),
            valid_from,
            valid_to,
            canonical_record_hash(version),
        ))
    if rows:
        connection.executemany("INSERT INTO stg_product_version VALUES (?, ?, ?, ?, ?)", rows)
    overlap = connection.execute(
        """
        SELECT COUNT(*) FROM stg_product_version a
        JOIN stg_product_version b
          ON encode(a.product_id) = encode(b.product_id)
         AND encode(a.product_version_id) < encode(b.product_version_id)
         AND a.valid_from < b.valid_to
         AND b.valid_from < a.valid_to
        """
    ).fetchone()[0]
    if overlap:
        raise WarehouseContractError("product versions overlap on the same product_id")
    return len(rows)


def count_unconstrained_product_join(connection) -> int:
    """Cartesian product_id join size (diagnosis replica). Not used for amounts."""
    row = connection.execute(
        """
        SELECT COUNT(*) FROM stg_order_line l
        JOIN stg_product_version v
          ON encode(l.product_id) = encode(v.product_id)
        """
    ).fetchone()
    return int(row[0])


def attach_product_versions(connection) -> int:
    """Range-join versions onto lines. Header amounts stay on fact_order_header."""
    connection.execute(
        """
        CREATE TABLE stg_line_version AS
        SELECT
            l.line_id,
            l.synthetic_user_id,
            l.order_id,
            l.product_id,
            l.quantity,
            v.product_version_id
        FROM stg_order_line l
        INNER JOIN stg_order_header h
          ON encode(l.synthetic_user_id) = encode(h.synthetic_user_id)
         AND encode(l.order_id) = encode(h.order_id)
        LEFT JOIN stg_product_version v
          ON encode(l.product_id) = encode(v.product_id)
         AND h.paid_at >= v.valid_from
         AND h.paid_at < v.valid_to
        """
    )
    matched = connection.execute("SELECT COUNT(*) FROM stg_line_version").fetchone()[0]
    return int(matched)


def fact_row_counts(connection) -> dict[str, int]:
    counts = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM fact_order_header),
            (SELECT COUNT(*) FROM fact_order_line),
            (SELECT COUNT(*) FROM fact_order_refund),
            (SELECT COUNT(*) FROM dim_customer),
            (SELECT COUNT(*) FROM fact_first_purchase)
        """
    ).fetchone()
    return {
        "fact_order_header": int(counts[0]),
        "fact_order_line": int(counts[1]),
        "fact_order_refund": int(counts[2]),
        "dim_customer": int(counts[3]),
        "fact_first_purchase": int(counts[4]),
    }


def _require_scope(connection, permission_scope: str) -> None:
    require_str_id(permission_scope, name="permission_scope")
    known = {
        row[0]
        for row in connection.execute("SELECT DISTINCT permission_scope FROM dim_customer").fetchall()
    }
    if permission_scope not in known:
        raise PermissionScopeDenied("permission_scope is not present in the warehouse")


def _reject_cross_scope_users(connection, permission_scope: str, user_ids: list[str]) -> None:
    if not user_ids:
        return
    rows = connection.execute(
        f"""
        SELECT synthetic_user_id, permission_scope
        FROM dim_customer
        WHERE {_encode_list_sql("synthetic_user_id")}
        """,
        [user_ids],
    ).fetchall()
    found = {row[0]: row[1] for row in rows}
    for user_id in user_ids:
        if user_id not in found or found[user_id] != permission_scope:
            raise PermissionScopeDenied("cross permission_scope access is refused")


def read_fact_order_header(connection, *, permission_scope: str, synthetic_user_ids=None) -> list[dict]:
    _require_scope(connection, permission_scope)
    users = list(synthetic_user_ids) if synthetic_user_ids is not None else None
    if users is not None:
        _reject_cross_scope_users(connection, permission_scope, users)
        rows = connection.execute(
            f"""
            SELECT synthetic_user_id, order_id, customer_key, paid_at, channel, status,
                   permission_scope, identity_domain, gross_paid_minor, refund_minor_as_of,
                   net_paid_minor, is_valid
            FROM fact_order_header
            WHERE encode(permission_scope) = encode(?)
              AND {_encode_list_sql("synthetic_user_id")}
            ORDER BY encode(synthetic_user_id), encode(order_id)
            """,
            [permission_scope, users],
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT synthetic_user_id, order_id, customer_key, paid_at, channel, status,
                   permission_scope, identity_domain, gross_paid_minor, refund_minor_as_of,
                   net_paid_minor, is_valid
            FROM fact_order_header
            WHERE encode(permission_scope) = encode(?)
            ORDER BY encode(synthetic_user_id), encode(order_id)
            """,
            [permission_scope],
        ).fetchall()
    result = []
    for row in rows:
        result.append({
            "synthetic_user_id": row[0],
            "order_id": row[1],
            "customer_key": int(row[2]),
            "paid_at": row[3],
            "channel": row[4],
            "status": row[5],
            "permission_scope": row[6],
            "identity_domain": row[7],
            "gross_paid_minor": int(row[8]),
            "refund_minor_as_of": int(row[9]),
            "net_paid_minor": int(row[10]),
            "is_valid": bool(row[11]),
        })
    return result


def read_fact_order_line(connection, *, permission_scope: str) -> list[dict]:
    _require_scope(connection, permission_scope)
    rows = connection.execute(
        """
        SELECT l.line_id, l.synthetic_user_id, l.order_id, l.product_id, l.quantity, l.product_version_id
        FROM fact_order_line l
        JOIN fact_order_header h
          ON encode(h.synthetic_user_id) = encode(l.synthetic_user_id)
         AND encode(h.order_id) = encode(l.order_id)
        WHERE encode(h.permission_scope) = encode(?)
        ORDER BY encode(l.line_id)
        """,
        [permission_scope],
    ).fetchall()
    return [
        {
            "line_id": row[0],
            "synthetic_user_id": row[1],
            "order_id": row[2],
            "product_id": row[3],
            "quantity": int(row[4]),
            "product_version_id": row[5],
        }
        for row in rows
    ]


def read_first_purchases(connection, *, permission_scope: str) -> list[dict]:
    _require_scope(connection, permission_scope)
    headers = connection.execute(
        """
        SELECT synthetic_user_id, customer_key, order_id, paid_at, channel,
               header_gross_paid_minor, header_net_paid_minor
        FROM fact_first_purchase
        WHERE encode(synthetic_user_id) IN (
            SELECT encode(synthetic_user_id) FROM dim_customer
            WHERE encode(permission_scope) = encode(?)
        )
        ORDER BY encode(synthetic_user_id)
        """,
        [permission_scope],
    ).fetchall()
    products = connection.execute(
        """
        SELECT p.synthetic_user_id, p.product_id
        FROM fact_first_purchase_product p
        JOIN dim_customer c
          ON encode(c.synthetic_user_id) = encode(p.synthetic_user_id)
        WHERE encode(c.permission_scope) = encode(?)
        ORDER BY encode(p.synthetic_user_id), encode(p.product_id)
        """,
        [permission_scope],
    ).fetchall()
    by_user: dict[str, list[str]] = {}
    for user_id, product_id in products:
        by_user.setdefault(user_id, []).append(product_id)
    result = []
    for row in headers:
        result.append({
            "synthetic_user_id": row[0],
            "customer_key": int(row[1]),
            "order_id": row[2],
            "paid_at": row[3],
            "channel": row[4],
            "header_gross_paid_minor": int(row[5]),
            "header_net_paid_minor": int(row[6]),
            "product_ids": list(by_user.get(row[0], [])),
        })
    return result


def customer_key_for_source(
    connection,
    *,
    identity_domain: str,
    source_channel: str,
    source_user_id: str,
    permission_scope: str,
) -> int:
    _require_scope(connection, permission_scope)
    row = connection.execute(
        """
        SELECT m.synthetic_user_id, m.permission_scope, m.identity_domain, c.customer_key
        FROM map_identity m
        JOIN dim_customer c
          ON encode(c.synthetic_user_id) = encode(m.synthetic_user_id)
        WHERE encode(m.identity_domain) = encode(?)
          AND encode(m.source_channel) = encode(?)
          AND encode(m.source_user_id) = encode(?)
        """,
        [identity_domain, source_channel, source_user_id],
    ).fetchone()
    if row is None:
        raise PermissionScopeDenied("identity mapping is not visible in this permission_scope")
    if row[1] != permission_scope or row[2] != identity_domain:
        raise PermissionScopeDenied("cross permission_scope identity lookup is refused")
    return int(row[3])
