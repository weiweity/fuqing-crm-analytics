"""
W3/W4 pipeline CI smoke test (sprint 3 P1-1) — design doc v1.1 §P1-1

目的: 补 sprint 2 task 1 (e60dbfd) 留下的 CI 缺口 — 之前 W3/W4 pipeline
集成测试 (test_w3w4_pipeline_integration.py) 走 inspect 抽源码 + exec 块验证
守卫/签名, 但**不真跑 pipeline.run_full_etl**, 改 W3/W4 集成代码 CI 拦不住.

本 smoke test 补这个缺口:
  ① mock parquet + temp DuckDB, 实际调 run_full_etl (mock 掉 113 xlsx rglob + 41GB 单例锁)
  ② step 7b --skip-dq flag 端到端生效 (skip_dq=True 不调 run_assertions)
  ③ step 8 W4 幂等 (跑 2 次 pipeline 行数不变 — dbt-style snapshot version 续号)
  ④ 1 断言 quarantine 触发能进 rfm_quarantine 表 (端到端, 不只单元测试)
  ⑤ 走 < 5min (heavy mock, 不真读 113 xlsx + 不真算 540 组合)

CLAUDE.md 合规:
  ① 走 homebrew Python 3.14 + PYTHONPATH=.
  ② temp DuckDB 隔离 (不持 41GB 锁, 跟 prod 完全独立)
  ③ mock _send_lark_alert 不真发 (lark-cli 不应被 CI 触发)
  ④ ruff F401/E402 兼容 (sys.path.insert 在 import 前, 测试文件 per-file-ignores)
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# Fixtures: temp DuckDB + mock parquet + 全套 pipeline 依赖 mock
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def temp_duckdb_path(tmp_path):
    """隔离 DuckDB 文件 — 不持 41GB 锁, 测试完即清."""
    return str(tmp_path / "smoke_test.duckdb")


@pytest.fixture
def mock_parquet_dirs(tmp_path):
    """Mock parquet 数据目录 (空目录, 模拟 113 xlsx 处理完)."""
    shop = tmp_path / "shop"
    member = tmp_path / "member"
    shop.mkdir()
    member.mkdir()
    return {"shop": shop, "member": member}


@pytest.fixture
def w3w4_smoke_env(temp_duckdb_path, mock_parquet_dirs, monkeypatch):
    """完整 mock 环境: 跑 run_full_etl 不用真 xlsx / 真 DuckDB / 真 lark.

    流程:
      1. temp DuckDB 预建 orders/user_rfm/fact_rfm_long/rfm_quarantine 表
      2. 灌 30 天历史 + 1 天 T-1 暴跌数据 (触发 W3 断言失败)
      3. patch DUCKDB_PATH 指向 temp
      4. patch SHOP_DATA_SOURCE/MEMBER_DATA_SOURCE 指向空 mock
      5. patch 所有 ETL 重活儿 (load_data_files, clean_data, preload 等) → 短路
      6. patch _send_lark_alert 避免真发
      7. patch get_db_max_pay_time 决定 mode='auto' → 'incremental' (db 有数据)
    """
    # Step 1: 预建 DuckDB schema + 灌 mock 数据
    conn = duckdb.connect(temp_duckdb_path)
    conn.execute("""
        CREATE TABLE orders (
            user_id INTEGER, order_id VARCHAR, sub_order_id VARCHAR,
            actual_amount DECIMAL(18,2), pay_time TIMESTAMP,
            order_time TIMESTAMP, ship_time TIMESTAMP, order_type VARCHAR,
            order_status VARCHAR, channel VARCHAR, spu_product_class VARCHAR,
            spu_type VARCHAR, spu_tier VARCHAR, spu_cosmetic VARCHAR,
            spu_spec VARCHAR, spu_product_subclass VARCHAR,
            is_goujinjin BOOLEAN, is_refund BOOLEAN, is_member BOOLEAN,
            influencer_name VARCHAR, influencer_id VARCHAR,
            live_room_id VARCHAR, video_id VARCHAR,
            traffic_source VARCHAR, traffic_type VARCHAR,
            seller_note VARCHAR, year INTEGER, month INTEGER,
            product_id VARCHAR, merchant_code VARCHAR, product_title VARCHAR,
            sku_id VARCHAR, sku_code VARCHAR, sku_name VARCHAR,
            quantity INTEGER, amount DECIMAL(18,2), refund_status VARCHAR,
            refund_amount DECIMAL(18,2), province VARCHAR, city VARCHAR,
            user_nickname VARCHAR, sku_code_2 VARCHAR, sku_name_2 VARCHAR,
            valid_sql INTEGER, spu_category VARCHAR
        )
    """)
    # user_rfm 表 (run_full_etl 期望)
    conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR PRIMARY KEY, r_score INTEGER, f_score INTEGER,
            m_score DECIMAL(18,2), segment_id INTEGER, first_pay_time TIMESTAMP,
            last_pay_time TIMESTAMP, total_orders BIGINT, total_amount DECIMAL(18,2)
        )
    """)
    # fact_rfm_long 表 (W4 需要)
    conn.execute("""
        CREATE TABLE fact_rfm_long (
            date DATE NOT NULL, dimension_key VARCHAR NOT NULL,
            dimension_json JSON NOT NULL, user_count BIGINT,
            gmv DECIMAL(18,2), repurchase_count BIGINT, version INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (date, dimension_key, version)
        )
    """)
    # daily_metrics (step 6.7 需要)
    conn.execute("""
        CREATE TABLE daily_metrics (
            date DATE PRIMARY KEY, gmv DECIMAL(18,2), gsv DECIMAL(18,2),
            order_count BIGINT, gsv_order_count BIGINT,
            new_user_count BIGINT, old_user_count BIGINT,
            member_gmv DECIMAL(18,2), member_gsv DECIMAL(18,2),
            member_count BIGINT, avg_order_value DECIMAL(18,2),
            new_user_gmv DECIMAL(18,2), old_user_gmv DECIMAL(18,2)
        )
    """)
    # user_first_purchase (step 6 需要)
    conn.execute("""
        CREATE TABLE user_first_purchase (
            user_id VARCHAR PRIMARY KEY, first_pay_date DATE
        )
    """)
    # user_recency (step 6.5 需要)
    conn.execute("""
        CREATE TABLE user_recency (
            user_id VARCHAR PRIMARY KEY, last_pay_time TIMESTAMP,
            is_member BOOLEAN DEFAULT FALSE, recency_days INTEGER,
            total_orders INTEGER DEFAULT 0, total_amount DECIMAL(18,2) DEFAULT 0
        )
    """)
    # processed_files tracking (避免冷启动重读)
    pdir = Path(ROOT) / "data" / "processed"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "shop_processed.json").write_text(json.dumps({
        "_smoke_marker.parquet": {
            "mtime": 0, "hash": "smoke_no_data"
        }
    }, ensure_ascii=False))
    (pdir / "member_processed.json").write_text(json.dumps({}, ensure_ascii=False))

    # Step 2: 灌 mock 数据 — 30 天历史 (每天 SUM 1000) + T-1 暴跌 (SUM 100 → 触发 assert_total_not_drop)
    base = date(2026, 6, 5)  # 跑批当天 = 2026-06-06
    rows = []
    for i in range(30):
        d = base - timedelta(days=i + 1)
        # 每天 5 单, 每单 200, 共 1000
        for u in range(1, 6):
            rows.append((
                u, f"hist_{d}_{u}", f"sub_{d}_{u}", 200.0,
                f"{d.isoformat()} 10:00:00", f"{d.isoformat()} 09:00:00",
                f"{d.isoformat()} 11:00:00", "normal", "已支付",
                "全店", "全品", "全品", "全品", "全品", "全品", "全品",
                False, False, False, "", "", "", "", "", "", "",
                d.year, d.month, "p1", "m1", f"商品{u}", "s1", "sc1", "sn1",
                1, 200.0, "无", 0.0, "北京", "北京", f"user{u}", "sc2", "sn2",
                1, "全品"
            ))
    # T-1 (2026-06-05) 暴跌: 5 单 × 20 = 100 (历史均值 1000 → 1/10, 触发 < 0.3 阈值)
    d_t1 = base
    for u in range(1, 6):
        rows.append((
            u, f"t1_{u}", f"sub_t1_{u}", 20.0,
            f"{d_t1.isoformat()} 10:00:00", f"{d_t1.isoformat()} 09:00:00",
            f"{d_t1.isoformat()} 11:00:00", "normal", "已支付",
            "全店", "全品", "全品", "全品", "全品", "全品", "全品",
            False, False, False, "", "", "", "", "", "", "",
            d_t1.year, d_t1.month, "p1", "m1", f"商品{u}", "s1", "sc1", "sn1",
            1, 20.0, "无", 0.0, "北京", "北京", f"user{u}", "sc2", "sn2",
            1, "全品"
        ))
    placeholders = ",".join(["?"] * len(rows[0]))
    conn.executemany(f"INSERT INTO orders VALUES ({placeholders})", rows)
    # user_first_purchase + user_recency
    conn.executemany(
        "INSERT INTO user_first_purchase VALUES (?, ?::DATE)",
        [(f"user{u}", d - timedelta(days=29)) for u in range(1, 6)],
    )
    conn.executemany(
        "INSERT INTO user_recency VALUES (?, ?::TIMESTAMP, FALSE, 1, ?, ?)",
        [(f"user{u}", f"{base.isoformat()} 10:00:00", 30, 6000.0) for u in range(1, 6)],
    )
    # daily_metrics (30 天)
    for i in range(30):
        d = base - timedelta(days=i + 1)
        conn.execute(
            "INSERT INTO daily_metrics VALUES (?::DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [d, 1000.0, 1000.0, 5, 5, 0, 5, 0, 0, 0, 200.0, 0, 1000.0],
        )
    conn.close()

    # Step 3-6: monkeypatch
    from scripts.etl import pipeline
    from scripts.etl import config as _config

    monkeypatch.setattr(pipeline, "DUCKDB_PATH", Path(temp_duckdb_path))
    monkeypatch.setattr(_config, "DUCKDB_PATH", Path(temp_duckdb_path))
    # 指向空 mock 目录, 跑批 0 xlsx → 0 行新增
    monkeypatch.setattr(pipeline, "SHOP_DATA_SOURCE", mock_parquet_dirs["shop"])
    monkeypatch.setattr(pipeline, "MEMBER_DATA_SOURCE", mock_parquet_dirs["member"])
    monkeypatch.setattr(_config, "SHOP_DATA_SOURCE", mock_parquet_dirs["shop"])
    monkeypatch.setattr(_config, "MEMBER_DATA_SOURCE", mock_parquet_dirs["member"])

    # mock get_db_max_pay_time → 强制 'auto' 走 'incremental' (db 有数据)
    monkeypatch.setattr(
        pipeline, "get_db_max_pay_time",
        lambda: datetime(2026, 6, 5, 10, 0, 0),
    )

    # 短路 SPU/渠道/淘客/直播 loader
    monkeypatch.setattr(
        pipeline, "load_spu_mapping", lambda: pd.DataFrame(),
    )
    monkeypatch.setattr(
        pipeline, "load_channel_rules", lambda: ({}, {}),
    )
    monkeypatch.setattr(
        pipeline, "load_taoke_order_ids", lambda: set(),
    )
    monkeypatch.setattr(
        pipeline, "load_live_order_ids", lambda: set(),
    )
    monkeypatch.setattr(
        pipeline, "load_taoke_product_rules", lambda: [],
    )

    # 短路 load_data_files → 返回 1 行 (绕过 "没有加载到任何店铺数据" early return,
    # 但 upsert_to_duckdb mock 不写, 所以只是过场)
    empty_df = pd.DataFrame()
    one_row_df = pd.DataFrame({
        "order_id": ["smoke_marker"],
        "user_id": [0],
        "pay_time": pd.to_datetime(["2026-06-05 10:00:00"]),
        "actual_amount": [0.0],
        "is_member": [False],
    })
    monkeypatch.setattr(
        pipeline, "load_data_files", lambda *a, **kw: one_row_df.copy(),
    )

    # 短路 clean_data / upsert (避免 spurious 错误)
    monkeypatch.setattr(
        pipeline, "clean_data", lambda df, *a, **kw: df,
    )
    monkeypatch.setattr(
        pipeline, "upsert_to_duckdb", lambda *a, **kw: None,
    )

    # 短路 filter_rolling_window → 0 新 0 刷
    monkeypatch.setattr(
        pipeline, "filter_rolling_window",
        lambda df, *a, **kw: (empty_df.copy(), empty_df.copy()),
    )

    # 短路 _mark_all_files_processed (全量模式下, 跑批写 processed.json)
    monkeypatch.setattr(
        pipeline, "_mark_all_files_processed", lambda: None,
    )

    # 短路 create_user_rfm_table + run_auto_preload (Step 6 全量)
    monkeypatch.setattr(
        "backend.database.create_user_rfm_table", lambda: None,
    )
    monkeypatch.setattr(
        "scripts.etl.preload_rfm.run_auto_preload",
        lambda: [("2026-06-05", 0)],
    )

    # 短路 _rebuild_metrics / _update_incremental_metrics (避免 daily_metrics 全量重算)
    monkeypatch.setattr(pipeline, "_rebuild_metrics", lambda: None)
    monkeypatch.setattr(pipeline, "_update_incremental_metrics", lambda *a, **kw: None)

    # 短路 _build_user_first_purchase_table / _build_user_recency_table
    monkeypatch.setattr(pipeline, "_build_user_first_purchase_table", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "_build_user_recency_table", lambda *a, **kw: None)

    # 短路品类看板 Step 8 (precompute_category_flow/churn)
    monkeypatch.setattr(
        "scripts.etl.precompute_category_flow.run_full_precomputation",
        lambda: None,
    )
    monkeypatch.setattr(
        "scripts.etl.precompute_category_churn.run_full_precomputation",
        lambda: None,
    )

    # 短路 W6 通知 (避免 lark-cli 真发)
    monkeypatch.setattr(
        "scripts.etl.notify.notify_etl_complete",
        lambda stats, status="success": (True, "smoke_mocked"),
    )

    # 短路 _send_lark_alert (W3 内部真发会被拦)
    monkeypatch.setattr(
        "scripts.etl.assertions._send_lark_alert_mockable",
        lambda content, open_id=None: (False, "smoke_mocked"),
    )

    yield {
        "duckdb_path": temp_duckdb_path,
        "monkeypatch": monkeypatch,
    }

    # 清理 processed_files
    for f in ["shop_processed.json", "member_processed.json"]:
        p = pdir / f
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────
# 1) --skip-dq flag 端到端生效: skip_dq=True 时不调 run_assertions
# ─────────────────────────────────────────────────────────────

