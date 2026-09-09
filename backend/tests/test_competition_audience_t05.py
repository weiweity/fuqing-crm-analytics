"""T05 independent 10-person gold. Production modules do not import this file."""

from __future__ import annotations

import os
from pathlib import Path

from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_audience import (
    CompetitionAudienceService,
    FixtureFeatureSource,
    T05_GOLD,
)
from backend.services.analytics.competition_audience.golden import (
    T05_CHANNEL_SWITCHED,
    T05_ORIGIN_CHANNEL_ABSENT,
    T05_ORIGIN_CHANNEL_RETURNED,
    T05_ORIGIN_PRODUCT_ABSENT,
    T05_OUTSIDER,
    T05_PINNED,
    T05_STOREWIDE_ABSENT,
    t05_cohort_payload,
    t05_rule,
)
from backend.services.analytics.family_handoff_audience import HANDOFF_IS_NOT_LAST_YEAR_F4

SOURCE_REF = "result_t05_gsv_20260831"


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def actor(scope="scope-brand-a"):
    return AnalyticsPrincipal(
        actor_id="analyst.brand-a" if scope.endswith("a") else "analyst.brand-b",
        capabilities=frozenset({"cohort:read", "draft:write"}),
        data_scopes=frozenset({scope}),
    )


def service(tmp_path, source=None):
    return CompetitionAudienceService(private_dir(tmp_path, "aud"), feature_source=source or FixtureFeatureSource())


def preview(tmp_path, kind, *, source=None, extra=None, combine="AND"):
    payload = {
        "cohort": t05_cohort_payload(rules=[t05_rule(f"rule_{kind.lower()}", kind)]),
        "combine": combine,
        "source_result_ref": SOURCE_REF,
        "permission_scope": "scope-brand-a",
        "auto_send": False,
    }
    if extra:
        payload.update(extra)
        if "cohort" in extra:
            payload["cohort"] = extra["cohort"]
    return service(tmp_path, source).preview_candidates(actor(), payload)


def test_t05_gold_is_hand_calculated_and_independent():
    assert T05_GOLD["method"] == "hand_calculated"
    assert T05_GOLD["not_a2_c_xch"] is True
    assert T05_GOLD["not_rfm_reselect"] is True
    assert len(T05_PINNED) == 10
    assert len(T05_ORIGIN_CHANNEL_RETURNED) == 4
    assert len(T05_CHANNEL_SWITCHED) == 2
    assert len(T05_STOREWIDE_ABSENT) == 4
    assert len(T05_ORIGIN_CHANNEL_ABSENT) == 6
    assert len(T05_ORIGIN_CHANNEL_ABSENT) != len(T05_STOREWIDE_ABSENT)
    assert HANDOFF_IS_NOT_LAST_YEAR_F4 is True
    assert "C_XCH" not in T05_PINNED
    assert "cust_c0_1" not in T05_PINNED
    assert "ha-1" not in T05_PINNED


def test_t05_origin_channel_absent_six_not_equal_storewide_four(tmp_path):
    channel = preview(tmp_path, "ORIGIN_CHANNEL_ABSENT", extra={"candidate_set_id": "cand_t05_ch"})
    store = preview(tmp_path, "STOREWIDE_ABSENT", extra={"candidate_set_id": "cand_t05_sw"})
    product = preview(tmp_path, "ORIGIN_PRODUCT_ABSENT", extra={"candidate_set_id": "cand_t05_pr"})
    assert channel["candidates"].unique_count == 6
    assert store["candidates"].unique_count == 4
    assert channel["candidates"].unique_count != store["candidates"].unique_count
    assert tuple(channel["candidates"].customer_keys) == T05_ORIGIN_CHANNEL_ABSENT
    assert tuple(store["candidates"].customer_keys) == T05_STOREWIDE_ABSENT
    assert tuple(product["candidates"].customer_keys) == T05_ORIGIN_PRODUCT_ABSENT
    assert channel["pinned_count"] == 10
    assert store["pinned_count"] == 10
    assert T05_OUTSIDER not in channel["candidates"].customer_keys
    assert channel["candidates"].auto_send is False
    assert channel["member_history_status"] == "UNKNOWN"


