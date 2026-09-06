"""Exercise the commands actually registered in the project hook configuration.

No copied hook implementation, real Git mutations, global config, service start,
or in-place source corruption. Dangerous commands are input strings only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".claude" / "settings.json"


@pytest.fixture
def sandbox(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    tripwire = tmp_path / "unexpected-actions"
    for name in ("branch_cleanup", "session_start_check", "session_close_check",
                 "check_remaining_tasks"):
        (scripts / f"{name}.py").write_text(
            f"from pathlib import Path\nPath({str(tripwire)!r}).write_text('called')\n"
        )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    lint_log = tmp_path / "lint-args.json"
    ruff = bindir / "ruff"
    ruff.write_text(
        f"#!{sys.executable}\nimport json, os, sys\nfrom pathlib import Path\n"
        f"Path({str(lint_log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "sys.exit(int(os.environ.get('FAKE_RUFF_EXIT', '0')))\n"
    )
    ruff.chmod(0o700)
    return tmp_path, tripwire, lint_log, {
        "PATH": f"{bindir}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}/usr/bin:/bin",
        "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
    }


def dispatch(event, tool, payload, sandbox, extra_env=None):
    cwd, _, _, env = sandbox
    config = json.loads(CONFIG.read_text())
    results = []
    for rule in config.get("hooks", {}).get(event, []):
        matcher = rule.get("matcher", "*")
        if matcher != "*" and not re.search(matcher, tool):
            continue
        for hook in rule["hooks"]:
            assert hook["type"] == "command"
            results.append(subprocess.run(
                ["/bin/sh", "-c", hook["command"]],
                input=json.dumps({"tool_name": tool, "tool_input": payload}),
                text=True, capture_output=True, timeout=10, cwd=cwd,
                env={**env, **(extra_env or {})},
            ))
    return results


@pytest.mark.parametrize("path", [
    ".env", "/isolated/project/.env", ".env.local", "nested/.env.test.local",
    "data/processed/sample.duckdb", "/isolated/project/data/processed/sample.duckdb",
])
def test_configured_edit_hook_blocks_protected_paths(path, sandbox):
    results = dispatch("PreToolUse", "Edit", {"file_path": path}, sandbox)
    assert results and all(result.returncode == 2 for result in results)


@pytest.mark.parametrize("path", [".env.example", "backend/example.py", "AGENTS.md"])
def test_configured_edit_hook_allows_normal_source(path, sandbox):
    results = dispatch("PreToolUse", "Write", {"file_path": path}, sandbox)
    assert results and all(result.returncode == 0 for result in results)


@pytest.mark.parametrize("command", [
    "git push origin main --force", "git push origin main -f",
    "rm -rf /tmp", "rm -rf /", "chmod -R 777 /tmp", "chmod -R 777 /",
    "mkfs.ext4 /dev/sda1", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/sda",
])
def test_configured_bash_guard_blocks_dangerous_input(command, sandbox):
    results = dispatch("PreToolUse", "Bash", {"command": command}, sandbox)
    assert results and all(result.returncode == 2 for result in results)


@pytest.mark.parametrize("command", ["git status --short", "ls -la", "git push origin main"])
def test_guard_is_not_a_general_permission_grant(command, sandbox):
    # Passing this pattern guard does not supply Git/external-action permission.
    results = dispatch("PreToolUse", "Bash", {"command": command}, sandbox)
    assert results and all(result.returncode == 0 for result in results)


@pytest.mark.parametrize("code", ["0", "1"])
def test_post_edit_lints_only_the_target_without_fixing_it(code, sandbox):
    result = dispatch("PostToolUse", "Edit", {"file_path": "backend/example.py"},
                      sandbox, {"FAKE_RUFF_EXIT": code})
    assert result and all(row.returncode == 0 for row in result)
    assert json.loads(sandbox[2].read_text()) == ["check", "backend/example.py"]


def test_contract_reminder_does_not_generate_or_start_service(sandbox):
    results = dispatch("PostToolUse", "Edit", {"file_path": "backend/contracts/analytics.py"}, sandbox)
    assert results and all(row.returncode == 0 for row in results)
    assert "contract" in "".join(row.stdout for row in results)
    assert not sandbox[1].exists()


def test_non_python_edit_does_not_lint(sandbox):
    results = dispatch("PostToolUse", "Write", {"file_path": "AGENTS.md"}, sandbox)
    assert all(row.returncode == 0 for row in results)
    assert not sandbox[2].exists()


@pytest.mark.parametrize("event,tool,payload", [
    ("PostToolUse", "Bash", {"command": "git push origin main"}),
    ("SessionStart", "*", {}),
    ("Stop", "*", {}),
    ("UserPromptSubmit", "剩余任务 backlog", {}),
])
def test_no_implicit_cleanup_config_change_or_global_scan(event, tool, payload, sandbox):
    # An accidental restored legacy hook would run a harmless tripwire, not the
    # real maintenance script. Also demand zero registered commands for this event.
    results = dispatch(event, tool, payload, sandbox)
    assert not sandbox[1].exists(), f"{event} invoked legacy maintenance"
    assert results == []
