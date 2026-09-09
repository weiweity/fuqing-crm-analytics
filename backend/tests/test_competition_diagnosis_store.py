"""Computed result persistence, permission and HTTP-to-board integration."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from backend.analytics_competition_app import create_competition_app
from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.services.analytics.resource_profile import content_hash
from backend.services.analytics.saved_analyses import SavedAnalysisStore
from backend.tests.test_competition_computed_results import source as computed_source, condition

source = computed_source

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "computed-diagnosis-local-test-token-32chars"
OTHER_TOKEN = "computed-diagnosis-other-test-token-32chars"
CAPS = frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"})
SCOPES = frozenset({DATA_SCOPE, "channel-followup-fixture", "brand-a"})
ALICE = AnalyticsPrincipal("alice", CAPS, SCOPES)
BOB = AnalyticsPrincipal("bob", CAPS, SCOPES)
BASE = "/api/v1/analytics/competition"


def private(path):
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def app_at(tmp_path, source, registry):
    return create_competition_app(SavedAnalysisStore(private(tmp_path / "saved")), identities=registry,
        asset_state_dir=private(tmp_path / "assets"), diagnosis_source=source,
        diagnosis_state_dir=private(tmp_path / "diagnosis"))


def test_saved_result_survives_new_process_and_rejects_corruption(tmp_path, source):
    directory = private(tmp_path / "state")
    store = ComputedResultStore(directory)
    result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r1")
    digest = content_hash(condition().model_dump(mode="json"))
    saved = store.save(ALICE, "s1", "r1", digest, result)
    assert store.save(ALICE, "s1", "r1", digest, result) == saved
    with pytest.raises(AnalyticsError) as error:
        store.save(ALICE, "s1", "r1", "0" * 64, result)
    assert error.value.status == 409
    process = subprocess.run([sys.executable, "-c", """
