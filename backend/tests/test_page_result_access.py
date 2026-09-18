"""Authorized free-page result bridge. Synthetic snapshots only; no DuckDB."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.services.analytics.access import AnalyticsError, AnalyticsPrincipal
from backend.services.analytics.page_result_access import (
    BINDING_STATES,
    DATA_SCOPE,
    FORBIDDEN_OPS,
    MAX_CUMULATIVE_ROWS,
    MAX_PAGE_LIMIT,
    MAX_RESPONSE_BYTES,
    PAGE_TO_HOST_OPS,
    PROTOCOL,
    SUMMARY_FIELDS,
    PageResultAccess,
    default_synthetic_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json"
CAPS = frozenset({"dashboard:read", "analysis:read"})
ALICE = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE}))
BOB = AnalyticsPrincipal("bob", CAPS, frozenset({DATA_SCOPE}))
NO_CAP = AnalyticsPrincipal("alice", frozenset(), frozenset({DATA_SCOPE}))
NO_SCOPE = AnalyticsPrincipal("alice", CAPS, frozenset({"other-scope"}))

BOUND_MANIFEST = {
    "result_refs": ["result_fixture_1"],
    "bindings": [{
        "result_ref": "result_fixture_1",
        "unit": "CNY 元",
        "time_range": {"start": "2026-04-30", "end": "2026-07-28"},
        "result_version": 1,
    }],
}
UNBOUND_MANIFEST = {"result_refs": [], "bindings": []}


def store(clock=lambda: 1_000, **snapshot):
    access = PageResultAccess(clock=clock)
    access.put_snapshot(default_synthetic_snapshot(**snapshot))
    return access


def read(access, actor=ALICE, manifest=BOUND_MANIFEST, **request):
    body = {"op": "data.read", "request_id": "req_1", "result_ref": "result_fixture_1",
            "mode": "summary", **request}
    return access.read(actor, body, manifest=manifest)


def test_frozen_contract_v0_is_the_consumed_bridge_shape():
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    assert frozen["approved_plan_sha256"] == (
        "47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb")
    bridge = frozen["bridge"]
    assert bridge["protocol"] == PROTOCOL
    assert bridge["page_to_host_ops"] == list(PAGE_TO_HOST_OPS)
    assert bridge["forbidden_ops"] == list(FORBIDDEN_OPS)
    assert frozen["data_read"]["response_summary_fields"] == list(SUMMARY_FIELDS)
    assert frozen["data_read"]["budget"] == {
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "max_cumulative_rows": MAX_CUMULATIVE_ROWS,
    }
    assert frozen["data_read"]["request"]["result_ref"] == "result_fixture_1"
    assert frozen["asset"]["binding_states"] == list(BINDING_STATES)
    assert frozen["errors"]["RESULT_UNAVAILABLE"] == 409
    assert frozen["errors"]["RESULT_STALE"] == 409
    assert frozen["errors"]["RESULT_REVOKED"] == 403
    assert frozen["errors"]["BRIDGE_UNKNOWN_OP"] == 400
    assert frozen["asset"]["binding_state"] == "UNBOUND_SAMPLE"


def test_unbound_page_opens_without_verified_mark():
    access = store()
    state = access.binding_state(ALICE, UNBOUND_MANIFEST)
    assert state["binding_state"] == "UNBOUND_SAMPLE"
    assert state["verified"] is False
    assert state["host_source"]["does_not_endorse"] == "page_dom"
    with pytest.raises(AnalyticsError, match="FORBIDDEN"):
        read(access, manifest=UNBOUND_MANIFEST)


def test_summary_issues_data_ref_and_exact_summary_fields():
    access = store()
    body = read(access)
    assert body["ok"] is True
    assert set(body["summary"]) == set(SUMMARY_FIELDS)
    assert body["summary"]["unit"] == "CNY 元"
    assert body["summary"]["time_range"] == {"start": "2026-04-30", "end": "2026-07-28"}
    assert body["summary"]["row_count"] == 120
    assert body["summary"]["source"].startswith("合成结果夹具")
    assert body["data_ref"].startswith("data_")
    assert body["result_version"] == 1
    assert body["binding_state"] == "BOUND_VERIFIED"
    assert len(body["rows"]) == 5
    assert access.binding_state(ALICE, BOUND_MANIFEST)["binding_state"] == "BOUND_VERIFIED"


def test_empty_result_is_recoverable():
    access = store(row_count=0)
    body = read(access)
    assert body["summary"]["row_count"] == 0
    assert body["rows"] == []
    assert body["cursor"] is None
    assert body["ok"] is True


def test_page_and_range_pin_result_version():
    access = store()
    first = read(access, mode="page", limit=50, request_id="req_page_1")
    assert [row["i"] for row in first["rows"]] == list(range(50))
    second = read(access, mode="page", limit=50, cursor=first["cursor"], request_id="req_page_2")
    assert [row["i"] for row in second["rows"]] == list(range(50, 100))
    third = read(access, mode="page", limit=50, cursor=second["cursor"], request_id="req_page_3")
    assert [row["i"] for row in third["rows"]] == list(range(100, 120))
    assert third["cursor"] is None
    ranged = read(access, mode="range", start=10, end=15, request_id="req_range")
    assert [row["i"] for row in ranged["rows"]] == list(range(10, 15))
    access.put_snapshot(default_synthetic_snapshot(result_version=2))
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        read(access, mode="page", cursor=first["cursor"], request_id="req_stale_cursor")


def test_data_ref_rereads_the_pinned_snapshot():
    access = store()
    issued = read(access)["data_ref"]
    body = access.read(ALICE, {
        "op": "data.read", "request_id": "req_data_ref", "data_ref": issued, "mode": "page", "limit": 10,
    }, manifest=BOUND_MANIFEST)
    assert [row["i"] for row in body["rows"]] == list(range(10))
    access.put_snapshot(default_synthetic_snapshot(result_version=2))
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        access.read(ALICE, {
            "op": "data.read", "request_id": "req_old_data", "data_ref": issued, "mode": "summary",
        }, manifest=BOUND_MANIFEST)


def test_cross_actor_is_not_found_and_does_not_leak():
    access = store()
    with pytest.raises(AnalyticsError, match="NOT_FOUND") as denied:
        read(access, actor=BOB)
    assert denied.value.status == 404
    state = access.binding_state(BOB, BOUND_MANIFEST)
    assert state["binding_state"] == "BOUND_STALE"
    assert "NOT_FOUND" in state["reasons"]


def test_missing_capability_and_scope_are_forbidden():
    access = store()
    with pytest.raises(AnalyticsError, match="FORBIDDEN"):
        read(access, actor=NO_CAP)
    scoped = PageResultAccess()
    scoped.put_snapshot(default_synthetic_snapshot())
    with pytest.raises(AnalyticsError, match="FORBIDDEN"):
        scoped.read(NO_SCOPE, {
            "op": "data.read", "result_ref": "result_fixture_1", "mode": "summary",
        }, manifest=BOUND_MANIFEST)


def test_revoke_rejects_cache_hit_and_marks_stale():
    access = store()
    assert read(access)["ok"] is True
    access.revoke(ALICE, "result_fixture_1")
    with pytest.raises(AnalyticsError, match="RESULT_REVOKED") as revoked:
        read(access, request_id="req_cached")
    assert revoked.value.status == 403
    state = access.binding_state(ALICE, BOUND_MANIFEST)
    assert state["binding_state"] == "BOUND_STALE"
    assert "RESULT_REVOKED" in state["reasons"]
    assert state["verified"] is False
    with pytest.raises(AnalyticsError, match="NOT_FOUND") as hidden:
        read(access, actor=BOB, request_id="req_bob")
    assert hidden.value.status == 404
    assert "RESULT_REVOKED" not in access.binding_state(BOB, BOUND_MANIFEST)["reasons"]


def test_expiry_and_unit_time_version_mismatch_are_stale():
    clock = {"now": 100}
    access = store(clock=lambda: clock["now"], expires_at_ms=150)
    assert read(access)["ok"] is True
    clock["now"] = 150
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        read(access, request_id="req_expired")
    live = store()
    stale_unit = deepcopy(BOUND_MANIFEST)
    stale_unit["bindings"][0]["unit"] = "CNY 分"
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        read(live, manifest=stale_unit, request_id="req_unit")
    stale_time = deepcopy(BOUND_MANIFEST)
    stale_time["bindings"][0]["time_range"] = {"start": "2020-01-01", "end": "2020-01-31"}
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        read(live, manifest=stale_time, request_id="req_time")
    stale_version = deepcopy(BOUND_MANIFEST)
    stale_version["bindings"][0]["result_version"] = 9
    with pytest.raises(AnalyticsError, match="RESULT_STALE"):
        read(live, manifest=stale_version, request_id="req_version")


def test_sql_token_save_and_unknown_ops_are_rejected():
    access = store()
    for request in (
        {"op": "sql", "result_ref": "result_fixture_1"},
        {"op": "save", "result_ref": "result_fixture_1"},
        {"op": "http.fetch", "url": "https://example.invalid"},
        {"op": "credential.read"},
        {"op": "data.read", "result_ref": "result_fixture_1", "sql": "SELECT 1"},
        {"op": "data.read", "result_ref": "result_fixture_1", "token": "secret"},
        {"op": "data.query", "result_ref": "result_fixture_1"},
    ):
        with pytest.raises(AnalyticsError, match="BRIDGE_UNKNOWN_OP") as error:
            access.read(ALICE, request, manifest=BOUND_MANIFEST)
        assert error.value.status == 400


def test_cancel_stops_a_later_read_of_the_same_request():
    access = store()
    cancelled = access.cancel(ALICE, {"op": "data.cancel", "request_id": "req_cancel"})
    assert cancelled == {"request_id": "req_cancel", "status": "CANCELLED"}
    with pytest.raises(AnalyticsError, match="RESULT_UNAVAILABLE"):
        read(access, request_id="req_cancel")
    assert read(access, request_id="req_other")["ok"] is True


def test_cumulative_and_single_response_budgets():
    access = store(row_count=MAX_CUMULATIVE_ROWS)
    consumed = 0
    cursor = None
    pages = 0
    while consumed < MAX_CUMULATIVE_ROWS:
        body = read(access, mode="page", limit=MAX_PAGE_LIMIT, cursor=cursor,
                    request_id=f"req_budget_{pages}", instance_id="inst_1")
        consumed += len(body["rows"])
        cursor = body["cursor"]
        pages += 1
        if cursor is None:
            break
    assert consumed == MAX_CUMULATIVE_ROWS
    with pytest.raises(AnalyticsError, match="PACKAGE_TOO_LARGE"):
        read(access, mode="page", limit=1, request_id="req_over", instance_id="inst_1")
    other = read(access, mode="page", limit=1, request_id="req_other_inst", instance_id="inst_2")
    assert len(other["rows"]) == 1
    huge = store(row_count=80)
    huge.put_snapshot(default_synthetic_snapshot(rows=[
        {"i": index, "blob": "x" * 2000} for index in range(80)
    ]))
    with pytest.raises(AnalyticsError, match="PACKAGE_TOO_LARGE"):
        huge.read(ALICE, {
            "op": "data.read", "request_id": "req_bytes", "result_ref": "result_fixture_1",
            "mode": "page", "limit": 50,
        }, manifest=BOUND_MANIFEST)


def test_bob_cannot_revoke_alice_result():
    access = store()
    with pytest.raises(AnalyticsError, match="NOT_FOUND"):
        access.revoke(BOB, "result_fixture_1")
    assert read(access)["ok"] is True


def test_module_surface_stays_read_only():
    import ast
    tree = ast.parse((ROOT / "backend/services/analytics/page_result_access.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append((node.module or "") + "." + ",".join(alias.name for alias in node.names))
    joined = "\n".join(imported)
    assert "page_documents" not in joined
    assert "duckdb" not in joined
    access = PageResultAccess()
    assert not hasattr(access, "save")
    assert not hasattr(access, "query")
    assert not hasattr(access, "execute")
