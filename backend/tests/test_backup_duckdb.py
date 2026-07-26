"""
Sprint 25 备份系统可信化 - 3 个 restore 演练 test

背景:
  - 修复前: cleanup_backups.sh 漏 *.duckdb.zst 模式 (7 天清理伪命题) +
            backup_duckdb.py 每天同名覆盖 (无历史滚动) +
            loud_fail 只用 osascript 弹窗 (无远端告警)
  - 修复后: find 加 *.duckdb.zst + 文件名加 _{HHMM}

3 个 case 覆盖关键修复点, 不依赖真实 launchd / DuckDB.

Sprint 164: 飞书完整解耦, 删 _send_lark_alert 主通道 + lark mock. loud_fail 改走 osascript + mail 直接调用 (不依赖 lark 状态). Case 2 + Case 2b 合并为 Case 2 (本地告警直接走 osascript + mail).

Branch: fix/sprint25-backup-restore-trust-2026-06-16
"""
import inspect
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SCRIPT_DIR = ROOT / "scripts" / "etl"
sys.path.insert(0, str(ROOT))


class TestBackupDuckdbSprint25:
    """Sprint 25 备份系统可信化 3 个 case。"""

    def test_find_pattern_matches_all_backup_formats(self, tmp_path):
        """Case 1: cleanup_backups.sh find 表达式必须匹配 .parquet + .duckdb + .duckdb.zst.

        修复前: 只匹配 .parquet + .duckdb, 漏掉 zstd 压缩后的 .duckdb.zst,
                7 天清理伪命题, 实际 280GB 备份永久累积.
        修复后: 加 -o -name "*.duckdb.zst" 模式, 7 天真滚动.
        """
        # 造 3 种格式: .parquet + .duckdb + .duckdb.zst
        for ext in ("parquet", "duckdb", "duckdb.zst"):
            f = tmp_path / f"fuqing_crm_2026-06-08_0300.{ext}"
            f.write_bytes(b"x" * 100)
            old_time = time.time() - 8 * 86400
            os.utime(f, (old_time, old_time))

        # 跑修复后的 find 表达式 (跟 cleanup_backups.sh L67 一致)
        result = subprocess.run(
            ["find", str(tmp_path), "-type", "f",
             "(", "-name", "*.parquet",
             "-o", "-name", "*.duckdb",
             "-o", "-name", "*.duckdb.zst", ")",
             "-mtime", "+7"],
            capture_output=True, text=True, timeout=5,
        )
        matched_files = [Path(line) for line in result.stdout.strip().split("\n") if line]

        # 验证 3 种格式都被匹配
        assert len(matched_files) == 3, f"期望 3 个文件被匹配, 实际 {len(matched_files)}: {matched_files}"
        matched_names = {f.name for f in matched_files}
        assert "fuqing_crm_2026-06-08_0300.parquet" in matched_names
        assert "fuqing_crm_2026-06-08_0300.duckdb" in matched_names
        assert "fuqing_crm_2026-06-08_0300.duckdb.zst" in matched_names

    def test_legacy_copy_mode_is_hard_disabled(self, tmp_path, monkeypatch, capsys):
        """默认入口必须在创建目录、复制、压缩或告警前返回 2。"""
        from scripts.etl import backup_duckdb

        fake_duckdb = tmp_path / "fake_crm.duckdb"
        fake_duckdb.write_bytes(b"x" * 100)
        monkeypatch.setattr(backup_duckdb, "DUCKDB_PATH", fake_duckdb)
        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path / "backups")
        monkeypatch.setattr(
            backup_duckdb.subprocess,
            "run",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("legacy guard 不得启动 subprocess")
            ),
        )

        assert backup_duckdb.main() == 2
        assert not (tmp_path / "backups").exists()
        assert "REFUSED" in capsys.readouterr().out

    def test_main_contains_no_legacy_copy_or_compression(self):
        """入口实现不得恢复整库 copy2 / zstd 路径。"""
        from scripts.etl import backup_duckdb

        source = inspect.getsource(backup_duckdb.main)
        assert "shutil.copy2(" not in source
        assert "subprocess.run(" not in source
        assert "compressed_path =" not in source
        assert "if not verify_only" in source

    def test_verify_only_lock_conflict_is_not_false_green(
        self, tmp_path, monkeypatch, capsys
    ):
        """未实际打开数据库时必须返回非零，不能把锁冲突报告成验证成功。"""
        from scripts.etl import backup_duckdb

        lock_dir = tmp_path / "backup.lock.d"
        lock_dir.mkdir()
        monkeypatch.setattr(backup_duckdb, "LOCK_DIR", lock_dir)

        assert backup_duckdb.main(verify_only=True) == 1
        output = capsys.readouterr().out
        assert "verify-only did not run" in output
        assert lock_dir.exists()

    def test_verify_only_rejects_empty_orders_table(
        self, tmp_path, monkeypatch
    ):
        """文件可打开但没有业务数据时，生产 sanity check 必须返回非零。"""
        import duckdb

        from scripts.etl import backup_duckdb

        empty_db = tmp_path / "empty.duckdb"
        conn = duckdb.connect(str(empty_db))
        conn.execute("CREATE TABLE orders (pay_time TIMESTAMP)")
        conn.close()

        failures: list[str] = []
        monkeypatch.setattr(backup_duckdb, "DUCKDB_PATH", empty_db)
        monkeypatch.setattr(backup_duckdb, "LOCK_DIR", tmp_path / "backup.lock.d")
        monkeypatch.setattr(backup_duckdb, "loud_fail", failures.append)

        assert backup_duckdb.main(verify_only=True) == 1
        assert failures
        assert "non-empty rows" in failures[0]


