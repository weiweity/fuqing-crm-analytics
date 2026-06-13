"""
Sprint 22 #29 regression test: ground-truth-lint 白名单覆盖 4 字段.

4 字段业务上可超 1, 命名 _ratio 是历史遗留, 走白名单跳过 R1 强约束 (跟 Sprint 18 #141
yoy_*_ratio 同款决定). 防止后续改 _lint.py 不小心删白名单 → 这 4 字段被 R1 误报.

覆盖:
  - common.py: WoolPartyBreakdown.type1_ratio / type2_ratio
  - sampling.py: SamplingLockYOY / SamplingSamplingLockAnalysis new_locked_ratio
"""
from pathlib import Path

from backend.contracts import _lint

ROOT = Path(__file__).parent.parent.parent


def test_non_ratio_business_over_one_whitelist_has_4_fields():
    """白名单必须包含 4 字段 (Sprint 22 #29 决策). 防白名单被改/被删."""
    expected = {"type1_ratio", "type2_ratio", "new_locked_ratio"}
    actual = set(_lint._NON_RATIO_BUSINESS_OVER_ONE)
    # new_locked_ratio 可能在 sampling.py 出现 2 次, frozenset 去重, 实际是 3 个 unique name
    assert actual == expected, (
        f"Sprint 22 #29 白名单应包含 {expected}, 实际 {actual}. "
        f"如果新增字段: 同步更新 common.py / sampling.py 测试 + CHANGELOG."
    )


def test_lint_returns_zero_issues_for_4_fields():
    """跑 _lint 实际 0 issue (4 字段不被 R1 误报)."""
    issues = []
    for py_path in sorted(_lint.CONTRACT_DIR.glob("*.py")):
        if py_path.name in ("_lint.py", "__init__.py", "types.py", "schemas.py"):
            continue
        issues.extend(_lint.lint_contract_file(py_path))
    r1_issues = [i for i in issues if i.rule == "R1"
                 and i.field in _lint._NON_RATIO_BUSINESS_OVER_ONE]
    assert not r1_issues, (
        f"_NON_RATIO_BUSINESS_OVER_ONE 字段不应触发 R1, 但报: "
        f"{[(i.file, i.line, i.field, i.message) for i in r1_issues]}"
    )


def test_common_type1_ratio_above_one_legitimate():
    """B2 audit 业务测试 (Sprint 17 #120 已建): type1_ratio > 1 合法 (跨品类用户重复计)."""
    from backend.contracts.common import WoolPartyBreakdown
    wp = WoolPartyBreakdown(
        type1_count=10, type2_count=20, total_count=30,
        type1_ratio=1.5,  # 跨品类累加 > 1
        type2_ratio=0.5,
    )
    assert wp.type1_ratio == 1.5
    assert wp.type2_ratio == 0.5


def test_sampling_new_locked_ratio_above_one_legitimate():
    """new_locked_ratio (cur-ly)*100 可超 1 (Sprint 18 #141 注释已知)."""
    from backend.contracts.sampling import SamplingLockYOY
    yoy = SamplingLockYOY(new_locked_ratio=45.0)  # (0.55 - 0.1) * 100 = 45
    assert yoy.new_locked_ratio == 45.0
