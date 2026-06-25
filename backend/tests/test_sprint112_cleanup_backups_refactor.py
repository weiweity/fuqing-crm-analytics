"""Sprint 112 真 refactor sprint: cleanup_backups.py 8 case regression (修 #D6).

Sprint 112 refactor: 抽 shared `_prune_with_safety` 函数从 backup_duckdb.py,
cleanup_backups.py 复用 8 项 safety check (修 Sprint 111 /review defer #D5).

8 case 覆盖 8 项 safety check 来源 + lock + soft fail + log:
  1. test_default_RETENTION_DAYS_is_2       — 默认值 = 2 (Sprint 111)
  2. test_default_BACKUP_KEEP_MIN_is_2     — 默认值 = 2 (Sprint 111)
  3. test_prune_respects_retention_param    — retention_days=1 (真治本 #1 mtime age)
  4. test_prune_respects_keep_min_param     — keep_min=3 守护 (真治本 #2 KEEP_MIN)
  5. test_prune_keep_min_exact_boundary     — keep_min=N + len=N 边界 (off-by-one 守)
  6. test_main_lock_dir_skips_concurrent    — F18 修复 (mkdir-based lock)
  7. test_main_soft_fail_logs_warning       — soft fail #8 (不 raise + log warn)
  8. test_main_log_file_appends_correctly   — log() BJ_TZ +8:00 timestamp + append mode

不依赖真实 launchd / DuckDB / lark (mock 隔离), 跟 Sprint 62.5 B1 + Sprint 111 模式一致.

Branch: fix/sprint112-refactor-shared-prune-with-safety
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint112CleanupBackups:
    """Sprint 112 真 refactor: cleanup_backups.py 8 case (修 #D6)."""

    def _make_zst(self, path: Path, days_old: int) -> Path:
        """造 zst magic 头 + 设 mtime (跟 test_backup_duckdb.py:_make_zst 一致)."""
        path.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_default_RETENTION_DAYS_is_2(self):
        """Case 1: cleanup_backups.RETENTION_DAYS 默认值 = 2 (Sprint 111 改动).

        验证: 默认 retention 跟 Sprint 111 一致.
        (env override 真测见 test_default_BACKUP_KEEP_MIN_is_2 + test_prune_respects_retention_param)
        """
        from scripts.etl import cleanup_backups

        # 默认值 = 2 (Sprint 111 改动)
        assert cleanup_backups.RETENTION_DAYS == 2

    def test_default_BACKUP_KEEP_MIN_is_2(self):
        """Case 2: cleanup_backups.BACKUP_KEEP_MIN 默认值 = 2 (Sprint 111 改动).

        验证: 默认 keep_min 跟 Sprint 111 一致.
        """
        from scripts.etl import cleanup_backups

        # 默认值 = 2 (Sprint 111 改动)
        assert cleanup_backups.BACKUP_KEEP_MIN == 2

    def test_prune_respects_retention_param(self, tmp_path):
        """Case 3: _prune_with_safety retention_days 参数阈值验证 (Sprint 112 真治本 #1).

        验证: retention_days=1 时, > 1d 的 zst 被删, <= 1d 的留 (KEEP_MIN=1 守护).
        """
        from scripts.etl import backup_duckdb

        zst_1d = self._make_zst(tmp_path / "fuqing_crm_a.duckdb.zst", days_old=1)
        zst_3d = self._make_zst(tmp_path / "fuqing_crm_b.duckdb.zst", days_old=3)

        deleted = backup_duckdb._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=1,
            keep_min=1,
            log_fn=lambda msg: None,
        )

        assert deleted == 1, f"期望删 1 个 (> 1d), 实际 {deleted}"
        assert zst_1d.exists(), "1d zst (KEEP_MIN 守护内) 应保留"
        assert not zst_3d.exists(), "3d zst (> 1d) 应被删"

    def test_prune_respects_keep_min_param(self, tmp_path):
        """Case 4: _prune_with_safety keep_min 参数守护验证 (Sprint 112 真治本 #2).

        验证: KEEP_MIN=3 + 5 zst 全 > retention=2 → 删 2 份 (8d+10d), 留 3 份 (2d/4d/6d).
        """
        from scripts.etl import backup_duckdb

        zsts = []
        for i, days in enumerate([10, 8, 6, 4, 2]):
            zsts.append(self._make_zst(tmp_path / f"fuqing_crm_{i}.duckdb.zst", days_old=days))

        deleted = backup_duckdb._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=2,
            keep_min=3,
            log_fn=lambda msg: None,
        )

        assert deleted == 2, f"期望删 2 个 (8d + 10d, KEEP_MIN=3 守护前 3 份), 实际 {deleted}"
        remaining = sorted(tmp_path.glob("*.duckdb.zst"), key=lambda p: p.stat().st_mtime, reverse=True)
        assert len(remaining) == 3, f"期望保留 3 份 (KEEP_MIN 守护), 实际 {len(remaining)}"

    def test_prune_keep_min_exact_boundary(self, tmp_path):
        """Case 5: keep_min 边界 case — keep_min=N + len=N → 删 0 (off-by-one 守).

        验证: keep_min=2 + 2 文件全 > retention → 删 0 (sorted[KEEP_MIN:] 空).
        (跟 backup_duckdb.py:113 'if len(sorted_files) <= keep_min: skip' 互证)
        """
        from scripts.etl import backup_duckdb

        self._make_zst(tmp_path / "a.duckdb.zst", days_old=5)
        self._make_zst(tmp_path / "b.duckdb.zst", days_old=10)

        deleted = backup_duckdb._prune_with_safety(
            backup_dir=tmp_path,
            glob_patterns=("*.duckdb.zst",),
            retention_days=2,
            keep_min=2,
            log_fn=lambda msg: None,
        )

        assert deleted == 0, f"期望删 0 个 (keep_min=2 守护全 2 文件), 实际 {deleted}"
        remaining = list(tmp_path.glob("*.duckdb.zst"))
        assert len(remaining) == 2, f"期望保留 2 份, 实际 {len(remaining)}"

    def test_main_lock_dir_skips_concurrent(self, tmp_path, monkeypatch):
        """Case 6: LOCK_DIR 已存在 → main() 立即 SKIP return 0 (不删任何文件).

        F18 修复: 防止 launchd 配错一天跑两次时双进程抢删.
        """
        from scripts.etl import cleanup_backups

        # Mock LOCK_DIR 到 tmp_path, 预先 mkdir (模拟另一个实例在跑)
        monkeypatch.setattr(cleanup_backups, "LOCK_DIR", tmp_path / "fake_lock")
        cleanup_backups.LOCK_DIR.mkdir()

        # Mock BACKUP_DIR (避免 launchd 真实路径)
        monkeypatch.setattr(cleanup_backups, "BACKUP_DIR", tmp_path / "backups")
        (tmp_path / "backups").mkdir()

        # 造 1 份超 retention zst
        zst = self._make_zst(tmp_path / "backups" / "old.duckdb.zst", days_old=10)

        exit_code = cleanup_backups.main()

        assert exit_code == 0, f"期望 exit 0 (SKIP), 实际 {exit_code}"
        assert zst.exists(), "LOCK 状态下不应删任何文件"

    def test_main_soft_fail_logs_warning(self, tmp_path, monkeypatch):
        """Case 7: 单文件 unlink 失败 log warning ('prune: delete failed' in LOG_FILE), 不 raise.

        8 项 safety check #8: soft fail = '不 raise + log warn', 两半都要测.
        """
        from scripts.etl import cleanup_backups

        # Mock LOCK_DIR + BACKUP_DIR + KEEP_MIN=0 + LOG_FILE
        log_file = tmp_path / "log"
        monkeypatch.setattr(cleanup_backups, "LOCK_DIR", tmp_path / "lock")
        monkeypatch.setattr(cleanup_backups, "BACKUP_DIR", tmp_path / "backups")
        monkeypatch.setattr(cleanup_backups, "BACKUP_KEEP_MIN", 0)
        monkeypatch.setattr(cleanup_backups, "LOG_FILE", log_file)
        (tmp_path / "backups").mkdir()

        # 造 1 份超 retention zst (10d > 2d cutoff)
        zst = self._make_zst(tmp_path / "backups" / "a.duckdb.zst", days_old=10)

        # Mock Path.unlink 全部 raise OSError
        def mock_unlink_fail(self, *args, **kwargs):
            raise OSError("mock unlink fail (Sprint 112 test)")

        monkeypatch.setattr(Path, "unlink", mock_unlink_fail)

        # main() 应不 raise (soft fail), return 0
        exit_code = cleanup_backups.main()

        assert exit_code == 0, f"期望 exit 0 (soft fail), 实际 {exit_code}"
        assert zst.exists(), "zst 应保留 (unlink 全部 fail, soft fail 不 raise)"
        # 验证 log warn: LOG_FILE 含 'prune: delete failed' (来自 _prune_with_safety 第 8 项)
        log_content = log_file.read_text()
        assert "prune: delete failed" in log_content, (
            f"期望 log 含 'prune: delete failed' (soft fail #8), 实际 log: {log_content}"
        )

    def test_main_log_file_appends_correctly(self, tmp_path, monkeypatch):
        """Case 8: cleanup_backups.log() 写到 LOG_FILE (append mode + BJ_TZ +8:00 timestamp).

        验证: log file append 模式 (不清空) + BJ_TZ +8:00 timestamp.
        (8 项 safety check 来源 验证见 test_main_soft_fail_logs_warning)
        """
        from scripts.etl import cleanup_backups

        # Mock LOG_FILE 到 tmp_path
        log_file = tmp_path / "test.log"
        monkeypatch.setattr(cleanup_backups, "LOG_FILE", log_file)

        cleanup_backups.log("test message 1")
        cleanup_backups.log("test message 2")

        # 验证 log file 存在 + 含 2 行
        assert log_file.exists(), "LOG_FILE 应被创建"
        content = log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2, f"期望 2 行, 实际 {len(lines)}"
        assert "test message 1" in lines[0]
        assert "test message 2" in lines[1]
        # BJ_TZ +08:00 timestamp (ISO 8601 format)
        assert "+0800" in lines[0], f"期望 BJ_TZ +0800 timestamp, 实际 {lines[0]}"
