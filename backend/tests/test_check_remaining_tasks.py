"""test_check_remaining_tasks.py — Sprint 67 3 case 最小测试 (Karpathy 简化版)

替代 13 case: 1 happy + 1 missing fail-open + 1 中文解析 = 3 essential case.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "scripts" / "check_remaining_tasks.py"


def _run(cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=10, cwd=cwd or REPO
    )


# Case 1: happy path — 解析真实 TECH-DEBT.md, exit 0, 至少 2 个留尾项
def test_happy_path_parses_tech_debt() -> None:
    result = _run()
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert "remaining" in out
    assert len(out["remaining"]) >= 2, f"应有 ≥ 2 个留尾项, 实际 {len(out['remaining'])}"
    # Sprint 98 已关闭 FilterBuilder 留尾；验证仍真实存在的规模化 benchmark 留尾
    titles = " ".join(r["title"] for r in out["remaining"])
    assert "D1 50m-scale benchmark" in titles, f"必含 D1 50m-scale benchmark, 实际: {titles}"


# Case 2: fail-open — 缺失 TECH-DEBT.md 不 crash
def test_fail_open_missing_tech_debt(tmp_path: Path) -> None:
    fake_td = tmp_path / "nonexistent.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--tech-debt", str(fake_td)],
        capture_output=True, text=True, timeout=10, cwd=REPO,
    )
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["remaining"] == []
    assert "warning" in out


# Case 3: 中文 + emoji 解析
def test_chinese_unicode() -> None:
    result = _run()
    out = json.loads(result.stdout)
    has_chinese = any(any("一" <= c <= "鿿" for c in r["title"]) for r in out["remaining"])
    assert has_chinese, "至少 1 项 title 含中文"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
