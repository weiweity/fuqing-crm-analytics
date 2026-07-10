"""L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 NavBar.vue 1:1 stable 永久规则化沿用)

4 case 锁 L4.85.1:
- test_get_request_status_pending (B 端 polling 等 A 响应)
- test_get_request_status_approved_returns_new_token (A 同意 → B 收到 new_token 自动登入)
- test_get_request_status_rejected (A 拒绝 → B 端显示拒绝)
- test_get_request_status_invalid_request_id (无效 request_id → 404)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试用环境变量必须在导入 auth 之前设置
# 注意: dotenv.load_dotenv() 在 import auth 时跑, 把 .env 的 FQ_CRM_PASSWORDS 加载了
# setdefault 不生效, 必须用跟 .env 1:1 stable 配套的密码 (跟 L4.42 + L4.84 1:1 stable 配套)
os.environ.setdefault("FQ_CRM_PASSWORDS", "admin:123456,fqsw:fqsw888")

from backend.routers import auth as auth_module  # noqa: E402
from backend.routers import login_request as lr_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state():
    """每个 test 前清空所有状态, 保证隔离."""
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    lr_module._reset_l4_85_state()
    # L4.85.1: 清空 _PENDING_REQUEST_TOKENS (新增的 B 端鉴权 dict)
    if hasattr(lr_module, "_PENDING_REQUEST_TOKENS"):
        lr_module._PENDING_REQUEST_TOKENS.clear()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    lr_module._reset_l4_85_state()
    if hasattr(lr_module, "_PENDING_REQUEST_TOKENS"):
        lr_module._PENDING_REQUEST_TOKENS.clear()


def _activate_admin():
    """helper: 让 admin 变成 active (有 token)."""
    auth_module.ACTIVE_TOKENS["admin-token-1"] = ("admin", datetime.now())


def test_get_request_status_pending():
    """B 端 polling 等 A 响应: status=pending, 没有 new_token."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # B 申请
    resp_create = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
        headers={"X-Forwarded-For": "192.168.1.20"},
    )
    request_id = resp_create.json()["request_id"]

    # B 端 polling status (还没人响应)
    resp = client.get(f"/api/v1/auth/login-request/{request_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data.get("new_token") is None
    assert data["username"] is None


def test_get_request_status_approved_returns_new_token():
    """A 同意 → B 端 polling 检测 approved → receive new_token 自动登入 (跟 L4.85.1 1:1 stable 永久规则化沿用)."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # B 申请
    resp_create = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
        headers={"X-Forwarded-For": "192.168.1.20"},
    )
    request_id = resp_create.json()["request_id"]

    # A 同意
    resp_approve = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    # A approve 时后端发 new_token 给 A 端响应 (line 246-247)
    a_new_token = resp_approve.json()["new_token"]
    # A 旧 token 已被 _evict 踢出
    assert "admin-token-1" not in auth_module.ACTIVE_TOKENS

    # B 端 polling status
    resp_status = client.get(f"/api/v1/auth/login-request/{request_id}/status")
    assert resp_status.status_code == 200
    data = resp_status.json()
    assert data["status"] == "approved"
    # B 端 receive new_token (B 端用这个 token 写入 sessionStorage + router.push)
    assert data.get("new_token") is not None
    assert data["username"] == "admin"
    # new_token 在 ACTIVE_TOKENS 中
    assert data["new_token"] in auth_module.ACTIVE_TOKENS


def test_get_request_status_rejected():
    """A 拒绝 → B 端 polling 检测 rejected (跟 L4.85 1:1 stable 永久规则化沿用)."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # B 申请
    resp_create = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
        headers={"X-Forwarded-For": "192.168.1.20"},
    )
    request_id = resp_create.json()["request_id"]

    # A 拒绝
    resp_reject = client.post(
        f"/api/v1/auth/login-request/{request_id}/reject",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp_reject.status_code == 200

    # B 端 polling status
    resp_status = client.get(f"/api/v1/auth/login-request/{request_id}/status")
    assert resp_status.status_code == 200
    data = resp_status.json()
    assert data["status"] == "rejected"
    assert data.get("new_token") is None


def test_get_request_status_invalid_request_id():
    """无效 request_id → 404 (跟 L4.85 1:1 stable 永久规则化沿用)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    resp = client.get("/api/v1/auth/login-request/non-existent-request-id-xyz/status")
    assert resp.status_code == 404
