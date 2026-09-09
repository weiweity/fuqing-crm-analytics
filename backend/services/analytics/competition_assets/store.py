"""Isolated competition-board/v1 SQLite. Not analytics-cockpit/v1."""

from __future__ import annotations

import fcntl
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.cockpit import _now_ms
from backend.services.analytics.resource_profile import canonical_json

APPLICATION_ID = 1397572505  # SMc2; distinct from SMA1/SMC1/SMB0.
STATE_SCHEMA_VERSION = 1
KIND = "competition_board"
UNAVAILABLE = "比赛看板状态暂不可用，请使用原请求标识查询或重试。"

_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE endorsed_results (
    owner TEXT NOT NULL,
    result_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    analysis_id TEXT NOT NULL,
    analysis_version INTEGER NOT NULL,
    evidence_digest TEXT NOT NULL,
    completeness TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    PRIMARY KEY(owner, result_id)
);
CREATE TABLE boards (
    board_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version >= 1),
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    layout_mode TEXT NOT NULL,
    data_namespace TEXT NOT NULL,
    snapshot_compat TEXT NOT NULL,
    blocks_json TEXT NOT NULL,
    batch_id TEXT,
    operation_id TEXT,
    created_ms INTEGER NOT NULL,
    PRIMARY KEY(board_id, version)
);
CREATE INDEX boards_owner ON boards(owner, created_ms, board_id);
CREATE TABLE operations (
    actor TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    board_id TEXT,
    version INTEGER,
    status TEXT NOT NULL,
    error_code TEXT,
    retryable INTEGER NOT NULL,
    receipt_json TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    updated_ms INTEGER NOT NULL,
    PRIMARY KEY(actor, operation_id)
);
CREATE UNIQUE INDEX operations_idempotency ON operations(actor, idempotency_key);
CREATE TABLE batches (
    actor TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    layout_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    updated_ms INTEGER NOT NULL,
    PRIMARY KEY(actor, batch_id)
);
CREATE TABLE edit_targets (
    actor TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    board_id TEXT NOT NULL,
    block_id TEXT,
    base_version INTEGER NOT NULL,
    intent TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_version INTEGER,
    result_json TEXT,
    created_ms INTEGER NOT NULL,
    updated_ms INTEGER NOT NULL,
    PRIMARY KEY(actor, attempt_id)
);
CREATE TABLE idempotency (
    actor TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, key TEXT NOT NULL,
    request_hash TEXT NOT NULL, response_json TEXT NOT NULL, http_status INTEGER NOT NULL,
    PRIMARY KEY(actor, operation, target, key)
);
"""


class CompetitionAssetStore:
    finite_mock = True
    http_api = "NOT_CONNECTED"

    def __init__(self, state_dir: Path, *, clock: Callable[[], int] = _now_ms):
        original = Path(state_dir)
        if original.is_symlink() or not original.is_dir():
            raise ValueError("an existing private competition-board directory is required")
        self.directory = original.resolve(strict=True)
        mode = self.directory.stat()
        if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
            raise ValueError("competition-board directory must be owned by the caller and mode 0700")
        self.path = self.directory / "competition_assets.sqlite3"
        self.clock = clock
        self._initialize()

    def close(self) -> None:
        """Connections are per-call; callers drop the instance before reopen."""

    def _initialize(self) -> None:
        flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
        fd = os.open(self.directory / ".initialize.lock", flags, 0o600)
        try:
            lock_info = os.fstat(fd)
            if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1 or lock_info.st_uid != os.getuid():
                raise ValueError("refusing unowned or linked competition-board initialization lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            existed = self.path.exists() or self.path.is_symlink()
            if existed:
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    raise ValueError("refusing unowned or linked competition-board state file")
                with self._connection(readonly=True) as con:
                    if con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                        raise ValueError("refusing a foreign or incomplete competition-board database")
                    if con.execute("PRAGMA user_version").fetchone()[0] != STATE_SCHEMA_VERSION:
                        raise ValueError("competition-board schema differs; retain old evidence and use fresh state")
                    kind = con.execute("SELECT value FROM metadata WHERE key = ?", ("kind",)).fetchone()
                    if kind is None or kind[0] != KIND:
                        raise ValueError("refusing a foreign or incomplete competition-board database")
                return
            created = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(created)
            with self._connection() as con:
                con.execute("PRAGMA journal_mode=WAL")
                con.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
                try:
                    con.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    con.execute(f"PRAGMA user_version={STATE_SCHEMA_VERSION}")
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("kind", KIND))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("finite_mock", "true"))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("http_api", "NOT_CONNECTED"))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("data_namespace", "competition-board/v1"))
                    con.execute("COMMIT")
                except BaseException:
                    if con.in_transaction:
                        con.execute("ROLLBACK")
                    raise
        finally:
            os.close(fd)

    @contextmanager
    def _connection(self, *, readonly: bool = False):
        if self.path.is_symlink():
            raise ValueError("competition-board state file must not be a symlink")
        uri = self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw")
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
    def transaction(self):
        try:
            with self._connection() as con:
                con.execute("BEGIN IMMEDIATE")
                try:
                    yield con
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
        except sqlite3.IntegrityError as error:
            raise AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前看板后核对。") from error
        except sqlite3.DatabaseError as error:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", UNAVAILABLE, retryable=True) from error

    @contextmanager
    def readonly(self):
        with self._connection(readonly=True) as con:
            yield con

    @staticmethod
    def prior(con, principal, operation, target, key, digest):
        row = con.execute(
            "SELECT * FROM idempotency WHERE actor=? AND operation=? AND target=? AND key=?",
            (principal.actor_id, operation, target, key),
        ).fetchone()
        if row is not None and row["request_hash"] != digest:
            raise AnalyticsError(409, "CONFLICT", "同幂等键的请求载荷不一致，已拒绝。")
        return row

    @staticmethod
    def remember(con, principal, operation, target, key, digest, response, status):
        con.execute(
            "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
            (principal.actor_id, operation, target, key, digest, canonical_json(response), status),
        )

    @staticmethod
    def endorsement(con, principal: AnalyticsPrincipal, result_id: str):
        return con.execute(
            "SELECT * FROM endorsed_results WHERE owner=? AND result_id=?",
            (principal.actor_id, result_id),
        ).fetchone()

    def upsert_endorsement(self, con, principal: AnalyticsPrincipal, binding: dict[str, Any]) -> None:
        existing = self.endorsement(con, principal, binding["result_id"])
        if existing is not None:
            same = (
                existing["run_id"] == binding["run_id"]
                and existing["analysis_id"] == binding["analysis_id"]
                and existing["analysis_version"] == binding["version"]
                and existing["evidence_digest"] == binding["evidence_digest"]
            )
            if not same:
                raise AnalyticsError(409, "BINDING_CORRUPT", "同一 result_id 不能绑定不同 SNAPSHOT。")
            return
        con.execute(
            """INSERT INTO endorsed_results (
                owner, result_id, run_id, analysis_id, analysis_version, evidence_digest, completeness, created_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                principal.actor_id, binding["result_id"], binding["run_id"], binding["analysis_id"],
                binding["version"], binding["evidence_digest"], binding.get("completeness") or "COMPLETE",
                self.clock(),
            ),
        )

    @staticmethod
    def board_row(con, principal: AnalyticsPrincipal, board_id: str, version: int | None):
        if version is None:
            return con.execute(
                """SELECT * FROM boards WHERE board_id=? AND owner=?
                   ORDER BY version DESC LIMIT 1""",
                (board_id, principal.actor_id),
            ).fetchone()
        return con.execute(
            "SELECT * FROM boards WHERE board_id=? AND owner=? AND version=?",
            (board_id, principal.actor_id, version),
        ).fetchone()

    def insert_board(
        self, con, principal: AnalyticsPrincipal, *, board_id: str, version: int, title: str,
        layout_mode: str, blocks: list[dict[str, Any]], batch_id: str | None, operation_id: str | None,
    ):
        con.execute(
            """INSERT INTO boards (
                board_id, version, owner, title, layout_mode, data_namespace, snapshot_compat,
                blocks_json, batch_id, operation_id, created_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                board_id, version, principal.actor_id, title, layout_mode,
                "competition-board/v1", "ISOLATED_NEW", canonical_json(blocks),
                batch_id, operation_id, self.clock(),
            ),
        )
        return self.board_row(con, principal, board_id, version)

    @staticmethod
    def list_latest(con, principal: AnalyticsPrincipal):
        return con.execute(
            """SELECT b.* FROM boards b
               JOIN (
                   SELECT board_id, MAX(version) AS version
                   FROM boards WHERE owner=? GROUP BY board_id
               ) latest
                 ON b.board_id=latest.board_id AND b.version=latest.version
               WHERE b.owner=?
               ORDER BY b.created_ms DESC, b.board_id""",
            (principal.actor_id, principal.actor_id),
        ).fetchall()

    @staticmethod
    def get_operation(con, principal: AnalyticsPrincipal, operation_id: str):
        return con.execute(
            "SELECT * FROM operations WHERE actor=? AND operation_id=?",
            (principal.actor_id, operation_id),
        ).fetchone()

    @staticmethod
    def get_operation_by_key(con, principal: AnalyticsPrincipal, key: str):
        return con.execute(
            "SELECT * FROM operations WHERE actor=? AND idempotency_key=?",
            (principal.actor_id, key),
        ).fetchone()

    def upsert_operation(
        self, con, principal: AnalyticsPrincipal, *, operation_id: str, batch_id: str,
        idempotency_key: str, request_fingerprint: str, payload_hash: str, board_id: str | None,
        version: int | None, status: str, error_code: str | None, retryable: bool, receipt: dict[str, Any],
    ) -> None:
        now = self.clock()
        con.execute(
            """INSERT INTO operations (
                actor, operation_id, batch_id, idempotency_key, request_fingerprint, payload_hash,
                board_id, version, status, error_code, retryable, receipt_json, created_ms, updated_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(actor, operation_id) DO UPDATE SET
                batch_id=excluded.batch_id,
                request_fingerprint=excluded.request_fingerprint,
                payload_hash=excluded.payload_hash,
                board_id=excluded.board_id,
                version=excluded.version,
                status=excluded.status,
                error_code=excluded.error_code,
                retryable=excluded.retryable,
                receipt_json=excluded.receipt_json,
                updated_ms=excluded.updated_ms""",
            (
                principal.actor_id, operation_id, batch_id, idempotency_key, request_fingerprint,
                payload_hash, board_id, version, status, error_code, int(retryable),
                canonical_json(receipt), now, now,
            ),
        )

    def upsert_batch(
        self, con, principal: AnalyticsPrincipal, *, batch_id: str, layout_mode: str,
        status: str, receipt: dict[str, Any],
    ) -> None:
        now = self.clock()
        con.execute(
            """INSERT INTO batches (
                actor, batch_id, layout_mode, status, receipt_json, created_ms, updated_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(actor, batch_id) DO UPDATE SET
                status=excluded.status,
                receipt_json=excluded.receipt_json,
                updated_ms=excluded.updated_ms""",
            (principal.actor_id, batch_id, layout_mode, status, canonical_json(receipt), now, now),
        )

    @staticmethod
    def get_batch(con, principal: AnalyticsPrincipal, batch_id: str):
        return con.execute(
            "SELECT * FROM batches WHERE actor=? AND batch_id=?",
            (principal.actor_id, batch_id),
        ).fetchone()

    @staticmethod
    def get_attempt(con, principal: AnalyticsPrincipal, attempt_id: str):
        return con.execute(
            "SELECT * FROM edit_targets WHERE actor=? AND attempt_id=?",
            (principal.actor_id, attempt_id),
        ).fetchone()

    def upsert_attempt(
        self, con, principal: AnalyticsPrincipal, *, attempt_id: str, board_id: str, block_id: str | None,
        base_version: int, intent: str, idempotency_key: str, payload_hash: str, status: str,
        result_version: int | None = None, result: dict[str, Any] | None = None,
    ) -> None:
        now = self.clock()
        existing = self.get_attempt(con, principal, attempt_id)
        result_json = None if result is None else canonical_json(result)
        if existing is None:
            con.execute(
                """INSERT INTO edit_targets (
                    actor, attempt_id, board_id, block_id, base_version, intent, idempotency_key,
                    payload_hash, status, result_version, result_json, created_ms, updated_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    principal.actor_id, attempt_id, board_id, block_id, base_version, intent,
                    idempotency_key, payload_hash, status, result_version, result_json, now, now,
                ),
            )
            return
        con.execute(
            """UPDATE edit_targets SET status=?, result_version=?, result_json=?, updated_ms=?
               WHERE actor=? AND attempt_id=?""",
            (status, result_version, result_json, now, principal.actor_id, attempt_id),
        )
