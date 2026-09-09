"""SQLite persistence for pinned membership, candidate sets, and drafts."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path

from backend.contracts.analytics_query import canonical_json
from backend.contracts.competition_c0 import (
    CompetitionActionDraft,
    CompetitionCandidateSet,
    CompetitionCohortSpec,
)
from backend.services.analytics.competition_audience.errors import CompetitionAudienceError, forbidden, unavailable

APPLICATION_ID = 1397571928  # SMA8
STATE_SCHEMA_VERSION = 1
KIND = "competition-audience"

_DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE cohorts (
    cohort_id TEXT PRIMARY KEY,
    permission_scope TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    source_tense TEXT NOT NULL,
    source_result_ref TEXT,
    spec_json TEXT NOT NULL,
    pinned_json TEXT NOT NULL,
    membership_digest TEXT NOT NULL
);
CREATE TABLE candidates (
    candidate_set_id TEXT PRIMARY KEY,
    cohort_id TEXT NOT NULL,
    permission_scope TEXT NOT NULL,
    combine TEXT NOT NULL,
    source_result_ref TEXT NOT NULL,
    unique_count INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(cohort_id) REFERENCES cohorts(cohort_id)
);
CREATE TABLE drafts (
    draft_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version >= 1),
    candidate_set_id TEXT NOT NULL,
    owner TEXT NOT NULL,
    permission_scope TEXT NOT NULL,
    status TEXT NOT NULL,
    expired_reason TEXT,
    source_result_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(draft_id, version),
    FOREIGN KEY(candidate_set_id) REFERENCES candidates(candidate_set_id)
);
"""


