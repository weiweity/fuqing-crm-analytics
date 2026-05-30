"""category_service 单元测试"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── get_category_overview 边界测试 ───────────────────────────


class TestGetCategoryOverviewEdgeCases:
    def test_empty_orders_returns_valid_structure(self, monkeypatch):
        """空orders表应返回有效结构，不抛异常"""
        import duckdb

        def empty_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            return c

        monkeypatch.setattr(
            "backend.services.category_service.overview.get_connection",
            empty_db_factory,
        )

        from backend.services.category_service.overview import get_category_overview

        result = get_category_overview(
            start_date="2025-06-01",
            end_date="2025-06-15",
            level="class",
        )

        # 必须返回有效结构
        assert isinstance(result, dict)
        assert "all_rows" in result
        assert "member_rows" in result
        assert "all_ttl" in result
        assert "member_ttl" in result
        assert "date_start" in result
        assert "date_end" in result
        assert "metric_type" in result
        # 全零数据
        assert result["all_rows"] == []
        assert result["all_ttl"]["gsv"] == 0


# ── GSV 口径验证 ─────────────────────────────────────────────


class TestCategoryGSVCaliber:
    def test_gsv_excludes_refund_and_goujinjin(self, monkeypatch):
        """GSV 应剔除退款、购物金、交易关闭订单"""
        import duckdb

        def gsv_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            # 有效订单
            c.execute("""
                INSERT INTO orders VALUES
                ('O1', 'S1', 'U1', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P1', 'M1', '产品A', 'SKU1', 'SC1', '名称A',
                 1, 100.0, '无退款', 0.0, 100.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, FALSE)
            """)
            # 退款订单（actual_amount=0）
            c.execute("""
                INSERT INTO orders VALUES
                ('O2', 'S2', 'U2', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P2', 'M1', '产品B', 'SKU2', 'SC2', '名称B',
                 1, 100.0, '退款成功', 100.0, 0.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, TRUE)
            """)
            return c

        monkeypatch.setattr(
            "backend.services.category_service.overview.get_connection",
            gsv_db_factory,
        )

        from backend.services.category_service.overview import get_category_overview

        result = get_category_overview(
            start_date="2025-06-01",
            end_date="2025-06-15",
            level="class",
        )

        # 退款订单不计入 GSV（全店 TTL）
        assert result["all_ttl"]["gsv"] == 100.0  # 只有O1的100


class TestCategoryLevelParameter:
    def test_level_class_uses_spu_category(self, monkeypatch):
        """level='class' 按 spu_category 聚合"""
        import duckdb

        def class_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            c.execute("""
                INSERT INTO orders VALUES
                ('O1', 'S1', 'U1', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P1', 'M1', '产品A', 'SKU1', 'SC1', '名称A',
                 1, 100.0, '无退款', 0.0, 100.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, FALSE)
            """)
            return c

        monkeypatch.setattr(
            "backend.services.category_service.overview.get_connection",
            class_db_factory,
        )

        from backend.services.category_service.overview import get_category_overview

        result = get_category_overview(
            start_date="2025-06-01",
            end_date="2025-06-15",
            level="class",
        )

        # level=class 按 spu_category 聚合，all_rows 包含明细
        assert result["all_ttl"]["gsv"] == 100.0
        # 有一条记录（all_rows 是明细，不是汇总）
        assert len(result["all_rows"]) == 1


class TestCategoryNewVsOldCustomer:
    def test_new_customer_identified_by_first_pay_date(self, monkeypatch):
        """新客 = 在cutoff之前无首购记录的客户"""
        import duckdb

        def new_old_db_factory():
            c = duckdb.connect(database=":memory:")
            c.execute("""
                CREATE TABLE orders (
                    order_id VARCHAR, sub_order_id VARCHAR, user_id VARCHAR,
                    order_time TIMESTAMP, pay_time TIMESTAMP, ship_time TIMESTAMP,
                    order_type VARCHAR, order_status VARCHAR, product_id VARCHAR,
                    merchant_code VARCHAR, product_title VARCHAR, sku_id VARCHAR,
                    sku_code VARCHAR, sku_name VARCHAR, quantity INTEGER,
                    amount DOUBLE, refund_status VARCHAR, refund_amount DOUBLE,
                    actual_amount DOUBLE, province VARCHAR, city VARCHAR,
                    influencer_name VARCHAR, influencer_id VARCHAR, live_room_id VARCHAR,
                    video_id VARCHAR, traffic_source VARCHAR, traffic_type VARCHAR,
                    seller_note VARCHAR, year INTEGER, month INTEGER,
                    is_member BOOLEAN, spu_category VARCHAR, spu_type VARCHAR,
                    spu_tier VARCHAR, spu_product_class VARCHAR, spu_product_subclass VARCHAR,
                    spu_cosmetic VARCHAR, spu_spec VARCHAR, channel VARCHAR,
                    is_goujinjin BOOLEAN, is_refund BOOLEAN
                )
            """)
            c.execute("""
                CREATE TABLE user_first_purchase (
                    user_id VARCHAR PRIMARY KEY, first_pay_date DATE
                )
            """)
            # U1 在2025-05-01首购（cutoff之前）→ 老客
            # U2 在2025-06-10首购（当期）→ 新客
            c.execute("INSERT INTO user_first_purchase VALUES ('U1', '2025-05-01')")
            c.execute("INSERT INTO user_first_purchase VALUES ('U2', '2025-06-10')")
            c.execute("""
                INSERT INTO orders VALUES
                ('O1', 'S1', 'U1', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P1', 'M1', '产品A', 'SKU1', 'SC1', '名称A',
                 1, 100.0, '无退款', 0.0, 100.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, FALSE),
                ('O2', 'S2', 'U2', '2025-06-10', '2025-06-10', '2025-06-10',
                 '普通', '交易成功', 'P2', 'M1', '产品B', 'SKU2', 'SC2', '名称B',
                 1, 50.0, '无退款', 0.0, 50.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, FALSE, '护肤', 'B5', '经典', '护肤套装',
                 NULL, 'B5面膜', '50ml', '货架', FALSE, FALSE)
            """)
            return c

        monkeypatch.setattr(
            "backend.services.category_service.overview.get_connection",
            new_old_db_factory,
        )

        from backend.services.category_service.overview import get_category_overview

        result = get_category_overview(
            start_date="2025-06-01",
            end_date="2025-06-15",
            level="class",
        )

        # U1(老客, 100) + U2(新客, 50) = 150
        assert result["all_ttl"]["gsv"] == 150.0
        assert result["all_ttl"]["old_gsv"] == 100.0
        assert result["all_ttl"]["new_gsv"] == 50.0
        assert result["all_ttl"]["old_users"] == 1
        assert result["all_ttl"]["new_users"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
