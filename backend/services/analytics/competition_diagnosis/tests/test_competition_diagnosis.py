"""Offline diagnosis adapter tests. No HTTP, DuckDB, or second runtime."""

from __future__ import annotations

from dataclasses import replace

from backend.contracts.competition_c0 import success_condition
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.chain import FORBIDDEN_EXPANSIONS, REGISTERED_TOOLS, REQUIRED_FOR_COMPLETE_CHAIN
from backend.services.analytics.competition_diagnosis.eval import run_suite
from backend.services.analytics.competition_diagnosis.orchestrator import DiagnosisAdapter


def test_offline_eval_suite_passes():
    report = run_suite()
    assert report["t13_real_model"] == "NOT_RUN"
    assert report["failed"] == []
    assert report["passed"] == report["total"]
    assert report["total"] >= 20


def test_tools_do_not_expose_old_routes():
    assert "/api/v1/audience/table" not in REGISTERED_TOOLS
    assert "analytics_b0_query" not in REGISTERED_TOOLS
    for item in FORBIDDEN_EXPANSIONS:
        assert item not in REGISTERED_TOOLS


def test_chain_is_partial_while_cohort_unsupported():
    adapter = DiagnosisAdapter(AnalyticsPrincipal(
        actor_id="analyst.brand-a",
        capabilities=frozenset({
            "analysis:read", "analysis:save", "cohort:read", "draft:write",
            "dashboard:read", "dashboard:update",
        }),
        data_scopes=frozenset({"synthetic-c0"}),
    ))
    payload = adapter.run_chain(
        request_id="req_unit_chain",
        condition=success_condition().model_dump(mode="json"),
    )
    assert payload["analysis_complete"] is False
    assert payload["chain_status"] == "PARTIAL"
    assert payload["live_transport"] == "NOT_CONNECTED"


def test_partial_steps_and_changed_conditions_never_complete_a_chain():
    adapter = DiagnosisAdapter(AnalyticsPrincipal("analyst.brand-a",
        frozenset({"analysis:read"}), frozenset({"synthetic-c0"})))
    condition = success_condition().model_dump(mode="json")
    adapter.run_step(capability_id="diag.gsv", condition_mode="EXPLICIT",
                     condition=condition, request_id="first")
    first = adapter.session.steps[0]
    roles = [role if role != "diag.comparison" else "diag.yoy" for role in REQUIRED_FOR_COMPLETE_CHAIN]
    adapter.session.steps = [replace(first, capability_id=role, completeness="PARTIAL") for role in roles]
    assert adapter._chain_status() == "PARTIAL"
    adapter.session.steps = [replace(step, completeness="COMPLETE") for step in adapter.session.steps]
    assert adapter._chain_status() == "COMPLETE"
    adapter.run_step(capability_id="diag.gsv", condition_mode="INHERIT", request_id="unchanged")
    assert len(adapter.session.steps) == len(roles) + 1
    changed = {**condition, "sales_scope": {"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]}}
    result = adapter.run_step(capability_id="diag.gsv", condition_mode="EXPLICIT", condition=changed, request_id="changed")
    assert len(adapter.session.steps) == 1
    assert result["chain_status"] == "PARTIAL" and result["analysis_complete"] is False
