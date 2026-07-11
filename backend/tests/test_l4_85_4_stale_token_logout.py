"""L4.85.4 治本: logout 踢所有 stale token + polling sliding=False (跟 user 7/11 拍板 1:1 stable 永久规则化沿用)

user 7/11 报: "我不知道啥情况，我因该都退出账号了，但是还是要申请登陆，然后就一直卡在这里了"
真根因 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用):
  1. logout 只删当前 token, 多次登录/refresh 留下 stale token, _is_account_active 5min 误判 True
  2. polling 10s 间隔调 _verify_token(sliding=True) 持续刷新 last_active_at, 用户离开工位永远 active

4 case 锁 L4.85.4 治本:
- test_logout_clears_all_user_tokens (核心 case 1: logout 踢该 user 所有 stale token, 不只当前)
- test_login_after_logout_works (核心 case 2: logout 后第二人能 login 200, 不卡 409)
- test_polling_does_not_refresh_active_at (核心 case 3: polling sliding=False 不刷新 last_active_at)
- test_idle_5min_keeps_account_inactive (核心 case 4: 用户离开工位 5min, polling 不让 active 永远 True)

跟 L4.85 + L4.85.1 + L4.85.3 + L4.85.4 1:1 stable 永久规则链配套.
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

# 测试用环境变量必须在导入 auth 之前设置 (跟 L4.42 + L4.84 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 1:1 stable 配套)
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


def test_logout_clears_all_user_tokens():
    """核心 case 1: L4.85.4 治本 - logout 踢该 user 所有 stale token, 不只当前 token.

    user 7/11 报: "我因该都退出账号了，但是还是要申请登陆" 真根因 = logout 只删当前 token.
    修复: 复用 _evict_previous_sessions_for_user 踢出同账号所有 stale token.

    模拟场景: ACTIVE_TOKENS 中已有 2 个 admin token (之前多次刷新/并发 login 留下),
    user 现在按退出按钮, 应该踢所有 admin token (修复前只踢当前 1 个).
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 准备: 手动塞 2 个 admin token 到 ACTIVE_TOKENS (模拟多次刷新留下的场景)
    admin_token_1 = "admin-token-stale-1"
    admin_token_2 = "admin-token-stale-2"
    now = datetime.now()
    auth_module.ACTIVE_TOKENS[admin_token_1] = ("admin", now - timedelta(minutes=1))
    auth_module.ACTIVE_TOKENS[admin_token_2] = ("admin", now - timedelta(minutes=2))

    # A 端用 token_2 退出 (L4.85.4 fix 后应该踢所有 admin token)
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {admin_token_2}"},
    )
    assert logout_resp.status_code == 200

    # L4.85.4 治本: 2 个 admin token 都被踢
    assert admin_token_1 not in auth_module.ACTIVE_TOKENS
    assert admin_token_2 not in auth_module.ACTIVE_TOKENS
    # _is_account_active 也应该 False
    assert auth_module._is_account_active("admin") is False


def test_login_after_logout_works():
    """核心 case 2: logout 后第二人能直接 login 200, 不卡 409 申请登录 (跟 user 7/11 拍板 1:1 stable).

    修复前: logout 后 _is_account_active 仍 True → B login 409 → 卡申请登录.
    修复后: logout 踢所有 token → _is_account_active False → B login 200.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # A 端 login
    a = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}).json()
    assert auth_module._is_account_active("admin") is True

    # A 端 logout
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {a['token']}"})

    # B 端 admin login (第二台设备, 同账号) → 应该 200, 不卡 409
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200, (
        f"应该 200 (logout 后第二人能直接 login), 实际 {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "token" in data


def test_polling_does_not_refresh_active_at():
    """核心 case 3: polling get_pending_requests 走 sliding=False, 不刷新 last_active_at.

    修复前: polling 10s 滑动续期 → 用户离开工位 polling 仍跑 → _is_account_active 永远 True.
    修复后: polling sliding=False read-only check → last_active_at 不刷新 → 5 分钟外 inactive.
    """
    from backend.routers.login_request import _get_current_username_from_token
    from backend.routers.auth import _verify_token

    # 准备: 1 个 token, last_active_at 4 分钟前
    token = "test-polling-token"
    initial_time = datetime.now() - timedelta(minutes=4)
    auth_module.ACTIVE_TOKENS[token] = ("admin", initial_time)

    # 模拟 polling endpoint 调用 _verify_token(sliding=False)
    username = _verify_token(token, sliding=False)
    assert username == "admin"

    # 关键: last_active_at 应该没变 (仍 4 分钟前), 不是被刷新成 now
    record = auth_module.ACTIVE_TOKENS[token]
    assert record[1] == initial_time, (
        f"polling 不该刷新 last_active_at, 期望 {initial_time}, 实际 {record[1]}"
    )


def test_idle_5min_keeps_account_inactive():
    """核心 case 4: 用户离开工位 5min, polling 不让 account 永远 active.

    模拟场景: 用户 login → 离开工位 5 分钟 → polling 持续跑 → _is_account_active 应该 False
    修复前: polling 滑动续期 → _is_account_active 永远 True → B 端 login 永远 409
    修复后: polling sliding=False → last_active_at 不刷新 → 5 分钟外 _is_account_active False
    """
    # 模拟: admin token, last_active_at 6 分钟前 (用户离开工位 6 分钟)
    stale_time = datetime.now() - timedelta(minutes=6)
    auth_module.ACTIVE_TOKENS["admin-stale-token"] = ("admin", stale_time)

    # L4.85.3 + L4.85.4 治本: _is_account_active 应该 False (6 分钟外 stale)
    assert auth_module._is_account_active("admin") is False

    # 模拟 polling 调用 (sliding=False): last_active_at 保持不变
    from backend.routers.auth import _verify_token
    username = _verify_token("admin-stale-token", sliding=False)
    assert username == "admin"  # token 还没过期 (TTL 8h)
    record = auth_module.ACTIVE_TOKENS["admin-stale-token"]
    assert record[1] == stale_time  # 没刷新

    # B 端 login 应该 200 (跟 test_login_after_logout_works 1:1 stable)
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200, (
        f"应该 200 (admin 离开工位 6min 无 polling 续期), 实际 {resp.status_code}: {resp.text}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])