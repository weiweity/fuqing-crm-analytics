"""Durable B0 run state, with no Agent loop and no CRM/DuckDB imports.

    accept: [run + key/hash + dispatch intent + original 202] -> COMMIT
    claim:  QUEUED -> RUNNING + one global active slot -> COMMIT -> transport
    cancel: QUEUED -> CANCELLED, or active -> CANCELLING (keep the slot)
    finish: matching attempt + trusted exit evidence -> terminal + release slot

No transport is called inside a SQLite transaction. A lost dispatch receipt or
an orphaned execution becomes UNKNOWN. Recovery never invents a new request ID.
"""

import fcntl
import json
import os
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from backend.contracts.analytics import (
    AnalyticsB0Result,
    AnalyticsCancelRequest,
    AnalyticsConversation,
    AnalyticsConversationRequest,
    AnalyticsEventPayload,
    AnalyticsRunAccepted,
    AnalyticsRunDiagnostics,
    AnalyticsRunEvent,
    AnalyticsRunRequest,
    AnalyticsRunSnapshot,
)
from .access import AnalyticsError, AnalyticsPrincipal, require
from .execution_lease import clear_owned_spill, released_lease
from .resource_profile import B0ResourceProfile, canonical_json, content_hash
from backend.semantic.analytics_b0 import CHANNEL, CONTENT_SHA256, DATA_AS_OF, FIXTURE_ID

APPLICATION_ID = 1397572144  # SMB0, not a general-purpose SQLite database.
STATE_SCHEMA_VERSION = 2  # Existing v1 evidence is retained, never auto-migrated.
TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "NEEDS_INPUT"})
SAFE_ERRORS = frozenset({
    "MODEL_FAILED", "TOOL_FAILED", "TIMEOUT", "EXECUTION_UNKNOWN",
    "RESOURCE_EXCEEDED", "PERMISSION_REVOKED", "RUNTIME_REJECTED",
})
CRITICAL_EVENT_RESERVE = 32 * 1024

_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
    created_ms INTEGER NOT NULL, runtime_session_id TEXT NOT NULL UNIQUE
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    parent_run_id TEXT REFERENCES runs(run_id),
    request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
    original_202 TEXT NOT NULL, profile_json TEXT NOT NULL, profile_hash TEXT NOT NULL,
    created_ms INTEGER NOT NULL, updated_ms INTEGER NOT NULL, deadline_ms INTEGER NOT NULL,
    version INTEGER NOT NULL CHECK(version >= 1),
    status TEXT NOT NULL CHECK(status IN
        ('QUEUED','RUNNING','NEEDS_INPUT','SUCCEEDED','FAILED','CANCELLING','CANCELLED','UNKNOWN')),
    phase TEXT NOT NULL CHECK(phase IN ('ACCEPTED','PLANNING','EXECUTING','FINALIZING')),
    attempt_id TEXT NOT NULL UNIQUE,
    active_slot INTEGER UNIQUE CHECK(active_slot IS NULL OR active_slot = 1),
    cancel_reason TEXT, error_code TEXT, result_json TEXT, evidence_digest TEXT,
    primary_result_ref TEXT, tool_steps_used INTEGER NOT NULL DEFAULT 0,
    last_sequence INTEGER NOT NULL DEFAULT 0, event_bytes INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX runs_owner_status ON runs(owner, status);