def test_t05_membership_stays_pinned_if_source_tries_to_reselect(tmp_path):
    source = FixtureFeatureSource(mutate_pin_on_reload=("t05u01", "t05u02", T05_OUTSIDER))
    first = preview(tmp_path, "STOREWIDE_ABSENT", source=source)
    second = preview(tmp_path, "STOREWIDE_ABSENT", source=source)
    assert first["pinned_count"] == 10
    assert second["pinned_count"] == 10
    assert T05_OUTSIDER not in second["candidates"].customer_keys
    assert tuple(second["candidates"].customer_keys) == T05_STOREWIDE_ABSENT


def test_t05_or_union_dedups_and_and_is_storewide(tmp_path):
    svc = service(tmp_path)
    payload = {
        "cohort": t05_cohort_payload(rules=[
            t05_rule("rule_ch", "ORIGIN_CHANNEL_ABSENT"),
            t05_rule("rule_sw", "STOREWIDE_ABSENT"),
        ]),
        "combine": "OR",
        "source_result_ref": SOURCE_REF,
        "permission_scope": "scope-brand-a",
        "auto_send": False,
    }
    union = svc.preview_candidates(actor(), payload)
    assert union["candidates"].unique_count == 6
    assert union["candidates"].customer_keys == list(T05_ORIGIN_CHANNEL_ABSENT)
    payload["combine"] = "AND"
    payload["candidate_set_id"] = "cand_t05_and"
    inter = svc.preview_candidates(actor(), payload)
    assert inter["candidates"].unique_count == 4
    assert inter["candidates"].customer_keys == list(T05_STOREWIDE_ABSENT)


def test_t05_or_channel_and_product_has_seven_unique(tmp_path):
    payload = {
        "cohort": t05_cohort_payload(rules=[
            t05_rule("rule_ch", "ORIGIN_CHANNEL_ABSENT"),
            t05_rule("rule_pr", "ORIGIN_PRODUCT_ABSENT"),
        ]),
        "combine": "OR",
        "source_result_ref": SOURCE_REF,
        "permission_scope": "scope-brand-a",
        "auto_send": False,
    }
    result = service(tmp_path).preview_candidates(actor(), payload)
    expected = tuple(sorted(set(T05_ORIGIN_CHANNEL_ABSENT) | set(T05_ORIGIN_PRODUCT_ABSENT)))
    assert result["candidates"].unique_count == 7
    assert tuple(result["candidates"].customer_keys) == expected
    reasons = {item.customer_key: item.reasons for item in result["candidates"].explanations}
    assert "ORIGIN_PRODUCT_ABSENT" in reasons["t05u04"]
    assert "ORIGIN_CHANNEL_ABSENT" in reasons["t05u05"]
    assert "ORIGIN_CHANNEL_ABSENT" in reasons["t05u06"] and "ORIGIN_PRODUCT_ABSENT" in reasons["t05u06"]


def test_t05_a9_cohort_id_keeps_independent_c01_c10_gold(tmp_path):
    a8 = preview(tmp_path, "ORIGIN_CHANNEL_ABSENT", extra={"candidate_set_id": "cand_a8_keep"})
    assert tuple(a8["candidates"].customer_keys) == T05_ORIGIN_CHANNEL_ABSENT
    assert a8["pinned_count"] == 10
    payload = {
        "cohort": {
            "cohort_id": "cohort_a9_t05_ly_f4_10",
            "enrollment_window": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
            "observation_window": {"start_date": "2026-01-01", "end_date": "2026-09-21"},
            "enrollment_rule_version": "competition-cohort-rule-v1",
            "as_of": "2025-12-31T04:00:00.000000+00:00",
            "published_at": "2026-09-21T16:00:00.000000+00:00",
            "source_tense": "PUBLISHED_SNAPSHOT",
            "member_history_status": "UNKNOWN",
            "existing_family": "none",
            "rules": [t05_rule("rule_origin_channel", "ORIGIN_CHANNEL_ABSENT")],
            "permission_scope": "scope-brand-a",
            "limitations": ["A9 independent T05 gold; last-year F>=4 frozen 10."],
        },
        "combine": "AND",
        "source_result_ref": "result_a9_t05_gsv",
        "permission_scope": "scope-brand-a",
        "auto_send": False,
        "candidate_set_id": "cand_a9_keep",
    }
    a9 = service(tmp_path).preview_candidates(actor(), payload)
    assert a9["pinned_count"] == 10
    assert set(a9["candidates"].customer_keys) == {"C05", "C06", "C07", "C08", "C09", "C10"}
    assert a9["candidates"].unique_count == 6
    assert set(a8["candidates"].customer_keys).isdisjoint(a9["candidates"].customer_keys)
