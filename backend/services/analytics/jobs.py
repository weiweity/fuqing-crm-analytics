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
from typing import Callable, Literal
from uuid import uuid4

from backend.contracts.analytics import (
    ANALYTICS_RUN_SCHEMA,
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
from backend.contracts.analytics_query import (
    ChannelFollowupQueryRequest,
    canonical_rfc3339,
    parse_query_datetime,
)
from backend.contracts.analytics_query_run import (
    QUERY_CONTEXT_SCHEMA,
    QUERY_DATA_SCOPE,
    QUERY_RUN_FAMILY,
    QUERY_RUN_SCHEMA,
    AnalyticsQueryNativePrompt,
    ChannelFollowupFixtureDescriptor,
)
from backend.contracts.analytics_first_purchase_kernel import FIRST_PURCHASE_CONTEXT_SCHEMA
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_HTTP_PREFIX
from .access import AnalyticsError, AnalyticsPrincipal, require
from .execution_lease import clear_owned_spill, released_lease
from .resource_profile import B0ResourceProfile, canonical_json, content_hash
from backend.semantic.analytics_b0 import CHANNEL, CONTENT_SHA256, DATA_AS_OF, FIXTURE_ID

from .query_codecs import CODECS, resolve_filters

RUN_FAMILIES = ("b0", *CODECS)
FAMILY_SCOPE = {"b0": "b0-fixture", QUERY_RUN_FAMILY: QUERY_DATA_SCOPE, "first_purchase": "first-purchase-fixture"}

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
class QueryStepBinding:
    """Trusted frozen query step identity. Callers cannot replace scope or fixture."""

    run_id: str
    attempt_id: str
    step_id: str
    family: str
    request: ChannelFollowupQueryRequest
    resolved_filters: dict
    fixture: ChannelFollowupFixtureDescriptor
    permission_scope: str
    method_package_digest: str


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
                 *, family: Literal["b0", "channel_followup", "first_purchase"] = "b0",
                 clock: Callable[[], int] = _now_ms,
                 fault_hook: Callable[[str], None] | None = None):
        # No default path, dotenv, database fallback, migration or deletion.
        if family not in RUN_FAMILIES:
            raise ValueError("unsupported run family")
        original = Path(state_dir)
        if original.is_symlink() or not original.is_dir():
            raise ValueError("an existing private B0 state directory is required")
        self.directory = original.resolve(strict=True)
        mode = self.directory.stat()
        if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
            raise ValueError("B0 state directory must be owned by the caller and mode 0700")
        self.path = self.directory / "runs.sqlite3"
        self.profile = profile
        self.family = family
        self.codec = CODECS.get(family)
        self.is_query = self.codec is not None
        self.data_scope = FAMILY_SCOPE[family]
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
                    self._assert_existing_family(con)
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
                    if self.is_query:
                        con.execute("INSERT INTO metadata VALUES (?, ?)", ("run_family", self.family))
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

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=self.data_scope)

    def _permission_scope(self, principal: AnalyticsPrincipal) -> str:
        return content_hash({"actor_id": principal.actor_id, "data_scope": self.data_scope})

    def _owner_scope(self, owner: str) -> str:
        return content_hash({"actor_id": owner, "data_scope": self.data_scope})

    @staticmethod
    def _request_schema(row) -> str | None:
        try:
            payload = json.loads(row["request_json"])
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        schema = payload.get("schema_version")
        return schema if isinstance(schema, str) else None

    def _assert_run_schema(self, row) -> None:
        expected = self.codec.schema if self.is_query else ANALYTICS_RUN_SCHEMA
        if self._request_schema(row) != expected:
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")

    @staticmethod
    def _idempotency(con, actor, operation, target, key):
        return con.execute(
            "SELECT * FROM idempotency WHERE actor=? AND operation=? AND target=? AND key=?",
            (actor, operation, target, key),
        ).fetchone()

    @staticmethod
    def _fixture_metadata(binding: object) -> dict:
        fixture = binding.fixture
        return {
            "snapshot_id": fixture.snapshot_id,
            "data_version": fixture.data_version,
            "data_digest": fixture.data_digest,
            "as_of": fixture.as_of,
            "timezone": fixture.timezone,
        }

    def _step_payload(self, request: object, resolved, binding: object) -> dict:
        return {
            "request": request.model_dump(mode="json"),
            "resolved_filters": resolved.model_dump(mode="json"),
            "data_digest": binding.fixture.data_digest,
            "permission_scope": binding.permission_scope,
            "family": self.family,
        }

    def _accept_digest(self, request_payload, method_package_digest, fixture, permission_scope,
                       native=None) -> str:
        payload = {
            "request": request_payload, "family": self.family,
            "method_package_digest": method_package_digest,
            "fixture": fixture, "permission_scope": permission_scope,
        }
        if native is not None:
            payload["native"] = native
        return content_hash(payload)

    def _query_native_payload(self, con, row) -> dict | None:
        stored = self._idempotency(con, row["owner"], "runtime.native-binding", row["run_id"], "native")
        intent = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
        if stored is None:
            if intent is not None:
                try:
                    payload = json.loads(intent["payload_json"])
                except json.JSONDecodeError:
                    raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
                if payload.get("native_request") is not None:
                    raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
            return None
        try:
            native = AnalyticsQueryNativePrompt.model_validate(json.loads(stored["response_json"]))
            native = native.model_dump(mode="json")
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        if content_hash(native) != stored["request_hash"]:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        if intent is None:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        try:
            payload = json.loads(intent["payload_json"])
        except json.JSONDecodeError:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        if (payload.get("native_request") != native or intent["request_id"] != native["requestId"]
                or intent["session_id"] != native["sessionId"]):
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        conversation = con.execute(
            "SELECT runtime_session_id FROM conversations WHERE conversation_id=?",
            (row["conversation_id"],),
        ).fetchone()
        if conversation is None or conversation["runtime_session_id"] != native["sessionId"]:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        return native

    def _freeze_query_native(self, native_request, request, key) -> dict:
        try:
            prompt = AnalyticsQueryNativePrompt.model_validate(native_request)
            frozen = prompt.model_dump(mode="json")
        except Exception:
            raise AnalyticsError(422, "UNSUPPORTED_NATIVE", "查询任务的 native 受理无效。") from None
        if frozen["requestId"] != key:
            raise _conflict()
        normalized = self.codec.run_request(question=frozen["content"][0]["text"]).question
        if normalized != request.question:
            raise _conflict()
        return frozen

    def _inspect_query_run(self, con, row) -> object:
        """Persistence self-check. Does not grant or re-check current capabilities."""
        if not self.is_query:
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
        try:
            request = self.codec.run_request.model_validate(json.loads(row["request_json"]))
        except Exception:
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。") from None
        descriptor = self._idempotency(con, row["owner"], "runtime.binding", row["run_id"], "descriptor")
        if descriptor is None:
            raise AnalyticsError(409, "BINDING_MISSING", "查询任务缺少冻结绑定，不能继续。")
        try:
            stored = json.loads(descriptor["response_json"])
            binding = self.codec.binding.model_validate(stored)
            binding = self.codec.binding.model_validate(binding.model_dump(mode="python"))
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        if content_hash(stored) != descriptor["request_hash"]:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        if binding.family != self.family or binding.permission_scope != self._owner_scope(row["owner"]):
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        method = self._idempotency(con, row["owner"], "runtime.binding", row["run_id"], "method")
        if method is None or method["request_hash"] != binding.method_package_digest:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        native = self._query_native_payload(con, row)
        expected = self._accept_digest(
            request.model_dump(mode="json"), binding.method_package_digest,
            binding.fixture.model_dump(mode="json"), binding.permission_scope, native,
        )
        if expected != row["request_hash"]:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        return binding

    def _inspect_query_step(self, con, row, step, binding: object) -> dict:
        stored_row = self._idempotency(con, row["owner"], "runtime.step-binding", row["run_id"], step["call_id"])
        if stored_row is None:
            raise AnalyticsError(409, "BINDING_MISSING", "查询步骤缺少冻结绑定，不能继续。")
        try:
            stored = json.loads(stored_row["response_json"])
            request = self.codec.request.model_validate(stored["request"])
            request = self.codec.request.model_validate(request.model_dump(mode="python"))
            resolved = resolve_filters(self.family, request, binding)
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询步骤绑定已损坏，不能继续。") from None
        payload = self._step_payload(request, resolved, binding)
        digest = content_hash(payload)
        if (
            content_hash(stored) != stored_row["request_hash"]
            or stored_row["request_hash"] != step["request_hash"]
            or digest != step["request_hash"]
            or stored.get("resolved_filters") != payload["resolved_filters"]
            or stored.get("permission_scope") != binding.permission_scope
            or stored.get("data_digest") != binding.fixture.data_digest
            or stored.get("family") != self.family
        ):
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询步骤绑定已损坏，不能继续。")
        return payload

    def _assert_query_integrity(self, con) -> None:
        fixtures = []
        for row in con.execute("SELECT * FROM runs ORDER BY rowid"):
            try:
                binding = self._inspect_query_run(con, row)
            except AnalyticsError as error:
                raise ValueError(error.message) from error
            fixtures.append(canonical_json(binding.fixture.model_dump(mode="json")))
            for step in con.execute("SELECT * FROM steps WHERE run_id=? ORDER BY rowid", (row["run_id"],)):
                try:
                    self._inspect_query_step(con, row, step, binding)
                except AnalyticsError as error:
                    raise ValueError(error.message) from error
        if len(set(fixtures)) > 1:
            raise ValueError("query store contains mixed fixture bindings")

    @staticmethod
    def _query_evidence(con) -> bool:
        for item in con.execute("SELECT request_json FROM runs"):
            try:
                payload = json.loads(item["request_json"])
            except json.JSONDecodeError:
                return True
            if not isinstance(payload, dict):
                return True
            schema = payload.get("schema_version")
            if schema == QUERY_RUN_SCHEMA or schema not in {ANALYTICS_RUN_SCHEMA, None}:
                return True
        return con.execute(
            "SELECT 1 FROM idempotency WHERE operation='runtime.binding' AND key='descriptor' LIMIT 1",
        ).fetchone() is not None

    def _assert_existing_family(self, con) -> None:
        row = con.execute("SELECT value FROM metadata WHERE key=?", ("run_family",)).fetchone()
        stored = None if row is None else row[0]
        if stored is not None:
            if stored not in RUN_FAMILIES:
                raise ValueError("unknown persisted run family; refusing to overwrite")
            if stored != self.family:
                raise ValueError("persisted run family differs; implicit migration is forbidden")
        else:
            if self.family != "b0":
                raise ValueError("existing state has no run family; channel_followup requires explicit metadata")
            if self._query_evidence(con):
                raise ValueError("missing run_family metadata with query evidence; refusing B0 downgrade")
        if self.is_query:
            self._assert_query_integrity(con)
        elif self._query_evidence(con):
            raise ValueError("B0 store contains query evidence; refusing to open")

    def _authorize_run(self, con, principal: AnalyticsPrincipal, row, capability: str) -> object | None:
        self._require(principal, capability)
        if not self.is_query:
            self._assert_run_schema(row)
            return None
        binding = self._inspect_query_run(con, row)
        if binding.permission_scope != self._permission_scope(principal):
            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
        return binding

    def _decode_query_result(self, con, row, step, encoded: str, binding: object) -> object:
        frozen = self._inspect_query_step(con, row, step, binding)
        try:
            payload = json.loads(encoded)
            # Family-fixed codec: never select a result type from schema_version.
            result = self.codec.result.model_validate(payload)
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询结果与冻结绑定不一致。") from None
        resolved = frozen["resolved_filters"]
        request = frozen["request"]
        dumped = result.resolved_filters.model_dump(mode="json")
        if (
            result.query_version != self.codec.query_version
            or result.metric_version != self.codec.metric_version
            or result.data_version != self.codec.data_version
            or result.data_snapshot_ref != binding.fixture.snapshot_id
            or result.filter_hash != resolved["filter_hash"]
            or dumped != resolved
            or (result.facts is not None and result.facts.observation_days != request["observation_days"])
            or result.resolved_filters.permission_scope != frozen["permission_scope"]
            or result.resolved_filters.data_digest != frozen["data_digest"]
            or result.resolved_filters.data_digest != binding.fixture.data_digest
            or canonical_rfc3339(result.as_of) != canonical_rfc3339(parse_query_datetime(resolved["as_of"]))
        ):
            raise AnalyticsError(409, "BINDING_MISMATCH", "查询结果与冻结步骤绑定不一致。")
        return result

    def query_fixture_descriptor(self) -> object | None:
        """Unique frozen fixture identity for this query store. No budget charge."""
        if not self.is_query:
            raise ValueError("query fixture identity is only defined for channel_followup stores")
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            self._assert_query_integrity(con)
            row = con.execute("SELECT * FROM runs ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            return self._inspect_query_run(con, row).fixture

    def query_step_binding(self, principal: AnalyticsPrincipal, run_id: str, attempt_id: str,
                           step_id: str) -> QueryStepBinding:
        """Fresh authorized read of the frozen step. Callers cannot rebind scope."""
        self._require(principal, "run:create")
        if not self.is_query:
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:create")
            if row["attempt_id"] != attempt_id:
                raise _conflict()
            step = con.execute(
                "SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=?",
                (run_id, attempt_id, step_id),
            ).fetchone()
            if step is None:
                raise _conflict()
            frozen = self._inspect_query_step(con, row, step, binding)
            return QueryStepBinding(
                run_id=run_id, attempt_id=attempt_id, step_id=step_id, family=self.family,
                request=self.codec.request.model_validate(frozen["request"]),
                resolved_filters=frozen["resolved_filters"], fixture=binding.fixture,
                permission_scope=binding.permission_scope,
                method_package_digest=binding.method_package_digest,
            )

    def _encode_query_result(self, result) -> str:
        try:
            payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            parsed = self.codec.result.model_validate(payload)
        except Exception:
            raise AnalyticsError(422, "INVALID_RESULT", "查询结果无法按冻结合同验收。") from None
        encoded = canonical_json(parsed.model_dump(mode="json"))
        if len(encoded.encode()) > self.profile.max_result_bytes:
            raise AnalyticsError(422, "RESULT_TOO_LARGE", "结果超过本次 B0 的大小上限。")
        return encoded

    @staticmethod
    def _query_worker_success(row) -> bool:
        return (row is not None and row["state"] == "EXITED" and row["active_slot"] is None
                and row["error_code"] is None and row["exit_code"] == 0)

    def _inspect_query_steps(self, con, row, binding: object) -> None:
        limit = self.profile.max_tool_steps
        steps = con.execute(
            "SELECT * FROM steps WHERE run_id=? ORDER BY rowid LIMIT ?",
            (row["run_id"], limit + 1),
        ).fetchall()
        if len(steps) > limit:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询步骤绑定已损坏，不能继续。")
        for step in steps:
            self._inspect_query_step(con, row, step, binding)

    def _replay_query_conversation(self, con, principal, cached: str):
        try:
            conversation = self.codec.conversation.model_validate_json(cached)
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        row = self._conversation(con, principal, conversation.conversation_id)
        if row["title"] != conversation.title or _timestamp(row["created_ms"]) != conversation.created_at:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        return conversation

    def _replay_query_accepted(self, con, principal, conversation_id, digest, cached: str):
        try:
            response = self.codec.accepted.model_validate_json(cached)
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        stored = con.execute(
            "SELECT * FROM runs WHERE run_id=? AND owner=? AND conversation_id=?",
            (response.run_id, principal.actor_id, conversation_id),
        ).fetchone()
        if stored is None:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        if stored["request_hash"] != digest:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        try:
            original = json.loads(stored["original_202"])
        except json.JSONDecodeError:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        if canonical_json(original) != canonical_json(response.model_dump(mode="json")):
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        binding = self._inspect_query_run(con, stored)
        if binding.permission_scope != self._permission_scope(principal):
            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
        self._inspect_query_steps(con, stored, binding)
        return response

    def _replay_query_snapshot(self, con, principal, row, cached: str):
        try:
            snapshot = self.codec.snapshot.model_validate_json(cached)
        except Exception:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。") from None
        if (
            snapshot.run_id != row["run_id"]
            or snapshot.conversation_id != row["conversation_id"]
            or snapshot.source_ref != row["conversation_id"]
            or snapshot.parent_run_id != row["parent_run_id"]
        ):
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        binding = self._inspect_query_run(con, row)
        if principal is not None and binding.permission_scope != self._permission_scope(principal):
            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
        self._inspect_query_steps(con, row, binding)
        if snapshot.result is not None:
            if snapshot.primary_result_ref is None:
                raise AnalyticsError(409, "BINDING_MISSING", "查询结果缺少冻结步骤绑定，不能继续。")
            step = con.execute(
                "SELECT * FROM steps WHERE run_id=? AND step_id=?",
                (row["run_id"], snapshot.primary_result_ref),
            ).fetchone()
            if step is None:
                raise AnalyticsError(409, "BINDING_MISSING", "查询结果缺少冻结步骤绑定，不能继续。")
            encoded = canonical_json(snapshot.result.model_dump(mode="json"))
            self._decode_query_result(con, row, step, encoded, binding)
        return snapshot

    def create_conversation(self, principal: AnalyticsPrincipal, key: str,
                            request: object,
                            *, runtime_session_id: str | None = None):
        self._require(principal, "run:create")
        expected = self.codec.conversation_request if self.is_query else AnalyticsConversationRequest
        if not isinstance(request, expected):
            raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "会话合同与当前实例不一致。")
        if self.is_query:
            try:
                request = self.codec.conversation_request.model_validate(request.model_dump(mode="python"))
            except Exception:
                raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "会话合同与当前实例不一致。") from None
        validate_key(key)
        digest_payload = {**request.model_dump(mode="json"), **({"native_session": runtime_session_id} if runtime_session_id else {})}
        if self.is_query:
            digest_payload = {**digest_payload, "family": self.family}
        digest = content_hash(digest_payload)
        conversation_type = self.codec.conversation if self.is_query else AnalyticsConversation
        with self._transaction() as con:
            prior = self._prior(con, principal, "conversation:create", "", key, digest)
            if prior:
                if self.is_query:
                    return self._replay_query_conversation(con, principal, prior["response_json"])
                return conversation_type.model_validate_json(prior["response_json"])
            counts = con.execute("SELECT count(*), count(CASE WHEN owner=? THEN 1 END) FROM conversations",
                                 (principal.actor_id,)).fetchone()
            if counts[0] >= self.profile.max_retained_conversations or counts[1] >= self.profile.max_retained_conversations_per_actor:
                raise AnalyticsError(429, "RETENTION_LIMIT", "B0 会话保留额度已满；不会删除已有记录。")
            self._admit_storage(con, new_run=False)
            now = self.clock()
            response = conversation_type(conversation_id=_id("conv"), title=request.title, created_at=_timestamp(now))
            con.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                        (response.conversation_id, principal.actor_id, request.title, now, runtime_session_id or _id("session")))
            self._remember(con, principal, "conversation:create", "", key, digest, response.model_dump(mode="json"), 201)
        return response

    def get_conversation(self, principal: AnalyticsPrincipal, conversation_id: str):
        self._require(principal, "run:read")
        conversation_type = self.codec.conversation if self.is_query else AnalyticsConversation
        with self._connection(readonly=True) as con:
            row = self._conversation(con, principal, conversation_id)
            ids = con.execute("SELECT run_id FROM runs WHERE conversation_id=? AND owner=? ORDER BY rowid",
                              (conversation_id, principal.actor_id)).fetchall()
            return conversation_type(conversation_id=conversation_id, title=row["title"],
                                     created_at=_timestamp(row["created_ms"]), run_ids=[item[0] for item in ids])

    def accept(self, principal: AnalyticsPrincipal, conversation_id: str, key: str,
               request, *, allow_new: bool = True, native_request: dict | None = None,
               method_package_digest: str | None = None, fixture_descriptor=None):
        self._require(principal, "run:create")
        validate_key(key)
        if method_package_digest is not None and (len(method_package_digest) != 64
                or any(c not in "0123456789abcdef" for c in method_package_digest)):
            raise ValueError("explicit fixed method package digest required")
        if self.is_query:
            if not isinstance(request, self.codec.run_request):
                raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "任务合同与当前实例不一致。")
            try:
                request = self.codec.run_request.model_validate(request.model_dump(mode="python"))
            except Exception:
                raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "任务合同与当前实例不一致。") from None
            if method_package_digest is None:
                raise ValueError("explicit fixed method package digest required")
            if fixture_descriptor is None:
                raise AnalyticsError(422, "FIXTURE_REQUIRED", "查询任务必须登记封存快照描述。")
        elif not isinstance(request, AnalyticsRunRequest) or fixture_descriptor is not None:
            raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "任务合同与当前实例不一致。")
        payload = request.model_dump(mode="json")
        permission_scope = self._permission_scope(principal) if self.is_query else None
        binding_payload = None
        frozen_native = None
        if self.is_query:
            try:
                fixture = self.codec.descriptor.model_validate(fixture_descriptor)
                fixture = self.codec.descriptor.model_validate(fixture.model_dump(mode="python"))
                binding_payload = self.codec.binding.model_validate({
                    "family": self.family, "method_package_digest": method_package_digest,
                    "fixture": fixture.model_dump(mode="json"), "permission_scope": permission_scope,
                }).model_dump(mode="json")
            except Exception:
                raise AnalyticsError(422, "INVALID_FIXTURE", "封存快照描述无效。") from None
            if native_request is not None:
                if self.family not in {QUERY_RUN_FAMILY, "first_purchase"}:
                    raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "当前族尚未接通 native 受理。")
                frozen_native = self._freeze_query_native(native_request, request, key)
            digest = self._accept_digest(
                payload, method_package_digest, binding_payload["fixture"], permission_scope,
                frozen_native,
            )
        else:
            # Native metadata is supplied only by the validated server-side adapter,
            # never by the public RunRequest. Preserve its original request ID for
            # DSH's optimistic echo and journal deduplication.
            frozen_native = native_request
            digest = content_hash(payload if native_request is None else {"request": payload, "native": native_request})
        accepted_type = self.codec.accepted if self.is_query else AnalyticsRunAccepted
        with self._transaction() as con:
            conversation = self._conversation(con, principal, conversation_id)
            prior = self._prior(con, principal, "run:create", conversation_id, key, digest)
            if prior:
                if self.is_query:
                    return self._replay_query_accepted(
                        con, principal, conversation_id, digest, prior["response_json"],
                    )
                return accepted_type.model_validate_json(prior["response_json"])
            if not allow_new:
                raise AnalyticsError(503, "RUNTIME_NOT_CONNECTED", "运行时尚未接线，不接受新的执行任务。")
            if frozen_native is not None:
                if (frozen_native.get("sessionId") != conversation["runtime_session_id"]
                        or frozen_native.get("requestId") != key
                        or con.execute("SELECT 1 FROM dispatch_intents WHERE request_id=?", (key,)).fetchone()):
                    raise _conflict()
            if request.parent_run_id is not None:
                parent = self._run(con, principal, request.parent_run_id)
                if parent["conversation_id"] != conversation_id:
                    raise _missing()
                if self.is_query:
                    parent_binding = self._inspect_query_run(con, parent)
                    child_fixture = self.codec.binding.model_validate(binding_payload).fixture
                    if (parent_binding.fixture != child_fixture
                            or parent_binding.permission_scope != permission_scope):
                        raise AnalyticsError(422, "UNSUPPORTED_PARENT", "不支持的父子任务关系。")
            if self.is_query:
                existing = con.execute(
                    "SELECT actor, target FROM idempotency WHERE operation='runtime.binding' AND key='descriptor' LIMIT 1",
                ).fetchone()
                if existing is not None:
                    previous_run = con.execute("SELECT * FROM runs WHERE run_id=? AND owner=?",
                                               (existing["target"], existing["actor"])).fetchone()
                    if previous_run is None:
                        raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
                    previous = self._inspect_query_run(con, previous_run)
                    if previous.fixture != self.codec.binding.model_validate(binding_payload).fixture:
                        raise AnalyticsError(409, "FIXTURE_CONFLICT", "同一查询实例不能绑定不同的封存快照。")
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
            if self.family == "first_purchase":
                location = f"{FIRST_PURCHASE_HTTP_PREFIX}/runs/{run_id}"
            elif self.is_query:
                location = f"/internal/store/analytics-query/runs/{run_id}"
            else:
                location = f"/api/v1/analytics/runs/{run_id}"
            response = accepted_type(run_id=run_id, location=location)
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
            if self.is_query:
                dispatch_payload["family"] = self.family
            if frozen_native is not None:
                dispatch_payload["native_request"] = frozen_native
            con.execute("INSERT INTO dispatch_intents VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0)",
                        (run_id, conversation["runtime_session_id"], key if frozen_native is not None else _id("dispatch"), attempt_id,
                         canonical_json(dispatch_payload), content_hash(dispatch_payload)))
            self._remember(con, principal, "run:create", conversation_id, key, digest, response.model_dump(mode="json"), 202)
            if method_package_digest is not None:
                self._remember(con, principal, "runtime.binding", run_id, "method", method_package_digest, {}, 200)
            if binding_payload is not None:
                self._remember(con, principal, "runtime.binding", run_id, "descriptor",
                               content_hash(binding_payload), binding_payload, 200)
            if self.is_query and frozen_native is not None:
                self._remember(con, principal, "runtime.native-binding", run_id, "native",
                               content_hash(frozen_native), frozen_native, 200)
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
            work = []
            for row in rows:
                if self.is_query:
                    binding = self._inspect_query_run(con, row)
                    for step in con.execute("SELECT * FROM steps WHERE run_id=? ORDER BY rowid", (row["run_id"],)):
                        self._inspect_query_step(con, row, step, binding)
                elif self._request_schema(row) == QUERY_RUN_SCHEMA:
                    raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
                work.append({"intent": DispatchIntent(row["run_id"], row["attempt_id"], row["session_id"], row["request_id"],
                                                      json.loads(row["payload_json"]), row["payload_hash"], row["deadline_ms"]),
                             "owner": row["owner"], "status": row["status"], "cancel_requested": row["cancel_reason"] is not None,
                             "pending_steps": con.execute("SELECT count(*) FROM steps WHERE run_id=? AND state!='SUCCEEDED'", (row["run_id"],)).fetchone()[0],
                             "steps": {s["call_id"]: s["step_id"] for s in con.execute(
                                 "SELECT call_id, step_id FROM steps WHERE run_id=? AND state='SUCCEEDED'", (row["run_id"],))}})
            return work

    def _snapshot(self, con, row):
        self._assert_run_schema(row)
        intent = con.execute("SELECT * FROM dispatch_intents WHERE run_id=?", (row["run_id"],)).fetchone()
        refs = con.execute("SELECT step_id FROM steps WHERE run_id=? AND state='SUCCEEDED' ORDER BY step_id",
                           (row["run_id"],)).fetchall()
        diagnostics = AnalyticsRunDiagnostics(
            attempt_id=row["attempt_id"], runtime_status=intent["state"], execution_active=row["active_slot"] is not None,
            tool_steps_used=row["tool_steps_used"], dispatch_attempts=intent["attempts"],
            profile_version=json.loads(row["profile_json"])["version"], profile_hash=row["profile_hash"],
            error_code=row["error_code"],
        )
        if not self.is_query:
            return AnalyticsRunSnapshot(
                run_id=row["run_id"], version=row["version"], source_ref=row["conversation_id"],
                conversation_id=row["conversation_id"], parent_run_id=row["parent_run_id"],
                status=row["status"], phase=row["phase"], created_at=_timestamp(row["created_ms"]),
                updated_at=_timestamp(row["updated_ms"]), deadline=_timestamp(row["deadline_ms"]),
                result=AnalyticsB0Result.model_validate_json(row["result_json"]) if row["result_json"] else None,
                evidence_digest=row["evidence_digest"], primary_result_ref=row["primary_result_ref"],
                evidence_refs=[r[0] for r in refs], last_sequence=row["last_sequence"],
                diagnostics=diagnostics,
            )
        binding = self._inspect_query_run(con, row)
        self._inspect_query_steps(con, row, binding)
        result = None
        if row["result_json"]:
            if row["primary_result_ref"] is None:
                raise AnalyticsError(409, "BINDING_MISSING", "查询结果缺少冻结步骤绑定，不能继续。")
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND step_id=?",
                               (row["run_id"], row["primary_result_ref"])).fetchone()
            if step is None:
                raise AnalyticsError(409, "BINDING_MISSING", "查询结果缺少冻结步骤绑定，不能继续。")
            result = self._decode_query_result(con, row, step, row["result_json"], binding)
        return self.codec.snapshot(
            run_id=row["run_id"], version=row["version"], source_ref=row["conversation_id"],
            conversation_id=row["conversation_id"], parent_run_id=row["parent_run_id"],
            status=row["status"], phase=row["phase"], created_at=_timestamp(row["created_ms"]),
            updated_at=_timestamp(row["updated_ms"]), deadline=_timestamp(row["deadline_ms"]),
            result=result, evidence_digest=row["evidence_digest"], primary_result_ref=row["primary_result_ref"],
            evidence_refs=[r[0] for r in refs], last_sequence=row["last_sequence"],
            diagnostics=diagnostics,
        )

    def get(self, principal: AnalyticsPrincipal, run_id: str):
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            row = self._run(con, principal, run_id)
            self._authorize_run(con, principal, row, "run:read")
            return self._snapshot(con, row)

    def query_succeeded_source(self, principal: AnalyticsPrincipal, run_id: str) -> dict:
        """Authorized SUCCEEDED query source. Requires run:read. Starts no worker."""
        if self.family != QUERY_RUN_FAMILY:
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
        return self._succeeded_query_source(principal, run_id)

    def succeeded_operating_source(self, principal: AnalyticsPrincipal, run_id: str) -> dict:
        """Read a frozen operating source using the store's trusted family codec."""
        if self.family == QUERY_RUN_FAMILY:
            return self.query_succeeded_source(principal, run_id)
        if self.family != "first_purchase":
            raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
        return self._succeeded_query_source(principal, run_id)

    def _succeeded_query_source(self, principal: AnalyticsPrincipal, run_id: str) -> dict:
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:read")
            if row["status"] != "SUCCEEDED":
                raise AnalyticsError(422, "UNPROCESSABLE", "只能绑定 SUCCEEDED 运行。")
            if row["result_json"] is None or row["primary_result_ref"] is None:
                raise AnalyticsError(422, "UNPROCESSABLE", "SUCCEEDED 结果缺少冻结步骤引用。")
            step = con.execute(
                "SELECT * FROM steps WHERE run_id=? AND step_id=?",
                (run_id, row["primary_result_ref"]),
            ).fetchone()
            if step is None or step["state"] != "SUCCEEDED":
                raise AnalyticsError(422, "UNPROCESSABLE", "SUCCEEDED 结果缺少冻结步骤引用。")
            frozen = self._inspect_query_step(con, row, step, binding)
            result = self._decode_query_result(con, row, step, row["result_json"], binding)
            request = self.codec.request.model_validate(frozen["request"])
            dumped = result.model_dump(mode="json")
            digest = content_hash(dumped)
            if row["evidence_digest"] != digest:
                raise AnalyticsError(409, "BINDING_CORRUPT", "查询结果与冻结绑定不一致。")
            if result.query_id != self.codec.query_id or result.query_version != self.codec.query_version:
                raise AnalyticsError(
                    422, "UNPROCESSABLE",
                    f"本波只允许 {self.codec.query_id} / {self.codec.query_version}。",
                )
            if result.metric_id != self.codec.metric_id or result.metric_version != self.codec.metric_version:
                raise AnalyticsError(422, "UNPROCESSABLE", "指标版本与本波合同不一致。")
            if result.data_version != self.codec.data_version:
                raise AnalyticsError(422, "UNPROCESSABLE", "数据版本与本波合同不一致。")
            if self.family == "first_purchase" and (result.status != "OK" or result.facts is None):
                raise AnalyticsError(422, "UNPROCESSABLE", "合同拒绝结果不能保存为有效经营分析。")
            source = {
                "run_id": run_id,
                "status": "SUCCEEDED",
                "query_id": result.query_id,
                "query_version": result.query_version,
                "metric_id": result.metric_id,
                "metric_version": result.metric_version,
                "data_version": result.data_version,
                "filter_hash": result.filter_hash,
                "evidence_digest": digest,
                "request": request.model_dump(mode="json"),
                "result": dumped,
                "owner_id": principal.actor_id,
                "primary_result_ref": row["primary_result_ref"],
            }
            if self.family == "first_purchase":
                source["method_package_digest"] = binding.method_package_digest
            return source

    def rebuild_context(self, principal, run_id, attempt_id, *, package_digest, unit_id, resource=None):
        """Re-read authoritative state, never a model summary or a cached grant.

        Existing idempotency storage binds the method version and charges each
        model step/method read once. No new state DB or implicit migration.
        Method reads share the query tool budget but are never numeric evidence.
        """
        self._require(principal, "run:read")
        self._require(principal, "run:create")
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
            self._authorize_run(con, principal, row, "run:read")
            # A completed first-purchase tool still needs a bounded native
            # model step to summarize its trusted receipt. No method/tool grant.
            summary_only = (self.family == "first_purchase" and resource is None
                            and row["status"] == "SUCCEEDED" and row["active_slot"] is None)
            if (row["attempt_id"] != attempt_id
                    or (not summary_only and (row["status"] != "RUNNING" or row["active_slot"] is None))
                    or row["cancel_reason"] or row["deadline_ms"] <= self.clock()):
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
            remaining = {
                "tool_steps": self.profile.max_tool_steps - row["tool_steps_used"],
                "model_steps": self.profile.max_tool_steps - model_used,
                "deadline": _timestamp(row["deadline_ms"]).isoformat(),
                "remaining_ms": max(0, row["deadline_ms"] - self.clock()),
            }
            if self.is_query:
                payload = self._query_context(con, principal, row, attempt_id, package_digest, remaining)
            else:
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
                    "remaining_budget": remaining,
                    "approval_state": "NOT_AVAILABLE_IN_B0", "memory_authority": "NONE",
                    "contains_real_data": False,
                }
            if len(canonical_json(payload).encode()) > 65536:
                raise AnalyticsError(409, "RESOURCE_EXCEEDED", "上下文超出有界摘要限制。")
            return payload

    def _query_context(self, con, principal, row, attempt_id, package_digest, remaining):
        if not self.is_query:
            raise AnalyticsError(422, "UNSUPPORTED_REQUEST", "当前族尚未接通 native 上下文。")
        run_binding = self._inspect_query_run(con, row)
        if run_binding.permission_scope != self._permission_scope(principal):
            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
        if run_binding.method_package_digest != package_digest:
            raise AnalyticsError(409, "BINDING_CORRUPT", "查询任务绑定已损坏，不能继续。")
        completed = []
        registered = []
        conditions = {"mode": "AWAITING_REGISTERED_QUERY"}
        for step in con.execute("SELECT * FROM steps WHERE run_id=? ORDER BY rowid", (row["run_id"],)):
            frozen = self._inspect_query_step(con, row, step, run_binding)
            item = {
                "step_id": step["step_id"], "call_id": step["call_id"],
                "request": frozen["request"], "resolved_filters": frozen["resolved_filters"],
            }
            registered.append(item)
            conditions = {"mode": "REGISTERED_QUERY", **item}
            if step["state"] == "SUCCEEDED":
                result = self._decode_query_result(con, row, step, step["result_json"], run_binding).model_dump(mode="json")
                completed.append({"step_id": step["step_id"], "call_id": step["call_id"], "state": "SUCCEEDED",
                                  "request": frozen["request"], "resolved_filters": frozen["resolved_filters"],
                                  "result": result, "evidence_digest": content_hash(result)})
        context_schema = QUERY_CONTEXT_SCHEMA if self.family == QUERY_RUN_FAMILY else FIRST_PURCHASE_CONTEXT_SCHEMA
        return {
            "schema_version": context_schema, "run_id": row["run_id"], "attempt_id": attempt_id,
            "run_version": row["version"], "run_status": row["status"], "phase": row["phase"],
            "question": json.loads(row["request_json"])["question"], "parent_run_id": row["parent_run_id"],
            "conditions": conditions, "registered_queries": registered,
            "versions": {"contract": self.codec.schema, "method_package_digest": run_binding.method_package_digest,
                         "query": self.codec.query_version, "metric": self.codec.metric_version,
                         "fixture_id": run_binding.fixture.snapshot_id,
                         "data_digest": run_binding.fixture.data_digest},
            "completed_steps": completed, "primary_result_ref": row["primary_result_ref"],
            "pending_clarifications": ["等待已登记查询条件；自然语言不解析为筛选。"] if conditions["mode"] == "AWAITING_REGISTERED_QUERY" else [],
            "remaining_budget": remaining,
            "approval_state": "NOT_AVAILABLE_IN_QUERY_RUN", "memory_authority": "NONE",
            "contains_real_data": False,
        }

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
               request: AnalyticsCancelRequest):
        self._require(principal, "run:cancel")
        validate_key(key)
        digest = content_hash({"request": request.model_dump(), "if_match": version})
        snapshot_type = self.codec.snapshot if self.is_query else AnalyticsRunSnapshot
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            self._authorize_run(con, principal, row, "run:cancel")
            prior = self._prior(con, principal, "run:cancel", run_id, key, digest)
            if prior:
                if self.is_query:
                    return self._replay_query_snapshot(con, principal, row, prior["response_json"])
                return snapshot_type.model_validate_json(prior["response_json"])
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
                    self._require(principal, "run:create")
                except AnalyticsError:
                    allowed = False
            with self._transaction() as con:
                row = con.execute("SELECT * FROM runs WHERE run_id=? AND status='QUEUED'", (candidate["run_id"],)).fetchone()
                if row is None:
                    continue
                if allowed and self.is_query:
                    try:
                        binding = self._inspect_query_run(con, row)
                        if binding.permission_scope != self._permission_scope(principal):
                            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
                    except AnalyticsError as error:
                        if error.status == 403:
                            allowed = False
                        else:
                            raise
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
                     call_id: str, *, query: str = "channel_repeat_rate", request=None) -> StepReservation:
        self._require(principal, "run:create")
        validate_key(call_id)
        if self.is_query:
            if request is None:
                raise AnalyticsError(422, "UNSUPPORTED_QUERY", "查询步骤必须提供已登记的完整条件。")
            try:
                query_request = self.codec.request.model_validate(
                    request.model_dump(mode="python") if isinstance(request, self.codec.request) else request
                )
            except Exception:
                raise AnalyticsError(422, "INVALID_QUERY", "查询条件无法按冻结快照规范化。") from None
        else:
            if request is not None or query != "channel_repeat_rate":
                raise AnalyticsError(422, "UNSUPPORTED_QUERY", "B0 仅允许已登记的固定合成 fixture。")
            query_request = None
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:create")
            if con.execute("SELECT 1 FROM idempotency WHERE operation='runtime.method-read' AND target=? AND key=?", (run_id, call_id)).fetchone():
                raise _conflict()
            if row["attempt_id"] != attempt_id:
                raise _conflict()
            if row["status"] != "RUNNING" or row["cancel_reason"] or row["deadline_ms"] <= self.clock():
                raise _conflict()
            if self.is_query:
                try:
                    resolved = resolve_filters(self.family, query_request, binding)
                except Exception:
                    raise AnalyticsError(422, "INVALID_QUERY", "查询条件无法按冻结快照规范化。") from None
                step_payload = self._step_payload(query_request, resolved, binding)
                digest = content_hash(step_payload)
            else:
                step_payload = None
                digest = content_hash({"query": query})
            prior = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND call_id=?", (run_id, attempt_id, call_id)).fetchone()
            if prior:
                if prior["request_hash"] != digest:
                    raise _conflict()
                if step_payload is not None:
                    self._inspect_query_step(con, row, prior, binding)
                reservation = StepReservation(prior["step_id"], "REUSE_RESULT" if prior["state"] == "SUCCEEDED" else "PENDING", prior["deadline_ms"])
                self._hook("reserve:before_commit")
            else:
                if row["tool_steps_used"] >= self.profile.max_tool_steps:
                    raise AnalyticsError(429, "TOOL_STEP_LIMIT", "本任务的工具步数预算已用完。")
                if step_payload is not None and self._prior(con, principal, "runtime.step-binding", run_id, call_id, digest) is not None:
                    raise AnalyticsError(409, "BINDING_CORRUPT", "查询步骤绑定与步骤记录不一致。")
                step_id = _id("step")
                step_deadline = min(row["deadline_ms"], self.clock() + self.profile.query_timeout_ms)
                con.execute("INSERT INTO steps VALUES (?, ?, ?, ?, ?, 'STARTED', NULL, ?)", (step_id, run_id, attempt_id, call_id, digest, step_deadline))
                if step_payload is not None:
                    self._remember(con, principal, "runtime.step-binding", run_id, call_id, digest, step_payload, 200)
                row = self._update(con, row, phase="EXECUTING", tool_steps_used=row["tool_steps_used"] + 1)
                self._emit(con, row, "tool.started", step_id=step_id)
                reservation = StepReservation(step_id, "EXECUTE", step_deadline)
                self._hook("reserve:before_commit")
        self._hook("reserve:after_commit")
        return reservation

    def complete_step(self, principal: AnalyticsPrincipal, run_id: str, attempt_id: str,
                      step_id: str, result) -> None:
        self._require(principal, "run:create")
        if not self.is_query:
            # Revalidate even if an internal caller used model_construct().
            result = AnalyticsB0Result.model_validate(result.model_dump(mode="json"))
            encoded = canonical_json(result.model_dump(mode="json"))
            if len(encoded.encode()) > self.profile.max_result_bytes:
                raise AnalyticsError(422, "RESULT_TOO_LARGE", "结果超过本次 B0 的大小上限。")
        else:
            encoded = None
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:create")
            if row["attempt_id"] != attempt_id or row["status"] != "RUNNING" or row["cancel_reason"] or row["deadline_ms"] <= self.clock():
                raise _conflict()
            if con.execute("SELECT 1 FROM worker_executions WHERE step_id=? AND active_slot=1", (step_id,)).fetchone():
                raise AnalyticsError(409, "WORKER_ACTIVE", "查询执行尚未确认退出，不能提交结果。")
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=?", (run_id, attempt_id, step_id)).fetchone()
            if step is None:
                raise _conflict()
            if self.is_query:
                self._inspect_query_step(con, row, step, binding)
                exited = con.execute(
                    "SELECT * FROM worker_executions WHERE step_id=? AND run_id=? AND attempt_id=?",
                    (step_id, run_id, attempt_id),
                ).fetchone()
                if not self._query_worker_success(exited):
                    raise AnalyticsError(409, "WORKER_NOT_EXITED", "查询步骤尚未有已退出且释放租约的成功执行记录，不能提交结果。")
                encoded = self._encode_query_result(result)
                self._decode_query_result(con, row, step, encoded, binding)
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
        with self._connection(readonly=True) as con:
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:read")
            if row["attempt_id"] != attempt_id:
                raise _conflict()
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=? AND state='SUCCEEDED'",
                               (run_id, attempt_id, step_id)).fetchone()
            if step is None:
                raise _conflict()
            if self.is_query:
                return self._decode_query_result(con, row, step, step["result_json"], binding)
            return AnalyticsB0Result.model_validate_json(step["result_json"])

    def begin_worker(self, principal, run_id, attempt_id, step_id, execution_id, lease_dev, lease_ino):
        """Persist one physical intent while its parent already holds the lease."""
        self._require(principal, "run:create")
        with self._transaction() as con:
            row = self._run(con, principal, run_id)
            binding = self._authorize_run(con, principal, row, "run:create")
            step = con.execute("SELECT * FROM steps WHERE run_id=? AND attempt_id=? AND step_id=?",
                               (run_id, attempt_id, step_id)).fetchone()
            if (row["attempt_id"] != attempt_id or row["status"] != "RUNNING" or row["cancel_reason"]
                    or step is None or step["state"] != "STARTED" or step["deadline_ms"] <= self.clock()):
                raise _conflict()
            if self.is_query:
                self._inspect_query_step(con, row, step, binding)
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
                    self._require(principal, "run:create")
                    if self.is_query:
                        binding = self._inspect_query_run(con, row)
                        if binding.permission_scope != self._permission_scope(principal):
                            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")
                except AnalyticsError as error:
                    if error.status in {401, 403}:
                        allowed = False
                    else:
                        raise
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
                    if self.is_query:
                        run_binding = self._inspect_query_run(con, row)
                        result = self._decode_query_result(con, row, step, step["result_json"], run_binding)
                    else:
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
                if self.is_query:
                    binding = self._inspect_query_run(con, row)
                    for step in con.execute("SELECT * FROM steps WHERE run_id=? ORDER BY rowid", (row["run_id"],)):
                        self._inspect_query_step(con, row, step, binding)
                elif self._request_schema(row) == QUERY_RUN_SCHEMA:
                    raise AnalyticsError(409, "FAMILY_MISMATCH", "任务合同与当前实例不一致。")
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
        with self._connection(readonly=True) as con:
            con.execute("BEGIN")
            row = self._run(con, principal, run_id)
            self._authorize_run(con, principal, row, "run:read")
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
