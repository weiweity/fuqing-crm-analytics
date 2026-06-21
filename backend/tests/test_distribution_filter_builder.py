# -*- coding: utf-8 -*-
"""
Sprint 54 Lane C L3 FilterBuilder 改造 (distribution.py) 回归测试.

Root cause: distribution.py 4 处 `{valid_sql}` 字符串内嵌 → 全部走 FilterBuilder.build()
+ DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 distribution.py 都会被本测试集捕获.
"""
import inspect

from backend.services.category_service import distribution
from backend.services.category_service.distribution import _build_distribution_filter


class TestDistributionFilterBuilder:
    """Sprint 54 Lane C L3 regression test: distribution.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_distribution_source(self):
        """
        源码扫描: distribution.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(distribution)
        assert "{valid_sql}" not in source, (
            "distribution.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_distribution_filter_no_channel(self):
        """
        无 channel/exclude: FilterBuilder 输出 valid_order 静态 SQL.
        """
        sql, params = _build_distribution_filter(channel=None, exclude_channels=None)
        assert "?" not in sql, f"no user input expected, got: {sql}"
        # FilterBuilder with_metric_type(GSV) 输出 valid_order 静态 SQL
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        assert params == []

    def test_distribution_filter_with_channel(self):
        """
        channel 通过 ? 参数化, 不在 SQL 字符串中.
        """
        sql, params = _build_distribution_filter(channel="纯派样", exclude_channels=None)
        # channel 走 ? 占位, 不在 SQL 字面量
        assert "纯派样" not in sql
        # expand_channels("纯派样") → ["U先派样", "百补派样"]
        assert "U先派样" in params
        assert "百补派样" in params
        assert "?" in sql

    def test_distribution_filter_with_exclude(self):
        """
        exclude_channels 通过 ? 参数化.
        """
        sql, params = _build_distribution_filter(
            channel=None, exclude_channels=["低价"]
        )
        assert "低价" not in sql
        assert "?" in sql
        # exclude params 进入 params
        assert len(params) >= 1

    def test_distribution_filter_channel_takes_precedence(self):
        """
        channel 和 exclude 同时给: channel 优先 (elif 逻辑).
        """
        sql_with_ch, params_with_ch = _build_distribution_filter(
            channel="直播", exclude_channels=["低价"]
        )
        sql_no_ch, params_no_ch = _build_distribution_filter(
            channel=None, exclude_channels=["低价"]
        )
        # channel=直播 时, params 只含直播的 db_name,不含低价
        # channel=None 时, params 含低价的 db_name
        # 两者 params 不同 (因为不同选择路径)
        assert params_with_ch != params_no_ch


class TestSprint601ChannelAliasRegression:
    """Sprint 60.1 治本: _build_distribution_filter / _build_value_tier_filter
    输出 SQL 加 `o.channel` 别名前缀, 跟 `LEFT JOIN user_rfm r` 共存时不再触发
    DuckDB Binder 错 (Ambiguous reference to column name "channel").

    根因: FilterBuilder.channel_in/channel_not_in 输出 `channel IN/NOT IN` 无表别名,
    跟 `r.channel` 冲突. Sprint 60.1 fix: 在生成 SQL 后做一次 `channel` → `o.channel`
    replace (精准修改, 不动其他字段).
    """

    def test_distribution_filter_channel_has_alias(self):
        """_build_distribution_filter 加 channel 时, SQL 必须含 `o.channel` 前缀."""
        sql, params = _build_distribution_filter(
            channel="直播", exclude_channels=None
        )
        assert "o.channel IN" in sql, (
            f"channel 字段需加 o. 别名, 实际 SQL: {sql}"
        )
        # 防回归: 不能出现无别名 `channel IN` (跟 LEFT JOIN user_rfm r 冲突).
        # 严格模式: SQL 全文不能含裸 `channel IN` (前面没有 o.):
        # 用 regex 扫 `(?<!o\.)\bchannel IN\b` 应该找不到.
        import re
        bare_channel_in = re.findall(r"(?<!o\.)\bchannel IN\b", sql)
        assert not bare_channel_in, (
            f"channel IN 必须加 o. 前缀, 实际 SQL: {sql}, 命中: {bare_channel_in}"
        )

    def test_distribution_filter_exclude_channel_has_alias(self):
        """_build_distribution_filter 加 exclude_channels 时, SQL 必须含 `o.channel` 前缀."""
        sql, params = _build_distribution_filter(
            channel=None, exclude_channels=["U先派样", "百补派样"]
        )
        assert "o.channel NOT IN" in sql, (
            f"channel NOT IN 需加 o. 别名, 实际 SQL: {sql}"
        )
