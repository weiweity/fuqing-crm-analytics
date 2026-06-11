"""Sprint 17 #121 ground-truth-lint.

强制新 contract 字段用 Pydantic Field 元数据, 防 LLM 写无 RatioField/PercentageField/PpField 的 contract.

4 条规则 (从 Sprint 16.5 retrospective Section 6.3 提取):
  R1: 字段名以 _ratio 结尾 -> 必须 RatioField (0-1) 或 Annotated[float, Field(ge=0, le=1)]
  R2: 字段名以 _pct 结尾  -> 必须 PercentageField (0-1B) 或 Annotated[float, Field(ge=-1e9, le=1e9)]
  R3: 字段名以 _ppt 结尾  -> 必须 PpField (-100~+100) 或 Annotated[float, Field(ge=-100, le=100)]
  R4: List[X] 字段 where X 是 RatioField/PercentageField/PpField -> 必须用 List[Annotated[X, Field(...)]] 不许 List["X"] 前向引用

使用:
    cd backend && python -m backend.contracts._lint
    # 返 0 表示合规; 返 1 + issue 列表表示违规
"""
import ast
import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

CONTRACT_DIR = Path(__file__).parent

# 命名 -> (ge, le) 预期约束, 跟 backend/contracts/types.py 一致
RATIO_GE_LE = (0.0, 1.0)            # RatioField: 0-1 decimal
PCT_GE_LE = (-1_000_000_000.0, 1_000_000_000.0)  # PercentageField: 0-1B (yoy_absolute 兼容)
PPT_GE_LE = (-100.0, 100.0)         # PpField: -100~+100 pp 差


@dataclass
class LintIssue:
    file: str
    line: int
    field: str
    rule: str
    message: str
    severity: str = "error"  # error | warning


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    """检查 ClassDef 是否 BaseModel 子类 (ast 层面)."""
    for base in node.bases:
        # BaseModel 或 pydantic.BaseModel
        if isinstance(base, ast.Name) and base.id == "BaseModel":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


def _extract_field_args(call: ast.Call) -> dict:
    """从 ast.Call (e.g. Field(ge=0, le=1)) 提取 kwargs."""
    out = {}
    for kw in call.keywords:
        if kw.arg is None:
            continue
        try:
            out[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, SyntaxError):
            out[kw.arg] = None
    return out


def _annotation_has_constrained_float(annotation: ast.AST, ge: float, le: float) -> bool:
    """检查 annotation 是否带 ge/le 约束的 float 字段 (5 种合法写法).

    合法的 5 种写法:
      1) RatioField (直接 Name 引用, 假设从 types.py 导入) — 名称以 RatioField/PercentageField/PpField 开头
      2) Optional[RatioField] (Subscript of Optional)
      3) RatioField | None (PEP 604 BinOp)
      4) Annotated[float, Field(ge, le)] (Subscript of Annotated, 含 Field(ge, le) kwargs)
      5) "RatioField" (字符串前向引用, 单字段 OK — Pydantic v2 会解析为类型 alias)
    """
    # 写法 5: 字符串前向引用 "RatioField" — ast.Constant
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return _name_matches_constrained(annotation.value, ge, le)

    # 写法 1: 直接 Name 引用 (e.g. RatioField)
    if isinstance(annotation, ast.Name):
        return _name_matches_constrained(annotation.id, ge, le)

    # 写法 2: Optional[RatioField] / Optional["RatioField"] — Subscript(Name('Optional'), X)
    if isinstance(annotation, ast.Subscript):
        # PEP 585: Optional[X] = Subscript(value=Name('Optional'), slice=X)
        if isinstance(annotation.value, ast.Name) and annotation.value.id in ("Optional", "Union"):
            return _annotation_has_constrained_float(annotation.slice, ge, le)
        # Annotated[float, Field(ge, le)]
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Annotated":
            return _is_annotated_float_with_field(annotation.slice, ge, le)
        # 直接是 Name ("RatioField" / "PercentageField" / "PpField" — 前向引用)
        if isinstance(annotation.value, ast.Name):
            return _name_matches_constrained(annotation.value.id, ge, le)
        return False

    # 写法 3: PEP 604 — RatioField | None (BinOp)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        # 左/右只要一个合规就行
        return (_annotation_has_constrained_float(annotation.left, ge, le)
                or _annotation_has_constrained_float(annotation.right, ge, le))

    return False


def _is_annotated_float_with_field(slice_node: ast.AST, ge: float, le: float) -> bool:
    """检查 Annotated[X, Field(ge, le)] slice 是否合规 (X=float + kwargs 匹配)."""
    # Annotated[X, Field(...)] — Tuple slice, 至少 2 元素, 第 1 个是 float, 第 2+ 含 Field(ge, le)
    if not isinstance(slice_node, ast.Tuple):
        # 简单情况 Annotated[float, Field(ge, le)] slice 可能是单一节点
        # 实际 ast 用 Tuple[elts=[float, Field(...)]]
        return False
    elts = slice_node.elts
    if len(elts) < 2:
        return False
    # 第 1 个必须是 float
    if not (isinstance(elts[0], ast.Name) and elts[0].id == "float"):
        return False
    # 后续 element 至少 1 个 Field(ge=..., le=...) 匹配
    for elt in elts[1:]:
        if isinstance(elt, ast.Call):
            callee = elt.func
            is_field = (isinstance(callee, ast.Name) and callee.id == "Field") or \
                       (isinstance(callee, ast.Attribute) and callee.attr == "Field")
            if not is_field:
                continue
            kw = _extract_field_args(elt)
            ge_ok = ("ge" not in kw) or (kw["ge"] is not None and kw["ge"] <= ge + 1e-9)
            le_ok = ("le" not in kw) or (kw["le"] is not None and kw["le"] >= le - 1e-9)
            # 严格: 必须同时有 ge 和 le, 且覆盖预期范围
            if "ge" in kw and "le" in kw and ge_ok and le_ok:
                return True
    return False


