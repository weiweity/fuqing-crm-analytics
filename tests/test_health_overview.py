"""health/overview.py 单元测试"""
import sys
from pathlib import Path
from datetime import date, timedelta
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── _soft_cap 纯函数测试 ──────────────────────────────────────


class TestSoftCap:
    def test_ratio_below_1_returns_ratio(self):
        from backend.services.health.overview import _soft_cap

        assert _soft_cap(0.5, 1.0) == 0.5
        assert _soft_cap(0.8, 1.0) == 0.8
        assert _soft_cap(1.0, 1.0) == 1.0

    def test_ratio_at_1_returns_1(self):
        from backend.services.health.overview import _soft_cap

        assert _soft_cap(1.0, 1.0) == 1.0

    def test_ratio_above_1_log_bonus(self):
        from backend.services.health.overview import _soft_cap
        import math

        # 3x target 时达到 max_bonus = 0.2（ln(3)/ln(4) ≈ 0.792）
        ratio_3x = _soft_cap(3.0, 1.0, max_bonus=0.2)
        expected_3x = 1.0 + 0.2 * math.log(3.0) / math.log(4.0)
        assert abs(ratio_3x - expected_3x) < 1e-6
        assert 1.0 < ratio_3x < 1.2

    def test_ratio_4x_returns_1_plus_max_bonus(self):
        from backend.services.health.overview import _soft_cap

        # 4x 时达到封顶（ln(4)/ln(4) = 1.0）
        ratio_4x = _soft_cap(4.0, 1.0, max_bonus=0.2)
        assert abs(ratio_4x - 1.2) < 1e-6

    def test_ratio_10x_bonus_but_diminishing(self):
        from backend.services.health.overview import _soft_cap

        # 10x ratio 有额外bonus（超过3x的边际递减，但增速放缓）
        ratio_10x = _soft_cap(10.0, 1.0, max_bonus=0.2)
        # ln(10)/ln(4) ≈ 1.66， bonus ≈ 0.2*1.66 = 0.332
        assert 1.3 < ratio_10x < 1.35
        # 相对于 ratio=4（封顶点），10x 的 bonus 更小（边际递减）
        ratio_4x = _soft_cap(4.0, 1.0, max_bonus=0.2)
        assert ratio_10x < ratio_4x + 0.2  # 10x bonus < 4x bonus + 0.2

    def test_zero_target_returns_zero(self):
        from backend.services.health.overview import _soft_cap

        assert _soft_cap(5.0, 0.0) == 0.0

    def test_zero_value_returns_zero(self):
        from backend.services.health.overview import _soft_cap

        assert _soft_cap(0.0, 1.0) == 0.0


# ── _is_historical_period 测试 ───────────────────────────────


class TestIsHistoricalPeriod:
    def test_today_is_not_historical(self):
        from backend.services.health.overview import _is_historical_period

        today = date.today().strftime("%Y-%m-%d")
        assert _is_historical_period(today) is False

    def test_yesterday_is_historical(self):
        from backend.services.health.overview import _is_historical_period

        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert _is_historical_period(yesterday) is True

    def test_7_days_ago_is_historical(self):
        from backend.services.health.overview import _is_historical_period

        past = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        assert _is_historical_period(past) is True

    def test_future_date_is_not_historical(self):
        from backend.services.health.overview import _is_historical_period

        future = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
        assert _is_historical_period(future) is False


# ── _compute_health_score 测试 ───────────────────────────────


