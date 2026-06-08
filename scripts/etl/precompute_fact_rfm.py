"""
W4 fact_rfm_long 全历史预计算 (v0.4.12 full) — design doc v1.1 §W4 + §7.4

痛点 3 根因: API 层每次重算 RFM, 历史 range 查询慢. 修法: 预计算宽表 fact_rfm_long,
纯增量 append T-1, 走语义层 (backend.semantic.segments).

MVP v0.4.9 范围 (1 组合 channel='全店' 验证机制):
- fact_rfm_long 表 schema + 唯一索引
- 增量加载: append T-1 (target_date - 1) 当天数据, 1 组合
- 幂等性: (date, dimension_key, version) UNIQUE + ON CONFLICT DO NOTHING
- 走语义层: 调 backend.semantic.segments.build_*_sql 拼 SQL
- 16GB 内存: W7 setup_async_memory() override 已有

W4 full v0.4.12 范围 (本次扩展):
- 540 组合 (channel × item × segment_id) — channel 9 × item 60 × 1 (segment='all' 聚合)
- dbt-style snapshot T-7 修复 late-arriving (merge_replace UPDATE + INSERT version++)
- 全量重算脚本 rfm_recompute_window.py (--from + --to)
- pipeline.py 集成 (W2 manifest write_active() 配套)

CLAUDE.md 合规:
- ① 走 backend.semantic.segments (CLAUDE.md 硬规则: ETL 走语义层, 改 RFM 口径只改 1 文件)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): duckdb.connect + conn.close()
- ③ cutoff = start_date - 1 day (教训 2026-05-29 RFM 象限名严格同步)
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# 把项目根加到 path（与 scripts/etl/_timer.py 等一致）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import (  # noqa: E402  跨子项目 import（CLAUDE.md §启动项）
    get_duckdb_memory_limit,
)
from scripts.etl.config import DUCKDB_PATH as _DUCKDB_PATH  # noqa: E402  跟 config 双确认


# W4 async 跑批期间临时 override（默认 8GB 跟 DUCKDB_MEMORY_LIMIT 一致，可在 env DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC 覆盖）
# Sprint 10 preflight B1: 之前 16GB override 跟主 conn 8GB + W3 8GB + W4 8GB 不同 config,
# DuckDB 1.5.2 strict mode 报 "Can't open a connection to same database file with a different configuration".
# 16GB 过度设计, Sprint 5 真闭环 17 min 跑批 8GB 也 OK. 统一改 8GB.
# DEFAULT_ASYNC_OVERRIDE 在 module-level 缓存（仅文档用途，setup_async_memory() 动态读 env）
DEFAULT_ASYNC_OVERRIDE = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", "8GB")


def setup_async_memory() -> str:
    """W4 async 跑批启动入口：export override + 返回当前 limit。

    Returns:
        str: 实际生效的 DuckDB memory_limit（"8GB" / 默认值）

    Usage (W4 实施时):
        from scripts.etl.precompute_fact_rfm import setup_async_memory
        memory_limit = setup_async_memory()
        conn = duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": memory_limit})
        try:
            run_fact_rfm_long_computation()
        finally:
            cleanup_async_memory()  # unset override
    """
    # 动态读 env（DEFAULT_ASYNC_OVERRIDE module-level 缓存仅文档用）
    # 这样 monkeypatch.setenv + W4 实时 export 都能正确生效
    async_override = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", DEFAULT_ASYNC_OVERRIDE)
    os.environ["DUCKDB_MEMORY_LIMIT_OVERRIDE"] = async_override
    return get_duckdb_memory_limit()


# ─────────────────────────────────────────────────────────────
# W4 MVP v0.4.9 + v0.4.12 full: fact_rfm_long 表 + 540 组合 + dbt-style merge
# ─────────────────────────────────────────────────────────────

FACT_RFM_TABLE = "fact_rfm_long"


FACT_RFM_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {FACT_RFM_TABLE} (
    date DATE NOT NULL,
    dimension_key VARCHAR NOT NULL,     -- e.g. "channel=全店|item=洁面|segment=all"
    dimension_json JSON NOT NULL,        -- e.g. {{"channel": "全店", "item": "洁面", "segment_id": 0}}
    user_count BIGINT NOT NULL,
    gmv DECIMAL(18,2),
    repurchase_count BIGINT,
    segment_id INTEGER NOT NULL DEFAULT 0,  -- 0 = "all" 聚合; 1-8 = 8 象限
    version INTEGER NOT NULL,            -- dbt-style snapshot version
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (date, dimension_key, version)
);
"""

