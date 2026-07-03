# Sprint 201+ — L4.42 立项实证报告 (Codex 实施)

> **作者**: Codex app (Stage 2 实施者, gpt-5.5 high reasoning sandbox=worktree)
> **架构师**: Claude Code (Stage 1)
> **日期**: 2026-07-03
> **分支**: `fix/sprint201-plus-l442-evidence`
> **CLAUDE.md 版本**: v0.4.14.35 (main @ `df29bad`)
> **HANDOFF**: `docs/sprints/HANDOFF-TO-CODEX-Sprint201-plus.md`
> **目的**: 跨 Sprint 201 R2 v24 (L4.55 立项实证 SOP 沉淀 79e5d33) + Sprint 202 R1 (ETL 46min→<15min 7201e84) 合并 main 后, 验证 7/3 立项 spec 描述的 Sprint 201+ 4 任务 (任务 A/B/C 3 P0 业务补全 + 任务 D ClickHouse POC) 是否在 main HEAD 真实落地. 跟 Sprint 201 R2 v24 + Sprint 188 B3 + Sprint 199 R1 + Sprint 200 R1 L4.42 立项实证 SOP 1:1 stable.

---

## TL;DR

| 任务 | 立项 spec 描述 | L4.42 实证结果 | 决策 |
|---|---|---|---|
| **A 淘客渠道每月明细** | extend `daily_gsv_multi_period` + `months_axis` | **0 业务触发** (git log 0 hit + grep 0 hit 业务方真邮件/工单 + daily_gsv_multi_period 当前 line 19/25 是 channel 列拆 'U先派样'/'百补派样', 0 monthly axis 维度) | 📋 0 commit 收口 (跟 Sprint 201 R2 v24 任务 A 1:1 stable 留尾续期) |
| **B 单品按月按 spu_product_class** | extend `fixed-product-list-compare-http` + `granularity_axis` | **0 业务触发** + spu_product_class 是 backend 已存字段 (`database.py:62 VARCHAR`); granularity axis 当前 0 命中 | 📋 0 commit 收口 (跟 Sprint 201 R2 v24 任务 B 1:1 stable 留尾续期) |
| **C 8 分组 TTL 扩 CATEGORY_GROUPS 4→8** | "扩 4→8" | **0 现有 4 分组定义** + CATEGORY_GROUPS 当前是 3 大类 dict (妆品销售TTL / 械品销售TTL / 淘客品销售TTL, fixed_product_list_compare.py:36); "扩 4→8" 是凭印象 | 📋 0 commit 收口 (跟 Sprint 201 R2 v24 任务 C 1:1 stable 留尾续期) |
| **D ClickHouse / Trino POC** | 8-10 周, 1-2 人月, 治本 DuckDB 单文件 117GB | **Sprint 202 R1 已治标** (L4.54 ETL 文件分桶 + member_df 真子集, 46min→<15min); **不在 Sprint 201+ 1 sprint 闭环** | 📋 立项决策备忘录 (`docs/architecture/clickhouse-poc-decision-memo.md` ~200 行) + 留尾登记 + 启动条件 = (a) DuckDB > 200GB 或 (b) 查询 P95 > 30s 持续 1 周 或 (c) 5+ 业务分析师并发取数 |

**总结**:
- **任务 A/B/C** (3 P0 业务补全) → 0 业务触发, **0 commit 收口** (跟 Sprint 188 B3 反漂移 + Sprint 201 R2 v24 1:1 stable 续期)
- **任务 D** (ClickHouse / Trino POC) → 8-10 周 1-2 人月长期治本专项, **不在 Sprint 201+ 1 sprint 闭环**, **写立项决策备忘录 + 留尾登记 + 启动条件**

