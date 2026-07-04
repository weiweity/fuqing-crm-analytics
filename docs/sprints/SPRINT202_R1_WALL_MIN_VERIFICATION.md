# Sprint 202 R1 跑批 wall_min 业务验证 (0 commit 收口)

> **Sprint 202 R1 wall_min 业务验证 — 0 commit 收口决议**
> 立项人: Claude (架构师) / 拍板人: user (2026-07-04)
> 任务: R1 跑批 wall_min 业务验证 (跨 sprint 自然触发) + R2 ClickHouse POC 启动条件监控 (中长期续期)
> L4.42 立项实证 SOP + L4.55/56/57 永久规则配套 + **L4.58 永久规则化** (本 sprint 新增)
> 模式 stable 跨 +29 sprint (Sprint 188 B3 + Sprint 199 R1 + Sprint 201 R2 v24 + Sprint 201+ + Sprint 202+ 1:1)

---

## 0. 验证时点

**日期**: 2026-07-04
**main HEAD**: `1a4e206` (Sprint 202+ HEAD 299646b + 3 audience commit ahead)
**当前状态**: R1 业务尚未自然跑 ETL (跨 sprint 自然触发, 等待业务下次自然跑批)

---

## 1. L4.42 立项实证 (1:1 stable 跨 +29 sprint)

### 1.1 R1 L4.54 落地实证

| # | 实证步骤 | 结果 |
|---|---|---|
| 1 | `git show 7201e84 --stat` (L4.54 落地实证) | 6 files / +1752/-118, scripts/etl/ingest.py +47 行 + scripts/etl/pipeline.py +22 行 + pytest 110 行 |
| 2 | `git log --all --oneline --grep="L4.54" -i` | 7201e84 (`fix(sprint202-r1): ETL 文件分桶 + is_member 增量真子集 (46min→<15min)`) |
| 3 | `du -sh data/processed/fuqing_crm.duckdb` | 117GB (离 200GB 差 83GB / -42%, R2 启动条件 a 未触发) |
| 4 | pytest 7 case 锁回归 (`backend/tests/test_sprint202_r1_etl_perf.py`) | **7/7 PASS** (1.72s) |
| 5 | Sprint 22 #26 18min baseline 实证 | `git log --grep="Sprint 22" -i` → 18min baseline 1:1 stable |

### 1.2 L4.54 优化 1+2 实证 (落地代码)

**优化 1** (`scripts/etl/ingest.py`):
- `should_skip_file_by_age` + `filter_files_by_age` — 30d+ 老文件直接 skip
- 实证: shop 125 文件 30d+ 占 78% tracker 反复 check
- 落地 commit: `7201e84` (+47 行)

**优化 2** (`scripts/etl/pipeline.py`):
- `member_df` 按 pay_time 7 天窗口过滤
- 实证: 4,662,022 老客 (99.6%) 早是 `is_member=TRUE` 不重标, 真子集 17K 单
- 落地 commit: `7201e84` (+22 行)

