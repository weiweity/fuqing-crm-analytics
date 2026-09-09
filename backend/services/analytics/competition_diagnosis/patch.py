"""Controlled patch planning. STYLE_ONLY does not query; FILTER_CHANGE is a new run."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.contracts.competition_c0 import CompetitionPatchRequest, PatchIntent, SupportStatus
from backend.services.analytics.competition_diagnosis.catalog import capability_by_id
from backend.services.analytics.competition_diagnosis.errors import invalid_patch

_SCRIPTISH = ("<script", "javascript:", "onerror=", "eval(", "function(", "import ", "../", "/etc/")


def _looks_unsafe(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(token in lowered for token in _SCRIPTISH)
    if isinstance(value, dict):
        return any(_looks_unsafe(item) for item in value.values()) or any(_looks_unsafe(key) for key in value)
    if isinstance(value, list):
        return any(_looks_unsafe(item) for item in value)
    return False


def plan_patch(
    *,
    intent: str,
    payload: dict[str, Any],
    selection: dict[str, Any],
    in_flight: dict[str, Any] | None,
    request_id: str,
) -> dict[str, Any]:
    if intent not in {item.value for item in PatchIntent}:
        raise invalid_patch("intent 必须是 STYLE_ONLY / FILTER_CHANGE / STRUCTURE。", request_id, "intent")
    if _looks_unsafe(payload) or _looks_unsafe(selection):
        raise invalid_patch("补丁含脚本、路径穿越或未登记字段。", request_id, "patch")
    target = dict(in_flight) if in_flight is not None else dict(selection)
    for key in ("board_id", "block_id", "base_version"):
        if key not in target:
            raise invalid_patch("点选范围缺少稳定 board_id/block_id/base_version。", request_id, key)
    ignored_ui = False
    if in_flight is not None and selection:
        if any(selection.get(key) != in_flight.get(key) for key in ("board_id", "block_id", "base_version")):
            ignored_ui = True
    body = {
        "schema_version": "competition-board-patch/v1",
        "board_id": target["board_id"],
        "block_id": target["block_id"],
        "base_version": target["base_version"],
        "attempt_id": payload.get("attempt_id") or target.get("attempt_id") or "attempt_c0_offline",
        "idempotency_key": payload.get("idempotency_key") or "patch-offline-1",
        "intent": intent,
        "cockpit_op": payload.get("cockpit_op"),
        "display_op": payload.get("display_op"),
        "filter_change": payload.get("filter_change"),
    }
    try:
        parsed = CompetitionPatchRequest.model_validate(body)
    except ValidationError as error:
        loc = "patch"
        if error.errors() and error.errors()[0].get("loc"):
            loc = str(error.errors()[0]["loc"][-1])
        raise invalid_patch("补丁与 competition-board-patch/v1 不匹配。", request_id, loc) from error
    queries = parsed.intent is PatchIntent.FILTER_CHANGE
    creates_new_run = parsed.intent is PatchIntent.FILTER_CHANGE
    apply_status = "PLANNED_OFFLINE"
    if parsed.intent is PatchIntent.FILTER_CHANGE:
        filt = capability_by_id("board.single_cockpit")
        apply_status = SupportStatus.NOT_CONNECTED.value
        if filt is not None:
            apply_status = SupportStatus.NOT_CONNECTED.value
    return {
        "schema_version": "competition-diagnosis-patch-plan/v1",
        "queries": queries,
        "creates_new_run": creates_new_run,
        "apply_status": apply_status,
        "ignored_ui_selection": ignored_ui,
        "in_flight_target": {
            "board_id": parsed.board_id,
            "block_id": parsed.block_id,
            "base_version": parsed.base_version,
        },
        "patch": parsed.model_dump(mode="json"),
        "limitations": [
            "STYLE_ONLY 不得查询。FILTER_CHANGE 必须新 run，当前 cockpit HTTP 为 NOT_CONNECTED。",
            "UI 切选中不能改写 FastAPI 在途目标。",
        ],
    }
