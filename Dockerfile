# 芙清 CRM - 后端 Dockerfile
FROM python:3.13-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 项目代码
COPY backend/ backend/
COPY scripts/ scripts/
COPY config/ config/

# 数据目录（挂载卷）
RUN mkdir -p data/processed data/parquet data/cache

# 环境变量
ENV PYTHONPATH=/app
ENV DUCKDB_PATH=/app/data/processed/fuqing.duckdb

EXPOSE 8001

COPY scripts/docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
