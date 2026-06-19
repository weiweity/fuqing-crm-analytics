#!/usr/bin/env python3
"""
spec-lint-l2: L2 AST parser upgrade for e2e spec lint.

Sprint 50+ #S43-L2: parse .spec.ts with tree-sitter-typescript so
multiline calls are caught while comments and string literals are ignored.
L1 (spec-lint.sh) is kept as the fallback wrapper path.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Set

try:
    from tree_sitter import Language, Parser
    import tree_sitter_typescript
except ImportError as exc:  # pragma: no cover - wrapper normally handles this.
    print(f"⚠️  spec-lint-l2: tree-sitter 不可用 ({exc})", file=sys.stderr)
    sys.exit(2)


REQUEST_METHODS = {b"get", b"post", b"put", b"delete"}
SCOPE_NODE_TYPES = {"program", "statement_block"}


@dataclass(frozen=True)
class Finding:
    kind: str
    path: Path
    line: int
    message: str


def build_parser() -> Parser:
    parser = Parser()
    language_capsule = tree_sitter_typescript.language_typescript()

    try:
        language = Language(language_capsule)
    except TypeError:
        language = language_capsule

    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language

    return parser


PARSER = build_parser()


def node_line(node) -> int:
    point = node.start_point
    return getattr(point, "row", point[0]) + 1


def node_text(node) -> bytes:
    if node is None:
        return b""
    return node.text or b""


def named_children(node) -> Iterator:
    for idx in range(node.named_child_count):
        yield node.named_child(idx)


def walk(node) -> Iterator:
    yield node
    for child in node.children:
        yield from walk(child)


def field(node, name: str):
    return node.child_by_field_name(name)


def property_name(node) -> Optional[bytes]:
    if node is None:
        return None
    if node.type in {"identifier", "property_identifier", "private_property_identifier"}:
        return node_text(node)
    if node.type == "string":
        return node_text(node).strip(b"'\"")
    if node.type == "computed_property_name":
        for child in named_children(node):
            value = property_name(child)
            if value:
                return value
    return None


def is_member_property(node, expected: bytes) -> bool:
    if node is None or node.type != "member_expression":
        return False
    return property_name(field(node, "property")) == expected


def is_expect_call(node) -> bool:
    if node is None or node.type != "call_expression":
        return False
    callee = field(node, "function")
    return callee is not None and callee.type == "identifier" and node_text(callee) == b"expect"


def single_argument(node):
    if node is None or node.type != "arguments" or node.named_child_count != 1:
        return None
    return node.named_child(0)


def is_numeric_literal(node) -> bool:
    return node is not None and node.type == "number"


def expect_length_argument(expect_call):
    args = field(expect_call, "arguments")
    arg = single_argument(args)
    if is_member_property(arg, b"length"):
        return arg
    return None


def find_rule1(root, path: Path) -> Iterator[Finding]:
    for node in walk(root):
        if node.type != "call_expression":
            continue

        callee = field(node, "function")
        if not is_member_property(callee, b"toBe"):
            continue

        expect_call = field(callee, "object")
        if not is_expect_call(expect_call):
            continue

        length_arg = expect_length_argument(expect_call)
        to_be_arg = single_argument(field(node, "arguments"))
        if length_arg is None or not is_numeric_literal(to_be_arg):
            continue

        yield Finding(
            kind="violation",
            path=path,
            line=node_line(node),
            message=(
                "Rule 1 - hardcode 业务数据长度 "
                f"({node_text(length_arg).decode('utf-8', 'replace')}.toBe("
                f"{node_text(to_be_arg).decode('utf-8', 'replace')}))"
            ),
        )


def find_rule2(root, path: Path) -> Iterator[Finding]:
    for node in walk(root):
        if node.type != "call_expression":
            continue
        callee = field(node, "function")
        if is_member_property(callee, b"waitForTimeout"):
            yield Finding(
                kind="violation",
                path=path,
                line=node_line(node),
                message="Rule 2 - waitForTimeout 死等",
            )


def nearest_scope(node):
    current = node
    while current is not None:
        if current.type in SCOPE_NODE_TYPES:
            return current
        current = current.parent
    return None


def same_node(left, right) -> bool:
    return (
        left is not None
        and right is not None
        and left.type == right.type
        and left.start_byte == right.start_byte
        and left.end_byte == right.end_byte
    )


def scope_chain(node) -> list:
    scopes = []
    current = node
    while current is not None:
        if current.type in SCOPE_NODE_TYPES:
            scopes.append(current)
        current = current.parent
    return list(reversed(scopes))


def collect_variable_values(scope) -> Dict[bytes, object]:
    values: Dict[bytes, object] = {}
    for node in walk(scope):
        if node.type != "variable_declarator":
            continue
        if not same_node(nearest_scope(node), scope):
            continue
        name = field(node, "name")
        value = field(node, "value")
        if name is not None and value is not None and name.type == "identifier":
            values[node_text(name)] = value
    return values


def collect_visible_variable_values(node) -> Dict[bytes, object]:
    values: Dict[bytes, object] = {}
    for scope in scope_chain(node):
        values.update(collect_variable_values(scope))
    return values


def node_has_authorization_header(node, variables: Dict[bytes, object], seen: Optional[Set[bytes]] = None) -> bool:
    if node is None:
        return False
    if seen is None:
        seen = set()

    if node.type in {"identifier", "shorthand_property_identifier"}:
        name = node_text(node)
        if name in seen:
            return False
        target = variables.get(name)
        if target is not None:
            return node_has_authorization_header(target, variables, seen | {name})

    if node.type == "pair" and property_name(field(node, "key")) == b"Authorization":
        return True

    return any(node_has_authorization_header(child, variables, seen) for child in node.children)


def is_page_request_call(node) -> bool:
    if node.type != "call_expression":
        return False

    callee = field(node, "function")
    if callee is None or callee.type != "member_expression":
        return False

    method = property_name(field(callee, "property"))
    target = field(callee, "object")
    return method in REQUEST_METHODS and is_member_property(target, b"request") and node_text(field(target, "object")) == b"page"


def find_rule3(root, path: Path) -> Iterator[Finding]:
    for node in walk(root):
        if not is_page_request_call(node):
            continue
        variables = collect_visible_variable_values(node)
        args = field(node, "arguments")
        if not node_has_authorization_header(args, variables):
            yield Finding(
                kind="warn",
                path=path,
                line=node_line(node),
                message="Rule 3 - page.request 缺 Authorization header",
            )


def iter_specs(paths: Iterable[Path]) -> Iterator[Path]:
    seen: Set[Path] = set()
    for path in paths:
        if path.is_file() and path.name.endswith(".spec.ts"):
            specs = [path]
        elif path.is_dir():
            specs = path.rglob("*.spec.ts")
        else:
            continue

        for spec in specs:
            spec_text = str(spec)
            if "/node_modules/" in spec_text or "/screenshots/" in spec_text:
                continue
            resolved = spec.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield spec


def lint_spec(spec_path: Path) -> tuple[int, int]:
    source = spec_path.read_bytes()
    tree = PARSER.parse(source)
    root = tree.root_node

    violations = 0
    warns = 0
    for finding in (
        *find_rule1(root, spec_path),
        *find_rule2(root, spec_path),
        *find_rule3(root, spec_path),
    ):
        icon = "❌" if finding.kind == "violation" else "⚠️ "
        print(f"{icon} {finding.path}:{finding.line}: {finding.message}")
        if finding.kind == "violation":
            violations += 1
        else:
            warns += 1

    return violations, warns


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="L2 AST spec lint for Playwright .spec.ts files")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--specs-dir", type=Path, help="Directory containing .spec.ts files")
    parser.add_argument("--advisory", action="store_true", help="Report violations but exit 0")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    paths = args.paths
    if args.specs_dir is not None:
        paths = [args.specs_dir, *paths]
    if not paths:
        paths = [Path("frontend-vue3/e2e")]

    violations = 0
    warns = 0
    specs_checked = 0
    for spec_path in iter_specs(paths):
        specs_checked += 1
        spec_violations, spec_warns = lint_spec(spec_path)
        violations += spec_violations
        warns += spec_warns

    if violations == 0:
        print(f"✅ spec-lint-l2: 0 violation, {warns} warn ({specs_checked} spec checked)")
        return 0

    if args.advisory:
        print(
            f"⚠️  spec-lint-l2: {violations} violations, {warns} warn "
            f"({specs_checked} spec checked) [advisory mode, exit 0]"
        )
        return 0

    print(f"❌ spec-lint-l2: {violations} violations, {warns} warn ({specs_checked} spec checked)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
