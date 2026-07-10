"""L4.85.2 治本: 整合 L4.84 path 跟 L4.85 path (跟 user 7/10 拍板 1:1 stable 永久规则化沿用, 跟 plan-eng-review 1:1 stable 永久规则化沿用)

4 case 锁 L4.85.2 治本:
- test_login_normal_when_no_active (核心 case 1: 无 active → 正常 login 200 + 拿到 token)
- test_login_rejected_with_409_when_active (核心 case 2: 有 active → login 409 + 不踢人)
- test_login_then_apply_after_logout (兼容 case: 登出后 login 200 + 申请也 200)
- test_apply_still_works_when_active (兼容 case: 申请按钮仍走 L4.85 path, active 时返回 pending)
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


def test_login_normal_when_no_active():
    """核心 case 1: 无 active → 正常 login 200 + 拿到 token (跟 L4.84 1:1 stable 永久规则化沿用)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert resp.status_code == 200, f"应该 200, 实际 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "token" in data
    assert data["username"] == "admin"
    # token 写入 ACTIVE_TOKENS
    assert data["token"] in auth_module.ACTIVE_TOKENS
    assert auth_module.ACTIVE_TOKENS[data["token"]][0] == "admin"


def test_login_rejected_with_409_when_active():
    """核心 case 2: 有 active → login 409 + 不踢人 (跟 L4.85.2 整合 1:1 stable 永久规则化沿用)."""
    _activate_admin()
    assert "admin-token-1" in auth_module.ACTIVE_TOKENS

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # B 端 login 时, A 已 active → 应该 409
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert resp.status_code == 409, f"应该 409, 实际 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "正在被使用" in data["detail"]
    assert "请使用申请登录按钮" in data["detail"]
    # 关键: A 端旧 token 不变 (不踢人, 跟 L4.85.2 整合 1:1 stable 永久规则化沿用)
    assert "admin-token-1" in auth_module.ACTIVE_TOKENS, "A 端旧 token 应该不变 (L4.85.2 整合后, active 时不踢)"


def test_login_then_apply_after_logout():
    """兼容 case: 登出后 login 200 + 申请 200 (跟 L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则化沿用)."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # A 登出
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert logout_resp.status_code == 200
    assert "admin-token-1" not in auth_module.ACTIVE_TOKENS

    # B login → 应该 200 (无 active)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_resp.status_code == 200
    new_token = login_resp.json()["token"]
    assert new_token in auth_module.ACTIVE_TOKENS

    # B 申请登录 (B 自己已 login active, 跟 L4.85 1:1 stable 永久规则化沿用, active 时创建申请 200)
    apply_resp = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    # admin 是 active (B 已 login), 所以 create_login_request 应该 200 + status=pending
    # 跟 L4.85 path 1:1 stable 永久规则化沿用: active 时创建申请 (B 申请等待 A 同意)
    assert apply_resp.status_code == 200
    data = apply_resp.json()
    assert data["status"] == "pending"
    assert "request_id" in data


def test_apply_still_works_when_active():
    """兼容 case: 申请按钮仍走 L4.85 path, active 时返回 pending (跟 L4.85 + L4.85.1 1:1 stable 永久规则化沿用)."""
    _activate_admin()

    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # B 端申请登录 admin (A 已 active) → 应该 200 + status=pending (跟 L4.85 1:1 stable 永久规则化沿用)
    apply_resp = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert apply_resp.status_code == 200
    data = apply_resp.json()
    assert data["status"] == "pending"
    assert "request_id" in data

    # A 端查 pending
    pending_resp = client.get(
        "/api/v1/auth/login-requests/pending",
        headers={"Authorization": "Bearer admin-token-1"},
    )
    assert pending_resp.status_code == 200
    pending_data = pending_resp.json()
    assert len(pending_data["pending"]) == 1
    assert pending_data["pending"][0]["request_id"] == data["request_id"]
