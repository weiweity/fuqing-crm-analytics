"""C0 contract fixtures and mapping checks. No CRM/HTTP/DuckDB."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.contracts.analytics import AnalyticsErrorDetail
from backend.contracts.competition_c0 import (
    C0_DEFAULTS,
    CONCEPT_MAP,
    SUPPORT_MATRIX,
    CompetitionActionDraft,
    CompetitionBoardSpec,
    CompetitionCandidateSet,
    CompetitionCondition,
    CompetitionErrorResponse,
    CompetitionResultRef,
    c0_openapi,
    empty_candidates,
    empty_result,
    param_error_payloads,
    permission_error,
    success_batch,
    success_board,
    success_condition,
    success_draft,
    success_patch,
    success_result,
    validate_fixture_library,
)
from backend.contracts.schemas import CompetitionCondition as ExportedCondition


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs/hackathon/parallel-competition-2026-09-09/contracts"


def test_exported_type_is_c0_condition():
    assert ExportedCondition is CompetitionCondition


def test_openapi_is_offline_and_reuses_cockpit_op():
    schema = c0_openapi()
    assert schema["paths"] == {}
    assert schema["x-not-an-http-api"] is True
    assert schema["x-b0-run-schema-untouched"] == "analytics-run-b0/v1"
    assert "CompetitionCondition" in schema["components"]["schemas"]
    assert "AnalyticsCockpitAddOp" in schema["components"]["schemas"]


def test_fixture_library_validates():
    validate_fixture_library()
    assert success_condition().metric_type == "GSV"
    assert empty_result().completeness == "EMPTY"
    assert empty_result().empty_reason == "NO_CURRENT_MONTH_DATA"
    assert empty_candidates().unique_count == 0
    assert success_draft().auto_send is False
    assert success_board().snapshot_compat == "READ_OLD_SNAPSHOT"
    assert success_patch().intent == "STYLE_ONLY"
    assert success_batch().layout_mode == "ONE_BOARD_MULTI_BLOCK"


def test_gmv_and_silent_owner_rejected():
    with pytest.raises(ValidationError):
        CompetitionCondition.model_validate(param_error_payloads()["condition"])
    payload = success_condition().model_dump(mode="json")
    payload["owner_id"] = "analyst.brand-a"
    with pytest.raises(ValidationError):
        CompetitionCondition.model_validate(payload)


def test_empty_is_not_an_error():
    row = empty_result()
    assert row.row_count == 0
    assert row.completeness != "FAILED"
    with pytest.raises(ValidationError):
        CompetitionResultRef.model_validate({
            **success_result().model_dump(mode="json"),
            "completeness": "COMPLETE",
            "row_count": 0,
        })


def test_history_recompute_is_explicit():
    payload = success_condition().model_dump(mode="json")
    payload["sample_mode"] = "EXCLUDE_AND_RECOMPUTE_HISTORY"
    with pytest.raises(ValidationError):
        CompetitionCondition.model_validate(payload)
    payload["history_scope"] = {
        "kind": "CHANNEL_IDS",
        "channel_ids": ["sample-channel-unverified-a"],
        "product_ids": [],
    }
    CompetitionCondition.model_validate(payload)


def test_error_is_superset_of_b0_detail():
    body = permission_error(param="result_id", message="无权", request_id="req")
    mapped = body.error.as_b0_error_detail()
    assert isinstance(mapped, AnalyticsErrorDetail)
    assert mapped.code == "FORBIDDEN"
    assert body.error.param == "result_id"
    assert body.error.doc_ref
    dumped = json.loads(json.dumps(body.model_dump(mode="json")))
    assert dumped["error"]["http_status"] == 403


def test_f_threshold_blocked_while_unknown():
    from backend.contracts.competition_c0 import CohortRule, success_cohort
    with pytest.raises(ValidationError):
        CohortRule.model_validate({
            "rule_id": "rule_f",
            "kind": "ENROLLMENT_SNAPSHOT",
            "member_mark": "UNKNOWN",
            "f_threshold": 4,
            "f_grain_status": "UNKNOWN",
            "channel_ids": [],
            "product_ids": [],
        })
    assert success_cohort().member_history_status == "UNKNOWN"


def test_copy_only_draft_cannot_expire():
    payload = success_draft().model_dump(mode="json")
    payload["copy_only_change"] = True
    payload["status"] = "EXPIRED"
    payload["expired_reason"] = "RULE_CHANGED"
    with pytest.raises(ValidationError):
        CompetitionActionDraft.model_validate(payload)


def test_concept_map_covers_required_names():
    names = {item.concept for item in CONCEPT_MAP}
    assert names == {
        "Condition", "ResultRef", "BoardSpec", "Patch", "Audience", "Action", "Error", "Capabilities",
    }
    pending = {item.key for item in C0_DEFAULTS if item.pending_confirmation}
    assert pending == {"sample_mode_when_excluding", "board_layout_mode"}
    statuses = {item.capability_id: item.support_status for item in SUPPORT_MATRIX}
    assert statuses["diag.sample_recompute_history"] == "UNSUPPORTED"
    assert statuses["diag.fixed_cohort"] == "UNSUPPORTED"
    sample = next(item for item in SUPPORT_MATRIX if item.capability_id == "diag.sample_exclude_current")
    assert "SAMPLE_CHANNEL_SET" in sample.unknown_flags


def test_docs_fixtures_roundtrip_if_present():
    path = DOCS / "fixtures/condition/success.json"
    if not path.is_file():
        pytest.skip("generator has not written docs fixtures yet")
    CompetitionCondition.model_validate(json.loads(path.read_text(encoding="utf-8")))
    empty = json.loads((DOCS / "fixtures/result/empty.json").read_text(encoding="utf-8"))
    CompetitionResultRef.model_validate(empty)
    board = json.loads((DOCS / "fixtures/board/success.json").read_text(encoding="utf-8"))
    CompetitionBoardSpec.model_validate(board["board"])
    audience = json.loads((DOCS / "fixtures/audience/success.json").read_text(encoding="utf-8"))
    CompetitionCandidateSet.model_validate(audience["candidates"])
    error = json.loads((DOCS / "fixtures/board/conflict_409.json").read_text(encoding="utf-8"))
    CompetitionErrorResponse.model_validate(error)
    assert error["error"]["http_status"] == 409