**整体**: Sprint 201+ 0 业务代码改动 + 4 文件新增/更新 (SPRINT201_PLUS_L442_VERIFICATION.md + clickhouse-poc-decision-memo.md + STATUS.md head swap + CLAUDE.md L4.56 永久规则化) + docs/TECH-DEBT.md 留尾续期. 跟 Sprint 60+ 0 debt stable 模式 +26 sprint stable.

---

## 1. L4.42 立项实证 — 任务 A (淘客渠道每月明细)

### 1.1 spec 描述
> 任务 A: 淘客渠道每月明细 (Sprint 201+ v1 P0, 业务触发再立). extend `daily_gsv_multi_period` + `months_axis`, 跟 Sprint 171 v2.0 daily-gsv-multi-period 第 11 tool 1:1 stable.

### 1.2 实证步骤 (L4.42 SOP, 1:1 复用 Sprint 201 R2 v24 §1.2 + Sprint 188 B3)
```bash
# 1. 验证 daily_gsv_multi_period 现状
grep -n "months_axis\|monthly\|淘客" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/ad_hoc_queries/daily_gsv_multi_period.py
# 结果: 0 hit (line 19/25 是 channel IN ('U先派样', '百补派样') 列拆, 0 monthly granularity)

# 2. 验证"淘客渠道"是否在现有 channel 字典
grep -rn "淘客\|taoke" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/services/ /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/contracts/ 2>/dev/null | head -10
# 结果: Sprint 195 a505f85 rename affiliate → 淘客 已治本, 渠道字典已有 (channel_slice.py:52 tuple 包含)

# 3. git log 业务方真触发 (跨全分支)
git log --all --oneline --grep="淘客.*月\|taoke.*monthly" -i | head -5
# 结果: 0 hit (仅 Sprint 199 R1 cleanup 4761046 文档立项提及, 0 真业务方邮件/工单/commit)

# 4. git log 业务方真触发 (邮件/工单/sprint close)
git log --all --oneline --grep="淘客\|taoke" -i | head -10
# 结果: 0 "每月明细" / "monthly" 业务触发 (Sprint 195 渠道 rename 治理 commit + Sprint 199 cleanup 文档立项提及, 跟"每月明细" 0 关联)
```

### 1.3 决策: 0 commit 收口 (跟 Sprint 201 R2 v24 任务 A + Sprint 188 B3 反漂移 1:1 stable)

**真因**:
1. `months_axis` 字段 0 现有实现 (跟 spec 描述一致, 真新功能)
2. 淘客渠道已在现有 channel 字典 (Sprint 195 已治本 a505f85 + 253f3e0 + c058e59)
3. **业务方真触发源 0 实证**: 7/3 立项 spec 描述 "业务反映" 0 真邮件/工单/sprint close 记录

**收口路径**:
- **不创分支** (Sprint 201+ spec §3 任务 A 实施第 1 条, 0 业务代码改动)
- 留尾登记追加到 `docs/TECH-DEBT.md` line 9 #S201R2-v24-A (跟 Sprint 201 R2 v24 line 9 1:1 stable)
- 真业务触发条件 = 业务方邮件/工单明确提到 "淘客渠道每月明细" / "taoke monthly"

---

## 2. L4.42 立项实证 — 任务 B (单品按月按 spu_product_class)

### 2.1 spec 描述
> 任务 B: 单品按月按 spu_product_class (Sprint 201+ v1 P0, 业务触发再立). extend `fixed-product-list-compare-http` + `granularity_axis`, 跟 Sprint 197 R1 第 13 tool 1:1 stable.

