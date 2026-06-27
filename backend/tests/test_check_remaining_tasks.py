"""test_check_remaining_tasks.py — Sprint 67 3 case 最小测试 (Karpathy 简化版)

替代 13 case: 1 happy + 1 missing fail-open + 1 中文解析 = 3 essential case.

Sprint 135 改 (2026-06-27): Sprint 134 留尾 SSOT 暂收口 (Sprint 89 模式) 后,
留尾 bullets 全部标 ✅ 闭环, scripts/check_remaining_tasks.py grep 0 项.
test_happy_path + test_chinese_unicode 失配. 改成 "暂收口 mode 0 留尾 + 健壮性"
断言, 加 case 4 用 mock TECH-DEBT.md 验证 "有留尾时仍能 detect" (防止脚本
真被改坏, 0 留尾时无法发现).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "scripts" / "check_remaining_tasks.py"


def _run(cwd: Path | None = None, tech_debt: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if tech_debt is not None:
        cmd.extend(["--tech-debt", str(tech_debt)])
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=10, cwd=cwd or REPO
    )


# Case 1: 暂收口 mode happy path (Sprint 134 改) — 解析真实 TECH-DEBT.md, exit 0,
# Sprint 134 留尾全部标 ✅ 闭环, remaining == [] 是正确的稳态 (跟 Sprint 89 模式一致)
def test_happy_path_parses_tech_debt() -> None:
    result = _run()
    assert result.returncode == 0, f"exit code: {result.returncode}, stderr: {result.stderr}"
    out = json.loads(result.stdout)
    assert "remaining" in out
    assert "fetched_at" in out
    # Sprint 134 暂收口后剩余: 0 项是正确稳态 (Sprint 60+ 累计 60 sprint 0 debt 持续)
    assert len(out["remaining"]) == 0, (
        f"Sprint 134 暂收口后应为 0 留尾项, 实际 {len(out['remaining'])}: "
        f"{[r['title'] for r in out['remaining']]}"
    )


# Case 2: fail-open — 缺失 TECH-DEBT.md 不 crash (Sprint 67 持续, 暂收口 mode 仍 PASS)
def test_fail_open_missing_tech_debt(tmp_path: Path) -> None:
    fake_td = tmp_path / "nonexistent.md"
    result = _run(tech_debt=fake_td)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["remaining"] == []
    assert "warning" in out


# Case 3: 暂收口 mode 健壮性 — Sprint 67 原本测 "至少 1 项 title 含中文", 暂收口后
# 0 留尾无 title 可断言, 改测 JSON shape + 关键字段存在 (script 仍能跑通)
def test_chinese_unicode() -> None:
    result = _run()
    out = json.loads(result.stdout)
    # 0 留尾时验证 JSON shape 健壮性: remaining list + fetched_at timestamp
    assert "remaining" in out, f"JSON 必须含 remaining 字段, 实际 keys: {list(out.keys())}"
    assert isinstance(out["remaining"], list)
    assert "fetched_at" in out
    # 关键: script 不 crash + 返回合法 JSON
    assert result.returncode == 0, f"暂收口 mode script 必须 exit 0, 实际 {result.returncode}"


# Case 4: NEW (Sprint 135) — mock TECH-DEBT.md 含 2 留尾 bullet, 验证 script
# 真能 detect (防止 0 留尾时脚本被改坏无法发现). 用 tmp_path fixture 隔离.
def test_detects_remaining_when_present(tmp_path: Path) -> None:
    mock_td = tmp_path / "MOCK_TECH_DEBT.md"
    mock_td.write_text(
        "# MOCK\n\n"
        "- 📋 **D1 50m-scale benchmark**: 调研 0 进展, 触发 = 30M 数据量\n"
        "- 📋 **Sprint 105 follow-up #3**: DuckDB 锁 holder PID 白名单\n"
        "- ✅ **#S34-1 churn.py**: 漏 f 前缀治根 (Sprint 34.1)\n"
        "- 📋 **#S35+ 候选 2**: commit message ↔ diff 一致性\n",
        encoding="utf-8",
    )
    result = _run(tech_debt=mock_td)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    # 3 个 📋 推后项 (排除 1 个 ✅ 已闭环) — 验证 script 仍能 detect 真有留尾
    assert len(out["remaining"]) == 3, (
        f"mock 含 3 留尾, 实际 detect {len(out['remaining'])}: "
        f"{[r['title'] for r in out['remaining']]}"
    )
    titles = " ".join(r["title"] for r in out["remaining"])
    # 验证中文 + emoji + 多项 detect
    assert "D1 50m-scale benchmark" in titles
    assert "Sprint 105 follow-up #3" in titles
    assert "#S35+ 候选 2" in titles
    # 验证 desc 也被解析
    descs = " ".join(r["desc"] for r in out["remaining"])
    assert "30M" in descs
    assert "PID 白名单" in descs


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