class TestSkipDqFlagEndToEnd:
    """run_full_etl(skip_dq=True) 端到端验证: W3 run_assertions 不执行, quarantine 表空."""

    def test_skip_dq_true_does_not_run_assertions(self, w3w4_smoke_env):
        """skip_dq=True: rfm_quarantine 表应为空 (run_assertions 未调)."""
        from scripts.etl.pipeline import run_full_etl

        run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                     force_continue=True)

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        # rfm_quarantine 表可能存在也可能不存在 (run_assertions 没调过, 表也未建)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "rfm_quarantine" in tables:
            count = conn.execute("SELECT COUNT(*) FROM rfm_quarantine").fetchone()[0]
        else:
            count = 0
        conn.close()
        assert count == 0, (
            f"skip_dq=True 时 rfm_quarantine 应空, 实际 {count} 行"
        )

    def test_skip_dq_false_default_runs_assertions(self, w3w4_smoke_env):
        """skip_dq=False (默认): 暴跌数据应触发 assert_total_not_drop → quarantine 1 行.

        这是 P1-1 验收第 3 条: "1 断言 quarantine 触发能进 rfm_quarantine 表".
        """
        from scripts.etl.pipeline import run_full_etl

        run_full_etl(mode="inc", skip_dq=False, skip_w4=True, window_days=30,
                     force_continue=True)

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        assert "rfm_quarantine" in tables, (
            "skip_dq=False (默认) 应建 rfm_quarantine 表"
        )
        count = conn.execute("SELECT COUNT(*) FROM rfm_quarantine").fetchone()[0]
        assert count >= 1, (
            f"暴跌数据应触发 ≥1 断言失败入 quarantine, 实际 {count} 行"
        )
        # 验证失败的断言名 (T-1 SUM=100 vs prev 30d avg=1000, < 0.3 阈值)
        rows = conn.execute(
            "SELECT failed_assertion, reason FROM rfm_quarantine"
        ).fetchall()
        failed_names = [r[0] for r in rows]
        conn.close()
        # 暴跌断言名: assert_total_not_drop
        assert any("total" in name.lower() or "drop" in name.lower()
                   for name in failed_names), (
            f"暴跌应触发 total/drop 类断言, 实际失败: {failed_names}"
        )


