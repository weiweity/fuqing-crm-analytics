"""GitHub Actions 供应链与硬门禁回归测试。"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
USES_RE = re.compile(r"\buses:\s*([^\s#]+)")


def test_third_party_actions_are_pinned_to_full_commit_sha() -> None:
    """禁止 workflow 重新使用可移动的 ``@vN`` / branch tag。"""
    violations: list[str] = []

    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = USES_RE.search(line)
            if match is None:
                continue
            action = match.group(1)
            if action.startswith(("./", "docker://")):
                continue
            if "@" not in action:
                violations.append(f"{workflow.name}:{line_number}: missing @ref")
                continue
            ref = action.rsplit("@", 1)[1]
            if FULL_SHA_RE.fullmatch(ref) is None:
                violations.append(
                    f"{workflow.name}:{line_number}: mutable ref @{ref}"
                )

    assert violations == []


def test_security_and_build_jobs_are_hard_gates() -> None:
    """已稳定通过的审计、前端和 Docker job 不得静默放行。"""
    workflow = yaml.safe_load(
        (WORKFLOWS_DIR / "lint.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]

    for job_name in (
        "ground-truth-lint",
        "contract-filterbuilder-lint",
        "frontend",
        "dependency-audit",
        "docker-smoke",
        "b0-contract-build",
        "merge-gate",
    ):
        assert jobs[job_name].get("continue-on-error") is not True
    assert jobs["merge-gate"].get("if") == "always()"
    assert jobs["ground-truth-lint"]["if"] == "needs.changes.outputs.ground_truth == 'true'"
    assert jobs["contract-filterbuilder-lint"]["if"] == "needs.changes.outputs.filterbuilder == 'true'"

    ground_truth_steps = jobs["ground-truth-lint"]["steps"]
    ground_truth_run = next(
        step["run"]
        for step in ground_truth_steps
        if step.get("name", "").startswith("Ground truth lint")
    )
    assert "||" not in ground_truth_run

    dependency_steps = jobs["dependency-audit"]["steps"]
    install_audit = next(
        step["run"]
        for step in dependency_steps
        if step.get("name") == "Install Python deps for pip-audit"
    )
    assert "pip install pip-audit==2.10.1" in install_audit
    assert "\npip install pip-audit\n" not in f"\n{install_audit}\n"


def test_e2e_credentials_exist_before_backend_and_browser_login() -> None:
    workflow = yaml.safe_load(
        (WORKFLOWS_DIR / "e2e-smoke.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["e2e-smoke"]["steps"]
    names = [step.get("name", "") for step in steps]

    credentials_index = names.index("Generate ephemeral test credentials (masked)")
    backend_index = names.index("Build (Vite) + Start preview + uvicorn")
    browser_index = names.index("Run shell smoke (login only)")
    assert credentials_index < backend_index < browser_index

    setup_node_count = sum(
        str(step.get("uses", "")).startswith("actions/setup-node@")
        for step in steps
    )
    setup_python_count = sum(
        str(step.get("uses", "")).startswith("actions/setup-python@")
        for step in steps
    )
    assert setup_node_count == 1
    assert setup_python_count == 1


def test_docker_database_path_and_runtime_smoke_do_not_drift() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    entrypoint = (REPO_ROOT / "scripts" / "docker-entrypoint.sh").read_text(
        encoding="utf-8"
    )
    nginx = (REPO_ROOT / "frontend-vue3" / "nginx.conf").read_text(
        encoding="utf-8"
    )
    workflow = (WORKFLOWS_DIR / "lint.yml").read_text(encoding="utf-8")

    expected = "/app/data/processed/fuqing_crm.duckdb"
    assert f"ENV DUCKDB_PATH={expected}" in dockerfile
    assert f"DUCKDB_PATH={expected}" in compose
    assert "fuqing.duckdb" not in dockerfile
    assert "fuqing.duckdb" not in compose
    assert "docker run --detach" in workflow
    assert "scripts/ci/seed_e2e_duckdb.py" in workflow
    assert "/api/v1/health" in workflow
    assert '"127.0.0.1:8000:8001"' in compose
    assert '"127.0.0.1:5173:8080"' in compose
    assert "FORWARDED_ALLOW_IPS=127.0.0.1,172.16.0.0/12" in compose
    assert '--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"' in entrypoint
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in nginx
    assert "$proxy_add_x_forwarded_for" not in nginx
    assert 'docker network create "$SMOKE_NETWORK"' in workflow
    assert '--network-alias backend' in workflow
    assert "http://127.0.0.1:18080/api/v1/health" in workflow


def test_docker_runtime_smoke_keeps_both_containers_on_one_network() -> None:
    """nginx 必须能解析 backend，且 cleanup 只能在两容器验收后执行。"""
    workflow = yaml.safe_load(
        (WORKFLOWS_DIR / "lint.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["docker-smoke"]["steps"]
    runtime_step = next(
        step
        for step in steps
        if step.get("name") == "Run backend and frontend container smoke"
    )
    run = runtime_step["run"]

    assert run.count('--network "$SMOKE_NETWORK"') == 2
    assert "--network-alias backend" in run
    assert "trap cleanup EXIT" in run
    assert run.index("trap cleanup EXIT") < run.index("docker run --detach")
    assert run.index("fuqing-crm-backend:ci") < run.index("fuqing-crm-frontend:ci")
    assert run.index("http://127.0.0.1:18080/api/v1/health") < run.index(
        "Content-Security-Policy:"
    )


def test_ruff_install_reads_exactly_one_pin_and_never_installs_the_backend(monkeypatch, tmp_path):
    import subprocess
    import sys

    workflow = yaml.safe_load((WORKFLOWS_DIR / 'lint.yml').read_text())
    steps = workflow['jobs']['lint']['steps']
    install = next(step['run'] for step in steps if step.get('name') == 'Install only the locked Ruff version')
    source = install.split("python - <<'PYTHON'\n", 1)[1].rsplit('PYTHON', 1)[0]
    actual_lock = (REPO_ROOT / 'requirements-lock.txt').read_text()
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.chdir(tmp_path)
    lock = tmp_path / 'requirements-lock.txt'
    lock.write_text(actual_lock)
    exec(compile(source, 'workflow-ruff-install', 'exec'), {})
    pin = next(line for line in actual_lock.splitlines() if line.startswith('ruff=='))
    assert calls == [([sys.executable, '-m', 'pip', 'install', '--no-deps', pin], {'check': True})]
    for invalid in ('requests==2.0.0\n', 'ruff==0.16.6\nruff==0.15.15\n', 'ruff>=0.16.6\n'):
        lock.write_text(invalid)
        calls.clear()
        import pytest
        with pytest.raises(SystemExit):
            exec(compile(source, 'workflow-ruff-install', 'exec'), {})
        assert calls == []


def test_dependency_selection_survives_cli_and_reusable_workflow_outputs(tmp_path):
    import json
    import os
    import subprocess
    import sys

    shared = yaml.safe_load((WORKFLOWS_DIR / 'check-plan.yml').read_text())
    events = shared.get('on', shared.get(True))
    job = yaml.safe_load((WORKFLOWS_DIR / 'lint.yml').read_text())['jobs']['dependency-audit']
    for path, python_selected, frontend_selected in (
        ('frontend-vue3/package-lock.json', False, True),
        ('requirements-lock.txt', True, False),
        ('.github/workflows/lint.yml', True, True),
    ):
        output = tmp_path / 'github-output'
        output.write_text('')
        result = subprocess.run(
            [sys.executable, 'scripts/ci/pre_push_path_class.py', path, '--json', '--github-output'],
            cwd=REPO_ROOT, env={**os.environ, 'GITHUB_OUTPUT': str(output)},
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0, result.stderr
        flags = dict(line.split('=', 1) for line in output.read_text().splitlines())
        assert flags['dependencies'] == 'true'
        assert json.loads(flags['plan']) == json.loads(result.stdout)
        for axis, selected in (('python_dependencies', python_selected), ('frontend_dependencies', frontend_selected)):
            assert flags[axis] == str(selected).lower()
            assert shared['jobs']['changes']['outputs'][axis] == '${{ steps.plan.outputs.' + axis + ' }}'
            assert events['workflow_call']['outputs'][axis]['value'] == '${{ jobs.changes.outputs.' + axis + ' }}'
        selected_steps = []
        for step in job['steps']:
            condition = step.get('if')
            if condition:
                match = re.fullmatch(r"needs.changes.outputs.(python_dependencies|frontend_dependencies) == 'true'", condition)
                assert match, condition
                if flags[match[1]] != 'true':
                    continue
            selected_steps.append(step)
        runs = '\n'.join(step.get('run', '') for step in selected_steps)
        uses = '\n'.join(step.get('uses', '') for step in selected_steps)
        assert ('pip-audit -r' in runs) == python_selected
        assert ('actions/setup-python@' in uses) == python_selected
        assert ('npm audit' in runs) == frontend_selected
        assert ('actions/setup-node@' in uses) == frontend_selected
        assert ('npm ci' in runs) == frontend_selected


def test_ci_python_uses_deduplicated_runner_and_lint_remains_required():
    workflow = yaml.safe_load((WORKFLOWS_DIR / 'lint.yml').read_text())
    jobs = workflow['jobs']
    assert jobs['lint']['if'] == jobs['test']['if']
    assert 'lint' in jobs['merge-gate']['needs'] and 'test' in jobs['merge-gate']['needs']
    runs = '\n'.join(step.get('run', '') for step in jobs['test']['steps'])
    assert '--only ci-python' in runs
    assert '.githooks/check_imports.py' not in runs
    lint_runs = '\n'.join(step.get('run', '') for step in jobs['lint']['steps'])
    assert 'ruff check backend/' in lint_runs
    assert 'scripts/sync-agents.sh --check' in lint_runs
