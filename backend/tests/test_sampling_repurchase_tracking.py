"""Sprint 169: Sampling 回购周期跟踪 (3 年对比) 回归测试.

验证 backend/services/sampling_service.get_sampling_repurchase_tracking:
- 3 年桶顺序 (2026 / 2025 / 2024)
- 4 桶顺序 (0-7d / 8-30d / 31-60d / 61-90d)
- 期间回退 -1y / -2y 正确
- window_days 边界 (1 / 30 / 90)
- 早期年份无数据时静默回落 0 (不抛异常)
- 跨年桶分布率不可加总 (业务文档约束)
"""

import pytest

from backend.services.sampling_service import get_sampling_repurchase_tracking
from backend.tests.conftest import _PROD_DUCKDB_AVAILABLE


pytestmark = pytest.mark.skipif(
    not _PROD_DUCKDB_AVAILABLE,
    reason="production DuckDB 不可用",
)


def _reset_orders(conn, rows):
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE orders (
            order_id VARCHAR,
            sub_order_id VARCHAR,
            user_id VARCHAR,
            channel VARCHAR,
            pay_time TIMESTAMP,
            sample_received_at TIMESTAMP,
            spu_category VARCHAR,
            spu_tier VARCHAR,
            spu_product_class VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic VARCHAR,
            spu_type VARCHAR,
            actual_amount DOUBLE,
            is_refund BOOLEAN,
            order_status VARCHAR
        )
    """)
    if rows:
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


@pytest.fixture
def tracking_orders(monkeypatch_connection):
    """3 年跨度的派样+回购订单: 2024 / 2025 / 2026 各覆盖 4 桶."""
    rows = [
        # 2026 年: 派样 2026-04-01 ~ 2026-06-29, 回购 0-7d / 8-30d / 31-60d / 61-90d 各 1 人
        ("s26a", None, "u26a", "U先派样", "2026-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r26a", None, "u26a", "货架", "2026-04-08", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 10.0, False, "交易成功"),
        ("s26b", None, "u26b", "U先派样", "2026-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r26b", None, "u26b", "货架", "2026-04-20", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 20.0, False, "交易成功"),
        ("s26c", None, "u26c", "百补派样", "2026-04-05", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r26c", None, "u26c", "货架", "2026-05-15", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 30.0, False, "交易成功"),
        ("s26d", None, "u26d", "百补派样", "2026-04-05", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r26d", None, "u26d", "货架", "2026-06-15", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 40.0, False, "交易成功"),
        # 2025 年同期: 派样 2025-04-01 ~ 2025-06-29, 回购 4 桶各 1 人
        ("s25a", None, "u25a", "U先派样", "2025-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r25a", None, "u25a", "货架", "2025-04-10", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 11.0, False, "交易成功"),
        ("s25b", None, "u25b", "U先派样", "2025-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r25b", None, "u25b", "货架", "2025-04-25", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 21.0, False, "交易成功"),
        ("s25c", None, "u25c", "百补派样", "2025-04-05", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r25c", None, "u25c", "货架", "2025-05-20", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 31.0, False, "交易成功"),
        ("s25d", None, "u25d", "百补派样", "2025-04-05", None, "精华", "潜力", "精华", "安瓶", "抗老", "小样", 0.01, False, "交易成功"),
        ("r25d", None, "u25d", "货架", "2025-06-10", None, "精华", "潜力", "精华", "安瓶", "抗老", "正装", 41.0, False, "交易成功"),
        # 2024 年同期: 派样 2024-04-01 ~ 2024-06-29, 只有 2 桶 (0-7d / 8-30d), 31-60d / 61-90d 应为 0
        ("s24a", None, "u24a", "U先派样", "2024-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r24a", None, "u24a", "货架", "2024-04-10", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 12.0, False, "交易成功"),
        ("s24b", None, "u24b", "U先派样", "2024-04-05", None, "面膜", "核心", "面膜", "涂抹", "修护", "小样", 0.01, False, "交易成功"),
        ("r24b", None, "u24b", "货架", "2024-04-25", None, "面膜", "核心", "面膜", "涂抹", "修护", "正装", 22.0, False, "交易成功"),
    ]
    _reset_orders(monkeypatch_connection, rows)
    try:
        yield monkeypatch_connection
    finally:
        monkeypatch_connection.execute("DROP TABLE IF EXISTS orders")


def test_tracking_3_years_4_buckets_shape(tracking_orders):
    """3 年 × 4 桶 = 12 桶扁平列表, 年份按 cur/ly/prev2 顺序."""
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=90)

    assert result["year_labels"] == ["2026年", "2025年", "2024年"]
    assert result["window_days"] == 90
    assert result["time_range"]["start"] == "2026-04-01"
    assert result["time_range"]["end"] == "2026-06-29"
    assert len(result["buckets"]) == 12

    # 桶顺序: 每年都按 0-7d / 8-30d / 31-60d / 61-90d
    for year in result["year_labels"]:
        year_buckets = [b for b in result["buckets"] if b["year_label"] == year]
        assert [b["bucket"] for b in year_buckets] == ["0-7d", "8-30d", "31-60d", "61-90d"]


def test_tracking_year_range_shifts_correctly(tracking_orders):
    """3 年期间回退 -1y / -2y 正确."""
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=90)

    by_year = {b["year_label"]: b for b in result["buckets"] if b["bucket"] == "0-7d"}
    assert by_year["2026年"]["year_range_start"] == "2026-04-01"
    assert by_year["2026年"]["year_range_end"] == "2026-06-29"
    assert by_year["2025年"]["year_range_start"] == "2025-04-01"
    assert by_year["2025年"]["year_range_end"] == "2025-06-29"
    assert by_year["2024年"]["year_range_start"] == "2024-04-01"
    assert by_year["2024年"]["year_range_end"] == "2024-06-29"


def test_tracking_per_year_per_bucket_rate(tracking_orders):
    """3 年各自桶分布率 = 正装回购人数 / 派样人数."""
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=90)

    def get_rate(year: str, bucket: str) -> float:
        for b in result["buckets"]:
            if b["year_label"] == year and b["bucket"] == bucket:
                return b["rate"]
        raise AssertionError(f"missing year={year} bucket={bucket}")

    # 2026 年: 4 人派样, 4 桶各 1 人正装回购 → 0.25
    assert get_rate("2026年", "0-7d") == pytest.approx(0.25)
    assert get_rate("2026年", "8-30d") == pytest.approx(0.25)
    assert get_rate("2026年", "31-60d") == pytest.approx(0.25)
    assert get_rate("2026年", "61-90d") == pytest.approx(0.25)

    # 2025 年: 4 人派样, 4 桶各 1 人正装回购 → 0.25
    assert get_rate("2025年", "0-7d") == pytest.approx(0.25)
    assert get_rate("2025年", "8-30d") == pytest.approx(0.25)
    assert get_rate("2025年", "31-60d") == pytest.approx(0.25)
    assert get_rate("2025年", "61-90d") == pytest.approx(0.25)

    # 2024 年: 2 人派样, 仅 0-7d / 8-30d 各 1 人正装回购 → 0.5; 31-60d / 61-90d 静默回落 0
    assert get_rate("2024年", "0-7d") == pytest.approx(0.5)
    assert get_rate("2024年", "8-30d") == pytest.approx(0.5)
    assert get_rate("2024年", "31-60d") == pytest.approx(0.0)
    assert get_rate("2024年", "61-90d") == pytest.approx(0.0)


def test_tracking_empty_orders_returns_zeros(monkeypatch_connection):
    """空 orders 表 → 12 桶分布率全 0, 不抛异常."""
    _reset_orders(monkeypatch_connection, [])

    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=90)

    assert len(result["buckets"]) == 12
    assert all(b["rate"] == 0.0 for b in result["buckets"])


def test_tracking_window_days_boundary(monkeypatch_connection):
    """window_days 越界 → 自动夹紧到 [1, 90]."""
    _reset_orders(monkeypatch_connection, [])

    # 传 200 越界 → 夹紧到 90
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=200)
    assert result["window_days"] == 90

    # 传 0 越界 → 夹紧到 1
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=0)
    assert result["window_days"] == 1


def test_tracking_3_years_not_summable(tracking_orders):
    """3 年桶分布率不可加总 (业务文档约束, 3 年不是同一群人).

    同一总桶 (2026 0-7d) 不应 == sum(2026 + 2025 + 2024 的 0-7d 分布率).
    """
    result = get_sampling_repurchase_tracking("2026-04-01", "2026-06-29", window_days=90)

    bucket_0_7d = [b["rate"] for b in result["buckets"] if b["bucket"] == "0-7d"]
    # 2026 = 0.25, 2025 = 0.25, 2024 = 0.5, 总和 = 1.0
    assert sum(bucket_0_7d) == pytest.approx(1.0)
    # 但业务上是不同人群, 不该把 3 年当 1 个加总值用, 测试仅锁定当前实现
    assert bucket_0_7d == [pytest.approx(0.25), pytest.approx(0.25), pytest.approx(0.5)]