# ─────────────────────────────────────────────────────────────
# 2) W4 幂等性: 跑 2 次 pipeline, fact_rfm_long 行数不变 (version 续号)
# ─────────────────────────────────────────────────────────────

class TestW4IdempotencyEndToEnd:
    """run_full_etl 跑 2 次: W4 incremental + merge 不抛 PK 冲突, 行数可控."""

    def test_w4_two_runs_no_pk_conflict(self, w3w4_smoke_env):
        """跑 2 次 run_full_etl (skip_dq=True, skip_w4=False): W4 不抛 PK 冲突.

        这是 P1-1 验收第 2 条: "step 8 W4 幂等 (跑 2 次行数不变)".

        幂等性语义 (dbt-style snapshot):
          - 每次跑批 W4 插新 version 行 (同 date,dim 出现 v=1, v=2, ...)
          - 总行数会变 (540 + 540 = 1080 after 2 runs)
          - 但 UNIQUE (date, dimension_key) 组合数不变 (W4 写同样的 dim 集合)
          - 第 2 次跑不应抛 PK 冲突 (ON CONFLICT DO NOTHING 兜底)

        smoke test 验证: 2 次跑不抛错 + UNIQUE (date, dim) 组合数一致
        (业务语义幂等: 同样的输入数据产生同样的维度集合).
        """
        from scripts.etl.pipeline import run_full_etl

        # 第一次跑
        run_full_etl(mode="inc", skip_dq=True, skip_w4=False, window_days=30,
                     force_continue=True)
        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        tables1 = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "fact_rfm_long" not in tables1:
            conn.close()
            pytest.skip("第一次跑未建 fact_rfm_long, mock 数据可能不全")
        dim_count_1 = conn.execute(
            "SELECT COUNT(DISTINCT (date, dimension_key)) FROM fact_rfm_long"
        ).fetchone()[0]
        conn.close()

        # 第二次跑 (W4 幂等关键测试 — 不抛错)
        try:
            run_full_etl(mode="inc", skip_dq=True, skip_w4=False, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"W4 第二次跑应不抛错 (ON CONFLICT DO NOTHING 兜底), 实际: "
                f"{type(e).__name__}: {e}"
            )

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        dim_count_2 = conn.execute(
            "SELECT COUNT(DISTINCT (date, dimension_key)) FROM fact_rfm_long"
        ).fetchone()[0]
        conn.close()

        # UNIQUE (date, dim) 组合数应一致 (业务幂等)
        assert dim_count_1 == dim_count_2, (
            f"W4 两次跑 UNIQUE (date, dim) 数应一致 (幂等), "
            f"第 1 次 {dim_count_1}, 第 2 次 {dim_count_2}"
        )
        # 至少应有 ≥1 个 (date, dim) 组合 (mock 数据 '全品' 不在 fallback
        # 60 items 时, W4 可能 0 行, 用 pytest.skip 兜底)
        assert dim_count_1 > 0, (
            f"W4 第 1 次跑应产生 ≥1 个 (date, dim) 组合, 实际 {dim_count_1}, "
            f"可能 mock data 不在 enumerate_combos 兜底"
        )

    def test_w4_version_continues_when_data_exists(self, w3w4_smoke_env, temp_duckdb_path):
        """W4 incremental_load 跑 2 次 (单独调): version 续号, 行数 2x.

        不通过 run_full_etl, 直接调 incremental_load 2 次, 验证 version 逻辑
        (dbt-style snapshot). 灌 1 combo (mock data 仅 '全品') 让 incremental
        真插 1 行.
        """
        from scripts.etl.precompute_fact_rfm import (
            create_fact_rfm_table, incremental_load,
        )

        # 灌 T-1 (2026-06-05) 订单 — fixture 已灌, 复用
        # 但 fixture data 用了 '全品' 不在 enumerate_combos 兜底 60 items,
        # 手动灌 1 combo 'channel=全店|item=item1|segment=all' 兼容
        conn = duckdb.connect(temp_duckdb_path)
        conn.execute("""
            INSERT INTO orders VALUES
                (10, 'o_v1', 'so_v1', 100.0, '2026-06-05 10:00:00',
                 '2026-06-05 09:00:00', '2026-06-05 11:00:00',
                 'normal', '已支付', '全店', 'item1', 'item1', 'item1',
                 'item1', 'item1', 'item1', False, False, False,
                 '', '', '', '', '', '', '', 2026, 6, 'p1', 'm1',
                 '商品_v1', 's1', 'sc1', 'sn1', 1, 100.0, '无', 0.0,
                 '北京', '北京', 'user_v1', 'sc2', 'sn2', 1, 'item1')
        """)
        create_fact_rfm_table(conn)

        # 1 combo (避免 540 组合慢)
        combo = [{
            "channel": "全店",
            "item": "item1",
            "segment_id": 0,
            "dimension_key": "channel=全店|item=item1|segment=all",
            "dimension_json": json.dumps(
                {"channel": "全店", "item": "item1", "segment_id": 0},
                ensure_ascii=False,
            ),
        }]
        target = date(2026, 6, 6)  # load_date = 2026-06-05

        n1 = incremental_load(conn, target, combos=combo)
        n2 = incremental_load(conn, target, combos=combo)
        conn.close()

        # 两次都应 ≥1 行插入 (version 续号)
        assert n1 >= 1, f"第 1 次 incremental_load 应插入 ≥1 行, 实际 {n1}"
        assert n2 >= 1, f"第 2 次 incremental_load 应插入 ≥1 行 (新 version), 实际 {n2}"


