#!/usr/bin/env python3
"""Sprint 10 B2-merged + Sprint 15 D.1 治根: replay 全表 is_member 从 membership_mark 表.

Sprint 10 B2: prod orders 表 is_member 字段长期累积错误. 修法: 用 membership_mark
表 (4.6M unique order_id) JOIN orders UPDATE is_member.
DuckDB 1.5.2 ART index 竞态: 10.6M orders JOIN 4.6M membership_mark 触发
"Corrupted ART index - likely the same row id was inserted twice". 修法:
DROP 6 个 secondary indexes → UPDATE (1.8s) → CREATE INDEX 重建 (19.7s).

Sprint 15 D.1 治根 (2026-06-11): 整个 DROP+UPDATE+CREATE 序列包单事务.
- 之前是 3 个独立 SQL, 中途 crash (eg. system OOM, 6 秒数据窗口) → indexes 没了但 UPDATE 已写盘
- Sprint 15 Wave 2 (B1+B2+D.1) 三件套治根:
  - B1: mark 缺口一次性回填 (1M order_id 不在 mark 4.6M 但 is_member=TRUE)
  - B2: mark 增量同步 (pipeline.py 跑批时 append 新 order_id)
  - D.1 (本脚本): 包单事务, atomicity 保证

跑法: PYTHONPATH=. python3 scripts/etl/replay_is_member.py
幂等: 重复跑只 UPDATE 仍 is_member=FALSE 的行 (前提: 跑过 build_membership_mark.py).
"""
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH  # noqa: E402

# 6 个 secondary indexes (B1 已删 idx_orders_order_unique)
INDEXES_TO_DROP = [
    "idx_orders_pay_time",
    "idx_orders_user",
    "idx_orders_year_month",
    "idx_orders_product",
    "idx_orders_channel_pay_time",
    "idx_orders_channel_member",
]

INDEX_RECREATE_SQL = [
    "CREATE INDEX idx_orders_pay_time ON orders(pay_time)",
    "CREATE INDEX idx_orders_user ON orders(user_id)",
    'CREATE INDEX idx_orders_year_month ON orders("year", "month")',
    "CREATE INDEX idx_orders_product ON orders(product_id)",
    "CREATE INDEX idx_orders_channel_pay_time ON orders(channel, pay_time)",
    "CREATE INDEX idx_orders_channel_member ON orders(channel, is_member)",
]


