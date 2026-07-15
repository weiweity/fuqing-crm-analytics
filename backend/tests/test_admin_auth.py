"""Sprint 205+ Admin Upload Sprint 1: admin auth 覆盖.

职责描述 (不写固定 case 数量, 避免后续漂移):
- is_admin_username SSOT (True / False / env 三件套 / 边界 case)
- POST /auth/login response 含 is_admin
- GET /auth/me response 含 is_admin
- auth_middleware 写 request.state.username (admin 上传依赖, 间接验证)
- login_request ClaimRequestOut 含 is_admin

跟 L4.50 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套, 跟 L4.88
VALID_CREDENTIALS race 1:1 stable 永久规则化沿用 (conftest 已 autouse).
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"login {username} 失败: {resp.status_code} {resp.text}"
    return resp.json()


def test_is_admin_username_true_for_admin():
    """FQ_CRM_ADMINS=admin (conftest fixture 默认) → admin → True"""
    from backend.routers.auth import is_admin_username
    os.environ["FQ_CRM_ADMINS"] = "admin"
    assert is_admin_username("admin") is True


def test_is_admin_username_false_for_non_admin():
    """FQ_CRM_ADMINS=admin → fqsw → False"""
    from backend.routers.auth import is_admin_username
    os.environ["FQ_CRM_ADMINS"] = "admin"
    assert is_admin_username("fqsw") is False
    assert is_admin_username("unknown") is False


def test_is_admin_username_respects_env_var():
    """边界: 多个 admin / 空格 / 空 / unset / None"""
    from backend.routers.auth import is_admin_username
    # 多 admin
    os.environ["FQ_CRM_ADMINS"] = "admin,fqsw"
    assert is_admin_username("admin") is True
    assert is_admin_username("fqsw") is True
    assert is_admin_username("fqsw_admin") is False  # 精确匹配, 模糊不命中
    # 空格容忍
    os.environ["FQ_CRM_ADMINS"] = "admin , fqsw , "
    assert is_admin_username("admin") is True
    assert is_admin_username("fqsw") is True
    # 空字符串
    os.environ["FQ_CRM_ADMINS"] = ""
    assert is_admin_username("admin") is False
    # unset
    os.environ.pop("FQ_CRM_ADMINS", None)
    assert is_admin_username("admin") is False
    # None / 空白 username
    assert is_admin_username(None) is False
    assert is_admin_username("") is False
    assert is_admin_username("   ") is False


def test_login_response_includes_is_admin(client):
    """POST /api/v1/auth/login response 含 is_admin 字段"""
    payload = _login(client, "admin", "123456")
    assert "is_admin" in payload, f"login response 缺 is_admin: {payload}"
    assert payload["is_admin"] is True
    # 非 admin 账号
    payload = _login(client, "fqsw", "fqsw888")
    assert payload["is_admin"] is False


def test_me_response_includes_is_admin(client):
    """GET /api/v1/auth/me response 含 is_admin 字段"""
    payload = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}).json()
    token = payload["token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


def test_middleware_sets_request_state_username(client):
    """auth_middleware 把 username 写到 request.state.
    间接验证: GET /upload-config 需要 admin + 401/403 路径不同.
    """
    # 1. 无 token → 401 (不走 middleware 进 router)
    resp = client.get("/api/v1/admin/upload-config")
    assert resp.status_code == 401, f"无 token 应 401, 实得 {resp.status_code}"
    # 2. fqsw token (非 admin) → 403 (middleware 写 username, require_admin 拒)
    fqsw_payload = client.post("/api/v1/auth/login", json={"username": "fqsw", "password": "fqsw888"}).json()
    resp = client.get(
        "/api/v1/admin/upload-config",
        headers={"Authorization": f"Bearer {fqsw_payload['token']}"},
    )
    assert resp.status_code == 403, f"非 admin 应 403, 实得 {resp.status_code} {resp.text}"
    assert resp.json()["detail"]["code"] == "ADMIN_REQUIRED"
    # 3. admin token → 200 (中间件放行 + require_admin 通过)
    admin_payload = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}).json()
    resp = client.get(
        "/api/v1/admin/upload-config",
        headers={"Authorization": f"Bearer {admin_payload['token']}"},
    )
    assert resp.status_code == 200, f"admin 应 200, 实得 {resp.status_code} {resp.text}"


def test_login_request_claim_response_includes_is_admin(client):
    """申请+批准+claim 流程: claim response 含 is_admin.
    完整 E2E 路径已在 L4.85 测试覆盖; 此 case 验证 schema 字段存在性 + 边界."""
    from backend.routers.login_request import ClaimRequestOut
    fields = ClaimRequestOut.model_fields.keys()
    assert "is_admin" in fields, f"ClaimRequestOut 缺 is_admin: {fields}"
    assert "token" in fields
    assert "username" in fields