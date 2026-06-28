"""Sprint 141 派样留尾治本回归测试 — period_distribution + DQM docs."""

import pytest

from backend.services.sampling_service import get_sampling_roi
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSprint141PeriodDistribution:
    """Sprint 141: 61-90d 桶 + QualityFlag 字段描述."""

    @pytest.mark.parametrize("window_days", [30, 60, 90])
    def test_period_distribution_61_90d_fields_present(self, monkeypatch_connection, window_days):
        """任意 window_days 都返回 5 桶字段, 小于 61 天时 61-90d 自然为 0."""
        result = get_sampling_roi(
            start_date="2026-04-01",
            end_date="2026-06-30",
            window_days=window_days,
            level="spu_category",
        )

        pd = result["period_distribution"]
        assert "bucket_61_90d" in pd
        assert "full_bucket_61_90d" in pd
        assert isinstance(pd["bucket_61_90d"], int)
        assert isinstance(pd["full_bucket_61_90d"], int)
        if window_days < 61:
            assert pd["bucket_61_90d"] == 0
            assert pd["full_bucket_61_90d"] == 0

    def test_quality_flag_field_descriptions_present(self, monkeypatch_connection):
        """QualityFlag 所有对外字段都通过 Pydantic Field 暴露语义说明."""
        from backend.contracts.sampling import QualityFlag

        for field_name in ("code", "severity", "message", "posize_ratio", "total_posize_gsv", "total_gsv"):
            description = QualityFlag.model_fields[field_name].description
            assert description is not None
            assert description.strip()
