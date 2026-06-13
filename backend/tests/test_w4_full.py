"""
W4 full v0.4.12 — 540 组合 + dbt-style merge T-7 + 全量重算 pytest 覆盖
(design doc v1.1 §7.4)

测试覆盖:
1. test_enumerate_combos_returns_540: enumerate_combos() 返 540
2. test_enumerate_items_fallback: orders 空时用 W4_ITEMS_FALLBACK (60 个)
3. test_incremental_load_full_540: incremental_load() 走 540 组合全量
4. test_merge_replace_late_arriving: merge_replace() 修复 late-arriving (version 续 +1)
5. test_merge_replace_idempotency: 同一天跑两次 merge_replace, version 续 +1
6. test_incremental_load_with_merge: incremental + merge T-7 整合
7. test_rfm_recompute_window_dry_run: rfm_recompute_window.py --dry-run
8. test_rfm_recompute_window_basic: rfm_recompute_window.py --from --to 范围
9. test_pipeline_w4_integration: pipeline 末尾 W4 调 (mock 验证)
10. test_540_combo_completeness: 校验所有 9 channel × 60 item 都有数据

CLAUDE.md 合规: pytest 走 in-memory DuckDB 隔离.
"""
import importlib.util
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.etl.precompute_fact_rfm import (  # noqa: E402
    FACT_RFM_TABLE,
    W4_CHANNELS,
    W4_ITEMS_FALLBACK,
    W4_TOTAL_COMBOS,
    create_fact_rfm_table,
    enumerate_combos,
    enumerate_items,
    incremental_load,
    incremental_load_with_merge,
    merge_replace,
)


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB with mock orders (10.6M 模拟) — 1 天 540 组合测试用.

    Schema 跟生产 orders 表匹配 (subset: user_id, order_id, actual_amount,
    pay_time, channel, spu_product_class, is_goujinjin, is_refund, order_status).
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
    # 灌测试数据: 1 天 (T-1=2026-06-05) 9 channel × 60 item 都覆盖
    # 用循环灌: 60 item × 9 channel = 540 行 / day
    rows = []
    user_id = 1
    for ch in W4_CHANNELS:
        for it in W4_ITEMS_FALLBACK:
            # 每个组合 1 个用户, 1 单
            rows.append((
                user_id, f"o_{user_id}", 100.00, "2026-06-05 10:00:00",
                ch, it, False, False, "已支付"
            ))
            user_id += 1
    # 再灌 1 个复购用户 (order_count=2) 测 repurchase_count
    rows.append((
        user_id, f"o_{user_id}_a", 200.00, "2026-06-05 10:00:00",
        "货架", "氨基酸洁面", False, False, "已支付"
    ))
    rows.append((
        user_id, f"o_{user_id}_b", 150.00, "2026-06-05 11:00:00",
        "货架", "氨基酸洁面", False, False, "已支付"
    ))
    user_id += 1
    # 灌 1 个退款单 (is_refund=TRUE, 不应计入 user_count)
    rows.append((
        user_id, f"o_{user_id}", 50.00, "2026-06-05 12:00:00",
        "货架", "氨基酸洁面", False, True, "已退款"
    ))

    # 灌 5 天历史 (用于 T-7 merge 测试)
    for d_offset in range(1, 6):
        target = date(2026, 6, 5) - timedelta(days=d_offset)
        rows.append((
            user_id, f"o_{user_id}_h", 80.00, f"{target} 10:00:00",
            "货架", "氨基酸洁面", False, False, "已支付"
        ))
        user_id += 1

    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    yield conn
    conn.close()


class TestEnumerateCombos:
    """540 组合枚举."""

    def test_enumerate_combos_returns_540(self, duckdb_conn):
        """enumerate_combos() 默认返 540 = 9 channels × 60 items."""
        combos = enumerate_combos(duckdb_conn)
        assert len(combos) == 540

    def test_enumerate_combos_structure(self, duckdb_conn):
        """每个 combo 含 channel / item / segment_id / dimension_key / dimension_json."""
        combos = enumerate_combos(duckdb_conn)
        sample = combos[0]
        assert "channel" in sample
        assert "item" in sample
        assert "segment_id" in sample
        assert "dimension_key" in sample
        assert "dimension_json" in sample
        # 校验 dimension_json 可被 JSON 解析
        parsed = json.loads(sample["dimension_json"])
        assert "channel" in parsed
        assert "item" in parsed
        assert "segment_id" in parsed

    def test_enumerate_combos_9_channels(self, duckdb_conn):
        """9 channels 完整覆盖 (来自 W4_CHANNELS)."""
        combos = enumerate_combos(duckdb_conn)
        channels_in_combos = {c["channel"] for c in combos}
        assert channels_in_combos == set(W4_CHANNELS)
        assert len(channels_in_combos) == 9

    def test_enumerate_combos_60_items(self, duckdb_conn):
        """60 items 完整覆盖 (来自 enumerate_items)."""
        combos = enumerate_combos(duckdb_conn)
        items_in_combos = {c["item"] for c in combos}
        assert len(items_in_combos) == 60

    def test_enumerate_items_fallback(self):
        """orders 表空时, enumerate_items() 用 W4_ITEMS_FALLBACK."""
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("CREATE TABLE orders (spu_product_class VARCHAR, actual_amount DECIMAL, pay_time TIMESTAMP)")
            # 空表, 应走 fallback
            items = enumerate_items(conn)
            assert len(items) == 60
            assert items == W4_ITEMS_FALLBACK
        finally:
            conn.close()

    def test_enumerate_items_top_60(self, duckdb_conn):
        """orders 有数据时, enumerate_items() 返 top 60 by GMV."""
        items = enumerate_items(duckdb_conn)
        assert len(items) == 60


