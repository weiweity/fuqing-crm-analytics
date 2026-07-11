"""L4.85.6 reproduce test: 验证 Bug #2 真根因.

user 7/11 报 Bug #2: 'A 运营登录后退出 (Cmd+Q), B 运营 20 秒后再次登录, 提示申请登录, 但当前已经没有人看板'

真根因 (跟 L4.42 立项实证 SOP 'git log + grep 实证' 1:1 stable 永久规则化沿用):
1. A Cmd+Q 退出浏览器 → frontend JS 全停
2. backend ACTIVE_TOKENS[tokenA] 仍在内存 dict
3. last_active_at 永远停止滑动 (前端不再发请求)
4. _is_account_active('admin') 检查 last_active_at < 3min → True
5. B 端 login() 抛 409 → 申请 + 同意 → A 已经不在, 申请 3min 后 expired
6. user 体验劣化: '需要申请登录, 但当前没人在看板'

4 case 锁 L4.85.6 治本:
- test_bug2_reproduce: A login + Cmd+Q 模拟 (不 logout) + 20s 后 B login 409 (现状 fail, 治本 PASS)
- test_bug2_fix_beacon: A login + Cmd+Q + beforeunload sendBeacon → 后端踢 token → B login 200 (方案 A)
- test_bug2_fix_evictor: A login + Cmd+Q + background task evict > 1min → B login 200 (方案 D)
- test_evictor_idempotent: background task evict 时 token 还在 ACTIVE_TOKENS → 安全 evict 不影响其他 user

跟 L4.42 + L4.50 + L4.55 + L4.85 + L4.85.3 + L4.85.4 + L4.85.5 + L4.85.6 1:1 stable 永久规则链配套.
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

os.environ.setdefault("FQ_CRM_PASSWORDS", "admin:123456,fqsw:fqsw888")

from backend.routers import auth as auth_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state():
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()


def test_bug2_reproduce_a_cmdq_b_login_409():
    """核心 case 1: 验证 Bug #2 真根因 (现状 FAIL, 治本 PASS).

    场景: A login → 模拟 Cmd+Q (不调 logout) → 20 秒后 B login → 应该 409 (现状)
    治本后: A beforeunload sendBeacon 或后台 evict > 1min → B login 200.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 1. A 端 login
    a_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert a_resp.status_code == 200
    a_token = a_resp.json()["token"]

    # 2. 模拟 A Cmd+Q: 不调 logout, 但 last_active_at 模拟 50 秒前 (模拟 A 操作后 50 秒, 然后 Cmd+Q)
    auth_module.ACTIVE_TOKENS[a_token] = ("admin", datetime.now() - timedelta(seconds=50))

    # 3. B 端 admin login (不同 IP, 模拟第二台设备)
    # 现状: _is_account_active('admin') 检查 last_active_at 50s < 3min → True → 409
    b_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert b_resp.status_code == 409, (
        f"现状期望 409 (Bug #2 真根因), 实际 {b_resp.status_code}: {b_resp.text}"
    )
    assert "正在被使用" in b_resp.json().get("detail", "")


def test_bug2_fix_beacon_a_cmdq_b_login_200():
    """核心 case 2: 方案 A 治本 (beforeunload + sendBeacon).

    场景: A login → 模拟 Cmd+Q with sendBeacon → 后端踢 token → 50 秒后 B login 200.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 1. A 端 login
    a_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert a_resp.status_code == 200
    a_token = a_resp.json()["token"]
    auth_module.ACTIVE_TOKENS[a_token] = ("admin", datetime.now() - timedelta(seconds=50))

    # 2. 模拟 beforeunload sendBeacon: 浏览器关掉前 sendBeacon POST /api/v1/auth/logout
    #    sendBeacon 不能设 Authorization header, 所以 logout endpoint 需支持 token via query/body
    #    治本方案: logout endpoint 接受 token via query param 或 body
    #    模拟 sendBeacon: 调 logout API 携带 token
    beacon_resp = client.post(f"/api/v1/auth/logout?token={a_token}")
    assert beacon_resp.status_code == 200

    # 3. 验证: token 已删
    assert a_token not in auth_module.ACTIVE_TOKENS
    assert auth_module._is_account_active("admin") is False

    # 4. B 端 admin login → 应该 200 (方案 A 治本)
    b_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert b_resp.status_code == 200, (
        f"方案 A 治本期望 200, 实际 {b_resp.status_code}: {b_resp.text}"
    )


def test_bug2_fix_evictor_a_cmdq_b_login_200():
    """核心 case 3: 方案 D 治本 (background task evict idle token > 1min).

    场景: A login → 模拟 last_active_at 70s 前 (模拟 A idle 后 70s, 没 logout) →
    background task evict → 验证 ACTIVE_TOKENS 中 A token 已清 → B login 200.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.services.auth_token_evictor import evict_idle_tokens

    client = TestClient(app)

    # 1. A 端 login
    a_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert a_resp.status_code == 200
    a_token = a_resp.json()["token"]
    auth_module.ACTIVE_TOKENS[a_token] = ("admin", datetime.now() - timedelta(seconds=70))

    # 2. 验证现状: token 仍 active (last_active_at 70s < 3min)
    assert auth_module._is_account_active("admin") is True

    # 3. 调 background task evict_idle_tokens (idle_threshold_seconds=60)
    evicted = evict_idle_tokens(idle_threshold_seconds=60)
    assert evicted == 1, f"应该 evict 1 个 idle token, 实际 evict {evicted}"

    # 4. 验证: A token 已清
    assert a_token not in auth_module.ACTIVE_TOKENS
    assert auth_module._is_account_active("admin") is False

    # 5. B 端 admin login → 应该 200 (方案 D 治本)
    b_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert b_resp.status_code == 200, (
        f"方案 D 治本期望 200, 实际 {b_resp.status_code}: {b_resp.text}"
    )


def test_evictor_idempotent_active_user_not_evicted():
    """核心 case 4: 边界 case - active user 不被 evict.

    验证: last_active_at < threshold 的 active user token 不会被误 evict.
    跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用 (边界 case 防回归).
    """
    from backend.services.auth_token_evictor import evict_idle_tokens

    # 1. admin token, last_active_at 30s 前 (active, 不应 evict)
    active_time = datetime.now() - timedelta(seconds=30)
    auth_module.ACTIVE_TOKENS["admin-active-token"] = ("admin", active_time)

    # 2. fqsw token, last_active_at 30s 前 (active, 不应 evict)
    auth_module.ACTIVE_TOKENS["fqsw-active-token"] = ("fqsw", active_time)

    # 3. admin token, last_active_at 70s 前 (idle > 60s, 应 evict)
    idle_time = datetime.now() - timedelta(seconds=70)
    auth_module.ACTIVE_TOKENS["admin-idle-token"] = ("admin", idle_time)

    # 4. 调 evict
    evicted = evict_idle_tokens(idle_threshold_seconds=60)
    assert evicted == 1, f"应该只 evict 1 个 (admin-idle-token), 实际 evict {evicted}"

    # 5. 验证: active user token 仍在, idle token 已清
    assert "admin-active-token" in auth_module.ACTIVE_TOKENS
    assert "fqsw-active-token" in auth_module.ACTIVE_TOKENS
    assert "admin-idle-token" not in auth_module.ACTIVE_TOKENS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])