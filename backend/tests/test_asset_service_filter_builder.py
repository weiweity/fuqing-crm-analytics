# -*- coding: utf-8 -*-
"""
Sprint 54 Lane C L3 FilterBuilder 改造 (asset_service.py) 回归测试.

Root cause: asset_service.py 1 处 `{valid_sql}` 字符串内嵌 (get_asset_trend) →
走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.
"""
import inspect
import pytest

from backend.services import asset_service
from backend.services.asset_service import _build_asset_trend_filter


class TestAssetServiceFilterBuilder:
    """Sprint 54 Lane C L3 regression test: asset_service.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_asset_service_source(self):
        """
        源码扫描: asset_service.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(asset_service)
        assert "{valid_sql}" not in source, (
            "asset_service.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_asset_trend_filter_includes_time_range_and_valid_order(self):
        """
        _build_asset_trend_filter 输出 time_range + valid_order (via FilterBuilder).
        """
        sql, params = _build_asset_trend_filter("2026-01-01", "2026-01-31")
        # FilterBuilder.with_time_range 自动用 ? 占位
        assert "?" in sql
        # FilterBuilder.with_metric_type(GSV) 输出 valid_order 静态 SQL
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        # params 至少: start_dt + end_dt
        assert len(params) >= 2
        # with_time_range 自动补全时间
        assert "2026-01-01 00:00:00" in params
        assert "2026-01-31 23:59:59.999999" in params
