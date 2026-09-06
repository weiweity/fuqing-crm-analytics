"""Adapter/real SQLite tests. Native DSH execution is tested separately."""

import pytest
from dataclasses import asdict
from fastapi.testclient import TestClient

from backend.analytics_runtime import runtime_app
from backend.contracts.analytics import AnalyticsRunRequest, AnalyticsConversationRequest, AnalyticsCancelRequest
from backend.services.analytics.access import AnalyticsError
from backend.services.analytics.runtime import RunDispatcher, execute_native_fixture
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import actor, make_store, accept, conversation, synthetic_fixture, sqlite_connection


class Receiver:
    """Controllable protocol receiver; deliberately NOT described as native DSH."""
    def __init__(self):
        self.calls = []
        self.lose_receipt = False
        self.corrupt = False
        self.outcome = "RUNNING"
        self.exited = False
        self.tool_calls = []
        self.available = True

    def call(self, operation, payload):
        self.calls.append((operation, payload))
        if not self.available:
            raise OSError("controlled transport down")
        if operation == "health":
            return {"ready": True}
        if operation == "dispatch":
            if self.lose_receipt:
                raise OSError("accepted but receipt lost")
            return {"accepted": True}
        if operation == "cancel":
            return {"accepted": True}
        return {**{key: payload[key] for key in ("run_id", "attempt_id", "session_id", "request_id")},
                "execution_exited": self.exited, "outcome": self.outcome, "successful_call_ids": self.tool_calls,
                **({"request_id": "foreign-request"} if self.corrupt else {})}


def native(key="native-1", text="合成渠道"):
    return {"sessionId": "native-session", "requestId": key, "mode": "queue", "content": [{"type": "text", "text": text}],
            "clientTimeZone": "Asia/Shanghai"}


def setup_native(path):
    store = make_store(path)
    conv = store.create_conversation(actor(), "native", AnalyticsConversationRequest(), runtime_session_id="native-session")
    payload = native()
    run = store.accept(actor(), conv.conversation_id, "native-1", AnalyticsRunRequest(question="合成渠道"), native_request=payload)
    return store, conv, run


def test_native_binding_preserves_request_id_and_replays_original_202_when_offline(tmp_path):
    store, conv, run = setup_native(tmp_path)
    intent = store.claim_next(lambda _id: actor())
    assert (intent.session_id, intent.request_id) == ("native-session", "native-1")
    replay = store.accept(actor(), conv.conversation_id, "native-1", AnalyticsRunRequest(question="合成渠道"),
                          native_request=native(), allow_new=False)
    assert replay == run
    with pytest.raises(AnalyticsError) as error:
        store.accept(actor(), conv.conversation_id, "native-1", AnalyticsRunRequest(question="合成渠道"),
                     native_request={**native(), "clientTimeZone": "UTC"})
    assert error.value.status == 409


def test_native_session_cannot_bind_foreign_conversation(tmp_path):
    store = make_store(tmp_path)
    conv = conversation(store)
    with pytest.raises(AnalyticsError):
        store.accept(actor(), conv.conversation_id, "native-1", AnalyticsRunRequest(question="合成渠道"), native_request=native())
    assert store.get_conversation(actor(), conv.conversation_id).run_ids == []


def test_dispatcher_lock_is_cross_instance_and_recover_does_not_resend(tmp_path):
    store, _, run = setup_native(tmp_path)
    receiver = Receiver()
    receiver.lose_receipt = True
    first = RunDispatcher(store, lambda _: actor(), receiver)
    first.start()
    second = RunDispatcher(store, lambda _: actor(), receiver)
    try:
        with pytest.raises(BlockingIOError):
            second.start()
        first.tick()
        assert store.get(actor(), run.run_id).status == "UNKNOWN"
    finally:
        first.close()
    second.start()
    try:
        second.tick()
        result = store.get(actor(), run.run_id)
        assert result.status == "RUNNING"
        assert result.diagnostics.dispatch_attempts == 1
        assert sum(method == "dispatch" for method, _ in receiver.calls) == 1
    finally:
        second.close()


def test_sqlite_writer_contention_pauses_dispatch_and_recovers_without_resend(tmp_path):
    store, _, run = setup_native(tmp_path)
    receiver = Receiver()
    dispatcher = RunDispatcher(store, lambda _: actor(), receiver)
    dispatcher.start()
    try:
        dispatcher.tick()
        before = store.get(actor(), run.run_id)
        assert dispatcher.ready
        with sqlite_connection(store.path) as writer:
            writer.execute("BEGIN IMMEDIATE")
            dispatcher.tick()
            assert not dispatcher.ready and dispatcher.last_error == "STATE_UNAVAILABLE"
            assert store.get(actor(), run.run_id) == before
            assert sum(method == "dispatch" for method, _ in receiver.calls) == 1
            writer.rollback()
        dispatcher.tick()
        assert dispatcher.ready and dispatcher.last_error is None
        assert sum(method == "dispatch" for method, _ in receiver.calls) == 1
        assert store.get(actor(), run.run_id).diagnostics.dispatch_attempts == 1
    finally:
        dispatcher.close()


