from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from scripts.synthetic.generate_hackathon_dataset import (
    generate_dataset,
    validate_synthetic_database,
)


TEST_ANALYSIS_DATE = date(2026, 8, 31)


def _generate(path: Path, *, seed: int = 20260904) -> dict:
    return generate_dataset(
        path,
        seed=seed,
        analysis_as_of_date=TEST_ANALYSIS_DATE,
        n_users=120,
        n_orders=420,
    )


def test_generator_creates_valid_synthetic_only_dataset(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.duckdb"
    manifest = _generate(db_path)

    assert db_path.exists()
    assert db_path.with_suffix(".manifest.json").exists()
    assert manifest["data_profile"] == "synthetic"
    assert manifest["contains_real_data"] is False
    assert manifest["source"] == "generated_from_code_only"
    assert manifest["validation"]["row_counts"]["synthetic_users"] == 120
    assert manifest["validation"]["row_counts"]["synthetic_orders"] == 420
    assert manifest["validation"]["multi_channel_users"] > 0
    assert manifest["semantic_views"] == [
        "sem_customer_origin",
        "sem_customer_lifecycle_snapshot",
        "sem_channel_customer_quality",
    ]
    assert manifest["manifest_sha256"].startswith("sha256:")
    assert len(manifest["manifest_sha256"]) == 71


def test_same_seed_produces_same_business_content_hash(tmp_path: Path) -> None:
    first_path = tmp_path / "first.duckdb"
    second_path = tmp_path / "second.duckdb"
    different_path = tmp_path / "different.duckdb"
    first = _generate(first_path)
    second = _generate(second_path)
    different = _generate(different_path, seed=20260905)

    assert first["dataset_content_sha256"] == second["dataset_content_sha256"]
    assert first["dataset_content_sha256"] != different["dataset_content_sha256"]
    assert first["id_namespace"] == second["id_namespace"]
    assert first["id_namespace"] != different["id_namespace"]

    def user_ids(path: Path) -> list[str]:
        conn = duckdb.connect(str(path), read_only=True)
        try:
            return [
                row[0]
                for row in conn.execute(
                    "SELECT synthetic_user_id FROM synthetic_users ORDER BY 1"
                ).fetchall()
            ]
        finally:
            conn.close()

    assert user_ids(first_path) == user_ids(second_path)
    assert set(user_ids(first_path)).isdisjoint(user_ids(different_path))


def test_stable_user_id_links_relationship_and_cross_channel_orders(tmp_path: Path) -> None:
    db_path = tmp_path / "linked.duckdb"
    _generate(db_path)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        orphan_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM synthetic_orders orders
            LEFT JOIN synthetic_relationship_events events USING (synthetic_user_id)
            WHERE events.synthetic_user_id IS NULL
            """
        ).fetchone()[0]
        linked_cross_channel_count = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT synthetic_user_id
                FROM synthetic_orders
                GROUP BY synthetic_user_id
                HAVING COUNT(DISTINCT channel) > 1
            )
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert orphan_count == 0
    assert linked_cross_channel_count > 0


def test_synthetic_scenario_preserves_relationship_and_channel_quality_contrast(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scenario.duckdb"
    generate_dataset(
        db_path,
        seed=20260904,
        analysis_as_of_date=TEST_ANALYSIS_DATE,
        n_users=600,
        n_orders=2_100,
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sample_relationships = conn.execute(
            """
            SELECT COUNT(*) FROM synthetic_relationship_events WHERE channel = '小样'
            """
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT
                first_paid_channel,
                cohort_customers,
                second_paid_rate_30d,
                avg_net_value_180d
            FROM sem_channel_customer_quality
            """
        ).fetchall()
        sample_to_paid = conn.execute(
            """
            SELECT COUNT(*)
            FROM sem_customer_origin
            WHERE first_relationship_channel = '小样'
              AND first_paid_channel IN ('货架', '直播', '淘客')
            """
        ).fetchone()[0]
        lifecycle_counts = conn.execute(
            """
            SELECT lifecycle_stage, COUNT(*)
            FROM sem_customer_lifecycle_snapshot
            GROUP BY lifecycle_stage
            """
        ).fetchall()
    finally:
        conn.close()

    channel_metrics = {
        channel: {
            "cohort_customers": int(cohort_customers),
            "second_paid_rate_30d": float(second_paid_rate_30d),
            "avg_net_value_180d": float(avg_net_value_180d),
        }
        for channel, cohort_customers, second_paid_rate_30d, avg_net_value_180d in rows
    }
    assert sample_relationships > 0
    assert sample_to_paid == sample_relationships
    assert set(channel_metrics) == {"货架", "直播", "淘客"}
    assert channel_metrics["直播"]["cohort_customers"] > channel_metrics["货架"][
        "cohort_customers"
    ]
    assert (
        channel_metrics["货架"]["second_paid_rate_30d"]
        > channel_metrics["直播"]["second_paid_rate_30d"]
        > channel_metrics["淘客"]["second_paid_rate_30d"]
    )
    assert (
        channel_metrics["货架"]["avg_net_value_180d"]
        > channel_metrics["直播"]["avg_net_value_180d"]
        > channel_metrics["淘客"]["avg_net_value_180d"]
    )
    assert {stage for stage, _ in lifecycle_counts} == {
        "NEW",
        "ACTIVE",
        "REPLENISHMENT_DUE",
        "DORMANT",
        "CHURNED",
    }


def test_validator_rejects_pii_like_text(tmp_path: Path) -> None:
    db_path = tmp_path / "pii.duckdb"
    _generate(db_path)
    synthetic_phone = "138" + "0" * 8
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE synthetic_products SET generic_product_name = ? WHERE product_code = ?",
            [f"联系 {synthetic_phone}", "SYN-P-001"],
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="PII-like text"):
        validate_synthetic_database(db_path)


def test_generator_refuses_silent_overwrite(tmp_path: Path) -> None:
    db_path = tmp_path / "existing.duckdb"
    _generate(db_path)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        _generate(db_path)