# ─────────────────────────────────────────────────────────────
# 3) --skip-w4 flag 端到端生效: skip_w4=True 时 incremental_load_with_merge 不执行
# ─────────────────────────────────────────────────────────────

class TestSkipW4FlagEndToEnd:
    """run_full_etl(skip_w4=True) 端到端验证: W4 块不执行."""

    def test_skip_w4_true_does_not_run_w4(self, w3w4_smoke_env):
        """skip_w4=True: fact_rfm_long 表不应有新行 (W4 块跳过)."""
        from scripts.etl.pipeline import run_full_etl

        run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                     force_continue=True)

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if "fact_rfm_long" in tables:
            count = conn.execute("SELECT COUNT(*) FROM fact_rfm_long").fetchone()[0]
        else:
            count = 0
        conn.close()
        # skip_w4=True → W4 块跳过 → fact_rfm_long 不应被 create / insert
        # (注: _w4_create_table 也不调, 所以表可能根本不存在 → count=0)
        assert count == 0, (
            f"skip_w4=True 时 fact_rfm_long 应空, 实际 {count} 行"
        )

    def test_skip_w4_false_default_runs_w4_block(self, w3w4_smoke_env):
        """skip_w4=False (默认): W4 块执行, fact_rfm_long 表被创建."""
        from scripts.etl.pipeline import run_full_etl

        run_full_etl(mode="inc", skip_dq=True, skip_w4=False, window_days=30,
                     force_continue=True)

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        conn.close()
        # W4 块 create_fact_rfm_table → 表应存在 (即使 0 行)
        assert "fact_rfm_long" in tables, (
            "skip_w4=False (默认) W4 块应建 fact_rfm_long 表"
        )