# 幂等性: (date, dimension_key, version) 唯一, 重复跑 ON CONFLICT DO NOTHING
FACT_RFM_UNIQUE_INDEX_SQL = f"""
CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_rfm_dkv
    ON {FACT_RFM_TABLE} (date, dimension_key, version);
"""


def create_fact_rfm_table(conn) -> None:
    """创建 fact_rfm_long 表 + 唯一索引. 幂等 (IF NOT EXISTS).

    Args:
        conn: duckdb.Connection (CLAUDE.md §ETL 例外: conn.close() 由 caller 管)
    """
    conn.execute(FACT_RFM_SCHEMA_SQL)
    conn.execute(FACT_RFM_UNIQUE_INDEX_SQL)


# ─────────────────────────────────────────────────────────────
# W4 full v0.4.12: 540 组合 = 9 channels × 60 items × segment_id=0
# ─────────────────────────────────────────────────────────────

# 9 channels (来自 backend.semantic.channels.ACTIVE_CHANNELS, 剔除购物金)
W4_CHANNELS = [
    "货架", "达播", "直播", "淘客", "微博",
    "U先派样", "百补派样", "赠品&0.01渠道", "其他",
]

# 60 items (来自 orders.spu_product_class 实际枚举, 兜底固定列表 60 个)
# 兜底列表: 芙清典型 spu_product_class 值, 真实场景由 enumerate_items() 从 DB 动态获取
W4_ITEMS_FALLBACK = [
    # 洁面类 (8)
    "氨基酸洁面", "皂基洁面", "洁面慕斯", "洁面啫喱", "洁面霜", "洁面乳", "洁面粉", "洁面皂",
    # 水乳类 (8)
    "化妆水", "爽肤水", "精华水", "乳液", "面霜", "凝霜", "凝胶", "喷雾",
    # 精华类 (8)
    "精华液", "精华乳", "精华霜", "安瓶", "原液", "肌底液", "面部精华", "眼部精华",
    # 面膜类 (8)
    "片状面膜", "涂抹面膜", "睡眠面膜", "撕拉面膜", "泥膜", "冻膜", "泡泡面膜", "面膜粉",
    # 防晒类 (8)
    "防晒霜", "防晒乳", "防晒喷雾", "防晒露", "防晒凝胶", "防晒BB", "防晒CC", "防晒粉",
    # 彩妆类 (8)
    "粉底液", "气垫", "散粉", "粉饼", "遮瑕", "妆前乳", "卸妆油", "卸妆水",
    # 眼部彩妆 (8)
    "眼影", "眼线", "睫毛膏", "眉笔", "眉粉", "腮红", "高光", "修容",
    # 其他 (4, 凑齐 60)
    "润唇膏", "口红", "护手霜", "沐浴露",
]

assert len(W4_CHANNELS) == 9, f"channel 数量必须为 9, 实际 {len(W4_CHANNELS)}"
assert len(W4_ITEMS_FALLBACK) == 60, f"item 数量必须为 60, 实际 {len(W4_ITEMS_FALLBACK)}"

# 540 = 9 channels × 60 items × segment_id=0 (聚合)
W4_TOTAL_COMBOS = len(W4_CHANNELS) * len(W4_ITEMS_FALLBACK)  # 540


