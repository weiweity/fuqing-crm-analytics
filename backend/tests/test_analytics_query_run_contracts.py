"""Independent query-run contract checks. HTTP / worker / native are NOT RUN."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.contracts.analytics import (
    ANALYTICS_RUN_SCHEMA,
    AnalyticsB0Facts,
    AnalyticsB0Result,
    AnalyticsRunSnapshot,
)
from backend.contracts.analytics_query import (
    ChannelFollowupQueryRequest,
    ChannelFollowupResult,
    query_contract_openapi,
)
from backend.contracts.analytics_query_run import (
    QUERY_RUN_SCHEMA,
    AnalyticsQueryConversation,
    AnalyticsQueryRunAccepted,
    AnalyticsQueryRunRequest,
    AnalyticsQueryRunSnapshot,
    ChannelFollowupFixtureDescriptor,
    ChannelFollowupRunBinding,
    query_run_contract_openapi,
)
from backend.contracts.schemas import (
    AnalyticsQueryRunRequest as ExportedRequest,
    AnalyticsQueryRunSnapshot as ExportedSnapshot,
    ChannelFollowupRunBinding as ExportedBinding,
)

ROOT = Path(__file__).resolve().parents[2]
B0_OPENAPI = ROOT / "backend/contracts/analytics-run.openapi.json"
QUERY_OPENAPI = ROOT / "backend/contracts/analytics-query.openapi.json"
QUERY_RUN_OPENAPI = ROOT / "backend/contracts/analytics-query-run.openapi.json"
B0_OPENAPI_SHA256 = "5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679"
B0_ANALYTICS_PY_SHA256 = "40050e9acd5024a418b07f8add94f93a476b7f422b933eb547e3080ab6dfa72d"


def _sha(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def test_query_run_schema_is_not_b0_or_g2_query():
    request = AnalyticsQueryRunRequest(question="查看合成渠道后续购买")
    assert request.schema_version == QUERY_RUN_SCHEMA
    assert request.schema_version != ANALYTICS_RUN_SCHEMA
    with pytest.raises(ValidationError):
        AnalyticsQueryRunRequest.model_validate({"schema_version": ANALYTICS_RUN_SCHEMA, "question": "查看"})
    with pytest.raises(ValidationError):
        AnalyticsQueryRunRequest(question="q", sql="SELECT private_information")
    with pytest.raises(ValidationError):
        AnalyticsQueryRunRequest(question="")


def test_cannot_wrap_g2_result_in_b0_snapshot_or_stub_in_query_run():
    facts = AnalyticsB0Result(facts=AnalyticsB0Facts())
    with pytest.raises(ValidationError):
        AnalyticsRunSnapshot.model_validate({
            "schema_version": ANALYTICS_RUN_SCHEMA,
            "run_id": "run_1",
            "version": 1,
            "source_ref": "conv_1",
            "conversation_id": "conv_1",
            "parent_run_id": None,
            "status": "SUCCEEDED",
            "phase": "FINALIZING",
            "created_at": "2026-09-01T00:00:00+00:00",
            "updated_at": "2026-09-01T00:00:00+00:00",
            "deadline": "2026-09-01T00:02:00+00:00",
            "result": {"schema_version": "analytics-channel-followup/v1", "answer_mode": "DETERMINISTIC_TOOL"},
            "evidence_digest": None,
            "primary_result_ref": None,
            "evidence_refs": [],
            "last_sequence": 0,
            "diagnostics": {
                "attempt_id": "attempt_1",
                "runtime_status": "PENDING",
                "execution_active": False,
                "tool_steps_used": 0,
                "dispatch_attempts": 0,
                "profile_version": "b0-run-resource/v1",
                "profile_hash": _sha("profile"),
            },
        })
    with pytest.raises(ValidationError):
        AnalyticsQueryRunSnapshot.model_validate({
            "schema_version": QUERY_RUN_SCHEMA,
            "run_id": "run_1",
            "version": 1,
            "source_ref": "conv_1",
            "conversation_id": "conv_1",
            "parent_run_id": None,
            "status": "QUEUED",
            "phase": "ACCEPTED",
            "created_at": "2026-09-01T00:00:00+00:00",
            "updated_at": "2026-09-01T00:00:00+00:00",
            "deadline": "2026-09-01T00:02:00+00:00",
            "answer_mode": "STUB",
            "result": facts.model_dump(mode="json"),
            "evidence_digest": None,
            "primary_result_ref": None,
            "evidence_refs": [],
            "last_sequence": 0,
            "diagnostics": {
                "attempt_id": "attempt_1",
                "runtime_status": "PENDING",
                "execution_active": False,
                "tool_steps_used": 0,
                "dispatch_attempts": 0,
                "profile_version": "b0-run-resource/v1",
                "profile_hash": _sha("profile"),
            },
        })


def test_descriptor_is_small_identity_not_snapshot_body():
    descriptor = ChannelFollowupFixtureDescriptor(
        data_digest=_sha("digest"),
        as_of="2026-09-01T00:00:00+08:00",
        physical_sha256=_sha("physical"),
    )
    dumped = descriptor.model_dump(mode="json")
    assert set(dumped) == {
        "snapshot_id", "data_version", "data_digest", "as_of", "timezone", "physical_sha256",
    }
    assert "orders" not in dumped
    binding = ChannelFollowupRunBinding(
        method_package_digest=_sha("method"),
        fixture=descriptor,
        permission_scope=_sha("scope"),
    )
    assert binding.family == "channel_followup"


def test_schemas_reexport_query_run_types():
    assert ExportedRequest is AnalyticsQueryRunRequest
    assert ExportedSnapshot is AnalyticsQueryRunSnapshot
    assert ExportedBinding is ChannelFollowupRunBinding


def test_openapi_is_store_only_and_does_not_mount_http():
    schema = query_run_contract_openapi()
    assert schema["paths"] == {}
    assert schema["x-not-an-http-api"] is True
    assert schema["x-store-only"] is True
    assert schema["x-query-run-schema"] == QUERY_RUN_SCHEMA
    assert "x-js-max-safe-integer" not in schema
    assert "x-timestamp-canonical-rule" not in schema
    assert "AnalyticsQueryRunSnapshot" in schema["components"]["schemas"]
    assert "ChannelFollowupResult" in schema["components"]["schemas"]
    assert "AnalyticsB0Result" not in schema["components"]["schemas"]
    assert "AnalyticsRunSnapshot" not in schema["components"]["schemas"]
    parsed = json.loads(json.dumps(schema, sort_keys=True, ensure_ascii=False, allow_nan=False))
    digest = hashlib.sha256(json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    artifact = json.loads(QUERY_RUN_OPENAPI.read_text(encoding="utf-8"))
    sha = artifact.pop("x-schema-sha256")
    assert sha == digest
    assert artifact["paths"] == {}
    assert artifact["x-not-an-http-api"] is True


def test_b0_and_g2_artifacts_are_untouched():
    openapi = json.loads(B0_OPENAPI.read_text(encoding="utf-8"))
    assert openapi["x-schema-sha256"] == B0_OPENAPI_SHA256
    analytics_py = hashlib.sha256((ROOT / "backend/contracts/analytics.py").read_bytes()).hexdigest()
    assert analytics_py == B0_ANALYTICS_PY_SHA256
    query_schema = query_contract_openapi()
    assert query_schema["paths"] == {}
    query_artifact = json.loads(QUERY_OPENAPI.read_text(encoding="utf-8"))
    assert query_artifact["paths"] == {}
    assert query_artifact["x-not-an-http-api"] is True
    ChannelFollowupQueryRequest.model_validate({
        "cohort_window": {"kind": "FIXED", "start_date": "2026-06-01", "end_date": "2026-09-01"},
        "observation_days": 30,
    })
    assert ChannelFollowupResult.__name__ == "ChannelFollowupResult"


@pytest.mark.parametrize("value", [[], {}, True, "future/v99", "analytics-run-b0/v1"])
def test_schema_version_non_strings_and_unknown_are_validation_errors(value):
    with pytest.raises(ValidationError):
        AnalyticsQueryRunRequest.model_validate({"schema_version": value, "question": "查看合成渠道后续购买"})
    with pytest.raises(ValidationError):
        AnalyticsQueryRunSnapshot.model_validate({
            "schema_version": value,
            "run_id": "run_1",
            "version": 1,
            "source_ref": "conv_1",
            "conversation_id": "conv_1",
            "parent_run_id": None,
            "status": "QUEUED",
            "phase": "ACCEPTED",
            "created_at": "2026-09-01T00:00:00+00:00",
            "updated_at": "2026-09-01T00:00:00+00:00",
            "deadline": "2026-09-01T00:02:00+00:00",
            "result": None,
            "evidence_digest": None,
            "primary_result_ref": None,
            "evidence_refs": [],
            "last_sequence": 0,
            "diagnostics": {
                "attempt_id": "attempt_1",
                "runtime_status": "PENDING",
                "execution_active": False,
                "tool_steps_used": 0,
                "dispatch_attempts": 0,
                "profile_version": "b0-run-resource/v1",
                "profile_hash": _sha("profile"),
            },
        })


def test_default_limitations_are_stable_synthetic_not_stage_text():
    snapshot = AnalyticsQueryRunSnapshot.model_validate({
        "run_id": "run_1",
        "version": 1,
        "source_ref": "conv_1",
        "conversation_id": "conv_1",
        "parent_run_id": None,
        "status": "QUEUED",
        "phase": "ACCEPTED",
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "deadline": "2026-09-01T00:02:00+00:00",
        "result": None,
        "evidence_digest": None,
        "primary_result_ref": None,
        "evidence_refs": [],
        "last_sequence": 0,
        "diagnostics": {
            "attempt_id": "attempt_1",
            "runtime_status": "PENDING",
            "execution_active": False,
            "tool_steps_used": 0,
            "dispatch_attempts": 0,
            "profile_version": "b0-run-resource/v1",
            "profile_hash": _sha("profile"),
        },
    })
    text = " ".join(snapshot.limitations)
    assert "synthetic" in text and "worker" not in text and "成功出口" not in text


def test_accepted_location_is_not_a_mounted_http_claim():
    accepted = AnalyticsQueryRunAccepted(run_id="run_1", location="/internal/store/analytics-query/runs/run_1")
    assert accepted.schema_version == QUERY_RUN_SCHEMA
    assert accepted.location.startswith("/internal/store/")
    conversation = AnalyticsQueryConversation.model_validate({
        "conversation_id": "conv_1",
        "title": "渠道后续购买查询",
        "created_at": "2026-09-01T00:00:00+00:00",
    })
    assert conversation.schema_version == QUERY_RUN_SCHEMA
