"""P12: page_documents router mounts only when page_state_dir is explicit."""
from fastapi.testclient import TestClient

from backend.analytics_competition_app import create_competition_app
from backend.contracts.competition_computed import DATA_SCOPE
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry
from backend.services.analytics.page_documents_routes import PREFIX

CAPS = frozenset({"analysis:read", "analysis:save", "dashboard:read", "dashboard:update"})
TOKEN = "library-page-isolated-test-token-32chars"


def test_page_routes_absent_without_page_state_dir():
    app = create_competition_app()
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.startswith(PREFIX) for path in paths)


def test_page_routes_present_with_page_state_dir(tmp_path):
    registry = B0IdentityRegistry()
    registry.grant(TOKEN, AnalyticsPrincipal("alice", CAPS, frozenset({DATA_SCOPE, "brand-a"})))
    directory = tmp_path / "pages"
    directory.mkdir(mode=0o700)
    app = create_competition_app(identities=registry, page_state_dir=directory)
    client = TestClient(app)
    response = client.get(PREFIX + "/pages", headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200
    assert response.json()["items"] == []
