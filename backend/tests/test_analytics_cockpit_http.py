"""Cockpit HTTP: trusted saved-analysis SNAPSHOT, ACL, preview, versions."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.analytics_analysis_app import PREFIX as ANALYSIS_PREFIX
from backend.analytics_analysis_app import create_analysis_app
from backend.analytics_cockpit_app import PREFIX, create_cockpit_app
from backend.contracts.analytics import AnalyticsErrorResponse
from backend.contracts.analytics_cockpit import AnalyticsDashboard, HTTP_API_CONNECTED
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.cockpit import CockpitStore
from backend.services.analytics.saved_analyses import SavedAnalysisStore
from backend.tests.test_analytics_analysis_http import analysis_counts, inventory, succeed_query
from backend.tests.test_analytics_cockpit import make_store as make_cockpit_store
from backend.tests.test_analytics_saved_analyses import make_store as make_analysis_store

TOKEN = "a" * 40
OTHER = "b" * 40
READER = "c" * 40


def cockpit_actor(name="alice", *, capabilities=None):
    return AnalyticsPrincipal(
        name,
        frozenset(
            {"run:read", "analysis:save", "analysis:read", "dashboard:read", "dashboard:update"}
            if capabilities is None else capabilities
        ),
        frozenset({"channel-followup-fixture"}),
    )


def headers(token=TOKEN, key=None, etag=None):
    values = {"authorization": f"Bearer {token}"}
    if key is not None:
        values["idempotency-key"] = key
    if etag is not None:
        values["if-match"] = str(etag)
    return values


def cockpit_counts(store: CockpitStore):
    with closing(sqlite3.connect(store.path)) as con:
        return {
            "dashboards": con.execute("SELECT count(*) FROM dashboards").fetchone()[0],
            "owners": con.execute("SELECT count(*) FROM owners").fetchone()[0],
            "idempotency": con.execute("SELECT count(*) FROM idempotency").fetchone()[0],
        }


def save_analysis(tmp_path, days, title, key):
    root = tmp_path / f"query-{days}-{key}"
    root.mkdir()
    run_store, run_id, _intent = succeed_query(root, days=days)
    analyses = make_analysis_store(tmp_path / "analyses")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, cockpit_actor())
    client = TestClient(create_analysis_app(run_store, analyses, registry))
    created = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run_id, "title": title}, headers=headers(key=key),
    )
    assert created.status_code == 201, created.text
    return run_store, analyses, created.json()


def make_clients(tmp_path, run_store, analyses, **grants):
    boards = make_cockpit_store(tmp_path / "cockpit")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, cockpit_actor())
    registry.grant(OTHER, cockpit_actor("bob"))
    registry.grant(READER, cockpit_actor(capabilities={"dashboard:read", "analysis:read"}))
    for token, principal in grants.items():
        registry.grant(token, principal)
    analysis_http = TestClient(create_analysis_app(run_store, analyses, registry))
    cockpit_http = TestClient(create_cockpit_app(analyses, boards, registry))
    return cockpit_http, boards, analysis_http, registry


def test_unconfigured_app_fail_closed_and_openapi_is_offline():
    app = create_cockpit_app()
    schema = app.openapi()
    assert schema["x-cockpit-http"] is True
    assert schema["x-query-session-fence"] is False
    assert schema["x-saved-analysis-http"] is False
    assert "200" in schema["paths"][PREFIX]["post"]["responses"]
    assert "201" in schema["paths"][PREFIX]["post"]["responses"]
    assert PREFIX in schema["paths"]
    assert "/api/v1/analytics/analyses" not in schema["paths"]
    assert "/api/v1/analytics-query/runs/{run_id}" not in schema["paths"]
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, cockpit_actor())
    listed = TestClient(create_cockpit_app(identities=registry)).get(PREFIX, headers=headers())
    assert listed.status_code == 503
    assert listed.json()["error"]["code"] == "COCKPIT_NOT_CONFIGURED"


def test_worker_source_save_add_reopen_sessionless_read(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日快照", "a30")
    before = inventory(run_store)
    client, boards, _analysis_http, _registry = make_clients(tmp_path, run_store, analyses)
    empty = client.get(PREFIX, headers=headers())
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    created = client.post(PREFIX, json={"title": "我的驾驶舱"}, headers=headers(key="board-1"))
    assert created.status_code == 201, created.text
    AnalyticsDashboard.model_validate(created.json())
    replay = client.post(PREFIX, json={"title": "我的驾驶舱"}, headers=headers(key="board-1"))
    assert replay.status_code == 201
    assert replay.json()["dashboard_id"] == created.json()["dashboard_id"]
    existing = client.post(PREFIX, json={"title": "我的驾驶舱"}, headers=headers(key="board-2"))
    assert existing.status_code == 200
    AnalyticsDashboard.model_validate(existing.json())
    dashboard_id = created.json()["dashboard_id"]
    assert created.json()["http_api"] == HTTP_API_CONNECTED
    assert created.json()["cards"] == []
    assert boards.get(cockpit_actor(), dashboard_id).as_dict()["http_api"] == "NOT_CONNECTED"
    added = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-1", etag=1),
    )
    assert added.status_code == 201, added.text
    card = added.json()["cards"][0]
    assert card["source_status"] == "OK"
    assert card["facts"]["observation_days"] == 30
    assert card["snapshot"]["run_id"] == saved["created_from_run_id"]
    assert card["analysis_ref"]["version"] == 1
    assert "facts" not in {"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}}
    boards.close()
    reopened = CockpitStore(tmp_path / "cockpit")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, cockpit_actor())
    fresh = TestClient(create_cockpit_app(analyses, reopened, registry, runtime_ready=lambda: False))
    fetched = fresh.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert fetched.status_code == 200
    assert "x-runtime-session-id" not in fetched.request.headers
    assert fetched.json()["cards"][0]["snapshot"] == card["snapshot"]
    assert fetched.json()["http_api"] == HTTP_API_CONNECTED
    listed = fresh.get(PREFIX, headers=headers())
    assert listed.json()["items"][0]["dashboard_id"] == dashboard_id
    assert inventory(run_store) == before


def test_two_saved_windows_stay_isolated_across_copy_layout_remove_undo(tmp_path):
    (tmp_path / "q30").mkdir()
    (tmp_path / "q60").mkdir()
    run_30, id_30, _intent_30 = succeed_query(tmp_path / "q30", days=30)
    run_60, id_60, _intent_60 = succeed_query(tmp_path / "q60", days=60)
    shared = make_analysis_store(tmp_path / "analyses")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, cockpit_actor())
    c30 = TestClient(create_analysis_app(run_30, shared, registry))
    c60 = TestClient(create_analysis_app(run_60, shared, registry))
    a30 = c30.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": id_30, "title": "30 日"},
        headers=headers(key="share-30"),
    )
    a60 = c60.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": id_60, "title": "60 日"},
        headers=headers(key="share-60"),
    )
    assert a30.status_code == 201 and a60.status_code == 201, (a30.text, a60.text)
    client, boards, analysis_http, _reg = make_clients(tmp_path, run_30, shared)
    board = client.post(PREFIX, json={}, headers=headers(key="board")).json()
    dashboard_id = board["dashboard_id"]
    first = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": a30.json()["analysis_id"], "version": 1}},
        headers=headers(key="add-30", etag=1),
    )
    second = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": a60.json()["analysis_id"], "version": 1}},
        headers=headers(key="add-60", etag=2),
    )
    assert first.status_code == 201 and second.status_code == 201
    cards = second.json()["cards"]
    assert [card["facts"]["observation_days"] for card in cards] == [30, 60]
    card_30, card_60 = cards
    copied = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(key="copy-30", etag=3),
    )
    assert copied.status_code == 201
    clone = next(card for card in copied.json()["cards"] if card["card_id"] not in {card_30["card_id"], card_60["card_id"]})
    assert clone["facts"]["observation_days"] == 30
    assert clone["snapshot"]["run_id"] == card_30["snapshot"]["run_id"]
    assert clone["card_id"] != card_30["card_id"]
    moved = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "layout", "card_id": card_60["card_id"], "layout": {"x": 0, "y": 8, "w": 12, "h": 4}},
        headers=headers(key="lay-60", etag=4),
    )
    target = next(card for card in moved.json()["cards"] if card["card_id"] == card_60["card_id"])
    assert target["layout"] == {"x": 0, "y": 8, "w": 12, "h": 4}
    assert target["facts"]["observation_days"] == 60
    titled = analysis_http.post(
        f"{ANALYSIS_PREFIX}/{a30.json()['analysis_id']}/versions",
        json={"title": "改过的 30 日标题"},
        headers=headers(key="title-30", etag=1),
    )
    assert titled.status_code == 201
    latest = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    pinned = next(card for card in latest.json()["cards"] if card["card_id"] == card_30["card_id"])
    assert pinned["analysis_ref"]["version"] == 1
    assert pinned["facts"]["observation_days"] == 30
    tall = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "layout", "card_id": card_60["card_id"], "layout": {"x": 0, "y": 241, "w": 12, "h": 4}},
        headers=headers(key="lay-tall", etag=latest.json()["version"]),
    )
    assert tall.status_code == 422
    assert client.get(f"{PREFIX}/{dashboard_id}", headers=headers()).json()["cards"]
    removed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": clone["card_id"]},
        headers=headers(key="rm-clone", etag=5),
    )
    assert [card["card_id"] for card in removed.json()["cards"]] == [card_30["card_id"], card_60["card_id"]]
    undone = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "undo", "scope": "board", "restore_from_version": 4},
        headers=headers(key="undo-4", etag=6),
    )
    assert undone.status_code == 201
    assert undone.json()["version"] == 7
    assert len(undone.json()["cards"]) == 3
    days = {card["card_id"]: card["facts"]["observation_days"] for card in undone.json()["cards"]}
    assert days[card_30["card_id"]] == 30
    assert days[card_60["card_id"]] == 60
    assert days[clone["card_id"]] == 30
    assert cockpit_counts(boards)["dashboards"] == 7


def test_forged_snapshot_and_partial_revoke_are_rejected(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日", "a30")
    client, _boards, _analysis_http, registry = make_clients(tmp_path, run_store, analyses)
    board = client.post(PREFIX, json={}, headers=headers(key="board")).json()
    dashboard_id = board["dashboard_id"]
    forged = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={
            "op": "add",
            "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1},
            "facts": saved["facts"],
            "snapshot": saved["snapshot"],
            "owner_id": "eve",
        },
        headers=headers(key="forge", etag=1),
    )
    assert forged.status_code == 422
    missing_version = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"]}},
        headers=headers(key="no-ver", etag=1),
    )
    assert missing_version.status_code == 422
    bob = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(OTHER, key="bob", etag=1),
    )
    assert bob.status_code == 404
    added = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-ok", etag=1),
    )
    assert added.status_code == 201
    registry.grant(TOKEN, cockpit_actor(capabilities={"dashboard:read", "dashboard:update"}))
    fetched = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["cards"][0]["source_status"] == "UNAVAILABLE"
    assert "facts" not in fetched.json()["cards"][0]
    assert "snapshot" not in fetched.json()["cards"][0]
    replay = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-ok", etag=1),
    )
    assert replay.status_code == 403
    assert "facts" not in replay.json()
    denied = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-after-revoke", etag=2),
    )
    assert denied.status_code == 403
    assert "facts" not in denied.json()


def test_preview_does_not_write_and_failed_save_keeps_config(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日", "a30")
    before_runs = inventory(run_store)
    client, boards, _analysis_http, _registry = make_clients(tmp_path, run_store, analyses)
    board = client.post(PREFIX, json={}, headers=headers(key="board")).json()
    dashboard_id = board["dashboard_id"]
    before = cockpit_counts(boards)
    preview = client.post(
        f"{PREFIX}/{dashboard_id}/preview",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(etag=1),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["preview"] is True
    assert preview.json()["persisted"] is False
    assert preview.json()["base_version"] == 1
    assert preview.json()["version"] == 1
    assert preview.json()["cards"][0]["card_id"].startswith("preview_")
    assert cockpit_counts(boards) == before
    assert inventory(run_store) == before_runs
    with patch.object(
        boards, "apply", side_effect=AnalyticsError(503, "STATE_UNAVAILABLE", "驾驶舱状态暂不可用。", retryable=True),
    ):
        failed = client.post(
            f"{PREFIX}/{dashboard_id}/versions",
            json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
            headers=headers(key="save-fail", etag=1),
        )
    assert failed.status_code == 503
    assert cockpit_counts(boards) == before
    saved_add = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="save-ok", etag=1),
    )
    assert saved_add.status_code == 201
    stale = client.post(
        f"{PREFIX}/{dashboard_id}/preview",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(etag=1),
    )
    assert stale.status_code == 200
    stale_save = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "layout", "card_id": saved_add.json()["cards"][0]["card_id"],
              "layout": {"x": 0, "y": 0, "w": 8, "h": 4}},
        headers=headers(key="stale", etag=1),
    )
    assert stale_save.status_code == 409
    current = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert current.json()["version"] == 2
    assert current.json()["cards"][0]["layout"] == saved_add.json()["cards"][0]["layout"]


def test_idempotency_conflict_and_concurrent_same_key(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日", "a30")
    client, boards, _analysis_http, _registry = make_clients(tmp_path, run_store, analyses)
    dashboard_id = client.post(PREFIX, json={}, headers=headers(key="board")).json()["dashboard_id"]
    body = {"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}}
    first = client.post(f"{PREFIX}/{dashboard_id}/versions", json=body, headers=headers(key="same", etag=1))
    assert first.status_code == 201
    replay = client.post(f"{PREFIX}/{dashboard_id}/versions", json=body, headers=headers(key="same", etag=1))
    assert replay.status_code == 201
    assert replay.json()["cards"][0]["card_id"] == first.json()["cards"][0]["card_id"]
    changed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": first.json()["cards"][0]["card_id"]},
        headers=headers(key="same", etag=1),
    )
    assert changed.status_code == 409
    missing = client.post(f"{PREFIX}/{dashboard_id}/versions", json=body, headers=headers(etag=1))
    assert missing.status_code == 428

    def once():
        row = None
        for _ in range(8):
            row = client.post(
                f"{PREFIX}/{dashboard_id}/versions", json=body, headers=headers(key="parallel", etag=2),
            )
            if row.status_code != 503:
                return row
        return row

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: once(), range(2)))
    assert {row.status_code for row in results} == {201}
    assert results[0].json()["cards"][0]["card_id"] == results[1].json()["cards"][0]["card_id"]
    with closing(sqlite3.connect(boards.path)) as con:
        assert con.execute("SELECT count(*) FROM dashboards").fetchone()[0] == 3


def test_one_unavailable_card_does_not_block_remove(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日", "a30")
    (tmp_path / "q60").mkdir()
    other_store, other_run, _intent = succeed_query(tmp_path / "q60", days=60)
    client, boards, analysis_http, registry = make_clients(tmp_path, run_store, analyses)
    other_http = TestClient(create_analysis_app(other_store, analyses, registry))
    other = other_http.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": other_run, "title": "60 日"}, headers=headers(key="a60"),
    )
    assert other.status_code == 201, other.text
    dashboard_id = client.post(PREFIX, json={}, headers=headers(key="board")).json()["dashboard_id"]
    first = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-30", etag=1),
    )
    second = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": other.json()["analysis_id"], "version": 1}},
        headers=headers(key="add-60", etag=2),
    )
    assert first.status_code == 201 and second.status_code == 201
    with closing(sqlite3.connect(analyses.path)) as con:
        con.execute(
            "UPDATE analyses SET snapshot_json=? WHERE analysis_id=?",
            (json.dumps({"broken": True}), saved["analysis_id"]),
        )
        con.commit()
    fetched = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    cards = {card["analysis_ref"]["analysis_id"]: card for card in fetched.json()["cards"]}
    broken = cards[saved["analysis_id"]]
    healthy = cards[other.json()["analysis_id"]]
    assert broken["source_status"] == "UNAVAILABLE"
    assert "facts" not in broken
    assert healthy["source_status"] == "OK"
    assert healthy["facts"]["observation_days"] == 60
    before_copy = cockpit_counts(boards)
    copied = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": broken["card_id"]},
        headers=headers(key="copy-broken", etag=3),
    )
    assert copied.status_code in (403, 404, 409, 422)
    assert "facts" not in copied.json()
    assert cockpit_counts(boards) == before_copy
    removed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": broken["card_id"]},
        headers=headers(key="rm-broken", etag=3),
    )
    assert removed.status_code == 201
    remaining = removed.json()["cards"]
    assert all(card["card_id"] != broken["card_id"] for card in remaining)
    assert any(card["source_status"] == "OK" and card["facts"]["observation_days"] == 60 for card in remaining)


def test_read_without_run_store_and_undo_cannot_restore_revoked_facts(tmp_path):
    run_store, analyses, saved = save_analysis(tmp_path, 30, "30 日", "a30")
    client, boards, _analysis_http, registry = make_clients(tmp_path, run_store, analyses)
    dashboard_id = client.post(PREFIX, json={}, headers=headers(key="board")).json()["dashboard_id"]
    added = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}},
        headers=headers(key="add-1", etag=1),
    )
    assert added.status_code == 201
    card_id = added.json()["cards"][0]["card_id"]
    client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": card_id},
        headers=headers(key="rm-1", etag=2),
    )
    registry.grant(TOKEN, cockpit_actor(capabilities={"dashboard:read", "dashboard:update"}))
    before_undo = cockpit_counts(boards)
    undone = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "undo", "scope": "board", "restore_from_version": 2},
        headers=headers(key="undo-revoked", etag=3),
    )
    assert undone.status_code == 403
    assert "facts" not in undone.json()
    assert cockpit_counts(boards) == before_undo
    registry.grant(TOKEN, cockpit_actor())
    restored = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "undo", "scope": "board", "restore_from_version": 2},
        headers=headers(key="undo-ok", etag=3),
    )
    assert restored.status_code == 201
    assert restored.json()["cards"][0]["source_status"] == "OK"
    assert restored.json()["cards"][0]["facts"]["observation_days"] == 30
    boards.close()
    fresh = TestClient(create_cockpit_app(SavedAnalysisStore(tmp_path / "analyses"), CockpitStore(tmp_path / "cockpit"), registry, runtime_ready=lambda: False))
    listed = fresh.get(PREFIX, headers=headers())
    assert listed.status_code == 200
    fetched = fresh.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 4
    assert fetched.json()["cards"][0]["facts"]["observation_days"] == 30


def _write_latest_cards(store, dashboard_id, cards):
    with closing(sqlite3.connect(store.path)) as con:
        version = con.execute(
            "SELECT MAX(version) FROM dashboards WHERE dashboard_id=?", (dashboard_id,),
        ).fetchone()[0]
        con.execute(
            "UPDATE dashboards SET cards_json=? WHERE dashboard_id=? AND version=?",
            (json.dumps(cards), dashboard_id, version),
        )
        con.commit()
        return version


def _latest_cards(store, dashboard_id):
    with closing(sqlite3.connect(store.path)) as con:
        row = con.execute(
            "SELECT cards_json FROM dashboards WHERE dashboard_id=? ORDER BY version DESC LIMIT 1",
            (dashboard_id,),
        ).fetchone()
        return json.loads(row[0])


def _two_saved_cards(tmp_path):
    run_store, analyses, saved_30 = save_analysis(tmp_path, 30, "30 日", "a30")
    (tmp_path / "q60").mkdir()
    other_store, other_run, _intent = succeed_query(tmp_path / "q60", days=60)
    client, boards, _analysis_http, registry = make_clients(tmp_path, run_store, analyses)
    other_http = TestClient(create_analysis_app(other_store, analyses, registry))
    saved_60 = other_http.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": other_run, "title": "60 日"}, headers=headers(key="a60"),
    )
    assert saved_60.status_code == 201, saved_60.text
    dashboard_id = client.post(PREFIX, json={}, headers=headers(key="board")).json()["dashboard_id"]
    first = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved_30["analysis_id"], "version": 1}},
        headers=headers(key="add-30", etag=1),
    )
    second = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": saved_60.json()["analysis_id"], "version": 1}},
        headers=headers(key="add-60", etag=2),
    )
    assert first.status_code == 201 and second.status_code == 201
    cards = second.json()["cards"]
    card_30 = next(card for card in cards if card["facts"]["observation_days"] == 30)
    card_60 = next(card for card in cards if card["facts"]["observation_days"] == 60)
    return client, boards, analyses, registry, dashboard_id, card_30, card_60, saved_30


def test_cached_facts_drift_and_source_corruption_degrade_only_that_card(tmp_path):
    client, boards, analyses, _registry, dashboard_id, card_30, card_60, saved = _two_saved_cards(tmp_path)
    original = _latest_cards(boards, dashboard_id)

    def get_after(mutate):
        cards = json.loads(json.dumps(original))
        mutate(cards[0])
        _write_latest_cards(boards, dashboard_id, cards)
        row = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
        assert row.status_code == 200, row.text
        document = AnalyticsDashboard.model_validate(row.json())
        first, second = document.cards
        _write_latest_cards(boards, dashboard_id, original)
        return first.model_dump(mode="json"), second.model_dump(mode="json")

    drifted, healthy = get_after(lambda card: card["facts"].update(observation_days=60))
    assert drifted["source_status"] == "UNAVAILABLE"
    assert "facts" not in drifted
    assert "snapshot" not in drifted
    assert healthy["source_status"] == "OK"
    assert healthy["facts"]["observation_days"] == 60

    broken_facts, healthy = get_after(lambda card: card.update(facts={"broken": True}))
    assert broken_facts["source_status"] == "UNAVAILABLE"
    assert "facts" not in broken_facts
    assert healthy["source_status"] == "OK"

    with closing(sqlite3.connect(analyses.path)) as con:
        original_facts = con.execute(
            "SELECT facts_json FROM analyses WHERE analysis_id=?", (saved["analysis_id"],),
        ).fetchone()[0]
        con.execute(
            "UPDATE analyses SET facts_json=? WHERE analysis_id=?",
            (json.dumps({"broken": True}), saved["analysis_id"]),
        )
        con.commit()
    row = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert row.status_code == 200
    document = AnalyticsDashboard.model_validate(row.json())
    assert document.cards[0].source_status == "UNAVAILABLE"
    assert document.cards[1].source_status == "OK"
    assert document.cards[1].facts.observation_days == 60
    with closing(sqlite3.connect(analyses.path)) as con:
        con.execute("UPDATE analyses SET facts_json=? WHERE analysis_id=?", (original_facts, saved["analysis_id"]))
        con.commit()

    with closing(sqlite3.connect(analyses.path)) as con:
        original_version = con.execute(
            "SELECT data_version FROM analyses WHERE analysis_id=?", (saved["analysis_id"],),
        ).fetchone()[0]
        con.execute("UPDATE analyses SET data_version=? WHERE analysis_id=?", ("unknown/v9", saved["analysis_id"]))
        con.commit()
    row = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert row.status_code == 200
    document = AnalyticsDashboard.model_validate(row.json())
    assert document.cards[0].source_status == "UNAVAILABLE"
    assert document.cards[1].source_status == "OK"
    with closing(sqlite3.connect(analyses.path)) as con:
        con.execute("UPDATE analyses SET data_version=? WHERE analysis_id=?", (original_version, saved["analysis_id"]))
        con.commit()

    with closing(sqlite3.connect(analyses.path)) as con:
        original_snapshot = con.execute(
            "SELECT snapshot_json FROM analyses WHERE analysis_id=?", (saved["analysis_id"],),
        ).fetchone()[0]
        snapshot = json.loads(original_snapshot)
        snapshot["run_id"] = "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        con.execute("UPDATE analyses SET snapshot_json=? WHERE analysis_id=?", (json.dumps(snapshot), saved["analysis_id"]))
        con.commit()
    row = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
    assert row.status_code == 200
    document = AnalyticsDashboard.model_validate(row.json())
    assert document.cards[0].source_status == "UNAVAILABLE"
    assert "facts" not in document.cards[0].model_dump(mode="json")
    assert document.cards[1].source_status == "OK"


def test_corrupt_card_shape_does_not_500_the_board(tmp_path):
    client, boards, _analyses, _registry, dashboard_id, card_30, card_60, _saved = _two_saved_cards(tmp_path)
    original = _latest_cards(boards, dashboard_id)

    def get_case(mutate):
        cards = json.loads(json.dumps(original))
        mutate(cards[0])
        _write_latest_cards(boards, dashboard_id, cards)
        row = client.get(f"{PREFIX}/{dashboard_id}", headers=headers())
        assert row.status_code == 200, row.text
        document = AnalyticsDashboard.model_validate(row.json())
        first, second = document.model_dump(mode="json")["cards"]
        _write_latest_cards(boards, dashboard_id, original)
        return first, second

    first, second = get_case(lambda card: card["analysis_ref"].update(version="broken"))
    assert first["source_status"] == "UNAVAILABLE"
    assert first["analysis_ref"] is None
    assert "facts" not in first
    assert second["source_status"] == "OK"
    assert second["facts"]["observation_days"] == 60

    first, second = get_case(lambda card: card["plugin_ref"].update(version="analytics-visual-table/v999"))
    assert first["source_status"] == "UNAVAILABLE"
    assert first.get("plugin_ref") is None
    assert second["source_status"] == "OK"

    first, second = get_case(lambda card: card.update(facts={"broken": True}))
    assert first["source_status"] == "UNAVAILABLE"
    assert "facts" not in first
    assert second["source_status"] == "OK"

    first, second = get_case(lambda card: card.update(layout={"x": "bad"}))
    assert first["source_status"] == "UNAVAILABLE"
    assert first["layout"] == {"x": 0, "y": 0, "w": 6, "h": 4}
    assert second["source_status"] == "OK"

    first, _second = get_case(lambda card: card["analysis_ref"].update(version="broken"))
    removed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": card_30["card_id"]},
        headers=headers(key="rm-shape", etag=3),
    )
    assert removed.status_code == 201, removed.text
    remaining = AnalyticsDashboard.model_validate(removed.json())
    assert remaining.version == 4
    assert [card.card_id for card in remaining.cards] == [card_60["card_id"]]
    assert remaining.cards[0].source_status == "OK"


def test_copy_and_undo_require_visible_sources_before_write(tmp_path):
    client, boards, analyses, registry, dashboard_id, card_30, card_60, saved = _two_saved_cards(tmp_path)
    before = cockpit_counts(boards)
    registry.grant(TOKEN, cockpit_actor(capabilities={"dashboard:read", "dashboard:update"}))
    preview_copy = client.post(
        f"{PREFIX}/{dashboard_id}/preview",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(etag=3),
    )
    assert preview_copy.status_code == 403
    assert cockpit_counts(boards) == before
    copied = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(key="copy-revoked", etag=3),
    )
    assert copied.status_code == 403
    assert "facts" not in copied.json()
    assert cockpit_counts(boards) == before
    replay = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(key="copy-revoked", etag=3),
    )
    assert replay.status_code == 403
    assert cockpit_counts(boards) == before
    registry.grant(TOKEN, cockpit_actor(name="alice", capabilities={"dashboard:read", "dashboard:update", "analysis:read", "analysis:save", "run:read"}))
    registry.grant(TOKEN, AnalyticsPrincipal("alice", cockpit_actor().capabilities, frozenset()))
    scoped = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(key="copy-scope", etag=3),
    )
    assert scoped.status_code == 403
    assert cockpit_counts(boards) == before
    registry.grant(TOKEN, cockpit_actor())
    with closing(sqlite3.connect(analyses.path)) as con:
        con.execute(
            "UPDATE analyses SET snapshot_json=? WHERE analysis_id=?",
            (json.dumps({"broken": True}), saved["analysis_id"]),
        )
        con.commit()
    damaged = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_30["card_id"]},
        headers=headers(key="copy-damaged", etag=3),
    )
    assert damaged.status_code in (409, 422)
    assert cockpit_counts(boards) == before
    removed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": card_30["card_id"]},
        headers=headers(key="rm-keep", etag=3),
    )
    assert removed.status_code == 201
    after_remove = cockpit_counts(boards)
    registry.grant(TOKEN, cockpit_actor(capabilities={"dashboard:read", "dashboard:update"}))
    preview_undo = client.post(
        f"{PREFIX}/{dashboard_id}/preview",
        json={"op": "undo", "scope": "board", "restore_from_version": 3},
        headers=headers(etag=4),
    )
    assert preview_undo.status_code in (403, 409, 422)
    assert cockpit_counts(boards) == after_remove
    undone = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "undo", "scope": "board", "restore_from_version": 3},
        headers=headers(key="undo-revoked-new", etag=4),
    )
    assert undone.status_code in (403, 409, 422)
    assert cockpit_counts(boards) == after_remove
    registry.grant(TOKEN, cockpit_actor())
    copied_ok = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "copy", "card_id": card_60["card_id"]},
        headers=headers(key="copy-60", etag=4),
    )
    assert copied_ok.status_code == 201
    days = {card["card_id"]: card["facts"]["observation_days"] for card in copied_ok.json()["cards"] if card["source_status"] == "OK"}
    assert 60 in days.values()
    assert 30 not in days.values()


_SOURCE_JSON_COLUMNS = frozenset({"request_json", "snapshot_json", "facts_json"})


def _read_source_json(store, analysis_id):
    with closing(sqlite3.connect(store.path)) as con:
        row = con.execute(
            "SELECT request_json, snapshot_json, facts_json FROM analyses WHERE analysis_id=?",
            (analysis_id,),
        ).fetchone()
        return {"request_json": row[0], "snapshot_json": row[1], "facts_json": row[2]}


def _write_source_json(store, analysis_id, column, value):
    assert column in _SOURCE_JSON_COLUMNS
    with closing(sqlite3.connect(store.path)) as con:
        con.execute(f"UPDATE analyses SET {column}=? WHERE analysis_id=?", (value, analysis_id))
        con.commit()


def _logic_counts(boards, analyses, tmp_path):
    runs = {"runs": 0, "workers": 0, "steps": 0}
    for path in tmp_path.rglob("*.sqlite3"):
        with closing(sqlite3.connect(path)) as con:
            tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "worker_executions" in tables:
                runs["runs"] += con.execute("SELECT count(*) FROM runs").fetchone()[0]
                runs["workers"] += con.execute("SELECT count(*) FROM worker_executions").fetchone()[0]
                runs["steps"] += con.execute("SELECT count(*) FROM steps").fetchone()[0]
    return {"cockpit": cockpit_counts(boards), "analyses": analysis_counts(analyses), "runs": runs}


def _source_ops(saved, card_30):
    add = {"op": "add", "analysis_ref": {"analysis_id": saved["analysis_id"], "version": 1}}
    copy = {"op": "copy", "card_id": card_30["card_id"]}
    undo = {"op": "undo", "scope": "board", "restore_from_version": 2}
    return (
        ("add", "preview", add, None),
        ("add", "versions", add, "src-add"),
        ("copy", "preview", copy, None),
        ("copy", "versions", copy, "src-copy"),
        ("undo", "preview", undo, None),
        ("undo", "versions", undo, "src-undo"),
    )


def _assert_contract_error(row, *, codes, statuses=(409, 422)):
    assert row.status_code in statuses, row.text
    envelope = AnalyticsErrorResponse.model_validate(row.json())
    assert envelope.error.code in codes
    payload = row.json()
    assert list(payload) == ["error"]
    assert "facts" not in payload
    assert "snapshot" not in payload
    assert "Traceback" not in row.text
    return envelope


def _assert_first_source_unavailable(row, saved):
    assert row.status_code == 200, row.text
    document = AnalyticsDashboard.model_validate(row.json())
    cards = document.model_dump(mode="json")["cards"]
    broken = next(card for card in cards if (card.get("analysis_ref") or {}).get("analysis_id") == saved["analysis_id"])
    healthy = next(card for card in cards if (card.get("analysis_ref") or {}).get("analysis_id") != saved["analysis_id"])
    assert broken["source_status"] == "UNAVAILABLE"
    assert "facts" not in broken
    assert "snapshot" not in broken
    assert healthy["source_status"] == "OK"
    assert healthy["facts"]["observation_days"] == 60
    return document


def _post_op(client, dashboard_id, endpoint, body, key):
    return client.post(
        f"{PREFIX}/{dashboard_id}/{endpoint}",
        json=body,
        headers=headers(key=key, etag=3),
    )


def test_source_request_must_bind_full_resolved_filters(tmp_path):
    client, boards, analyses, _registry, dashboard_id, card_30, card_60, saved = _two_saved_cards(tmp_path)
    url = f"{PREFIX}/{dashboard_id}"
    original = _read_source_json(analyses, saved["analysis_id"])
    before = _logic_counts(boards, analyses, tmp_path)
    request = json.loads(original["request_json"])
    snapshot = json.loads(original["snapshot_json"])
    assert request["channel_ids"] == []
    assert snapshot["resolved_filters"]["channel_ids"] == ["A", "B"]

    fetched = client.get(url, headers=headers())
    assert fetched.status_code == 200
    document = AnalyticsDashboard.model_validate(fetched.json())
    assert [card.source_status for card in document.cards] == ["OK", "OK"]
    assert document.cards[0].snapshot.resolved_filters.channel_ids == ("A", "B")

    for equivalent in ([], ["A", "B"], ["B", "A"]):
        request["channel_ids"] = equivalent
        _write_source_json(analyses, saved["analysis_id"], "request_json", json.dumps(request))
        row = client.get(url, headers=headers())
        assert row.status_code == 200, row.text
        board = AnalyticsDashboard.model_validate(row.json())
        pinned = next(card for card in board.cards if card.analysis_ref.analysis_id == saved["analysis_id"])
        neighbor = next(card for card in board.cards if card.card_id == card_60["card_id"])
        assert pinned.source_status == "OK"
        assert pinned.snapshot.resolved_filters.channel_ids == ("A", "B")
        assert pinned.facts.observation_days == 30
        assert neighbor.source_status == "OK"
        assert neighbor.facts.observation_days == 60

    def reject_binding(mutate_request=None, mutate_snapshot=None, *, code, label):
        if mutate_request is not None:
            payload = json.loads(original["request_json"])
            mutate_request(payload)
            _write_source_json(analyses, saved["analysis_id"], "request_json", json.dumps(payload))
        if mutate_snapshot is not None:
            payload = json.loads(original["snapshot_json"])
            mutate_snapshot(payload)
            _write_source_json(analyses, saved["analysis_id"], "snapshot_json", json.dumps(payload))
        _assert_first_source_unavailable(client.get(url, headers=headers()), saved)
        counts = _logic_counts(boards, analyses, tmp_path)
        for op, endpoint, body, _key in _source_ops(saved, card_30):
            envelope = _assert_contract_error(
                _post_op(client, dashboard_id, endpoint, body, None if endpoint == "preview" else f"{label}-{op}"),
                codes={code},
            )
            assert envelope.error.code == code
        assert _logic_counts(boards, analyses, tmp_path) == counts
        _write_source_json(analyses, saved["analysis_id"], "request_json", original["request_json"])
        _write_source_json(analyses, saved["analysis_id"], "snapshot_json", original["snapshot_json"])

    reject_binding(lambda payload: payload.update(channel_ids=["A"]), code="BINDING_CORRUPT", label="ch")
    reject_binding(lambda payload: payload["cohort_window"].__setitem__("end_date", "2026-08-01"), code="BINDING_CORRUPT", label="win")
    reject_binding(mutate_snapshot=lambda payload: payload.update(as_of="2026-01-01T00:00:00.000000+00:00"), code="BINDING_CORRUPT", label="asof")
    reject_binding(lambda payload: payload.update(query_version="channel-followup-query/v9"), code="UNPROCESSABLE", label="ver")
    assert _logic_counts(boards, analyses, tmp_path) == before
    latest = AnalyticsDashboard.model_validate(client.get(url, headers=headers()).json())
    assert [card.source_status for card in latest.cards] == ["OK", "OK"]
    assert latest.cards[0].facts.observation_days == 30
    assert latest.cards[1].facts.observation_days == 60


@pytest.mark.parametrize("column", ["request_json", "snapshot_json", "facts_json"])
def test_source_json_decode_failures_are_safe_contract_errors(tmp_path, column):
    client, boards, analyses, _registry, dashboard_id, card_30, _card_60, saved = _two_saved_cards(tmp_path)
    original = _read_source_json(analyses, saved["analysis_id"])
    before = _logic_counts(boards, analyses, tmp_path)
    payloads = ("{", "[]", "{}", "null", "1", '{"query_id":"channel_first_observed_followup"}')
    for index, payload in enumerate(payloads):
        _write_source_json(analyses, saved["analysis_id"], column, payload)
        _assert_first_source_unavailable(client.get(f"{PREFIX}/{dashboard_id}", headers=headers()), saved)
        for op, endpoint, body, _key in _source_ops(saved, card_30):
            _assert_contract_error(
                _post_op(
                    client, dashboard_id, endpoint, body,
                    None if endpoint == "preview" else f"dec-{column}-{index}-{op}",
                ),
                codes={"UNPROCESSABLE", "BINDING_CORRUPT"},
            )
        assert _logic_counts(boards, analyses, tmp_path) == before
        _write_source_json(analyses, saved["analysis_id"], column, original[column])


def test_remove_corrupt_source_without_restoring_or_analysis_read(tmp_path):
    client, boards, analyses, registry, dashboard_id, card_30, card_60, saved = _two_saved_cards(tmp_path)
    _write_source_json(analyses, saved["analysis_id"], "request_json", "{")
    _assert_first_source_unavailable(client.get(f"{PREFIX}/{dashboard_id}", headers=headers()), saved)
    registry.grant(TOKEN, cockpit_actor(capabilities={"dashboard:read", "dashboard:update"}))
    assert _read_source_json(analyses, saved["analysis_id"])["request_json"] == "{"
    before = _logic_counts(boards, analyses, tmp_path)
    removed = client.post(
        f"{PREFIX}/{dashboard_id}/versions",
        json={"op": "remove", "card_id": card_30["card_id"]},
        headers=headers(key="rm-still-corrupt", etag=3),
    )
    assert removed.status_code == 201, removed.text
    document = AnalyticsDashboard.model_validate(removed.json())
    assert [card.card_id for card in document.cards] == [card_60["card_id"]]
    after = _logic_counts(boards, analyses, tmp_path)
    assert after["cockpit"]["dashboards"] == before["cockpit"]["dashboards"] + 1
    assert after["cockpit"]["idempotency"] == before["cockpit"]["idempotency"] + 1
    assert after["analyses"] == before["analyses"]
    assert after["runs"] == before["runs"]
    assert _read_source_json(analyses, saved["analysis_id"])["request_json"] == "{"
    registry.grant(TOKEN, cockpit_actor())
    remaining = AnalyticsDashboard.model_validate(client.get(f"{PREFIX}/{dashboard_id}", headers=headers()).json())
    assert [card.card_id for card in remaining.cards] == [card_60["card_id"]]
    assert remaining.cards[0].source_status == "OK"
    assert remaining.cards[0].facts.observation_days == 60
    assert _read_source_json(analyses, saved["analysis_id"])["request_json"] == "{"
