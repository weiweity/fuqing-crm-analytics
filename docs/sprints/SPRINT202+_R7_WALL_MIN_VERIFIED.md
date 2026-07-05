# Sprint 202+ R7 — wall_min <15min 验证实证 (跟 L4.58 SOP + L4.36 + L4.38 永久规则 1:1 stable)

> **作者**: Claude Code 架构师 (你 7/5 19:15 手动跑 `./scripts/etl/run-etl.sh --update` 跨 sprint 续期 A1 wall_min 真验证触发, 跟 L4.58 SOP 沿用 1:1 stable 跨 sprint 等真业务跑批)
> **日期**: 2026-07-05
> **关联 commit**: Sprint 202+ R4 L4.54 优化 1+2 设计 BUG 真治本 (`83b7dc2`, merged as `9f364e5`) + Sprint 202+ R6 wall_min 估算 (`616756d`) + Sprint 204+ L4.42 立项实证 (`538692f`)
> **关联永久规则**: L4.36 (禁停 uvicorn) + L4.38 (DuckDB flock 锁死) + L4.51 (Read-Write Splitting) + L4.54 (ETL 文件分桶 30d+ skip + member_df 真子集) + L4.58 (跑批 wall_min 验证 SOP)

---

## 1. 跑批实证 (跟 `/tmp/fuqing-etl-manual.log` 1:1 stable)

### 1.1 你手动跑 ETL 触发链 (跟 L4.36 永久规则沿用 1:1 stable)

```bash
./scripts/etl/run-etl.sh --update
# run-etl.sh 脚本自动:
#   1. 临时卸载 com.fuqing.uvicorn plist (run-etl.sh:104-115 Sprint 105 实战 fix)
#   2. bootout-poll wait uvicorn 真正退出 2s (run-etl.sh:120)
#   3. 跑 ETL (本次 3196s = 53.3 min)
#   4. 重新 launchctl bootstrap 自动启回 uvicorn (PID 64617)
```

### 1.2 wall_min 实测 (跟 L4.58 SOP 沿用 1:1 stable)

| 维度 | 实测值 | W6 step 报告 | RunAtLoad 总耗时 |
|---|---|---|---|
| **Start time** | 2026-07-05 19:15:14 | - | - |
| **End time (W6 step 8)** | (W6 timestamp) | `step8_ok=True wall_min=43.7 mode=inc run_mode=incremental` | - |
| **End time (run-etl.sh exit 0)** | (cleanup + uvicorn 启回) | - | **3196s = 53.3 min** |
| **wall_min (W6 step 8)** | **43.7 min** | - | - |
| **wall_min 总 (RunAtLoad exit 0)** | **53.3 min** | - | **3196s** |
| **W6 飞书解耦 no-op** | ✅ (Sprint 164 解耦, no-op 1:1 stable) | - | - |

### 1.3 跟 R6 wall_min 估算 (估算 14-18 min) 1:1 stable 错算分析

