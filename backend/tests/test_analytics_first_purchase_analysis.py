"""First-purchase SNAPSHOT save and cockpit HTTP. Shared succeeded_source is not claimed."""

from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.analytics_first_purchase_analysis_app import PREFIX as ANALYSIS_PREFIX
from backend.analytics_first_purchase_analysis_app import create_first_purchase_analysis_app
from backend.analytics_first_purchase_app import PREFIX as RUN_PREFIX
from backend.analytics_first_purchase_app import create_first_purchase_app
from backend.analytics_first_purchase_cockpit_app import PREFIX as COCKPIT_PREFIX
from backend.analytics_first_purchase_cockpit_app import create_first_purchase_cockpit_app
from backend.analytics_first_purchase_fixture import create_first_purchase_fixture
from backend.contracts.analytics_first_purchase_analysis import HTTP_API_CONNECTED
from backend.contracts.analytics_first_purchase_cockpit import FirstPurchaseDashboard
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.first_purchase.cockpit import FirstPurchaseCockpitStore
from backend.services.analytics.first_purchase.runtime import FirstPurchaseRuntime
from backend.services.analytics.first_purchase.saved import FirstPurchaseSavedAnalysisStore
from backend.services.analytics.jobs import RunStore
from backend.tests.analytics_run_support import profile
from backend.tests.test_analytics_first_purchase_http import (
    EXPECTED_PATH,
    MISSING_EXPECTED_PATH,
    MISSING_SNAPSHOT_PATH,
    SNAPSHOT_PATH,
    load_json,
)

TOKEN = "a" * 40
OTHER = "b" * 40
READER = "c" * 40


def private_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(mode=0o700, parents=True)
    os.chmod(path, 0o700)
    return path


def asset_actor(name="synthetic-demo", *, capabilities=None, scopes=None):
    default = {
        "run:create", "run:read", "run:cancel",
        "analysis:save", "analysis:read",
        "dashboard:read", "dashboard:update",
    }
    return AnalyticsPrincipal(
        name,
        frozenset(default if capabilities is None else capabilities),
        frozenset({"first-purchase-fixture"} if scopes is None else scopes),
    )


def headers(token=TOKEN, key=None, etag=None):
    values = {"authorization": f"Bearer {token}"}
    if key is not None:
        values["idempotency-key"] = key
    if etag is not None:
        values["if-match"] = str(etag)
    return values


def succeed_first_purchase(tmp_path, snapshot=None, request=None):
    fixture = create_first_purchase_fixture(snapshot or load_json(SNAPSHOT_PATH))
    store = RunStore(private_dir(tmp_path, "state"), profile(), family="first_purchase")
    runtime = FirstPurchaseRuntime(store, fixture, lambda _: asset_actor())
    body = request or load_json(EXPECTED_PATH)["request"]
    snapshot_doc = runtime.submit_and_execute(asset_actor(), "run-1", body)
    return store, runtime, snapshot_doc


def make_registry(**grants):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, asset_actor())
    registry.grant(OTHER, asset_actor("other-demo"))
    registry.grant(READER, asset_actor("reader-demo", capabilities={"analysis:read", "dashboard:read", "run:read"}))
    for token, principal in grants.items():
        registry.grant(token, principal)
    return registry


def analysis_counts(store: FirstPurchaseSavedAnalysisStore):
    with closing(sqlite3.connect(store.path)) as con:
        return {
            "analyses": con.execute("SELECT count(*) FROM analyses").fetchone()[0],
            "idempotency": con.execute("SELECT count(*) FROM idempotency").fetchone()[0],
        }


def cockpit_counts(store: FirstPurchaseCockpitStore):
    with closing(sqlite3.connect(store.path)) as con:
        return {
            "dashboards": con.execute("SELECT count(*) FROM dashboards").fetchone()[0],
            "owners": con.execute("SELECT count(*) FROM owners").fetchone()[0],
        }