def _name_matches_constrained(name: str, ge: float, le: float) -> bool:
    """检查 ast.Name 是否对应一个合规的 Field 类型 (用名称启发式).

    约定: backend/contracts/types.py 定义 3 个 type alias:
      - RatioField (ge=0, le=1)
      - PercentageField (ge=-1e9, le=1e9)
      - PpField (ge=-100, le=100)
    任何 Annotation 里出现这 3 个名字的 Name, 视为合规 (含前向引用 "RatioField" 在
    ast 层面是 Constant, 也会被识别).
    """
    # 去掉前向引用的引号 (e.g. 'RatioField' -> RatioField)
    if isinstance(name, str):
        name_lower = name.strip('"').strip("'").lower()
    else:
        return False
    if name_lower in ("ratiofield", "percentagefield", "ppfield"):
        return _name_range_match(name_lower, ge, le)
    return False


def _name_range_match(name_lower: str, ge: float, le: float) -> bool:
    """基于名称 + 预期 (ge, le) 推断是否合规 (启发式, 假设导入正确)."""
    # RatioField -> (0, 1) 严格; PercentageField -> (-1B, 1B); PpField -> (-100, 100)
    if name_lower == "ratiofield":
        return ge <= 0.0 + 1e-9 and le >= 1.0 - 1e-9
    if name_lower == "percentagefield":
        # 允许任意的 pct (Sprint 15 放宽到 1B 兼容 yoy_absolute)
        return ge <= -1_000_000_000.0 + 1e-9 and le >= 1_000_000_000.0 - 1e-9
    if name_lower == "ppfield":
        return ge <= -100.0 + 1e-9 and le >= 100.0 - 1e-9
    return False


def _is_list_with_forward_ref(annotation: ast.AST) -> bool:
    """检查 annotation 是否是 List["X"] (前向引用字符串) — 触发 R4 警告.

    Pydantic v2 知识点: List["RatioField"] 在前向引用解析后会丢 Field 元数据,
    必须用 List[Annotated[float, Field(...)]] 才会触发 element-wise 约束.
    """
    if not isinstance(annotation, ast.Subscript):
        return False
    # List / list
    if not (isinstance(annotation.value, ast.Name) and annotation.value.id in ("List", "list")):
        return False
    slice_node = annotation.slice
    # 内部直接是 Name (字符串 "X" 在 ast 里是 Constant(str))
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        # List["X"] — 前向引用, 触发 R4
        return True
    # Optional[List["X"]]
    if isinstance(slice_node, ast.Subscript):
        return _is_list_with_forward_ref(slice_node)
    return False


def lint_contract_file(py_path: Path) -> List[LintIssue]:
    """解析 1 个 contract .py, 返回 LintIssue 列表."""
    issues: List[LintIssue] = []
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [LintIssue(str(py_path), e.lineno or 0, "<file>", "SYNTAX", f"语法错误: {e}", "error")]

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_pydantic_model(node):
            continue
        for item in node.body:
            if not (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)):
                continue
            field_name = item.target.id
            field_line = item.lineno
            annotation = item.annotation

            # R1-R3: ratio/pct/ppt 命名约定
            if field_name.endswith("_ratio"):
                if not _annotation_has_constrained_float(annotation, *RATIO_GE_LE):
                    issues.append(LintIssue(
                        str(py_path), field_line, field_name, "R1",
                        f"{field_name} 字段名以 _ratio 结尾, 必须用 RatioField (0-1) 或 Annotated[float, Field(ge=0, le=1)]",
                        "error",
                    ))
            elif field_name.endswith("_pct"):
                if not _annotation_has_constrained_float(annotation, *PCT_GE_LE):
                    issues.append(LintIssue(
                        str(py_path), field_line, field_name, "R2",
                        f"{field_name} 字段名以 _pct 结尾, 必须用 PercentageField (0-1B) 或 Annotated[float, Field(ge=-1e9, le=1e9)]",
                        "error",
                    ))
            elif field_name.endswith("_ppt"):
                if not _annotation_has_constrained_float(annotation, *PPT_GE_LE):
                    issues.append(LintIssue(
                        str(py_path), field_line, field_name, "R3",
                        f"{field_name} 字段名以 _ppt 结尾, 必须用 PpField (-100~+100) 或 Annotated[float, Field(ge=-100, le=100)]",
                        "error",
                    ))

            # R4: List["X"] 前向引用
            if _is_list_with_forward_ref(annotation):
                issues.append(LintIssue(
                    str(py_path), field_line, field_name, "R4",
                    f"{field_name} 是 List[\"X\"] 前向引用, 不会触发 Pydantic element-wise 约束. 改 List[Annotated[float, Field(...)] 或显式 List[RatioField]",
                    "error",
                ))
    return issues


def main() -> int:
    issues: List[LintIssue] = []
    for py_path in sorted(CONTRACT_DIR.glob("*.py")):
        # 跳过工具自身 + 类型定义文件 + 包初始化 + 通用 schemas
        if py_path.name in ("_lint.py", "__init__.py", "types.py", "schemas.py"):
            continue
        issues.extend(lint_contract_file(py_path))

    if issues:
        for issue in issues:
            print(f"[{issue.severity.upper()}] {issue.file}:{issue.line} [{issue.rule}] {issue.field}: {issue.message}")
        print(f"\n{len(issues)} issue(s) found.")
        return 1
    else:
        print("OK All contracts pass ground-truth-lint")
        return 0


if __name__ == "__main__":
    sys.exit(main())
