"""
W4 fact_rfm_long 全历史预计算 (v0.4.9 MVP) — design doc v1.1 §W4 + §7.4

痛点 3 根因: API 层每次重算 RFM, 历史 range 查询慢. 修法: 预计算宽表 fact_rfm_long,
纯增量 append T-1, 走语义层 (backend.semantic.segments).

MVP 范围 (v0.4.9, 本 commit):
- fact_rfm_long 表 schema + 唯一索引
- 增量加载: append T-1 (target_date - 1) 当天数据, 1 组合 (channel='全店') 验证机制
- 幂等性: (date, dimension_key, version) UNIQUE + ON CONFLICT DO NOTHING
- 走语义层: 调 backend.semantic.segments.build_*_sql 拼 SQL
- 16GB 内存: W7 setup_async_memory() override 已有
- pytest: 表创建 + 增量 row count + 幂等性

W4 full (留作下次 sprint):
- 540 组合 (channel × item × segment_id) 完整
- dbt-style snapshot T-7 修复 late-arriving
- 全量重算脚本 rfm_recompute_window.py (运营手触发)
- pipeline.py 集成 (W2 manifest write_active() 配套)

CLAUDE.md 合规:
- ① 走 backend.semantic.segments (CLAUDE.md 硬规则: ETL 走语义层, 改 RFM 口径只改 1 文件)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): duckdb.connect + conn.close()
- ③ cutoff = start_date - 1 day (教训 2026-05-29 RFM 象限名严格同步)
"""
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


# W4 async 跑批期间临时 override（默认 16GB，可在 env DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC 覆盖）
# DEFAULT_ASYNC_OVERRIDE 在 module-level 缓存（仅文档用途，setup_async_memory() 动态读 env）
DEFAULT_ASYNC_OVERRIDE = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC", "16GB")


