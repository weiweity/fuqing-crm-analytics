"""Immutable computed snapshots. No model dispatch, client facts or state migration."""
from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from backend.contracts.competition_computed import CompetitionComputedResult, DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.cockpit import PLUGIN_TABLE
from backend.services.analytics.first_purchase.asset_state import (
    connect, initialize_sqlite, now_ms, opaque, timestamp, transaction,
)
from backend.services.analytics.resource_profile import canonical_json, content_hash
from backend.services.analytics.saved_analyses import SavedAnalysisRecord

APPLICATION_ID = 1397572679  # SMDG, independent from existing asset families.
UNAVAILABLE = "诊断结果状态暂不可用，请保留原请求标识重试。"
DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE results (
    run_id TEXT PRIMARY KEY,
    analysis_id TEXT UNIQUE,
    owner TEXT NOT NULL,
    session_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    UNIQUE(owner, session_id, request_id)
);
CREATE INDEX result_owner ON results(owner, created_ms, run_id);
"""


def is_computed_reference(analysis_id: str | None, run_id: str | None = None) -> bool:
    return bool((analysis_id or "").startswith("analysis_diag_") or (run_id or "").startswith("run_diag_"))


class ComputedResultStore:
    def __init__(self, directory: Path):
        self.path = directory.resolve() / "diagnosis_results.sqlite3"
        initialize_sqlite(directory, self.path, application_id=APPLICATION_ID, schema_version=1,
                          kind="competition_computed_results", ddl=DDL, unavailable=UNAVAILABLE)

    @contextmanager
    def _read(self):
        try:
            with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as conn:
                yield conn
        except sqlite3.DatabaseError as error:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", UNAVAILABLE, retryable=True) from error

    @staticmethod
    def _missing():
        return AnalyticsError(404, "NOT_FOUND", "诊断结果不存在或当前身份不可见。")

    @staticmethod
    def _parse(row, principal) -> CompetitionComputedResult:
        if row is None or row["owner"] != principal.actor_id:
            raise ComputedResultStore._missing()
        try:
            result = CompetitionComputedResult.model_validate_json(row["result_json"])
            execution = content_hash([row["owner"], row["session_id"], row["request_id"]])[:48]
            if (result.resolved_condition.actor_id != principal.actor_id or result.run_id != row["run_id"]
                    or result.analysis_id != row["analysis_id"]
                    or result.run_id != "run_diag_" + execution
                    or result.result_id != "result_diag_" + execution
                    or result.analysis_id != ("analysis_diag_" + execution if result.completeness.value == "COMPLETE" else None)):
                raise ValueError("stored execution binding differs")
            return result
        except (ValueError, TypeError, ValidationError) as error:
            raise AnalyticsError(409, "BINDING_CORRUPT", "诊断快照与冻结证据不一致。") from error

    def prior(self, principal: AnalyticsPrincipal, session_id: str, request_id: str, request_hash: str):
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        with self._read() as conn:
            self._require_active(conn, principal, session_id, request_id)
            row = conn.execute("SELECT * FROM results WHERE owner=? AND session_id=? AND request_id=?",
                               (principal.actor_id, session_id, request_id)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise AnalyticsError(409, "CONFLICT", "同一诊断请求标识的条件已变化，请使用新的请求标识。")
        return self._parse(row, principal)

    @staticmethod
    def _cancel_key(principal, session_id, request_id):
        opaque(session_id, label="session_id")
        opaque(request_id, label="request_id")
        return "cancel:" + canonical_json([principal.actor_id, session_id, request_id])

    @classmethod
    def _require_active(cls, conn, principal, session_id, request_id):
        key = cls._cancel_key(principal, session_id, request_id)
        if conn.execute("SELECT 1 FROM metadata WHERE key=?", (key,)).fetchone():
            raise AnalyticsError(409, "CANCELLED", "本次诊断已取消，未发布结果；继续诊断请使用新的请求标识。")

    def require_active(self, principal, session_id, request_id):
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        with self._read() as conn:
            self._require_active(conn, principal, session_id, request_id)

    def cancel(self, principal, session_id, request_id):
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        key = self._cancel_key(principal, session_id, request_id)
        # Existing metadata namespace, no migration. The same write transaction
        # as save() arbitrates cancellation vs publication, including restarts.
        with transaction(self.path, unavailable=UNAVAILABLE) as conn:
            row = conn.execute("SELECT * FROM results WHERE owner=? AND session_id=? AND request_id=?",
                               (principal.actor_id, session_id, request_id)).fetchone()
            if row is not None:
                self._parse(row, principal)
                raise AnalyticsError(409, "ALREADY_PUBLISHED", "诊断结果已保存，取消不会撤销已保存的证据。")
            conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES (?,?)", (key, "true"))
        return {"session_id": session_id, "request_id": request_id, "status": "CANCELLED", "late_attempt_publish": False}

    def save(self, principal: AnalyticsPrincipal, session_id: str, request_id: str,
             request_hash: str, result: CompetitionComputedResult):
        require(principal, "analysis:save", data_scope=DATA_SCOPE)
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        opaque(session_id, label="session_id")
        opaque(request_id, label="request_id")
        result = CompetitionComputedResult.model_validate(result.model_dump(mode="json"))
        if result.resolved_condition.actor_id != principal.actor_id:
            raise AnalyticsError(403, "FORBIDDEN", "计算期间身份已变化，未保存诊断结果。")
        execution = content_hash([principal.actor_id, session_id, request_id])[:48]
        if result.run_id != "run_diag_" + execution or result.result_id != "result_diag_" + execution:
            raise AnalyticsError(409, "BINDING_CORRUPT", "诊断结果与当前会话和请求标识不一致。")
        payload = result.model_dump(mode="json")
        payload["analysis_id"] = "analysis_diag_" + result.run_id.removeprefix("run_diag_") if result.completeness.value == "COMPLETE" else None
        stored = CompetitionComputedResult.model_validate(payload)
        with transaction(self.path, unavailable=UNAVAILABLE) as conn:
            self._require_active(conn, principal, session_id, request_id)
            row = conn.execute("SELECT * FROM results WHERE owner=? AND session_id=? AND request_id=?",
                               (principal.actor_id, session_id, request_id)).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    raise AnalyticsError(409, "CONFLICT", "同一诊断请求标识的条件已变化，请使用新的请求标识。")
                return self._parse(row, principal)
            conn.execute("INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (stored.run_id, stored.analysis_id, principal.actor_id, session_id, request_id,
                          request_hash, canonical_json(stored.model_dump(mode="json")), now_ms()))
        return stored

    def list_results(self, principal: AnalyticsPrincipal, *, limit=100, offset=0):
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise AnalyticsError(422, "INVALID_REQUEST", "诊断结果分页参数无效。")
        with self._read() as conn:
            rows = conn.execute("SELECT * FROM results WHERE owner=? AND analysis_id IS NOT NULL ORDER BY created_ms DESC, run_id LIMIT ? OFFSET ?",
                                (principal.actor_id, limit, offset)).fetchall()
        return [self._parse(row, principal).model_dump(mode="json") for row in rows]

    def get(self, principal: AnalyticsPrincipal, analysis_id: str, version=1) -> SavedAnalysisRecord:
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        opaque(analysis_id, label="analysis_id")
        if type(version) is not int or version != 1:
            raise self._missing()
        with self._read() as conn:
            row = conn.execute("SELECT * FROM results WHERE owner=? AND analysis_id=?", (principal.actor_id, analysis_id)).fetchone()
        result = self._parse(row, principal)
        resolved = result.resolved_condition.model_dump(mode="json")
        return SavedAnalysisRecord(
            schema_version="competition-computed-analysis/v1", analysis_id=analysis_id, version=1,
            title=f"GSV {resolved['current_period']['start_date']}–{resolved['current_period']['end_date']}",
            query_ref={"query_id": result.query_id, "query_version": result.query_version},
            metric_refs=[{"metric_id": result.metric_id, "metric_version": result.metric_version}],
            filters=resolved, visual_spec={"schema_version": "analytics-visual-table/v1", "kind": "TABLE"},
            created_from_run_id=result.run_id, owner_id=principal.actor_id, visibility="PRIVATE", endorsement="NONE",
            data_mode="SNAPSHOT", snapshot={"run_id": result.run_id, "as_of": resolved["as_of"],
                "evidence_digest": result.evidence_digest, "data_snapshot_ref": resolved["data_snapshot_ref"],
                "resolved_filters": resolved, "computed_result": result.model_dump(mode="json")},
            facts=result.facts.model_dump(mode="json"), data_version=resolved["data_version"], filter_hash=resolved["filter_hash"],
            limitations=list(result.limitations), refresh_candidate=None, created_at=timestamp(row["created_ms"]),
            finite_mock=True, http_api="CONNECTED")

    def resolve_endorsed(self, principal, ref):
        require(principal, "analysis:read", data_scope=DATA_SCOPE)
        if ref.analysis_id is None:
            with self._read() as conn:
                row = conn.execute("SELECT analysis_id FROM results WHERE owner=? AND run_id=?", (principal.actor_id, ref.run_id)).fetchone()
            if row is None or row["analysis_id"] is None:
                raise self._missing()
            analysis_id = row["analysis_id"]
        else:
            analysis_id = ref.analysis_id
        record = self.get(principal, analysis_id)
        result = record.snapshot["computed_result"]
        if any(result[key] != getattr(ref, key) for key in ("result_id", "run_id", "evidence_digest", "completeness")):
            raise AnalyticsError(409, "BINDING_CORRUPT", "认可引用与已保存的诊断事实不一致。")
        return {**record.binding(), "result_id": result["result_id"], "completeness": "COMPLETE",
                "snapshot": record.snapshot, "facts": record.facts, "limitations": record.limitations}

    def resolve_card(self, principal, analysis_id, version):
        record = self.get(principal, analysis_id, version)
        return {"analysis_ref": {"analysis_id": analysis_id, "version": version}, "snapshot": record.snapshot,
                "facts": record.facts, "limitations": record.limitations, "plugin_ref": dict(PLUGIN_TABLE),
                "filter_hash": record.filter_hash}
