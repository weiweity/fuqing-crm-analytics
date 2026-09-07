"""Saved-analysis HTTP: trusted RunStore source, ACL, idempotency, sessionless read."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.analytics_analysis_app import PREFIX, create_analysis_app
from backend.contracts.analytics_analysis import HTTP_API_CONNECTED
from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.jobs import RunStore
from backend.services.analytics.saved_analyses import SavedAnalysisStore
from backend.services.analytics.worker import WorkerManager
from backend.tests.analytics_run_support import accept, make_store, observation
from backend.tests.test_analytics_query_jobs import query_actor
from backend.tests.test_analytics_query_worker import setup_query_worker
from backend.tests.test_analytics_saved_analyses import make_store as make_analysis_store

TOKEN = "a" * 40
OTHER = "b" * 40
READER = "c" * 40


def analysis_actor(name="alice", *, capabilities=None):
    return AnalyticsPrincipal(
        name,
        frozenset({"run:read", "analysis:save", "analysis:read"} if capabilities is None else capabilities),
        frozenset({"channel-followup-fixture"}),
    )


def headers(token=TOKEN, key=None, etag=None):
    values = {"authorization": f"Bearer {token}"}
    if key is not None:
        values["idempotency-key"] = key
    if etag is not None:
        values["if-match"] = str(etag)
    return values


def succeed_query(tmp_path, days=30):
    store, accepted, intent, step, fixture = setup_query_worker(tmp_path, days=days)
    WorkerManager(store, lambda _: query_actor(), fixture).execute(query_actor(), intent, step)
    done = store.observe(query_actor(), observation(intent, "SUCCEEDED", primary=step.step_id))
    assert done.status == "SUCCEEDED" and done.result is not None
    return store, accepted.run_id, intent


def analysis_client(tmp_path, run_store, **grants):
    analyses = make_analysis_store(tmp_path / "analyses")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    registry.grant(OTHER, analysis_actor("bob"))
    registry.grant(READER, analysis_actor(capabilities={"analysis:read"}))
    for token, principal in grants.items():
        registry.grant(token, principal)
    app = create_analysis_app(run_store, analyses, registry)
    return TestClient(app), analyses, app


def inventory(run_store: RunStore):
    with closing(sqlite3.connect(run_store.path)) as con:
        return {
            "runs": con.execute("SELECT count(*) FROM runs").fetchone()[0],
            "workers": con.execute("SELECT count(*) FROM worker_executions").fetchone()[0],
            "steps": con.execute("SELECT count(*) FROM steps").fetchone()[0],
        }


def analysis_counts(store: SavedAnalysisStore):
    with closing(sqlite3.connect(store.path)) as con:
        return {
            "analyses": con.execute("SELECT count(*) FROM analyses").fetchone()[0],
            "succeeded_runs": con.execute("SELECT count(*) FROM succeeded_runs").fetchone()[0],
            "idempotency": con.execute("SELECT count(*) FROM idempotency").fetchone()[0],
        }


def test_unconfigured_app_fail_closed_and_openapi_is_offline():
    app = create_analysis_app()
    schema = app.openapi()
    assert schema["x-saved-analysis-http"] is True
    assert schema["x-query-session-fence"] is False
    assert "/api/v1/analytics/analyses" in schema["paths"]
    assert "/api/v1/analytics-query/runs/{run_id}" not in schema["paths"]
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    listed = TestClient(create_analysis_app(identities=registry)).get(PREFIX, headers=headers())
    assert listed.status_code == 503
    assert listed.json()["error"]["code"] == "ANALYSIS_NOT_CONFIGURED"


def test_real_worker_source_save_reopen_sessionless_read(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    before = inventory(run_store)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    created = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "渠道 30 日快照"}, headers=headers(key="save-1"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["http_api"] == HTTP_API_CONNECTED
    assert body["data_mode"] == "SNAPSHOT"
    assert body["created_from_run_id"] == run_id
    assert body["snapshot"]["run_id"] == run_id
    assert body["facts"]["observation_days"] == 30
    assert body["owner_id"] == "alice"
    assert "owner_id" not in {"created_from_run_id": run_id, "title": "渠道 30 日快照"}
    store_doc = analyses.get(analysis_actor(), body["analysis_id"]).as_dict()
    assert store_doc["http_api"] == "NOT_CONNECTED"
    analyses.close()
    reopened = SavedAnalysisStore(tmp_path / "analyses")
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    fresh = TestClient(create_analysis_app(run_store, reopened, registry))
    fetched = fresh.get(f"{PREFIX}/{body['analysis_id']}", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"] == body["snapshot"]
    assert fetched.json()["http_api"] == HTTP_API_CONNECTED
    assert "x-runtime-session-id" not in fetched.request.headers
    listed = fresh.get(PREFIX, headers=headers())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["analysis_id"] == body["analysis_id"]
    assert listed.json()["items"][0]["http_api"] == HTTP_API_CONNECTED
    assert inventory(run_store) == before


def test_rejects_non_succeeded_b0_family_and_client_forgeries(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    queued = tmp_path / "queued"
    queued.mkdir()
    other_store, accepted, *_rest = setup_query_worker(queued)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    (tmp_path / "qapp").mkdir()
    client_q, _, _ = analysis_client(tmp_path / "qapp", other_store)
    pending = client_q.post(PREFIX, json={"created_from_run_id": accepted.run_id, "title": "未完成"}, headers=headers(key="k-run"))
    assert pending.status_code == 422
    with closing(sqlite3.connect(tmp_path / "qapp" / "analyses" / "analyses.sqlite3")) as con:
        assert con.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0
    b0 = make_store(tmp_path / "b0")
    b0_run = accept(b0)
    (tmp_path / "b0app").mkdir()
    b0_client, _, _ = analysis_client(tmp_path / "b0app", b0)
    b0_save = b0_client.post(PREFIX, json={"created_from_run_id": b0_run.run_id, "title": "B0"}, headers=headers(key="k-b0"))
    assert b0_save.status_code == 409
    forged = client.post(
        PREFIX,
        json={"created_from_run_id": run_id, "title": "伪造", "facts": {"observation_days": 30}, "owner_id": "eve",
              "status": "SUCCEEDED", "evidence_digest": "a" * 64},
        headers=headers(key="k-forge"),
    )
    assert forged.status_code == 422
    bob = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "越权"}, headers=headers(OTHER, key="k-bob"))
    assert bob.status_code == 404
    reader = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "只读"}, headers=headers(READER, key="k-read"))
    assert reader.status_code == 403
    with closing(sqlite3.connect(analyses.path)) as con:
        assert con.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0


def test_idempotency_conflict_retry_and_revocation(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    first = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "同一把钥匙"}, headers=headers(key="same"))
    assert first.status_code == 201
    replay = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "同一把钥匙"}, headers=headers(key="same"))
    assert replay.status_code == 201
    assert replay.json()["analysis_id"] == first.json()["analysis_id"]
    assert replay.json()["version"] == 1
    changed = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "改语义"}, headers=headers(key="same"))
    assert changed.status_code == 409
    missing = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "无钥匙"}, headers=headers())
    assert missing.status_code == 428

    def once():
        row = None
        for _ in range(8):
            row = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "并发"}, headers=headers(key="parallel"))
            if row.status_code != 503:
                return row
        return row

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: once(), range(2)))
    assert {row.status_code for row in results} == {201}
    assert results[0].json()["analysis_id"] == results[1].json()["analysis_id"]
    with closing(sqlite3.connect(analyses.path)) as con:
        assert con.execute("SELECT count(*) FROM analyses WHERE title=?", ("并发",)).fetchone()[0] == 1
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    live = TestClient(create_analysis_app(run_store, analyses, registry))
    saved = live.post(PREFIX, json={"created_from_run_id": run_id, "title": "将撤权"}, headers=headers(key="revoke"))
    assert saved.status_code == 201
    registry.revoke(TOKEN)
    replay_revoked = live.post(PREFIX, json={"created_from_run_id": run_id, "title": "将撤权"}, headers=headers(key="revoke"))
    assert replay_revoked.status_code == 401
    listed = live.get(PREFIX, headers=headers())
    assert listed.status_code == 401


def test_list_isolation_title_version_and_old_if_match(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    client, _analyses, _app = analysis_client(tmp_path, run_store)
    empty = client.get(PREFIX, headers=headers())
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    created = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "原标题"}, headers=headers(key="v1"))
    analysis_id = created.json()["analysis_id"]
    snapshot = created.json()["snapshot"]
    bob_list = client.get(PREFIX, headers=headers(OTHER))
    assert bob_list.json()["items"] == []
    missing_if = client.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "新标题"}, headers=headers(key="v2"),
    )
    assert missing_if.status_code == 428
    updated = client.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "新标题"},
        headers=headers(key="v2", etag=1),
    )
    assert updated.status_code == 201
    assert updated.json()["version"] == 2
    assert updated.json()["title"] == "新标题"
    assert updated.json()["snapshot"] == snapshot
    old = client.get(f"{PREFIX}/{analysis_id}", params={"version": 1}, headers=headers())
    assert old.status_code == 200
    assert old.json()["title"] == "原标题"
    assert old.json()["snapshot"] == snapshot
    latest = client.get(f"{PREFIX}/{analysis_id}", headers=headers())
    assert latest.json()["version"] == 2
    assert latest.json()["facts"] == created.json()["facts"]
    stale = client.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "更后的标题"},
        headers=headers(key="v3", etag=1),
    )
    assert stale.status_code == 409


def test_save_does_not_start_runs_and_errors_hide_paths(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    before = inventory(run_store)
    client, _analyses, _app = analysis_client(tmp_path, run_store)
    created = client.post(PREFIX, json={"created_from_run_id": run_id, "title": "只读资产"}, headers=headers(key="idle"))
    assert created.status_code == 201
    listed = client.get(PREFIX, headers=headers())
    fetched = client.get(f"{PREFIX}/{created.json()['analysis_id']}", headers=headers())
    assert listed.status_code == 200 and fetched.status_code == 200
    assert inventory(run_store) == before
    unknown = client.get(f"{PREFIX}/analysis_{'ab' * 16}", headers=headers())
    assert unknown.status_code == 404
    assert "sqlite" not in unknown.text.lower()
    assert str(tmp_path) not in unknown.text
    assert TOKEN not in unknown.text


def test_corrupt_source_schema_ref_digest_rejected_without_asset_rows(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    before = inventory(run_store)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    body = {"created_from_run_id": run_id, "title": "损坏源拒绝"}
    empty = {"analyses": 0, "succeeded_runs": 0, "idempotency": 0}
    with closing(sqlite3.connect(run_store.path)) as con:
        original = con.execute(
            "SELECT result_json, primary_result_ref, evidence_digest, status FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()

    def restore_source():
        with closing(sqlite3.connect(run_store.path)) as con:
            con.execute(
                "UPDATE runs SET result_json=?, primary_result_ref=?, evidence_digest=?, status=? WHERE run_id=?",
                (*original, run_id),
            )
            con.commit()

    for case, field, value in (
        ("unknown_schema", "schema_version", "unknown/v9"),
        ("filter_mismatch", "filter_hash", "0" * 64),
    ):
        data = json.loads(original[0])
        data[field] = value
        with closing(sqlite3.connect(run_store.path)) as con:
            con.execute("UPDATE runs SET result_json=? WHERE run_id=?", (json.dumps(data), run_id))
            con.commit()
        response = client.post(PREFIX, json=body, headers=headers(key=case))
        assert response.status_code in (409, 422), (case, response.text)
        assert analysis_counts(analyses) == empty
        restore_source()

    for case, column, value in (
        ("missing_primary", "primary_result_ref", None),
        ("wrong_primary", "primary_result_ref", "step_nonexistent"),
        ("digest_mismatch", "evidence_digest", "0" * 64),
        ("cancelled", "status", "CANCELLED"),
        ("failed", "status", "FAILED"),
    ):
        with closing(sqlite3.connect(run_store.path)) as con:
            con.execute(f"UPDATE runs SET {column}=? WHERE run_id=?", (value, run_id))
            con.commit()
        response = client.post(PREFIX, json=body, headers=headers(key=case))
        assert response.status_code in (409, 422), (case, response.text)
        assert analysis_counts(analyses) == empty
        restore_source()
    assert inventory(run_store) == before


def test_register_then_save_failure_recovers_same_key(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    before = inventory(run_store)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    body = {"created_from_run_id": run_id, "title": "登记后保存失败"}
    with patch.object(
        analyses,
        "save",
        side_effect=AnalyticsError(503, "STATE_UNAVAILABLE", "分析状态暂不可用。", retryable=True),
    ):
        failed = client.post(PREFIX, json=body, headers=headers(key="recover"))
    assert failed.status_code == 503
    # Sequential analysis-DB transactions: source registration can commit
    # without an analysis or idempotency row. Not cross-RunStore atomicity.
    assert analysis_counts(analyses) == {"analyses": 0, "succeeded_runs": 1, "idempotency": 0}
    recovered = client.post(PREFIX, json=body, headers=headers(key="recover"))
    assert recovered.status_code == 201, recovered.text
    assert recovered.json()["created_from_run_id"] == run_id
    assert analysis_counts(analyses)["analyses"] == 1
    assert inventory(run_store) == before


def test_partial_revoke_blocks_create_and_title_replay(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    created = client.post(
        PREFIX, json={"created_from_run_id": run_id, "title": "将部分撤权"}, headers=headers(key="keep"),
    )
    assert created.status_code == 201
    analysis_id = created.json()["analysis_id"]
    snapshot = created.json()["snapshot"]
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    live = TestClient(create_analysis_app(run_store, analyses, registry))
    version = live.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "第二版"}, headers=headers(key="title", etag=1),
    )
    assert version.status_code == 201
    assert version.json()["snapshot"] == snapshot
    for case, actor in (
        ("save_revoked", analysis_actor(capabilities={"run:read", "analysis:read"})),
        ("read_run_revoked", analysis_actor(capabilities={"analysis:save", "analysis:read"})),
        ("scope_revoked", AnalyticsPrincipal("alice", analysis_actor().capabilities, frozenset())),
    ):
        registry.grant(TOKEN, actor)
        response = live.post(
            PREFIX, json={"created_from_run_id": run_id, "title": "将部分撤权"}, headers=headers(key="keep"),
        )
        assert response.status_code == 403, (case, response.text)
        assert "facts" not in response.json()
    registry.grant(TOKEN, analysis_actor(capabilities={"analysis:read"}))
    denied = live.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "第二版"}, headers=headers(key="title", etag=1),
    )
    assert denied.status_code == 403
    assert "facts" not in denied.json()


def test_read_and_title_replay_without_run_store_or_dispatcher(tmp_path):
    run_store, run_id, _intent = succeed_query(tmp_path)
    client, analyses, _app = analysis_client(tmp_path, run_store)
    created = client.post(
        PREFIX, json={"created_from_run_id": run_id, "title": "无会话读取"}, headers=headers(key="idle-read"),
    )
    assert created.status_code == 201
    analysis_id = created.json()["analysis_id"]
    snapshot = created.json()["snapshot"]
    titled = client.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "第二版"}, headers=headers(key="title-read", etag=1),
    )
    assert titled.status_code == 201
    analyses.close()
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, analysis_actor())
    reopened = SavedAnalysisStore(tmp_path / "analyses")
    fresh = TestClient(create_analysis_app(None, reopened, registry, runtime_ready=lambda: False))
    fetched = fresh.get(f"{PREFIX}/{analysis_id}", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 2
    assert fetched.json()["snapshot"] == snapshot
    assert "x-runtime-session-id" not in fetched.request.headers
    listed = fresh.get(PREFIX, headers=headers())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["analysis_id"] == analysis_id
    old = fresh.get(f"{PREFIX}/{analysis_id}", params={"version": 1}, headers=headers())
    assert old.status_code == 200
    assert old.json()["title"] == "无会话读取"
    assert old.json()["snapshot"] == snapshot
    replay = fresh.post(
        f"{PREFIX}/{analysis_id}/versions", json={"title": "第二版"}, headers=headers(key="title-read", etag=1),
    )
    assert replay.status_code == 201
    assert replay.json()["version"] == 2
    assert replay.json()["snapshot"] == snapshot
