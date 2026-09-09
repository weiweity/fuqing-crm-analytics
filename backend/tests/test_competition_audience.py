"""Competition audience service: drafts, permission, T12/T14. No HTTP."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from backend.contracts.competition_c0 import (
    CompetitionCandidateSet,
    empty_candidates,
    success_draft,
)
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_audience import (
    CompetitionAudienceError,
    CompetitionAudienceService,
    FixtureFeatureSource,
    load_cohort_features,
)
from backend.services.analytics.competition_audience.golden import (
    T05_ENROLLMENT_AS_OF,
    T05_PINNED,
    T05_PUBLISHED_AT,
    T05_SCOPE,
    T05_STOREWIDE_ABSENT,
    t05_cohort_payload,
    t05_rule,
)
from backend.services.analytics.family_handoff_audience import (
    HANDOFF_IS_NOT_LAST_YEAR_F4,
    execute_handoff_audience,
    refuse_last_year_f4_impersonation,
    preview_competition_candidates,
)

ROOT = Path(__file__).resolve().parents[2]
AUDIENCE_DIR = ROOT / "backend/services/analytics/competition_audience"
FAMILY_PATH = ROOT / "backend/services/analytics/family_handoff_audience.py"
C0_EMPTY = ROOT / "docs/hackathon/parallel-competition-2026-09-09/contracts/fixtures/audience/empty.json"
SOURCE_REF = "result_t05_gsv_20260831"


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def actor(*, actor_id="analyst.brand-a", scope=T05_SCOPE, caps=("cohort:read", "draft:write")):
    return AnalyticsPrincipal(
        actor_id=actor_id,
        capabilities=frozenset(caps),
        data_scopes=frozenset({scope}),
    )


def make_service(tmp_path, source=None):
    return CompetitionAudienceService(private_dir(tmp_path, "aud"), feature_source=source or FixtureFeatureSource())


def preview_payload(kind="ORIGIN_CHANNEL_ABSENT", **overrides):
    payload = {
        "cohort": t05_cohort_payload(rules=[t05_rule(f"rule_{kind.lower()}", kind)]),
        "combine": "AND",
        "source_result_ref": SOURCE_REF,
        "permission_scope": T05_SCOPE,
        "auto_send": False,
    }
    payload.update(overrides)
    return payload


def _imported_names(path: Path) -> set[str]:
    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
            names.update(alias.name for alias in node.names)
    return names


def test_modules_do_not_copy_rfm_or_handoff_sql():
    names = _imported_names(FAMILY_PATH)
    for path in AUDIENCE_DIR.glob("*.py"):
        names |= _imported_names(path)
    blob = " ".join(sorted(names)).lower()
    assert "backend.services.rfm" not in names
    assert "compute_customer_features" not in names
    assert "get_user_rfm_extended" not in names
    assert "get_rfm" not in blob
    assert "preload_rfm" not in blob
    assert HANDOFF_IS_NOT_LAST_YEAR_F4 is True


def test_handoff_refuses_last_year_f4_fields():
    with pytest.raises(ValueError, match="last-year F>=4"):
        refuse_last_year_f4_impersonation({"enrollment_window": {"start_date": "2025-01-01"}})
    with pytest.raises(ValueError, match="last-year F>=4"):
        execute_handoff_audience(
            request={"query_id": "candidate_handoff_audience", "non_repurchase": "STOREWIDE_ABSENT"},
            snapshot={},
            permission_scope="synthetic-demo",
            fixture_directory="unused",
            temp_directory="unused",
        )


def test_c0_empty_and_draft_contract_fixtures_roundtrip():
    empty = CompetitionCandidateSet.model_validate(json.loads(C0_EMPTY.read_text(encoding="utf-8")))
    assert empty.unique_count == 0
    assert empty.auto_send is False
    assert empty.explanations == []
    assert empty_candidates().unique_count == 0
    assert success_draft().auto_send is False
    assert success_draft().existing_mission_export == "not-mission-draft-export"


def test_load_cohort_features_fixture_keeps_member_unknown():
    bundle = load_cohort_features(
        permission_scope=T05_SCOPE,
        customer_keys=T05_PINNED,
        as_of=T05_ENROLLMENT_AS_OF,
        history_scope={"kind": "ALL", "channel_ids": [], "product_ids": []},
        sample_mode="INCLUDE",
        source_tense="PUBLISHED_SNAPSHOT",
        data_version="synthetic-t05-cohort-features/v1",
        rule_version="competition-cohort-rule/v1",
    )
    assert bundle.member_history_available is False
    assert all(row.member_status_as_of == "unknown" for row in bundle.rows)
    assert bundle.rows[0].current_is_member_trap is True


def test_zero_candidates_do_not_fabricate_names(tmp_path):
    payload = preview_payload()
    payload["cohort"] = t05_cohort_payload(
        as_of="2025-06-30T16:00:00.000000+00:00",
        rules=[t05_rule("rule_sw", "STOREWIDE_ABSENT")],
    )
    result = make_service(tmp_path).preview_candidates(actor(), payload)
    assert result["candidates"].unique_count == 0
    assert result["candidates"].customer_keys == []
    assert result["candidates"].explanations == []
    assert result["pinned_count"] == 0
    assert "不得伪造" in result["candidates"].limitations[0]


def test_or_partial_rejects_unknown_f_threshold_without_mixing(tmp_path):
    payload = preview_payload()
    payload["combine"] = "OR"
    payload["cohort"] = t05_cohort_payload(rules=[
        t05_rule("rule_ch", "ORIGIN_CHANNEL_ABSENT"),
        {
            "rule_id": "rule_f_ge_4",
            "kind": "ENROLLMENT_SNAPSHOT",
            "member_mark": "UNKNOWN",
            "f_threshold": 4,
            "f_grain_status": "UNKNOWN",
            "channel_ids": [],
            "product_ids": [],
        },
    ])
    result = make_service(tmp_path).preview_candidates(actor(), payload)
    assert result["status"] == "PARTIAL"
    assert result["candidates"].unique_count == 6
    assert result["rejected"][0]["rule_id"] == "rule_f_ge_4"
    assert result["rejected"][0]["error"]["code"] == "UNSUPPORTED_FILTER"


def test_and_unknown_f_threshold_fails(tmp_path):
    payload = preview_payload()
    payload["cohort"] = t05_cohort_payload(rules=[
        t05_rule("rule_ch", "ORIGIN_CHANNEL_ABSENT"),
        {
            "rule_id": "rule_f_ge_4",
            "kind": "ENROLLMENT_SNAPSHOT",
            "member_mark": "UNKNOWN",
            "f_threshold": 4,
            "f_grain_status": "UNKNOWN",
            "channel_ids": [],
            "product_ids": [],
        },
    ])
    with pytest.raises(CompetitionAudienceError) as error:
        make_service(tmp_path).preview_candidates(actor(), payload)
    assert error.value.status == 422
    assert error.value.param == "f_threshold"


def test_draft_contains_ops_fields_and_never_autosends(tmp_path):
    svc = make_service(tmp_path)
    preview = svc.preview_candidates(actor(), preview_payload("STOREWIDE_ABSENT"))
    draft = svc.save_draft(actor(), {
        "candidate_set_id": preview["candidates"].candidate_set_id,
        "permission_scope": T05_SCOPE,
        "owner_id": "analyst.brand-a",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 100000,
        "control_design": "holdout 待确认",
        "stop_condition": "观察窗结束或人工停止",
        "channel": "t05-ch-origin",
        "auto_send": False,
        "unknowns": ["MEMBER_HISTORY"],
    })
    assert draft.auto_send is False
    assert draft.owner_id == "analyst.brand-a"
    assert draft.reviewer_id == "reviewer.ops"
    assert str(draft.review_by) == "2026-09-15"
    assert draft.budget_cap_minor == 100000
    assert draft.control_design == "holdout 待确认"
    assert draft.stop_condition == "观察窗结束或人工停止"
    assert "MEMBER_HISTORY" in draft.unknowns
    assert draft.existing_mission_export == "not-mission-draft-export"
    with pytest.raises(CompetitionAudienceError) as error:
        svc.save_draft(actor(), {
            "candidate_set_id": preview["candidates"].candidate_set_id,
            "permission_scope": T05_SCOPE,
            "auto_send": True,
        })
    assert error.value.param == "auto_send"


def test_copy_only_does_not_expire_rule_change_does(tmp_path):
    svc = make_service(tmp_path)
    first = svc.preview_candidates(actor(), preview_payload("STOREWIDE_ABSENT", candidate_set_id="cand_t12"))
    saved = svc.save_draft(actor(), {
        "draft_id": "draft_t12",
        "candidate_set_id": "cand_t12",
        "permission_scope": T05_SCOPE,
        "owner_id": "analyst.brand-a",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 1,
        "control_design": "A",
        "stop_condition": "stop",
        "auto_send": False,
    })
    copied = svc.save_draft(actor(), {
        "draft_id": "draft_t12",
        "base_version": saved.version,
        "candidate_set_id": "cand_t12",
        "permission_scope": T05_SCOPE,
        "copy_only_change": True,
        "control_design": "B 文案",
        "stop_condition": "stop",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 1,
        "auto_send": False,
    })
    assert copied.status.value == "DRAFT"
    assert copied.copy_only_change is True
    assert copied.control_design == "B 文案"
    assert copied.expired_reason is None
    svc.preview_candidates(actor(), preview_payload(
        "ORIGIN_CHANNEL_ABSENT", candidate_set_id="cand_t12_b",
        cohort=t05_cohort_payload(rules=[t05_rule("rule_ch", "ORIGIN_CHANNEL_ABSENT")]),
    ))
    expired = svc.get_draft(actor(), "draft_t12", permission_scope=T05_SCOPE)
    assert expired.status.value == "EXPIRED"
    assert expired.expired_reason == "RULE_CHANGED"
    assert expired.copy_only_change is False
    assert first["candidates"].unique_count == 4


def test_source_tense_change_expires_and_late_refund_does_not_unpin(tmp_path):
    svc = make_service(tmp_path)
    published = svc.preview_candidates(actor(), preview_payload("ORIGIN_CHANNEL_ABSENT", candidate_set_id="cand_t14"))
    assert "t05u01" not in published["candidates"].customer_keys
    assert published["pinned_count"] == 10
    svc.save_draft(actor(), {
        "draft_id": "draft_t14",
        "candidate_set_id": "cand_t14",
        "permission_scope": T05_SCOPE,
        "owner_id": "analyst.brand-a",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-20",
        "budget_cap_minor": 2,
        "control_design": "holdout",
        "stop_condition": "stop",
        "auto_send": False,
    })
    rebuilt_payload = preview_payload(
        "ORIGIN_CHANNEL_ABSENT",
        candidate_set_id="cand_t14_rebuilt",
        cohort=t05_cohort_payload(
            source_tense="REBUILT_FROM_LATEST_CORRECTIONS",
            rules=[t05_rule("rule_origin_channel_absent", "ORIGIN_CHANNEL_ABSENT")],
        ),
    )
    rebuilt = svc.preview_candidates(actor(), rebuilt_payload)
    assert rebuilt["pinned_count"] == 10
    assert "t05u01" in rebuilt["candidates"].customer_keys
    expired = svc.get_draft(actor(), "draft_t14", permission_scope=T05_SCOPE)
    assert expired.expired_reason == "SOURCE_CHANGED"
    assert expired.status.value == "EXPIRED"


def test_handoff_family_cannot_be_used_as_enrollment(tmp_path):
    payload = preview_payload()
    payload["cohort"] = t05_cohort_payload(existing_family="analytics-handoff-audience/v1")
    with pytest.raises(CompetitionAudienceError) as error:
        make_service(tmp_path).preview_candidates(actor(), payload)
    assert error.value.param == "existing_family"


def test_observation_as_of_cannot_reselect(tmp_path):
    payload = preview_payload()
    payload["cohort"] = t05_cohort_payload(as_of=T05_PUBLISHED_AT)
    with pytest.raises(CompetitionAudienceError) as error:
        make_service(tmp_path).preview_candidates(actor(), payload)
    assert error.value.param == "as_of"


def test_cross_brand_guess_and_revoke_are_forbidden(tmp_path):
    svc = make_service(tmp_path)
    result = svc.preview_candidates(actor(), preview_payload("STOREWIDE_ABSENT", candidate_set_id="cand_t06"))
    other = actor(actor_id="analyst.brand-b", scope="scope-brand-b")
    with pytest.raises(CompetitionAudienceError) as error:
        svc.get_candidates(other, "cand_t06", permission_scope="scope-brand-b")
    assert error.value.status == 403
    assert "t05u07" not in error.value.message
    with pytest.raises(CompetitionAudienceError) as error:
        svc.preview_candidates(other, preview_payload(permission_scope="scope-brand-a"))
    assert error.value.status == 403
    revoked = actor(caps=("draft:write",))
    with pytest.raises(CompetitionAudienceError) as error:
        svc.get_candidates(revoked, "cand_t06", permission_scope=T05_SCOPE)
    assert error.value.status == 403
    with pytest.raises(CompetitionAudienceError) as error:
        svc.preview_candidates(None, preview_payload())
    assert error.value.status == 401
    assert tuple(result["candidates"].customer_keys) == T05_STOREWIDE_ABSENT


def test_draft_version_conflict(tmp_path):
    svc = make_service(tmp_path)
    svc.preview_candidates(actor(), preview_payload("STOREWIDE_ABSENT", candidate_set_id="cand_409"))
    svc.save_draft(actor(), {
        "draft_id": "draft_409",
        "candidate_set_id": "cand_409",
        "permission_scope": T05_SCOPE,
        "owner_id": "analyst.brand-a",
        "auto_send": False,
        "control_design": "a",
        "stop_condition": "s",
        "reviewer_id": "reviewer.ops",
        "review_by": "2026-09-15",
        "budget_cap_minor": 0,
    })
    with pytest.raises(CompetitionAudienceError) as error:
        svc.save_draft(actor(), {
            "draft_id": "draft_409",
            "base_version": 99,
            "candidate_set_id": "cand_409",
            "permission_scope": T05_SCOPE,
            "owner_id": "analyst.brand-a",
            "auto_send": False,
        })
    assert error.value.status == 409
    assert error.value.code == "VERSION_CONFLICT"


def test_family_wrapper_preview_matches_service(tmp_path):
    svc = make_service(tmp_path)
    payload = preview_payload("STOREWIDE_ABSENT", candidate_set_id="cand_wrap")
    wrapped = preview_competition_candidates(actor(), payload, service=svc)
    assert wrapped["candidates"].unique_count == 4
    assert wrapped["auto_send"] is False
