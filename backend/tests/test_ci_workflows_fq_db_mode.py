"""
Sprint 66 P0 治根: lint.yml e2e job 必须设 FQ_DB_MODE=schema_test

反向教训: Sprint 63 P1b 只改了 .github/workflows/e2e.yml (独立 e2e workflow),
但 CI workflow 的 e2e job 在 .github/workflows/lint.yml line 67 也需要 FQ_DB_MODE=schema_test.
Sprint 64+65 CI test+e2e 双 FAILURE 5+sprint 复发.

治根: lint CI yml 文件强制 e2e job 含 FQ_DB_MODE=schema_test.

CI 留尾 ROI 重评 (CLAUDE.md L5.1): 治本 < 1 天闭环 + 0 复发 → 治本.
这个 lint 0.1d 闭环, 防下次 lint.yml 改回忘了 env 又复发.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_lint_yml_e2e_job_sets_fq_db_mode_schema_test():
    """lint.yml e2e job env 必须含 FQ_DB_MODE=schema_test (Sprint 66 P0 治根).

    防再发: Sprint 63 P1b 只改独立 e2e workflow, CI workflow e2e job 漏 → 5+sprint 双 FAILURE.
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    # strict match 整行 (防 substring 误报, Sprint 63 review 抓的 same bug)
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test"
        for line in lint_yml.splitlines()
    ), (
        "lint.yml env 必须设 FQ_DB_MODE=schema_test (Sprint 66 P0 治根). "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise, "
        "uvicorn 60s 起不来, e2e exit 1."
    )


def test_lint_yml_e2e_job_uses_schema_only_duckdb_fixture():
    """lint.yml e2e 必须用 /tmp/e2e_duckdb.duckdb schema-only fixture (Sprint 60.3+ C+).

    防再发: Sprint 60.3 之前 CI 试图 ATTACH 117GB 生产库 → 50+MB OOM 5+ sprint 复发.
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    assert "e2e_duckdb.duckdb" in lint_yml, (
        "lint.yml e2e 必须用 /tmp/e2e_duckdb.duckdb schema-only fixture (Sprint 60.3+ C+ 治根)"
    )
    # 验证没误用 production path
    assert "data/processed/fuqing_crm.duckdb" not in lint_yml, (
        "lint.yml 不应引用 117GB production DB (Sprint 58 #1 OOM 治根: ATTACH read_only)"
    )


def test_e2e_yml_e2e_job_sets_fq_db_mode_schema_test():
    """e2e.yml (独立 e2e workflow) env 必须含 FQ_DB_MODE=schema_test (Sprint 63 P1b).

    防再发: Sprint 63 P1b 修了独立 e2e workflow 但漏 CI workflow 的 e2e job (在 lint.yml).
    """
    e2e_yml = (ROOT / ".github" / "workflows" / "e2e.yml").read_text()
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test"
        for line in e2e_yml.splitlines()
    ), (
        "e2e.yml env 必须设 FQ_DB_MODE=schema_test (Sprint 63 P1b 治根). "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise, "
        "uvicorn 60s 起不来, e2e exit 1."
    )