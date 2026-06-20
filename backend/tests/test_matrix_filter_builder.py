# -*- coding: utf-8 -*-
"""
Sprint 54 Lane B L3 FilterBuilder 改造 (matrix.py) 回归测试.

Root cause: matrix.py 3 处 `{valid_sql}` f-string 内嵌 + 多处 channel/exclude/
excluded_cat 字符串拼接 → 全部走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.
"""
import inspect
import duckdb
import tempfile
import os

from backend.services.category_service.flow import matrix
from backend.services.category_service.flow.matrix import (
    _build_all_orders_filter,
    get_category_flow_matrix,
)


class TestMatrixFilterBuilder:
    """Sprint 54 Lane B L3 regression test: matrix.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_matrix_source(self):
        """源码扫描: matrix.py 中已无 `{valid_sql}` 占位符."""
        source = inspect.getsource(matrix)
        assert "{valid_sql}" not in source, (
            "matrix.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_all_orders_filter_returns_parametrized_sql(self):
        """_build_all_orders_filter 返回的 SQL 全部用 `?` 占位."""
        sql, params = _build_all_orders_filter(
            level_col="spu_product_class",
            start_date="2026-06-01",
            end_date="2026-06-30",
            channel=None,
            exclude_channels=None,
        )
        assert sql.count("?") == len(params), (
            f"? count {sql.count('?')} != params count {len(params)}\n"
            f"sql: {sql}\nparams: {params}"
        )

    def test_all_orders_filter_with_exclude(self):
        """exclude_channels 进 params, 不在 SQL 字面量."""
        sql, params = _build_all_orders_filter(
            level_col="spu_product_class",
            start_date="2026-06-01",
            end_date="2026-06-30",
            channel=None,
            exclude_channels=["赠品&0.01", "其他"],
        )
        # expand_channels: "赠品&0.01" → "赠品&0.01渠道", "其他" 保持
        assert "赠品&0.01渠道" in params
        assert "其他" in params
        # 防注入: 排除渠道名不在 SQL 字面量
        assert "赠品&0.01" not in sql
        assert "其他" not in sql
        # excluded_cat 18 项也进 params
        assert sum(1 for p in params if p in matrix.EXCLUDED_PRODUCT_CATEGORIES) == len(matrix.EXCLUDED_PRODUCT_CATEGORIES)

    def test_end_to_end_get_category_flow_matrix(self):
        """端到端: 真 DuckDB 跑 get_category_flow_matrix."""
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            os.makedirs("backend/cache/category_flow", exist_ok=True)

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
                ('o1', 'u1', '直播', 'cat_001', 100.0, '2026-06-10 10:00:00', FALSE, '交易成功', FALSE),
                ('o2', 'u1', '直播', 'cat_002', 50.0, '2026-06-15 10:00:00', FALSE, '交易成功', FALSE),
                ('o3', 'u2', '货架', 'cat_001', 200.0, '2026-06-12 10:00:00', FALSE, '交易成功', FALSE),
                ('o4', 'u2', '货架', 'cat_002', 80.0, '2026-06-14 10:00:00', FALSE, '交易成功', FALSE)
            """)
            matrix.get_connection = lambda: real_conn

            result = get_category_flow_matrix(
                start_date="2026-06-01",
                end_date="2026-06-30",
                level="class",
                top_n=10,
                window_days=30,
                channel=None,
                exclude_channels=None,
            )
            # 矩阵 sources/targets 应包含 cat_001 和 cat_002
            assert "cat_001" in result["matrix"]["sources"]
            assert "cat_002" in result["matrix"]["targets"]
            # 2 users flowed from cat_001 to cat_002
            assert sum(sum(row) for row in result["matrix"]["matrix"]) == 2
