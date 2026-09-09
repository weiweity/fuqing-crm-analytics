"""Pin last-year membership. Observation F/RFM must not reselect the set."""

from __future__ import annotations

from datetime import date

from backend.contracts.competition_c0 import (
    CompetitionCohortSpec,
    InclusiveDateRange,
    MemberMark,
    SourceTense,
)
from backend.semantic.analytics_handoff_audience import audience_digest
from backend.services.analytics.competition_audience.errors import invalid
from backend.services.analytics.competition_audience.features import (
    CohortFeatureSource,
    load_cohort_features,
)

HANDOFF_FAMILY = "analytics-handoff-audience/v1"


def _window_after(left: InclusiveDateRange, right: InclusiveDateRange) -> bool:
    return left.end_date < right.start_date


def validate_cohort_windows(spec: CompetitionCohortSpec) -> None:
    if spec.existing_family == HANDOFF_FAMILY:
        raise invalid(
            "handoff-audience 不得冒充去年 F≥4 固定 cohort。",
            param="existing_family",
        )
    if spec.member_history_status != "UNKNOWN":
        raise invalid("会员历史不存在时必须为 UNKNOWN。", param="member_history_status")
    if not _window_after(spec.enrollment_window, spec.observation_window):
        raise invalid("观察窗必须晚于入组窗。", param="observation_window")
    enroll_day = spec.as_of.date()
    if enroll_day < spec.enrollment_window.start_date or enroll_day > spec.enrollment_window.end_date:
        raise invalid("入组 as_of 必须落在入组窗内，不得用本期 as_of 重选。", param="as_of")
    observe_start: date = spec.observation_window.start_date
    if enroll_day >= observe_start:
        raise invalid("不得用观察期 as_of 当作入组快照。", param="as_of")


def pin_membership(
    spec: CompetitionCohortSpec,
    source: CohortFeatureSource,
) -> tuple[tuple[str, ...], str]:
    """Freeze enrollment keys at spec.as_of. Does not read observation F."""
    validate_cohort_windows(spec)
    pin_kwargs = {
        "permission_scope": spec.permission_scope,
        "as_of": spec.as_of,
        "enrollment_window": spec.enrollment_window,
        "source_tense": spec.source_tense.value if isinstance(spec.source_tense, SourceTense) else spec.source_tense,
        "data_version": spec.enrollment_rule_version,
        "rule_version": spec.enrollment_rule_version,
    }
    try:
        raw = source.pinned_enrollment_keys(**pin_kwargs, cohort_id=spec.cohort_id)
    except TypeError:
        raw = source.pinned_enrollment_keys(**pin_kwargs)
    seen: list[str] = []
    for key in raw:
        if type(key) is not str or not key:
            raise invalid("入组 customer_key 必须是非空字符串。", param="customer_key")
        if key not in seen:
            seen.append(key)
    bundle = load_cohort_features(
        permission_scope=spec.permission_scope,
        customer_keys=tuple(seen),
        as_of=spec.as_of,
        history_scope={"kind": "ALL", "channel_ids": [], "product_ids": []},
        sample_mode="INCLUDE",
        source_tense=spec.source_tense.value if isinstance(spec.source_tense, SourceTense) else spec.source_tense,
        data_version=spec.enrollment_rule_version,
        rule_version=spec.enrollment_rule_version,
        source=source,
    )
    if bundle.member_history_available:
        raise invalid("夹具/接口声称有会员历史时仍须由 A2 核验；当前不得当作已知。", param="member_history_status")
    if any(row.member_status_as_of != "unknown" for row in bundle.rows):
        raise invalid("会员历史不存在则 UNKNOWN，不得用当前 is_member 回填。", param="member_mark")
    if any(rule.member_mark != MemberMark.UNKNOWN for rule in spec.rules):
        raise invalid("无历史会员维时 member_mark 只能是 UNKNOWN。", param="member_mark")
    digest = audience_digest(seen, spec.enrollment_rule_version)
    return tuple(seen), digest
