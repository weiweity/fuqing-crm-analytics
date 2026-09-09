"""Diagnosis chain constants. Does not compute GSV/RFM/cohorts."""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final = "competition-diagnosis-orchestrator/v1"
METRICS_CONTRACT_ID: Final = "competition-metrics/v1"
CONDITION_SCHEMA: Final = "competition-condition/v1"
RESULT_SCHEMA: Final = "competition-result/v1"
PATCH_SCHEMA: Final = "competition-board-patch/v1"
SHANGHAI: Final = "Asia/Shanghai"
STUB_PLANNER: Final = "OFFLINE_STUB"
LIVE_TRANSPORT: Final = "NOT_CONNECTED"

# Model-visible tools. Old CRM routes are not in this list.
REGISTERED_TOOLS: Final[tuple[str, ...]] = (
    "competition_growth_skill_resource",
    "competition_growth_capabilities",
    "competition_growth_step",
    "competition_growth_patch",
)

RESOURCE_TOOL: Final = REGISTERED_TOOLS[0]
CAPABILITIES_TOOL: Final = REGISTERED_TOOLS[1]
STEP_TOOL: Final = REGISTERED_TOOLS[2]
PATCH_TOOL: Final = REGISTERED_TOOLS[3]
SKILL_NAME: Final = "competition-growth"

DIAGNOSIS_CHAIN: Final[tuple[str, ...]] = (
    "diag.gsv",
    "diag.comparison",
    "diag.channel",
    "diag.sample",
    "diag.new_old",
    "diag.member",
    "diag.product",
    "diag.rfm",
    "diag.fixed_cohort",
    "diag.non_repurchase",
    "action.draft",
)

COMPARISON_BY_MODE: Final[dict[str, str]] = {
    "YOY_SAME_PERIOD": "diag.yoy",
    "LAST_WEEK_SAME_WEEKDAY": "diag.last_week_same_weekday",
    "CUSTOM_DUAL_WINDOW": "diag.promo_dual_window",
}

SAMPLE_BY_MODE: Final[dict[str, str | None]] = {
    "INCLUDE": None,
    "EXCLUDE_CURRENT_SALES_ONLY": "diag.sample_exclude_current",
    "EXCLUDE_AND_RECOMPUTE_HISTORY": "diag.sample_recompute_history",
}

STEP_CAPABILITIES: Final[frozenset[str]] = frozenset({
    "diag.gsv",
    "diag.yoy",
    "diag.last_week_same_weekday",
    "diag.promo_dual_window",
    "diag.channel",
    "diag.sample_exclude_current",
    "diag.sample_recompute_history",
    "diag.new_old",
    "diag.member",
    "diag.product",
    "diag.rfm",
    "diag.fixed_cohort",
    "diag.non_repurchase",
    "action.draft",
})

REQUIRED_FOR_COMPLETE_CHAIN: Final[frozenset[str]] = frozenset({
    "diag.gsv",
    "diag.comparison",
    "diag.channel",
    "diag.new_old",
    "diag.member",
    "diag.product",
    "diag.rfm",
    "diag.fixed_cohort",
    "diag.non_repurchase",
})

AUDIENCE_SUMMARY_STEPS: Final[frozenset[str]] = frozenset({
    "diag.gsv",
    "diag.yoy",
    "diag.last_week_same_weekday",
    "diag.promo_dual_window",
    "diag.channel",
    "diag.sample_exclude_current",
    "diag.new_old",
    "diag.member",
    "diag.product",
    "diag.rfm",
})

FORBIDDEN_EXPANSIONS: Final[tuple[str, ...]] = (
    "/api/v1/audience/table",
    "/api/v1/audience/summary",
    "/api/v1/analytics/catalog",
    "analytics_b0_query",
    "analytics_channel_followup_query",
    "analytics_first_purchase_query",
    "execute_sql",
    "run_script",
    "shell",
)

INHERITABLE_FIELDS: Final[tuple[str, ...]] = (
    "current_period",
    "comparison_mode",
    "comparison_period",
    "sales_scope",
    "history_scope",
    "sample_mode",
    "sample_channel_ids",
    "data_snapshot_ref",
    "as_of",
    "rule_version",
)

CONDITION_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "metrics_contract_id",
    "metric_type",
    "timezone",
    "current_period",
    "comparison_mode",
    "comparison_period",
    "sales_scope",
    "history_scope",
    "sample_mode",
    "sample_channel_ids",
    "data_cutoff_policy",
    "leap_day_alignment",
    "data_snapshot_ref",
    "as_of",
    "rule_version",
)

CONDITION_CONSTANTS: Final[dict[str, str]] = {
    "schema_version": CONDITION_SCHEMA,
    "metrics_contract_id": METRICS_CONTRACT_ID,
    "metric_type": "GSV",
    "timezone": SHANGHAI,
    "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
    "leap_day_alignment": "CLAMP_TO_MONTH_END",
}

PERIOD_CHANGE_REQUIRES_COMPARISON: Final[frozenset[str]] = frozenset({
    "current_period",
    "comparison_mode",
})

DEFAULT_BUDGET: Final[dict[str, int]] = {
    "max_tool_calls": 12,
    "max_deadline_ms": 30000,
    "max_concurrent": 1,
    "max_retries": 2,
}

DOC_T03: Final = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T03"
DOC_T06: Final = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06"
DOC_T08: Final = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T08"
DOC_T10: Final = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T10"
DOC_T13: Final = "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T13"
