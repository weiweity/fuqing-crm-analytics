#!/usr/bin/env python3
"""Sprint 10 B2-merged: 从 78 个 member parquet 重建 membership_mark 表.

背景: prod orders 表 is_member 字段长期累积错误 (2020-2026 全部 False, 跟源
数据不符). 根因: 78 个 member parquet (data/parquet/member/) 覆盖 4.6M unique
order_id, 但 ETL 增量跑批时 member_order_ids 加载逻辑 (pipeline.py:154) 在
跑批时拿不到 4-6 月增量数据对应的会员标记.

B2-merged 修法: CREATE TABLE membership_mark (order_id PRIMARY KEY) 持久表
+ 从 78 parquet 用 DuckDB-native read_parquet 加载 4.6M + JOIN UPDATE 修
is_member (DROP secondary indexes → UPDATE 1.8s → 重建 indexes 19.7s).

跑法: PYTHONPATH=. python3 scripts/etl/build_membership_mark.py
幂等: 用 INSERT INTO ... SELECT DISTINCT, 重复跑只 INSERT 缺失的.
"""
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.config import DUCKDB_MEMORY_LIMIT, DUCKDB_PATH  # noqa: E402

MEMBER_DIR = Path("data/parquet/member")


def main() -> int:
    print("=" * 60)
    print("Sprint 10 B2-merged: build_membership_mark")
    print("=" * 60)

    conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": DUCKDB_MEMORY_LIMIT})
    try:
        # 1. CREATE TABLE IF NOT EXISTS
        conn.execute("""
            CREATE TABLE IF NOT EXISTS membership_mark (
                order_id VARCHAR PRIMARY KEY,
                is_member BOOLEAN DEFAULT TRUE,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        n_before = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        print(f"  [现状] membership_mark rows: {n_before:,}")

        # 2. DuckDB-direct read_parquet (10-100x 快于 pd.read_parquet + executemany)
        parquet_glob = str(MEMBER_DIR / "*.parquet")
        t0 = time.perf_counter()
        n_inserted = conn.execute(f"""
            INSERT INTO membership_mark (order_id)
            SELECT DISTINCT CAST(order_id AS VARCHAR)
            FROM read_parquet('{parquet_glob}')
            WHERE order_id IS NOT NULL
            ON CONFLICT (order_id) DO NOTHING
        """).fetchone()
        elapsed = time.perf_counter() - t0
        n_after = conn.execute("SELECT COUNT(*) FROM membership_mark").fetchone()[0]
        print(f"  [OK] 加载: {n_before:,} → {n_after:,} (+{n_after - n_before:,}, {elapsed:.1f}s)")
        return 0
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
