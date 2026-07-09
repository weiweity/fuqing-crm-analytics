"""L4.74 PostgreSQL 16 UDF regression tests."""
from __future__ import annotations

from pathlib import Path

from backend.semantic.segments import R_INTERVALS, SEGMENTS


ROOT = Path(__file__).resolve().parents[2]


def test_r_interval_udf_matches_semantic_ssot() -> None:
    sql = (ROOT / "scripts/postgresql16_udf/r_interval_udf.sql").read_text(encoding="utf-8")

    for label, start, end in R_INTERVALS:
        assert label in sql
        if end < 99999:
            assert f"BETWEEN {start} AND {end}" in sql

    assert "WHEN last_pay_date IS NULL OR as_of_date IS NULL THEN NULL" in sql
    assert "WHEN as_of_date < last_pay_date THEN '近1个月已购客'" in sql


def test_rfm_udf_contains_all_8_business_segments() -> None:
    sql = (ROOT / "scripts/postgresql16_udf/rfm_udf.sql").read_text(encoding="utf-8")
    expected = [segment.name_cn for segment in SEGMENTS if segment.segment_id <= 8]

    for name in expected:
        assert name in sql

    assert "WHEN r_score IS NULL OR f_score IS NULL OR m_score IS NULL THEN '其他用户'" in sql
    assert "ELSE '其他用户'" in sql


def test_rfm_score_udfs_handle_nulls_and_boundary_days() -> None:
    sql = (ROOT / "scripts/postgresql16_udf/rfm_udf.sql").read_text(encoding="utf-8")

    assert "WHEN last_pay_date IS NULL OR as_of_date IS NULL THEN NULL" in sql
    assert "WHEN as_of_date - last_pay_date < 30 THEN 5" in sql
    assert "WHEN as_of_date - last_pay_date < 90 THEN 4" in sql
    assert "WHEN as_of_date - last_pay_date <= 30 THEN 5" not in sql
    assert "WHEN order_count IS NULL THEN NULL" in sql
    assert "WHEN gsv IS NULL THEN NULL" in sql


def test_udf_files_are_postgresql_schema_scoped() -> None:
    for path in [
        ROOT / "scripts/postgresql16_udf/rfm_udf.sql",
        ROOT / "scripts/postgresql16_udf/r_interval_udf.sql",
    ]:
        sql = path.read_text(encoding="utf-8")
        assert "CREATE SCHEMA IF NOT EXISTS crm_semantic" in sql
        assert "CREATE OR REPLACE FUNCTION crm_semantic." in sql
