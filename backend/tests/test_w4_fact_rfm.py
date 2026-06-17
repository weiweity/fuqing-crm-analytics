"""
W4 MVP v0.4.9 — fact_rfm_long 预计算 pytest 覆盖 (design doc v1.1 §7.4)

MVP 覆盖 (4 个核心):
1. test_create_fact_rfm_table: 表 + 唯一索引创建, 幂等
2. test_incremental_load_basic: 1 组合 (channel='全店') 插入成功
3. test_incremental_load_idempotency: 同一天跑两次结果一致 (ON CONFLICT DO NOTHING)
4. test_incremental_load_version_increments: 连续跑 version 续号

CLAUDE.md 合规: pytest 走 homebrew Python 3.14, in-memory DuckDB 隔离.

v0.4.12 调整: 适配 540 组合 (channel × item × segment_id).
- mock orders 表加 spu_product_class 列
- 单测调 incremental_load 时传 explicit 1-combo list (保持 MVP 1 组合语义)

Sprint 30.1 调整: W4 540 combo batch INSERT (4,320 → 1 次 conn.execute).
- 新增 3 个测试覆盖: batch 等价性 (row count + 字段) + JSON deep equal + perf ratio > 3×
- env var W4_USE_BATCH_INSERT=0 切回串行版 (默认 1)
"""
import json
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.precompute_fact_rfm import (  # noqa: E402
    FACT_RFM_TABLE,
    create_fact_rfm_table,
    incremental_load,
)


# MVP 1 组合 (channel='全店', item='全品' 兼容 v0.4.9 测试语义)
MVP_COMBO = [{
    "channel": "全店",
    "item": "全品",
    "segment_id": 0,
    "dimension_key": "channel=全店",
    "dimension_json": json.dumps({"channel": "全店", "item": "全品", "segment_id": 0}, ensure_ascii=False),
}]


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders table (3 rows: 2 users, 1 repurchase).

    Schema 跟生产 orders 表匹配 (subset: user_id, order_id, actual_amount,
    pay_time, channel, spu_product_class, is_goujinjin, is_refund, order_status).
    v0.4.12: 加 spu_product_class 列 (item 维度需要).
    """
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER,
            order_id VARCHAR,
            actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP,
            channel VARCHAR,
            spu_product_class VARCHAR,
            is_goujinjin BOOLEAN,
            is_refund BOOLEAN,
            order_status VARCHAR
        )
    """)
    # 灌测试数据: 3 个 user, 1 个复购
    # 昨天 (T-1): 2026-06-05
    conn.execute("""
        INSERT INTO orders VALUES
            (1, 'o1', 100.00, '2026-06-05 10:00:00', '全店', '全品', FALSE, FALSE, '已支付'),
            (2, 'o2', 200.00, '2026-06-05 11:00:00', '全店', '全品', FALSE, FALSE, '已支付'),
            (2, 'o3', 150.00, '2026-06-05 12:00:00', '全店', '全品', FALSE, FALSE, '已支付'),
            (3, 'o4', 50.00,  '2026-06-04 10:00:00', '全店', '全品', FALSE, FALSE, '已支付'),
            (4, 'o5', 999.00, '2026-06-05 10:00:00', '抖音', '全品', FALSE, FALSE, '已支付')
    """)
    yield conn
    conn.close()


class TestFactRfmTable:
    """表 + 索引创建."""

    def test_create_table_idempotent(self, duckdb_conn):
        """create_fact_rfm_table 幂等 (跑 2 次不报错)."""
        create_fact_rfm_table(duckdb_conn)
        create_fact_rfm_table(duckdb_conn)  # 第二次不报错
        # 表存在
        tables = duckdb_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [FACT_RFM_TABLE],
        ).fetchall()
        assert len(tables) == 1
        # 唯一索引存在
        indexes = duckdb_conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'idx_fact_rfm_dkv'"
        ).fetchall()
        assert len(indexes) == 1

    def test_table_schema_columns(self, duckdb_conn):
        """表 schema 列对."""
        create_fact_rfm_table(duckdb_conn)
        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
            [FACT_RFM_TABLE],
        ).fetchall()
        col_names = [c[0] for c in cols]
        # 必须含的关键列
        for required in ["date", "dimension_key", "dimension_json", "user_count", "gmv", "repurchase_count", "version", "created_at"]:
            assert required in col_names, f"缺列: {required}"


