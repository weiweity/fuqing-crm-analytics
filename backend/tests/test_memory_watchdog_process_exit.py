"""The RSS watchdog must terminate the process, not only its worker thread."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_watchdog_hard_limit_exits_entire_child_process():
    env = os.environ.copy()
    env["FQ_RSS_HARD_LIMIT_GB"] = "0.000001"
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import time; print('WATCHDOG_STARTED', flush=True); "
                "from backend.db.memory_monitor import MemoryWatchdog; "
                "watchdog=MemoryWatchdog(interval=0.01); "
                "watchdog.start(); "
                "time.sleep(2); "
                "raise RuntimeError('watchdog only stopped its own thread')"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert child.returncode == 1, child.stderr
    assert "WATCHDOG_STARTED" in child.stdout
    assert "[内存监控] watchdog FATAL" in child.stderr
    assert "Traceback" not in child.stderr


def test_web_lifespan_checks_memory_every_five_seconds():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "start_memory_watchdog(interval=5)" in source