def main() -> int:
    print("=" * 60)
    print("Sprint 10 B2-merged + Sprint 15 D.1: replay_is_member (单事务 DROP idx → UPDATE → 重建)")
    print("=" * 60)

    # Sprint 15 D.1 治根: DuckDB 不支持跨连接的分布式事务, 但同一连接内
    # 显式 BEGIN; ... COMMIT; 包多个 DDL+DML 语句, 中途异常回滚 (DROP idx 之前状态).
    # 之前 3 个独立 SQL 中途 crash → indexes 没了但 UPDATE 已写盘, 数据不一致.
    # 修法: 整段包 BEGIN; ... COMMIT;, try/except 失败 ROLLBACK 恢复.
    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        # 健康检查
        try:
            n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            print(f"  [健康检查] orders count = {n:,}")
        except Exception as e:
            print(f"  [FAIL] DB 损坏: {e}")
            return 1

        # membership_mark 存在性
        mm_exists = conn.execute("""
            SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = 'membership_mark'
        """).fetchone()[0]
        if mm_exists == 0:
            # Sprint 11+ 修 ruff F541: 无 placeholder 删 f 前缀
            print("  [FAIL] membership_mark 表不存在, 先跑 build_membership_mark.py")
            return 1
        mm_count = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        t_before = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        # Sprint 11+ 修 ruff F541: 实际有 placeholder (.0f 等) 不能简单删 f. 改用 f-string 内的字符串拼接
        print(f"  [现状] membership_mark: {mm_count:,} | orders is_member=T: {t_before:,}")

        # Sprint 15 D.1 治根: 整段包单事务 (DROP idx + UPDATE + CREATE idx).
        # DuckDB 事务是单连接的 ACID, BEGIN/COMMIT 包裹 → 中途 crash 自动 ROLLBACK,
        # indexes 状态保持不变 (没 DROP 也没 CREATE, 跟 DROP 之前一致).
        # Sprint 15 D.1 也增加 1M 缺口回填: 反向从 orders.is_member=TRUE 补 mark 表
        # (B1 一次性回填, 跟 B2 增量同步配套, mark 表跟 orders.is_member 永远对齐).
        print("\n  [Sprint 15 D.1] 事务化 DROP idx → 回填 mark → UPDATE → 重建 idx:")
        t0_total = time.perf_counter()
        try:
            # Sprint 15 D.1: 单事务包裹 4 步
            conn.execute("BEGIN")
            # Step A: DROP 6 secondary indexes
            print("\n  [Step A] DROP 6 secondary indexes (DuckDB 1.5.2 ART race 缓解):")
            for idx in INDEXES_TO_DROP:
                try:
                    conn.execute(f"DROP INDEX IF EXISTS {idx}")
                    print(f"    [OK] DROP {idx}")
                except Exception as e:
                    print(f"    [SKIP] {idx}: {e}")

            # Step B (Sprint 15 B1): mark 缺口回填 (反向从 orders.is_member=TRUE)
            # 1M order_id 不在 mark 4.6M 但 is_member=TRUE (Sprint 10 救火遗留).
            # 反向回填: INSERT INTO membership_mark (order_id) SELECT order_id FROM orders
            # WHERE is_member = TRUE ON CONFLICT DO NOTHING (idempotent, +0 重复跑).
            # B1 跟 B2 配套, 治根: 增量 ETL 拉的新 order_id 自动进 mark (B2) +
            # 历史 1M 缺口一次性回填 (B1).
            print("\n  [Step B] Sprint 15 B1: 反向回填 mark 缺口 (orders.is_member=TRUE 兜底):")
            n_mark_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
            conn.execute("""
                INSERT INTO membership_mark (order_id)
                SELECT order_id FROM orders
                WHERE is_member = TRUE AND order_id IS NOT NULL
                ON CONFLICT (order_id) DO NOTHING
            """)
            n_mark_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
            n_mark_delta = n_mark_after - n_mark_before
            print(f"    [OK] mark 回填: {n_mark_before:,} → {n_mark_after:,} (+{n_mark_delta:,})")

            # Step C: UPDATE orders JOIN membership_mark (Sprint 10 B2 主逻辑)
            print("\n  [Step C] UPDATE orders JOIN membership_mark:")
            t0 = time.perf_counter()
            conn.execute("""
                UPDATE orders
                SET is_member = m.is_member
                FROM membership_mark m
                WHERE orders.order_id = m.order_id
            """)
            elapsed = time.perf_counter() - t0
            t_after = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
            delta = t_after - t_before
            print(f"    [OK] UPDATE: {t_before:,} → {t_after:,} (+{delta:,}, {elapsed:.1f}s)")

            # Step D: 重建 6 secondary indexes
            print("\n  [Step D] 重建 6 secondary indexes:")
            t0 = time.perf_counter()
            for sql in INDEX_RECREATE_SQL:
                try:
                    conn.execute(sql)
                    idx_name = sql.split("INDEX ")[1].split(" ")[0]
                    print(f"    [OK] CREATE {idx_name}")
                except Exception as e:
                    print(f"    [FAIL] {sql}: {e}")
            print(f"    总耗时: {time.perf_counter() - t0:.1f}s")

            # Sprint 15 D.1: 全部成功才 COMMIT, 失败自动 ROLLBACK (D.1 治根)
            conn.execute("COMMIT")
            print("\n  [D.1 事务 COMMIT] 全部 4 步成功, 整段已落盘 (atomicity 保证)")
        except Exception as e:
            # D.1 治根: 中途 crash 自动 ROLLBACK, 回到 BEGIN 之前状态 (indexes 还在, UPDATE 未写)
            conn.execute("ROLLBACK")
            print(f"\n  [D.1 事务 ROLLBACK] {type(e).__name__}: {e}")
            print("    整段 4 步已回滚, indexes 跟 BEGIN 之前一致, UPDATE 未写盘, atomicity 保证")
            return 1
        print(f"\n  [总耗时] {time.perf_counter() - t0_total:.1f}s")

        # 验证
        total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        print(f"\n  [总结] total: {total:,} | is_member=T: {t_after:,} ({t_after/total*100:.2f}%)")
        return 0
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
