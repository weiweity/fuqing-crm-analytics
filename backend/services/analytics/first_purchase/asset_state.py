"""Shared SQLite helpers for first-purchase saved-analysis and cockpit stores."""

from __future__ import annotations

import fcntl
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from backend.services.analytics.access import AnalyticsError

OPAQUE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
B0_SCHEMAS = frozenset({"analytics-run-b0/v1", "analytics-b0/v1"})
CHANNEL_SCHEMAS = frozenset({"analytics-channel-followup/v1", "analytics-run-channel-followup/v1"})


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def timestamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def missing(kind: str) -> AnalyticsError:
    if kind == "analysis":
        return AnalyticsError(404, "NOT_FOUND", "分析不存在或当前身份不可见。")
    return AnalyticsError(404, "NOT_FOUND", "驾驶舱不存在或当前身份不可见。")


def conflict(kind: str) -> AnalyticsError:
    if kind == "analysis":
        return AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前分析后核对。")
    return AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前驾驶舱后核对。")


def unprocessable(message: str) -> AnalyticsError:
    return AnalyticsError(422, "UNPROCESSABLE", message)


def invalid(message: str) -> AnalyticsError:
    return AnalyticsError(400, "INVALID_REQUEST", message)


def validate_key(key: str | None) -> str:
    if key is None:
        raise AnalyticsError(428, "IDEMPOTENCY_KEY_REQUIRED", "需要稳定的 Idempotency-Key。")
    if not key or len(key) > 200 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise AnalyticsError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key 格式无效。")
    return key


def validate_if_match(value: str | None) -> int:
    if value is None:
        raise AnalyticsError(428, "IF_MATCH_REQUIRED", "需要 If-Match 版本。")
    if not isinstance(value, str) or not value.isdigit() or value.startswith("0"):
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    version = int(value)
    if version < 1:
        raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
    return version


def opaque(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not OPAQUE_ID.fullmatch(value):
        raise invalid(f"{label} 不是合法标识。")
    return value


def sha256_hex(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise invalid(f"{label} 不是 SHA-256。")
    return value


def mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or isinstance(value, bool):
        raise invalid(f"{label} 必须是对象。")
    return value


def title_text(value: object) -> str:
    if not isinstance(value, str):
        raise invalid("标题必须是文字。")
    title = value.strip()
    if not title or len(title) > 120 or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise invalid("标题须为 1–120 个字符，不含控制字符。")
    return title


def looks_like_foreign_family(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    schema = payload.get("schema_version")
    if schema in B0_SCHEMAS:
        return "B0"
    if schema in CHANNEL_SCHEMAS or payload.get("query_id") == "channel_first_observed_followup":
        return "channel"
    if "repeat_rate" in payload or "repeat_customers" in payload:
        return "B0"
    if payload.get("customers") == 100 and payload.get("repeat_customers") == 25:
        return "B0"
    for nested in (payload.get("result"), payload.get("facts"), payload.get("filters"), payload.get("snapshot")):
        found = looks_like_foreign_family(nested)
        if found is not None:
            return found
    return None


def reject_foreign_family(payload: object) -> None:
    found = looks_like_foreign_family(payload)
    if found == "B0":
        raise unprocessable("B0 固定 fixture 不能保存为首购经营分析。")
    if found == "channel":
        raise unprocessable("渠道后续购买结果不能伪装为首购经营分析。")


def prior_row(con, principal, operation, target, key, digest, *, kind: str):
    row = con.execute(
        "SELECT * FROM idempotency WHERE actor=? AND operation=? AND target=? AND key=?",
        (principal.actor_id, operation, target, key),
    ).fetchone()
    if row is not None and row["request_hash"] != digest:
        raise conflict(kind)
    return row


def remember(con, principal, operation, target, key, digest, response, status, canonical_json: Callable):
    con.execute(
        "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
        (principal.actor_id, operation, target, key, digest, canonical_json(response), status),
    )


def initialize_sqlite(
    directory: Path,
    path: Path,
    *,
    application_id: int,
    schema_version: int,
    kind: str,
    ddl: str,
    unavailable: str,
) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"an existing private {kind} directory is required")
    resolved = directory.resolve(strict=True)
    mode = resolved.stat()
    if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
        raise ValueError(f"{kind} directory must be owned by the caller and mode 0700")
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(resolved / ".initialize.lock", flags, 0o600)
    try:
        lock_info = os.fstat(fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1 or lock_info.st_uid != os.getuid():
            raise ValueError(f"refusing unowned or linked {kind} initialization lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existed = path.exists() or path.is_symlink()
        if existed:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                raise ValueError(f"refusing unowned or linked {kind} state file")
            with connect(path, readonly=True, unavailable=unavailable) as con:
                if con.execute("PRAGMA application_id").fetchone()[0] != application_id:
                    raise ValueError(f"refusing a foreign or incomplete {kind} database")
                if con.execute("PRAGMA user_version").fetchone()[0] != schema_version:
                    raise ValueError(f"{kind} schema differs; retain old evidence and use fresh state")
                stored = con.execute("SELECT value FROM metadata WHERE key = ?", ("kind",)).fetchone()
                if stored is None or stored[0] != kind:
                    raise ValueError(f"refusing a foreign or incomplete {kind} database")
            return
        created = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(created)
        with connect(path, readonly=False, unavailable=unavailable) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("BEGIN IMMEDIATE;\n" + ddl)
            try:
                con.execute(f"PRAGMA application_id={application_id}")
                con.execute(f"PRAGMA user_version={schema_version}")
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("kind", kind))
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("finite_mock", "true"))
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("http_api", "NOT_CONNECTED"))
                con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
    finally:
        os.close(fd)


@contextmanager
def connect(path: Path, *, readonly: bool, unavailable: str):
    if path.is_symlink():
        raise ValueError("state file must not be a symlink")
    uri = path.as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    con = sqlite3.connect(uri, uri=True, timeout=0.1, autocommit=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        if not readonly:
            con.execute("PRAGMA synchronous=FULL")
        yield con
    finally:
        con.close()


@contextmanager
def transaction(path: Path, *, unavailable: str):
    try:
        with connect(path, readonly=False, unavailable=unavailable) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
    except sqlite3.DatabaseError as error:
        raise AnalyticsError(503, "STATE_UNAVAILABLE", unavailable, retryable=True) from error
