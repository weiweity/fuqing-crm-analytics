#!/usr/bin/env python3
"""
benchmark_50m.py — 从现有 sample_crm.duckdb 采样分布，生成 50M 行模拟订单数据。

策略：
  1. 从源库采样字段分布（枚举值 + 权重、用户ID、产品组合、地理、日期等）
  2. 用 Numpy 向量化 + 加权随机 批量生成数据
  3. 以 Parquet 文件为中间格式，DuckDB COPY 导入目标表

用法：python3 scripts/etl/benchmark_50m.py
输出：data/processed/sample_crm_50m.duckdb（不修改原始数据库）
"""

import os
import sys
import time
import shutil
import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb

# ── 路径 ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
SRC_DB = ROOT / "data" / "processed" / "sample_crm.duckdb"
DST_DB = ROOT / "data" / "processed" / "sample_crm_50m.duckdb"
PARQUET_DIR = ROOT / "data" / "processed" / "_bench_parquet"

TARGET_ROWS = 50_000_000
BATCH_SIZE = 5_000_000  # 每批写入行数
PROGRESS_STEP = 10_000_000


# ── 辅助函数 ──────────────────────────────────────────────────────
def pct(part, total):
    return f"{part / total * 100:.1f}%"


def fmt_size(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def weighted_choice_np(vals, weights, k, rng):
    """用 numpy 做加权随机选择，返回 object array[k]"""
    probs = np.array(weights, dtype=np.float64)
    probs /= probs.sum()
    indices = rng.choice(len(vals), size=k, p=probs)
    return vals[indices]


# ── 主流程 ──────────────────────────────────────────────────────────
def main():
    if not SRC_DB.exists():
        print(f"错误: 源数据库不存在: {SRC_DB}", file=sys.stderr)
        sys.exit(1)

    # 清理旧文件
    if DST_DB.exists():
        os.unlink(DST_DB)
    for suffix in (".wal", ".tmp"):
        p = DST_DB.with_suffix(DST_DB.suffix + suffix)
        if p.exists():
            os.unlink(p)
    if PARQUET_DIR.exists():
        shutil.rmtree(PARQUET_DIR)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    t_total_start = time.time()

    # ── 1. 从源库采样分布 ──────────────────────────────────────────
    print("[1/4] 读取源数据库字段分布 ...")
    t0 = time.time()

    tmp_copy = ROOT / "data" / "processed" / "_benchmark_tmp.duckdb"
    shutil.copy2(SRC_DB, tmp_copy)
    src = duckdb.connect(str(tmp_copy), read_only=True)

    # 枚举型字段采样
    enum_fields = {
        "channel":        "SELECT channel, count(*) FROM orders GROUP BY channel",
        "order_type":     "SELECT order_type, count(*) FROM orders GROUP BY order_type",
        "order_status":   "SELECT order_status, count(*) FROM orders GROUP BY order_status",
        "refund_status":  "SELECT refund_status, count(*) FROM orders GROUP BY refund_status",
        "spu_category":   "SELECT spu_category, count(*) FROM orders GROUP BY spu_category",
        "spu_type":       "SELECT spu_type, count(*) FROM orders GROUP BY spu_type",
        "spu_tier":       "SELECT spu_tier, count(*) FROM orders GROUP BY spu_tier",
        "spu_product_class":    "SELECT spu_product_class, count(*) FROM orders GROUP BY spu_product_class",
        "spu_product_subclass": "SELECT spu_product_subclass, count(*) FROM orders GROUP BY spu_product_subclass",
        "spu_cosmetic":   "SELECT spu_cosmetic, count(*) FROM orders GROUP BY spu_cosmetic",
    }

    distributions = {}
    for field, sql in enum_fields.items():
        rows = src.execute(sql).fetchall()
        vals = []
        weights = []
        for v, cnt in rows:
            vals.append(v)  # 保留 None
            weights.append(cnt)
        distributions[field] = (np.array(vals, dtype=object), weights)
        print(f"  {field}: {len(vals)} 个值")

    # user_id 列表（采样 20 万，足以循环覆盖 50M 行）
    print("  采样 user_id ...")
    user_rows = src.execute(
        "SELECT DISTINCT user_id FROM orders "
        "USING SAMPLE 200000 ROWS"
    ).fetchall()
    # 如果采样太少，回退到全量
    if len(user_rows) < 10000:
        user_rows = src.execute("SELECT DISTINCT user_id FROM orders").fetchall()
    user_ids = np.array([r[0] for r in user_rows], dtype=object)
    print(f"  {len(user_ids):,} 个唯一用户")

    # product/sku 组合 (用 DISTINCT 获取全部，行数少)
    print("  采样 product/sku 组合 ...")
    product_combos = src.execute(
        "SELECT DISTINCT product_id, sku_id, sku_code, sku_name, merchant_code, "
        "spu_spec, spu_hash, product_title FROM orders WHERE product_id IS NOT NULL"
    ).fetchall()
    print(f"  {len(product_combos):,} 个 product/sku 组合")

    # 省份/城市
    print("  采样 省份/城市 ...")
    geo_rows = src.execute(
        "SELECT province, city, count(*) as cnt FROM orders "
        "WHERE province IS NOT NULL AND city IS NOT NULL "
        "GROUP BY province, city ORDER BY cnt DESC"
    ).fetchall()
    geo_vals = np.array([(r[0], r[1]) for r in geo_rows], dtype=object)
    geo_weights = [r[2] for r in geo_rows]
    print(f"  {len(geo_vals):,} 个省份/城市组合")

    # year/month 分布 (过滤 NULL)
    year_rows = src.execute("SELECT year, count(*) FROM orders WHERE year IS NOT NULL GROUP BY year ORDER BY year").fetchall()
    year_vals = np.array([r[0] for r in year_rows])
    year_weights = [r[1] for r in year_rows]

    month_rows = src.execute("SELECT month, count(*) FROM orders WHERE month BETWEEN 1 AND 12 GROUP BY month ORDER BY month").fetchall()
    month_vals = np.array([r[0] for r in month_rows])
    month_weights = [r[1] for r in month_rows]

    # 布尔概率
    total_src = src.execute("SELECT count(*) FROM orders").fetchone()[0]
    member_pct = src.execute("SELECT count(*) FROM orders WHERE is_member = true").fetchone()[0] / total_src
    goujinjin_pct = src.execute("SELECT count(*) FROM orders WHERE is_goujinjin = true").fetchone()[0] / total_src
    refund_bool_pct = src.execute("SELECT count(*) FROM orders WHERE is_refund = true").fetchone()[0] / total_src

    src.close()
    os.unlink(tmp_copy)

    # 转换 product_combos 为 numpy 结构化数组以便快速索引
    prod_arr = np.array(product_combos, dtype=object)

    print(f"  字段分布读取完成 ({time.time() - t0:.1f}s)")

    # ── 2. 创建目标数据库和表 ──────────────────────────────────────
    print("[2/4] 创建目标数据库 ...")
    t0 = time.time()

    con = duckdb.connect(str(DST_DB))
    con.execute("""
        CREATE TABLE orders (
            order_id             VARCHAR,
            sub_order_id         VARCHAR,
            user_id              VARCHAR,
            user_nickname        VARCHAR,
            order_time           TIMESTAMP,
            pay_time             TIMESTAMP,
            ship_time            TIMESTAMP,
            order_type           VARCHAR,
            order_status         VARCHAR,
            product_id           VARCHAR,
            merchant_code        VARCHAR,
            product_title        VARCHAR,
            sku_id               VARCHAR,
            sku_code             VARCHAR,
            sku_name             VARCHAR,
            quantity             INTEGER,
            amount               DECIMAL(12,2),
            refund_status        VARCHAR,
            refund_amount        DECIMAL(12,2),
            actual_amount        DECIMAL(12,2),
            province             VARCHAR,
            city                 VARCHAR,
            influencer_name      VARCHAR,
            influencer_id        VARCHAR,
            live_room_id         VARCHAR,
            video_id             VARCHAR,
            traffic_source       VARCHAR,
            traffic_type         VARCHAR,
            seller_note          VARCHAR,
            year                 INTEGER,
            month                INTEGER,
            is_member            BOOLEAN,
            spu_category         VARCHAR,
            spu_type             VARCHAR,
            spu_tier             VARCHAR,
            spu_product_class    VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic         VARCHAR,
            spu_spec             VARCHAR,
            spu_hash             VARCHAR,
            channel              VARCHAR,
            is_goujinjin         BOOLEAN,
            is_refund            BOOLEAN
        )
    """)
    print(f"  表创建完成 ({time.time() - t0:.1f}s)")

    # ── 3. 分批生成 Parquet → COPY 导入 ────────────────────────────
    print(f"[3/4] 生成 {TARGET_ROWS:,} 行数据 (batch={BATCH_SIZE:,}) ...")
    t0 = time.time()
    written = 0
    next_progress = PROGRESS_STEP
    batch_num = 0
    pq_files = []

    rng = np.random.default_rng(seed=42)

    while written < TARGET_ROWS:
        batch_n = min(BATCH_SIZE, TARGET_ROWS - written)
        batch_num += 1
        offset = written

        # user_id: 循环使用
        user_indices = np.arange(offset, offset + batch_n) % len(user_ids)
        batch_user_id = user_ids[user_indices]
        batch_user_nickname = np.array([f"user_{uid[-6:]}" for uid in batch_user_id], dtype=object)

        # order_id / sub_order_id
        order_offsets = np.arange(offset, offset + batch_n)
        batch_order_id = np.array([f"BENCH{i:012d}" for i in order_offsets], dtype=object)
        batch_sub_order_id = np.array([f"BENCH{i:012d}_1" for i in order_offsets], dtype=object)

        # 枚举字段加权采样
        batch_channel = weighted_choice_np(*distributions["channel"], batch_n, rng)
        batch_order_type = weighted_choice_np(*distributions["order_type"], batch_n, rng)
        batch_order_status = weighted_choice_np(*distributions["order_status"], batch_n, rng)
        batch_refund_status = weighted_choice_np(*distributions["refund_status"], batch_n, rng)
        batch_spu_category = weighted_choice_np(*distributions["spu_category"], batch_n, rng)
        batch_spu_type = weighted_choice_np(*distributions["spu_type"], batch_n, rng)
        batch_spu_tier = weighted_choice_np(*distributions["spu_tier"], batch_n, rng)
        batch_spu_product_class = weighted_choice_np(*distributions["spu_product_class"], batch_n, rng)
        batch_spu_product_subclass = weighted_choice_np(*distributions["spu_product_subclass"], batch_n, rng)
        batch_spu_cosmetic = weighted_choice_np(*distributions["spu_cosmetic"], batch_n, rng)

        # product 组合
        prod_indices = rng.integers(0, len(prod_arr), size=batch_n)
        batch_product_id = prod_arr[prod_indices, 0]
        batch_sku_id = prod_arr[prod_indices, 1]
        batch_sku_code = prod_arr[prod_indices, 2]
        batch_sku_name = prod_arr[prod_indices, 3]
        batch_merchant_code = prod_arr[prod_indices, 4]
        batch_spu_spec = prod_arr[prod_indices, 5]
        batch_spu_hash = prod_arr[prod_indices, 6]
        batch_product_title = prod_arr[prod_indices, 7]

        # 省份/城市 加权采样
        geo_indices = weighted_choice_np(
            np.arange(len(geo_vals)), geo_weights, batch_n, rng
        )
        batch_province = geo_vals[geo_indices, 0]
        batch_city = geo_vals[geo_indices, 1]

        # year / month 加权采样
        batch_year = weighted_choice_np(year_vals, year_weights, batch_n, rng).astype(int)
        batch_month = weighted_choice_np(month_vals, month_weights, batch_n, rng).astype(int)

        # 日期生成: 按 year/month 生成 day/hour/min/sec
        # 安全计算每月天数（处理 m=12 时 m+1=13 的边界）
        def _days_in_month(y, m):
            if m == 12:
                return 31
            return (_dt.date(int(y), int(m) + 1, 1) - _dt.date(int(y), int(m), 1)).days

        days_in_month = np.array([_days_in_month(y, m) for y, m in zip(batch_year, batch_month)])
        batch_day = rng.integers(1, days_in_month + 1)
        batch_hour = rng.integers(0, 24, size=batch_n)
        batch_minute = rng.integers(0, 60, size=batch_n)
        batch_second = rng.integers(0, 60, size=batch_n)

        # pay_time
        batch_pay_time = np.array([
            _dt.datetime(int(y), int(m), int(d), int(h), int(mi), int(s))
            for y, m, d, h, mi, s in zip(
                batch_year, batch_month, batch_day, batch_hour, batch_minute, batch_second)
        ], dtype='datetime64[ns]')

        # order_time = pay_time - 0~60 分钟
        offset_minutes = rng.integers(0, 61, size=batch_n).astype('timedelta64[m]')
        batch_order_time = batch_pay_time - offset_minutes

        # ship_time: 70% 有值
        has_ship = rng.random(batch_n) < 0.7
        ship_offset_days = rng.integers(0, 8, size=batch_n).astype('timedelta64[D]')
        ship_offset_hours = rng.integers(0, 24, size=batch_n).astype('timedelta64[h]')
        batch_ship_time = np.where(
            has_ship,
            batch_pay_time + ship_offset_days + ship_offset_hours,
            np.datetime64('NaT')
        )

        # amount: 对数正态分布
        raw_amounts = rng.lognormal(mean=4.7, sigma=0.8, size=batch_n)
        batch_amount = np.clip(raw_amounts, 0, 4000)
        batch_amount = np.round(batch_amount, 2)

        # quantity
        batch_quantity = np.where(rng.random(batch_n) < 0.7, 1, rng.integers(1, 11, size=batch_n))

        # actual_amount
        ratio = 0.3 + rng.random(batch_n) * 0.7  # [0.3, 1.0)
        is_zero_actual = rng.random(batch_n) < 0.05
        batch_actual_amount = np.where(
            is_zero_actual | (batch_amount == 0),
            0.0,
            np.round(batch_amount * ratio, 2)
        )

        # refund_amount
        is_refund_amt = rng.random(batch_n) < refund_bool_pct
        refund_ratio = 0.5 + rng.random(batch_n) * 0.5
        batch_refund_amount = np.where(
            is_refund_amt,
            np.round(batch_amount * refund_ratio, 2),
            0.0
        )

        # boolean
        batch_is_member = rng.random(batch_n) < member_pct
        batch_is_goujinjin = rng.random(batch_n) < goujinjin_pct
        batch_is_refund = rng.random(batch_n) < refund_bool_pct

        # 构造 DataFrame
        df = pd.DataFrame({
            "order_id": batch_order_id,
            "sub_order_id": batch_sub_order_id,
            "user_id": batch_user_id,
            "user_nickname": batch_user_nickname,
            "order_time": pd.Series(batch_order_time),
            "pay_time": pd.Series(batch_pay_time),
            "ship_time": pd.Series(batch_ship_time),
            "order_type": batch_order_type,
            "order_status": batch_order_status,
            "product_id": batch_product_id,
            "merchant_code": batch_merchant_code,
            "product_title": batch_product_title,
            "sku_id": batch_sku_id,
            "sku_code": batch_sku_code,
            "sku_name": batch_sku_name,
            "quantity": batch_quantity,
            "amount": batch_amount,
            "refund_status": batch_refund_status,
            "refund_amount": batch_refund_amount,
            "actual_amount": batch_actual_amount,
            "province": batch_province,
            "city": batch_city,
            "influencer_name": None,
            "influencer_id": None,
            "live_room_id": None,
            "video_id": None,
            "traffic_source": None,
            "traffic_type": None,
            "seller_note": None,
            "year": batch_year,
            "month": batch_month,
            "is_member": batch_is_member,
            "spu_category": batch_spu_category,
            "spu_type": batch_spu_type,
            "spu_tier": batch_spu_tier,
            "spu_product_class": batch_spu_product_class,
            "spu_product_subclass": batch_spu_product_subclass,
            "spu_cosmetic": batch_spu_cosmetic,
            "spu_spec": batch_spu_spec,
            "spu_hash": batch_spu_hash,
            "channel": batch_channel,
            "is_goujinjin": batch_is_goujinjin,
            "is_refund": batch_is_refund,
        })

        # 写入 Parquet
        pq_path = PARQUET_DIR / f"batch_{batch_num:04d}.parquet"
        df.to_parquet(pq_path, index=False, engine='pyarrow')
        pq_files.append(str(pq_path))

        written += batch_n

        if written >= next_progress or written >= TARGET_ROWS:
            elapsed = time.time() - t0
            rate = written / elapsed if elapsed > 0 else 0
            eta = (TARGET_ROWS - written) / rate if rate > 0 else 0
            print(f"  {written:>14,} / {TARGET_ROWS:,}  ({pct(written, TARGET_ROWS)})  "
                  f"elapsed {elapsed:.0f}s  ETA {eta:.0f}s  rate {rate:,.0f} rows/s")
            next_progress += PROGRESS_STEP

    t_gen = time.time() - t0
    print(f"  Parquet 生成完成: {written:,} 行, 耗时 {t_gen:.1f}s ({written / t_gen:,.0f} rows/s)")

    # ── 3b. COPY Parquet → DuckDB ──────────────────────────────────
    print("  COPY Parquet → DuckDB ...")
    t_copy = time.time()
    pq_glob = str(PARQUET_DIR / "*.parquet")
    con.execute(f"COPY orders FROM '{pq_glob}' (FORMAT PARQUET)")
    t_copy = time.time() - t_copy
    print(f"  COPY 完成: {t_copy:.1f}s")

    # ── 4. 清理 & 验证 ────────────────────────────────────────────
    print("[4/4] 验证 & 清理 ...")
    final_count = con.execute("SELECT count(*) FROM orders").fetchone()[0]

    # 抽样统计
    sample_channel = con.execute(
        "SELECT channel, count(*) as cnt FROM orders GROUP BY channel ORDER BY cnt DESC LIMIT 5"
    ).fetchall()
    sample_status = con.execute(
        "SELECT order_status, count(*) as cnt FROM orders GROUP BY order_status ORDER BY cnt DESC LIMIT 5"
    ).fetchall()

    con.close()

    # 清理 Parquet 临时文件
    shutil.rmtree(PARQUET_DIR, ignore_errors=True)

    db_size = DST_DB.stat().st_size
    t_total = time.time() - t_total_start

    print()
    print("=" * 60)
    print(f"  目标数据库: {DST_DB}")
    print(f"  总行数:     {final_count:>14,}")
    print(f"  文件大小:   {fmt_size(db_size)}")
    print(f"  生成耗时:   {t_total:.1f}s  (gen={t_gen:.1f}s + copy={t_copy:.1f}s)")
    print(f"  写入速率:   {final_count / t_total:,.0f} rows/s")
    print()
    print("  channel 分布 (top 5):")
    for ch, cnt in sample_channel:
        print(f"    {ch or '(NULL)'}: {cnt:,} ({cnt / final_count * 100:.1f}%)")
    print()
    print("  order_status 分布 (top 5):")
    for st, cnt in sample_status:
        print(f"    {st or '(NULL)'}: {cnt:,} ({cnt / final_count * 100:.1f}%)")
    print("=" * 60)

    if final_count < TARGET_ROWS:
        print(f"警告: 实际行数 {final_count:,} < 目标 {TARGET_ROWS:,}", file=sys.stderr)
        sys.exit(1)

    print("完成。")


if __name__ == "__main__":
    main()
