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

# 创建非 root 用户
RUN useradd -m -r appuser && \
    mkdir -p data/processed data/parquet data/cache && \
    chown -R appuser:appuser /app

# 项目代码
COPY --chown=appuser:appuser backend/ backend/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser config/ config/

# 环境变量
ENV PYTHONPATH=/app
ENV DUCKDB_PATH=/app/data/processed/fuqing.duckdb

EXPOSE 8000

COPY --chown=appuser:appuser scripts/docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 切换到非 root 用户
USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
