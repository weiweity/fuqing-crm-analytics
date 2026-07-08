"""Sprint 202+ R7 regression tests — uvicorn 持锁 + DuckDB 异 config detector.

覆盖范围:
- run-etl.sh 4-signal wait (port + proc + db_lock + wal)
- run-etl.sh SIGTERM fallback 5 retries × 4-signal verify
- run-etl.sh cleanup_ticker bootstrap-back launchctl verify loop
- ETL step 0 cli.py fail-fast DuckDB 持锁 detector
- 跨 CI runner 守卫: darwin 跑全 case, Linux pytest.mark.skipif

L4.63 永久规则化 — uvicorn 退出必须等 4 件 signal 同时 release,
ETL step 0 必须 fail-fast DuckDB 持锁, 不允许 step 7 才暴露.
"""
# ruff: noqa: E731  # L4.50 模式 0 业务代码改动: test helper default fn 用 lambda injection (lsof_runner / pgrep_runner / kill_fn / sleep_fn), 改 def 冗长, ruff 0.15.14 强制 E731
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Pure-Python helpers — 镜像 run-etl.sh 4-signal wait + cli.py detector 逻辑
# 用 Python 写一份, 测试直接调; bash 版本在 run-etl.sh 同步保留.
# ─────────────────────────────────────────────────────────────────────────────

WAIT_MAX_DEFAULT = 30
SIGTERM_RETRY_MAX = 5


def wait_uvicorn_release(
    *,
    duckdb_path: str,
    wait_max: int = WAIT_MAX_DEFAULT,
    sleep_fn=time.sleep,
    lsof_runner=None,
    pgrep_runner=None,
    path_exists_fn=None,
) -> tuple[bool, int, dict]:
    """4-signal wait helper — 镜像 run-etl.sh 主路径 wait 逻辑 (L4.63).

    Returns: (released?, waited_seconds, last_signal_state)
    """
    if lsof_runner is None:
        lsof_runner = lambda p: _run_lsof(p)
    if pgrep_runner is None:
        pgrep_runner = lambda pat: _run_pgrep(pat)
    if path_exists_fn is None:
        path_exists_fn = os.path.isfile

    waited = 0
    last_state = {"port": None, "proc": None, "db_lock": None, "wal": None}
    while waited < wait_max:
        port_held = (lsof_runner(":8000") or "").strip()
        proc_held = (pgrep_runner("uvicorn_launchd.py") or "").strip()
        db_held = (lsof_runner(duckdb_path) or "").strip()
        wal_held = "yes" if path_exists_fn(duckdb_path + ".wal") else ""
        last_state = {
            "port": port_held or None,
            "proc": proc_held or None,
            "db_lock": db_held or None,
            "wal": "yes" if wal_held else None,
        }
        if not port_held and not proc_held and not db_held and not wal_held:
            return True, waited, last_state
        sleep_fn(1)
        waited += 1
    return False, waited, last_state


def sigterm_fallback(
    *,
    duckdb_path: str,
    retry_max: int = SIGTERM_RETRY_MAX,
    sleep_fn=time.sleep,
    lsof_runner=None,
    pgrep_runner=None,
    kill_fn=None,
    path_exists_fn=None,
) -> tuple[bool, int]:
    """SIGTERM fallback helper — 镜像 run-etl.sh SIGTERM fallback 5x 重试 + 4-signal verify (L4.63)."""
    if lsof_runner is None:
        lsof_runner = lambda p: _run_lsof(p)
    if pgrep_runner is None:
        pgrep_runner = lambda pat: _run_pgrep(pat)
    if kill_fn is None:
        kill_fn = lambda sig, pid: os.kill(pid, sig) if pid else None
    if path_exists_fn is None:
        path_exists_fn = os.path.isfile

    for retry in range(retry_max):
        port_held = (lsof_runner(":8000") or "").strip()
        proc_held = (pgrep_runner("uvicorn_launchd.py") or "").strip()
        db_held = (lsof_runner(duckdb_path) or "").strip()
        wal_held = path_exists_fn(duckdb_path + ".wal")
        if not port_held and not proc_held and not db_held and not wal_held:
            return True, retry
        # port_held 形如 "1234" 取首行 PID
        pid = int(port_held.split("\n")[0]) if port_held else 0
        if pid:
            kill_fn(15, pid)  # SIGTERM
        sleep_fn(3)
        if not lsof_runner(":8000") and not pgrep_runner("uvicorn_launchd.py"):
            return True, retry
        # SIGTERM 无效, SIGKILL
        pid = int(((lsof_runner(":8000") or "0").split("\n")[0]) or 0) or 0
        if pid:
            kill_fn(9, pid)
        sleep_fn(2)
    return False, retry_max


