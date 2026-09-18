"""Isolated HTTP for PageResultAccess. Not mounted unless explicitly configured.

Do not import analytics_competition_app here: that module pulls archived CRM
dotenv, which the B0 interpreter does not install.
"""
import ast
from pathlib import Path

from fastapi.testclient import TestClient

from backend.contracts.competition_computed import DATA_SCOPE as PAGE_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.page_result_access import (
    DATA_SCOPE, PageResultAccess, default_synthetic_snapshot,
)
from backend.services.analytics.page_result_access_routes import PREFIX, create_result_access_app
from backend.services.analytics.page_documents_routes import PREFIX as PAGE_PREFIX, create_page_app

ROOT = Path(__file__).resolve().parents[2]

CAPS = frozenset({"dashboard:read", "dashboard:update", "analysis:read", "analysis:save"})
TOKEN = "library-page-isolated-test-token-32chars"
ALICE = AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE, PAGE_SCOPE, "brand-a"}))
BOUND = {
    "result_refs": ["result_fixture_1"],
    "bindings": [{
        "result_ref": "result_fixture_1",
        "unit": "CNY 元",
        "time_range": {"start": "2026-04-30", "end": "2026-07-28"},
        "result_version": 1,
    }],
}


def _client():
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    access = PageResultAccess()
    access.put_snapshot(default_synthetic_snapshot())
    return TestClient(create_result_access_app(identities=registry, access=access)), {"Authorization": "Bearer " + TOKEN}


def test_result_http_read_cancel_and_forbidden_sql():
    client, headers = _client()
    denied = client.post(PREFIX + "/read", json={
        "request": {"op": "sql", "request_id": "req_sql", "result_ref": "result_fixture_1"},
        "manifest": BOUND,
    }, headers=headers)
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "BRIDGE_UNKNOWN_OP"
    read = client.post(PREFIX + "/read", json={
        "request": {"op": "data.read", "request_id": "req_1", "result_ref": "result_fixture_1", "mode": "summary"},
        "manifest": BOUND,
    }, headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["ok"] is True
    assert read.json()["result_ref"] == "result_fixture_1"
    cancel = client.post(PREFIX + "/cancel", json={"op": "data.cancel", "request_id": "req_1"}, headers=headers)
    assert cancel.status_code == 200
    blocked = client.post(PREFIX + "/read", json={
        "request": {"op": "data.read", "request_id": "req_1", "result_ref": "result_fixture_1", "mode": "summary"},
        "manifest": BOUND,
    }, headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "RESULT_UNAVAILABLE"


def test_result_routes_absent_on_competition_app_by_default():
    source = ast.parse((ROOT / "backend/analytics_competition_app.py").read_text(encoding="utf-8"))
    dumped = ast.dump(source)
    assert "page_result_access_router" in dumped
    gated = False
    for node in ast.walk(source):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "page_result_access"):
            continue
        if "page_result_access_router" in ast.unparse(node):
            gated = True
    assert gated is True


def test_result_routes_present_when_explicit(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    access = PageResultAccess()
    access.put_snapshot(default_synthetic_snapshot())
    directory = tmp_path / "pages"
    directory.mkdir(mode=0o700)
    app = create_page_app(identities=registry, page_state_dir=directory, result_access=access)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert any(PREFIX in path for path in paths)
    client = TestClient(app)
    state = client.post(PREFIX + "/binding-state", json={"manifest": {"bindings": [], "result_refs": []}},
                        headers={"Authorization": "Bearer " + TOKEN})
    assert state.status_code == 200
    assert state.json()["binding_state"] == "UNBOUND_SAMPLE"


def test_combined_page_app_can_host_result_access(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, ALICE)
    access = PageResultAccess()
    directory = tmp_path / "pages"
    directory.mkdir(mode=0o700)
    app = create_page_app(identities=registry, page_state_dir=directory, result_access=access)
    client = TestClient(app)
    seeded = client.post(PREFIX + "/snapshots", json=default_synthetic_snapshot(),
                         headers={"Authorization": "Bearer " + TOKEN})
    assert seeded.status_code == 201
    pages = client.get(PAGE_PREFIX + "/pages", headers={"Authorization": "Bearer " + TOKEN})
    assert pages.status_code == 200
    assert pages.json()["items"] == []
