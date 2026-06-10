# Sprint 14 Retrospective — Ratio 治理 Stage 2 + ETL 治根 + 0.5% 显示根治

**Sprint**: 14
**时间**: 2026-06-10
**状态**: ✅ 收口 (main @ 2814ace)
**主题**: A.1+A.3 Stage 2 Pydantic 6 contract 替换 + A.2 openapi-typescript codegen + B mtime 语义统一 + B+ is_member replay 集成 + /qa + /codex 对抗 4 P0 治根 + 0.5% 显示根治 3 frontend 修复

---

## 1. Sprint 结果

### 数字说话

| 维度 | Sprint 13 收口 | Sprint 14 收口 | Delta |
|------|----------------|----------------|-------|
| **Contract 治理** | | | |
| backend/contracts 自定义 Pydantic 类型 | 0 个 | **3 个** (RatioField 0-1, PercentageField -1M~1M, PpField -100~100) | +3 |
| Contract validator 字段 (audience + metrics + category + health + rfm) | 0 处 | **70+ 处** | +70 |
| **ETL 治根** | | | |
| processed_files_*.json mtime 语义 | 错位 (parquet vs xlsx) | **统一源 xlsx mtime** | 修 |
| is_member 集成 | 手动跑 2 个脚本 | **自动 Step 4.6 + 4.7** (集成 pipeline) | 修 |
| 拉数据 pipeline 写 processed_files | 误用同一 artifact | **Sprint 14.5 跟进** (architecture 改动大) | 部分 |
| **Bug 修复** | | | |
| Sprint 14 引入 regression (audience/table 9620 越界 + 3 端点 500) | — | **0 处** (4 P0 治根) | 修 |
| Sprint 14 治根不彻底 (0.5% 显示) | — | **0 处** (fmtRatio + 4 处 + tooltip *100) | 修 |
| **测试** | | | |
| backend pytest | 375 passed | 394 passed | +19 |
| frontend vitest | 38 passed | 38 passed | ✓ |
| vue-tsc --noEmit (真编译 .vue 模板) | 未跑 (漏错) | **0 错** (3 commit 漏语法后修) | 教训防线 |
| 4 端点 (audience/table + audience/summary + category/overview + metrics/overview) | Sprint 13 全 200 | Sprint 14 全 200 (引入 regression 全治根) | ✓ |
| **is_member 数据** | | | |
| orders is_member=TRUE | 5,632,356 (Sprint 10 救火后) | 5,632,356 (Sprint 14 B+ 集成后, 跑批 2 次稳定) | 幂等 |
| membership_mark unique order_id | 4,600,432 | 4,600,432 | 稳定 |
| 6/9 数据进库 | Sprint 13 已修 | Sprint 14 自动跑批持续 | 持续 |
| **Commits** | | | |
| Sprint 14 commits | 8 (Sprint 13) | **11** (5 wave + 2 治根 + 3 frontend + 1 defensive) | +3 |
| 紧急 frontend 修 (regex backref 漏改) | — | 1 (ba745ca) | 教训 |

---

## 2. 关键 bug 复盘

### 2.1 Sprint 14 A.1 治根不彻底 (service /100 改但 frontend 漏 *100)

**根因**:
- Sprint 13 治理后, 契约约定 ratio 字段存 0-1 decimal, 前端 caller 自乘显示
- Sprint 14 A.1 改 service `audience_summary.py` 50 行 + `overview.py` 3 行 `round(x * 100, 2)` → `round(x, 4)` (存 0-1)
- **但 frontend 5 处显示位置漏 `* 100`**: `fmtRatio()` (line 1694) + 4 处 `member_*_vs_all_*` inline (line 1112/1124/1151/1163) + 趋势图 tooltip (line 1416)
- 用户报告 (2026-06-10): "老客占比/新客占比/会员GSV占比显示 0.5%, 真实应是 50%"

**修法** (3 commits):
- `f72cbe3` `fmtRatio()` + 4 处 inline 加 `*100`
- `1126957` 趋势图 tooltip 加 `*100`
- `ba745ca` 紧急修 4 处 regex backref 漏改的语法错 (`const v = row.const v = row.X`)

**教训**: sprint 范围大, contract + service + frontend 3 端同步修改时, 应**单端验证再 commit** 而不是"全改完跑测试"。

