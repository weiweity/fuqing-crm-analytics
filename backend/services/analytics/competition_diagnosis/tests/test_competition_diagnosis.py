"""Offline diagnosis adapter tests. No HTTP, DuckDB, or second runtime."""

from __future__ import annotations

from backend.contracts.competition_c0 import success_condition
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.chain import FORBIDDEN_EXPANSIONS, REGISTERED_TOOLS
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
