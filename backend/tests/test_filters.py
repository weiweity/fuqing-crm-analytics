"""
Tests for backend/semantic/filters.py - unified filter condition builder.

Covers:
- OrderFilters: static SQL fragment generators
- FilterBuilder: dynamic WHERE clause builder
- AmountExprBuilder: amount expression generators
- _expand_channels: channel group expansion
"""
from backend.semantic.filters import (
    OrderFilters,
    FilterBuilder,
    AmountExprBuilder,
    MetricType,
    _expand_channels,
)


class TestOrderFilters:
    """Test OrderFilters static methods."""

    def test_valid_order_triple_condition(self):
        """valid_order() returns the canonical triple-filter."""
        sql, params = OrderFilters.valid_order()
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        assert params == []

    def test_gmv_base_excludes_goujinjin_and_closed(self):
        """gmv_base() excludes goujinjin and closed orders, but keeps refunds."""
        sql, params = OrderFilters.gmv_base()
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        # GMV includes refunds, so no is_refund check
        assert "is_refund" not in sql

    def test_not_goujinjin(self):
        sql, params = OrderFilters.not_goujinjin()
        assert sql == "is_goujinjin = FALSE"
        assert params == []

    def test_not_refund_double_safety(self):
        """not_refund uses double-safety: status != closed AND is_refund = FALSE."""
        sql, _ = OrderFilters.not_refund()
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql

    def test_pay_time_between(self):
        sql, params = OrderFilters.pay_time_between("2026-01-01 00:00:00", "2026-01-31 23:59:59")
        assert "pay_time >= ?" in sql
        assert "pay_time <= ?" in sql
        assert params == ["2026-01-01 00:00:00", "2026-01-31 23:59:59"]

    def test_pay_time_between_dates_auto_fill(self):
        """pay_time_between_dates auto-fills 00:00:00 and 23:59:59."""
        sql, params = OrderFilters.pay_time_between_dates("2026-01-01", "2026-01-31")
        assert params == ["2026-01-01 00:00:00", "2026-01-31 23:59:59"]

    def test_is_member(self):
        sql, params = OrderFilters.is_member()
        assert sql == "is_member = TRUE"
        assert params == []

    def test_channel_in_expands(self):
        """channel_in produces parameterized IN clause."""
        sql, params = OrderFilters.channel_in(["直播", "货架"])
        assert "channel IN (" in sql
        assert "?" in sql
        assert "直播" in params
        assert "货架" in params

    def test_channel_in_empty_returns_true(self):
        """Empty channel list => 1=1 (no filter)."""
        sql, params = OrderFilters.channel_in([])
        assert sql == "1=1"
        assert params == []

    def test_channel_not_in(self):
        sql, params = OrderFilters.channel_not_in(["购物金"])
        assert "channel NOT IN (" in sql
        assert "购物金" in params

    def test_dimension_eq(self):
        sql, params = OrderFilters.dimension_eq("province", "广东")
        assert "COALESCE(province, '未知') = ?" in sql
        assert params == ["广东"]


