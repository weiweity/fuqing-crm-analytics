"""PR3 — Layer 6 tracker 路径: 仅清理 tracker 登记且在允许根内的过期文件.

旧行为 (扫全局 /tmp 删 untracked orphan) 已废除.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def _force_expired(tracker, path: str, age_h: float = 48.0) -> None:
    conn = sqlite3.connect(tracker.db_path)
    conn.execute(
        "UPDATE tracker SET create_at = ? WHERE path = ?",
        (time.time() - age_h * 3600, str(Path(path).resolve())),
    )
    conn.commit()
    conn.close()


class TestLayer6TrackerSafeDelete:
    def test_tracked_under_private_tmp_deleted(self, tmp_path, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)
        monkeypatch.setattr(cleanup_subagent, "_TRACKER_MIN_AGE_HOURS", 1.0)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (False, "empty"),
        )

        target = priv / "fuqing_tracked.duckdb"
        target.write_bytes(b"x" * 200)
        old = time.time() - 2 * 3600
        os.utime(target, (old, old))

        tracker = TrackerDB()
        tracker.register(str(target), size=200, pid=1)
        _force_expired(tracker, str(target))

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=tracker, private_tmp=priv
        )
        assert result["deleted_count"] == 1
        assert not target.exists()

    def test_untracked_global_tmp_style_not_scanned(self, tmp_path, monkeypatch):
        """模拟全局 /tmp 风格路径: 不在 private tmp 且未跟踪 → 不进候选."""
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (False, "empty"),
        )

        # 全局风格孤儿 (不在 priv, 不在 tracker)
        fake_global = tmp_path / "global_orphan.duckdb"
        fake_global.write_bytes(b"x" * 200)
        old = time.time() - 2 * 3600
        os.utime(fake_global, (old, old))

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=TrackerDB(), private_tmp=priv
        )
        assert fake_global.exists()
        assert result["deleted_count"] == 0

    def test_protected_basenames_still_protected(self):
        from scripts.etl import cleanup_subagent

        required = {
            "fuqing-tmp-tracker.db",
            "fuqing-tmp-tracker.db-wal",
            "fuqing-tmp-tracker.db-shm",
        }
        missing = required - cleanup_subagent._PROTECTED_BASENAMES
        assert not missing

    def test_tracker_db_protected_even_in_private(self, tmp_path, monkeypatch):
        from scripts.etl import cleanup_subagent
        from scripts.etl.common import tmp_tracker
        from scripts.etl.common.tmp_tracker import TrackerDB

        priv = tmp_path / "priv"
        priv.mkdir(mode=0o700)
        monkeypatch.setenv("FQ_PRIVATE_TMP", str(priv))
        monkeypatch.setattr(tmp_tracker, "TRACKER_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)
        monkeypatch.setattr(
            cleanup_subagent,
            "is_open_by_any_process",
            lambda p: (False, "empty"),
        )

        db_file = priv / "fuqing-tmp-tracker.db"
        db_file.write_bytes(b"x" * 200)
        old = time.time() - 2 * 3600
        os.utime(db_file, (old, old))

        result = cleanup_subagent.cleanup_subagent_tmp(
            dry_run=False, tracker=TrackerDB(), private_tmp=priv
        )
        assert db_file.exists()
        assert result["deleted_count"] == 0
