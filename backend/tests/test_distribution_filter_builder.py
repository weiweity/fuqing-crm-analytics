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

    根因: 旧 FilterBuilder.channel_in/channel_not_in 输出 `channel IN/NOT IN` 无表别名,
    跟 `r.channel` 冲突. Sprint 98 真治本后由 FilterBuilder 默认输出 `o.channel`.
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


class TestSprint6011DistributionParamsOrderRegression:
    """Sprint 60.1.1 治本: get_category_distribution params 顺序对齐 SQL `?` 占位符.

    根因 (跟 Sprint 60 同根因类型, Sprint 60 漏修 Lane C):
    get_category_distribution SQL 模板的 `?` 占位符顺序是
    base_params DATE(?) × 2 → rfm r.analysis_date = ? → r.lookback_days = ? → DATE(?) end_date
    → valid_where_clause (pay_time × 2 + channel × 4) → excluded_cat_sql × 18 → channel_filter × 4.
    修前 valid_where_params 在前 → SQL 第 1 个 DATE(?) 拿到 pay_time start, 错位 2 params
    → DuckDB ConversionException: invalid date field format: "百补派样" → API 500.

    防御: 故意 rollback 验证 test 真 FAIL (Sprint 34.1 "破坏 → 验证 → 恢复" 模式).
    """

    def test_get_category_distribution_params_aligned_with_sql(self, monkeypatch_connection):
        """get_category_distribution + exclude_channels 真跑 SQL, 验证不抛 ConversionException."""
        from backend.services.category_service.distribution import get_category_distribution
        result = get_category_distribution(
            date="2026-06-20",
            lookback_days=19,
            level="class",
            exclude_channels=["U先派样", "百补派样", "赠品&0.01", "其他"],
        )
        # 修复后应该不抛 ConversionException
        assert isinstance(result, dict)
        assert "date" in result
        assert "distribution" in result
        # total_users > 0 (排除低价后还应有真实品类用户)
        assert result.get("total_users", 0) > 0, (
            f"修复后 total_users 应 > 0, 实际: {result.get('total_users')}"
        )
