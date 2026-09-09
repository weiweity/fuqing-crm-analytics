"""G2 wiring: competition board + audience HTTP. Independent of old /dashboards."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.analytics_app import _BodyLimit, _single_header
from backend.middleware.query_router import (
    competition_error_response,
    new_request_id,
    overlay_live_capabilities,
)
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.services.analytics.cockpit import CockpitStore
from backend.services.analytics.competition_assets import (
    CompetitionAssetService,
    as_competition_error,
)
from backend.services.analytics.competition_audience import (
    CompetitionAudienceError,
    CompetitionAudienceService,
)
from backend.services.analytics.competition_diagnosis.errors import DiagnosisFault
from backend.services.analytics.competition_diagnosis.orchestrator import DiagnosisAdapter
from backend.services.analytics.saved_analyses import SavedAnalysisStore

PREFIX = "/api/v1/analytics/competition"


def _competition_result_item(record) -> dict[str, Any]:
    """C0 endorsable pointer from a saved SNAPSHOT. Not a B0 /b0/assets document."""
    binding = record.binding()
    snapshot = record.snapshot if isinstance(record.snapshot, dict) else {}
    as_of = snapshot.get("as_of") or "2026-08-31T16:00:00.000000+00:00"
    run_id = binding.get("run_id") or snapshot.get("run_id")
    analysis_id = binding.get("analysis_id")
    digest = binding.get("evidence_digest") or snapshot.get("evidence_digest")
    result_id = f"result_{str(run_id or analysis_id or 'synth')[4:]}"
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", result_id or ""):
        result_id = f"result_{str(analysis_id or 'synth')}"
    return {
        "schema_version": "competition-result/v1",
        "result_id": result_id,
        "run_id": run_id,
        "analysis_id": analysis_id,
        "evidence_digest": digest,
        "completeness": "COMPLETE",
        "contains_real_data": False,
        "data_mode": "SNAPSHOT",
        "query_id": record.query_ref.get("query_id") if isinstance(record.query_ref, dict) else "channel_first_observed_followup",
        "query_version": record.query_ref.get("query_version") if isinstance(record.query_ref, dict) else "channel-followup-query/v1",
        "metric_id": "gsv",
        "metric_version": "competition-metrics/v1",
        "existing_result_schema": "analytics-channel-followup/v1",
        "facts_schema_ref": "backend.contracts.analytics_query.ChannelFollowupResult",
        "primary_result_ref": result_id,
        "empty_reason": None,
        "limitations": list(record.limitations) or ["合成 SNAPSHOT，不是真实经营结论。"],
        "row_count": 1,
        "page": {
            "checksum": digest,
            "complete": True,
            "limit": 50,
            "offset": 0,
            "total": 1,
        },
        "resolved_condition": {
            "metric_type": "GSV",
            "timezone": "Asia/Shanghai",
            "as_of": as_of,
            "comparison_mode": "YOY_SAME_PERIOD",
            "current_period": {"start_date": "2026-08-01", "end_date": "2026-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
            "comparison_period": {"start_date": "2025-08-01", "end_date": "2025-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
            "cutoff": "2026-07-31",
            "sample_mode": "EXCLUDE_CURRENT_SALES_ONLY",
            "data_version": "synthetic-c0-demo-data/v1",
            "rule_version": "competition-condition-rule/v1",
            "source_tense": "PUBLISHED_SNAPSHOT",
            "history_scope": {"channel_ids": [], "kind": "ALL", "product_ids": []},
            "sales_scope": {"channel_ids": [], "kind": "ALL", "product_ids": []},
            "unknown_flags": [],
        },
        "http_api": "CONNECTED",
        "finite_mock": True,
    }


def _request_id(request: Request) -> str:
    return getattr(request.state, "analytics_request_id", None) or new_request_id()


def _json_error(status: int, payload: dict[str, Any], request_id: str) -> JSONResponse:
    headers = {"cache-control": "no-store", "x-request-id": request_id}
    retry_after = (payload.get("error") or {}).get("retry_after")
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(payload, status_code=status, headers=headers)


def create_competition_app(
    analysis_store: SavedAnalysisStore | None = None,
    cockpit_store: CockpitStore | None = None,
    identities: B0IdentityRegistry | None = None,
    *,
    asset_state_dir: Path | None = None,
    audience_state_dir: Path | None = None,
    runtime_ready: Callable[[], bool] | None = None,
) -> FastAPI:
    app = FastAPI(title="Competition Assets", version="competition-c0/v1",
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_BodyLimit)
    registry = identities or B0IdentityRegistry()
    if asset_state_dir is None or analysis_store is None:
        assets: CompetitionAssetService | None = None
    else:
        assets = CompetitionAssetService(
            asset_state_dir, analysis_store=analysis_store, cockpit_store=cockpit_store,
        )
    audience = CompetitionAudienceService(audience_state_dir) if audience_state_dir is not None else None
    # T08: cancel then reject late attempt publish. In-memory per app instance.
    cancelled_attempts: set[tuple[str, str]] = set()
    cancelled_batches: set[tuple[str, str]] = set()
    diagnosis_by_actor: dict[str, DiagnosisAdapter] = {}

    def principal(request: Request):
        return registry.resolve(_single_header(request, "authorization"))

    def reject_late_attempt_publish(actor_id: str, attempt_id: str | None, *, batch_id: str | None = None) -> None:
        """After cancel, a late attempt must not publish a new board version."""
        if attempt_id and (actor_id, attempt_id) in cancelled_attempts:
            raise AnalyticsError(
                409, "CANCELLED",
                "迟到 attempt 已取消，禁止发布。",
                retryable=False,
            )
        if batch_id and (actor_id, batch_id) in cancelled_batches:
            raise AnalyticsError(
                409, "CANCELLED",
                "批次已取消，迟到 attempt 禁止发布。",
                retryable=False,
            )

    def require_assets() -> CompetitionAssetService:
        if assets is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "比赛资产库尚未显式配置。", retryable=True)
        return assets

    def require_audience() -> CompetitionAudienceService:
        if audience is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "比赛人群库尚未显式配置。", retryable=True)
        return audience

    def require_analyses() -> SavedAnalysisStore:
        if analysis_store is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "分析资产库尚未显式配置。", retryable=True)
        return analysis_store

    def diagnosis_for(actor) -> DiagnosisAdapter:
        adapter = diagnosis_by_actor.get(actor.actor_id)
        if adapter is None:
            adapter = DiagnosisAdapter(actor, session_id=f"http_{actor.actor_id}")
            diagnosis_by_actor[actor.actor_id] = adapter
        return adapter

    def idempotency(request: Request) -> str:
        key = _single_header(request, "idempotency-key")
        if not key:
            raise AnalyticsError(400, "INVALID_REQUEST", "需要 Idempotency-Key。")
        return key

    def if_match_version(request: Request) -> int | None:
        raw = _single_header(request, "if-match")
        if raw is None:
            return None
        if not re.fullmatch(r"[1-9][0-9]{0,15}", raw):
            raise AnalyticsError(400, "INVALID_VERSION", "If-Match 必须是正整数字符串。")
        return int(raw)

    @app.middleware("http")
    async def stamp_request_id(request: Request, call_next):
        if not getattr(request.state, "analytics_request_id", None):
            request.state.analytics_request_id = uuid4().hex
        if runtime_ready is not None and not runtime_ready():
            return _json_error(
                503,
                as_competition_error(
                    AnalyticsError(503, "STATE_UNAVAILABLE", "运行时未就绪。", retryable=True),
                    request_id=_request_id(request),
                ),
                _request_id(request),
            )
        return await call_next(request)

    @app.exception_handler(AnalyticsError)
    async def analytics_error(request: Request, error: AnalyticsError):
        rid = _request_id(request)
        return _json_error(error.status, as_competition_error(error, request_id=rid), rid)

    @app.exception_handler(CompetitionAudienceError)
    async def audience_error(request: Request, error: CompetitionAudienceError):
        payload = error.to_response().model_dump(mode="json")
        return _json_error(error.status, payload, error.request_id)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        loc = ""
        if error.errors():
            loc = str(error.errors()[0].get("loc", ("body",))[-1])
        return competition_error_response(
            http_status=422, code="INVALID_REQUEST",
            message="请求与当前合同不匹配。",
            request_id=_request_id(request), retryable=False,
            param=loc or None, doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T03",
        )

    @app.get("/api/v1/analytics/catalog")
    def catalog(request: Request):
        actor = principal(request)
        return {
            "schema_version": "competition-capabilities/v1",
            "capabilities": overlay_live_capabilities(set(actor.capabilities)),
        }

    @app.get(f"{PREFIX}/results")
    def list_results(request: Request):
        actor = principal(request)
        store = require_analyses()
        items = []
        for row in store.list(actor):
            analysis_id = row.get("analysis_id")
            if not analysis_id:
                continue
            record = store.get(actor, analysis_id)
            item = _competition_result_item(record)
            if item.get("run_id") and item.get("evidence_digest"):
                items.append(item)
        return {"items": items, "http_api": "CONNECTED", "asset_plane": "competition"}

    @app.post(f"{PREFIX}/diagnosis/capabilities")
    def diagnosis_capabilities(payload: dict[str, Any], request: Request):
        actor = principal(request)
        request_id = str(payload.get("request_id") or _request_id(request))
        try:
            body = diagnosis_for(actor).list_capabilities(request_id)
        except DiagnosisFault as fault:
            raise AnalyticsError(fault.error.http_status or 400, fault.error.code, fault.error.message) from fault
        body["live_transport"] = "HTTP_CONNECTED"
        body["http_api"] = "CONNECTED"
        return body

    @app.post(f"{PREFIX}/diagnosis/step")
    def diagnosis_step(payload: dict[str, Any], request: Request):
        actor = principal(request)
        request_id = str(payload.get("request_id") or _request_id(request))
        try:
            body = diagnosis_for(actor).run_step(
                capability_id=str(payload.get("capability_id") or ""),
                condition_mode=str(payload.get("condition_mode") or "INHERIT"),
                request_id=request_id,
                condition=payload.get("condition") if isinstance(payload.get("condition"), dict) else None,
                condition_patch=payload.get("condition_patch") if isinstance(payload.get("condition_patch"), dict) else None,
            )
        except DiagnosisFault as fault:
            raise AnalyticsError(fault.error.http_status or 400, fault.error.code, fault.error.message) from fault
        body["live_transport"] = "HTTP_CONNECTED"
        body["http_api"] = "CONNECTED"
        return body

    @app.post(f"{PREFIX}/diagnosis/patch")
    def diagnosis_patch(payload: dict[str, Any], request: Request):
        actor = principal(request)
        request_id = str(payload.get("request_id") or _request_id(request))
        adapter = diagnosis_for(actor)
        selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else {}
        patch_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        try:
            from backend.services.analytics.competition_diagnosis.patch import plan_patch
            body = plan_patch(
                intent=str(payload.get("intent") or ""),
                payload=patch_payload,
                selection=selection,
                in_flight=adapter.session.in_flight_patch,
                request_id=request_id,
            )
        except DiagnosisFault as fault:
            raise AnalyticsError(fault.error.http_status or 400, fault.error.code, fault.error.message) from fault
        adapter.session.in_flight_patch = {
            "board_id": body.get("board_id"),
            "block_id": body.get("block_id"),
            "base_version": body.get("base_version"),
        }
        body["live_transport"] = "HTTP_CONNECTED"
        body["http_api"] = "CONNECTED"
        return body

    @app.post(f"{PREFIX}/endorsements")
    def endorse(payload: dict[str, Any], request: Request, response: Response):
        result = require_assets().endorse_results(
            principal(request), idempotency(request), payload.get("result_refs") or payload.get("refs") or [],
        )
        result["http_api"] = "CONNECTED"
        response.status_code = 201
        return result

    @app.post(f"{PREFIX}/batches")
    def apply_batch(payload: dict[str, Any], request: Request):
        actor = principal(request)
        reject_late_attempt_publish(actor.actor_id, None, batch_id=str(payload.get("batch_id") or "") or None)
        result = require_assets().apply_batch(actor, payload)
        if not isinstance(result, dict):
            return result
        result["http_api"] = "CONNECTED"
        items = result.get("items") or []
        board_id = items[0].get("board_id") if items and items[0].get("status") == "SUCCEEDED" else None
        if board_id:
            loaded = require_assets().get_board(actor, board_id)
            spec = loaded.get("spec") if isinstance(loaded, dict) else None
            if spec:
                spec = dict(spec)
                spec["http_api"] = "CONNECTED"
                result["board"] = spec
        return result

    @app.get(f"{PREFIX}/batches/{{batch_id}}")
    def get_batch(batch_id: str, request: Request):
        return require_assets().get_batch(principal(request), batch_id)

    @app.get(f"{PREFIX}/boards")
    def list_boards(request: Request):
        return {
            "items": require_assets().list_boards(principal(request)),
            "http_api": "CONNECTED",
            "asset_plane": "competition",
        }

    @app.get(f"{PREFIX}/boards/{{board_id}}")
    def get_board(board_id: str, request: Request):
        return require_assets().get_board(principal(request), board_id)

    @app.post(f"{PREFIX}/boards/{{board_id}}/preview")
    def preview_patch(board_id: str, payload: dict[str, Any], request: Request):
        body = dict(payload)
        body.setdefault("board_id", board_id)
        return require_assets().preview_patch(principal(request), body)

    @app.post(f"{PREFIX}/boards/{{board_id}}/versions")
    def apply_patch(board_id: str, payload: dict[str, Any], request: Request):
        body = dict(payload)
        body.setdefault("board_id", board_id)
        reject_late_attempt_publish(principal(request).actor_id, str(body.get("attempt_id") or "") or None)
        matched = if_match_version(request)
        if matched is not None:
            body["base_version"] = matched
        elif "base_version" not in body:
            raise AnalyticsError(428, "IF_MATCH_REQUIRED", "保存需要 If-Match 或 base_version。")
        return require_assets().apply_patch(principal(request), body)

    @app.get(f"{PREFIX}/attempts/{{attempt_id}}")
    def get_attempt(attempt_id: str, request: Request):
        return require_assets().get_edit_target(principal(request), attempt_id)

    @app.post(f"{PREFIX}/attempts/{{attempt_id}}/discard")
    def discard_attempt(attempt_id: str, request: Request):
        return require_assets().discard_attempt(principal(request), attempt_id)

    @app.post(f"{PREFIX}/attempts/{{attempt_id}}/cancel")
    def cancel_attempt(attempt_id: str, request: Request):
        actor = principal(request)
        cancelled_attempts.add((actor.actor_id, attempt_id))
        return {
            "attempt_id": attempt_id,
            "status": "CANCELLED",
            "late_attempt_publish": False,
        }

    @app.post(f"{PREFIX}/batches/{{batch_id}}/cancel")
    def cancel_batch(batch_id: str, request: Request):
        actor = principal(request)
        cancelled_batches.add((actor.actor_id, batch_id))
        return {
            "batch_id": batch_id,
            "status": "CANCELLED",
            "late_attempt_publish": False,
        }

    @app.post(f"{PREFIX}/candidates/preview")
    def preview_candidates(payload: dict[str, Any], request: Request):
        out = require_audience().preview_candidates(principal(request), payload)
        if isinstance(out.get("candidates"), object) and hasattr(out["candidates"], "model_dump"):
            out = dict(out)
            out["candidates"] = out["candidates"].model_dump(mode="json")
        out["auto_send"] = False
        return out

    @app.post(f"{PREFIX}/drafts")
    def save_draft(payload: dict[str, Any], request: Request):
        draft = require_audience().save_draft(principal(request), payload)
        dumped = draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft
        return dumped

    @app.get(f"{PREFIX}/drafts/current")
    def load_current_draft(request: Request):
        principal(request)
        return {"http_api": "CONNECTED", "draft": None, "candidates": None}

    return app
