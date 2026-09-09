"""Review regressions: isolated state, real HTTP handlers and deterministic races."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend.analytics_competition_app import create_competition_app
from backend.contracts.competition_c0 import success_condition
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.competition_assets.service import CompetitionAssetService
from backend.services.analytics.competition_assets.store import CompetitionAssetStore
from backend.services.analytics.competition_audience.errors import CompetitionAudienceError
from backend.services.analytics.competition_audience.golden import t05_cohort_payload
from backend.services.analytics.competition_audience.service import CompetitionAudienceService
from backend.services.analytics.competition_audience.store import transaction
from backend.tests.test_competition_http_wiring import CAPS, SCOPE, TOKEN, _app, _private, _run

BASE = "/api/v1/analytics/competition"


def actor(name="alice", scope="scope-brand-a"):
    return AnalyticsPrincipal(name, CAPS, frozenset({scope}))


def preview_body(**overrides):
    return {"cohort": t05_cohort_payload(), "combine": "AND",
            "source_result_ref": "result_review_source", "candidate_set_id": "cand_review", **overrides}


def test_candidate_id_is_immutable_across_scopes_and_reopen(tmp_path):
    service = CompetitionAudienceService(_private(tmp_path / "audience"))
    original = service.preview_candidates(actor(), preview_body())["candidates"]
    # Exact replay is allowed, mutation of evidence under the same ID is not.
    assert service.preview_candidates(actor(), preview_body())["candidates"] == original
    with pytest.raises(CompetitionAudienceError) as error:
        service.preview_candidates(actor("bob", "scope-brand-b"), preview_body(
            cohort=t05_cohort_payload(cohort_id="cohort_b", permission_scope="scope-brand-b")))
    assert error.value.status == 403
    with pytest.raises(CompetitionAudienceError) as error:
        service.preview_candidates(actor(), preview_body(source_result_ref="result_changed"))
    assert error.value.status == 409
    reopened = CompetitionAudienceService(tmp_path / "audience")
    assert reopened.get_candidates(actor(), "cand_review", permission_scope="scope-brand-a") == original
    # Reject state left inconsistent by the old vulnerable UPSERT as well.
    corrupt = original.model_copy(update={"permission_scope": "scope-brand-b"})
    with transaction(service.store.path) as con:
        con.execute("UPDATE candidates SET payload_json=? WHERE candidate_set_id=?",
                    (corrupt.model_dump_json(), "cand_review"))
    with pytest.raises(CompetitionAudienceError) as error:
        reopened.get_candidates(actor(), "cand_review", permission_scope="scope-brand-a")
    assert error.value.status == 503


def diagnosis_client():
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    client = TestClient(create_competition_app(identities=registry), headers={"Authorization": f"Bearer {TOKEN}"})
    return registry, client


def test_diagnosis_reauthorizes_existing_session(tmp_path):
    registry, client = diagnosis_client()
    payload = {"session_id": "native_one", "capability_id": "diag.gsv", "condition_mode": "EXPLICIT",
               "condition": success_condition().model_dump(mode="json")}
    assert client.post(BASE + "/diagnosis/step", json=payload).status_code == 200
    registry.grant(TOKEN, AnalyticsPrincipal("alice", frozenset(), frozenset()))
    denied = client.post(BASE + "/diagnosis/step", json=payload)
    assert denied.status_code == 403
    assert "diag.gsv" not in client.post(BASE + "/diagnosis/capabilities", json={"session_id": "native_one"}).json()["capability_ids"]


def test_diagnosis_budget_and_conditions_are_session_scoped():
    _, client = diagnosis_client()
    payload = {"session_id": "native_one", "capability_id": "diag.gsv", "condition_mode": "EXPLICIT",
               "condition": success_condition().model_dump(mode="json")}
    assert client.post(BASE + "/diagnosis/step", json=payload).status_code == 200
    inherit = {"session_id": "native_two", "capability_id": "diag.gsv", "condition_mode": "INHERIT"}
    assert client.post(BASE + "/diagnosis/step", json=inherit).status_code == 422
    for _ in range(11):
        assert client.post(BASE + "/diagnosis/capabilities", json={"session_id": "native_one"}).status_code == 200
    assert client.post(BASE + "/diagnosis/capabilities", json={"session_id": "native_one"}).status_code == 429
    assert client.post(BASE + "/diagnosis/capabilities", json={"session_id": "native_three"}).status_code == 200
    for _ in range(14):
        assert client.post(BASE + "/diagnosis/capabilities", json={}).status_code == 200


def test_current_draft_survives_app_reopen_and_is_private(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, actor())
    bob_token = "bob-review-synthetic-token-32chars"
    registry.grant(bob_token, actor("bob"))
    directory = _private(tmp_path / "audience")
    def client(token=TOKEN):
        return TestClient(create_competition_app(identities=registry, audience_state_dir=directory),
                          headers={"Authorization": f"Bearer {token}"})
    original = client()
    assert original.get(BASE + "/drafts/current").json()["draft"] is None
    candidates = original.post(BASE + "/candidates/preview", json=preview_body()).json()["candidates"]
    saved = original.post(BASE + "/drafts", json={"candidate_set_id": candidates["candidate_set_id"],
        "permission_scope": "scope-brand-a", "control_design": "test control", "stop_condition": "test stop"})
    assert saved.status_code == 200
    reopened = client().get(BASE + "/drafts/current")
    assert reopened.status_code == 200
    assert reopened.json()["draft"] == saved.json()
    assert reopened.json()["candidates"] == candidates
    assert client(bob_token).get(BASE + "/drafts/current").json()["draft"] is None
    registry.grant(TOKEN, actor(scope="scope-brand-b"))
    assert client().get(BASE + "/drafts/current").json()["draft"] is None


def seeded(tmp_path):
    app, analyses = _app(tmp_path)
    owner = AnalyticsPrincipal("alice", CAPS, SCOPE)
    run = _run()
    analyses.register_succeeded_run(owner, run)
    analyses.save(owner, "save-review", {"title": "review", "created_from_run_id": run["run_id"],
                                        "filters": deepcopy(run["request"])})
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    row = client.get(BASE + "/results").json()["items"][0]
    ref = {key: row[key] for key in ("result_id", "run_id", "analysis_id", "evidence_digest", "completeness")}
    payload = {"schema_version": "competition-board-batch/v1", "batch_id": "batch_review",
               "layout_mode": "ONE_BOARD_MULTI_BLOCK", "operations": [{"board_id": None,
                   "endorsed_result_refs": [ref], "idempotency_key": "create-review", "operation_id": "op_review",
                   "layout_mode": "ONE_BOARD_MULTI_BLOCK", "request_fingerprint": ref["evidence_digest"], "title": "review"}]}
    return client, payload


@pytest.mark.parametrize("kind", ["batch", "attempt"])
def test_cancel_wins_before_publish_even_after_handler_check(tmp_path, monkeypatch, kind):
    client, batch = seeded(tmp_path)
    if kind == "batch":
        method, path, payload, target = "apply_batch", "/batches", batch, batch["batch_id"]
    else:
        created = client.post(BASE + "/batches", json=batch).json()["board"]
        payload = {"schema_version": "competition-board-patch/v1", "attempt_id": "attempt_review",
                   "board_id": created["board_id"], "block_id": created["block_ids"][0], "base_version": 1,
                   "idempotency_key": "patch-review", "intent": "STYLE_ONLY",
                   "display_op": {"op": "display", "card_id": created["block_ids"][0], "display_overrides": {"title": "new"}}}
        method, path, target = "apply_patch", f"/boards/{created['board_id']}/versions", "attempt_review"
    entered, release = Event(), Event()
    original = getattr(CompetitionAssetService, method)
    def held(self, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(CompetitionAssetService, method, held)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, BASE + path, json=payload)
        try:
            assert entered.wait(10)
            cancelled = client.post(BASE + f"/{'batches' if kind == 'batch' else 'attempts'}/{target}/cancel")
            assert cancelled.status_code == 200, cancelled.text
        finally:
            release.set()
        assert future.result(timeout=10).json()["error"]["code"] == "CANCELLED"
    reopened, _ = _app(tmp_path)
    other = TestClient(reopened, headers={"Authorization": f"Bearer {TOKEN}"})
    assert other.post(BASE + path, json=payload).json()["error"]["code"] == "CANCELLED"
    boards = other.get(BASE + "/boards").json()["items"]
    assert len(boards) == (0 if kind == "batch" else 1)
    assert not boards or boards[0]["version"] == 1


def test_cancel_cannot_report_success_while_publish_holds_write_transaction(tmp_path, monkeypatch):
    client, batch = seeded(tmp_path)
    entered, release = Event(), Event()
    original = CompetitionAssetStore.insert_board
    def held(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(CompetitionAssetStore, "insert_board", held)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, BASE + "/batches", json=batch)
        try:
            assert entered.wait(10)
            assert client.post(BASE + "/batches/batch_review/cancel").status_code == 503
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    assert client.post(BASE + "/batches/batch_review/cancel").json()["error"]["code"] == "ALREADY_PUBLISHED"


def test_cancel_is_committed_across_process_exit(tmp_path):
    directory = _private(tmp_path / "cancel-state")
    root = Path(__file__).resolve().parents[2]
    script = """
