#!/bin/bash
set -e

echo "=========================================="
echo "芙清 CRM 后端服务启动"
echo "=========================================="

# 确保数据目录存在
mkdir -p /app/data/processed /app/data/parquet /app/data/cache

# 生成 API Key（如果未设置）
if [ -z "$HEALTH_API_KEY" ]; then
    export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    echo "已自动生成 HEALTH_API_KEY"
fi

# 容器内端口：默认 8001（与 nginx proxy_pass / compose 映射一致）
# 本地非 Docker 仍可在 README 用 8000；勿混用。
UVICORN_PORT="${UVICORN_PORT:-8001}"

echo "DUCKDB_PATH: $DUCKDB_PATH"
echo "UVICORN_PORT: $UVICORN_PORT"
echo "启动 uvicorn..."

# 默认 1 worker：
# - DuckDB 文件锁 / 连接池与多 worker 进程模型易冲突
# - FQ_SINGLE_USER_V2=1 强制单 worker（会话一致性）
# - 需要 >1 时显式 export UVICORN_WORKERS=N，并确认无单用户模式
UVICORN_WORKER_COUNT="${UVICORN_WORKERS:-1}"
if [ "${FQ_SINGLE_USER_V2:-0}" = "1" ]; then
    if [ -n "${UVICORN_WORKERS:-}" ] && [ "$UVICORN_WORKERS" != "1" ]; then
        echo "FATAL: FQ_SINGLE_USER_V2=1 时 UVICORN_WORKERS 必须为 1" >&2
        exit 1
    fi
    UVICORN_WORKER_COUNT=1
fi

echo "UVICORN_WORKERS: $UVICORN_WORKER_COUNT"

exec python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "$UVICORN_PORT" \
    --workers "$UVICORN_WORKER_COUNT"
