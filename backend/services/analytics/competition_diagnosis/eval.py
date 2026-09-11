"""Offline eval runner. T13 real model is NOT_RUN."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.errors import DiagnosisFault, invalid_request
from backend.services.analytics.competition_diagnosis.orchestrator import Budget, DiagnosisAdapter
from backend.services.analytics.competition_diagnosis.planner import dump_fault, plan_stub

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CASES = ROOT / "docs/hackathon/parallel-competition-2026-09-09/evidence/A7/eval/cases.json"

READ = frozenset({"analysis:read"})
COHORT = frozenset({"analysis:read", "cohort:read"})
WRITE = frozenset({"analysis:read", "dashboard:read", "dashboard:update"})
FULL = frozenset({
    "analysis:read", "analysis:save", "cohort:read", "draft:write",
    "dashboard:read", "dashboard:update",
})


def _principal(name: str) -> AnalyticsPrincipal:
    caps = {
        "analyst": FULL,
        "analyst_read": READ,
        "analyst_cohort": COHORT,
        "editor": WRITE,
        "none": frozenset(),
    }[name]
    return AnalyticsPrincipal(actor_id="analyst.brand-a" if name != "none" else "", capabilities=caps, data_scopes=frozenset({"synthetic-c0"}))


def _adapter(case: dict[str, Any]) -> DiagnosisAdapter:
    budget = case.get("budget") or {}
    faults = frozenset(case.get("faults") or [])
    return DiagnosisAdapter(
        _principal(case.get("actor", "analyst")),
        session_id=case.get("session_id", "session_c0_eval"),
        budget=Budget(
            max_tool_calls=int(budget.get("max_tool_calls", 12)),
            max_deadline_ms=int(budget.get("max_deadline_ms", 30000)),
        ),
        faults=faults,
    )


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    request_id = case.get("request_id", "req_eval")
    adapter = _adapter(case)
    if case.get("prior_condition"):
        adapter.session.prior_condition = case["prior_condition"]
    if case.get("in_flight_patch"):
        adapter.session.in_flight_patch = case["in_flight_patch"]
    action = case["action"]
    try:
        if action == "plan":
            payload = plan_stub(
                case["utterance"], request_id=request_id,
                has_prior=adapter.session.prior_condition is not None,
            )
        elif action == "step":
            payload = adapter.run_step(
                capability_id=case["capability_id"],
                condition_mode=case.get("condition_mode", "EXPLICIT"),
                condition=case.get("condition"),
                condition_patch=case.get("condition_patch"),
                request_id=request_id,
            )
        elif action == "chain":
            payload = adapter.run_chain(request_id=request_id, condition=case["condition"])
        elif action == "patch":
            payload = adapter.plan_selected_patch(
                intent=case["intent"],
                payload=case.get("payload") or {},
                selection=case.get("selection") or {},
                request_id=request_id,
            )
        elif action == "capabilities":
            payload = adapter.list_capabilities(request_id)
        elif action == "cancel":
            adapter.session.budget.used_calls = 0
            adapter._charge(request_id)
            payload = adapter.cancel(request_id)
        elif action == "resource":
            payload = adapter.read_resource(
                case["resource"], request_id,
                tuple(case.get("allowed") or ("references/evidence-policy.md", "assets/result-example.json")),
            )
        else:
            raise invalid_request("未知 eval action。", request_id, "action")
    except DiagnosisFault as fault:
        payload = dump_fault(fault)
        payload["chain_status"] = adapter.session.chain_status
        payload["analysis_complete"] = False
    except Exception:
        raise
    expected = case.get("expect") or {}
    failures = _check(expected, payload)
    for key, value in (case.get("expect_in") or {}).items():
        actual = _lookup(payload, key)
        if not isinstance(actual, list) or value not in actual:
            failures.append(f"{key} missing {value!r}")
    for key, value in (case.get("expect_not_in") or {}).items():
        actual = _lookup(payload, key)
        if isinstance(actual, list) and value in actual:
            failures.append(f"{key} unexpectedly has {value!r}")
    for left, right in case.get("expect_ne") or []:
        if _lookup(payload, left) == _lookup(payload, right):
            failures.append(f"{left} must differ from {right}")
    for key, value in (case.get("expect_contains") or {}).items():
        actual = _lookup(payload, key)
        if isinstance(actual, list):
            text = "\n".join(str(item) for item in actual)
        elif isinstance(actual, str):
            text = actual
        else:
            text = ""
        if value not in text:
            failures.append(f"{key} missing {value!r}")
    return {
        "id": case["id"],
        "ok": not failures,
        "failures": failures,
        "payload": payload,
        "t13_real_model": "NOT_RUN",
        "planner": "OFFLINE_STUB",
    }


def _check(expected: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key, value in expected.items():
        actual = _lookup(payload, key)
        if actual != value:
            failures.append(f"{key}: expected {value!r} got {actual!r}")
    return failures


def _lookup(payload: dict[str, Any], key: str) -> Any:
    current: Any = payload
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_CASES
    payload = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload["cases"])


def run_suite(path: Path | None = None) -> dict[str, Any]:
    cases = load_cases(path)
    results = [run_case(case) for case in cases]
    failed = [item["id"] for item in results if not item["ok"]]
    return {
        "schema_version": "competition-diagnosis-eval/v1",
        "planner": "OFFLINE_STUB",
        "t13_real_model": "NOT_RUN",
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": failed,
        "results": results,
    }


def main() -> int:
    report = run_suite()
    print(json.dumps({
        "total": report["total"],
        "passed": report["passed"],
        "failed": report["failed"],
        "t13_real_model": "NOT_RUN",
        "planner": "OFFLINE_STUB",
    }, ensure_ascii=False, indent=2))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
