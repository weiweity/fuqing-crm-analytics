"""Sprint 98 真治本：FilterBuilder 集中处理 channel 表别名."""

import re
from pathlib import Path

from backend.semantic.filters import FilterBuilder, MetricType, OrderFilters


ROOT = Path(__file__).resolve().parents[2]

PATTERN_CHANNEL_REPLACE = re.compile(
    r"\.replace\([\"']channel IN \([\"'],\s*[\"']o\.channel IN \([\"']\)"
)
PATTERN_CHANNEL_NOT_REPLACE = re.compile(
    r"\.replace\([\"']channel NOT IN \([\"'],\s*[\"']o\.channel NOT IN \([\"']\)"
)


def test_no_service_channel_replace_postprocessing() -> None:
    """所有 service 都不再保留 Sprint 60.1/97 的 replace 治标代码."""
    for service in sorted((ROOT / "backend/services").rglob("*.py")):
        text = service.read_text(encoding="utf-8")
        assert not PATTERN_CHANNEL_REPLACE.search(text), service
        assert not PATTERN_CHANNEL_NOT_REPLACE.search(text), service


def test_order_filters_table_alias_default() -> None:
    sql, params = OrderFilters.channel_in(["直播", "货架"])
    assert sql == "o.channel IN (?,?)"
    assert params == ["直播", "货架"]

    sql, params = OrderFilters.channel_not_in(["购物金"])
    assert sql == "o.channel NOT IN (?)"
    assert params == ["购物金"]

    assert OrderFilters.channel_in([]) == ("1=1", [])


def test_order_filters_table_alias_empty() -> None:
    sql, params = OrderFilters.channel_in(["直播"], table_alias="")
    assert sql == "channel IN (?)"
    assert params == ["直播"]


def test_filter_builder_table_alias_method() -> None:
    default_builder = FilterBuilder()
    default_builder.with_metric_type(MetricType.GSV).with_channels(["直播"])
    default_sql, default_params = default_builder.build()
    assert "o.channel IN (?)" in default_sql
    assert default_params == ["直播"]

    bare_builder = FilterBuilder()
    bare_builder.with_metric_type(MetricType.GSV).with_table_alias("").with_channels(["直播"])
    bare_sql, bare_params = bare_builder.build()
    assert "channel IN (?)" in bare_sql
    assert "o.channel" not in bare_sql
    assert bare_params == ["直播"]
