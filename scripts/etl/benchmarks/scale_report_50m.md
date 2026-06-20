# Sprint 52 - 50m Scale Benchmark

## Reproduce

```bash
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 1000000
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 5000000
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 10000000
# Run only after explicit approval and with >200 GiB free:
python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 50000000 --allow-50m
```

All generated inputs, trackers, performance output, and DuckDB files live under
`data/benchmarks/scale-<N>/`; the production DuckDB is never opened.

## Scale Results

| Orders | Status | Total sec | W1 generate sec | W2-W7 ETL sec | Peak RSS | Peak disk | DuckDB |
|---:|---|---:|---:|---:|---:|---:|---:|
| 10,000 | passed | 0.80 | 0.02 | 0.57 | 274.7 MiB | 0.01 GiB | 0.01 GiB |
| 1,000,000 | passed | 49.84 | 1.33 | 48.32 | 3372.4 MiB | 0.51 GiB | 0.49 GiB |

## Latest ETL Step Timings

The end-to-end ETL total includes every production stage, including W4 fact-RFM.
The per-step timers below expose source load, transform, DuckDB upsert, user
tables, daily metrics, category precompute, and W3 DQ assertions; W4 currently
has no dedicated `PerfTimer`, so it remains inside the aggregate ETL time.

| Timer | Wall sec | CPU sec | Peak RSS MiB |
|---|---:|---:|---:|
| pl_step1_load_ref_data | 0.0003 | 0.0003 | 297.6 |
| load_filter_rolling_window | 0.0685 | 0.0683 | 2087.8 |
| pl_step2_5_filter_rolling_window | 0.0873 | 0.0871 | 2087.8 |
| transform_match_channel | 0.2609 | 0.2604 | 2126.7 |
| transform_clean_data | 1.4939 | 1.4929 | 2242.8 |
| pl_step3_clean_data_new | 1.4939 | 1.4929 | 2242.8 |
| load_upsert_to_duckdb | 4.3265 | 5.9061 | 3002.1 |
| pl_step4_upsert_to_duckdb | 4.3265 | 5.9061 | 3002.1 |
| pl_step4_7_replay_is_member_incremental | 33.8274 | 51.6357 | 3318.0 |
| pl_step6_user_first_purchase | 1.2303 | 1.8108 | 3318.0 |
| pl_step6_5_user_recency | 1.2581 | 1.9039 | 3318.0 |
| pl_step6_7_update_metrics_after_ufp | 0.1404 | 0.4001 | 3318.0 |
| pl_step8a_category_flow | 1.1064 | 7.1357 | 3318.0 |
| pl_step8b_category_churn | 0.1930 | 0.8428 | 3345.2 |
| pl_step8_5_dq_assertions | 0.0040 | 0.0051 | 3345.3 |

## Capacity Gate

Current host physical memory: 16.00 GiB. Projections are linear
planning estimates from the largest completed rung, not substitute measurements.

| Orders | Evidence | Peak RSS | Decision |
|---:|---|---:|---|
| 5,000,000 | projected from 1,000,000 | 16.47 GiB | not run; projected RSS exceeds 80% of host memory |
| 10,000,000 | projected from 1,000,000 | 32.93 GiB | not run; projected RSS exceeds 80% of host memory |
| 50,000,000 | projected from 1,000,000 | 164.67 GiB | approval required; current host memory is insufficient |

## Bottleneck Notes

- W1 generates Parquet inside DuckDB, so Python does not materialize all rows.
- W2-W7 intentionally use the production incremental ETL. Its current Parquet
  ingest concatenates source files into Pandas DataFrames, so peak RSS is the
  primary scaling risk to watch at 10m and 50m.
- Slowest measured ETL timer: `pl_step4_7_replay_is_member_incremental` at 33.83s.
- A failed rung still writes `result.json` and updates this report before exit.
