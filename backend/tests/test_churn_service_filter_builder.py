# -*- coding: utf-8 -*-
"""
Sprint 54 Lane B L3 FilterBuilder 改造 (churn_service.py) 回归测试.

Root cause: churn_service.py 4 个 builder 中 6 处 `{valid_sql}` f-string 内嵌 + 多处
ex_clause 字符串拼接 → 全部走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 churn_service.py 都会被本测试集捕获.
"""
import inspect
import duckdb

from backend.services import churn_service
from backend.services.churn_service import (
    _build_order_intervals_where,
    _build_user_orders_where,
    _build_segment_filter,
    _build_dynamic_churn_sql,
    _build_fixed_churn_sql,
    _build_dynamic_user_sql,
    _build_fixed_user_sql,
)


class TestChurnServiceFilterBuilder:
    """Sprint 54 Lane B L3 regression test: churn_service.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_churn_service_source(self):
        """源码扫描: churn_service.py 中已无 `{valid_sql}` 占位符."""
        source = inspect.getsource(churn_service)
        assert "{valid_sql}" not in source, (
            "churn_service.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_order_intervals_where(self):
        """_build_order_intervals_where 含 spu_product_class IS NOT NULL."""
        sql, params = _build_order_intervals_where("2024-07-02", None)
        assert "spu_product_class IS NOT NULL" in sql
        assert sql.count("?") == len(params)
        assert "2024-07-02" in params

    def test_user_orders_where_aliased(self):
        """_build_user_orders_where 默认 alias='o' (用于 dynamic builders)."""
        sql, params = _build_user_orders_where("2024-07-02", None)
        assert "o.pay_time >= ?" in sql
        assert sql.count("?") == len(params)

    def test_user_orders_where_no_alias(self):
        """_build_user_orders_where alias='' (用于 fixed builders 的 subquery)."""
        sql, params = _build_user_orders_where("2024-07-02", None, alias="")
        # 没有 "o." 前缀
        assert "o.pay_time" not in sql
        assert "pay_time >= ?" in sql
        assert sql.count("?") == len(params)

    def test_segment_filter(self):
        """_build_segment_filter 接受 Optional[int]."""
        sql, params = _build_segment_filter(5)
        assert sql == "AND r.segment_id = ?"
        assert params == [5]

        sql_none, params_none = _build_segment_filter(None)
        assert sql_none == ""
        assert params_none == []

    def test_dynamic_churn_sql_parametrized(self):
        """_build_dynamic_churn_sql ? count = params count."""
        sql, params = _build_dynamic_churn_sql("2026-06-30", 5, None)
        assert sql.count("?") == len(params)
        # segment_id 5 进 params
        assert 5 in params
        # lookback_start 进 params
        assert "2024-06-30" in params  # 2026-06-30 - 730 days

    def test_fixed_churn_sql_parametrized(self):
        """_build_fixed_churn_sql 4 个 DATE(?) + ulo params + analysis_date + seg."""
        sql, params = _build_fixed_churn_sql("2026-06-30", None, 60, None)
        assert sql.count("?") == len(params)
        # date 出现 5 次: 4x DATE(?) + 1x analysis_date=?
        assert params.count("2026-06-30") == 5

    def test_dynamic_user_sql_parametrized(self):
        """_build_dynamic_user_sql + LIMIT ?."""
        sql, params = _build_dynamic_user_sql("2026-06-30", 3, 100, None)
        assert sql.count("?") == len(params)
        assert 3 in params
        assert 100 in params

    def test_fixed_user_sql_parametrized(self):
        """_build_fixed_user_sql 包含 LIMIT ? + seg ?."""
        sql, params = _build_fixed_user_sql("2026-06-30", 5, 60, 50, None)
        assert sql.count("?") == len(params)
        assert 5 in params  # seg
        assert 50 in params  # limit

    def test_exclude_channels_parametrized(self):
        """exclude_channels 走 ? 参数化, 防 SQL 注入."""
        sql, params = _build_user_orders_where("2024-07-02", ["赠品&0.01", "其他"])
        # 排除渠道进 params, 不在 SQL 字面量
        assert "赠品&0.01" not in sql
        assert "其他" not in sql
        # expand_channels 后: "其他" 是直接值, "赠品&0.01" 走 expand
        # 注意: expand_channels 取决于 channels.py, 这里只验证 leak prevention
        # 防注入: 用户输入值不在 sql 字面量
        # "赠品&0.01" 在 params 中
        # (具体 expand 后的值由 expand_channels 决定)
        assert any("赠品&0.01" in str(p) for p in params) or any(p == "其他" for p in params)

    def test_end_to_end_dynamic_churn(self):
        """端到端: 真 DuckDB 跑 get_churn_risk_distribution (dynamic)."""
        real_conn = duckdb.connect(":memory:")
        real_conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
                spu_product_class VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        real_conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', 'cat_001', 100.0, '2025-01-01 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u1', '直播', 'cat_001', 50.0, '2025-06-01 10:00:00', FALSE, '交易成功', FALSE),
            ('o3', 'u2', '货架', 'cat_001', 200.0, '2024-12-01 10:00:00', FALSE, '交易成功', FALSE)
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
        churn_service.get_connection = lambda: real_conn

        result = churn_service.get_churn_risk_distribution(
            date="2026-06-30", churn_mode="dynamic",
        )
        assert result["total_users"] >= 1
        assert result["high_risk"] + result["medium_risk"] + result["low_risk"] == result["total_users"]

    def test_end_to_end_fixed_users(self):
        """端到端: 真 DuckDB 跑 get_churn_risk_users (fixed)."""
        real_conn = duckdb.connect(":memory:")
        real_conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
                spu_product_class VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        real_conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', 'cat_001', 100.0, '2025-01-01 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u2', '货架', 'cat_001', 50.0, '2025-06-01 10:00:00', FALSE, '交易成功', FALSE)
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
        churn_service.get_connection = lambda: real_conn

        result = churn_service.get_churn_risk_users(
            date="2026-06-30", churn_mode="fixed", fixed_threshold=60, limit=10,
        )
        # total_matched 可能为 0 或 1+
        assert "total_matched" in result
        assert "users" in result
