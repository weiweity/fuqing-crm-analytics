#!/usr/bin/env python3
"""Sprint 10 B2-merged: replay 全表 is_member 从 membership_mark 表.

背景: prod orders 表 is_member 字段长期累积错误. 修法: 用 membership_mark
表 (4.6M unique order_id) JOIN orders UPDATE is_member.

DuckDB 1.5.2 ART index 竞态: 10.6M orders JOIN 4.6M membership_mark 触发
"Corrupted ART index - likely the same row id was inserted twice". 修法:
DROP 6 个 secondary indexes → UPDATE (1.8s) → CREATE INDEX 重建 (19.7s).

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
    print("Sprint 10 B2-merged: replay_is_member (DROP idx → UPDATE → 重建)")
    print("=" * 60)

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
            print(f"  [FAIL] membership_mark 表不存在, 先跑 build_membership_mark.py")
            return 1
        mm_count = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        t_before = conn.execute("SELECT COUNT(*) FROM orders WHERE is_member = TRUE").fetchone()[0]
        print(f"  [现状] membership_mark: {mm_count:,} | orders is_member=T: {t_before:,}")

        # DROP secondary indexes (避 ART index race)
        print(f"\n  [Step 1] DROP 6 secondary indexes (DuckDB 1.5.2 ART race 缓解):")
        for idx in INDEXES_TO_DROP:
            try:
                conn.execute(f"DROP INDEX IF EXISTS {idx}")
                print(f"    [OK] DROP {idx}")
            except Exception as e:
                print(f"    [SKIP] {idx}: {e}")

        # UPDATE
        print(f"\n  [Step 2] UPDATE orders JOIN membership_mark:")
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

        # 重建 indexes
        print(f"\n  [Step 3] 重建 6 secondary indexes:")
        t0 = time.perf_counter()
        for sql in INDEX_RECREATE_SQL:
            try:
                conn.execute(sql)
                idx_name = sql.split("INDEX ")[1].split(" ")[0]
                print(f"    [OK] CREATE {idx_name}")
            except Exception as e:
                print(f"    [FAIL] {sql}: {e}")
        print(f"    总耗时: {time.perf_counter() - t0:.1f}s")

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
