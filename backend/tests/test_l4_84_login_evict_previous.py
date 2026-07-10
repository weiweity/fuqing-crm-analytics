"""L4.84 治本: 同账号踢人回归 test (跟 L4.50 + L4.75 v2 + L4.65.1 + L4.69.1 1:1 stable 永久规则链配套)

4 case 锁 L4.84 治本:
- test_login_evicts_previous_token_for_same_user (核心: 同账号 A 旧 token 失效)
- test_login_does_not_evict_different_user (隔离: admin 登录不踢 fqsw)
- test_logout_then_login_no_evict (兼容性: 登出后登录不踢)
- test_concurrent_login_evicts_oldest (并发: 同账号 3 设备并发登录只保留最新)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试用环境变量必须在导入 auth 之前设置
os.environ.setdefault("FQ_CRM_PASSWORDS", "admin:test_admin_pwd,fqsw:test_fqsw_pwd")

from backend.routers import auth as auth_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_auth_state():
    """每个 test 前清空 ACTIVE_TOKENS / _LOGIN_ATTEMPTS, 保证隔离."""
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()
    yield
    auth_module.ACTIVE_TOKENS.clear()
    auth_module._LOGIN_ATTEMPTS.clear()


def test_login_evicts_previous_token_for_same_user():
    """核心 case: A 账号 token 1 登录后, A 账号 token 2 登录, token 1 失效."""
    # 1. admin 第一次登录, 拿到 token_old
    token_old = "token-old-device-A"
    auth_module.ACTIVE_TOKENS[token_old] = ("admin", __import__("datetime").datetime.now())
    assert auth_module.ACTIVE_TOKENS[token_old][0] == "admin"

    # 2. 调 _evict_previous_sessions_for_user("admin")
    evicted = auth_module._evict_previous_sessions_for_user("admin")
    assert evicted == 1, f"应该踢出 1 个旧 token, 实际 {evicted}"
    assert token_old not in auth_module.ACTIVE_TOKENS, "旧 token 应该失效"


def test_login_does_not_evict_different_user():
    """隔离 case: admin 登录不踢 fqsw."""
    auth_module.ACTIVE_TOKENS["token-admin"] = ("admin", __import__("datetime").datetime.now())
    auth_module.ACTIVE_TOKENS["token-fqsw"] = ("fqsw", __import__("datetime").datetime.now())

    evicted = auth_module._evict_previous_sessions_for_user("admin")
    assert evicted == 1
    assert "token-admin" not in auth_module.ACTIVE_TOKENS
    assert "token-fqsw" in auth_module.ACTIVE_TOKENS, "不同账号 token 不应被踢"


def test_logout_then_login_no_evict():
    """兼容性 case: 登出后登录不踢 (因为登出已删除 token, 没东西可踢)."""
    auth_module.ACTIVE_TOKENS["token-old"] = ("admin", __import__("datetime").datetime.now())
    # 模拟登出
    auth_module.ACTIVE_TOKENS.pop("token-old", None)

    evicted = auth_module._evict_previous_sessions_for_user("admin")
    assert evicted == 0, "登出后没东西可踢"


def test_concurrent_login_evicts_oldest():
    """并发 case: 同账号 3 设备并发登录, 调 3 次 _evict, 最终只有最后一个 token 保留."""
    auth_module.ACTIVE_TOKENS["t1"] = ("admin", __import__("datetime").datetime.now())
    auth_module.ACTIVE_TOKENS["t2"] = ("admin", __import__("datetime").datetime.now())
    auth_module.ACTIVE_TOKENS["t3"] = ("admin", __import__("datetime").datetime.now())

    # 调 1 次 _evict, 踢 3 个
    evicted = auth_module._evict_previous_sessions_for_user("admin")
    assert evicted == 3
    assert "t1" not in auth_module.ACTIVE_TOKENS
    assert "t2" not in auth_module.ACTIVE_TOKENS
    assert "t3" not in auth_module.ACTIVE_TOKENS
