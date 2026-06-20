# -*- coding: utf-8 -*-
"""
Sprint 54 Lane C L3 FilterBuilder 改造 (repurchase/rfm.py) 回归测试.

Root cause: repurchase/rfm.py 6 处 `{valid_sql}` 字符串内嵌 → 全部走
FilterBuilder.build() + DuckDB `?` DB-API 参数化.

注意: rfm.py 是死代码 (Sprint 33 留尾, 路由未注册). 仍做 L3 改造 (代码质量).
"""
import inspect
import pytest

from backend.services.category_service.repurchase import rfm
from backend.services.category_service.repurchase.rfm import _build_repurchase_rfm_filter


class TestRepurchaseRfmFilterBuilder:
    """Sprint 54 Lane C L3 regression test: repurchase/rfm.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_rfm_source(self):
        """
        源码扫描: repurchase/rfm.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(rfm)
        assert "{valid_sql}" not in source, (
            "repurchase/rfm.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_rfm_filter_no_channel(self):
        """
        无 channel/exclude: FilterBuilder 输出 valid_order 静态 SQL, 无 ? 无 params.
        """
        sql, params = _build_repurchase_rfm_filter(channel=None, exclude_channels=None)
        assert "?" not in sql
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        assert params == []

    def test_rfm_filter_with_channel(self):
        """
        channel 通过 ? 参数化.
        """
        sql, params = _build_repurchase_rfm_filter(channel="直播", exclude_channels=None)
        assert "直播" not in sql
        assert "?" in sql
        assert "直播" in params or any("直播" in str(p) for p in params)

    def test_rfm_filter_with_exclude(self):
        """
        exclude_channels 通过 ? 参数化.
        """
        sql, params = _build_repurchase_rfm_filter(
            channel=None, exclude_channels=["低价"]
        )
        assert "低价" not in sql
        assert "?" in sql
        assert len(params) >= 1
