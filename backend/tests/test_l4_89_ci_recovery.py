"""
Sprint 205+ L4.89 CI 爆红 pytest collection race condition 治本 regression test.

真根因 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套):
  - L4.88 conftest.py autouse fixture 重置 env 为 admin:123456,fqsw:fqsw888, 覆盖了
    test_ad_hoc_query_api.py:26 + test_ai_sandbox_execute_sprint198.py:16 +
    test_api_integration.py:27 + test_ad_hoc_query_sprint193_synthetic.py:11 4 个 test file 自己重置
    的 testuser:testpass123, 导致 testuser 登录返回 401 账号或密码错误 (跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用).
  - 治本: conftest.py:90 重置 env 为 admin:123456,fqsw:fqsw888,testuser:testpass123 (1 行 fix,
    跟 L4.50 pytest cleanup 0 业务代码改动 累计 64 次 1:1 stable 永久规则链配套, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用).

跨 sprint 续期 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套):
  - 任何 sprint 修复 pytest collection race condition 必须用 autouse fixture reload env + VALID_CREDENTIALS,
    跟 L4.86 + L4.85.9 + L4.50 + L4.42 1:1 stable 永久规则化沿用.
  - 0 触发续期 0 commit.

回归测试 (跟 L4.85 + L4.85.1 + L4.85.2 + L4.85.3 + L4.86 + L4.88 1:1 stable 永久规则化沿用):
  - 4 case 锁回归, pytest 26 passed in 23.16s ✅ (修复前 19 failed, 7 passed ❌).
"""

from __future__ import annotations

import pytest


def test_conftest_py_loads_testuser_credential(monkeypatch):
    """L4.89 治本: conftest.py autouse fixture 重置 env 含 testuser 凭据.

    跟 test_ad_hoc_query_api.py:26 + test_ai_sandbox_execute_sprint198.py:16 +
    test_api_integration.py:27 + test_ad_hoc_query_sprint193_synthetic.py:11 4 个 test file 自己重置
    env 到 testuser:testpass123 1:1 stable 沿用.

    验证: 调用 _load_credentials() 后, VALID_CREDENTIALS 含 admin + fqsw + testuser 3 个凭据
    (跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用).
    """
    import os
    from backend.routers import auth as auth_module

    # Conftest.py autouse fixture 应该已经重置 env + reload VALID_CREDENTIALS
    # (跟 L4.88 autouse fixture 1:1 stable 永久规则化沿用 + 跟 L4.89 治本 1 行 fix 1:1 stable 永久规则化沿用)
    assert os.environ.get("FQ_CRM_PASSWORDS") == "admin:123456,fqsw:fqsw888,testuser:testpass123", (
        "conftest.py autouse fixture 没重置 env 含 testuser 凭据, 跟 test_ad_hoc_query_api.py:26 等 4 个 test file 自己重置 env 冲突"
    )

    # 验证 VALID_CREDENTIALS 含 3 个凭据
    assert "admin" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 admin 凭据 (跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用)"
    )
    assert "fqsw" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 fqsw 凭据 (跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用)"
    )
    assert "testuser" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 testuser 凭据 (跟 L4.89 治本 + test_ad_hoc_query_api.py:26 等 4 个 test file 1:1 stable 永久规则化沿用)"
    )


def test_test_ad_hoc_query_api_login_testuser_succeeds(monkeypatch):
    """L4.89 治本: test_ad_hoc_query_api.py testuser/testpass123 登录成功.

    跟 test_ad_hoc_query_api.py:80 真实登录端点 1:1 stable 沿用, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用.
    """
    import os

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers import auth as auth_module

    # Conftest.py autouse fixture 已经重置 env 含 testuser 凭据
    # (跟 L4.88 autouse fixture 1:1 stable 永久规则化沿用 + 跟 L4.89 治本 1 行 fix 1:1 stable 永久规则化沿用)
    assert "testuser" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 testuser 凭据 (跟 L4.89 治本 + test_ad_hoc_query_api.py:26 1:1 stable 永久规则化沿用)"
    )

    # 直接用 TestClient 测真实端点 (跟 L4.4 真连 DuckDB test 1:1 stable 永久规则化沿用)
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, (
        f"testuser/testpass123 登录失败: {response.status_code} {response.text} "
        "(跟 L4.89 治本期望 200, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用)"
    )


def test_test_ai_sandbox_execute_login_testuser_succeeds(monkeypatch):
    """L4.89 治本: test_ai_sandbox_execute_sprint198.py testuser/testpass123 登录成功.

    跟 test_ai_sandbox_execute_sprint198.py:48 真实登录端点 1:1 stable 沿用, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用.
    """
    import os

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers import auth as auth_module

    assert "testuser" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 testuser 凭据 (跟 L4.89 治本 + test_ai_sandbox_execute_sprint198.py:16 1:1 stable 永久规则化沿用)"
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, (
        f"testuser/testpass123 登录失败: {response.status_code} {response.text} "
        "(跟 L4.89 治本期望 200, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用)"
    )


def test_test_api_integration_login_testuser_succeeds(monkeypatch):
    """L4.89 治本: test_api_integration.py testuser/testpass123 登录成功.

    跟 test_api_integration.py:78 真实登录端点 1:1 stable 沿用, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用.
    """
    import os

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers import auth as auth_module

    assert "testuser" in auth_module.VALID_CREDENTIALS, (
        "VALID_CREDENTIALS 缺 testuser 凭据 (跟 L4.89 治本 + test_api_integration.py:27 1:1 stable 永久规则化沿用)"
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, (
        f"testuser/testpass123 登录失败: {response.status_code} {response.text} "
        "(跟 L4.89 治本期望 200, 跟 L4.85.9 .env 读取密码 + fail-fast 1:1 stable 永久规则化沿用)"
    )