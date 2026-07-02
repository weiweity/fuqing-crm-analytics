"""Client for the Sprint 201 R1 isolated query worker."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from backend.config import DUCKDB_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def execute_via_query_worker(
    sql: str,
    duckdb_path: str | os.PathLike[str] | None = None,
    memory_limit: str = "4GB",
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute SQL through an isolated read-only worker process."""

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    db_path = str(duckdb_path or os.environ.get("FQ_AI_SANDBOX_DUCKDB_PATH") or DUCKDB_PATH)

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "query_worker.py"),
                "--sql-stdin",
                "--duckdb-path",
                db_path,
                "--memory-limit",
                memory_limit,
                "--timeout",
                str(timeout),
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"query_worker subprocess exceeded {timeout + 5}s",
            "blocked_reason": "timeout",
        }

    stdout = result.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            payload = {"success": False, "error": stdout}
    else:
        payload = {"success": False, "error": result.stderr.strip() or "query_worker produced no output"}

    if result.returncode != 0:
        payload.setdefault("success", False)
        payload.setdefault("error", result.stderr.strip() or "query_worker failed")
    return payload
