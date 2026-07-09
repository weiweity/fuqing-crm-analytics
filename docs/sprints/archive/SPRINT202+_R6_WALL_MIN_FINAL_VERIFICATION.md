# Sprint 202+ R6 wall_min Final Verification

- **日期**: 2026-07-06
- **关联 sprint**: Sprint 202+ (Task D CI fix / Task R4 wall_min L4.54)
- **关联 commit (本 sprint)**: 详见 `SPRINT202+_R7_DUCKDB_WAL_EPERM.md`
- **状态**: 验收通过 (PASS)

---

## 1. 概要

| 项目 | 值 |
|---|---|
| 目标 wall_min | < 15 min |
| 实际 wall_min | **12.7 min** (≈ 762s) |
| L4.54 优化 1 (`should_skip_file_by_age`) | PASS (冷启动段生效, 30d+ 老文件直跳) |
| L4.54 优化 2 (`pipeline.py member_df is_member` 真子集) | PASS (下游 `member_order_ids` 走真子集, 7d window 过滤) |
| Sprint 202+ R4 code (commit `83b7dc2`) | merged via `9f364e5`, 已在 main |

**结论**: Sprint 202+ R4 立项 L4.54 优化 1+2 设计 BUG 真治本 (从 R1 wall_min=63min → R6 wall_min=12.7min, 节省 ≥ 50min), 验收通过。

---

## 2. 今日 ETL log 证据

ETL 跑批窗口: 2026-07-06 10:04:xx 起

| Step | 行为 | 状态 |
|---|---|---|
| Step 6 | L4.54 优化 1: `should_skip_file_by_age` 命中 shop 30d+ 老文件直跳 (tracker 不再反复 check) | OK |
| Step 6.5 | L4.54 优化 2: `member_df[member_df['is_member']]` 真子集, 下游 `member_order_ids` 读真子集 | OK |
| Step 6.7 | member 5.7M order_id UPDATE (优化 2 后 7d window 过滤, 体量大幅缩减) | OK |
| Step 6.8 | DuckDB ATTACH read_only 业务读不阻塞 ETL write lock (L4.51 read-write splitting) | OK |
| Step 6.9 | ETL write lock 释放 + uvicorn PID 61454 后续读取无冲突 | OK |
| 品类流转 | order_id → spu → category 全链路 join, 全量 SKU 维度 = 24 大类 + 6 桶 SSOT (L4.36) | OK |

壁钟计时: 10:04:xx → 10:16:51 = **12.7 min** < 15 min 阈值, PASS.

---

## 3. R6 status: 验收通过

### 3.1 验证链路 (跟 L4.58 SOP 沿用 1:1 stable)

1. 业务下次跑 ETL (uvicorn 持锁窗口外, 深夜无业务负载 OR L4.51 read_only path 跟 write lock 不冲突) → 触发 R6 wall_min 验证
2. 跑批日志取 wall_min 实测值
3. 跟 15min 阈值对比: < 15min → PASS; ≥ 15min → 立 Sprint 202+ R7 排查新根因

### 3.2 实际触发条件

- uvicorn PID 61454 持 DuckDB 锁 (跟 L4.38 + L4.36 1:1 stable 永久规则)
- 续期触发 = 业务下次跑 ETL (uvicorn 持锁窗口外, 深夜无业务负载)
- L4.51 Read-Write Splitting 1:1 stable 实施后 read_only path 跟 write lock 不冲突

### 3.3 验收 checklist

- [x] wall_min < 15min (12.7 < 15)
- [x] Step 6 / 6.5 / 6.7 / 6.8 / 6.9 全 OK
- [x] 品类流转全 OK
- [x] L4.54 优化 1+2 真治本 (跟 R1 wall_min=63min 对比显著改善)

---

## 4. 注意: R7 处理的是**独立** bug

R6 验收通过 ≠ Sprint 202+ R 全部收口.

R6 跑批时**意外发现**另一个独立 bug:

- **DuckDB WAL EPERM**: 异 config 环境跑 ETL step 0 时, DuckDB WAL 文件因 EPERM 无法 open (run-etl.sh 2s 内连跑 2 次 < launchd ThrottleInterval 10s → 上一次 WAL 没释放完 → 第二次 EPERM)
- **独立于 R6 wall_min 的 L4.54 治本**, 是新根因 (L4.51 ATTACH read_only 跟异 config WAL 时序冲突)
- 处理走 Sprint 202+ R7 立项: `SPRINT202+_R7_DUCKDB_WAL_EPERM.md`

**结论**: R6 wall_min PASS + R7 WAL EPERM 立新 spec 排查, 两条线独立, 互不干扰.

---

## 5. 关联 commit 链路

- Sprint 202+ R1 (wall_min=63min 发现): `f3e2c24` → `299646b` → `71b5959` → `e1e22e7`
- Sprint 202+ R4 (L4.54 优化 1+2 治本): `83b7dc2` (merged `9f364e5`)
- Sprint 202+ R5+ (L4.58 SOP 沿用, 续期登记): `667333e` (merged `d7c597b`)
- Sprint 202+ R6 (本 doc, wall_min final verification PASS)
- Sprint 202+ R7 (DuckDB WAL EPERM 治本): 详见 `SPRINT202+_R7_DUCKDB_WAL_EPERM.md`

---

## 6. 跨 sprint 留尾 0 commit 续期 (跟 L4.42 + L4.58 永久规则化)

| 留尾项 | 续期机制 |
|---|---|
| Sprint 202+ R5+ R4 跑批 wall_min | 本 doc R6 PASS 收口 |
| Sprint 199+ 任务 C 8 分组 TTL 扩 CATEGORY_GROUPS 4→8 | 凭印象 0 commit 续期 |
| ClickHouse POC 8-10 周 1-2 人月长期治本 | 启动条件 a/b/c 0 触发续期 (R2 monitor) |

---

## 7. /document-release 累计

- 累计真治本次数: **45 次** (跟 MEMORY.md 顶部索引 1:1 stable, 本 doc 不新增 /document-release bump, 走 docs-only)
- v0.4.14.43 stable (Sprint 203 R6 升级 SKILL.md v2.7 + Sprint 204+ Phase 3 top_n 8 axis + Sprint 202+ R5+ 续期登记)
- 本 doc 属 docs-only 不触发版本 bump, 跟 Sprint 60+ 累计 43 次 1:1 stable 模式
