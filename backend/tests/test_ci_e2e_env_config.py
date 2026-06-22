"""
Sprint 63 P1b 治根: e2e.yml 必须设 FQ_DB_MODE=schema_test

反向教训: Sprint 62.5 PR #28 CI 爆红 e2e 真正根因不是 DuckDB 117GB,
而是 Sprint 61 P2 fail-fast 默认 production raise, e2e schema-only
fixture 没 orders 数据 → uvicorn 60s 起不来.

治根: lint CI yml 文件强制 e2e job 含 FQ_DB_MODE=schema_test.

CI 留尾 ROI 重评 (CLAUDE.md L5.1): 治本 < 1 天闭环 + 0 复发 → 治本.
这个 lint 0.1d 闭环, 防下次 e2e.yml 改回忘了 env 又复发.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_e2e_workflow_sets_fq_db_mode_schema_test():
    """e2e.yml env 必须含 FQ_DB_MODE=schema_test (Sprint 63 P1b 治根).

    防再发: Sprint 62.5 PR #28 CI e2e 爆红真因是 Sprint 61 fail-fast 默认 raise.
    """
    e2e_yml = (ROOT / ".github" / "workflows" / "e2e.yml").read_text()
    # 用 strict 匹配 (整行), 防 substring 误报 (e.g. schema_test_FOO 误命中)
    assert any(
        line.strip() == "FQ_DB_MODE: schema_test"
        for line in e2e_yml.splitlines()
    ), (
        "e2e.yml env 必须设 FQ_DB_MODE=schema_test (Sprint 63 P1b 治根). "
        "缺这个 env 会导致 Sprint 61 fail-fast 默认 production raise, "
        "uvicorn 60s 起不来, e2e exit 1."
    )


def test_e2e_workflow_uses_60s_uvicorn_readiness_timeout():
    """e2e.yml uvicorn readiness 必须 ≥ 60s (Sprint 60+ L5.2 fail-fast 兼容).

    如果 < 60s, Sprint 61 fail-fast 路径下 uvicorn 还没 startup 完成就 timeout.
    """
    e2e_yml = (ROOT / ".github" / "workflows" / "e2e.yml").read_text()
    # strict match "{1..60}" 整段 (避免 "60}" OR 子句在 {2..60} 场景下误报).
    # Sprint 63 adversarial review 抓: OR 子句是 false-negative ({2..60} 含 60} 会 PASS).
    assert "{1..60}" in e2e_yml, (
        "e2e.yml uvicorn readiness 等待窗口必须 = 60s, 当前 < 60s 会跟 Sprint 61 fail-fast 冲突"
    )


def test_e2e_workflow_uses_schema_only_duckdb_fixture():
    """e2e.yml 必须用 /tmp/e2e_duckdb.duckdb schema-only fixture (Sprint 60.3+ C+).

    防再发: Sprint 60.3 之前 CI 试图 ATTACH 117GB 生产库 → 50+MB OOM 5+ sprint 复发.
    """
    e2e_yml = (ROOT / ".github" / "workflows" / "e2e.yml").read_text()
    assert "e2e_duckdb.duckdb" in e2e_yml, (
        "e2e.yml 必须用 /tmp/e2e_duckdb.duckdb schema-only fixture (Sprint 60.3+ C+ 治根)"
    )
    # 验证没误用 production path
    assert "data/processed/fuqing_crm.duckdb" not in e2e_yml, (
        "e2e.yml 不应引用 117GB production DB (Sprint 58 #1 OOM 治根: ATTACH read_only)"
    )
