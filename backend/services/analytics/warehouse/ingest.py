"""Source listing, age filter, and the actual read set. No re-glob after filtering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend.services.analytics.warehouse.contract import WarehouseContractError
from backend.services.analytics.warehouse.generate import SOURCE_FILES


@dataclass
class IngestPlan:
    eligible: tuple[Path, ...]
    skipped: tuple[Path, ...]


@dataclass
class ReadResult:
    records: list[dict]
    bytes_read: int
    opened: list[str] = field(default_factory=list)


def list_named_sources(root: Path, names: tuple[str, ...] = SOURCE_FILES) -> list[Path]:
    files = []
    for name in names:
        path = root / name
        if path.is_symlink():
            raise WarehouseContractError("source files cannot be symlinks")
        if path.is_file():
            files.append(path)
    return files


def list_matching_sources(root: Path, pattern: str) -> list[Path]:
    files = []
    for path in sorted(root.glob(pattern)):
        if path.is_symlink():
            raise WarehouseContractError("source files cannot be symlinks")
        if path.is_file():
            files.append(path)
    return files


def filter_files_by_age(files: list[Path], *, now: datetime, max_age_days: int) -> IngestPlan:
    if max_age_days < 0:
        raise WarehouseContractError("max_age_days must be non-negative")
    now_ts = now.timestamp()
    cutoff = max_age_days * 86400
    keep = []
    skip = []
    for path in files:
        age = now_ts - path.stat().st_mtime
        if age > cutoff:
            skip.append(path)
        else:
            keep.append(path)
    return IngestPlan(eligible=tuple(keep), skipped=tuple(skip))


def plan_ingest(files: list[Path], *, now: datetime | None = None, max_age_days: int | None = None) -> IngestPlan:
    if max_age_days is None:
        return IngestPlan(eligible=tuple(files), skipped=())
    if now is None:
        raise WarehouseContractError("age filter requires an injected now")
    return filter_files_by_age(files, now=now, max_age_days=max_age_days)


def read_planned_jsonl(plan: IngestPlan, *, file_hashes: dict[str, str] | None = None) -> ReadResult:
    """Read exactly plan.eligible. Callers must not pass a re-enumerated directory listing."""
    records = []
    opened = []
    bytes_read = 0
    for path in plan.eligible:
        raw = path.read_bytes()
        if file_hashes is not None and hashlib.sha256(raw).hexdigest() != file_hashes.get(path.name):
            raise WarehouseContractError(f"source file hash mismatch: {path.name}")
        bytes_read += len(raw)
        opened.append(path.name)
        if not raw:
            continue
        for line in raw.splitlines():
            if not line:
                continue
            records.append(json.loads(line.decode("utf-8")))
    return ReadResult(records=records, bytes_read=bytes_read, opened=opened)


def assert_read_matches_plan(plan: IngestPlan, result: ReadResult) -> None:
    planned = [path.name for path in plan.eligible]
    if result.opened != planned:
        raise WarehouseContractError("file age filter is disconnected from the actual read set")
