"""Lightweight A3 HTTP bind tests. No real DuckDB, no main.py, no port 8000."""
from __future__ import annotations

import asyncio
import inspect
import io
import json
from unittest import mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.middleware.query_router import (
    QueryRouterMiddleware,
    competition_error_response,
    overlay_live_capabilities,
)
from backend.routers.audience import router as audience_router
from backend.routers.sampling import router as sampling_router

FACTS = {
    "year_label": "2026",
    "comp_year_label": "2025",
    "prev2_year_label": "2024",
    "metric_type": "GSV",
    "indicators": [
        {"field": "全店GSV", "kind": "money", "values_by_year": {"2026": 1.0, "2025": 1.0}, "yoy": 0.0},
    ],
    "channel_all": [],
    "channel_member": [],
}

TABLE = {
    "dimension": "channel",
    "mode": "mtd",
    "current_period": {"start": "2026-09-01", "end": "2026-09-08"},
    "comparison_period": {"start": "2025-09-01", "end": "2025-09-08"},
    "rows": [],
}


def _mini_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        user = request.headers.get("x-test-user")
        if user:
            request.state.username = user
        return await call_next(request)

    app.include_router(audience_router)
    app.include_router(sampling_router)
    return app


def _client() -> TestClient:
    return TestClient(_mini_app())


def test_classify_exact_readonly_posts_only():
    mw = QueryRouterMiddleware(lambda scope, receive, send: None)
    assert mw.classify("/api/v1/audience/summary", "GET") == "read"
    assert mw.classify("/api/v1/audience/summary", "POST") == "read"
    assert mw.classify("/api/v1/ad-hoc/two-year-overview", "POST") == "read"
    assert mw.classify("/api/v1/ad-hoc/new-old-customer", "POST") == "read"
    assert mw.classify("/api/v1/two-year-overview", "POST") == "read"
    assert mw.classify("/api/v1/new-old-customer", "POST") == "read"
    assert mw.classify("/api/v1/ad-hoc/export-excel", "POST") == "default"
    assert mw.classify("/api/v1/ad-hoc/daily-gsv", "POST") == "default"
    assert mw.classify("/api/v1/sampling/roi", "GET") == "read"
    assert mw.classify("/api/v1/sampling/roi", "POST") == "default"
    assert mw.classify("/api/v1/ad-hoc/ai-sandbox-execute", "POST") == "worker"
    assert mw.classify("/api/v1/auth/login", "POST") == "default"
    assert mw.classify("/api/v1/health", "GET") == "default"
    assert mw.classify("/api/v1/health/pool", "GET") == "default"
    assert mw.classify("/api/v1/customer-health/rfm-analysis", "GET") == "read"


def test_summary_forwards_period_not_folded_dates(monkeypatch):
    captured: dict = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return FACTS

    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", fake)
    res = _client().get(
        "/api/v1/audience/summary",
        params={"period": "WTD", "metric_type": "GSV"},
        headers={"X-Test-User": "alice"},
    )
    assert res.status_code == 200, res.text
    assert captured["period"] == "WTD"
    assert captured["start_date"] is None
    assert captured["end_date"] is None
    body = res.json()
    assert body["executed_windows"]["period"] == "WTD"
    assert body["executed_windows"]["cutoff_policy"] == "period_builder_start_minus_one"
    assert body["current_period"]["cutoff"] == body["executed_windows"]["cutoff"]
    assert body["integrity"]["complete"] is True
    assert body["result_ref"]["completeness"] == "COMPLETE"


def test_summary_rejects_gmv_and_inverted_dates(monkeypatch):
    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", lambda **k: FACTS)
    client = _client()
    gmv = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GMV", "period": "MTD"},
        headers={"X-Test-User": "alice"},
    )
    assert gmv.status_code == 422
    assert gmv.json()["error"]["param"] == "metric_type"
    assert gmv.json()["error"]["code"] == "INVALID_REQUEST"
    inverted = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "start_date": "2026-09-10", "end_date": "2026-09-01"},
        headers={"X-Test-User": "alice"},
    )
    assert inverted.status_code == 422
    assert inverted.json()["error"]["param"] == "end_date"


