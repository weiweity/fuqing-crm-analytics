"""Query runtime with explicit saved-analysis/cockpit HTTP. No session fence on assets."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

from backend.analytics_runtime import QUERY_CAPABILITIES, runtime_app
from backend.contracts.analytics_analysis import HTTP_API_CONNECTED as ANALYSIS_HTTP
from backend.contracts.analytics_cockpit import AnalyticsDashboard, HTTP_API_CONNECTED
from backend.services.analytics.jobs import ExecutionObservation
from backend.tests.test_analytics_native_runtime import Receiver
from backend.tests.test_analytics_query_runtime import (
    GATEWAY, SESSIONS, accept_and_claim, followup_body, gateway, query_config, runtime, runtime_actor,
    setup_query_app,
)

ASSET_CAPS = ["analysis:save", "analysis:read", "dashboard:read", "dashboard:update"]


def asset_config(tmp_path):
    config = query_config(tmp_path)
    analysis = tmp_path / "analyses"
    cockpit = tmp_path / "cockpit"
    analysis.mkdir(mode=0o700)
    cockpit.mkdir(mode=0o700)
    os.chmod(analysis, 0o700)
    os.chmod(cockpit, 0o700)
    config["analysis_dir"] = str(analysis)
    config["cockpit_dir"] = str(cockpit)
    config["asset_capabilities"] = list(ASSET_CAPS)
    return config


def setup_asset_app(tmp_path):
    app = runtime_app(asset_config(tmp_path), bridge=Receiver())
    app.state.dispatcher.ready = True
    return app


def succeed_run(client, app, session, key, days):
    accepted, intent = accept_and_claim(client, app, session, key)
    executed = client.post(
        "/internal/native/channel-followup", json=followup_body(session, key, f"call-{key}", days), headers=runtime(),
    )
    assert executed.status_code == 200, executed.text
    app.state.store.observe(runtime_actor(), ExecutionObservation(
        intent.run_id, intent.attempt_id, intent.session_id, intent.request_id, True, "SUCCEEDED",
        executed.json()["step_id"],
    ))
    return accepted["run_id"]


def test_query_only_runtime_does_not_gain_asset_routes_or_caps(tmp_path):
    app = setup_query_app(tmp_path)
    client = TestClient(app)
    try:
        principal = app.state.registry.resolve(f"Bearer {GATEWAY}")
        assert principal.capabilities == QUERY_CAPABILITIES
        listed = client.get("/api/v1/analytics/analyses", headers={"authorization": f"Bearer {GATEWAY}"})
        assert listed.status_code == 404
        boards = client.get("/api/v1/analytics/dashboards", headers={"authorization": f"Bearer {GATEWAY}"})
        assert boards.status_code == 404
    finally:
        client.close()


def test_asset_runtime_save_add_preview_without_session_header(tmp_path):
    app = setup_asset_app(tmp_path)
    client = TestClient(app)
    try:
        run_id = succeed_run(client, app, SESSIONS[0], "n30", 30)
        auth = {"authorization": f"Bearer {GATEWAY}"}
        saved = client.post(
            "/api/v1/analytics/analyses",
            json={"created_from_run_id": run_id, "title": "30 日快照"},
            headers={**auth, "idempotency-key": f"save-{run_id}"},
        )
        assert saved.status_code == 201, saved.text
        assert saved.json()["http_api"] == ANALYSIS_HTTP
        analysis_id = saved.json()["analysis_id"]
        created = client.post(
            "/api/v1/analytics/dashboards", json={"title": "我的驾驶舱"},
            headers={**auth, "idempotency-key": "board-1"},
        )
        assert created.status_code == 201, created.text
        dashboard_id = created.json()["dashboard_id"]
        preview = client.post(
            f"/api/v1/analytics/dashboards/{dashboard_id}/preview",
            json={"op": "add", "analysis_ref": {"analysis_id": analysis_id, "version": 1}},
            headers={**auth, "if-match": "1"},
        )
        assert preview.status_code == 200, preview.text
        document = AnalyticsDashboard.model_validate(preview.json())
        assert document.preview is True and document.persisted is False
        with closing(sqlite3.connect(app.state.cockpit_store.path)) as con:
            before = {
                "dashboards": con.execute("SELECT count(*) FROM dashboards").fetchone()[0],
                "idempotency": con.execute("SELECT count(*) FROM idempotency").fetchone()[0],
            }
        added = client.post(
            f"/api/v1/analytics/dashboards/{dashboard_id}/versions",
            json={"op": "add", "analysis_ref": {"analysis_id": analysis_id, "version": 1}},
            headers={**auth, "idempotency-key": f"add-{analysis_id}", "if-match": "1"},
        )
        assert added.status_code == 201, added.text
        board = AnalyticsDashboard.model_validate(added.json())
        assert board.http_api == HTTP_API_CONNECTED
        assert board.cards[0].source_status == "OK"
        assert board.cards[0].facts.observation_days == 30
        with closing(sqlite3.connect(app.state.cockpit_store.path)) as con:
            after = {
                "dashboards": con.execute("SELECT count(*) FROM dashboards").fetchone()[0],
                "idempotency": con.execute("SELECT count(*) FROM idempotency").fetchone()[0],
            }
        assert after["dashboards"] == before["dashboards"] + 1
        fetched = client.get(f"/api/v1/analytics/dashboards/{dashboard_id}", headers=auth)
        assert fetched.status_code == 200
        assert fetched.json()["cards"][0]["facts"]["observation_days"] == 30
        query = client.get(
            f"/api/v1/analytics-query/runs/{run_id}", headers=gateway(SESSIONS[0]),
        )
        assert query.status_code == 200
    finally:
        client.close()
