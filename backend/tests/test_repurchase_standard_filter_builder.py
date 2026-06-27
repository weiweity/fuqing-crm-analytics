# -*- coding: utf-8 -*-
"""
Sprint 54 Lane C L3 FilterBuilder 改造 (repurchase/standard.py) 回归测试.

Root cause: repurchase/standard.py 6 处 `{valid_sql}` 字符串内嵌 → 全部走
FilterBuilder.build() + DuckDB `?` DB-API 参数化.
"""
import inspect

from backend.services.category_service.repurchase import standard
from backend.services.category_service.repurchase.standard import _build_repurchase_period_filter


class TestRepurchaseStandardFilterBuilder:
    """Sprint 54 Lane C L3 regression test: repurchase/standard.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_standard_source(self):
        """
        源码扫描: repurchase/standard.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(standard)
        assert "{valid_sql}" not in source, (
            "repurchase/standard.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_standard_filter_no_channel(self):
        """
        无 channel/exclude: FilterBuilder 输出 valid_order 静态 SQL, 无 ? 无 params.
        """
        sql, params = _build_repurchase_period_filter(channel=None, exclude_channels=None)
        assert "?" not in sql
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        assert params == []

    def test_standard_filter_with_channel(self):
        """
        channel 通过 ? 参数化.
        """
        sql, params = _build_repurchase_period_filter(channel="直播", exclude_channels=None)
        assert "直播" not in sql
        assert "?" in sql
        # 渠道展开: "直播" → ["直播"] (1 个 db_name)
        assert "直播" in params or any("直播" in str(p) for p in params)

    def test_standard_filter_with_exclude(self):
        """
        exclude_channels 通过 ? 参数化.
        """
        sql, params = _build_repurchase_period_filter(
            channel=None, exclude_channels=["低价"]
        )
        assert "低价" not in sql
        assert "?" in sql
        assert len(params) >= 1

    def test_standard_filter_channel_takes_precedence(self):
        """
        channel 跟 exclude 同时给: channel 优先 (elif 逻辑).
        """
        sql_ch, params_ch = _build_repurchase_period_filter(
            channel="直播", exclude_channels=["低价"]
        )
        sql_no, params_no = _build_repurchase_period_filter(
            channel=None, exclude_channels=["低价"]
        )
        # 不同路径 → 不同 params
        assert params_ch != params_no