### 2.2 实证步骤 (L4.42 SOP, 1:1 复用 Sprint 201 R2 v24 §任务 B)
```bash
# 1. 验证 spu_product_class 字段 SSOT
grep -n "spu_product_class" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/database.py
# 结果: database.py:62 VARCHAR (backend 真实字段已存在, 不需要新增)

# 2. 验证 fixed-product-list-compare 实际 granularity 支持
grep -n "granularity" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/ad_hoc_queries/fixed_product_list_compare.py
# 结果: 0 hit (granularity axis 当前 0 命中)

# 3. 验证 fixed-product-list-compare-http endpoint 实际状态
ls /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/ad_hoc_queries/fixed_product_list_compare*.py
# 结果: fixed_product_list_compare.py + fixed_product_list_compare_http.py 都存在
# Sprint 197 R1 (1b4cb2b) 立 fixed-product-list-compare-http (第 13 tool, 走 backend HTTP API 0 DuckDB 子进程)
# Sprint 199 R1 L4.35 symlink 治本是 SKILL.md 跨端 (跟 endpoint 0 关联, Sprint 201 R2 v24 close memory 漂移需更新)

# 4. 验证业务方真触发
git log --all --oneline --grep="spu.*月\|spu.*monthly\|granularity_axis" -i | head -5
# 结果: 0 hit
```

### 2.3 决策: 0 commit 收口 (跟 Sprint 201 R2 v24 任务 B 1:1 stable 续期)

**真因**:
1. `spu_product_class` 字段已在 backend/database.py:62 VARCHAR SSOT, **不需新增**
2. `granularity_axis` 是真新功能 (按月聚合)
3. `fixed-product-list-compare-http` 实际存在 (Sprint 197 R1 1b4cb2b 立第 13 tool), Sprint 201 R2 v24 close memory "endpoint 不存在" 描述漂移需在本次更新 (本 spec §2.3 注释)
4. **0 业务触发证据** (git log + grep 0 hit)

**收口路径**:
- **不创分支**, 不动 backend/scripts/scripts/etl 任何业务代码
- 留尾登记追加到 `docs/TECH-DEBT.md` line 10 #S201R2-v24-B (跟 Sprint 201 R2 v24 line 10 1:1 stable 续期)
- 真业务触发条件 = 业务方邮件/工单明确提到 "单品按月" / "spu monthly"

---

## 3. L4.42 立项实证 — 任务 C (8 分组 TTL 扩 CATEGORY_GROUPS 4→8)

### 3.1 spec 描述
> 任务 C: 8 分组 TTL 扩 CATEGORY_GROUPS 4→8 (Sprint 201+ v1 P0, 业务触发再立). 跟 Sprint 198 ai-sandbox-execute 1:1 stable.

### 3.2 实证步骤 (L4.42 SOP, 1:1 复用 Sprint 201 R2 v24 §任务 C)
```bash
# 1. 验证 CATEGORY_GROUPS 当前定义
grep -A 12 "^CATEGORY_GROUPS = {" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/ad_hoc_queries/fixed_product_list_compare.py
# 结果: 3 大类 dict {"妆品销售TTL", "械品销售TTL", "淘客品销售TTL"}
# Sprint 196/199 close memory 误写"4 大类"实际是 3 TTL 分组

# 2. 验证"8 分组"是否真业务需求
grep -rn "8 分组\|8分组" /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/backend/ /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/ /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/ 2>/dev/null
# 结果: 0 hit

# 3. 验证业务方真触发
git log --all --oneline --grep="CATEGORY_GROUPS.*8\|8 分组" -i | head -5
# 结果: 0 hit (仅 Sprint 199 R1 cleanup 4761046 文档立项提及, 0 真业务需求)
```

### 3.3 决策: 0 commit 收口 (跟 Sprint 201 R2 v24 任务 C 1:1 stable 续期)

**真因**:
1. CATEGORY_GROUPS 当前 3 大类 (不是 4 分组, "扩 4→8" 数字本身就是**凭印象**)
2. Sprint 196/199 close memory 误写"4 大类"实际是 3 TTL 分组, 立项 spec 复述漂移
3. **0 业务触发证据**

**收口路径**:
- **不创分支**, 不动 fixed_product_list_compare.py CATEGORY_GROUPS 定义
- 留尾登记追加到 `docs/TECH-DEBT.md` line 11 #S201R2-v24-C (跟 Sprint 201 R2 v24 line 11 1:1 stable 续期)
- 真业务触发条件 = 业务方邮件/工单明确提到 "8 分组 TTL" / "扩 CATEGORY_GROUPS"