def test_summary_forwards_product_ids_and_rejects_silent_filters(monkeypatch):
    captured: dict = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return FACTS

    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", fake)
    client = _client()
    ok = client.get(
        "/api/v1/audience/summary",
        params=[("metric_type", "GSV"), ("period", "MTD"), ("product_ids", "p1"), ("product_ids", "p2")],
        headers={"X-Test-User": "alice"},
    )
    assert ok.status_code == 200, ok.text
    assert captured["product_ids"] == ["p1", "p2"]
    silent = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "period": "MTD", "sample_mode": "INCLUDE"},
        headers={"X-Test-User": "alice"},
    )
    assert silent.status_code == 422
    assert silent.json()["error"]["param"] == "sample_mode"
    posted = client.post(
        "/api/v1/audience/summary",
        json={"metric_type": "GSV", "period": "MTD", "product_ids": ["sku-1"], "timezone": "UTC"},
        headers={"X-Test-User": "alice"},
    )
    assert posted.status_code == 422
    assert posted.json()["error"]["param"] == "timezone"


def test_unauthenticated_and_cross_actor_result_ref(monkeypatch):
    monkeypatch.setattr("backend.routers.audience.calculate_audience_summary", lambda **k: FACTS)
    client = _client()
    denied = client.get("/api/v1/audience/summary", params={"metric_type": "GSV", "period": "MTD"})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "UNAUTHENTICATED"
    created = client.get(
        "/api/v1/audience/summary",
        params={"metric_type": "GSV", "period": "MTD"},
        headers={"X-Test-User": "alice"},
    )
    result_id = created.json()["result_ref"]["result_id"]
    other = client.get(
        f"/api/v1/audience/results/{result_id}",
        headers={"X-Test-User": "bob"},
    )
    assert other.status_code == 403
    assert other.json()["error"]["code"] == "FORBIDDEN"
    assert "alice" not in other.text
    owner = client.get(
        f"/api/v1/audience/results/{result_id}",
        headers={"X-Test-User": "alice"},
    )
    assert owner.status_code == 200
    assert owner.json()["integrity"]["checksum"] == created.json()["integrity"]["checksum"]
    assert owner.json()["integrity"]["complete"] is True


def test_live_catalog_marks_product_ids_and_filters_actor():
    visible = overlay_live_capabilities({"analysis:read"})
    product = next(item for item in visible if item["capability_id"] == "diag.product")
    assert product["support_status"] != "UNSUPPORTED"
    assert "product_ids" in product["http_mapping"]
    catalog = next(item for item in visible if item["capability_id"] == "catalog.http")
    assert catalog["http_mapping"] == "GET /api/v1/audience/capabilities"
    hidden = overlay_live_capabilities(set())
    assert all(item["capability_id"] != "diag.gsv" for item in hidden)
    client = _client()
    res = client.get("/api/v1/audience/capabilities", headers={"X-Test-User": "alice"})
    assert res.status_code == 200
    ids = {item["capability_id"] for item in res.json()["capabilities"]}
    assert "diag.gsv" in ids
    assert "diag.product" in ids


def test_table_default_gsv_member_only_and_custom_compare(monkeypatch):
    captured: dict = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return TABLE

    monkeypatch.setattr("backend.routers.audience.get_audience_table", fake)
    client = _client()
    gmv = client.get(
        "/api/v1/audience/table",
        params={"metric_type": "GMV"},
        headers={"X-Test-User": "alice"},
    )
    assert gmv.status_code == 422
    compare = client.get(
        "/api/v1/audience/table",
        params={"compare_start_date": "2025-01-01", "compare_end_date": "2025-01-31"},
        headers={"X-Test-User": "alice"},
    )
    assert compare.status_code == 422
    ok = client.get(
        "/api/v1/audience/table",
        params={"member_only": True, "metric_type": "GSV"},
        headers={"X-Test-User": "alice"},
    )
    assert ok.status_code == 200, ok.text
    assert captured["member_only"] is True
    assert captured["metric_type"] == "GSV"


def test_sampling_roi_rejects_exclude_low_price():
    res = _client().get("/api/v1/sampling/roi", params={"exclude_low_price": True})
    assert res.status_code == 422
    assert res.json()["error"]["param"] == "exclude_low_price"


