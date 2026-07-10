"""
Sprint 205+ Windows NSSM 启动 wrapper (跟 macOS uvicorn_launchd.py 同位).
读 .env -> os.environ.setdefault() -> uvicorn.run().
NSSM 直接调这个 Python 文件,不走 macOS launchd 模式.
"""
import os
from pathlib import Path

# Force UTF-8 for stdout/stderr on Windows (fix Chinese garbled output)
os.environ["PYTHONIOENCODING"] = "utf-8"

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

# 1. 读 .env 注入 os.environ (setdefault 保留系统已有的,不覆盖 Windows 自身环境变量)
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

# 2. PYTHONPATH
os.environ["PYTHONPATH"] = str(REPO_ROOT)

# Sprint 205+ DuckDB 性能调优 (PC2 SSD + 64GB RAM + i5-14600K 14 核)
# memory_limit 默认 8GB, PC2 给 32GB (50% RAM)
# threads 默认 1, PC2 给 14 (i5-14600K 14 核 20 线程, 留 6 核给 ETL)
# ANALYZE_ON_START 启动时跑 ANALYZE 刷统计信息 (query planner 优化)
duckdb_memory = os.environ.get("DUCKDB_MEMORY_LIMIT", "32GB")
duckdb_threads = os.environ.get("DUCKDB_THREADS", "14")
print(f"[DUCKDB 调优] memory_limit={duckdb_memory}, threads={duckdb_threads}, analyze_on_start={os.environ.get('DUCKDB_ANALYZE_ON_START', '0')}")

# Sprint 205+ DuckDB ANALYZE 启动 hook (L4.68 永久规则化)
# ANALYZE 刷新 query planner 统计信息, 避免 table scan 慢
if os.environ.get("DUCKDB_ANALYZE_ON_START", "0") == "1":
    try:
        import duckdb
        from backend.config import DUCKDB_PATH
        _analyze_con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        _analyze_con.execute("ANALYZE")
        _tables = _analyze_con.execute("SELECT count(*) FROM duckdb_tables").fetchone()[0]
        print(f"[DUCKDB ANALYZE] 已分析 {_tables} 张表, query planner 优化完成")
        _analyze_con.close()
    except Exception as _e:
        print(f"[DUCKDB ANALYZE] 失败 (非致命, 不阻断启动): {_e}")

# 3. 启动 uvicorn
import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("UVICORN_PORT", "8000"))
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    if os.environ.get("FQ_SINGLE_USER_V2", "0") == "1" and workers != 1:
        raise SystemExit(
            "FQ_SINGLE_USER_V2=1 使用进程内 FIFO 租约，UVICORN_WORKERS 必须为 1"
        )
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level="info",
    )
