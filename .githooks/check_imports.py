#!/usr/bin/env python3
"""
B2 P0 根因预防: pre-commit import 完整性检查 (v0.4.7.5)

扫 backend/ + scripts/etl/ 所有 .py 的 3rd-party imports, 跟 requirements.txt 对账.
缺任意一个 → exit 1 拦截 commit. 根因预防 v0.4.7.3 → .3.2 链式 CI ImportError.

用法:
  - 自动: 由 .githooks/pre-commit 调
  - 手动: python3 .githooks/check_imports.py

设计: 静态 AST 扫, 不实际 import (避免副作用). stdlib 名单用 sys.stdlib_module_names
(Python 3.10+, 项目 baseline 满足). 已知 import↔pip 名字不一致的进 PIP_ALIASES 表.

局限: 不能扫 dynamic import (importlib.import_module("X") 等). 项目里如出现需手动加 requirements.
"""
import ast
import sys
import sysconfig
import pkgutil
import pathlib
import re

# Python 3.10+ stdlib module names
try:
    STDLIB = {m.lower() for m in sys.stdlib_module_names}
except AttributeError:
    # Fallback for Python < 3.10 (项目实际不用, 兜底)
    stdlib_paths = {
        sysconfig.get_paths().get("stdlib"),
        sysconfig.get_paths().get("platstdlib"),
        sysconfig.get_config_var("DESTSHARED"),
    }
    STDLIB = {
        name.lower()
        for path in stdlib_paths
        if path
        for _finder, name, _ispkg in pkgutil.iter_modules([path])
    }
    STDLIB.update({m.lower() for m in sys.builtin_module_names})
    STDLIB.update({
        '__future__', 'os', 'sys', 're', 'json', 'pathlib', 'typing', 'collections',
        'datetime', 'time', 'logging', 'subprocess', 'threading', 'functools',
        'itertools', 'contextlib', 'ast', 'unittest', 'pytest', 'asyncio',
        'abc', 'enum', 'dataclasses', 'inspect', 'importlib', 'warnings',
        'traceback', 'copy', 'io', 'csv', 'hashlib', 'http', 'urllib', 'uuid',
        'math', 'resource',
    })

# 已知 import 名字 vs pip 名字不同的别名 (项目实际遇到的 + 常见)
PIP_ALIASES = {
    'pil': 'pillow',
    'PIL': 'pillow',
    'cv2': 'opencv-python',
    'yaml': 'pyyaml',
    'sklearn': 'scikit-learn',
    'bs4': 'beautifulsoup4',
    'dateutil': 'python-dateutil',
    'dotenv': 'python-dotenv',
    'pptx': 'python-pptx',
    'attr': 'attrs',
    'skimage': 'scikit-image',
    'crypto': 'pycryptodome',
    'magic': 'python-magic',
    'serial': 'pyserial',
    'grpc': 'grpcio',
}

# 项目本地包 (项目根下的目录, 不是 pip 包). 跳过后 import 不会被算 3rd-party.
# 自动检测: 任何项目根下含 __init__.py 的顶级目录都算本地包.
# Monorepo: 显式列举 implicit namespace package (无 __init__.py 但代码 from X.Y import Z).
#
# 2026-07-21: 另扫 scripts/ad_hoc_queries 等「被测试 sys.path 插入后按顶层 import」的 .py 模块
# (channel_monthly / top_n …)，避免 Nightly 假红.
def _detect_local_packages() -> set[str]:
    local: set[str] = set()
    skip_dirs = {
        'node_modules', '.venv', 'venv', '.git', '.codegraph',
        '.pytest_cache', '.ruff_cache', '.workbuddy', '.gstack',
        'docs', 'logs', 'frontend-vue3',  # 前端, 不被 Python import
        'data', 'outputs', 'logs',
    }
    root = pathlib.Path('.')
    for p in root.iterdir():
        if p.is_dir() and p.name not in skip_dirs and not p.name.startswith('.'):
            if (p / '__init__.py').exists():
                local.add(p.name)
            elif any(p.rglob('*.py')):
                # implicit namespace package: 有 .py 但无 __init__.py
                local.add(p.name)

    # 可被 `import <stem>` 的仓库内脚本模块 (tests 常把 scripts/ 或 ad_hoc_queries 塞进 sys.path)
    for scripts_dir in (
        root / 'scripts',
        root / 'scripts' / 'ad_hoc_queries',
        root / 'scripts' / 'etl',
        root / 'scripts' / 'ops',
        root / 'scripts' / 'ci',
        root / 'mcp_servers',
    ):
        if not scripts_dir.is_dir():
            continue
        for py in scripts_dir.glob('*.py'):
            if py.name.startswith('_') and py.name != '__init__.py':
                # 允许 _utils 等仍算本地 (tests 极少顶层 import)
                local.add(py.stem)
            elif py.name != '__init__.py':
                local.add(py.stem)
        for sub in scripts_dir.iterdir():
            if sub.is_dir() and not sub.name.startswith('.') and (
                (sub / '__init__.py').exists() or any(sub.glob('*.py'))
            ):
                local.add(sub.name)
    return local