def make_analysis_client(tmp_path, run_store, registry=None):
    analyses = FirstPurchaseSavedAnalysisStore(private_dir(tmp_path, "analyses"))
    identities = registry or make_registry()
    app = create_first_purchase_analysis_app(run_store, analyses, identities)
    return TestClient(app), analyses, identities


def test_offline_openapi_declares_shared_source():
    schema = create_first_purchase_analysis_app().openapi()
    assert schema["x-saved-analysis-http"] is True
    assert schema["x-first-purchase-saved-analysis-http"] is True
    assert schema["x-shared-succeeded-source"] is True
    assert ANALYSIS_PREFIX in schema["paths"]
    assert "/api/v1/analytics/analyses" not in schema["paths"]
    assert "/api/v1/analytics-query/runs/{run_id}" not in schema["paths"]
    cockpit = create_first_purchase_cockpit_app().openapi()
    assert cockpit["x-cockpit-http"] is True
    assert cockpit["x-first-purchase-cockpit-http"] is True
    assert COCKPIT_PREFIX in cockpit["paths"]
    assert "/api/v1/analytics/dashboards" not in cockpit["paths"]


def test_save_close_reopen_read_add_cockpit(tmp_path):
    run_store, _runtime, run = succeed_first_purchase(tmp_path)
    assert run.status == "SUCCEEDED" and run.result.status == "OK"
    called = []

    def forbidden(*_args, **_kwargs):
        called.append(1)
        raise AssertionError("query_succeeded_source must not be used for first-purchase")

    client, analyses, registry = make_analysis_client(tmp_path, run_store)
    with patch("backend.services.analytics.jobs.RunStore.query_succeeded_source", forbidden):
        created = client.post(
            ANALYSIS_PREFIX,
            json={"created_from_run_id": run.run_id, "title": "首购 30 日快照"},
            headers=headers(key="save-1"),
        )
    assert created.status_code == 201, created.text
    assert called == []
    body = created.json()
    assert body["http_api"] == HTTP_API_CONNECTED
    assert body["data_mode"] == "SNAPSHOT"
    assert body["created_from_run_id"] == run.run_id
    assert body["snapshot"]["run_id"] == run.run_id
    assert body["facts"]["observation_days"] == 30
    assert body["facts"] == run.result.facts.model_dump(mode="json")
    assert body["query_ref"]["query_id"] == "first_purchase_product_path"
    assert analyses.get(asset_actor(), body["analysis_id"]).as_dict()["http_api"] == "NOT_CONNECTED"
    analyses.close()
    reopened = FirstPurchaseSavedAnalysisStore(tmp_path / "analyses")
    fresh = TestClient(create_first_purchase_analysis_app(run_store, reopened, registry))
    fetched = fresh.get(f"{ANALYSIS_PREFIX}/{body['analysis_id']}", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"] == body["snapshot"]
    assert fetched.json()["facts"] == body["facts"]
    boards = FirstPurchaseCockpitStore(private_dir(tmp_path, "cockpit"))
    cockpit = TestClient(create_first_purchase_cockpit_app(reopened, boards, registry))
    board = cockpit.post(COCKPIT_PREFIX, json={"title": "我的首购驾驶舱"}, headers=headers(key="board-1"))
    assert board.status_code == 201, board.text
    FirstPurchaseDashboard.model_validate(board.json())
    dashboard_id = board.json()["dashboard_id"]
    added = cockpit.post(
        f"{COCKPIT_PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": body["analysis_id"], "version": 1}},
        headers=headers(key="add-1", etag=1),
    )
    assert added.status_code == 201, added.text
    card = added.json()["cards"][0]
    assert card["source_status"] == "OK"
    assert card["facts"] == body["facts"]
    assert card["snapshot"]["run_id"] == run.run_id
    boards.close()
    cockpit_again = FirstPurchaseCockpitStore(tmp_path / "cockpit")
    reread = TestClient(create_first_purchase_cockpit_app(reopened, cockpit_again, registry))
    shown = reread.get(f"{COCKPIT_PREFIX}/{dashboard_id}", headers=headers())
    assert shown.status_code == 200
    assert shown.json()["cards"][0]["facts"] == body["facts"]
    assert shown.json()["http_api"] == HTTP_API_CONNECTED


