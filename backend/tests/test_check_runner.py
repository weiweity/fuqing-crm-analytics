"""Check selection, process boundaries and evidence without real Git/network."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.ci.pre_push_path_class import TOOL_TESTS, verification_plan
from scripts.ci.run_checks import ROOT, commands, execute, preflight
from scripts.ci.summarize_checks import summarize
from scripts import run_backend_tests_bounded as bounded


@pytest.mark.parametrize('paths,backend,b0,frontend,tooling', [
    (['docs/a.md'], 'none', False, False, False),
    (['AGENTS.md'], 'none', False, False, True),
    (['dsh-plugins/analytics-workbench/src/tool.ts'], 'none', True, False, False),
    (['backend/services/analytics/context.py'], 'none', True, False, False),
    (['scripts/dsh-b0/pipeline.mjs'], 'none', True, False, False),
    (['frontend-vue3/src/views/Any.vue'], 'none', False, True, False),
    (['backend/services/churn.py'], 'full', False, False, False),
    (['backend/tests/test_example.py'], 'scoped', False, False, False),
    (['backend/tests/conftest.py'], 'full', False, False, True),
    (['backend/tests/helpers.py'], 'full', False, False, False),
    (['.githooks/pre-push'], 'none', False, False, True),
    (['scripts/etl/cli.py'], 'full', False, False, False),
    (['backend/routers/auth.py', 'dsh-plugins/analytics-workbench/src/a.ts',
      'frontend-vue3/src/views/X.vue'], 'full', True, True, False),
    ([], 'full', False, False, True),
])
def test_matrix_covers_independent_and_mixed_axes(paths, backend, b0, frontend, tooling):
    p = verification_plan(paths)
    assert (p['backend'], p['b0'], p['frontend'], p['tooling']) == (backend, b0, frontend, tooling)


def test_deleted_test_expands_without_dropping_new_name(tmp_path):
    p = verification_plan(['backend/tests/test_deleted.py', 'backend/tests/test_renamed.py'])
    steps = commands(p, tmp_path)
    pytest_step = next(args for _, args, _ in steps if 'scripts/run_backend_tests_bounded.py' in args)
    assert pytest_step == [sys.executable, 'scripts/run_backend_tests_bounded.py']


def test_tool_targets_exist_and_full_plan_does_not_duplicate_them():
    assert all((ROOT / p).is_file() for p in TOOL_TESTS)
    full = commands(verification_plan(['backend/tests/conftest.py']))
    assert not any('pytest' in args for _, args, _ in full)
    tooling = commands(verification_plan(['.githooks/pre-push']))
    assert any('pytest' in args and '--noconftest' in args for _, args, _ in tooling)


def test_failure_stops_next_check():
    seen = []
    def fail(args, **kwargs):
        seen.append(args)
        return SimpleNamespace(returncode=31)
    assert execute([('tooling', ['first'], ROOT), ('b0', ['second'], ROOT)], fail) == 31
    assert seen == [['first']]


def test_runner_environment_does_not_forward_credentials_or_git_state(monkeypatch, tmp_path):
    monkeypatch.setenv('FQ_CRM_PASSWORDS', 'sensitive-do-not-forward')
    monkeypatch.setenv('OPENAI_API_KEY', 'not-a-real-key')
    monkeypatch.setenv('GIT_DIR', '/unrelated/repository')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--deselect=everything')
    monkeypatch.setenv('DUCKDB_PATH', '/unrelated/archive.duckdb')
    env = bounded.isolated_env(tmp_path)
    assert not {'OPENAI_API_KEY', 'GIT_DIR', 'PYTEST_ADDOPTS', 'DUCKDB_PATH'} & env.keys()
    assert env['FQ_CRM_PASSWORDS'] == 'admin:123456,fqsw:fqsw888,testuser:testpass123'
    assert Path(env['HOME']).parent == tmp_path
    assert env['PYTHON_DOTENV_DISABLED'] == '1'


def test_runner_keeps_c_class_ssot_and_explicit_slow_exclusion(tmp_path):
    args = bounded.pytest_args(['backend/tests/test_check_runner.py'], tmp_path / 'group.xml')
    assert args.count('--deselect') == 7
    assert args[args.index('-m', args.index('pytest')) + 1] == 'not slow'
    assert 'no:xdist' in args


def test_runner_executes_without_optional_xdist_plugin(tmp_path):
    sample = tmp_path / 'test_serial_sample.py'
    sample.write_text('def test_serial():\n    assert 2 + 2 == 4\n')
    env = bounded.isolated_env(tmp_path)
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    command = bounded.pytest_args([str(sample)], tmp_path / 'sample.xml')
    result = subprocess.run([*command, '--noconftest'], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed' in result.stdout


def test_runner_terminates_only_its_child_on_resource_limit(monkeypatch, tmp_path):
    class Child:
        pid = 999999
        returncode = None
        def poll(self):
            return self.returncode
    child = Child()
    stopped = []
    monkeypatch.setattr(bounded, 'source_identity', lambda: {'head': 'fixture'})
    monkeypatch.setattr(bounded.subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(bounded, '_rss_tree_bytes', lambda pid: 2 * 1024**3)
    def stop(process):
        stopped.append(process)
        process.returncode = -15
    monkeypatch.setattr(bounded, '_stop_process_tree', stop)
    report = tmp_path / 'report'
    assert bounded.run(25, 1, ['backend/tests/test_check_runner.py'], report, 30) == 90
    assert stopped == [child]
    saved = json.loads((report / 'summary.json').read_text())
    assert saved['returncode'] == 90 and saved['groups'][0]['peak_rss_bytes'] == 2 * 1024**3


def test_junit_summary_reads_children_and_records_partial_failure(tmp_path):
    (tmp_path / 'group-001.xml').write_text('<testsuites><testsuite tests="4" failures="1" errors="0" skipped="1" time="2.5"/></testsuites>')
    (tmp_path / 'summary.json').write_text('{"returncode": 1}')
    assert summarize(tmp_path) == {'tests': 4, 'failures': 1, 'errors': 0, 'skipped': 1,
                                   'time': 2.5, 'groups_with_junit': 1, 'runner_returncode': 1}


def test_plan_cli_does_not_execute_checks():
    result = subprocess.run([sys.executable, 'scripts/ci/run_checks.py', '--files-from', '-', '--plan-only'],
                            cwd=ROOT, input='backend/services/churn.py\n', text=True,
                            capture_output=True, timeout=5)
    assert result.returncode == 0 and json.loads(result.stdout)['backend'] == 'full'


def test_b0_pipeline_lists_query_native_fault():
    text = (ROOT / 'scripts/dsh-b0/pipeline.mjs').read_text()
    assert 'query_native_fault' in text


def test_ci_reuses_local_matrix_and_owns_profile_exclusions():
    import yaml
    workflows = ROOT / '.github/workflows'
    shared = yaml.safe_load((workflows / 'check-plan.yml').read_text())
    assert 'scripts/ci/pre_push_path_class.py' in shared['jobs']['changes']['steps'][-1]['run']
    data = yaml.safe_load((workflows / 'lint.yml').read_text())
    assert data['jobs']['changes']['uses'] == './.github/workflows/check-plan.yml'
    assert 'b0-contract-build' in data['jobs']
    assert 'merge-gate' in data['jobs']
    dispatch = yaml.safe_load((workflows / 'dsh-b0.yml').read_text())
    assert 'changes' not in dispatch['jobs']
    assert 'pull_request' not in (dispatch.get('on') or dispatch.get(True) or {})
    for name in ('nightly.yml', 'weekly-report.yml'):
        text = (workflows / name).read_text()
        assert 'scripts/run_backend_tests_bounded.py' in text
        assert 'pytest backend/tests/' not in text
        assert 'pytest_deselect_args.sh' not in text
    text = (workflows / 'lint.yml').read_text()
    assert 'scripts/ci/run_checks.py' in text and '--only python' in text and '--only frontend' in text


def test_node_mismatch_fails_before_any_expensive_check():
    called = []
    def wrong_node(args, **kwargs):
        called.append(args)
        return SimpleNamespace(returncode=0, stdout='v25.8.2')
    assert preflight(verification_plan(['backend/main.py', 'dsh-plugins/analytics-workbench/src/tool.ts']), None, wrong_node) == 2
    assert called == [['node', '--version']]
    assert preflight(verification_plan(['backend/main.py']), None, wrong_node) == 0
    assert len(called) == 1


def test_code_renamed_to_docs_keeps_the_removed_code_check():
    # Hook/CI diff --no-renames supplies both names, preventing a docs-only skip.
    plan = verification_plan(['backend/services/old.py', 'docs/history/old.py'])
    assert plan['backend'] == 'full'
    assert '--no-renames' in (ROOT / '.github/workflows/check-plan.yml').read_text()
