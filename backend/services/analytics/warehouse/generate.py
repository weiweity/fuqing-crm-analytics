"""Fixed-seed synthetic warehouse sources. Filesystem only; no DuckDB."""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.services.analytics.warehouse.contract import (
    AMOUNT_PRECISION,
    AMOUNT_UNIT,
    CURRENCY,
    DATA_SOURCE,
    DEFAULT_AS_OF,
    DEFAULT_SEED,
    GENERATOR_VERSION,
    MANIFEST_NAME,
    PIPELINE_VERSION,
    RULE_VERSION,
    SCHEMA_VERSION,
    TIMEZONE,
    WarehouseContractError,
    normalize_rules,
    require_minor,
    require_str_id,
)

SOURCE_FILES = (
    "orders.jsonl",
    "lines.jsonl",
    "refunds.jsonl",
    "product_versions.jsonl",
    "identities.jsonl",
)
PRODUCED_AT = "2026-09-01T00:00:00.000000+00:00"
SHANGHAI = ZoneInfo(TIMEZONE)


def _canonical_jsonl(rows: list[dict], sort_by: tuple[str, ...]) -> bytes:
    ordered = sorted(rows, key=lambda row: tuple(row[key] for key in sort_by))
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in ordered
    ).encode("utf-8")


def _write_exclusive(path: Path, payload: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def content_hash_from_file_hashes(file_hashes: dict[str, str]) -> str:
    material = json.dumps(file_hashes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_hex(material.encode("utf-8"))


def canonical_record_hash(record: dict) -> str:
    material = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_hex(material.encode("utf-8"))


def _manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


@dataclass(frozen=True)
class SourceManifest:
    directory: str
    payload: dict
    content_hash: str

    def to_dict(self) -> dict:
        return dict(self.payload)


def write_tabular_sources(
    directory,
    *,
    orders: list[dict],
    lines: list[dict],
    refunds: list[dict],
    product_versions: list[dict],
    identities: list[dict],
    as_of: str = DEFAULT_AS_OF,
    seed: int | None = None,
    source_kind: str = "synthetic_generator",
    generator_id: str = "analytics-warehouse-w1",
    rules=None,
    rule_version: str = RULE_VERSION,
) -> SourceManifest:
    root = Path(directory)
    if not root.is_dir():
        raise WarehouseContractError("source directory must exist")
    if any(root.iterdir()):
        raise WarehouseContractError("source directory must be empty")
    for order in orders:
        require_str_id(order.get("synthetic_user_id"), name="synthetic_user_id")
        require_str_id(order.get("order_id"), name="order_id")
        require_minor(order.get("gross_paid_minor"), name="gross_paid_minor")
    tables = {
        "orders.jsonl": (_canonical_jsonl(orders, ("synthetic_user_id", "order_id")),),
        "lines.jsonl": (_canonical_jsonl(lines, ("line_id",)),),
        "refunds.jsonl": (_canonical_jsonl(refunds, ("refund_id",)),),
        "product_versions.jsonl": (_canonical_jsonl(product_versions, ("product_version_id",)),),
        "identities.jsonl": (
            _canonical_jsonl(identities, ("identity_domain", "source_channel", "source_user_id")),
        ),
    }
    file_hashes = {}
    for name, (payload,) in tables.items():
        _write_exclusive(root / name, payload)
        file_hashes[name] = _sha256_hex(payload)
    digest = content_hash_from_file_hashes(file_hashes)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": rule_version,
        "generator_version": GENERATOR_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "source_identity": {
            "kind": source_kind,
            "generator_id": generator_id,
            "seed": seed,
            "produced_at": PRODUCED_AT,
        },
        "content_hash": digest,
        "file_hashes": file_hashes,
        "contains_real_data": False,
        "data_source": DATA_SOURCE,
        "seed": seed,
        "as_of": as_of,
        "timezone": TIMEZONE,
        "currency": CURRENCY,
        "amount_unit": AMOUNT_UNIT,
        "amount_precision": AMOUNT_PRECISION,
        "row_counts": {
            "orders": len(orders),
            "lines": len(lines),
            "refunds": len(refunds),
            "product_versions": len(product_versions),
            "identities": len(identities),
        },
    }
    if rules is not None:
        manifest["rules"] = normalize_rules(rules)
    _write_exclusive(root / MANIFEST_NAME, _manifest_bytes(manifest))
    return SourceManifest(str(root), manifest, digest)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def generate_synthetic_sources(directory, *, seed: int = DEFAULT_SEED, as_of: str = DEFAULT_AS_OF) -> SourceManifest:
    rng = random.Random(seed)
    users = []
    for index in range(8):
        if index == 0:
            user_id = "0009007199254740993"
        else:
            user_id = f"{index:019d}{rng.randrange(10**18):018d}"
        users.append(user_id)
    identities = []
    for index, user_id in enumerate(users):
        domain = "group-2" if index == 7 else "group-1"
        scope = "brand_b" if index == 7 else "brand_a"
        identities.append({
            "identity_domain": domain,
            "source_channel": "taobao",
            "source_user_id": f"tb-{user_id}",
            "synthetic_user_id": user_id,
            "permission_scope": scope,
        })
        identities.append({
            "identity_domain": domain,
            "source_channel": "jd",
            "source_user_id": f"jd-{user_id}",
            "synthetic_user_id": user_id,
            "permission_scope": scope,
        })
    products = ["sku_sample", "sku_full", "sku_a", "sku_b"]
    versions = []
    for product in products:
        for month in range(1, 10):
            valid_from = datetime(2026, month, 1, tzinfo=SHANGHAI)
            valid_to = datetime(2026, month + 1, 1, tzinfo=SHANGHAI) if month < 9 else datetime(2027, 1, 1, tzinfo=SHANGHAI)
            versions.append({
                "product_id": product,
                "product_version_id": f"{product}-m{month:02d}",
                "valid_from": _iso(valid_from),
                "valid_to": _iso(valid_to),
            })
    orders = []
    lines = []
    refunds = []
    for index, user_id in enumerate(users):
        first_paid = datetime(2026, 6, 1, 10, 0, tzinfo=SHANGHAI) + timedelta(days=index)
        second_paid = first_paid + timedelta(days=12)
        first_id = f"o-{index:02d}-a"
        second_id = "dup-oid" if index >= 6 else f"o-{index:02d}-b"
        channel_a = "A" if index % 2 == 0 else "B"
        channel_b = "B" if channel_a == "A" else "A"
        first_gross = 15000 if index == 0 else 1000 * (index + 3)
        second_gross = 7000 if index == 0 else 500 * (index + 2)
        orders.append({
            "synthetic_user_id": user_id,
            "order_id": first_id,
            "paid_at": _iso(first_paid),
            "channel": channel_a,
            "status": "PAID",
            "gross_paid_minor": first_gross,
        })
        orders.append({
            "synthetic_user_id": user_id,
            "order_id": second_id,
            "paid_at": _iso(second_paid),
            "channel": channel_b,
            "status": "PAID",
            "gross_paid_minor": second_gross,
        })
        first_product = products[index % len(products)]
        lines.append({
            "line_id": f"{first_id}-l1",
            "synthetic_user_id": user_id,
            "order_id": first_id,
            "product_id": first_product,
            "quantity": 1,
        })
        if index == 0:
            lines.append({
                "line_id": f"{first_id}-l2",
                "synthetic_user_id": user_id,
                "order_id": first_id,
                "product_id": "sku_full",
                "quantity": 1,
            })
        lines.append({
            "line_id": f"{second_id}-l1-{index}",
            "synthetic_user_id": user_id,
            "order_id": second_id,
            "product_id": products[(index + 1) % len(products)],
            "quantity": 1,
        })
        if index in (0, 3):
            refunds.append({
                "refund_id": f"{second_id}-r1-{index}",
                "synthetic_user_id": user_id,
                "order_id": second_id,
                "refunded_at": _iso(second_paid + timedelta(days=1)),
                "refund_minor": 2000,
            })
    return write_tabular_sources(
        directory,
        orders=orders,
        lines=lines,
        refunds=refunds,
        product_versions=versions,
        identities=identities,
        as_of=as_of,
        seed=seed,
        source_kind="synthetic_generator",
        generator_id="analytics-warehouse-w1",
    )
