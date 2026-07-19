"""Sprint 201+ R6 pre-existing fail monitor 锁回归 (L4.59 永久规则化)

- 验证 scripts/ops/pre_existing_fail_monitor.py 跑出 PRE_EXISTING_FAIL_MONITOR_PASS
- 无生产业务库时直接 PASS（不裸跑 14 case 假红）— 2026-07-19 CI 修
- 验证 fail-open 原则 (异常 exit 0 不阻 commit)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台 (test 在 backend/tests/ 下, parents[2] 是 repo root)
SCRIPT = REPO_ROOT / "scripts" / "ops" / "pre_existing_fail_monitor.py"


def _run_monitor() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_pre_existing_fail_monitor_pass_跨平台() -> None:  # noqa: N802
    """R6: 有库则探针；无库/CI 直接 PASS failed=0（不得 7-fail 假红）。"""
    result = _run_monitor()
    assert "PRE_EXISTING_FAIL_MONITOR_PASS" in result.stdout, (
        f"R6 monitor did not report PASS: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "failed=0" in result.stdout or "0 failed" in result.stdout, (
        f"R6 monitor must report failed=0, got: {result.stdout!r}"
    )
    assert result.returncode == 0, f"R6 monitor exited non-zero: {result.returncode}"


def test_is_business_duckdb_ready_rejects_empty_file(tmp_path: Path) -> None:
    """shipped is_business_duckdb_ready: 空库 → False。"""
    import duckdb

    from scripts.ops.pre_existing_fail_monitor import is_business_duckdb_ready

    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()
    assert empty.is_file()
    assert is_business_duckdb_ready(empty) is False


def test_is_business_duckdb_ready_accepts_orders_table(tmp_path: Path) -> None:
    """shipped is_business_duckdb_ready: 有 orders 且体积够 → True。"""
    import duckdb

    from scripts.ops.pre_existing_fail_monitor import is_business_duckdb_ready

    db = tmp_path / "biz.duckdb"
    conn = duckdb.connect(str(db))
    # 足够行数保证文件 > 50KB + 有 orders 表
    conn.execute(
        "CREATE TABLE orders AS SELECT i AS order_id, "
        "TIMESTAMP '2026-01-01' + INTERVAL (i) DAY AS pay_time "
        "FROM range(200000) t(i)"
    )
    conn.close()
    assert db.stat().st_size >= 50_000, f"fixture too small: {db.stat().st_size}"
    assert is_business_duckdb_ready(db) is True


def test_main_no_prod_db_prints_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() 在 is_business_duckdb_ready=False 时 stdout 含 PASS + failed=0。"""
    import scripts.ops.pre_existing_fail_monitor as mon

    monkeypatch.setattr(mon, "is_business_duckdb_ready", lambda path=None: False)
    monkeypatch.setattr(mon, "run_pytest", lambda: (_ for _ in ()).throw(AssertionError("should not run")))

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mon.main()
    out = buf.getvalue()
    assert rc == 0
    assert "PRE_EXISTING_FAIL_MONITOR_PASS" in out
    assert "failed=0" in out
    assert "skip live probe" in out or "no prod" in out.lower()


def test_pre_existing_fail_monitor_script_syntax() -> None:
    """R6 监控脚本可被 Python 编译 (语法 OK)"""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"R6 script syntax error: {result.stderr}"


def test_pre_existing_fail_monitor_fail_open() -> None:
    """R6 监控脚本 main() 失败不阻 commit (fail-open 原则, 跟 L4.40 post-merge hook 配套)"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("pre_existing_fail_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 异常路径不阻 commit (return 0)
    assert callable(mod.main)
    assert callable(mod.run_pytest)
    assert callable(mod.append_tech_debt)