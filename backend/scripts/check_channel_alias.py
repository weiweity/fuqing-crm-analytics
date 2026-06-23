"""Sprint 97 ground-truth-lint: 参数化 channel 条件必须含表别名.

防 Sprint 60.1 Binder 500 回归：orders 跟含 channel 字段的表 JOIN 时，
DuckDB 会拒绝无别名的 ``channel IN/NOT IN/=`` 条件。

本检查只分析 Python 字符串字面量中的参数化 SQL 条件，跳过 docstring、
注释、普通 Python 赋值和 ``str.replace`` 的匹配模板，避免文本 grep 误报。
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path


PATTERN_NO_ALIAS = re.compile(
    r"(?<![\w.])channel\s+(?:(?:NOT\s+IN|IN)\s*\(|=\s*\?)",
    re.IGNORECASE,
)


def _ignored_string_nodes(tree: ast.AST) -> set[int]:
    """返回 docstring 和 replace 参数中字符串节点的 id."""
    ignored: set[int] = set()
    docstring_owners = (
        ast.Module,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )

    for node in ast.walk(tree):
        if isinstance(node, docstring_owners) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                ignored.add(id(first.value))

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "replace"
        ):
            for arg in node.args:
                ignored.update(id(child) for child in ast.walk(arg))

    return ignored


def _candidate_strings(tree: ast.AST, source: str) -> list[tuple[int, str]]:
    """提取需检查的普通字符串和 f-string 源码片段."""
    ignored = _ignored_string_nodes(tree)
    parents = {
        id(child): parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    candidates: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if id(node) in ignored:
            continue
        if isinstance(node, ast.JoinedStr):
            segment = ast.get_source_segment(source, node) or ""
            candidates.append((node.lineno, segment))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if isinstance(parents.get(id(node)), ast.JoinedStr):
                continue
            candidates.append((node.lineno, node.value))

    return candidates


def _candidate_strings_from_tokens(source: str) -> list[tuple[int, str]]:
    """兼容 Python 3.12+ f-string：旧解释器 AST 失败时退回 tokenize."""
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    candidates: list[tuple[int, str]] = []
    ignored_types = {
        tokenize.ENCODING,
        tokenize.NL,
        tokenize.COMMENT,
        tokenize.INDENT,
        tokenize.DEDENT,
    }

    for index, token in enumerate(tokens):
        if token.type != tokenize.STRING:
            continue

        previous = next(
            (item for item in reversed(tokens[:index]) if item.type not in ignored_types),
            None,
        )
        following = next(
            (item for item in tokens[index + 1 :] if item.type not in ignored_types),
            None,
        )
        is_standalone_string = (
            (previous is None or previous.type in {tokenize.NEWLINE, tokenize.INDENT})
            and following is not None
            and following.type in {tokenize.NEWLINE, tokenize.ENDMARKER}
        )
        if not is_standalone_string:
            candidates.append((token.start[0], token.string))

    return candidates


def check_file(path: Path) -> list[str]:
    """检查单个 Python 文件，返回无别名 channel SQL 列表."""
    if path.name.startswith("test_") or "tests" in path.parts:
        return []

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
        candidates = _candidate_strings(tree, source)
    except SyntaxError:
        try:
            candidates = _candidate_strings_from_tokens(source)
        except (IndentationError, tokenize.TokenError) as exc:
            return [f"{path}:1: Python tokenization error: {exc}"]

    errors: list[str] = []
    source_lines = source.splitlines()
    for lineno, value in candidates:
        if not PATTERN_NO_ALIAS.search(value):
            continue
        line = source_lines[lineno - 1].strip() if lineno <= len(source_lines) else value.strip()
        errors.append(f"{path}:{lineno}: {line}")
    return errors


def _iter_python_files(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(Path("backend/services").rglob("*.py"))

    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        files.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return files


def main(argv: list[str] | None = None) -> int:
    paths = sys.argv[1:] if argv is None else argv
    files = _iter_python_files(paths)
    if not files:
        print("ERROR: no Python files found", file=sys.stderr)
        return 1

    all_errors = [error for path in files for error in check_file(path)]
    if all_errors:
        print(f"❌ Found {len(all_errors)} channel alias violations:")
        for error in all_errors:
            print(f"  {error}")
        return 1

    print("✅ channel alias lint passed: all parameterized channel conditions contain a table prefix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