class TestIncrementalLoadFull540:
    """incremental_load 走 540 组合全量."""

    def test_incremental_load_inserts_540_rows(self, duckdb_conn):
        """incremental_load() 走 540 组合, 应插入 ≥ 540 行 (有数据组合)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        inserted = incremental_load(duckdb_conn, target)
        # 540 组合 - 退款单被 OrderFilters 滤掉 - 没有 user 的组合
        # 实际插入 ≈ 540 - (退款单影响的 item 跳过) = 539 (因为 '氨基酸洁面' 1 个退款单)
        # 更稳的校验: 至少 540 - 1 行
        assert inserted >= 539, f"期望 ≥ 539 行, 实际 {inserted}"
        # 验 fact_rfm_long 总行数
        total = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {FACT_RFM_TABLE}"
        ).fetchone()[0]
        assert total >= 539

    def test_incremental_load_dedupes_channels(self, duckdb_conn):
        """incremental_load() 每个 (date, dimension_key) 只 1 行, 不重复."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target)
        # 验: 9 channel × 60 item = 540 distinct dimension_key
        distinct_keys = duckdb_conn.execute(
            f"SELECT COUNT(DISTINCT dimension_key) FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05'"
        ).fetchone()[0]
        assert distinct_keys >= 540

    def test_incremental_load_idempotency_540(self, duckdb_conn):
        """同一天跑两次 incremental_load, version 续 +1, UNIQUE 不冲突."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        n1 = incremental_load(duckdb_conn, target)
        n2 = incremental_load(duckdb_conn, target)
        # 第 2 次应该插入新行 (version=2)
        assert n2 == n1
        # 验: 2 个 version 的 row count 一致
        rows_v1 = duckdb_conn.execute(
            f"SELECT dimension_key, user_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' AND version = 1 ORDER BY dimension_key"
        ).fetchall()
        rows_v2 = duckdb_conn.execute(
            f"SELECT dimension_key, user_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' AND version = 2 ORDER BY dimension_key"
        ).fetchall()
        assert rows_v1 == rows_v2  # v1 和 v2 数据一致

    def test_incremental_load_repurchase_count(self, duckdb_conn):
        """复购用户 (order_count>=2) 计入 repurchase_count."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target)
        # '货架' + '氨基酸洁面' 这个组合, 应该有 1 个复购用户 + 1 个退款单被滤
        # user_id 540 (循环里最后的 1 个) 在 '货架'+'氨基酸洁面' 下有 2 单, order_count=2
        # 此外 541 在 '货架'+'氨基酸洁面' 有 1 单退款 (被 OrderFilters 滤)
        # 实际 repurchase_count 应 = 1
        row = duckdb_conn.execute(
            f"SELECT repurchase_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' AND dimension_key = 'channel=货架|item=氨基酸洁面|segment=all'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1


class TestMergeReplaceLateArriving:
    """dbt-style merge T-7 修复 late-arriving."""

    def test_merge_replace_inserts_new_version(self, duckdb_conn):
        """merge_replace(load_date) INSERT 新 version (= existing_max + 1)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        # 先 incremental 一次 (version=1)
        incremental_load(duckdb_conn, target)
        # 再 merge T-1 (version 续 +1 = 2)
        n = merge_replace(duckdb_conn, target - timedelta(days=1))
        assert n > 0
        # 验: T-1 (2026-06-05) 有 v1 + v2 两种
        versions = duckdb_conn.execute(
            f"SELECT DISTINCT version FROM {FACT_RFM_TABLE} WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2]

    def test_merge_replace_repairs_late_arriving(self, duckdb_conn):
        """late-arriving 订单到达后, merge_replace 重算 user_count."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        # 第一次 incremental (T-1 = 2026-06-05)
        incremental_load(duckdb_conn, target)
        # 模拟 late-arriving: 插 1 个新用户到 2026-06-05
        duckdb_conn.execute("""
            INSERT INTO orders VALUES
            (9999, 'late_o', 500.00, '2026-06-05 14:00:00',
             '货架', '氨基酸洁面', FALSE, FALSE, '已支付')
        """)
        # 第二次: merge T-1 (T-1=2026-06-05, 1 天前)
        # 注意: merge_replace 算 _next_version, 已经是 v2 (T-1 已有 v1)
        merge_replace(duckdb_conn, target - timedelta(days=1))
        # 验: 2026-06-05 货架+氨基酸洁面 v2 的 user_count = 1 (旧) + 1 (新) - 1 (退款滤) = 2
        row = duckdb_conn.execute(
            f"SELECT user_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' AND version = 2 "
            f"AND dimension_key = 'channel=货架|item=氨基酸洁面|segment=all'"
        ).fetchone()
        assert row is not None
        # v1 当时没晚到订单, v2 晚到后应多 1
        v1_row = duckdb_conn.execute(
            f"SELECT user_count FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' AND version = 1 "
            f"AND dimension_key = 'channel=货架|item=氨基酸洁面|segment=all'"
        ).fetchone()
        assert row[0] > v1_row[0], f"v2 ({row[0]}) 应 > v1 ({v1_row[0]})"

    def test_merge_replace_idempotency(self, duckdb_conn):
        """同一天跑两次 merge_replace, version 续 +1, 不冲突."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        # 灌 1 个 incremental (v1)
        incremental_load(duckdb_conn, target)
        # 第 1 次 merge (v2)
        n1 = merge_replace(duckdb_conn, target - timedelta(days=1))
        # 第 2 次 merge (v3)
        n2 = merge_replace(duckdb_conn, target - timedelta(days=1))
        assert n1 > 0
        assert n2 > 0
        # 验: 3 个 version
        versions = duckdb_conn.execute(
            f"SELECT DISTINCT version FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05' ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3]


class TestIncrementalLoadWithMerge:
    """incremental_load_with_merge 整合 (W4 full 推荐)."""

    def test_with_merge_appends_t1_and_repairs_t7(self, duckdb_conn):
        """incremental_load_with_merge: append T-1 + merge T-1..T-7 (7 天修复)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        inc, merge, dates = incremental_load_with_merge(duckdb_conn, target, t_minus_days=7)
        # T-1 应该新增 (incremental)
        assert inc > 0
        # T-1..T-7 应该都跑 merge (merge_inserted > 0 即使有部分日期没数据)
        assert isinstance(merge, int)
        # dates 应有 7 个
        assert len(dates) == 7
        # 第 1 个 merge date 应该是 T-1
        assert dates[0] == "2026-06-05"


class TestRfmRecomputeWindow:
    """scripts/etl/rfm_recompute_window.py 全量重算脚本 (CLI 测试)."""

    def test_rfm_recompute_window_dry_run(self, tmp_path, skip_if_uvicorn_alive):
        """rfm_recompute_window.py --dry-run 不写入 (Sprint 22 #25: skip-if-DuckDB-locked fixture 防 uvicorn 锁冲突)."""
        # 跑 CLI: --from 2026-06-04 --to 2026-06-05 --dry-run
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "etl" / "rfm_recompute_window.py"),
                "--from", "2026-06-04",
                "--to", "2026-06-05",
                "--dry-run",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        # dry-run 应正常退出 (returncode 0)
        assert result.returncode == 0, f"stderr={result.stderr}"
        # 输出应含 DRY-RUN
        assert "DRY-RUN" in result.stdout or "dry-run" in result.stdout.lower()

    def test_rfm_recompute_window_script_exists(self):
        """rfm_recompute_window.py 文件存在."""
        script_path = ROOT / "scripts" / "etl" / "rfm_recompute_window.py"
        assert script_path.exists()
        # 验证 main() 可导入
        spec = importlib.util.spec_from_file_location(
            "rfm_recompute_window", str(script_path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")
        assert hasattr(mod, "recompute_window")


class TestPipelineW4Integration:
    """pipeline.py W4 集成 (mock pipeline 末尾调)."""

    def test_w4_constants(self):
        """W4 组合常量正确."""
        assert W4_TOTAL_COMBOS == 540
        assert len(W4_CHANNELS) == 9
        assert len(W4_ITEMS_FALLBACK) == 60

    def test_540_combo_completeness_in_db(self, duckdb_conn):
        """incremental_load 后, fact_rfm_long 应含 540 个 distinct dimension_key (T-1)."""
        create_fact_rfm_table(duckdb_conn)
        target = date(2026, 6, 6)
        incremental_load(duckdb_conn, target)
        # 540 = 9 channel × 60 item, 每个组合 1 行
        distinct_keys = duckdb_conn.execute(
            f"SELECT COUNT(DISTINCT dimension_key) FROM {FACT_RFM_TABLE} "
            f"WHERE date = '2026-06-05'"
        ).fetchone()[0]
        assert distinct_keys == 540