def test_duplicate_save_version_conflict_cross_owner_revocation(tmp_path):
    run_store, _runtime, run = succeed_first_purchase(tmp_path)
    client, analyses, registry = make_analysis_client(tmp_path, run_store)
    first = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "同一把钥匙"},
        headers=headers(key="same"),
    )
    assert first.status_code == 201
    replay = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "同一把钥匙"},
        headers=headers(key="same"),
    )
    assert replay.status_code == 201
    assert replay.json()["analysis_id"] == first.json()["analysis_id"]
    changed = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "改语义"},
        headers=headers(key="same"),
    )
    assert changed.status_code == 409
    analysis_id = first.json()["analysis_id"]
    stale = client.post(
        f"{ANALYSIS_PREFIX}/{analysis_id}/versions", json={"title": "新标题"},
        headers=headers(key="v2", etag=1),
    )
    assert stale.status_code == 201
    conflict = client.post(
        f"{ANALYSIS_PREFIX}/{analysis_id}/versions", json={"title": "更后的标题"},
        headers=headers(key="v3", etag=1),
    )
    assert conflict.status_code == 409
    bob = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "越权"},
        headers=headers(OTHER, key="k-bob"),
    )
    assert bob.status_code == 404
    reader = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "只读"},
        headers=headers(READER, key="k-read"),
    )
    assert reader.status_code == 403
    boards = FirstPurchaseCockpitStore(private_dir(tmp_path, "cockpit"))
    cockpit = TestClient(create_first_purchase_cockpit_app(analyses, boards, registry))
    board = cockpit.post(COCKPIT_PREFIX, json={}, headers=headers(key="board"))
    dashboard_id = board.json()["dashboard_id"]
    added = cockpit.post(
        f"{COCKPIT_PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": analysis_id, "version": 2}},
        headers=headers(key="add", etag=1),
    )
    assert added.status_code == 201
    stale_board = cockpit.post(
        f"{COCKPIT_PREFIX}/{dashboard_id}/versions",
        json={"op": "add", "analysis_ref": {"analysis_id": analysis_id, "version": 2}},
        headers=headers(key="add-stale", etag=1),
    )
    assert stale_board.status_code == 409
    registry.revoke(TOKEN)
    listed = client.get(ANALYSIS_PREFIX, headers=headers())
    assert listed.status_code == 401
    fetched = cockpit.get(f"{COCKPIT_PREFIX}/{dashboard_id}", headers=headers())
    assert fetched.status_code == 401


def test_rejected_result_forged_source_and_unsupported_family(tmp_path):
    rejected_store, _runtime, rejected = succeed_first_purchase(
        tmp_path / "rejected", load_json(MISSING_SNAPSHOT_PATH), load_json(MISSING_EXPECTED_PATH)["request"],
    )
    assert rejected.result.status == "REJECTED" and rejected.result.facts is None
    client, analyses, _registry = make_analysis_client(tmp_path / "rejected-app", rejected_store)
    denied = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": rejected.run_id, "title": "拒绝结果"},
        headers=headers(key="rej"),
    )
    assert denied.status_code == 422
    assert analysis_counts(analyses)["analyses"] == 0

    ok_store, _ok_runtime, ok = succeed_first_purchase(tmp_path / "ok")
    ok_client, ok_analyses, _ok_reg = make_analysis_client(tmp_path / "ok-app", ok_store)
    forged = ok_client.post(
        ANALYSIS_PREFIX,
        json={
            "created_from_run_id": ok.run_id, "title": "伪造",
            "facts": {"observation_days": 30}, "owner_id": "eve",
        },
        headers=headers(key="forge"),
    )
    assert forged.status_code == 422
    assert analysis_counts(ok_analyses)["analyses"] == 0

    b0 = RunStore(private_dir(tmp_path, "b0"), profile(), family="b0")
    b0_client, b0_analyses, _ = make_analysis_client(tmp_path / "b0-app", b0)
    b0_save = b0_client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": "run_missing", "title": "B0"},
        headers=headers(key="b0"),
    )
    assert b0_save.status_code == 409
    assert analysis_counts(b0_analyses)["analyses"] == 0