class TestFilterBuilder:
    """Test FilterBuilder dynamic construction."""

    def test_default_build_uses_valid_order(self):
        """Empty builder => valid_order (GSV base)."""
        fb = FilterBuilder()
        sql, params = fb.build()
        assert "is_goujinjin = FALSE" in sql
        assert "is_refund = FALSE" in sql

    def test_gmv_metric_type(self):
        """GMV metric => gmv_base (no is_refund check)."""
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GMV)
        sql, params = fb.build()
        assert "is_goujinjin = FALSE" in sql
        assert "is_refund" not in sql

    def test_gsv_metric_type(self):
        """GSV metric => valid_order (with is_refund check)."""
        fb = FilterBuilder()
        fb.with_metric_type(MetricType.GSV)
        sql, params = fb.build()
        assert "is_refund = FALSE" in sql

    def test_time_range(self):
        fb = FilterBuilder()
        fb.with_time_range("2026-01-01", "2026-01-31")
        sql, params = fb.build()
        assert "pay_time >= ?" in sql
        assert "2026-01-01 00:00:00" in params
        assert "2026-01-31 23:59:59.999999" in params

    def test_channels_filter(self):
        fb = FilterBuilder()
        fb.with_channels(["直播", "货架"])
        sql, params = fb.build()
        assert "channel IN (" in sql
        assert "直播" in params

    def test_exclude_channels(self):
        fb = FilterBuilder()
        fb.with_exclude_channels(["购物金"])
        sql, params = fb.build()
        assert "channel NOT IN (" in sql

    def test_member_only(self):
        fb = FilterBuilder()
        fb.with_member_only(True)
        sql, params = fb.build()
        assert "is_member = TRUE" in sql

    def test_dimension_filter(self):
        fb = FilterBuilder()
        fb.with_dimension("province", "广东")
        sql, params = fb.build()
        assert "COALESCE(province, '未知') = ?" in sql

    def test_extra_conditions(self):
        fb = FilterBuilder()
        fb.add_extra("custom_col = ?", ["value"])
        sql, params = fb.build()
        assert "custom_col = ?" in sql
        assert "value" in params

    def test_chained_builder(self):
        """Builder supports method chaining."""
        fb = FilterBuilder()
        result = (
            fb.with_metric_type(MetricType.GMV)
            .with_time_range("2026-01-01", "2026-01-31")
            .with_channels(["直播"])
            .with_member_only()
        )
        assert result is fb
        sql, params = fb.build()
        assert "pay_time >= ?" in sql
        assert "channel IN (" in sql
        assert "is_member = TRUE" in sql

    def test_lookback(self):
        fb = FilterBuilder()
        fb.with_lookback("2026-04-20", 90)
        sql, params = fb.build()
        assert "pay_time >= ?" in sql
        # start should be 2026-01-20 (90 days before Apr 20)
        assert "2026-01-20 00:00:00" in params
        assert "2026-04-20 23:59:59.999999" in params


class TestAmountExprBuilder:
    """Test AmountExprBuilder SQL expression generators."""

    def test_sum_gsv_contains_triple_filter(self):
        expr = AmountExprBuilder.sum_gsv()
        assert "SUM(CASE WHEN" in expr
        assert "is_goujinjin = FALSE" in expr
        assert "order_status != '交易关闭'" in expr
        assert "is_refund = FALSE" in expr

    def test_sum_gmv_is_plain_sum(self):
        expr = AmountExprBuilder.sum_gmv()
        assert expr == "SUM(actual_amount)"

    def test_gsv_case_when(self):
        expr = AmountExprBuilder.gsv()
        assert "CASE WHEN" in expr
        assert "is_goujinjin = FALSE" in expr

    def test_gmv_is_plain_column(self):
        expr = AmountExprBuilder.gmv()
        assert expr == "actual_amount"

    def test_custom_column(self):
        expr = AmountExprBuilder.sum_gsv("order_amount")
        assert "order_amount" in expr

    def test_conditional_sum(self):
        expr = AmountExprBuilder.conditional_sum("amount", "is_member = TRUE")
        assert "SUM(CASE WHEN is_member = TRUE THEN amount ELSE 0 END)" == expr


class TestExpandChannels:
    """Test channel group expansion."""

    def test_combo_channel_expands(self):
        """纯派样 => U先派样 + 百补派样"""
        result = _expand_channels(["纯派样"])
        assert "U先派样" in result
        assert "百补派样" in result

    def test_single_channel_passthrough(self):
        """Individual channels pass through with UI->DB mapping."""
        result = _expand_channels(["直播"])
        assert result == ["直播"]

    def test_dedup(self):
        """Duplicate channels are deduplicated."""
        result = _expand_channels(["直播", "直播"])
        assert result == ["直播"]

    def test_ui_to_db_mapping(self):
        """赠品&0.01 => 赠品&0.01渠道"""
        result = _expand_channels(["赠品&0.01"])
        assert "赠品&0.01渠道" in result

    def test_mixed_combo_and_single(self):
        result = _expand_channels(["纯派样", "货架"])
        assert "U先派样" in result
        assert "百补派样" in result
        assert "货架" in result
