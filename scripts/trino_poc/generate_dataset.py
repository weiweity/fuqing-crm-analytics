"""Generate a DuckDB-compatible Parquet orders dataset for Trino POC."""

from __future__ import annotations

import argparse
import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

from scripts.trino_poc.schema import ORDER_COLUMNS, parquet_schema


DEFAULT_OUTPUT_URI = "data/trino-poc/orders"
DEFAULT_BATCH_ROWS = 50_000
DEFAULT_ROWS = 100_000

CHANNELS = ("直播", "货架", "短视频", "淘客", "搜索", "私域")
CATEGORIES = ("面膜", "洁面", "精华", "面霜", "防晒", "医用凝胶")
PROVINCES = ("广东", "浙江", "江苏", "上海", "北京", "四川", "湖北")
TRAFFIC_SOURCES = ("推荐", "搜索", "直播间", "短视频", "会员中心")


@dataclass(frozen=True)
class DatasetManifest:
    output_uri: str
    files: int
    rows: int
    bytes_written: int
    compression: str | None
    seed: int


def _decimal_from_cents(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def _make_batch(start_id: int, rows: int, seed: int) -> pa.Table:
    rng = random.Random(seed + start_id)
    base = datetime(2025, 1, 1, 9, 0, 0)
    data: dict[str, list] = {column.name: [] for column in ORDER_COLUMNS}

    for offset in range(rows):
        idx = start_id + offset
        pay_time = base + timedelta(days=rng.randrange(0, 730), minutes=rng.randrange(0, 1440))
        order_time = pay_time - timedelta(minutes=rng.randrange(1, 180))
        ship_time = pay_time + timedelta(days=rng.randrange(1, 5))
        quantity = rng.randint(1, 4)
        amount = _decimal_from_cents(rng.randint(1_900, 89_900) * quantity)
        is_refund = rng.random() < 0.06
        refund_amount = (amount * Decimal("0.35")).quantize(Decimal("0.01")) if is_refund else Decimal("0.00")
        actual_amount = amount - refund_amount
        category = CATEGORIES[idx % len(CATEGORIES)]
        channel = CHANNELS[idx % len(CHANNELS)]
        product_id = f"P{idx % 5000:05d}"
        sku_id = f"SKU{idx % 12000:05d}"

        data["order_id"].append(f"O{idx:012d}")
        data["sub_order_id"].append(f"SO{idx:012d}")
        data["user_id"].append(f"U{idx % 300_000:09d}")
        data["user_nickname"].append(f"user_{idx % 300_000:09d}")
        data["order_time"].append(order_time)
        data["pay_time"].append(pay_time)
        data["ship_time"].append(ship_time)
        data["order_type"].append("天猫订单")
        data["order_status"].append("交易关闭" if rng.random() < 0.015 else "交易成功")
        data["product_id"].append(product_id)
        data["merchant_code"].append(f"M{idx % 400:04d}")
        data["product_title"].append(f"{category} POC 商品 {idx % 5000:05d}")
        data["sku_id"].append(sku_id)
        data["sku_code"].append(f"SC{idx % 12000:05d}")
        data["sku_name"].append(f"{category} 规格 {idx % 12 + 1}")
        data["quantity"].append(quantity)
        data["amount"].append(amount)
        data["refund_status"].append("已退款" if is_refund else "无退款")
        data["refund_amount"].append(refund_amount)
        data["actual_amount"].append(actual_amount)
        data["province"].append(PROVINCES[idx % len(PROVINCES)])
        data["city"].append(f"城市{idx % 80:02d}")
        data["influencer_name"].append(f"达人{idx % 160:03d}")
        data["influencer_id"].append(f"I{idx % 160:04d}")
        data["live_room_id"].append(f"L{idx % 260:04d}")
        data["video_id"].append(f"V{idx % 900:05d}")
        data["traffic_source"].append(TRAFFIC_SOURCES[idx % len(TRAFFIC_SOURCES)])
        data["traffic_type"].append("paid" if rng.random() < 0.35 else "organic")
        data["seller_note"].append("")
        data["year"].append(pay_time.year)
        data["month"].append(pay_time.month)
        data["is_member"].append((idx % 5) != 0)
        data["spu_category"].append(category)
        data["spu_type"].append("正装" if idx % 7 else "小样")
        data["spu_tier"].append(f"T{idx % 4 + 1}")
        data["spu_product_class"].append(f"{category}-主类{idx % 5}")
        data["spu_product_subclass"].append(f"{category}-子类{idx % 11}")
        data["spu_cosmetic"].append("械" if category == "医用凝胶" else "妆")
        data["spu_spec"].append(f"{30 + idx % 120}ml")
        data["spu_hash"].append(f"h{idx % 20000:05d}")
        data["channel"].append(channel)
        data["is_goujinjin"].append(rng.random() < 0.02)
        data["is_refund"].append(is_refund)

    return pa.Table.from_pydict(data, schema=parquet_schema())


def _resolve_filesystem(output_uri: str) -> tuple[pafs.FileSystem, str]:
    parsed = urlparse(output_uri)
    if parsed.scheme == "s3":
        endpoint = os.environ.get("FQ_TRINO_S3_ENDPOINT", "http://127.0.0.1:19000")
        endpoint_parsed = urlparse(endpoint)
        scheme = endpoint_parsed.scheme or "http"
        host = endpoint_parsed.netloc or endpoint_parsed.path
        filesystem = pafs.S3FileSystem(
            access_key=os.environ.get("FQ_TRINO_S3_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("FQ_TRINO_S3_SECRET_KEY", "minioadmin"),
            endpoint_override=host,
            scheme=scheme,
            region=os.environ.get("FQ_TRINO_S3_REGION", "us-east-1"),
            allow_bucket_creation=True,
        )
        return filesystem, f"{parsed.netloc}{parsed.path}".strip("/")

    output_path = Path(output_uri).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    return pafs.LocalFileSystem(), str(output_path)


def _write_manifest(filesystem: pafs.FileSystem, base_path: str, manifest: DatasetManifest) -> None:
    payload = {
        **asdict(manifest),
        "schema": [
            {"name": column.name, "trino_type": column.trino_type}
            for column in ORDER_COLUMNS
        ],
    }
    with filesystem.open_output_stream(f"{base_path.rstrip('/')}/_manifest.json") as sink:
        sink.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))