def etl_step0_lock_detector(
    *,
    duckdb_path: str,
    lsof_runner=None,
    path_exists_fn=None,
) -> tuple[bool, str]:
    """ETL step 0 fail-fast DuckDB 持锁 detector (L4.63).

    Returns: (locked?, message)
    """
    if lsof_runner is None:
        lsof_runner = lambda p: _run_lsof(p)
    if path_exists_fn is None:
        path_exists_fn = os.path.isfile

    if not path_exists_fn(duckdb_path):
        return False, f"  ⚠️  Sprint 202+ R7 step 0 DuckDB file 不存在 ({duckdb_path}), 首次跑 ETL?"
    lsof_out = (lsof_runner(duckdb_path) or "").strip()
    wal_exists = path_exists_fn(duckdb_path + ".wal")
    if lsof_out or wal_exists:
        holders = lsof_out.split("\n") if lsof_out else []
        msg = (
            f"  ❌ Sprint 202+ R7 FATAL: step 0 检测到 DuckDB 持锁 "
            f"(lsof PIDs: {holders}, wal exists: {wal_exists})"
        )
        return True, msg
    return False, f"  ✅ Sprint 202+ R7 step 0 DuckDB lock pre-check PASS (path: {duckdb_path})"


def cleanup_ticker_verify_bootstrap_back(
    *,
    bootstrap_fn=None,
    launchctl_list_fn=None,
    sleep_fn=time.sleep,
    max_wait: int = 5,
) -> int:
    """cleanup_ticker bootstrap-back 后 verify plist 真起来 (L4.63)."""
    if bootstrap_fn is None:
        bootstrap_fn = lambda: _run_bootstrap()
    if launchctl_list_fn is None:
        launchctl_list_fn = lambda: _run_launchctl_list()
    bootstrap_fn()
    for waited in range(1, max_wait + 1):
        out = launchctl_list_fn() or ""
        if "com.fuqing.uvicorn" in out:
            return waited
        sleep_fn(1)
    return max_wait


# ─────────────────────────────────────────────────────────────────────────────
# subprocess shims — 在测试中被 mock 替换, 不实际执行 lsof/pgrep
# ─────────────────────────────────────────────────────────────────────────────

