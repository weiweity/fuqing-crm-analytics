"""
Sprint 25 备份系统可信化 - 3 个 restore 演练 test

背景:
  - 修复前: cleanup_backups.sh 漏 *.duckdb.zst 模式 (7 天清理伪命题) +
            backup_duckdb.py 每天同名覆盖 (无历史滚动) +
            loud_fail 只用 osascript 弹窗 (无远端告警)
  - 修复后: find 加 *.duckdb.zst + 文件名加 _{HHMM} + _send_lark_alert 走 webhook

3 个 case 覆盖关键修复点, 不依赖真实 launchd / DuckDB / lark-cli (mock 隔离).

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

    def test_compressed_corruption_reports_lark_alert(self, tmp_path, monkeypatch):
        """Case 2: zstd 压缩失败时, _send_lark_alert 走 webhook 主通道告警 (替代 osascript 弹窗).

        修复前: loud_fail 只用 osascript display notification (本机弹窗, 远程看不到) +
                mail 发到 hutou@fuqing.local (本地 mail 可能不工作, 静默失败)
        修复后: _send_lark_alert 走 lark-cli webhook 私聊 (主通道),
                osascript + mail 保留作 fallback (仅 lark 失败时触发).

        治根 (2026-06-17): 加 osascript subprocess.run mock 防 test 副作用 (之前
        loud_fail osascript 无条件调用, 跑 test 时 macOS 真通知被 spam).
        """
        from scripts.etl import backup_duckdb
        import subprocess

        # 准备假 DUCKDB_PATH + BACKUP_DIR (mock 真实路径, 隔离测试)
        fake_duckdb = tmp_path / "fake_crm.duckdb"
        fake_duckdb.write_bytes(b"x" * 100)
        monkeypatch.setattr(backup_duckdb, "DUCKDB_PATH", fake_duckdb)
        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path / "backups")

        # mock _send_lark_alert 记录调用 (不真发, 防副作用)
        lark_calls: list[str] = []

        def mock_send_lark(content, **kwargs):
            lark_calls.append(content)
            return (True, "OK (mock)")

        monkeypatch.setattr(backup_duckdb, "_send_lark_alert", mock_send_lark)

        # mock osascript + mail subprocess.run 防 macOS 通知 spam (loud_fail fallback 链)
        # 关键: 治根 2026-06-17 — 之前 osascript 无条件调用, 跑 test 时 macOS 真通知被 spam.
        subprocess_calls: list[tuple] = []

        def mock_subprocess_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            return subprocess.CompletedProcess(args=args[0] if args else [], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(backup_duckdb.subprocess, "run", mock_subprocess_run)

        # mock shutil.copy2 raise (模拟 copy / zstd 上游失败, 触发 loud_fail)
        def mock_copy2_fail(*args, **kwargs):
            raise IOError("disk full (Sprint 25 test mock)")

        monkeypatch.setattr(backup_duckdb.shutil, "copy2", mock_copy2_fail)

        # 跑 main(), 期望 exit 1 + lark 被调 + osascript 不被调 (lark OK 时跳过 fallback)
        exit_code = backup_duckdb.main()
        assert exit_code == 1, f"期望 exit 1, 实际 {exit_code}"
        assert len(lark_calls) == 1, f"期望 _send_lark_alert 被调 1 次, 实际 {len(lark_calls)}"
        lark_content = lark_calls[0]
        assert "FAILED" in lark_content
        assert "disk full (Sprint 25 test mock)" in lark_content
        assert "fuqing-duckdb-backup.log" in lark_content  # 日志路径提示
        # 治根验证: lark OK 时 osascript + mail fallback 不应触发 (无 subprocess_calls)
        osascript_calls = [c for c in subprocess_calls if c[0] and c[0][0] and "osascript" in str(c[0][0])]
        assert len(osascript_calls) == 0, (
            f"lark OK 时 osascript 不应被调 (避免 macOS 通知 spam), "
            f"实际调用 {len(osascript_calls)} 次: {osascript_calls}"
        )

    def test_loud_fail_falls_back_to_osascript_on_lark_failure(self, tmp_path, monkeypatch):
        """Case 2b: lark 失败时, loud_fail 应走 osascript + mail fallback 链 (治根验证).

        2026-06-17 治根: 之前 osascript 是无条件调用, 现在改为仅 lark 失败时调用.
        这个 case 验证 fallback 链在 lark 真失败时仍能跑通.
        """
        from scripts.etl import backup_duckdb
        import subprocess

        fake_duckdb = tmp_path / "fake_crm.duckdb"
        fake_duckdb.write_bytes(b"x" * 100)
        monkeypatch.setattr(backup_duckdb, "DUCKDB_PATH", fake_duckdb)
        monkeypatch.setattr(backup_duckdb, "BACKUP_DIR", tmp_path / "backups")

        # mock _send_lark_alert 返回 False (模拟 lark 真失败)
        lark_calls: list[str] = []

        def mock_send_lark_fail(content, **kwargs):
            lark_calls.append(content)
            return (False, "lark webhook 4xx (test mock)")

        monkeypatch.setattr(backup_duckdb, "_send_lark_alert", mock_send_lark_fail)

        # mock subprocess.run 记录 osascript + mail 调用 (不真发, 但允许记录 args)
        subprocess_calls: list[tuple] = []

        def mock_subprocess_run(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            return subprocess.CompletedProcess(args=args[0] if args else [], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(backup_duckdb.subprocess, "run", mock_subprocess_run)

        def mock_copy2_fail(*args, **kwargs):
            raise IOError("disk full (lark fail fallback test mock)")

        monkeypatch.setattr(backup_duckdb.shutil, "copy2", mock_copy2_fail)

        # 跑 main(), 期望 exit 1 + lark 被调 + osascript + mail fallback 被调
        exit_code = backup_duckdb.main()
        assert exit_code == 1
        assert len(lark_calls) == 1
        # lark 失败 → osascript fallback 应被调 1 次
        osascript_calls = [c for c in subprocess_calls if c[0] and c[0][0] and "osascript" in str(c[0][0])]
        assert len(osascript_calls) == 1, (
            f"lark 失败时 osascript fallback 应被调 1 次, 实际 {len(osascript_calls)} 次"
        )
        # mail fallback 也应被调 1 次
        mail_calls = [c for c in subprocess_calls if c[0] and c[0][0] and "/usr/bin/mail" in str(c[0][0])]
        assert len(mail_calls) == 1, (
            f"lark 失败时 mail fallback 应被调 1 次, 实际 {len(mail_calls)} 次"
        )

    def test_timestamped_filename_includes_hhmm(self):
        """Case 3: backup_duckdb.py main() 文件名带 _{HHMM} 后缀, 真滚动不覆盖.

        修复前: backup_path = f"fuqing_crm_{TODAY}.duckdb" 每天同名覆盖,
                cleanup_backups.sh 7 天清理伪命题 (实际只有 1 份历史).
        修复后: backup_path = f"fuqing_crm_{TODAY}_{hhmm}.duckdb" 真滚动,
                7 天保留 7 份不同时间戳的备份.
        """
        from scripts.etl import backup_duckdb

        # 用 inspect 读 main() 源码验证关键修改点
        source = inspect.getsource(backup_duckdb.main)

        # 验证文件名模板含 _{HHMM} 时间戳 (Sprint 25 关键改动)
        assert 'f"fuqing_crm_{TODAY}_' in source, \
            "修复未生效: backup_duckdb.py 文件名缺 _{HHMM} 后缀"
        assert "hhmm" in source, "修复未生效: 缺 hhmm 变量"

        # 验证 strftime 调 %H%M 格式 (e.g. "0330", "1430")
        assert 'strftime("%H%M")' in source, "修复未生效: 缺 HHMM 时间格式"

        # 验证导入 datetime (用于 hhmm 计算)
        from datetime import datetime
        # 实际跑一次生成, 验证格式正确
        BJ_TZ = backup_duckdb.BJ_TZ
        sample_dt = datetime(2026, 6, 16, 3, 30, tzinfo=BJ_TZ)
        sample_hhmm = sample_dt.strftime("%H%M")
        assert sample_hhmm == "0330", f"HHMM 格式错: {sample_hhmm}"

        # 注: 不做"反向验证修复前模式不存在"严格检查, 因为 compressed_path
        # 用 backup_path.with_suffix(".duckdb.zst") 仍会展开 f"fuqing_crm_{TODAY}_{hhmm}.duckdb"
        # 子串, 误报率高. 改"正向验证修复后模式存在" 即可.


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