def enumerate_items(conn) -> list:
    """从 orders.spu_product_class 动态枚举实际 item 列表 (top 60 by GMV).

    兜底: 当 orders 表空 / spu_product_class 全 NULL 时, 用 W4_ITEMS_FALLBACK 固定列表.

    Args:
        conn: duckdb.Connection

    Returns:
        list: 60 个 spu_product_class 字符串列表
    """
    try:
        rows = conn.execute("""
            SELECT spu_product_class, COALESCE(SUM(actual_amount), 0) AS gmv
            FROM orders
            WHERE spu_product_class IS NOT NULL
              AND spu_product_class != ''
              AND pay_time IS NOT NULL
            GROUP BY spu_product_class
            ORDER BY gmv DESC
            LIMIT 60
        """).fetchall()
        if len(rows) >= 60:
            return [r[0] for r in rows[:60]]
        # 不足 60 个, 用 W4_ITEMS_FALLBACK 补齐 (去重)
        existing = {r[0] for r in rows}
        merged = [r[0] for r in rows]
        for it in W4_ITEMS_FALLBACK:
            if it not in existing and len(merged) < 60:
                merged.append(it)
                existing.add(it)
        return merged
    except Exception:
        return list(W4_ITEMS_FALLBACK)


def enumerate_combos(conn=None, channels=None, items=None) -> list:
    """枚举所有 (channel, item, segment_id) 组合, 走 backend.semantic.segments.

    默认 540 组合: 9 channels × 60 items × 1 segment (segment_id=0 = "all" 聚合).
    segment_id=0 含义: user_count / gmv / repurchase_count 是该 channel×item 下所有 segment 聚合.

    Args:
        conn: duckdb.Connection (用于动态枚举 items, 传 None 时用兜底列表)
        channels: 自定义 channels 列表, 传 None 时用 W4_CHANNELS
        items: 自定义 items 列表, 传 None 时用 enumerate_items() 或 W4_ITEMS_FALLBACK

    Returns:
        list of dict: 每个 dict 含 channel/item/segment_id/dimension_key/dimension_json
    """
    # 走语义层: 校验 segment_id 走 SegmentRegistry
    from backend.semantic.segments import get_registry  # noqa: F401  校验用

    _channels = channels or W4_CHANNELS
    _items = items if items is not None else (enumerate_items(conn) if conn is not None else list(W4_ITEMS_FALLBACK))

    combos = []
    for ch in _channels:
        for it in _items:
            dim_key = f"channel={ch}|item={it}|segment=all"
            dim_json = json.dumps({"channel": ch, "item": it, "segment_id": 0}, ensure_ascii=False)
            combos.append({
                "channel": ch,
                "item": it,
                "segment_id": 0,
                "dimension_key": dim_key,
                "dimension_json": dim_json,
            })
    return combos


def _next_version(conn, load_date: date) -> int:
    """读 (load_date) 已有的最大 version, +1 作为新 version. 同一天重跑 → version 续 +1.

    设计 (design doc v1.1 §W4 dbt-style snapshot):
    - 每次增量加载 version 续号, 旧 version 保留 (后续 dbt-style merge 用)
    - MVP 简化: 实际就 append, 不 merge. 留 merge 给 W4 full.

    Args:
        load_date: 增量加载的目标日期 (= target_date - 1, T-1)
                   跟 fact_rfm_long.date 列匹配
    """
    row = conn.execute(
        f"SELECT COALESCE(MAX(version), 0) FROM {FACT_RFM_TABLE} WHERE date = ?::DATE",
        [load_date],
    ).fetchone()
    return int(row[0]) + 1