CREATE INDEX runs_queue ON runs(status, created_ms, run_id);
CREATE TABLE dispatch_intents (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id), session_id TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE, attempt_id TEXT NOT NULL,
    payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('PENDING','DISPATCHING','ACCEPTED','UNKNOWN','EXITED')),
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE idempotency (
    actor TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, key TEXT NOT NULL,
    request_hash TEXT NOT NULL, response_json TEXT NOT NULL, http_status INTEGER NOT NULL,
    PRIMARY KEY(actor, operation, target, key)
);
CREATE TABLE steps (
    step_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
    attempt_id TEXT NOT NULL, call_id TEXT NOT NULL, request_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('STARTED','SUCCEEDED')),
    result_json TEXT, deadline_ms INTEGER NOT NULL, UNIQUE(run_id, attempt_id, call_id)
);
CREATE TABLE worker_executions (
    execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
    attempt_id TEXT NOT NULL, step_id TEXT NOT NULL UNIQUE REFERENCES steps(step_id),
    lease_dev INTEGER NOT NULL, lease_ino INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('RESERVED','RUNNING','EXITED')),
    active_slot INTEGER UNIQUE CHECK(active_slot IS NULL OR active_slot=1),
    deadline_ms INTEGER NOT NULL, pid INTEGER, exit_code INTEGER,
    error_code TEXT, metrics_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE events (
    run_id TEXT NOT NULL REFERENCES runs(run_id), sequence INTEGER NOT NULL,
    created_ms INTEGER NOT NULL, event_json TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
);
"""


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _timestamp(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _missing() -> AnalyticsError:
    return AnalyticsError(404, "NOT_FOUND", "任务不存在或当前身份不可见。")


def _conflict() -> AnalyticsError:
    return AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前任务后核对。")


def validate_key(key: str | None) -> str:
    if key is None:
        raise AnalyticsError(428, "IDEMPOTENCY_KEY_REQUIRED", "需要稳定的 Idempotency-Key。")
    if not key or len(key) > 200 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise AnalyticsError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key 格式无效。")
    return key


@dataclass(frozen=True)
class DispatchIntent:
    run_id: str
    attempt_id: str
    session_id: str
    request_id: str
    payload: dict
    payload_hash: str
    deadline_ms: int


@dataclass(frozen=True)
class StepReservation:
    step_id: str
    disposition: str  # EXECUTE / REUSE_RESULT / PENDING; PENDING must not execute again.
    deadline_ms: int


@dataclass(frozen=True)
class ExecutionObservation:
    """Trusted adapter evidence, never deserialized from a model or public API.

    The adapter must establish actual exit independently (owned process handle
    or a verified runtime protocol). An accepted/cancel acknowledgement alone
    MUST NOT set execution_exited. All four correlation fields are mandatory.
    """

    run_id: str
    attempt_id: str
    session_id: str
    request_id: str
    execution_exited: bool
    outcome: str  # RUNNING / UNKNOWN / SUCCEEDED / FAILED / CANCELLED / NEEDS_INPUT
    primary_result_ref: str | None = None
    error_code: str | None = None


class RunStore:
    def __init__(self, state_dir: Path, profile: B0ResourceProfile,
                 *, clock: Callable[[], int] = _now_ms,
                 fault_hook: Callable[[str], None] | None = None):
        # No default path, dotenv, database fallback, migration or deletion.
        original = Path(state_dir)
        if original.is_symlink() or not original.is_dir():
            raise ValueError("an existing private B0 state directory is required")
        self.directory = original.resolve(strict=True)
        mode = self.directory.stat()
        if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
            raise ValueError("B0 state directory must be owned by the caller and mode 0700")
        self.path = self.directory / "runs.sqlite3"
        self.profile = profile
        self.clock = clock
        self.fault_hook = fault_hook
        self._initialize()

    def _hook(self, point: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(point)

    def _initialize(self) -> None:
        # Serialize initialization only. O_NOFOLLOW prevents replacing another
        # file via a symlink; never adopt an existing foreign SQLite database.
        flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
        fd = os.open(self.directory / ".initialize.lock", flags, 0o600)
        try:
            lock_info = os.fstat(fd)
            if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1 or lock_info.st_uid != os.getuid():
                raise ValueError("refusing unowned or linked B0 initialization lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            existed = self.path.exists() or self.path.is_symlink()
            if existed:
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    raise ValueError("refusing unowned or linked B0 state file")
                with self._connection(readonly=True) as con:
                    if con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                        raise ValueError("refusing a foreign or incomplete state database")
                    if con.execute("PRAGMA user_version").fetchone()[0] != STATE_SCHEMA_VERSION:
                        raise ValueError("B0 state schema differs; retain old evidence and use fresh state, not an implicit migration")
                    row = con.execute("SELECT value FROM metadata WHERE key = ?", ("profile_hash",)).fetchone()
                    if row is None or row[0] != self.profile.digest:
                        raise ValueError("persisted B0 profile differs; implicit migration is forbidden")
                return
            created = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(created)
            with self._connection() as con:
                con.execute("PRAGMA journal_mode=WAL")
                con.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
                try:
                    con.execute("PRAGMA application_id=1397572144")
                    con.execute("PRAGMA user_version=2")
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("profile_hash", self.profile.digest))
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("profile_json", canonical_json(self.profile.model_dump())))
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
            raise ValueError("B0 state file must not be a symlink")
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
    def _transaction(self):
        try:
            with self._connection() as con:
                con.execute("BEGIN IMMEDIATE")
                try:
                    yield con
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
        except sqlite3.DatabaseError as error:
            # Do not expose SQL, paths or driver diagnostics to the caller.
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "任务状态暂不可用，请使用原请求标识查询或重试。",
                                 retryable=True) from error

    def storage_bytes(self) -> int:
        return sum(p.stat().st_size for p in (self.path, Path(str(self.path) + "-wal"),
                                             Path(str(self.path) + "-shm")) if p.exists())

    def _admit_storage(self, con, *, new_run: bool) -> None:
        outstanding = con.execute("SELECT count(*) FROM runs WHERE status NOT IN ('SUCCEEDED','FAILED','CANCELLED','NEEDS_INPUT')").fetchone()[0]
        reservation = (outstanding + int(new_run)) * self.profile.run_reservation_bytes + 65536
        if self.storage_bytes() + reservation > self.profile.state_high_water_bytes:
            raise AnalyticsError(503, "STATE_HIGH_WATER", "B0 状态空间已达准入上限；现有证据保留，暂停新任务。")

    @staticmethod
    def _prior(con, principal, operation, target, key, digest):
        row = con.execute(
            "SELECT * FROM idempotency WHERE actor=? AND operation=? AND target=? AND key=?",
            (principal.actor_id, operation, target, key),
        ).fetchone()
        if row is not None and row["request_hash"] != digest:
            raise _conflict()
        return row

    @staticmethod
    def _remember(con, principal, operation, target, key, digest, response, status):
        con.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (principal.actor_id, operation, target, key, digest, canonical_json(response), status))

    @staticmethod
    def _conversation(con, principal, conversation_id):
        row = con.execute("SELECT * FROM conversations WHERE conversation_id=? AND owner=?",
                          (conversation_id, principal.actor_id)).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _run(con, principal, run_id):
        row = con.execute("SELECT * FROM runs WHERE run_id=? AND owner=?", (run_id, principal.actor_id)).fetchone()
        if row is None:
            raise _missing()
        return row

    def create_conversation(self, principal: AnalyticsPrincipal, key: str,
                            request: AnalyticsConversationRequest, *, runtime_session_id: str | None = None) -> AnalyticsConversation:
        require(principal, "run:create")
        validate_key(key)
        digest = content_hash({**request.model_dump(mode="json"), **({"native_session": runtime_session_id} if runtime_session_id else {})})
        with self._transaction() as con:
            prior = self._prior(con, principal, "conversation:create", "", key, digest)
            if prior:
                return AnalyticsConversation.model_validate_json(prior["response_json"])
            counts = con.execute("SELECT count(*), count(CASE WHEN owner=? THEN 1 END) FROM conversations",
                                 (principal.actor_id,)).fetchone()
            if counts[0] >= self.profile.max_retained_conversations or counts[1] >= self.profile.max_retained_conversations_per_actor:
                raise AnalyticsError(429, "RETENTION_LIMIT", "B0 会话保留额度已满；不会删除已有记录。")
            self._admit_storage(con, new_run=False)
            now = self.clock()
            response = AnalyticsConversation(conversation_id=_id("conv"), title=request.title, created_at=_timestamp(now))
            con.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                        (response.conversation_id, principal.actor_id, request.title, now, runtime_session_id or _id("session")))
            self._remember(con, principal, "conversation:create", "", key, digest, response.model_dump(mode="json"), 201)
        return response

    def get_conversation(self, principal: AnalyticsPrincipal, conversation_id: str) -> AnalyticsConversation:
        require(principal, "run:read")
        with self._connection(readonly=True) as con:
            row = self._conversation(con, principal, conversation_id)
            ids = con.execute("SELECT run_id FROM runs WHERE conversation_id=? AND owner=? ORDER BY rowid",
                              (conversation_id, principal.actor_id)).fetchall()
            return AnalyticsConversation(conversation_id=conversation_id, title=row["title"],
                                         created_at=_timestamp(row["created_ms"]), run_ids=[item[0] for item in ids])

    def accept(self, principal: AnalyticsPrincipal, conversation_id: str, key: str,
               request: AnalyticsRunRequest, *, allow_new: bool = True, native_request: dict | None = None,
               method_package_digest: str | None = None) -> AnalyticsRunAccepted:
        require(principal, "run:create")
        validate_key(key)
        if method_package_digest is not None and (len(method_package_digest) != 64
                or any(c not in "0123456789abcdef" for c in method_package_digest)):
            raise ValueError("explicit fixed method package digest required")
        payload = request.model_dump(mode="json")
        # Native metadata is supplied only by the validated server-side adapter,
        # never by the public RunRequest. Preserve its original request ID for
        # DSH's optimistic echo and journal deduplication.
        digest = content_hash(payload if native_request is None else {"request": payload, "native": native_request})
        with self._transaction() as con:
            conversation = self._conversation(con, principal, conversation_id)
            prior = self._prior(con, principal, "run:create", conversation_id, key, digest)
            if prior:
                return AnalyticsRunAccepted.model_validate_json(prior["response_json"])
            if not allow_new:
                raise AnalyticsError(503, "RUNTIME_NOT_CONNECTED", "运行时尚未接线，不接受新的执行任务。")
            if native_request is not None:
                if (native_request.get("sessionId") != conversation["runtime_session_id"]
                        or native_request.get("requestId") != key
                        or con.execute("SELECT 1 FROM dispatch_intents WHERE request_id=?", (key,)).fetchone()):
                    raise _conflict()
            if request.parent_run_id is not None:
                parent = self._run(con, principal, request.parent_run_id)
                if parent["conversation_id"] != conversation_id:
                    raise _missing()
            counts = con.execute("SELECT count(*), count(CASE WHEN owner=? THEN 1 END) FROM runs",
                                 (principal.actor_id,)).fetchone()
            if counts[0] >= self.profile.max_retained_runs or counts[1] >= self.profile.max_retained_runs_per_actor:
                raise AnalyticsError(429, "RETENTION_LIMIT", "B0 任务保留额度已满；已有任务与幂等记录保持可查。")
            queued = con.execute("SELECT count(*) FROM runs WHERE status='QUEUED'").fetchone()[0]
            inflight = con.execute("SELECT count(*) FROM runs WHERE owner=? AND status NOT IN ('SUCCEEDED','FAILED','CANCELLED','NEEDS_INPUT')",
                                   (principal.actor_id,)).fetchone()[0]
            if queued >= self.profile.max_queued or inflight >= self.profile.max_actor_inflight:
                raise AnalyticsError(429, "RUN_QUOTA", "任务队列或当前调用者在途额度已满。", retryable=True)
            self._admit_storage(con, new_run=True)
            now, run_id, attempt_id = self.clock(), _id("run"), _id("attempt")
            response = AnalyticsRunAccepted(run_id=run_id, location=f"/api/v1/analytics/runs/{run_id}")
            con.execute("""INSERT INTO runs (
                run_id, owner, conversation_id, parent_run_id, request_json, request_hash,
                original_202, profile_json, profile_hash, created_ms, updated_ms, deadline_ms,
                version, status, phase, attempt_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'QUEUED', 'ACCEPTED', ?)""",
                        (run_id, principal.actor_id, conversation_id, request.parent_run_id,
                         canonical_json(payload), digest, canonical_json(response.model_dump(mode="json")),
                         canonical_json(self.profile.model_dump()), self.profile.digest,
                         now, now, now + self.profile.run_timeout_ms, attempt_id))
            dispatch_payload = {"question": request.question, "parent_run_id": request.parent_run_id}
            if native_request is not None:
                dispatch_payload["native_request"] = native_request
            con.execute("INSERT INTO dispatch_intents VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0)",
                        (run_id, conversation["runtime_session_id"], key if native_request is not None else _id("dispatch"), attempt_id,
                         canonical_json(dispatch_payload), content_hash(dispatch_payload)))
            self._remember(con, principal, "run:create", conversation_id, key, digest, response.model_dump(mode="json"), 202)
            if method_package_digest is not None:
                self._remember(con, principal, "runtime.binding", run_id, "method", method_package_digest, {}, 200)
            self._emit(con, con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone(), "run.updated")
            self._hook("accept:before_commit")
        self._hook("accept:after_commit")
        return response

    def runtime_work(self, *, session_id: str | None = None, request_id: str | None = None) -> list[dict]:
        """Internal read model; never expose owners or dispatch payloads publicly.

        Exact native correlation can find an old terminal run so late tool calls
        are rejected by that run's fence, not charged to a newer active run.
        """
        with self._connection(readonly=True) as con:
            predicate, values = ("r.active_slot=1", ()) if session_id is None else (
                "d.session_id=? AND d.request_id=?", (session_id, request_id))
            rows = con.execute("""SELECT r.*, d.session_id, d.request_id, d.payload_json, d.payload_hash
                FROM runs r JOIN dispatch_intents d USING(run_id) WHERE """ + predicate, values).fetchall()
            return [{"intent": DispatchIntent(row["run_id"], row["attempt_id"], row["session_id"], row["request_id"],
                                              json.loads(row["payload_json"]), row["payload_hash"], row["deadline_ms"]),
                     "owner": row["owner"], "status": row["status"], "cancel_requested": row["cancel_reason"] is not None,
                     "pending_steps": con.execute("SELECT count(*) FROM steps WHERE run_id=? AND state!='SUCCEEDED'", (row["run_id"],)).fetchone()[0],
                     "steps": {s["call_id"]: s["step_id"] for s in con.execute(
                         "SELECT call_id, step_id FROM steps WHERE run_id=? AND state='SUCCEEDED'", (row["run_id"],))}}
                    for row in rows]

    def _snapshot(self, con, row) -> AnalyticsRunSnapshot:
        intent = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
        refs = con.execute("SELECT step_id FROM steps WHERE run_id=? AND state='SUCCEEDED' ORDER BY step_id",
                           (row["run_id"],)).fetchall()
        return AnalyticsRunSnapshot(
            run_id=row["run_id"], version=row["version"], source_ref=row["conversation_id"],
            conversation_id=row["conversation_id"], parent_run_id=row["parent_run_id"],
            status=row["status"], phase=row["phase"], created_at=_timestamp(row["created_ms"]),
            updated_at=_timestamp(row["updated_ms"]), deadline=_timestamp(row["deadline_ms"]),
            result=AnalyticsB0Result.model_validate_json(row["result_json"]) if row["result_json"] else None,
            evidence_digest=row["evidence_digest"], primary_result_ref=row["primary_result_ref"],
            evidence_refs=[r[0] for r in refs], last_sequence=row["last_sequence"],
            diagnostics=AnalyticsRunDiagnostics(
                attempt_id=row["attempt_id"], runtime_status=intent["state"], execution_active=row["active_slot"] is not None,
                tool_steps_used=row["tool_steps_used"], dispatch_attempts=intent["attempts"],
                profile_version=json.loads(row["profile_json"])["version"], profile_hash=row["profile_hash"],
                error_code=row["error_code"],
            ),
        )

    def get(self, principal: AnalyticsPrincipal, run_id: str) -> AnalyticsRunSnapshot:
        require(principal, "run:read")
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            return self._snapshot(con, self._run(con, principal, run_id))

    def rebuild_context(self, principal, run_id, attempt_id, *, package_digest, unit_id, resource=None):
        """Re-read authoritative state, never a model summary or a cached grant.

        Existing idempotency storage binds the method version and charges each
        model step/method read once. No new state DB or implicit migration.
        Method reads share the query tool budget but are never numeric evidence.
        """
        require(principal, "run:read")
        require(principal, "run:create")
        validate_key(unit_id)
        if (not isinstance(package_digest, str) or len(package_digest) != 64
                or any(c not in "0123456789abcdef" for c in package_digest)):
            raise ValueError("explicit fixed method package digest required")
        if resource not in {None, "SKILL.md", "references/evidence-policy.md", "assets/result-example.json"}:
            raise AnalyticsError(422, "UNSUPPORTED_RESOURCE", "只能读取登记的 B0 方法资源。")
        operation = "runtime.model-step" if resource is None else "runtime.method-read"
        digest = content_hash({"resource": resource, "package_digest": package_digest})
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            if (row["attempt_id"] != attempt_id or row["status"] != "RUNNING"
                    or row["active_slot"] is None or row["cancel_reason"] or row["deadline_ms"] <= self.clock()):
                raise _conflict()
            binding = self._prior(con, principal, "runtime.binding", run_id, "method", package_digest)
            if binding is None:
                raise AnalyticsError(409, "METHOD_NOT_BOUND", "任务受理时未绑定方法版本，不能事后补用当前版本。")
            prior = self._prior(con, principal, operation, run_id, unit_id, digest)
            if resource is not None and con.execute(
                    "SELECT 1 FROM steps WHERE run_id=? AND attempt_id=? AND call_id=?", (run_id, attempt_id, unit_id)).fetchone():
                raise _conflict()
            model_used = con.execute("SELECT count(*) FROM idempotency WHERE operation='runtime.model-step' AND target=?", (run_id,)).fetchone()[0]
            if prior is None:
                if ((resource is None and model_used >= self.profile.max_tool_steps)
                        or (resource is not None and row["tool_steps_used"] >= self.profile.max_tool_steps)):
                    raise AnalyticsError(409, "RESOURCE_EXCEEDED", "任务原总预算已用尽；恢复或压缩不重置预算。")
                self._remember(con, principal, operation, run_id, unit_id, digest, {}, 200)
                model_used += int(resource is None)
                row = self._update(con, row, tool_steps_used=row["tool_steps_used"] + int(resource is not None))
                self._emit(con, row, "run.updated")
            completed = []
            for step in con.execute("SELECT step_id, result_json FROM steps WHERE run_id=? AND state='SUCCEEDED' ORDER BY step_id", (run_id,)):
                result = AnalyticsB0Result.model_validate_json(step["result_json"]).model_dump(mode="json")
                completed.append({"step_id": step["step_id"], "state": "SUCCEEDED", "result": result, "evidence_digest": content_hash(result)})
            payload = {
                "schema_version": "analytics-b0-runtime-context/v1", "run_id": run_id, "attempt_id": attempt_id,
                "run_version": row["version"], "run_status": row["status"], "phase": row["phase"],
                "question": json.loads(row["request_json"])["question"], "parent_run_id": row["parent_run_id"],
                "conditions": {"mode": "FIXED_FIXTURE_NOT_PARSED_FROM_QUESTION", "query": "channel_repeat_rate",
                               "channel": CHANNEL, "data_as_of": DATA_AS_OF},
                "versions": {"contract": "analytics-run-b0/v1", "method_package_digest": package_digest,
                             "query": "analytics-b0-query/v1", "metric": "analytics-b0-repeat/v1",
                             "fixture_id": FIXTURE_ID, "data_digest": CONTENT_SHA256},
                "completed_steps": completed, "primary_result_ref": row["primary_result_ref"],
                "pending_clarifications": ["仅支持固定合成 fixture；自然语言条件未解析，不代表筛选已生效。"],
                "remaining_budget": {"tool_steps": self.profile.max_tool_steps - row["tool_steps_used"],
                                     "model_steps": self.profile.max_tool_steps - model_used,
                                     "deadline": _timestamp(row["deadline_ms"]).isoformat(),
                                     "remaining_ms": max(0, row["deadline_ms"] - self.clock())},
                "approval_state": "NOT_AVAILABLE_IN_B0", "memory_authority": "NONE",
                "contains_real_data": False,
            }
            if len(canonical_json(payload).encode()) > 65536:
                raise AnalyticsError(409, "RESOURCE_EXCEEDED", "上下文超出有界摘要限制。")
            return payload

    def _update(self, con, row, *, status=None, phase=None, active_slot="unchanged",
                cancel_reason=None, error_code=None, result=None, primary_result_ref=None,
                tool_steps_used=None):
        result_json = canonical_json(result.model_dump(mode="json")) if result is not None else row["result_json"]
        digest = content_hash(result.model_dump(mode="json")) if result is not None else row["evidence_digest"]
        cursor = con.execute("""UPDATE runs SET status=?, phase=?, active_slot=?,
            cancel_reason=?, error_code=?, result_json=?, evidence_digest=?, primary_result_ref=?,
            tool_steps_used=?, version=version+1, updated_ms=?
            WHERE run_id=? AND version=? AND attempt_id=?""", (
            status or row["status"], phase or row["phase"],
            row["active_slot"] if active_slot == "unchanged" else active_slot,
            cancel_reason or row["cancel_reason"], error_code,
            result_json, digest, primary_result_ref or row["primary_result_ref"],
            row["tool_steps_used"] if tool_steps_used is None else tool_steps_used,
            self.clock(), row["run_id"], row["version"], row["attempt_id"],
        ))
        if cursor.rowcount != 1:
            raise _conflict()
        return con.execute("SELECT * FROM runs WHERE run_id=?", (row["run_id"],)).fetchone()

    def _emit(self, con, row, event_type, *, step_id=None):
        seq = row["last_sequence"] + 1
        event = AnalyticsRunEvent(
            event_id=f"{row['run_id']}:{seq}", run_id=row["run_id"], sequence=seq, type=event_type,
            occurred_at=_timestamp(self.clock()), payload=AnalyticsEventPayload(
                status=row["status"], phase=row["phase"], version=row["version"], step_id=step_id,
            ),
        )
        encoded = canonical_json(event.model_dump(mode="json"))
        size = len(encoded.encode())
        critical = event_type.startswith("run.")
        available = self.profile.max_run_event_bytes - (0 if critical else CRITICAL_EVENT_RESERVE)
        if size > self.profile.max_event_bytes or row["event_bytes"] + size > available:
            raise AnalyticsError(503, "EVENT_CAPACITY", "任务事件空间不足，等待受控恢复；不丢弃已有证据。")
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (row["run_id"], seq, self.clock(), encoded))
        con.execute("UPDATE runs SET last_sequence=?, event_bytes=event_bytes+? WHERE run_id=?",
                    (seq, size, row["run_id"]))

    def cancel(self, principal: AnalyticsPrincipal, run_id: str, key: str, version: int,
               request: AnalyticsCancelRequest) -> AnalyticsRunSnapshot:
        require(principal, "run:cancel")
        validate_key(key)
        digest = content_hash({"request": request.model_dump(), "if_match": version})
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            prior = self._prior(con, principal, "run:cancel", run_id, key, digest)
            if prior:
                return AnalyticsRunSnapshot.model_validate_json(prior["response_json"])
            if version != row["version"]:
                raise _conflict()
            count = con.execute("SELECT count(*) FROM idempotency WHERE operation='run:cancel' AND target=?", (run_id,)).fetchone()[0]
            if count >= self.profile.max_cancel_keys_per_run:
                raise AnalyticsError(429, "CANCEL_KEY_LIMIT", "取消请求标识额度已满，请使用原 key 查询或重放。")
            if row["status"] not in TERMINAL and row["cancel_reason"] is None:
                queued = row["status"] == "QUEUED"
                row = self._update(con, row, status="CANCELLED" if queued else "CANCELLING", cancel_reason="USER_REQUEST")
                if queued:
                    con.execute("UPDATE dispatch_intents SET state='EXITED' WHERE run_id=?", (run_id,))
                self._emit(con, row, "run.cancelled" if queued else "run.updated")
            response = self._snapshot(con, con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
            self._remember(con, principal, "run:cancel", run_id, key, digest, response.model_dump(mode="json"), 200)
            self._hook("cancel:before_commit")
        self._hook("cancel:after_commit")
        return response

    def claim_next(self, resolve_actor: Callable[[str], AnalyticsPrincipal | None]) -> DispatchIntent | None:
        """Claim FIFO work once; the caller dispatches only AFTER this returns.

        Authorization resolution happens outside the writer lock. UNKNOWN and
        CANCELLING continue to own the unique active slot, including on restart.
        """
        for _ in range(self.profile.max_queued):
            with self._connection(readonly=True) as con:
                candidate = con.execute("SELECT * FROM runs WHERE status='QUEUED' ORDER BY rowid LIMIT 1").fetchone()
            if candidate is None:
                return None
            principal = resolve_actor(candidate["owner"])
            allowed = principal is not None and principal.actor_id == candidate["owner"]
            if allowed:
                try:
                    require(principal, "run:create")
                except AnalyticsError:
                    allowed = False
            with self._transaction() as con:
                row = con.execute("SELECT * FROM runs WHERE run_id=? AND status='QUEUED'", (candidate["run_id"],)).fetchone()
                if row is None:
                    continue
                if not allowed or row["deadline_ms"] <= self.clock():
                    row = self._update(con, row, status="FAILED", error_code="PERMISSION_REVOKED" if not allowed else "TIMEOUT")
                    con.execute("UPDATE dispatch_intents SET state='EXITED' WHERE run_id=?", (row["run_id"],))
                    self._emit(con, row, "run.failed")
                    continue
                if con.execute("SELECT 1 FROM runs WHERE active_slot=1").fetchone():
                    return None
                row = self._update(con, row, status="RUNNING", phase="PLANNING", active_slot=1)
                con.execute("UPDATE dispatch_intents SET state='DISPATCHING', attempts=attempts+1 WHERE run_id=? AND state='PENDING'",
                            (row["run_id"],))
                dispatch = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
                self._emit(con, row, "run.started")
                intent = DispatchIntent(row["run_id"], row["attempt_id"], dispatch["session_id"],
                                        dispatch["request_id"], json.loads(dispatch["payload_json"]),
                                        dispatch["payload_hash"], row["deadline_ms"])
                self._hook("claim:before_commit")
            self._hook("claim:after_commit")
            return intent
        return None

    @staticmethod
    def _active_attempt(con, run_id: str, attempt_id: str):
        row = con.execute("SELECT * FROM runs WHERE run_id=? AND attempt_id=?", (run_id, attempt_id)).fetchone()
        if row is None:
            raise _conflict()
        return row

    def reserve_step(self, principal: AnalyticsPrincipal, run_id: str, attempt_id: str,
                     call_id: str, *, query: str = "channel_repeat_rate") -> StepReservation:
        require(principal, "run:create")
        validate_key(call_id)
        if query != "channel_repeat_rate":
            raise AnalyticsError(422, "UNSUPPORTED_QUERY", "B0 仅允许已登记的固定合成 fixture。")
        digest = content_hash({"query": query})
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            if con.execute("SELECT 1 FROM idempotency WHERE operation='runtime.method-read' AND target=? AND key=?", (run_id, call_id)).fetchone():
                raise _conflict()
            if row["attempt_id"] != attempt_id:
                raise _conflict()
            if row["status"] != "RUNNING" or row["cancel_reason"] or row["deadline_ms"] <= self.clock():
                raise _conflict()
            prior = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND call_id=?", (run_id, attempt_id, call_id)).fetchone()
            if prior:
                if prior["request_hash"] != digest:
                    raise _conflict()
                return StepReservation(prior["step_id"], "REUSE_RESULT" if prior["state"] == "SUCCEEDED" else "PENDING", prior["deadline_ms"])
            if row["tool_steps_used"] >= self.profile.max_tool_steps:
                raise AnalyticsError(429, "TOOL_STEP_LIMIT", "本任务的工具步数预算已用完。")
            step_id = _id("step")
            step_deadline = min(row["deadline_ms"], self.clock() + self.profile.query_timeout_ms)
            con.execute("INSERT INTO steps VALUES (?, ?, ?, ?, ?, 'STARTED', NULL, ?)", (step_id, run_id, attempt_id, call_id, digest, step_deadline))
            row = self._update(con, row, phase="EXECUTING", tool_steps_used=row["tool_steps_used"] + 1)
            self._emit(con, row, "tool.started", step_id=step_id)
            return StepReservation(step_id, "EXECUTE", step_deadline)

    def complete_step(self, principal: AnalyticsPrincipal, run_id: str, attempt_id: str,
                      step_id: str, result: AnalyticsB0Result) -> None:
        require(principal, "run:create")
        # Revalidate even if an internal caller used model_construct().
        result = AnalyticsB0Result.model_validate(result.model_dump(mode="json"))
        encoded = canonical_json(result.model_dump(mode="json"))
        if len(encoded.encode()) > self.profile.max_result_bytes:
            raise AnalyticsError(422, "RESULT_TOO_LARGE", "结果超过本次 B0 的大小上限。")
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            if row["attempt_id"] != attempt_id or row["status"] != "RUNNING" or row["cancel_reason"] or row["deadline_ms"] <= self.clock():
                raise _conflict()
            if con.execute("SELECT 1 FROM worker_executions WHERE step_id=? AND active_slot=1", (step_id,)).fetchone():
                raise AnalyticsError(409, "WORKER_ACTIVE", "查询执行尚未确认退出，不能提交结果。")
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=?", (run_id, attempt_id, step_id)).fetchone()
            if step is None:
                raise _conflict()
            if step["state"] == "SUCCEEDED":
                if step["result_json"] != encoded:
                    raise _conflict()
                return
            if step["deadline_ms"] <= self.clock():
                raise AnalyticsError(409, "QUERY_TIMEOUT", "该查询步骤的原截止时间已过，不能提交迟到结果。")
            con.execute("UPDATE steps SET state='SUCCEEDED', result_json=? WHERE step_id=? AND state='STARTED'", (encoded, step_id))
            row = self._update(con, row)
            self._emit(con, row, "tool.completed", step_id=step_id)

    def step_result(self, principal, run_id, attempt_id, step_id):
        require(principal, "run:read")
        with self._connection(readonly=True) as con:
            row = self._run(con, principal, run_id)
            if row["attempt_id"] != attempt_id:
                raise _conflict()
            step = con.execute("SELECT result_json FROM steps WHERE run_id=? AND attempt_id=? AND step_id=? AND state='SUCCEEDED'",
                               (run_id, attempt_id, step_id)).fetchone()
            if step is None:
                raise _conflict()
            return AnalyticsB0Result.model_validate_json(step[0])

    def begin_worker(self, principal, run_id, attempt_id, step_id, execution_id, lease_dev, lease_ino):
        """Persist one physical intent while its parent already holds the lease."""
        require(principal, "run:create")
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=?",
                               (run_id, attempt_id, step_id)).fetchone()
            if (row["attempt_id"] != attempt_id or row["status"] != "RUNNING" or row["cancel_reason"]
                    or step is None or step["state"] != "STARTED" or step["deadline_ms"] <= self.clock()):
                raise _conflict()
            if con.execute("SELECT 1 FROM worker_executions WHERE step_id=?", (step_id,)).fetchone():
                raise AnalyticsError(409, "WORKER_ALREADY_REGISTERED", "原步骤已有执行记录，不能启动第二份执行。")
            if con.execute("SELECT 1 FROM worker_executions WHERE active_slot=1").fetchone():
                raise AnalyticsError(429, "WORKER_BUSY", "共享计算名额仍被占用。")
            con.execute("""INSERT INTO worker_executions
                (execution_id, run_id, attempt_id, step_id, lease_dev, lease_ino, state, active_slot, deadline_ms)
                VALUES (?, ?, ?, ?, ?, ?, 'RESERVED', 1, ?)""",
                        (execution_id, run_id, attempt_id, step_id, lease_dev, lease_ino, step["deadline_ms"]))
            self._hook("worker:before_commit")
        self._hook("worker:after_commit")

    def worker_started(self, execution_id, pid):
        with self._transaction() as con:
            if con.execute("UPDATE worker_executions SET state='RUNNING', pid=? WHERE execution_id=? AND state='RESERVED'",
                           (pid, execution_id)).rowcount != 1:
                raise _conflict()

    def worker_records(self, *, active_only=True, execution_id=None):
        with self._connection(readonly=True) as con:
            records = con.execute("""SELECT w.*, r.owner, r.status AS run_status, r.cancel_reason,
                r.deadline_ms AS run_deadline_ms FROM worker_executions w JOIN runs r USING(run_id)
                WHERE (?=0 OR w.active_slot=1) AND (? IS NULL OR w.execution_id=?)""",
                                  (int(active_only), execution_id, execution_id)).fetchall()
            return [dict(row) for row in records]

    def request_stop(self, run_id, attempt_id, error_code):
        """Trusted resource/runtime adapter request; not a public cancellation API."""
        if error_code not in SAFE_ERRORS:
            raise ValueError("unsafe stop reason")
        with self._transaction() as con:
            row = self._active_attempt(con, run_id, attempt_id)
            if row["status"] not in TERMINAL and row["cancel_reason"] is None:
                row = self._update(con, row, status="CANCELLING", cancel_reason=error_code, error_code=error_code)
                self._emit(con, row, "run.updated")

    def worker_exited(self, execution_id, *, exit_code, error_code, metrics):
        """Require the persisted lease inode to be free before recording exit.

        Even a trusted caller cannot turn an acknowledgement into lease exit.
        Repeated recovery is idempotent; an unknown lease retains both slots.
        """
        if error_code is not None and error_code not in SAFE_ERRORS:
            raise ValueError("unsafe worker error")
        encoded = canonical_json(metrics)
        if len(encoded.encode()) > 65536:
            raise ValueError("worker diagnostics exceed the bounded record")
        with self._transaction() as con:
            record = con.execute("SELECT * FROM worker_executions WHERE execution_id=?", (execution_id,)).fetchone()
            if record is None:
                raise _conflict()
            if record["state"] == "EXITED":
                return
            with released_lease(self.directory, record) as directory:
                cleanup = clear_owned_spill(directory)
                encoded = canonical_json({**metrics, **cleanup})
                con.execute("""UPDATE worker_executions SET state='EXITED', active_slot=NULL,
                    exit_code=?, error_code=?, metrics_json=? WHERE execution_id=? AND active_slot=1""",
                            (exit_code, error_code, encoded, execution_id))
                if error_code:
                    row = self._active_attempt(con, record["run_id"], record["attempt_id"])
                    if row["status"] not in TERMINAL and row["cancel_reason"] is None:
                        row = self._update(con, row, status="CANCELLING", cancel_reason=error_code, error_code=error_code)
                        self._emit(con, row, "run.updated")
                self._hook("worker-exit:before_commit")
        self._hook("worker-exit:after_commit")

    def observe(self, principal: AnalyticsPrincipal | None, observation: ExecutionObservation) -> AnalyticsRunSnapshot:
        """Apply trusted, correlated runtime evidence with terminal CAS fencing."""
        valid_outcomes = TERMINAL | {"RUNNING", "UNKNOWN"}
        if (type(observation.execution_exited) is not bool or observation.outcome not in valid_outcomes
                or observation.error_code not in SAFE_ERRORS | {None}):
            raise ValueError("unsupported runtime evidence")
        if observation.outcome in TERMINAL and not observation.execution_exited:
            raise ValueError("terminal runtime evidence requires confirmed execution exit")
        with self._transaction() as con:
            row = self._active_attempt(con, observation.run_id, observation.attempt_id)
            if principal is not None and principal.actor_id != row["owner"]:
                raise _missing()
            allowed = principal is not None
            if allowed:
                try:
                    require(principal, "run:create")
                except AnalyticsError:
                    allowed = False
            dispatch = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
            if dispatch["session_id"] != observation.session_id or dispatch["request_id"] != observation.request_id:
                raise _conflict()
            if row["status"] in TERMINAL:
                return self._snapshot(con, row)
            if row["active_slot"] is None:
                raise _conflict()
            if observation.execution_exited and con.execute(
                    "SELECT 1 FROM worker_executions WHERE run_id=? AND active_slot=1", (row["run_id"],)).fetchone():
                raise AnalyticsError(409, "WORKER_ACTIVE", "原生循环已退出，但查询执行尚未确认退出。")
            result, primary = None, None
            status = observation.outcome
            error_code = observation.error_code
            if observation.execution_exited:
                if row["cancel_reason"] == "USER_REQUEST":
                    status = "CANCELLED"
                elif not allowed:
                    status, error_code = "FAILED", "PERMISSION_REVOKED"
                elif row["cancel_reason"] or row["deadline_ms"] <= self.clock():
                    status, error_code = "FAILED", row["cancel_reason"] or "TIMEOUT"
                elif status not in TERMINAL:
                    status, error_code = "FAILED", "EXECUTION_UNKNOWN"
                if status == "SUCCEEDED":
                    primary = observation.primary_result_ref
                    step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=? AND state='SUCCEEDED'",
                                       (row["run_id"], observation.attempt_id, primary)).fetchone()
                    pending = con.execute("SELECT 1 FROM steps WHERE run_id=? AND state!='SUCCEEDED'", (row["run_id"],)).fetchone()
                    if step is None or pending:
                        raise AnalyticsError(409, "INCOMPLETE_EVIDENCE", "没有完整主结果或仍有未完成步骤，不能提交成功。")
                    result = AnalyticsB0Result.model_validate_json(step["result_json"])
                row = self._update(con, row, status=status, phase="FINALIZING", active_slot=None,
                                   error_code=error_code, result=result, primary_result_ref=primary)
                con.execute("UPDATE dispatch_intents SET state='EXITED' WHERE run_id=?", (row["run_id"],))
                event_type = {"SUCCEEDED": "run.completed", "FAILED": "run.failed",
                              "CANCELLED": "run.cancelled", "NEEDS_INPUT": "run.needs_input"}[status]
            else:
                cancel_reason = row["cancel_reason"] or ("PERMISSION_REVOKED" if not allowed else None)
                status = "CANCELLING" if cancel_reason else status
                error_code = cancel_reason if cancel_reason in SAFE_ERRORS else error_code
                dispatch_status = "UNKNOWN" if observation.outcome == "UNKNOWN" else "ACCEPTED"
                if (row["status"] == status and dispatch["state"] == dispatch_status
                        and row["cancel_reason"] == cancel_reason and row["error_code"] == error_code):
                    return self._snapshot(con, row)
                row = self._update(con, row, status=status, cancel_reason=cancel_reason, error_code=error_code)
                con.execute("UPDATE dispatch_intents SET state=? WHERE run_id=?", (dispatch_status, row["run_id"]))
                event_type = "run.updated"
            self._emit(con, row, event_type)
            self._hook("observe:before_commit")
            response = self._snapshot(con, con.execute("SELECT * FROM runs WHERE run_id=?", (row["run_id"],)).fetchone())
        self._hook("observe:after_commit")
        return response

    def recover(self) -> list[DispatchIntent]:
        """Record uncertainty, retain reservations and return original identities.

        No PID probing, process killing, new attempt, new request or transport.
        The adapter must independently reconcile each returned intent.
        """
        pending = []
        with self._transaction() as con:
            rows = con.execute("SELECT * FROM runs WHERE active_slot=1").fetchall()
            for row in rows:
                dispatch = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
                target = "CANCELLING" if row["cancel_reason"] else "UNKNOWN"
                if row["status"] != target or dispatch["state"] != "UNKNOWN":
                    row = self._update(con, row, status=target, error_code="EXECUTION_UNKNOWN")
                    con.execute("UPDATE dispatch_intents SET state='UNKNOWN' WHERE run_id=?", (row["run_id"],))
                    self._emit(con, row, "run.updated")
                pending.append(DispatchIntent(row["run_id"], row["attempt_id"], dispatch["session_id"],
                                              dispatch["request_id"], json.loads(dispatch["payload_json"]),
                                              dispatch["payload_hash"], row["deadline_ms"]))
        return pending

    def enforce_deadlines(self) -> list[str]:
        """Request stop for active timeouts, never release an unconfirmed slot."""
        stop_ids = []
        with self._transaction() as con:
            rows = con.execute("SELECT * FROM runs WHERE deadline_ms<=? AND status NOT IN ('SUCCEEDED','FAILED','CANCELLED','NEEDS_INPUT')",
                               (self.clock(),)).fetchall()
            for row in rows:
                if row["active_slot"] is None:
                    row = self._update(con, row, status="FAILED", error_code="TIMEOUT")
                    con.execute("UPDATE dispatch_intents SET state='EXITED' WHERE run_id=?", (row["run_id"],))
                    self._emit(con, row, "run.failed")
                else:
                    if row["cancel_reason"] is None:
                        row = self._update(con, row, status="CANCELLING", cancel_reason="TIMEOUT", error_code="TIMEOUT")
                        self._emit(con, row, "run.updated")
                    stop_ids.append(row["run_id"])
        return stop_ids

    def events(self, principal: AnalyticsPrincipal, run_id: str, after: int = 0) -> list[AnalyticsRunEvent]:
        require(principal, "run:read")
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            row = self._run(con, principal, run_id)
            if isinstance(after, bool) or not isinstance(after, int) or after < 0 or after > row["last_sequence"]:
                raise AnalyticsError(422, "INVALID_EVENT_CURSOR", "事件游标不属于当前有效范围。")
            first = con.execute("SELECT min(sequence) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
            first = first if first is not None else row["last_sequence"] + 1
            if after < first - 1:
                raise AnalyticsError(410, "EVENT_CURSOR_EXPIRED", "事件游标已过期，请读取任务快照后继续，不要重新提问。",
                                     recovery_url=f"/api/v1/analytics/runs/{run_id}")
            records = con.execute("SELECT event_json FROM events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT 100",
                                  (run_id, after)).fetchall()
            return [AnalyticsRunEvent.model_validate_json(item[0]) for item in records]
