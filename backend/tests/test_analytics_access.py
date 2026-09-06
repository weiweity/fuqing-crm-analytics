"""Current identity, object ownership and capability checks for isolated B0."""

import pytest
from fastapi.testclient import TestClient

from backend.analytics_app import PREFIX, create_app
from backend.contracts.analytics import AnalyticsCancelRequest
from backend.services.analytics.access import AnalyticsError, B0IdentityRegistry
from backend.tests.analytics_run_support import (
    accept, actor, conversation, make_store, observation, successful_step,
)

TOKEN = "b0-tests-only-not-a-live-secret-0001"


def test_identical_keys_from_two_actors_do_not_share_objects(tmp_path):
    store = make_store(tmp_path / "state")
    alice = accept(store, actor("alice"))
    bob = accept(store, actor("bob"))
    assert alice.run_id != bob.run_id
    for operation in (
        lambda: store.get(actor("bob"), alice.run_id),
        lambda: store.events(actor("bob"), alice.run_id),
        lambda: store.cancel(actor("bob"), alice.run_id, "cancel", 1, AnalyticsCancelRequest()),
        lambda: store.get_conversation(actor("bob"), store.get(actor(), alice.run_id).conversation_id),
    ):
        with pytest.raises(AnalyticsError) as error:
            operation()
        assert error.value.status == 404


def test_parent_must_belong_to_actor_and_same_conversation(tmp_path):
    store = make_store(tmp_path / "state")
    parent = accept(store)
    other = conversation(store, key="second")
    for principal, conv in ((actor(), other), (actor("bob"), conversation(store, actor("bob")))):
        with pytest.raises(AnalyticsError) as error:
            accept(store, principal, conversation_id=conv.conversation_id, parent=parent.run_id)
        assert error.value.status == 404


@pytest.mark.parametrize("revoked", [actor(capabilities={"run:read"}), actor(scopes=set())])
def test_acceptance_and_replay_recheck_current_capability_and_scope(tmp_path, revoked):
    store = make_store(tmp_path / "state")
    first = accept(store)
    conv = store.get(actor(), first.run_id).conversation_id
    for key in ("run", "new"):
        with pytest.raises(AnalyticsError) as error:
            accept(store, revoked, conversation_id=conv, key=key)
        assert error.value.status == 403
    assert store.get(actor(), first.run_id).version == 1


def test_read_does_not_grant_cancel(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    reader = actor(capabilities={"run:read"})
    assert store.get(reader, accepted.run_id).status == "QUEUED"
    with pytest.raises(AnalyticsError) as error:
        store.cancel(reader, accepted.run_id, "cancel", 1, AnalyticsCancelRequest())
    assert error.value.status == 403


def test_dispatch_rechecks_current_grants_before_transport(tmp_path):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    assert store.claim_next(lambda _owner: actor(capabilities=set())) is None
    snapshot = store.get(actor(), accepted.run_id)
    assert snapshot.status == "FAILED" and snapshot.diagnostics.error_code == "PERMISSION_REVOKED"
    assert snapshot.diagnostics.dispatch_attempts == 0


def test_revoked_execution_keeps_slot_and_cannot_publish_result(tmp_path):
    store = make_store(tmp_path / "state")
    accept(store)
    intent = store.claim_next(actor)
    step = successful_step(store, intent)
    denied = actor(capabilities={"run:read"})
    waiting = store.observe(denied, observation(intent, "RUNNING", exited=False))
    assert waiting.status == "CANCELLING" and waiting.diagnostics.execution_active
    assert waiting.diagnostics.error_code == "PERMISSION_REVOKED"
    assert store.events(actor(), intent.run_id)[-1].payload.version == waiting.version
    assert store.observe(denied, observation(intent, "RUNNING", exited=False)) == waiting
    with pytest.raises(AnalyticsError) as error:
        store.reserve_step(denied, intent.run_id, intent.attempt_id, "revoked-tool")
    assert error.value.status == 403
    terminal = store.observe(None, observation(intent, "SUCCEEDED", primary=step.step_id))
    assert terminal.status == "FAILED" and terminal.result is None
    assert terminal.diagnostics.error_code == "PERMISSION_REVOKED"
    assert not terminal.diagnostics.execution_active


@pytest.mark.parametrize("change", ["revoke", "capability", "scope", "actor"])
def test_sse_rechecks_identity_before_each_disclosure(tmp_path, monkeypatch, change):
    store = make_store(tmp_path / "state")
    accepted = accept(store)
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    original = store.events
    calls = 0

    def revoke_after_read(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 2:  # after preflight, immediately before the first yield
            if change == "revoke":
                registry.revoke(TOKEN)
            elif change == "capability":
                registry.grant(TOKEN, actor(capabilities=set()))
            elif change == "scope":
                registry.grant(TOKEN, actor(scopes=set()))
            else:
                registry.grant(TOKEN, actor("bob"))
        return result

    monkeypatch.setattr(store, "events", revoke_after_read)
    with TestClient(create_app(store, registry, stream_window_seconds=0.1)) as client:
        response = client.get(f"{PREFIX}/runs/{accepted.run_id}/events", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert "event: error" in response.text
    assert accepted.run_id not in response.text and "run.updated" not in response.text


def test_registry_has_no_default_or_actor_id_identity():
    registry = B0IdentityRegistry()
    for authorization in (None, "Bearer alice", f"Bearer {TOKEN}", "Basic ignored"):
        with pytest.raises(AnalyticsError) as error:
            registry.resolve(authorization)
        assert error.value.status == 401
    for token in ("short", "x" * 1020, "x" * 31 + " "):
        with pytest.raises(ValueError):
            registry.grant(token, actor())
