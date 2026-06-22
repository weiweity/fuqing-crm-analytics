"""
Sprint 62.5 B4: Codex code_sign_clone GC 验证 (2026-06-22)

痛点: Codex 累积 40 份 code_sign_clone = 53GB.
治根: scripts/launchd/codex_clone_gc.py 每天清理 > 7d 保留最新 1 份.

4 case 覆盖关键 safety check: mtime / keep_min / lsof open / 仅扫描 Codex+Chrome.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestCodexCloneGc:
    """Sprint 62.5 B4: GC 4 case 验证."""

    def _make_clone(self, path: Path, days_old: int) -> Path:
        """造一个 code_sign_clone.{rand} 目录 + 1 文件 + 设 mtime."""
        path.mkdir(parents=True, exist_ok=True)
        (path / "marker.txt").write_bytes(b"x" * 100)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))
        return path

    def test_gc_deletes_clones_older_than_retention(self, tmp_path, monkeypatch):
        """Case 1: > 7d clone 被删, 最新保留."""
        from scripts.launchd import codex_clone_gc

        # 造 X_DIR 跟 target_dir
        x_dir = tmp_path / "tz" / "user1" / "X"
        target_dir = x_dir / "com.openai.codex.code_sign_clone"
        new = self._make_clone(target_dir / "com.openai.codex.code_sign_clone.NEW", days_old=1)
        old1 = self._make_clone(target_dir / "com.openai.codex.code_sign_clone.OLD1", days_old=8)
        old2 = self._make_clone(target_dir / "com.openai.codex.code_sign_clone.OLD2", days_old=12)

        # 把 glob 路径换成我们的 tmp_path
        monkeypatch.setattr(codex_clone_gc, "X_DIR_GLOB_BASE", tmp_path / "tz")

        # Sprint 66 P1 排查: CI runner 上 deleted=0 但本地 PASS. 加诊断输出 (pytest -s 也捕获不了,
        # 写断言 message 里). 抓真因靠 assertion message.
        clones = codex_clone_gc._collect_clones()
        deleted, _ = codex_clone_gc.gc_once()

        assert deleted == 2, (
            f"期望删 2 个 (> 7d), 实际 {deleted}. "
            f"DEBUG: X_DIR_GLOB_BASE={codex_clone_gc.X_DIR_GLOB_BASE} "
            f"is_dir={codex_clone_gc.X_DIR_GLOB_BASE.is_dir()} "
            f"cwd_exists={tmp_path.exists()} "
            f"target_dir_exists={target_dir.exists()} "
            f"clones_found={[c.name for c in clones]}"
        )
        assert new.exists(), "新 clone 不应被删"
        assert not old1.exists(), "old1 应被删"
        assert not old2.exists(), "old2 应被删"

    def test_gc_keeps_at_least_keep_min(self, tmp_path, monkeypatch):
        """Case 2: 全部 > 7d 时, 保留最新 KEEP_MIN 份."""
        from scripts.launchd import codex_clone_gc

        x_dir = tmp_path / "tz" / "user1" / "X"
        target_dir = x_dir / "com.openai.codex.code_sign_clone"
        self._make_clone(target_dir / "com.openai.codex.code_sign_clone.A", days_old=12)
        self._make_clone(target_dir / "com.openai.codex.code_sign_clone.B", days_old=8)
        self._make_clone(target_dir / "com.openai.codex.code_sign_clone.C", days_old=1)

        monkeypatch.setattr(codex_clone_gc, "X_DIR_GLOB_BASE", tmp_path / "tz")

        deleted, _ = codex_clone_gc.gc_once()

        assert deleted == 2, f"期望删 2 个 (留最新 1 份), 实际 {deleted}"
        remaining = sorted(target_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        assert len(remaining) == 1, f"期望保留 1 份 (KEEP_MIN), 实际 {len(remaining)}"
        assert "C" in remaining[0].name, f"最新应是 C, 实际 {remaining[0].name}"

    def test_gc_skips_lsof_open_clones(self, tmp_path, monkeypatch):
        """Case 3: lsof open 的 clone 不被删."""
        from scripts.launchd import codex_clone_gc

        x_dir = tmp_path / "tz" / "user1" / "X"
        target_dir = x_dir / "com.openai.codex.code_sign_clone"
        open_clone = self._make_clone(target_dir / "com.openai.codex.code_sign_clone.OPEN", days_old=10)
        # 新 clone (KEEP_MIN 守护, 必保留)
        self._make_clone(target_dir / "com.openai.codex.code_sign_clone.NEW", days_old=1)

        monkeypatch.setattr(codex_clone_gc, "X_DIR_GLOB_BASE", tmp_path / "tz")

        # mock lsof 返回有 fd 占用
        def mock_lsof_open(*args, **kwargs):
            return subprocess.CompletedProcess(args=["lsof"], returncode=0, stdout="12345\n", stderr="")

        monkeypatch.setattr(codex_clone_gc.subprocess, "run", mock_lsof_open)

        deleted, _ = codex_clone_gc.gc_once()

        assert deleted == 0, f"lsof open 时应跳过, 实际删了 {deleted}"
        assert open_clone.exists(), "lsof open 的 clone 不应被删"

    def test_gc_only_scans_target_names(self, tmp_path, monkeypatch):
        """Case 4: 仅扫描 com.openai.codex + com.google.Chrome, 其他不动."""
        from scripts.launchd import codex_clone_gc

        x_dir = tmp_path / "tz" / "user1" / "X"

        # 造目标 (Codex) + 干扰 (Safari)
        codex_dir = x_dir / "com.openai.codex.code_sign_clone"
        self._make_clone(codex_dir / "com.openai.codex.code_sign_clone.OLD", days_old=10)
        self._make_clone(codex_dir / "com.openai.codex.code_sign_clone.NEW", days_old=1)

        # 干扰: Safari clone (不在 TARGET_NAMES)
        safari_dir = x_dir / "com.apple.Safari.code_sign_clone"
        safari_old = self._make_clone(safari_dir / "code_sign_clone.SAFARI", days_old=10)

        monkeypatch.setattr(codex_clone_gc, "X_DIR_GLOB_BASE", tmp_path / "tz")

        deleted, _ = codex_clone_gc.gc_once()

        assert deleted == 1, f"期望删 1 个 (Codex old), 实际 {deleted}"
        assert safari_old.exists(), "Safari clone 不应被 GC 删"