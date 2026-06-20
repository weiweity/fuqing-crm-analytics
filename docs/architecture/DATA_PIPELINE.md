# 数据管道架构 (Data Pipeline)

> ETL 4 阶段 (W1→W2→W3→W4) 数据流图 + 关键 metrics + 50M scale 触发条件 + Sprint 52 实战。

**最后更新**: 2026-06-21
**Sprint 收口验证**: Sprint 28+ 端到端跑批 (10.75M 订单, 12.5h 总计 ~32min)

---

## 1. 4 阶段总览

```
W1 增量拉取          W2 数据规范化         W3 预计算           W4 RFM/clickhouse
─────────          ────────────         ──────────          ─────────────────
data/raw/      →   data/parquet/    →   data/processed/ →   data/processed/
channel_details/    member/ shop/        fuqing_crm.duckdb    fuqing_crm.duckdb
csv (11 渠道)       parquet (列存)       orders + 规范化表    + fact_rfm_long
                                         + 6 DQ 断言          + 540 combo batch
                                                                    ↓
                                                              FastAPI /v1/* endpoint
```

| 阶段 | 入口脚本 | 输出 | 耗时 (10.75M) | 失败处理 |
|---|---|---|---|---|
| **W1** | `scripts/etl/ingest.py` | W2 输入 csv 临时区 | ~2 min | 重试 3 次 + 飞书告警 |
| **W2** | `scripts/etl/transform.py` | `data/parquet/{member,shop}/` | ~3 min | 跳过无变化 + 飞书告警 |
| **W3** | `scripts/etl/assertions.py` | DuckDB orders + 6 DQ 断言 | ~5 min | 失败记录到 `rfm_quarantine` 不阻塞 |
| **W4** | `scripts/etl/precompute_fact_rfm.py` | `fact_rfm_long` 540 combo batch | **~3s** (Sprint 30.1 50.4× 加速) | 失败 graceful degrade, 不阻塞 ETL |

---