def generate_dataset(
    output_uri: str,
    rows: int | None,
    target_gb: float | None,
    batch_rows: int,
    seed: int,
    compression: str,
) -> DatasetManifest:
    filesystem, base_path = _resolve_filesystem(output_uri)
    filesystem.create_dir(base_path, recursive=True)

    target_bytes = int(target_gb * 1024**3) if target_gb is not None else None
    row_goal = rows if rows is not None else DEFAULT_ROWS
    total_rows = 0
    total_bytes = 0
    files = 0

    while True:
        if target_bytes is None and total_rows >= row_goal:
            break
        remaining = max(row_goal - total_rows, 0) if target_bytes is None else batch_rows
        current_rows = min(batch_rows, remaining) if target_bytes is None else batch_rows
        if current_rows <= 0:
            break

        table = _make_batch(total_rows, current_rows, seed)
        file_path = f"{base_path.rstrip('/')}/part-{files:05d}.parquet"
        with filesystem.open_output_stream(file_path) as sink:
            pq.write_table(table, sink, compression=compression)
        info = filesystem.get_file_info(file_path)
        total_bytes += max(info.size, 0)
        total_rows += current_rows
        files += 1

        if target_bytes is not None and total_bytes >= target_bytes:
            break

    manifest = DatasetManifest(
        output_uri=output_uri,
        files=files,
        rows=total_rows,
        bytes_written=total_bytes,
        compression=compression,
        seed=seed,
    )
    _write_manifest(filesystem, base_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-uri", default=DEFAULT_OUTPUT_URI)
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--target-gb", type=float, default=None)
    parser.add_argument("--batch-rows", type=int, default=DEFAULT_BATCH_ROWS)
    parser.add_argument("--seed", type=int, default=20302)
    parser.add_argument("--compression", default="zstd", choices=["zstd", "snappy", "none"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    compression = None if args.compression == "none" else args.compression
    manifest = generate_dataset(
        output_uri=args.output_uri,
        rows=args.rows,
        target_gb=args.target_gb,
        batch_rows=args.batch_rows,
        seed=args.seed,
        compression=compression,
    )
    print(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
