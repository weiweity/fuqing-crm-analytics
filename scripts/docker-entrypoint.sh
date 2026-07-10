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

echo "DUCKDB_PATH: $DUCKDB_PATH"
echo "启动 uvicorn..."

UVICORN_WORKER_COUNT="${UVICORN_WORKERS:-2}"
if [ "${FQ_SINGLE_USER_V2:-0}" = "1" ]; then
    if [ -n "${UVICORN_WORKERS:-}" ] && [ "$UVICORN_WORKERS" != "1" ]; then
        echo "FATAL: FQ_SINGLE_USER_V2=1 时 UVICORN_WORKERS 必须为 1" >&2
        exit 1
    fi
    UVICORN_WORKER_COUNT=1
fi

exec python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers "$UVICORN_WORKER_COUNT"
