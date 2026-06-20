# -*- coding: utf-8 -*-
"""
Sprint 54 Lane B L3 FilterBuilder 改造 (association.py) 回归测试.

Root cause: association.py 3 处 `{valid_sql}` f-string 内嵌 → 全部走
FilterBuilder.build() + DuckDB `?` DB-API 参数化.
"""
import inspect
import duckdb
import tempfile
import os

from backend.services.category_service.flow import association
from backend.services.category_service.flow.association import (
    _build_all_orders_filter,
    get_category_flow,
)


class TestAssociationFilterBuilder:
    """Sprint 54 Lane B L3 regression test: association.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_association_source(self):
        """源码扫描: association.py 中已无 `{valid_sql}` 占位符."""
        source = inspect.getsource(association)
        assert "{valid_sql}" not in source, (
            "association.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_all_orders_filter_returns_parametrized_sql(self):
        """_build_all_orders_filter 返回的 SQL 全部用 `?` 占位."""
        sql, params = _build_all_orders_filter(
            level_col="spu_product_class",
            start_date="2026-06-01",
            end_date="2026-06-30",
            channel=None,
            exclude_channels=["赠品&0.01"],
        )
        assert sql.count("?") == len(params)
        # exclude 进 params (expand_channels: "赠品&0.01" → "赠品&0.01渠道")
        assert "赠品&0.01渠道" in params
        assert "赠品&0.01" not in sql

    def test_end_to_end_get_category_flow_no_target(self):
        """端到端: 不带 target_category, 只跑 flow matrix 部分."""
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
                ('o3', 'u2', '货架', 'cat_001', 200.0, '2026-06-12 10:00:00', FALSE, '交易成功', FALSE)
            """)
            association.get_connection = lambda: real_conn

            result = get_category_flow(
                start_date="2026-06-01",
                end_date="2026-06-30",
                level="class",
                top_n=10,
                window_days=30,
                channel=None,
                exclude_channels=None,
                target_category=None,
            )
            # 应有 sankey_data 和 matrix
            assert "sankey_data" in result
            assert "matrix" in result
            assert result["matrix"]["sources"]
            assert result["matrix"]["targets"]

    def test_end_to_end_get_category_flow_with_target(self):
        """端到端: 带 target_category, 触发时序关联分析 (走 temporal.py)."""
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
                ('o2', 'u1', '直播', 'cat_002', 50.0, '2026-06-15 10:00:00', FALSE, '交易成功', FALSE)
            """)
            association.get_connection = lambda: real_conn

            result = get_category_flow(
                start_date="2026-06-01",
                end_date="2026-06-30",
                level="class",
                top_n=10,
                window_days=30,
                channel=None,
                exclude_channels=None,
                target_category="cat_001",
            )
            # 应有 target_category + post_purchase / pre_purchase
            assert result["target_category"] == "cat_001"
            assert "post_purchase" in result
            assert "pre_purchase" in result
            assert "post_sankey" in result
            assert "pre_sankey" in result
            # u1 先买 cat_001 后买 cat_002
            cat_002_post = next((i for i in result["post_purchase"] if i["category_name"] == "cat_002"), None)
            assert cat_002_post is not None
            assert cat_002_post["user_count"] == 1
