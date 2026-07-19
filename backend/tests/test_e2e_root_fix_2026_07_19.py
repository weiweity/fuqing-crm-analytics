"""e2e 根治锁回归 (2026-07-19): L4.85 409 + _test/reset 白名单 + CI seed.

真因链:
1. Playwright 每 case 新 browser context，但 uvicorn 进程共享 ACTIVE_TOKENS
2. 第 2 个 case login → L4.85 409 → 停在「申请登录」→ 业务页 toBeVisible 全红
3. /api/v1/_test/reset 被 auth_middleware 401 挡住 → 无法清会话
4. CI 未设 FQ_CRM_TEST_MODE=1
5. schema-only 0 行 orders 导致部分 API 非预期

治本:
- FQ_CRM_TEST_MODE=1 → login 跳过 409 + 踢旧 token
- auth_middleware 放行 /api/v1/_test/*
- scripts/ci/seed_e2e_duckdb.py 最小业务 seed
- lint.yml e2e 去 continue-on-error
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINT_YML = ROOT / ".github" / "workflows" / "lint.yml"
MAIN_PY = ROOT / "backend" / "main.py"
AUTH_PY = ROOT / "backend" / "routers" / "auth.py"
SEED_PY = ROOT / "scripts" / "ci" / "seed_e2e_duckdb.py"


class TestE2eRootCiConfig:
    def test_fq_crm_test_mode_enabled_in_e2e_job(self) -> None:
        text = LINT_YML.read_text(encoding="utf-8")
        assert re.search(r"FQ_CRM_TEST_MODE:\s*['\"]?1['\"]?", text), (
            "lint.yml e2e job 必须 FQ_CRM_TEST_MODE=1"
        )

    def test_e2e_job_not_continue_on_error(self) -> None:
        text = LINT_YML.read_text(encoding="utf-8")
        # e2e job 段内不应再有 continue-on-error: true
        m = re.search(r"^\s*e2e:\s*\n(?:.*\n){0,40}?", text, re.M)
        assert m, "lint.yml 缺少 e2e job"
        # 取 e2e job 到下一个 top-level job 或文件尾
        start = text.index("  e2e:")
        rest = text[start:]
        # 下一个同级 job 以 "  name:" 或 EOF；简化：前 80 行
        head = "\n".join(rest.splitlines()[:80])
        assert "continue-on-error: true" not in head, (
            "e2e 根治后禁止 continue-on-error: true（应挡 merge）"
        )

    def test_e2e_uses_seed_script(self) -> None:
        text = LINT_YML.read_text(encoding="utf-8")
        assert "seed_e2e_duckdb.py" in text
        assert SEED_PY.is_file()


class TestE2eRootSourceGuards:
    def test_auth_middleware_whitelists_test_reset_in_test_mode(self) -> None:
        src = MAIN_PY.read_text(encoding="utf-8")
        assert 'FQ_CRM_TEST_MODE' in src
        assert 'path.startswith("/api/v1/_test/")' in src or "path.startswith('/api/v1/_test/')" in src

    def test_login_skips_409_in_test_mode(self) -> None:
        src = AUTH_PY.read_text(encoding="utf-8")
        assert "FQ_CRM_TEST_MODE" in src
        assert "not _test_mode" in src or "_test_mode" in src


class TestE2eSeedScript:
    def test_seed_builds_nonempty_orders(self, tmp_path: Path) -> None:
        import subprocess
        import sys

        db = tmp_path / "e2e.duckdb"
        r = subprocess.run(
            [sys.executable, str(SEED_PY), str(db)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "E2E_DUCKDB_OK" in r.stdout
        assert db.is_file() and db.stat().st_size > 10_000

        import duckdb

        conn = duckdb.connect(str(db), read_only=True)
        try:
            n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            assert n >= 50
        finally:
            conn.close()


class TestE2eAuthTestModeBehavior:
    """FastAPI TestClient: TEST_MODE 下二次 login 不 409，reset 可无 token。"""

    @pytest.fixture()
    def client(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # 用 seed db 隔离生产
        import subprocess
        import sys

        db = tmp_path / "e2e.duckdb"
        subprocess.run(
            [sys.executable, str(SEED_PY), str(db)],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
        )
        monkeypatch.setenv("DUCKDB_PATH", str(db))
        monkeypatch.setenv("FQ_DB_MODE", "schema_test")
        monkeypatch.setenv("FQ_CRM_TEST_MODE", "1")
        monkeypatch.setenv("FQ_CRM_PASSWORDS", "admin:123456")
        monkeypatch.setenv("FQ_CRM_ADMINS", "admin")
        monkeypatch.setenv("HEALTH_API_KEY", "ci-fake")
        monkeypatch.setenv("FQ_SINGLE_USER_V2", "0")

        import backend.routers.auth as auth_mod

        auth_mod.ACTIVE_TOKENS.clear()
        from fastapi.testclient import TestClient

        from backend.main import app

        with TestClient(app) as c:
            yield c
        auth_mod.ACTIVE_TOKENS.clear()

    def test_double_login_ok_in_test_mode(self, client) -> None:
        r1 = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert r1.status_code == 200, r1.text
        t1 = r1.json()["token"]
        r2 = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert r2.status_code == 200, r2.text
        t2 = r2.json()["token"]
        assert t1 != t2

    def test_reset_without_token_in_test_mode(self, client) -> None:
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        r = client.post("/api/v1/_test/reset")
        assert r.status_code == 200, r.text
        assert r.json().get("success") is True
