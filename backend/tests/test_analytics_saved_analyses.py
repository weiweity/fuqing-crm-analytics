"""Saved-analysis store: SUCCEEDED bind, reopen, ACL, SNAPSHOT immutability.

HTTP/OpenAPI is NOT RUN. Fixtures are handwritten; this file does not generate
expected documents from SavedAnalysisStore.
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
from backend.services.analytics.saved_analyses import (
    APPLICATION_ID,
    SavedAnalysisStore,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ANALYSIS_ID = re.compile(r"^analysis_[a-f0-9]{32}$")
CLOCK_MS = 1_800_000_000_000


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def succeeded_run() -> dict:
    return deepcopy(load_fixture("analytics_saved_analysis_succeeded_run.json")["run"])


def refresh_run() -> dict:
    return deepcopy(load_fixture("analytics_saved_analysis_refresh_run.json")["run"])


def expected_analysis() -> dict:
    return deepcopy(load_fixture("analytics_saved_analysis_expected.json")["analysis"])


def b0_rejected() -> dict:
    return deepcopy(load_fixture("analytics_saved_analysis_b0_rejected.json")["run"])


def actor(name="alice", *, capabilities=None, scopes=None):
    return AnalyticsPrincipal(
        name,
        frozenset({"analysis:save", "analysis:read"} if capabilities is None else capabilities),
        frozenset({"channel-followup-fixture"} if scopes is None else scopes),
    )


def make_store(path: Path, *, clock=lambda: CLOCK_MS) -> SavedAnalysisStore:
    path.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return SavedAnalysisStore(path, clock=clock)


def save_payload(run: dict, **changes) -> dict:
    payload = {
        "title": "首次观察到的渠道 / 30日二单率",
        "created_from_run_id": run["run_id"],
        "filters": deepcopy(run["request"]),
        "owner_id": "should-be-ignored",
        "visibility": "PUBLIC",
        "endorsement": "VERIFIED",
    }
    payload.update(changes)
    return payload


def seed_and_save(store: SavedAnalysisStore, principal=None, run=None, key="save-1"):
    principal = principal or actor()
    run = run or succeeded_run()
    store.register_succeeded_run(principal, run)
    return store.save(principal, key, save_payload(run))


def assert_matches_expected(actual: dict, expected: dict) -> None:
    assert ANALYSIS_ID.fullmatch(actual["analysis_id"])
    for key, value in expected.items():
        assert actual[key] == value, key
    assert actual["facts"]["totals"]["channel_repeat_ratio"] == 0.5
    assert actual["facts"]["totals"]["channel_mature_cohort_count"] != 100
    assert "repeat_rate" not in actual["facts"]


def test_fixture_files_are_handwritten_not_store_output():
    for name in (
        "analytics_saved_analysis_succeeded_run.json",
        "analytics_saved_analysis_refresh_run.json",
        "analytics_saved_analysis_expected.json",
        "analytics_saved_analysis_b0_rejected.json",
    ):
        payload = load_fixture(name)
        assert payload["handwritten"] is True
        assert payload["not_generated_by_store"] is True
        assert "SavedAnalysisStore" not in json.dumps(payload)


def test_save_binds_succeeded_run_and_ignores_client_owner(tmp_path):
    store = make_store(tmp_path / "saved")
    record = seed_and_save(store)
    actual = record.as_dict()
    assert_matches_expected(actual, expected_analysis())
    assert actual["owner_id"] == "alice"
    assert actual["visibility"] == "PRIVATE"
    assert actual["http_api"] == "NOT_CONNECTED"
    assert actual["finite_mock"] is True


def test_idempotent_save_replays_same_analysis(tmp_path):
    store = make_store(tmp_path / "saved")
    first = seed_and_save(store, key="same-key")
    replay = store.save(actor(), "same-key", save_payload(succeeded_run()))
    assert replay.as_dict() == first.as_dict()
    with sqlite3.connect(store.path) as con:
        assert con.execute("SELECT count(*) FROM analyses").fetchone()[0] == 1


def test_reopen_same_file_keeps_snapshot(tmp_path):
    directory = tmp_path / "saved"
    store = make_store(directory)
    saved = seed_and_save(store)
    snapshot = saved.as_dict()["snapshot"]
    store.close()
    reopened = SavedAnalysisStore(directory, clock=lambda: CLOCK_MS)
    restored = reopened.get(actor(), saved.analysis_id, 1)
    assert restored.analysis_id == saved.analysis_id
    assert restored.version == 1
    assert restored.as_dict()["snapshot"] == snapshot
    assert restored.as_dict()["filter_hash"] == expected_analysis()["filter_hash"]
    assert restored.as_dict()["facts"] == expected_analysis()["facts"]
    listed = reopened.list(actor())
    assert listed[0]["analysis_id"] == saved.analysis_id
    assert listed[0]["data_mode"] == "SNAPSHOT"


def test_other_principal_get_and_list_do_not_leak(tmp_path):
    store = make_store(tmp_path / "saved")
    saved = seed_and_save(store)
    bob = actor("bob")
    with pytest.raises(AnalyticsError) as missing:
        store.get(bob, saved.analysis_id)
    assert missing.value.status == 404
    assert missing.value.code == "NOT_FOUND"
    assert missing.value.message == "分析不存在或当前身份不可见。"
    assert store.list(bob) == []
    reader = actor(capabilities={"analysis:read"})
    with pytest.raises(AnalyticsError) as forbidden_save:
        store.save(reader, "k", save_payload(succeeded_run()))
    assert forbidden_save.value.status == 403
    b0_only = actor(scopes={"b0-fixture"})
    with pytest.raises(AnalyticsError) as scope:
        store.get(b0_only, saved.analysis_id)
    assert scope.value.status == 403


def test_non_succeeded_and_missing_run_are_rejected(tmp_path):
    store = make_store(tmp_path / "saved")
    running = succeeded_run()
    running["status"] = "RUNNING"
    with pytest.raises(AnalyticsError) as status:
        store.register_succeeded_run(actor(), running)
    assert status.value.status == 422
    with pytest.raises(AnalyticsError) as missing:
        store.save(actor(), "k", save_payload(succeeded_run()))
    assert missing.value.status == 404


def test_filter_hash_and_query_mismatch_rejected(tmp_path):
    store = make_store(tmp_path / "saved")
    run = succeeded_run()
    store.register_succeeded_run(actor(), run)
    mismatched = save_payload(run)
    mismatched["filters"]["observation_days"] = 60
    with pytest.raises(AnalyticsError) as changed:
        store.save(actor(), "k", mismatched)
    assert changed.value.status == 422
    wrong_query = save_payload(run, query_ref={
        "query_id": "first_purchase_product_path",
        "query_version": "channel-followup-query/v1",
    })
    with pytest.raises(AnalyticsError) as query:
        store.save(actor(), "k2", wrong_query)
    assert query.value.status == 422


def test_b0_fixture_is_not_a_business_result(tmp_path):
    store = make_store(tmp_path / "saved")
    with pytest.raises(AnalyticsError) as rejected:
        store.register_succeeded_run(actor(), b0_rejected())
    assert rejected.value.status == 422
    assert "B0" in rejected.value.message
    store.register_succeeded_run(actor(), succeeded_run())
    with pytest.raises(AnalyticsError) as nested:
        store.save(actor(), "k", save_payload(succeeded_run(), filters=b0_rejected()["result"]))
    assert nested.value.status == 422


def test_refresh_candidate_does_not_rewrite_published_snapshot(tmp_path):
    store = make_store(tmp_path / "saved")
    saved = seed_and_save(store)
    store.register_succeeded_run(actor(), refresh_run())
    original = json.dumps(saved.as_dict()["snapshot"], sort_keys=True)
    noted = store.record_refresh_candidate(actor(), saved.analysis_id, 1, refresh_run()["run_id"])
    assert noted["snapshot_rewritten"] is False
    assert noted["snapshot_run_id"] == succeeded_run()["run_id"]
    current = store.get(actor(), saved.analysis_id, 1)
    assert json.dumps(current.as_dict()["snapshot"], sort_keys=True) == original
    assert current.snapshot["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert current.refresh_candidate["run_id"] == "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    with sqlite3.connect(store.path) as con:
        versions = list(con.execute(
            "SELECT version, snapshot_json FROM analyses WHERE analysis_id=? ORDER BY version",
            (saved.analysis_id,),
        ))
        assert len(versions) == 1
        assert json.loads(versions[0][1])["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    newer = store.publish_version(
        actor(), "confirm", saved.analysis_id,
        base_version=1, snapshot_run_id=refresh_run()["run_id"],
    )
    assert newer.version == 2
    assert newer.snapshot["run_id"] == "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    frozen = store.get(actor(), saved.analysis_id, 1)
    assert frozen.snapshot["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert frozen.as_dict()["facts"] == expected_analysis()["facts"]
    with sqlite3.connect(store.path) as con:
        rows = list(con.execute(
            "SELECT version, snapshot_json FROM analyses WHERE analysis_id=? ORDER BY version",
            (saved.analysis_id,),
        ))
        assert len(rows) == 2
        assert json.loads(rows[0][1])["run_id"] == "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert json.loads(rows[1][1])["run_id"] == "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_published_version_is_not_updated_in_place_for_title(tmp_path):
    store = make_store(tmp_path / "saved")
    saved = seed_and_save(store)
    renamed = store.publish_version(
        actor(), "rename", saved.analysis_id, base_version=1, title="渠道后续购买 · 已保存",
    )
    assert renamed.version == 2
    assert renamed.title == "渠道后续购买 · 已保存"
    original = store.get(actor(), saved.analysis_id, 1)
    assert original.title == expected_analysis()["title"]
    assert original.snapshot == saved.snapshot


def test_foreign_sqlite_is_refused(tmp_path):
    directory = tmp_path / "foreign"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / "analyses.sqlite3"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT INTO metadata VALUES ('kind', 'saved_analysis')")
        con.execute("PRAGMA application_id=1397572144")
        con.execute("PRAGMA user_version=1")
    with pytest.raises(ValueError, match="foreign"):
        SavedAnalysisStore(directory)


def test_http_surface_is_explicitly_disconnected(tmp_path):
    store = make_store(tmp_path / "saved")
    assert store.http_api == "NOT_CONNECTED"
    assert store.finite_mock is True
    saved = seed_and_save(store)
    assert saved.http_api == "NOT_CONNECTED"
    with sqlite3.connect(store.path) as con:
        assert con.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert con.execute("SELECT value FROM metadata WHERE key='http_api'").fetchone()[0] == "NOT_CONNECTED"


@pytest.mark.parametrize("change", [
    {"observation_days":60}, {"channel_ids":["B"]},
    {"cohort_window":{"kind":"FIXED","start_date":"2026-06-02","end_date":"2026-09-01"}},
])
def test_saved_run_rejects_request_result_mismatch_before_persistence(tmp_path, change):
    from backend.services.analytics.access import AnalyticsError
    store = make_store(tmp_path / "saved")
    run = succeeded_run()
    run["request"].update(deepcopy(change))
    with pytest.raises(AnalyticsError) as error:
        store.register_succeeded_run(actor(), run)
    assert error.value.status == 422
    assert error.value.code == "UNPROCESSABLE"
    assert store.list(actor()) == []


def test_saved_run_condition_binding_survives_reopen(tmp_path):
    store = make_store(tmp_path / "saved")
    run = succeeded_run()
    store.register_succeeded_run(actor(), run)
    saved = store.save(actor(), "save", save_payload(run))
    store.close()
    reopened = make_store(tmp_path / "saved").get(actor(), saved.analysis_id)
    assert reopened.filters["observation_days"] == reopened.facts["observation_days"] == 30
    assert reopened.filters["channel_ids"] == [row["channel_id"] for row in reopened.facts["channels"]]
