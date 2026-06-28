"""Sprint 140 派样 ROI 自由窗口 + level 联动回归测试."""

import pytest

from backend.services.sampling_service import get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSamplingROIWindowFlexibility:
    """Task 1-2: 任意 window_days 都返回 1 套统一字段."""

    @pytest.mark.parametrize("window_days", [7, 14, 30, 60, 90])
    def test_unified_fields_present_for_any_window(self, monkeypatch_connection, window_days):
        """任意 window_days 都返回统一字段."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=window_days,
            level="spu_category",
        )

        assert result["summary"]["channels"]
        assert result["time_range"]["window_days"] == window_days
        for ch in result["summary"]["channels"]:
            for key in (
                "repurchase_users",
                "repurchase_rate",
                "repurchase_gsv",
                "repurchase_aus",
                "full_repurchase_users",
                "full_repurchase_rate",
                "full_repurchase_gsv",
                "full_repurchase_aus",
                "nonfull_repurchase_users",
                "nonfull_repurchase_gsv",
                "nonfull_repurchase_aus",
            ):
                assert key in ch, f"channel={ch['channel']} missing {key}"

    def test_window_30_gsv_partition_matches_sprint139(self, monkeypatch_connection):
        """window_days=30 时正装 + 非正装 GSV 应覆盖任意回购 GSV."""
        result = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )

        for ch in result["summary"]["channels"]:
            split_gsv = ch["full_repurchase_gsv"] + ch["nonfull_repurchase_gsv"]
            assert abs(split_gsv - ch["repurchase_gsv"]) <= 0.05


class TestSamplingROILevelLinkage:
    """Task 3: level 切换触发不同聚合维度."""

    def test_level_changes_category_breakdown(self, monkeypatch_connection):
        """切 level 时 cat_sql 返回对应聚合字段的 category 值."""
        result_category = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_category",
        )
        result_tier = get_sampling_roi(
            start_date="2026-05-01",
            end_date="2026-05-31",
            window_days=30,
            level="spu_tier",
        )

        assert result_category["category_breakdown"]
        assert result_tier["category_breakdown"]
        assert "category" in result_category["category_breakdown"][0]
        assert "category" in result_tier["category_breakdown"][0]
