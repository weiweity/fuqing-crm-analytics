"""Sprint 198 ai-sandbox-execute regression tests."""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("HEALTH_API_KEY", secrets.token_urlsafe(32))
os.environ["FQ_CRM_PASSWORDS"] = "testuser:testpass123"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_SANDBOX_SQL = """
SELECT
    COUNT(DISTINCT o.user_id) AS users,
    SUM(o.actual_amount) AS gsv
FROM orders o
WHERE o.pay_time >= '2026-06-15 00:00:00'::TIMESTAMP
  AND o.pay_time <= '2026-06-15 23:59:59'::TIMESTAMP
  AND o.is_goujinjin = FALSE
  AND o.order_status != '交易关闭'
  AND o.is_refund = FALSE
"""


@pytest.fixture
def synthetic_client(monkeypatch_synthetic_ad_hoc_connection, monkeypatch, tmp_path):
    monkeypatch.setenv("FQ_TAKE_ROOT", str(tmp_path / "take_root"))
    from backend.routers import auth

    auth.VALID_CREDENTIALS = auth._load_credentials()
    auth._LOGIN_ATTEMPTS.clear()
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def synthetic_auth_headers(synthetic_client):
    response = synthetic_client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200, f"login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['token']}"}


class TestSandboxAudienceSummarySSOT:
    def test_sandbox_uses_valid_order_ssot(self, monkeypatch_synthetic_ad_hoc_connection) -> None:
        from backend.services.ai_sandbox import ai_sandbox_execute

        result = ai_sandbox_execute(VALID_SANDBOX_SQL, audit_id="sprint198-ssot")

        assert result["headers"] == ["users", "gsv"]
        assert result["rows"] == [[3, 350.0]]
        assert result["row_count"] == 1


class TestSandboxSQLInjectionPrevention:
    def test_rejects_writes_and_multi_statement(self, monkeypatch_synthetic_ad_hoc_connection) -> None:
        from backend.services.ai_sandbox import _validate_sql_security, ai_sandbox_execute

        blocked = [
            "DROP TABLE orders",
            "DELETE FROM orders",
            "TRUNCATE TABLE orders",
            "INSERT INTO orders VALUES (1)",
            "UPDATE orders SET actual_amount = 0",
            "EXEC something",
            f"{VALID_SANDBOX_SQL}; SELECT 1",
        ]
        hits = 0
        for sql in blocked:
            hits += int(not _validate_sql_security(sql))
            with pytest.raises(ValueError):
                ai_sandbox_execute(sql, audit_id="sprint198-block")
        assert hits == len(blocked), f"Sprint 198 SQL guard accuracy {hits}/{len(blocked)}"


class TestSandboxAuditLogWritten:
    def test_audit_log_written(self, monkeypatch_synthetic_ad_hoc_connection, monkeypatch, tmp_path) -> None:
        from backend.services import ai_sandbox

        audit_path = tmp_path / "fuqing_adhoc_audit.log"
        monkeypatch.setattr(ai_sandbox, "AUDIT_LOG_PATH", audit_path)

        ai_sandbox.ai_sandbox_execute(VALID_SANDBOX_SQL, audit_id="sprint198-audit")

        text = audit_path.read_text(encoding="utf-8")
        assert "ai-sandbox-execute" in text
        assert "audit_id=sprint198-audit" in text
        assert "L4.5_SSOT=OrderFilters.valid_order" in text


class TestSandboxRoutingAccuracy:
    def test_registry_cli_mcp_and_dynamic_headers_14th_tool(self, monkeypatch) -> None:
        from scripts.ad_hoc_queries import ai_sandbox_execute as wrapper
        from mcp_servers.fuqing_adhoc._dispatch import TOOL_DEFS
        from scripts.ad_hoc_queries.registry import QUERIES

        monkeypatch.setattr(
            wrapper,
            "_post_ai_sandbox_execute",
            lambda *args, **kwargs: {
                "headers": ["users", "gsv"],
                "rows": [[3, 350.0]],
                "row_count": 1,
            },
        )
        json_rows = wrapper._run_ai_sandbox_execute_cli("SELECT 1")
        payload = json.loads(json_rows[0][0])
        checks = [
            "ai-sandbox-execute" in QUERIES,
            any(t["name"] == "ai_sandbox_execute" for t in TOOL_DEFS),
            QUERIES["ai-sandbox-execute"].business_tag == "AI 沙箱执行",
            payload["headers"] == ["users", "gsv"],
            payload["rows"] == [[3, 350.0]],
        ]
        help_result = subprocess.run(
            [sys.executable, "scripts/ad_hoc_query.py", "ai-sandbox-execute", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        checks.extend([
            help_result.returncode == 0,
            "--audit-id" in help_result.stdout,
        ])

        hits = sum(int(check) for check in checks)
        assert hits == len(checks), f"Sprint 198 routing accuracy {hits}/{len(checks)}"


class TestSandboxSyntheticDuckdb:
    def test_http_endpoint_runs_on_synthetic_duckdb(self, synthetic_client, synthetic_auth_headers) -> None:
        response = synthetic_client.post(
            "/api/v1/ad-hoc/ai-sandbox-execute",
            headers=synthetic_auth_headers,
            json={
                "sql": VALID_SANDBOX_SQL,
                "sandbox_type": "aggregate",
                "audit_id": "sprint198-http",
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["command"] == "ai-sandbox-execute"
        assert body["headers"] == ["users", "gsv"]
        assert body["rows"] == [[3, 350.0]]
