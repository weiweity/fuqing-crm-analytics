"""
Sprint 63 P1b 治根: e2e job (lint.yml 集成, 修前是 e2e.yml 独立) 必须设 FQ_DB_MODE=schema_test

反向教训: Sprint 62.5 PR #28 CI 爆红 e2e 真正根因不是 DuckDB 117GB,
而是 Sprint 61 P2 fail-fast 默认 production raise, e2e schema-only
fixture 没 orders 数据 → uvicorn 60s 起不来.

治根: lint CI yml 文件强制 e2e job 含 FQ_DB_MODE=schema_test.

Sprint 123 R2 CI 跑 e2e (Sprint 34 候选 4) 集成: e2e.yml 删, e2e job 移到 lint.yml.
Sprint 123 必修 2 真因真修: test 改读 lint.yml, 验证 e2e job 仍含 3 项 env 关键配置.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_e2e_workflow_sets_fq_db_mode_schema_test():
    """lint.yml e2e job env 必须含 FQ_DB_MODE=schema_test (Sprint 63 P1b 治根 + Sprint 123 集成).

    Sprint 123 集成后: e2e.yml 删, e2e job 移到 lint.yml. test 改读 lint.yml.
    防再发: Sprint 62.5 PR #28 CI e2e 爆红真因是 Sprint 61 fail-fast 默认 raise.
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    # 用 strict 匹配 (整行), 防 substring 误报 (e.g. schema_test_FOO 误命中)
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test"
        for line in lint_yml.splitlines()
    ), (
        "lint.yml e2e job env 必须设 FQ_DB_MODE=schema_test (Sprint 63 P1b 治根 + Sprint 123 集成). "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise, "
        "uvicorn 60s 起不来, e2e exit 1."
    )


def test_e2e_workflow_uses_60s_uvicorn_readiness_timeout():
    """lint.yml e2e job uvicorn readiness 必须 ≥ 60s (Sprint 60+ L5.2 fail-fast 兼容 + Sprint 123 集成).

    如果 < 60s, Sprint 61 fail-fast 路径下 uvicorn 还没 startup 完成就 timeout.
    Sprint 123 集成后: e2e.yml 删, e2e job 移到 lint.yml. test 改读 lint.yml.
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    # strict match "{1..60}" 整段 (避免 "60}" OR 子句在 {2..60} 场景下误报).
    # Sprint 63 adversarial review 抓: OR 子句是 false-negative ({2..60} 含 60} 会 PASS).
    assert "{1..60}" in lint_yml, (
        "lint.yml e2e job uvicorn readiness 等待窗口必须 = 60s, 当前 < 60s 会跟 Sprint 61 fail-fast 冲突"
    )


def test_e2e_workflow_uses_schema_only_duckdb_fixture():
    """lint.yml e2e job 必须用 /tmp/e2e_duckdb.duckdb（schema+seed，非生产库）.

    防再发: Sprint 60.3 之前 CI 试图 ATTACH 117GB 生产库 → 50+MB OOM 5+ sprint 复发.
    2026-07-19 根治: seed_e2e_duckdb.py 写最小业务 seed，仍禁止 production path.
    """
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    assert "e2e_duckdb.duckdb" in lint_yml, (
        "lint.yml e2e job 必须用 /tmp/e2e_duckdb.duckdb fixture (Sprint 60.3+ C+ 治根 + Sprint 123 集成)"
    )
    assert "seed_e2e_duckdb.py" in lint_yml, (
        "lint.yml e2e job 必须用 scripts/ci/seed_e2e_duckdb.py（e2e 根治 2026-07-19）"
    )
    # 验证没误用 production path
    assert "data/processed/fuqing_crm.duckdb" not in lint_yml, (
        "lint.yml e2e job 不应引用 117GB production DB (Sprint 58 #1 OOM 治根: ATTACH read_only)"
    )


def test_e2e_workflow_sets_fq_crm_test_mode():
    """lint.yml e2e job 必须 FQ_CRM_TEST_MODE=1（L4.85 会话隔离 + /_test/reset 白名单）."""
    lint_yml = (ROOT / ".github" / "workflows" / "lint.yml").read_text()
    assert any(
        "FQ_CRM_TEST_MODE" in line and "1" in line for line in lint_yml.splitlines()
    ), "lint.yml e2e job 必须设 FQ_CRM_TEST_MODE=1"
