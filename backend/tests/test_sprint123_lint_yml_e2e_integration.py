"""Sprint 123 R2 CI 跑 e2e (Sprint 34 候选 4) 闭环: lint.yml e2e job 集成验证.

Sprint 123 立项决策: lint.yml 加 e2e job 替代 .github/workflows/e2e.yml 独立 (1 file workflow 4 jobs 替代 2 file workflow 4 jobs). 触发条件 = Sprint 95-96.5 7 sprint 链实战 fix 模式闭环后 e2e.yml 跑 4m29s success 5 次累计稳定 + Sprint 32.1 advisory OOM 18m+ 风险已闭环.

测试策略 (跟 Sprint 3 P1-3 破坏→验证→恢复 模式 一致):
- case 1: lint.yml 4 jobs (lint + ground-truth-lint + test + e2e) 验证
- case 2: e2e.yml 独立 workflow 已删 验证 (Sprint 123 真治本: 1 file workflow 4 jobs 替代 2 file workflow)
- case 3: e2e job 10 steps 完整 (跟原 e2e.yml 1:1 一致, 跟 Sprint 95-96.5 7 sprint 链实战 fix 模式 配套)
- case 4: e2e job 关键 env 5 个 (DUCKDB_PATH + HEALTH_API_KEY + FQ_CRM_PASSWORDS + ETL_MIN_DISK_GB + FQ_DB_MODE) 验证 (跟 Sprint 61 P2 fail-fast + Sprint 63 P0 lint.yml e2e env FQ_DB_MODE=schema_test 一致)

Branch: fix/sprint123-r2-ci-e2e-lint-yml-integration
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestSprint123LintYmlE2EIntegration:
    """Sprint 123 R2 CI 跑 e2e 集成验证 (破坏→验证→恢复 模式)."""

    def _load_workflow(self, relative_path: str) -> dict:
        """加载 + 解析 GH Actions workflow YAML."""
        import yaml
        workflow_path = ROOT / relative_path
        assert workflow_path.exists(), f"workflow {relative_path} 应存在, 实际不存在"
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_e2e_job_step_names_complete(self):
        """Case 3.5 (Sprint 123 必修 2 验证): e2e job step names 完整 (跟原 e2e.yml 1:1)."""
        workflow = self._load_workflow(".github/workflows/lint.yml")
        e2e_steps = workflow["jobs"]["e2e"]["steps"]
        # Sprint 123 必修 2: 验证 10 step names 完整 (跟原 e2e.yml 一致)
        expected_step_keywords = [
            "Install Python deps",
            "Install Node deps",
            "Install Playwright browsers",
            "Setup e2e DuckDB schema + seed",
            "Build (Vite) + Start preview server",
            "Run e2e with auto-recovery",
            "Upload auto-recovery log on failure",
        ]
        all_step_names = " ".join(s.get("name", "") for s in e2e_steps)
        for keyword in expected_step_keywords:
            assert keyword in all_step_names, (
                f"e2e step 应含 {keyword!r} (Sprint 123 必修 2 验证), 实际 step names: {all_step_names}"
            )

    def test_lint_yml_has_4_jobs(self):
        """Case 1: lint.yml 4 jobs (lint + ground-truth-lint + test + e2e) 验证.

        Sprint 123 集成前: lint.yml 3 jobs (lint + ground-truth-lint + test).
        Sprint 123 集成后: lint.yml 4 jobs (lint + ground-truth-lint + test + e2e).
        """
        workflow = self._load_workflow(".github/workflows/lint.yml")
        jobs = list(workflow["jobs"].keys())
        assert "lint" in jobs, f"lint job 应在, 实际 {jobs}"
        assert "ground-truth-lint" in jobs, f"ground-truth-lint job 应在, 实际 {jobs}"
        assert "test" in jobs, f"test job 应在, 实际 {jobs}"
        assert "e2e" in jobs, f"e2e job 应在 (Sprint 123 集成), 实际 {jobs}"
        assert len(jobs) == 4, f"4 jobs 验证 (Sprint 123 集成后), 实际 {len(jobs)} jobs: {jobs}"

    def test_e2e_yml_independent_deleted(self):
        """Case 2: .github/workflows/e2e.yml 已删 验证 (Sprint 123 真治本: 1 file workflow 4 jobs).

        Sprint 123 集成前: .github/workflows/e2e.yml 存在 (独立 workflow 1 job).
        Sprint 123 集成后: .github/workflows/e2e.yml 已删 (集成到 lint.yml, 1 file workflow 4 jobs).
        """
        e2e_yml = ROOT / ".github/workflows/e2e.yml"
        assert not e2e_yml.exists(), (
            ".github/workflows/e2e.yml 应已删 (Sprint 123 集成到 lint.yml), 实际仍存在"
        )

    def test_e2e_job_10_steps_complete(self):
        """Case 3: e2e job 10 steps 完整 (跟原 e2e.yml 1:1 一致).

        验证: Sprint 123 复制 e2e.yml 全部 10 steps 完整, 跟 Sprint 95-96.5 7 sprint 链实战 fix 模式 配套.
        步骤: checkout + setup-node + setup-python + Install Python deps + Install Node deps +
              Install Playwright browsers + Setup e2e DuckDB schema-only fixture (Sprint 60.3+ C+) +
              Build (Vite) + Start preview server + Start uvicorn backend +
              Run e2e with auto-recovery (Sprint 58 #4 wrapper) + Upload auto-recovery log on failure.
        """
        workflow = self._load_workflow(".github/workflows/lint.yml")
        e2e_job = workflow["jobs"]["e2e"]
        steps = e2e_job["steps"]
        assert len(steps) == 10, f"e2e job 应 10 steps, 实际 {len(steps)}"

        # 关键步骤名验证
        step_names = [s.get("name", "") for s in steps]
        assert "Install Python deps" in step_names, f"Install Python deps 应在, 实际 {step_names}"
        assert "Install Node deps" in step_names, f"Install Node deps 应在, 实际 {step_names}"
        assert "Install Playwright browsers" in step_names, f"Install Playwright browsers 应在, 实际 {step_names}"
        assert any("Setup e2e DuckDB schema" in n for n in step_names), (
            f"Setup e2e DuckDB schema(+seed) step 应在, 实际 {step_names}"
        )
        assert any("Build (Vite) + Start preview server" in n for n in step_names), (
            f"Build + preview server step 应在, 实际 {step_names}"
        )
        assert any("Run e2e with auto-recovery" in n for n in step_names), (
            f"Run e2e with auto-recovery 应在 (Sprint 58 #4 wrapper), 实际 {step_names}"
        )

    def test_e2e_job_env_5_keys(self):
        """Case 4: e2e job 关键 env 5 个 验证 (跟 Sprint 61 P2 fail-fast + Sprint 63 P0 一致).

        验证: env 5 keys (DUCKDB_PATH + HEALTH_API_KEY + FQ_CRM_PASSWORDS + ETL_MIN_DISK_GB + FQ_DB_MODE) 完整,
        跟 Sprint 61 P2 fail-fast 默认 production raise + Sprint 63 P0 lint.yml e2e env FQ_DB_MODE=schema_test
        走 warn 路径 一致.
        """
        workflow = self._load_workflow(".github/workflows/lint.yml")
        e2e_job = workflow["jobs"]["e2e"]
        env = e2e_job.get("env", {})

        required_env_keys = [
            "DUCKDB_PATH",
            "HEALTH_API_KEY",
            "FQ_CRM_PASSWORDS",
            "ETL_MIN_DISK_GB",
            "FQ_DB_MODE",
        ]
        for key in required_env_keys:
            assert key in env, f"e2e env {key} 应在, 实际 env keys: {list(env.keys())}"

        # 关键 env 值验证 (Sprint 63 P0 治根 FQ_DB_MODE=schema_test 走 warn 路径)
        assert env["FQ_DB_MODE"] == "schema_test", (
            f"FQ_DB_MODE 应 = 'schema_test' (Sprint 63 P0 治根 走 warn 路径), 实际 {env['FQ_DB_MODE']!r}"
        )
