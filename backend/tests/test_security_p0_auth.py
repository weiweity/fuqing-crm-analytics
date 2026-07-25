"""P0 认证与登录安全回归 (PR1).

覆盖:
- 未登录保护接口 401
- 畸形 Host 不改变认证安全判断 (或被 TrustedHost 拒绝)
- 认证失败时业务 endpoint 不执行
- 认证与限流 path 同源 (ASGI scope path)
- bcrypt 72/73 字节与 Unicode
- 随机用户名洪泛后状态表容量受控
- 已知/未知账号响应状态与格式一致
- 不同 IP 不因组合外失败锁死真实账号
- 不可信 X-Forwarded-For 不当作 client IP
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import _asgi_path, app
from backend.routers import auth as auth_module


@pytest.fixture
def client():
    return TestClient(app)


def _login_ok(client: TestClient, username: str = "admin", password: str = "123456") -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


# ── A. Host / path / 认证中间件 ─────────────────────────────────


def test_unauthenticated_protected_endpoint_returns_401(client: TestClient):
    resp = client.get("/api/v1/core/summary")
    assert resp.status_code == 401
    assert resp.json().get("detail")


def test_malformed_host_does_not_bypass_auth(client: TestClient):
    """畸形/非法 Host 不得把受保护路径变成白名单路径。

    TrustedHost 会 400；即便放行，仍须 401（无 token）。
    """
    resp = client.get(
        "/api/v1/core/summary",
        headers={"Host": "evil.example\r\nX-Injected: 1"},
    )
    assert resp.status_code in (400, 401)
    if resp.status_code == 401:
        assert "detail" in resp.json()


def test_disallowed_host_rejected_when_trusted_host_enabled(client: TestClient):
    resp = client.get("/api/v1/health", headers={"Host": "evil.attacker.example"})
    assert resp.status_code == 400


def test_auth_failure_does_not_execute_endpoint(client: TestClient):
    """无效 token 时不得进入业务 handler（用状态侧写验证：无 username 注入）。"""
    seen = {"called": False}

    @app.get("/api/v1/_test_security_probe_never")
    def _probe(request):  # pragma: no cover - must not run
        seen["called"] = True
        return {"ok": True}

    try:
        resp = client.get(
            "/api/v1/_test_security_probe_never",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
        assert seen["called"] is False
    finally:
        # 清理动态路由，避免污染后续用例
        app.router.routes = [
            r
            for r in app.router.routes
            if getattr(r, "path", None) != "/api/v1/_test_security_probe_never"
        ]


def test_asgi_path_helper_uses_scope_not_url(client: TestClient):
    """_asgi_path 读取 scope['path']。"""

    class _FakeReq:
        scope = {"path": "/api/v1/auth/login"}
        url = type("U", (), {"path": "/tampered/path"})()

    assert _asgi_path(_FakeReq()) == "/api/v1/auth/login"


def test_auth_and_rate_limit_share_scope_path_bypass(client: TestClient):
    """login 路径对认证与限流均 bypass，且均基于 scope path。"""
    # 未登录 login 可达（非 401）
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password-xxx"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("detail") == "账号或密码错误"

    # health 无 token 可达
    health = client.get("/api/v1/health")
    assert health.status_code == 200


# ── B. 登录 DoS / 枚举 / bcrypt ─────────────────────────────────


def test_known_and_unknown_account_same_401_shape(client: TestClient):
    known = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "definitely-wrong"},
    )
    unknown = client.post(
        "/api/v1/auth/login",
        json={"username": "no_such_user_xyz", "password": "definitely-wrong"},
    )
    assert known.status_code == 401
    assert unknown.status_code == 401
    assert known.json() == unknown.json()
    assert known.json()["detail"] == "账号或密码错误"


def test_bcrypt_72_byte_password_accepted_when_configured(client: TestClient, monkeypatch):
    """正好 72 UTF-8 字节的密码可校验（不抛 ValueError）。"""
    pwd_72 = "a" * 72
    assert len(pwd_72.encode("utf-8")) == 72
    hashed = auth_module.bcrypt.hashpw(
        pwd_72.encode("utf-8"), auth_module.bcrypt.gensalt(rounds=4)
    ).decode()
    auth_module.VALID_CREDENTIALS["edge72"] = hashed
    try:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "edge72", "password": pwd_72},
        )
        # 可能 200 或 409（若 active）；不得 500
        assert resp.status_code in (200, 409)
    finally:
        auth_module.VALID_CREDENTIALS.pop("edge72", None)


def test_bcrypt_73_byte_password_returns_401_not_500(client: TestClient):
    pwd_73 = "a" * 73
    assert len(pwd_73.encode("utf-8")) == 73
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": pwd_73},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "账号或密码错误"


def test_bcrypt_unicode_password_byte_limit(client: TestClient):
    """多字节 Unicode：按 UTF-8 字节计，超 72 返回统一 401。"""
    # 每个中文 3 字节；25 字 = 75 字节 > 72
    pwd = "密" * 25
    assert len(pwd.encode("utf-8")) > 72
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": pwd},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "账号或密码错误"


def test_username_max_64_and_charset(client: TestClient):
    long_name = "a" * 65
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": long_name, "password": "x"},
    )
    assert resp.status_code == 422

    bad_chars = client.post(
        "/api/v1/auth/login",
        json={"username": "admin;drop", "password": "x"},
    )
    assert bad_chars.status_code == 422


def test_random_username_flood_state_capacity_bounded(client: TestClient, monkeypatch):
    """随机用户名洪泛后 _LOGIN_ATTEMPTS 容量受 LOGIN_STATE_MAX_ENTRIES 约束。"""
    monkeypatch.setattr(auth_module, "LOGIN_STATE_MAX_ENTRIES", 64)
    # 缩小 IP 阈值，避免先触发 IP 锁导致无法写满 combo 表
    monkeypatch.setattr(auth_module, "MAX_IP_FAIL_ATTEMPTS", 10_000)

    auth_module._LOGIN_ATTEMPTS.clear()
    auth_module._IP_LOGIN_ATTEMPTS.clear()

    for i in range(200):
        client.post(
            "/api/v1/auth/login",
            json={"username": f"flooduser{i}", "password": "x"},
        )

    assert len(auth_module._LOGIN_ATTEMPTS) <= 64
    assert len(auth_module._IP_LOGIN_ATTEMPTS) <= 64


def test_different_ip_does_not_lock_real_account_for_legit_ip(client: TestClient):
    """攻击 IP 锁组合不影响另一 IP 的合法登录。"""
    # 模拟攻击者 IP 打满 admin
    with patch.object(auth_module, "_get_client_ip", return_value="10.0.0.66"):
        for _ in range(auth_module.MAX_FAIL_ATTEMPTS):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrong"},
            )
            assert r.status_code in (401, 429)

        locked = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "123456"},
        )
        assert locked.status_code == 429

    # 合法 IP（TestClient 默认）仍可登录
    ok = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert ok.status_code == 200, ok.text


def test_xff_not_trusted_by_default(client: TestClient, monkeypatch):
    monkeypatch.delenv("FQ_TRUST_PROXY", raising=False)
    # 即使带 XFF，默认仍用 testclient host；不会因伪造 XFF 绕过组合锁
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        "client": ("9.9.9.9", 12345),
        "server": ("testserver", 80),
    }
    req = Request(scope)
    ip = auth_module._get_client_ip(req)
    assert ip == "9.9.9.9"


def test_xff_trusted_when_proxy_mode(monkeypatch):
    monkeypatch.setenv("FQ_TRUST_PROXY", "1")
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")],
        "client": ("9.9.9.9", 12345),
        "server": ("testserver", 80),
    }
    req = Request(scope)
    assert auth_module._get_client_ip(req) == "1.2.3.4"


def test_login_request_shares_combo_lockout(client: TestClient):
    """与既有 handoff 测试一致：login + login-request 共享组合锁定。"""
    auth_module.ACTIVE_TOKENS["admin-token-a"] = (
        "admin",
        auth_module.datetime.now(),
    )
    for _ in range(auth_module.MAX_FAIL_ATTEMPTS - 1):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    fifth = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "wrong"},
    )
    locked = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert fifth.status_code == 401
    assert locked.status_code == 429