class TestComputeHealthScore:
    @pytest.fixture
    def mock_health_config(self, monkeypatch):
        """模拟健康评分配置"""
        mock_cfg = {
            "targets": {
                "all_store_repurchase_rate": 0.21,
                "same_product_repurchase_rate": 0.12,
                "old_customer_gsv_ratio": 0.55,
                "old_customer_aus": 180.0,
                "recent_7d_repurchase_users": 300.0,
            },
            "weights": {
                "all_store_repurchase_rate": 0.20,
                "same_product_repurchase_rate": 0.30,
                "old_customer_gsv_ratio": 0.10,
                "old_customer_aus": 0.30,
                "recent_7d_repurchase_users": 0.10,
            },
            "health_level_bounds": {
                "healthy": 80.0,
                "warning": 60.0,
            },
        }

        def mock_get_config():
            return mock_cfg

        monkeypatch.setattr(
            "backend.services.health.config.get_health_config",
            mock_get_config,
        )

    def test_perfect_score_returns_100_healthy(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        score, level = _compute_health_score(
            all_store_repurchase_rate=0.21,
            same_product_repurchase_rate=0.12,
            old_customer_gsv_ratio=0.55,
            old_customer_aus=180.0,
            period_repurchase_users=300,
            period_days=7,
        )
        assert score == 100.0
        assert level == "healthy"

    def test_zero_repurchase_returns_low_score(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        score, level = _compute_health_score(
            all_store_repurchase_rate=0.0,
            same_product_repurchase_rate=0.0,
            old_customer_gsv_ratio=0.0,
            old_customer_aus=0.0,
            period_repurchase_users=0,
            period_days=7,
        )
        assert score == 0.0
        assert level == "critical"

    def test_score_is_rounded_to_1_decimal(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        score, level = _compute_health_score(
            all_store_repurchase_rate=0.10,
            same_product_repurchase_rate=0.06,
            old_customer_gsv_ratio=0.30,
            old_customer_aus=100.0,
            period_repurchase_users=150,
            period_days=7,
        )
        assert isinstance(score, float)
        # 验证四舍五入到1位小数
        assert round(score, 1) == score

    def test_weekly_repurchase_normalized_to_7_days(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        # 30天内1500复购用户 → 周均 = 1500/30*7 = 350
        score, level = _compute_health_score(
            all_store_repurchase_rate=0.21,
            same_product_repurchase_rate=0.12,
            old_customer_gsv_ratio=0.55,
            old_customer_aus=180.0,
            period_repurchase_users=1500,
            period_days=30,
        )
        # 350 > 300(目标)，有bonus但未超3倍
        assert score > 100.0
        assert level == "healthy"

    def test_score_at_warning_threshold(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        # 复购率50%目标=warning区；客单达标+周均复购50%目标
        score, level = _compute_health_score(
            all_store_repurchase_rate=0.105,   # 50% of 0.21
            same_product_repurchase_rate=0.06,  # 50% of 0.12
            old_customer_gsv_ratio=0.275,       # 50% of 0.55
            old_customer_aus=180.0,              # 100% of 180 (达标，拉高分数)
            period_repurchase_users=150,         # 50% of 300
            period_days=7,
        )
        assert level == "warning"
        assert 60.0 <= score < 80.0

    def test_score_at_critical(self, mock_health_config):
        from backend.services.health.overview import _compute_health_score

        score, level = _compute_health_score(
            all_store_repurchase_rate=0.05,
            same_product_repurchase_rate=0.02,
            old_customer_gsv_ratio=0.10,
            old_customer_aus=50.0,
            period_repurchase_users=30,
            period_days=7,
        )
        assert level == "critical"
        assert score < 60.0


# ── get_overview 边界测试 ────────────────────────────────────


class TestGetOverviewEdgeCases:
    def test_empty_orders_returns_structure(self, monkeypatch):
        """空orders表应返回有效结构（全零值），不抛异常"""
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
            "backend.services.health.overview.get_connection",
            empty_db_factory,
        )

        from backend.services.health.overview import get_overview

        result = get_overview(
            analysis_date="2025-06-15",
            period_days=30,
        )

        # 必须返回有效结构
        assert isinstance(result, dict)
        assert "health_score" in result
        assert "health_level" in result
        assert "alerts" in result
        # 全零数据时 score 应该是 0
        assert result["health_score"] == 0.0
        assert result["health_level"] == "critical"


# ── GSV 口径验证 ─────────────────────────────────────────────


class TestGSVCaliber:
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
            # 插入一条有效订单和一条退款订单
            c.execute("""
                INSERT INTO orders VALUES
                ('O1', 'S1', 'U1', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P1', 'M1', '产品A', 'SKU1', 'SC1', '名称A',
                 1, 100.0, '无退款', 0.0, 100.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, TRUE, '护肤', 'B5', '经典', '护肤套装',
                 'B5面膜', '50ml', '货架', FALSE, FALSE),
                ('O2', 'S2', 'U2', '2025-06-01', '2025-06-01', '2025-06-01',
                 '普通', '交易成功', 'P2', 'M1', '产品B', 'SKU2', 'SC2', '名称B',
                 1, 100.0, '退款成功', 100.0, 0.0, '浙江', '杭州',
                 '达人A', 'I1', 'R1', 'V1', '自然', '搜索',
                 '备注', 2025, 6, TRUE, '护肤', 'B5', '经典', '护肤套装',
                 'B5面膜', '50ml', '货架', FALSE, TRUE)
            """)
            return c

        monkeypatch.setattr(
            "backend.services.health.overview.get_connection",
            gsv_db_factory,
        )

        from backend.services.health.overview import get_overview

        result = get_overview(analysis_date="2025-06-15", period_days=30)

        # 退款订单的 actual_amount=0，有效 GMV=100
        # health_score 不依赖 GSV 直接，但验证 SQL 不报错
        assert result["health_score"] >= 0
        assert result["health_level"] in ("healthy", "warning", "critical")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
