#!/usr/bin/env python3
"""Generate deterministic, production-shaped synthetic order Parquet files."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb


FIFTY_MILLION = 50_000_000
MIN_FREE_BYTES_FOR_50M = 200 * 1024**3


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def _require_50m_approval(n_orders: int, output_dir: Path, allow_50m: bool) -> None:
    if n_orders < FIFTY_MILLION:
        return
    if not allow_50m:
        raise ValueError("50m generation requires explicit approval: pass --allow-50m")
    output_dir.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(output_dir).free
    if free_bytes < MIN_FREE_BYTES_FOR_50M:
        raise OSError(
            f"50m generation requires >200 GiB free; available={free_bytes / 1024**3:.1f} GiB"
        )


def generate_synthetic_orders(
    n_orders: int,
    output_dir: Path,
    *,
    force: bool = False,
    allow_50m: bool = False,
) -> dict[str, object]:
    if n_orders <= 0:
        raise ValueError("n_orders must be positive")

    output_dir = Path(output_dir)
    _require_50m_approval(n_orders, output_dir, allow_50m)
    shop_dir = output_dir / "shop"
    member_dir = output_dir / "member"
    shop_dir.mkdir(parents=True, exist_ok=True)
    member_dir.mkdir(parents=True, exist_ok=True)
    shop_path = shop_dir / f"synthetic_orders_{n_orders}.parquet"
    member_path = member_dir / f"synthetic_members_{n_orders}.parquet"
    manifest_path = output_dir / "manifest.json"

    if not force and shop_path.exists() and member_path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("n_orders") == n_orders:
            manifest["reused"] = True
            return manifest

    for path in (shop_path, member_path):
        path.unlink(missing_ok=True)

    started = time.perf_counter()
    conn = duckdb.connect()
    try:
        conn.execute("SET threads TO 4")
        conn.execute(
            f"""
            COPY (
                WITH synthetic AS (
                    SELECT
                        i,
                        TIMESTAMP '2025-01-01 00:00:00'
                            + ((i % 525600)::BIGINT) * INTERVAL '1 minute' AS order_ts,
                        CAST(50 + (i % 5000) / 100.0 AS DECIMAL(12, 2)) AS paid
                    FROM range({n_orders}) AS t(i)
                )
                SELECT
                    printf('SYN%012d', i) AS order_id,
                    printf('SYN%012d-1', i) AS sub_order_id,
                    printf('USR%09d', i % greatest(1, {n_orders // 4})) AS user_id,
                    printf('synthetic-user-%d', i % 10000) AS user_nickname,
                    order_ts AS order_time,
                    order_ts + INTERVAL '5 minutes' AS pay_time,
                    order_ts + INTERVAL '1 day' AS ship_time,
                    'normal' AS order_type,
                    '交易成功' AS order_status,
                    CAST(100000 + (i % 1000) AS VARCHAR) AS product_id,
                    printf('MC%06d', i % 1000) AS merchant_code,
                    printf('Synthetic Product %d', i % 1000) AS product_title,
                    printf('SKU%06d', i % 2000) AS sku_id,
                    printf('SKU-CODE-%06d', i % 2000) AS sku_code,
                    printf('Synthetic SKU %d', i % 2000) AS sku_name,
                    CAST(1 + (i % 3) AS INTEGER) AS quantity,
                    paid AS amount,
                    CAST(NULL AS VARCHAR) AS refund_status,
                    CAST(0 AS DECIMAL(12, 2)) AS refund_amount,
                    paid AS actual_amount,
                    CASE i % 4 WHEN 0 THEN '上海' WHEN 1 THEN '北京'
                        WHEN 2 THEN '广东' ELSE '浙江' END AS province,
                    CASE i % 4 WHEN 0 THEN '上海' WHEN 1 THEN '北京'
                        WHEN 2 THEN '广州' ELSE '杭州' END AS city,
                    CAST(NULL AS VARCHAR) AS influencer_name,
                    CAST(NULL AS VARCHAR) AS influencer_id,
                    CAST(NULL AS VARCHAR) AS live_room_id,
                    CAST(NULL AS VARCHAR) AS video_id,
                    'synthetic' AS traffic_source,
                    'benchmark' AS traffic_type,
                    '' AS seller_note,
                    CAST(year(order_ts) AS INTEGER) AS year,
                    CAST(month(order_ts) AS INTEGER) AS month,
                    (i % 3 = 0) AS is_member,
                    printf('Category %d', i % 10) AS spu_category,
                    '正装' AS spu_type,
                    CASE WHEN i % 5 = 0 THEN '核心品' ELSE '常规品' END AS spu_tier,
                    printf('Product Class %d', i % 20) AS spu_product_class,
                    printf('Product Subclass %d', i % 50) AS spu_product_subclass,
                    '妆' AS spu_cosmetic,
                    'standard' AS spu_spec,
                    printf('syn-%04d', i % 1000) AS spu_hash,
                    '货架' AS channel,
                    FALSE AS is_goujinjin,
                    FALSE AS is_refund
                FROM synthetic
            ) TO '{_sql_path(shop_path)}'
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        conn.execute(
            f"""
            COPY (
                SELECT printf('SYN%012d', i) AS order_id
                FROM range({n_orders}) AS t(i)
                WHERE i % 3 = 0
            ) TO '{_sql_path(member_path)}'
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        schema = [row[0] for row in conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{_sql_path(shop_path)}')"
        ).fetchall()]
    finally:
        conn.close()

    elapsed = time.perf_counter() - started
    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_orders": n_orders,
        "member_orders": (n_orders + 2) // 3,
        "shop_parquet": str(shop_path.resolve()),
        "member_parquet": str(member_path.resolve()),
        "shop_bytes": shop_path.stat().st_size,
        "member_bytes": member_path.stat().st_size,
        "generation_sec": round(elapsed, 4),
        "schema": schema,
        "reused": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n_orders", "--n-orders", type=int, default=FIFTY_MILLION)
    parser.add_argument("--output_dir", "--output-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-50m", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = generate_synthetic_orders(
            args.n_orders,
            args.output_dir,
            force=args.force,
            allow_50m=args.allow_50m,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