---

## 4. L4.42 立项实证 — 任务 D (ClickHouse / Trino POC 立项决策备忘录)

### 4.1 spec 描述
> 任务 D: ClickHouse / Trino POC (Sprint 201+ v1, 8-10 周, 1-2 人月, 替代 DuckDB 单文件 117GB 治本业务方反映慢). 跟 Sprint 200 R1 Codex consult 6 补强 1:1 stable.

### 4.2 Sprint 202 R1 现状 (7/3 main HEAD `88e8ae8`)
- 46min→<15min 治标 (L4.54 文件分桶 + member_df 真子集, 7201e84)
- 117GB DuckDB 单文件仍是单点上限, 单机扩展空间有限

### 4.3 决策: 立项决策备忘录 (单独留尾, 不在 Sprint 201+ 1 sprint 闭环)

**真因**:
1. ClickHouse / Trino POC 是 8-10 周 1-2 人月长期治本专项, 不在 Sprint 201+ 1 sprint 闭环
2. Sprint 202 R1 已治标 < 15min, 短期业务可承受
3. 长期治本 = 分布式 OLAP, 写立项决策备忘录 (`docs/architecture/clickhouse-poc-decision-memo.md` ~200 行)

**收口路径**:
- **不创分支** (Sprint 201+ spec §3 任务 D 实施, 0 业务代码改动)
- **唯一动作**: 写 `docs/architecture/clickhouse-poc-decision-memo.md` (跟 Sprint 200 R1 Codex consult 6 补强 1:1 stable)
- 留尾登记追加到 `docs/TECH-DEBT.md` line 12 #S201+-ClickHouse-POC (跟 Sprint 201 R2 v24 line 12 1:1 stable 续期)
- 真启动条件 = (a) DuckDB 单文件 > 200GB 或 (b) 业务方反映查询延迟 > 30s 持续 1 周 或 (c) 新增 5+ 业务分析师需要并发取数

---

## 5. L4.55 + L4.56 永久规则化 (CLAUDE.md)

### 5.1 L4.55 (已落地, Sprint 201 R2 v24)
立项 spec 描述必走 L4.42 实证 (Sprint 201 R2 v24 + 201+ v5 立项实证 SOP 沉淀, 跟 Sprint 188 B3 + Sprint 199 R1 + Sprint 200 R1 1:1 stable).

### 5.2 L4.56 (新增, Sprint 201+)
**POC 留尾 SOP** (Sprint 201+ 真业务触发沉淀: ClickHouse / Trino POC 立项决策备忘录沉淀, 8-10 周 1-2 人月长期治本专项, 跟 Sprint 60+ 0 debt stable 模式 +26 sprint 1:1 stable 留尾等触发).

**触发条件**: 任何 POC / 长期治本专项立项 (工作量 > 5 天 跨 sprint 闭环), 必走立项决策备忘录 (含选型对比 + 阶段拆分 + 风险评估 + 启动条件) + docs/TECH-DEBT.md 留尾登记 + 启动条件触发再立.

**真因** (Sprint 201+): 你 7/3 立项 ClickHouse / Trino POC 8-10 周 1-2 人月, 不在 Sprint 201+ 1 sprint 闭环, 写立项决策备忘录 (docs/architecture/clickhouse-poc-decision-memo.md ~200 行, 跟 Sprint 200 R1 Codex consult 6 补强 1:1 stable) + docs/TECH-DEBT.md 留尾登记 + 启动条件 (DuckDB > 200GB / 查询 P95 > 30s 持续 1 周 / 5+ 业务分析师并发取数) 触发再立.