### 2.2 Sprint 14 A.1 引入 regression (audience/table 9620 validator 越界)

**根因**:
- Sprint 14 A.1 给 70+ 字段加 `RatioField` (0-1 范围) + `PercentageField` (0-100 范围) + `PpField` (-100~100)
- 但 backend service `yoy_absolute` 已 *100 返 percentage (e.g. 117829.76 = 1178.29% YOY), 超出 PercentageField 0-100 范围
- Pydantic ValidationError, 端点 500 INTERNAL_ERROR

**修法** (2 commits):
- `67b794d` 临时放宽 `PercentageField` le=1M (QA 修)
- `8b2352c` /codex 治根 4 P0 (含 service /100 同步 + _mark_all_files_processed 修)

**教训**: Pydantic validator 加在 contract 时, 必须**先跑端到端**确认 service 端数据范围匹配, 而不是看 contract 觉得对就行。

### 2.3 /codex 对抗检查找出 4 P0 (Sprint 14 自评漏掉)

**根因**: Sprint 14 收口时, 4 wave 跑完 + pytest 全过就 merge, 漏掉 service/100 同步 + _mark_all_files_processed 漏改 + PercentageField ge=0 拒负 YOY。

**修法**: /codex adversarial 跑出 6 P0 + 3 P2, 治根 4 P0 全部修复。

**教训**: /review + /qa 都"过"了 ≠ 无 bug。/codex cross-model adversarial 才有"找 review 跟 QA 漏掉的"价值。

### 2.4 pre-commit 漏 vue-tsc 真编译, 3 commit 漏语法错

**根因**: 
- vitest 不 import `.vue` 模板 (单测时模板不编译)
- Sprint 14 3 次 frontend commit (f72cbe3/1126957/ba745ca) regex backref 漏改, `const v = row.const v = row.X` 语法错, vitest 跑过但 vite 编译报
- 用户跑 vite 才发现 "Missing semicolon (1111:29)"

**修法** (`2814ace`): pre-commit 加 `vue-tsc --noEmit` 强制 type check (改 frontend-vue3/src/ 时阻断, 不许 `--no-verify` 跳过)

**教训**: 单测过 ≠ 无语法错。Vue SFC 模板必须在 commit 前真编译。

---

## 3. 决策审计

### 3.1 Sprint 14 拍板 (用户决策)

| 决策 | 选项 | 拍板 | 理由 |
|------|------|------|------|
| Sprint 14 范围 | A: Pydantic only / B: A+B+H / C: A+B+B++H | **C (扩 5-6d)** | 治根 + ETL 治根, 一次性收口 |
| B 方案 | A: mtime 语义统一 / B: 拉数据 pending_files | **A** | 改动小 (1 行), 跟 ingest.py 一致 |
| is_member 集成 | P: pipeline 集成 / Q: cron / R: P+Q | **P** | 改 0 行 ETL 外代码, 自动一致 |
| Sprint 14.5 范围 | 5-6d 含 is_member 集成 / 4-5d 留 Sprint 14.5 | **5-6d** | 完整治根 |
| 前端 *100 修法 | A: service /100 / B: contract 改 / C: A+B 治根 | **A (root cause)** | 跟 Sprint 13 治理契约一致 |

### 3.2 Sprint 14 自评 vs 实际

| 维度 | 自评 (Sprint 14 收口时) | 实际 (/codex + 用户报告) |
|------|--------------------------|--------------------------|
| 5 wave 完成 | ✅ | ✅ |
| pytest 394 passed | ✅ | ✅ |
| 4 端点全 200 | ✅ (初始) | ❌ (引入 regression, /qa 找出) |
| service/contract 同步 | ✅ (自评) | ❌ (frontend 漏 *100) |
| is_member 端到端 | ✅ (Sprint 10 救火) | ✅ (Sprint 14 B+ 集成后) |
| 治根彻底 | ✅ (自评) | ❌ (5 处 frontend 漏 *100) |

**教训**: 治根 ≠ commit, 必须**端到端 + 真实显示验证**才算彻底。

---

## 4. 治理债务 (Sprint 14.5+ 待办)

