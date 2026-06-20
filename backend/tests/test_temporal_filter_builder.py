# -*- coding: utf-8 -*-
"""
Sprint 54 Lane B L3 FilterBuilder 改造 (temporal.py) 回归测试.

Root cause: temporal.py 14 处 `{valid_sql}` f-string 内嵌 + 多处 channel/exclude/
excluded_cat 字符串拼接 → 全部走 FilterBuilder.build() + DuckDB `?` DB-API 参数化.

防回归: 任何后续修改把 f-string 拼接/字符串内嵌放回 temporal.py 都会被本测试集捕获.

测试策略 (Sprint 24+ P3 教训: 真连接 + 真 SQL):
- case 1 (test_no_valid_sql_fstring_in_temporal_source): 源码扫描
- case 2-5: helper 单元测试 — 直接调 helpers 验证返回 (sql, params), ? 数量匹配
- case 6: end-to-end — 真 DuckDB + 模拟数据, 验证 anchor_mode / path_depth / channel
"""
import inspect
import duckdb

from backend.services.category_service.flow import temporal
from backend.services.category_service.flow.temporal import (
    _build_target_orders_filter,
    _build_assoc_filter,
    _build_extra_cats_in_filter,
    _compute_temporal_association,
)


class TestTemporalFilterBuilder:
    """Sprint 54 Lane B L3 regression test: temporal.py FilterBuilder 改造."""

    def test_no_valid_sql_fstring_in_temporal_source(self):
        """源码扫描: temporal.py 中已无 `{valid_sql}` 占位符."""
        source = inspect.getsource(temporal)
        assert "{valid_sql}" not in source, (
            "temporal.py 仍有 `{valid_sql}` f-string 内嵌, "
            "必须用 FilterBuilder.build() 替换"
        )

    def test_target_orders_filter_returns_parametrized_sql(self):
        """_build_target_orders_filter 返回的 SQL 全部用 `?` 占位."""
        sql, params = _build_target_orders_filter(
            level_col="spu_product_class",
            target_category="cat_001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            channel=None,
            exclude_channels=None,
        )
        # ? count 包含 3 (category + start + end) + valid_order (0) + channel (0/1/2)
        assert sql.count("?") == len(params), (
            f"? count {sql.count('?')} != params count {len(params)}\n"
            f"sql: {sql}\nparams: {params}"
        )
        # category, start_date, end_date 进 params
        assert "cat_001" in params
        assert "2026-06-01 00:00:00" in params
        assert "2026-06-30" in params

    def test_target_orders_channel_parametrized(self):
        """channel 通过 ? 参数化, 不在 SQL 字符串中 (防 SQL 注入回归)."""
        sql, params = _build_target_orders_filter(
            level_col="spu_product_class",
            target_category="cat_001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            channel="纯派样",  # expand → ["U先派样", "百补派样"]
            exclude_channels=None,
        )
        # "纯派样" 应在 params, 不在 SQL 字面量
        assert "纯派样" not in sql
        # expand_channels 后的 DB 名
        assert "U先派样" in params
        assert "百补派样" in params

    def test_assoc_filter_parametrized(self):
        """_build_assoc_filter 包含 target_category + excluded_cat + valid_order."""
        sql, params = _build_assoc_filter(
            level_col="spu_product_class",
            target_category="cat_001",
            channel=None,
            exclude_channels=None,
        )
        assert sql.count("?") == len(params)
        # target_category 参数化
        assert "cat_001" not in sql
        assert "cat_001" in params
        # excluded_cat 16 项进 params
        assert sum(1 for p in params if p in temporal.EXCLUDED_PRODUCT_CATEGORIES) == len(temporal.EXCLUDED_PRODUCT_CATEGORIES)

    def test_extra_cats_in_filter(self):
        """step1 的 _cat_expr IN (...) 走参数化."""
        # 用 SQL 元字符注入测试值, 防注入回归
        sql, params = _build_extra_cats_in_filter(
            level_col="spu_product_class",
            extra_cats=["foo'; DROP TABLE", "bar OR 1=1 --", "baz"],
        )
        assert sql.count("?") == 3
        assert params == ["foo'; DROP TABLE", "bar OR 1=1 --", "baz"]
        # 防注入: 用户值不在 SQL 字面量
        assert "foo" not in sql
        assert "DROP" not in sql
        assert "bar" not in sql
        assert "1=1" not in sql

    def test_end_to_end_no_channel(self):
        """端到端: 真 DuckDB, 无 channel, anchor=first."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
                spu_product_class VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', 'cat_001', 100.0, '2026-06-10 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u1', '直播', 'cat_002', 50.0, '2026-06-15 10:00:00', FALSE, '交易成功', FALSE),
            ('o3', 'u2', '货架', 'cat_001', 200.0, '2026-06-12 10:00:00', FALSE, '交易成功', FALSE)
        """)
        result = _compute_temporal_association(
            conn,
            target_category="cat_001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            level="class",
            window_days=30,
            channel=None,
            exclude_channels=None,
            anchor_mode="first",
            path_depth=1,
        )
        # u1 bought cat_001 first, then cat_002 (post)
        assert any(item["category_name"] == "cat_002" for item in result["post_purchase"])
        # 1 user (u1) flowed cat_001 → cat_002
        cat_002_post = next((i for i in result["post_purchase"] if i["category_name"] == "cat_002"), None)
        assert cat_002_post["user_count"] == 1
        # Sankey has cat_001 + cat_002 + 未购买其他 (for u2)
        names = {n["name"] for n in result["post_sankey"]["nodes"]}
        assert "cat_001" in names
        assert "cat_002" in names
        assert "未购买其他" in names

    def test_end_to_end_with_channel(self):
        """端到端: channel 过滤, 防注入回归."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
                spu_product_class VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', 'cat_001', 100.0, '2026-06-10 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u1', '直播', 'cat_002', 50.0, '2026-06-15 10:00:00', FALSE, '交易成功', FALSE),
            ('o3', 'u2', '货架', 'cat_001', 200.0, '2026-06-12 10:00:00', FALSE, '交易成功', FALSE)
        """)
        # channel=直播 只算 u1
        result = _compute_temporal_association(
            conn,
            target_category="cat_001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            level="class",
            window_days=30,
            channel="直播",
            exclude_channels=None,
            anchor_mode="first",
            path_depth=1,
        )
        # 1 user, cat_002, ratio=1.0
        cat_002_post = next((i for i in result["post_purchase"] if i["category_name"] == "cat_002"), None)
        assert cat_002_post["user_count"] == 1
        assert cat_002_post["ratio"] == 1.0
        # u2 (货架) 不算入 total_users, 所以 no "未购买其他" 节点
        names = {n["name"] for n in result["post_sankey"]["nodes"]}
        assert "未购买其他" not in names

    def test_end_to_end_path_depth_2(self):
        """端到端: path_depth=2 不报错."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR, user_id VARCHAR, channel VARCHAR,
                spu_product_class VARCHAR, actual_amount DOUBLE,
                pay_time TIMESTAMP, is_goujinjin BOOLEAN,
                order_status VARCHAR, is_refund BOOLEAN
            )
        """)
        conn.execute("""
            INSERT INTO orders VALUES
            ('o1', 'u1', '直播', 'cat_001', 100.0, '2026-06-10 10:00:00', FALSE, '交易成功', FALSE),
            ('o2', 'u1', '直播', 'cat_002', 50.0, '2026-06-12 10:00:00', FALSE, '交易成功', FALSE),
            ('o3', 'u1', '直播', 'cat_003', 30.0, '2026-06-15 10:00:00', FALSE, '交易成功', FALSE)
        """)
        result = _compute_temporal_association(
            conn,
            target_category="cat_001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            level="class",
            window_days=30,
            channel=None,
            exclude_channels=None,
            anchor_mode="first",
            path_depth=2,
        )
        # 2-step path cat_001 → cat_002 → cat_003 (1 user)
        assert any(
            link["source"] == "cat_002" and link["target"] == "cat_003"
            for link in result["post_sankey"]["links"]
        )
