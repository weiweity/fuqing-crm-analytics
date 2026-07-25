"""PR3 — cleanup_subagent 安全边界验收

覆盖:
  1. 专属目录过期可删
  2. 根外绝不删
  3. symlink 不删
  4. lsof 失败 fail-closed 不删
  5. 在用文件不删
  6. 嵌套目录按 tracker 处理
  7. 默认 dry-run 不删
  8. 非当前 UID / 硬链接异常跳过
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent.parent
import sys

sys.path.insert(0, str(ROOT))


def _age_file(path: Path, hours: float = 2.0, size: int = 100) -> None:
    path.write_bytes(b"x" * size)
    old = time.time() - hours * 3600
    os.utime(path, (old, old))


@pytest.fixture
def priv_tmp(tmp_path, monkeypatch):
    """隔离 private tmp + 关闭真实 tracker DB."""
    priv = tmp_path / "private"
    priv.mkdir(mode=0o700)
    monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))

    from scripts.etl.common import tmp_tracker
    from scripts.etl import cleanup_subagent

    tracker_db = tmp_path / "tracker.db"
    monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tracker_db))
    monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)
    monkeypatch.setattr(cleanup_subagent, "_MIN_AGE_HOURS", 1.0)
    monkeypatch.setattr(cleanup_subagent, "_TRACKER_MIN_AGE_HOURS", 1.0)
    # 默认 lsof 报空 (可删)
    monkeypatch.setattr(
        cleanup_subagent,
        "is_open_by_any_process",
        lambda p: (False, "lsof empty [TEST]"),
    )
    return priv


class TestPrivateDirExpiredDeletable:
    def test_private_top_level_expired_deleted(self, priv_tmp, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "orphan.bin"
        _age_file(big, hours=3, size=200)

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert result["deleted_count"] == 1
        assert not big.exists()


class TestOutsideRootNeverDeleted:
    def test_outside_private_and_untracked_not_collected(self, priv_tmp, tmp_path):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        outsider = tmp_path / "outside_root.bin"
        _age_file(outsider, hours=48, size=500)

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert outsider.exists(), "根外文件绝不能删"
        assert result["deleted_count"] == 0

    def test_tracker_poison_path_outside_allowed_skipped(self, priv_tmp, tmp_path):
        """即便 tracker 被投毒登记根外路径, resolve 后拒绝删除."""
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        victim = tmp_path / "not_allowed.doc"
        _age_file(victim, hours=48, size=500)
        tracker = TrackerDB()
        tracker.register(str(victim), size=500, pid=1)
        # 伪造 create_at 过期: register 用 now, 需直接 SQL 改 create_at
        import sqlite3
        import time as _t

        conn = sqlite3.connect(tracker.db_path)
        conn.execute(
            "UPDATE tracker SET create_at = ? WHERE path = ?",
            (_t.time() - 48 * 3600, str(victim.resolve())),
        )
        conn.commit()
        conn.close()

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=tracker,
            private_tmp=priv_tmp,
        )
        assert victim.exists(), "根外 tracker 投毒路径绝不能删"
        assert result["deleted_count"] == 0


class TestSymlinkNotDeleted:
    def test_symlink_skipped(self, priv_tmp, tmp_path):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        target = tmp_path / "real_target.bin"
        _age_file(target, hours=3, size=200)
        link = priv_tmp / "link.bin"
        link.symlink_to(target)

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert link.exists() or link.is_symlink()
        assert target.exists(), "symlink 目标也不能被误删"
        assert result["deleted_count"] == 0


class TestLsofFailClosed:
    def test_lsof_missing_does_not_delete(self, priv_tmp, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "orphan.bin"
        _age_file(big, hours=3, size=200)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (True, "lsof not found in PATH (fail-closed: skip delete)"),
        )
        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert big.exists()
        assert result["deleted_count"] == 0
        assert result["skipped_open_count"] == 1

    def test_lsof_timeout_does_not_delete(self, priv_tmp, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "orphan.bin"
        _age_file(big, hours=3, size=200)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (True, "lsof timeout after 2.0s (fail-closed: skip delete)"),
        )
        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert big.exists()
        assert result["deleted_count"] == 0


class TestOpenFileNotDeleted:
    def test_in_use_file_skipped(self, priv_tmp, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "inuse.bin"
        _age_file(big, hours=3, size=200)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (True, "lsof found 1 fd(s)"),
        )
        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert big.exists()
        assert result["skipped_open_count"] == 1
        assert result["deleted_count"] == 0


class TestNestedDirViaTrackerOnly:
    def test_nested_untracked_not_deleted(self, priv_tmp):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        nested = priv_tmp / "nested" / "deep.bin"
        nested.parent.mkdir()
        _age_file(nested, hours=3, size=200)

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert nested.exists(), "嵌套未跟踪文件不应被递归扫删"
        assert result["deleted_count"] == 0

    def test_nested_tracked_expired_deleted(self, priv_tmp):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB
        import sqlite3
        import time as _t

        nested = priv_tmp / "nested" / "tracked.bin"
        nested.parent.mkdir()
        _age_file(nested, hours=3, size=200)

        tracker = TrackerDB()
        tracker.register(str(nested), size=200, pid=1)
        conn = sqlite3.connect(tracker.db_path)
        conn.execute(
            "UPDATE tracker SET create_at = ? WHERE path = ?",
            (_t.time() - 48 * 3600, str(nested.resolve())),
        )
        conn.commit()
        conn.close()

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=tracker,
            private_tmp=priv_tmp,
        )
        assert result["deleted_count"] == 1
        assert not nested.exists()


class TestDefaultDryRun:
    def test_default_dry_run_does_not_delete(self, priv_tmp):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "orphan.bin"
        _age_file(big, hours=3, size=200)

        result = cleanup_subagent.cleanup_subagent_tmp(
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )  # dry_run 默认 True
        assert result["dry_run"] is True
        assert result["candidates_scanned"] >= 1
        assert result["deleted_count"] == 0
        assert big.exists()


class TestHardlinkAndUid:
    def test_hardlink_anomaly_skipped(self, priv_tmp, tmp_path):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        a = priv_tmp / "a.bin"
        _age_file(a, hours=3, size=200)
        b = priv_tmp / "b.bin"
        try:
            os.link(a, b)
        except OSError:
            pytest.skip("hardlink not supported on this fs")

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        # nlink=2 → 两个都应跳过
        assert a.exists() and b.exists()
        assert result["deleted_count"] == 0

    def test_uid_mismatch_skipped(self, priv_tmp, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common.tmp_tracker import TrackerDB

        big = priv_tmp / "orphan.bin"
        _age_file(big, hours=3, size=200)

        real_lstat = os.lstat

        class FakeStat:
            def __init__(self, st):
                self.st_mode = st.st_mode
                self.st_uid = st.st_uid + 9999  # 非当前
                self.st_nlink = st.st_nlink
                self.st_size = st.st_size
                self.st_mtime = st.st_mtime

        def fake_lstat(path):
            st = real_lstat(path)
            if Path(path).name == "orphan.bin":
                return FakeStat(st)
            return st

        monkeypatch.setattr(cleanup_subagent.os, "lstat", fake_lstat)
        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False,
            tracker=TrackerDB(),
            private_tmp=priv_tmp,
        )
        assert big.exists()
        assert result["deleted_count"] == 0


class TestOpenCheckFailClosedUnit:
    def test_is_open_missing_lsof_fail_closed(self):
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value=None):
            is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")
        assert is_open is True
        assert "fail-closed" in reason

    def test_is_open_timeout_fail_closed(self):
        import subprocess
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch(
                "scripts.etl.common.open_check.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="lsof", timeout=2.0),
            ):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")
        assert is_open is True
        assert "fail-closed" in reason

    def test_empty_still_allows(self):
        from scripts.etl.common.open_check import is_open_by_any_process
        from unittest.mock import MagicMock

        fake = MagicMock()
        fake.stdout = "COMMAND  PID  USER   FD   TYPE\n"
        fake.returncode = 0
        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch("scripts.etl.common.open_check.subprocess.run", return_value=fake):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")
        assert is_open is False
