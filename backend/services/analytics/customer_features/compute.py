"""Deterministic customer features from a published W1–W3 warehouse snapshot.

Reads `fact_order_header` only. Does not create order facts, identities, or
warehouse schema objects. Recency may advance with feature_as_of; validity and
net amounts stay on the snapshot and do not re-apply future refunds.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.services.analytics.customer_features.contract import (
    FEATURE_GRAIN,
    FEATURE_LAYER_VERSION,
    FEATURE_PIPELINE_VERSION,
    FEATURES_NAME,
    ORDER_GRAIN,
    PUBLISHED_FEATURES_NAME,
    RECENCY_BASIS,
    RECENCY_UNIT,
    SECONDS_PER_DAY,
    VALID_ORDER_RULE,
)
from backend.services.analytics.warehouse.contract import (
    PermissionScopeDenied,
    WarehouseContractError,
    parse_aware_instant,
    require_str_id,
    utc_naive_instant,
)


def _encode_list_sql(column: str) -> str:
    return (
        f"list_contains(list_transform(?::VARCHAR[], x -> encode(x)), encode({column}))"
    )


def _as_int(value) -> int:
    return int(value)


def _naive_utc(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_naive_instant(value)


def _format_shanghai(value) -> str:
    naive = _naive_utc(value)
    return naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).isoformat()


def _days_since(last_paid_at, feature_as_of_utc: datetime) -> int:
    last = _naive_utc(last_paid_at)
    seconds = int((feature_as_of_utc - last).total_seconds())
    if seconds < 0:
        raise WarehouseContractError("last_paid_at is after feature_as_of")
    return seconds // SECONDS_PER_DAY


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


def _read_warehouse_meta(connection) -> dict:
    row = connection.execute(
        """
        SELECT schema_version, rule_version, generator_version, pipeline_version,
               as_of, timezone, currency, amount_unit, amount_precision,
               content_hash, contains_real_data
        FROM warehouse_meta
        """
    ).fetchall()
    if len(row) != 1:
        raise WarehouseContractError("warehouse_meta must contain exactly one row")
    meta = row[0]
    if meta[10] is not False:
        raise WarehouseContractError("customer features refuse non-synthetic warehouses")
    return {
        "schema_version": meta[0],
        "rule_version": meta[1],
        "generator_version": meta[2],
        "pipeline_version": meta[3],
        "as_of": _naive_utc(meta[4]),
        "timezone": meta[5],
        "currency": meta[6],
        "amount_unit": meta[7],
        "amount_precision": meta[8],
        "content_hash": meta[9],
        "contains_real_data": False,
    }


def _require_published_alignment(meta: dict, published: dict) -> None:
    if not isinstance(published, dict):
        raise WarehouseContractError("published_manifest must be an object")
    if published.get("contains_real_data") is not False:
        raise WarehouseContractError("customer features refuse non-synthetic published manifests")
    mapping = {
        "schema_version": "schema_version",
        "rule_version": "rule_version",
        "generator_version": "generator_version",
        "pipeline_version": "pipeline_version",
        "content_hash": "content_hash",
        "timezone": "timezone",
        "currency": "currency",
        "amount_unit": "amount_unit",
        "amount_precision": "amount_precision",
    }
    for meta_key, published_key in mapping.items():
        if published.get(published_key) != meta[meta_key]:
            raise WarehouseContractError(f"published_manifest {published_key} does not match warehouse_meta")
    published_as_of = published.get("as_of")
    if utc_naive_instant(published_as_of) != meta["as_of"]:
        raise WarehouseContractError("published_manifest as_of does not match warehouse_meta")


def _optional_database_hash(database_path, published: dict) -> str | None:
    digest = published.get("database_sha256")
    if database_path is None:
        return digest
    path = Path(database_path)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest is not None and digest != actual:
        raise WarehouseContractError("published_manifest database_sha256 does not match warehouse file")
    return actual


@dataclass(frozen=True)
class CustomerFeatureRun:
    permission_scope: str
    warehouse_as_of: str
    feature_as_of: str
    schema_version: str
    rule_version: str
    generator_version: str
    pipeline_version: str
    feature_layer_version: str
    feature_pipeline_version: str
    content_hash: str
    database_sha256: str | None
    timezone: str
    currency: str
    amount_unit: str
    amount_precision: str
    rows: tuple[dict, ...]
    features_sha256: str

    def published_manifest(self) -> dict:
        return {
            "feature_layer_version": self.feature_layer_version,
            "feature_pipeline_version": self.feature_pipeline_version,
            "schema_version": self.schema_version,
            "rule_version": self.rule_version,
            "generator_version": self.generator_version,
            "pipeline_version": self.pipeline_version,
            "content_hash": self.content_hash,
            "database_sha256": self.database_sha256,
            "features_sha256": self.features_sha256,
            "features_hash_encoding": "sha256-jsonl-utf8-sorted-keys-final-lf-v1",
            "contains_real_data": False,
            "data_source": "SYNTHETIC_WAREHOUSE",
            "warehouse_as_of": self.warehouse_as_of,
            "feature_as_of": self.feature_as_of,
            "timezone": self.timezone,
            "currency": self.currency,
            "amount_unit": self.amount_unit,
            "amount_precision": self.amount_precision,
            "permission_scope": self.permission_scope,
            "valid_order_rule": VALID_ORDER_RULE,
            "order_grain": list(ORDER_GRAIN),
            "feature_grain": list(FEATURE_GRAIN),
            "recency_unit": RECENCY_UNIT,
            "recency_basis": RECENCY_BASIS,
            "row_count": len(self.rows),
        }


def compute_customer_features(
    connection,
    *,
    permission_scope: str,
    published_manifest: dict,
    feature_as_of=None,
    synthetic_user_ids=None,
    database_path=None,
) -> CustomerFeatureRun:
    meta = _read_warehouse_meta(connection)
    _require_published_alignment(meta, published_manifest)
    database_sha256 = _optional_database_hash(database_path, published_manifest)
    _require_scope(connection, permission_scope)
    warehouse_as_of = published_manifest["as_of"]
    requested_as_of = warehouse_as_of if feature_as_of is None else feature_as_of
    parse_aware_instant(requested_as_of)
    feature_as_of_utc = utc_naive_instant(requested_as_of)
    if feature_as_of_utc < meta["as_of"]:
        raise WarehouseContractError("feature_as_of cannot precede warehouse snapshot as_of")

    users = None if synthetic_user_ids is None else [require_str_id(item, name="synthetic_user_id") for item in synthetic_user_ids]
    if users is not None:
        _reject_cross_scope_users(connection, permission_scope, users)

    params: list = [permission_scope, feature_as_of_utc]
    user_sql = ""
    if users is not None:
        if not users:
            rows = []
            return _finish(
                permission_scope=permission_scope,
                warehouse_as_of=warehouse_as_of,
                feature_as_of=requested_as_of,
                meta=meta,
                database_sha256=database_sha256,
                rows=rows,
            )
        user_sql = f"AND {_encode_list_sql('synthetic_user_id')}"
        params.append(users)

    fetched = connection.execute(
        f"""
        WITH valid AS (
            SELECT
                customer_key,
                synthetic_user_id,
                identity_domain,
                permission_scope,
                order_id,
                paid_at,
                net_paid_minor,
                ROW_NUMBER() OVER (
                    PARTITION BY encode(synthetic_user_id)
                    ORDER BY paid_at ASC, encode(order_id) ASC
                ) AS first_rn,
                ROW_NUMBER() OVER (
                    PARTITION BY encode(synthetic_user_id)
                    ORDER BY paid_at DESC, encode(order_id) DESC
                ) AS last_rn
            FROM fact_order_header
            WHERE encode(permission_scope) = encode(?)
              AND is_valid
              AND paid_at <= ?
              {user_sql}
        )
        SELECT
            customer_key,
            synthetic_user_id,
            identity_domain,
            permission_scope,
            MAX(CASE WHEN first_rn = 1 THEN order_id END) AS first_order_id,
            MAX(CASE WHEN first_rn = 1 THEN paid_at END) AS first_paid_at,
            MAX(CASE WHEN last_rn = 1 THEN order_id END) AS last_order_id,
            MAX(CASE WHEN last_rn = 1 THEN paid_at END) AS last_paid_at,
            COUNT(*) AS valid_order_count,
            SUM(net_paid_minor) AS valid_net_paid_minor
        FROM valid
        GROUP BY
            encode(synthetic_user_id),
            customer_key,
            synthetic_user_id,
            identity_domain,
            permission_scope
        ORDER BY customer_key ASC
        """,
        params,
    ).fetchall()

    rows = []
    for row in fetched:
        last_paid_at = row[7]
        rows.append({
            "customer_key": _as_int(row[0]),
            "synthetic_user_id": row[1],
            "identity_domain": row[2],
            "permission_scope": row[3],
            "first_order_id": row[4],
            "first_paid_at": _format_shanghai(row[5]),
            "last_order_id": row[6],
            "last_paid_at": _format_shanghai(last_paid_at),
            "valid_order_count": _as_int(row[8]),
            "valid_net_paid_minor": _as_int(row[9]),
            "days_since_last_paid": _days_since(last_paid_at, feature_as_of_utc),
        })
    return _finish(
        permission_scope=permission_scope,
        warehouse_as_of=warehouse_as_of,
        feature_as_of=requested_as_of,
        meta=meta,
        database_sha256=database_sha256,
        rows=rows,
    )


def _feature_bytes(rows) -> bytes:
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False) for row in rows]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def _finish(
    *,
    permission_scope: str,
    warehouse_as_of: str,
    feature_as_of: str,
    meta: dict,
    database_sha256,
    rows: list[dict],
) -> CustomerFeatureRun:
    payload = _feature_bytes(rows)
    return CustomerFeatureRun(
        permission_scope=permission_scope,
        warehouse_as_of=warehouse_as_of,
        feature_as_of=feature_as_of,
        schema_version=meta["schema_version"],
        rule_version=meta["rule_version"],
        generator_version=meta["generator_version"],
        pipeline_version=meta["pipeline_version"],
        feature_layer_version=FEATURE_LAYER_VERSION,
        feature_pipeline_version=FEATURE_PIPELINE_VERSION,
        content_hash=meta["content_hash"],
        database_sha256=database_sha256,
        timezone=meta["timezone"],
        currency=meta["currency"],
        amount_unit=meta["amount_unit"],
        amount_precision=meta["amount_precision"],
        rows=tuple(rows),
        features_sha256=hashlib.sha256(payload).hexdigest(),
    )


def write_customer_features(run: CustomerFeatureRun, output_dir) -> dict:
    root = Path(output_dir)
    if not root.is_dir():
        raise WarehouseContractError("feature output directory must exist")
    if any(root.iterdir()):
        raise WarehouseContractError("feature output directory must be empty")
    # Serialize once, validate these exact bytes, then write those same bytes.
    features_payload = _feature_bytes(run.rows)
    if hashlib.sha256(features_payload).hexdigest() != run.features_sha256:
        raise WarehouseContractError("customer feature rows changed after computation")
    published = run.published_manifest()
    published_payload = (
        json.dumps(published, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    _write_exclusive(root / FEATURES_NAME, features_payload)
    _write_exclusive(root / PUBLISHED_FEATURES_NAME, published_payload)
    return published


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
