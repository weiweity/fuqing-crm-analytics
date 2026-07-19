#!/usr/bin/env python3
"""pre-push smart path classifier (Track A 2026-07-19).

Classify a list of changed file paths into one of:

  skip  — docs / markdown / changelog / handoff only → skip full pytest
  ruff  — scripts / hooks / tooling only (no business tests) → ruff check backend/
  full  — backend tests/services/routers/middleware/db/main/requirements → full pytest

Default is full (safe). Pure functions — unit-testable without git.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- path rules (POSIX-style relative paths from repo root) ---

# Force full pytest if any path matches
_FULL_PREFIXES = (
    "backend/tests/",
    "backend/services/",
    "backend/routers/",
    "backend/middleware/",
    "backend/db/",
    "backend/contracts/",
    "backend/semantic/",
    "backend/auth/",
)
_FULL_EXACT = frozenset(
    {
        "backend/main.py",
        "requirements.txt",
        "requirements-lock.txt",
        "pyproject.toml",
    }
)
_FULL_NAME_RE = re.compile(r"^requirements.*\.txt$")

# Docs-only skip (all files must match)
_SKIP_PREFIXES = (
    "docs/",
    "memory/",
    "outputs/",
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

# Ruff / tooling path (no full pytest required if only these + skip)
_RUFF_PREFIXES = (
    "scripts/",
    "backend/scripts/",
    ".githooks/",
    ".github/",
)


def _norm(path: str) -> str:
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def is_full_path(path: str) -> bool:
    p = _norm(path)
    if not p:
        return False
    if p in _FULL_EXACT:
        return True
    if _FULL_NAME_RE.match(p):
        return True
    return any(p.startswith(pref) for pref in _FULL_PREFIXES)


def is_skip_path(path: str) -> bool:
    p = _norm(path)
    if not p:
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
    if _SKIP_MD_RE.search(p) and not p.startswith("backend/") and not p.startswith("frontend"):
        return True
    return False


def is_ruff_path(path: str) -> bool:
    p = _norm(path)
    if not p:
        return False
    return any(p.startswith(pref) for pref in _RUFF_PREFIXES)


def classify_paths(paths: list[str]) -> str:
    """Return 'skip' | 'ruff' | 'full' for a changed-file list."""
    files = [_norm(p) for p in paths if _norm(p)]
    if not files:
        # empty diff → safe default full (unknown push range)
        return "full"
    if all(is_skip_path(p) for p in files):
        return "skip"
    if any(is_full_path(p) for p in files):
        return "full"
    if all(is_skip_path(p) or is_ruff_path(p) for p in files):
        return "ruff"
    # e.g. frontend-only: pre-push only runs backend pytest → skip full suite
    frontend_only = all(
        p.startswith("frontend-vue3/") or is_skip_path(p) for p in files
    )
    if frontend_only:
        return "skip"
    return "full"


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
            paths.extend(Path(args.files_from).read_text(encoding="utf-8").splitlines())

    mode = classify_paths(paths)
    print(mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
