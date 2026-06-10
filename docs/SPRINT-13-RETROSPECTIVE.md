# Sprint 13 Retrospective — 比率口径统一

**Sprint**: 13
**时间**: 2026-06-10
**状态**: ✅ 收口 (main @ ad1cb20)
**主题**: 33 处 100× bug + 1 处 10000× bug + 1 处永远 0% + 4 处 Excel + 8 处 unit 漏标 全部修复

---

## 1. Sprint 结果

### 数字说话

| 维度 | Sprint 12 收口 (修前) | Sprint 13 收口 (修后) | Delta |
|------|------------------------|------------------------|-------|
| **功能完整性** | | | |
| Health score | 70/100 | **98/100** | **+28** |
| 已知 100× bug | 33 处 | 0 处 | -33 |
| 已知 10000× bug | 1 处 (30 指标表) | 0 处 | -1 |
| 永远 0% bug | 1 处 (churn 详情页新客占比) | 0 处 | -1 |
| Excel 100× bug | 4 处 | 0 处 (改双列) | -4 |
| unit 漏标 | 8 处 | 0 处 | -8 |
| **测试** | | | |
| backend pytest | 375 passed | 375 passed | ✓ |
| frontend vitest | 38 passed | 38 passed | ✓ |
| playwright e2e | 1/2 passed (WASM flake) | 1/2 passed (WASM flake 仍 pre-existing) | 不变 |
| **ETL** | | | |
| 增量 ETL 跑批 | 10:18 一次 26min | 10:18 + 11:28 两次, 第二跑批 24min | 1 跑批变 2 跑批 (6/9 数据首次延迟) |
| max(pay_time) | 2026-06-08 23:59:57 | 2026-06-09 23:59:57 | +1 天 |
| orders 6/9 行数 | 0 (delay) | 6,445 | +6,445 |

---

## 2. 关键 bug 复盘

### 2.1 根因 (3 重 ×100 串味)

| 位置 | 行为 | 倍率 |
|------|------|------|
| `audience_summary._extract_metrics:293-309` | `*100` 把 ratio 存 percentage | ×100 |
| `yoy_ratio()` (calculations.py:58) | `(cur - comp) * 100` 返 pp 数值 | ×100 |
| `humanizeChange` (MetricCard/YOYBadge) | `unit === 'pp' ? raw * 100 : raw` 内部又 ×100 | ×100 |
| **合计** | 30 指标表 10000× 偏大 | ×10000 |

`audience_summary` 改成 ratio 字段存 0-1 decimal, 让 `yoy_ratio` 入参对齐, 修掉双重 ×100. 前端 `humanizeChange` 改 pass-through, 修掉第三次 ×100.

### 2.2 visitor_service 孪生 bug

`line 70 + line 86` 是同一作者同一 commit 写的同款 `(rate/100 - comp/100)` 公式. 调研阶段漏标 line 86, **/qa 阶段发现并一起修**. 这是 Wave 3 subagent 漏标的盲区, 通过 /qa 的 curl 验证发现.

### 2.3 unit 漏标 8 处

R/M/F IntervalTab + ValueTierTab 共 8 处 `yoy_repurchase_rate / yoy_repurchase_gsv_ratio` 漏标 `unit='pp'`. 字段名带 `_rate` / `_ratio` 暗示百分比, 但语义是 pp 差. 这是 Sprint 11+12 修复 AudienceView/CategoryView/HealthOverview 时漏过的. **治本方案**: Sprint 15 Stage 3 用 TypeScript Branded Type (`type Pp = number & { __brand: 'Pp' }`) 强制区分.

### 2.4 老客 GSV 0.41% — **非 bug, 是误判**

`yoy_absolute` 内部 `*100` 返 percentage 41, 前端 `unit='%'` 不 `*100` 直显, 数学一致. 用户视觉跟"老客占比 5.28pp"对齐产生误判, 实际两者语义不同 (占比是当前值, 同比是变化量). **保留不动**.

