# 芙清 CRM - 后端 Dockerfile
# 基础镜像：固定 minor 标签；digest 见 docs/operating/docker-ports-and-images.md（人工锁定）
FROM python:3.13.5-slim-bookworm

WORKDIR /app

# 系统依赖（编译部分 wheel；slim 无 curl — healthcheck 用 Python urllib）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖（可复现 lock；禁止把 ML/OCR 大包打进 CRM 镜像）
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt

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
# 容器内监听端口（对外由 compose 映射 8000:8001）
ENV UVICORN_PORT=8001
# 默认单 worker：DuckDB 连接/写锁与进程模型不兼容多 worker 默认值
# 需要水平扩展时显式设 UVICORN_WORKERS，并确认 FQ_SINGLE_USER_V2!=1
ENV UVICORN_WORKERS=1

EXPOSE 8001

COPY --chown=appuser:appuser scripts/docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
