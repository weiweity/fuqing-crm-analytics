"""Explicit tiny synthetic DuckDB creation/validation. Never a path fallback.

Creation is a separate CLI/test setup action. Runtime validation only reads
fixed filenames under an owned private directory and verifies sealed hashes.
"""

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from backend.semantic.analytics_b0 import CONTENT_SHA256, FIXTURE_ID, ORDERS

MAX_DATABASE_BYTES = 4 * 1024 * 1024


def private_directory(value):
    original = Path(value)
    if original.is_symlink():
        raise ValueError("B0 directory cannot be a symlink")
    path = original.resolve(strict=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("B0 directory must be private and owned")
    return path


def bounded_bytes(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size > limit):
            raise ValueError("B0 input must be a small owned private regular file")
        value = source.read(limit + 1)
        if len(value) > limit:
            raise ValueError("B0 input exceeds its bound")
        return value


@dataclass(frozen=True)
class SyntheticFixture:
    directory: str
    manifest_sha256: str

    def validate(self):
        root = private_directory(self.directory)
        raw = bounded_bytes(root / "manifest.json", 4096)
        if hashlib.sha256(raw).hexdigest() != self.manifest_sha256:
            raise ValueError("B0 manifest changed")
        manifest = json.loads(raw)
        database = root / "fixture.duckdb"
        expected_metadata = {
            "schema_version": "analytics-b0-data/v1", "fixture_id": FIXTURE_ID,
            "contains_real_data": False, "data_source": "SYNTHETIC_FIXTURE",
            "database": "fixture.duckdb", "content_sha256": CONTENT_SHA256, "rows": 125,
        }
        if (not isinstance(manifest, dict) or set(manifest) != {*expected_metadata, "database_sha256"}
                or {key: manifest[key] for key in expected_metadata} != expected_metadata
                or manifest.get("contains_real_data") is not False
                or type(manifest.get("rows")) is not int):
            raise ValueError("B0 synthetic manifest is invalid")
        if hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest() != manifest["database_sha256"]:
            raise ValueError("B0 synthetic data checksum is invalid")
        return database


def create_synthetic_fixture(directory):
    """Create only in an explicit, empty private fixture directory; no overwrite."""
    import duckdb

    root = private_directory(directory)
    if any(root.iterdir()):
        raise ValueError("fixture creation requires an empty directory")
    database = root / "fixture.duckdb"
    # This setup-only connection writes 125 invented rows, then closes before
    # any worker opens the file read-only. It is not the Web singleton path.
    con = duckdb.connect(str(database), config={"memory_limit": "32MiB", "threads": 2,
                                               "enable_external_access": False})
    try:
        con.execute("CREATE TABLE b0_orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER, channel VARCHAR, paid_on VARCHAR)")
        con.executemany("INSERT INTO b0_orders VALUES (?, ?, ?, ?)", ORDERS)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    database.chmod(0o600)
    manifest = {
        "schema_version": "analytics-b0-data/v1", "fixture_id": FIXTURE_ID,
        "contains_real_data": False, "data_source": "SYNTHETIC_FIXTURE",
        "database": "fixture.duckdb", "content_sha256": CONTENT_SHA256, "rows": 125,
        "database_sha256": hashlib.sha256(bounded_bytes(database, MAX_DATABASE_BYTES)).hexdigest(),
    }
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(root / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    result = SyntheticFixture(str(root), hashlib.sha256(raw).hexdigest())
    result.validate()
    return result


if __name__ == "__main__":
    from dataclasses import asdict

    if len(sys.argv) != 3 or sys.argv[1] != "--create" or not Path(sys.argv[2]).is_absolute():
        raise SystemExit("usage: python -m backend.analytics_fixture --create /absolute/private/empty/directory")
    print(json.dumps(asdict(create_synthetic_fixture(sys.argv[2]))))