def test_error_helpers_cover_429_and_503():
    limited = competition_error_response(
        http_status=429,
        code="RATE_LIMITED",
        message="Rate limit exceeded.",
        request_id="req_test_429",
        retryable=True,
        retry_after=60,
        param="Authorization",
        doc_ref="docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T08",
    )
    assert limited.status_code == 429
    assert limited.body
    payload = json.loads(limited.body)
    assert payload["error"]["retryable"] is True
    assert payload["error"]["retry_after"] == 60


def test_read_pool_timeout_returns_c0_503(monkeypatch):
    from backend.services import dual_conn

    def boom(timeout=5.0):
        raise dual_conn.ReadPoolTimeout("DuckDB read pool full, 请重试")

    monkeypatch.setattr(dual_conn, "get_read_connection", boom)
    mw = QueryRouterMiddleware(lambda scope, receive, send: None)

    async def scenario():
        messages = []

        async def send(message):
            messages.append(message)

        async def receive():
            return {"type": "http.disconnect"}

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/api/v1/audience/summary",
            "raw_path": b"/api/v1/audience/summary",
            "query_string": b"",
            "headers": [(b"x-request-id", b"req_test_503")],
            "client": ("127.0.0.1", 123),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        await mw(scope, receive, send)
        return messages

    messages = asyncio.run(scenario())
    start = next(item for item in messages if item["type"] == "http.response.start")
    assert start["status"] == 503
    body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
    payload = json.loads(body)
    assert payload["error"]["http_status"] == 503
    assert payload["error"]["retryable"] is True
    assert payload["error"]["code"] == "STATE_UNAVAILABLE"
    assert "read pool full" in payload["error"]["message"].lower() or "ReadPoolTimeout" in payload["error"]["message"]


def test_pooled_connection_close_does_not_close_others(monkeypatch, tmp_path):
    import duckdb

    from backend.db.connection import close_connection, get_connection
    from backend.services import dual_conn

    path = tmp_path / "a3-pool.duckdb"
    seed = duckdb.connect(str(path))
    seed.execute("CREATE TABLE ping(i INTEGER)")
    seed.execute("INSERT INTO ping VALUES (1)")
    seed.close()
    monkeypatch.setattr(dual_conn, "DUCKDB_PATH", path)
    dual_conn.close_all_connections()
    try:
        with dual_conn.read_request_context():
            wrapped = get_connection()
            assert wrapped._pooled is True
            wrapped.close()
            assert wrapped.execute("SELECT i FROM ping").fetchone()[0] == 1
            close_connection()
            assert wrapped.execute("SELECT 1").fetchone()[0] == 1
    finally:
        dual_conn.close_all_connections()


def test_mcp_truncated_output_is_not_complete_success():
    from mcp_servers.fuqing_adhoc import server as server_mod

    with mock.patch.object(
        server_mod,
        "_run_cli",
        return_value={"returncode": 0, "stdout": "x" * 100 + "\n... [truncated]", "stderr": ""},
    ):
        resp = server_mod._handle_call_tool(
            1,
            {"name": "daily_gsv", "arguments": {"start": "2026-01-01", "end": "2026-01-02"}},
        )
    assert resp["result"]["isError"] is True
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["completeness"] == "FAILED"
    assert payload["truncated"] is True
    assert "/api/v1/audience/summary" in payload["http_fallback"]


def test_mcp_write_message_does_not_slice_json(monkeypatch):
    from mcp_servers.fuqing_adhoc import server as server_mod

    buf = io.BytesIO()

    class _Stdout:
        buffer = buf

        def flush(self):
            return None

    monkeypatch.setattr(server_mod.sys, "stdout", _Stdout())
    huge = {"jsonrpc": "2.0", "id": 1, "result": {"blob": "中文" * (server_mod.MAX_CONTENT_LENGTH // 2)}}
    server_mod._write_message(huge)
    raw = buf.getvalue()
    assert raw.endswith(b"\n")
    parsed = json.loads(raw.decode("utf-8"))
    assert parsed["error"]["code"] == -32603
    src = inspect.getsource(server_mod._write_message)
    assert "body[:MAX_CONTENT_LENGTH]" not in src


def test_get_read_connection_timeout_default_unchanged():
    from backend.services import dual_conn

    sig = inspect.signature(dual_conn.get_read_connection)
    assert sig.parameters["timeout"].default == 5.0