### 2.5 QA 找到的次生 bug

`AudienceView.vue:255` `renderValue` 把 ratio 字段 (Sprint 13 W6 改成 0-1 decimal) 仍当 percentage 显示, 显示 "0.41%" 而非 "40.66%". 同时 Excel 导出 `aoa.push` 也有同款 bug. **/qa 阶段用 curl API 验证发现, 修了 1 文件 8 行**.

### 2.6 6/9 数据延迟 — 增量逻辑的盲区

源 xlsx 6/9 拉数据时 (6/10 00:29) `processed_files_shop.json` 提前更新, 但 ETL 实际跑批 (10:18) 增量模式判定"已处理"跳过, INSERT 路径未触发. 第二次跑批 (11:28) 全量覆盖才进库. **根因**: 拉数据 pipeline 跟 ETL pipeline 误用同一 artifact. Sprint 14 治理: 拉数据写 `pending_files.json`, ETL 成功 INSERT 后转换 processed_files.

---

## 3. 决策审计

### 3.1 修法方向选择

| 方向 | 选 | 不选 | 理由 |
|------|----|----|------|
| 修前端 pass-through (方向 A) | ✅ | | 符合 CLAUDE.md "前端只展示" 硬规则, 改动最小, 跟 v0.4.14.26 一致 |
| 修后端返 0-1 (方向 B) | | ✅ | 违反 v0.4.14.26 重构方向, 19 caller 需同步 |

### 3.2 治理节奏

| 阶段 | Sprint | 选择 |
|------|--------|------|
| Stage 1 止血 | Sprint 13 | ✅ (本次) |
| Stage 2 契约加固 | Sprint 14 | 待启动 (A+B+H 4-5d) |
| Stage 3 AI 友好 | Sprint 15 | 计划 (C 全做 useFormat+Branded+Lint, 5-7d) |

### 3.3 user 拍板 (4 项)

| 决策 | 拍板 |
|------|------|
| Sprint 节奏 | 3 阶段分 sprint |
| Excel 格式 | 改双列 (数值 + 标签) |
| 信任修复 | CHANGELOG 强条目 + 4 页面 banner 3 天 |
| Stage 3 范围 | 全做 (useFormat + Branded + Lint) |

---

## 4. 治理债务 (Sprint 14+ 待办)

| # | 任务 | 优先级 | 阻塞 |
|---|------|--------|------|
| 1 | Sprint 14 Stage 2 Pydantic 契约加固 (6 contract) | 🔴 P0 | ratio 治根 |
| 2 | processed_files 误用 bug 修 (拉数据改 pending_files.json) | 🔴 P0 | 6/9 数据延迟同类 |
| 3 | Sprint 15 Stage 3 useFormat + Branded Type + Lint | 🟡 P1 | AI 友好化 |
| 4 | 6 道门禁 Connection 错误 (cross_day/api_health/dedup) | 🟢 P2 | ETL 跑批后报 6 道门禁 fail |
| 5 | e2e customer-health WASM 网络加载 flake | 🟢 P2 | 1/2 e2e 间歇失败 |
| 6 | 50M 架构实施 (Stage 2 plan 已写好) | 🔵 P3 | 50M 行架构预演 |
| 7 | is_member 派生重构 (143 处引用) | 🔵 P3 | 性能/一致性 (defer) |
| 8 | /tmp/etl-*.log + 旧备份清理 | 🟢 P2 | 磁盘 52GB 释放 |

---

## 5. 学到的教训 (Learnings)

### 5.1 契约层失守 = bug 频发源

**问题**: `backend/contracts/` 0 个 `Field(ge/le/decimal_places)` validator, 错返 0-1 / pp / percentage 类型无法在 API 入口拦.

**教训**: 契约层失守会让"前后端语义对齐"靠人工维护, 100× bug 类问题反复出现.