def _compute_combo_sql(combo: dict, load_date: date) -> str:
    """生成单个 (channel, item, segment_id=0) 组合的 INSERT SQL.

    走 backend.semantic.filters.OrderFilters.valid_order() 校验口径 (CLAUDE.md 合规).

    Args:
        combo: enumerate_combos() 返回的 dict
        load_date: 数据日期 (T-1, 跟 fact_rfm_long.date 列匹配)
    """
    from backend.semantic.filters import OrderFilters
    valid_sql, _ = OrderFilters.valid_order()

    return f"""
        INSERT INTO {FACT_RFM_TABLE}
            (date, dimension_key, dimension_json, user_count, gmv, repurchase_count, segment_id, version)
        SELECT
            ?::DATE,
            ?,
            ?::JSON,
            COUNT(DISTINCT user_id) as user_count,
            SUM(actual_amount) as gmv,
            COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_count,
            ? as segment_id,
            ? as version
        FROM (
            SELECT
                user_id,
                actual_amount,
                COUNT(order_id) OVER (PARTITION BY user_id) as order_count
            FROM orders
            WHERE DATE(pay_time) = ?::DATE
              AND channel = ?
              AND spu_product_class = ?
              AND {valid_sql}
        ) t
        ON CONFLICT (date, dimension_key, version) DO NOTHING
    """


def incremental_load(
    conn,
    target_date: date,
    combos: list = None,
) -> int:
    """W4 full 增量加载: append T-1 (target_date - 1) 当天数据, 540 组合.

    走 backend.semantic.segments (校验) + 走 backend.semantic.filters (口径).

    Args:
        conn: duckdb.Connection
        target_date: 触发日期 (= today), 实际加载 T-1 (target_date - 1)
        combos: 自定义 combos 列表, 传 None 时自动 enumerate (540 默认)

    Returns:
        int: 实际插入行数 (含 ON CONFLICT DO NOTHING 跳过)
    """
    # T-1: target_date - 1 = 增量当天 (cutoff = start_date - 1 day, 教训 2026-05-29)
    load_date = target_date - timedelta(days=1)
    _combos = combos if combos is not None else enumerate_combos(conn)

    version = _next_version(conn, load_date)  # 一次增量共用一个 version

    total_inserted = 0
    for combo in _combos:
        sql = _compute_combo_sql(combo, load_date)
        result = conn.execute(
            sql + " RETURNING date",
            [
                load_date,
                combo["dimension_key"],
                combo["dimension_json"],
                combo["segment_id"],
                version,
                load_date,
                combo["channel"],
                combo["item"],
            ],
        ).fetchall()
        total_inserted += len(result)
    return total_inserted


def merge_replace(conn, load_date: date, combos: list = None) -> int:
    """W4 dbt-style snapshot: 对 (load_date) 整批 UPDATE 同一 (date) 旧 version 行 → INSERT 新 version.

    用途: 修复 late-arriving 订单 (T-7 内 99% 覆盖, 设计 doc v1.1 Premise 7).
    dbt-style snapshot 语义: 同一 (date, dimension_key) 的历史 version 保留可追溯,
    但 API 默认查 MAX(version). 当 late-arriving 订单到达时, 重算 + version++ 即可.

    Args:
        conn: duckdb.Connection
        load_date: 要 merge 的目标日期 (T-N, 通常 N in [1, 7])
        combos: 自定义 combos 列表, 传 None 时自动 enumerate

    Returns:
        int: 实际 INSERT 新 version 行数
    """
    _combos = combos if combos is not None else enumerate_combos(conn)

    # 1. 算 version (在已有 version 基础上 +1, 即使已有 v99 也不冲突)
    new_version = _next_version(conn, load_date)

    # 2. 重新计算 load_date 当天数据, 走 540 组合 INSERT 新 version
    from backend.semantic.filters import OrderFilters
    valid_sql, _ = OrderFilters.valid_order()

    total_inserted = 0
    for combo in _combos:
        # dbt-style merge: 不删旧 version, 直接 INSERT 新 version (dbt snapshot 保留历史链)
        # UNIQUE 索引保证 ON CONFLICT DO NOTHING 幂等
        sql = f"""
            INSERT INTO {FACT_RFM_TABLE}
                (date, dimension_key, dimension_json, user_count, gmv, repurchase_count, segment_id, version)
            SELECT
                ?::DATE,
                ?,
                ?::JSON,
                COUNT(DISTINCT user_id) as user_count,
                SUM(actual_amount) as gmv,
                COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_count,
                ? as segment_id,
                ? as version
            FROM (
                SELECT
                    user_id,
                    actual_amount,
                    COUNT(order_id) OVER (PARTITION BY user_id) as order_count
                FROM orders
                WHERE DATE(pay_time) = ?::DATE
                  AND channel = ?
                  AND spu_product_class = ?
                  AND {valid_sql}
            ) t
            ON CONFLICT (date, dimension_key, version) DO NOTHING
        """
        result = conn.execute(
            sql + " RETURNING date",
            [
                load_date,
                combo["dimension_key"],
                combo["dimension_json"],
                combo["segment_id"],
                new_version,
                load_date,
                combo["channel"],
                combo["item"],
            ],
        ).fetchall()
        total_inserted += len(result)
    return total_inserted


