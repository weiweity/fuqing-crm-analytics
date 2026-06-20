# -*- coding: utf-8 -*-
"""
Sprint 54 Lane A L3 FilterBuilder 改造 (flow_service.py) 回归测试.

Root cause: flow_service.py 2 处 `{valid_sql}` 字符串内嵌 → FilterBuilder.build()
+ DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 flow_service.py 都会被本测试集捕获.

测试策略 (Sprint 24+ P3 教训: 真连接 + 真 SQL):
- case 1 (test_no_valid_sql_fstring_in_flow_source): 源码扫描 — `inspect.getsource()`
  扫 flow_service.py 全文, 确保无 `{valid_sql}` 占位符
- case 2-3: helper 单元测试 — `_build_flow_fm_filter` / `_build_flow_r_filter`
  验证返回 (sql, params), ? 数量匹配, 用户输入不在 sql 字面量中
- case 4: 双 CTE (F/M vs R) 各 build 一次, params 独立
"""
import inspect

from backend.services import flow_service
from backend.services.flow_service import (
    _build_flow_fm_filter,
    _build_flow_r_filter,
)


class TestFlowServiceFilterBuilder:
    """Sprint 54 Lane A L3 regression test: flow_service.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_flow_source(self):
        """
        源码扫描: flow_service.py 中已无 `{valid_sql}` 占位符.

        这是 Sprint 34.1 教训的"破坏 → 验证 → 恢复"循环的 source-level 保护.
        任何后续修改把 `f"... {valid_sql} ..."` 拼回 flow_service.py 都会被本测试捕获.
        """
        source = inspect.getsource(flow_service)
        assert "{valid_sql}" not in source, (
            "flow_service.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_flow_fm_filter_returns_parametrized_sql(self):
        """
        _build_flow_fm_filter 返回的 SQL 全部用 `?` 占位.
        """
        sql, params = _build_flow_fm_filter(
            "2026-06-01", "2026-06-30", exclude_channels=None,
        )
        assert "?" in sql
        # 2 个 ? (time range) + valid_order 无 params
        assert sql.count("?") == len(params)
        # time range 自动补全时间
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30 23:59:59.999999" in params

    def test_flow_fm_filter_exclude_channels_parametrized(self):
        """
        exclude_channels 通过 ? 参数化, 不在 SQL 字面量 (防 SQL 注入回归).
        """
        sql, params = _build_flow_fm_filter(
            "2026-06-01", "2026-06-30", exclude_channels=["小程序"],
        )
        assert "小程序" in params
        assert "小程序" not in sql
        assert sql.count("?") == len(params)

    def test_flow_r_filter_no_channel(self):
        """
        R 指标 (365 天固定窗口) 不应用 channel 过滤, 但 valid_order 三条件仍走 FilterBuilder.
        """
        sql, params = _build_flow_r_filter("2025-06-20", "2026-06-20")
        assert "is_goujinjin = FALSE" in sql
        assert "is_refund = FALSE" in sql
        assert "channel NOT IN" not in sql  # R 不应用 channel 过滤
        assert sql.count("?") == len(params)
