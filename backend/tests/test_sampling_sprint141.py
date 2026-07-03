"""Sprint 141 派样留尾治本回归测试 — DQM docs (period_distribution 部分已删).

Sprint 145 留尾治理删 period_sql + period_distribution 字段 (前端 Sprint 144
已切 repurchaseDistribution), TestSprint141PeriodDistribution 是 dead code
配套, 跟 Sprint 145 dead code cleanup 1:1 stable 删 (Sprint 201 R2 v24 L4.42
立项实证反漂移). 仅保留 DQM QualityFlag 描述回归.
"""

import pytest

from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


class TestSprint141QualityFlagDocs:
    """Sprint 141: QualityFlag 字段描述回归 (period_distribution 已删)."""

    def test_quality_flag_field_descriptions_present(self, monkeypatch_connection):
        """QualityFlag 所有对外字段都通过 Pydantic Field 暴露语义说明."""
        from backend.contracts.sampling import QualityFlag

        for field_name in ("code", "severity", "message", "posize_ratio", "total_posize_gsv", "total_gsv"):
            description = QualityFlag.model_fields[field_name].description
            assert description is not None
            assert description.strip()
