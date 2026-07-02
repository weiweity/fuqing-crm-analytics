#!/usr/bin/env python3
"""Run one read-only DuckDB query in an isolated worker process."""
from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import signal
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PYTHONPATH"] = str(PROJECT_ROOT)

import duckdb  # noqa: E402

_FORBIDDEN_SQL = re.compile(
    r"\b(drop|delete|truncate|insert|update|exec|execute|alter|create|attach|detach|copy|pragma|call)\b",
    re.IGNORECASE,
)
_VALID_ORDER_PATTERNS = (
    r"(?:\bo\.)?is_goujinjin\s*=\s*false",
    r"(?:\bo\.)?order_status\s*(?:!=|<>)\s*'交易关闭'",
    r"(?:\bo\.)?is_refund\s*=\s*false",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _error(message: str, blocked_reason: str = "validation_failed") -> int:
    print(json.dumps({"success": False, "error": message, "blocked_reason": blocked_reason}, ensure_ascii=False))
    return 1


def _uses_orders(sql: str) -> bool:
    lowered = sql.lower()
    return "from orders" in lowered or " join orders" in lowered or " from main.orders" in lowered


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate worker SQL before opening DuckDB."""

    stripped = sql.strip()
    if not stripped:
        return False, "SQL is empty"
    if ";" in stripped or "--" in stripped or "/*" in stripped or "*/" in stripped:
        return False, "SQL contains rejected pattern: statement separator/comment"
    match = _FORBIDDEN_SQL.search(stripped)
    if match:
        return False, f"SQL contains rejected pattern: {match.group(1).upper()}"
    first_token = stripped.split(None, 1)[0].upper()
    if first_token not in {"SELECT", "WITH", "EXPLAIN"}:
        return False, "SQL must start with SELECT, WITH, or EXPLAIN"
    if _uses_orders(stripped) and not all(re.search(p, stripped, re.IGNORECASE) for p in _VALID_ORDER_PATTERNS):
        return False, "orders 查询必须包含 valid_order 三条件"
    return True, ""


def _read_sql_arg(args: argparse.Namespace) -> str:
    if args.sql_stdin:
        return sys.stdin.read()
    if args.sql:
        return args.sql
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql")
    parser.add_argument("--sql-stdin", action="store_true")
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--memory-limit", default="4GB")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    sql = _read_sql_arg(args)
    ok, message = validate_sql(sql)
    if not ok:
        return _error(message)

    def handler(signum, frame):  # noqa: ARG001
        raise TimeoutError(f"SQL execution exceeded {args.timeout}s")

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(args.timeout)
    conn = None
    try:
        conn = duckdb.connect(
            args.duckdb_path,
            config={
                "memory_limit": args.memory_limit,
                "enable_external_access": False,
                "autoload_known_extensions": False,
                "autoinstall_known_extensions": False,
                "allow_community_extensions": False,
                "lock_configuration": True,
            },
            read_only=True,
        )
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [[_jsonable(cell) for cell in row] for row in cursor.fetchall()]
        print(
            json.dumps(
                {
                    "success": True,
                    "headers": columns,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except TimeoutError as exc:
        return _error(str(exc), "timeout")
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc), "execution_failed")
    finally:
        signal.alarm(0)
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
