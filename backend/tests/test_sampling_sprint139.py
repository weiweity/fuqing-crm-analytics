"""Sprint 139 派样人群正装转化漏斗回归测试."""

import pytest

from backend.services.sampling_service import get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSamplingROIPosizeConversion:
    """Task 1: 正装/非正装拆分."""

    def test_summary_contains_posize_fields_and_gsv_partition(self, monkeypatch_connection):
        """正装 GSV + 非正装 GSV 应覆盖所选窗口任意回购 GSV."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )

        assert result["summary"]["channels"]
        for ch in result["summary"]["channels"]:
            for key in (
                "full_repurchase_users",
                "full_repurchase_gsv",
                "full_repurchase_aus",
                "nonfull_repurchase_users",
                "nonfull_repurchase_gsv",
                "nonfull_repurchase_aus",
                "full_repurchase_rate",
            ):
                assert key in ch

            split_gsv = ch["full_repurchase_gsv"] + ch["nonfull_repurchase_gsv"]
            assert abs(split_gsv - ch["repurchase_gsv"]) <= 0.05

    def test_category_rows_contain_posize_fields(self, monkeypatch_connection):
        """品类明细行包含正装回购人/GSV/AUS 字段."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )

        assert result["category_breakdown"]
        for row in result["category_breakdown"][:10]:
            for key in (
                "full_repurchase_users",
                "full_repurchase_rate",
                "full_repurchase_gsv",
                "full_repurchase_aus",
                "nonfull_repurchase_users",
                "nonfull_repurchase_gsv",
                "nonfull_repurchase_aus",
            ):
                assert key in row


class TestSamplingROIPeriodDistribution:
    """Task 2: 回购周期分布."""

    def test_period_distribution_buckets_are_ints(self, monkeypatch_connection):
        """周期分布 4 桶 + 正装 4 桶均返回 int."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=60,
            level="spu_category",
        )
        period_distribution = result["period_distribution"]

        for key in (
            "bucket_1_3d",
            "bucket_4_7d",
            "bucket_8_30d",
            "bucket_31_60d",
            "full_bucket_1_3d",
            "full_bucket_4_7d",
            "full_bucket_8_30d",
            "full_bucket_31_60d",
        ):
            assert isinstance(period_distribution[key], int)

    def test_full_buckets_do_not_exceed_total_buckets(self, monkeypatch_connection):
        """每个周期桶内，正装用户数不应超过任意回购用户数."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=60,
            level="spu_category",
        )
        period_distribution = result["period_distribution"]

        assert period_distribution["full_bucket_1_3d"] <= period_distribution["bucket_1_3d"]
        assert period_distribution["full_bucket_4_7d"] <= period_distribution["bucket_4_7d"]
        assert period_distribution["full_bucket_8_30d"] <= period_distribution["bucket_8_30d"]
        assert period_distribution["full_bucket_31_60d"] <= period_distribution["bucket_31_60d"]


class TestSamplingROIDataQualityGuard:
    """Task 3: DQM warnings."""

    def test_quality_flags_structure(self, monkeypatch_connection):
        """quality_flags 始终是 list，触发时包含 code/severity/message."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )
        flags = result.get("quality_flags", [])

        assert isinstance(flags, list)
        for flag in flags:
            assert "code" in flag
            assert "severity" in flag
            assert "message" in flag
            assert flag["severity"] in ("warning", "error")
