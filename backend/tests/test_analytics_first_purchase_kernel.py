"""Real first-purchase child on the shared lease/RunStore path."""
import json
from pathlib import Path
import pytest
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.contracts.analytics_first_purchase_kernel import FirstPurchaseConversationRequest, FirstPurchaseKernelRequest
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import profile, observation
from backend.tests.test_analytics_first_purchase_http import fp_actor

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.mark.parametrize("missing", [False, True])
def test_shared_worker_first_purchase(tmp_path, missing):
    suffix = "_missing_role" if missing else ""
    source = json.loads((FIXTURES / f"analytics_first_purchase_v1{suffix}.json").read_text())
    expected = json.loads((FIXTURES / f"analytics_first_purchase_v1{suffix}_expected.json").read_text())
    fixture = create_first_purchase_fixture(source)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = RunStore(state, profile(), family="first_purchase")
    actor = fp_actor()
    conv = store.create_conversation(actor, "conversation", FirstPurchaseConversationRequest())
    accepted = store.accept(actor, conv.conversation_id, "first-run", FirstPurchaseKernelRequest(question="首购"),
                            method_package_digest="a" * 64, fixture_descriptor=fixture.binding_descriptor())
    intent = store.claim_next(lambda _: actor)
    step = store.reserve_step(actor, intent.run_id, intent.attempt_id, "compute", request=expected["request"])
    result = WorkerManager(store, lambda _: actor, fixture).execute(actor, intent, step)
    assert result.facts == (None if missing else result.facts)
    assert result.status == ("REJECTED" if missing else "OK")
    if not missing:
        assert result.facts.model_dump(mode="json") == expected["result"]["facts"]
    done = store.observe(actor, observation(intent, "SUCCEEDED", primary=step.step_id))
    assert done.status == "SUCCEEDED"
    assert done.result == result
    reopened = RunStore(state, profile(), family="first_purchase")
    assert reopened.get(actor, accepted.run_id).result == result
    with pytest.raises(ValueError):
        RunStore(state, profile(), family="channel_followup")