def test_cancel_receipt_holds_slot_until_later_exit_and_second_question_dispatches(tmp_path):
    store, conv, run = setup_native(tmp_path)
    receiver = Receiver()
    dispatcher = RunDispatcher(store, lambda _: actor(), receiver)
    dispatcher.start()
    try:
        dispatcher.tick()
        initial = store.get(actor(), run.run_id)
        store.cancel(actor(), run.run_id, "cancel", initial.version, AnalyticsCancelRequest())
        next_run = accept(store, key="second", conversation_id=conv.conversation_id)
        dispatcher.tick()
        assert store.get(actor(), run.run_id).status == "CANCELLING"
        assert store.get(actor(), next_run.run_id).status == "QUEUED"
        assert any(method == "cancel" for method, _ in receiver.calls)
        receiver.outcome, receiver.exited = "CANCELLED", True
        dispatcher.tick()
        assert store.get(actor(), run.run_id).status == "CANCELLED"
        assert store.get(actor(), next_run.run_id).status == "RUNNING"
    finally:
        dispatcher.close()


@pytest.mark.parametrize("failure", ["foreign", "receipt-only", "unavailable"])
def test_invalid_or_missing_execution_proof_never_releases_slot(tmp_path, failure):
    store, _, run = setup_native(tmp_path)
    receiver = Receiver()
    dispatcher = RunDispatcher(store, lambda _: actor(), receiver)
    dispatcher.start()
    try:
        dispatcher.tick()
        receiver.corrupt = failure == "foreign"
        receiver.available = failure != "unavailable"
        if failure == "receipt-only":
            receiver.outcome = "SUCCEEDED"
        dispatcher.tick()
        snapshot = store.get(actor(), run.run_id)
        assert snapshot.status == "UNKNOWN"
        assert snapshot.diagnostics.execution_active
    finally:
        dispatcher.close()


def test_tool_budget_before_fixture_reuse_and_late_previous_request_fenced(tmp_path):
    store, conv, run = setup_native(tmp_path)
    receiver = Receiver()
    dispatcher = RunDispatcher(store, lambda _: actor(), receiver)
    workers = WorkerManager(store, lambda _: actor(), synthetic_fixture(tmp_path / "fixture"))
    dispatcher.start()
    try:
        dispatcher.tick()
        value = execute_native_fixture(store, lambda _: actor(), "native-session", "native-1", "tool-1", "channel_repeat_rate", workers=workers)
        replay = execute_native_fixture(store, lambda _: actor(), "native-session", "native-1", "tool-1", "channel_repeat_rate", workers=workers)
        assert value["step_id"] == replay["step_id"]
        assert replay["disposition"] == "REUSE_RESULT"
        assert replay["result"]["repeat_rate"] == 0.25
        assert store.get(actor(), run.run_id).diagnostics.tool_steps_used == 1
        receiver.tool_calls, receiver.outcome, receiver.exited = ["tool-1"], "SUCCEEDED", True
        dispatcher.tick()
        assert store.get(actor(), run.run_id).status == "SUCCEEDED"
        next_run = accept(store, key="second", conversation_id=conv.conversation_id)
        dispatcher.tick()
        with pytest.raises(AnalyticsError):
            execute_native_fixture(store, lambda _: actor(), "native-session", "native-1", "late", "channel_repeat_rate", workers=workers)
        assert store.get(actor(), next_run.run_id).diagnostics.tool_steps_used == 0
    finally:
        dispatcher.close()


def test_native_success_without_committed_primary_is_business_failure_not_success(tmp_path):
    store, _, run = setup_native(tmp_path)
    receiver = Receiver()
    dispatcher = RunDispatcher(store, lambda _: actor(), receiver)
    dispatcher.start()
    try:
        dispatcher.tick()
        receiver.outcome, receiver.exited = "SUCCEEDED", True
        dispatcher.tick()
        result = store.get(actor(), run.run_id)
        assert result.status == "FAILED"
        assert not result.diagnostics.execution_active
    finally:
        dispatcher.close()


def test_private_api_auth_roles_and_no_public_contract_expansion(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    config = {"state_dir": str(state), "session_id": "native-session", "gateway_token": "g" * 40, "runtime_token": "r" * 40,
              "fixture": asdict(synthetic_fixture(tmp_path / "fixture"))}
    app = runtime_app(config, bridge=Receiver())
    app.state.dispatcher.ready = True
    client = TestClient(app)
    try:
        assert not any(path.startswith("/internal") for path in app.openapi()["paths"])
        endpoint = "/internal/native/prompt"
        assert client.post(endpoint, json=native()).status_code == 401
        assert client.post(endpoint, json=native(), headers={"authorization": "Bearer " + "r" * 40}).status_code == 401
        auth = {"authorization": "Bearer " + "g" * 40}
        created = client.post(endpoint, json=native(), headers=auth)
        assert created.status_code == 202
        assert client.post(endpoint, json={**native(), "sessionId": "foreign"}, headers=auth).status_code == 404
        assert client.post(endpoint, json={**native(), "run_id": "injected"}, headers=auth).status_code == 422
        assert client.post(endpoint, json=native(text="  "), headers=auth).status_code == 422
        assert client.post(endpoint, json=native(text="bad\x00text"), headers=auth).status_code == 422
        foreign = client.post('/api/v1/analytics/conversations', json={}, headers={**auth, 'idempotency-key': 'unbound'}).json()
        unbound = client.post(f'/api/v1/analytics/conversations/{foreign["conversation_id"]}/runs', json={"question": "fixture"},
                              headers={**auth, 'idempotency-key': 'unbound-run'})
        assert unbound.status_code == 503
        step = {"session_id": "native-session", "request_id": "native-1", "call_id": "tool", "query": "channel_repeat_rate"}
        assert client.post("/internal/native/fixture", json=step, headers=auth).status_code == 401
        app.state.registry.revoke(config["gateway_token"])
        assert client.post(endpoint, json=native(), headers=auth).status_code == 401
    finally:
        client.close()
