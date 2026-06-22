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

        deleted, _ = codex_clone_gc.gc_once()

        assert deleted == 2, f"期望删 2 个 (> 7d), 实际 {deleted}"
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

    def test_main_skips_on_non_darwin(self, monkeypatch):
        """Case 5: main() 在非 darwin 平台跳过 gc_once (Sprint 66 P1 治根).

        防再发: 平台特定检查必须在 main() 入口 (CLAUDE.md L4.10), 不能在 gc_once() 核心逻辑里.
        Sprint 66 P1 CI FAILURE 真因 = gc_once() 含 sys.platform == "darwin" 检查,
        Linux CI runner 上 return (0, 0) 直接跳过, 4 个 case 全 FAILURE.

        这个测试验证: main() 在非 darwin 平台 return 0 + 不调 gc_once.
        """
        from scripts.launchd import codex_clone_gc

        # 记录 gc_once 是否被调
        gc_once_called: list[bool] = []
        def mock_gc_once():
            gc_once_called.append(True)
            return 0, 0
        monkeypatch.setattr(codex_clone_gc, "gc_once", mock_gc_once)

        # 模拟非 darwin 平台 (如 Linux CI runner)
        monkeypatch.setattr(codex_clone_gc.sys, "platform", "linux")

        result = codex_clone_gc.main()

        assert result == 0, f"main() 在非 darwin 应 return 0, 实际 {result}"
        assert gc_once_called == [], (
            f"main() 在非 darwin 平台不应调用 gc_once, 但被调了 {len(gc_once_called)} 次"
        )

    def test_main_calls_gc_once_on_darwin(self, monkeypatch):
        """Case 6: main() 在 darwin 平台调 gc_once (Sprint 66 P1 治根配对).

        防再发: 验证 main() 在 darwin 平台会调 gc_once (不能过度防御).
        跟 Case 5 配对: 平台检查只在 main() 入口, gc_once() 任意 OS 可测.
        """
        from scripts.launchd import codex_clone_gc

        # 记录 gc_once 是否被调
        gc_once_called: list[bool] = []
        def mock_gc_once():
            gc_once_called.append(True)
            return 0, 0
        monkeypatch.setattr(codex_clone_gc, "gc_once", mock_gc_once)

        # 模拟 darwin 平台 (本地开发)
        monkeypatch.setattr(codex_clone_gc.sys, "platform", "darwin")

        result = codex_clone_gc.main()

        assert result == 0, f"main() 在 darwin 应 return 0, 实际 {result}"
        assert gc_once_called == [True], (
            f"main() 在 darwin 平台应调 gc_once 1 次, 实际 {len(gc_once_called)} 次"
        )