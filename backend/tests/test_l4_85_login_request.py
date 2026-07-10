"""L4.85 申请+同意 模式 回归 test (跟 L4.50 + L4.75 v2 + L4.84 1:1 stable 永久规则链配套)

6 case 锁 L4.85 治本:
- test_create_login_request (核心: B 申请 → 收到 request_id)
- test_pending_requests_for_active_user (A 查 → 看到 B 申请)
- test_approve_login_request (A 同意 → A 登出 + B 登录)
- test_reject_login_request (A 拒绝 → A 不受影响, B 看到拒绝)
- test_login_request_timeout (5 分钟超时 → 自动 expired)
- test_login_request_invalid_request_id (无效 request_id → 404)
"""
from __future__ import annotations

import os
import sys
import time
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
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    lr_module._reset_l4_85_state()


def _activate_admin():
    """helper: 让 admin 变成 active (有 token)."""
    auth_module.ACTIVE_TOKENS["admin-token-1"] = ("admin", datetime.now())


def test_create_login_request():
    """核心 case: A active, B 申请登录 admin → 收到 request_id, status=pending."""
    # 1. A active
    _activate_admin()

    # 2. B 申请登录 admin (用 fastapi TestClient 模拟)
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
        headers={"X-Forwarded-For": "192.168.1.20"},
    )
    assert resp.status_code == 200, f"应该 200, 实际 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "pending"
    assert "request_id" in data
    assert "已发送申请" in data["message"]


def test_pending_requests_for_active_user():
    """A 查待处理申请 → 看到 B 申请."""
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

    # A 查 (用 admin token)
    resp_pending = client.get(
        "/api/v1/auth/login-requests/pending",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp_pending.status_code == 200
    data = resp_pending.json()
    assert len(data["pending"]) == 1
    assert data["pending"][0]["request_id"] == request_id
    # 注意: TestClient 默认 request.client.host == "testclient", X-Forwarded-For 不被读
    # 跟 L4.42 立项实证 SOP 1:1 stable 配套, 测 request_id + status 就够了, 不强制 IP
    assert data["pending"][0]["status"] == "pending"


def test_approve_login_request():
    """A 同意 B 的申请 → A 登出, B 登录 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 配套)."""
    _activate_admin()
    assert "admin-token-1" in auth_module.ACTIVE_TOKENS

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
    assert resp_approve.status_code == 200
    data = resp_approve.json()
    assert data["success"] is True
    assert data["username"] == "admin"
    assert "new_token" in data
    assert len(data["new_token"]) > 20

    # 验证: A 的旧 token 失效 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 配套)
    assert "admin-token-1" not in auth_module.ACTIVE_TOKENS, "A 旧 token 应该被踢"

    # 验证: B 的新 token 有效
    new_token = data["new_token"]
    assert new_token in auth_module.ACTIVE_TOKENS
    assert auth_module.ACTIVE_TOKENS[new_token][0] == "admin"


def test_reject_login_request():
    """A 拒绝 B 的申请 → A 不受影响, B 看到拒绝."""
    _activate_admin()
    assert "admin-token-1" in auth_module.ACTIVE_TOKENS

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
    assert resp_reject.json()["success"] is True

    # 验证: A 的 token 还在 (跟 L4.85 1:1 stable 配套, 拒绝时 A 不受影响)
    assert "admin-token-1" in auth_module.ACTIVE_TOKENS, "A 拒绝后不应该被踢"

    # 验证: B 查不到 pending 了
    resp_pending = client.get(
        "/api/v1/auth/login-requests/pending",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp_pending.json()["pending"] == []


def test_login_request_timeout():
    """5 分钟超时 → 自动 expired (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 配套)."""
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

    # 手动改 created_at 到 6 分钟前 (模拟超时)
    target = lr_module._PENDING_REQUESTS["admin"][0]
    target.created_at = time.monotonic() - (lr_module.LOGIN_REQUEST_TIMEOUT_SECONDS + 60)

    # A 查 (触发 _evict_expired_requests_locked)
    resp_pending = client.get(
        "/api/v1/auth/login-requests/pending",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    # 验证: 超时申请被清理, pending 列表为空
    assert resp_pending.json()["pending"] == [], "超时申请应该被清理"

    # 验证: 同意已 expired 的申请 → 404
    resp_approve = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp_approve.status_code == 404


def test_login_request_invalid_request_id():
    """无效 request_id → 404."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 同意一个不存在的 request_id
    resp = client.post(
        "/api/v1/auth/login-request/non-existent-request-id-xyz/approve",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp.status_code == 404

    # 拒绝一个不存在的 request_id
    resp = client.post(
        "/api/v1/auth/login-request/non-existent-request-id-xyz/reject",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert resp.status_code == 404