def test_queued_failed_and_cancelled_cannot_save(tmp_path):
    fixture = create_first_purchase_fixture(load_json(SNAPSHOT_PATH))
    store = RunStore(private_dir(tmp_path, "state"), profile(), family="first_purchase")
    registry = make_registry()
    actors = {"synthetic-demo": asset_actor(), "other-demo": asset_actor("other-demo")}
    runtime = FirstPurchaseRuntime(store, fixture, actors.get)
    run_app = TestClient(create_first_purchase_app(runtime, registry))
    import fcntl
    path = runtime.store.directory / ".first-purchase-dispatch.lock"
    with path.open("w") as lock:
        path.chmod(0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        accepted = run_app.post(RUN_PREFIX + "/runs", json=load_json(EXPECTED_PATH)["request"], headers=headers(key="queued"))
        assert accepted.status_code == 202
        analysis_http, analyses, _ = make_analysis_client(tmp_path / "qapp", store, registry)
        pending = analysis_http.post(
            ANALYSIS_PREFIX, json={"created_from_run_id": accepted.json()["run_id"], "title": "未完成"},
            headers=headers(key="pending"),
        )
        assert pending.status_code == 422
        cancelled = run_app.post(
            RUN_PREFIX + "/runs/" + accepted.json()["run_id"] + "/cancel",
            json={"reason": "USER_REQUEST"}, headers=headers(key="cancel", etag=accepted.json()["version"]),
        )
        assert cancelled.json()["status"] == "CANCELLED"
        after_cancel = analysis_http.post(
            ANALYSIS_PREFIX, json={"created_from_run_id": accepted.json()["run_id"], "title": "已取消"},
            headers=headers(key="cancelled"),
        )
        assert after_cancel.status_code == 422
        assert analysis_counts(analyses)["analyses"] == 0


def test_wrong_scope_and_channel_disguise_rejected(tmp_path):
    run_store, _runtime, run = succeed_first_purchase(tmp_path)
    scoped = asset_actor(scopes={"channel-followup-fixture"})
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, scoped)
    client, analyses, _ = make_analysis_client(tmp_path / "scoped", run_store, registry)
    denied = client.post(
        ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "错域"},
        headers=headers(key="scope"),
    )
    assert denied.status_code == 403
    assert analysis_counts(analyses)["analyses"] == 0


def test_unconfigured_apps_fail_closed():
    registry = make_registry()
    listed = TestClient(create_first_purchase_analysis_app(identities=registry)).get(ANALYSIS_PREFIX, headers=headers())
    assert listed.status_code == 503
    boards = TestClient(create_first_purchase_cockpit_app(identities=registry)).get(COCKPIT_PREFIX, headers=headers())
    assert boards.status_code == 503


def test_idempotent_concurrent_save(tmp_path):
    run_store, _runtime, run = succeed_first_purchase(tmp_path)
    client, analyses, _ = make_analysis_client(tmp_path, run_store)

    def once():
        row = None
        for _ in range(8):
            row = client.post(
                ANALYSIS_PREFIX, json={"created_from_run_id": run.run_id, "title": "并发"},
                headers=headers(key="parallel"),
            )
            if row.status_code != 503:
                return row
        return row

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: once(), range(2)))
    assert {row.status_code for row in results} == {201}
    assert results[0].json()["analysis_id"] == results[1].json()["analysis_id"]
    assert analysis_counts(analyses)["analyses"] == 1
