"""Independent arithmetic for computed diagnosis; no C0/A9 numeric fixtures."""
from copy import deepcopy
from datetime import date, timedelta
import json
import math
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from backend.contracts.competition_c0 import CompetitionCondition
from backend.contracts.competition_computed import (CompetitionComputedResult, CompetitionGsvFacts,
                                                    CompetitionGsvFactsV2, CompetitionGsvFactsV3,
                                                    CompetitionGsvFactsV4, CompetitionGsvFactsV5, DATA_SCOPE,
                                                    reconciles)
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.synthetic import materialize_synthetic_source
from backend.services.analytics.resource_profile import content_hash

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
    assert result.result_id != result.run_id
    assert result.result_id.startswith("result_diag_")
    assert result.run_id.startswith("run_diag_")
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


def test_unimplemented_capability_refuses_without_inventing_facts(source):
    with pytest.raises(AnalyticsError) as exc:
        calculate(source, cap="diag.rfm")
    assert exc.value.status == 422
    assert exc.value.code == "UNSUPPORTED_CAPABILITY"
    assert "尚未实现所请求的诊断能力" in exc.value.message


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
    payload["facts"]["current_daily"]["points"][4]["gsv"] += 5
    payload["facts"]["difference"] = 10
    payload["facts"]["change_ratio"] = 10 / 135
    with pytest.raises(ValidationError, match="evidence digest"):
        CompetitionComputedResult.model_validate(payload)


def test_legacy_v1_roundtrip_keeps_original_facts_and_digest():
    path = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed/result.json"
    original = json.loads(path.read_text())
    parsed = CompetitionComputedResult.model_validate(original)
    assert parsed.model_dump(mode="json") == original
    assert "money_unit" not in parsed.facts.model_dump(mode="json")


def test_undeclared_unit_is_unknown_without_changing_source_digest(source):
    result = calculate(source)
    assert result.result_id != result.run_id
    assert result.facts.schema_version == "competition-gsv-facts/v5"
    assert result.facts.money_unit.model_dump() == {"status": "UNKNOWN", "currency": None, "amount_unit": None}
    # The existing loader normalizes publication time to UTC before hashing.
    assert result.data_digest == content_hash({**snapshot(), "published_at": "2026-08-31T16:00:00.000000+00:00"})


@pytest.mark.parametrize("denomination", ["major", "minor"])
def test_declared_unit_preserves_raw_arithmetic_and_is_bound_to_evidence(tmp_path, source, denomination):
    declared = snapshot()
    declared["money_unit"] = {"status": "KNOWN", "currency": "CNY", "amount_unit": denomination}
    folder = tmp_path / "declared"
    folder.mkdir(mode=0o700)
    result = calculate(materialize_synthetic_source(folder, declared))
    original = calculate(source)
    assert result.facts.money_unit.model_dump() == declared["money_unit"]
    assert result.facts.current.gsv == original.facts.current.gsv == 140
    assert result.facts.change_ratio == original.facts.change_ratio
    assert result.data_digest != original.data_digest
    assert result.evidence_digest != original.evidence_digest
    forged = result.model_dump(mode="json")
    forged["facts"]["money_unit"]["amount_unit"] = "minor" if denomination == "major" else "major"
    with pytest.raises(ValidationError, match="evidence digest"):
        CompetitionComputedResult.model_validate(forged)


@pytest.mark.parametrize("unit", [
    None, {"status": "KNOWN"}, {"status": "UNKNOWN", "currency": "CNY"},
    {"status": "KNOWN", "currency": "CNY", "amount_unit": "yuan"},
    {"status": "KNOWN", "currency": "USD", "amount_unit": "major"},
    {"status": "UNKNOWN", "scale": 100},
])
def test_malformed_source_units_fail_before_database_creation(tmp_path, unit):
    folder = tmp_path / "invalid-unit"
    folder.mkdir(mode=0o700)
    with pytest.raises(ValidationError):
        materialize_synthetic_source(folder, {**snapshot(), "money_unit": unit})
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("field,value", [
    ("facts_schema_ref", "backend.contracts.competition_computed.CompetitionGsvFacts"),
    ("existing_result_schema", "competition-gsv-facts/v1"),
])
def test_v2_rejects_mismatched_facts_references(source, field, value):
    forged = calculate(source).model_dump(mode="json")
    forged[field] = value
    with pytest.raises(ValidationError, match="facts schema references"):
        CompetitionComputedResult.model_validate(forged)


