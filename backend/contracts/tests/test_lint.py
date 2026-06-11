"""Sprint 17 #121 ground-truth-lint 测试.

8 个 test:
- 4 个 true-positive (R1 缺 RatioField, R2 缺 PercentageField, R3 缺 PpField, R4 List["X"] 前向引用)
- 4 个 false-positive 检查 (合规 RatioField, 合规 PercentageField, 合规 PpField, 合规 List[Annotated[X, Field(...)]])

每个 test 创建临时 .py 文件, 调用 lint_contract_file, assert issue 数.
"""
import pytest
from pathlib import Path

from backend.contracts._lint import lint_contract_file, LintIssue


def _write_tmp(tmp_path: Path, name: str, content: str) -> Path:
    """写临时 contract 文件, 返回 Path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ============================================================
# True-positive 测试 (4 个) — 期望 lint 报错
# ============================================================

class TestTruePositives:
    """Linter 应正确报出 4 类违规."""

    def test_r1_missing_ratio_field(self, tmp_path):
        """R1: 字段名以 _ratio 结尾但用裸 float, 期望 1 个 R1 issue."""
        content = '''from pydantic import BaseModel

class BadContract(BaseModel):
    bad_ratio: float = 0.0
    good_ratio: float = 0.5
'''
        p = _write_tmp(tmp_path, "bad_ratio.py", content)
        issues = lint_contract_file(p)
        r1 = [i for i in issues if i.rule == "R1"]
        # 2 个 _ratio 字段都缺 RatioField, 期望 2 个 R1
        assert len(r1) == 2, f"期望 2 个 R1, 实际 {len(r1)}: {[i.message for i in r1]}"
        assert all(i.severity == "error" for i in r1)
        assert all(i.field.endswith("_ratio") for i in r1)

    def test_r2_missing_percentage_field(self, tmp_path):
        """R2: 字段名以 _pct 结尾但用裸 float, 期望 1 个 R2 issue."""
        content = '''from pydantic import BaseModel

class BadContract(BaseModel):
    conversion_pct: float = 42.0
    churn_pct: float = 5.0
'''
        p = _write_tmp(tmp_path, "bad_pct.py", content)
        issues = lint_contract_file(p)
        r2 = [i for i in issues if i.rule == "R2"]
        assert len(r2) == 2, f"期望 2 个 R2, 实际 {len(r2)}: {[i.message for i in r2]}"
        assert all("PercentageField" in i.message or "pct" in i.field for i in r2)

    def test_r3_missing_pp_field(self, tmp_path):
        """R3: 字段名以 _ppt 结尾但用裸 float, 期望 1 个 R3 issue."""
        content = '''from pydantic import BaseModel

class BadContract(BaseModel):
    yoy_ppt: float = 5.28
    diff_ppt: float = -2.5
'''
        p = _write_tmp(tmp_path, "bad_ppt.py", content)
        issues = lint_contract_file(p)
        r3 = [i for i in issues if i.rule == "R3"]
        assert len(r3) == 2, f"期望 2 个 R3, 实际 {len(r3)}: {[i.message for i in r3]}"
        assert all("PpField" in i.message for i in r3)

    def test_r4_list_forward_ref(self, tmp_path):
        """R4: List["RatioField"] 前向引用, 期望 1 个 R4 issue."""
        content = '''from typing import List
from pydantic import BaseModel

class BadContract(BaseModel):
    ratios: List["RatioField"] = []
    pcts: List["PercentageField"] = []
'''
        p = _write_tmp(tmp_path, "bad_list.py", content)
        issues = lint_contract_file(p)
        r4 = [i for i in issues if i.rule == "R4"]
        assert len(r4) == 2, f"期望 2 个 R4, 实际 {len(r4)}: {[i.message for i in r4]}"
        assert all("前向引用" in i.message for i in r4)


# ============================================================
# False-positive 测试 (4 个) — 期望 lint 不报错
# ============================================================

class TestFalsePositives:
    """Linter 不应误报合规的 contract."""

    def test_compliant_ratio_field(self, tmp_path):
        """合规: 字段名 _ratio 结尾用 RatioField, 期望 0 issue."""
        content = '''from pydantic import BaseModel
from backend.contracts.types import RatioField

class GoodContract(BaseModel):
    member_ratio: RatioField = 0.42
    old_ratio: RatioField = 0.7
'''
        p = _write_tmp(tmp_path, "good_ratio.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"

    def test_compliant_percentage_field(self, tmp_path):
        """合规: 字段名 _pct 结尾用 PercentageField, 期望 0 issue."""
        content = '''from pydantic import BaseModel
from backend.contracts.types import PercentageField
from typing import Optional

class GoodContract(BaseModel):
    yoy_pct: Optional[PercentageField] = None
    growth_pct: PercentageField = 12.5
'''
        p = _write_tmp(tmp_path, "good_pct.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"

    def test_compliant_pp_field(self, tmp_path):
        """合规: 字段名 _ppt 结尾用 PpField (含 PEP 604 | None 写法), 期望 0 issue."""
        content = '''from pydantic import BaseModel
from backend.contracts.types import PpField

class GoodContract(BaseModel):
    yoy_ppt: PpField | None = None
    diff_ppt: PpField = 5.28
'''
        p = _write_tmp(tmp_path, "good_ppt.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"

    def test_compliant_annotated_list(self, tmp_path):
        """合规: List[Annotated[float, Field(ge, le)]] 写法, 期望 0 issue (含 R4 跟 _ratio 命名的复合).

        注意: 字段名不以 _ratio/_pct/_ppt 结尾时, R1-R3 不触发, R4 只检查 List["X"] 前向引用.
        """
        content = '''from typing import List, Annotated
from pydantic import BaseModel, Field

class GoodContract(BaseModel):
    amounts: List[Annotated[float, Field(ge=0.0)]] = []
    pct_values: List[Annotated[float, Field(ge=0.0, le=100.0)]] = []
    # _pct 结尾 + Annotated[float, Field(ge=-1e9, le=1e9)] 也合规
    yoy_pcts: List[Annotated[float, Field(ge=-1_000_000_000.0, le=1_000_000_000.0)]] = []
'''
        p = _write_tmp(tmp_path, "good_list.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"


# ============================================================
# Bonus 测试: 跳过非 BaseModel + 跳过非 Annotated 字段
# ============================================================

class TestSkipRules:
    """Linter 应正确跳过非 contract 类."""

    def test_skip_non_basemodel_class(self, tmp_path):
        """非 BaseModel 类 (e.g. dataclass) 不应被检查."""
        content = '''from dataclasses import dataclass

@dataclass
class NotBaseModel:
    bad_ratio: float = 0.0
    bad_pct: float = 1.0
'''
        p = _write_tmp(tmp_path, "non_base.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"dataclass 不应被检查, 实际: {[i.message for i in issues]}"

    def test_syntax_error_returns_single_issue(self, tmp_path):
        """语法错误的 .py 文件应返 1 个 SYNTAX issue, 不抛异常."""
        content = '''from pydantic import BaseModel

class Bad(BaseModel
    x: int
'''
        p = _write_tmp(tmp_path, "syntax_err.py", content)
        issues = lint_contract_file(p)
        assert len(issues) == 1
        assert issues[0].rule == "SYNTAX"
        assert issues[0].severity == "error"
