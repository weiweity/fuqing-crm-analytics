# -*- coding: utf-8 -*-
"""
Sprint 54 Lane B L3 FilterBuilder 改造 (user_profile.py) 回归测试.

Root cause: user_profile.py 5 处 `{valid_sql}` f-string 内嵌 + category_filter 字符串拼接
→ 全部走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.
"""
import inspect
import duckdb

from backend.services.category_service import user_profile
from backend.services.category_service.user_profile import (
    _build_user_profile_period_where,
    _build_user_rfm_join,
    get_category_user_profile,
)


class TestUserProfileFilterBuilder:
    """Sprint 54 Lane B L3 regression test: user_profile.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_user_profile_source(self):
        """源码扫描: user_profile.py 中已无 `{valid_sql}` 占位符."""
        source = inspect.getsource(user_profile)
        assert "{valid_sql}" not in source, (
            "user_profile.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_period_where_returns_parametrized_sql(self):
        """_build_user_profile_period_where 返回的 SQL 全部用 `?` 占位."""
        sql, params = _build_user_profile_period_where(
            start_date="2026-04-01",
            end_date="2026-06-30",
            category="护肤",
        )
        assert sql.count("?") == len(params)
        # 3 params: start_date, end_date, category
        assert "2026-04-01" in params
        assert "2026-06-30" in params
        assert "护肤" in params
        # 防注入: category 不在 SQL 字面量
        assert "护肤" not in sql

    def test_rfm_join(self):
        """_build_user_rfm_join 返回的 SQL 全部用 `?` 占位."""
        sql, params = _build_user_rfm_join("2026-06-30", 90)
        assert sql.count("?") == len(params)
        assert "2026-06-30" in params
        assert 90 in params

    def test_end_to_end_get_category_user_profile(self):
        """端到端: 真 DuckDB 跑 get_category_user_profile."""
        real_conn = duckdb.connect(":memory:")
        real_conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR, province VARCHAR,
                spu_category VARCHAR, spu_type VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        real_conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', '北京', '护肤', '面霜', 100.0, '2026-05-01 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u2', '货架', '上海', '护肤', '精华', 200.0, '2026-05-15 10:00:00', FALSE, '交易成功', FALSE),
            ('o3', 'u3', '直播', '广州', '美妆', '口红', 300.0, '2026-05-20 10:00:00', FALSE, '交易成功', FALSE)
        """)
        real_conn.execute("""
            CREATE TABLE user_rfm (
                user_id VARCHAR, segment_id INTEGER, analysis_date VARCHAR,
                metric_type VARCHAR, lookback_days INTEGER
            )
        """)
        real_conn.execute("""
            INSERT INTO user_rfm VALUES
            ('u1', 1, '2026-06-30', 'GMV', 90),
            ('u2', 2, '2026-06-30', 'GMV', 90)
        """)
        user_profile.get_connection = lambda: real_conn
        user_profile._normalize_date = lambda d: d

        result = get_category_user_profile(
            date="2026-06-30",
            lookback_days=90,
            category="护肤",
        )
        # 护肤 category: u1 + u2 (美妆的 u3 被排除)
        assert result["total_users"] == 2
        assert result["total_gmv"] == 300.0
        assert result["avg_order_value"] == 150.0
        # 省份只有 北京 + 上海 (广州是美妆)
        provinces = [p["province"] for p in result["province_distribution"]]
        assert "北京" in provinces
        assert "上海" in provinces
        assert "广州" not in provinces
        # 渠道 直播 + 货架
        channels = [c["channel"] for c in result["channel_distribution"]]
        assert "直播" in channels
        assert "货架" in channels
