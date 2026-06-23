"""Sprint 97 regression: 7 个目标 service 的 channel 条件均有表别名."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FILTER_BUILDER_SERVICES = [
    "backend/services/flow_service.py",
    "backend/services/asset_service.py",
    "backend/services/metrics/overview.py",
    "backend/services/churn_service.py",
    "backend/services/geo_service.py",
]

MANUAL_SERVICES = [
    "backend/services/metrics/audience_summary.py",
    "backend/services/sampling_service.py",
]

SPRINT60_1_SERVICES = [
    "backend/services/category_service/distribution.py",
    "backend/services/category_service/overview.py",
    "backend/services/health/tier_flow.py",
    "backend/services/health/rfm_analysis/period.py",
    "backend/services/category_service/basket.py",
]

PATTERN = re.compile(r"(?<![\w.])channel\s+(?:(?:NOT\s+IN|IN)\s*\(|=\s*\?)")


def test_filter_builder_services_use_central_channel_alias() -> None:
    """Sprint 98 后 service 不再自行 replace，默认别名由 FilterBuilder 提供."""
    from backend.semantic.filters import FilterBuilder

    sql, _ = FilterBuilder().with_channels(["直播"]).build()
    assert "o.channel IN (?)" in sql

    for service in FILTER_BUILDER_SERVICES:
        text = (ROOT / service).read_text(encoding="utf-8")
        assert '.replace("channel IN (", "o.channel IN (")' not in text, service
        assert '.replace("channel NOT IN (", "o.channel NOT IN (")' not in text, service


def test_manual_services_have_table_prefix() -> None:
    for service in MANUAL_SERVICES:
        for lineno, line in enumerate((ROOT / service).read_text(encoding="utf-8").splitlines(), 1):
            if PATTERN.search(line):
                raise AssertionError(f"{service}:{lineno} 含无别名 channel: {line.strip()}")


def test_no_regression_in_sprint60_1_services() -> None:
    for service in SPRINT60_1_SERVICES:
        for lineno, line in enumerate((ROOT / service).read_text(encoding="utf-8").splitlines(), 1):
            if not PATTERN.search(line):
                continue
            if service.endswith("distribution.py") and "replace" in line:
                continue
            raise AssertionError(f"{service}:{lineno} 含无别名 channel: {line.strip()}")
