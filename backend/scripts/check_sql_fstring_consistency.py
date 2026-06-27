#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint 34.1 L1 防御: SQL f-string 一致性 lint 钩子.

Root cause (a9b1d91 对称教训): churn.py:418 count_sql 漏写 f 前缀,
DuckDB 解析字面量 {valid_sql} 抛 ParserException, 5+ 天未发现.

L1 防御机制:
- 扫 backend/services/**/*.py + backend/scripts/**/*.py + scripts/etl/**/*.py (Sprint 36-4 对称补盲)
- 规则: 三引号 SQL 字符串 body 含 {identifier} 但缺 f 前缀 = violation
- 跨多行扫描 (opening line + body lines + closing line)

L2 (可选, Sprint 34.2): AST parser 升级版
L3 (可选, Sprint 35+): 全面 FilterBuilder 化
L4 (Sprint 34.1): review checklist 加一条, 写 CLAUDE.md

Usage:
    python -m backend.scripts.check_sql_fstring_consistency          # 扫全目录
    python -m backend.scripts.check_sql_fstring_consistency FILE...   # 扫指定文件
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


# Pattern: variable assignment opening a triple-quoted string on the same line
SQL_OPEN_PATTERN = re.compile(
    r"""^(?P<indent>\s*)
        (?P<varname>[a-zA-Z_][a-zA-Z0-9_]*)
        \s*=\s*
        (?P<prefix>[rRfF]?[fF]?[rRfR]?)
        (?P<quote>\"\"\"|''')
        (?P<rest>.*)$""",
    re.VERBOSE,
)


# Pattern: f-string interpolation placeholder in body
INTERPOLATION_PATTERN = re.compile(r"\{[a-zA-Z_]\w*\}")


def _is_docstring_start(stripped: str) -> bool:
    """Heuristic: line starts module/class/function docstring (single or open)."""
    return (
        stripped.startswith('"""')
        or stripped.startswith("'''")
    )


def _is_sql_like(text: str) -> bool:
    """Heuristic: text starts with SQL keyword."""
    t = text.strip().lower()
    return any(
        t.startswith(kw)
        for kw in (
            "select",
            "insert",
            "update",
            "delete",
            "with ",
            "merge",
            "create",
        )
    )


def _in_module_docstring(lines: list, idx: int) -> bool:
    """
    Track multi-line docstring state across file lines.

    Returns True if lines[idx] is inside a triple-quoted module/class/function
    docstring (not a SQL triple-quoted string).
    """
    in_ds = False
    ds_quote = ""
    # Walk from start to current line
    for i in range(idx + 1):
        stripped = lines[i].strip()
        if not in_ds:
            if _is_docstring_start(stripped):
                quote = stripped[:3]
                rest = stripped[3:]
                # Single-line docstring: contains closing quote on same line
                if quote in rest:
                    continue
                in_ds = True
                ds_quote = quote
        else:
            if ds_quote in stripped:
                in_ds = False
                ds_quote = ""
    return in_ds


def check_file(filepath: Path) -> List[Tuple[int, str, str, str]]:
    """Check one file. Returns list of (line_num, varname, reason, full_opening_line)."""
    violations: List[Tuple[int, str, str, str]] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"[skip] {filepath}: {e}", file=sys.stderr)
        return violations

    lines = content.splitlines()

    for idx, line in enumerate(lines):
        # Skip if inside a docstring
        if _in_module_docstring(lines, idx):
            continue

        match = SQL_OPEN_PATTERN.match(line)
        if not match:
            continue

        varname = match.group("varname")
        prefix = match.group("prefix").lower()
        rest = match.group("rest")
        quote = match.group("quote")
        quote_char = quote[0]  # " or '

        # Filter: only SQL/query variable names
        if "sql" not in varname.lower() and "query" not in varname.lower():
            continue

        # Filter: rest should look like SQL start (or body has SQL keyword)
        # If rest is non-empty, check it; else we'll find SQL in body lines
        sql_in_opening = bool(rest.strip()) and _is_sql_like(rest)

        # Skip if not opening a multi-line triple-quoted SQL string
        # (we only check multi-line; single-line triples like x = """SELECT 1""" are too rare)
        if not rest.endswith(quote_char * 2) and len(rest.strip()) > 0:
            # Opening line has content after triple-quote (single-line case)
            # Skip: single-line SQL triple-quotes are rare and would have body on same line
            pass

        # Walk forward to collect body lines until closing triple-quote
        body_lines = [rest]
        for j in range(idx + 1, len(lines)):
            body_lines.append(lines[j])
            if quote_char * 3 in lines[j]:
                break

        body_text = "\n".join(body_lines)

        # If opening line doesn't have SQL keyword, check body
        sql_keyword_found = sql_in_opening or _is_sql_like(body_text)
        if not sql_keyword_found:
            continue

        # Filter: body must have f-string interpolation placeholder
        if not INTERPOLATION_PATTERN.search(body_text):
            continue

        # Filter: opening line must NOT have f prefix
        has_f = "f" in prefix
        if has_f:
            continue  # valid f-string

        # Violation: missing f-prefix on interpolated SQL string
        reason = f"missing f-prefix (have {prefix!r}, body has f-string interpolation but no f prefix at L{idx+1})"
        violations.append((idx + 1, varname, reason, line.rstrip()))

    return violations


def main() -> int:
    """Main entry. Returns exit code."""
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        # Sprint 36-4: 对称补盲扩范围 — services + scripts (backend + etl)
        # 跟 Sprint 33 .vue / Sprint 34.1 services SQL lint 完整闭环 AI safety net
        scan_dirs = [
            repo_root / "backend" / "services",
            repo_root / "backend" / "scripts",
            repo_root / "scripts" / "etl",
        ]
        paths = []
        for d in scan_dirs:
            if d.exists():
                paths.extend(sorted(d.rglob("*.py")))
        if not paths:
            print("[error] no scan dirs found", file=sys.stderr)
            return 2

    total_violations = 0
    files_with_violations = 0

    for path in paths:
        violations = check_file(path)
        if violations:
            files_with_violations += 1
            for line_num, varname, reason, full_line in violations:
                print(f"{path}:{line_num}: {varname}: {reason}")
                print(f"    {full_line}")
                total_violations += 1

    if total_violations > 0:
        print(
            f"\n[FAIL] {total_violations} violation(s) in {files_with_violations} file(s)",
            file=sys.stderr,
        )
        print(
            "[hint] Sprint 34.1 fix: add f-prefix to triple-quoted SQL string. "
            "See churn.py:418 bug for reference (was missing f-prefix).",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] 0 violations in {len(paths)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
