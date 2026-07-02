"""ai-sandbox-execute — Sprint 198 HTTP wrapper."""
from __future__ import annotations

import json
import os
from typing import Any

import requests

from scripts.ad_hoc_queries.registry import QuerySpec, register

UVICORN_BASE_URL = os.environ.get("FQ_CRM_BASE_URL", "http://localhost:8000")
AUTH_TOKEN_ENV = "FQ_CRM_AUTH_TOKEN"


def _auth_headers(auth_token: str | None = None) -> dict[str, str]:
    token = auth_token or os.environ.get(AUTH_TOKEN_ENV)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _post_ai_sandbox_execute(
    sql: str,
    sandbox_type: str = "aggregate",
    audit_id: str | None = None,
    auth_token: str | None = None,
    base_url: str = UVICORN_BASE_URL,
) -> dict[str, Any]:
    """Call backend HTTP API; the backend service owns execution and audit."""
    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/ad-hoc/ai-sandbox-execute",
        json={"sql": sql, "sandbox_type": sandbox_type, "audit_id": audit_id},
        headers=_auth_headers(auth_token),
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def run_ai_sandbox_execute(
    sql: str,
    sandbox_type: str = "aggregate",
    audit_id: str | None = None,
    auth_token: str | None = None,
    base_url: str = UVICORN_BASE_URL,
) -> list[list[Any]]:
    """Return raw backend rows for direct Python callers."""
    return _post_ai_sandbox_execute(sql, sandbox_type, audit_id, auth_token, base_url)["rows"]


def _run_ai_sandbox_execute_cli(
    sql: str,
    sandbox_type: str = "aggregate",
    audit_id: str | None = None,
    auth_token: str | None = None,
) -> list[list[Any]]:
    """Return one JSON cell so dynamic SQL headers are not truncated by table output."""
    data = _post_ai_sandbox_execute(sql, sandbox_type, audit_id, auth_token)
    return [[json.dumps(data, ensure_ascii=False, default=str)]]


_ai_sandbox_execute_spec = QuerySpec(
    name="ai-sandbox-execute",
    description="AI 命中不到固定 tool 时走 backend sandbox service + audit log (Sprint 198)",
    args=[
        {"flags": ("--sql",), "required": True, "help": "单条 SELECT/WITH 只读 SQL"},
        {
            "flags": ("--sandbox-type",),
            "required": False,
            "default": "aggregate",
            "choices": ["aggregate", "timeseries", "rfm", "ltv"],
            "help": "sandbox 类型",
        },
        {"flags": ("--audit-id",), "required": False, "default": None, "help": "审计 ID"},
        {"flags": ("--auth-token",), "required": False, "default": None, "help": "Bearer token; 默认读 FQ_CRM_AUTH_TOKEN"},
        {
            "flags": ("--format",),
            "required": False,
            "default": "table",
            "choices": ["table", "csv"],
        },
        {"flags": ("--output", "-o"), "required": False, "default": None},
    ],
    headers=["result_json"],
    run=lambda **kw: _run_ai_sandbox_execute_cli(**kw),
    business_tag="AI 沙箱执行",
    base_year_arg="",
)
register(_ai_sandbox_execute_spec)
