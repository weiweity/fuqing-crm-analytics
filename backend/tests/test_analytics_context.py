"""Small SQLite context/recovery tests, without CRM, model calls or servers."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from backend.analytics_runtime import runtime_app
from backend.contracts.analytics import AnalyticsCancelRequest, AnalyticsRunRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.jobs import RunStore
from backend.tests.analytics_run_support import (
    accept, actor, conversation, make_store, observation, profile, successful_step, synthetic_fixture,
)
from backend.tests.test_analytics_native_runtime import Receiver, native

DIGEST = "a" * 64


def running(path, **kwargs):
    store = make_store(path, **kwargs)
    conv = conversation(store)
    accepted = store.accept(actor(), conv.conversation_id, "run", AnalyticsRunRequest(question="查看合成渠道"), method_package_digest=DIGEST)
    intent = store.claim_next(lambda _: actor())
    return store, accepted, intent


def test_method_version_must_be_fixed_at_acceptance_not_inferred_after_a_crash(tmp_path):
    store = make_store(tmp_path)
    accept(store)
    intent = store.claim_next(lambda _: actor())
    with pytest.raises(AnalyticsError) as error:
        context(store, intent)
    assert error.value.code == "METHOD_NOT_BOUND"


def context(store, intent, *, unit="model:1:1", digest=DIGEST, principal=None, resource=None):
    return store.rebuild_context(principal or actor(), intent.run_id, intent.attempt_id,
                                 package_digest=digest, unit_id=unit, resource=resource)


def test_context_has_server_conditions_no_approval_or_fabricated_result(tmp_path):
    store, _, intent = running(tmp_path)
    state = context(store, intent)
    assert state["run_status"] == "RUNNING" and state["completed_steps"] == []
    assert state["conditions"]["mode"] == "FIXED_FIXTURE_NOT_PARSED_FROM_QUESTION"
    assert state["versions"]["method_package_digest"] == DIGEST
    assert state["contains_real_data"] is False
    assert state["memory_authority"] == "NONE" and state["approval_state"] == "NOT_AVAILABLE_IN_B0"
    assert state["remaining_budget"]["model_steps"] == 7


def test_context_rebuild_retains_budget_and_reads_new_evidence_across_connection_restart(tmp_path):
    clock = [10000]
    store, _, intent = running(tmp_path, clock=lambda: clock[0])
    first = context(store, intent)
    context(store, intent, unit="load-skill", resource="SKILL.md")
    step = successful_step(store, intent)
    clock[0] += 1000
    restored = RunStore(store.directory, profile(), clock=lambda: clock[0])
    after = context(restored, intent)  # same step identity, not a new allowance
    assert after["remaining_budget"]["model_steps"] == first["remaining_budget"]["model_steps"]
    assert after["remaining_budget"]["tool_steps"] == 6
    assert after["remaining_budget"]["remaining_ms"] == first["remaining_budget"]["remaining_ms"] - 1000
    assert after["remaining_budget"]["deadline"] == first["remaining_budget"]["deadline"]
    assert after["completed_steps"][0]["step_id"] == step.step_id
    assert after["completed_steps"][0]["result"]["facts"]["repeat_ratio"] == 0.25
    assert after["primary_result_ref"] is None  # step success is not run completion


def test_version_drift_and_replay_with_different_resource_are_rejected(tmp_path):
    store, _, intent = running(tmp_path)
    context(store, intent, unit="read-1", resource="SKILL.md")
    for changes in ({"digest": "b" * 64}, {"resource": "references/evidence-policy.md"}):
        with pytest.raises(AnalyticsError):
            context(store, intent, **{"unit": "read-1", "resource": "SKILL.md", **changes})


@pytest.mark.parametrize("principal", [actor("bob"), actor(capabilities={"run:read"}), actor(scopes=set())])
def test_context_rereads_object_and_current_capabilities_even_for_replay(tmp_path, principal):
    store, _, intent = running(tmp_path)
    context(store, intent)
    with pytest.raises(AnalyticsError):
        context(store, intent, principal=principal)


@pytest.mark.parametrize("ending", ["cancel", "timeout", "terminal"])
def test_no_late_context_can_restart_cancelled_expired_or_terminal_work(tmp_path, ending):
    clock = [10000]
    store, accepted, intent = running(tmp_path, clock=lambda: clock[0])
    context(store, intent)
    if ending == "cancel":
        current = store.get(actor(), accepted.run_id)
        store.cancel(actor(), accepted.run_id, "cancel", current.version, AnalyticsCancelRequest())
    elif ending == "timeout":
        clock[0] += profile().run_timeout_ms
    else:
        store.observe(actor(), observation(intent, "FAILED"))
    with pytest.raises(AnalyticsError):
        context(store, intent)


def test_model_and_shared_method_query_budgets_do_not_reset(tmp_path):
    store, _, intent = running(tmp_path, resource_profile=profile(max_tool_steps=2))
    context(store, intent)
    context(store, intent, unit="model:1:2")
    with pytest.raises(AnalyticsError):
        context(store, intent, unit="model:1:3")
    context(store, intent, unit="skill-1", resource="SKILL.md")
    successful_step(store, intent)
    with pytest.raises(AnalyticsError):
        context(store, intent, unit="resource-1", resource="references/evidence-policy.md")
    with pytest.raises(AnalyticsError):
        store.reserve_step(actor(), intent.run_id, intent.attempt_id, "query-too-many")
    assert context(store, intent)["remaining_budget"]["tool_steps"] == 0


def test_context_idempotency_survives_concurrent_callers_and_tool_id_cannot_change_kind(tmp_path):
    store, _, intent = running(tmp_path)
    peer = RunStore(store.directory, profile())
    barrier = Barrier(2)

    def read(instance):
        barrier.wait(timeout=2)
        return context(instance, intent, unit="same", resource="SKILL.md")

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(read, store), pool.submit(read, peer)
        assert a.result(timeout=3)["remaining_budget"]["tool_steps"] == b.result(timeout=3)["remaining_budget"]["tool_steps"] == 7
    with pytest.raises(AnalyticsError):
        store.reserve_step(actor(), intent.run_id, intent.attempt_id, "same")
    successful_step(store, intent, call_id="query")
    with pytest.raises(AnalyticsError):
        context(store, intent, unit="query", resource="SKILL.md")


def test_private_context_endpoint_requires_separate_runtime_capability_and_rechecks_revocation(tmp_path):
    fixture = synthetic_fixture(tmp_path / "fixture")
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    gateway, runtime = "g" * 32, "r" * 32
    app = runtime_app({"state_dir": state_dir, "session_id": "native-session", "fixture": asdict(fixture),
                       "gateway_token": gateway, "runtime_token": runtime, "method_package_digest": DIGEST}, bridge=Receiver())
    # TestClient executes in process; the synthetic bridge never opens a server.
    with TestClient(app) as client:
        app.state.dispatcher.tick()
        accepted = client.post("/internal/native/prompt", headers={"authorization": "Bearer " + gateway}, json=native())
        assert accepted.status_code == 202
        app.state.dispatcher.tick()
        body = {"session_id": "native-session", "request_id": "native-1", "unit_id": "model:1:1", "package_digest": DIGEST}
        headers = {"authorization": "Bearer " + runtime}
        assert client.post("/internal/native/run-context", headers=headers, json=body).status_code == 200
        assert client.post("/internal/native/run-context", headers={"authorization": "Bearer " + gateway}, json=body).status_code == 401
        for patch, status in [({"request_id": "other"}, 409), ({"session_id": "other"}, 404),
                              ({"package_digest": "b" * 64}, 409), ({"memory": "approved"}, 422), ({"resource": "../private"}, 422)]:
            assert client.post("/internal/native/run-context", headers=headers, json={**body, **patch}).status_code == status
        app.state.registry.revoke(gateway)
        assert client.post("/internal/native/run-context", headers=headers, json=body).status_code == 403