def _private_directory(value) -> Path:
    original = Path(value)
    if original.is_symlink():
        raise ValueError("directory cannot be a symlink")
    path = original.resolve(strict=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("directory must be private and owned")
    return path


@contextmanager
def connect(path: Path, *, readonly: bool):
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
def transaction(path: Path):
    try:
        with connect(path, readonly=False) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
    except sqlite3.DatabaseError as error:
        raise unavailable() from error


def initialize(directory) -> Path:
    root = _private_directory(directory)
    path = root / "competition-audience.sqlite"
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(root / ".initialize.lock", flags, 0o600)
    try:
        lock_info = os.fstat(fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1 or lock_info.st_uid != os.getuid():
            raise ValueError("refusing unowned or linked audience initialization lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existed = path.exists() or path.is_symlink()
        if existed:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                raise ValueError("refusing unowned or linked audience state file")
            with connect(path, readonly=True) as con:
                if con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                    raise ValueError("refusing a foreign or incomplete audience database")
                if con.execute("PRAGMA user_version").fetchone()[0] != STATE_SCHEMA_VERSION:
                    raise ValueError("audience schema differs; retain old evidence and use fresh state")
            return path
        created = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(created)
        with connect(path, readonly=False) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("BEGIN IMMEDIATE;\n" + _DDL)
            try:
                con.execute(f"PRAGMA application_id={APPLICATION_ID}")
                con.execute(f"PRAGMA user_version={STATE_SCHEMA_VERSION}")
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("kind", KIND))
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("http_api", "NOT_CONNECTED"))
                con.execute("INSERT INTO metadata VALUES (?, ?)", ("auto_send", "false"))
                con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
    finally:
        os.close(fd)
    return path


def dump(value) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return canonical_json(payload)


class AudienceStore:
    def __init__(self, directory):
        self.path = initialize(directory)

    def get_cohort(self, cohort_id: str) -> sqlite3.Row | None:
        with connect(self.path, readonly=True) as con:
            return con.execute("SELECT * FROM cohorts WHERE cohort_id=?", (cohort_id,)).fetchone()

    def put_cohort(
        self, spec: CompetitionCohortSpec, pinned: tuple[str, ...], digest: str,
        *, source_result_ref: str | None,
    ) -> None:
        with transaction(self.path) as con:
            con.execute(
                """
                INSERT INTO cohorts(
                    cohort_id, permission_scope, rule_version, source_tense,
                    source_result_ref, spec_json, pinned_json, membership_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cohort_id) DO UPDATE SET
                    rule_version=excluded.rule_version,
                    source_tense=excluded.source_tense,
                    source_result_ref=excluded.source_result_ref,
                    spec_json=excluded.spec_json,
                    pinned_json=excluded.pinned_json,
                    membership_digest=excluded.membership_digest
                """,
                (
                    spec.cohort_id, spec.permission_scope, spec.enrollment_rule_version,
                    spec.source_tense.value, source_result_ref, dump(spec),
                    json.dumps(list(pinned), ensure_ascii=False), digest,
                ),
            )

    def put_candidates(self, candidates: CompetitionCandidateSet) -> None:
        with transaction(self.path) as con:
            existing = con.execute(
                "SELECT * FROM candidates WHERE candidate_set_id=?", (candidates.candidate_set_id,),
            ).fetchone()
            if existing is not None:
                if existing["permission_scope"] != candidates.permission_scope:
                    raise forbidden(param="candidate_set_id")
                # Candidate sets are snapshots. Reusing an ID must never change
                # the membership or evidence of an already linked draft.
                if (existing["cohort_id"] != candidates.cohort_id
                        or existing["payload_json"] != dump(candidates)):
                    raise CompetitionAudienceError(
                        409, "CONFLICT", "候选集 ID 已绑定其他内容，请重新预览生成新 ID。",
                        param="candidate_set_id",
                    )
                return
            con.execute(
                """
                INSERT INTO candidates(
                    candidate_set_id, cohort_id, permission_scope, combine,
                    source_result_ref, unique_count, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidates.candidate_set_id, candidates.cohort_id,
                    candidates.permission_scope, candidates.combine.value,
                    candidates.source_result_ref, candidates.unique_count, dump(candidates),
                ),
            )

    def get_candidates(self, candidate_set_id: str) -> sqlite3.Row | None:
        with connect(self.path, readonly=True) as con:
            return con.execute(
                "SELECT * FROM candidates WHERE candidate_set_id=?", (candidate_set_id,),
            ).fetchone()

    def latest_draft(self, draft_id: str) -> sqlite3.Row | None:
        with connect(self.path, readonly=True) as con:
            return con.execute(
                "SELECT * FROM drafts WHERE draft_id=? ORDER BY version DESC LIMIT 1",
                (draft_id,),
            ).fetchone()

    def current_draft(self, owner: str, scopes: frozenset[str]) -> sqlite3.Row | None:
        if not scopes:
            return None
        with connect(self.path, readonly=True) as con:
            placeholders = ",".join("?" for _ in scopes)
            return con.execute(
                f"SELECT * FROM drafts WHERE owner=? AND permission_scope IN ({placeholders}) "
                "ORDER BY rowid DESC LIMIT 1", (owner, *sorted(scopes)),
            ).fetchone()

    def insert_draft(self, draft: CompetitionActionDraft, permission_scope: str) -> None:
        with transaction(self.path) as con:
            con.execute(
                """
                INSERT INTO drafts(
                    draft_id, version, candidate_set_id, owner, permission_scope,
                    status, expired_reason, source_result_ref, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.draft_id, draft.version, draft.candidate_set_id, draft.owner_id,
                    permission_scope, draft.status.value, draft.expired_reason,
                    draft.source_result_ref, dump(draft),
                ),
            )

    def drafts_for_cohort(self, cohort_id: str) -> list[sqlite3.Row]:
        with connect(self.path, readonly=True) as con:
            return list(con.execute(
                """
                SELECT d.* FROM drafts d
                JOIN candidates c ON c.candidate_set_id = d.candidate_set_id
                WHERE c.cohort_id=?
                """,
                (cohort_id,),
            ).fetchall())
