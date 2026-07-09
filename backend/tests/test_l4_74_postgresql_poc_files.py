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

    assert text.count("citus-worker-1") >= 1
    assert text.count("citus-worker-2") >= 1
    assert text.count("citus-worker-3") >= 1
    assert "5434:5432" in text


def test_l474_docs_exist() -> None:
    required = [
        "docs/operations/RFM-high-concurrency-notice.md",
        "docs/operations/citus-cluster-runbook.md",
        "docs/architecture/dual-write-ux-design.md",
        "docs/architecture/dual-write-strategy.md",
        "docs/sprints/SPRINT-L474-STAGE-1-REQUIREMENT-BASELINE.md",
        "docs/sprints/SPRINT-L474-STAGE-1-SELECTION-REPORT.md",
        "docs/sprints/SPRINT-L474-STAGE-2-BENCHMARK-REPORT.md",
        "docs/sprints/SPRINT-L474-STAGE-2-SQL-COMPATIBILITY.md",
        "docs/sprints/SPRINT-L474-STAGE-3-CLUSTER-BENCHMARK.md",
        "docs/sprints/SPRINT-L474-STAGE-5-POC-SUMMARY.md",
        "docs/sprints/SPRINT-L474-STAGE-5-GO-NO-GO-DECISION.md",
        "docs/sprints/SPRINT-L474-STAGE-5-RISK-ASSESSMENT-COST-ESTIMATE.md",
    ]

    for rel in required:
        assert (ROOT / rel).exists(), rel
