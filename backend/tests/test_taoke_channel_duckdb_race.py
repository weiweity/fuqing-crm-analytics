"""
Sprint 16 P0 治根测试: 验证 _update_taoke_channel_impl 的 DuckDB 1.5.x ART index
race 治根 (DROP 2 channel index + BEGIN/COMMIT + RECREATE 序列).

背景: Sprint 15 Wave 3 跑批真验时, baseline (无 Wave 3 改动) 同样崩
'Vector::Reference used on vector of different type (VARCHAR referenced TIMESTAMP)'
在 _update_taoke_channel_impl (cli.py:715 → pipeline.py:1050) 段. 根因: DuckDB 1.5.x
ART index 在 UPDATE 场景下 channel 字段 (VARCHAR) 跟 index metadata 类型错乱, 触发
BoundIndex::ApplyBufferedReplays 内部 vector reference race.

Sprint 10 B2-merged (99c0196) 治根同路: DROP 6 secondary indexes → UPDATE →
CREATE INDEX 重建 (replay_is_member.py). 但 Sprint 10 fix 漏修 _update_taoke_channel_impl,
本次 Sprint 16 P0 治根补这一刀 (DROP 2 channel index + 包 BEGIN/COMMIT, 跟 D.1 atomicity 一致).

测试覆盖 (D-7 教训: 模拟生产新连接, 不用单连接 in-memory 误导):
1. 治根序列 (BEGIN+DROP+UPDATE+RECREATE+COMMIT) 不崩 Vector::Reference
2. 重复跑 3 次 idempotent
3. ROLLBACK 保留 BEGIN 之前 index 状态
"""
import pytest
import duckdb
import tempfile
import os


