#!/usr/bin/env python3
"""Create an atomic DuckDB snapshot for read-heavy consumers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = PROJECT_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "processed" / "snapshots"
RETENTION_DAYS = 30


def cleanup_old_snapshots(snapshot_dir: Path, retention_days: int = RETENTION_DAYS) -> int:
    """Delete snapshots older than retention_days."""

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    deleted = 0
    for path in snapshot_dir.glob("fuqing_crm_*.duckdb"):
        if path.name.endswith(".tmp"):
            continue
        if now - path.stat().st_mtime > retention_days * 86400:
            path.unlink()
            deleted += 1
    return deleted


def create_snapshot(
    source_db: Path = SOURCE_DB,
    snapshot_dir: Path = SNAPSHOT_DIR,
    timestamp: int | None = None,
) -> Path:
    """Copy source_db to a temp file and atomically rename it into place."""

    source_db = Path(source_db)
    snapshot_dir = Path(snapshot_dir)
    if not source_db.exists():
        raise FileNotFoundError(f"DuckDB source not found: {source_db}")

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or int(time.time())
    final_path = snapshot_dir / f"fuqing_crm_{ts}.duckdb"
    tmp_path = final_path.with_suffix(".duckdb.tmp")
    try:
        shutil.copy2(source_db, tmp_path)
        os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return final_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=SOURCE_DB)
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    parser.add_argument("--retention-days", type=int, default=RETENTION_DAYS)
    args = parser.parse_args()

    snapshot_path = create_snapshot(args.source_db, args.snapshot_dir)
    deleted = cleanup_old_snapshots(args.snapshot_dir, args.retention_days)
    print(f"Snapshot created: {snapshot_path}")
    print(f"Old snapshots cleaned: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