import json, sys
from pathlib import Path
from backend.services.analytics.access import AnalyticsPrincipal
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
actor=AnalyticsPrincipal('alice', frozenset({'analysis:read'}), frozenset({'competition-diagnosis-fixture'}))
record=ComputedResultStore(Path(sys.argv[1])).get(actor,sys.argv[2])
print(json.dumps(record.facts))
""", str(directory), saved.analysis_id], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(process.stdout) == result.facts.model_dump(mode="json")
    assert store.list_results(BOB) == []
    with pytest.raises(AnalyticsError) as error:
        store.get(BOB, saved.analysis_id)
    assert error.value.status == 404
    with pytest.raises(AnalyticsError) as error:
        store.get(AnalyticsPrincipal("alice", frozenset(), SCOPES), saved.analysis_id)
    assert error.value.status == 403
    with sqlite3.connect(store.path) as conn:
        payload = saved.model_dump(mode="json")
        payload["evidence_digest"] = "0" * 64
        conn.execute("UPDATE results SET result_json=?", (json.dumps(payload),))
    with pytest.raises(AnalyticsError) as error:
        store.get(ALICE, saved.analysis_id)
    assert error.value.code == "BINDING_CORRUPT"


def test_sqlite_writer_conflict_does_not_publish_result(tmp_path, source):
    store = ComputedResultStore(private(tmp_path / "state"))
    result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r1")
    with sqlite3.connect(store.path) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(AnalyticsError) as error:
            store.save(ALICE, "s1", "r1", "1" * 64, result)
        assert error.value.status == 503 and error.value.retryable
        lock.rollback()
    assert store.list_results(ALICE) == []
    assert store.save(ALICE, "s1", "r1", "1" * 64, result).analysis_id


def test_saved_execution_cannot_move_to_another_request(tmp_path, source):
    store = ComputedResultStore(private(tmp_path / "state"))
    result = compute_result(source, ALICE, condition(), "diag.gsv", session_id="s1", request_id="r1")
    for session_id, request_id in (("s2", "r1"), ("s1", "r2")):
        with pytest.raises(AnalyticsError) as error:
            store.save(ALICE, session_id, request_id, "1" * 64, result)
        assert error.value.code == "BINDING_CORRUPT"
    assert store.list_results(ALICE) == []
    saved = store.save(ALICE, "s1", "r1", "1" * 64, result)
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE results SET session_id='s2'")
    with pytest.raises(AnalyticsError) as error:
        store.get(ALICE, saved.analysis_id)
    assert error.value.code == "BINDING_CORRUPT"


def test_http_computation_endorse_batch_and_frozen_reopen(tmp_path, source):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    registry.grant(OTHER_TOKEN, BOB)
    with TestClient(app_at(tmp_path, source, registry), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        payload = {"capability_id": "diag.gsv", "condition_mode": "EXPLICIT", "condition": condition().model_dump(mode="json"),
                   "request_id": "req1", "session_id": "native-session"}
        response = client.post(BASE + "/diagnosis/step", json=payload)
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert response.json()["analysis_persisted"] is True
        assert result["facts"]["current"]["gsv"] == 140
        assert response.json()["analysis_complete"] is False
        assert client.post(BASE + "/diagnosis/step", json=payload).json()["result"] == result
        items = client.get(BASE + "/results").json()["items"]
        assert items == [result]
        changed = deepcopy(payload)
        changed["condition"]["sales_scope"] = {"kind": "CHANNEL_IDS", "channel_ids": ["CH_RETAIL"]}
        assert client.post(BASE + "/diagnosis/step", json=changed).status_code == 409
        ref = {key: result[key] for key in ("result_id", "run_id", "analysis_id", "evidence_digest", "completeness")}
        forged = {**ref, "result_id": "result_someone_else"}
        assert client.post(BASE + "/endorsements", json={"result_refs": [forged]}, headers={"Idempotency-Key": "bad-ref"}).status_code == 409
        assert client.post(BASE + "/endorsements", json={"result_refs": [ref]}, headers={"Idempotency-Key": "endorse1"}).status_code == 201
        batch = {"schema_version": "competition-board-batch/v1", "batch_id": "batch_diag1", "layout_mode": "ONE_BOARD_MULTI_BLOCK",
                 "operations": [{"operation_id": "operation1", "idempotency_key": "create1", "request_fingerprint": result["evidence_digest"],
                                  "layout_mode": "ONE_BOARD_MULTI_BLOCK", "board_id": None, "title": "计算诊断板", "endorsed_result_refs": [ref]}]}
        created = client.post(BASE + "/batches", json=batch, headers={"Idempotency-Key": "create1"})
        assert created.status_code == 200, created.text
        board_id = created.json()["items"][0]["board_id"]
        assert board_id, created.text
        assert client.post(BASE + "/batches", json=batch, headers={"Idempotency-Key": "create1"}).json() == created.json()
        patch = {"board_id": board_id, "base_version": 1, "attempt_id": "add1", "idempotency_key": "add1",
                 "intent": "STRUCTURE", "cockpit_op": {"op": "add", "analysis_ref": {"analysis_id": result["analysis_id"], "version": 1}}}
        preview = client.post(BASE + "/boards/" + board_id + "/preview", json=patch)
        added = client.post(BASE + "/boards/" + board_id + "/versions", json=patch)
        assert preview.status_code == added.status_code == 200, added.text
        assert len(added.json()["blocks"]) == 2
        added_block = added.json()["blocks"][-1]
        assert added_block["result_id"] == result["result_id"] != result["run_id"]
        assert added_block["result"] == result
        assert preview.json()["blocks"][-1]["result"] == result
        copied = client.post(BASE + "/boards/" + board_id + "/versions", json={
            **patch, "base_version": 2, "attempt_id": "copy1", "idempotency_key": "copy1",
            "cockpit_op": {"op": "copy", "card_id": added_block["block_id"]}})
        assert copied.status_code == 200, copied.text
        assert len(copied.json()["blocks"]) == 3
        assert all(block["result"] == result for block in copied.json()["blocks"])
        undone = client.post(BASE + "/boards/" + board_id + "/versions", json={
            **patch, "base_version": 3, "attempt_id": "undo1", "idempotency_key": "undo1",
            "cockpit_op": {"op": "undo", "scope": "board", "restore_from_version": 1}})
        assert undone.status_code == 200, undone.text
        assert len(undone.json()["blocks"]) == 1
    # New app/store connections, and no source database: opening a board must not recompute.
    source.path.unlink()
    with TestClient(app_at(tmp_path, source, registry), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        response = client.get(BASE + "/boards/" + board_id)
        assert response.status_code == 200, response.text
        block = response.json()["blocks"][0]
        assert block["source_status"] == "OK", block
        assert block["facts"] == result["facts"]
        assert block["result"] == result
        assert len(client.get(BASE + "/boards").json()["items"]) == 1
        with sqlite3.connect(tmp_path / "assets" / "competition_assets.sqlite3") as conn:
            raw = json.loads(conn.execute("SELECT blocks_json FROM boards WHERE board_id=? AND version=4", (board_id,)).fetchone()[0])
        for key in ("result_id", "run_id"):
            corrupted = deepcopy(raw)
            corrupted[0][key] = key + "_other_execution"
            with sqlite3.connect(tmp_path / "assets" / "competition_assets.sqlite3") as conn:
                conn.execute("UPDATE boards SET blocks_json=? WHERE board_id=? AND version=4", (json.dumps(corrupted), board_id))
            response = client.get(BASE + "/boards/" + board_id)
            assert response.status_code == 200
            assert response.json()["blocks"][0]["source_status"] == "UNAVAILABLE"
        assert client.get(BASE + "/results", headers={"Authorization": f"Bearer {OTHER_TOKEN}"}).json()["items"] == []
        registry.grant(TOKEN, AnalyticsPrincipal("alice", CAPS - {"analysis:read"}, SCOPES))
        assert client.get(BASE + "/results").status_code == 403


def test_revocation_between_compute_and_save_never_publishes(tmp_path, source, monkeypatch):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    import backend.analytics_competition_app as wiring
    original = wiring.compute_result
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        registry.revoke(TOKEN)
        return result
    monkeypatch.setattr(wiring, "compute_result", revoke)
    with TestClient(app_at(tmp_path, source, registry), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        response = client.post(BASE + "/diagnosis/step", json={"capability_id": "diag.gsv", "condition_mode": "EXPLICIT",
            "condition": condition().model_dump(mode="json"), "session_id": "s1", "request_id": "r1"})
        assert response.status_code == 401
    assert ComputedResultStore(tmp_path / "diagnosis").list_results(ALICE) == []