class TestBackupDuckdbSprint625Retention:
    """Sprint 62.5 B1: backup retention 治根 — 4 个 case 验证 _prune_old_backups.

    Sprint 25 设计意图 (7 天滚动), 实施遗漏导致 4 份 zst 累积 169GB.
    Sprint 62.5 加 _prune_old_backups(), 8 项 safety check 后删 >7d zst.

    4 case 覆盖: age threshold / keep_min 守护 / 跳过非 zstd / 跳过 lsof open.
    """

    def _make_zst(self, path: Path, days_old: int) -> Path:
        """造 zst magic 头 + 设 mtime."""
        path.write_bytes(b"\x28\xb5\x2f\xfd" + b"\x00" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_prune_deletes_zst_older_than_retention(self, tmp_path, monkeypatch):
        """Case 1: > BACKUP_RETENTION_DAYS 天的 zst 被删, 新保留.

        Sprint 111: 显式 setattr KEEP_MIN=1 (隔离默认值 KEEP_MIN=2 变更),
        这个 case 专注验证 age threshold, 不依赖 KEEP_MIN 默认值.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_duckdb, "BACKUP_RETENTION_DAYS", 7)
        monkeypatch.setattr(backup_duckdb, "BACKUP_KEEP_MIN", 1)  # Sprint 111: 显式

        new = self._make_zst(tmp_path / "fuqing_crm_2026-06-22_0330.duckdb.zst", days_old=1)
        old1 = self._make_zst(tmp_path / "fuqing_crm_2026-06-14_0330.duckdb.zst", days_old=8)
        old2 = self._make_zst(tmp_path / "fuqing_crm_2026-06-10_0330.duckdb.zst", days_old=12)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 2, f"期望删 2 个 (> 7d), 实际 {deleted}"
        assert new.exists(), "新 zst 不应被删"
        assert not old1.exists(), "old1 应被删"
        assert not old2.exists(), "old2 应被删"

    def test_prune_keeps_at_least_keep_min(self, tmp_path, monkeypatch):
        """Case 2: 即便全部 > retention, 至少保留最新 BACKUP_KEEP_MIN 份.

        守护: 防 cap=0 / retention=0 时误删全部.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_duckdb, "BACKUP_RETENTION_DAYS", 7)
        monkeypatch.setattr(backup_duckdb, "BACKUP_KEEP_MIN", 2)

        # 造 3 份全部 > 7d (最老优先删, 但保留最新 2 份)
        self._make_zst(tmp_path / "fuqing_crm_2026-06-10_0330.duckdb.zst", days_old=12)
        self._make_zst(tmp_path / "fuqing_crm_2026-06-14_0330.duckdb.zst", days_old=8)
        self._make_zst(tmp_path / "fuqing_crm_2026-06-21_0330.duckdb.zst", days_old=1)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 1, f"期望删 1 个 (留最新 2 份), 实际 {deleted}"
        remaining = sorted(tmp_path.glob("*.duckdb.zst"), key=lambda p: p.stat().st_mtime, reverse=True)
        assert len(remaining) == 2, f"期望保留 2 份, 实际 {len(remaining)}"
        # 保留的是最新 2 份 (按 mtime 倒序)
        assert "06-21" in remaining[0].name, f"最新应是 06-21, 实际 {remaining[0].name}"
        assert "06-14" in remaining[1].name, f"次新应是 06-14, 实际 {remaining[1].name}"

    def test_prune_skips_non_zstd_files(self, tmp_path, monkeypatch):
        """Case 3: 缺 zstd magic 头的文件不被删 (防误删 .duckdb 等其他格式).

        Sprint 25 测试用 cleanup_backups.sh find *.parquet + *.duckdb + *.duckdb.zst,
        Sprint 62.5 Python 版只 glob *.duckdb.zst + magic 校验, 更严格.

        Sprint 111: 显式 setattr KEEP_MIN=1 (隔离默认值 KEEP_MIN=2 变更),
        这个 case 专注验证 non-zstd skip, 不依赖 KEEP_MIN 默认值.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_duckdb, "BACKUP_RETENTION_DAYS", 7)
        monkeypatch.setattr(backup_duckdb, "BACKUP_KEEP_MIN", 1)  # Sprint 111: 显式

        # 造非 zst (空文件, magic 不匹配)
        non_zst = tmp_path / "fuqing_crm_2026-06-10_0330.duckdb"
        non_zst.write_bytes(b"not zstd")
        old_time = time.time() - 10 * 86400
        os.utime(non_zst, (old_time, old_time))

        # 造真 zst (应被删)
        old_zst = self._make_zst(tmp_path / "fuqing_crm_2026-06-10_0330.duckdb.zst", days_old=10)
        # 造新 zst (应保留)
        new_zst = self._make_zst(tmp_path / "fuqing_crm_2026-06-22_0330.duckdb.zst", days_old=1)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 1, f"期望只删 1 个真 zst, 实际 {deleted}"
        assert non_zst.exists(), "非 zst 不应被删"
        assert not old_zst.exists(), "老 zst 应被删"
        assert new_zst.exists(), "新 zst 应保留"

    def test_prune_skips_lsof_open_files(self, tmp_path, monkeypatch):
        """Case 4: 正在被进程打开的 zst 不被删 (lsof 副检).

        Sprint 26 F6 经验: mtime 决策 + lsof 副检, 防 race condition.
        """
        from scripts.etl import backup_duckdb

        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_duckdb, "BACKUP_RETENTION_DAYS", 7)

        open_zst = self._make_zst(tmp_path / "fuqing_crm_2026-06-10_0330.duckdb.zst", days_old=10)

        # mock lsof 返回非空 (模拟有进程在用)
        def mock_lsof_open(*args, **kwargs):
            return subprocess.CompletedProcess(args=["lsof"], returncode=0, stdout="12345\n", stderr="")

        monkeypatch.setattr(backup_duckdb.subprocess, "run", mock_lsof_open)

        deleted = backup_duckdb._prune_old_backups()

        assert deleted == 0, f"lsof open 时应跳过, 实际删了 {deleted}"
        assert open_zst.exists(), "lsof open 的 zst 不应被删"
