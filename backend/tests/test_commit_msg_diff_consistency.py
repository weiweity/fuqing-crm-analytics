from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "git" / "check_commit_msg_diff_consistency.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    # 隔离父 repo 的 hooksPath，避免临时仓库继承 .githooks/commit-msg/pre-commit
    _git(repo, "config", "core.hooksPath", str(repo / ".git" / "hooks"))

    target = repo / "SamplingView.vue"
    target.write_text("".join(f"line {i:03d}\n" for i in range(100)), encoding="utf-8")
    _git(repo, "add", "SamplingView.vue")
    _git(repo, "commit", "-qm", "feat: add sampling view")
    return repo, target


def _run_checker(repo: Path, message: str) -> subprocess.CompletedProcess[str]:
    message_path = repo / "COMMIT_MSG"
    message_path.write_text(message, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECKER), str(message_path)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def test_normal_message_passes_without_warning(tmp_path: Path) -> None:
    repo, target = _make_repo(tmp_path)
    target.write_text(target.read_text(encoding="utf-8") + "line 100\n", encoding="utf-8")
    _git(repo, "add", "SamplingView.vue")

    result = _run_checker(repo, "fix(view): update SamplingView.vue rendering\n")

    assert result.returncode == 0
    assert "WARN [commit-diff]" not in result.stderr


def test_mentioned_file_with_mass_deletion_warns_but_passes(tmp_path: Path) -> None:
    repo, target = _make_repo(tmp_path)
    target.write_text("".join(f"line {i:03d}\n" for i in range(10)), encoding="utf-8")
    _git(repo, "add", "SamplingView.vue")

    result = _run_checker(repo, "chore: clean SamplingView.vue business names\n")

    assert result.returncode == 0
    assert "WARN [commit-diff]" in result.stderr
    assert "SamplingView.vue" in result.stderr
    assert "90.0%" in result.stderr


def test_no_file_mention_skips_warning(tmp_path: Path) -> None:
    repo, target = _make_repo(tmp_path)
    target.write_text("".join(f"line {i:03d}\n" for i in range(10)), encoding="utf-8")
    _git(repo, "add", "SamplingView.vue")

    result = _run_checker(repo, "chore: clean legacy business names\n")

    assert result.returncode == 0
    assert "WARN [commit-diff]" not in result.stderr


def test_explicit_refactor_intent_suppresses_warning(tmp_path: Path) -> None:
    repo, target = _make_repo(tmp_path)
    target.write_text("".join(f"line {i:03d}\n" for i in range(10)), encoding="utf-8")
    _git(repo, "add", "SamplingView.vue")

    result = _run_checker(repo, "refactor(view): rewrite SamplingView.vue\n")

    assert result.returncode == 0
    assert "WARN [commit-diff]" not in result.stderr
