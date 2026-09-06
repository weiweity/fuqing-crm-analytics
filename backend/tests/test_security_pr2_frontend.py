"""PR2 security regressions: logout body token, require_admin, CSP Report-Only.

不输出任何真实业务数据。token 仅用于内存会话断言。
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import auth as auth_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    """空 DuckDB：customer-health/rfm 走 read pool 时需要文件存在。"""
    db = tmp_path / "pr2.duckdb"
    duckdb.connect(str(db)).close()
    # dual_conn / config 两侧路径对齐
    monkeypatch.setattr("backend.config.DUCKDB_PATH", db)
    try:
        import backend.services.dual_conn as dual

        monkeypatch.setattr(dual, "DUCKDB_PATH", db)
    except Exception:
        pass
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_tokens():
    auth_module.ACTIVE_TOKENS.clear()
    os.environ.setdefault("FQ_CRM_ADMINS", "admin")
    yield
    auth_module.ACTIVE_TOKENS.clear()


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["token"]


# ── logout: body / bearer only；query token 拒绝 ──


def test_logout_via_json_body_evicts_token(client):
    token = _login(client, "admin", "123456")
    assert token in auth_module.ACTIVE_TOKENS
    resp = client.post("/api/v1/auth/logout", json={"token": token})
    assert resp.status_code == 200
    assert resp.json().get("success") is True
    assert token not in auth_module.ACTIVE_TOKENS


def test_logout_via_bearer_header(client):
    token = _login(client, "admin", "123456")
    resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert token not in auth_module.ACTIVE_TOKENS


def test_logout_query_token_rejected(client):
    """query token 已移除：必须 400，且 token 仍有效。"""
    token = _login(client, "admin", "123456")
    resp = client.post(f"/api/v1/auth/logout?token={token}")
    assert resp.status_code == 400
    assert token in auth_module.ACTIVE_TOKENS


def test_logout_openapi_declares_json_body_and_no_query_token():
    operation = app.openapi()["paths"]["/api/v1/auth/logout"]["post"]
    query_names = {
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query"
    }
    assert "token" not in query_names
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    assert "LogoutRequest" in str(body)


# ── require_admin unit ──


def test_require_admin_unit():
    from starlette.requests import Request
    from backend.routers.auth import require_admin, is_admin_username

    os.environ["FQ_CRM_ADMINS"] = "admin"
    assert is_admin_username("admin") is True
    assert is_admin_username("fqsw") is False

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    req = Request(scope)
    req.state.username = "fqsw"
    with pytest.raises(Exception) as ei:
        require_admin(req)
    assert getattr(ei.value, "status_code", None) == 403

    req.state.username = "admin"
    assert require_admin(req) == "admin"


# ── require_admin: health history/audit + rfm cache ──


def test_config_history_requires_admin(client):
    r = client.get("/api/v1/customer-health/config/history")
    assert r.status_code == 401

    os.environ["FQ_CRM_ADMINS"] = "admin"
    fqsw_token = _login(client, "fqsw", "fqsw888")
    r = client.get(
        "/api/v1/customer-health/config/history",
        headers={"Authorization": f"Bearer {fqsw_token}"},
    )
    assert r.status_code == 403

    admin_token = _login(client, "admin", "123456")
    r = client.get(
        "/api/v1/customer-health/config/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert "history" in r.json()


def test_config_audit_log_requires_admin(client):
    os.environ["FQ_CRM_ADMINS"] = "admin"
    fqsw_token = _login(client, "fqsw", "fqsw888")
    r = client.get(
        "/api/v1/customer-health/config/audit-log",
        headers={"Authorization": f"Bearer {fqsw_token}"},
    )
    assert r.status_code == 403

    admin_token = _login(client, "admin", "123456")
    r = client.get(
        "/api/v1/customer-health/config/audit-log",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert "logs" in r.json()


def test_rfm_cache_invalidate_requires_admin(client):
    os.environ["FQ_CRM_ADMINS"] = "admin"
    r = client.post("/api/v1/rfm/cache/invalidate")
    assert r.status_code == 401

    fqsw_token = _login(client, "fqsw", "fqsw888")
    r = client.post(
        "/api/v1/rfm/cache/invalidate",
        headers={"Authorization": f"Bearer {fqsw_token}"},
    )
    assert r.status_code == 403

    admin_token = _login(client, "admin", "123456")
    r = client.post(
        "/api/v1/rfm/cache/invalidate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # admin 通过鉴权后：可能 200（空 cache）或 5xx（无业务表）；鉴权层必须不是 401/403
    assert r.status_code not in (401, 403)


@pytest.mark.parametrize(
    "path",
    (
        "/metrics",
        "/api/v1/health/metrics",
        "/api/v1/health/db_size",
        "/api/v1/health/manifest",
        "/api/v1/health/pool",
    ),
)
def test_ops_health_endpoints_require_admin(client, path):
    assert client.get(path).status_code == 401

    fqsw_token = _login(client, "fqsw", "fqsw888")
    denied = client.get(
        path,
        headers={"Authorization": f"Bearer {fqsw_token}"},
    )
    assert denied.status_code == 403

    admin_token = _login(client, "admin", "123456")
    allowed = client.get(
        path,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    if path.endswith("/metrics"):
        assert allowed.headers["content-type"].startswith("text/plain")
        assert "fq_query_" in allowed.text
    else:
        assert "path" not in allowed.json()
        assert "error" not in allowed.json()


# ── CSP (enforced) ──


def test_csp_enforced_header_present(client):
    r = client.get("/api/v1/health")
    csp = r.headers.get("content-security-policy") or r.headers.get(
        "Content-Security-Policy"
    )
    assert csp, f"missing CSP header: {dict(r.headers)}"
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_frontend_has_no_vite_health_api_key_usage():
    """静态门禁：浏览器代码不得读取 VITE_HEALTH_API_KEY 环境变量。"""
    root = Path(__file__).resolve().parents[2] / "frontend-vue3" / "src"
    offenders = []
    for path in root.rglob("*"):
        if path.suffix not in {".ts", ".vue", ".js", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "import.meta.env.VITE_HEALTH_API_KEY" in text or "VITE_HEALTH_API_KEY ||" in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"VITE_HEALTH_API_KEY still used: {offenders}"


def test_frontend_preserves_session_during_navigation_and_reload():
    """浏览器 unload 生命周期不得注销仍需在刷新后复用的 token。"""
    main_ts = (
        Path(__file__).resolve().parents[2] / "frontend-vue3" / "src" / "main.ts"
    ).read_text(encoding="utf-8")
    assert "logout?token=" not in main_ts
    assert "beforeunload" not in main_ts
    assert "sendBeacon" not in main_ts

    nav_bar = (
        Path(__file__).resolve().parents[2]
        / "frontend-vue3"
        / "src"
        / "components"
        / "NavBar.vue"
    ).read_text(encoding="utf-8")
    assert "await authStore.logout()" in nav_bar
