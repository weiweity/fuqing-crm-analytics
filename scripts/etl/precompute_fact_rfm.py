"""
W4 占位：fact_rfm_long 全历史预计算（独立 worker，nohup 异步跑）

设计：docs/design/etl-phase4-architecture.md §W4
- 背景：W4 全历史预计算需要临时 16GB 内存，平时 ETL 跑 8GB
- W7 集成：启动时 export DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB，跑完后 unset
- 状态：W7 完成 config.py + get_duckdb_memory_limit() helper；W4 实施时在本文件
  启动入口加 override 设置 + 调 get_duckdb_memory_limit() 拿真实 limit 拼 conn

实施时机：W4 工单（待立项，独立 12 步流程）
当前实现：仅暴露设计契约，W4 实际跑批逻辑按 W4 设计文档实施
"""
import os
import sys
from pathlib import Path

# 把项目根加到 path（与 scripts/etl/_timer.py 等一致）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import (  # noqa: E402  跨子项目 import（CLAUDE.md §启动项）
    get_duckdb_memory_limit,
)


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
