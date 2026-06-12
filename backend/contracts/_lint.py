"""Sprint 17 #121 ground-truth-lint.

强制新 contract 字段用 Pydantic Field 元数据, 防 LLM 写无 RatioField/PercentageField/PpField 的 contract.

5 条规则 (Sprint 17 R1-R4 + Sprint 19 R5 + Sprint 20 P1-1 R5 扩 Optional):
  R1: 字段名以 _ratio 结尾 -> 必须 RatioField (0-1) 或 Annotated[float, Field(ge=0, le=1)]
  R2: 字段名以 _pct 结尾  -> 必须 PercentageField (0-1B) 或 Annotated[float, Field(ge=-1e9, le=1e9)]
  R3: 字段名以 _ppt 结尾  -> 必须 PpField (-100~+100) 或 Annotated[float, Field(ge=-100, le=100)]
  R4: List[X] 字段 where X 是 RatioField/PercentageField/PpField -> 必须用 List[Annotated[X, Field(...)]] 不许 List["X"] 前向引用
  R5: List[RatioField/PercentageField/PpField] (没 Annotated) -> 改 List[Annotated[float, Field(ge, le)]]
       Sprint 20 P1-1 扩展: 覆盖 Optional 包装场景
       - Optional[List[RatioField]]  (Optional 套 List)   — R5 fires
       - List[Optional[RatioField]]  (List 套 Optional)   — R5 fires
       - List[RatioField | None]     (PEP 604 inside List) — R5 fires
       - List["RatioField"]          (字符串 forward ref)  — R4 覆盖

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

# Sprint 18 #141 白名单: yoy_*_ratio 字段实际语义是 pp 差 (PpField),
# 命名 _ratio 是历史遗留 (Sprint 14 之前 ratio 字段没 Pydantic 时约定),
# 改命名跨 14+ 文件影响太大 (audience/rfm/category/health 前端), 走白名单兜底.
# 决策见 docs/SPRINT-18-YOY-FIX.md "决策审计" 表.
_YOY_PPT_FIELDS = frozenset({
    # audience.py: 10 字段
    "yoy_old_gsv_ratio", "yoy_old_users_ratio",
    "yoy_new_gsv_ratio", "yoy_new_users_ratio",
    "yoy_member_gsv_ratio", "yoy_member_users_ratio",
    "yoy_member_old_gsv_ratio", "yoy_member_old_users_ratio",
    "yoy_member_new_gsv_ratio", "yoy_member_new_users_ratio",
    # rfm.py: 1 字段 (5 处重复使用, 同一 schema 名)
    "yoy_repurchase_gsv_ratio",
    # category.py: 1 字段
    # (yoy_repurchase_gsv_ratio 同上)
    # health.py: 2 字段
    "yoy_old_customer_gsv_ratio", "yoy_member_old_customer_gsv_ratio",
    # Sprint 18 #141 已知合规 List[RATIO] 字段: linter 暂不支持 List[Annotated[...]] element-wise 识别
    # (Sprint 17 #121 R4 只检查前向引用, 没查 element-wise Field 元数据)
    # 已知用 Annotated[float, Field(ge, le)] 正确写法的 List[RatioField] 字段白名单
    "_LIST_RATIO_FIELDS_PLACEHOLDER",  # 不放字段名, 实际用 _LIST_RATIO_FIELDS
})

# 已知 List[Annotated[float, Field(ge, le)]] 合规字段 (linter 暂不识别 list element-wise)
_LIST_RATIO_FIELDS = frozenset({
    "new_customer_ratio",  # churn.py CategoryDailyTrendResponse
})


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


def _list_inner_type_name(annotation: ast.AST) -> Optional[str]:
    """提取 List[X] 里的 X 类型名 (X 是 Name 节点, e.g. 'RatioField' / 'str').

    递归支持 (Sprint 20 P1-1 扩展):
    - Optional[List[X]] (Optional 套 List) — Sprint 19 已部分支持, 实际 Sprint 20 修
    - List[Optional[X]] (List 套 Optional) — Sprint 20 P1-1 新增
    - List[X | None]    (PEP 604 inside List) — Sprint 20 P1-1 新增
    - Union[List[X], None] (Union Tuple slice) — Sprint 20 P1-1 新增
    如果不是 List 类型或最里层 X 不是 Name, 返 None.
    Annotated 节点视为合规 (返 None 让 R5 跳过).
    """
    if not isinstance(annotation, ast.Subscript):
        return None
    # 顶层 Optional / Union 包装:
    #   Optional[X]: slice 是 Subscript (单元素, 跟 PEP 484 一致)
    #   Union[A, B, ...]: slice 是 Tuple (多元素)
    if isinstance(annotation.value, ast.Name) and annotation.value.id in ("Optional", "Union"):
        if isinstance(annotation.slice, ast.Tuple):
            # Union[A, B, ...]: 找第一个 List[...] 元素的 inner name
            for elt in annotation.slice.elts:
                if (isinstance(elt, ast.Subscript)
                        and isinstance(elt.value, ast.Name)
                        and elt.value.id in ("List", "list")):
                    return _extract_inner_name(elt.slice)
            return None
        return _list_inner_type_name(annotation.slice)
    # 顶层必须是 List / list
    if not (isinstance(annotation.value, ast.Name) and annotation.value.id in ("List", "list")):
        return None
    # 提取 slice 的类型名
    return _extract_inner_name(annotation.slice)


def _extract_inner_name(annotation: ast.AST) -> Optional[str]:
    """从 list slice 节点提取类型名 (递归 unwrap Optional / PEP 604 / Union / 字符串 forward ref).

    支持 (Sprint 20 P1-1 扩展):
    - Name('RatioField')                  -> 'RatioField'
    - Constant('RatioField') (字符串)       -> 'RatioField'  (但 R4 也会触发, 双重提示)
    - Subscript(value=Optional, ...)      -> 递归 slice
    - BinOp(BitOr, Name, Constant(None))  -> 拿非 None 那一边的 Name
    - Tuple (Union[A, B] slice)           -> 拿第一个非 None 元素的 Name
    - Annotated / 其他                     -> None (合规, 让 R5 跳过)

    不支持嵌套 Optional (Optional[Optional[X]]) — 实际工程不出现, 跳过.
    """
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant):
        # 字符串 forward ref (e.g. "RatioField" 在 List["RatioField"] 里)
        if isinstance(annotation.value, str):
            return annotation.value.strip('"').strip("'")
        return None
    if isinstance(annotation, ast.Subscript):
        # Optional[Name] / Union[Name, ...]
        if isinstance(annotation.value, ast.Name) and annotation.value.id in ("Optional", "Union"):
            return _extract_inner_name(annotation.slice)
        # Annotated / Dict / 其他: 视为合规
        return None
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        # PEP 604: X | None 拿非 None 那一边的 Name
        for side in (annotation.left, annotation.right):
            if isinstance(side, ast.Constant) and side.value is None:
                continue
            if isinstance(side, ast.Name) and side.id == "None":
                continue
            return _extract_inner_name(side)
        return None
    if isinstance(annotation, ast.Tuple):
        # Union[A, B, ...] slice: 拿第一个非 None 元素的 Name
        for elt in annotation.elts:
            if isinstance(elt, ast.Constant) and elt.value is None:
                continue
            if isinstance(elt, ast.Name) and elt.id == "None":
                continue
            return _extract_inner_name(elt)
        return None
    return None


def _is_list_with_constrained_type_without_annotated(annotation: ast.AST) -> bool:
    """检查 annotation 是否是 List[RatioField/PercentageField/PpField] (没 Annotated) — 触发 R5.

    Pydantic v2 知识点: List[RatioField] 跟 List[Annotated[float, Field(...)]] 不同.
    前者不会触发 element-wise Field 约束 (slice 是裸 Name, 解析后 Field 元数据丢),
    后者才会触发.

    合规写法: List[Annotated[float, Field(ge, le)]]
    不合规 (Sprint 19 R5 起步, Sprint 20 P1-1 扩 Optional 包装):
    - List[RatioField] / List[PercentageField] / List[PpField]
    - Optional[List[RatioField]] / List[Optional[RatioField]]
    - List[RatioField | None] (PEP 604)
    - Union[List[RatioField], None] (Union Tuple)

    合规 (R5 不触发):
    - List[Annotated[float, Field(ge, le)]]
    - List[Optional[Annotated[float, Field(...)]]]
    - List[str] / List[int] (非约束类型)
    """
    inner = _list_inner_type_name(annotation)
    if inner is None:
        return False
    return inner in ("RatioField", "PercentageField", "PpField")


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
                # Sprint 18 #141 白名单: 已知合规 List[Annotated[float, Field(ge, le)]] 字段
                # (linter 暂不识别 list element-wise Field 元数据, 留 Sprint 18.5 linter 增强)
                if field_name in _LIST_RATIO_FIELDS:
                    pass
                # Sprint 18 #141 白名单: yoy_*_ratio 实际 PpField (pp 差) — 命名 _ratio 是历史遗留
                elif field_name in _YOY_PPT_FIELDS:
                    if not _annotation_has_constrained_float(annotation, *PPT_GE_LE):
                        issues.append(LintIssue(
                            str(py_path), field_line, field_name, "R1",
                            f"{field_name} 是 yoy_*_ratio 白名单字段, 实际是 PpField (-100~+100 pp 差), 需用 PpField 或 Annotated[float, Field(ge=-100, le=100)]",
                            "error",
                        ))
                elif not _annotation_has_constrained_float(annotation, *RATIO_GE_LE):
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

            # R5: List[RatioField/PercentageField/PpField] (没 Annotated) — Sprint 19 治根
            # Pydantic v2 不会触发 element-wise Field 约束, 必须 List[Annotated[float, Field(ge, le)]]
            if _is_list_with_constrained_type_without_annotated(annotation):
                issues.append(LintIssue(
                    str(py_path), field_line, field_name, "R5",
                    f"{field_name} 是 List[RatioField/PercentageField/PpField] 但没用 Annotated 元素. 改 List[Annotated[float, Field(ge, le)]] 才会触发 Pydantic element-wise 约束",
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
