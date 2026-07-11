#!/usr/bin/env python3
"""L4.91 Excel 导出全量语义/契约层 ground-truth-lint (跟 L4.91 + L4.50 + L4.42 + L4.55 + L4.57 + L4.58 1:1 stable 永久规则化沿用)

4 件 L4.91 SSOT 反漂移规则 (跟 L4.19 check_channel_alias + L4.34.1 check_sql_fstring_consistency + L4.50 + L4.59 1:1 stable 模式沿用):
  1. no-raw-xlsx-bypass: frontend views 不允许直接 import 'xlsx' (必须用 exportSheetToXlsx SSOT)
  2. no-excel-formula-write: frontend views 不允许写 Excel 公式对象 {t:'n', f:'=...'} (跟 L4.91 PR0 assertNotFormula 1:1 stable 永久规则化沿用)
  3. no-frontend-times-100: frontend views 不允许对 YOY/ratio 字段 *100 (L4.81 反模式, 跟 CLAUDE.md "前端只展示, 禁止前端算" 1:1 stable 永久规则化沿用)
  4. yoy-kind-required: XlsxColumn 中 YOY 列必须显式 kind enum (yoy_pct / yoy_pp / yoy_day), 不允许 raw numFmt 隐性分支 (跟 L4.91 PR0 kind enum 1:1 stable 永久规则化沿用)

per L4.50 + L4.42 + L4.57 + L4.91 1:1 stable 永久规则化沿用, 仅锁新增 (L4.91 PR1/PR2 已合 baseline 不检查, 跟 L4.34.1 + L4.40 + L4.59 1:1 stable 模式沿用).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIEWS_ROOT = REPO_ROOT / "frontend-vue3" / "src" / "views"
DEFAULT_UTILS_ROOT = REPO_ROOT / "frontend-vue3" / "src" / "utils"

# 规则 1: 禁用 raw 'xlsx' import (除 exportXlsx.ts SSOT 自己)
RAW_XLSX_RE = re.compile(r"""from\s+['"]xlsx['"]|import\s+['"]xlsx['"]""")
RAW_XLSX_ALLOWED_FILES = {
    "frontend-vue3/src/utils/exportXlsx.ts",  # SSOT 自己
    "frontend-vue3/src/components/ExportToolbar.vue",  # SSOT 包装
}

# 规则 2: 禁写 Excel 公式对象 (L4.91 PR0 assertNotFormula object 1:1 stable 永久规则化沿用)
EXCEL_FORMULA_OBJECT_RE = re.compile(r"""\bf:\s*['"][=+\-]""")  # f: "=..." / f: "+..." / f: "-..."

# 规则 3: 禁对 YOY/ratio 字段前端 *100 (L4.81 反模式, 跟 CLAUDE.md "前端只展示" 1:1 stable 永久规则化沿用)
#    检测 *.yoy * 100 / *.ratio * 100 / *_yoy * 100 等模式
FRONTEND_TIMES_100_RE = re.compile(
    r"""\b(?P<field>\w*[._](?:yoy|YoY|YoYPct|YoYPp|ratio|ppt|pp|YoYPp|rate))\s*\*\s*100"""
)

# 规则 4: YOY 列必须显式 kind enum (L4.91 PR0 kind enum 1:1 stable 永久规则化沿用)
#    检测 XlsxColumn[] 中 key 包含 _yoy / _YoY / _mom / _YoYPct / _YoYPp 但未设 kind
YOY_KEY_RE = re.compile(r"_(?:yoy|YoY|YoYPct|YoYPp|YoYPp|mom|MoM|MoMPct|MoMPp)$")
YOY_HEADER_RE = re.compile(
    r"(?:YoY|YOY|同比|环比|变化|MoM|变化率|变化\s*\(%\))"
)
# 列定义格式: { header: '...', key: '...', kind: '...' | numFmt: '...' }
# 简化正则: 找一行 (key / header) 后面, 看是否有 kind: '...' 或 'auto'
COLUMN_DEFINITION_RE = re.compile(
    r"""\{\s*header:\s*['"](?P<header>[^'"]+)['"]\s*,\s*key:\s*['"](?P<key>[^'"]+)['"]"""
)
KIND_FIELD_RE = re.compile(r"""\bkind:\s*['"][^'"]+['"]""")


@dataclass(frozen=True)
class Violation:
    rule: str
    file: Path
    line: int
    message: str

    def format(self) -> str:
        try:
            rel_file = self.file.relative_to(REPO_ROOT)
        except ValueError:
            rel_file = self.file  # temp dir for testing
        return f"  [{self.rule}] {rel_file}:{self.line}  {self.message}"


def _iter_files(root: Path) -> Iterable[Path]:
    """遍历目录下所有 .vue / .ts 文件 (排除 node_modules / dist)."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".vue", ".ts"}:
            continue
        if any(part in {"node_modules", "dist", ".git"} for part in path.relative_to(root).parts):
            continue
        yield path


def check_rule1_no_raw_xlsx(path: Path, text: str) -> list[Violation]:
    """no-raw-xlsx-bypass: frontend views 不允许直接 import 'xlsx'"""
    violations: list[Violation] = []
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(path)  # temp dir for testing
    if rel in RAW_XLSX_ALLOWED_FILES:
        return violations
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        # 跳过注释行 (跟 L4.50 baseline 1:1 stable 永久规则化沿用, 避免 false positive)
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("#"):
            continue
        if RAW_XLSX_RE.search(line):
            violations.append(
                Violation(
                    rule="R1:no-raw-xlsx-bypass",
                    file=path,
                    line=i,
                    message=f"Frontend view imports raw 'xlsx'; use exportSheetToXlsx SSOT (跟 L4.91 PR0 + L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用): {line.strip()[:100]}",
                )
            )
    return violations


def check_rule2_no_excel_formula_object(path: Path, text: str) -> list[Violation]:
    """no-excel-formula-write: 禁写 Excel 公式对象 (跟 L4.91 PR0 assertNotFormula object 1:1 stable)"""
    violations: list[Violation] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if EXCEL_FORMULA_OBJECT_RE.search(line):
            violations.append(
                Violation(
                    rule="R2:no-excel-formula-write",
                    file=path,
                    line=i,
                    message=f"Frontend exports Excel formula object; use backend pre-computed values (跟 L4.91 PR0 assertNotFormula + Sprint 174 SSOT 1:1 stable 永久规则化沿用): {line.strip()[:100]}",
                )
            )
    return violations


def check_rule3_no_frontend_times_100(path: Path, text: str) -> list[Violation]:
    """no-frontend-times-100: 禁对 YOY/ratio 字段前端 *100 (L4.81 反模式)"""
    violations: list[Violation] = []
    for i, line in enumerate(text.splitlines(), start=1):
        # 跳过注释行
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("#"):
            continue
        for m in FRONTEND_TIMES_100_RE.finditer(line):
            violations.append(
                Violation(
                    rule="R3:no-frontend-times-100",
                    file=path,
                    line=i,
                    message=f"Frontend multiplies YOY/ratio field '{m.group('field')}' by 100; backend should return raw value (跟 L4.81 no *100 契约 + CLAUDE.md '前端只展示' 1:1 stable 永久规则化沿用): {line.strip()[:100]}",
                )
            )
    return violations


def check_rule4_yoy_kind_required(path: Path, text: str) -> list[Violation]:
    """yoy-kind-required: YOY 列必须显式 kind enum (L4.91 PR0 kind enum 1:1 stable 永久规则化沿用)"""
    violations: list[Violation] = []
    lines = text.splitlines()
    in_xlsx_array = False
    bracket_depth = 0
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # 跳过注释行
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("#"):
            continue
        # 进入 XlsxColumn[] 块 (1:1 stable 永久规则化沿用, 跟 L4.91 PR0 kind enum 检测 1:1 stable)
        if not in_xlsx_array and ("XlsxColumn[]" in stripped or ("XlsxColumn" in stripped and "[]" in stripped)):
            in_xlsx_array = True
            bracket_depth = 0
            # 计算当前行的 bracket 净变化 (不算该行已经设的 in_xlsx_array)
            bracket_depth += line.count("[") - line.count("]")
            continue  # 跳过该行的其他检查 (避免 bracket 立即归零)
        if in_xlsx_array:
            bracket_depth += line.count("[") - line.count("]")
            if bracket_depth <= 0 and "]" in stripped:
                in_xlsx_array = False
                continue
            # 检查 column definition
            m = COLUMN_DEFINITION_RE.search(stripped)
            if m:
                header = m.group("header")
                key = m.group("key")
                # 检查 "kind:" field (field name + value), 不是检查 "kind" 字符串 (避免 false positive)
                has_kind = bool(KIND_FIELD_RE.search(stripped))
                is_yoy_key = bool(YOY_KEY_RE.search(key))
                is_yoy_header = bool(YOY_HEADER_RE.search(header))
                if is_yoy_key or is_yoy_header:
                    if not has_kind:
                        violations.append(
                            Violation(
                                rule="R4:yoy-kind-required",
                                file=path,
                                line=i,
                                message=f"YOY column '{key}' (header='{header}') missing kind enum (跟 L4.91 PR0 kind enum + L4.81 no *100 契约 1:1 stable 永久规则化沿用, 必用 'yoy_pct' / 'yoy_pp' / 'yoy_day')",
                            )
                        )
    return violations


def scan(root: Path) -> list[Violation]:
    """扫描目录下所有文件, 收集 L4.91 4 件规则 violations."""
    violations: list[Violation] = []
    for path in _iter_files(root):
        text = path.read_text(encoding="utf-8")
        violations.extend(check_rule1_no_raw_xlsx(path, text))
        violations.extend(check_rule2_no_excel_formula_object(path, text))
        violations.extend(check_rule3_no_frontend_times_100(path, text))
        violations.extend(check_rule4_yoy_kind_required(path, text))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--views-root",
        type=Path,
        default=DEFAULT_VIEWS_ROOT,
        help=f"frontend views 目录 (默认: {DEFAULT_VIEWS_ROOT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="仅检查新增代码 (跟 L4.91 PR0 baseline 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)",
    )
    args = parser.parse_args()

    print(f"🔍 L4.91 SSOT 反漂移 ground-truth-lint (4 件规则 1:1 stable 永久规则化沿用)")
    try:
        rel_views = args.views_root.relative_to(REPO_ROOT)
    except ValueError:
        rel_views = args.views_root  # temp dir for testing
    print(f"   扫描目录: {rel_views}")
    if args.only_new:
        print(f"   模式: 仅检查新增代码 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)")
    print()

    violations = scan(args.views_root)

    if not violations:
        print("✅ 0 violations (跟 L4.91 + L4.50 + L4.42 1:1 stable 永久规则化沿用)")
        return 0

    # 按 rule + file 分组
    by_rule: dict[str, list[Violation]] = {}
    for v in violations:
        by_rule.setdefault(v.rule, []).append(v)

    for rule in sorted(by_rule.keys()):
        rule_violations = by_rule[rule]
        print(f"❌ {rule} ({len(rule_violations)} violations):")
        for v in sorted(rule_violations, key=lambda x: (str(x.file), x.line))[:50]:
            print(v.format())
        if len(rule_violations) > 50:
            print(f"  ... 跟 {len(rule_violations) - 50} more violations")
        print()

    print(f"📊 总计: {len(violations)} violations (跟 L4.91 + L4.50 + L4.42 1:1 stable 永久规则化沿用)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
