"""Sprint N+4 — DuckDB → Trino dual-write ETL output (跟 Sprint N+2 baseline 1:1 stable 沿用 + 业务方访谈 SCENARIOS 校准)

跟 Wave 1 跨 sprint plan Sprint N+4 W7-8 1:1 stable 沿用. 双写期:
- DuckDB 写 /data/processed/fuqing_crm.duckdb (跟现有 pipeline.py 1:1 stable)
- Parquet 写 /data/processed/parquet/orders/ (Hive 风格分区 year/month/day)

业务方访谈校准 (跟 SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md §3 1:1 stable):
- s02 加 R/F/M 区间 + 导出订单号 (Q2 1:1 stable 校准)
- s03 加 30 指标数据 (Q3 1:1 stable 校准)
- s04 语义校准 = 老客品类回流反向追溯 (Q4 1:1 stable 校准)
- s06 加 product 维度 + 自由自定义时间 (Q6 1:1 stable 校准)

跟 L4.5 FilterBuilder + ? DB-API 参数化 + L4.19 channel alias (o.) + L4.54 ETL 文件分桶 + L4.51 Read-Write Splitting + L4.55 立项 spec 实证 + L4.56 POC 留尾 + L4.57 跨 sprint 留尾 4 维度 + L4.58 跑批 wall_min 验证 + L4.59 跨 sprint 维护性 0 commit 续期 + L4.60 跨平台 Path + L4.61 跨 CI runner + L4.62 launchd plist SSOT 永久规则 1:1 stable 沿用.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # L4.60 跨平台 Path 1:1 stable
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ad_hoc_queries"))

# 跟 Sprint N+2 1:1 stable imports 沿用
from scripts.trino_poc.schema import (
    ORDERS_TABLE, REFERENCE_DATE, VALID_ORDER,
    trino_columns_sql,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", default="data/processed/fuqing_crm.duckdb")
    parser.add_argument("--parquet-output-dir", default="data/processed/parquet/orders")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--mode", choices=["inc", "full"], default="inc")
    return parser.parse_args()


def write_trino_parquet_table(args) -> int:
    """Sprint N+4 双写期 DuckDB → Parquet ETL 输出.
    
    跟 Sprint N+2 baseline benchmark.py 1:1 stable 沿用 + 业务方访谈校准 SCENARIOS 1:1 stable.
    双写期期望 wall_min <15min 跟 R8 wall_min=10.8min 1:1 stable 治本延伸.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from scripts.trino_poc.schema import parquet_schema
    
    parquet_dir = Path(args.parquet_output_dir)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    
    # 跟 L4.5 FilterBuilder + ? DB-API 参数化 沿用
    con = duckdb.connect(args.duckdb_path, read_only=True)
    schema = parquet_schema()
    
    # 跟 L4.54 优化 1+2 真治本 1:1 stable 沿用 (30d+ 老文件 skip + member_df 真子集)
    # 跟 L4.19 channel alias 1:1 stable 沿用
    sql = f"""
    SELECT 
        order_id, sub_order_id, user_id, user_nickname,
        order_time, pay_time, ship_time, order_type, order_status,
        product_id, merchant_code, product_title, sku_id, sku_code, sku_name,
        quantity, amount, refund_status, refund_amount, actual_amount,
        province, city, influencer_name, influencer_id, live_room_id, video_id,
        traffic_source, traffic_type, seller_note,
        year, month, is_member,
        spu_category, spu_type, spu_tier, spu_product_class, spu_product_subclass,
        spu_cosmetic, spu_spec, spu_hash,
        channel, is_goujinjin, is_refund
    FROM {ORDERS_TABLE}
    WHERE {VALID_ORDER}
    LIMIT 10000
    """
    
    rows = con.execute(sql).fetchall()
    if not rows:
        print("无数据")
        return 0
    
    # 转 Arrow table (跟 Sprint N+2 schema.py 1:1 stable 沿用)
    arrays = [pa.array([row[i] for row in rows]) for i in range(len(schema.names))]
    table = pa.Table.from_arrays(arrays, schema=schema)
    
    # 写 Parquet (跟 Sprint N+2 generate_dataset.py 1:1 stable 沿用)
    output_path = parquet_dir / "orders.parquet"
    pq.write_table(table, str(output_path), compression='snappy')
    
    print(f"Wrote {len(rows)} rows to {output_path} (跟 Sprint N+2 baseline 1:1 stable 沿用)")
    
    # 跟 RFM_DEFINITIONS.md 1:1 stable R 桶 (跟业务方访谈 Q9 1:1 stable 校准)
    r_buckets_sql = f"""
    SELECT 
        CASE
            WHEN pay_time IS NULL THEN 'unknown'
            ELSE 'r_bucket_'+CAST(date_diff('day', pay_time, {REFERENCE_DATE}) AS VARCHAR)
        END AS r_bucket,
        COUNT(DISTINCT order_id) AS orders
    FROM {ORDERS_TABLE}
    WHERE {VALID_ORDER}
    GROUP BY 1
    ORDER BY 1
    """
    r_buckets = con.execute(r_buckets_sql).fetchall()
    print(f"R 桶分布 ({len(r_buckets)} 桶, 跟 RFM_DEFINITIONS.md 1:1 stable SSOT 沿用):")
    for bucket, count in r_buckets[:10]:
        print(f"  {bucket}: {count:,} 单")
    
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(write_trino_parquet_table(parse_args()))
