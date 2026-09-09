"""Append-only saved analyses for first-purchase SNAPSHOT assets.

Independent SQLite; not the jobs.py run kernel and not an HTTP/OpenAPI surface.
Facts are copied from a server-resolved SUCCEEDED operating result. Reopen
reads this store, not RunStore. Owner always comes from the server principal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from backend.contracts.analytics_first_purchase import (
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_VERSION,
    FirstPurchaseFacts,
    FirstPurchaseQueryRequest,
    FirstPurchaseResult,
)
from backend.contracts.analytics_first_purchase_run import FIRST_PURCHASE_DATA_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, require
from backend.services.analytics.first_purchase.asset_state import (
    conflict,
    connect,
    initialize_sqlite,
    invalid,
    mapping,
    missing,
    new_id,
    now_ms,
    opaque,
    prior_row,
    reject_foreign_family,
    remember,
    timestamp,
    title_text,
    transaction,
    unprocessable,
    validate_key,
)
from backend.services.analytics.first_purchase.source import FirstPurchaseTrustedSource
from backend.services.analytics.resource_profile import canonical_json, content_hash

ANALYSIS_SCHEMA = "analytics-first-purchase-saved-analysis/v1"
VISUAL_SCHEMA = "analytics-visual-table/v1"
DATA_SCOPE = FIRST_PURCHASE_DATA_SCOPE
CAPABILITY_SAVE = "analysis:save"
CAPABILITY_READ = "analysis:read"
APPLICATION_ID = 1397572502  # SMF1; distinct from SMA1/SMC1/SMB0.
STATE_SCHEMA_VERSION = 1
KIND = "first_purchase_saved_analysis"
UNAVAILABLE = "分析状态暂不可用，请使用原请求标识查询或重试。"
DEFAULT_VISUAL = {"schema_version": VISUAL_SCHEMA, "kind": "TABLE"}
QUERY_REF = {"query_id": QUERY_ID, "query_version": QUERY_VERSION}
METRIC_REFS = [{"metric_id": METRIC_ID, "metric_version": METRIC_VERSION}]

_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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
    evidence_digest TEXT NOT NULL,
    created_ms INTEGER NOT NULL,
    PRIMARY KEY(analysis_id, version)
);
CREATE INDEX analyses_owner ON analyses(owner, created_ms, analysis_id);
CREATE TABLE idempotency (
    actor TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL, key TEXT NOT NULL,
    request_hash TEXT NOT NULL, response_json TEXT NOT NULL, http_status INTEGER NOT NULL,
    PRIMARY KEY(actor, operation, target, key)
);
"""


def _visual_spec(value: object | None) -> dict[str, str]:
    if value is None:
        return dict(DEFAULT_VISUAL)
    payload = mapping(value, label="visual_spec")
    if payload != DEFAULT_VISUAL:
        raise unprocessable("本波只允许 TABLE 视觉配置。")
    return dict(DEFAULT_VISUAL)


@dataclass(frozen=True)
class FirstPurchaseSavedAnalysisRecord:
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
    created_at: str
    finite_mock: bool
    http_api: str

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
            "created_at": self.created_at,
            "finite_mock": True,
            "http_api": "NOT_CONNECTED",
        }


