# -*- coding: utf-8 -*-
"""
Sprint 54 Lane C L3 FilterBuilder 改造 (basket.py) 回归测试.

Root cause: basket.py 1 处 `{valid_sql}` 字符串内嵌 → 走 FilterBuilder.build() 参数化.
"""
import inspect

from backend.services.category_service import basket
from backend.services.category_service.basket import _build_basket_valid_filter


class TestBasketFilterBuilder:
    """Sprint 54 Lane C L3 regression test: basket.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_basket_source(self):
        """
        源码扫描: basket.py 中已无 `{valid_sql}` 占位符.
        """
        source = inspect.getsource(basket)
        assert "{valid_sql}" not in source, (
            "basket.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_basket_valid_filter_returns_valid_order_sql(self):
        """
        _build_basket_valid_filter 输出 valid_order 静态 SQL (无 ?, 无 params).
        """
        sql, params = _build_basket_valid_filter()
        # FilterBuilder.with_metric_type(GSV) 内部调 valid_order(),输出静态 SQL
        assert "?" not in sql
        assert "is_goujinjin = FALSE" in sql
        assert "order_status != '交易关闭'" in sql
        assert "is_refund = FALSE" in sql
        assert params == []
