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


def test_rfm_udf_contains_all_8_business_segments() -> None:
    sql = (ROOT / "scripts/postgresql16_udf/rfm_udf.sql").read_text(encoding="utf-8")
    expected = [segment.name_cn for segment in SEGMENTS if segment.segment_id <= 8]

    for name in expected:
        assert name in sql


def test_udf_files_are_postgresql_schema_scoped() -> None:
    for path in [
        ROOT / "scripts/postgresql16_udf/rfm_udf.sql",
        ROOT / "scripts/postgresql16_udf/r_interval_udf.sql",
    ]:
        sql = path.read_text(encoding="utf-8")
        assert "CREATE SCHEMA IF NOT EXISTS crm_semantic" in sql
        assert "CREATE OR REPLACE FUNCTION crm_semantic." in sql
