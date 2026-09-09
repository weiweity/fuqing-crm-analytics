"""Explicit, bounded synthetic input. Never discovers test modules or real data."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import timedelta

from backend.contracts.analytics_query import canonical_rfc3339, parse_query_datetime
from backend.services.analytics.resource_profile import canonical_json, content_hash

MAX_ROWS = 10000
MAX_DATABASE_BYTES = 16 * 1024 * 1024
ORDER_FIELDS = ("order_id", "sub_order_id", "user_id", "pay_time", "channel", "actual_amount",
                "is_member", "is_refund", "is_goujinjin", "order_status", "product_id", "spu_type")
DDL = """
CREATE TABLE orders (
    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR, pay_time TIMESTAMP,
    channel VARCHAR, actual_amount DOUBLE, is_member BOOLEAN, is_refund BOOLEAN,
    is_goujinjin BOOLEAN, order_status VARCHAR, product_id VARCHAR, spu_type VARCHAR
);
CREATE TABLE refunds (order_id VARCHAR, refunded_at DATE, amount DOUBLE);
"""


@dataclass(frozen=True)
class SyntheticDiagnosisSource:
    path: Path
    file_digest: str
    data_digest: str
    snapshot_id: str
    data_version: str
    published_at: datetime
    coverage_start: date
    data_through: date

    @contextmanager
    def connect(self):
        import duckdb

        if (self.path.is_symlink() or not self.path.is_file()
                or self.path.stat().st_size > MAX_DATABASE_BYTES
                or sha256(self.path.read_bytes()).hexdigest() != self.file_digest):
            raise ValueError("synthetic diagnosis snapshot changed")
        connection = duckdb.connect(str(self.path), read_only=True, config={
            "threads": 1, "memory_limit": "64MB", "enable_external_access": "false",
        })
        try:
            connection.execute("SET lock_configuration=true")
            yield connection
        finally:
            connection.close()


def materialize_synthetic_source(directory: Path, payload: dict) -> SyntheticDiagnosisSource:
    """Caller-owned private, empty directory; input is server data, never HTTP."""
    import duckdb

    if (directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077
            or directory.stat().st_uid != os.getuid()):
        raise ValueError("explicit private synthetic directory required")
    if any(directory.iterdir()):
        raise ValueError("synthetic materialization requires an empty directory")
    payload = json.loads(canonical_json(payload))
    expected = {"contains_real_data", "snapshot_id", "data_version", "published_at",
                "coverage_start", "data_through", "orders", "refunds"}
    if set(payload) != expected or payload["contains_real_data"] is not False:
        raise ValueError("only explicit synthetic diagnosis snapshots are accepted")
    orders, refunds = payload["orders"], payload["refunds"]
    if not isinstance(orders, list) or not isinstance(refunds, list) or len(orders) + len(refunds) > MAX_ROWS:
        raise ValueError("synthetic diagnosis input exceeds its row bound")
    if any(set(row) != set(ORDER_FIELDS) for row in orders):
        raise ValueError("synthetic orders must declare the complete row shape")
    if any(set(row) != {"order_id", "refunded_at", "amount"} for row in refunds):
        raise ValueError("synthetic refunds must declare dated amounts")
    published_at = parse_query_datetime(payload["published_at"])
    coverage_start = date.fromisoformat(payload["coverage_start"])
    data_through = date.fromisoformat(payload["data_through"])
    if coverage_start > data_through:
        raise ValueError("synthetic coverage dates are reversed")
    if data_through > published_at.astimezone(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1):
        raise ValueError("synthetic data_through exceeds its T+1 publication bound")
    seen = set()
    order_days = {}
    for row in orders:
        key = (row["order_id"], row["sub_order_id"])
        if key in seen:
            raise ValueError("synthetic order line IDs must be unique")
        seen.add(key)
        day = datetime.fromisoformat(row["pay_time"]).date()
        if not coverage_start <= day <= data_through:
            raise ValueError("synthetic order exceeds declared coverage")
        order_days[row["order_id"]] = min(day, order_days.get(row["order_id"], day))
        amount = row["actual_amount"]
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            raise ValueError("synthetic order amounts must be finite non-negative numbers")
    for row in refunds:
        day = date.fromisoformat(row["refunded_at"])
        amount = row["amount"]
        if row["order_id"] not in order_days or not order_days[row["order_id"]] <= day <= data_through:
            raise ValueError("synthetic refund must bind an order and a covered date")
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            raise ValueError("synthetic refunds must be finite non-negative numbers")
    payload["published_at"] = canonical_rfc3339(published_at)
    path = directory.resolve() / "diagnosis.duckdb"
    connection = duckdb.connect(str(path), config={"threads": 1, "memory_limit": "64MB", "enable_external_access": "false"})
    try:
        connection.execute(DDL)
        if orders:
            connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   [[row[field] for field in ORDER_FIELDS] for row in orders])
        if refunds:
            connection.executemany("INSERT INTO refunds VALUES (?, ?, ?)",
                                   [[row["order_id"], row["refunded_at"], row["amount"]] for row in refunds])
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    path.chmod(0o600)
    return SyntheticDiagnosisSource(path, sha256(path.read_bytes()).hexdigest(), content_hash(payload),
                                    payload["snapshot_id"], payload["data_version"], published_at,
                                    coverage_start, data_through)


def demo_snapshot() -> dict:
    """Runtime example, deliberately independent from A9 acceptance data."""
    specs = [
        ("PY-1", "2025-08-05", "CH_RETAIL", "FULL", 100.0),
        ("PY-2", "2025-08-18", "CH_RETAIL", "FULL", 200.0),
        ("PY-S", "2025-08-20", "CH_SAMPLE", "SAMPLE", 5.0),
        ("CY-1", "2026-08-05", "CH_RETAIL", "FULL", 180.0),
        ("CY-2", "2026-08-18", "CH_RETAIL", "FULL", 240.0),
        ("CY-S", "2026-08-20", "CH_SAMPLE", "SAMPLE", 10.0),
    ]
    orders = [dict(zip(ORDER_FIELDS, (oid, "1", f"SYNTH-{oid}", day + " 12:00:00", channel,
                                    amount, None, False, False, "交易成功", product, "正装")))
              for oid, day, channel, product, amount in specs]
    return {"contains_real_data": False, "snapshot_id": "synthetic-diagnosis-202608-v1",
            "data_version": "synthetic-diagnosis-data/v1", "published_at": "2026-09-01T00:00:00+08:00",
            "coverage_start": "2025-01-01", "data_through": "2026-08-31", "orders": orders,
            "refunds": [{"order_id": "CY-2", "refunded_at": "2026-08-25", "amount": 20.0}]}
