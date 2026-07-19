"""
FQ_DB_MODE=schema_test 锁在可选 e2e-smoke（Sprint 66 治根 → 2026-07-19 门禁分层）.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_e2e_smoke_job_sets_fq_db_mode_schema_test():
    """e2e-smoke.yml 必须 FQ_DB_MODE=schema_test（防 fail-fast production raise）."""
    smoke = (ROOT / ".github" / "workflows" / "e2e-smoke.yml").read_text(
        encoding="utf-8"
    )
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test" for line in smoke.splitlines()
    ), (
        "e2e-smoke.yml 必须设 FQ_DB_MODE=schema_test. "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise."
    )


def test_pr_lint_yml_has_no_e2e_job_env_block():
    """PR lint.yml 不应再嵌入 e2e job 的 FQ_DB_MODE（e2e 已迁出）."""
    import yaml

    with open(ROOT / ".github" / "workflows" / "lint.yml", encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    assert "e2e" not in wf.get("jobs", {})
