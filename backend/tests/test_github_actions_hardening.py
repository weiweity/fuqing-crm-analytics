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
    ):
        assert jobs[job_name].get("continue-on-error") is not True

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