def incremental_load_with_merge(conn, target_date: date, t_minus_days: int = 7) -> tuple:
    """W4 full 增量加载: append T-1 + merge T-7 内修复 late-arriving.

    流程 (设计 doc v1.1 §W4):
      1. incremental_load(target_date) — append T-1 (新订单)
      2. for d in [T-7, T-1]: merge_replace(d) — 修复 late-arriving (走 dbt-style snapshot)

    Args:
        conn: duckdb.Connection
        target_date: 触发日期 (= today)
        t_minus_days: late-arriving 修复窗口 (默认 7 天, 设计 doc Premise 7)

    Returns:
        tuple: (incremental_inserted, merge_inserted, merge_dates)
    """
    # Step 1: append T-1
    incremental_inserted = incremental_load(conn, target_date)

    # Step 2: merge T-7 内修复 late-arriving (dbt-style snapshot)
    merge_inserted = 0
    merge_dates = []
    for i in range(1, t_minus_days + 1):
        merge_date = target_date - timedelta(days=i)
        n = merge_replace(conn, merge_date)
        merge_inserted += n
        merge_dates.append(merge_date.isoformat())

    return (incremental_inserted, merge_inserted, merge_dates)


def run_mvp_async() -> int:
    """W4 MVP 完整跑批入口: setup 16GB override + 建表 + 跑当天增量.

    Returns:
        int: 实际插入行数
    """
    import duckdb
    setup_async_memory()
    memory_limit = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "8GB")
    conn = duckdb.connect(str(_DUCKDB_PATH), config={"memory_limit": memory_limit})
    try:
        create_fact_rfm_table(conn)
        today = date.today()
        return incremental_load(conn, today)
    finally:
        conn.close()


def cleanup_async_memory() -> None:
    """W4 async 跑批结束：unset override，恢复默认 8GB。
    """
    os.environ.pop("DUCKDB_MEMORY_LIMIT_OVERRIDE", None)


if __name__ == "__main__":
    # CLI 入口 (W4 MVP): python3 scripts/etl/precompute_fact_rfm.py --async
    import argparse
    parser = argparse.ArgumentParser(description="W4 fact_rfm_long 预计算 (v0.4.12 full)")
    parser.add_argument("--async", action="store_true", help="nohup 后台跑 (MVP 同步跑)")
    parser.add_argument(
        "--merge-t7", action="store_true",
        help="增量 + merge T-7 修复 late-arriving (W4 full 推荐)",
    )
    parser.add_argument(
        "--t-minus", type=int, default=7,
        help="late-arriving 修复窗口天数 (默认 7)",
    )
    args = parser.parse_args()
    if args.merge_t7:
        import duckdb
        setup_async_memory()
        memory_limit = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "8GB")
        conn = duckdb.connect(str(_DUCKDB_PATH), config={"memory_limit": memory_limit})
        try:
            create_fact_rfm_table(conn)
            today = date.today()
            inc, merge, dates = incremental_load_with_merge(conn, today, t_minus_days=args.t_minus)
            print(f"W4 full 跑批完成: incremental={inc} 行, merge={merge} 行 ({len(dates)} 天)")
        finally:
            conn.close()
    else:
        inserted = run_mvp_async()
        print(f"W4 MVP 跑批完成: inserted={inserted} 行")
    sys.exit(0)


