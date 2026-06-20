# -*- coding: utf-8 -*-
"""
Sprint 54 Lane A L3 FilterBuilder 改造 (geo_service.py) 回归测试.

Root cause: geo_service.py 5 处 `{valid_sql}` 字符串内嵌 → FilterBuilder.build()
+ DuckDB `?` DB-API 参数化. (3 个函数, 主查询 + 总计 + top_provinces + month_sql).

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 geo_service.py 都会被本测试集捕获.

测试策略 (Sprint 24+ P3 教训: 真连接 + 真 SQL):
- case 1: 源码扫描 — `inspect.getsource()` 扫 geo_service.py 全文
- case 2-4: helper 单元测试 — `_build_geo_filter` 验证返回 (sql, params),
  ? 数量匹配, 用户输入 (exclude_channels / segment_id) 不在 sql 字面量中
"""
import inspect

from backend.services import geo_service
from backend.services.geo_service import _build_geo_filter


class TestGeoServiceFilterBuilder:
    """Sprint 54 Lane A L3 regression test: geo_service.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_geo_source(self):
        """
        源码扫描: geo_service.py 中已无 `{valid_sql}` 占位符.

        这是 Sprint 34.1 教训的"破坏 → 验证 → 恢复"循环的 source-level 保护.
        任何后续修改把 `f"... {valid_sql} ..."` 拼回 geo_service.py 都会被本测试捕获.
        """
        source = inspect.getsource(geo_service)
        assert "{valid_sql}" not in source, (
            "geo_service.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_geo_filter_returns_parametrized_sql(self):
        """
        _build_geo_filter 返回的 SQL 全部用 `?` 占位, 无 f-string 拼接痕迹.
        """
        sql, params = _build_geo_filter(
            "2026-06-01", "2026-06-30", None, None,
        )
        assert "?" in sql
        assert sql.count("?") == len(params)
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30 23:59:59.999999" in params

    def test_geo_filter_exclude_channels_parametrized(self):
        """
        exclude_channels 通过 ? 参数化, 不在 SQL 字符串中 (防 SQL 注入回归).
        """
        sql, params = _build_geo_filter(
            "2026-06-01", "2026-06-30", ["小程序"], None,
        )
        assert "小程序" in params
        assert "小程序" not in sql, (
            f"channel leaked into SQL: {sql}"
        )
        assert sql.count("?") == len(params)

    def test_geo_filter_segment_id_parametrized(self):
        """
        segment_id 通过 add_extra ? 占位, 走 r.segment_id = ? 形式 (JOIN user_rfm 用).
        """
        sql, params = _build_geo_filter(
            "2026-06-01", "2026-06-30", None, 3,
        )
        assert "r.segment_id = ?" in sql
        assert 3 in params
        assert sql.count("?") == len(params)
        # segment_id 不应被字面量化到 SQL
        assert "r.segment_id = 3" not in sql