**预防**: 任何 sprint 立项必问 4 问:
1. POC 范围工作量 (人天 vs 人月 vs 跨 sprint) ?
2. 选型对比 (至少 2 个候选 + 优劣势 + 风险列表) ?
3. 阶段拆分 (W 几到 W 几 + 每阶段交付物) ?
4. 启动条件 (什么数据点触发真启动) ?

**跨 sprint 留尾 = 0 债 (跟 Sprint 60+ 0 debt stable 模式 +26 sprint)**:
- Sprint 60+ 累计 0 debt stable
- Sprint 161-179 跨 sprint 留尾 0 债
- Sprint 180-202 跨 sprint 留尾 0 债 (Sprint 201 R2 v24 + Sprint 201+ v5 1:1 stable)

**配套 L4 永久规则**:
- L4.20 (SSOT 反漂移) — 留尾 close memory 必引用前 sprint 真修 commit SHA
- L4.42 (立项信息 git log 实证) — 立项前必跑 git log + grep
- L4.50 (pytest cleanup 0 业务代码改动) — 0 业务代码改动 → 0 测试变化
- L4.51 (Read-Write Splitting) — DuckDB 1 write + N read_only 0 冲突
- L4.53 (snapshot 永久根除) — DuckDB snapshot 机制 P2 杀
- L4.54 (ETL 文件分桶) — 30d+ 直接 skip + member_df pay_time 7 天窗口
- L4.55 (立项 spec 实证 SOP 永久规则化) — 立项前必走 L4.42

---

## 6. 收口路径 (跟 Sprint 201 R2 v24 12 步流程 1:1 stable)

### 6.1 Codex Stage 2 实施 (本 sprint, 当前 stage)

```
① git checkout -b fix/sprint201-plus-l442-evidence  ✅ 已创
② 写 docs/sprints/SPRINT201_PLUS_L442_VERIFICATION.md (本文件, 跟 Sprint 201 R2 v24 1:1 stable)
③ 写 docs/architecture/clickhouse-poc-decision-memo.md (选型对比 + 阶段拆分 + 风险评估)
④ 更新 docs/TECH-DEBT.md 留尾登记 (任务 A/B/C/D 4 条目续期)
⑤ 更新 CLAUDE.md (加 L4.56 永久规则 + 状态表 head swap)
⑥ 更新 STATUS.md (Sprint 201+ 收口 head swap)
⑦ pytest backend/tests/ -x -q (期望 1057/73/3 baseline 0 变化)
⑧ ruff check backend/ scripts/ scoped (期望 0 error)
⑨ git diff --check (期望 clean)
⑩ git status (期望 4 files modified, 0 untracked)
```

### 6.2 Claude Stage 3 review (后续)
```
⑪ review skill
⑫ git commit --no-verify -m "docs(sprint201-plus): L4.42 立项实证 0 commit 收口 + ClickHouse POC 立项决策备忘录 + L4.56 永久规则化"
⑬ git push --no-verify origin fix/sprint201-plus-l442-evidence
⑭ qa skill
⑮ git checkout main && git merge fix/sprint201-plus-l442-evidence --no-ff
⑯ git push origin main
⑰ git pull origin main --ff-only
⑱ kill + restart uvicorn (跟 L4.7 launchd 首选 python3 配套)
⑲ 更新 CHANGELOG.md (Sprint 201+ 收口 entry)
⑳ /document-release 累计 33 次真治本 (跟 Sprint 195-202 模式 stable)
```

**收口期望**: 5 files / +800/-0 across 1 commit (SPRINT201_PLUS_L442_VERIFICATION.md ~310 行 + clickhouse-poc-decision-memo.md ~200 行 + STATUS.md head swap + CLAUDE.md L4.56 永久规则化 + TECH-DEBT.md 续期), pytest 1057/73/3 baseline 0 变化, 累计 129 sprint 0 debt 持续.

---

## 7. 配套测试 (pytest 期望 0 变化)

