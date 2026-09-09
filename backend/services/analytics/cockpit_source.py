"""Resolve a saved SNAPSHOT analysis for cockpit HTTP.

Not a public card-registration adapter. Callers never pass client facts.
Reading a dashboard re-authorizes each card; a missing source degrades that
card only. Copy/undo must re-check sources before writing. Analysis-store
reads and cockpit writes are sequential, not a cross-store atomic transaction.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from backend.contracts.analytics_analysis import AnalyticsSavedSnapshot
from backend.contracts.analytics_cockpit import (
    AnalyticsCockpitAnalysisRef,
    AnalyticsCockpitCardOk,
    AnalyticsCockpitCardUnavailable,
    AnalyticsCockpitLayout,
    AnalyticsCockpitOp,
    AnalyticsCockpitTablePlugin,
)
from backend.contracts.analytics_query import (
    DATA_VERSION,
    METRIC_ID,
    METRIC_VERSION,
    QUERY_ID,
    QUERY_VERSION,
    ChannelFollowupFacts,
    ChannelFollowupQueryRequest,
    ChannelFollowupResolvedFilters,
)
from backend.contracts.competition_c0 import (
    CompetitionBoardSpec,
    CompetitionPatchRequest,
    PatchIntent,
)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.catalog import bind_resolved_filters_from_metadata
from backend.services.analytics.cockpit import (
    OPAQUE_ID,
    PLUGIN_TABLE,
    CockpitRecord,
    CockpitStore,
    _spec_hash,
    legacy_spec_payload,
)
from backend.services.analytics.resource_profile import canonical_json
from backend.services.analytics.saved_analyses import SavedAnalysisStore

SAFE_LAYOUT = {"x": 0, "y": 0, "w": 6, "h": 4}
_CARD_ERRORS = {403, 404, 409, 422}
_SOURCE_DECODE_ERRORS = (json.JSONDecodeError, TypeError, ValueError, KeyError, ValidationError)


def _source_document(
    analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, analysis_id: str, version: int,
) -> dict:
    try:
        return analysis_store.get(principal, analysis_id, version).as_dict()
    except AnalyticsError:
        raise
    except _SOURCE_DECODE_ERRORS as error:
        raise AnalyticsError(422, "UNPROCESSABLE", "保存分析缺少合法冻结 SNAPSHOT。") from error


def _assert_request_matches_frozen_snapshot(filters: dict, snapshot: dict, document: dict, facts: dict) -> None:
    """Re-normalize the full request against sealed snapshot metadata. No DuckDB."""
    if snapshot.get("run_id") != document.get("created_from_run_id"):
        raise AnalyticsError(409, "BINDING_CORRUPT", "分析快照与冻结来源不一致。")
    try:
        resolved = ChannelFollowupResolvedFilters.model_validate(snapshot["resolved_filters"])
        expected = bind_resolved_filters_from_metadata(
            filters,
            {
                "snapshot_id": snapshot["data_snapshot_ref"],
                "data_version": document.get("data_version"),
                "data_digest": resolved.data_digest,
                "as_of": snapshot["as_of"],
                "timezone": resolved.timezone,
            },
            resolved.permission_scope,
        )
    except _SOURCE_DECODE_ERRORS as error:
        raise AnalyticsError(409, "BINDING_CORRUPT", "分析条件与冻结快照不一致。") from error
    if expected.model_dump() != resolved.model_dump():
        raise AnalyticsError(409, "BINDING_CORRUPT", "分析条件与冻结快照不一致。")
    if facts.get("observation_days") != resolved.observation_days:
        raise AnalyticsError(409, "BINDING_CORRUPT", "分析 facts 与冻结条件不一致。")
    if document.get("filter_hash") != resolved.filter_hash:
        raise AnalyticsError(409, "BINDING_CORRUPT", "分析条件与冻结快照不一致。")


def resolve_trusted_analysis_card(
    analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, analysis_id: str, version: int,
) -> dict:
    """Load and contract-validate a frozen saved analysis. Requires analysis:read."""
    document = _source_document(analysis_store, principal, analysis_id, version)
    if document.get("data_mode") != "SNAPSHOT":
        raise AnalyticsError(422, "UNPROCESSABLE", "驾驶舱本波只绑定 SNAPSHOT 分析。")
    query = document.get("query_ref") or {}
    if query.get("query_id") != QUERY_ID or query.get("query_version") != QUERY_VERSION:
        raise AnalyticsError(422, "UNPROCESSABLE", "分析合同与当前驾驶舱不一致。")
    metrics = document.get("metric_refs") or []
    if not metrics or metrics[0].get("metric_id") != METRIC_ID or metrics[0].get("metric_version") != METRIC_VERSION:
        raise AnalyticsError(422, "UNPROCESSABLE", "指标版本与当前驾驶舱不一致。")
    if document.get("data_version") != DATA_VERSION:
        raise AnalyticsError(422, "UNPROCESSABLE", "数据版本与当前驾驶舱不一致。")
    try:
        snapshot = json.loads(canonical_json(AnalyticsSavedSnapshot.model_validate(document.get("snapshot")).model_dump(mode="json")))
        facts = json.loads(canonical_json(ChannelFollowupFacts.model_validate(document.get("facts")).model_dump(mode="json")))
        filters = json.loads(canonical_json(ChannelFollowupQueryRequest.model_validate(document.get("filters")).model_dump(mode="json")))
    except _SOURCE_DECODE_ERRORS as error:
        raise AnalyticsError(422, "UNPROCESSABLE", "保存分析缺少合法冻结 SNAPSHOT。") from error
    _assert_request_matches_frozen_snapshot(filters, snapshot, document, facts)
    return {
        "analysis_ref": {"analysis_id": document["analysis_id"], "version": document["version"]},
        "snapshot": snapshot,
        "facts": facts,
        "limitations": list(document.get("limitations") or []),
        "plugin_ref": dict(PLUGIN_TABLE),
        "filter_hash": snapshot["resolved_filters"]["filter_hash"],
    }


def add_patch_from_trusted(trusted: dict, payload) -> dict:
    patch = {
        "op": "add",
        "analysis_ref": dict(trusted["analysis_ref"]),
        "snapshot": dict(trusted["snapshot"]),
        "facts": dict(trusted["facts"]),
        "limitations": list(trusted["limitations"]),
        "plugin_ref": dict(payload.plugin_ref.model_dump(mode="json") if payload.plugin_ref is not None else PLUGIN_TABLE),
    }
    if payload.layout is not None:
        patch["layout"] = payload.layout.model_dump(mode="json")
    if payload.display_overrides is not None:
        patch["display_overrides"] = payload.display_overrides.model_dump(mode="json")
    return patch


def store_patch_from_http(op) -> dict:
    if op.op == "copy":
        return {"op": "copy", "card_id": op.card_id}
    if op.op == "remove":
        return {"op": "remove", "card_id": op.card_id}
    if op.op == "layout":
        return {"op": "layout", "card_id": op.card_id, "layout": op.layout.model_dump(mode="json")}
    if op.op == "undo":
        return {"op": "undo", "scope": "board", "restore_from_version": op.restore_from_version}
    raise AnalyticsError(400, "INVALID_REQUEST", "op 必须是 add/copy/remove/layout/undo。")


def _card_error(error: AnalyticsError) -> dict:
    message = error.message if isinstance(error.message, str) and error.message else "板块来源不可用。"
    return {"code": error.code, "message": message[:200]}


def _safe_card_id(card: object) -> str:
    value = card.get("card_id") if isinstance(card, dict) else None
    if isinstance(value, str) and OPAQUE_ID.fullmatch(value):
        return value
    return "card_unavailable"


def _safe_ref(card: dict) -> dict | None:
    raw = card.get("analysis_ref")
    try:
        return AnalyticsCockpitAnalysisRef.model_validate(raw).model_dump(mode="json")
    except ValidationError:
        return None


def _safe_layout(card: dict) -> dict:
    try:
        return AnalyticsCockpitLayout.model_validate(card.get("layout")).model_dump(mode="json")
    except ValidationError:
        return dict(SAFE_LAYOUT)


def _safe_plugin(card: dict) -> dict | None:
    try:
        return AnalyticsCockpitTablePlugin.model_validate(card.get("plugin_ref")).model_dump(mode="json")
    except ValidationError:
        return None


def _error_card(card: object, error: AnalyticsError) -> dict:
    payload = card if isinstance(card, dict) else {}
    projected = {
        "card_id": _safe_card_id(payload),
        "analysis_ref": _safe_ref(payload),
        "data_mode": "SNAPSHOT",
        "layout": _safe_layout(payload),
        "plugin_ref": _safe_plugin(payload),
        "freshness": "PINNED",
        "source_status": "UNAVAILABLE",
        "error": _card_error(error),
    }
    return AnalyticsCockpitCardUnavailable.model_validate(projected).model_dump(mode="json")


def _bind_cached_card(card: dict, trusted: dict) -> None:
    ref = _safe_ref(card)
    if ref != trusted["analysis_ref"]:
        raise AnalyticsError(409, "BINDING_CORRUPT", "板块分析引用与冻结来源不一致。")
    try:
        cached_snapshot = json.loads(canonical_json(AnalyticsSavedSnapshot.model_validate(card.get("snapshot")).model_dump(mode="json")))
        cached_facts = json.loads(canonical_json(ChannelFollowupFacts.model_validate(card.get("facts")).model_dump(mode="json")))
    except (ValidationError, TypeError, ValueError, KeyError) as error:
        raise AnalyticsError(422, "UNPROCESSABLE", "板块缓存无法按合同解码。") from error
    if canonical_json(cached_snapshot) != canonical_json(trusted["snapshot"]):
        raise AnalyticsError(409, "BINDING_CORRUPT", "板块冻结快照与保存分析不一致。")
    if canonical_json(cached_facts) != canonical_json(trusted["facts"]):
        raise AnalyticsError(409, "BINDING_CORRUPT", "板块冻结 facts 与保存分析不一致。")


def authorize_existing_card(analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, card: dict) -> dict:
    ref = _safe_ref(card)
    if ref is None:
        raise AnalyticsError(422, "UNPROCESSABLE", "板块缺少合法分析引用。")
    trusted = resolve_trusted_analysis_card(analysis_store, principal, ref["analysis_id"], ref["version"])
    _bind_cached_card(card, trusted)
    return trusted


def authorize_http_op(
    analysis_store: SavedAnalysisStore,
    cockpit_store: CockpitStore,
    principal: AnalyticsPrincipal,
    dashboard_id: str,
    payload: AnalyticsCockpitOp,
    if_match: str,
) -> dict:
    """Build the store patch. Copy/undo re-check sources before any write."""
    if payload.op == "add":
        trusted = resolve_trusted_analysis_card(
            analysis_store, principal, payload.analysis_ref.analysis_id, payload.analysis_ref.version,
        )
        return add_patch_from_trusted(trusted, payload)
    if payload.op == "copy":
        baseline = cockpit_store.get_version(principal, dashboard_id, int(if_match))
        target = next((card for card in baseline.cards if card.get("card_id") == payload.card_id), None)
        if target is None:
            raise AnalyticsError(422, "UNPROCESSABLE", "目标板块不存在。")
        authorize_existing_card(analysis_store, principal, target)
        return store_patch_from_http(payload)
    if payload.op == "undo":
        restored = cockpit_store.get_version(principal, dashboard_id, payload.restore_from_version)
        for card in restored.cards:
            authorize_existing_card(analysis_store, principal, card)
        return store_patch_from_http(payload)
    return store_patch_from_http(payload)


def _ok_card(card: dict, trusted: dict) -> dict:
    raw_filters = card.get("local_filters") if isinstance(card.get("local_filters"), dict) else {}
    local_filters = raw_filters if all(isinstance(key, str) and isinstance(value, list) for key, value in raw_filters.items()) else {}
    display = card.get("display_overrides") if isinstance(card.get("display_overrides"), dict) else {}
    projected = {
        "card_id": _safe_card_id(card),
        "plugin_ref": dict(PLUGIN_TABLE),
        "analysis_ref": dict(trusted["analysis_ref"]),
        "data_mode": "SNAPSHOT",
        "layout": _safe_layout(card),
        "display_overrides": display if all(isinstance(key, str) and isinstance(value, str) for key, value in display.items()) else {},
        "filter_mapping": {},
        "local_filters": local_filters,
        "snapshot": dict(trusted["snapshot"]),
        "facts": dict(trusted["facts"]),
        "filter_hash": trusted["filter_hash"],
        "limitations": list(trusted["limitations"]),
        "effective_spec_hash": _spec_hash(trusted["analysis_ref"], trusted["snapshot"], local_filters),
        "freshness": "PINNED",
        "source_status": "OK",
    }
    return AnalyticsCockpitCardOk.model_validate(projected).model_dump(mode="json")


def project_card(analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, card: object) -> dict:
    payload = card if isinstance(card, dict) else {}
    try:
        if _safe_plugin(payload) is None:
            return _error_card(payload, AnalyticsError(422, "UNPROCESSABLE", "本波 HTTP 只展示 TABLE 板块。"))
        try:
            AnalyticsCockpitLayout.model_validate(payload.get("layout"))
        except ValidationError:
            return _error_card(payload, AnalyticsError(422, "UNPROCESSABLE", "板块布局无法展示。"))
        trusted = authorize_existing_card(analysis_store, principal, payload)
        return _ok_card(payload, trusted)
    except AnalyticsError as error:
        if error.status not in _CARD_ERRORS:
            raise
        return _error_card(payload, error)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError, ValidationError):
        return _error_card(payload, AnalyticsError(422, "UNPROCESSABLE", "板块来源无法解码。"))


def project_dashboard(
    analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, payload: dict, *, base_version: int,
) -> dict:
    document = dict(payload)
    document["base_version"] = base_version
    document["cards"] = [project_card(analysis_store, principal, card) for card in payload.get("cards") or []]
    return document


def project_legacy_board_spec(record: CockpitRecord) -> dict:
    return CompetitionBoardSpec.model_validate(legacy_spec_payload(record)).model_dump(mode="json")


def project_legacy_board_document(
    analysis_store: SavedAnalysisStore, principal: AnalyticsPrincipal, record: CockpitRecord,
) -> dict:
    spec = project_legacy_board_spec(record)
    return {
        "spec": spec,
        "blocks": [project_card(analysis_store, principal, card) for card in record.cards],
        "data_namespace": spec["data_namespace"],
        "snapshot_compat": spec["snapshot_compat"],
        "http_api": "NOT_CONNECTED",
        "finite_mock": True,
    }


def reject_filter_change(payload: CompetitionPatchRequest) -> None:
    if payload.intent == PatchIntent.FILTER_CHANGE or payload.filter_change is not None:
        raise AnalyticsError(
            422, "NOT_CONNECTED", "FILTER_CHANGE 必须创建新 run，当前驾驶舱未接通。",
        )
