# -*- coding: utf-8 -*-
"""
Sprint 53.5 L3 FilterBuilder 改造 (churn.py) 回归测试.

Root cause: churn.py 4 处 `{valid_sql}` 字符串内嵌 + 多处 channel/level/granularity
f-string 内嵌 → 全部走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 churn.py 都会被本测试集捕获.

测试策略 (Sprint 24+ P3 教训: 真连接 + 真 SQL):
- case 1 (test_no_valid_sql_fstring_in_churn_source): 源码扫描 — `inspect.getsource()` 
  扫 churn.py 全文, 确保无 `{valid_sql}` 占位符
- case 2-4: helper 单元测试 — 直接调 `_build_churn_filter` 验证返回 (sql, params),
  ? 数量匹配, 用户输入不在 sql 字面量中
- case 5-6: helper 单元测试 — `_build_daily_trend_filter` / `_build_user_list_filter`
  验证 granularity/category_id 参数化
"""
import inspect

from backend.services.category_service import churn
from backend.services.category_service.churn import (
    _build_churn_filter,
    _build_daily_trend_filter,
    _build_user_list_filter,
)


class TestChurnFilterBuilder:
    """Sprint 53.5 L3 regression test: churn.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_churn_source(self):
        """
        源码扫描: churn.py 中已无 `{valid_sql}` 占位符.

        这是 Sprint 34.1 教训的"破坏 → 验证 → 恢复"循环的 source-level 保护.
        任何后续修改把 `f"... {valid_sql} ..."` 拼回 churn.py 都会被本测试捕获.
        """
        source = inspect.getsource(churn)
        assert "{valid_sql}" not in source, (
            "churn.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_churn_filter_returns_parametrized_sql(self):
        """
        _build_churn_filter 返回的 SQL 全部用 `?` 占位, 无 f-string 拼接痕迹.
        """
        sql, params = _build_churn_filter(
            "2026-06-01", "2026-06-30",
            channel=None, exclude_channels=None, level="category",
        )
        # valid_order 静态部分无 ?, 但其他条件 (time range, level, excluded) 必须用 ?
        assert "?" in sql, f"expected '?' placeholders in SQL, got: {sql}"
        # params 至少: start + end + 16 个 excluded + level + level
        assert len(params) >= 2, f"params too short: {params}"
        # with_time_range 自动补全时间: start→"00:00:00", end→"23:59:59.999999"
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30 23:59:59.999999" in params

    def test_churn_double_cte_params_independent(self):
        """
        双 CTE 各 build 一次, params 独立 (current 跟 previous 互不影响).
        """
        a_sql, a_params = _build_churn_filter(
            "2026-06-01", "2026-06-30", None, None, "category"
        )
        b_sql, b_params = _build_churn_filter(
            "2026-05-01", "2026-05-31", None, None, "category"
        )
        # SQL 时间范围不同, params 第一项 (start_date) 也不同
        assert "2026-06-01 00:00:00" in a_params
        assert "2026-05-01 00:00:00" in b_params
        # params 总数必须一致 (helper 自洽, 不管时间范围)
        assert len(a_params) == len(b_params), (
            f"params length mismatch: {len(a_params)} vs {len(b_params)}"
        )

    def test_churn_with_channel_parametrized(self):
        """
        channel 通过 ? 参数化, 不在 SQL 字符串中 (防 SQL 注入回归).
        """
        sql, params = _build_churn_filter(
            "2026-06-01", "2026-06-30",
            channel="纯派样", exclude_channels=None, level="category",
        )
        # channel "纯派样" 应在 params 中, 不在 SQL 字面量
        assert "纯派样" not in sql, (
            f"channel leaked into SQL: {sql}"
        )
        # expand_channels("纯派样") → ["U先派样", "百补派样"]
        # 因为是多渠道, params 会有 2 个
        assert "U先派样" in params
        assert "百补派样" in params

    def test_daily_trend_filter_parametrized(self):
        """
        granularity 通过 `? = ?` 占位进 params (date_col 决策由调用方做).
        """
        sql, params = _build_daily_trend_filter(
            "2026-06-01", "2026-06-30", "cat_001", "day",
        )
        # "day" 应在 params 中, 不在 SQL 字面量
        assert "day" not in sql, (
            f"granularity leaked into SQL: {sql}"
        )
        assert "day" in [str(p) for p in params]
        # category_id 也进 params
        assert "cat_001" in params

    def test_user_list_filter_shared_by_count_sql(self):
        """
        _build_user_list_filter 返回稳定 filter (主 SQL + count_sql 共用).
        """
        sql, params = _build_user_list_filter(
            "2026-06-01", "2026-06-30", "cat_001",
        )
        # params 至少: start + end + category_id = 3
        assert params is not None
        assert len(params) >= 3, f"params too short: {params}"
        assert "cat_001" in params
        # with_time_range 自动补全时间: start→"00:00:00", end→"23:59:59.999999"
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30 23:59:59.999999" in params


# Warning: Temporary break verification (Sprint 24+ P3 single-connection lesson)
#
# To verify the test really catches the typo:
#   1. 故意改 _build_churn_filter, 把 `where_sql = where_sql + " AND ? = ?"` 改为 f-string
#   2. PYTHONPATH=. pytest backend/tests/test_churn_filter_builder.py -v
#      Expected: 至少 case 2 / 4 FAIL
#   3. 恢复 + 验证 PASS
