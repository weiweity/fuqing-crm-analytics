"""Shared source proves the frozen request and refuses corrupt persisted bindings."""
import json
import sqlite3
from contextlib import closing

import pytest

from backend.services.analytics.first_purchase.runtime import METHOD_DIGEST
from backend.services.analytics.first_purchase.source import resolve_trusted_first_purchase_source
from backend.services.analytics.jobs import RunStore
from backend.tests.analytics_run_support import profile
from backend.tests.test_analytics_first_purchase_analysis import (
    ANALYSIS_PREFIX, asset_actor, headers, make_analysis_client, succeed_first_purchase,
)
from backend.tests.test_analytics_first_purchase_http import EXPECTED_PATH, load_json


def test_frozen_request_and_method_survive_reopen_and_save(tmp_path):
    request = load_json(EXPECTED_PATH)["request"]
    request["channel_ids"] = []
    store, _runtime, run = succeed_first_purchase(tmp_path, request=request)
    reopened = RunStore(store.directory, profile(), family="first_purchase")
    source = resolve_trusted_first_purchase_source(reopened, asset_actor(), run.run_id)
    assert source.request["channel_ids"] == []
    assert source.result["resolved_filters"]["channel_ids"] == ["A", "B"]
    assert source.method_package_digest == METHOD_DIGEST
    assert source.primary_result_ref == run.primary_result_ref
    assert source.source_layer == "runstore_succeeded_source"
    client, _analyses, _registry = make_analysis_client(tmp_path, reopened)
    response = client.post(ANALYSIS_PREFIX, json={"created_from_run_id":run.run_id, "title":"冻结条件"}, headers=headers(key="save"))
    assert response.status_code == 201, response.text
    assert response.json()["filters"]["channel_ids"] == []


@pytest.mark.parametrize("corruption", ["method", "step", "digest", "primary"])
def test_corrupt_shared_source_cannot_create_asset(tmp_path, corruption):
    store, _runtime, run = succeed_first_purchase(tmp_path)
    client, analyses, _registry = make_analysis_client(tmp_path, store)
    # Only the synthetic temporary store created by this test is modified.
    with closing(sqlite3.connect(store.directory / "runs.sqlite3")) as con:
        if corruption == "method":
            con.execute("UPDATE idempotency SET request_hash=? WHERE operation='runtime.binding' AND key='method'", ("0"*64,))
        elif corruption == "step":
            row = con.execute("SELECT response_json FROM idempotency WHERE operation='runtime.step-binding'").fetchone()
            body = json.loads(row[0])
            body["request"]["observation_days"] = 90
            con.execute("UPDATE idempotency SET response_json=? WHERE operation='runtime.step-binding'", (json.dumps(body),))
        elif corruption == "digest":
            con.execute("UPDATE runs SET evidence_digest=? WHERE run_id=?", ("0"*64, run.run_id))
        else:
            con.execute("UPDATE runs SET primary_result_ref=NULL WHERE run_id=?", (run.run_id,))
        con.commit()
    response = client.post(ANALYSIS_PREFIX, json={"created_from_run_id":run.run_id, "title":"不能保存"}, headers=headers(key="save"))
    assert response.status_code in {409, 422}, response.text
    with closing(sqlite3.connect(analyses.path)) as con:
        assert con.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0