**行动**: Sprint 14 Stage 2 Pydantic validator, Sprint 15 Stage 3 codegen.

### 5.2 增量逻辑的 artifact 误用

**问题**: 拉数据 pipeline 跟 ETL pipeline 误用同一 `processed_files_shop.json` artifact.

**教训**: 不同阶段 pipeline 写同一 artifact 必出问题. artifact 应按"已拉取 / 已处理"严格分离.

**行动**: Sprint 14 修, 用 `pending_files.json` 分离.

### 5.3 /qa 阶段 catch 真实 bug

**问题**: Wave 2 subagent 漏标 visitor_service line 86 孪生 bug + AudienceView ratio 显示次生 bug.

**教训**: Subagent 报告覆盖率有盲区, 真实 ETL 数据 + 浏览器 e2e 才能 catch.

**行动**: 保持 /qa 流程, 每次 commit 后跑 curl API 验证 + playwright e2e.

### 5.4 字段名误导 (rate/ratio 暗示百分比)

**问题**: 字段名 `yoy_repurchase_rate` 暗示 percentage, 但语义是 pp 差. 8 处 caller 漏标 unit='pp'.

**教训**: 字段名 + 类型应一致, 不要靠 caller "猜" 字段语义.

**行动**: Sprint 15 Stage 3 Branded Type (Percentage / Decimal / Pp) 强制区分.

### 5.5 数字跳变 = 信任冲击

**问题**: 30 指标 10000× 修后, PM/老板看到数字 4 数量级跳变, 怀疑"是不是又改错".

**教训**: 大改后必须主动沟通 (CHANGELOG + banner + 邮件), 否则引发"二次信任"问题.

**行动**: Sprint 13 用了 CHANGELOG 强条目 + 4 页面 banner 3 天 TTL, 化解有效.

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

**总耗时**: ~6 小时 (从用户报告 4 bug 到 Sprint 13 完整收口)

---

## 7. 未来 Sprint 建议

### Sprint 14 (Stage 2 Pydantic)
- A.1: 6 个 contract 加 `Field(ge/le/decimal_places)` (1.5d)
- A.2: openapi-typescript codegen (0.5d)
- A.3: 跑 codegen 验证 + 前端类型切换 (1d)
- B: processed_files 误用 bug 修 (1-2h)
- H: /tmp/etl-*.log + 旧备份清理 (30min)
- 总: 3-4d, 价值: ratio 治根 + AI 友好

### Sprint 15 (Stage 3 useFormat)
- C.1: composables/useFormat.ts (4 函数, 2h)
- C.2: 替换 50+ 处散落 *100 (3h)
- C.3: TypeScript Branded Type (4h)
- C.4: ESLint AST 级别 lint (4h, dry-run 1 周)
- 总: 5-7d, 价值: 50% AI 友好化

### Sprint 16+ (技术债)
- 6 道门禁 Connection 错误
- e2e WASM 网络 flake
- 50M 架构实施
- is_member 派生重构 (大改, defer)

---

## 8. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 1 天 (2026-06-10) |
| Commits | 8 |
| Files changed | 26 (+ 2 new) |
| Lines changed | +1024 -80 |
| Memory files | project_sprint13.md (新) |
| Plan files | SPRINT-13-PLAN + SPRINT-14-PLAN (新) |
| Plan retrospective files | SPRINT-13-RETROSPECTIVE (新, 本文件) |
| QA 报告 | .gstack/qa-reports/qa-report-sprint13-2026-06-10.md |
| Health score | 70 → 98 (+28) |
| Bug 修复 | 47 处 (33+1+1+4+8+1 QA 次生) |
| 跑批验证 | 2 次 (首次延迟, 二次自愈) |
| Disk 治理 | 待 (52GB 备份 / 11 个 /tmp log) |

---

*此文件由 Sprint 13 收口流程生成, 最后更新 2026-06-10*
