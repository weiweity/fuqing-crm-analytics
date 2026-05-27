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

exec python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 2
