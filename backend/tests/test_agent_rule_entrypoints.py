"""Single authoritative rule entrypoint; the legacy sync command is read-only."""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("agents,claude,args,expected", [
    ("# Authoritative\\nKEEP USER EDITS\\n", "@AGENTS.md\\n", [], 0),
    ("# Authoritative\\n", "@AGENTS.md\\n", ["--check"], 0),
    (None, "@AGENTS.md\\n", [], 1),
    ("", "@AGENTS.md\\n", [], 1),
    ("# Authoritative\\n", "# stale old rules\\n", [], 1),
    ("# Authoritative\\n", None, [], 1),
    ("# Authoritative\\n", "@AGENTS.md\\n", ["--force"], 2),
])
def test_sync_command_never_overwrites_rules(tmp_path, agents, claude, args, expected):
    repo = tmp_path / "repo with spaces"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    check = scripts / "sync-agents.sh"
    shutil.copy2(ROOT / "scripts/sync-agents.sh", check)
    for name, content in (("AGENTS.md", agents), ("CLAUDE.md", claude)):
        if content is not None:
            (repo / name).write_text(content.replace("\\n", "\n"))
    before = {p.name: p.read_bytes() for p in repo.iterdir() if p.is_file()}
    result = subprocess.run(
        ["bash", str(check), *args], cwd=tmp_path, capture_output=True,
        text=True, timeout=10, env={"PATH": "/usr/bin:/bin"},
    )
    after = {p.name: p.read_bytes() for p in repo.iterdir() if p.is_file()}
    assert result.returncode == expected, result.stdout + result.stderr
    assert after == before


@pytest.mark.parametrize("configured,expected", [(".githooks", 0), ("absolute", 0), ("other", 1), ("", 1)])
def test_precommit_checks_configuration_without_mutating_it(tmp_path, configured, expected):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    mutations = tmp_path / "git-mutations.json"
    git = bindir / "git"
    hook_path = str(tmp_path / ".githooks") if configured == "absolute" else configured
    git.write_text(
        f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
        "args = sys.argv[1:]\n"
        f"if args == ['rev-parse', '--show-toplevel']: print({str(tmp_path)!r})\n"
        f"elif args == ['config', 'core.hooksPath']: print({hook_path!r})\n"
        "elif args[:1] == ['diff']: pass\n"
        "else:\n"
        f"    Path({str(mutations)!r}).write_text(json.dumps(args))\n"
        "    sys.exit(3)\n"
    )
    git.chmod(0o700)
    result = subprocess.run(
        ["/bin/bash", str(ROOT / ".githooks/pre-commit")], cwd=tmp_path,
        capture_output=True, text=True, timeout=10,
        env={"PATH": f"{bindir}:/usr/bin:/bin"},
    )
    assert not mutations.exists(), json.loads(mutations.read_text()) if mutations.exists() else ""
    assert result.returncode == expected, result.stdout + result.stderr