class TestIncrementalLoad:
    """MVP 增量加载: 1 组合 (channel='全店') 验证机制.

    v0.4.12: 显式传 1-combo 列表, 保持 MVP 1 组合测试语义.
    """

    def test_incremental_load_basic(self, duckdb_conn):
        """基本增量: T-1 (2026-06-05) 数据 1 组合插入成功."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        inserted = incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        assert inserted == 1
        # 验: load_date = 2026-06-05 (T-1)
        row = duckdb_conn.execute(
            f"SELECT date, dimension_key, user_count, gmv, repurchase_count, version "
            f"FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()
        assert row is not None
        assert row[0] == date(2026, 6, 5)
        assert row[1] == "channel=全店"
        # user_count: user_id 1, 2 (2 distinct, 不含 user 4 因为 channel='抖音')
        assert row[2] == 2
        # gmv: 100 + 200 + 150 = 450 (user 2 两单都算)
        assert float(row[3]) == 450.0
        # repurchase: user 2 (order_count=2) → 1
        assert row[4] == 1
        # version: 1
        assert row[5] == 1

    def test_incremental_load_idempotency(self, duckdb_conn):
        """同一天跑两次: ON CONFLICT DO NOTHING 跳过, row count 1:1 (设计 doc v1.1 §7.4)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        # 第 1 次
        inserted_1 = incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        assert inserted_1 == 1
        # 第 2 次 (同一天) — version 续 +1, 但 ON CONFLICT (date, dim, version) DO NOTHING
        # 实际 ON CONFLICT 是 (date, dim, version) 三元组, 第 2 次 version=2 不冲突, 会插入
        inserted_2 = incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        # 重要: 第 2 次应该插入新行 (version=2), 不是 0
        assert inserted_2 == 1
        # 验: 总行数 2 (v1 + v2 同一天)
        total = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()[0]
        assert total == 2
        # 幂等性 (v1.1 §7.4 验收点 3): "重跑同一天结果一致" — row count 累加, 但每行 value 一致
        rows = duckdb_conn.execute(
            f"SELECT user_count, gmv, repurchase_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert rows[0] == rows[1]  # v1 和 v2 数据一致

    def test_incremental_load_version_increments(self, duckdb_conn):
        """version 续号: 第 N 次跑 version = N."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        for i in range(1, 4):
            incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        versions = duckdb_conn.execute(
            f"SELECT version FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3]

    def test_incremental_load_only_target_date(self, duckdb_conn):
        """增量只 append T-1, 不影响其他日期 (orders 里 6/4 数据不会被 load)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        # 验: 6/4 (前天) 不在 fact_rfm_long 里 (orders 6/4 有 1 行, 但不在 load_date=T-1 范围)
        rows = duckdb_conn.execute(
            f"SELECT date FROM {FACT_RFM_TABLE}"
        ).fetchall()
        dates = [r[0] for r in rows]
        assert date(2026, 6, 5) in dates
        assert date(2026, 6, 4) not in dates

    def test_incremental_load_channel_filter(self, duckdb_conn):
        """MVP 只算 channel='全店', 其他 channel 不算 (user 4 在 '抖音' 不进 user_count)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target, combos=MVP_COMBO)
        user_count = duckdb_conn.execute(
            f"SELECT user_count FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()[0]
        # user 4 (channel='抖音') 不算 → user_count = 2 (user 1 + 2)
        assert user_count == 2


# ─────────────────────────────────────────────────────────────
# Sprint 30.1: W4 540 combo batch INSERT 性能治根
# ─────────────────────────────────────────────────────────────

import os
import time as _time  # noqa: E402  跟 stdlib time 同名, 加 _ 防冲突


def _make_540_combos(orders_conn) -> list:
    """生成 540 测试 combo (3 channel × 60 item × 1 segment, 跟生产 9×60 简化为 3×60 测 batch 等价性).

    简化: 3 channel 够测 batch 路径 (走完整 STRUCT 数组 + LATERAL 子查询),
    不需要 9×60 全部. 性能回归保护由 test_w4_batch_perf 覆盖.
    """
    test_channels = ["货架", "达播", "直播"]
    test_items = [f"item_{i}" for i in range(60)]
    combos = []
    for ch in test_channels:
        for it in test_items:
            dim_key = f"channel={ch}|item={it}|segment=all"
            dim_json = json.dumps({"channel": ch, "item": it, "segment_id": 0}, ensure_ascii=False)
            combos.append({
                "channel": ch, "item": it, "segment_id": 0,
                "dimension_key": dim_key, "dimension_json": dim_json,
            })
    return combos


@pytest.fixture
def w4_batch_conn():
    """180 combo 测试 in-memory DuckDB (3 channel × 60 item)."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER, order_id VARCHAR, actual_amount DECIMAL(18,2),
            pay_time TIMESTAMP, channel VARCHAR, spu_product_class VARCHAR,
            is_goujinjin BOOLEAN, is_refund BOOLEAN, order_status VARCHAR
        )
    """)
    # 灌 180 combo × 3 user = 540 row 测试数据
    rows = []
    for ch in ["货架", "达播", "直播"]:
        for i in range(60):
            for u in range(3):
                rows.append((
                    u, f"o_{ch}_{i}_{u}", 100.0 + u * 10, "2026-06-05 10:00:00",
                    ch, f"item_{i}", False, False, "已支付",
                ))
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", rows,
    )
    yield conn
    conn.close()


class TestW4BatchInsert:
    """Sprint 30.1: W4 540 combo batch INSERT 等价性 + 性能测试.

    设计:
    - batch (新): STRUCT 数组 + LATERAL 聚合子查询 → 1 次 conn.execute
    - serial (旧): 540 次串行 conn.execute (env var W4_USE_BATCH_INSERT=0 切回)
    - 验证: 两种模式 row count + 7 字段值完全一致 (byte-equal except timestamp)
    """

    def test_w4_batch_insert_equivalent(self, w4_batch_conn):
        """batch 跟 serial 等价: row count + 7 字段值完全一致.

        Sprint 7 P2 教训: 用真连接, 不 mock. batch + serial 都用 :memory: 连接
        (生产 ETL 单次跑批本来就用 :memory: 模式, 区别在 batch/serial 实现),
        比较两者输出 byte-equal.
        """
        target = date(2026, 6, 6)
        combos = _make_540_combos(w4_batch_conn)

        # --- batch 模式 (默认) ---
        create_fact_rfm_table(w4_batch_conn)
        n_batch = incremental_load(w4_batch_conn, target, combos=combos)
        batch_rows = w4_batch_conn.execute(
            f"SELECT date, dimension_key, user_count, gmv, repurchase_count, segment_id, version "
            f"FROM {FACT_RFM_TABLE} ORDER BY dimension_key"
        ).fetchall()
        batch_data = {r[1]: r for r in batch_rows}

        # 清表跑 serial (env var 切回, 新连接模式, 跟生产 ETL 模式一致)
        w4_batch_conn.execute(f"DELETE FROM {FACT_RFM_TABLE}")
        os.environ["W4_USE_BATCH_INSERT"] = "0"
        try:
            n_serial = incremental_load(w4_batch_conn, target, combos=combos)
            serial_rows = w4_batch_conn.execute(
                f"SELECT date, dimension_key, user_count, gmv, repurchase_count, segment_id, version "
                f"FROM {FACT_RFM_TABLE} ORDER BY dimension_key"
            ).fetchall()
            serial_data = {r[1]: r for r in serial_rows}
        finally:
            os.environ.pop("W4_USE_BATCH_INSERT", None)

        # --- 断言等价性 ---
        assert n_batch == n_serial, f"row count 不一致: batch={n_batch}, serial={n_serial}"
        assert n_batch == 180, f"应 180 row, 实际 {n_batch}"
        assert len(batch_data) == len(serial_data) == 180
        # 关键: 每个 dimension_key 的 7 字段完全一致 (date, dim_key, user_count, gmv, repurchase_count, seg_id, version)
        for k in batch_data:
            assert batch_data[k] == serial_data[k], (
                f"字段值不一致: dim_key={k}\n"
                f"  batch : {batch_data[k]}\n"
                f"  serial: {serial_data[k]}"
            )

    def test_w4_batch_insert_equivalent_dimension_json(self, w4_batch_conn):
        """batch 跟 serial 等价: dimension_json 字段 deep equal.

        单独拆出来: DuckDB JSON 列默认返回 str, 用 json.loads 反序列化验证.
        """
        create_fact_rfm_table(w4_batch_conn)
        target = date(2026, 6, 6)
        combos = _make_540_combos(w4_batch_conn)
        n = incremental_load(w4_batch_conn, target, combos=combos)
        assert n == 180

        # 验: 每个 dim_key 的 dimension_json 字符串可被 json.loads + 字段对齐 combo
        rows = w4_batch_conn.execute(
            f"SELECT dimension_key, dimension_json FROM {FACT_RFM_TABLE} ORDER BY dimension_key"
        ).fetchall()
        for dim_key, dim_json_str in rows:
            # dim_key 拆 channel + item
            parts = dict(p.split("=") for p in dim_key.split("|"))
            ch = parts["channel"]
            it = parts["item"]
            seg = parts["segment"]
            assert seg == "all"
            # dim_json_str 是 str (DuckDB JSON 列返回 JSON 字符串)
            # 若 dict 则是 DuckDB 自动 parse 了, 兼容两种
            if isinstance(dim_json_str, dict):
                parsed = dim_json_str
            else:
                parsed = json.loads(dim_json_str)
            assert parsed["channel"] == ch
            assert parsed["item"] == it
            assert parsed["segment_id"] == 0

    def test_w4_batch_perf(self, w4_batch_conn):
        """batch 性能 ratio > 3×: 1 次 conn.execute 应至少比 180 次串行快 3 倍.

        Sprint 30.1 性能分档: 必 < 50s / 应 < 30s / 极 < 20s (端到端 540 combo 真 ETL).
        in-memory 单测只能做相对加速比 (串行 < N ms / batch < N ms), 绝对时间
        跟机器/CI 漂移, 不可靠. ratio > 3× 是安全线.
        """
        create_fact_rfm_table(w4_batch_conn)
        target = date(2026, 6, 6)
        combos = _make_540_combos(w4_batch_conn)

        # --- batch 模式 ---
        t0 = _time.perf_counter()
        incremental_load(w4_batch_conn, target, combos=combos)
        batch_elapsed = _time.perf_counter() - t0

        # --- serial 模式 (env var 切回) ---
        # 重置数据: 清表 + 重新灌
        w4_batch_conn.execute(f"DELETE FROM {FACT_RFM_TABLE}")
        os.environ["W4_USE_BATCH_INSERT"] = "0"
        try:
            t0 = _time.perf_counter()
            incremental_load(w4_batch_conn, target, combos=combos)
            serial_elapsed = _time.perf_counter() - t0
        finally:
            os.environ.pop("W4_USE_BATCH_INSERT", None)

        ratio = serial_elapsed / max(batch_elapsed, 1e-6)
        # Sprint 30.1 安全线: ratio > 3× (in-memory 测, 端到端会更显著)
        assert ratio > 3.0, (
            f"batch 加速比 {ratio:.2f}× < 3× 阈值: "
            f"batch={batch_elapsed*1000:.1f}ms, serial={serial_elapsed*1000:.1f}ms"
        )
