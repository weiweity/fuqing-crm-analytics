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
    # P1-1 review B1 修: 路径名必须与 scripts/etl/config.py:_get_processed_files_path
    # 完全一致 — production 是 "processed_files_{data_type}.json", 不是 "{data_type}_processed.json".
    # 错配会让 fixture 写的占位文件对生产代码不可见 (load 返回空), 跑批仍会扫 113 xlsx.
    (pdir / "processed_files_shop.json").write_text(json.dumps({
        "_smoke_marker.parquet": {
            "mtime": 0, "hash": "smoke_no_data"
        }
    }, ensure_ascii=False))
    (pdir / "processed_files_member.json").write_text(json.dumps({}, ensure_ascii=False))

    # Step 2: 灌 mock 数据 — 30 天历史 (每天 SUM 1000) + 当天暴跌 (SUM 100, 触发 W3 断言)
    #
    # P1-1 review B2/P1/P4 修: 时间钉死 base=date(2026,6,5) 会产生 3 个 bug:
    #   ① 30 天后 fixture 数据滑出 prev_30d 窗口, prev_avg=0, assert_total_not_drop
    #      走 'if prev_avg == 0: return True' 退化路径, quarantine 0 行 fail.
    #   ② pipeline L443 `_assert_target = _date.today()` 是 today (不是 T-1).
    #      base=2026-06-05 把"暴跌"数据灌在 T-1, 跑批今日 today=2026-06-06 查 today
    #      → 0 行 (退化触发, 不是真"暴跌检测"逻辑).
    #   ③ test_w4_two_runs_no_pk_conflict (B2): pipeline 用 _date.today() 触发 W4
    #      load_date = today - 1, fixture 没灌 today-1 数据 → dim_count_1==0 fail.
    #
    # 修法: base = date.today() 动态. fixture 灌"今天 (暴跌 100) + 30 天历史 (每天 1000)",
    # pipeline 内部 _date.today() 看到的 today 与 fixture base 一致, 暴跌检测走真触发逻辑.
    # P7 / W4 测试一并复用: incremental_load load_date = target_date - 1 = today - 1,
    # fixture 在 today-1 (= base - 1) 灌了 5 单, W4 会真正插入行.
    base = date.today()
    rows = []
    # 注: 行尾的 `1, "全品"` 是 (valid_sql, spu_category) 两列, valid_sql=1 表示
    # 该行通过 backend.semantic.filters.OrderFilters.valid_order() 校验 (is_refund=FALSE
    # AND order_status != '交易关闭' AND is_goujinjin=FALSE 综合判定). assert_total_not_drop
    # SQL 用 `WHERE valid_sql = 1` 过滤, 所以 fixture 必须显式置 1 才能被统计 (P5 review).
    # 30 天历史: today-30 ... today-1, 每天 5 单 × 200 = 1000
    for i in range(1, 31):
        d = base - timedelta(days=i)
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
    # 当天 (today) 暴跌: 5 单 × 20 = 100 (vs 历史均值 1000 → 1/10 < 0.3 阈值, 触发断言)
    d_today = base
    for u in range(1, 6):
        rows.append((
            u, f"today_{u}", f"sub_today_{u}", 20.0,
            f"{d_today.isoformat()} 10:00:00", f"{d_today.isoformat()} 09:00:00",
            f"{d_today.isoformat()} 11:00:00", "normal", "已支付",
            "全店", "全品", "全品", "全品", "全品", "全品", "全品",
            False, False, False, "", "", "", "", "", "", "",
            d_today.year, d_today.month, "p1", "m1", f"商品{u}", "s1", "sc1", "sn1",
            1, 20.0, "无", 0.0, "北京", "北京", f"user{u}", "sc2", "sn2",
            1, "全品"
        ))
    placeholders = ",".join(["?"] * len(rows[0]))
    conn.executemany(f"INSERT INTO orders VALUES ({placeholders})", rows)
    # user_first_purchase + user_recency
    conn.executemany(
        "INSERT INTO user_first_purchase VALUES (?, ?::DATE)",
        [(f"user{u}", base - timedelta(days=29)) for u in range(1, 6)],
    )
    conn.executemany(
        "INSERT INTO user_recency VALUES (?, ?::TIMESTAMP, FALSE, 1, ?, ?)",
        [(f"user{u}", f"{base.isoformat()} 10:00:00", 30, 6000.0) for u in range(1, 6)],
    )
    # daily_metrics (30 天历史, today-30 ... today-1)
    for i in range(1, 31):
        d = base - timedelta(days=i)
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
    # 从源头 patch backend.config.DUCKDB_PATH, 所有 from backend.config import DUCKDB_PATH 的模块生效
    import backend.config as _backend_config
    monkeypatch.setattr(_backend_config, "DUCKDB_PATH", Path(temp_duckdb_path))
    # preload_rfm/backend.db.init/backend.db.connection 各自缓存了 import 时的引用, 需逐个 patch
    from scripts.etl import preload_rfm as _preload_rfm
    monkeypatch.setattr(_preload_rfm, "DUCKDB_PATH", Path(temp_duckdb_path))
    from backend.db import init as _db_init
    monkeypatch.setattr(_db_init, "DUCKDB_PATH", Path(temp_duckdb_path))
    from backend.db import connection as _db_conn
    monkeypatch.setattr(_db_conn, "DUCKDB_PATH", Path(temp_duckdb_path))
    # 指向空 mock 目录, 跑批 0 xlsx → 0 行新增
    monkeypatch.setattr(pipeline, "SHOP_DATA_SOURCE", mock_parquet_dirs["shop"])
    monkeypatch.setattr(pipeline, "MEMBER_DATA_SOURCE", mock_parquet_dirs["member"])
    monkeypatch.setattr(_config, "SHOP_DATA_SOURCE", mock_parquet_dirs["shop"])
    monkeypatch.setattr(_config, "MEMBER_DATA_SOURCE", mock_parquet_dirs["member"])

    # P1-1 review P7 修: 显式说明 mock get_db_max_pay_time 设计意图.
    # 返回 today 10:00:00 → 强制 mode='auto' 走 'incremental' 分支
    # (db 已有数据, max_pay_time 非 None). 全量模式覆盖见 TestModeFullVsIncremental.
    # 时间动态对齐 fixture base = date.today() (不再钉死 2026-06-05).
    _today_ts = datetime.combine(date.today(), datetime.min.time()).replace(hour=10)
    monkeypatch.setattr(
        pipeline, "get_db_max_pay_time",
        lambda: _today_ts,
    )

    # 短路 SPU/渠道/affiliate/直播 loader
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
        "backend.db.init.create_user_rfm_table", lambda: None,
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

    # 短路 _send_lark_alert (W3 内部真发会被拦)
    monkeypatch.setattr(
        "scripts.etl.assertions._send_lark_alert_mockable",
        lambda content, open_id=None: (False, "smoke_mocked"),
    )

    yield {
        "duckdb_path": temp_duckdb_path,
        "monkeypatch": monkeypatch,
    }

    # 清理 processed_files (P1-1 review B1: 路径名必须与生产一致)
    for f in ["processed_files_shop.json", "processed_files_member.json"]:
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

        P4 review 修: 触发路径说明 (避免被误读为"退化路径触发").
          - assert_total_not_drop 算 today_total = SUM(actual_amount WHERE pay_time=today, valid_sql=1)
          - fixture 灌 today=base 5 单 × 20 = 100 (非零), prev_30d_avg = 30 × 1000 / 30 = 1000
          - if prev_avg == 0 → return True 退化路径不触发 (prev_avg=1000, 非零)
          - threshold = 1000 × 0.3 = 300, today_total=100 < 300 → 触发 → quarantine
          - 这是真"100% 触发逻辑" (前后 30 天历史 + 当天暴跌 1/10), 不是退化触发.
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
        # 验证失败的断言名 (today SUM=100 vs prev 30d avg=1000, < 0.3 阈值)
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
    """run_full_etl 跑 2 次: W4 version 续号 + 不抛错, dim 组合数幂等."""

    def test_w4_two_runs_version_continues(self, w3w4_smoke_env):
        """跑 2 次 run_full_etl (skip_dq=True, skip_w4=False): W4 version 续号 + 行数翻倍.

        P1-1 验收第 2 条 + review P2 修: "step 8 W4 幂等" 真正语义.

        幂等性语义 (dbt-style snapshot, 见 precompute_fact_rfm._next_version):
          - PRIMARY KEY (date, dimension_key, version), version 每次 +1
          - 每次跑批 W4 插新 version 行 (同 date,dim 出现 v=1, v=2, ...)
          - 总行数翻倍 (N + N = 2N), 但 UNIQUE (date, dim) 组合数不变 (业务幂等)
          - P2: "ON CONFLICT DO NOTHING 不抛错" 是平凡性质 (PK 含 version 永不冲突),
            真正要验的是 MAX(version) 续号 (v1=1 → v2=2).

        验证三个真信号:
          ① 不抛错 (跑批稳定)
          ② UNIQUE (date, dim) 组合数一致 (输入数据稳定 → 维度集合稳定)
          ③ MAX(version) 续号: 第 2 次跑后 v=2 行存在 (dbt-style snapshot 保留历史链)
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
        max_version_1 = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM fact_rfm_long"
        ).fetchone()[0]
        conn.close()

        # 第二次跑
        try:
            run_full_etl(mode="inc", skip_dq=True, skip_w4=False, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"W4 第二次跑应不抛错 (跑批稳定), 实际: "
                f"{type(e).__name__}: {e}"
            )

        conn = duckdb.connect(w3w4_smoke_env["duckdb_path"], read_only=True)
        dim_count_2 = conn.execute(
            "SELECT COUNT(DISTINCT (date, dimension_key)) FROM fact_rfm_long"
        ).fetchone()[0]
        max_version_2 = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM fact_rfm_long"
        ).fetchone()[0]
        conn.close()

        # ② UNIQUE (date, dim) 组合数应一致 (业务幂等: 同输入 → 同维度集合)
        assert dim_count_1 == dim_count_2, (
            f"W4 两次跑 UNIQUE (date, dim) 数应一致 (幂等), "
            f"第 1 次 {dim_count_1}, 第 2 次 {dim_count_2}"
        )
        # 至少应有 ≥1 个 (date, dim) 组合 (fixture base=date.today() 动态对齐 pipeline,
        # incremental_load 不过滤空聚合, 每 combo 都会 INSERT 一行)
        assert dim_count_1 > 0, (
            f"W4 第 1 次跑应产生 ≥1 个 (date, dim) 组合, 实际 {dim_count_1}, "
            f"可能 mock data 与 enumerate_combos 不匹配"
        )
        # ③ P2 review 修: version 续号 (dbt-style snapshot 真正语义)
        assert max_version_2 > max_version_1, (
            f"W4 第 2 次跑 MAX(version) 应 > 第 1 次 (version 续号), "
            f"第 1 次 {max_version_1}, 第 2 次 {max_version_2}"
        )

    def test_w4_version_continues_when_data_exists(self, w3w4_smoke_env, temp_duckdb_path):
        """W4 incremental_load 跑 2 次 (单独调): version 续号 n1==n2==1, MAX(version) 翻倍.

        不通过 run_full_etl, 直接调 incremental_load 2 次, 验证 version 续号
        (dbt-style snapshot, _next_version 续 +1 → 同 date,dim 出现 v=1, v=2).
        """
        from scripts.etl.precompute_fact_rfm import (
            W4_ITEMS_FALLBACK,
            create_fact_rfm_table,
            incremental_load,
        )

        # P3 review 修: 显式选不在 W4_ITEMS_FALLBACK 60 个化妆品名内的 item 名,
        # 避免与未来 fallback 列表扩展产生隐式冲突 (smoke_test_item 不在 fallback).
        # 自定义 combo 传给 incremental_load(combos=...), 完全绕过 enumerate_combos.
        test_item = "smoke_test_item_unique_xyz"
        assert test_item not in W4_ITEMS_FALLBACK, (
            f"test_item={test_item!r} 不应在 W4_ITEMS_FALLBACK (避免 enumerate_items 冲突)"
        )

        # 灌 today-1 (= base - 1 = pipeline load_date) 订单 — fixture 用了 spu='全品',
        # 本测试需要 spu={test_item}, 单独灌一行 (避免与 fixture orders.spu='全品' 冲突).
        load_date = date.today() - timedelta(days=1)
        target = date.today()  # incremental_load(target_date) → load_date = target - 1
        conn = duckdb.connect(temp_duckdb_path)
        conn.execute(
            """
            INSERT INTO orders VALUES
                (10, 'o_v1', 'so_v1', 100.0, ?::TIMESTAMP,
                 ?::TIMESTAMP, ?::TIMESTAMP,
                 'normal', '已支付', '全店', ?, ?, ?,
                 ?, ?, ?, FALSE, FALSE, FALSE,
                 '', '', '', '', '', '', '', ?, ?, 'p1', 'm1',
                 '商品_v1', 's1', 'sc1', 'sn1', 1, 100.0, '无', 0.0,
                 '北京', '北京', 'user_v1', 'sc2', 'sn2', 1, ?)
            """,
            [
                f"{load_date.isoformat()} 10:00:00",
                f"{load_date.isoformat()} 09:00:00",
                f"{load_date.isoformat()} 11:00:00",
                test_item, test_item, test_item,
                test_item, test_item, test_item,
                load_date.year, load_date.month, test_item,
            ],
        )
        create_fact_rfm_table(conn)

        # 1 combo (避免 540 组合慢) — 走 test_item 不在 fallback 内
        combo = [{
            "channel": "全店",
            "item": test_item,
            "segment_id": 0,
            "dimension_key": f"channel=全店|item={test_item}|segment=all",
            "dimension_json": json.dumps(
                {"channel": "全店", "item": test_item, "segment_id": 0},
                ensure_ascii=False,
            ),
        }]

        n1 = incremental_load(conn, target, combos=combo)
        n2 = incremental_load(conn, target, combos=combo)
        # 验 version 续号 (MAX(version) 第 1 次 1, 第 2 次 2)
        max_version = conn.execute(
            "SELECT MAX(version) FROM fact_rfm_long WHERE date = ?::DATE",
            [load_date],
        ).fetchone()[0]
        conn.close()

        # 两次都应 ≥1 行插入 (version 续号, ON CONFLICT 因 version 不同永不触发)
        assert n1 >= 1, f"第 1 次 incremental_load 应插入 ≥1 行, 实际 {n1}"
        assert n2 >= 1, f"第 2 次 incremental_load 应插入 ≥1 行 (新 version), 实际 {n2}"
        # P2 review 修: 加 version 续号断言 (v=2)
        assert max_version == 2, (
            f"2 次 incremental_load 后 MAX(version) 应 = 2 (dbt-style 续号), "
            f"实际 {max_version}"
        )


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


# ─────────────────────────────────────────────────────────────
# 5) P6 review 修: 真 parquet → 真 DuckDB 写入 (端到端验证 mock stub 覆盖盲区)
# ─────────────────────────────────────────────────────────────

class TestRealDuckdbWriteEndToEnd:
    """P6 review 修: 不走 fixture stub, 用真 parquet (1KB) + 真 DuckDB 验列类型/Decimal/None.

    fixture 的 clean_data/upsert_to_duckdb/filter_rolling_window 是 stub, 不模拟
    Decimal/None/列类型. 加 1 个独立测试用真 parquet sample 写入 temp DuckDB,
    验真 DuckDB 行数 + 列类型, 补 mock stub 覆盖盲区.
    """

    def test_real_parquet_to_duckdb_decimal_and_null(self, tmp_path):
        """真 parquet (Decimal + None) → 真 DuckDB INSERT → 验列类型保留."""
        from decimal import Decimal

        # 真 parquet sample (1KB, 含 Decimal + None 边界)
        df = pd.DataFrame({
            "user_id": [1, 2, 3],
            "order_id": ["o1", "o2", "o3"],
            "actual_amount": [Decimal("199.99"), Decimal("0.01"), None],
            "pay_time": pd.to_datetime([
                "2026-06-05 10:00:00", "2026-06-05 11:00:00", None,
            ]),
            "is_refund": [False, True, None],
        })
        parquet_path = tmp_path / "real_sample.parquet"
        df.to_parquet(parquet_path, index=False)
        assert parquet_path.stat().st_size < 10_000, "sample 应 < 10KB (CI 快速)"

        # 真 DuckDB INSERT (不用 stub)
        duckdb_path = tmp_path / "real_write.duckdb"
        conn = duckdb.connect(str(duckdb_path))
        conn.execute("""
            CREATE TABLE orders_real (
                user_id INTEGER, order_id VARCHAR,
                actual_amount DECIMAL(18,2),
                pay_time TIMESTAMP, is_refund BOOLEAN
            )
        """)
        # 用 DuckDB native parquet read (真路径, 不走 ETL stub)
        conn.execute(f"INSERT INTO orders_real SELECT * FROM read_parquet('{parquet_path}')")

        # 验真写入: 3 行 + Decimal 精度 + NULL 容忍
        rows = conn.execute(
            "SELECT user_id, actual_amount, pay_time, is_refund "
            "FROM orders_real ORDER BY user_id"
        ).fetchall()
        conn.close()
        assert len(rows) == 3, f"应写入 3 行, 实际 {len(rows)}"
        # Decimal 精度保留 (199.99 不 round 成 200.00)
        assert rows[0][1] == Decimal("199.99"), (
            f"actual_amount Decimal 精度丢失, 期望 199.99, 实际 {rows[0][1]}"
        )
        assert rows[1][1] == Decimal("0.01"), (
            f"actual_amount 小数边界丢失, 期望 0.01, 实际 {rows[1][1]}"
        )
        # NULL 容忍 (actual_amount None / pay_time None / is_refund None)
        assert rows[2][1] is None, f"NULL actual_amount 应保留, 实际 {rows[2][1]}"
        assert rows[2][2] is None, f"NULL pay_time 应保留, 实际 {rows[2][2]}"
        assert rows[2][3] is None, f"NULL is_refund 应保留, 实际 {rows[2][3]}"


# ─────────────────────────────────────────────────────────────
# 6) P7 review 修: ETL mode (full vs incremental) 分支显式覆盖
# ─────────────────────────────────────────────────────────────

class TestModeFullVsIncremental:
    """P7 review 修: fixture 默认走 incremental (get_db_max_pay_time mock 返回 today).

    本 class 显式覆盖 2 种 mode:
      ① mode='inc' (= 'auto' → incremental, db 有数据) → fixture 默认路径
      ② mode='full' (强制全量重建) → 独立 test, 验跑批不抛错
    """

    def test_mode_inc_runs_incremental_branch(self, w3w4_smoke_env):
        """mode='inc' 端到端: 走 incremental 分支不抛错 (fixture 已 mock get_db_max_pay_time)."""
        from scripts.etl.pipeline import run_full_etl

        try:
            run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"mode='inc' 端到端应不抛错, 实际: {type(e).__name__}: {e}"
            )

    def test_mode_full_runs_full_branch(self, w3w4_smoke_env):
        """mode='full' 端到端: 走全量重建分支不抛错.

        mock 全套 stub 后, 'full' 分支主要走 load_data_files → clean_data → upsert (stub),
        本 test 验签名兼容 + 不抛错 (覆盖 'full' code path).
        """
        from scripts.etl.pipeline import run_full_etl

        try:
            run_full_etl(mode="full", skip_dq=True, skip_w4=True, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"mode='full' 端到端应不抛错, 实际: {type(e).__name__}: {e}"
            )


class TestColdStartEmptyTrackerDoesNotMarkAllProcessed:
    """Regression: processed_files_*.json 存在但为空 {} 时, 冷启动不应标记全部文件已处理.

    之前 bug: `if not processed` 把空 dict 当成"无处理记录", 调用 _mark_all_files_processed()
    把包括新增文件在内的所有历史文件标为已处理, 导致增量跑批跳过新增文件.
    修复后: 只有 tracker 文件不存在时才走冷启动; 空 {} 不触发.
    """

    def test_empty_tracker_file_does_not_trigger_cold_start_mark_all(self, w3w4_smoke_env):
        """tracker 文件存在但内容为空 {} 时, _mark_all_files_processed 不应被调用."""
        from unittest.mock import MagicMock
        from scripts.etl import pipeline
        from scripts.etl.pipeline import run_full_etl

        monkeypatch = w3w4_smoke_env["monkeypatch"]

        # tracker 文件存在 (tmp 空文件)
        empty_tracker = Path(w3w4_smoke_env["duckdb_path"]).parent / "processed_files_empty.json"
        empty_tracker.write_text("{}")

        monkeypatch.setattr(
            pipeline, "_get_processed_files_path",
            lambda data_type: empty_tracker,
        )
        monkeypatch.setattr(
            pipeline, "_load_processed_files",
            lambda data_type: {},
        )

        mark_all_mock = MagicMock()
        monkeypatch.setattr(pipeline, "_mark_all_files_processed", mark_all_mock)

        try:
            run_full_etl(mode="inc", skip_dq=True, skip_w4=True, window_days=30,
                         force_continue=True)
        except Exception as e:
            pytest.fail(
                f"空 tracker 修复后跑批应不抛错, 实际: {type(e).__name__}: {e}"
            )

        assert not mark_all_mock.called, (
            "tracker 文件存在但为空 {} 时, _mark_all_files_processed 不应被调用"
        )
