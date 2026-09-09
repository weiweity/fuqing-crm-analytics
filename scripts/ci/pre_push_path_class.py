#!/usr/bin/env python3
"""Shared changed-path matrix for local validation and CI.

The backend, B0, Vue, tooling, dependency and deployment axes are independent.
No files means an unknown range and conservatively selects backend + tooling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# --- path rules (POSIX-style relative paths from repo root) ---

# Tests-only → scoped (not full suite)
_TEST_PREFIXES = (
    "backend/tests/",
)

# Docs-only skip (all files must match)
_SKIP_PREFIXES = (
    "docs/",
    "memory/",
    "outputs/",
)
# Root / tooling config that must not force full pytest (hygiene push lesson)
_SKIP_EXACT = frozenset(
    {
        ".gitignore",
        ".gitattributes",
        ".gitmessage",
        ".mcp.json",
        ".pre-commit-config.yaml",
        ".dockerignore",
        "VERSION",
        "Dockerfile",
        "docker-compose.yml",
        "package.json",
        "package-lock.json",
    }
)
_SKIP_NAME_RE = re.compile(
    r"(^|/)("
    r"CHANGELOG.*|"
    r"HANDOFF.*|"
    r"STATUS\.md|"
    r"README.*|"
    r"TECH-DEBT\.md|"
    r"\.ship-audit\.log"
    r")$",
    re.IGNORECASE,
)
_SKIP_MD_RE = re.compile(r"\.md$", re.IGNORECASE)

def _norm(path: str) -> str:
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def is_test_path(path: str) -> bool:
    p = _norm(path)
    if not p:
        return False
    return any(p.startswith(pref) for pref in _TEST_PREFIXES)


def is_skip_path(path: str) -> bool:
    p = _norm(path)
    if not p:
        return True
    if p in _SKIP_EXACT:
        return True
    if any(p.startswith(pref) for pref in _SKIP_PREFIXES):
        return True
    if _SKIP_NAME_RE.search(p):
        return True
    # bare markdown anywhere (e.g. CLAUDE.md, AGENTS.md at root)
    if _SKIP_MD_RE.search(p) and "/" not in p:
        return True
    if _SKIP_MD_RE.search(p) and p.startswith("docs/"):
        return True
    # any .md under non-code trees already covered; root-level .md
    if _SKIP_MD_RE.search(p) and not p.startswith("backend/") and not p.startswith(
        "frontend"
    ):
        return True
    return False


def scoped_pytest_targets(paths: list[str]) -> list[str]:
    """Return unique backend/tests/*.py paths suitable for scoped pytest argv."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        p = _norm(raw)
        if not is_test_path(p):
            continue
        # only .py test modules (skip __pycache__, snapshots, etc.)
        if not p.endswith(".py") or not Path(p).name.startswith("test_"):
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


B0_PREFIXES = ('dsh-plugins/analytics-workbench/', 'scripts/dsh-b0/', 'scripts/dsh-dev/',
               'backend/services/analytics/', 'backend/tests/analytics_')
B0_EXACT = {'backend/contracts/analytics.py', 'backend/semantic/analytics_b0.py',
            '.github/workflows/dsh-b0.yml', 'backend/analytics_analysis_app.py',
            'backend/contracts/analytics_analysis.py', 'backend/contracts/analytics-analysis.openapi.json',
            'backend/analytics_cockpit_app.py', 'backend/contracts/analytics_cockpit.py',
            'backend/contracts/analytics-cockpit.openapi.json', 'backend/analytics_runtime.py'}
SHARED = {'backend/tests/conftest.py', 'pyproject.toml', 'requirements.txt',
          'requirements-lock.txt', 'uv.lock', 'scripts/run_backend_tests_bounded.py'}
GROUND_TRUTH_PREFIXES = ('docs/validation-reports/', 'docs/飞书版架构文档/')
FILTERBUILDER_EXACT = {
    'backend/scripts/check_filter_builder_usage.py',
    'backend/scripts/check_channel_alias.py',
}
TOOL_TESTS = [
    'backend/tests/test_git_hook_boundaries.py',
    'backend/tests/test_pre_push_smart_path.py',
    'backend/tests/test_precommit_changelog.py',
    'backend/tests/test_agent_rule_entrypoints.py',
    'backend/tests/test_claude_hooks.py',
    'backend/tests/test_branch_cleanup.py',
    'backend/tests/test_check_runner.py',
    'backend/tests/test_excel_lint_index.py',
    'backend/tests/test_check_l4_91_excel_export_ssot.py',
    'backend/tests/test_github_actions_hardening.py',
    'backend/tests/test_ci_e2e_env_config.py',
    'backend/tests/test_ci_lfs_checkout.py',
]


def is_b0_path(path: str) -> bool:
    return (path in B0_EXACT or path.startswith(B0_PREFIXES)
            or (path.startswith('backend/analytics') and path.endswith('.py'))
            or path.startswith('backend/tests/test_analytics_'))


def verification_plan(paths: list[str]) -> dict:
    """Independent axes, so mixed changes never lose another module's checks.

    Deleted files remain in the input plan. The runner checks existence only
    when forming an executable target; missing test modules expand to full.
    """
    files = sorted({_norm(p) for p in paths if _norm(p)})
    plan = {'backend': 'none', 'b0': False, 'frontend': False,
            'tooling': False, 'deployment': False, 'dependencies': False,
            'ground_truth': False, 'filterbuilder': False,
            'targets': [], 'files': files}
    for p in files:
        if p in SHARED:
            plan['backend'] = 'full'
            plan['tooling'] = True
            if p not in {'backend/tests/conftest.py', 'scripts/run_backend_tests_bounded.py'}:
                plan['dependencies'] = True
                plan['b0'] = True
        elif is_b0_path(p):
            plan['b0'] = True
            if p.startswith('.github/'):
                plan['tooling'] = True
            # FilterBuilder scanners walk backend/services/**, including analytics.
            if p.startswith('backend/services/'):
                plan['filterbuilder'] = True
            # B0-prefixed tests must still run as scoped Python; #80 skipped otherwise.
            if is_test_path(p):
                if Path(p).name.startswith('test_') and p.endswith('.py'):
                    plan['targets'].append(p)
                    if plan['backend'] == 'none':
                        plan['backend'] = 'scoped'
                else:
                    plan['backend'] = 'full'
        elif p.startswith('frontend-vue3/'):
            plan['frontend'] = True
            if p.endswith(('package.json', 'package-lock.json')):
                plan['dependencies'] = True
            if '/assets/brand/' in p or p in {'frontend-vue3/src/App.vue',
                  'frontend-vue3/src/composables/useFilterSync.ts',
                  'frontend-vue3/public/shine-mage-mark.svg'}:
                plan['b0'] = True
            if p.endswith('Dockerfile'):
                plan['deployment'] = True
        elif p.startswith(('.githooks/', 'scripts/ci/', '.github/', '.claude/')) or p in {
                'AGENTS.md', 'CLAUDE.md', 'scripts/branch_cleanup.py', 'scripts/setup-hooks.sh',
                'scripts/sync-agents.sh', '.pre-commit-config.yaml'}:
            plan['tooling'] = True
            if p.startswith(('.github/workflows/', 'scripts/ci/')):
                plan['b0'] = True
            if p.startswith('.github/workflows/'):
                plan['backend'] = 'full'
                plan['frontend'] = True
                plan['deployment'] = True
                plan['dependencies'] = True
            if p.endswith('check_review_ground_truth.py'):
                plan['ground_truth'] = True
        elif is_test_path(p):
            if Path(p).name.startswith('test_') and p.endswith('.py'):
                plan['targets'].append(p)
                if plan['backend'] == 'none':
                    plan['backend'] = 'scoped'
            else:
                plan['backend'] = 'full'
        elif p in {'Dockerfile', 'docker-compose.yml', '.dockerignore'}:
            plan['deployment'] = True
            plan['backend'] = 'full'
        elif p.startswith(('docs/operating/', 'docs/maintenance/')):
            plan['tooling'] = True
        elif p.startswith(GROUND_TRUTH_PREFIXES):
            plan['tooling'] = True
            plan['ground_truth'] = True
        elif p in FILTERBUILDER_EXACT:
            plan['filterbuilder'] = True
            plan['backend'] = 'full'
        elif is_skip_path(p):
            continue
        else:
            # Unmapped code, offline ETL and root configuration are conservative.
            plan['backend'] = 'full'
            if p.startswith('backend/services/'):
                plan['filterbuilder'] = True
    if not files:
        plan['backend'] = 'full'
        plan['tooling'] = True
    return plan


def classify_paths(paths: list[str]) -> str:
    plan = verification_plan(paths)
    if plan['backend'] == 'full':
        return 'full'
    if plan['backend'] == 'scoped':
        return 'scoped'
    if plan['b0'] or plan['frontend']:
        return 'matrix'
    return 'tooling' if plan['tooling'] else 'skip'


def load_deselect_nodeids(ssot: Path | None = None) -> list[str]:
    """Load C-class nodeids from SSOT txt (non-comment lines)."""
    if ssot is None:
        ssot = Path(__file__).resolve().parent / "pytest_c_class_deselects.txt"
    nodeids: list[str] = []
    for raw in ssot.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        nodeids.append(line)
    return nodeids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify pre-push changed paths")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Changed file paths (relative to repo root)",
    )
    parser.add_argument(
        "--files-from",
        metavar="FILE",
        help="Read paths from file (use - for stdin)",
    )
    parser.add_argument(
        "--list-deselects",
        action="store_true",
        help="Print C-class deselect nodeids (one per line) and exit",
    )
    parser.add_argument(
        "--list-scoped-targets",
        action="store_true",
        help="Print scoped pytest file targets for given paths and exit",
    )
    parser.add_argument("--json", action="store_true", help="emit the shared check matrix")
    parser.add_argument("--github-output", action="store_true", help="write CI job flags to GITHUB_OUTPUT")
    args = parser.parse_args(argv)

    if args.list_deselects:
        for n in load_deselect_nodeids():
            print(n)
        return 0

    paths: list[str] = list(args.paths)
    if args.files_from:
        if args.files_from == "-":
            paths.extend(sys.stdin.read().splitlines())
        else:
            paths.extend(
                Path(args.files_from).read_text(encoding="utf-8").splitlines()
            )

    if args.list_scoped_targets:
        for t in scoped_pytest_targets(paths):
            print(t)
        return 0

    plan = verification_plan(paths)
    if args.github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            for axis in ('b0', 'frontend', 'tooling', 'deployment', 'dependencies',
                         'ground_truth', 'filterbuilder'):
                output.write(f'{axis}={str(plan[axis]).lower()}\n')
            output.write(f'backend={str(plan["backend"] != "none").lower()}\n')
            output.write(f'checks={str(plan["backend"] != "none" or plan["tooling"]).lower()}\n')
            output.write(f'plan={json.dumps(plan)}\n')
    print(json.dumps(plan) if args.json else classify_paths(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