def test_ui_unit_fixtures_match_actual_computation():
    import runpy

    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    actual = runpy.run_path(str(folder / "unit-fixtures.py"))["fixtures"]()
    assert actual == json.loads((folder / "funnel-results.json").read_text())
    for result in actual.values():
        CompetitionComputedResult.model_validate(result)


def test_legacy_v2_roundtrip_keeps_original_facts_and_digest():
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    for original in json.loads((folder / "unit-results.json").read_text()).values():
        parsed = CompetitionComputedResult.model_validate(original)
        assert parsed.model_dump(mode="json") == original
        assert "current_daily" not in parsed.facts.model_dump(mode="json")


def test_legacy_v3_roundtrip_keeps_original_facts_and_digest():
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    for original in json.loads((folder / "daily-results.json").read_text()).values():
        parsed = CompetitionComputedResult.model_validate(original)
        assert parsed.model_dump(mode="json") == original
        assert "channel_bridge" not in parsed.facts.model_dump(mode="json")


def test_legacy_v4_roundtrip_keeps_original_facts_and_digest():
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    for original in json.loads((folder / "waterfall-results.json").read_text()).values():
        parsed = CompetitionComputedResult.model_validate(original)
        assert parsed.model_dump(mode="json") == original
        assert "current_purchase_frequency" not in parsed.facts.model_dump(mode="json")


def test_daily_uses_effective_order_grain_and_cutoff_refunds(source):
    result = calculate(source)
    daily = result.facts.current_daily
    assert daily.status == "AVAILABLE" and daily.unavailable_reason is None
    assert len(daily.points) == 31
    assert [(str(p.date), p.gsv, p.order_count) for p in daily.points if p.order_count] == [
        ("2026-08-05", 90, 1), ("2026-08-10", 40, 1), ("2026-08-15", 10, 1)]
    assert daily.points[24].gsv == 0  # refund is NOT negative cashflow on Aug 25
    assert sum(p.gsv for p in daily.points) == result.facts.current.gsv == 140
    earlier = calculate(source, condition(as_of="2026-08-20T00:00:00+08:00")).facts.current_daily
    assert earlier.points[9].gsv == 60  # late refund not yet known
    assert all(p.gsv == 0 for p in earlier.points[15:19])
    assert all(p.gsv is None and p.order_count == 0 for p in earlier.points[19:])