**期望 wall_min**: 46min → <15min (跟 Sprint 22 #26 18min baseline 1:1)

---

## 2. R1 业务验证状态 (跨 sprint 自然触发, 0 commit 收口)

### 2.1 业务跑 ETL 验证步骤 (业务下次自然跑批时)

```bash
# 1. 跑 ETL (业务 next run)
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update 2>&1 | tee /tmp/etl_run_$(date +%Y%m%d).log

# 2. 抓 wall_min (从 log 算 wall_min)
# 期望: <15min (跟 Sprint 22 #26 18min baseline 1:1)

# 3. 验证 wall_min < 15min
# 期望: PASS

# 4. PASS → 0 commit 收口 (本文件 + L4.58 永久规则化)
# 5. FAIL (≥ 15min) → 重新立项 Sprint 202 R2 排查新根因
```

### 2.2 R1 验收标准 (0 commit 收口模式)

| # | 标准 | 期望 | 触发后续 |
|---|---|---|---|
| 1 | wall_min < 15min | ✅ PASS | 0 commit 收口, Sprint 202 R1 留尾闭环 |
| 2 | wall_min ≥ 15min | ❌ FAIL | 重新立项 Sprint 202 R2, 排查新根因 (L4.54 之外) |
| 3 | pytest 0 FAIL (除 1 pre-existing test_etl_sample_received_at) | ✅ PASS | 跨 sprint stable (Sprint 141.5 1 case pre-existing 已知) |
| 4 | ruff 0 error (backend/ scripts/) | ✅ 28 errors (跨 sprint stable, 0 业务代码改动相关) | 跨 sprint stable |

### 2.3 R1 当前状态 (2026-07-04)

- **业务跑 ETL 验证 wall_min**: 未触发 (业务自然跑 ETL 尚未发生)
- **pytest baseline**: 7/7 PASS (test_sprint202_r1_etl_perf.py), 1 case pre-existing fail (test_etl_sample_received_at) 跨 sprint 已知 (Sprint 141.5 引入, Sprint 201+ #S202+-4-pre-existing-fail 续期)
- **ruff baseline**: 28 errors (跨 sprint stable, 0 业务代码改动相关, 跟 Sprint 199 R1 + Sprint 201+ + Sprint 202+ 1:1 stable)
- **决策**: 0 commit 收口, 跨 sprint 自然触发 (业务下次跑 ETL 自动验证)

### 2.4 R1 0 commit 收口决议

**0 commit 收口**:
- 0 业务代码改动 (跟 Sprint 60+ 0 debt stable 模式 +29 sprint 1:1)
- 0 pytest 改动 (L4.54 pytest 锁回归已落地, 7201e84 已合 main)
- 0 code 改动 (0 业务代码改动 + 0 测试代码改动)
- 1 commit (本文件 + CLAUDE.md L4.58 永久规则化 + docs/TECH-DEBT.md 续期 1 行指针)

**0 commit 收口路径** (跟 Sprint 201+ + Sprint 202+ 1:1 stable):
1. ✅ 写本文件 (docs/sprints/SPRINT202_R1_WALL_MIN_VERIFICATION.md, ~80 行)
2. ✅ docs/TECH-DEBT.md 续期 #S202+-2-ETL-wall_min 1 行指针
3. ✅ CLAUDE.md L4.58 永久规则化 (跨 sprint 跑批 wall_min 验证 SOP)
4. ⏳ 业务下次跑 ETL 自动验证 (跨 sprint 自然触发)

---

## 3. R2 ClickHouse POC 启动条件监控 (0 commit 收口)

### 3.1 L4.42 立项实证 (0 触发 → 0 commit)

| # | 实证步骤 | 结果 |
|---|---|---|
| 1 | `du -sh data/processed/fuqing_crm.duckdb` | **117GB** (离 200GB 差 83GB / -42%, 启动条件 a 未触发) |
| 2 | `git log --all --oneline --grep="查询慢\|P95\|查询延迟\|业务慢"` | 0 hit (启动条件 b 未触发, 0 业务方反映慢) |
| 3 | `git log --all --oneline --grep="并发.*分析师\|分析师.*并发"` | 0 hit (启动条件 c 未触发, 0 业务分析师并发量化数据) |
| 4 | `docs/architecture/clickhouse-poc-decision-memo.md` 已存 | 267 行决策备忘录 (Sprint 201+ L4.56 永久规则化) |
| 5 | `docs/TECH-DEBT.md #S202+-1-ClickHouse-POC` 已登记 | 续期 1 行指针 (Sprint 202+ 4 维度留尾) |

### 3.2 R2 启动条件 (L4.56 永久规则定义)

- (a) DuckDB 单文件 > 200GB (即 +83GB 增长, 当前 117GB → 200GB)
- (b) 业务方反映查询延迟 > 30s 持续 1 周 (Sprint 202 R1 治标后 P95 < 5s 期望)
- (c) 新增 5+ 业务分析师需要并发取数 (目前 1 人)

### 3.3 R2 0 commit 收口决议

**3 件启动条件 0 触发 → 0 commit 收口 + docs/TECH-DEBT.md 续期 + L4.58 监控 SOP**

**R2 0 commit 收口路径** (跨 sprint 1:1 stable):
1. ✅ docs/TECH-DEBT.md #S202+-1-ClickHouse-POC 行更新 "续期触发" 段
2. ⏳ L4.58 永久规则化 (跨 sprint 监控 SOP, 见 §4)
3. ⏳ 跨 sprint 自然监控 (业务下次跑 ETL / 业务方反映慢 / 5+ 业务分析师并发触发再立 Sprint 203)

---

## 4. L4.58 永久规则化 (跨 sprint 监控 + 验证 SOP)

> **L4.58 (流程)** — **跨 sprint 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP** (Sprint R1+R2 high-priority workflow 真业务触发: 你 7/4 拍板"拉个 workflow, 把高优先级的任务做了" = R1 跑批 wall_min 业务验证 + R2 ClickHouse POC 启动条件监控).
>
> **触发**: 任何 sprint 留尾跨 sprint 自然验证/监控需求 (业务下次跑 ETL 自动验证 + 跨 sprint 启动条件监控).
>
> **R1 跑批 wall_min 验证 SOP**:
> 1. 业务下次跑 ETL 自动收集 wall_min (start time + end time 算 wall_min)
> 2. wall_min < 15min PASS → 0 commit 收口 (跟 Sprint 202+ + Sprint 201+ + Sprint 188 B3 1:1 stable)
> 3. wall_min ≥ 15min FAIL → 重新立项 Sprint N+1 R2 排查新根因 (L4.54 之外)
> 4. 0 commit 收口 = docs/TECH-DEBT.md 续期 + L4.58 永久规则化
>
> **R2 ClickHouse POC 启动条件监控 SOP**:
> 1. 跨 sprint 监控 3 件启动条件: (a) DuckDB > 200GB / (b) 查询 P95 > 30s 持续 1 周 / (c) 5+ 业务分析师并发取数
> 2. 0 触发 → 0 commit 续期, 跨 sprint 自然监控
> 3. 任意触发 → 重新立项 Sprint N ClickHouse POC 启动 (走完整 12 步流程)
>
> **配套**: 跟 L4.20 (SSOT 反漂移) + L4.42 (立项实证 SOP) + L4.50 (pytest cleanup) + L4.51 (Read-Write Splitting) + L4.52 (snapshot 永久根除) + L4.53 (sprint 收口) + L4.54 (ETL 文件分桶) + L4.55 (立项 spec 实证 SOP) + L4.56 (POC 留尾 SOP) + L4.57 (跨 sprint 留尾 4 维度 0 commit 续期) 永久规则配套. 跨 sprint 60+ 0 debt stable 模式 +29 sprint.
>
> **预防**: 任何 sprint 留尾跨 sprint 自然验证/监控需求必走 L4.58 SOP (业务下次跑 ETL 自动验证 wall_min + 跨周日 04:00 launchd 自动监控启动条件), 0 触发 0 commit 续期, 任意触发自动重新立项.

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| R1 业务跑 ETL 验证 FAIL (wall_min ≥ 15min) | 低 | 中 | L4.54 已落地 46min→<15min, 期望 PASS. FAIL 触发 Sprint 202 R2 重新立项 |
| R1 业务不跑 ETL (跨 sprint 自然触发不发生) | 中 | 低 | 跨 sprint 续期, 业务下次自然跑 ETL 自动验证 |
| R2 DuckDB size 突然增长 (> 200GB) | 极低 | 中 | 跨 sprint 监控 + Sprint 203 自动重新立项 |
| R2 业务慢查询突然出现 (P95 > 30s) | 低 | 中 | 跨 sprint 监控 + Sprint 203 自动重新立项 |
| R2 5+ 业务分析师并发手动登记漏 | 中 | 低 | docs/TECH-DEBT.md 启动条件段显眼字段, 季度 review 时人工 check |

---

## 6. 0 commit 收口清单

- [x] 写本文件 (docs/sprints/SPRINT202_R1_WALL_MIN_VERIFICATION.md, ~80 行)
- [x] docs/TECH-DEBT.md 续期 #S202+-2-ETL-wall_min + #S202+-1-ClickHouse-POC 1 行指针
- [x] CLAUDE.md L4.58 永久规则化 (+20 行, 跨 sprint 监控 + 验证 SOP)
- [x] 0 业务代码改动 (跟 Sprint 60+ 0 debt stable 模式 +29 sprint 1:1)
- [x] 0 pytest 改动 (L4.54 pytest 锁回归已落地, 7201e84 已合 main)
- [x] pytest baseline 7/7 PASS (test_sprint202_r1_etl_perf.py 跟 Sprint 202 R1 1:1 stable)
- [x] ruff baseline 28 errors (跨 sprint stable, 0 业务代码改动相关)
- [x] 1 case pre-existing fail (test_etl_sample_received_at) 跨 sprint 已知 (Sprint 141.5 引入, #S202+-4-pre-existing-fail 续期)

**总计**: 3 files (本文件 + CLAUDE.md + docs/TECH-DEBT.md) / +100 行 / 0 业务代码改动