# 直接 import 但由已声明包提供的传递依赖 (不必重复写进 requirements.txt)
# starlette: fastapi 运行时依赖, middleware/tests 会直接 from starlette...
TRANSITIVE_ALLOWED: set[str] = {
    'starlette',
    'anyio',
    'sniffio',
    'h11',
    'httptools',
    'websockets',
    'watchfiles',
    'multipart',  # python-multipart import name varies
}

LOCAL_PACKAGES = _detect_local_packages()


def is_stdlib(name: str) -> bool:
    return name.lower() in STDLIB


def is_local_package(name: str) -> bool:
    """项目本地包 (如 backend/, scraper/, scripts/) 跳过."""
    return name in LOCAL_PACKAGES or name.lower() in {p.lower() for p in LOCAL_PACKAGES}


def get_third_party_imports(root_dirs: list[str]) -> set[str]:
    """AST scan all .py under root_dirs, return set of top-level 3rd party import names."""
    imports: set[str] = set()
    for root in root_dirs:
        root_p = pathlib.Path(root)
        if not root_p.exists():
            continue
        for py in root_p.rglob('*.py'):
            # skip caches and venvs
            if any(part in py.parts for part in ('__pycache__', 'node_modules')):
                continue
            if '.venv' in py.parts or 'venv' in py.parts:
                continue
            try:
                source = py.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(source, filename=str(py))
            except (SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split('.')[0]
                        if top and not is_stdlib(top) and not is_local_package(top):
                            imports.add(top)
                elif isinstance(node, ast.ImportFrom):
                    # level > 0 = relative import (intra-package), skip
                    if node.level and node.level > 0:
                        continue
                    if node.module:
                        top = node.module.split('.')[0]
                        if top and not is_stdlib(top) and not is_local_package(top):
                            imports.add(top)
    return imports


def get_requirements(requirements_path: str = 'requirements.txt') -> set[str]:
    """Parse requirements.txt, return set of pip package names (lowercase)."""
    reqs: set[str] = set()
    p = pathlib.Path(requirements_path)
    if not p.exists():
        return reqs
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        # strip version specifier / extras / markers
        # pip syntax: name[extras]>=1.0; marker
        name = re.split(r'[><=!\[;]', line, maxsplit=1)[0].strip()
        if name:
            reqs.add(name.lower())
    return reqs


def normalize_to_pip(import_name: str) -> str:
    """Convert Python import name to pip package name."""
    return PIP_ALIASES.get(import_name, import_name.lower())


def find_files_using(import_name: str, root_dirs: list[str]) -> list[str]:
    """Find .py files that import the given name. Used for error messages."""
    users: list[str] = []
    pattern = re.compile(
        rf'^\s*(?:import|from)\s+{re.escape(import_name)}\b',
        re.MULTILINE,
    )
    for root in root_dirs:
        root_p = pathlib.Path(root)
        if not root_p.exists():
            continue
        for py in root_p.rglob('*.py'):
            if any(part in py.parts for part in ('__pycache__',)):
                continue
            try:
                src = py.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            if pattern.search(src):
                users.append(str(py))
    return users


def main() -> int:
    scan_roots = ['backend', 'scripts/etl']
    imports = get_third_party_imports(scan_roots)
    reqs = get_requirements()

    # Normalize import names → pip names
    pip_imports = {normalize_to_pip(i) for i in imports}

    # Missing = in code but not declared (exclude known transitive deps of declared packages)
    missing = pip_imports - reqs - {t.lower() for t in TRANSITIVE_ALLOWED}

    if missing:
        print("❌ B2: 检测到 3rd-party imports 在代码中但 requirements.txt 没声明:")
        print()
        for m in sorted(missing):
            # find which file(s) actually use it (try import name + common reverse aliases)
            users = find_files_using(m, scan_roots)
            if not users:
                # reverse alias: pillow → may appear as PIL in source
                for imp_name, pip_name in PIP_ALIASES.items():
                    if pip_name == m:
                        users = find_files_using(imp_name, scan_roots)
                        if users:
                            break
            sample = ', '.join(users[:3]) + ('...' if len(users) > 3 else '')
            print(f"  - {m}  (used in: {sample or 'n/a'})")
        print()
        print("修复: 在 requirements.txt 加缺失的包, 然后重跑 commit.")
        print("例外 (确认 deps 故意未声明): git commit --no-verify")
        print(f"(debug) local_packages sample: {sorted(LOCAL_PACKAGES)[:12]}…")
        return 1

    print(f"✅ B2: {len(imports)} 个 3rd-party imports 全部声明在 requirements.txt")
    print(f"   (local packages detected: {len(LOCAL_PACKAGES)}; transitive allow: {len(TRANSITIVE_ALLOWED)})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