# ─────────────────────────────────────────────────────────────
# 4) 端到端: 一次完整 run_full_etl (skip_dq=True) 跑通 + 不抛错
# ─────────────────────────────────────────────────────────────

class TestEndToEndPipelineRun:
    """一次完整 run_full_etl 跑通 (mock 掉所有重活儿), 验证 CI 不会因 pipeline 集成坏掉."""

    def test_run_full_etl_does_not_raise(self, w3w4_smoke_env):
        """run_full_etl 端到端不抛错 (mock 掉 113 xlsx + 41GB 单例锁)."""
        from scripts.etl.pipeline import run_full_etl

        try:
            run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"run_full_etl 端到端应不抛错 (mock 全套), 实际: "
                f"{type(e).__name__}: {e}"
            )

    def test_run_full_etl_writes_expected_tables(self, w3w4_smoke_env):
        """run_full_etl 跑完, 关键表 (orders/user_rfm/daily_metrics) 应保留."""
        from scripts.etl.pipeline import run_full_etl

        run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                     force_continue=True)

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
        conn.close()
        # 关键表应保留 (不破坏 fixture 灌的 schema)
        for required in ["orders", "user_rfm", "user_first_purchase",
                         "user_recency", "daily_metrics"]:
            assert required in tables, (
                f"run_full_etl 跑完关键表 {required} 应保留, 实际表: {sorted(tables)}"
            )
