"""Isolated page HTTP launcher (scripts/dsh-dev). Never the live 6677 web.

The node launcher owns a Python uvicorn child; these tests verify the server
side directly (mount, auth, CORS, port refusal) without spawning node, plus
the file contract that keeps the launcher from ever binding 6677.
"""
from __future__ import annotations

from pathlib import Path
import re

from fastapi.testclient import TestClient

from backend.services.analytics.page_documents_routes import PREFIX as PAGE_PREFIX
from backend.services.analytics.page_result_access_routes import PREFIX as RESULT_PREFIX

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "scripts/dsh-dev/page_http_server.py"
LAUNCHER = ROOT / "scripts/dsh-dev/page-http.mjs"


def _server_app(state_dir: Path, token: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location("lane_h_page_http_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_app(state_dir=state_dir, token=token)


def _token() -> str:
    return "lane-h-isolated-page-http-token-32ch"


def _client(state_dir: Path, token: str = _token()) -> TestClient:
    directory = state_dir / "pages"
    directory.mkdir(mode=0o700)
    return TestClient(_server_app(directory, token))


def test_server_mounts_documents_and_result_access_with_explicit_state_dir(tmp_path):
    token = _token()
    client = _client(tmp_path, token)
    headers = {"Authorization": "Bearer " + token}
    pages = client.get(PAGE_PREFIX + "/pages", headers=headers)
    assert pages.status_code == 200
    assert pages.json()["items"] == []
    unauth = client.get(PAGE_PREFIX + "/pages")
    assert unauth.status_code == 401
    paths = {getattr(route, "path", "") for route in client.app.routes}
    assert any(RESULT_PREFIX in path for path in paths)
    sqlite_file = tmp_path / "pages" / "page_documents.sqlite3"
    assert sqlite_file.exists()


def test_server_refuses_host_other_than_loopback_and_live_port(tmp_path, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("lane_h_page_http_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import sys

    argv = sys.argv
    sys.argv = ["page_http_server.py", "--host", "0.0.0.0", "--port", "18091",
                "--state-dir", str(tmp_path / "pages")]
    try:
        assert module.main() == 2
    finally:
        sys.argv = argv
    sys.argv = ["page_http_server.py", "--host", "127.0.0.1", "--port", "6677",
                "--state-dir", str(tmp_path / "pages")]
    try:
        assert module.main() == 2
    finally:
        sys.argv = argv
    sys.argv = ["page_http_server.py", "--host", "127.0.0.1", "--port", "18091",
                "--state-dir", str(tmp_path / "pages")]
    try:
        assert module.main() == 2  # missing PAGE_DOCUMENTS_HTTP_TOKEN in test env
    finally:
        sys.argv = argv


def test_cors_allows_the_live_web_origin_for_cross_origin_bridge(tmp_path):
    client = _client(tmp_path)
    preflight = client.options(
        PAGE_PREFIX + "/pages",
        headers={
            "Origin": "http://127.0.0.1:6677",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:6677"
    foreign = client.options(
        PAGE_PREFIX + "/pages",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert foreign.headers.get("access-control-allow-origin") is None


def test_result_bridge_read_and_forbidden_sql_op(tmp_path):
    from backend.services.analytics.page_result_access import default_synthetic_snapshot

    client = _client(tmp_path)
    headers = {"Authorization": "Bearer " + _token()}
    seeded = client.post(RESULT_PREFIX + "/snapshots",
                         json=default_synthetic_snapshot(owner="page_http_local"),
                         headers=headers)
    assert seeded.status_code == 201
    read = client.post(RESULT_PREFIX + "/read", json={
        "request": {"op": "data.read", "request_id": "req_test_1",
                    "result_ref": "result_fixture_1", "mode": "summary"},
        "manifest": {"result_refs": ["result_fixture_1"], "bindings": []},
    }, headers=headers)
    assert read.status_code == 200
    assert read.json()["ok"] is True
    denied = client.post(RESULT_PREFIX + "/read", json={
        "request": {"op": "sql", "request_id": "req_sql", "result_ref": "result_fixture_1"},
        "manifest": {"result_refs": ["result_fixture_1"], "bindings": []},
    }, headers=headers)
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "BRIDGE_UNKNOWN_OP"


def test_launcher_source_refuses_6677_and_requires_state_dir():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "6677" in source
    assert re.search(r"assert\.notEqual\(port, 6677", source)
    # The runtime binding decision lives in the Python server body, not its
    # module docstring; check below the docstring.
    server_body = SERVER.read_text(encoding="utf-8").split('"""', 2)[2]
    assert "page_state_dir=state_dir" in server_body
    assert "result_access=PageResultAccess()" in server_body
    # The page app factory is the shared production one, not a second contract.
    assert "create_page_app" in server_body
    assert "BoardSpec" not in server_body


def test_default_port_is_not_6677_or_browser_blocked():
    source = LAUNCHER.read_text(encoding="utf-8")
    match = re.search(r"PAGE_HTTP_DEFAULT_PORT = (\d+)", source)
    assert match, "launcher must pin a default port constant"
    port = int(match.group(1))
    assert port != 6677
    assert port not in {8000, 5173, 4325, 4326, 4327, 4328, 4329, 14327, 15173}
