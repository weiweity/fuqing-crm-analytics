"""Sprint 97 regression: 7 个目标 service 的 channel 条件均有表别名."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FILTER_BUILDER_SERVICES = {
    "backend/services/flow_service.py": 4,
    "backend/services/asset_service.py": 1,
    "backend/services/metrics/overview.py": 7,
    "backend/services/churn_service.py": 2,
    "backend/services/geo_service.py": 1,
}

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


def test_filter_builder_services_post_process_every_build() -> None:
    for service, expected_count in FILTER_BUILDER_SERVICES.items():
        text = (ROOT / service).read_text(encoding="utf-8")
        assert text.count('.replace("channel IN (", "o.channel IN (")') == expected_count, service
        assert text.count('.replace("channel NOT IN (", "o.channel NOT IN (")') == expected_count, service


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
