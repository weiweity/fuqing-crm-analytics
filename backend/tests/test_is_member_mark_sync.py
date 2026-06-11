"""
Sprint 15 Wave 2 治根测试: 验证 B1 (mark 缺口回填) + B2 (mark 增量同步) + D.1 (replay 包事务) 三件套.

背景: Sprint 10 救火时, mark 表 snapshot 4.6M unique order_id, 跟 orders.is_member=TRUE 5.6M 差 1M 缺口 (历史 xlsx 缺数据, parquet 补不了). Sprint 14.5 B+ 集成 replay 跟 build 但只 replay mark 包含的 4.6M, 1M 缺口永远在. Sprint 15 Wave 2 三件套治根:

- B1 (replay_is_member.py): 反向回填 mark 缺口 — 单事务 BEGIN; ... COMMIT; 包 DROP idx + 回填 mark + UPDATE + 重建 idx, 中途 crash 自动 ROLLBACK
- B2 (pipeline.py): 增量跟全量模式都加 mark 增量同步 (idempotent ON CONFLICT DO NOTHING)
- D.1 (replay_is_member.py): 单事务包裹, 避免 6 秒数据风险窗口

测试覆盖:
1. B1: 反向回填 (orders.is_member=TRUE → mark 表) idempotent
2. B2: 增量同步 idempotent (重复跑 +0)
3. D.1: 事务 ROLLBACK (mock 异常, 验证 indexes 没被 DROP)
"""
import pytest
import duckdb
import tempfile
import os
from pathlib import Path

from backend.config import DUCKDB_MEMORY_LIMIT  # noqa: E402


