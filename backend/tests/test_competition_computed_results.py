"""Independent arithmetic for computed diagnosis; no C0/A9 numeric fixtures."""
from copy import deepcopy

import duckdb
import pytest
from pydantic import ValidationError

from backend.contracts.competition_c0 import CompetitionCondition
from backend.contracts.competition_computed import CompetitionComputedResult, DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.synthetic import materialize_synthetic_source

PRINCIPAL = AnalyticsPrincipal("alice", frozenset({"analysis:read", "analysis:save"}), frozenset({DATA_SCOPE}))


def condition(**overrides):
    payload = {"metric_type": "GSV", "timezone": "Asia/Shanghai",
               "current_period": {"start_date": "2026-08-01", "end_date": "2026-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
               "comparison_period": {"start_date": "2025-08-01", "end_date": "2025-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
               "comparison_mode": "YOY_SAME_PERIOD", "sales_scope": {"kind": "ALL"}, "history_scope": {"kind": "ALL"},
               "sample_mode": "INCLUDE", "sample_channel_ids": None, "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
               "leap_day_alignment": "CLAMP_TO_MONTH_END"}
    payload.update(overrides)
    return CompetitionCondition.model_validate(payload)


def snapshot():
    rows = [("P1", "1", "2025-08-05", 100, "CH_RETAIL"), ("P2", "1", "2025-08-18", 40, "CH_RETAIL"),
            ("PS", "1", "2025-08-15", 5, "CH_SAMPLE"), ("C1", "1", "2026-08-05", 30, "CH_RETAIL"),
            ("C1", "2", "2026-08-05", 60, "CH_RETAIL"), ("C2", "1", "2026-08-10", 60, "CH_RETAIL"),
            ("CS", "1", "2026-08-15", 10, "CH_SAMPLE")]
    return {"contains_real_data": False, "snapshot_id": "independent-arithmetic-v1", "data_version": "independent/v1",
            "published_at": "2026-09-01T00:00:00+08:00", "coverage_start": "2025-01-01", "data_through": "2026-08-31",
            "orders": [{"order_id": oid, "sub_order_id": line, "user_id": "U-" + oid, "pay_time": day + " 12:00:00",
                        "channel": channel, "actual_amount": amount, "is_member": None, "is_refund": False,
                        "is_goujinjin": False, "order_status": "交易成功", "product_id": "P-S" if channel == "CH_SAMPLE" else "P-R",
                        "spu_type": "正装"} for oid, line, day, amount, channel in rows],
            "refunds": [{"order_id": "P2", "refunded_at": "2025-08-20", "amount": 10},
                        {"order_id": "C2", "refunded_at": "2026-08-25", "amount": 20}]}


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir(mode=0o700)
    return materialize_synthetic_source(folder, snapshot())


def calculate(source, request=None, cap="diag.gsv", actor=PRINCIPAL):
    return compute_result(source, actor, request or condition(), cap, session_id="session-1", request_id="request-1")


def test_two_period_arithmetic_and_order_grain(source):
    result = calculate(source)
    assert result.facts.current.gsv == 140  # 30+60+60-20+10
    assert result.facts.comparison.gsv == 135  # 100+40-10+5
    assert result.facts.difference == 5
    assert result.facts.change_ratio == pytest.approx(5 / 135)
    assert result.facts.current.order_count == result.facts.current.customer_count == 3
    assert result.row_count == 2 and result.completeness.value == "COMPLETE"
    assert result.execution_kind == "TOOL_COMPUTATION"
    assert result.analysis_id is None
    assert result.resolved_condition.actor_id == "alice"
    assert result.resolved_condition.sample_channel_set_status == "UNKNOWN"
    assert {row.code for row in result.resolved_condition.unknown_flags} == {"SAMPLE_CHANNEL_SET", "MEMBER_HISTORY"}
    assert CompetitionComputedResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("scope", [
    {"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]},
    {"kind": "PRODUCT_IDS", "product_ids": ["P-R"]},
    {"kind": "CHANNEL_AND_PRODUCT", "channel_ids": ["CH_RETAIL"], "product_ids": ["P-R"]},
])
def test_sales_scopes_apply_to_both_periods(source, scope):
    result = calculate(source, condition(sales_scope=scope))
    assert result.facts.current.gsv == result.facts.comparison.gsv == 130
    assert result.facts.change_ratio == 0
    assert result.resolved_condition.sales_scope.model_dump(exclude_defaults=True) == condition(sales_scope=scope).sales_scope.model_dump(exclude_defaults=True)


@pytest.mark.parametrize("mode", ["EXCLUDE_CURRENT_SALES_ONLY", "EXCLUDE_AND_RECOMPUTE_HISTORY"])
def test_explicit_sample_modes(source, mode):
    result = calculate(source, condition(sample_mode=mode, sample_channel_ids=["CH_SAMPLE"],
                                        history_scope={"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL", "CH_SAMPLE"]}))
    assert result.facts.current.gsv == result.facts.comparison.gsv == 130
    assert result.resolved_condition.sample_history_recomputed == (mode == "EXCLUDE_AND_RECOMPUTE_HISTORY")


def test_as_of_excludes_later_refund_and_clamps_effective_end(source):
    result = calculate(source, condition(as_of="2026-08-20T00:00:00+08:00"))
    assert result.facts.current.gsv == 160
    assert str(result.facts.current.through_date) == "2026-08-19"
    assert str(result.facts.comparison.through_date) == "2025-08-31"
    assert result.evidence_digest != calculate(source).evidence_digest


@pytest.mark.parametrize("mode,cap,compare", [
    ("CUSTOM_DUAL_WINDOW", "diag.promo_dual_window", ("2025-08-05", "2025-08-12")),
    ("LAST_WEEK_SAME_WEEKDAY", "diag.last_week_same_weekday", ("2026-07-29", "2026-08-05")),
])
def test_comparison_modes(source, mode, cap, compare):
    request = condition(comparison_mode=mode,
        current_period={"start_date": "2026-08-05", "end_date": "2026-08-12", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
        comparison_period={"start_date": compare[0], "end_date": compare[1], "end_bound": "INCLUSIVE_CALENDAR_DAY"})
    result = calculate(source, request, cap)
    assert result.facts.current.gsv == 130
    assert result.facts.comparison.gsv == (100 if mode == "CUSTOM_DUAL_WINDOW" else 90)


@pytest.mark.parametrize("overrides", [
    {"data_snapshot_ref": "foreign-snapshot"}, {"rule_version": "unknown-rule"},
    {"as_of": "2026-09-02T00:00:00+08:00"},
    {"comparison_period": {"start_date": "2025-08-02", "end_date": "2025-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"}},
])
def test_mismatched_metadata_is_not_silently_rewritten(source, overrides):
    with pytest.raises(AnalyticsError) as exc:
        calculate(source, condition(**overrides))
    assert exc.value.status == 422


def test_unavailable_month_is_not_zero_sales(source):
    request = condition(comparison_mode="CUSTOM_DUAL_WINDOW",
        current_period={"start_date": "2026-09-01", "end_date": "2026-09-30", "end_bound": "INCLUSIVE_CALENDAR_DAY"},
        comparison_period={"start_date": "2026-08-01", "end_date": "2026-08-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"})
    result = calculate(source, request)
    assert result.completeness.value == "EMPTY" and result.row_count == 0
    assert result.empty_reason == "NO_CURRENT_MONTH_DATA"
    assert result.facts.current.gsv is None and result.facts.comparison.gsv == 140
    assert result.facts.change_ratio is None and result.facts.change_ratio_unavailable_reason == "PERIOD_UNAVAILABLE"


@pytest.mark.parametrize("both_zero", [True, False])
def test_zero_comparison_returns_null_ratio(source, both_zero):
    request = condition(comparison_mode="CUSTOM_DUAL_WINDOW",
        sales_scope={"kind": "CHANNEL_IDS", "channel_ids": ["NO-SUCH-CHANNEL"]} if both_zero else {"kind": "ALL"},
        comparison_period={"start_date": "2025-01-01", "end_date": "2025-01-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"})
    result = calculate(source, request)
    assert result.completeness.value == "COMPLETE"
    assert result.facts.current.gsv == (0 if both_zero else 140)
    assert result.facts.comparison.gsv == 0
    assert result.facts.change_ratio is None
    assert result.facts.change_ratio_unavailable_reason == "ZERO_COMPARISON_GSV"


def test_current_permissions_and_corrupt_snapshot_fail(source):
    with pytest.raises(AnalyticsError) as exc:
        calculate(source, actor=AnalyticsPrincipal("alice", frozenset(), PRINCIPAL.data_scopes))
    assert exc.value.status == 403
    with source.connect() as conn:
        with pytest.raises(duckdb.InvalidInputException):
            conn.execute("DELETE FROM orders")
    source.path.write_bytes(source.path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="snapshot changed"):
        calculate(source)


@pytest.mark.parametrize("field,value", [("evidence_digest", "0" * 64), ("schema_version", "competition-result/v1"),
                                        ("contains_real_data", True), ("facts_schema_ref", "backend.contracts.analytics_query.ChannelFollowupResult")])
def test_forged_or_foreign_result_rejected(source, field, value):
    payload = calculate(source).model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError):
        CompetitionComputedResult.model_validate(payload)


def test_changed_facts_cannot_keep_old_evidence(source):
    payload = deepcopy(calculate(source).model_dump(mode="json"))
    payload["facts"]["current"]["gsv"] = 145
    payload["facts"]["difference"] = 10
    payload["facts"]["change_ratio"] = 10 / 135
    with pytest.raises(ValidationError, match="evidence digest"):
        CompetitionComputedResult.model_validate(payload)
