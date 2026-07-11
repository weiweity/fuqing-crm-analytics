# Sprint N+2 Trino Benchmark

> 状态: 待实测。当前仓库已提供可复现脚本；本机 Codex 环境没有 Docker CLI，未启动 Trino/MinIO/HMS，也未生成 100GB 数据集。

## 运行命令

```bash
docker compose -f docker-compose.trino.yml up -d

export FQ_TRINO_S3_ENDPOINT=http://127.0.0.1:19000
export FQ_TRINO_S3_ACCESS_KEY=minioadmin
export FQ_TRINO_S3_SECRET_KEY=minioadmin

PYTHONPATH="$(pwd)" python3 scripts/trino_poc/generate_dataset.py \
  --output-uri s3://fuqing-crm-poc/orders \
  --target-gb 100 \
  --batch-rows 50000 \
  --compression zstd

PYTHONPATH="$(pwd)" python3 scripts/trino_poc/register_table.py \
  --trino-url http://127.0.0.1:18080 \
  --data-location s3://fuqing-crm-poc/orders \
  --wait

PYTHONPATH="$(pwd)" python3 scripts/trino_poc/benchmark.py \
  --engine both \
  --duckdb-path data/processed/fuqing_crm.duckdb \
  --runs 10 \
  --output-json data/processed/trino_poc/benchmark_results.json \
  --output-md docs/sprints/SPRINT-N+2-TRINO-BENCHMARK.md
```

## 结果表

| Engine | Scenario | Runs | Rows | P50(s) | P95(s) | P99(s) |
|---|---:|---:|---:|---:|---:|---:|
| pending | s01_monthly_gmv GMV 月度聚合 | 10 | pending | pending | pending | pending |
| pending | s02_rfm_lifecycle_value_potential RFM 生命周期×价值×潜力 | 10 | pending | pending | pending | pending |
| pending | s03_channel_distribution_yoy Channel 渠道分布 | 10 | pending | pending | pending | pending |
| pending | s04_category_transition 品类流转 | 10 | pending | pending | pending | pending |
| pending | s05_refund_rate 退款率分析 | 10 | pending | pending | pending | pending |
| pending | s06_member_repurchase 老客复购率 | 10 | pending | pending | pending | pending |
| pending | s07_member_lifecycle_distribution 会员分布 | 10 | pending | pending | pending | pending |
| pending | s08_channel_share 渠道占比 | 10 | pending | pending | pending | pending |
| pending | s09_r_bucket_repurchase R 区间复购 | 10 | pending | pending | pending | pending |
| pending | s10_top20_category_growth 增速最快的 20 个品类 | 10 | pending | pending | pending | pending |

## 实测要求

- 每个场景跑 10 次，保留每轮耗时。
- Trino 和 DuckDB 使用同一业务时间窗。
- DuckDB 只用 read-only 连接，不停止 uvicorn。
- 实测后由脚本覆盖本文件，不手填 P50/P95/P99。