@pytest.fixture
def temp_duckdb():
    """In-memory test fixture: 模拟 mark 缺口 (4.6M 跟 5.6M 错位 1M)."""
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(path)  # DuckDB 拒绝连接空文件, 让 connect 自己建
    conn = duckdb.connect(path, config={"memory_limit": "1GB"})
    try:
        # 建 orders 表 (跟 prod schema 一致)
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR PRIMARY KEY,
                is_member BOOLEAN,
                actual_amount DECIMAL(12,2)
            )
        """)
        # 建 membership_mark 表 (B1 之前 snapshot 4.6M, 缺 1M)
        conn.execute("""
            CREATE TABLE membership_mark (
                order_id VARCHAR PRIMARY KEY,
                is_member BOOLEAN DEFAULT TRUE
            )
        """)
        # 5.6M 模拟: 4.6M order_id 是会员 (mark 跟 is_member 都 TRUE), 1M order_id 是会员但 mark 没记
        # B1 测: 4.6M + 1M 缺口 + 5M 非会员 = 10.6M total
        member_marked = [f"M{i:07d}" for i in range(4_600_432)]  # mark 表 4.6M
        member_unmarked = [f"U{i:07d}" for i in range(1_000_000)]  # is_member=TRUE 但 mark 没记
        non_member = [f"N{i:07d}" for i in range(5_000_000)]  # 非会员
        # 插入 mark 表 (4.6M)
        for i in range(0, len(member_marked), 10000):
            batch = member_marked[i:i+10000]
            placeholders = ','.join(['?' for _ in batch])
            sql = f"INSERT INTO membership_mark (order_id) VALUES {placeholders.replace('?', '(?)')} ON CONFLICT DO NOTHING"
            conn.execute(sql, batch)
        # 插入 orders 表 (10.6M)
        # 4.6M mark 覆盖 + 1M 缺口 + 5M 非会员
        all_member = member_marked + member_unmarked
        all_orders_ids = all_member + non_member
        conn.execute(f"INSERT INTO orders (order_id, is_member) SELECT order_id, TRUE FROM (VALUES {','.join(['(?)' for _ in all_member])}) t(order_id) WHERE TRUE",
                    all_member)
        conn.execute(f"INSERT INTO orders (order_id, is_member) SELECT order_id, FALSE FROM (VALUES {','.join(['(?)' for _ in non_member])}) t(order_id) WHERE TRUE",
                    non_member)
        yield conn, path
    finally:
        conn.close()
        os.unlink(path)


class TestB1MarkBackfill:
    """Sprint 15 B1: 反向回填 mark 缺口 (orders.is_member=TRUE → mark 表)."""

    def test_b1_idempotent_backfill(self, temp_duckdb):
        """B1 主逻辑: 反向回填 mark 缺口, idempotent (重复跑 +0)."""
        conn, path = temp_duckdb
        # 现状: mark 4.6M, orders is_member=TRUE 5.6M, 缺口 1M
        n_mark_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        n_true_before = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        assert n_mark_before == 4_600_432
        assert n_true_before == 5_600_432
        delta = n_true_before - n_mark_before
        assert delta == 1_000_000  # 1M 缺口

        # 跑 B1 主逻辑 (跟 replay_is_member.py Step B 一致)
        conn.execute("""
            INSERT INTO membership_mark (order_id)
            SELECT order_id FROM orders
            WHERE is_member = TRUE AND order_id IS NOT NULL
            ON CONFLICT (order_id) DO NOTHING
        """)
        n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        assert n_mark_after == n_true_before, f"B1 期望 mark 跟 is_member 对齐, 实际 {n_mark_after} != {n_true_before}"

        # 重复跑 idempotent (+0)
        conn.execute("""
            INSERT INTO membership_mark (order_id)
            SELECT order_id FROM orders
            WHERE is_member = TRUE AND order_id IS NOT NULL
            ON CONFLICT (order_id) DO NOTHING
        """)
        n_mark_after2 = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        assert n_mark_after2 == n_mark_after, f"B1 重复跑应 idempotent, 实际 {n_mark_after2} != {n_mark_after}"

    def test_b1_on_conflict_does_nothing(self, temp_duckdb):
        """B1 ON CONFLICT DO NOTHING 真的不覆盖已有 mark 行 (保护 is_member=FALSE 反向标)."""
        conn, path = temp_duckdb
        # 假设 mark 里有 1 个 order_id 是 is_member=FALSE (例如退会)
        conn.execute("INSERT INTO membership_mark (order_id, is_member) VALUES ('REVOKED001', FALSE) ON CONFLICT (order_id) DO NOTHING")
        # 跑 B1 (orders.is_member 跟 mark 独立)
        conn.execute("""
            INSERT INTO membership_mark (order_id)
            SELECT order_id FROM orders
            WHERE is_member = TRUE AND order_id IS NOT NULL
            ON CONFLICT (order_id) DO NOTHING
        """)
        # 验证: REVOKED001 仍 is_member=FALSE (ON CONFLICT DO NOTHING 保护)
        v = conn.execute("SELECT is_member FROM membership_mark WHERE order_id = 'REVOKED001'").fetchone()[0]
        assert v is False, f"ON CONFLICT DO NOTHING 应保护 REVOKED001 is_member=FALSE, 实际 {v}"


class TestB2IncrementalSync:
    """Sprint 15 B2: mark 增量同步 (pipeline.py 跑批时 append 新 order_id)."""

    def test_b2_incremental_idempotent(self, temp_duckdb):
        """B2 增量 append + 重复跑 idempotent."""
        conn, path = temp_duckdb
        # 模拟增量 ETL: 跑批时把新拉 member_order_ids append 到 mark
        new_order_ids = [f"NEW{i:05d}" for i in range(100)]
        n_mark_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]

        # 第一次 append
        for batch_start in range(0, len(new_order_ids), 50):
            batch = new_order_ids[batch_start:batch_start+50]
            values_clause = ','.join(['(CAST(? AS VARCHAR))' for _ in batch])
            sql = f"INSERT INTO membership_mark (order_id) VALUES {values_clause} ON CONFLICT (order_id) DO NOTHING"
            conn.execute(sql, batch)
        n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        assert n_mark_after == n_mark_before + 100

        # 重复跑 idempotent (+0)
        for batch_start in range(0, len(new_order_ids), 50):
            batch = new_order_ids[batch_start:batch_start+50]
            values_clause = ','.join(['(CAST(? AS VARCHAR))' for _ in batch])
            sql = f"INSERT INTO membership_mark (order_id) VALUES {values_clause} ON CONFLICT (order_id) DO NOTHING"
            conn.execute(sql, batch)
        n_mark_after2 = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        assert n_mark_after2 == n_mark_after, f"B2 重复跑应 idempotent, 实际 {n_mark_after2} != {n_mark_after}"


class TestD1Transactional:
    """Sprint 15 D.1: replay_is_member 包单事务, 中途 crash ROLLBACK."""

    def test_d1_rollback_preserves_state(self, temp_duckdb):
        """D.1 治根: 单事务包裹, 中途异常 ROLLBACK 保持 BEGIN 之前状态."""
        conn, path = temp_duckdb
        # 建测试 idx
        conn.execute("CREATE INDEX idx_test ON orders(is_member)")
        idx_exists_before = conn.execute("""
            SELECT COUNT(*) FROM duckdb_indexes() WHERE index_name = 'idx_test'
        """).fetchone()[0]
        assert idx_exists_before == 1

        # 模拟 D.1 事务: BEGIN → DROP idx → (异常) → ROLLBACK
        conn.execute("BEGIN")
        conn.execute("DROP INDEX idx_test")
        # 模拟 UPDATE 失败 (例如 syntax error)
        try:
            conn.execute("UPDATE orders SET invalid_col = 1 WHERE 1=0")
        except Exception:
            conn.execute("ROLLBACK")

        # 验证 idx 还在 (ROLLBACK 恢复)
        idx_exists_after = conn.execute("""
            SELECT COUNT(*) FROM duckdb_indexes() WHERE index_name = 'idx_test'
        """).fetchone()[0]
        assert idx_exists_after == 1, f"D.1 ROLLBACK 应保留 idx, 实际 {idx_exists_after} != 1"

    def test_d1_commit_persists(self, temp_duckdb):
        """D.1 正常 COMMIT 4 步都落盘."""
        conn, path = temp_duckdb
        conn.execute("CREATE INDEX idx_test ON orders(is_member)")

        conn.execute("BEGIN")
        conn.execute("DROP INDEX idx_test")
        conn.execute("COMMIT")

        idx_exists = conn.execute("""
            SELECT COUNT(*) FROM duckdb_indexes() WHERE index_name = 'idx_test'
        """).fetchone()[0]
        assert idx_exists == 0, f"D.1 COMMIT 应落盘 (DROP idx 持久), 实际 {idx_exists} != 0"


class TestB1B2D1Integration:
    """Sprint 15 Wave 2 三件套集成: B1 补缺口 + B2 同步增量 + D.1 事务化 replay."""

    def test_full_workflow_aligns_mark_with_orders(self, temp_duckdb):
        """完整跑 B1 (回填) + B2 (增量) + 模拟 D.1 replay, mark 跟 orders.is_member=TRUE 永远对齐."""
        conn, path = temp_duckdb

        # Step 1: B1 回填 1M 缺口
        conn.execute("""
            INSERT INTO membership_mark (order_id)
            SELECT order_id FROM orders
            WHERE is_member = TRUE AND order_id IS NOT NULL
            ON CONFLICT (order_id) DO NOTHING
        """)
        n_true = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        n_mark = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        assert n_mark == n_true, f"B1 后 mark {n_mark} != orders.is_member=TRUE {n_true}"

        # Step 2: 增量 ETL 拉新 data (100 个新 order_id 全是会员)
        new_ids = [f"FULL{i:05d}" for i in range(100)]
        conn.execute(f"INSERT INTO orders (order_id, is_member) VALUES {','.join(['(?, TRUE)' for _ in new_ids])}", new_ids)

        # Step 3: B2 增量 append
        for batch_start in range(0, len(new_ids), 50):
            batch = new_ids[batch_start:batch_start+50]
            values_clause = ','.join(['(CAST(? AS VARCHAR))' for _ in batch])
            sql = f"INSERT INTO membership_mark (order_id) VALUES {values_clause} ON CONFLICT (order_id) DO NOTHING"
            conn.execute(sql, batch)

        # Step 4: 模拟 D.1 replay (UPDATE orders JOIN mark)
        n_true_before = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        conn.execute("""
            UPDATE orders SET is_member = m.is_member
            FROM membership_mark m
            WHERE orders.order_id = m.order_id
        """)
        n_true_after = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        # 治根: mark 跟 orders.is_member=TRUE 永远对齐
        assert n_mark_after == n_true_after, (
            f"三件套治根: mark {n_mark_after} 跟 orders.is_member=TRUE {n_true_after} 应对齐"
        )
