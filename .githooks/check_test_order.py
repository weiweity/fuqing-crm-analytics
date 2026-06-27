#!/usr/bin/env python3
"""
B5 P2: pre-commit test 顺序无关性 lint (v0.4.7.8)

扫 backend/tests/ + tests/ 的 .py, 检测 N-index 断言 (`assert X[N].method()`),
WARN 但不 FAIL. 根因预防 v0.4.7.3.3 跨平台 flaky test (macOS extfs vs Linux ext4
glob 返回顺序不同, 索引断言跨平台 flaky).

修法推荐: 改顺序无关断言, 例:
  assert files[0].exists()                          # BAD: 顺序依赖
  → assert sum(1 for f in files if f.exists()) == 1  # GOOD: 顺序无关

设计: WARN 不 FAIL. 原因:
  - 故意 N-index (固定 list, mock data) 多, 强 fail 误伤
  - lint 工具的常规做法 (ruff 类似规则都 warn)
  - user 看到 warning 自己评估改不改
"""
import ast
import sys
import pathlib


def is_test_file(py: pathlib.Path) -> bool:
    """test_*.py 或 *_test.py 或 tests/ 目录下."""
    return 'tests/' in str(py) or py.name.startswith('test_') or py.name.endswith('_test.py')


def find_index_assertions(tree: ast.Module) -> list[tuple[int, str, int]]:
    """Return [(lineno, var_name, index)] for each `assert X[N].method()` pattern.
    N is int literal. Detects: assert files[0].exists(), assert arr[2].is_file() 等.
    """
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        # Walk the assert.test, look for Call with Attribute func that has Subscript value
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if isinstance(sub.func.value, ast.Subscript):
                    subscript = sub.func.value
                    if isinstance(subscript.slice, ast.Constant) and isinstance(subscript.slice.value, int):
                        try:
                            var_name = ast.unparse(subscript.value)
                        except Exception:
                            var_name = '?'
                        findings.append((sub.lineno, var_name, subscript.slice.value))
    return findings


def main() -> int:
    test_dirs = ['backend/tests', 'tests']
    findings_total: list[tuple[str, int, str, int]] = []

    for root in test_dirs:
        root_p = pathlib.Path(root)
        if not root_p.exists():
            continue
        for py in root_p.rglob('*.py'):
            if '__pycache__' in py.parts or any(p.startswith('.') for p in py.parts):
                continue
            if not is_test_file(py):
                continue
            try:
                source = py.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(source, filename=str(py))
            except SyntaxError:
                continue
            for lineno, var, idx in find_index_assertions(tree):
                findings_total.append((str(py), lineno, var, idx))

    if findings_total:
        print("⚠️  B5: 检测到潜在顺序依赖的 N-index 断言 (建议改成顺序无关):")
        print()
        for py, lineno, var, idx in findings_total:
            print(f"  {py}:{lineno}  assert {var}[{idx}].*  (顺序依赖, 跨平台可能 flaky)")
        print()
        print("修法推荐: 改成顺序无关断言, 例:")
        print("  assert files[0].exists()                            # BAD: 顺序依赖")
        print("  → assert sum(1 for f in files if f.exists()) == 1  # GOOD: 顺序无关")
        print()
        print(f"共 {len(findings_total)} 处. WARN 不阻断 commit, 但建议修.")
        return 0  # WARN 不 fail

    print("✅ B5: 无 N-index 顺序依赖断言")
    return 0


if __name__ == '__main__':
    sys.exit(main())
