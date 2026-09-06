"""Exercise maintenance against a private temporary Git repository."""
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/branch_cleanup.py"


@pytest.fixture
def repo(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, check=True).stdout.strip()
    git('init', '-b', 'main')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '--allow-empty', '-m', 'fixture')
    git('branch', 'merged')
    def invoke(*args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=tmp_path,
                              env=env, capture_output=True, text=True, timeout=10)
    return git, invoke


def test_default_only_previews(repo):
    git, invoke = repo
    before = git('show-ref')
    result = invoke()
    assert result.returncode == 0, result.stderr
    assert 'preview only' in result.stdout
    assert git('show-ref') == before


def test_apply_requires_exact_targets(repo):
    git, invoke = repo
    assert invoke('--apply').returncode == 2
    assert invoke('--apply', '--local', 'main').returncode != 0
    assert 'refs/heads/merged' in git('show-ref')


def test_apply_deletes_only_selected_merged_branch(repo):
    git, invoke = repo
    git('branch', 'keep')
    result = invoke('--apply', '--local', 'merged')
    assert result.returncode == 0, result.stderr + result.stdout
    refs = git('show-ref')
    assert 'refs/heads/merged' not in refs
    assert 'refs/heads/keep' in refs and 'refs/heads/main' in refs


def test_unmerged_branch_is_refused(repo):
    git, invoke = repo
    git('checkout', '-b', 'unmerged')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '--allow-empty', '-m', 'not merged')
    git('checkout', 'main')
    assert invoke('--apply', '--local', 'unmerged').returncode != 0
    assert 'refs/heads/unmerged' in git('show-ref')


def test_occupied_worktree_branch_is_refused(repo, tmp_path):
    git, invoke = repo
    git('worktree', 'add', str(tmp_path.parent / (tmp_path.name + '-occupied')), 'merged')
    assert invoke('--apply', '--local', 'merged').returncode != 0
    assert 'refs/heads/merged' in git('show-ref')


def test_delete_failure_never_force_deletes(monkeypatch):
    from scripts import branch_cleanup as cleanup
    calls = []
    monkeypatch.setattr(cleanup, 'is_merged', lambda branch: True)
    def refuse(args):
        calls.append(args)
        return 1, 'refused'
    monkeypatch.setattr(cleanup, 'run', refuse)
    assert cleanup.delete_local('topic', dry_run=False) is False
    assert calls == [['git', 'branch', '-d', '--', 'topic']]


def test_no_agent_hook_automatically_cleans_branches():
    settings = json.loads((ROOT / '.claude/settings.json').read_text())
    assert 'branch_cleanup' not in json.dumps(settings.get('hooks', {}))
    assert 'branch_cleanup' not in (ROOT / '.githooks/post-merge').read_text()
