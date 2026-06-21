# -*- coding: utf-8 -*-
"""
Sprint 54 Lane A L3 FilterBuilder 改造 (category_service/overview.py) 回归测试.

Root cause: category_service/overview.py 4 处 `{valid_sql}` 字符串内嵌
(3 个 helper 函数 _compute_category_period / _compute_wool_party_breakdown /
_compute_value_tier_base) → FilterBuilder.build() + DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 category_service/overview.py
都会被本测试集捕获.

测试策略 (Sprint 24+ P3 教训: 真连接 + 真 SQL):
- case 1: 源码扫描 — `inspect.getsource()` 扫 category_service/overview.py 全文
- case 2-7: helper 单元测试 — `_build_category_period_filter` /
  `_build_wool_party_filter` / `_build_value_tier_filter`
  验证 (sql, params), ? 数量匹配, 用户输入 (channel / exclude_channels)
  不在 sql 字面量中, metric_type (GMV/GSV) 动态切换正确.
"""
import inspect

from backend.services.category_service import overview as category_overview
from backend.services.category_service.overview import (
    _build_category_period_filter,
    _build_wool_party_filter,
    _build_value_tier_filter,
)


class TestCategoryOverviewFilterBuilder:
    """Sprint 54 Lane A L3 regression test: category_service/overview.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_category_overview_source(self):
        """
        源码扫描: category_service/overview.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(category_overview)
        assert "{valid_sql}" not in source, (
            "category_service/overview.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_category_period_filter_gmv(self):
        """
        _build_category_period_filter GMV 模式: gmv_base() 不含 is_refund.
        """
        sql, params = _build_category_period_filter(
            "2026-06-01", "2026-06-30", "GMV", None, None,
        )
        assert "?" in sql
        assert sql.count("?") == len(params)
        assert "is_goujinjin = FALSE" in sql
        assert "is_refund = FALSE" not in sql  # gmv_base 不含 is_refund
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30 23:59:59.999999" in params

    def test_category_period_filter_gsv(self):
        """
        _build_category_period_filter GSV 模式: valid_order() 含 is_refund.
        """
        sql, params = _build_category_period_filter(
            "2026-06-01", "2026-06-30", "GSV", None, None,
        )
        assert "is_refund = FALSE" in sql
        assert sql.count("?") == len(params)

    def test_category_period_filter_channel_parametrized(self):
        """
        channel 通过 ? 参数化, 不在 SQL 字面量 (防 SQL 注入回归).
        """
        sql, params = _build_category_period_filter(
            "2026-06-01", "2026-06-30", "GSV", "小程序", None,
        )
        assert "小程序" in params
        assert "小程序" not in sql, (
            f"channel leaked into SQL: {sql}"
        )
        assert sql.count("?") == len(params)

    def test_category_period_filter_exclude_parametrized(self):
        """
        exclude_channels 通过 ? 参数化, 不在 SQL 字面量.
        """
        sql, params = _build_category_period_filter(
            "2026-06-01", "2026-06-30", "GSV", None, ["U先派样", "百补派样"],
        )
        assert "U先派样" in params
        assert "百补派样" in params
        assert "U先派样" not in sql
        assert "百补派样" not in sql
        assert sql.count("?") == len(params)

    def test_wool_party_filter_no_exclude(self):
        """
        _build_wool_party_filter: 默认 GSV, 不应用 exclude_channels (羊毛党定义决定).
        """
        sql, params = _build_wool_party_filter(
            "2026-06-01", "2026-06-30", None,
        )
        assert "is_refund = FALSE" in sql
        assert "channel NOT IN" not in sql  # 羊毛党不应用 exclude
        assert sql.count("?") == len(params)

    def test_wool_party_filter_with_channel(self):
        """
        _build_wool_party_filter 接受 channel (但不接受 exclude_channels).
        """
        sql, params = _build_wool_party_filter(
            "2026-06-01", "2026-06-30", "小程序",
        )
        assert "小程序" in params
        assert "小程序" not in sql
        assert sql.count("?") == len(params)

    def test_value_tier_filter_parametrized(self):
        """
        _build_value_tier_filter 接受 channel + exclude_channels, 全部参数化.
        """
        sql, params = _build_value_tier_filter(
            "2026-06-01", "2026-06-30", "小程序", ["U先派样"],
        )
        assert "小程序" in params
        assert "小程序" not in sql
        assert "U先派样" in params
        assert "U先派样" not in sql
        assert sql.count("?") == len(params)
        assert "is_refund = FALSE" in sql


class TestSprint60CategoryParamsMismatchRegression:
    """Sprint 60 治本: _compute_category_period / _compute_value_tier_base params 顺序错位.

    根因: Sprint 54 Lane A L3 改造时, 两个函数的 params 列表把 start_date/end_date
    错位插在 EXCLUDED_PRODUCT_CATEGORIES 之前, 而 SQL `?` 占位符顺序是
    DATE(?) + time range(?) + EXCLUDED(?) + where_params(?) — 多 2 个 params
    触发 DuckDB InvalidInputException "excess parameters: 22, 23" → API 500.

    防御: 真连接 + 真 SQL 调 _compute_category_period / _compute_value_tier_base,
    跑通无异常 = fix 生效; 故意改回旧顺序 (Stage 3 review 验证 test 真 FAIL).
    """

    def test_compute_category_period_params_order_fixed(self, monkeypatch_connection):
        """_compute_category_period 用 monkeypatch_connection fixture (Sprint 53 隔离 DuckDB).

        修复后 params 顺序正确, SQL 21 个 `?` 跟 params 21 个一一对应, 不抛 InvalidInputException.
        """
        from backend.services.category_service.overview import _compute_category_period
        from datetime import date
        from datetime import timedelta

        start_dt = date(2026, 6, 1)
        end_dt = date(2026, 6, 20)
        cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # 修复后应该不抛 InvalidInputException; 跟 fixture DuckDB 真实跑 SQL
        result = _compute_category_period(
            conn=monkeypatch_connection,
            start_date="2026-06-01",
            end_date="2026-06-20",
            cutoff=cutoff,
            level="class",
            metric_type="GSV",
        )
        # 至少返回 __ttl__ 键 (空 DuckDB 也应该返回空 dict, 不抛异常)
        assert isinstance(result, dict)

    def test_compute_value_tier_base_params_order_fixed(self, monkeypatch_connection):
        """_compute_value_tier_base 同样 params 顺序错位 bug, 修复后跑通.

        验证 _compute_value_tier_base 跟 _compute_category_period 同根因同治本.
        """
        from backend.services.category_service.overview import _compute_value_tier_base
        from datetime import date
        from datetime import timedelta

        start_dt = date(2026, 6, 1)
        end_dt = date(2026, 6, 20)
        cutoff = (date(start_dt.year, start_dt.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

        # 修复后应该不抛 InvalidInputException
        result, wool = _compute_value_tier_base(
            conn=monkeypatch_connection,
            start_date="2026-06-01",
            end_date="2026-06-20",
            cutoff=cutoff,
            level="class",
            channel=None,
            exclude_channels=None,
        )
        # 真实跑 SQL, 返回 list
        assert isinstance(result, list)

    def test_value_tier_filter_channel_has_alias(self):
        """Sprint 60.1 fix: _build_value_tier_filter 加 channel 时, SQL 必须含 `o.channel` 前缀.

        根因: FilterBuilder.channel_in 输出 `channel IN` 无表别名, 跟 `LEFT JOIN user_rfm r`
        共存时 DuckDB 报 Binder 错. Sprint 60.1 fix: 改用手写 `o.channel IN` (配 _build_distribution_channel_filter 模式).
        """
        sql, params = _build_value_tier_filter(
            "2026-06-01", "2026-06-30", "小程序", None,
        )
        assert "o.channel IN" in sql, (
            f"channel 字段需加 o. 别名, 实际 SQL: {sql}"
        )
        # exclude 路径
        sql2, params2 = _build_value_tier_filter(
            "2026-06-01", "2026-06-30", None, ["U先派样"],
        )
        assert "o.channel NOT IN" in sql2, (
            f"channel NOT IN 需加 o. 别名, 实际 SQL: {sql2}"
        )
