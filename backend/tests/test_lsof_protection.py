"""
PR3: lsof 副检 — fail-closed 单元 + Layer 6 集成

变更 (相对 Sprint 26 F6):
  - lsof 不可用 / 超时 / 报错 → is_open=True (fail-closed, 跳过删除)
  - Layer 6 不再扫全局 /tmp; 仅 private tmp / tracker
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestIsOpenByAnyProcess:
    def test_empty_stdout_returns_false(self):
        from scripts.etl.common.open_check import is_open_by_any_process

        fake_result = MagicMock()
        fake_result.stdout = "COMMAND  PID  USER   FD   TYPE             DEVICE  SIZE/OFF       NODE        NAME\n"
        fake_result.returncode = 0
        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch("scripts.etl.common.open_check.subprocess.run", return_value=fake_result):
                is_open, reason = is_open_by_any_process("/tmp/fake_closed.duckdb")

        assert is_open is False
        assert "no process holds fd" in reason

    def test_nonempty_stdout_returns_true(self):
        from scripts.etl.common.open_check import is_open_by_any_process

        fake_result = MagicMock()
        fake_result.stdout = (
            "COMMAND  PID  USER   FD   TYPE             DEVICE  SIZE/OFF       NODE        NAME\n"
            "python3  1234 hutou   3u   REG                1,5    12345678      12345       /tmp/fake_open.duckdb\n"
            "python3  5678 hutou   7u   REG                1,5    12345678      12345       /tmp/fake_open.duckdb\n"
        )
        fake_result.returncode = 0
        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch("scripts.etl.common.open_check.subprocess.run", return_value=fake_result):
                is_open, reason = is_open_by_any_process("/tmp/fake_open.duckdb")

        assert is_open is True
        assert "2 fd" in reason

    def test_lsof_missing_fail_closed(self):
        """PR3: lsof 不在 PATH → (True, fail-closed), 跳过删除."""
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value=None):
            is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is True
        assert "fail-closed" in reason

    def test_lsof_timeout_fail_closed(self):
        import subprocess
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch(
                "scripts.etl.common.open_check.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="lsof", timeout=2.0),
            ):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is True
        assert "fail-closed" in reason or "timeout" in reason.lower()

    def test_lsof_oserror_fail_closed(self):
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch(
                "scripts.etl.common.open_check.subprocess.run",
                side_effect=OSError("Permission denied"),
            ):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is True
        assert "fail-closed" in reason


class TestCleanupSubagentLsofGuard:
    def test_lsof_open_prevents_delete(self, tmp_path, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        big = priv / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (True, "lsof found 1 fd(s) [TEST]"),
        )

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=TrackerDB(), private_tmp=priv
        )

        assert result["deleted_count"] == 0
        assert result["skipped_open_count"] == 1
        assert big.exists()

    def test_lsof_empty_allows_delete(self, tmp_path, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        big = priv / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (False, "lsof empty (no process holds fd) [TEST]"),
        )

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=TrackerDB(), private_tmp=priv
        )

        assert result["deleted_count"] == 1
        assert not big.exists()

    def test_lsof_missing_fail_closed_does_not_delete(self, tmp_path, monkeypatch):
        """PR3: lsof 不可用 → fail-closed → 不删."""
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        big = priv / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (True, "lsof not found in PATH (fail-closed: skip delete)"),
        )

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=TrackerDB(), private_tmp=priv
        )

        assert result["deleted_count"] == 0
        assert result["skipped_open_count"] == 1
        assert big.exists()


class TestCleanupFqTmpLsofGuard:
    """Layer 1 (cli.py atexit) 仍用同一 lsof 护栏."""

    def test_lsof_layer1_skips_open(self, tmp_path, monkeypatch):
        from scripts.etl import cli

        wl_file = tmp_path / "_fq_ro_old.duckdb"
        wl_file.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(wl_file, (old, old))

        new_prefixes = (str(tmp_path / "_fq_ro"),)
        monkeypatch.setattr(cli, "FQ_TMP_PREFIXES", new_prefixes)
        marker = Path("/tmp/fuqing-etl-marker.json")
        marker.write_text('{"pid": 1, "started_at": "2026-06-17", "script": "test"}')
        try:
            monkeypatch.setattr(
                cli,
                "is_open_by_any_process",
                lambda p: (True, "lsof found 1 fd(s) [TEST]"),
            )
            deleted_count = cli._cleanup_fq_tmp_orphans()
        finally:
            marker.unlink(missing_ok=True)

        assert deleted_count == 0
        assert wl_file.exists()


class TestSprint31TrackerDbProtection:
    def test_tracker_db_in_protected_basenames(self):
        from scripts.etl import cleanup_subagent

        required = {
            "fuqing-tmp-tracker.db",
            "fuqing-tmp-tracker.db-wal",
            "fuqing-tmp-tracker.db-shm",
        }
        missing = required - cleanup_subagent._PROTECTED_BASENAMES
        assert not missing

    def test_layer6_skips_tracker_db_files(self, tmp_path, monkeypatch):
        from scripts.etl import cleanup_subagent

        for name in (
            "fuqing-tmp-tracker.db",
            "fuqing-tmp-tracker.db-wal",
            "fuqing-tmp-tracker.db-shm",
        ):
            f = tmp_path / name
            f.write_bytes(b"x" * 100)
            assert cleanup_subagent._is_protected(str(f)) is True
