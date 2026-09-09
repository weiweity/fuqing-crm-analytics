"""Inherit or explicitly change C0 conditions. Does not shift leap days."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.contracts.competition_c0 import CompetitionCondition, SampleMode
from backend.services.analytics.competition_diagnosis.chain import (
    CONDITION_CONSTANTS,
    CONDITION_FIELDS,
    INHERITABLE_FIELDS,
    PERIOD_CHANGE_REQUIRES_COMPARISON,
)
from backend.services.analytics.competition_diagnosis.errors import (
    invalid_request,
    needs_input,
)

def project_condition(source: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = dict(CONDITION_CONSTANTS)
    for key in CONDITION_FIELDS:
        if key in CONDITION_CONSTANTS:
            continue
        if key in source:
            payload[key] = source[key]
    return payload


def _reject_injection(payload: dict[str, Any], request_id: str) -> None:
    if "owner_id" in payload or "actor_id" in payload or "permission_scope" in payload:
        raise invalid_request("条件不得由客户端指定 owner/actor/permission_scope。", request_id, "owner_id")
    metric = payload.get("metric_type", "GSV")
    if metric != "GSV":
        raise invalid_request("工具必须显式传 GSV，不得继承旧 table 的 GMV 默认。", request_id, "metric_type")
    extra = set(payload) - set(CONDITION_FIELDS)
    if extra:
        raise invalid_request("条件含未声明字段。", request_id, sorted(extra)[0])


def _validate(payload: dict[str, Any], request_id: str) -> CompetitionCondition:
    try:
        return CompetitionCondition.model_validate(payload)
    except ValidationError as error:
        loc = "condition"
        if error.errors():
            first = error.errors()[0]
            if first.get("loc"):
                loc = str(first["loc"][-1])
        raise invalid_request("条件与 competition-condition/v1 不匹配。", request_id, loc) from error


def resolve_condition(
    *,
    prior: dict[str, Any] | None,
    mode: str,
    condition: dict[str, Any] | None,
    condition_patch: dict[str, Any] | None,
    request_id: str,
) -> tuple[CompetitionCondition, dict[str, Any]]:
    if mode not in {"INHERIT", "EXPLICIT"}:
        raise invalid_request("condition_mode 只允许 INHERIT 或 EXPLICIT。", request_id, "condition_mode")
    if mode == "INHERIT":
        if condition is not None or condition_patch:
            raise invalid_request("INHERIT 不得同时提交 condition 或 condition_patch。", request_id, "condition_mode")
        if prior is None:
            raise needs_input("无先验条件时不能继承，请提交完整 Condition。", request_id, "condition")
        payload = project_condition(prior)
        _reject_injection(payload, request_id)
        parsed = _validate(payload, request_id)
        trace = {
            "mode": "INHERIT",
            "inherited_fields": list(INHERITABLE_FIELDS),
            "changed_fields": [],
            "sample_mode": parsed.sample_mode.value,
        }
        return parsed, trace

    if condition is not None and condition_patch:
        raise invalid_request("EXPLICIT 只能提交完整 condition 或 condition_patch 之一。", request_id, "condition")
    if condition is not None:
        _reject_injection(condition, request_id)
        merged = dict(CONDITION_CONSTANTS)
        merged.update({key: condition[key] for key in CONDITION_FIELDS if key in condition})
        parsed = _validate(merged, request_id)
        changed = [key for key in INHERITABLE_FIELDS if key in condition]
        trace = {
            "mode": "EXPLICIT",
            "inherited_fields": [],
            "changed_fields": changed,
            "sample_mode": parsed.sample_mode.value,
        }
        return parsed, trace

    patch = condition_patch or {}
    if not isinstance(patch, dict):
        raise invalid_request("condition_patch 必须是对象。", request_id, "condition_patch")
    _reject_injection(patch, request_id)
    extra = set(patch) - set(INHERITABLE_FIELDS)
    if extra:
        raise invalid_request("condition_patch 含不可变更字段。", request_id, sorted(extra)[0])
    if prior is None:
        if "current_period" not in patch or "comparison_period" not in patch or "comparison_mode" not in patch:
            raise needs_input("无先验时显式变更必须同时给出本期与对比期。", request_id, "current_period")
        base = {
            "sales_scope": {"kind": "ALL", "channel_ids": [], "product_ids": []},
            "history_scope": {"kind": "ALL", "channel_ids": [], "product_ids": []},
            "sample_mode": SampleMode.INCLUDE.value,
            "sample_channel_ids": None,
        }
        inherited: list[str] = []
    else:
        base = project_condition(prior)
        inherited = [key for key in INHERITABLE_FIELDS if key not in patch]
        if set(patch) & PERIOD_CHANGE_REQUIRES_COMPARISON:
            if "comparison_period" not in patch:
                raise needs_input(
                    "变更本期或对比方式时必须显式给 comparison_period，适配器不自行闰日平移。",
                    request_id, "comparison_period",
                )
    merged = dict(CONDITION_CONSTANTS)
    merged.update({key: base[key] for key in CONDITION_FIELDS if key in base and key not in CONDITION_CONSTANTS})
    merged.update(patch)
    parsed = _validate(merged, request_id)
    if parsed.sample_mode != SampleMode.INCLUDE and not parsed.sample_channel_ids:
        raise needs_input("剔除小样必须显式 sample_channel_ids；不得猜派样渠道。", request_id, "sample_channel_ids")
    trace = {
        "mode": "EXPLICIT",
        "inherited_fields": inherited,
        "changed_fields": list(patch),
        "sample_mode": parsed.sample_mode.value,
    }
    return parsed, trace
