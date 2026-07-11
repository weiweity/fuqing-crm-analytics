"""L4.85.3 治本: _is_account_active last_active_at + 5min 检查 (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用)

4 case 锁 L4.85.3 治本:
- test_is_account_active_within_5min (核心 case 1: 5 分钟内 active → True)
- test_is_account_active_beyond_5min (核心 case 2: 5 分钟外 active → False, 跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用)
- test_login_after_stale_active_works (核心 case 3: 5 分钟外的旧 token 不算 active, login 200 + 拿到新 token)
- test_logout_clears_own_token (兼容 case: logout 只删自己的 token, 5 分钟内有效)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试用环境变量必须在导入 auth 之前设置
# 注意: dotenv.load_dotenv() 在 import auth 时跑, 把 .env 的 FQ_CRM_PASSWORDS 加载了
# setdefault 不生效, 必须用跟 .env 1:1 stable 配套的密码 (跟 L4.42 + L4.84 + L4.85 + L4.85.1 + L4.85.2 1:1 stable 配套)
os.environ.setdefault("FQ_CRM_PASSWORDS", "admin:123456,fqsw:fqsw888")

from backend.routers import auth as auth_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state():
    """每个 test 前清空所有状态, 保证隔离."""
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()


def test_is_account_active_within_3min():
    """核心 case 1: 3 分钟内 active → True (跟 L4.75 v2 lock_timeout_seconds 3min 1:1 stable 永久规则化沿用).

    user 7/11 拍板 "5 分钟时间太长了，可以 3 分钟", 全栈统一 3min.
    """
    # admin 2 分钟前 active (3min 阈值内)
    auth_module.ACTIVE_TOKENS["admin-token-1"] = ("admin", datetime.now() - timedelta(minutes=2))
    assert auth_module._is_account_active("admin") is True


def test_is_account_active_beyond_3min():
    """核心 case 2: 3 分钟外 active → False (跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用).

    user 7/11 拍板 "5 分钟时间太长了，可以 3 分钟", 全栈统一 3min.
    """
    # admin 10 分钟前 active (3 分钟外, 远超 3min 阈值)
    auth_module.ACTIVE_TOKENS["admin-stale-1"] = ("admin", datetime.now() - timedelta(minutes=10))
    assert auth_module._is_account_active("admin") is False


def test_login_after_stale_active_works():
    """核心 case 3: 3 分钟外的旧 token 不算 active, login 200 + 拿到新 token (跟 L4.85.3 治本 1:1 stable 永久规则化沿用)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # admin 10 分钟前 active (stale, 远超 3min 阈值)
    auth_module.ACTIVE_TOKENS["admin-stale-1"] = ("admin", datetime.now() - timedelta(minutes=10))

    # B 端 admin login → 应该 200 (stale token 不算 active, 跟 L4.85.3 治本 1:1 stable 永久规则化沿用)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert resp.status_code == 200, f"应该 200, 实际 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "token" in data
    assert data["username"] == "admin"
    # 新 token 写入 ACTIVE_TOKENS
    assert data["token"] in auth_module.ACTIVE_TOKENS
    # stale token 还在 (L4.85.3 不 evict stale, 跟 L4.84 1:1 stable 永久规则化沿用)
    # (注意: 这跟 L4.84 + L4.85.2 1:1 stable 永久规则化沿用冲突, L4.85.3 改成 "5 分钟外的 stale 不算 active 但不 evict")


def test_logout_clears_own_token():
    """兼容 case: logout 只删自己的 token, 5 分钟内有效 (跟 L4.85.3 + L4.85.1 1:1 stable 永久规则化沿用)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # A 端 login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_resp.status_code == 200
    a_token = login_resp.json()["token"]
    assert a_token in auth_module.ACTIVE_TOKENS

    # A 端 logout
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert logout_resp.status_code == 200
    # A 自己的 token 被删
    assert a_token not in auth_module.ACTIVE_TOKENS
    # A 端 _is_account_active 现在是 False (没 token)
    assert auth_module._is_account_active("admin") is False