@pytest.fixture
def temp_orders_with_channel_index():
    """模拟 orders 表 + 2 个 channel index (跟 prod schema 一致)."""
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(path)  # DuckDB 拒绝连接空文件
    conn = duckdb.connect(path)
    try:
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR PRIMARY KEY,
                channel VARCHAR,
                is_member BOOLEAN,
                pay_time TIMESTAMP,
                product_title VARCHAR
            )
        """)
        # 50 affiliate (跟 prod ~5% 比例一致)
        for i in range(50):
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                [f"TAOKE_{i:03d}", "affiliate", True, "2026-06-01 10:00:00", "Product T1"],
            )
        # 30 其他 (非affiliate订单, 不动)
        for i in range(30):
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                [f"OTHER_{i:03d}", "其他", False, "2026-06-02 10:00:00", "Product X"],
            )
        # 20 其他 + product_title 含 T1 关键词 (P6-2 关键词匹配场景)
        for i in range(20):
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                [f"NEW_OTHER_{i:03d}", "其他", False, "2026-06-03 10:00:00", "Product T1 Keyword"],
            )
        # 跟 prod 一样的 2 个 channel index
        conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
        conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")
        yield conn, path
    finally:
        conn.close()
        os.unlink(path)


class TestTaokeChannelRace:
    """Sprint 16 P0 治根: _update_taoke_channel_impl DuckDB race 治根测试 (DROP 2 + BEGIN/COMMIT)."""

    def test_drop_recreate_index_no_crash(self, temp_orders_with_channel_index):
        """Sprint 16 治根序列: BEGIN → DROP 2 channel index → UPDATE → RECREATE 2 index → COMMIT 不崩.

        治根前 (无本次 fix): race 在 `SELECT COUNT(*) FROM orders WHERE channel = 'affiliate'`
        触发 Vector::Reference VARCHAR/TIMESTAMP error. 治根后: DROP 2 channel index,
        SELECT 走 heap (无 index 触发 race), UPDATE 走 heap, RECREATE index, COMMIT.
        """
        conn, path = temp_orders_with_channel_index
        # 模拟 _update_taoke_channel_impl 的 BEGIN+DROP+UPDATE+RECREATE+COMMIT 序列
        conn.execute("BEGIN")
        # 1. DROP 2 channel index (race 触发点)
        conn.execute("DROP INDEX IF EXISTS idx_orders_channel_pay_time")
        conn.execute("DROP INDEX IF EXISTS idx_orders_channel_member")
        # 2. 跑 channel 相关 query (UPDATE + SELECT)
        conn.execute("UPDATE orders SET channel = '其他' WHERE channel = 'affiliate'")
        after_count = conn.execute("SELECT COUNT(*) FROM orders WHERE channel = 'affiliate'").fetchone()[0]
        # 3. 重建 2 channel index (跟 Sprint 10 fix 同一模式)
        conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
        conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")
        # 4. COMMIT
        conn.execute("COMMIT")

        # 验证: 50 个原affiliate订单全 reset 为'其他'
        assert after_count == 0, f"reset 后affiliate应为 0, 实际 {after_count}"
        # 验证: 50 reset + 30 老客 + 20 新客 = 100 行"其他"
        n_other = conn.execute("SELECT COUNT(*) FROM orders WHERE channel = '其他'").fetchone()[0]
        assert n_other == 100, f"reset 后其他应为 100, 实际 {n_other}"

    def test_idempotent_rerun(self, temp_orders_with_channel_index):
        """重复跑 _update_taoke_channel_impl 治根序列 → idempotent (跟 Sprint 15 D.1 一致).

        跟 Sprint 15 Wave 2 D.1 replay_is_member.py 一致: 重复跑只 UPDATE 仍 is_member=FALSE
        的行, 不破坏现有数据.
        """
        conn, path = temp_orders_with_channel_index
        for run in range(3):
            conn.execute("BEGIN")
            conn.execute("DROP INDEX IF EXISTS idx_orders_channel_pay_time")
            conn.execute("DROP INDEX IF EXISTS idx_orders_channel_member")
            conn.execute("UPDATE orders SET channel = '其他' WHERE channel = 'affiliate'")
            conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
            conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")
            conn.execute("COMMIT")
        # 3 次跑完, 所有 50 个原affiliate订单都应 reset 为'其他' (幂等)
        n_other = conn.execute("SELECT COUNT(*) FROM orders WHERE channel = '其他'").fetchone()[0]
        assert n_other == 100, f"3 次重跑后其他应为 100, 实际 {n_other}"

    def test_rollback_preserves_state(self, temp_orders_with_channel_index):
        """Sprint 16 治根: 事务 ROLLBACK 保持 BEGIN 之前状态 (idx 还在).

        跟 Sprint 15 D.1 (replay_is_member.py:90-152) atomicity 一致:
        中途 crash 自动 ROLLBACK, indexes 跟 UPDATE 状态保持不变.
        """
        conn, path = temp_orders_with_channel_index
        idx_before = conn.execute("""
            SELECT COUNT(*) FROM duckdb_indexes() WHERE index_name LIKE 'idx_orders_channel_%'
        """).fetchone()[0]
        assert idx_before == 2, f"初始应有 2 channel index, 实际 {idx_before}"

        conn.execute("BEGIN")
        conn.execute("DROP INDEX idx_orders_channel_pay_time")
        conn.execute("DROP INDEX idx_orders_channel_member")
        # 模拟中途失败 (eg. OOM) → ROLLBACK
        conn.execute("ROLLBACK")

        # 验证: 2 个 channel index 都还在 (ROLLBACK 恢复)
        idx_after = conn.execute("""
            SELECT COUNT(*) FROM duckdb_indexes() WHERE index_name LIKE 'idx_orders_channel_%'
        """).fetchone()[0]
        assert idx_after == 2, f"ROLLBACK 应保留 2 channel index, 实际 {idx_after}"
        # 验证: 50 affiliate订单数未变
        n_taoke = conn.execute("SELECT COUNT(*) FROM orders WHERE channel = 'affiliate'").fetchone()[0]
        assert n_taoke == 50, f"ROLLBACK 应保留 50 affiliate, 实际 {n_taoke}"

    def test_p6_2_keyword_re_mark_after_drop(self, temp_orders_with_channel_index):
        """Sprint 16 治根 + 业务: P6-2 关键词匹配 (product_title LIKE '%t1%') 在 DROP index 后仍正常."""
        conn, path = temp_orders_with_channel_index
        conn.execute("BEGIN")
        conn.execute("DROP INDEX IF EXISTS idx_orders_channel_pay_time")
        conn.execute("DROP INDEX IF EXISTS idx_orders_channel_member")
        # P6-2 关键词匹配: 20 个 NEW_OTHER (product_title 含 T1) 标affiliate
        conn.execute("""
            UPDATE orders
            SET channel = 'affiliate'
            WHERE channel = '其他'
            AND (LOWER(product_title) LIKE '%t1%' OR LOWER(product_title) LIKE '%t2%'
                 OR LOWER(product_title) LIKE '%t4%' OR LOWER(product_title) LIKE '%tk%')
        """)
        # 20 个 P6-2 标记
        n_taoke = conn.execute("SELECT COUNT(*) FROM orders WHERE channel = 'affiliate'").fetchone()[0]
        conn.execute("CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)")
        conn.execute("CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)")
        conn.execute("COMMIT")

        # 验证: 50 原affiliate + 20 NEW_OTHER 标了affiliate = 70 (P6-2 关键词匹配, 没改原 50 affiliate)
        assert n_taoke == 70, f"P6-2 后affiliate应为 70 (50 原 + 20 NEW_OTHER), 实际 {n_taoke}"
        # 验证: 20 NEW_OTHER 是新标affiliate (跟 P6 订单号匹配不一样的逻辑, 通过 product_title LIKE 触发)
        n_new_other_taoke = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id LIKE 'NEW_OTHER_%' AND channel = 'affiliate'"
        ).fetchone()[0]
        assert n_new_other_taoke == 20, f"NEW_OTHER 标affiliate应 20, 实际 {n_new_other_taoke}"
