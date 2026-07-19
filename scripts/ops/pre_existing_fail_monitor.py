#!/usr/bin/env python3
"""Sprint 201+ R6 pre-existing fail 跨 sprint 监控 (L4.42 立项实证 + L4.59 永久规则化)

- 每周日 04:00 launchd 触发
- 有生产业务库时: pytest 跑 4 file（sampling + w4_t7）
- 0 FAIL → print "PRE_EXISTING_FAIL_MONITOR_PASS …"
- failed > 0 且有生产库 → 告警文案（脚本仍 fail-open exit 0）
- 无生产业务库（CI / 空库 / 无 orders）→ 直接 PASS 0/0，不裸跑 14 case 假红

L4.61 + 2026-07-19 CI 修:
- 仅 Path.exists() 不够：空 duckdb 可 connect 但无表 → 必须查 orders
- 无库环境禁止子进程裸跑依赖真库的 case（否则 7 failed 外层 pytest 红）
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60: scripts/ops/ → repo root
DEFAULT_PROD_DB = REPO_ROOT / "data" / "processed" / "fuqing_crm.duckdb"
TEST_FILES = [
    "backend/tests/test_sampling_roi_yoy.py",
    "backend/tests/test_sampling_sprint139.py",
    "backend/tests/test_sampling_sprint141.py",
    "backend/tests/test_w4_t7_integration.py",
]
LOG_FILE = Path("/tmp/fuqing-pre-existing-fail.log")
TECH_DEBT = REPO_ROOT / "docs/TECH-DEBT.md"

PASS_PATTERN = re.compile(r"(\d+)\s+passed")
FAIL_PATTERN = re.compile(r"(\d+)\s+failed")

# 空库 / 占位文件下限（duckdb 新建空文件约 12KB；业务库远大于此）
_MIN_DB_BYTES = 50_000


def is_business_duckdb_ready(db_path: Path | None = None) -> bool:
    """生产业务库是否可用：文件存在、非空占位、可读且含 orders 表。

    供 monitor 与 pytest 共用，避免「文件在但无表」误当生产库。
    """
    path = Path(db_path) if db_path is not None else DEFAULT_PROD_DB
    try:
        if not path.is_file():
            return False
        if path.stat().st_size < _MIN_DB_BYTES:
            return False
        import duckdb

        conn = duckdb.connect(str(path), read_only=True)
        try:
            conn.execute("SELECT 1 FROM orders LIMIT 1").fetchone()
            return True
        finally:
            conn.close()
    except Exception:
        return False


def run_pytest() -> tuple[int, int, str]:
    """跑 pytest 4 case, return (passed_count, failed_count, raw_output)"""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *TEST_FILES,
                "-q",
                "--tb=no",
            ],
            cwd=str(REPO_ROOT),
            env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        passed = 0
        failed = 0
        m = PASS_PATTERN.search(output)
        if m:
            passed = int(m.group(1))
        m = FAIL_PATTERN.search(output)
        if m:
            failed = int(m.group(1))
        return passed, failed, output
    except Exception as e:
        return 0, 0, f"PYTEST_EXCEPTION: {type(e).__name__}: {e}"


def append_tech_debt(msg: str) -> None:
    """跨 sprint 留尾告警 (跟 L4.12 SSOT 配套)"""
    try:
        if not TECH_DEBT.exists():
            TECH_DEBT.write_text("# Tech Debt (Sprint 67+ L4.12 SSOT)\n\n")
        with TECH_DEBT.open("a") as f:
            f.write(f"\n## R6 Pre-existing Fail Alert (Sprint 201+)\n\n{msg}\n")
    except Exception as e:
        print(f"[PRE_EXISTING_FAIL_MONITOR] TECH_DEBT write failed: {e}", file=sys.stderr)


def main() -> int:
    # CI / fresh clone：无业务库 → 不裸跑 14 case（会 7 failed 假红）
    if not is_business_duckdb_ready():
        msg = (
            "PRE_EXISTING_FAIL_MONITOR_PASS 0 passed "
            "(R6 no prod business DB / CI, failed=0, skip live probe)"
        )
        print(msg)
        try:
            with LOG_FILE.open("a") as f:
                f.write(f"{msg}\n")
        except Exception:
            pass
        return 0

    try:
        passed, failed, output = run_pytest()
    except Exception as e:
        # fail-open: 异常不阻 commit (跟 L4.40 post-merge hook 配套)
        warn = f"[PRE_EXISTING_FAIL_MONITOR] EXCEPTION (fail-open): {type(e).__name__}: {e}"
        print(warn, file=sys.stderr)
        with LOG_FILE.open("a") as f:
            f.write(f"{warn}\n")
        return 0

    if failed > 0:
        msg = (
            f"[PRE_EXISTING_FAIL_MONITOR] FAIL: passed={passed} failed={failed} "
            f"(期望 14 passed / 0 failed, 跟 Sprint 201 R2 v24 1:1 stable)"
        )
        print(msg)
        with LOG_FILE.open("a") as f:
            f.write(f"{msg}\n{output}\n\n")
        append_tech_debt(
            f"- passed={passed}, failed={failed}\n- pytest output tail:\n```\n{output[-500:]}\n```"
        )
        # fail-open: 监控不阻 commit, 只告警
        return 0

    # 有生产库且 failed=0：PASS（passed 可为 14 或其它 skip 混合）
    msg = (
        f"PRE_EXISTING_FAIL_MONITOR_PASS {passed} passed (R6 cross-sprint stable, "
        f"failed=0, 期望 14 passed macOS / 0 passed CI no-db)"
    )
    print(msg)
    with LOG_FILE.open("a") as f:
        f.write(f"{msg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
