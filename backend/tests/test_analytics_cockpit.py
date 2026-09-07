"""Private cockpit store: SNAPSHOT cards, preview/save/undo, 409, isolation.

HTTP/OpenAPI is NOT RUN. Snapshot facts come from the handwritten saved-analysis
fixture and are displayed as supplied; this file does not compute metrics.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.cockpit import APPLICATION_ID, CockpitStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DASHBOARD_ID = re.compile(r"^dashboard_[a-f0-9]{32}$")
CARD_ID = re.compile(r"^card_[a-f0-9]{32}$")
CLOCK_MS = 1_800_000_000_000
ANALYSIS_ID = "analysis_" + "a" * 32


def load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def snapshot_bundle() -> dict:
    run = deepcopy(load_json("analytics_saved_analysis_succeeded_run.json")["run"])
    result = run["result"]
    return {
        "analysis_ref": {"analysis_id": ANALYSIS_ID, "version": 1},
        "snapshot": {
            "run_id": run["run_id"],
            "evidence_digest": run["evidence_digest"],
            "resolved_filters": deepcopy(result["resolved_filters"]),
            "data_snapshot_ref": result["data_snapshot_ref"],
            "as_of": result["as_of"],
        },
        "facts": deepcopy(result["facts"]),
        "limitations": list(result["limitations"]),
    }


def b0_payload() -> dict:
    return deepcopy(load_json("analytics_saved_analysis_b0_rejected.json")["run"])


def actor(name="alice", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(
        name,
        frozenset({"dashboard:read", "dashboard:update"} if capabilities is None else capabilities),
        frozenset({"channel-followup-fixture"} if scopes is None else scopes),
    )


def make_store(path: Path, *, clock=lambda: CLOCK_MS) -> CockpitStore:
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return CockpitStore(path, clock=clock)


def add_patch(**changes) -> dict:
    payload = {"op": "add", **snapshot_bundle()}
    payload.update(changes)
    return payload


def seed_board(store: CockpitStore, principal=None, key="create-1") -> dict:
    principal = principal or actor()
    board = store.create(principal, key, {"owner_id": "should-be-ignored", "visibility": "PUBLIC"})
    return board.as_dict()


def test_create_one_private_cockpit_and_ignore_client_owner(tmp_path):
    store = make_store(tmp_path / "cockpit")
    first = seed_board(store)
    replay = store.create(actor(), "create-1", {"title": "我的驾驶舱"}).as_dict()
    second_key = store.create(actor(), "create-2", {"title": "另一个"}).as_dict()
    assert DASHBOARD_ID.fullmatch(first["dashboard_id"])
    assert first["owner_id"] == "alice"
    assert first["visibility"] == "PRIVATE"
    assert first["title"] == "我的驾驶舱"
    assert first["cards"] == []
    assert first["finite_mock"] is True
    assert first["http_api"] == "NOT_CONNECTED"
    assert first["persisted"] is True
    assert first["preview"] is False
    assert replay == first
    assert second_key["dashboard_id"] == first["dashboard_id"]
    listed = store.list(actor())
    assert len(listed) == 1
    assert listed[0]["dashboard_id"] == first["dashboard_id"]
    assert listed[0]["http_api"] == "NOT_CONNECTED"


def test_add_copy_remove_layout_keep_stable_card_id_and_snapshot(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    added = store.apply(actor(), "add-1", board["dashboard_id"], "1", add_patch()).as_dict()
    assert added["version"] == 2
    assert added["persisted"] is True
    assert len(added["cards"]) == 1
    card = added["cards"][0]
    assert CARD_ID.fullmatch(card["card_id"])
    assert card["data_mode"] == "SNAPSHOT"
    assert card["freshness"] == "PINNED"
    assert card["snapshot"]["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert card["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    assert card["facts"]["totals"]["channel_mature_cohort_count"] != 100
    assert "repeat_rate" not in card["facts"]
    copied = store.apply(
        actor(), "copy-1", board["dashboard_id"], "2", {"op": "copy", "card_id": card["card_id"]},
    ).as_dict()
    assert copied["version"] == 3
    assert len(copied["cards"]) == 2
    clone = copied["cards"][1]
    assert clone["card_id"] != card["card_id"]
    assert CARD_ID.fullmatch(clone["card_id"])
    assert clone["snapshot"]["run_id"] == card["snapshot"]["run_id"]
    assert clone["snapshot"]["evidence_digest"] == card["snapshot"]["evidence_digest"]
    original = next(item for item in copied["cards"] if item["card_id"] == card["card_id"])
    assert original["layout"] == card["layout"]
    moved = store.apply(
        actor(), "layout-1", board["dashboard_id"], "3",
        {"op": "layout", "card_id": card["card_id"], "layout": {"x": 0, "y": 8, "w": 12, "h": 4}},
    ).as_dict()
    target = next(item for item in moved["cards"] if item["card_id"] == card["card_id"])
    other = next(item for item in moved["cards"] if item["card_id"] == clone["card_id"])
    assert target["layout"] == {"x": 0, "y": 8, "w": 12, "h": 4}
    assert other["layout"] == clone["layout"]
    removed = store.apply(
        actor(), "remove-1", board["dashboard_id"], "4", {"op": "remove", "card_id": clone["card_id"]},
    ).as_dict()
    assert [item["card_id"] for item in removed["cards"]] == [card["card_id"]]


def test_preview_does_not_persist_and_save_requires_if_match(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    preview = store.preview(actor(), board["dashboard_id"], add_patch()).as_dict()
    assert preview["preview"] is True
    assert preview["persisted"] is False
    assert preview["version"] == 1
    assert preview["affected_card_ids"]
    assert preview["cards"][0]["card_id"].startswith("preview_")
    current = store.get(actor(), board["dashboard_id"]).as_dict()
    assert current["cards"] == []
    assert current["version"] == 1
    with sqlite3.connect(store.path) as con:
        assert con.execute("SELECT count(*) FROM dashboards").fetchone()[0] == 1
    with pytest.raises(AnalyticsError) as missing:
        store.apply(actor(), "add-no-match", board["dashboard_id"], None, add_patch())
    assert missing.value.status == 428
    with pytest.raises(AnalyticsError) as bad:
        store.apply(actor(), "add-bad-match", board["dashboard_id"], "01", add_patch())
    assert bad.value.status == 400
    saved = store.apply(actor(), "add-save", board["dashboard_id"], "1", add_patch()).as_dict()
    assert saved["persisted"] is True
    assert saved["preview"] is False
    assert saved["version"] == 2
    assert CARD_ID.fullmatch(saved["cards"][0]["card_id"])


def test_stale_if_match_is_409_and_does_not_overwrite(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    first = store.apply(actor(), "add-a", board["dashboard_id"], "1", add_patch()).as_dict()
    with pytest.raises(AnalyticsError) as stale:
        store.apply(
            actor(), "add-stale", board["dashboard_id"], "1",
            {"op": "layout", "card_id": first["cards"][0]["card_id"], "layout": {"x": 0, "y": 0, "w": 8, "h": 4}},
        )
    assert stale.value.status == 409
    assert stale.value.code == "CONFLICT"
    current = store.get(actor(), board["dashboard_id"]).as_dict()
    assert current["version"] == 2
    assert current["cards"][0]["layout"] == first["cards"][0]["layout"]


def test_ai_finite_mock_only_changes_target_card_and_not_facts(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    first = store.apply(actor(), "add-a", board["dashboard_id"], "1", add_patch()).as_dict()
    second = store.apply(
        actor(), "copy-a", board["dashboard_id"], "2", {"op": "copy", "card_id": first["cards"][0]["card_id"]},
    ).as_dict()
    target_id = first["cards"][0]["card_id"]
    other_id = second["cards"][1]["card_id"]
    original_facts = json.dumps(second["cards"][0]["facts"], sort_keys=True)
    original_run = second["cards"][0]["snapshot"]["run_id"]
    preview = store.preview(
        actor(), board["dashboard_id"],
        {"op": "ai_edit", "card_id": target_id, "intent": "annotate-live"},
    ).as_dict()
    assert preview["persisted"] is False
    assert preview["affected_card_ids"] == [target_id]
    changed = next(card for card in preview["cards"] if card["card_id"] == target_id)
    untouched = next(card for card in preview["cards"] if card["card_id"] == other_id)
    assert changed["display_overrides"]["title"] == "直播渠道快照"
    assert changed["local_filters"] == {"channel_ids": ["A"]}
    assert json.dumps(changed["facts"], sort_keys=True) == original_facts
    assert changed["snapshot"]["run_id"] == original_run
    assert untouched["display_overrides"] == {}
    persisted = store.get(actor(), board["dashboard_id"]).as_dict()
    assert persisted["version"] == 3
    assert persisted["cards"][0]["display_overrides"] == {}
    saved = store.apply(
        actor(), "ai-save", board["dashboard_id"], "3",
        {"op": "ai_edit", "card_id": target_id, "intent": "trend-enlarge"},
    ).as_dict()
    saved_target = next(card for card in saved["cards"] if card["card_id"] == target_id)
    saved_other = next(card for card in saved["cards"] if card["card_id"] == other_id)
    assert saved_target["plugin_ref"]["type"] == "LINE"
    assert saved_target["layout"]["w"] == 12
    assert saved_target["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    assert saved_other["plugin_ref"]["type"] == "TABLE"
    with pytest.raises(AnalyticsError) as whole:
        store.preview(actor(), board["dashboard_id"], {"op": "remove", "scope": "board"})
    assert whole.value.status == 422
    with pytest.raises(AnalyticsError) as missing_target:
        store.preview(actor(), board["dashboard_id"], {"op": "remove"})
    assert missing_target.value.status == 422


def test_undo_writes_new_version_and_keeps_database_history(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    added = store.apply(actor(), "add-a", board["dashboard_id"], "1", add_patch()).as_dict()
    card_id = added["cards"][0]["card_id"]
    store.apply(actor(), "rm-a", board["dashboard_id"], "2", {"op": "remove", "card_id": card_id})
    undone = store.apply(
        actor(), "undo-a", board["dashboard_id"], "3",
        {"op": "undo", "scope": "board", "restore_from_version": 2},
    ).as_dict()
    assert undone["version"] == 4
    assert undone["cards"][0]["card_id"] == card_id
    assert undone["cards"][0]["snapshot"]["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with sqlite3.connect(store.path) as con:
        versions = list(con.execute(
            "SELECT version, cards_json FROM dashboards WHERE dashboard_id=? ORDER BY version",
            (board["dashboard_id"],),
        ))
        assert [row[0] for row in versions] == [1, 2, 3, 4]
        assert json.loads(versions[0][1]) == []
        assert json.loads(versions[2][1]) == []
        assert json.loads(versions[1][1])[0]["card_id"] == card_id
        assert json.loads(versions[3][1])[0]["card_id"] == card_id


def test_reopen_without_session_keeps_snapshot(tmp_path):
    directory = tmp_path / "cockpit"
    store = make_store(directory)
    board = seed_board(store)
    saved = store.apply(actor(), "add-a", board["dashboard_id"], "1", add_patch())
    snapshot = saved.as_dict()["cards"][0]["snapshot"]
    store.close()
    reopened = CockpitStore(directory, clock=lambda: CLOCK_MS)
    restored = reopened.get(actor(), saved.dashboard_id)
    assert restored.version == 2
    assert restored.as_dict()["cards"][0]["snapshot"] == snapshot
    assert restored.as_dict()["cards"][0]["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    assert restored.http_api == "NOT_CONNECTED"


def test_other_principal_and_missing_capability_do_not_leak(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    bob = actor("bob")
    with pytest.raises(AnalyticsError) as missing:
        store.get(bob, board["dashboard_id"])
    assert missing.value.status == 404
    assert store.list(bob) == []
    reader = actor(capabilities={"dashboard:read"})
    with pytest.raises(AnalyticsError) as forbidden:
        store.create(reader, "k", {})
    assert forbidden.value.status == 403
    b0_only = actor(scopes={"b0-fixture"})
    with pytest.raises(AnalyticsError) as scope:
        store.get(b0_only, board["dashboard_id"])
    assert scope.value.status == 403


def test_b0_fixture_and_foreign_sqlite_are_rejected(tmp_path):
    store = make_store(tmp_path / "cockpit")
    board = seed_board(store)
    with pytest.raises(AnalyticsError) as rejected:
        store.apply(actor(), "b0", board["dashboard_id"], "1", add_patch(facts=b0_payload()["result"]))
    assert rejected.value.status == 422
    assert "B0" in rejected.value.message
    directory = tmp_path / "foreign"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / "cockpit.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT INTO metadata VALUES ('kind', 'cockpit')")
        con.execute("PRAGMA application_id=1397571889")
        con.execute("PRAGMA user_version=1")
    with pytest.raises(ValueError, match="foreign"):
        CockpitStore(directory)


def test_http_surface_is_explicitly_disconnected(tmp_path):
    store = make_store(tmp_path / "cockpit")
    assert store.http_api == "NOT_CONNECTED"
    assert store.finite_mock is True
    board = seed_board(store)
    assert board["http_api"] == "NOT_CONNECTED"
    with sqlite3.connect(store.path) as con:
        assert con.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert con.execute("SELECT value FROM metadata WHERE key='http_api'").fetchone()[0] == "NOT_CONNECTED"
