"""Sprint 17 #121 ground-truth-lint 测试.

19 个 test (Sprint 17 R1-R4 + Sprint 19 R5 + Sprint 20 P1-1 R5 扩 Optional):
- 4 个 true-positive (R1 缺 RatioField, R2 缺 PercentageField, R3 缺 PpField, R4 List["X"] 前向引用)
- 4 个 false-positive 检查 (合规 RatioField, 合规 PercentageField, 合规 PpField, 合规 List[Annotated[X, Field(...)]])
- 4 个 R5 (Sprint 19): List[RatioField/PercentageField] + Annotated 合规 + 非 ratio
- 5 个 R5a (Sprint 20 P1-1): Optional[List[X]] / List[Optional[X]] / List[X|None] / Union[List[X],None] / 合规 Annotated

每个 test 创建临时 .py 文件, 调用 lint_contract_file, assert issue 数.
"""
from pathlib import Path

from backend.contracts._lint import lint_contract_file


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
    yoy_pcts: List[Annotated[float, Field(ge=-1_000_000_000_000.0, le=1_000_000_000_000.0)]] = []
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


# ============================================================
# Sprint 19 #1 R5: 递归 List element-wise 检查 (4 个)
# ============================================================

class TestR5ListElementWise:
    """R5 (Sprint 19 #1): List[T] 字段 (T 是 ratio/pct/ppt 约束类型) 必须用
    List[Annotated[float, Field(ge, le)]] 否则 Pydantic 不会触发 element-wise 约束.

    4 个测试:
    - 2 个 true-positive (违规,期望 R5 issue)
    - 2 个 false-positive (合规,期望 0 issue)
    """

    def test_r5_list_ratio_field(self, tmp_path):
        """R5: List[RatioField] (无 Annotated 包装) -> R5 issue."""
        content = '''from typing import List
from pydantic import BaseModel
from backend.contracts.types import RatioField

class BadContract(BaseModel):
    daily_ratios: List[RatioField] = []
'''
        p = _write_tmp(tmp_path, "bad_list_ratio.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "RatioField" in r5[0].message
        assert "Annotated" in r5[0].message

    def test_r5_list_pct_field(self, tmp_path):
        """R5: List[PercentageField] (无 Annotated 包装) -> R5 issue."""
        content = '''from typing import List
from pydantic import BaseModel
from backend.contracts.types import PercentageField

class BadContract(BaseModel):
    daily_pcts: List[PercentageField] = []
'''
        p = _write_tmp(tmp_path, "bad_list_pct.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "PercentageField" in r5[0].message

    def test_r5_list_annotated_compliant(self, tmp_path):
        """合规: List[Annotated[float, Field(ge, le)]] -> 0 issue."""
        content = '''from typing import List, Annotated
from pydantic import BaseModel, Field

class GoodContract(BaseModel):
    daily_ratios: List[Annotated[float, Field(ge=0.0, le=1.0)]] = []
    daily_pcts: List[Annotated[float, Field(ge=-1_000_000_000_000.0, le=1_000_000_000_000.0)]] = []
    daily_ppts: List[Annotated[float, Field(ge=-100.0, le=100.0)]] = []
'''
        p = _write_tmp(tmp_path, "good_list_annotated.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"

    def test_r5_list_non_ratio(self, tmp_path):
        """非 ratio 类型 List[str] / List[int] -> 不报 (R5 不触发)."""
        content = '''from typing import List
from pydantic import BaseModel

class GoodContract(BaseModel):
    names: List[str] = []
    counts: List[int] = []
'''
        p = _write_tmp(tmp_path, "good_list_non_ratio.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert r5 == [], f"R5 不应触发, 实际: {[i.message for i in r5]}"


# ============================================================
# Sprint 20 P1-1 R5 扩 Optional 包装 (5 个)
# ============================================================

class TestR5OptionalWrappers:
    """R5 Sprint 20 P1-1 扩展: Optional / PEP 604 / Union 包装的 List 字段.

    4 个 true-positive (违规,期望 R5 issue):
    - Optional[List[RatioField]]  (Optional 套 List)
    - List[Optional[RatioField]]  (List 套 Optional)
    - List[RatioField | None]     (PEP 604 inside List)
    - Union[List[PpField], None]  (Union Tuple slice)
    1 个 false-positive (合规,期望 0 issue):
    - List[Optional[Annotated[float, Field(...)]]]  (Annotated 算合规)
    """

    def test_r5a_optional_list_ratio(self, tmp_path):
        """R5a: Optional[List[RatioField]] -> R5 issue (Sprint 19 漏掉, Sprint 20 治根)."""
        content = '''from typing import List, Optional
from pydantic import BaseModel
from backend.contracts.types import RatioField

class BadContract(BaseModel):
    daily_ratios: Optional[List[RatioField]] = None
'''
        p = _write_tmp(tmp_path, "bad_opt_list_ratio.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "RatioField" in r5[0].message
        assert "Annotated" in r5[0].message

    def test_r5a_list_optional_pct(self, tmp_path):
        """R5a: List[Optional[PercentageField]] -> R5 issue (Sprint 20 P1-1 新增)."""
        content = '''from typing import List, Optional
from pydantic import BaseModel
from backend.contracts.types import PercentageField

class BadContract(BaseModel):
    daily_pcts: List[Optional[PercentageField]] = []
'''
        p = _write_tmp(tmp_path, "bad_list_opt_pct.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "PercentageField" in r5[0].message

    def test_r5a_list_pep604_ppt(self, tmp_path):
        """R5a: List[PpField | None] (PEP 604) -> R5 issue (Sprint 20 P1-1 新增)."""
        content = '''from typing import List
from pydantic import BaseModel
from backend.contracts.types import PpField

class BadContract(BaseModel):
    daily_ppts: List[PpField | None] = []
'''
        p = _write_tmp(tmp_path, "bad_list_pep604_ppt.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "PpField" in r5[0].message

    def test_r5a_union_list_ppt(self, tmp_path):
        """R5a: Union[List[PpField], None] (Union Tuple slice) -> R5 issue (Sprint 20 P1-1 新增)."""
        content = '''from typing import List, Union
from pydantic import BaseModel
from backend.contracts.types import PpField

class BadContract(BaseModel):
    daily_ppts: Union[List[PpField], None] = None
'''
        p = _write_tmp(tmp_path, "bad_union_list_ppt.py", content)
        issues = lint_contract_file(p)
        r5 = [i for i in issues if i.rule == "R5"]
        assert len(r5) == 1, f"期望 1 个 R5, 实际 {len(r5)}: {[i.message for i in r5]}"
        assert "PpField" in r5[0].message

    def test_r5a_list_optional_annotated_compliant(self, tmp_path):
        """合规: List[Optional[Annotated[float, Field(...)]]] -> 0 issue (Annotated 算合规)."""
        content = '''from typing import List, Optional, Annotated
from pydantic import BaseModel, Field

class GoodContract(BaseModel):
    daily_ratios: List[Optional[Annotated[float, Field(ge=0.0, le=1.0)]]] = []
    daily_pcts: List[Optional[Annotated[float, Field(ge=-1_000_000_000_000.0, le=1_000_000_000_000.0)]]] = []
    daily_ppts: Optional[List[Annotated[float, Field(ge=-100.0, le=100.0)]]] = None
'''
        p = _write_tmp(tmp_path, "good_list_opt_annotated.py", content)
        issues = lint_contract_file(p)
        assert issues == [], f"期望 0 issue, 实际: {[i.message for i in issues]}"
