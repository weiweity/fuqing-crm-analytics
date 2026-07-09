"""L4.72.6 rfm_dashboard_full extended target planner tests."""
from __future__ import annotations

from datetime import date

from scripts.etl.build_rfm_dashboard_full_table import (
    DEFAULT_CHANNELS,
    DEFAULT_EXCLUDE_CHANNELS,
    DEFAULT_LOOKBACK_DAYS,
    get_full_extended_target_objects,
    get_full_extended_targets,
)


def test_l4_72_6_default_channels_follow_business_ssot() -> None:
    assert len(DEFAULT_CHANNELS) >= 5
    assert DEFAULT_CHANNELS[0] == "全店"
    assert "货架" in DEFAULT_CHANNELS
    assert "淘客" in DEFAULT_CHANNELS
    assert "抖音" not in DEFAULT_CHANNELS


def test_l4_72_6_default_excludes_cover_low_price_label() -> None:
    assert DEFAULT_EXCLUDE_CHANNELS == ("", "LOW_PRICE_CHANNELS")


def test_l4_72_6_get_full_extended_targets_count_and_shape() -> None:
    targets = get_full_extended_targets(date(2026, 7, 9))

    assert len(targets) == 5 * 3 * len(DEFAULT_CHANNELS) * len(DEFAULT_EXCLUDE_CHANNELS)
    assert len(targets) >= 100
    assert ("MTD", "2026-07-01", "全店", "", DEFAULT_LOOKBACK_DAYS) in targets
    assert ("MTD", "2025-07-01", "货架", "LOW_PRICE_CHANNELS", DEFAULT_LOOKBACK_DAYS) in targets


def test_l4_72_6_typed_targets_keep_end_date_for_future_materialization() -> None:
    targets = get_full_extended_target_objects(date(2026, 7, 9))
    target = targets[0]

    assert target.period_type == "MTD"
    assert target.as_of_date == "2026-07-01"
    assert target.end_date == "2026-07-08"
    assert target.channel == "全店"
    assert target.lookback_days == DEFAULT_LOOKBACK_DAYS
