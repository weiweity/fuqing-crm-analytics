"""
Sprint 26 F6 (mtime→lsof 副检): /tmp 孤儿清理的最后一道防线单元测试

设计:
  - Layer 1 (cli.py atexit) + Layer 6 (cleanup_subagent.py hourly) 删前调
    is_open_by_any_process() 二次确认
  - 软失败: lsof 不可用 / 超时不阻塞 cleanup (返回 False, 保守放行)
  - 失败模式统一: (False, reason) — 调用方永不删已开文件

测试覆盖:
  1. test_lsof_open_prevents_delete: lsof 报开 → 跳过删除 (Layer 6)
  2. test_lsof_empty_allows_delete: lsof 报空 → 正常删除
  3. test_lsof_missing_soft_fails: lsof 不存在 → 返回 False, 不阻塞
  4. test_lsof_timeout_soft_fails: lsof 超时 → 返回 False, 不阻塞
  5. test_lsof_layer1_skips_open: Layer 1 atexit 也用同一护栏
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================
# 直接单测: scripts.etl.common.open_check
# ============================================================

class TestIsOpenByAnyProcess:
    """直接单测 is_open_by_any_process() — Sprint 26 F6 核心 helper."""

    def test_empty_stdout_returns_false(self):
        """lsof stdout 仅 header (无 fd 行) → (False, '...no process holds fd')."""
        from scripts.etl.common.open_check import is_open_by_any_process

        fake_result = MagicMock()
        fake_result.stdout = "COMMAND  PID  USER   FD   TYPE             DEVICE  SIZE/OFF       NODE        NAME\n"
        with patch("scripts.etl.common.open_check.subprocess.run", return_value=fake_result):
            is_open, reason = is_open_by_any_process("/tmp/fake_closed.duckdb")

        assert is_open is False
        assert "no process holds fd" in reason

    def test_nonempty_stdout_returns_true(self):
        """lsof stdout 有 fd 行 → (True, 'lsof found N fd(s)')."""
        from scripts.etl.common.open_check import is_open_by_any_process

        fake_result = MagicMock()
        fake_result.stdout = (
            "COMMAND  PID  USER   FD   TYPE             DEVICE  SIZE/OFF       NODE        NAME\n"
            "python3  1234 hutou   3u   REG                1,5    12345678      12345       /tmp/fake_open.duckdb\n"
            "python3  5678 hutou   7u   REG                1,5    12345678      12345       /tmp/fake_open.duckdb\n"
        )
        with patch("scripts.etl.common.open_check.subprocess.run", return_value=fake_result):
            is_open, reason = is_open_by_any_process("/tmp/fake_open.duckdb")

        assert is_open is True
        assert "2 fd" in reason

    def test_lsof_missing_soft_fails_to_false(self):
        """lsof 不在 PATH → 返回 (False, '...保守放行'), 不抛异常."""
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value=None):
            is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is False
        assert "not found" in reason.lower() or "保守放行" in reason

    def test_lsof_timeout_soft_fails_to_false(self):
        """lsof 超时 → 返回 (False, 'timeout ...'), 不抛异常."""
        import subprocess
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch(
            "scripts.etl.common.open_check.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lsof", timeout=2.0),
        ):
            with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is False
        assert "timeout" in reason.lower() or "保守放行" in reason

    def test_lsof_oserror_soft_fails_to_false(self):
        """lsof exec 抛 OSError → 返回 (False, '...exec error'), 不抛异常."""
        from scripts.etl.common.open_check import is_open_by_any_process

        with patch("scripts.etl.common.open_check.shutil.which", return_value="/usr/sbin/lsof"):
            with patch(
                "scripts.etl.common.open_check.subprocess.run",
                side_effect=OSError("Permission denied"),
            ):
                is_open, reason = is_open_by_any_process("/tmp/fake.duckdb")

        assert is_open is False
        assert "exec error" in reason.lower() or "保守放行" in reason


# ============================================================
# 集成测试: Layer 6 cleanup_subagent 用 lsof 护栏
# ============================================================

class TestCleanupSubagentLsofGuard:
    """Layer 6 (cleanup_subagent.py hourly) 在 lsof 报开时跳过删除."""

    def test_lsof_open_prevents_delete(self, tmp_path, monkeypatch):
        """候选文件被某进程打开 → cleanup 跳过, deleted_count=0."""
        from scripts.etl import cleanup_subagent

        big = tmp_path / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        # 用 monkeypatch 限定扫描根到 tmp_path, 避开真 /tmp 干扰
        monkeypatch.setattr(cleanup_subagent, "_SCAN_ROOTS", (str(tmp_path),))
        monkeypatch.setattr(cleanup_subagent, "_FQ_TMP_PREFIXES", (str(tmp_path) + "/fuqing_",))  # 让 helper 走
        monkeypatch.setattr(cleanup_subagent, "_EXCLUDE_PATH_PREFIXES", ())  # 放行 tmp_path
        monkeypatch.setattr(cleanup_subagent, "_PROTECTED_BASENAMES", set())
        monkeypatch.setattr(cleanup_subagent, "_is_excluded_ext", lambda p: False)
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)  # 测试小文件能进候选

        # mock lsof 报开
        def fake_lsof(path):
            return (True, "lsof found 1 fd(s) [TEST]")

        monkeypatch.setattr(cleanup_subagent, "is_open_by_any_process", fake_lsof)

        result = cleanup_subagent.cleanup_subagent_tmp(dry_run=False)

        assert result["deleted_count"] == 0
        assert result["skipped_open_count"] == 1
        assert result["candidates_scanned"] == 1
        assert big.exists(), "lsof 报开的文件绝不能删"

    def test_lsof_empty_allows_delete(self, tmp_path, monkeypatch):
        """候选文件没进程打开 → cleanup 正常删."""
        from scripts.etl import cleanup_subagent

        big = tmp_path / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(cleanup_subagent, "_SCAN_ROOTS", (str(tmp_path),))
        monkeypatch.setattr(cleanup_subagent, "_FQ_TMP_PREFIXES", (str(tmp_path) + "/fuqing_",))
        monkeypatch.setattr(cleanup_subagent, "_EXCLUDE_PATH_PREFIXES", ())
        monkeypatch.setattr(cleanup_subagent, "_PROTECTED_BASENAMES", set())
        monkeypatch.setattr(cleanup_subagent, "_is_excluded_ext", lambda p: False)
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        monkeypatch.setattr(
            cleanup_subagent, "is_open_by_any_process",
            lambda p: (False, "lsof empty (no process holds fd) [TEST]"),
        )

        result = cleanup_subagent.cleanup_subagent_tmp(dry_run=False)

        assert result["deleted_count"] == 1
        assert result["skipped_open_count"] == 0
        assert not big.exists(), "lsof 报空应该删掉"

    def test_lsof_missing_soft_fails_still_deletes(self, tmp_path, monkeypatch):
        """lsof 不可用 (软失败) → 仍按 mtime 决策删, 不阻塞."""
        from scripts.etl import cleanup_subagent

        big = tmp_path / "big.duckdb"
        big.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(big, (old, old))

        monkeypatch.setattr(cleanup_subagent, "_SCAN_ROOTS", (str(tmp_path),))
        monkeypatch.setattr(cleanup_subagent, "_FQ_TMP_PREFIXES", (str(tmp_path) + "/fuqing_",))
        monkeypatch.setattr(cleanup_subagent, "_EXCLUDE_PATH_PREFIXES", ())
        monkeypatch.setattr(cleanup_subagent, "_PROTECTED_BASENAMES", set())
        monkeypatch.setattr(cleanup_subagent, "_is_excluded_ext", lambda p: False)
        monkeypatch.setattr(cleanup_subagent, "_MIN_SIZE_BYTES", 1)

        # lsof 不可用时 is_open 返回 (False, ...) 软失败
        monkeypatch.setattr(
            cleanup_subagent, "is_open_by_any_process",
            lambda p: (False, "lsof not found in PATH (保守放行) [TEST]"),
        )

        result = cleanup_subagent.cleanup_subagent_tmp(dry_run=False)

        assert result["deleted_count"] == 1
        assert result["skipped_open_count"] == 0
        assert not big.exists(), "lsof 软失败 → 维持原 mtime 决策, 应该删"


# ============================================================
# 集成测试: Layer 1 cli atexit 用同一 lsof 护栏
# ============================================================

class TestCleanupFqTmpLsofGuard:
    """Layer 1 (cli.py atexit) 也走同一 lsof 护栏 (Sprint 26 F6 一致性)."""

    def test_lsof_layer1_skips_open(self, tmp_path, monkeypatch):
        """Layer 1: lsof 报开 → atexit 跳过删除."""
        from scripts.etl import cli

        wl_file = tmp_path / "_fq_ro_old.duckdb"
        wl_file.write_bytes(b"x" * 100)
        old = time.time() - 48 * 3600
        os.utime(wl_file, (old, old))

        new_prefixes = (str(tmp_path / "_fq_ro"),)
        monkeypatch.setattr(cli, "FQ_TMP_PREFIXES", new_prefixes)
        # 写一个 marker 让 cli 走"正常退出"分支, 不打 WARN 日志
        marker = Path("/tmp/fuqing-etl-marker.json")
        marker.write_text('{"pid": 1, "started_at": "2026-06-17", "script": "test"}')
        try:
            monkeypatch.setattr(
                cli, "is_open_by_any_process",
                lambda p: (True, "lsof found 1 fd(s) [TEST]"),
            )
            deleted_count = cli._cleanup_fq_tmp_orphans()
        finally:
            marker.unlink(missing_ok=True)

        assert deleted_count == 0
        assert wl_file.exists(), "Layer 1: lsof 报开的文件绝不能删"


# ============================================================
# Sprint 31.1 P2 finding: tracker DB + WAL sidecars 必须被 Layer 6 保护
# ============================================================

class TestSprint31TrackerDbProtection:
    """Sprint 31.1 P2 review finding: tracker DB 文件加进 _PROTECTED_BASENAMES.

    Defense-in-depth: 万一 tracker DB 长大 (e.g. 10万 rows 写满 1GB+) 触到
    Layer 6 1h+ 1GB+ 扫描阈值, 静态白名单保护避免整个 cleanup 失明.
    """

    def test_tracker_db_in_protected_basenames(self):
        """Sprint 31.1 P2: tracker DB + WAL sidecars 在保护名单."""
        from scripts.etl import cleanup_subagent

        required = {
            "fuqing-tmp-tracker.db",
            "fuqing-tmp-tracker.db-wal",
            "fuqing-tmp-tracker.db-shm",
        }
        missing = required - cleanup_subagent._PROTECTED_BASENAMES
        assert not missing, f"tracker DB basenames 缺失: {missing}"

    def test_layer6_skips_tracker_db_files(self, tmp_path, monkeypatch):
        """集成: Layer 6 扫描时 tracker DB 命名格式被 _is_protected 跳过."""
        from scripts.etl import cleanup_subagent

        # 造 3 个 tracker DB 命名文件, 1h+ 1GB+ (用 _MIN_SIZE_BYTES=1 触发)
        db_file = tmp_path / "fuqing-tmp-tracker.db"
        wal_file = tmp_path / "fuqing-tmp-tracker.db-wal"
        shm_file = tmp_path / "fuqing-tmp-tracker.db-shm"
        for f in (db_file, wal_file, shm_file):
            f.write_bytes(b"x" * 100)
            old = time.time() - 2 * 3600  # 2h 前
            os.utime(f, (old, old))

        # 验证 _is_protected 对 3 个文件都返 True
        for f in (db_file, wal_file, shm_file):
            assert cleanup_subagent._is_protected(str(f)) is True, (
                f"Layer 6 _is_protected 必须跳过 {f.name}"
            )