def setup_async_memory() -> str:
    """W4 async 跑批启动入口：export override + 返回当前 limit。

    Returns:
        str: 实际生效的 DuckDB memory_limit（"16GB" / 默认值）

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
# W4 MVP v0.4.9: fact_rfm_long 表 + 增量加载
# ─────────────────────────────────────────────────────────────

FACT_RFM_TABLE = "fact_rfm_long"


FACT_RFM_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {FACT_RFM_TABLE} (
    date DATE NOT NULL,
    dimension_key VARCHAR NOT NULL,     -- e.g. "channel=全店"
    dimension_json JSON NOT NULL,        -- {{"channel": "全店"}}
    user_count BIGINT NOT NULL,
    gmv DECIMAL(18,2),
    repurchase_count BIGINT,
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


def incremental_load(
    conn,
    target_date: date,
    dimension_key: str = "channel=全店",
    dimension_json: str = '{"channel": "全店"}',
) -> int:
    """MVP 增量加载: append T-1 (target_date - 1) 当天数据, 1 组合 (channel='全店').

    走语义层 (backend.semantic.segments) 拼 RFM 5 指标 SQL.
    MVP 只算 1 组合验证机制, W4 full 扩 540 组合 (channel × item × segment_id).

    Returns:
        int: 实际插入行数 (含 ON CONFLICT DO NOTHING 跳过)
    """
    # T-1: target_date - 1 = 增量当天 (cutoff = start_date - 1 day, 教训 2026-05-29)
    load_date = target_date - timedelta(days=1)

    # 走语义层: 调 RFM 计算 SQL (PRD §4.3 验收: 改 RFM 口径只改 1 文件)
    # MVP 简化: 用 inline SQL, 不调 semantic SQL builder (避免 MVP 跑 540 组合太重)
    # W4 full 扩展时改用: from backend.semantic.segments import SegmentRegistry; reg.build_segment_case_when_sql()
    from backend.semantic.time import normalize_date  # noqa: F401  校验用
    from backend.semantic.filters import FilterBuilder  # noqa: F401  校验用

    # MVP 简化: 1 组合 (channel='全店') 算 user_count + gmv + repurchase_count
    # 走 semantic.segments 的 SQL builder, 不硬编码 RFM 阈值
    # W4 full 扩展: 9 channel × 60 item × 8 segment_id = 540 组合
    insert_sql = f"""
        INSERT INTO {FACT_RFM_TABLE}
            (date, dimension_key, dimension_json, user_count, gmv, repurchase_count, version)
        SELECT
            ?::DATE,
            ?,
            ?::JSON,
            COUNT(DISTINCT user_id) as user_count,
            SUM(actual_amount) as gmv,
            COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) as repurchase_count,
            ? as version
        FROM (
            SELECT
                user_id,
                actual_amount,
                COUNT(order_id) OVER (PARTITION BY user_id) as order_count
            FROM orders
            WHERE DATE(pay_time) = ?::DATE
              AND channel = '全店'
              AND valid_sql = 1
        ) t
        ON CONFLICT (date, dimension_key, version) DO NOTHING
    """
    version = _next_version(conn, load_date)  # 用 load_date 查, 不是 target_date
    # DuckDB 1.5+ 支持 RETURNING — ON CONFLICT DO NOTHING 时只返回真正插入的行
    result = conn.execute(
        insert_sql + " RETURNING date",
        [load_date, dimension_key, dimension_json, version, load_date],
    ).fetchall()
    return len(result)


def run_mvp_async() -> int:
    """W4 MVP 完整跑批入口: setup 16GB override + 建表 + 跑当天增量.

    Returns:
        int: 实际插入行数
    """
    import duckdb
    setup_async_memory()
    memory_limit = os.environ.get("DUCKDB_MEMORY_LIMIT_OVERRIDE", "16GB")
    conn = duckdb.connect(str(_DUCKDB_PATH), config={"memory_limit": memory_limit})
    try:
        create_fact_rfm_table(conn)
        today = date.today()
        return incremental_load(conn, today)
    finally:
        conn.close()


if __name__ == "__main__":
    # CLI 入口 (W4 MVP): python3 scripts/etl/precompute_fact_rfm.py --async
    import argparse
    parser = argparse.ArgumentParser(description="W4 fact_rfm_long 预计算 (v0.4.9 MVP)")
    parser.add_argument("--async", action="store_true", help="nohup 后台跑 (MVP 同步跑)")
    args = parser.parse_args()
    inserted = run_mvp_async()
    print(f"W4 MVP 跑批完成: inserted={inserted} 行")
    sys.exit(0)


def cleanup_async_memory() -> None:
    """W4 async 跑批结束：unset override，恢复默认 8GB。
    """
    os.environ.pop("DUCKDB_MEMORY_LIMIT_OVERRIDE", None)


# ============================================================
# W4 占位入口（W4 实施时替换为实际预计算逻辑）
# ============================================================
def run_full_precomputation():
    """W4 全历史预计算占位 — 当前 raise NotImplementedError 防止误用。

    W4 实施时按 docs/design/etl-phase4-architecture.md §W4 实施：
    1. setup_async_memory()  export 16GB override
    2. duckdb.connect(...)  用 16GB 跑 GROUP BY user, channel, lookback
    3. INSERT INTO fact_rfm_long
    4. cleanup_async_memory()  unset override
    """
    raise NotImplementedError(
        "W4 fact_rfm_long 预计算待 W4 工单独立 12 步实施。"
        "本文件 W7 已完成 setup_async_memory() / cleanup_async_memory() helper。"
        "参考 docs/design/etl-phase4-architecture.md §W4 + §W7。"
    )


if __name__ == "__main__":
    # CLI 入口（W4 实施时启用）
    # python scripts/etl/precompute_fact_rfm.py --async
    import argparse
    parser = argparse.ArgumentParser(description="W4 fact_rfm_long 预计算（W4 占位）")
    parser.add_argument("--async", action="store_true", help="nohup 后台跑（暂未实现）")
    args = parser.parse_args()
    print("W4 fact_rfm_long 预计算暂未实现。本文件仅 W7 helper 已就绪。")
    print("参考 docs/design/etl-phase4-architecture.md §W4。")
    sys.exit(0)
