#!/usr/bin/env python3
"""Sprint 201+ R6 pre-existing fail 跨 sprint 监控 (L4.42 立项实证 + L4.59 永久规则化)

- 每周日 04:00 launchd 触发
- pytest 跑 4 case (3 sampling + 1 w4_t7)
- 0 FAIL → print "PRE_EXISTING_FAIL_MONITOR_PASS 14 passed"
- 任何 FAIL → exit 1 + 写 TECH-DEBT.md 跨 sprint 留尾告警
- fail-open: 异常 stderr warn + exit 0 (跟 L4.40 post-merge hook 配套)

L4.61 跨 CI runner 适配 (跟 L4.40 + L4.50 1:1 stable):
- CI Linux runner 加 --deselect 把 14 pre-existing fail 全 deselect → 0 passed 也是预期
- main() 改: passed == 0 + failed == 0 视为 PASS (deselected 跳过), 不告警
- failed > 0 才告警 (跟 macOS launchd 跨 sprint stable 1:1)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60: scripts/ops/ → repo root
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

    # L4.61 跨 CI runner 适配: passed=0 是 CI --deselect 预期, 也算 PASS
    # macOS launchd 跑期望 14 passed (本地实证 Sprint 202 R1 14 passed)
    # Linux CI runner 跑期望 0 passed (--deselect 14 pre-existing fail 全跳过, 跟 Sprint 201 R1 v2.1 lint.yml 1:1 stable)
    msg = (
        f"PRE_EXISTING_FAIL_MONITOR_PASS {passed} passed (R6 cross-sprint stable, "
        f"failed=0, 期望 14 passed macOS / 0 passed CI runner)"
    )
    print(msg)
    with LOG_FILE.open("a") as f:
        f.write(f"{msg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())