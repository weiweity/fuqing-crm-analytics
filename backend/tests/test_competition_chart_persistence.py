"""Runtime chart preferences use the same durable, authorized board versions."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.tests.test_competition_http_wiring import TOKEN, _app
from backend.tests.test_competition_review_regressions import BASE, seeded


def chart_case(tmp_path):
    client, batch = seeded(tmp_path)
    board = client.post(BASE + "/batches", json=batch).json()["board"]
    path = f"{BASE}/boards/{board['board_id']}"
    patch = {"schema_version": "competition-board-chart-patch/v1",
             "board_id": board["board_id"], "block_id": board["block_ids"][0],
             "base_version": board["version"], "attempt_id": "attempt_chart",
             "idempotency_key": "chart-one", "intent": "STYLE_ONLY", "chart_type": "BAR"}
    return client, path, patch


def test_chart_preview_save_retry_and_new_app_reopen(tmp_path):
    client, path, patch = chart_case(tmp_path)
    original = client.get(path).json()["blocks"][0]
    preview = client.post(path + "/preview", json=patch)
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocks"][0]["plugin"] == "BAR"
    assert client.get(path).json()["spec"]["version"] == 1
    saved = client.post(path + "/versions", json=patch)
    assert saved.status_code == 200, saved.text
    assert saved.json()["spec"]["version"] == 2
    assert client.post(path + "/versions", json=patch).json() == saved.json()
    app, _ = _app(tmp_path)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        actual = reopened.get(path).json()
    assert actual["spec"]["version"] == 2
    assert actual["blocks"][0]["plugin"] == "BAR"
    for field in ("analysis_ref", "result", "layout", "evidence_digest", "display_overrides"):
        assert actual["blocks"][0][field] == original[field]
    changed = {**patch, "chart_type": "LINE"}
    assert client.post(path + "/versions", json=changed).status_code == 409
    stale = {**changed, "attempt_id": "attempt_stale", "idempotency_key": "chart-stale"}
    assert client.post(path + "/versions", json=stale).status_code == 409


@pytest.mark.parametrize("change", [
    {"chart_type": "SCRIPT"}, {"block_id": None}, {"block_id": "block_missing"},
    {"intent": "FILTER_CHANGE"}, {"filter_change": {}}, {"base_version": True},
])
def test_chart_rejects_invalid_or_untargeted_patch_without_writing(tmp_path, change):
    client, path, patch = chart_case(tmp_path)
    assert client.post(path + "/versions", json={**patch, **change}).status_code == 422
    assert client.get(path).json()["spec"]["version"] == 1


def test_chart_rechecks_access_and_honors_durable_cancellation(tmp_path):
    client, path, patch = chart_case(tmp_path)
    denied = client.post(path + "/versions", json=patch,
                         headers={"Authorization": "Bearer bob-independent-synthetic-token-32chars"})
    assert denied.status_code in {403, 404}
    assert client.post(BASE + "/attempts/attempt_chart/cancel").status_code == 200
    assert client.post(path + "/versions", json=deepcopy(patch)).status_code == 409
    assert client.get(path).json()["spec"]["version"] == 1