class FirstPurchaseSavedAnalysisStore:
    """Finite-mock first-purchase SNAPSHOT catalog. HTTP/OpenAPI is NOT_CONNECTED."""

    finite_mock = True
    http_api = "NOT_CONNECTED"

    def __init__(self, state_dir: Path, *, clock: Callable[[], int] = now_ms):
        original = Path(state_dir)
        self.directory = original.resolve(strict=True)
        self.path = self.directory / "first_purchase_analyses.sqlite3"
        self.clock = clock
        initialize_sqlite(
            original, self.path, application_id=APPLICATION_ID, schema_version=STATE_SCHEMA_VERSION,
            kind=KIND, ddl=_SCHEMA, unavailable=UNAVAILABLE,
        )

    def close(self) -> None:
        """Connections are per-call; callers drop the instance before reopen."""

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=DATA_SCOPE)

    def save_from_trusted_source(
        self,
        principal: AnalyticsPrincipal,
        key: str,
        *,
        title: str,
        visual_spec: dict[str, str] | None,
        trusted: FirstPurchaseTrustedSource,
    ) -> FirstPurchaseSavedAnalysisRecord:
        """Persist frozen SNAPSHOT facts from a server-resolved operating result."""
        self._require(principal, CAPABILITY_SAVE)
        key = validate_key(key)
        title = title_text(title)
        visual = _visual_spec(visual_spec)
        if trusted.owner_id != principal.actor_id:
            raise missing("analysis")
        reject_foreign_family(trusted.result)
        reject_foreign_family(trusted.request)
        try:
            request = FirstPurchaseQueryRequest.model_validate(trusted.request)
            result = FirstPurchaseResult.model_validate(trusted.result)
        except ValidationError as error:
            raise unprocessable("SUCCEEDED 结果不合法，不能保存。") from error
        if result.status != "OK" or result.facts is None:
            raise unprocessable("SUCCEEDED 但结果 REJECTED 或 facts 为空，不能保存为有效经营分析。")
        if content_hash(result.model_dump(mode="json")) != trusted.evidence_digest:
            raise unprocessable("evidence_digest 与 SUCCEEDED 结果不一致。")
        digest = content_hash({
            "title": title,
            "created_from_run_id": trusted.run_id,
            "filters": request.model_dump(mode="json"),
            "visual_spec": visual,
            "query_ref": QUERY_REF,
            "metric_refs": METRIC_REFS,
            "evidence_digest": trusted.evidence_digest,
        })
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            prior = prior_row(con, principal, "analysis:save", "", key, digest, kind="analysis")
            if prior is not None:
                return FirstPurchaseSavedAnalysisRecord(**json.loads(prior["response_json"]))
            analysis_id = new_id("analysis")
            created_ms = self.clock()
            record = self._insert(
                con, principal, analysis_id, 1, title, request, visual, trusted, result, created_ms,
            )
            response = record.as_dict()
            remember(con, principal, "analysis:save", "", key, digest, response, 201, canonical_json)
            return FirstPurchaseSavedAnalysisRecord(**response)

    def publish_version(
        self,
        principal: AnalyticsPrincipal,
        key: str,
        analysis_id: str,
        *,
        base_version: int,
        title: str,
    ) -> FirstPurchaseSavedAnalysisRecord:
        self._require(principal, CAPABILITY_SAVE)
        key = validate_key(key)
        analysis_id = opaque(analysis_id, label="analysis_id")
        if type(base_version) is not int or base_version < 1:
            raise invalid("base_version 必须是从 1 起的整数。")
        new_title = title_text(title)
        digest = content_hash({
            "analysis_id": analysis_id,
            "base_version": base_version,
            "title": new_title,
        })
        with transaction(self.path, unavailable=UNAVAILABLE) as con:
            prior = prior_row(con, principal, "analysis:version", analysis_id, key, digest, kind="analysis")
            if prior is not None:
                return FirstPurchaseSavedAnalysisRecord(**json.loads(prior["response_json"]))
            row = self._analysis_row(con, principal, analysis_id, base_version)
            latest = con.execute(
                "SELECT MAX(version) FROM analyses WHERE analysis_id=? AND owner=?",
                (analysis_id, principal.actor_id),
            ).fetchone()[0]
            if latest != base_version:
                raise conflict("analysis")
            request = FirstPurchaseQueryRequest.model_validate(json.loads(row["request_json"]))
            visual = json.loads(row["visual_json"])
            snapshot = json.loads(row["snapshot_json"])
            facts = FirstPurchaseFacts.model_validate(json.loads(row["facts_json"]))
            created_ms = self.clock()
            con.execute(
                """INSERT INTO analyses (
                    analysis_id, version, owner, title, request_json, visual_json, created_from_run_id,
                    snapshot_json, facts_json, limitations_json, filter_hash, data_version,
                    evidence_digest, created_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id, base_version + 1, principal.actor_id, new_title,
                    row["request_json"], canonical_json(visual), row["created_from_run_id"],
                    row["snapshot_json"], row["facts_json"], row["limitations_json"],
                    row["filter_hash"], row["data_version"], row["evidence_digest"], created_ms,
                ),
            )
            stored = self._analysis_row(con, principal, analysis_id, base_version + 1)
            record = self._record(stored)
            if record.snapshot != snapshot or record.facts != facts.model_dump(mode="json"):
                raise conflict("analysis")
            if canonical_json(record.filters) != canonical_json(request.model_dump(mode="json")):
                raise conflict("analysis")
            response = record.as_dict()
            remember(con, principal, "analysis:version", analysis_id, key, digest, response, 201, canonical_json)
            return FirstPurchaseSavedAnalysisRecord(**response)

    def get(
        self, principal: AnalyticsPrincipal, analysis_id: str, version: int | None = None,
    ) -> FirstPurchaseSavedAnalysisRecord:
        self._require(principal, CAPABILITY_READ)
        analysis_id = opaque(analysis_id, label="analysis_id")
        if version is not None and (type(version) is not int or version < 1):
            raise invalid("version 必须是从 1 起的整数。")
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
            return self._record(self._analysis_row(con, principal, analysis_id, version))

    def list(self, principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
        self._require(principal, CAPABILITY_READ)
        with connect(self.path, readonly=True, unavailable=UNAVAILABLE) as con:
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
            return [self._list_item(row) for row in rows]

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
            raise missing("analysis")
        return row

    def _insert(
        self, con, principal, analysis_id, version, title, request, visual, trusted, result, created_ms,
    ) -> FirstPurchaseSavedAnalysisRecord:
        facts = FirstPurchaseFacts.model_validate(result.facts.model_dump(mode="json")).model_dump(mode="json")
        snapshot = {
            "run_id": trusted.run_id,
            "evidence_digest": trusted.evidence_digest,
            "resolved_filters": result.resolved_filters.model_dump(mode="json"),
            "data_snapshot_ref": result.data_snapshot_ref,
            "as_of": result.model_dump(mode="json")["as_of"],
        }
        con.execute(
            """INSERT INTO analyses (
                analysis_id, version, owner, title, request_json, visual_json, created_from_run_id,
                snapshot_json, facts_json, limitations_json, filter_hash, data_version,
                evidence_digest, created_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id, version, principal.actor_id, title,
                canonical_json(request.model_dump(mode="json")), canonical_json(visual),
                trusted.run_id, canonical_json(snapshot), canonical_json(facts),
                canonical_json(list(result.limitations)), result.filter_hash, result.data_version,
                trusted.evidence_digest, created_ms,
            ),
        )
        row = con.execute(
            "SELECT * FROM analyses WHERE analysis_id=? AND version=?",
            (analysis_id, version),
        ).fetchone()
        return self._record(row)

    def _record(self, row) -> FirstPurchaseSavedAnalysisRecord:
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
        return FirstPurchaseSavedAnalysisRecord(
            schema_version=ANALYSIS_SCHEMA,
            analysis_id=row["analysis_id"],
            version=row["version"],
            title=row["title"],
            query_ref=dict(QUERY_REF),
            metric_refs=[dict(item) for item in METRIC_REFS],
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
            created_at=timestamp(row["created_ms"]),
            finite_mock=True,
            http_api="NOT_CONNECTED",
        )

    @staticmethod
    def _list_item(row) -> dict[str, Any]:
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
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
            "finite_mock": True,
            "http_api": "NOT_CONNECTED",
        }
