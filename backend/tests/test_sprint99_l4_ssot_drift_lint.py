"""Sprint 99 L4.20 close-memory SSOT drift lint regression tests."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/check_ssot_drift.py"
HANDOFF = ROOT / "docs/sprints/HANDOFF-TO-CODEX-Sprint99-Close-LongTail11-SSOT-Drift.md"
FIX_COMMIT = "287efb8"


def test_sprint99_close_memory_references_real_fix_commit_sha() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    assert f"commit={FIX_COMMIT}" in text

    result = subprocess.run(
        ["git", "cat-file", "-e", f"{FIX_COMMIT}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{FIX_COMMIT} 不是真实 commit"


def test_sprint99_close_memory_marks_longtail_11_closed() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    assert "留尾 #11 | ✅ 闭环" in text


def test_ssot_drift_lint_detects_unmarked_longtail(tmp_path: Path) -> None:
    bad_handoff = tmp_path / "HANDOFF-TO-CODEX-Sprint100-Bad-Close.md"
    bad_handoff.write_text(
        "# Sprint 100\n\n"
        "<!-- L4.20-CLOSE-MEMORY -->\n"
        "- 留尾 #11 | Sprint 91 未修，继续留尾\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--docs-root",
            str(tmp_path),
            "--repo-root",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "留尾 # 未按 L4.20 标记" in result.stdout


def test_ssot_drift_lint_source_scan_min_lint_lines() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert len(source.splitlines()) >= 100
    assert "留尾 #" in source
    assert "✅ 闭环" in source
    assert "📋 推后" in source