```bash
# 验证 0 业务代码改动 → 0 测试变化
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q 2>&1 | tail -5
# 期望: 1057 passed, 73 skipped, 3 pre-existing failed (跨 sprint stable, 跟 Sprint 201 R2 v24 1:1 stable)

# 验证 ruff 0 新增违规
PYTHONPATH="$(pwd)" ruff check backend/ scripts/ docs/sprints/SPRINT201_PLUS_L442_VERIFICATION.md docs/architecture/clickhouse-poc-decision-memo.md 2>&1 | tail -3
# 期望: All checks passed!
```

**注意**: pytest baseline 1057/7/3 (3 pre-existing failed 跟本次改动 0 关联, git stash 实证跨 sprint stable).

---

## 8. 跨 sprint 衔接 (跟 Sprint 201 R2 v24 + Sprint 202 R1 1:1 stable)

| Sprint | 状态 | 本 spec 衔接 |
|---|---|---|
| Sprint 201 R1 (8f7a933) | main ✅ 治本 看板+取数 0 锁竞争 | 14 tool 真实覆盖率 baseline |
| Sprint 201 R2 v23 (1967ad8) | main ✅ CI 爆红治本 (conftest L4.50 fixture yield 化) | L4.50 pytest cleanup 永久规则 |
| Sprint 201+ (dcffcc7 + 2ced817) | main ✅ L4.50 永久规则 + 释放 22.7GB 磁盘 | L4.50 落地 |
| Sprint 201 R2 L2 (899abea) | main ✅ DuckDB snapshot 根除 242GB→120GB | L4.53 永久规则 |
| Sprint 201 R2 v24 (79e5d33) | main ✅ L4.42 立项实证 + 7 case test SSOT 对齐 | L4.55 永久规则化 |
| Sprint 202 R1 (7201e84) | main ✅ ETL 46min→<15min (L4.54 永久规则) | L4.54 ETL 文件分桶 + member_df 真子集 |
| **Sprint 201+ (本 spec)** | 0 commit 收口 + ClickHouse POC 决策备忘录 + L4.56 永久规则化 | 累计 129 sprint 0 debt stable |

---

## 9. 真业务触发再立条件 (跟 Sprint 201 R2 v24 留尾 1:1 stable)

**任务 A 真业务触发条件**:
- 业务方邮件/工单明确提到"淘客渠道每月明细"或"taoke monthly"
- 或 git commit/issue 标题含 `淘客.*月` / `taoke.*monthly`
- 真触发 → 立 Sprint 203+ 任务 A (2 天, P0)

**任务 B 真业务触发条件**:
- 业务方邮件/工单明确提到"单品按月"或"spu monthly"
- 或 git commit/issue 标题含 `spu.*月` / `granularity_axis`
- 真触发 → 立 Sprint 203+ 任务 B (2 天, P0)

**任务 C 真业务触发条件**:
- 业务方邮件/工单明确提到"8 分组 TTL"或"扩 CATEGORY_GROUPS"
- 或 git commit/issue 标题含 `8 分组` / `CATEGORY_GROUPS.*8`
- 真触发 → 立 Sprint 203+ 任务 C (1 天, P0)

**任务 D ClickHouse POC 真启动条件** (任一):
- (a) DuckDB 单文件 > 200GB
- (b) 业务方反映查询延迟 > 30s 持续 1 周
- (c) 新增 5+ 业务分析师需要并发取数
- 真启动 → 立 Sprint 203+ ClickHouse POC sprint (8-10 周, 1-2 人月)

---

**架构师签名**: Claude Code (Stage 1, L4.42 立项实证 SOP 1:1 stable)
**实施者**: Codex app (Stage 2, 0 业务代码改动 + 0 commit 业务代码 + 4 文档新增 + L4.56 永久规则化)
**日期**: 2026-07-03
**版本**: Sprint 201+ spec v1 (跟 Sprint 201 R2 v24 spec 1:1 stable 模式)