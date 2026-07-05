# Trino 单节点 POC 运维手册

> Sprint N+2 交付物。目标是在本机用 Trino coordinator + 1 worker + MinIO + Hive Metastore 跑 100GB Parquet 查询基准，不触碰生产 DuckDB 文件锁。

## 1. 启动

```bash
docker compose -f docker-compose.trino.yml up -d
```

端口约定：

| 组件 | 容器端口 | 本机端口 |
|---|---:|---:|
| Trino coordinator | 8080 | 18080 |
| MinIO S3 | 9000 | 19000 |
| MinIO console | 9001 | 19001 |
| Hive Metastore | 9083 | 19083 |

本机端口避开现有 uvicorn `8000` 和前端 `5173`。Trino 容器内部仍用默认 `8080`。

## 2. 生成 Parquet 数据

小样本 smoke：

```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/generate_dataset.py \
  --output-uri data/trino-poc/orders \
  --rows 100000
```

100GB POC 数据集：

```bash
export FQ_TRINO_S3_ENDPOINT=http://127.0.0.1:19000
export FQ_TRINO_S3_ACCESS_KEY=minioadmin
export FQ_TRINO_S3_SECRET_KEY=minioadmin

PYTHONPATH="$(pwd)" python3 scripts/trino_poc/generate_dataset.py \
  --output-uri s3://fuqing-crm-poc/orders \
  --target-gb 100 \
  --batch-rows 50000 \
  --compression zstd
```

生成器字段来自 `backend/database.py:init_database()` 的 `orders` 表，不包含 ETL 内部临时字段。

## 3. 注册 Trino 表

```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/register_table.py \
  --trino-url http://127.0.0.1:18080 \
  --data-location s3://fuqing-crm-poc/orders \
  --wait
```

注册结果为 `hive.crm.orders`。脚本先建 `hive.crm` schema，再建外部 Parquet 表。

## 4. 跑 10 场景 benchmark

只跑 Trino：

```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/benchmark.py \
  --engine trino \
  --runs 10 \
  --output-json data/processed/trino_poc/benchmark_results.json \
  --output-md docs/sprints/SPRINT-N+2-TRINO-BENCHMARK.md
```

Trino + DuckDB 对比：

```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/benchmark.py \
  --engine both \
  --duckdb-path data/processed/fuqing_crm.duckdb \
  --runs 10
```

输出包含每个场景的 P50 / P95 / P99、返回行数和每轮耗时。

## 5. 清理

```bash
docker compose -f docker-compose.trino.yml down
```

如需删除 POC 数据卷：

```bash
docker compose -f docker-compose.trino.yml down -v
```

本 POC 不需要停止 uvicorn，不读写生产 DuckDB；DuckDB 对比只用 read-only 连接。

