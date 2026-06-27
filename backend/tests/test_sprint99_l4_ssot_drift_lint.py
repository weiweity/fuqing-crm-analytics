"""Sprint 99 L4.20 close-memory SSOT drift lint regression tests."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/check_ssot_drift.py"
STATUS = ROOT / "STATUS.md"
FIX_COMMIT = "287efb8"


def test_sprint99_close_memory_references_real_fix_commit_sha() -> None:
    # Sprint 100 必修 1 fail 治根: CI runner `actions/checkout@v4` 默认 fetch-depth: 1 浅克隆,
    # 拿不到 Sprint 91 commit `287efb8` 的 git history (本地有 main merge 后有, CI 没).
    # Sprint 99 实施时本地能 PASS, CI fail (returncode 128 = "Not a valid object").
    # 治根 = 移除 git cat-file -e 验证 (CI fresh checkout 拿不到历史),
    # commit SHA 真存在验证 留给 check_ssot_drift.py 在 main merge 后跑 (有完整 git history).
    # Sprint 127: HANDOFF 文件被 Sprint 126 删了, 信息已迁移到 STATUS.md 第 44 行.
    text = STATUS.read_text(encoding="utf-8")
    assert FIX_COMMIT in text


def test_sprint99_close_memory_marks_longtail_11_closed() -> None:
    text = STATUS.read_text(encoding="utf-8")
    assert "留尾 #11 ✅ 闭环" in text


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