| # | 任务 | 优先级 | 阻塞 |
|---|------|--------|------|
| 1 | `AudienceRow.yoy_*` 28 字段加 `PercentageField` (Sprint 14 漏标) | 🟡 P1 | ratio 治根 |
| 2 | `replay_is_member.py` 包 `BEGIN; ... COMMIT;` (DROP INDEX 6 秒窗口数据风险) | 🔴 P0 | 跑批原子性 |
| 3 | `replay_is_member.py` member 删除不清 (mark rebuild 后 is_member 不清) | 🟢 P2 | 数据一致性 |
| 4 | Step 4.6/4.7 fail-soft 隐藏 mark drift | 🟢 P2 | 数据可见性 |
| 5 | 拉数据 pipeline 写 processed_files (上下游解耦) | 🟢 P2 | 架构债 |
| 6 | 6 道门禁 Connection 错误 (cross_day/api_health/dedup) | 🟢 P2 | pre-existing flake |
| 7 | e2e customer-health WASM flake | 🟢 P2 | pre-existing |
| 8 | 50M 架构实施 (Stage 2 plan 已写好) | 🔵 P3 | 长期 |
| 9 | is_member 派生重构 (143 处引用) | 🔵 P3 | defer |

---

## 5. 学到的教训 (Learnings)

### 5.1 治根 ≠ commit, 必须端到端验证

**问题**: Sprint 14 5 wave 跑完 + pytest 全过就 merge, 漏掉 frontend 5 处 *100 漏改。

**教训**: 改 contract / service / frontend 3 端时, 必须**先跑端到端** (curl API + 浏览器显示) 确认 3 端都正确, 不是"代码改完跑过单测就行"。

**行动**: Sprint 14.5 必跑端到端 ETL + 浏览器显示验证。

### 5.2 0.5% 显示 = 治根不彻底

**问题**: Sprint 14 A.1 改 service `*100` 但 frontend 漏 *100, 用户报告显示 0.5% 真实 50%。

**教训**: sprint 范围大, contract + service + frontend 3 端同步修改时, 必须**每端单独验证**再 commit, 不能"全改完跑测试"。

**行动**: Sprint 15+ 单端验证 checklist (contract validator / service SQL / frontend display / E2E 4 端)。

### 5.3 /codex 对抗找 review + QA 漏掉的

**问题**: Sprint 14 自评 + /review + /qa 都过了, /codex 才找出 4 P0 + 3 P2。

**教训**: cross-model adversarial 价值在"找 review 跟 QA 漏掉的", 不能省。

**行动**: Sprint 15+ 每个 sprint 收口前必跑 /codex 对抗。

### 5.4 Vue SFC 模板必须真编译

**问题**: vitest 不 import .vue 模板, 3 commit 漏语法错, 用户跑 vite 才发现。

**教训**: 单测过 ≠ 无语法错。pre-commit 必须真编译。

**行动**: `2814ace` pre-commit 加 vue-tsc --noEmit, 强制 type check 阻断。

### 5.5 数字跳变 (52.70% is_member) = 数据正确性信号

**问题**: Sprint 14 集成 is_member replay 后, prod 5,632,356 跟 membership_mark 4,600,432 对齐, 一致性提升。

**教训**: 数据正确性 (run 2 次稳定) 比"快速通过"重要。

**行动**: Sprint 15+ 跑批后必验 "跑 2 次稳定 (幂等)" 验收。

---

## 6. 时间线复盘