import sys
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.competition_assets.store import CompetitionAssetStore
owner = AnalyticsPrincipal('alice', frozenset(), frozenset())
store = CompetitionAssetStore(sys.argv[1])
if sys.argv[2] == 'write':
    store.cancel(owner, 'attempt', 'attempt_process_exit')
else:
    try:
        with store.readonly() as con:
            store.require_not_cancelled(con, owner, 'attempt', 'attempt_process_exit')
    except AnalyticsError as error:
        assert error.code == 'CANCELLED' and error.status == 409
    else:
        raise AssertionError('cancellation lost after process exit')
store.close()
"""
    for mode in ("write", "read"):
        child = subprocess.run(
            [sys.executable, "-c", script, str(directory), mode], cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(root), "PYTHON_DOTENV_DISABLED": "1"},
            capture_output=True, text=True, timeout=15,
        )
        assert child.returncode == 0, child.stderr


def test_board_http_returns_frozen_result_binding_and_saved_layout(tmp_path):
    client, batch = seeded(tmp_path)
    ref = batch["operations"][0]["endorsed_result_refs"][0]
    ref["result_id"] = "result_review_alias"
    created = client.post(BASE + "/batches", json=batch).json()["board"]
    board_id, block_id = created["board_id"], created["block_ids"][0]
    layout = {"x": 6, "y": 9, "w": 4, "h": 4}
    patch = {"schema_version": "competition-board-patch/v1", "attempt_id": "attempt_layout_review",
             "board_id": board_id, "block_id": block_id, "base_version": 1,
             "idempotency_key": "layout-review", "intent": "STYLE_ONLY",
             "cockpit_op": {"op": "layout", "card_id": block_id, "layout": layout}}
    saved = client.post(BASE + f"/boards/{board_id}/versions", json=patch)
    assert saved.status_code == 200, saved.text
    reopened, _ = _app(tmp_path)
    other = TestClient(reopened, headers={"Authorization": f"Bearer {TOKEN}"})
    block = other.get(BASE + f"/boards/{board_id}").json()["blocks"][0]
    assert block["layout"] == layout
    assert block["result_id"] == block["result"]["result_id"] == "result_review_alias"
    assert block["result"]["analysis_id"] == ref["analysis_id"]
    assert block["result"]["evidence_digest"] == ref["evidence_digest"]