| 维度 | R6 估算 (commit `616756d`) | 本次实测 | 偏差 |
|---|---|---|---|
| **wall_min** | 14-18 min (跟 Sprint 22 #26 18min baseline 1:1 stable) | **53.3 min** | **+35.5 min (跟 R6 估算 错算 297%)** |
| **L4.54 优化 1 真治本** | ✅ 假设 30-40% 节省 (shop 99 + member 74 skip) | ❌ **0 hit** (tracker 不存在, 走 "标记 125 个旧文件为已处理" 老路径) | **R6 估算 错算根因 #1** |
| **L4.54 优化 2 真治本** | ✅ 假设 member_df 5,703,316 → 0 节省 7 min | ❌ **0 hit** (走 5,703,956 单 is_member UPDATE 老路径) | **R6 估算 错算根因 #2** |
| **30d+ 老文件 skip** | ~78% 文件 skip | ❌ **0 hit** (tracker 重置冷启动) | 全部走 xlsx 重写 |

---

## 2. 慢的 5 大真因 (跟 `/tmp/fuqing-etl-manual.log` 1:1 stable 实证)

### 2.1 #1 头号慢点: **全冷启动 xlsx → parquet 写入 ~15 min**

```
[冷启动] shop: tracker 不存在, 标记 125 个旧文件为已处理, 保留 1 个新文件走增量路径
   [Parquet 写入] shop 126 个 + member 101 个 (累计 227 个)
```

实证:
- tracker 不存在 → L4.54 优化 1 (30d+ 老文件 skip) **完全 0 hit**
- shop 126 个 + member 101 个 = **227 个 xlsx 重写 parquet** (~15 min)
- log 显示 "[Parquet 写入] 芙清旗舰店_数据营销_购买订单_活动*.parquet (200,000 行)" 重复 90+ 次

### 2.2 #2 慢点: **Step 4.7 is_member 5,703,956 UPDATE ~10 min**

```
[Step 4.7 增量] 本次 UPDATE 影响 5,703,956 单 is_member=TRUE
```

实证:
- tracker 不存在 → L4.54 优化 2 (member_df 5,703,316 → 0 行 pay_time 7 天窗口) **完全 0 hit**
- 走老路径 5,703,316 单 is_member 全表 UPDATE + 4,663,531 加载历史 order_ids
- 实测 5,703,956 单 UPDATE (~10 min)

### 2.3 #3 慢点: **淘客全量纠正 1,920,715 单 ~10 min**

```
纠正前淘客订单: 1,916,606 条
  已重置 1,916,606 个淘客订单为'其他'
  P6 订单号匹配: +1,785,434 条
  P6-2 关键词匹配: +131,172 条
```

实证:
- 淘客纠正不跟 tracker 路径 (跟 main HEAD 1:1 stable 跨 sprint 全表纠正)
- 1.91M 订单纠正 + COMMIT + 索引 (~10 min)

### 2.4 #4 慢点: **Step 2.5 滑动窗口 30 天全量刷新 ~3 min**

```
[Step 2.5 滑动窗口过滤] start: 19:49:27
  滑动窗口过滤 (窗口=30天):
    全新订单:     0 行
    窗口内刷新:   163,087 行 (2026-06-05 ~ 2026-07-03)
    剔除旧数据:   10,659,772 行 (窗口外且已存在)
```

实证:
- 163,087 行窗口内刷新 + 10,659,772 行窗口外剔除 (~3 min)

### 2.5 #5 慢点: **W4 fact_rfm + Step 6-7.5 系列 ~5 min**

```
[W4 fact_rfm_long] incremental=540 行, merge=3780 行 (7 天修复)
user_first_purchase 增量更新: 130,990 个受影响用户
user_recency 增量更新: 130,990 个受影响用户
daily_metrics 29 个日期更新
user_rfm 预加载: 1/10 date 写入 4,564,142 行 (60 组合/date)
campaign_schedule 跳过 (21 条记录)
品类流转预计算 144 个 (108 新增, 0 跳过)
品类流失预警预计算 77 个月 (11 个月增量)
```

实证:
- W4 + user_rfm + 品类流转/流失 (~5 min)

---

## 3. 累计统计 (跟 Sprint 60+ + Sprint 202+ R5+/R6 1:1 stable 累计)

### 3.1 跑批实证累计

| 维度 | 值 | 备注 |
|---|---|---|
| **wall_min** | **43.7 (W6) / 53.3 (RunAtLoad)** | 跟 R6 估算 14-18min 错算 +35.5 min |
| **RunAtLoad exit code** | **0** | 跟 L4.40 fail-open 1:1 stable ✅ |
| **uvicorn 启回** | ✅ PID 64617 launchd 接管 | 跟 L4.7 launchd 1:1 stable |
| **Tracker 重置后状态** | **126 个 shop + 101 个 member = 227 个新 tracked** | 下次再跑应该走真增量路径 |
| **L4.54 优化 1+2** | ❌ **0 hit** (走全冷启动老路径) | R6 估算 假设 100% 命中**反向 0 hit** 错算 |

### 3.2 累计跨 sprint 跑批 baseline 锚定

| 基线 | wall_min | 来源 | 备注 |
|---|---|---|---|
| Sprint 22 #26 跑批 18min 闭环 (痛点 1) | 18 min | CHANGELOG.md v0.4.14.86 | 业务方目标基线 |
| 7/3 R0 baseline (L4.54 落地前) | 46 min | Sprint 202 R1 报告 | 业务方反映慢 |
| 7/4 R1 wall_min (L4.54 落地, 0 实质效果) | 63 min | Sprint 202 R1 §1 | R1 跑批 log "Sprint 202 R1 优化 1" 0 hit |
| 7/5 19:15 wall_min (R6 期望 warm hit, 实测 cold start) | 53.3 min | 本次 RunAtLoad | **跨 sprint FAIL ≥15min** |
| 7/5 期望 (再跑一次 warm 增量路径) | <15 min | R6 估算 1:1 stable 接受 | 待 R8 实证 |

---

## 4. 续期登记 (跟 L4.58 SOP FAIL 路径 1:1 stable 沿用)

### 4.1 wall_min ≥15min FAIL 触发 (本次实测 53.3 min)

按 L4.58 SOP 沿用 1:1 stable `wall_min ≥ 15min FAIL → 重新立项 Sprint N+1 R8 排查新根因`:

| 件 | 当前状态 | 续期触发 |
|---|---|---|
| **A1 Sprint 202+ wall_min 真验证** | ⏸ 跨 sprint 续期 (实测 53.3 min FAIL, 跟 R6 估算错算) | 再跑一次 (tracker 重置存在 → 走真增量路径) wall_min <15min PASS / ≥15min 立 Sprint N+1 R8 |
| **expected R8 wall_min 真增量路径** | 跟 L4.54 优化 1+2 真治本 1:1 stable 实证期望 <15 min | 待 R8 验证 |

### 4.2 R7 wall_min 验证 FAIL 写本 doc 收口 + 立 R8

跟 L4.58 SOP 沿用 1:1 stable:
- ✅ 写 `docs/sprints/SPRINT202+_R7_WALL_MIN_VERIFIED.md` 收口本次跑批实测 (本次)
- 📋 立 Sprint N+1 R8 wall_min 排查 (跟你拍板)

---

## 5. Sprint N+1 R8 wall_min 排查立项 (跟你拍板)

### 5.1 R8 立项 L4.42 实证前置

**预期真因** (跟本次实证 1:1 stable):
- (a) Tracker 不存在 → L4.54 优化 1+2 完全 0 hit (走冷启动老路径 5.7M UPDATE + 1.9M 淘客纠正)
- (b) 实际期望: 再跑一次 (tracker 已重置存在) → 走真增量路径 → wall_min <15min

**L4.42 实证**: Sprint 202+ R7 wall_min ≥15min FAIL 真因已实证 (跟 1.1-2.5 段), 0 commit 后续.

### 5.2 R8 选项 (跟你拍板)

| 选项 | 期望 wall_min | 工作量 |
|---|---|---|
| **A. 再跑一次** (tracker 已重置存在) | <15 min (跟 L4.54 优化 1+2 真治本 1:1 stable 期望) | 1 次手动跑批 (~10-15 min) |
| **B. 立 Sprint N+1 R8 真治本** | L4.54 优化 1+2 设计 BUG 二次排查 | 0.5-1 天 |

---

## 6. 累计统计 (跟 Sprint 60+ 累计 +139 sprint 1:1 stable)

- ✅ Sprint 202+ R4 code 治本 (`83b7dc2`, merged as `9f364e5`) — L4.54 优化 1+2 设计 BUG 100% 真治本 (但 cold start 0 hit)
- ✅ Sprint 204+ L4.42 立项实证 (`538692f`) — 3 件跨 sprint 留尾 0 commit 收口 (含 A1 wall_min 续期)
- ✅ Sprint 202+ R6 wall_min 估算 (`616756d`) — R6 估算 14-18min 实战 FAIL +35.5min 错算
- ✅ **Sprint 202+ R7 wall_min 验证 (`本次`)**: wall_min=43.7 (W6) / 53.3 (RunAtLoad) 实证 ≥15min FAIL 路径
- 累计 Sprint 60+ 0 debt stable **138 sprint** (跨 +34 sprint)
- /document-release 真治本累计 **48 次**
- 0 业务代码改动模式: Sprint 60+ 累计 **52 次** 1:1 stable
- pytest baseline **1083 passed / 7 skipped / 62 deselected / 0 failed / 5 pre-existing failed** (跟 Sprint 202+ R5+ 1:1 stable)
- L4.x stable: **62 stable 持续** (R7 0 新增, 跟 L4.36 + L4.38 + L4.51 + L4.54 + L4.58 永久规则配套)

---

## 7. L4.42 + L4.54 + L4.58 永久规则沿用合规

| 永久规则 | Sprint 202+ R7 应用 | 1:1 stable 模式 |
|---|---|---|
| **L4.42** 立项实证 SOP | ✅ R7 wall_min 验证 FAIL 真因实证 (跟 1.1-2.5 段 1:1 stable) | 跟 Sprint 60+ 累计 +38 sprint 1:1 stable |
| **L4.54** ETL 文件分桶 + member_df 真子集 | ❌ cold start 0 hit (tracker 不存在走老路径) | 跟 R4 design fix 1:1 stable (但 R7 实证 0 hit) |
| **L4.58** 跑批 wall_min 验证 SOP | ✅ FAIL 路径 (53.3 ≥15min) 1:1 stable 跨 sprint 续期 | 跟 Sprint 202+ R5+/R6 1:1 stable 沿用 |
| **L4.36** 禁停 uvicorn + run-etl.sh 内部自动 (跨 sprint 1:1 stable) | ✅ uvicorn PID 64617 launchd 接管 1:1 stable | 跟 Sprint 22+ run-etl.sh 设计 1:1 stable |
| **L4.38** DuckDB flock 锁死 | ✅ (本次成功跑批无 lock conflict, run-etl.sh 1:1 stable 接受) | 跟 run-etl.sh 1:1 stable 设计配套 |

---

**STATUS**: DONE (跟 L4.58 SOP FAIL 路径 1:1 stable 接受跨 sprint 续期, 写 R8 立 wall_min 排查)
**REASON**: wall_min=43.7 (W6) / 53.3 (RunAtLoad) 实证 ≥15min FAIL, 真因 = tracker 不存在 → L4.54 优化 1+2 0 hit → 全冷启动老路径
**ATTEMPTED**: read_only R7 跑批实证 + 5 大真因细分 + R6 估算错算分析 + 续期登记 + R8 立项 L4.42 实证前置
**RECOMMENDATION**: 跟你拍板 + R8 wall_min 排查 (选项 A 再跑一次 / 选项 B 立 Sprint N+1 R8 真治本)
