"""Map diagnosis steps onto frozen C0 fixtures. Does not recompute metrics."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from backend.contracts.competition_c0 import (
    ACTOR_A,
    AS_OF,
    SCOPE_A,
    Completeness,
    CompetitionCondition,
    CompetitionResultRef,
    SampleMode,
    SupportStatus,
    canonical_json,
    condition_hash_payload,
    empty_result,
    success_candidates,
    success_cohort,
    success_draft,
    success_result,
)
from backend.services.analytics.competition_diagnosis.chain import (
    AUDIENCE_SUMMARY_STEPS,
    SHANGHAI,
)
from backend.services.analytics.competition_diagnosis.errors import not_connected, unsupported_capability

_DATA_VERSION = "synthetic-c0-demo-data/v1"


def last_complete_day(condition: CompetitionCondition) -> date:
    """T+1 yesterday in Asia/Shanghai. as_of 2026-08-31T16:00Z is 9/1 00:00 CST."""
    instant = condition.as_of
    if instant is None:
        return date(2026, 8, 31)
    local = instant.astimezone(ZoneInfo(SHANGHAI)).date()
    return local - timedelta(days=1)


def is_empty_mtd(condition: CompetitionCondition) -> bool:
    return condition.current_period.start_date > last_complete_day(condition)


def echo_resolved(condition: CompetitionCondition, extra_limit: str) -> dict[str, Any]:
    dump = condition.model_dump(mode="json")
    as_of = dump["as_of"] or AS_OF
    published = as_of
    cutoff = (condition.current_period.start_date - timedelta(days=1)).isoformat()
    sample_ids = dump["sample_channel_ids"]
    snapshot = dump["data_snapshot_ref"] or "synthetic-c0-demo-v1"
    rule_version = dump["rule_version"] or "competition-condition-rule/v1"
    recomputed = condition.sample_mode is SampleMode.EXCLUDE_AND_RECOMPUTE_HISTORY
    hash_payload = condition_hash_payload({
        "as_of": as_of,
        "comparison_mode": dump["comparison_mode"],
        "comparison_period": dump["comparison_period"],
        "current_period": dump["current_period"],
        "cutoff": cutoff,
        "data_cutoff_policy": dump["data_cutoff_policy"],
        "data_snapshot_ref": snapshot,
        "data_version": _DATA_VERSION,
        "history_scope": dump["history_scope"],
        "leap_day_alignment": dump["leap_day_alignment"],
        "metric_type": dump["metric_type"],
        "metrics_contract_id": dump["metrics_contract_id"],
        "permission_scope": SCOPE_A,
        "published_at": published,
        "rule_version": rule_version,
        "sales_scope": dump["sales_scope"],
        "sample_channel_ids": sample_ids,
        "sample_mode": dump["sample_mode"],
        "source_tense": "PUBLISHED_SNAPSHOT",
        "timezone": dump["timezone"],
    })
    flags = [item.model_dump(mode="json") for item in success_result().resolved_condition.unknown_flags]
    limits = [extra_limit, "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。"]
    return {
        "schema_version": "competition-condition/v1",
        "metrics_contract_id": dump["metrics_contract_id"],
        "metric_type": "GSV",
        "timezone": SHANGHAI,
        "current_period": dump["current_period"],
        "comparison_mode": dump["comparison_mode"],
        "comparison_period": dump["comparison_period"],
        "cutoff": cutoff,
        "as_of": as_of,
        "published_at": published,
        "event_time": as_of,
        "source_tense": "PUBLISHED_SNAPSHOT",
        "sales_scope": dump["sales_scope"],
        "history_scope": dump["history_scope"],
        "sample_mode": dump["sample_mode"],
        "sample_channel_ids": sample_ids,
        "sample_history_recomputed": recomputed,
        "sample_channel_set_status": "UNKNOWN",
        "data_cutoff_policy": dump["data_cutoff_policy"],
        "leap_day_alignment": dump["leap_day_alignment"],
        "data_snapshot_ref": snapshot,
        "data_version": _DATA_VERSION,
        "rule_version": rule_version,
        "warehouse_as_of": as_of,
        "feature_as_of": as_of,
        "permission_scope": SCOPE_A,
        "actor_id": ACTOR_A,
        "filter_hash": hashlib.sha256(canonical_json(hash_payload).encode()).hexdigest(),
        "ignored_filters": [],
        "unknown_flags": flags,
        "limitations": limits,
    }


def _clone_result(
    template: CompetitionResultRef,
    *,
    capability_id: str,
    completeness: Completeness,
    facts_schema_ref: str,
    existing_result_schema: str,
    extra_limit: str,
    condition: CompetitionCondition | None = None,
    empty_reason: str | None = None,
    row_count: int | None = None,
) -> CompetitionResultRef:
    payload = template.model_dump(mode="json")
    payload["query_id"] = capability_id
    payload["query_version"] = "competition-metrics/v1"
    payload["completeness"] = completeness.value
    payload["facts_schema_ref"] = facts_schema_ref
    payload["existing_result_schema"] = existing_result_schema
    payload["empty_reason"] = empty_reason if completeness == Completeness.EMPTY else None
    payload["result_id"] = f"result_c0_{capability_id.replace('.', '_')}"
    payload["run_id"] = f"run_c0_{capability_id.replace('.', '_')}"
    payload["primary_result_ref"] = payload["result_id"]
    if condition is not None:
        payload["resolved_condition"] = echo_resolved(condition, extra_limit)
        payload["limitations"] = list(payload["resolved_condition"]["limitations"])
    else:
        limits = list(payload["limitations"])
        limits.insert(0, extra_limit)
        payload["limitations"] = limits
        payload["resolved_condition"]["limitations"] = list(limits)
    if row_count is not None:
        payload["row_count"] = row_count
        if payload.get("page"):
            payload["page"]["total"] = row_count
            payload["page"]["complete"] = True
    if completeness in {Completeness.FAILED, Completeness.UNSUPPORTED, Completeness.EMPTY}:
        payload["evidence_digest"] = None
        payload["page"] = None
        payload["analysis_id"] = None
        payload["metric_id"] = None
        payload["metric_version"] = None
        if completeness == Completeness.EMPTY:
            payload["primary_result_ref"] = None
        if completeness in {Completeness.FAILED, Completeness.UNSUPPORTED}:
            payload["row_count"] = 0
            payload["primary_result_ref"] = payload["result_id"]
    return CompetitionResultRef.model_validate(payload)


def fixture_result(capability_id: str, condition: CompetitionCondition, status: SupportStatus) -> CompetitionResultRef:
    if status is SupportStatus.NOT_CONNECTED:
        raise not_connected("该能力 HTTP 尚未接线，离线适配不假装已接通。", "req_offline", capability_id)
    if status is SupportStatus.UNSUPPORTED:
        raise unsupported_capability(
            "当前支持矩阵为 UNSUPPORTED，诚实拒答，不调用旧 handoff-audience 冒充。",
            "req_offline", capability_id,
        )
    if is_empty_mtd(condition):
        return _clone_result(
            empty_result(),
            capability_id=capability_id,
            completeness=Completeness.EMPTY,
            facts_schema_ref="competition-result/v1#empty",
            existing_result_schema="none",
            extra_limit="T+1 无本月可用数据：EMPTY，不比较未来完整月。",
            condition=condition,
            empty_reason="NO_CURRENT_MONTH_DATA",
            row_count=0,
        )
    if capability_id in {"diag.gsv", "diag.yoy", "diag.last_week_same_weekday", "diag.promo_dual_window", "diag.channel", "diag.sample_exclude_current"}:
        schema = "backend.contracts.analytics_query.ChannelFollowupResult"
        existing = "analytics-channel-followup/v1"
        completeness = Completeness.COMPLETE
        extra = "离线步使用 C0 ResultRef 信封，不重复计算渠道事实。"
    elif capability_id in AUDIENCE_SUMMARY_STEPS:
        schema = "backend.contracts.audience.AudienceSummaryResponse"
        existing = "none"
        completeness = Completeness.PARTIAL
        extra = "A2 计算未接线：PARTIAL，facts_schema_ref 指向 AudienceSummaryResponse，不编造交叉数字。"
    else:
        schema = "competition-result/v1#unsupported"
        existing = "none"
        completeness = Completeness.UNSUPPORTED
        extra = "能力未支持。"
    return _clone_result(
        success_result(),
        capability_id=capability_id,
        completeness=completeness,
        facts_schema_ref=schema,
        existing_result_schema=existing,
        extra_limit=extra,
        condition=condition,
        row_count=2,
    )


def unsupported_result(capability_id: str, condition: CompetitionCondition, note: str) -> CompetitionResultRef:
    return _clone_result(
        success_result() if not is_empty_mtd(condition) else empty_result(),
        capability_id=capability_id,
        completeness=Completeness.UNSUPPORTED,
        facts_schema_ref="competition-result/v1#unsupported",
        existing_result_schema="none",
        extra_limit=note,
        condition=condition,
        row_count=0,
    )


def failed_result(capability_id: str, condition: CompetitionCondition, note: str) -> CompetitionResultRef:
    return _clone_result(
        success_result() if not is_empty_mtd(condition) else empty_result(),
        capability_id=capability_id,
        completeness=Completeness.FAILED,
        facts_schema_ref="competition-result/v1#unsupported",
        existing_result_schema="none",
        extra_limit=note,
        condition=condition,
        row_count=0,
    )


def cohort_fixture() -> dict[str, Any]:
    return {
        "cohort": success_cohort().model_dump(mode="json"),
        "candidates": success_candidates().model_dump(mode="json"),
        "draft": success_draft().model_dump(mode="json"),
        "note": "C0 audience fixture 仅作结构；diag.fixed_cohort 当前 UNSUPPORTED，不得当已计算名单。",
    }
