"""AI sandbox execution service for Sprint 198.

The service runs inside the backend process through the shared DuckDB
connection. It deliberately rejects writes and multi-statement SQL.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import os
from pathlib import Path
import re
from typing import Any

from backend.db.connection import get_connection
from backend.services.query_worker_client import execute_via_query_worker
from backend.semantic.filters import OrderFilters

AUDIT_LOG_PATH = Path("/tmp/fuqing_adhoc_audit.log")
ALLOWED_SANDBOX_TYPES = {"aggregate", "timeseries", "rfm", "ltv"}
_FORBIDDEN_SQL = re.compile(
    r"\b(drop|delete|truncate|insert|update|exec|execute|alter|create|attach|detach|copy|pragma|call)\b",
    re.IGNORECASE,
)


def _validate_sql_security(sql: str) -> bool:
    """Return True when SQL is a single read-only SELECT/WITH statement."""
    stripped = sql.strip()
    if not stripped:
        return False
    if ";" in stripped or "--" in stripped or "/*" in stripped or "*/" in stripped:
        return False
    if _FORBIDDEN_SQL.search(stripped):
        return False
    first_token = stripped.split(None, 1)[0].lower()
    if first_token not in {"select", "with"}:
        return False
    return True


def _uses_valid_order_ssot(sql: str) -> bool:
    """Verify orders queries carry the OrderFilters.valid_order() predicate."""
    lowered = sql.lower()
    if " orders" not in lowered and "from orders" not in lowered and "join orders" not in lowered:
        return True
    valid_sql, _ = OrderFilters.valid_order()
    patterns = [
        r"(?:\bo\.)?is_goujinjin\s*=\s*false",
        r"(?:\bo\.)?order_status\s*(?:!=|<>)\s*'交易关闭'",
        r"(?:\bo\.)?is_refund\s*=\s*false",
    ]
    return all(re.search(pattern, sql, re.IGNORECASE) for pattern in patterns) and bool(valid_sql)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _write_audit(sql: str, sandbox_type: str, audit_id: str | None, row_count: int, status: str) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        safe_sql = " ".join(sql.split())[:300]
        line = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t"
            f"ai-sandbox-execute\t{status}\t"
            f"audit_id={audit_id or '-'} sandbox_type={sandbox_type} "
            f"rows={row_count} L4.5_SSOT=OrderFilters.valid_order sql={safe_sql}\n"
        )
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _execute_in_process(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Legacy in-process executor used only by synthetic tests."""

    conn = get_connection()
    cursor = conn.execute(sql)
    rows = [[_jsonable(cell) for cell in row] for row in cursor.fetchall()]
    headers = [desc[0] for desc in cursor.description] if cursor.description else []
    return headers, rows


def _worker_disabled_for_test() -> bool:
    return os.environ.get("FQ_AI_SANDBOX_WORKER_DISABLED", "").lower() in {"1", "true", "yes"}


def ai_sandbox_execute(
    sql: str,
    sandbox_type: str = "aggregate",
    audit_id: str | None = None,
    duckdb_path: str | None = None,
) -> dict[str, Any]:
    """Execute a read-only sandbox query through an isolated worker process."""
    if sandbox_type not in ALLOWED_SANDBOX_TYPES:
        raise ValueError(f"未知 sandbox_type: {sandbox_type}; 可选 {sorted(ALLOWED_SANDBOX_TYPES)}")
    if not _validate_sql_security(sql):
        _write_audit(sql, sandbox_type, audit_id, 0, "blocked")
        raise ValueError("SQL 含禁止操作或多语句; 只允许单条 SELECT/WITH 只读查询")
    if not _uses_valid_order_ssot(sql):
        _write_audit(sql, sandbox_type, audit_id, 0, "blocked")
        raise ValueError("orders 查询必须包含 OrderFilters.valid_order() 三条件, 防止 SSOT 漂移")

    if _worker_disabled_for_test():
        headers, rows = _execute_in_process(sql)
    else:
        result = execute_via_query_worker(
            sql=sql,
            duckdb_path=duckdb_path,
            memory_limit=os.environ.get("FQ_AI_SANDBOX_MEMORY_LIMIT", "4GB"),
            timeout=int(os.environ.get("FQ_AI_SANDBOX_TIMEOUT", "30")),
        )
        if not result.get("success"):
            _write_audit(sql, sandbox_type, audit_id, int(result.get("row_count", 0) or 0), "blocked")
            raise ValueError(str(result.get("error", "query worker failed")))
        headers = list(result.get("headers") or result.get("columns") or [])
        rows = list(result.get("rows") or [])
    _write_audit(sql, sandbox_type, audit_id, len(rows), "ok")
    return {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "audit_log": str(AUDIT_LOG_PATH),
        "sandbox_type": sandbox_type,
    }