@pytest.mark.parametrize("query_condition", [
    condition(sales_scope={"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]}),
    condition(sales_scope={"kind": "PRODUCT_IDS", "product_ids": ["P-R"]}),
    condition(sample_mode="EXCLUDE_CURRENT_SALES_ONLY", sample_channel_ids=["CH_SAMPLE"]),
    condition(sample_mode="EXCLUDE_AND_RECOMPUTE_HISTORY", sample_channel_ids=["CH_SAMPLE"],
              history_scope={"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL", "CH_SAMPLE"]}),
])
def test_daily_respects_same_filters_as_summary(source, query_condition):
    facts = calculate(source, query_condition).facts
    assert sum(p.gsv for p in facts.current_daily.points) == facts.current.gsv == 130
    assert facts.current_daily.points[14].gsv == 0


def test_daily_leap_day_and_large_window_have_no_silent_truncation(tmp_path):
    folder = tmp_path / "calendar"
    folder.mkdir(mode=0o700)
    source = materialize_synthetic_source(folder, {**snapshot(), "coverage_start": "2024-01-01"})
    def for_range(start, end):
        return calculate(source, condition(comparison_mode="CUSTOM_DUAL_WINDOW", current_period={
            "start_date": start, "end_date": end, "end_bound": "INCLUSIVE_CALENDAR_DAY"})).facts
    leap = for_range("2024-02-28", "2024-03-01").current_daily
    assert [str(p.date) for p in leap.points] == ["2024-02-28", "2024-02-29", "2024-03-01"]
    assert all(p.gsv == 0 for p in leap.points)
    assert len(for_range("2024-01-01", "2024-12-31").current_daily.points) == 366
    too_long = for_range("2024-01-01", "2025-01-01")
    assert too_long.current.gsv == 0  # valid summary, explicitly unsupported daily series
    assert too_long.current_daily.status == "UNSUPPORTED_RANGE"
    assert too_long.current_daily.unavailable_reason == "RANGE_EXCEEDS_366_DAYS"
    assert too_long.current_daily.points == []
    future = for_range("2026-09-01", "2026-09-30")
    assert future.current.gsv is None and all(p.gsv is None for p in future.current_daily.points)


@pytest.mark.parametrize("mutation", [
    lambda d: d["points"].pop(),
    lambda d: d["points"].reverse(),
    lambda d: d["points"][0].update(date="2026-08-02"),
    lambda d: d["points"][4].update(gsv=91),
    lambda d: d["points"][4].update(order_count=2),
    lambda d: d["points"][0].update(gsv=None),
    lambda d: d["points"][0].update(gsv=1),
    lambda d: d.update(timezone="UTC"),
    lambda d: d.update(status="UNSUPPORTED_RANGE", unavailable_reason="RANGE_EXCEEDS_366_DAYS", points=[]),
])
def test_daily_corruption_refused_even_with_recomputed_digest(source, mutation):
    from backend.contracts.competition_computed import evidence_payload
    forged = calculate(source).model_dump(mode="json")
    mutation(forged["facts"]["current_daily"])
    forged["evidence_digest"] = content_hash(evidence_payload(forged))
    forged["page"]["checksum"] = forged["evidence_digest"]
    with pytest.raises(ValidationError):
        CompetitionComputedResult.model_validate(forged)


def test_daily_uncovered_zero_and_relocated_facts_cannot_forge_evidence(source):
    payload = calculate(source, condition(as_of="2026-08-20T00:00:00+08:00")).model_dump(mode="json")
    payload["facts"]["current_daily"]["points"][19]["gsv"] = 0
    with pytest.raises(ValidationError, match="uncovered"):
        CompetitionComputedResult.model_validate(payload)
    payload = calculate(source).model_dump(mode="json")
    # Same total and valid dates; altering the distribution still invalidates evidence.
    payload["facts"]["current_daily"]["points"][4]["gsv"] -= 1
    payload["facts"]["current_daily"]["points"][9]["gsv"] += 1
    with pytest.raises(ValidationError, match="evidence digest"):
        CompetitionComputedResult.model_validate(payload)


# ---------------------------------------------------------------------------
# Reconciliation under float rounding (review R1).
#
# Parts and totals are rounded to four decimals independently, then held as binary
# floats. The tolerance must therefore scale with the magnitudes that produced the
# numbers -- and, for a difference of two large periods, with the operands rather than
# with the (possibly tiny) difference -- never be a flat epsilon that both rejects
# legitimate decompositions and accepts fabricated ones.
# ---------------------------------------------------------------------------

REVIEW_CURRENT_CHANNELS = [65728804463.2438, 55574578714.0255, 92978413517.0508, 66808821249.1391]
REVIEW_COMPARISON_CHANNELS = [65728804463.6639, 55574578714.7121, 92978413517.3764, 66808821248.2815]


def channel_snapshot(directory, current, comparison, *, current_days=("2026-08-05",), comparison_days=("2025-08-05",),
                     channels=None, coverage_start="2025-01-01", data_through="2026-08-31"):
    """One order per amount per period, inside this session's own small synthetic bound."""
    orders = []
    for year, days, values in ((2026, current_days, current), (2025, comparison_days, comparison)):
        for index, amount in enumerate(values):
            orders.append({"order_id": f"{year}-{index}", "sub_order_id": "1", "user_id": f"U-{year}-{index}",
                           "pay_time": f"{days[index % len(days)]} 12:00:00",
                           "channel": channels[index % len(channels)] if channels else f"CH_{index}",
                           "actual_amount": amount, "is_member": None, "is_refund": False, "is_goujinjin": False,
                           "order_status": "交易成功", "product_id": "P-R", "spu_type": "NORMAL"})
    directory.mkdir(mode=0o700)
    return materialize_synthetic_source(directory, {
        "contains_real_data": False, "snapshot_id": "reconcile-review", "data_version": "review/v1",
        "published_at": "2026-09-01T00:00:00+08:00", "coverage_start": coverage_start, "data_through": data_through,
        "orders": orders, "refunds": [],
        "money_unit": {"status": "KNOWN", "currency": "CNY", "amount_unit": "minor"}})


def channel_facts(tmp_path, current, comparison, **snapshot_options):
    return calculate(channel_snapshot(tmp_path / "reconcile", current, comparison, **snapshot_options),
                     condition()).facts


def test_reconciles_scales_with_operands_not_with_the_reconciled_result():
    parts = [-0.4201, -0.6866, -0.3256, 0.8576]
    # A one-step gap in a tiny result is accepted only when the large operands that
    # produced it are declared; the result alone cannot justify that gap.
    assert reconciles(parts, -0.5746, operands=tuple(REVIEW_CURRENT_CHANNELS + REVIEW_COMPARISON_CHANNELS))
    assert not reconciles(parts, -0.5746)
    assert not reconciles(parts, -0.5736, operands=tuple(REVIEW_CURRENT_CHANNELS + REVIEW_COMPARISON_CHANNELS))


def test_channel_bridge_reconciles_large_two_periods_that_almost_cancel(tmp_path):
    facts = channel_facts(tmp_path, REVIEW_CURRENT_CHANNELS, REVIEW_COMPARISON_CHANNELS)
    assert facts.current.gsv == 281090617943.4592
    assert facts.comparison.gsv == 281090617944.0339
    assert facts.difference == -0.5746
    deltas = math.fsum(item.delta for item in facts.channel_bridge.contributions)
    # The rounded channel differences legitimately miss the rounded total difference by
    # one four-decimal step. That is float representation error, not an inconsistent
    # decomposition, so it must not reject a result this source actually produced.
    assert round(deltas, 4) == -0.5747 != facts.difference
    assert facts.channel_bridge.status == "AVAILABLE"


@pytest.mark.parametrize("current,comparison", [
    (REVIEW_CURRENT_CHANNELS, REVIEW_COMPARISON_CHANNELS),
    (REVIEW_COMPARISON_CHANNELS, REVIEW_CURRENT_CHANNELS),
    ([65728804463.2438, 55574578714.0255], [65728804463.2438, 55574578714.0255]),
    ([100_000_000_000.0, 0.0001], [100_000_000_000.0]),
])
def test_channel_bridge_accepts_negative_positive_and_zero_differences(tmp_path, current, comparison):
    facts = channel_facts(tmp_path, current, comparison)
    assert facts.channel_bridge.status == "AVAILABLE"
    assert facts.channel_bridge.contributions
    assert abs(facts.difference) < 1.0


def test_daily_series_accepts_sparse_zero_days_at_large_amounts(tmp_path):
    facts = channel_facts(tmp_path, [100_000_000_000.0], [])
    points = facts.current_daily.points
    assert facts.current.gsv == 100_000_000_000.0
    assert len(points) == 31
    assert [p.order_count for p in points if p.order_count] == [1]
    assert math.fsum(p.gsv for p in points) == 100_000_000_000.0


@pytest.mark.parametrize("gap", [0.001, 0.0005, 0.0002])
def test_daily_series_rejects_a_gap_beyond_float_representation_noise(tmp_path, gap):
    facts = channel_facts(tmp_path, [100_000_000_000.0], []).model_dump(mode="json")
    for point in facts["current_daily"]["points"]:
        if point["order_count"]:
            point["gsv"] += gap
    with pytest.raises(ValidationError, match="daily GSV must sum to the period GSV"):
        CompetitionGsvFactsV5.model_validate(facts)


def test_channel_bridge_rejects_a_fabricated_split_that_still_sums_to_the_parent(tmp_path):
    # current_gsv and delta move together, so every per-item check still holds and only
    # the parent reconciliation can catch it.
    facts = channel_facts(tmp_path, REVIEW_CURRENT_CHANNELS, REVIEW_COMPARISON_CHANNELS).model_dump(mode="json")
    contribution = facts["channel_bridge"]["contributions"][0]
    contribution["current_gsv"] += 0.001
    contribution["delta"] += 0.001
    with pytest.raises(ValidationError, match="channel contributions must reconcile"):
        CompetitionGsvFactsV5.model_validate(facts)


def test_channel_bridge_rejects_compensated_delta_forgery(tmp_path):
    facts = channel_facts(tmp_path, REVIEW_CURRENT_CHANNELS, REVIEW_COMPARISON_CHANNELS).model_dump(mode="json")
    contributions = facts["channel_bridge"]["contributions"]
    contributions[0]["delta"] += 0.00008
    contributions[1]["delta"] -= 0.00008
    with pytest.raises(ValidationError, match="channel contribution must be its computed period difference"):
        CompetitionGsvFactsV5.model_validate(facts)


# ---------------------------------------------------------------------------
# Per-channel differences are checked against their own subtraction, never against
# the operand-scaled budget that the aggregate reconciliation needs (review R2).
# ---------------------------------------------------------------------------

REVIEW_MULTI_DAY_AMOUNTS = [54339576204.927, 76084263212.8113, 60443282806.4606, 92791012241.6957, 80229372682.7926]
REVIEW_CHANNEL_BULK = [70707282647.0219, 76118487540.9478, 80256607849.7445,
                       88702934555.2997, 48600119350.7518, 62334123055.1461]


@pytest.mark.parametrize("current,comparison,expected_deltas", [
    ([1_000_000_000_100.0] * 2, [1_000_000_000_000.0] * 2, [100.0, 100.0]),
    ([1_000_000_000_000.0] * 2, [1_000_000_000_100.0] * 2, [-100.0, -100.0]),
    ([1_000_000_000_000.0] * 2, [1_000_000_000_000.0] * 2, [0.0, 0.0]),
    ([100.0001] * 2, [100.0] * 2, [0.0001, 0.0001]),
])
@pytest.mark.parametrize("offset", [0.0002, 0.0001, 0.00008])
def test_channel_delta_is_checked_against_its_own_difference(tmp_path, current, comparison, expected_deltas, offset):
    facts = channel_facts(tmp_path, current, comparison)
    payload = facts.model_dump(mode="json")
    contributions = payload["channel_bridge"]["contributions"]
    assert [item.delta for item in facts.channel_bridge.contributions] == expected_deltas
    CompetitionGsvFactsV5.model_validate(payload)  # the producer's own output is accepted

    # Compensate across the two channels: every period total is untouched and the
    # aggregate rule still passes, so only the per-channel rule can reject this.
    contributions[0]["delta"] += offset
    contributions[1]["delta"] -= offset
    assert abs(math.fsum(item["delta"] for item in contributions) - payload["difference"]) <= 1e-9
    with pytest.raises(ValidationError, match="channel contribution must be its computed period difference"):
        CompetitionGsvFactsV5.model_validate(payload)


def test_daily_series_reconciles_large_amounts_spread_over_several_days(tmp_path):
    facts = channel_facts(tmp_path, REVIEW_MULTI_DAY_AMOUNTS, [],
                          current_days=("2026-08-05", "2026-08-10", "2026-08-15"))
    assert len(facts.current_daily.points) == 31
    assert facts.current.gsv == 363887507148.6872
    # The rounded days legitimately land one four-decimal step off the rounded total.
    assert round(math.fsum(point.gsv for point in facts.current_daily.points), 4) == 363887507148.6873
    assert round(math.fsum(point.gsv for point in facts.current_daily.points), 4) != facts.current.gsv


def test_channel_bridge_reconciles_large_single_period_channels(tmp_path):
    facts = channel_facts(tmp_path, REVIEW_CHANNEL_BULK, [], channels=("CH_RETAIL", "CH_SAMPLE"))
    assert facts.current.gsv == 426719554998.9118
    assert facts.channel_bridge.status == "AVAILABLE"
    assert round(math.fsum(item.current_gsv for item in facts.channel_bridge.contributions), 4) == 426719554998.9117


def test_daily_series_reconciles_a_full_leap_year_of_large_days(tmp_path):
    days = [(date(2024, 1, 1) + timedelta(days=index)).isoformat() for index in range(366)]
    source = channel_snapshot(tmp_path / "leap", [1234567.8901] * 366, [],
                              current_days=days, coverage_start="2024-01-01", data_through="2024-12-31")
    facts = calculate(source, condition(comparison_mode="CUSTOM_DUAL_WINDOW", current_period={
        "start_date": "2024-01-01", "end_date": "2024-12-31", "end_bound": "INCLUSIVE_CALENDAR_DAY"})).facts
    assert len(facts.current_daily.points) == 366
    assert facts.current.gsv == 451851847.7766
    assert all(point.gsv == 1234567.8901 for point in facts.current_daily.points)


# ---------------------------------------------------------------------------
# The per-channel rule is exactly Python's round(x, 4) of that very subtraction, so a
# four-decimal neighbour on the wrong side of an exact midpoint is rejected even though
# it stays inside the aggregate reconciliation budget (review R3).
# ---------------------------------------------------------------------------

EXACT_TIE_CURRENT = 1_000_000_000_000.0312
EXACT_TIE_COMPARISON = 1_000_000_000_000.0


def test_python_four_decimal_rounding_breaks_exact_midpoints_toward_even():
    # Sterbenz: the operands are within a factor of two, so the subtraction is exact and
    # the tie is a property of the stored binary64 values, not of the decimal literals.
    assert EXACT_TIE_CURRENT - EXACT_TIE_COMPARISON == 0.03125
    assert round(0.03125, 4) == 0.0312 and round(-0.03125, 4) == -0.0312
    assert round(math.nextafter(0.03125, math.inf), 4) == 0.0313
    assert round(math.nextafter(0.03125, -math.inf), 4) == 0.0312
    assert round(0.03135, 4) == 0.0314


def test_channel_delta_is_the_four_decimal_rounding_of_the_exact_midpoint(tmp_path):
    facts = channel_facts(tmp_path, [EXACT_TIE_CURRENT] * 2, [EXACT_TIE_COMPARISON] * 2)
    contributions = facts.channel_bridge.contributions
    assert [item.delta for item in contributions] == [0.0312, 0.0312]
    assert facts.difference == 0.0625
    # The two rounded halves land one four-decimal step under the rounded total; the
    # aggregate rule tolerates that, so only the per-channel rule can tell 0.0312 from 0.0313.
    assert round(math.fsum(item.delta for item in contributions), 4) == 0.0624 != facts.difference


@pytest.mark.parametrize("forged", [0.0313, 0.03121, 0.03119])
def test_channel_delta_rejects_the_midpoint_neighbour_that_python_rejects(tmp_path, forged):
    payload = channel_facts(tmp_path, [EXACT_TIE_CURRENT] * 2, [EXACT_TIE_COMPARISON] * 2).model_dump(mode="json")
    contributions = payload["channel_bridge"]["contributions"]
    contributions[0]["delta"] = forged
    contributions[1]["delta"] = round(payload["difference"] - forged, 4)
    # The compensated pair still reconciles, so the rejection below cannot come from a total.
    assert round(math.fsum(item["delta"] for item in contributions), 4) == payload["difference"]
    with pytest.raises(ValidationError, match="channel contribution must be its computed period difference"):
        CompetitionGsvFactsV5.model_validate(payload)


def test_the_closest_four_decimal_forgery_sits_exactly_on_the_old_half_step_window():
    # Every published delta is already a four-decimal value, so a forgery is at least one
    # published step from the honest one. At the exact midpoint that step is 5e-5 from the
    # true subtraction - precisely the half-step window an operand-scaled distance rule
    # accepts. Rounding the subtraction, instead of measuring a distance from it, is what
    # separates 0.0312 from 0.0313 without shrinking any tolerance.
    assert round(0.03125, 4) == 0.0312 and round(0.03125, 4) != 0.0313
    assert math.isclose(abs(0.0313 - 0.03125), 5e-5, rel_tol=1e-9)
    assert math.isclose(abs(0.0312 - 0.03125), 5e-5, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# The period difference is exactly round(current - comparison, 4) for every schema version,
# not a value near it; a four-decimal neighbour must not pass (review R4).
# ---------------------------------------------------------------------------

DIFFERENCE_FIXTURES = [
    ("v1", "result.json", None, CompetitionGsvFacts),
    ("v2", "unit-results.json", "major", CompetitionGsvFactsV2),
    ("v3", "daily-results.json", "major", CompetitionGsvFactsV3),
    ("v4", "waterfall-results.json", "major", CompetitionGsvFactsV4),
    ("v5", "funnel-results.json", "major", CompetitionGsvFactsV5),
]


@pytest.mark.parametrize("version,filename,key,model", DIFFERENCE_FIXTURES)
def test_period_difference_is_the_four_decimal_rounding_of_its_own_subtraction(version, filename, key, model):
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    payload = json.loads((folder / filename).read_text())
    facts = (payload[key] if key else payload)["facts"]
    model.model_validate(facts)  # the published fixture itself stays valid
    current, comparison = facts["current"]["gsv"], facts["comparison"]["gsv"]
    assert facts["difference"] == round(current - comparison, 4)
    for offset in (0.0001, -0.0001, 0.00004):
        forged = deepcopy(facts)
        forged["difference"] = facts["difference"] + offset
        with pytest.raises(ValidationError, match="difference must match period GSV"):
            model.model_validate(forged)


def test_zero_comparison_period_difference_is_still_the_four_decimal_rounding():
    # current 100.00004 against a zero comparison: the honest difference is
    # round(100.00004, 4) == 100, while the subtraction itself is 100.00004. A rule that
    # measures distance from (current - comparison) accepts the raw subtraction for free.
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    facts = json.loads((folder / "result.json").read_text())["facts"]
    facts["current"] = {**facts["current"], "gsv": 100.00004, "order_count": 1, "customer_count": 1}
    facts["comparison"] = {**facts["comparison"], "gsv": 0, "order_count": 0, "customer_count": 0}
    facts["difference"] = 100
    facts["change_ratio"] = None
    facts["change_ratio_unavailable_reason"] = "ZERO_COMPARISON_GSV"
    CompetitionGsvFacts.model_validate(facts)
    forged = deepcopy(facts)
    forged["difference"] = 100.00004
    with pytest.raises(ValidationError, match="difference must match period GSV"):
        CompetitionGsvFacts.model_validate(forged)


def test_period_difference_rejects_the_exact_midpoint_neighbour():
    # 2000000000000.0625 - 2000000000000 is exactly 0.0625, and 0.0313 is one published step
    # from the exact midpoint 0.03125 that the four-decimal rounding resolves to 0.0312.
    assert round(0.03125, 4) == 0.0312 and round(0.03125, 4) != 0.0313
    folder = Path(__file__).resolve().parents[2] / "dsh-plugins/analytics-workbench/tests/competition-computed"
    facts = json.loads((folder / "result.json").read_text())["facts"]
    current, comparison = 2_000_000_000_000.0625, 2_000_000_000_000.0
    assert current - comparison == 0.0625
    facts["current"] = {**facts["current"], "gsv": current, "order_count": 2, "customer_count": 2}
    facts["comparison"] = {**facts["comparison"], "gsv": comparison, "order_count": 2, "customer_count": 2}
    facts["difference"] = 0.0625
    facts["change_ratio"] = (current - comparison) / comparison
    CompetitionGsvFacts.model_validate(facts)
    for forged in (0.0626, 0.06255, 0.0624):
        broken = deepcopy(facts)
        broken["difference"] = forged
        with pytest.raises(ValidationError, match="difference must match period GSV"):
            CompetitionGsvFacts.model_validate(broken)
