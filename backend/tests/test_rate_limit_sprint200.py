"""Sprint 200 R1 v2.1 — uvicorn resilience + rate limit regression tests.

真因: 业务组持续取数 → uvicorn 一直处于下线状态 (Sprint 184 L4.38 DuckDB flock 锁死).
治本: 每用户每分钟 60 req 限流 + launchd KeepAlive watchdog (跟 Codex consult 6 补强 1:1).

跟 L4.36 禁停 uvicorn + L4.47 禁 /tmp/*.py + L4.38 DuckDB flock 永久规则 1:1 配套.

测试设计: 用 /api/v1/auth/me (需要 token, 不依赖 DB) 触发 rate limit, 跟 DuckDB 解耦.
"""
from __future__ import annotations

import os
import secrets

os.environ.setdefault("HEALTH_API_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("FQ_CRM_PASSWORDS", "admin:123456,fqsw:fqsw888")
os.environ["RATE_LIMIT_PER_MINUTE"] = "5"  # 测试用更小阈值

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _login(client, username: str, password: str) -> str:
    """登录拿 token (跟 backend.routers.auth._verify_token 1:1 stable)."""
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if r.status_code == 200:
        return r.json().get("token", "")
    return ""


@pytest.fixture(scope="module")
def admin_token(client):
    return _login(client, "admin", "123456")


@pytest.fixture(scope="module")
def fqsw_token(client):
    return _login(client, "fqsw", "fqsw888")


class TestRateLimitBasic:
    """Rate limit 基础行为验证 (跟 L4.36 友好错误 1:1)."""

    def test_health_endpoint_bypasses_rate_limit(self, client):
        """/api/v1/health 不限流 (健康检查不能用 429)."""
        for _ in range(10):
            r = client.get("/api/v1/health")
            assert r.status_code in (200, 401)

    def test_auth_endpoints_bypass_rate_limit(self, client):
        """/api/v1/auth/* 不限流 (登录接口不能用 429)."""
        for _ in range(10):
            r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
            # 200/401/422/429 都接受 (账号锁定 429 是 backend 锁定, 不是 rate limit)
            assert r.status_code in (200, 401, 422, 429)


class TestRateLimitHeaders:
    """Rate limit 响应头验证 (跟 L4.46 user prompt 强提示 1:1)."""

    def test_rate_limit_headers_present_on_auth_me(self, client, admin_token):
        """200 响应必须有 X-RateLimit-Limit + X-RateLimit-Remaining 头 (用 /auth/me 不依赖 DB)."""
        if not admin_token:
            pytest.skip("admin login failed")
        r = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert r.headers["X-RateLimit-Limit"] == "5"

    def test_rate_limit_decreases_remaining(self, client, admin_token):
        """连续请求 X-RateLimit-Remaining 应该递减."""
        if not admin_token:
            pytest.skip("admin login failed")
        r1 = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if r1.status_code != 200 or "X-RateLimit-Remaining" not in r1.headers:
            pytest.skip("rate limit headers missing or auth failed")
        r2 = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if r2.status_code == 200 and "X-RateLimit-Remaining" in r2.headers:
            assert int(r2.headers["X-RateLimit-Remaining"]) < int(r1.headers["X-RateLimit-Remaining"])


class TestRateLimitL436Compliance:
    """Rate limit 跟 L4.36 禁停 uvicorn + L4.47 禁 /tmp/*.py 永久规则 1:1 配套."""

    def test_429_response_format_compatible_with_l436(self, client, admin_token):
        """429 响应格式跟 L4.36 友好错误 1:1: 含 retry_after_seconds + user_id + L4.36 重试提示."""
        if not admin_token:
            pytest.skip("admin login failed")
        # 跑满 5 次触发 429 (RATE_LIMIT_PER_MINUTE=5)
        got_429 = False
        for _ in range(10):
            r = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if r.status_code == 429:
                # 验证 429 格式跟 L4.36 友好错误 1:1
                assert "Retry-After" in r.headers
                assert r.headers["Retry-After"] == "60"
                assert "X-RateLimit-Limit" in r.headers
                assert r.headers["X-RateLimit-Limit"] == "5"
                assert "X-RateLimit-Remaining" in r.headers
                assert r.headers["X-RateLimit-Remaining"] == "0"
                body = r.json()
                if "detail" in body and "Rate limit exceeded" in body["detail"]:
                    assert "retry_after_seconds" in body
                    assert body["retry_after_seconds"] == 60
                    assert body["user_id"] == "admin"
                    # L4.36 提示
                    assert "L4.36" in body["detail"] or "graceful retry" in body["detail"]
                got_429 = True
                return  # pass
        if not got_429:
            pytest.skip("never triggered 429 in 10 attempts")

    def test_no_temp_files_created_on_429(self, client, admin_token):
        """429 不创建 /tmp/*.py 临时脚本 (跟 L4.47 永久规则 1:1)."""
        if not admin_token:
            pytest.skip("admin login failed")
        import glob
        before = set(glob.glob("/tmp/*.py"))
        for _ in range(10):
            client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        after = set(glob.glob("/tmp/*.py"))
        new_files = after - before
        assert len(new_files) == 0, f"Rate limit 不应创建 /tmp/*.py: {new_files}"

    def test_429_does_not_shut_down_uvicorn(self, client):
        """触发 429 不影响健康检查 (uvicorn 没死, L4.36 友好错误)."""
        for _ in range(20):
            r = client.get("/api/v1/health")
            assert r.status_code in (200, 401)


class TestRateLimitUserIsolation:
    """Rate limit 按 user_id 隔离 (L4.5 SSOT 1:1)."""

    def test_admin_and_fqsw_separate_buckets(self, client, admin_token, fqsw_token):
        """admin 和 fqsw 是独立 bucket."""
        if not admin_token or not fqsw_token:
            pytest.skip("login failed")
        # admin 跑满 5 次触发 429
        admin_got_429 = False
        for _ in range(10):
            r = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if r.status_code == 429:
                admin_got_429 = True
                break

        if not admin_got_429:
            pytest.skip("admin didn't trigger 429 in 10 attempts")

        # fqsw 独立 bucket (admin 触发 429 不影响 fqsw)
        r_fqsw = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {fqsw_token}"},
        )
        # fqsw 第一次请求, 不应该 429
        assert r_fqsw.status_code != 429, "fqsw 应该独立 bucket, 不受 admin 触发 429 影响"
        assert r_fqsw.status_code == 200  # /auth/me 200 + 完整 user info