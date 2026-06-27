#!/usr/bin/env python3
"""Sprint 54 ground-truth-lint: 阻止 backend/services 新增 f-string 内嵌用户输入到 SQL 字符串.

规则 (CLAUDE.md L4.5):
- backend/services/** 任何 .py 文件禁止给 SQL 变量赋值时 f-string 内嵌用户输入占位符
  ({channel} / {category_id} / {level} / {granularity} / {user_id} 等)
- 替代: 用 FilterBuilder.build() + DuckDB `?` DB-API 参数化

退出口 (return 0):
- 全部 0 matches → OK
- 仅在白名单文件出现 (如新 sprint 留尾 TODO)

错误 (return 1):
- 任意 backend/services/**/*.py 给 SQL 变量赋值时含 f-string 内嵌用户输入

只检查 SQL 变量赋值 (sql / query / count_sql / total_query / where_sql / filter_sql / cte_sql),
不检查 error message / parts.append / log f-string (那些是字面量拼接, 不是 SQL 注入风险)

用法:
  python3 backend/scripts/check_filter_builder_usage.py [--files PATH...]
  退出码: 0 (clean) | 1 (violation)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 业务字段 placeholder 模式 — f-string 内嵌到 SQL 即违规
FORBIDDEN_FSTRING_PLACEHOLDERS = [
    "channel",
    "channels",
    "exclude_channels",
    "category_id",
    "level",
    "granularity",
    "user_id",
    "segment_id",
    "min_support",
    "min_confidence",
]

# 排除文件 (HANDOFF / test fixture / 已知的 .py 历史文件)
# 注意: 排除条件用 "路径含 tests/ 或文件名以 test_ 结尾" 来识别 test fixture
# 不要匹配名为 test_service.py 的临时 fixture (回归测试用)
EXCLUDE_PATTERNS = [
    "**/HANDOFF*.md",
    "**/CHANGELOG*.md",
]

# SQL 变量名 (赋值给这些名字的 f-string 才检查)
SQL_VAR_NAMES = (
    r"(?:sql|query|count_sql|total_query|main_sql|where_sql|filter_sql|cte_sql|"
    r"sum_query|stats_sql|distinct_sql|raw_sql|final_sql|union_sql|"
    r"period_query|baseline_sql|prev_query|curr_query)"
)
_PLACEHOLDER_ALT = "|".join(FORBIDDEN_FSTRING_PLACEHOLDERS)
_PLACEHOLDER_GROUP = r"(" + _PLACEHOLDER_ALT + r")"
_SQL_VAR_GROUP = r"(" + SQL_VAR_NAMES + r")"

# 三引号 multiline: var = f"""...""" 或 f'''...'''
TRIPLE_DOUBLE = re.compile(
    _SQL_VAR_GROUP + r'\s*=\s*f"""[\s\S]*?\{' + _PLACEHOLDER_GROUP + r"\}[\s\S]*?\"\"\"",
    re.MULTILINE,
)
SINGLE_TRIPLE_OPEN = "f" + "'''"
SINGLE_TRIPLE_CLOSE = "'''"
TRIPLE_SINGLE = re.compile(
    _SQL_VAR_GROUP + r"\s*=\s*" + SINGLE_TRIPLE_OPEN + r"[\s\S]*?\{" + _PLACEHOLDER_GROUP + r"\}[\s\S]*?" + SINGLE_TRIPLE_CLOSE,
    re.MULTILINE,
)
# 单引号 single line
SINGLE_LINE_DOUBLE = re.compile(
    _SQL_VAR_GROUP + r'\s*=\s*f"[^"\n]*\{' + _PLACEHOLDER_GROUP + r'\}[^"\n]*"',
)
SINGLE_LINE_SINGLE = re.compile(
    _SQL_VAR_GROUP + r"\s*=\s*f'[^'\n]*\{" + _PLACEHOLDER_GROUP + r"\}[^'\n]*'",
)

ALL_PATTERNS = [TRIPLE_DOUBLE, TRIPLE_SINGLE, SINGLE_LINE_DOUBLE, SINGLE_LINE_SINGLE]


def check_file(path: Path, exclude_tests: bool = True) -> list[tuple[int, str, str]]:
    """返回 (行号, 变量名, 行内容) 列表. 空列表 = 干净.

    Args:
        path: 要检查的文件
        exclude_tests: True = 跳过 tests/ 目录和 test_*.py (默认扫 services 用)
                       False = 不跳过 (regression test 用, 故意制造违规验证 lint 抓得到)
    """
    path_str = str(path)
    if exclude_tests:
        if "/tests/" in path_str or "/test/" in path_str:
            return []
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            return []
    if any(path.match(pat) for pat in EXCLUDE_PATTERNS):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    violations = []
    for pattern in ALL_PATTERNS:
        for match in pattern.finditer(text):
            var_name = match.group(2)  # placeholder
            line_no = text[: match.start()].count("\n") + 1
            line_content = text.splitlines()[line_no - 1].strip()
            violations.append((line_no, var_name, line_content))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--files",
        nargs="*",
        help="只检查指定文件 (默认: backend/services/**/*.py)",
    )
    args = parser.parse_args()

    if args.files:
        # 用户显式指定文件 → 不跳过 test fixture (regression test 用)
        files = [Path(f) for f in args.files]
        exclude_tests = False
    else:
        # 默认扫 backend/services/ → 跳过 tests/ 目录和 test_*.py
        services_dir = Path(__file__).resolve().parent.parent / "services"
        files = list(services_dir.rglob("*.py"))
        exclude_tests = True

    total_violations = 0
    for f in sorted(files):
        violations = check_file(f, exclude_tests=exclude_tests)
        for line_no, var_name, line_content in violations:
            print(f"❌ {f}:{line_no}  f-string {{ {var_name} }}  {line_content[:80]}")
            total_violations += 1

    if total_violations == 0:
        print(f"✅ FilterBuilder usage check passed: {len(files)} files scanned, 0 violations")
        return 0
    print(f"\n❌ {total_violations} violations found in {len(files)} files")
    print("   Fix: 用 FilterBuilder.build() + DuckDB `?` 占位符, 禁止 f-string 内嵌用户输入到 SQL 字符串")
    print("   详见 CLAUDE.md L4.5")
    return 1


if __name__ == "__main__":
    sys.exit(main())
