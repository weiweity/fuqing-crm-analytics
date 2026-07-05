# Sprint 202+ R5+ — R4 跑批 wall_min < 15min 真验证续期 (L4.58 SOP 沿用 1:1 stable 永久规则化)

> **作者**: Claude Code 架构师 (你 7/5 拍板"继续拉 workflow, 跑完剩余 3 件, 包括 Sprint 202+ R4 ETL wall_min 修 L4.54 优化 1+2 设计 BUG")
> **日期**: 2026-07-05
> **关联 commit**: Sprint 202+ R4 L4.54 优化 1+2 设计 BUG 真治本 (`83b7dc2`, merged as `9f364e5`)
> **关联永久规则**: L4.36 (禁停 uvicorn) + L4.38 (DuckDB flock) + L4.54 (ETL 文件分桶) + L4.58 (跑批 wall_min 验证 SOP) + L4.51 (Read-Write Splitting)

---

## 1. Sprint 202+ R4 治本状态 (跨 sprint 续期, 等业务跑批验证)

### R4 code 治本 (已在 main, commit `83b7dc2`)

| 维度 | R1 落地状态 (commit `7201e84`) | R4 真治本状态 (commit `83b7dc2`) |
|---|---|---|
| **L4.54 优化 1 文件分桶** | ❌ BUG: 嵌套在 `pipeline.py:177` `if not processed_path.exists()` 块内, tracker 永远存在 → 0 hit | ✅ FIX: 撤回 `pipeline.py:177-178`, 移到 `scripts/etl/ingest.py:181` 增量模式 (跟 `_file_changed` 同级) |
| **L4.54 优化 2 member_df** | ❌ BUG: `pipeline.py:273` 走 `member_df['order_id']` (17K 全表) | ✅ FIX: 改 `member_order_ids = set(member_df[member_df['is_member']]['order_id'].dropna())` (老客 4.66M 真子集) |
| **R4 跑批初步实证** | n/a | L4.54 优化 1 真治本 (跑批 log "Sprint 202+ R4 L4.54 优化 1 真治本" 命中 shop 99 + member 74 = 173 个 30d+ 老文件 skip) |

### R4 跑批 wall_min 真验证 续期 (本次 sprint 留尾)

- R4 跑批 21s fail @DuckDB lock (跟 R4 报告 §3 1:1 stable):
  - uvicorn PID 61454 持 DuckDB 锁 (跟 L4.38 DuckDB flock 1:1 stable 永久规则)
  - L4.36 禁停 uvicorn 永久规则 (本地即生产, 不能 kill)
  - L4.51 Read-Write Splitting 1:1 stable 永久规则 (uvicorn 持写锁, read_only conn 不冲突, 但 ETL pipeline.py 走 write 模式, 跟 R1 跑批 1:1 stable)
- 续期触发: 业务下次跑 ETL (uvicorn 持锁窗口外, 深夜无业务负载) 自然验证 wall_min < 15min

## 2. 期望验证目标 (跟 L4.58 SOP 沿用 1:1 stable)

| 指标 | 7/3 baseline (L4.54 落地前) | 7/4 R1 (L4.54 落地, 0 实质效果) | R4 治本后期望 |
|---|---|---|---|
| **wall_min (W6 通知)** | 33.7 min | ❌ 63.0 min (R1 跑批实证 +87% 远未达) | **<15 min** (跟 R1 跑批 7/3 baseline + L4.54 优化 1+2 期望 1:1 stable) |
| **L4.54 优化 1 触发** | ❌ 0 hit | ❌ 0 hit | ✅ **shop 99 + member 74 = 173 个 30d+ 老文件 skip** (R4 真治本) |
| **L4.54 优化 2 member_df 走 is_member 过滤** | ❌ 5,703,316 单 is_member 仍标 (走全表) | ❌ 5,703,316 单 is_member 仍标 (走全表) | ✅ 走 is_member 过滤 (老客 4.66M 真子集, R1 R4 1:1 stable 期望) |
| **Step 4.7 is_member 标** | 5,702,274 单 | 5,703,316 单 | 5,703,316 单 (跟 R1 1:1 stable) |
| **shop 文件处理数** | 125 | 126 | 125+ (R4 修法 30d+ 老文件真 skip, 期望 -78%) |
| **member 文件处理数** | 100 | 101 | 100+ (跟 shop 1:1 stable) |

## 3. Sprint 202+ R4 跨 sprint 留尾 0 commit 续期 (跟 L4.42 立项实证 SOP 1:1 stable)

- ⏸ **Sprint 202+ R5+**: R4 跑批 wall_min < 15min 真验证 (等 uvicorn 不持锁窗口, 业务跑 ETL)
  - 续期触发: 业务下次跑 ETL (uvicorn 持锁窗口外, 深夜无业务负载) OR L4.51 实施后 read_only path 跟 uvicorn write lock 不冲突 (但 ETL 走 write 模式, 跟 R1 R4 跑批 1:1 stable)
  - P3 (跨 sprint 自然触发, 跟 L4.58 SOP 沿用 1:1 stable)

## 4. L4.58 SOP 续期触发条件 (跟 Sprint 60+ 1:1 stable 永久规则化)

**L4.58 跑批 wall_min 验证 SOP** 续期触发:
- 业务下次跑 ETL 自动验证 wall_min < 15min
- 验证 wall_min < 15min → 写 `docs/sprints/SPRINT202+_R6_WALL_MIN_FINAL_VERIFICATION.md` 收口
- 验证 wall_min ≥ 15min → 立 Sprint 202+ R7 排查新根因 (跟 L4.54 优化 1+2 设计 BUG 1:1 stable 排查模式)

## 5. 累计统计 (Sprint 202+ 4 维度 0 commit 收口 + R4 治本跨 sprint 续期)

- ✅ Sprint 202+ R4 code 治本: commit `83b7dc2` (merged as `9f364e5`)
- ✅ Sprint 202+ R5 /workflow hardening: commit `59d9331` (merged as `0fa380e`)
- ⏸ Sprint 202+ R5+ R4 跑批 wall_min 真验证: 跨 sprint 续期 (等业务跑批, 跟 L4.58 SOP 沿用 1:1 stable)
- 累计 Sprint 60+ 0 debt stable 138 sprint (跨 +34 sprint)
- /document-release 真治本累计 44 次 (跟 Sprint 203 R6 1:1 stable)
- 0 业务代码改动模式: Sprint 60+ 累计 42 次 0 业务代码改动 1:1 stable

## 6. 跨 sprint 留尾登记 (跟 L4.42 立项实证 SOP 1:1 stable)

- ⏸ **Sprint 202+ R6+**: R4 跑批 wall_min < 15min 真验证 (本 sprint 留尾, 续期触发跟 L4.58 SOP 沿用 1:1 stable 永久规则)
- ⏸ **Sprint 202+ 留尾 4 维度** (跟 Sprint 202+ R4 0 commit 收口 1:1 stable):
  - Sprint 202+ R4 跑批 wall_min 业务验证 (本续期)
  - Sprint 199+ 3 P0 业务补全 (任务 A 淘客按月 / B 单品按 spu_product_class / C 8 分组 TTL 扩 CATEGORY_GROUPS 4→8) - 任务 A/B Sprint 203 R5 已实施, 任务 C 0 commit 续期
  - pre-existing fail 监控 (跟 R6 monitor 1:1 stable)
  - ClickHouse POC 8-10 周 1-2 人月长期治本 (启动条件 a/b/c 0 触发续期)
- 跨 sprint 留尾 0 commit 续期 (跟 L4.57 跨 sprint 留尾 4 维度永久规则化 1:1 stable)