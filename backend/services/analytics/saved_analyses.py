"""Append-only saved analyses for channel-follow-up SNAPSHOT assets.

Independent SQLite; not the jobs.py run kernel and not an HTTP/OpenAPI surface.
Succeeded runs are a finite mock catalog injected by the caller. Owner always
comes from the server principal. Published versions are never updated in place;
a later same-condition run cannot rewrite SNAPSHOT evidence.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from backend.contracts.analytics_query import (
    B0_RUN_SCHEMA,
    DATA_VERSION,
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_SCHEMA,
    QUERY_VERSION,
    ChannelFollowupFacts,
    ChannelFollowupQueryRequest,
    ChannelFollowupResult,
)
from backend.contracts.analytics_query_run import QUERY_DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.catalog import bind_resolved_filters_from_metadata
from backend.services.analytics.resource_profile import canonical_json, content_hash

ANALYSIS_SCHEMA = "analytics-saved-analysis/v1"
VISUAL_SCHEMA = "analytics-visual-table/v1"
DATA_SCOPE = QUERY_DATA_SCOPE
CAPABILITY_SAVE = "analysis:save"
CAPABILITY_READ = "analysis:read"
APPLICATION_ID = 1397571889  # SMA1; distinct from jobs.py SMB0.
STATE_SCHEMA_VERSION = 1
OPAQUE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_VISUAL = {"schema_version": VISUAL_SCHEMA, "kind": "TABLE"}
SAVE_FIELDS = frozenset({
    "title", "created_from_run_id", "filters", "visual_spec", "query_ref",
    "metric_refs", "owner_id", "visibility", "endorsement",
})
REGISTER_FIELDS = frozenset({
    "run_id", "status", "query_id", "query_version", "metric_id", "metric_version",
    "data_version", "filter_hash", "evidence_digest", "request", "result", "owner_id",
})
B0_SCHEMAS = frozenset({B0_RUN_SCHEMA, "analytics-b0/v1", "analytics-run-b0/v1"})

_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE succeeded_runs (
    run_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    filter_hash TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    query_id TEXT NOT NULL,
    query_version TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    metric_version TEXT NOT NULL,
    data_version TEXT NOT NULL,
    data_snapshot_ref TEXT NOT NULL,
    as_of TEXT NOT NULL,
    created_ms INTEGER NOT NULL
);
CREATE TABLE analyses (
    analysis_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version >= 1),
    owner TEXT NOT NULL,
    title TEXT NOT NULL,
    request_json TEXT NOT NULL,
    visual_json TEXT NOT NULL,
    created_from_run_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    facts_json TEXT NOT NULL,
    limitations_json TEXT NOT NULL,
    filter_hash TEXT NOT NULL,
    data_version TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    PRIMARY KEY(analysis_id, version)
);
CREATE INDEX analyses_owner ON analyses(owner, created_ms, analysis_id);
CREATE TABLE refresh_candidates (
    analysis_id TEXT NOT NULL,
    analysis_version INTEGER NOT NULL,
    candidate_run_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    recorded_ms INTEGER NOT NULL,
    PRIMARY KEY(analysis_id, analysis_version, candidate_run_id),
    FOREIGN KEY(analysis_id, analysis_version) REFERENCES analyses(analysis_id, version)
);
CREATE TABLE idempotency (
    actor TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, key TEXT NOT NULL,
    request_hash TEXT NOT NULL, response_json TEXT NOT NULL, http_status INTEGER NOT NULL,
    PRIMARY KEY(actor, operation, target, key)
);
"""


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _timestamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _missing() -> AnalyticsError:
    return AnalyticsError(404, "NOT_FOUND", "分析不存在或当前身份不可见。")


def _conflict() -> AnalyticsError:
    return AnalyticsError(409, "CONFLICT", "请求、状态或版本已变化，请读取当前分析后核对。")


def _unprocessable(message: str) -> AnalyticsError:
    return AnalyticsError(422, "UNPROCESSABLE", message)


def _invalid(message: str) -> AnalyticsError:
    return AnalyticsError(400, "INVALID_REQUEST", message)


