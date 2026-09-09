"""G2 HTTP wiring for competition assets/audience. Isolated TestClient, no port 8000."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from backend.analytics_competition_app import create_competition_app
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.cockpit import CockpitStore
from backend.services.analytics.saved_analyses import SavedAnalysisStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TOKEN = "b0-competition-http-token-32chars-min"
CAPS = frozenset({
    "analysis:save", "analysis:read", "dashboard:read", "dashboard:update",
    "cohort:read", "draft:write",
})
SCOPE = frozenset({"channel-followup-fixture", "brand-a"})


def _private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _run() -> dict:
    return deepcopy(json.loads((FIXTURE_DIR / "analytics_saved_analysis_succeeded_run.json").read_text())["run"])


def _app(tmp_path: Path):
    identities = B0IdentityRegistry()
    identities.grant(TOKEN, AnalyticsPrincipal("alice", CAPS, SCOPE))
    identities.grant("bob-independent-synthetic-token-32chars", AnalyticsPrincipal("bob", CAPS, SCOPE))
    analyses = SavedAnalysisStore(_private(tmp_path / "saved"))
    cockpit = CockpitStore(_private(tmp_path / "cockpit"))
    return create_competition_app(
        analyses, cockpit, identities,
        asset_state_dir=_private(tmp_path / "assets"),
        audience_state_dir=_private(tmp_path / "audience"),
    ), analyses


def test_unauthenticated_is_c0_body(tmp_path):
    app, _ = _app(tmp_path)
    client = TestClient(app)
    response = client.get("/api/v1/analytics/catalog")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_catalog_filters_actor(tmp_path):
    app, _ = _app(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    response = client.get("/api/v1/analytics/catalog")
    assert response.status_code == 200
    ids = {item["capability_id"] for item in response.json()["capabilities"]}
    assert "diag.gsv" in ids


def test_endorsement_conflict_on_payload_change(tmp_path):
    app, analyses = _app(tmp_path)
    principal = AnalyticsPrincipal("alice", CAPS, SCOPE)
    run = _run()
    analyses.register_succeeded_run(principal, run)
    saved = analyses.save(principal, "save-1", {
        "title": "t", "created_from_run_id": run["run_id"], "filters": deepcopy(run["request"]),
    })
    binding = saved.binding()
    ref = {
        "result_id": f"result_{binding['run_id'][4:]}",
        "run_id": binding["run_id"],
        "analysis_id": binding["analysis_id"],
        "evidence_digest": binding["evidence_digest"],
        "completeness": "COMPLETE",
    }
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "endorse-1"})
    first = client.post("/api/v1/analytics/competition/endorsements", json={"result_refs": [ref]})
    assert first.status_code == 201
    other = dict(ref)
    other["result_id"] = "result_other"
    second = client.post("/api/v1/analytics/competition/endorsements", json={"result_refs": [other]})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


def test_cancel_rejects_late_attempt_publish(tmp_path):
    app, _ = _app(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    cancelled = client.post("/api/v1/analytics/competition/attempts/attempt_late/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["late_attempt_publish"] is False
    late = client.post(
        "/api/v1/analytics/competition/boards/board_x/versions",
        json={
            "attempt_id": "attempt_late",
            "board_id": "board_x",
            "block_id": "block_x",
            "base_version": 1,
            "intent": "STYLE_ONLY",
            "idempotency_key": "late-1",
        },
        headers={"If-Match": "1"},
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "CANCELLED"


def test_draft_rejects_auto_send(tmp_path):
    app, _ = _app(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    response = client.post(
        "/api/v1/analytics/competition/drafts",
        json={"auto_send": True, "candidate_set_id": "cand_missing", "permission_scope": "brand-a"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["param"] == "auto_send"


def _app_t05(tmp_path: Path):
    identities = B0IdentityRegistry()
    identities.grant(TOKEN, AnalyticsPrincipal("alice", CAPS, frozenset({
        "channel-followup-fixture", "brand-a", "scope-brand-a",
    })))
    analyses = SavedAnalysisStore(_private(tmp_path / "saved"))
    cockpit = CockpitStore(_private(tmp_path / "cockpit"))
    return create_competition_app(
        analyses, cockpit, identities,
        asset_state_dir=_private(tmp_path / "assets"),
        audience_state_dir=_private(tmp_path / "audience"),
    )


def test_t05_http_keeps_a8_and_a9_golds_independent(tmp_path):
    from backend.services.analytics.competition_audience.golden import (
        T05_ORIGIN_CHANNEL_ABSENT,
        t05_cohort_payload,
        t05_rule,
    )

    app = _app_t05(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    a8 = client.post(
        "/api/v1/analytics/competition/candidates/preview",
        json={
            "cohort": t05_cohort_payload(rules=[t05_rule("rule_origin_channel", "ORIGIN_CHANNEL_ABSENT")]),
            "combine": "AND",
            "source_result_ref": "result_t05_gsv_20260831",
            "permission_scope": "scope-brand-a",
            "auto_send": False,
            "candidate_set_id": "cand_http_a8",
        },
    )
    assert a8.status_code == 200, a8.text
    assert set(a8.json()["candidates"]["customer_keys"]) == set(T05_ORIGIN_CHANNEL_ABSENT)
    a9 = client.post(
        "/api/v1/analytics/competition/candidates/preview",
        json={
            "cohort": {
                "cohort_id": "cohort_a9_t05_ly_f4_10",
                "enrollment_window": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                "observation_window": {"start_date": "2026-01-01", "end_date": "2026-09-21"},
                "enrollment_rule_version": "competition-cohort-rule-v1",
                "as_of": "2025-12-31T04:00:00.000000+00:00",
                "published_at": "2026-09-21T16:00:00.000000+00:00",
                "source_tense": "PUBLISHED_SNAPSHOT",
                "member_history_status": "UNKNOWN",
                "existing_family": "none",
                "rules": [t05_rule("rule_origin_channel", "ORIGIN_CHANNEL_ABSENT")],
                "permission_scope": "scope-brand-a",
                "limitations": ["A9 independent T05 gold."],
            },
            "combine": "AND",
            "source_result_ref": "result_a9_t05_gsv",
            "permission_scope": "scope-brand-a",
            "auto_send": False,
            "candidate_set_id": "cand_http_a9",
        },
    )
    assert a9.status_code == 200, a9.text
    assert set(a9.json()["candidates"]["customer_keys"]) == {
        "C05", "C06", "C07", "C08", "C09", "C10",
    }


def test_results_are_endorsable_and_batch_reopens_board(tmp_path):
    from backend.services.analytics.access import AnalyticsPrincipal

    app, analyses = _app(tmp_path)
    principal = AnalyticsPrincipal("alice", CAPS, SCOPE)
    run = _run()
    analyses.register_succeeded_run(principal, run)
    analyses.save(principal, "save-synth-board", {
        "title": "synth GSV",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
    })
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    listed = client.get("/api/v1/analytics/competition/results")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert items, listed.text
    row = items[0]
    assert row["completeness"] == "COMPLETE"
    assert row["contains_real_data"] is False
    assert row["resolved_condition"]["metric_type"] == "GSV"
    assert isinstance(row.get("row_count"), int)
    assert row["row_count"] >= 0
    assert row["resolved_condition"]["history_scope"]["kind"] == "ALL"
    assert row["resolved_condition"]["sales_scope"]["kind"] == "ALL"
    assert row["resolved_condition"]["cutoff"]
    assert row["resolved_condition"]["sample_mode"]
    assert len(row["evidence_digest"]) == 64
    endorse = client.post(
        "/api/v1/analytics/competition/endorsements",
        json={"result_refs": [{
            "result_id": row["result_id"],
            "run_id": row["run_id"],
            "analysis_id": row["analysis_id"],
            "evidence_digest": row["evidence_digest"],
            "completeness": "COMPLETE",
        }]},
        headers={"Idempotency-Key": "endorse-loop-1"},
    )
    assert endorse.status_code == 201, endorse.text
    batch = client.post(
        "/api/v1/analytics/competition/batches",
        json={
            "schema_version": "competition-board-batch/v1",
            "batch_id": "batch_synth_loop_1",
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "operations": [{
                "board_id": None,
                "endorsed_result_refs": [{
                    "result_id": row["result_id"],
                    "run_id": row["run_id"],
                    "analysis_id": row["analysis_id"],
                    "evidence_digest": row["evidence_digest"],
                    "completeness": "COMPLETE",
                }],
                "idempotency_key": "board-create-loop",
                "layout_mode": "ONE_BOARD_MULTI_BLOCK",
                "operation_id": "op_synth_board_a",
                "request_fingerprint": row["evidence_digest"],
                "title": "合成认可板",
            }],
        },
        headers={"Idempotency-Key": "board-create-loop"},
    )
    assert batch.status_code == 200, batch.text
    body = batch.json()
    assert body["http_api"] == "CONNECTED"
    board_id = (body.get("board") or {}).get("board_id") or body["items"][0]["board_id"]
    assert board_id
    boards = client.get("/api/v1/analytics/competition/boards")
    assert boards.status_code == 200
    ids = {item["board_id"] for item in boards.json()["items"]}
    assert board_id in ids
    reopened = client.get(f"/api/v1/analytics/competition/boards/{board_id}")
    assert reopened.status_code == 200, reopened.text
    spec = reopened.json().get("spec") or reopened.json()
    assert spec["board_id"] == board_id
    assert spec["schema_version"] == "competition-board/v1"
    assert spec["persisted"] is True
    replay = client.post(
        "/api/v1/analytics/competition/batches",
        json={
            "schema_version": "competition-board-batch/v1",
            "batch_id": "batch_synth_loop_1",
            "layout_mode": "ONE_BOARD_MULTI_BLOCK",
            "operations": [{
                "board_id": None,
                "endorsed_result_refs": [{
                    "result_id": row["result_id"],
                    "run_id": row["run_id"],
                    "analysis_id": row["analysis_id"],
                    "evidence_digest": row["evidence_digest"],
                    "completeness": "COMPLETE",
                }],
                "idempotency_key": "board-create-loop",
                "layout_mode": "ONE_BOARD_MULTI_BLOCK",
                "operation_id": "op_synth_board_a",
                "request_fingerprint": row["evidence_digest"],
                "title": "合成认可板",
            }],
        },
        headers={"Idempotency-Key": "board-create-loop"},
    )
    assert replay.status_code == 200, replay.text
    replay_id = (replay.json().get("board") or {}).get("board_id") or replay.json()["items"][0]["board_id"]
    assert replay_id == board_id
    listed_ids = [item["board_id"] for item in client.get("/api/v1/analytics/competition/boards").json()["items"]]
    assert listed_ids.count(board_id) == 1


def test_diagnosis_http_marks_connected_and_refuses_empty_patch(tmp_path):
    app = _app_t05(tmp_path)
    client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    caps = client.post(
        "/api/v1/analytics/competition/diagnosis/capabilities",
        json={"request_id": "req_diag_caps"},
    )
    assert caps.status_code == 200, caps.text
    body = caps.json()
    assert body["live_transport"] == "HTTP_CONNECTED"
    assert body["http_api"] == "CONNECTED"
    assert "diag.gsv" in body["capability_ids"] or any(
        item.get("capability_id") == "diag.gsv" for item in body.get("capabilities") or []
    )
    results = client.get("/api/v1/analytics/competition/results")
    assert results.status_code == 200
    assert results.json()["http_api"] == "CONNECTED"
    patch = client.post(
        "/api/v1/analytics/competition/diagnosis/patch",
        json={"intent": "STYLE_ONLY", "request_id": "req_diag_patch"},
    )
    assert patch.status_code in {400, 422}


def test_cancellation_is_scoped_to_authenticated_actor(tmp_path):
    app, _ = _app(tmp_path)
    alice = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    bob = TestClient(app, headers={"Authorization": "Bearer bob-independent-synthetic-token-32chars"})
    base = "/api/v1/analytics/competition"
    assert alice.post(f"{base}/attempts/shared_attempt/cancel").status_code == 200
    payload = {"attempt_id": "shared_attempt", "base_version": 1}
    alice_result = alice.post(f"{base}/boards/board_missing/versions", json=payload)
    bob_result = bob.post(f"{base}/boards/board_missing/versions", json=payload)
    assert alice_result.json()["error"]["code"] == "CANCELLED"
    assert bob_result.status_code >= 400
    assert bob_result.json()["error"]["code"] != "CANCELLED"
    assert alice.post(f"{base}/batches/shared_batch/cancel").status_code == 200
    for client, cancelled in [(alice, True), (bob, False)]:
        result = client.post(f"{base}/batches", json={"batch_id": "shared_batch"})
        assert result.status_code >= 400
        assert (result.json()["error"]["code"] == "CANCELLED") is cancelled


def test_synthetic_browser_origin_is_explicit_and_isolated(monkeypatch):
    import runpy

    module = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/competition-synth-http.py"))
    origin = module["web_origin"]
    monkeypatch.delenv("COMPETITION_SYNTH_WEB_ORIGIN", raising=False)
    assert origin() == "http://127.0.0.1:14327"
    monkeypatch.setenv("COMPETITION_SYNTH_WEB_ORIGIN", "http://127.0.0.1:4329")
    assert origin() == "http://127.0.0.1:4329"
    import pytest

    for value in ("*", "https://example.com", "http://127.0.0.1:4327", "http://127.0.0.1:8000", "http://127.0.0.1:5173"):
        monkeypatch.setenv("COMPETITION_SYNTH_WEB_ORIGIN", value)
        with pytest.raises(ValueError, match="isolated loopback"):
            origin()