## 2. 数据流图 (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│  业务方                                                                │
│  ├── data/raw/channel_details/  (11 渠道 csv, 不可变)                  │
│  ├── analysis/sampling_*.xlsx  (业务方分析模板)                          │
│  └── config/health_config.json (健康评分配置)                            │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  W1 增量拉取 (scripts/etl/ingest.py)                                  │
│  - 11 渠道 csv → tmp staging                                          │
│  - live_file_cache.json + taoke_order_ids.pkl 索引                     │
│  - 输出: W2 输入 + 增量 delta                                          │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  W2 数据规范化 (scripts/etl/transform.py)                              │
│  - 订单宽表 → long format                                              │
│  - 输出: data/parquet/member/*.parquet  (会员维表)                      │
│         data/parquet/shop/*.parquet    (店铺维表)                      │
│  - DuckDB ATTACH parquet 读                                            │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  W3 预计算 + DQ (scripts/etl/assertions.py)                            │
│  - DuckDB orders 主表 (~115GB, 10.75M 行)                              │
│  - 6 DQ 断言 (member_ratio / orders_count / etc.)                     │
│  - 失败 → rfm_quarantine 表 (不阻塞)                                   │
│  - dq_snapshot.json 覆盖写 (单文件, 反映最新状态)                        │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  W4 RFM 预计算 (scripts/etl/precompute_fact_rfm.py)                    │
│  - fact_rfm_long 540 组合 batch INSERT (Sprint 30.1 优化)               │
│  - incremental + merge_replace T-7 (修复 late-arriving orders)         │
│  - 输出: data/processed/fuqing_crm.duckdb.fact_rfm_long                 │
│  - 耗时: ~3s (旧版 165s, 50.4× 加速)                                    │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI endpoint (uvicorn)                                            │
│  - /v1/metrics/*       (主指标)                                        │
│  - /v1/flow/*          (RFM 桑基图, 读 W4 预计算)                       │
│  - /v1/health/*        (健康评分, 读 W3 + config)                      │
│  - /v1/exports/gsv     (CSV 导出, 读 W3)                              │
│  - /v1/sampling/*      (派样分析, 读 W3 + analysis/*.xlsx)             │
└─────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  前端 Vue 3 (frontend-vue3/)                                            │
│  - Overview / Audience / Sampling / RFM / Health / Report views        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 关键 metrics

### 3.1 DuckDB 库

| 指标 | 当前值 | 来源 | 备注 |
|---|---|---|---|
| orders 表行数 | 10.75M | W3 主表 | Sprint 28+ 端到端跑批验证 |
| 库大小 | 115GB | `data/processed/fuqing_crm.duckdb` | 含预计算表 + 索引 |
| fact_rfm_long 行数 | ~6M | W4 预计算 | 540 combo × 365 天 |
| member 维表 | ~5M | `data/parquet/member/` | |
| shop 维表 | ~500 | `data/parquet/shop/` | |

### 3.2 ETL 跑批性能 (Sprint 28+ 实测)

| 阶段 | 旧耗时 | 新耗时 | 加速 | Sprint |
|---|---|---|---|---|
| W1 ingest | ~3 min | ~2 min | 1.5× | Sprint 9 retry 优化 |
| W2 transform | ~5 min | ~3 min | 1.7× | Sprint 9 |
| W3 assertions | ~8 min | ~5 min | 1.6× | Sprint 28+ 6 断言 |
| W4 fact_rfm_long (旧版 serial) | **165s** | - | - | Sprint 30.0 旧版 |
| W4 fact_rfm_long (新 batch) | - | **~3s** | 50.4× | Sprint 30.1 |
| **ETL 总计** | 12.5h | **~32 min** | - | Sprint 28+ |

### 3.3 Query 性能 (单查询, 3 次平均, 10.6M 库)

| 场景 | 耗时 | 备注 |
|---|---|---|
| 全店复购率 | 0.129s | 走 W3 索引 |
| RFM 分群 (实时) | 0.624s | 旧版实时算, 新版走 W4 预计算 0.002s |
| 渠道占比 | 0.321s | 走 W3 索引 |
| 30 指标对比 | 0.760s | 走 W3 索引 |
| **合计** | **1.835s** | |

---

## 4. 50M scale 触发条件

> 详见 [docs/architecture/50m-scale-architecture.md](50m-scale-architecture.md) (Sprint 52 留尾, 30M 触发)

### 4.1 触发条件 (Phase 1-3 推后)

| 阈值 | 当前 | Phase 1 触发 | Phase 2 触发 | Phase 3 触发 |
|---|---|---|---|---|
| orders 表行数 | 10.75M | **30M** | 50M | 100M |
| 库大小 | 115GB | ~300GB | ~500GB | ~1TB |
| 单查询耗时 (合计) | 1.835s | ~5s | ~10s (实测 10.7s) | ~20s |
| RSS 峰值 | 2.3GB | ~5GB | ~4GB (50M 实测) | ~10GB |

### 4.2 当前 (10.75M) 性能预测 (50M benchmark)

> 2026-06-09 跑批实测, `data/processed/fuqing_crm_50m.duckdb` 7.3 GB (仅 orders)

| 场景 | 10.6M | 50M | 倍率 |
|---|---|---|---|
| 全店复购率 | 0.129s | 0.556s | 4.31× |
| RFM 分群 (实时) | 0.624s | 6.772s | 10.86× |
| 渠道占比 | 0.321s | 1.066s | 3.32× |
| 30 指标对比 | 0.760s | 2.280s | 3.00× |
| **合计** | **1.835s** | **10.674s** | **5.82×** |

数据量增长 ~4.7×, 查询耗时增长 ~5.8×, 接近线性扩展。**Phase 1 触发点 (30M) 性能余量充足**。

### 4.3 Phase 1-3 推后决策 (Sprint 52 P2 留尾)

| Phase | 内容 | 推后原因 |
|---|---|---|
| Phase 1 | fact_rfm_long 物化 + clickhouse 预聚合 | 当前 10.75M 不需要, 30M 触发 |
| Phase 2 | 分区表 (按月) + ClickHouse 列存 | 50M 触发 |
| Phase 3 | 读写分离 + 多副本 | 100M 触发 |

**实战教训** (Sprint 52): race flake 治本 + commit-msg diff check + 50m scale benchmark 三 worktree 并行, 详见 Sprint 52 close memory。

---

## 5. Sprint 52 实战 (Codex 协作工作流)

> Sprint 52 是 Codex 工作流 (Claude 架构 + Codex 实施) 第二次实战验证。

### 5.1 三 worktree 实施

| Worktree | 任务 | Stage 2 实施 | Stage 3 review 抓 |
|---|---|---|---|
| `feature/sprint52-visitor` | visitor 路由激活 | Codex 加 frontend router + backend endpoint | Claude 抓 hook 隔离 |
| `feature/sprint52-50m-scale` | 50m scale benchmark | Codex 写 benchmark 脚本 | Claude 抓 main core.bare 漂移 |
| `feature/sprint52-commit-msg` | commit-msg diff 一致性 WARN hook | Codex 写 hook | Claude 抓 pytest hooksPath 隔离 |

### 5.2 Stage 3 review 抓 1 真 bug (典型案例)

- **症状**: Stage 2 跑 pytest 全绿, Stage 3 review 时发现
- **根因**: 1m scale benchmark 在 49.84s 跑过, 50m scale 理论应该 ~10s 线性, 但实际 hang
- **修法**: Claude 抓 main core.bare 漂移 (worktree git config 不一致), 改后 50m scale benchmark 正常 1m 49.84s pass

### 5.3 Stage 4 三分支独立 commit/push/merge

```
feature/sprint52-visitor       → 独立 merge  →  1 commit
feature/sprint52-50m-scale     → 独立 merge  →  1 commit
feature/sprint52-commit-msg    → 独立 merge  →  1 commit
```

每分支 12 步流程完整, post-merge hook 自动追加 `.ship-audit.log` (Sprint 41+ Meta-Sprint /ship 接入)。

---

## 6. 故障排查

### 6.1 W1 拉取失败

```bash
# 1. 检查 11 渠道 csv 是否齐全
ls data/raw/channel_details/

# 2. 检查 live_file_cache.json 索引
ls -la data/processed/live_file_cache.json data/processed/taoke_*.pkl

# 3. 重跑 W1
python -m scripts.etl.pipeline --skip-w2 --skip-w3 --skip-w4
```

### 6.2 W3 DQ 断言失败

```bash
# 1. 看 rfm_quarantine 表 (失败订单隔离区, 不阻塞 W4)
python -c "
import duckdb
conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)
print(conn.execute('SELECT * FROM rfm_quarantine ORDER BY ts DESC LIMIT 20').fetchdf())
"

# 2. 跑 W3 调试模式
python -m scripts.etl.pipeline --skip-w1 --skip-w2 --skip-w4
```

### 6.3 W4 失败 graceful degrade

```bash
# W4 失败不阻塞 ETL 已完成的事实 (跟 W6 通知同样 graceful degrade)
# 手动重跑:
python -m scripts.etl.precompute_fact_rfm --incremental --merge-window 7
```

---

## 关联文档

- [STATUS.md](../../STATUS.md) — 项目总状态 (版本 + 测试 + debt)
- [docs/data-layout.md](../data-layout.md) — data/ 目录布局
- [docs/architecture/50m-scale-architecture.md](50m-scale-architecture.md) — 50M 行 benchmark
- [docs/architecture/AI_SAFETY_NET.md](AI_SAFETY_NET.md) — L1+L2+L3 AI typo 防御
- [docs/architecture/TEST_INFRASTRUCTURE.md](TEST_INFRASTRUCTURE.md) — pytest fixture + race flake 治本
- [docs/TECH-DEBT.md](../TECH-DEBT.md) — 技术债台账 (29 条已修)
- [scripts/etl/pipeline.py](../../scripts/etl/pipeline.py) — ETL 入口
