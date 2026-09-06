"""Exercise the configured Git hook programs without touching real Git state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
ZERO = "0" * 40
REFS = f"refs/heads/topic {'a' * 40} refs/heads/topic {ZERO}\n"


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)


@pytest.fixture
def hook_env(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "calls.jsonl"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "FQ_", "STRICT_CHANGELOG"))}
    env.update(PATH=f"{tools}:/usr/bin:/bin", HOOK_ROOT=str(tmp_path),
               CALL_LOG=str(log), REAL_PYTHON=sys.executable,
               PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="1")
    executable(tools / "git", f"#!{sys.executable}\n" + '''
import json, os, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps({'tool': 'git', 'args': args}) + '\\n')
if args == ['rev-parse', '--show-toplevel']:
    print(os.environ['HOOK_ROOT'])
elif args == ['config', 'core.hooksPath']:
    print('.githooks')
elif args[:2] == ['diff', '--cached']:
    print(os.environ.get('STAGED_FILES', 'backend/example.py'))
elif args[:2] == ['rev-parse', '--abbrev-ref']:
    print(os.environ.get('TEST_BRANCH', 'main'))
elif args[:1] == ['log']:
    print('a' * 40 + ' fix: sample')
elif args[:1] == ['describe']:
    sys.exit(1)
elif args[:1] == ['merge-base']:
    print('b' * 40)
elif args[:1] == ['diff']:
    print('docs/example.md')
elif args[:2] == ['lfs', 'pre-push']:
    with open(os.environ['CALL_LOG'], 'a') as f:
        f.write(json.dumps({'lfs_refs': sys.stdin.read(), 'remote_args': args[2:]}) + '\\n')
    sys.exit(int(os.environ.get('LFS_EXIT', '0')))
elif args[:1] not in [['rev-parse'], ['status']] and args != ['lfs', 'version']:
    raise SystemExit('unexpected git operation: ' + repr(args))
''')
    executable(tools / "python3", f"#!{sys.executable}\n" + '''
import json, os, subprocess, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps({'tool': 'python', 'args': args}) + '\\n')
if args and args[0].endswith('pre_push_path_class.py'):
    sys.exit(subprocess.call([os.environ['REAL_PYTHON'], *args]))
if os.environ.get('FAIL_CHECK') and os.environ['FAIL_CHECK'] in ' '.join(args):
    print('controlled checker failure')
    sys.exit(23)
''')
    # post-merge historically picked this absolute Python before PATH. The
    # maintenance script itself is a harmless tripwire, even on that path.
    executable(tmp_path / "scripts/branch_cleanup.py",
               "from pathlib import Path\nPath('maintenance-was-called').touch()\n")
    for name in ['check_imports.py', 'check_test_order.py', 'check_review_ground_truth.py']:
        executable(tmp_path / '.githooks' / name, '# fixture\n')
    (tmp_path / 'backend/scripts').mkdir(parents=True)
    (tmp_path / 'backend/scripts/check_l4_91_excel_export_ssot.py').touch()
    (tmp_path / 'scripts/ci').mkdir(parents=True)
    shutil.copyfile(ROOT / 'scripts/ci/pre_push_path_class.py',
                    tmp_path / 'scripts/ci/pre_push_path_class.py')
    return tmp_path, env, log


def run_hook(name, fixture, *, refs="", extra=None, args=()):
    cwd, env, _ = fixture
    return subprocess.run(['/bin/bash', str(ROOT / '.githooks' / name), *args],
                          cwd=cwd, env={**env, **(extra or {})}, input=refs,
                          text=True, capture_output=True, timeout=15)


@pytest.mark.parametrize('check,staged', [
    ('backend.contracts._lint', 'backend/contracts/example.py'),
    ('check_imports.py', 'backend/example.py'),
    ('check_test_order.py', 'backend/tests/test_example.py'),
    ('check_review_ground_truth.py', 'backend/example.py'),
    ('check_l4_91_excel_export_ssot.py', 'frontend-vue3/src/example.ts'),
])
def test_precommit_propagates_checker_failure(hook_env, check, staged):
    result = run_hook('pre-commit', hook_env,
                      extra={'FAIL_CHECK': check, 'STAGED_FILES': staged})
    assert result.returncode != 0, result.stdout + result.stderr
    assert 'controlled checker failure' in result.stdout


def test_postmerge_audits_without_maintenance(hook_env):
    result = run_hook('post-merge', hook_env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (hook_env[0] / 'maintenance-was-called').exists()
    assert 'a' * 40 in (hook_env[0] / '.ship-audit.log').read_text()


def test_feature_postmerge_does_not_write_audit(hook_env):
    result = run_hook('post-merge', hook_env, extra={'TEST_BRANCH': 'topic'})
    assert result.returncode == 0
    assert not (hook_env[0] / '.ship-audit.log').exists()
    assert not (hook_env[0] / 'maintenance-was-called').exists()


@pytest.mark.parametrize('extra', [{}, {'FQ_PRE_PUSH_SKIP': '1'}])
def test_pre_push_preserves_refs_for_lfs_even_when_checks_skip(hook_env, extra):
    result = run_hook('pre-push', hook_env, refs=REFS, extra=extra,
                      args=('origin', 'local-fixture-remote'))
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [json.loads(line) for line in hook_env[2].read_text().splitlines()]
    uploads = [row for row in rows if 'lfs_refs' in row]
    assert uploads == [{'lfs_refs': REFS, 'remote_args': ['origin', 'local-fixture-remote']}]


def test_pre_push_propagates_lfs_failure(hook_env):
    result = run_hook('pre-push', hook_env, refs=REFS, extra={'LFS_EXIT': '42'},
                      args=('origin', 'local-fixture-remote'))
    assert result.returncode == 42, result.stdout + result.stderr


def test_delete_only_does_not_upload_or_validate(hook_env):
    result = run_hook('pre-push', hook_env,
                      refs=f'(delete) {ZERO} refs/heads/topic {"b" * 40}\n')
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [json.loads(line) for line in hook_env[2].read_text().splitlines()]
    assert not any('lfs_refs' in row or row['tool'] == 'python' for row in rows)


def test_validation_failure_prevents_lfs_upload(hook_env):
    result = run_hook('pre-push', hook_env, refs=REFS,
                      extra={'FAIL_CHECK': 'scripts/ci/run_checks.py'},
                      args=('origin', 'local-fixture-remote'))
    assert result.returncode == 23
    rows = [json.loads(line) for line in hook_env[2].read_text().splitlines()]
    assert not any('lfs_refs' in row for row in rows)


def test_new_branch_checks_cumulative_range_and_keeps_rename_sources(hook_env):
    result = run_hook('pre-push', hook_env, refs=REFS, args=('origin', 'fixture'))
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [json.loads(line) for line in hook_env[2].read_text().splitlines()]
    diffs = [row['args'] for row in rows if row.get('tool') == 'git' and row['args'][:1] == ['diff']]
    assert diffs == [['diff', '--name-only', '--no-renames', 'b' * 40, 'a' * 40]]