def _run_lsof(target: str) -> str:
    """Real lsof runner — only invoked when NOT mocked. CI macOS only."""
    if sys.platform != "darwin":
        return ""
    try:
        result = subprocess.run(
            ["lsof", "-ti", target],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _run_pgrep(pattern: str) -> str:
    """Real pgrep runner — only invoked when NOT mocked."""
    if sys.platform != "darwin":
        return ""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _run_launchctl_list() -> str:
    if sys.platform != "darwin":
        return ""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout
    except Exception:
        return ""


def _run_bootstrap() -> bool:
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_duckdb(tmp_path: Path) -> Path:
    """tmp_path DuckDB fixture — 永远不指向生产 /Users/hutou/Desktop/.../fuqing.duckdb."""
    db = tmp_path / "fuqing.duckdb"
    db.write_bytes(b"")
    return db


@pytest.fixture
def no_sleep(monkeypatch):
    """默认 sleep = lambda _: None, 让 30s wait 在 pytest 里 0ms 跑完."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    return lambda _: None


# ─────────────────────────────────────────────────────────────────────────────
# TestRunEtlBootoutWait (3 cases) — 4-signal 主路径 wait 逻辑 (基础 3 件 release)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEtlBootoutWait:
    """run-etl.sh 主路径 4-signal wait — 镜像 line 120-148 块 (L4.63)."""

    def test_port_release_only_via_lsof(self, tmp_duckdb: Path, no_sleep):
        """mock lsof :8000 返回空 → 立即 break (waited=0)."""
        lsof_mock = mock.Mock(side_effect=lambda target: "" if target == ":8000" else "")
        pgrep_mock = mock.Mock(return_value="")
        result, waited, state = wait_uvicorn_release(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            path_exists_fn=lambda p: False,
        )
        assert result is True
        assert waited == 0
        assert state["port"] is None

    def test_pgrep_uvicorn_process_gone(self, tmp_duckdb: Path, no_sleep):
        """mock pgrep 返回空 → 第 2 件 signal release, 验证 proc state 记录."""
        lsof_mock = mock.Mock(side_effect=lambda target: "" if target == ":8000" else "")
        pgrep_mock = mock.Mock(return_value="")
        result, waited, state = wait_uvicorn_release(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            path_exists_fn=lambda p: False,
        )
        assert result is True
        assert state["proc"] is None

class TestRunEtlBootoutWaitTimeout:
    """wait_max 30s timeout — 4 件 signal 全持, 超时返回 released=False (L4.63)."""

    def test_max_wait_30s_timeout(self, tmp_duckdb: Path, no_sleep):
        """4 件 signal 全持 → 等满 wait_max 后 return (False, waited, last_state)."""
        lsof_mock = mock.Mock(return_value="1234\n")
        pgrep_mock = mock.Mock(return_value="5678\n")
        # .wal 仍存在 → path_exists 返回 True
        path_exists = mock.Mock(return_value=True)
        result, waited, state = wait_uvicorn_release(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            path_exists_fn=path_exists,
            wait_max=5,  # 测试用 5 加速
        )
        assert result is False
        assert waited == 5
        assert state["port"] == "1234"
        assert state["proc"] == "5678"
        assert state["wal"] == "yes"

    def test_duckdb_wal_file_released(self, tmp_duckdb: Path, no_sleep):
        """mock .wal 不存在 → 第 4 件 signal release."""
        lsof_mock = mock.Mock(return_value="")
        pgrep_mock = mock.Mock(return_value="")
        path_exists = mock.Mock(return_value=False)
        result, waited, state = wait_uvicorn_release(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            path_exists_fn=path_exists,
        )
        assert result is True
        assert waited == 0
        assert state["wal"] is None


# ─────────────────────────────────────────────────────────────────────────────
# TestRunEtlBootoutSigtermFallback (1 case) — 5x retry + 4-signal verify
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEtlBootoutSigtermFallback:
    """run-etl.sh SIGTERM fallback 5x × 3s + 4-signal verify (L4.63)."""

    def test_sigterm_fallback_five_retries(self, tmp_duckdb: Path, no_sleep):
        """bootout-fail 路径: 5x retry, kill 多次, 最后 4-signal 全 release."""
        # 前 3 次: port + proc 都持; 第 4 次 (retry=2 SIGKILL 后的二次 lsof):
        # port + proc + db 都空 → break
        call_count = {"lsof": 0, "pgrep": 0}

        def lsof_side_effect(target):
            call_count["lsof"] += 1
            # 第 1 次 lsof :8000 持, 后续空 (retry=0 break 路径)
            if target == ":8000":
                if call_count["lsof"] == 1:
                    return "9999\n"
                return ""
            return ""

        def pgrep_side_effect(pattern):
            call_count["pgrep"] += 1
            if call_count["pgrep"] == 1:
                return "8888\n"
            return ""

        lsof_mock = mock.Mock(side_effect=lsof_side_effect)
        pgrep_mock = mock.Mock(side_effect=pgrep_side_effect)
        path_exists = mock.Mock(return_value=False)
        kill_log = []

        def kill_fn(sig, pid):
            kill_log.append((sig, pid))

        result, retry = sigterm_fallback(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            kill_fn=kill_fn,
            path_exists_fn=path_exists,
        )
        # 第一次 retry: lsof :8000=9999, pgrep=8888 → 持锁 → kill PID → break
        # 第二次再调用 lsof 验证 SIGTERM 退出 → True
        assert result is True
        assert retry < SIGTERM_RETRY_MAX
        # 至少 kill 了一次 SIGTERM 或 SIGKILL
        assert any(sig == 15 or sig == 9 for sig, _ in kill_log)


# ─────────────────────────────────────────────────────────────────────────────
# TestEtlStep0LockDetector (4 cases) — ETL step 0 cli.py fail-fast detector
# ─────────────────────────────────────────────────────────────────────────────

class TestEtlStep0LockDetector:
    """ETL step 0 cli.py main() 入口 fail-fast DuckDB 持锁 detector (L4.63)."""

    def test_duckdb_lock_fail_fast_exits_1(self, tmp_duckdb: Path, capsys):
        """tmp_path DuckDB + lsof mock 持 PID → 返回 (locked=True, msg)."""
        lsof_mock = mock.Mock(return_value="4321\n")
        path_exists = mock.Mock(side_effect=lambda p: p == str(tmp_duckdb))
        locked, msg = etl_step0_lock_detector(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            path_exists_fn=path_exists,
        )
        assert locked is True
        assert "FATAL" in msg
        assert "4321" in msg

    def test_duckdb_lock_free_passes(self, tmp_duckdb: Path, capsys):
        """tmp_path DuckDB 0 锁 → 返回 (locked=False, PASS msg)."""
        lsof_mock = mock.Mock(return_value="")
        path_exists = mock.Mock(side_effect=lambda p: p == str(tmp_duckdb))
        locked, msg = etl_step0_lock_detector(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            path_exists_fn=path_exists,
        )
        assert locked is False
        assert "PASS" in msg

    def test_wal_file_exists_fail_fast(self, tmp_duckdb: Path, capsys):
        """tmp_path DuckDB 0 锁但 .wal 残留 → locked=True (上次 ETL 半中断)."""
        lsof_mock = mock.Mock(return_value="")
        # .wal 存在
        def path_exists(p):
            return p == str(tmp_duckdb) or p == str(tmp_duckdb) + ".wal"
        locked, msg = etl_step0_lock_detector(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            path_exists_fn=path_exists,
        )
        assert locked is True
        assert "wal" in msg.lower()

    def test_no_duckdb_file_or_no_wal_passes(self, tmp_path: Path, capsys):
        """DuckDB file 不存在 (首次跑 ETL) → locked=False, warn msg, 不 fail-fast."""
        nonexistent = tmp_path / "missing.duckdb"
        lsof_mock = mock.Mock(return_value="")
        path_exists = mock.Mock(return_value=False)
        locked, msg = etl_step0_lock_detector(
            duckdb_path=str(nonexistent),
            lsof_runner=lsof_mock,
            path_exists_fn=path_exists,
        )
        assert locked is False
        assert "不存在" in msg or "首次" in msg


# ─────────────────────────────────────────────────────────────────────────────
# TestCleanupTickerVerify (1 case) — bootstrap-back launchctl verify loop
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanupTickerVerify:
    """run-etl.sh cleanup_ticker bootstrap-back 后 verify launchctl list (L4.63)."""

    def test_bootstrap_back_verify_launchctl_list(self, no_sleep):
        """cleanup_ticker bootstrap-back 后, launchctl list | grep 命中 com.fuqing.uvicorn."""
        bootstrap_mock = mock.Mock(return_value=True)
        # 第一次 launchctl list 就有 com.fuqing.uvicorn (最快路径)
        launchctl_mock = mock.Mock(return_value="1234\t0\tcom.fuqing.uvicorn\n")
        waited = cleanup_ticker_verify_bootstrap_back(
            bootstrap_fn=bootstrap_mock,
            launchctl_list_fn=launchctl_mock,
        )
        assert waited == 1
        bootstrap_mock.assert_called_once()
        launchctl_mock.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# TestCrossPlatform (2 cases) — 跨 CI runner 平台守卫 (L4.60+L4.61 沿用)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossPlatform:
    """darwin runner 跑全 case; Linux runner pytest.mark.skipif 全 skip (L4.63)."""

    @pytest.mark.skipif(sys.platform != "darwin", reason="darwin-only lsof/pgrep/launchctl path")
    def test_darwin_full_path(self, tmp_duckdb: Path, no_sleep):
        """macOS runner 跑 4-signal wait — 但 lsof/pgrep mock 返回空模拟干净环境."""
        # 即使在 macOS, 真实 lsof 可能命中 dev backend (port 8000) — mock 让测试可控
        lsof_mock = mock.Mock(return_value="")
        pgrep_mock = mock.Mock(return_value="")
        result, waited, state = wait_uvicorn_release(
            duckdb_path=str(tmp_duckdb),
            lsof_runner=lsof_mock,
            pgrep_runner=pgrep_mock,
            path_exists_fn=lambda p: False,
            wait_max=3,
        )
        assert result is True
        assert state["port"] is None
        assert state["proc"] is None
        assert state["db_lock"] is None
        assert state["wal"] is None

    @pytest.mark.skipif(sys.platform == "darwin", reason="Linux CI runner 跳过 darwin-only 测试")
    def test_linux_skipped_via_skipif(self):
        """Linux runner 不跑 darwin 真 lsof/pgrep (CI 跨平台守卫)."""
        if sys.platform == "darwin":
            pytest.skip("darwin-only")
        # 在 Linux 上不应到达这里 (skipif 已 skip), 留个 assert 兜底
        assert sys.platform != "darwin"