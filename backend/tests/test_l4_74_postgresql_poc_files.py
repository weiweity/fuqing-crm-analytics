"""L4.74 PostgreSQL 16 POC file regression tests."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_single_node_compose_uses_postgresql16_and_isolated_port() -> None:
    text = (ROOT / "docker-compose-postgresql16-single-node.yml").read_text(encoding="utf-8")

    assert "image: postgres:16" in text
    assert '"5433:5432"' in text
    assert "postgresql16_single_data" in text


def test_citus_compose_has_three_workers() -> None:
    text = (ROOT / "docker-compose-postgresql16-citus-cluster.yml").read_text(encoding="utf-8")

    assert "citusdata/citus:" in text
    assert "pg16" in text
    assert text.count("citus-worker-1") >= 1
    assert text.count("citus-worker-2") >= 1
    assert text.count("citus-worker-3") >= 1
    assert "${CITUS_COORDINATOR_PORT:-5434}:5432" in text
    assert "condition: service_healthy" in text
    assert "FQ_CITUS_WORKERS" in text
    assert "citus_pg16_coordinator_data" in text
    assert "citus_pg16_worker_1_data" in text
    assert "010_resource_governance.sql" in text
    assert "data/processed/postgresql16_parquet" in text


def test_citus_init_registers_workers_and_resource_roles() -> None:
    init_sql = (ROOT / "scripts/postgresql16_citus_init/001_wait_and_register_workers.sh").read_text(encoding="utf-8")
    governance_sql = (ROOT / "scripts/postgresql16_citus_init/010_resource_governance.sql").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS citus" in init_sql
    assert "citus_add_node" in init_sql
    assert "crm_admin.distribute_if_exists" in init_sql
    assert "crm_interactive" in governance_sql
    assert "crm_batch" in governance_sql
    assert "crm_shadow_read" in governance_sql
    assert "crm_admin.resource_governance" in governance_sql


def test_l474_docs_exist() -> None:
    # L4.91 doc-cleanup (5985233) 后, docs/operations/citus-cluster-runbook.md / DOCKER-INSTALL-DEPLOY-MANUAL.md / docs/architecture/dual-write-* 都已归档到 docs/sprints/archive/ (跟 L4.91 plan-eng-review 缺陷 1+2 1:1 stable 永久规则化沿用)
    # RFM-high-concurrency-notice.md 跟 CLAUDE.md L4.72 永久规则化段重复, 已删除 (跟 L4.91 plan-eng-review 缺陷 1 1:1 stable 永久规则化沿用)
    required = [
        "docs/sprints/archive/citus-cluster-runbook.md",
        "docs/sprints/archive/dual-write-ux-design.md",
        "docs/sprints/archive/dual-write-strategy.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-1-REQUIREMENT-BASELINE.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-1-SELECTION-REPORT.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-2-BENCHMARK-REPORT.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-2-SQL-COMPATIBILITY.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-3-CLUSTER-BENCHMARK.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-5-POC-SUMMARY.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md",
        "docs/sprints/archive/SPRINT-L474-STAGE-5-RISK-ASSESSMENT-COST-ESTIMATE.md",
    ]

    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_l474_stage345_docs_lock_go_no_go_and_dual_write_contract() -> None:
    # L4.91 doc-cleanup (5985233) 后, dual-write-strategy.md 已归档到 docs/sprints/archive/
    cluster = (ROOT / "docs/sprints/archive/SPRINT-L474-STAGE-3-CLUSTER-BENCHMARK.md").read_text(encoding="utf-8")
    strategy = (ROOT / "docs/sprints/archive/dual-write-strategy.md").read_text(encoding="utf-8")
    decision = (ROOT / "docs/sprints/archive/SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md").read_text(encoding="utf-8")
    cost = (ROOT / "docs/sprints/archive/SPRINT-L474-STAGE-5-RISK-ASSESSMENT-COST-ESTIMATE.md").read_text(encoding="utf-8")

    assert "10 并发成功率" in cluster
    assert "duckdb_to_parquet_etl.py" in strategy
    assert "validate_dual_write_consistency.py" in strategy
    assert "Conditional Go" in decision
    assert "No-Go" in decision
    assert "人力估算" in cost
