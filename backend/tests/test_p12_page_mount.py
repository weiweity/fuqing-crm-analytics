"""P12: page_documents router mounts only when page_state_dir is explicit.

Competition-app import pulls archived CRM dotenv; B0 pytest cannot load it.
Gate checks read the source with AST. HTTP uses create_page_app.
"""
import ast
from pathlib import Path

from fastapi.testclient import TestClient

from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.page_documents_routes import PREFIX, create_page_app
from backend.services.analytics.page_result_access_routes import PREFIX as RESULT_PREFIX

ROOT = Path(__file__).resolve().parents[2]
CAPS = frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"})
TOKEN = "library-page-isolated-test-token-32chars"


def _competition_source():
    return ast.parse((ROOT / "backend/analytics_competition_app.py").read_text(encoding="utf-8"))


def _if_gates(flag: str, router: str) -> bool:
    for node in ast.walk(_competition_source()):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == flag):
            continue
        if not any(isinstance(op, ast.IsNot) for op in test.ops):
            continue
        if not any(isinstance(item, ast.Constant) and item.value is None for item in test.comparators):
            continue
        if router in ast.unparse(node):
            return True
    return False


def test_page_routes_absent_without_page_state_dir():
    assert _if_gates("page_state_dir", "page_documents_router")
    dumped = ast.dump(_competition_source())
    assert "page_documents_router" in dumped


def test_result_routes_absent_without_explicit_access():
    assert _if_gates("page_result_access", "page_result_access_router")


def test_page_routes_present_with_page_state_dir(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE, "brand-a"})))
    directory = tmp_path / "pages"
    directory.mkdir(mode=0o700)
    app = create_page_app(identities=registry, page_state_dir=directory)
    client = TestClient(app)
    response = client.get(PREFIX + "/pages", headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200
    assert response.json()["items"] == []
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.startswith(RESULT_PREFIX) for path in paths)
