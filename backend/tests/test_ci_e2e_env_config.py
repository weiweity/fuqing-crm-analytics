"""
e2e smoke 环境配置契约 (Sprint 63 治根 → 2026-07-19 迁到 e2e-smoke.yml).

PR 默认 lint.yml 不再含 e2e；schema_test / seed / TEST_MODE 锁在可选 smoke workflow。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SMOKE_YML = ROOT / ".github" / "workflows" / "e2e-smoke.yml"
LINT_YML = ROOT / ".github" / "workflows" / "lint.yml"


def test_e2e_smoke_sets_fq_db_mode_schema_test():
    """e2e-smoke.yml env 必须含 FQ_DB_MODE=schema_test."""
    text = SMOKE_YML.read_text(encoding="utf-8")
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test" for line in text.splitlines()
    ), "e2e-smoke.yml 必须设 FQ_DB_MODE=schema_test"


def test_e2e_smoke_uses_60s_uvicorn_readiness_timeout():
    """uvicorn readiness 等待窗口 = 60s."""
    text = SMOKE_YML.read_text(encoding="utf-8")
    assert "{1..60}" in text, "e2e-smoke uvicorn readiness 必须 = 60s"


def test_e2e_smoke_uses_schema_seed_duckdb_fixture():
    """必须用 /tmp/e2e_duckdb.duckdb + seed 脚本，禁止生产库路径."""
    text = SMOKE_YML.read_text(encoding="utf-8")
    assert "e2e_duckdb.duckdb" in text
    assert "seed_e2e_duckdb.py" in text
    assert "data/processed/fuqing_crm.duckdb" not in text


def test_e2e_smoke_sets_fq_crm_test_mode():
    """必须 FQ_CRM_TEST_MODE=1（L4.85 + /_test/reset）."""
    text = SMOKE_YML.read_text(encoding="utf-8")
    assert any(
        "FQ_CRM_TEST_MODE" in line and "1" in line for line in text.splitlines()
    ), "e2e-smoke.yml 必须设 FQ_CRM_TEST_MODE=1"


def test_pr_lint_yml_has_no_e2e_fixture_paths():
    """回归: lint.yml 不得再挂 e2e seed / playwright 全量路径."""
    text = LINT_YML.read_text(encoding="utf-8")
    assert "seed_e2e_duckdb.py" not in text
    assert "playwright test" not in text
