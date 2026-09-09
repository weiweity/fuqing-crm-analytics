#!/usr/bin/env python3
"""Run the shared changed-path plan. Installs nothing and never starts a service."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ci.pre_push_path_class import TOOL_TESTS, verification_plan  # noqa: E402


def commands(plan: dict, root: Path = ROOT, only: str | None = None) -> list[tuple[str, list[str], Path]]:
    steps = []
    def add(axis, args, cwd=root):
        if only is None or only == axis or (only in {'python', 'ci-python'} and axis in {'backend', 'tooling'}):
            steps.append((axis, args, cwd))
    python = sys.executable
    if plan['backend'] != 'none':
        targets = plan['targets'] if plan['backend'] == 'scoped' else []
        # A deleted/renamed test file is a real change, never silently dropped.
        if any(not (root / target).is_file() for target in targets):
            targets = []
        # CI's required lint job owns backend Ruff and the Agent entrypoint.
        # Local/default plans remain self-contained.
        if only != 'ci-python':
            add('backend', [python, '-m', 'ruff', 'check', 'backend/'])
        add('backend', [python, '.githooks/check_imports.py'])
        add('backend', [python, 'scripts/run_backend_tests_bounded.py', *targets])
    if plan['tooling']:
        if only != 'ci-python':
            add('tooling', ['bash', 'scripts/sync-agents.sh', '--check'])
        elif plan['backend'] == 'none':
            add('tooling', [python, '.githooks/check_imports.py'])
        changed_python = [p for p in plan['files'] if p.endswith('.py') and (root / p).is_file()]
        if only == 'ci-python':
            changed_python = [p for p in changed_python if not p.startswith('backend/')]
        if changed_python:
            add('tooling', [python, '-m', 'ruff', 'check', *changed_python])
        for path in plan['files']:
            source = root / path
            if source.is_file() and (path.endswith('.sh') or path in {
                    '.githooks/pre-commit', '.githooks/pre-push', '.githooks/post-merge', '.githooks/commit-msg'}):
                add('tooling', ['bash', '-n', path])
        # A full backend run already includes these tests. Avoid running twice.
        if plan['backend'] != 'full' or only == 'tooling':
            add('tooling', [python, '-m', 'pytest', '--noconftest', '-p', 'no:cacheprovider',
                            '-x', '-q', *TOOL_TESTS])
    if plan['frontend']:
        for task in ('build', 'test:unit'):
            add('frontend', ['npm', 'run', task], root / 'frontend-vue3')
    if plan['b0']:
        b0_python = os.environ.get('FQ_B0_PYTHON', python)
        if not Path(b0_python).is_absolute() or not Path(b0_python).is_file():
            raise ValueError('FQ_B0_PYTHON must name an existing absolute Python executable')
        add('b0', ['node', 'scripts/dsh-b0/pipeline.mjs', '--check', '--python', b0_python])
    return steps


def execute(steps, run=subprocess.run) -> int:
    for axis, args, cwd in steps:
        print(f'[checks:{axis}] {" ".join(args)}', flush=True)
        result = run(args, cwd=cwd, check=False)
        if result.returncode:
            return int(result.returncode)
    return 0


def preflight(plan: dict, only: str | None, run=subprocess.run) -> int:
    selected = only is None or only in {'b0', 'frontend'}
    if selected and ((plan['b0'] and only != 'frontend') or (plan['frontend'] and only != 'b0')):
        expected = json.loads((ROOT / 'dsh-plugins/analytics-workbench/toolchain.json').read_text())['node_major']
        try:
            result = run(['node', '--version'], capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print('Node unavailable; select the existing pinned runtime with --node /absolute/node', file=sys.stderr)
            return 2
        actual = result.stdout.strip().lstrip('v').split('.')[0]
        if result.returncode or actual != str(expected):
            print(f'Checks require Node {expected}; found {actual}. Select --node /absolute/node before running checks.', file=sys.stderr)
            return 2
    if plan['b0'] and only in (None, 'b0') and sys.version_info < (3, 14):
        print('B0 requires the existing Python 3.14+ environment', file=sys.stderr)
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files-from', required=True, help='newline-delimited paths, or - for stdin')
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--node', type=Path, help='existing Node binary; changes only this check process PATH')
    parser.add_argument('--only', choices=['backend', 'tooling', 'frontend', 'b0', 'python', 'ci-python'])
    parser.add_argument('--backend-mode', choices=['skip', 'ruff', 'scoped', 'full'])
    args = parser.parse_args(argv)
    paths = sys.stdin.read().splitlines() if args.files_from == '-' else Path(args.files_from).read_text().splitlines()
    plan = verification_plan(paths)
    if args.backend_mode:
        plan['backend'] = {'skip': 'none', 'ruff': 'none'}.get(args.backend_mode, args.backend_mode)
        if args.backend_mode == 'ruff':
            plan['tooling'] = True
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    if args.plan_only:
        return 0
    if args.node:
        if not args.node.is_absolute() or not args.node.is_file() or args.node.name != 'node':
            parser.error('--node must be an existing absolute path to a node binary')
        os.environ['PATH'] = str(args.node.parent) + os.pathsep + os.environ.get('PATH', '')
    status = preflight(plan, args.only)
    if status:
        return status
    # Dependency audit and container smoke run as separate CI jobs: local
    # validation never installs packages, accesses audit registries or starts Docker.
    return execute(commands(plan, only=args.only))


if __name__ == '__main__':
    raise SystemExit(main())
