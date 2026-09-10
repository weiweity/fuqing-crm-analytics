"""Competition board service: endorse, batch, preview/apply, undo, reopen.

Writes competition-board/v1 only. analytics-cockpit/v1 SNAPSHOT stays read-only.
HTTP/OpenAPI is NOT_CONNECTED; route registration is an integration request.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from backend.contracts.analytics_cockpit import (
    AnalyticsCockpitAddOp,
    AnalyticsCockpitCopyOp,
    AnalyticsCockpitLayoutOp,
    AnalyticsCockpitRemoveOp,
    AnalyticsCockpitUndoOp,
)
from backend.contracts.competition_c0 import (
    BoardLayoutMode,
    BoardOpReceipt,
    CompetitionBoardBatchReceipt,
    CompetitionBoardBatchRequest,
    CompetitionBoardSpec,
    CompetitionErrorDetail,
    CompetitionPatchRequest,
    EndorsedResultRef,
    PatchIntent,
    SnapshotCompat,
)
from backend.contracts.competition_chart import CompetitionChartPatchRequest
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, require
from backend.services.analytics.analysis_source import resolve_endorsed_result
from backend.services.analytics.cockpit import (
    COMPETITION_BOARD_NAMESPACE,
    DASHBOARD_SCHEMA,
    DATA_SCOPE,
    MAX_CARDS,
    PLUGIN_TABLE,
    _copy_layout,
    _display_overrides,
    _layout,
    _next_layout,
    _now_ms,
    _spec_hash,
    _title,
    CockpitStore,
    validate_key,
)
from backend.services.analytics.cockpit_source import (
    project_legacy_board_document,
    reject_filter_change,
    resolve_trusted_analysis_card,
)
from backend.services.analytics.competition_assets.store import CompetitionAssetStore
from backend.services.analytics.competition_assets.result import competition_result_item
from backend.services.analytics.resource_profile import canonical_json, content_hash
from backend.services.analytics.saved_analyses import SavedAnalysisStore
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore, is_computed_reference

CAPABILITY_READ = "dashboard:read"
CAPABILITY_WRITE = "dashboard:update"
CAPABILITY_ANALYSIS_READ = "analysis:read"
CAPABILITY_ANALYSIS_SAVE = "analysis:save"
NEW_BOARD_LIMITATIONS = [
    "competition-board/v1 隔离命名空间；旧 analytics-cockpit/v1 SNAPSHOT 只读兼容。",
    "结果按 analysis_id/run_id/evidence_digest 共享引用，不按板重复计算。",
]
DOC_T06 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06"
DOC_T09 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T09"
DOC_T10 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T10"
DOC_T11 = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T11"
HTTP_WIRING = {
    "http_api": "NOT_CONNECTED",
    "prefix": "/api/v1/analytics/competition",
    "notes": "Do not reuse single-owner /api/v1/analytics/dashboards for multi-board batch.",
    "routes": [
        {"method": "POST", "path": "/endorsements", "handler": "endorse_results", "idempotency": True},
        {"method": "POST", "path": "/batches", "handler": "apply_batch", "idempotency": True},
        {"method": "GET", "path": "/batches/{batch_id}", "handler": "get_batch"},
        {"method": "GET", "path": "/boards", "handler": "list_boards"},
        {"method": "GET", "path": "/boards/{board_id}", "handler": "get_board"},
        {"method": "POST", "path": "/boards/{board_id}/preview", "handler": "preview_patch"},
        {"method": "POST", "path": "/boards/{board_id}/versions", "handler": "apply_patch", "if_match": True},
        {"method": "GET", "path": "/attempts/{attempt_id}", "handler": "get_edit_target"},
        {"method": "POST", "path": "/attempts/{attempt_id}/discard", "handler": "discard_attempt"},
    ],
}


def _missing() -> AnalyticsError:
    return AnalyticsError(404, "NOT_FOUND", "驾驶舱不存在或当前身份不可见。")


def _conflict_payload() -> AnalyticsError:
    return AnalyticsError(409, "CONFLICT", "同幂等键的请求载荷不一致，已拒绝。")


def _version_conflict() -> AnalyticsError:
    return AnalyticsError(409, "VERSION_CONFLICT", "base_version 与已保存版本不一致，未覆盖。")


def _unprocessable(message: str) -> AnalyticsError:
    return AnalyticsError(422, "UNPROCESSABLE", message)


def _invalid(message: str) -> AnalyticsError:
    return AnalyticsError(400, "INVALID_REQUEST", message)


def _legacy_readonly() -> AnalyticsError:
    return AnalyticsError(
        422, "REJECT_UNSUPPORTED_VERSION",
        "旧 SNAPSHOT 驾驶舱只读；competition-board/v1 使用隔离命名空间。",
    )


def operation_payload_hash(batch_id: str, operation) -> str:
    return content_hash({
        "batch_id": batch_id,
        "operation_id": operation.operation_id,
        "layout_mode": operation.layout_mode,
        "board_id": operation.board_id,
        "title": operation.title,
        "endorsed_result_refs": [item.model_dump(mode="json") for item in operation.endorsed_result_refs],
    })


def stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{content_hash({'parts': list(parts)})[:32]}"


def as_competition_error(
    error: AnalyticsError, *, request_id: str, param: str | None = None,
) -> dict[str, Any]:
    docs = {
        "FORBIDDEN": DOC_T06,
        "UNAUTHENTICATED": DOC_T06,
        "CONFLICT": DOC_T09,
        "BINDING_CORRUPT": DOC_T09,
        "ANALYSIS_UNAVAILABLE": DOC_T09,
        "NOT_CONNECTED": DOC_T10,
        "REJECT_UNSUPPORTED_VERSION": DOC_T11,
        "VERSION_CONFLICT": DOC_T11,
    }
    params = {
        "FORBIDDEN": "board_id",
        "VERSION_CONFLICT": "base_version",
        "CONFLICT": "idempotency_key",
        "ANALYSIS_UNAVAILABLE": "result_id",
        "NOT_CONNECTED": "intent",
        "REJECT_UNSUPPORTED_VERSION": "data_namespace",
        "BINDING_CORRUPT": "evidence_digest",
    }
    detail = CompetitionErrorDetail(
        code=error.code,
        message=error.message[:500],
        param=param if param is not None else params.get(error.code),
        retryable=error.retryable,
        retry_after=None,
        request_id=request_id,
        doc_ref=docs.get(error.code),
        recovery_url=error.recovery_url,
        http_status=error.status,
        maps_to="backend.contracts.analytics.AnalyticsErrorDetail",
    )
    return {"error": detail.model_dump(mode="json")}


def _receipt(*, operation_id: str, board_id: str | None, version: int | None,
             status: str, error_code: str | None, retryable: bool) -> dict[str, Any]:
    return BoardOpReceipt(
        operation_id=operation_id, board_id=board_id, version=version,
        status=status, error_code=error_code, retryable=retryable,
    ).model_dump(mode="json")


def _failed_receipt(operation_id: str, error: AnalyticsError) -> dict[str, Any]:
    status = "CONFLICT" if error.status == 409 else "FAILED"
    retryable = error.retryable or error.code in {"ANALYSIS_UNAVAILABLE", "STATE_UNAVAILABLE"}
    return _receipt(
        operation_id=operation_id, board_id=None, version=None,
        status=status, error_code=error.code, retryable=retryable,
    )


def _batch_status(items: list[dict[str, Any]]) -> str:
    flags = {item["status"] for item in items}
    if flags == {"SUCCEEDED"}:
        return "SUCCEEDED"
    if "SUCCEEDED" in flags:
        return "PARTIAL"
    return "FAILED"


def _blocks_from_bindings(operation_id: str, bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for index, binding in enumerate(bindings):
        layout = _next_layout(blocks)
        block_id = stable_id("block", operation_id, binding["result_id"], str(index))
        blocks.append({
            "block_id": block_id,
            "card_id": block_id,
            "plugin_ref": dict(PLUGIN_TABLE),
            "analysis_ref": {"analysis_id": binding["analysis_id"], "version": binding["version"]},
            "result_id": binding["result_id"],
            "run_id": binding["run_id"],
            "evidence_digest": binding["evidence_digest"],
            "data_mode": "SNAPSHOT",
            "layout": dict(layout),
            "display_overrides": {},
            "filter_mapping": {},
            "local_filters": {},
            "filter_hash": binding["filter_hash"],
            "freshness": "PINNED",
        })
    return blocks


def _spec_from_row(row, *, preview: bool, persisted: bool, base_version: int,
                   affected: list[str]) -> dict[str, Any]:
    blocks = json.loads(row["blocks_json"])
    return CompetitionBoardSpec.model_validate({
        "schema_version": "competition-board/v1",
        "board_id": row["board_id"],
        "block_ids": [block["block_id"] for block in blocks],
        "version": row["version"] if persisted else base_version,
        "base_version": base_version,
        "title": row["title"],
        "owner_id": row["owner"],
        "visibility": "PRIVATE",
        "layout_mode": row["layout_mode"],
        "existing_dashboard_schema": DASHBOARD_SCHEMA,
        "data_namespace": COMPETITION_BOARD_NAMESPACE,
        "snapshot_compat": SnapshotCompat.ISOLATED_NEW,
        "data_mode": "SNAPSHOT",
        "preview": preview,
        "persisted": persisted,
        "batch_id": row["batch_id"],
        "operation_id": row["operation_id"],
        "affected_block_ids": list(affected),
        "limitations": list(NEW_BOARD_LIMITATIONS),
    }).model_dump(mode="json")


class CompetitionAssetService:
    """Finite-mock competition assets. HTTP/OpenAPI is NOT_CONNECTED."""

    finite_mock = True
    http_api = "NOT_CONNECTED"
    http_wiring = HTTP_WIRING

    def __init__(
        self,
        state_dir: Path,
        *,
        analysis_store: SavedAnalysisStore,
        cockpit_store: CockpitStore | None = None,
        computed_store: ComputedResultStore | None = None,
        clock: Callable[[], int] = _now_ms,
    ):
        self.store = CompetitionAssetStore(state_dir, clock=clock)
        self.analyses = analysis_store
        self.cockpit = cockpit_store
        self.computed = computed_store
        self.clock = clock

    def close(self) -> None:
        self.store.close()

    def _computed_store(self):
        if self.computed is None:
            raise AnalyticsError(503, "STATE_UNAVAILABLE", "诊断结果库尚未配置。")
        return self.computed

    def _resolve_endorsed(self, principal, ref):
        if is_computed_reference(ref.analysis_id, ref.run_id):
            return self._computed_store().resolve_endorsed(principal, ref)
        return resolve_endorsed_result(self.analyses, principal, ref)

    def _resolve_card(self, principal, analysis_id, version):
        if is_computed_reference(analysis_id):
            return self._computed_store().resolve_card(principal, analysis_id, version)
        return resolve_trusted_analysis_card(self.analyses, principal, analysis_id, version)

    def _analysis(self, principal, analysis_id, version):
        store = self._computed_store() if is_computed_reference(analysis_id) else self.analyses
        return store.get(principal, analysis_id, version)

    def _require(self, principal: AnalyticsPrincipal, capability: str) -> None:
        require(principal, capability, data_scope=DATA_SCOPE)

    def endorse_results(self, principal: AnalyticsPrincipal, key: str, refs: list[Any]) -> dict[str, Any]:
        self._require(principal, CAPABILITY_ANALYSIS_READ)
        self._require(principal, CAPABILITY_ANALYSIS_SAVE)
        key = validate_key(key)
        try:
            parsed = [item if isinstance(item, EndorsedResultRef) else EndorsedResultRef.model_validate(item)
                      for item in refs]
        except ValidationError:
            raise _unprocessable("认可结果集合不符合 competition-c0 合同。") from None
        if not parsed or len(parsed) > 20:
            raise _invalid("认可结果集合须为 1–20 条。")
        digest = content_hash([item.model_dump(mode="json") for item in parsed])
        with self.store.transaction() as con:
            prior = self.store.prior(con, principal, "result:endorse", "", key, digest)
            if prior is not None:
                return json.loads(prior["response_json"])
            bindings = []
            for item in parsed:
                binding = self._resolve_endorsed(principal, item)
                self.store.upsert_endorsement(con, principal, binding)
                bindings.append({
                    "result_id": binding["result_id"],
                    "run_id": binding["run_id"],
                    "analysis_id": binding["analysis_id"],
                    "version": binding["version"],
                    "evidence_digest": binding["evidence_digest"],
                    "completeness": "COMPLETE",
                })
            response = {
                "set_id": stable_id("endorse", principal.actor_id, key),
                "result_ids": [item["result_id"] for item in bindings],
                "bindings": bindings,
                "finite_mock": True,
                "http_api": "NOT_CONNECTED",
            }
            self.store.remember(con, principal, "result:endorse", "", key, digest, response, 201)
            return response

    def apply_batch(self, principal: AnalyticsPrincipal, payload: dict[str, Any] | CompetitionBoardBatchRequest):
        self._require(principal, CAPABILITY_WRITE)
        self._require(principal, CAPABILITY_ANALYSIS_READ)
        try:
            request = (
                payload if isinstance(payload, CompetitionBoardBatchRequest)
                else CompetitionBoardBatchRequest.model_validate(payload)
            )
        except ValidationError:
            raise _unprocessable("批量成板请求不符合 competition-board-batch/v1。") from None
        items = [self._apply_operation(principal, request.batch_id, request.layout_mode, operation)
                 for operation in request.operations]
        receipt = CompetitionBoardBatchReceipt.model_validate({
            "schema_version": "competition-board-batch/v1",
            "batch_id": request.batch_id,
            "status": _batch_status(items),
            "items": items,
        }).model_dump(mode="json")
        with self.store.transaction() as con:
            self.store.require_not_cancelled(con, principal, "batch", request.batch_id)
            self.store.upsert_batch(
                con, principal, batch_id=request.batch_id, layout_mode=request.layout_mode.value,
                status=receipt["status"], receipt=receipt,
            )
        return receipt

    def get_batch(self, principal: AnalyticsPrincipal, batch_id: str) -> dict[str, Any]:
        self._require(principal, CAPABILITY_READ)
        with self.store.readonly() as con:
            row = self.store.get_batch(con, principal, batch_id)
            if row is None:
                raise _missing()
            return json.loads(row["receipt_json"])

    def check_cancelled(self, principal, kind: str, target_id: str) -> None:
        with self.store.readonly() as con:
            self.store.require_not_cancelled(con, principal, kind, target_id)

    def cancel(self, principal, kind: str, target_id: str) -> dict[str, Any]:
        self._require(principal, CAPABILITY_WRITE)
        self.store.cancel(principal, kind, target_id)
        return {f"{kind}_id": target_id, "status": "CANCELLED", "late_attempt_publish": False}

    def _apply_operation(self, principal, batch_id: str, layout_mode: BoardLayoutMode, operation) -> dict[str, Any]:
        payload_hash = operation_payload_hash(batch_id, operation)
        try:
            with self.store.transaction() as con:
                self.store.require_not_cancelled(con, principal, "batch", batch_id)
                existing = self.store.get_operation(con, principal, operation.operation_id)
                by_key = self.store.get_operation_by_key(con, principal, operation.idempotency_key)
                if by_key is not None and by_key["operation_id"] != operation.operation_id:
                    raise _conflict_payload()
                replay = existing if existing is not None else by_key
                if replay is not None:
                    if (replay["payload_hash"] != payload_hash
                            or replay["request_fingerprint"] != operation.request_fingerprint):
                        raise _conflict_payload()
                    if replay["status"] == "SUCCEEDED":
                        return json.loads(replay["receipt_json"])
                try:
                    bindings = []
                    for ref in operation.endorsed_result_refs:
                        try:
                            bindings.append(self._resolve_endorsed(principal, ref))
                        except AnalyticsError as error:
                            if error.status == 404:
                                raise AnalyticsError(
                                    422, "ANALYSIS_UNAVAILABLE", "认可结果不存在或当前身份不可见。",
                                    retryable=True,
                                ) from error
                            raise
                    board_id = operation.board_id or stable_id(
                        "board", principal.actor_id, batch_id, operation.operation_id,
                    )
                    latest = self.store.board_row(con, principal, board_id, None)
                    if latest is not None and latest["operation_id"] != operation.operation_id:
                        raise AnalyticsError(409, "CONFLICT", "board_id 已被其他操作占用。")
                    if latest is not None and latest["operation_id"] == operation.operation_id:
                        receipt = _receipt(
                            operation_id=operation.operation_id, board_id=board_id,
                            version=latest["version"], status="SUCCEEDED",
                            error_code=None, retryable=False,
                        )
                        self.store.upsert_operation(
                            con, principal, operation_id=operation.operation_id, batch_id=batch_id,
                            idempotency_key=operation.idempotency_key,
                            request_fingerprint=operation.request_fingerprint, payload_hash=payload_hash,
                            board_id=board_id, version=latest["version"], status="SUCCEEDED",
                            error_code=None, retryable=False, receipt=receipt,
                        )
                        return receipt
                    blocks = _blocks_from_bindings(operation.operation_id, bindings)
                    if len(blocks) > MAX_CARDS:
                        raise _unprocessable("驾驶舱板块数量已达上限。")
                    for binding in bindings:
                        self.store.upsert_endorsement(con, principal, binding)
                    row = self.store.insert_board(
                        con, principal, board_id=board_id, version=1, title=_title(operation.title),
                        layout_mode=layout_mode.value, blocks=blocks, batch_id=batch_id,
                        operation_id=operation.operation_id,
                    )
                    receipt = _receipt(
                        operation_id=operation.operation_id, board_id=row["board_id"],
                        version=row["version"], status="SUCCEEDED", error_code=None, retryable=False,
                    )
                    self.store.upsert_operation(
                        con, principal, operation_id=operation.operation_id, batch_id=batch_id,
                        idempotency_key=operation.idempotency_key,
                        request_fingerprint=operation.request_fingerprint, payload_hash=payload_hash,
                        board_id=row["board_id"], version=row["version"], status="SUCCEEDED",
                        error_code=None, retryable=False, receipt=receipt,
                    )
                    return receipt
                except AnalyticsError as error:
                    if error.code == "CONFLICT" and error.status == 409:
                        raise
                    receipt = _failed_receipt(operation.operation_id, error)
                    self.store.upsert_operation(
                        con, principal, operation_id=operation.operation_id, batch_id=batch_id,
                        idempotency_key=operation.idempotency_key,
                        request_fingerprint=operation.request_fingerprint, payload_hash=payload_hash,
                        board_id=None, version=None, status=receipt["status"],
                        error_code=error.code, retryable=receipt["retryable"], receipt=receipt,
                    )
                    return receipt
        except AnalyticsError as error:
            if error.status == 409:
                raise
            return _failed_receipt(operation.operation_id, error)

    def list_boards(self, principal: AnalyticsPrincipal) -> list[dict[str, Any]]:
        self._require(principal, CAPABILITY_READ)
        items: list[dict[str, Any]] = []
        if self.cockpit is not None:
            for row in self.cockpit.list(principal):
                record = self.cockpit.get(principal, row["dashboard_id"])
                items.append(project_legacy_board_document(self.analyses, principal, record)["spec"])
        with self.store.readonly() as con:
            for row in self.store.list_latest(con, principal):
                items.append(_spec_from_row(row, preview=False, persisted=True,
                                            base_version=row["version"], affected=[]))
        return items

    def get_board(self, principal: AnalyticsPrincipal, board_id: str, version: int | None = None) -> dict[str, Any]:
        self._require(principal, CAPABILITY_READ)
        with self.store.readonly() as con:
            row = self.store.board_row(con, principal, board_id, version)
        if row is not None:
            spec = _spec_from_row(row, preview=False, persisted=True,
                                  base_version=row["version"], affected=[])
            blocks = [self._hydrate_block(principal, block) for block in json.loads(row["blocks_json"])]
            return {
                "spec": spec,
                "blocks": blocks,
                "data_namespace": COMPETITION_BOARD_NAMESPACE,
                "snapshot_compat": SnapshotCompat.ISOLATED_NEW.value,
                "http_api": "NOT_CONNECTED",
                "finite_mock": True,
            }
        if self.cockpit is None:
            raise _missing()
        try:
            record = (
                self.cockpit.get(principal, board_id) if version is None
                else self.cockpit.get_version(principal, board_id, version)
            )
        except AnalyticsError:
            raise _missing() from None
        return project_legacy_board_document(self.analyses, principal, record)

    def get_edit_target(self, principal: AnalyticsPrincipal, attempt_id: str) -> dict[str, Any]:
        self._require(principal, CAPABILITY_READ)
        with self.store.readonly() as con:
            row = self.store.get_attempt(con, principal, attempt_id)
        if row is None:
            raise _missing()
        return {
            "attempt_id": row["attempt_id"],
            "board_id": row["board_id"],
            "block_id": row["block_id"],
            "base_version": row["base_version"],
            "intent": row["intent"],
            "status": row["status"],
            "idempotency_key": row["idempotency_key"],
            "http_api": "NOT_CONNECTED",
            "finite_mock": True,
        }

    def discard_attempt(self, principal: AnalyticsPrincipal, attempt_id: str) -> dict[str, Any]:
        self._require(principal, CAPABILITY_WRITE)
        with self.store.transaction() as con:
            row = self.store.get_attempt(con, principal, attempt_id)
            if row is None:
                raise _missing()
            if row["status"] == "APPLIED":
                raise _unprocessable("已保存版本不能用放弃预览撤销。")
            self.store.upsert_attempt(
                con, principal, attempt_id=attempt_id, board_id=row["board_id"], block_id=row["block_id"],
                base_version=row["base_version"], intent=row["intent"],
                idempotency_key=row["idempotency_key"], payload_hash=row["payload_hash"],
                status="DISCARDED",
            )
        target = self.get_edit_target(principal, attempt_id)
        document = self.get_board(principal, target["board_id"])
        return {"attempt": target, "board": document, "discarded": True, "undone": False}

    def preview_patch(self, principal: AnalyticsPrincipal, payload: dict[str, Any] | CompetitionPatchRequest):
        return self._mutate_patch(principal, payload, persist=False)

    def apply_patch(self, principal: AnalyticsPrincipal, payload: dict[str, Any] | CompetitionPatchRequest):
        return self._mutate_patch(principal, payload, persist=True)

    def _parse_patch(self, payload) -> CompetitionPatchRequest | CompetitionChartPatchRequest:
        try:
            if isinstance(payload, (CompetitionPatchRequest, CompetitionChartPatchRequest)):
                return payload
            model = (CompetitionChartPatchRequest if isinstance(payload, dict) and payload.get("schema_version") == "competition-board-chart-patch/v1"
                     else CompetitionPatchRequest)
            return model.model_validate(payload)
        except ValidationError:
            raise _unprocessable("补丁不符合 C0 或比赛图表运行时合同。") from None

    def _load_competition_row(self, principal, board_id: str, version: int | None = None):
        with self.store.readonly() as con:
            return self.store.board_row(con, principal, board_id, version)

    def _ensure_attempt(self, con, principal, patch: CompetitionPatchRequest, payload_hash: str, *, persist: bool):
        row = self.store.get_attempt(con, principal, patch.attempt_id)
        if row is None:
            status = "APPLIED" if persist else "PREVIEWED"
            self.store.upsert_attempt(
                con, principal, attempt_id=patch.attempt_id, board_id=patch.board_id,
                block_id=patch.block_id, base_version=patch.base_version, intent=patch.intent.value,
                idempotency_key=patch.idempotency_key, payload_hash=payload_hash, status=status,
            )
            return self.store.get_attempt(con, principal, patch.attempt_id)
        if row["board_id"] != patch.board_id or row["block_id"] != patch.block_id:
            raise AnalyticsError(409, "CONFLICT", "在途编辑目标已绑定，不能随点选切换。")
        if row["base_version"] != patch.base_version:
            raise _version_conflict()
        if row["intent"] != patch.intent.value or row["payload_hash"] != payload_hash:
            raise _conflict_payload()
        if row["status"] == "DISCARDED":
            raise _unprocessable("已放弃的预览不能再保存。")
        if row["status"] == "APPLIED" and persist:
            return row
        if not persist and row["status"] == "APPLIED":
            raise _unprocessable("已保存 attempt 不能再当作预览。")
        return row

    def _mutate_patch(self, principal, payload, *, persist: bool) -> dict[str, Any]:
        self._require(principal, CAPABILITY_WRITE if persist else CAPABILITY_READ)
        patch = self._parse_patch(payload)
        validate_key(patch.idempotency_key)
        if isinstance(patch, CompetitionPatchRequest):
            reject_filter_change(patch)
        if self._load_competition_row(principal, patch.board_id) is None:
            if self.cockpit is not None:
                try:
                    self.cockpit.get(principal, patch.board_id)
                except AnalyticsError:
                    raise _missing() from None
                raise _legacy_readonly()
            raise _missing()
        payload_hash = content_hash(patch.model_dump(mode="json"))
        with self.store.readonly() as con:
            existing_attempt = self.store.get_attempt(con, principal, patch.attempt_id)
        if existing_attempt is not None:
            if (existing_attempt["board_id"] != patch.board_id
                    or existing_attempt["block_id"] != patch.block_id):
                raise AnalyticsError(409, "CONFLICT", "在途编辑目标已绑定，不能随点选切换。")
            if existing_attempt["base_version"] != patch.base_version:
                raise _version_conflict()
        if persist:
            with self.store.transaction() as con:
                self.store.require_not_cancelled(con, principal, "attempt", patch.attempt_id)
                attempt = self._ensure_attempt(con, principal, patch, payload_hash, persist=True)
                if attempt["status"] == "APPLIED" and attempt["result_json"]:
                    return json.loads(attempt["result_json"])
                row = self.store.board_row(con, principal, patch.board_id, None)
                if row is None:
                    raise _missing()
                if row["version"] != patch.base_version:
                    raise _version_conflict()
                blocks, title, affected = self._apply_c0_patch(con, principal, row, patch, preview=False)
                stored = self.store.insert_board(
                    con, principal, board_id=patch.board_id, version=patch.base_version + 1,
                    title=title, layout_mode=row["layout_mode"], blocks=blocks,
                    batch_id=row["batch_id"], operation_id=row["operation_id"],
                )
                spec = _spec_from_row(
                    stored, preview=False, persisted=True, base_version=patch.base_version, affected=affected,
                )
                document = {
                    "spec": spec,
                    "blocks": [self._hydrate_block(principal, block) for block in blocks],
                    "data_namespace": COMPETITION_BOARD_NAMESPACE,
                    "snapshot_compat": SnapshotCompat.ISOLATED_NEW.value,
                    "http_api": "NOT_CONNECTED",
                    "finite_mock": True,
                }
                self.store.upsert_attempt(
                    con, principal, attempt_id=patch.attempt_id, board_id=patch.board_id,
                    block_id=patch.block_id, base_version=patch.base_version, intent=patch.intent.value,
                    idempotency_key=patch.idempotency_key, payload_hash=payload_hash, status="APPLIED",
                    result_version=stored["version"], result=document,
                )
                return document
        row = self._load_competition_row(principal, patch.board_id)
        if row is None:
            raise _missing()
        if row["version"] != patch.base_version:
            raise _version_conflict()
        with self.store.readonly() as con:
            blocks, title, affected = self._apply_c0_patch(con, principal, row, patch, preview=True)
        with self.store.transaction() as con:
            self._ensure_attempt(con, principal, patch, payload_hash, persist=False)
        preview_row = {
            "board_id": row["board_id"],
            "version": row["version"],
            "owner": row["owner"],
            "title": title,
            "layout_mode": row["layout_mode"],
            "blocks_json": canonical_json(blocks),
            "batch_id": row["batch_id"],
            "operation_id": row["operation_id"],
        }
        spec = _spec_from_row(
            preview_row, preview=True, persisted=False, base_version=row["version"], affected=affected,
        )
        return {
            "spec": spec,
            "blocks": [self._hydrate_block(principal, block) for block in blocks],
            "data_namespace": COMPETITION_BOARD_NAMESPACE,
            "snapshot_compat": SnapshotCompat.ISOLATED_NEW.value,
            "http_api": "NOT_CONNECTED",
            "finite_mock": True,
        }

    def _apply_c0_patch(self, con, principal, row, patch: CompetitionPatchRequest, *, preview: bool):
        blocks = json.loads(row["blocks_json"])
        title = row["title"]
        if isinstance(patch, CompetitionChartPatchRequest):
            target = self._require_block(blocks, patch.block_id)
            updated = {**target, "plugin": patch.chart_type}
            return ([updated if block["block_id"] == target["block_id"] else block for block in blocks],
                    title, [target["block_id"]])
        if patch.intent == PatchIntent.STYLE_ONLY:
            return self._style_only(blocks, title, patch)
        if patch.cockpit_op is None:
            raise _unprocessable("STRUCTURE 需要 AnalyticsCockpitOp。")
        op = patch.cockpit_op
        if isinstance(op, AnalyticsCockpitUndoOp):
            return self._undo(con, principal, row, op)
        if isinstance(op, AnalyticsCockpitAddOp):
            return self._add_block(principal, blocks, title, patch, op)
        if isinstance(op, AnalyticsCockpitCopyOp):
            return self._copy_block(blocks, title, patch, op)
        if isinstance(op, AnalyticsCockpitRemoveOp):
            return self._remove_block(blocks, title, patch, op)
        if isinstance(op, AnalyticsCockpitLayoutOp):
            return self._layout_block(blocks, title, patch, op)
        raise _invalid("op 必须是 add/copy/remove/layout/undo。")

    def _require_block(self, blocks: list[dict[str, Any]], block_id: str | None) -> dict[str, Any]:
        if block_id is None:
            raise _unprocessable("未指明目标板块，不能改整板。")
        for block in blocks:
            if block["block_id"] == block_id:
                return block
        raise _unprocessable("目标板块不存在。")

    def _assert_target(self, patch: CompetitionPatchRequest, card_id: str) -> None:
        if patch.block_id is not None and patch.block_id != card_id:
            raise _unprocessable("在途 block_id 必须与补丁目标一致。")

    def _style_only(self, blocks, title, patch: CompetitionPatchRequest):
        if patch.display_op is not None:
            self._assert_target(patch, patch.display_op.card_id)
            target = self._require_block(blocks, patch.display_op.card_id)
            updated = json.loads(canonical_json(target))
            updated["display_overrides"] = _display_overrides(
                patch.display_op.display_overrides.model_dump(mode="json"),
            )
            blocks = [updated if block["block_id"] == target["block_id"] else block for block in blocks]
            return blocks, title, [target["block_id"]]
        if isinstance(patch.cockpit_op, AnalyticsCockpitLayoutOp):
            return self._layout_block(blocks, title, patch, patch.cockpit_op)
        raise _unprocessable("STYLE_ONLY 只允许 display_op 或 layout。")

    def _layout_block(self, blocks, title, patch, op: AnalyticsCockpitLayoutOp):
        self._assert_target(patch, op.card_id)
        target = self._require_block(blocks, op.card_id)
        updated = json.loads(canonical_json(target))
        updated["layout"] = _layout(op.layout.model_dump(mode="json"))
        blocks = [updated if block["block_id"] == target["block_id"] else block for block in blocks]
        return blocks, title, [target["block_id"]]

    def _add_block(self, principal, blocks, title, patch, op: AnalyticsCockpitAddOp):
        if len(blocks) >= MAX_CARDS:
            raise _unprocessable("驾驶舱板块数量已达上限。")
        trusted = self._resolve_card(principal, op.analysis_ref.analysis_id, op.analysis_ref.version)
        block_id = stable_id("block", patch.attempt_id, op.analysis_ref.analysis_id, str(op.analysis_ref.version))
        layout = op.layout.model_dump(mode="json") if op.layout is not None else _next_layout(blocks)
        display = {} if op.display_overrides is None else _display_overrides(op.display_overrides.model_dump(mode="json"))
        block = {
            "block_id": block_id,
            "card_id": block_id,
            "plugin_ref": dict(PLUGIN_TABLE),
            "analysis_ref": dict(trusted["analysis_ref"]),
            "result_id": (trusted["snapshot"]["computed_result"]["result_id"]
                          if is_computed_reference(op.analysis_ref.analysis_id) else trusted["snapshot"]["run_id"]),
            "run_id": trusted["snapshot"]["run_id"],
            "evidence_digest": trusted["snapshot"]["evidence_digest"],
            "data_mode": "SNAPSHOT",
            "layout": _layout(layout),
            "display_overrides": display,
            "filter_mapping": {},
            "local_filters": {},
            "filter_hash": trusted["filter_hash"],
            "freshness": "PINNED",
        }
        blocks.append(block)
        return blocks, title, [block_id]

    def _copy_block(self, blocks, title, patch, op: AnalyticsCockpitCopyOp):
        if len(blocks) >= MAX_CARDS:
            raise _unprocessable("驾驶舱板块数量已达上限。")
        self._assert_target(patch, op.card_id)
        target = self._require_block(blocks, op.card_id)
        clone = json.loads(canonical_json(target))
        clone["block_id"] = stable_id("block", patch.attempt_id, "copy", target["block_id"])
        clone["card_id"] = clone["block_id"]
        clone["layout"] = _copy_layout(target["layout"])
        blocks.append(clone)
        return blocks, title, [clone["block_id"]]

    def _remove_block(self, blocks, title, patch, op: AnalyticsCockpitRemoveOp):
        self._assert_target(patch, op.card_id)
        self._require_block(blocks, op.card_id)
        remaining = [block for block in blocks if block["block_id"] != op.card_id]
        return remaining, title, [op.card_id]

    def _undo(self, con, principal, row, op: AnalyticsCockpitUndoOp):
        if op.restore_from_version >= row["version"]:
            raise _unprocessable("只能从当前版本之前的配置恢复。")
        prior = self.store.board_row(con, principal, row["board_id"], op.restore_from_version)
        if prior is None:
            raise _missing()
        restored = json.loads(prior["blocks_json"])
        for block in restored:
            self._resolve_card(principal, block["analysis_ref"]["analysis_id"], block["analysis_ref"]["version"])
        return restored, prior["title"], [block["block_id"] for block in restored]

    def _hydrate_block(self, principal: AnalyticsPrincipal, block: dict[str, Any]) -> dict[str, Any]:
        payload = dict(block)
        payload["card_id"] = block["block_id"]
        try:
            ref = block.get("analysis_ref") or {}
            trusted = self._resolve_card(principal, ref["analysis_id"], ref["version"])
            if trusted["snapshot"]["evidence_digest"] != block.get("evidence_digest"):
                raise AnalyticsError(409, "BINDING_CORRUPT", "板块冻结快照与保存分析不一致。")
            local_filters = block.get("local_filters") if isinstance(block.get("local_filters"), dict) else {}
            result = competition_result_item(self._analysis(principal, ref["analysis_id"], ref["version"]))
            if is_computed_reference(ref["analysis_id"]):
                if any(result[key] != block.get(key) for key in ("result_id", "run_id")):
                    raise AnalyticsError(409, "BINDING_CORRUPT", "板块结果与冻结的诊断执行不一致。")
            else:
                result["result_id"] = result["primary_result_ref"] = block["result_id"]
            payload.update({
                "result": result,
                "snapshot": dict(trusted["snapshot"]),
                "facts": dict(trusted["facts"]),
                "limitations": list(trusted["limitations"]),
                "filter_hash": trusted["filter_hash"],
                "plugin_ref": dict(PLUGIN_TABLE),
                "effective_spec_hash": _spec_hash(trusted["analysis_ref"], trusted["snapshot"], local_filters),
                "source_status": "OK",
                "freshness": "PINNED",
                "data_mode": "SNAPSHOT",
            })
            return payload
        except AnalyticsError as error:
            if error.status not in {403, 404, 409, 422}:
                raise
            return {
                "block_id": block.get("block_id") or "block_unavailable",
                "card_id": block.get("block_id") or "card_unavailable",
                "analysis_ref": block.get("analysis_ref"),
                "data_mode": "SNAPSHOT",
                "layout": block.get("layout") or {"x": 0, "y": 0, "w": 6, "h": 4},
                "plugin_ref": dict(PLUGIN_TABLE),
                "freshness": "PINNED",
                "source_status": "UNAVAILABLE",
                "error": {"code": error.code, "message": (error.message or "板块来源不可用。")[:200]},
            }
