"""A9 independent goldens against real SUT compute. Not A1/A2 tables."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import duckdb
import pytest

_SUPPORT = Path(__file__).with_name("test_competition_acceptance.py")
_SPEC = importlib.util.spec_from_file_location("a9_acceptance_support", _SUPPORT)
_ACC = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_ACC)

A9T05FeatureSource = _ACC.A9T05FeatureSource
TOKEN = _ACC.TOKEN
a9_t05_payload = _ACC.a9_t05_payload
competition_http = _ACC.competition_http
identities_from = _ACC.identities_from
load_json = _ACC.load_json
money = _ACC.money
prefer_sut = _ACC.prefer_sut
private_dir = _ACC.private_dir
require_attr = _ACC.require_attr
seed_orders = _ACC.seed_orders

prefer_sut()


def compute():
    return require_attr("backend.services.metrics.competition_compute", "compute_competition_metrics")


def rfm_as_of():
    return require_attr("backend.services.rfm.as_of", "compute_rfm_as_of")


def period_builder():
    return require_attr("backend.semantic.time", "PeriodBuilder")


def analysis_cutoff():
    return require_attr("backend.semantic.time", "analysis_cutoff")


def shift_year_clamped():
    return require_attr("backend.semantic.time", "shift_year_clamped")


def window_has_no_current_month_data():
    return require_attr("backend.semantic.time", "window_has_no_current_month_data")


def empty_mtd_summary():
    return require_attr("backend.services.metrics.competition_compute", "empty_mtd_summary")


def orders_conn():
    fixture = load_json("t02_t03_orders.json")
    conn = duckdb.connect(":memory:")
    seed_orders(conn, fixture["orders"])
    return conn, fixture


def run_path(conn, fixture, sample_mode, sample_ids):
    analysis = fixture["analysis"]
    kwargs = {
        "start_date": analysis["start"],
        "end_date": analysis["end"],
        "metric_type": "GSV",
        "today": date.fromisoformat(analysis["as_of_today"]),
        "as_of": analysis["data_cutoff"],
        "sample_mode": sample_mode,
    }
    if sample_ids is None:
        kwargs["sample_channel_ids"] = None
    else:
        kwargs["sample_channel_ids"] = sample_ids
    metrics = compute()(conn, **kwargs)
    rfm = rfm_as_of()(
        conn,
        as_of=analysis["data_cutoff"],
        sample_mode=sample_mode,
        sample_channel_ids=sample_ids,
    )
    return metrics, rfm


def test_t01_sept1_tplus1_empty_month_compute():
    today = date(2026, 9, 1)
    assert window_has_no_current_month_data()("2026-09-01", "2026-09-30", today=today)
    empty = empty_mtd_summary()(today=today, metric_type="GSV")
    assert empty["completeness"] == "EMPTY"
    assert empty["empty_reason"] == "NO_CURRENT_MONTH_DATA"
    assert empty.get("current_period") is None
    blob = json_blob(empty)
    assert "2026-08-01" not in blob
    assert "2026-09-30" not in blob
    conn = duckdb.connect(":memory:")
    seed_orders(conn, [])
    actual = compute()(
        conn,
        start_date="2026-09-01",
        end_date="2026-09-30",
        metric_type="GSV",
        today=today,
        as_of="2026-08-31",
    )
    assert actual["completeness"] == "EMPTY"
    executed = actual.get("executed") or {}
    assert executed.get("current_period") is None
    conn.close()


def json_blob(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def test_t01_period_builder_mtd_must_not_replace_empty_september():
    ranges = period_builder().mtd(today=date(2026, 9, 1))
    if ranges["current"].start == "2026-08-01":
        pytest.fail(
            "T01: PeriodBuilder.mtd(2026-09-01) returns August; competition MTD must be empty, not last full month"
        )


def test_t01_leap_day_clamp_and_unequal_yoy_days():
    builder = period_builder()
    clamped = shift_year_clamped()(date(2024, 2, 29), 1)
    assert clamped.isoformat() == "2023-02-28"
    yoy = builder.yoy("2024-02-29", "2024-02-29")
    assert yoy.start == "2023-02-28"
    assert yoy.end == "2023-02-28"
    week = builder.free("2024-02-23", "2024-02-29")
    assert week["current"].start == "2024-02-23"
    assert week["current"].end == "2024-02-29"
    assert week["comparison"].start == "2023-02-23"
    assert week["comparison"].end == "2023-02-28"
    current_days = (date(2024, 2, 29) - date(2024, 2, 23)).days + 1
    yoy_days = (date.fromisoformat(week["comparison"].end) - date.fromisoformat(week["comparison"].start)).days + 1
    assert current_days == 7
    assert yoy_days == 6
    last_week = builder.last_week_same_weekday("2024-02-23", "2024-02-29")
    assert last_week.start == "2024-02-16"
    assert last_week.end == "2024-02-22"


def test_t01_cross_year_and_end_before_start():
    builder = period_builder()
    cross = builder.free("2025-12-28", "2026-01-03")
    assert cross["comparison"].start == "2024-12-28"
    assert cross["comparison"].end == "2025-01-03"
    last_week = builder.last_week_same_weekday("2025-12-28", "2026-01-03")
    assert last_week.start == "2025-12-21"
    assert last_week.end == "2025-12-27"
    assert analysis_cutoff()("2025-12-28").isoformat() == "2025-12-27"
    with pytest.raises(ValueError):
        compute()(
            duckdb.connect(":memory:"),
            start_date="2026-09-15",
            end_date="2026-09-01",
            metric_type="GSV",
        )
    conn = duckdb.connect(":memory:")
    seed_orders(conn, [])
    empty = compute()(
        conn,
        start_date="2026-09-15",
        end_date="2026-09-21",
        metric_type="GSV",
        today=date(2026, 9, 11),
        as_of="2026-09-10",
    )
    assert empty["completeness"] == "EMPTY"
    assert empty.get("empty_reason") != "INVALID_PERIOD"
    conn.close()


def test_t01_mid_month_cutoff_is_start_minus_one_not_month_start():
    cutoff = analysis_cutoff()("2026-09-15")
    assert cutoff.isoformat() == "2026-09-14"
    assert cutoff.isoformat() != "2026-08-31"
    yoy = period_builder().yoy("2026-09-15", "2026-09-21")
    assert yoy.start == "2025-09-15"
    assert yoy.end == "2025-09-21"
    last_week = period_builder().last_week_same_weekday("2026-09-15", "2026-09-21")
    assert last_week.start == "2026-09-08"
    assert last_week.end == "2026-09-14"
    promo = require_attr("backend.semantic.time", "resolve_comparison_range")(
        "CUSTOM_DUAL_WINDOW",
        "2026-06-16",
        "2026-06-18",
        "2025-06-16",
        "2025-06-18",
    )
    assert promo.start == "2025-06-16"
    assert promo.end == "2025-06-18"


def test_t02_tri_line_f_is_one_and_same_day_f_is_two():
    conn, fixture = orders_conn()
    try:
        rfm = rfm_as_of()(conn, as_of=fixture["analysis"]["data_cutoff"])
        assert int(rfm["U-TRI-LINE"]["f"]) == 1
        assert int(rfm["U-TWO"]["f"]) == 2
        assert "U-FULL" not in rfm
        assert money(rfm["U-TRI-LINE"]["m"]) == money("50.00")
    finally:
        conn.close()


def test_t02_sept5_is_old_because_cutoff_is_start_minus_one():
    conn, fixture = orders_conn()
    try:
        metrics, rfm = run_path(conn, fixture, "INCLUDE", None)
        expected = fixture["expected_by_path"]["default_include_sample"]
        ident = identities_from(metrics, rfm, fixture["analysis"])
        assert ident["U-SEP5"]["identity"] == "OLD"
        assert ident["U-SEP5"]["first_pay"] == "2026-09-05"
        if not ident["U-SEP5"]["in_period_buyers"]:
            if "U-SEP5" not in (metrics.get("old_users") or []):
                pytest.fail(
                    "T02: U-SEP5 is OLD (09-05 < 09-15) with period GSV 0, but compute_competition_metrics only classifies period buyers"
                )
        assert ident["U-TRI-LINE"]["lifetime_f"] == 1
        assert ident["U-TWO"]["lifetime_f"] == 2
        assert money(metrics["gsv"]) == money(expected["period_gsv"])
        assert len(metrics.get("old_users") or []) == expected["old_count"]
        assert len(metrics.get("new_users") or []) == expected["new_count"]
    finally:
        conn.close()


def test_t02_partial_refund_nets_sixty_three():
    conn, fixture = orders_conn()
    try:
        metrics, rfm = run_path(conn, fixture, "INCLUDE", None)
        if "U-PART" not in rfm:
            pytest.fail("T02: partial refund dropped the buyer entirely instead of net 63.00")
        assert money(rfm["U-PART"]["m"]) == money("63.00")
        user_period = None
        # period GSV includes 63 not 90
        assert money(metrics["gsv"]) == money("378.00")
        del user_period
    finally:
        conn.close()


def test_t03_current_only_vs_history_recompute_identity_differs():
    conn, fixture = orders_conn()
    try:
        current_only, current_rfm = run_path(
            conn, fixture, "EXCLUDE_CURRENT_SALES_ONLY", ["CH_SAMPLE"]
        )
        recompute, recompute_rfm = run_path(
            conn, fixture, "EXCLUDE_AND_RECOMPUTE_HISTORY", ["CH_SAMPLE"]
        )
        diff = fixture["path_diff_current_only_vs_history_recompute"]
        current_ids = identities_from(current_only, current_rfm, fixture["analysis"])
        recompute_ids = identities_from(recompute, recompute_rfm, fixture["analysis"])
        assert current_ids["U-SAMPLE"]["identity"] == "OLD"
        assert current_ids["U-SAMPLE"]["lifetime_f"] == 3
        assert recompute_ids["U-SAMPLE"]["identity"] == "NEW"
        assert recompute_ids["U-SAMPLE"]["lifetime_f"] == 1
        assert current_only["executed"]["sample_history_recomputed"] is False
        assert recompute["executed"]["sample_history_recomputed"] is True
        assert money(current_only["gsv"]) == money(diff["period_gsv"])
        assert money(recompute["gsv"]) == money(diff["period_gsv"])
        assert len(current_only.get("old_users") or []) == 2
        assert len(recompute.get("old_users") or []) == 1
    finally:
        conn.close()


def test_t03_sales_retail_must_not_collapse_history_scope():
    conn, fixture = orders_conn()
    try:
        metrics = compute()(
            conn,
            start_date=fixture["analysis"]["start"],
            end_date=fixture["analysis"]["end"],
            metric_type="GSV",
            today=date.fromisoformat(fixture["analysis"]["as_of_today"]),
            as_of=fixture["analysis"]["data_cutoff"],
            sample_mode="INCLUDE",
            sales_channels=["CH_RETAIL"],
        )
        rfm = rfm_as_of()(conn, as_of=fixture["analysis"]["data_cutoff"], sample_mode="INCLUDE")
        ident = identities_from(metrics, rfm, fixture["analysis"])
        assert ident["U-SAMPLE"]["identity"] == "OLD"
        assert ident["U-SAMPLE"]["lifetime_f"] == 3
        if money(metrics["gsv"]) != money("375.00"):
            pytest.fail(f"T03 sales-retail GSV {metrics['gsv']} != 375.00 (partial refund netting?)")
    finally:
        conn.close()


def test_t04_gsv_not_gmv_and_unknown_member_and_ratio():
    conn = duckdb.connect(":memory:")
    seed_orders(
        conn,
        [
            {"order_id": "O-GSV", "user_id": "U-MEM", "paid_date": "2026-09-16", "channel": "CH_RETAIL", "actual_amount": "10.00", "is_member": True, "lines": [{"sku": "A", "amount": "10.00"}], "refunds": []},
            {"order_id": "O-NON", "user_id": "U-NON", "paid_date": "2026-09-16", "channel": "CH_RETAIL", "actual_amount": "20.00", "is_member": False, "lines": [{"sku": "B", "amount": "20.00"}], "refunds": []},
            {"order_id": "O-UNK", "user_id": "U-UNK", "paid_date": "2026-09-16", "channel": "CH_RETAIL", "actual_amount": "30.00", "is_member": None, "lines": [{"sku": "C", "amount": "30.00"}], "refunds": []},
            {"order_id": "O-LIST", "user_id": "U-LIST", "paid_date": "2026-09-16", "channel": "CH_RETAIL", "actual_amount": "82.00", "is_member": False, "lines": [{"sku": "D", "amount": "82.00"}], "refunds": []},
        ],
    )
    try:
        with pytest.raises(ValueError, match="GSV"):
            compute()(conn, start_date="2026-09-15", end_date="2026-09-21", metric_type="GMV")
        metrics = compute()(
            conn,
            start_date="2026-09-15",
            end_date="2026-09-21",
            metric_type="GSV",
            today=date(2026, 9, 22),
            as_of="2026-09-21",
        )
        assert money(metrics["gsv"]) == money("142.00")
        assert "U-UNK" in metrics["member"]["UNKNOWN"]["users"]
        assert money(metrics["member"]["UNKNOWN"]["gsv"]) == money("30.00")
        assert money(metrics["member"]["MEMBER"]["gsv"]) == money("10.00")
        assert money(metrics["member"]["NON_MEMBER"]["gsv"]) == money("102.00")
        safe_ratio = require_attr("backend.semantic.calculations", "safe_ratio")
        ratio = safe_ratio(2, 8)
        assert ratio == 0.25
        zero = safe_ratio(0, 0)
        if zero == 0 or zero == 0.0:
            pytest.fail("T04: safe_ratio(0,0) returned 0; A9 requires null, not a fake 0%")
    finally:
        conn.close()


def test_t05_orig_channel_not_returned_six_not_equal_storewide_four(tmp_path):
    CompetitionAudienceService = require_attr(
        "backend.services.analytics.competition_audience",
        "CompetitionAudienceService",
    )
    AnalyticsPrincipal = require_attr("backend.services.analytics.access", "AnalyticsPrincipal")
    fixture = load_json("t05_cohort.json")
    svc = CompetitionAudienceService(private_dir(tmp_path / "aud"), feature_source=A9T05FeatureSource(fixture))
    actor = AnalyticsPrincipal("analyst.brand-a", frozenset({"cohort:read", "draft:write"}), frozenset({"scope-brand-a"}))
    channel = svc.preview_candidates(actor, a9_t05_payload(fixture, "ORIGIN_CHANNEL_ABSENT", extra={"candidate_set_id": "cand_a9_ch"}))
    store = svc.preview_candidates(actor, a9_t05_payload(fixture, "STOREWIDE_ABSENT", extra={"candidate_set_id": "cand_a9_sw"}))
    product = svc.preview_candidates(actor, a9_t05_payload(fixture, "ORIGIN_PRODUCT_ABSENT", extra={"candidate_set_id": "cand_a9_pr"}))
    assert channel["pinned_count"] == 10
    assert channel["candidates"].unique_count == 6
    assert store["candidates"].unique_count == 4
    assert channel["candidates"].unique_count != store["candidates"].unique_count
    assert set(channel["candidates"].customer_keys) == set(fixture["sets"]["orig_channel_not_returned"])
    assert set(store["candidates"].customer_keys) == set(fixture["sets"]["storewide_not_returned"])
    assert set(product["candidates"].customer_keys) == set(fixture["sets"]["orig_product_not_returned"])
    assert "C11" not in channel["candidates"].customer_keys
    assert channel["auto_send"] is False
    limitations = "\n".join(channel["candidates"].limitations)
    assert "不能确定为永久流失" in limitations or "观察期未回购" in limitations


def test_t05_http_default_source_must_not_replace_a9_ids(tmp_path):
    from fastapi.testclient import TestClient

    app, _analyses, _identities = competition_http(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    fixture = load_json("t05_cohort.json")
    response = client.post(
        "/api/v1/analytics/competition/candidates/preview",
        json=a9_t05_payload(fixture, "ORIGIN_CHANNEL_ABSENT", extra={"candidate_set_id": "cand_http_a9"}),
    )
    assert response.status_code == 200, response.text
    keys = response.json()["candidates"]["customer_keys"]
    if set(keys) != set(fixture["sets"]["orig_channel_not_returned"]):
        pytest.fail(
            f"T05 HTTP default FixtureFeatureSource did not compute A9 C01-C10; got {keys}"
        )


def test_t14_r_advances_without_new_orders_and_does_not_peek():
    conn, fixture = orders_conn()
    try:
        first = rfm_as_of()(conn, as_of="2026-09-21", user_ids=["U-SEP5"])
        second = rfm_as_of()(conn, as_of="2026-09-22", user_ids=["U-SEP5"])
        assert first["U-SEP5"]["f"] == second["U-SEP5"]["f"] == 1
        assert money(first["U-SEP5"]["m"]) == money(second["U-SEP5"]["m"])
        assert int(second["U-SEP5"]["r_days"]) == int(first["U-SEP5"]["r_days"]) + 1
        assert first["U-SEP5"]["member_status_as_of"] == "UNKNOWN"
        future = rfm_as_of()(conn, as_of="2026-09-04", user_ids=["U-SEP5"])
        assert "U-SEP5" not in future
    finally:
        conn.close()


def test_t14_late_refund_requires_dated_refund_not_boolean_flag():
    compute_src = Path_read("backend.services.metrics.competition_compute")
    if "refunded_at" not in compute_src and "refunds" not in compute_src:
        pytest.fail("T14: competition_compute has no dated refund path; late refund after cutoff cannot be isolated")


def Path_read(dotted: str) -> str:
    import inspect

    module = __import__(dotted, fromlist=["*"])
    return inspect.getsource(module)