def validate_key(key: str | None) -> str:
    if key is None:
        raise AnalyticsError(428, "IDEMPOTENCY_KEY_REQUIRED", "需要稳定的 Idempotency-Key。")
    if not key or len(key) > 200 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise AnalyticsError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key 格式无效。")
    return key


def _opaque(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not OPAQUE_ID.fullmatch(value):
        raise _invalid(f"{label} 不是合法标识。")
    return value


def _sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise _invalid(f"{label} 不是 SHA-256。")
    return value


def _mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or isinstance(value, bool):
        raise _invalid(f"{label} 必须是对象。")
    return value


def _looks_like_b0(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    schema = payload.get("schema_version")
    if schema in B0_SCHEMAS:
        return True
    if "repeat_rate" in payload or "repeat_customers" in payload:
        return True
    if payload.get("customers") == 100 and payload.get("repeat_customers") == 25:
        return True
    for nested in (payload.get("result"), payload.get("facts"), payload.get("filters")):
        if _looks_like_b0(nested):
            return True
    return False


def _reject_b0(payload: object) -> None:
    if _looks_like_b0(payload):
        raise _unprocessable("B0 固定 fixture 不能保存为渠道后续购买分析。")


def _title(value: object) -> str:
    if not isinstance(value, str):
        raise _invalid("标题必须是文字。")
    title = value.strip()
    if not title or len(title) > 120 or any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise _invalid("标题须为 1–120 个字符，不含控制字符。")
    return title


def _visual_spec(value: object | None) -> dict[str, str]:
    if value is None:
        return dict(DEFAULT_VISUAL)
    payload = _mapping(value, label="visual_spec")
    if payload != DEFAULT_VISUAL:
        raise _unprocessable("本波只允许 TABLE 视觉配置。")
    return dict(DEFAULT_VISUAL)


def _query_ref(value: object | None) -> dict[str, str]:
    expected = {"query_id": QUERY_ID, "query_version": QUERY_VERSION}
    if value is None:
        return expected
    payload = _mapping(value, label="query_ref")
    if payload != expected:
        raise _unprocessable("本波只允许 channel_first_observed_followup / channel-followup-query/v1。")
    return expected


def _metric_refs(value: object | None) -> list[dict[str, str]]:
    expected = [{"metric_id": METRIC_ID, "metric_version": METRIC_VERSION}]
    if value is None:
        return expected
    if value != expected:
        raise _unprocessable("本波只允许 channel_first_observed_n_day_repeat / channel-followup-metric/v1。")
    return expected


def _validate_request(value: object) -> ChannelFollowupQueryRequest:
    _reject_b0(value)
    try:
        request = ChannelFollowupQueryRequest.model_validate(value)
    except ValidationError:
        raise _unprocessable("分析条件不合法或不是完整 ChannelFollowup 请求。") from None
    if request.query_id != QUERY_ID or request.query_version != QUERY_VERSION:
        raise _unprocessable("本波只允许 channel_first_observed_followup / channel-followup-query/v1。")
    if request.metric_id != METRIC_ID or request.metric_version != METRIC_VERSION:
        raise _unprocessable("指标版本与本波合同不一致。")
    if request.schema_version != QUERY_SCHEMA:
        raise _unprocessable("查询 schema 与本波合同不一致。")
    return request


def _validate_result(value: object) -> ChannelFollowupResult:
    _reject_b0(value)
    try:
        result = ChannelFollowupResult.model_validate(value)
    except ValidationError:
        raise _unprocessable("SUCCEEDED 结果不合法，不能保存。") from None
    if result.query_id != QUERY_ID or result.query_version != QUERY_VERSION:
        raise _unprocessable("本波只允许 channel_first_observed_followup / channel-followup-query/v1。")
    if result.metric_id != METRIC_ID or result.metric_version != METRIC_VERSION:
        raise _unprocessable("指标版本与本波合同不一致。")
    if result.data_version != DATA_VERSION:
        raise _unprocessable("数据版本与本波合同不一致。")
    return result


def _assert_request_result(request: ChannelFollowupQueryRequest, result: ChannelFollowupResult) -> None:
    resolved = result.resolved_filters
    expected = bind_resolved_filters_from_metadata(
        request,
        {
            "snapshot_id": result.data_snapshot_ref,
            "data_version": result.data_version,
            "data_digest": resolved.data_digest,
            "as_of": result.as_of,
            "timezone": resolved.timezone,
        },
        resolved.permission_scope,
    )
    if expected.model_dump() != resolved.model_dump():
        raise _unprocessable("运行请求条件与结果的 resolved_filters 不一致。")


@dataclass(frozen=True)
class SavedAnalysisRecord:
    schema_version: str
    analysis_id: str
    version: int
    title: str
    query_ref: dict[str, str]
    metric_refs: list[dict[str, str]]
    filters: dict[str, Any]
    visual_spec: dict[str, str]
    created_from_run_id: str
    owner_id: str
    visibility: str
    endorsement: str
    data_mode: str
    snapshot: dict[str, Any]
    facts: dict[str, Any]
    data_version: str
    filter_hash: str
    limitations: list[str]
    refresh_candidate: dict[str, str] | None
    created_at: str
    finite_mock: bool
    http_api: str

    def binding(self) -> dict[str, Any]:
        """Shared result pointer. Callers must not copy facts per board."""
        snapshot = self.snapshot
        return {
            "analysis_id": self.analysis_id,
            "version": self.version,
            "run_id": snapshot["run_id"],
            "created_from_run_id": self.created_from_run_id,
            "evidence_digest": snapshot["evidence_digest"],
            "filter_hash": self.filter_hash,
            "data_version": self.data_version,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_id": self.analysis_id,
            "version": self.version,
            "title": self.title,
            "query_ref": dict(self.query_ref),
            "metric_refs": [dict(item) for item in self.metric_refs],
            "filters": json.loads(canonical_json(self.filters)),
            "visual_spec": dict(self.visual_spec),
            "created_from_run_id": self.created_from_run_id,
            "owner_id": self.owner_id,
            "visibility": self.visibility,
            "endorsement": self.endorsement,
            "data_mode": self.data_mode,
            "snapshot": json.loads(canonical_json(self.snapshot)),
            "facts": json.loads(canonical_json(self.facts)),
            "data_version": self.data_version,
            "filter_hash": self.filter_hash,
            "limitations": list(self.limitations),
            "refresh_candidate": None if self.refresh_candidate is None else dict(self.refresh_candidate),
            "created_at": self.created_at,
            "finite_mock": True,
            "http_api": "NOT_CONNECTED",
        }


class SavedAnalysisStore:
    """Finite-mock saved-analysis catalog. HTTP/OpenAPI is NOT_CONNECTED."""

    finite_mock = True
    http_api = "NOT_CONNECTED"

    def __init__(self, state_dir: Path, *, clock: Callable[[], int] = _now_ms):
        original = Path(state_dir)
        if original.is_symlink() or not original.is_dir():
            raise ValueError("an existing private saved-analysis directory is required")
        self.directory = original.resolve(strict=True)
        mode = self.directory.stat()
        if mode.st_mode & 0o077 or mode.st_uid != os.getuid():
            raise ValueError("saved-analysis directory must be owned by the caller and mode 0700")
        self.path = self.directory / "analyses.sqlite3"
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
                raise ValueError("refusing unowned or linked saved-analysis initialization lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            existed = self.path.exists() or self.path.is_symlink()
            if existed:
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    raise ValueError("refusing unowned or linked saved-analysis state file")
                with self._connection(readonly=True) as con:
                    if con.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                        raise ValueError("refusing a foreign or incomplete saved-analysis database")
                    if con.execute("PRAGMA user_version").fetchone()[0] != STATE_SCHEMA_VERSION:
                        raise ValueError("saved-analysis schema differs; retain old evidence and use fresh state")
                    kind = con.execute("SELECT value FROM metadata WHERE key = ?", ("kind",)).fetchone()
                    if kind is None or kind[0] != "saved_analysis":
                        raise ValueError("refusing a foreign or incomplete saved-analysis database")
                return
            created = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(created)
            with self._connection() as con:
                con.execute("PRAGMA journal_mode=WAL")
                con.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
                try:
                    con.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    con.execute(f"PRAGMA user_version={STATE_SCHEMA_VERSION}")
                    con.execute("INSERT INTO metadata VALUES (?, ?)", ("kind", "saved_analysis"))
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
    def _connection(self, *, readonly: bool = False):
        if self.path.is_symlink():
            raise ValueError("saved-analysis state file must not be a symlink")
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
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "分析状态暂不可用，请使用原请求标识查询或重试。",
                                 retryable=True) from error

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=DATA_SCOPE)

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
        con.execute(
            "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
            (principal.actor_id, operation, target, key, digest, canonical_json(response), status),
        )

    def register_succeeded_run(self, principal: AnalyticsPrincipal, payload: dict[str, Any]) -> dict[str, Any]:
        """Finite mock of a trusted SUCCEEDED query run. Not jobs.py."""
        self._require(principal, CAPABILITY_SAVE)
        body = _mapping(payload, label="succeeded_run")
        _reject_b0(body)
        extra = set(body) - REGISTER_FIELDS
        if extra:
            raise _invalid("请求包含未声明字段。")
        run_id = _opaque(body.get("run_id"), label="run_id")
        if body.get("status") != "SUCCEEDED":
            raise _unprocessable("只能绑定 SUCCEEDED 运行。")
        if body.get("query_id") != QUERY_ID or body.get("query_version") != QUERY_VERSION:
            raise _unprocessable("本波只允许 channel_first_observed_followup / channel-followup-query/v1。")
        if body.get("metric_id") != METRIC_ID or body.get("metric_version") != METRIC_VERSION:
            raise _unprocessable("指标版本与本波合同不一致。")
        if body.get("data_version") != DATA_VERSION:
            raise _unprocessable("数据版本与本波合同不一致。")
        request = _validate_request(body.get("request"))
        result = _validate_result(body.get("result"))
        _assert_request_result(request, result)
        filter_hash = _sha256(body.get("filter_hash"), label="filter_hash")
        evidence_digest = _sha256(body.get("evidence_digest"), label="evidence_digest")
        if request.query_id != result.query_id or request.query_version != result.query_version:
            raise _unprocessable("运行请求与结果的查询版本不一致。")
        if request.metric_id != result.metric_id or request.metric_version != result.metric_version:
            raise _unprocessable("运行请求与结果的指标版本不一致。")
        if filter_hash != result.filter_hash or filter_hash != result.resolved_filters.filter_hash:
            raise _unprocessable("filter_hash 与已解析条件不一致。")
        dumped_result = result.model_dump(mode="json")
        if content_hash(dumped_result) != evidence_digest:
            raise _unprocessable("evidence_digest 与 SUCCEEDED 结果不一致。")
        if result.data_snapshot_ref != request.data_snapshot_ref:
            raise _unprocessable("data_snapshot_ref 与请求不一致。")
        request_json = canonical_json(request.model_dump(mode="json"))
        result_json = canonical_json(dumped_result)
        as_of = dumped_result["as_of"]
        snapshot_ref = dumped_result["data_snapshot_ref"]
        with self._transaction() as con:
            existing = con.execute("SELECT * FROM succeeded_runs WHERE run_id=?", (run_id,)).fetchone()
            if existing is not None:
                if existing["owner"] != principal.actor_id:
                    raise _missing()
                same = (
                    existing["request_json"] == request_json
                    and existing["result_json"] == result_json
                    and existing["evidence_digest"] == evidence_digest
                    and existing["filter_hash"] == filter_hash
                )
                if not same:
                    raise _conflict()
                return {"run_id": run_id, "owner_id": principal.actor_id, "status": "SUCCEEDED"}
            con.execute(
                """INSERT INTO succeeded_runs (
                    run_id, owner, request_json, result_json, filter_hash, evidence_digest,
                    query_id, query_version, metric_id, metric_version, data_version,
                    data_snapshot_ref, as_of, created_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id, principal.actor_id, request_json, result_json, filter_hash, evidence_digest,
                    result.query_id, result.query_version, result.metric_id, result.metric_version,
                    result.data_version, snapshot_ref, as_of, self.clock(),
                ),
            )
        return {"run_id": run_id, "owner_id": principal.actor_id, "status": "SUCCEEDED"}

    def save_from_trusted_source(
        self, principal: AnalyticsPrincipal, key: str, *, title: str, visual_spec: dict[str, str] | None,
        trusted: dict[str, Any],
    ) -> SavedAnalysisRecord:
        """Persist from a server-resolved SUCCEEDED run. Not a public register route.

        register_succeeded_run and save are sequential analysis-DB transactions.
        A save failure may leave a valid trusted-source row; this is not
        cross-RunStore / analysis-store atomicity. HTTP callers still
        re-authorize and re-resolve the authoritative source on every request.
        """
        self._require(principal, CAPABILITY_SAVE)
        key = validate_key(key)
        title = _title(title)
        visual = _visual_spec(visual_spec)
        query_ref = _query_ref(None)
        metric_refs = _metric_refs(None)
        ingested = self.register_succeeded_run(principal, {
            "run_id": trusted["run_id"], "status": trusted["status"],
            "query_id": trusted["query_id"], "query_version": trusted["query_version"],
            "metric_id": trusted["metric_id"], "metric_version": trusted["metric_version"],
            "data_version": trusted["data_version"], "filter_hash": trusted["filter_hash"],
            "evidence_digest": trusted["evidence_digest"], "request": trusted["request"],
            "result": trusted["result"],
        })
        if ingested["owner_id"] != principal.actor_id or ingested["run_id"] != trusted["run_id"]:
            raise _missing()
        return self.save(principal, key, {
            "title": title,
            "created_from_run_id": trusted["run_id"],
            "filters": trusted["request"],
            "visual_spec": visual,
            "query_ref": query_ref,
            "metric_refs": metric_refs,
        })

    def save(self, principal: AnalyticsPrincipal, key: str, payload: dict[str, Any]) -> SavedAnalysisRecord:
        self._require(principal, CAPABILITY_SAVE)
        key = validate_key(key)
        body = _mapping(payload, label="save")
        _reject_b0(body)
        extra = set(body) - SAVE_FIELDS
        if extra:
            raise _invalid("请求包含未声明字段。")
        title = _title(body.get("title"))
        run_id = _opaque(body.get("created_from_run_id"), label="created_from_run_id")
        visual = _visual_spec(body.get("visual_spec"))
        query_ref = _query_ref(body.get("query_ref"))
        metric_refs = _metric_refs(body.get("metric_refs"))
        if "filters" not in body:
            raise _invalid("保存必须提供完整 filters。")
        request = _validate_request(body.get("filters"))
        digest = content_hash({
            "title": title,
            "created_from_run_id": run_id,
            "filters": request.model_dump(mode="json"),
            "visual_spec": visual,
            "query_ref": query_ref,
            "metric_refs": metric_refs,
        })
        with self._transaction() as con:
            prior = self._prior(con, principal, "analysis:save", "", key, digest)
            if prior is not None:
                return SavedAnalysisRecord(**json.loads(prior["response_json"]))
            run = self._run(con, principal, run_id)
            self._assert_bindable(run, request, query_ref, metric_refs)
            analysis_id = _id("analysis")
            created_ms = self.clock()
            record = self._insert_analysis(
                con, principal, analysis_id, 1, title, request, visual, run, created_ms,
            )
            response = record.as_dict()
            self._remember(con, principal, "analysis:save", "", key, digest, response, 201)
            return SavedAnalysisRecord(**response)

    def publish_version(
        self,
        principal: AnalyticsPrincipal,
        key: str,
        analysis_id: str,
        *,
        base_version: int,
        title: str | None = None,
        snapshot_run_id: str | None = None,
    ) -> SavedAnalysisRecord:
        self._require(principal, CAPABILITY_SAVE)
        key = validate_key(key)
        analysis_id = _opaque(analysis_id, label="analysis_id")
        if type(base_version) is not int or base_version < 1:
            raise _invalid("base_version 必须是从 1 起的整数。")
        if title is None and snapshot_run_id is None:
            raise _invalid("新版本必须改标题或确认 SNAPSHOT 引用。")
        new_title = None if title is None else _title(title)
        candidate_id = None if snapshot_run_id is None else _opaque(snapshot_run_id, label="snapshot_run_id")
        digest = content_hash({
            "analysis_id": analysis_id,
            "base_version": base_version,
            "title": new_title,
            "snapshot_run_id": candidate_id,
        })
        with self._transaction() as con:
            prior = self._prior(con, principal, "analysis:version", analysis_id, key, digest)
            if prior is not None:
                return SavedAnalysisRecord(**json.loads(prior["response_json"]))
            row = self._analysis_row(con, principal, analysis_id, base_version)
            latest = con.execute(
                "SELECT MAX(version) FROM analyses WHERE analysis_id=? AND owner=?",
                (analysis_id, principal.actor_id),
            ).fetchone()[0]
            if latest != base_version:
                raise _conflict()
            request = ChannelFollowupQueryRequest.model_validate(json.loads(row["request_json"]))
            visual = json.loads(row["visual_json"])
            title_value = new_title if new_title is not None else row["title"]
            run = self._run(con, principal, row["created_from_run_id"])
            if candidate_id is not None:
                candidate = con.execute(
                    """SELECT * FROM refresh_candidates
                       WHERE analysis_id=? AND analysis_version=? AND candidate_run_id=?""",
                    (analysis_id, base_version, candidate_id),
                ).fetchone()
                if candidate is None:
                    raise _unprocessable("只能确认已记录的刷新候选，不能原地改写 SNAPSHOT。")
                run = self._run(con, principal, candidate_id)
                self._assert_bindable(run, request, _query_ref(None), _metric_refs(None))
                if run["filter_hash"] != row["filter_hash"]:
                    raise _unprocessable("刷新候选与已保存条件不一致。")
            created_ms = self.clock()
            record = self._insert_analysis(
                con, principal, analysis_id, base_version + 1, title_value, request, visual, run, created_ms,
            )
            response = record.as_dict()
            self._remember(con, principal, "analysis:version", analysis_id, key, digest, response, 201)
            return SavedAnalysisRecord(**response)

    def record_refresh_candidate(
        self, principal: AnalyticsPrincipal, analysis_id: str, version: int, candidate_run_id: str,
    ) -> dict[str, Any]:
        self._require(principal, CAPABILITY_SAVE)
        analysis_id = _opaque(analysis_id, label="analysis_id")
        candidate_run_id = _opaque(candidate_run_id, label="candidate_run_id")
        if type(version) is not int or version < 1:
            raise _invalid("version 必须是从 1 起的整数。")
        with self._transaction() as con:
            row = self._analysis_row(con, principal, analysis_id, version)
            snapshot = json.loads(row["snapshot_json"])
            if candidate_run_id == snapshot["run_id"]:
                raise _unprocessable("候选 run 不能就是当前 SNAPSHOT。")
            run = self._run(con, principal, candidate_run_id)
            request = ChannelFollowupQueryRequest.model_validate(json.loads(row["request_json"]))
            self._assert_bindable(run, request, _query_ref(None), _metric_refs(None))
            if run["filter_hash"] != row["filter_hash"]:
                raise _unprocessable("刷新候选必须与已保存 filter_hash/query/metric/data 版本一致。")
            existing = con.execute(
                """SELECT * FROM refresh_candidates
                   WHERE analysis_id=? AND analysis_version=? AND candidate_run_id=?""",
                (analysis_id, version, candidate_run_id),
            ).fetchone()
            if existing is None:
                con.execute(
                    """INSERT INTO refresh_candidates
                       VALUES (?, ?, ?, ?, ?)""",
                    (analysis_id, version, candidate_run_id, run["evidence_digest"], self.clock()),
                )
            elif existing["evidence_digest"] != run["evidence_digest"]:
                raise _conflict()
            frozen = json.loads(row["snapshot_json"])
            if frozen != snapshot or frozen["run_id"] != snapshot["run_id"]:
                raise _conflict()
        return {
            "analysis_id": analysis_id,
            "version": version,
            "candidate_run_id": candidate_run_id,
            "snapshot_run_id": snapshot["run_id"],
            "snapshot_rewritten": False,
        }

    def find_latest_for_run(self, principal: AnalyticsPrincipal, run_id: str) -> SavedAnalysisRecord | None:
        """Owner-scoped SNAPSHOT bound to a SUCCEEDED run. None if not saved yet."""
        self._require(principal, CAPABILITY_READ)
        run_id = _opaque(run_id, label="run_id")
        with self._connection(readonly=True) as con:
            row = con.execute(
                """SELECT * FROM analyses WHERE owner=? AND created_from_run_id=?
                   ORDER BY created_ms DESC, version DESC, analysis_id DESC LIMIT 1""",
                (principal.actor_id, run_id),
            ).fetchone()
            if row is None:
                return None
            return self._record(con, row)

    def get(
        self, principal: AnalyticsPrincipal, analysis_id: str, version: int | None = None,
    ) -> SavedAnalysisRecord:
        self._require(principal, CAPABILITY_READ)
        analysis_id = _opaque(analysis_id, label="analysis_id")
        if version is not None and (type(version) is not int or version < 1):
            raise _invalid("version 必须是从 1 起的整数。")
        with self._connection(readonly=True) as con:
            row = self._analysis_row(con, principal, analysis_id, version)
            return self._record(con, row)

    def list(self, principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
        self._require(principal, CAPABILITY_READ)
        with self._connection(readonly=True) as con:
            rows = con.execute(
                """SELECT a.* FROM analyses a
                   JOIN (
                       SELECT analysis_id, MAX(version) AS version
                       FROM analyses WHERE owner=? GROUP BY analysis_id
                   ) latest
                     ON a.analysis_id=latest.analysis_id AND a.version=latest.version
                   WHERE a.owner=?
                   ORDER BY a.created_ms DESC, a.analysis_id""",
                (principal.actor_id, principal.actor_id),
            ).fetchall()
            return [self._list_item(con, row) for row in rows]

    @staticmethod
    def _run(con, principal: AnalyticsPrincipal, run_id: str):
        row = con.execute(
            "SELECT * FROM succeeded_runs WHERE run_id=? AND owner=?",
            (run_id, principal.actor_id),
        ).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _analysis_row(con, principal: AnalyticsPrincipal, analysis_id: str, version: int | None):
        if version is None:
            row = con.execute(
                """SELECT * FROM analyses WHERE analysis_id=? AND owner=?
                   ORDER BY version DESC LIMIT 1""",
                (analysis_id, principal.actor_id),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM analyses WHERE analysis_id=? AND owner=? AND version=?",
                (analysis_id, principal.actor_id, version),
            ).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _assert_bindable(run, request: ChannelFollowupQueryRequest, query_ref, metric_refs) -> None:
        stored = ChannelFollowupQueryRequest.model_validate(json.loads(run["request_json"]))
        result = ChannelFollowupResult.model_validate(json.loads(run["result_json"]))
        _assert_request_result(request, result)
        if canonical_json(stored.model_dump(mode="json")) != canonical_json(request.model_dump(mode="json")):
            raise _unprocessable("filters 必须与 SUCCEEDED 运行的完整条件一致。")
        if run["query_id"] != query_ref["query_id"] or run["query_version"] != query_ref["query_version"]:
            raise _unprocessable("query_ref 必须与 SUCCEEDED 运行一致。")
        if run["metric_id"] != metric_refs[0]["metric_id"] or run["metric_version"] != metric_refs[0]["metric_version"]:
            raise _unprocessable("metric_refs 必须与 SUCCEEDED 运行一致。")
        if run["data_version"] != result.data_version or run["data_version"] != DATA_VERSION:
            raise _unprocessable("data 版本必须与 SUCCEEDED 运行一致。")
        if run["filter_hash"] != result.filter_hash:
            raise _unprocessable("filter_hash 必须与 SUCCEEDED 运行一致。")

    def _insert_analysis(
        self, con, principal, analysis_id, version, title, request, visual, run, created_ms,
    ) -> SavedAnalysisRecord:
        result = ChannelFollowupResult.model_validate(json.loads(run["result_json"]))
        resolved = result.resolved_filters.model_dump(mode="json")
        snapshot = {
            "run_id": run["run_id"],
            "evidence_digest": run["evidence_digest"],
            "resolved_filters": resolved,
            "data_snapshot_ref": run["data_snapshot_ref"],
            "as_of": run["as_of"],
        }
        facts = ChannelFollowupFacts.model_validate(result.facts.model_dump(mode="json")).model_dump(mode="json")
        con.execute(
            """INSERT INTO analyses (
                analysis_id, version, owner, title, request_json, visual_json, created_from_run_id,
                snapshot_json, facts_json, limitations_json, filter_hash, data_version, created_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id, version, principal.actor_id, title,
                canonical_json(request.model_dump(mode="json")), canonical_json(visual),
                run["run_id"], canonical_json(snapshot), canonical_json(facts),
                canonical_json(list(result.limitations)), run["filter_hash"], run["data_version"], created_ms,
            ),
        )
        row = con.execute(
            "SELECT * FROM analyses WHERE analysis_id=? AND version=?",
            (analysis_id, version),
        ).fetchone()
        return self._record(con, row)

    @staticmethod
    def _candidate(con, row) -> dict[str, str] | None:
        found = con.execute(
            """SELECT candidate_run_id, evidence_digest FROM refresh_candidates
               WHERE analysis_id=? AND analysis_version=?
               ORDER BY recorded_ms DESC, candidate_run_id LIMIT 1""",
            (row["analysis_id"], row["version"]),
        ).fetchone()
        if found is None:
            return None
        return {"run_id": found["candidate_run_id"], "evidence_digest": found["evidence_digest"]}

    def _record(self, con, row) -> SavedAnalysisRecord:
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
        return SavedAnalysisRecord(
            schema_version=ANALYSIS_SCHEMA,
            analysis_id=row["analysis_id"],
            version=row["version"],
            title=row["title"],
            query_ref={"query_id": request["query_id"], "query_version": request["query_version"]},
            metric_refs=[{"metric_id": request["metric_id"], "metric_version": request["metric_version"]}],
            filters=request,
            visual_spec=json.loads(row["visual_json"]),
            created_from_run_id=row["created_from_run_id"],
            owner_id=row["owner"],
            visibility="PRIVATE",
            endorsement="PERSONAL",
            data_mode="SNAPSHOT",
            snapshot=snapshot,
            facts=json.loads(row["facts_json"]),
            data_version=row["data_version"],
            filter_hash=row["filter_hash"],
            limitations=json.loads(row["limitations_json"]),
            refresh_candidate=self._candidate(con, row),
            created_at=_timestamp(row["created_ms"]),
            finite_mock=True,
            http_api="NOT_CONNECTED",
        )

    def _list_item(self, con, row) -> dict[str, Any]:
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
        candidate = self._candidate(con, row)
        return {
            "schema_version": ANALYSIS_SCHEMA,
            "analysis_id": row["analysis_id"],
            "version": row["version"],
            "title": row["title"],
            "query_id": request["query_id"],
            "observation_days": request["observation_days"],
            "cohort_window": request["cohort_window"],
            "as_of": snapshot["as_of"],
            "data_mode": "SNAPSHOT",
            "visibility": "PRIVATE",
            "refreshable": candidate is not None,
            "finite_mock": True,
            "http_api": "NOT_CONNECTED",
        }
