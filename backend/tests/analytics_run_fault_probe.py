"""Owned child for B0 process faults. Never launched by application code."""

import json
import sys
from pathlib import Path

from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsRunRequest
from backend.services.analytics.jobs import ExecutionObservation, RunStore
from backend.tests.analytics_run_support import actor, observation, profile


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    payload = json.loads(sys.stdin.readline())
    if payload["action"] == "worker":
        emit({"ready": "worker", "attempt_id": payload["attempt_id"]})
        sys.stdin.readline()
        return

    def hook(point):
        if point == payload.get("fault"):
            emit({"ready": point})
            sys.stdin.readline()

    store = RunStore(Path(payload["state_dir"]), profile(), fault_hook=hook)
    principal = actor()
    if payload["action"] == "accept":
        accepted = store.accept(principal, payload["conversation_id"], payload["key"],
                                AnalyticsRunRequest(question="查看合成渠道"))
        emit({"accepted": accepted.model_dump(mode="json")})
    elif payload["action"] == "cancel":
        result = store.cancel(principal, payload["run_id"], "cancel", payload["version"], AnalyticsCancelRequest())
        emit({"cancelled": result.model_dump(mode="json")})
        return
    elif payload["action"] == "reserve-step":
        step = store.reserve_step(principal, payload["run_id"], payload["attempt_id"], "persistent-step")
        emit({"step_id": step.step_id, "deadline_ms": step.deadline_ms})
        sys.stdin.readline()
        return
    elif payload["action"] == "observe":
        result = store.observe(principal, ExecutionObservation(**payload["observation"]))
        emit({"terminal_notification": result.model_dump(mode="json")})
        return

    intent = store.claim_next(lambda owner: principal if owner == principal.actor_id else None)
    if intent is None:
        emit({"dispatch": None})
        return
    # The parent is an independent protocol receiver. Crash before its receipt
    # arrives simulates an accepted request whose response was lost in transit.
    emit({"dispatch": {
        "run_id": intent.run_id, "attempt_id": intent.attempt_id,
        "session_id": intent.session_id, "request_id": intent.request_id, "payload_hash": intent.payload_hash,
    }})
    receipt = json.loads(sys.stdin.readline())
    observed = observation(intent, "RUNNING", exited=False) if receipt["accepted"] else observation(
        intent, "FAILED", error_code="RUNTIME_REJECTED")
    result = store.observe(principal, observed)
    emit({"observed": result.status})


if __name__ == "__main__":
    main()