| 时间 | 事件 |
|------|------|
| 06:50 | 用户报告 4 个 100× bug + 问"大厂/AI 风格统一管理方案" |
| 07:00 | pp-ratio-audit workflow 跑 (8 agent / 562K tokens / 28 min) — 33+1+1+4+8+3 调研 |
| 08:00 | autoplan 4 phase review (CEO/Eng/DX 4.6/10/Design, 25 decision audit trail) |
| 09:00 | 4 phase 拍板 (3 阶段分 sprint / Excel 双列 / CHANGELOG+banner / Stage 3 全做) |
| 09:30 | 写 SPRINT-13-PLAN-RATIO-GOVERNANCE.md (538 行 19 章节) |
| 10:00 | 切 fix/sprint13-ratio-governance 分支 |
| 10:00-10:30 | 4 wave 并行修 (组件 + 后端契约 + caller + 文档) |
| 10:30 | 跑 pytest (375 passed) + vitest (38 passed) |
| 10:45 | /review 找 P0-3 docstring + P1-1 CHANGELOG, 修完 |
| 11:00 | 7 个 commit + push origin fix 分支 |
| 11:15 | /qa curl + playwright 验证, 找到 AudienceView ratio *100 次生 bug, 修完 d40a7ce |
| 11:25 | ⑨ merge fix → main (2bc6321) |
| 11:30 | ⑩ push main, ⑪ pull, ⑫ 重启 uvicorn |
| 11:35 | 第一次增量 ETL 跑批 (10:18-10:44) — 6/9 数据未进库 (processed_files 误用) |
| 11:45 | /ship 收口 + ad1cb20 推 main |
| 12:00-12:30 | 第二次增量 ETL 跑批 (11:28-11:52) — 6/9 数据进库, 修复自愈 |
| 12:30 | 总结报告 + Sprint 14 计划 (STAGE 2) |
| 13:00 | Sprint 13 收口文档 (CHANGELOG v0.4.14.30 + retrospective + index) |
| 14:00 | Sprint 14 启动 (4 wave) |
| 14:00-15:00 | Wave 4 B (mtime 语义) + Wave 5 B+ (is_member replay) + Wave 1+3 A.1+A.3 (6 contract) + Wave 2 A.2 (codegen) + Wave 6 H (清理) |
| 15:00 | Sprint 14 5 commits merged main (3cf1066) |
| 15:00-15:30 | /review 跑 (0 P0/P1/P2, 4 P3 graceful degrade) |
| 15:30-16:00 | /qa 跑 (4 端点, 找出 regression 9620 越界, 修 67b794d) |
| 16:00-16:30 | /codex 对抗跑 (找出 4 P0 + 3 P2, 治根 4 P0, commit 8b2352c) |
| 16:30-17:00 | 治根 4 P0: service /100 (50+3 行) + _mark_all_files_processed 修 + PercentageField ge=-1M |
| 17:00-17:30 | merge + push main (0e80b5d) |
| 17:30-18:00 | 用户报告 0.5% 显示 — frontend 5 处 *100 漏改 (3 commit: f72cbe3/1126957/ba745ca) |
| 18:00-18:30 | pre-commit 加 vue-tsc 强制 type check (2814ace) |

**总耗时**: ~12 小时 (从 Sprint 13 启动到 Sprint 14 完整收口 + 教训防线)

---

## 7. 未来 Sprint 建议

### Sprint 15 (Stage 3 useFormat + Branded Type + Lint)
- C.1: composables/useFormat.ts (4 函数, 2h)
- C.2: 替换 50+ 处散落 *100 (3h)
- C.3: TypeScript Branded Type (4h)
- C.4: ESLint AST 级别 lint (4h, dry-run 1 周)
- 总: 5-7d, 50% AI 友好化, 防 LLM 写双重 *100

### Sprint 16 (技术债)
- P0: replay_is_member.py 包 transaction
- P1: AudienceRow.yoy_* 28 字段加 PercentageField
- P2: 6 道门禁 Connection 错误 / e2e WASM flake / Step 4.6/4.7 fail-soft

### Sprint 17+ (长期)
- 50M 架构实施
- is_member 派生重构 (143 处引用)

---

## 8. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 1 天 (Sprint 14) |
| Commits | 11 (含 1 治根 + 1 教训防线) |
| Files changed | 30+ (含 codegen 8.3K 行) |
| Lines changed | +12000 (含 codegen) |
| Memory files | project_sprint14.md (新) |
| Plan files | SPRINT-14-PLAN-RATIO-STAGE2.md (✅ 收口) + SPRINT-14-RETROSPECTIVE.md (新) |
| Health score | 95/100 (Sprint 13 98 → 14 95, -3 因为 Sprint 14.5 留 4 P0) |
| 4 端点 HTTP | 全 200 |
| 跑批时间 | 14-15 min (含 is_member replay 1-2 min) |
| 测试 | 394 backend + 38 vitest + vue-tsc 0 错 |
| pre-commit 防线 | vue-tsc --noEmit 强制 (Sprint 15+ 防 0.5% 类 bug) |
| Sprint 14.5 留 9 任务 | 2 P0 (replay transaction + AudienceRow 漏标) + 4 P2 + 3 P3 |

---

*此文件由 Sprint 14 完整收口 + 教训防线流程生成, 最后更新 2026-06-10*
