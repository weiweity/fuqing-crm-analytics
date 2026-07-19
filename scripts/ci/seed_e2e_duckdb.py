#!/usr/bin/env python3
"""Build CI e2e DuckDB: schema + minimal business seed (not empty schema-only).

Root cause (2026-07-19):
  - GitHub Actions cannot host 131GB production DuckDB.
  - Empty schema-only + L4.85 session isolation made e2e permanently red.
  - This script keeps a *tiny* offline DB (~MB) with enough rows for dashboard
    shells / APIs to return 200 with non-empty shapes.

Usage:
  python3 scripts/ci/seed_e2e_duckdb.py [/tmp/e2e_duckdb.duckdb]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = REPO_ROOT / "scripts" / "ci" / "e2e_schema.sql"
DEFAULT_DB = Path("/tmp/e2e_duckdb.duckdb")


def build(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        _seed_orders(conn)
        _seed_metrics(conn)
        _seed_user_rfm(conn)
        # sanity
        n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert n >= 50, f"seed orders too few: {n}"
        print(f"E2E_DUCKDB_OK path={db_path} orders={n} size_bytes={db_path.stat().st_size}")
    finally:
        conn.close()


def _seed_orders(conn: duckdb.DuckDBPyConnection) -> None:
    """Insert ~60 orders across 2 users × 3 channels × 3 categories × 10 days."""
    base = datetime(2026, 6, 1, 12, 0, 0)
    channels = ["天猫", "京东", "抖音"]
    categories = [
        ("次抛隐形眼镜", "护理", "A类", "次抛"),
        ("美瞳", "彩妆", "B类", "美瞳"),
        ("护理液", "护理", "C类", "护理液"),
    ]
    rows = []
    oid = 1
    for day in range(20):
        pay = base + timedelta(days=day)
        for u in range(1, 4):
            for ch_i, channel in enumerate(channels):
                cat = categories[(day + u + ch_i) % len(categories)]
                order_id = f"E2E-O{oid:05d}"
                amount = 50.0 + (oid % 17) * 10
                rows.append(
                    (
                        order_id,
                        f"{order_id}-1",
                        f"U{u:03d}",
                        f"用户{u}",
                        pay,
                        pay,
                        pay + timedelta(hours=2),
                        "普通订单",
                        "交易成功",
                        f"P{cat[3]}",
                        f"MC{cat[3]}",
                        f"{cat[0]}-SKU",
                        f"SKU{oid}",
                        f"SKU{oid}",
                        cat[0],
                        1,
                        amount,
                        "无退款",
                        0.0,
                        amount,
                        "上海",
                        "上海",
                        None,
                        None,
                        None,
                        None,
                        "自然搜索",
                        "站内",
                        None,
                        pay.year,
                        pay.month,
                        u == 1,  # is_member
                        cat[0],
                        cat[1],
                        cat[2],
                        cat[0],
                        cat[3],
                        "否",
                        "规格1",
                        f"hash-{cat[3]}",
                        channel,
                        False,
                        False,
                    )
                )
                oid += 1
                if oid > 80:
                    break
            if oid > 80:
                break
        if oid > 80:
            break

    conn.executemany(
        """
        INSERT INTO orders (
          order_id, sub_order_id, user_id, user_nickname,
          order_time, pay_time, ship_time,
          order_type, order_status, product_id, merchant_code, product_title,
          sku_id, sku_code, sku_name, quantity, amount,
          refund_status, refund_amount, actual_amount,
          province, city, influencer_name, influencer_id, live_room_id, video_id,
          traffic_source, traffic_type, seller_note,
          year, month, is_member,
          spu_category, spu_type, spu_tier, spu_product_class, spu_product_subclass,
          spu_cosmetic, spu_spec, spu_hash, channel, is_goujinjin, is_refund
        ) VALUES (
          ?,?,?,?,
          ?,?,?,
          ?,?,?,?,?,
          ?,?,?,?,?,
          ?,?,?,
          ?,?,?,?,?,?,
          ?,?,?,
          ?,?,?,
          ?,?,?,?,?,
          ?,?,?,?,?,?
        )
        """,
        rows,
    )


def _seed_metrics(conn: duckdb.DuckDBPyConnection) -> None:
    base = datetime(2026, 6, 1).date()
    for i in range(30):
        d = base + timedelta(days=i)
        conn.execute(
            """
            INSERT INTO daily_metrics
            (d, order_count, user_count, gsv, member_user_count, member_gsv)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [d, 10 + i, 5 + i % 3, 1000.0 + i * 50, 2, 400.0 + i * 10],
        )
        conn.execute(
            """
            INSERT INTO daily_visitors (date, visitors, new_members, member_join_rate)
            VALUES (?, ?, ?, ?)
            """,
            [d, 100 + i * 3, 3, 0.03],
        )


def _seed_user_rfm(conn: duckdb.DuckDBPyConnection) -> None:
    analysis = datetime(2026, 6, 30).date()
    for u in range(1, 4):
        conn.execute(
            """
            INSERT INTO user_rfm (
              user_id, user_nickname, analysis_date, metric_type, lookback_days, channel,
              recency_days, frequency, monetary, r_score, f_score, m_score,
              rfm_tier, rfm_tier_en, segment_id, first_order_date, last_order_date,
              created_at, is_member
            ) VALUES (?, ?, ?, 'gsv', 365, '全店', ?, ?, ?, 4, 3, 3,
                      '重要价值客户', 'champions', 1, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            [
                f"U{u:03d}",
                f"用户{u}",
                analysis,
                10 + u,
                5 + u,
                500.0 * u,
                analysis - timedelta(days=60),
                analysis - timedelta(days=u),
                u == 1,
            ],
        )
        conn.execute(
            """
            INSERT INTO user_first_purchase (user_id, first_pay_date)
            VALUES (?, ?)
            """,
            [f"U{u:03d}", analysis - timedelta(days=90)],
        )
        conn.execute(
            """
            INSERT INTO user_recency
            (user_id, last_pay_time, is_member, recency_days, total_orders, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                f"U{u:03d}",
                datetime(2026, 6, 28, 10, 0, 0),
                u == 1,
                2 + u,
                10 + u,
                800.0 * u,
            ],
        )


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DB
    build(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
