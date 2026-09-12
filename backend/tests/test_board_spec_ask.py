"""BoardSpec ask HTTP: suggestion only, never writes the board."""

from fastapi.testclient import TestClient

from backend.analytics_competition_app import create_competition_app
from backend.services.analytics.access import AnalyticsPrincipal, B0IdentityRegistry

TOKEN = "b0-competition-http-token-32chars-min"
CAPS = frozenset({"analysis:read", "dashboard:read"})
SCOPE = frozenset({"channel-followup-fixture"})


def _client(auth=True):
    identities = B0IdentityRegistry()
    identities.grant(TOKEN, AnalyticsPrincipal("alice", CAPS, SCOPE))
    app = create_competition_app(identities=identities)
    headers = {"Authorization": f"Bearer {TOKEN}"} if auth else {}
    return TestClient(app, headers=headers)


def test_ask_set_title_from_quoted_text():
    response = _client().post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_retail_gsv_2026_08",
        "version": 1,
        "block_id": "b3",
        "ask": "把标题改成「本月渠道占比」",
    })
    assert response.status_code == 200
    assert response.json()["patch"] == {
        "block_id": "b3",
        "base_version": 1,
        "op": "set_title",
        "title": "本月渠道占比",
    }


def test_ask_set_kind_line():
    response = _client().post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_x",
        "version": 2,
        "block_id": "b1",
        "ask": "加一块折线",
    })
    assert response.status_code == 200
    assert response.json()["patch"]["op"] == "set_kind"
    assert response.json()["patch"]["kind"] == "LINE"


def test_ask_unauthenticated():
    response = _client(auth=False).post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_x", "version": 1, "block_id": "b1", "ask": "标题",
    })
    assert response.status_code == 401


def test_ask_refuses_facts_question():
    response = _client().post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_x", "version": 1, "block_id": "b1", "ask": "本月 GSV 是多少",
        "metric_ref": "retail_gsv", "source_result_id": "r1",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ASK_FACTS"


def test_ask_set_metric_ref():
    response = _client().post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_x", "version": 1, "block_id": "b1", "ask": "口径换成零售 GSV",
    })
    assert response.status_code == 200
    assert response.json()["patch"]["op"] == "set_metric_ref"
    assert response.json()["patch"]["metric_ref"] == "retail_gsv"


def test_ask_empty_does_not_invent_patch():
    response = _client().post("/api/v1/analytics/board-spec/ask", json={
        "board_id": "board_x", "version": 1, "block_id": "b1", "ask": "  ",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PATCH_TITLE"
