"""CI e2e 布局契约 (Sprint 123 集成史 → 2026-07-19 门禁分层).

历史: Sprint 123 曾把 e2e 并进 lint.yml。
现行: PR CI (lint.yml) 仅 lint + ground-truth-lint + test；
      可选壳层 smoke 在 e2e-smoke.yml（不挡 merge）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint123LintYmlE2EIntegration:
    """现行门禁布局（取代「lint.yml 必有 e2e job」旧断言）."""

    def _load_workflow(self, relative_path: str) -> dict:
        import yaml

        workflow_path = ROOT / relative_path
        assert workflow_path.exists(), f"workflow {relative_path} 应存在, 实际不存在"
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_lint_yml_pr_jobs_without_e2e(self):
        """PR/main lint.yml = 3 jobs，无 e2e。"""
        workflow = self._load_workflow(".github/workflows/lint.yml")
        jobs = list(workflow["jobs"].keys())
        assert "lint" in jobs
        assert "ground-truth-lint" in jobs
        assert "test" in jobs
        assert "e2e" not in jobs, f"PR CI 不得含 e2e job, 实际 {jobs}"
        assert len(jobs) == 3, f"期望 3 jobs, 实际 {jobs}"

    def test_e2e_yml_independent_deleted(self):
        """旧独立 e2e.yml 仍不存在（能力迁到 e2e-smoke.yml）。"""
        e2e_yml = ROOT / ".github/workflows/e2e.yml"
        assert not e2e_yml.exists(), (
            ".github/workflows/e2e.yml 应不存在; 可选 smoke 见 e2e-smoke.yml"
        )

    def test_optional_smoke_workflow_exists(self):
        """e2e-smoke.yml 存在且可手动/定时触发。"""
        smoke = ROOT / ".github/workflows/e2e-smoke.yml"
        assert smoke.is_file()
        workflow = self._load_workflow(".github/workflows/e2e-smoke.yml")
        jobs = workflow["jobs"]
        assert "e2e-smoke" in jobs
        env = jobs["e2e-smoke"].get("env", {})
        for key in (
            "DUCKDB_PATH",
            "HEALTH_API_KEY",
            "FQ_CRM_PASSWORDS",
            "ETL_MIN_DISK_GB",
            "FQ_DB_MODE",
            "FQ_CRM_TEST_MODE",
        ):
            assert key in env, f"smoke env 缺 {key}, 有 {list(env.keys())}"
        assert env["FQ_DB_MODE"] == "schema_test"

    def test_smoke_step_names_shell_path(self):
        """smoke steps 含最小依赖安装 + login-only 跑法。"""
        workflow = self._load_workflow(".github/workflows/e2e-smoke.yml")
        steps = workflow["jobs"]["e2e-smoke"]["steps"]
        all_names = " ".join(s.get("name", "") for s in steps)
        assert "Install Python deps" in all_names
        assert "Install Node deps" in all_names
        assert "Install Playwright browsers" in all_names
        assert "Setup e2e DuckDB" in all_names
        assert "Build (Vite)" in all_names or "preview" in all_names.lower()
        assert "shell smoke" in all_names.lower() or "login" in all_names.lower()
