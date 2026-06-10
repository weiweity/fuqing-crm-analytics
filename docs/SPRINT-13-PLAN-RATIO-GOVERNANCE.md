# Sprint 13 — 比率口径治理 (Ratio Governance)

**立项时间**: 2026-06-10
**生成方式**: /autoplan
**前置调研**: `pp-ratio-audit` workflow (8 agent / 562K tokens / 28min)
**模式**: SELECTIVE EXPANSION (hold scope on 33 个 bug 修复 + cherry-pick 契约层加固)

---

## 1. Problem Statement

### 1.1 用户可见痛点（不是 bug,是契约治理失败）

| 痛点 | 表面现象 | 根因（架构视角）|
|---|---|---|
| **P1 数字 100× 偏大** | 老客占比 1040.00pp、渠道 528.00pp、品类 7+ 处 | 后端 `yoy_ratio` 已 `*100` 返 pp 数值(5.0),前端 `humanizeChange` 在 `unit='pp'` 时又 `*100` → 双重 ×100 |
| **P2 30 指标 10000× 偏大** | 104000.00pp | `audience_summary._extract_metrics` ratio 字段 `*100` 存 percentage → `yoy_ratio(percentage, percentage)` 二次 `*100` → 前端 `YOYBadge` 三次 `*100` |
| **P3 品类细节永远 0%** | `CategoryDetailView` 新客占比 0% | `churn.py:336` `new_customer_ratio = [0.0] * len(dates)` hardcode 占位 |
| **P4 Excel 导出 100×** | `ProductClassRepurchaseTab` / `HealthOverviewTab` 导出 numFmt='0.0%' 把 pp 差再 `*100` | numFmt 套错,后端 pp 数值用 % 格式 |
| **P5 老客 GSV 0.41% 误判** | 用户怀疑 100× bug | 实际语义错位(占比 vs 同比),不是 bug |
| **P6 RFM/R/F/M 区间 + ValueTierTab 8 处** | 字段名 `_rate/_ratio` 但 YOYBadge 默认 `%` 不传 `unit='pp'` | caller 漏标 unit,Sprint 11+ 修漏 |
| **P7 MarketBasket 置信度变化 100×** | 0.1pp (应是 5pp) | `basket.py:326` `confidence_change` 返纯 decimal 差,前端又 `*100` 当 pp 差 |
| **P8 契约层 0 校验** | 错返 0-1/pp/percentage 类型无法在 API 入口拦 | `backend/contracts/` 0 个 `ge/le/decimal_places` validator |

### 1.2 战略问题

- **契约层失守**: `calculations.py:yoy_ratio` 返"已 *100"pp 数值,文档注释和契约 description 都不一致,新人/AI 难以推断字段单位
- **前端散落 50+ 处 `*100`**: 违反 CLAUDE.md "前端只展示" 硬规则,且无 lint 规则禁止
- **无 AI 友好契约**: LLM 看代码要靠 description 字符串(人读),不能靠类型/branded type/Zod schema(机器读)
- **Excel 导出独立 bug 源**: 5 个 `numFmt='0.0%'` 对 pp 数值错用,跟前端 `*100` 是同根问题(契约不明)

### 1.3 12 个月差距

```
当前: 33 个 100× bug + 1 个 10000× bug + 1 个永远 0% + 4 个 Excel 100×
理想: 契约层自动校验 + LLM 可读 schema + 前端 0 处散落 *100 + Excel numFmt 自动
```

---

## 2. Premises (决策的事实基础)

| # | Premise | 验证 | 反驳条件 |
|---|---|---|---|
| 1 | `humanizeChange` 在 `unit='pp'` 时去掉 `*100` 是方向 A 最小改动 | 调研确认后端 `yoy_ratio` 全栈已 *100 | 仍有 caller 传 0-1 (反向路径) |
| 2 | `visitor_service.py:70` 是唯一反向路径 | 调研覆盖 7 个 service + 1 个 visitor | 还有未发现的反向 caller |
| 3 | `audience_summary._extract_metrics:293` 是 10000× 唯一源头 | 调研覆盖 5 个 metrics service | category_service 也有同款 |
| 4 | Pydantic 加 `Field(ge=0, le=100, decimal_places=2)` 能 catch 单位错 | 业界 Stripe/Cloudflare/Linear 标准做法 | DuckDB→Pydantic 链路无 unit 约束 |
| 5 | composables/useFormat.ts 集中 *100 是 V0 风格(Stripe 模式) | 业界 Linear 用 zod+V0 风格 | 大型项目倾向 Zod+branded type |
| 6 | Excel numFmt 改 `'0.0"pp"'`/`'0.0"%"'` 是治标 | SheetJS 支持 numFmt literal | 中文/英文双 numFmt 复杂度 |
| 7 | 4 个文件加 `unit='pp'` 是 30 秒 fix | R/M/F IntervalTab + ValueTierTab 验证 | Sprint 11+ 留下未对齐的字段名 |
| 8 | 契约层加固是 Sprint 14+ 的事,Sprint 13 聚焦止血 | 12 步流程 1-2 天可完成 33 处 | 5 处 Pydantic 自定义类型要 2-3 天 |

---

## 3. 选定方案: **方向 A (3 阶段)**

### 3.1 Stage 1 — 止血 (Sprint 13, 1-2 天)

**目标**: 33 处 100× bug + 1 处 10000× + 1 处 0% + 4 处 Excel + 8 处 unit 漏标, 全部修完, 数字正确显示。

| 工单 | 文件 | 改动 |
|---|---|---|
| W1 | `MetricCard.vue:17` | `display = raw` (去掉 *100) |
| W2 | `YOYBadge.vue:17` | 同上 |
| W3 | `SamplingView.vue:170-172` | `fmtYoy` 去掉 `v * 100` |
| W4 | `RFMSegmentDrilldown.vue:174,194` | `fmtYoY` 去掉 `v * 100` |
| W5 | `ProductCustomerTab.vue:578-689` | `fmtYoy/fmtPctChange` 去掉 `v * 100` |
| W6 | `audience_summary.py:293-309` | 10000× bug 源头: 去掉 `_extract_metrics` 的 *100 |
| W7 | `visitor_service.py:70,86` | `(rate/100) - (comp/100)` → `(rate - comp)`, 对齐其它 yoy 字段 |
| W8 | RIntervalTab.vue:228,242 / MIntervalTab.vue:190,204 / FIntervalTab.vue:190,204 / ValueTierTab.vue:281,283 | 加 `unit='pp'` (8 处) |
| W9 | `MarketBasketTab.vue:255-261` | `*100` 去掉, 对齐 `lift_change` decimal 差 |
| W10 | `ProductClassRepurchaseTab.vue:95,107,119,131` | Excel numFmt 改 `'0.0"pp"'` / `'0.0"%"'` |
| W11 | `HealthOverviewTab.vue:334` | Excel numFmt 改 `'0.0"pp"'` (health_score_yoy) |
| W12 | `churn.py:336` | `new_customer_ratio` 真正实现 (走 `is_new` 计算) |
| W13 | 两组件 JSDoc 同步 | "caller 已 *100, humanizeChange 只做 abs + toFixed(2)" |
| W14 | `MetricCard.test.ts` / `YOYBadge.test.ts` | 补 6+6 个新单测 (pass-through 契约) |
| W15 | E2E 测试 | 老客占比卡片显示 5.00pp 而非 500.00pp |

**估时**: CC 1d / 人 0.5d (12 步流程)

### 3.2 Stage 2 — 契约层加固 (Sprint 14, 2-3 天)

**目标**: Pydantic 加 `RatioField / PpField / PercentageField` 三个自定义类型, 让契约层有牙齿。

| 类型 | 范围 | 用法 |
|---|---|---|
| `RatioField` | `0 <= v <= 1` | `*_ratio` (decimal) |
| `PercentageField` | `0 <= v <= 100` | `*_pct` (percentage) |
| `PpField` | `-100 <= v <= 100` | `*_ppt` (pp 差) |

**覆盖范围**:
- `backend/contracts/audience.py:146-215` (ChannelGSVRow)
- `backend/contracts/category.py:26-183` (CategoryOverviewItem / CategoryRepurchaseFlowRow / ValueTierTableRow)
- `backend/contracts/health.py:18-92` (HealthOverviewMetrics / RepurchaseBucket)
- `backend/contracts/metrics.py:19-23` (OverviewMetrics)
- `backend/contracts/rfm.py` (RFMRFlowRow / RFMFRFlowRow / RFMMFlowRow / RFMAnalysisRow)

**OpenAPI schema 自动带 minimum/maximum**: LLM 读 schema 知道字段范围。

**估时**: CC 2d / 人 1d (含 review + qa + 6 处 Pydantic schema)

### 3.3 Stage 3 — AI 风格落地 (Sprint 15, 5-7 天)

**目标**: 让 LLM 看契约就知道单位, 无需靠 description 字符串。

| 工单 | 内容 |
|---|---|
| W16 | `frontend-vue3/src/composables/useFormat.ts` (fmtRatio/fmtPct/fmtPp/fmtAbs 4 函数) |
| W17 | 替换 50+ 处散落 `* 100` |
| W18 | TypeScript Branded Types (Decimal / Percentage / Pp) |
| W19 | Lint 规则: ruff `RUF100-avoid-magic-100` + eslint `no-mixed-ratio-unit` |
| W20 | CLAUDE.md 加 Ratio Convention 章节 (LLM 可读) |
| W21 | pre-commit hook: contract test 必跑 |

**估时**: CC 5d / 人 2d

---

## 4. 依赖图 + 实施时间线

```
Stage 1 (Sprint 13):  止血
  W1+W2 → W3+W4+W5 → W6 → W7+W8 → W9+W10+W11+W12 → W13+W14+W15
  关键路径: 9 个工单 (1-2 天)

Stage 2 (Sprint 14):  契约加固
  Pydantic 类型 → 覆盖 6 个 contracts → 加 contract test → pre-commit hook
  关键路径: 3 个工单 (2-3 天)

Stage 3 (Sprint 15):  AI 风格
  useFormat → 50+ 处替换 → Lint → CLAUDE.md → pre-commit
  关键路径: 6 个工单 (5-7 天)
```

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Stage 1 W6 改 `_extract_metrics` 触发 100× → 10000× 漏修 | 中 | 高 | E2E 测试 + 单测断言 30 指标 yoy 在 [-50, 50] 范围 |
| Stage 1 W7 改 `visitor_service` 影响入会率趋势图 | 中 | 中 | 单测覆盖 `member_join_rate_yoy` 显示 0.50pp |
| Stage 2 Pydantic 自定义类型破坏现有 Pydantic v1 兼容 | 低 | 中 | 锁定 Pydantic v2 (项目已升 v2) |
| Stage 3 Lint 规则误伤非 ratio 代码 | 中 | 低 | 规则加 whitelist + dry-run 验证 |
| 老数据 (DuckDB 41GB) 字段值跟新契约不匹配 | 低 | 中 | 加 migration script 转换 0-1 → percentage |

---

## 6. Migration Plan

### Stage 1 Migration (Sprint 13)

1. 备份: `data/processed/backups/pre-sprint13-{ts}.duckdb`
2. 跑 baseline: 验证 30 指标表格 / 渠道概览 / 老客占比 / 健康评分 当前显示
3. 逐个工单走 12 步流程
4. 回归: 跑 E2E (audience/category/health/rfm) + pytest
5. 跑 1 次 ETL baseline (验证后端契约未变)

### Stage 2 Migration (Sprint 14)

1. Pydantic 类型先 dry-run (在 staging DuckDB)
2. 逐个 contract 迁移 (audience/category/health/metrics/rfm)
3. 跑 OpenAPI schema diff: 旧 schema vs 新 schema (无 diff 才 merge)

### Stage 3 Migration (Sprint 15)

1. Lint 规则先 warn-only 1 周 (收集误伤)
2. ESLint config 加 whitelist
3. 灰度 enforce (2 周)
4. 全量 enforce

---

## 7. Test Strategy

### Stage 1 测试

- `backend/tests/test_calculations.py` 不动 (后端不变)
- `frontend-vue3/src/components/MetricCard.test.ts` 加 6 个新单测 (pass-through 契约)
- `frontend-vue3/src/components/YOYBadge.test.ts` 加 6 个新单测
- E2E: `audience/category/health/rfm` 4 个 spec 断言显示正确数值
- 集成测试: 30 指标表格 yoy 范围 [-50, 50]

### Stage 2 测试

- `backend/tests/contracts/test_ratio_validators.py` (6 个 Pydantic 类型)
- OpenAPI schema snapshot test
- 契约层 fuzz test: 注入错值 (Decimal 给 PpField) → 期望 ValueError

### Stage 3 测试

- Lint 规则 dry-run (50+ 文件验证不误伤)
- `useFormat.ts` 单测
- Branded Type 编译期测试

---

## 8. Failure Modes

| 路径 | 失败 | 已有测试 | 错误处理 | 用户看到 |
|---|---|---|---|---|
| W6 `_extract_metrics` | 30 指标 yoy 变 10000× | E2E 必跑 | 回滚 commit | 104000.00pp 残留 |
| W7 `visitor_service` | 入会率趋势图空 | 集成测试 | 改回 /100 | 入会率 yoy 0.50pp → 0.01pp |
| W8 unit='pp' 漏标 | 显示 0.0x% | E2E 必跑 | 单文件 fix | RFM R 区间显示 0.03% |
| W12 `churn.py:336` | 详情页新客占比 SQL 慢 | 单测 | 加时间窗口 | 加载慢 5s |
| Stage 2 Pydantic | API 422 | 单测 | 字段 coerce | 数据 stale |

---

## 9. NOT in Scope (明确不做)

| 不做 | 理由 |
|---|---|
| 改后端 `yoy_ratio` 返 0-1 (方向 B) | 违反 v0.4.14.26 重构方向, 30+ caller 需同步 |
| 引入 tRPC / GraphQL 替代 OpenAPI | 现有 FastAPI 架构稳定, 改架构 ROI 低 |
| 重构前端到 React/Next.js | Vue3 稳定, 重构 1+ 月 |
| 引入 Zod / Yup 替代 Pydantic | 前后端语言不同, 共享 schema 难 |
| 改 is_member 派生 (143 处) | Sprint 9 评估过, 风险大, defer |
| DuckDB 1.5.3 升级 | Sprint 7 评估过, 无收益 |

---

## 10. Acceptance Criteria

### Stage 1 验收

- [ ] 老客占比卡片显示 `↑10.40pp` (而非 1040.00pp)
- [ ] 渠道概览 528.00pp → 5.28pp
- [ ] 30 指标表格 +104000.00pp → +10.40pp
- [ ] 品类 7+ 处 pp 显示正确
- [ ] Excel 导出 pp 字段显示 "5.0pp" 而非 "500.0%"
- [ ] 详情页新客占比不再永远 0%
- [ ] RFM/R/F/M 区间 + ValueTierTab 8 处加 unit='pp' 后显示 5.00pp
- [ ] 老客 GSV 41% (或真实百分比) 不变 (不是 bug)

### Stage 2 验收

- [ ] Pydantic 类型 6 个 contract 全部覆盖
- [ ] OpenAPI schema 自动带 `minimum: 0, maximum: 100`
- [ ] 契约层 fuzz test 通过: 注入错值 → ValueError
- [ ] pre-commit hook 必跑

### Stage 3 验收

- [ ] useFormat.ts 4 个函数单测
- [ ] 50+ 处散落 `* 100` 全部清零
- [ ] Lint 规则 dry-run 0 误伤
- [ ] TypeScript 编译期禁止混用 Decimal / Percentage / Pp

---

## 11. Time Estimate Summary

| 阶段 | CC | 人 | 墙钟 |
|---|---|---|---|
| Stage 1 (止血) | 1d | 0.5d | 1-2 天 |
| Stage 2 (契约加固) | 2d | 1d | 2-3 天 |
| Stage 3 (AI 风格) | 5d | 2d | 5-7 天 |
| **总计** | **8d** | **3.5d** | **8-12 天** |

---

## 12. Decision Audit Trail

| 决策 | 选项 | 选哪个 | 理由 |
|---|---|---|---|
| 修复方向 | A: 前端 pass-through / B: 后端返 0-1 | A | 符合 CLAUDE.md "前端只展示", 改动最小, 与 v0.4.14.26 一致 |
| 治理节奏 | 3 阶段分 sprint / 一次性 8 天 | 3 阶段 | Stage 1 立即止血, Stage 2 治根, Stage 3 AI 友好 |
| 契约层类型 | Pydantic / Zod / TypeScript branded | Pydantic | 后端权威, 前端靠 OpenAPI schema 派生 |
| 老客 GSV 0.41% 处理 | 改后端 / 改前端 / 文档化 | 不动 | 实际是真实值, 用户视觉对齐误判 |
| 8 处 unit 漏标 | 加 unit='pp' / 改后端字段名 | 加 unit | 字段名已有 _rate/_ratio 语义清晰, caller 漏标 |
| Excel numFmt 错 | 改 numFmt / 改后端返 decimal | 改 numFmt | 改动最小, 与 Sprint 11+ 设计一致 |
| churn.py:336 hardcode 0 | 临时 fix / 完整实现 | 完整实现 | 永远 0% 是 silent data loss, 跟 Stage 1 P3 痛点直接相关 |

---

## 13. Open Questions (等用户拍板)

1. **是否一次性做 Stage 1+2** (止血+契约加固, 4 天) 还是分 Sprint (Sprint 13/14)?
2. **Stage 3 useFormat composable 是 Sprint 15 必须, 还是 Sprint 16+?**
3. **8 处 unit 漏标是否 Stage 1 内一并修, 还是单独工单?**
4. **Stage 2 Pydantic 类型是否要覆盖 `member_join_rate` (0.67 语义怪) 这种异常点?**

---

## 14. Review Reports (autoplan 4 phase)

### Phase 1 — CEO 战略 Review (auto-decided)

| 维度 | 评估 |
|---|---|
| Premise 8 条 | 6 pass / 1 fail (P5 Stripe 模式) / 1 flag (P2 visitor 反向路径盲区) / 1 flag (P8 治根推到下 sprint) |
| Reframing 机会 | 契约层先行 / schema-driven form / v0.4.14.26 重做 |
| 6-month regret | Pydantic v2 已有 `Annotated[float, Field(ge/le)]`,自定义类型过时 / 19 个 PR 摊薄 / OpenAPI→TS 单向 |
| 忽视备选 | ESLint `no-restricted-syntax` 禁 `*100` / `Intl.NumberFormat` / Zod monorepo |
| 行业做法 | Stripe Zod+branded / Linear GraphQL codegen / Vercel `useFormatter` / Anthropic Pydantic v2 简单 / Shopify Polaris branded type |

**Top 3 改动建议**:
1. Stage 2 缩到 Stage 1b 同步 (省 1 sprint)
2. Stage 1 加 ESLint `no-restricted-syntax` 禁 `*100` (半天)
3. 重新评估 v0.4.14.26 方向 B (Pydantic 契约层让后端返 0-1 + 契约层 `*100` 集中,33 处 caller 0 改动)

### Phase 2 — Design UX Review (auto-decided)

**8 维度评分**:
- 信息层级: pp vs % 视觉权重失衡,缺"口径说明"小字
- 缺失状态: 极端值/负值/空数据/跨语种 4 态
- 用户旅程: 数字跳变 4 数量级触发"是不是又改错"二次反应
- 具体性: 颜色/字号/方向/Excel 双列 4 决策没定
- A11y/i18n: ARIA/locale/键盘焦点 3 个无障碍缺口

**Top 3 改动建议**:
1. 加 UI 规范子章节 "pp 显示 5 条规则"
2. CHANGELOG 必加 "ratio 口径统一" 条目 + 4 个页面一次性 banner 3 天
3. Excel 导出改"双列" (数值可计算 + 标签文本)

### Phase 3 — Eng 工程 Review (auto-decided)

**6 维度评分**:
- 架构: Pydantic v2 匹配 / Stage 1 估时 1d 偏紧 30-50% / `calculations.py:49-58` docstring 与实现错位
- 边界用例: 6 个具体场景, 2 个 Plan 漏 (None 透传语义错 / visitor line 86 孪生 bug)
- 测试: 单测 6/10 / E2E 5/10 / 集成 3/10 (缺 3 工单 E2E + Pydantic fuzz)
- 性能/安全: Pydantic validator +30-100ms 分批风险
- 隐藏复杂度: `_extract_metrics` 8 个字段 W6 模糊 / VisitorTrendView caller 漏 / `yoy_repurchase_rate` 字段名误导
- 部署风险: Excel 旧版本兼容 / DuckDB 老数据 vs 新契约 / 6 层防护备份窗口 24h

**Top 3 改动建议**:
1. W6 显式列 8 个 ratio 字段 (`old_gsv_ratio, old_users_ratio, new_gsv_ratio, new_users_ratio, member_penetration, member_users_ratio, member_old_gsv_ratio, member_old_users_ratio, member_new_gsv_ratio, member_new_users_ratio`)
2. `visitor_service.py:86` 孪生 bug (line 70 + 86 一起修)
3. Stage 2 拆 2a/2b, 估时 3-4d 不是 2-3d

### Phase 3.5 — DX 契约层 Review (auto-decided)

**8 维度评分** (总分 4.6/10):
- 上手时间 4/10 / API 一致性 5/10 / 错误信息 3/10 / 文档可发现性 4/10
- Lint 设计 5/10 / 类型分层 5/10 / 升级路径 6/10 / 魔法消失 5/10

**关键阻断性风险**: `docs/reference.md:148` 老规则跟 Plan 反转直接打架,Stage 1 合 main 后新人按老规则写会触发回归

**Top 3 改动建议**:
1. 新增 Sprint 13.5 半天任务: `docs/reference.md` 旧规则 deprecation 表
2. Stage 2 必带 `openapi-typescript` codegen 中间层
3. Stage 3 `useFormat.ts` 内部契约 + Lint 升级 (AST 级别,非 grep)

---

## 15. Decision Audit Trail (autoplan auto-decided)

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Stage 1 方向 A (前端 pass-through) | mechanical | P1+ P5 | 符合 CLAUDE.md "前端只展示", 改动最小, 与 v0.4.14.26 一致 | 方向 B 后端返 0-1 (代价 19 caller) |
| 2 | CEO | Stage 1 1-2d 估时合理 | mechanical | P3 | 工单机械活为主, Pydantic 留 Stage 2 | 一次做 Stage 1+2 (3-4d 偏紧) |
| 3 | CEO | Stage 2 Pydantic 类型 (治根) | mechanical | P1 | 契约层失守是根因, 治本要 Pydantic validator | 自定义类型 (CEO fail P5 反驳) — 改用 `Annotated[float, Field(ge/le)]` |
| 4 | CEO | Stage 3 useFormat + lint (LLM 友好) | mechanical | P1+ P4 | Stripe 模式, 集中 *100 逻辑 | monorepo + Zod 共享 schema (ROI 低) |
| 5 | CEO | 8 处 unit 漏标在 Stage 1 修 | mechanical | P2 | blast radius 内 (< 1d), 跟 33 处 caller 同一类型 bug | 留 Stage 2 (拖到下 sprint) |
| 6 | CEO | 老客 GSV 0.41% 不动 | mechanical | P5 | 实际真实值, 视觉对齐误判, UX 范畴 (非 Eng 治根) | 改成 pp 形式 (语义错) |
| 7 | CEO | Excel 4 处 numFmt 改 `'0.0"pp"'` / `'0.0"%"'` | mechanical | P1 | 跟 Sprint 11+ 设计一致, 改动最小 | 改后端返 decimal (后端契约变更 ROI 低) |
| 8 | CEO | `churn.py:336` 完整实现 `is_new` 派生 | mechanical | P1 | 永远 0% 是 silent data loss, 跟 Stage 1 P3 痛点直接相关 | 临时 fix (跟 永远 0% 同性质 bug) |
| 9 | CEO | `_extract_metrics` 改后端 ratio 存 0-1 | mechanical | P5 | yoy_ratio 内部 *100 一致, 33 处 caller 不变 (前端 pass-through) | 改 caller 自 *100 (前端散落) |
| 10 | CEO | `visitor_service.py` line 70+86 一起改 | mechanical | P2 | 孪生 bug, 一致性 | 只改 line 70 (留 line 86 回归) |
| 11 | Design | 加 UI 规范子章节 "pp 显示 5 条规则" | taste | P5 | 33 处改完避免 5 种风格, 显式规范 | 各 caller 各自决定 (风格分裂) |
| 12 | Design | CHANGELOG 必加 "ratio 口径统一" 条目 | mechanical | P1 | 数字跳变 4 数量级必触发"是不是又改错"二次反应 | 不动 (CHANGELOG 漏条目) |
| 13 | Design | 4 页面一次性 banner 3 天 (UI 提示) | taste | P1 | 化解运营信任修复, 3 天后收起 | 不 banner (运营困惑 1 周) |
| 14 | Design | Excel 改"双列" (数值 + 标签) | taste | P5 | 老板 pivot 保住可计算性, 表格里仍可读 | 单列字符串 (牺牲 pivot) |
| 15 | Design | ARIA 标签 "同比上升 10.40 个百分点" | mechanical | P1 | 屏幕阅读器读 "pp" 多半拼字母不解码 | 不加 (无障碍差) |
| 16 | Eng | W6 显式列 8 个 ratio 字段 (member_penetration 必含) | mechanical | P5 | 模糊话术"去掉 *100" 漏改 member_penetration 类 | 模糊话术 (漏改) |
| 17 | Eng | Stage 2 估时 3-4d 不是 2-3d | mechanical | P3 | 6 contracts × 30+ 字段加 validator + OpenAPI diff 真实估时 | 2-3d (低估 30-50%) |
| 18 | Eng | Stage 2 拆 2a/2b (audience+metrics / category+health+rfm) | mechanical | P3 | 2a 后跑 backend E2E 验证 Pydantic v2 序列化不回归 | 一次性 6 contracts (回归风险) |
| 19 | Eng | None 透传显示 `—` (不显示 0.00pp) | mechanical | P5 | humanizeChange(NaN) 当前返 '0.00pp' 是 wrong default, None 应 '—' | NaN 也走 '—' (语义错) |
| 20 | DX | 新增 Sprint 13.5 半天: `docs/reference.md:148` 旧规则 deprecation 表 | mechanical | P2 | 阻断性风险, Stage 1 合 main 后新人按老规则写会触发回归 | 留 Stage 2 (拖到下 sprint) |
| 21 | DX | Stage 2 必带 `openapi-typescript` codegen | mechanical | P4 | 70 个 ChannelGSVRow 字段手抄 JSDoc 必然 drift, codegen 是治根 | 手工维护 (drift 风险) |
| 22 | DX | useFormat.ts 文件顶部加 "SINGLE SOURCE OF TRUTH FOR *100" 注释 | mechanical | P5 | LLM 看 1 行注释就知道调用规则, 减少误用 | 注释散落 (LLM 看不全) |
| 23 | DX | Lint 规则升级到 AST 级别 (检 `<el-tag>` 内联) | taste | P1 | grep 字符串漏模板字符串/动态拼接, AST 才是治根 | grep 字符串 (覆盖不全) |
| 24 | CEO | 整体 3 阶段拆分 (Sprint 13/14/15) | taste | P3+ P5 | Stage 1 立即止血, Stage 2 治根, Stage 3 AI 友好 — 分 sprint 让 review/qa 集中 | 一次性 8-12 天 (context switch 累) |
| 25 | CEO | 不引入 Zod / tRPC (与现有 FastAPI 架构对齐) | mechanical | P4 | 现有架构稳定, 改 ROI 低 | 引入 Zod (前后端共享 schema, 但要新依赖) |

---

## 16. Cross-Phase Themes (多 phase 同时 flag)

| Theme | Flagged in | 严重度 |
|---|---|---|
| **契约层失守是根因** (Pydantic 无 validator) | CEO P8 / Eng 维度 1 / DX 维度 2 | 高 |
| **`docs/reference.md:148` 旧规则反转风险** | DX 维度 1 (阻断性) | 高 |
| **`calculations.py:49-58` docstring 与实现错位** | Eng 维度 1 / 维度 5 | 中 (二次 bug 风险) |
| **数字跳变 4 数量级触发"是不是又改错"** | Design 维度 3 | 中 (信任冲击) |
| **TypeScript 类型 0 JSDoc 单位注释** | Eng 维度 1 / DX 维度 4 | 中 (LLM 不友好) |
| **`yoy_repurchase_rate` 字段名误导 (rate 暗示 %) 8 处** | Eng 维度 5 (W8 治标) | 中 (AI 误判风险) |
| **Pydantic validator 性能 +30-100ms 风险** | Eng 维度 4 | 低 (可分批) |
| **Lint 规则误伤 (50+ 处 *100)** | DX 维度 5 | 低 (dry-run 验证) |

---

## 17. Implementation Tasks (aggregated across 4 phases)

### P0 必做 (Stage 1 + 阻断性)
- [ ] W1: `MetricCard.vue:17` `display = raw` (CC 5min)
- [ ] W2: `YOYBadge.vue:17` 同上 (CC 5min)
- [ ] W6: `audience_summary._extract_metrics:293-309` 8 个 ratio 字段去 *100 (CC 30min)
- [ ] W7: `visitor_service.py:70,86` (孪生 bug 一起修) (CC 10min)
- [ ] W8: R/M/FIntervalTab + ValueTierTab 8 处加 `unit='pp'` (CC 15min)
- [ ] W13: 两组件 JSDoc 同步 (CC 10min)
- [ ] W14: MetricCard.test.ts + YOYBadge.test.ts 加 6+6 单测 (CC 30min)
- [ ] Sprint 13.5: `docs/reference.md:148` 旧规则 deprecation 表 (CC 2h)
- [ ] CHANGELOG 必加 "ratio 口径统一" 条目 (CC 10min)
- [ ] 4 页面一次性 banner 3 天 (CC 1h, UX 决策)

### P1 应做 (Stage 1 剩余)
- [ ] W3: `SamplingView.vue:170-172` (CC 5min)
- [ ] W4: `RFMSegmentDrilldown.vue:174,194` (CC 5min)
- [ ] W5: `ProductCustomerTab.vue:578-689` (CC 10min)
- [ ] W9: `MarketBasketTab.vue:255-261` (CC 5min)
- [ ] W10: `ProductClassRepurchaseTab.vue:95,107,119,131` Excel numFmt (CC 10min)
- [ ] W11: `HealthOverviewTab.vue:334` Excel numFmt (CC 5min)
- [ ] W12: `churn.py:336` 完整实现 `is_new` (CC 1h, 跨 service)
- [ ] W15: E2E 测试 audience/category/health/rfm 4 spec (CC 1h)
- [ ] UI 规范子章节 "pp 显示 5 条规则" (CC 30min, UX 决策)
- [ ] VisitorTrendView caller 同步改 unit (CC 10min, Eng 漏)
- [ ] None 透传显示 `—` (CC 15min, humanizeChange 改)

### P2 治本 (Stage 2)
- [ ] Stage 2a: audience.py + metrics.py 加 `Annotated[float, Field(ge/le)]` (CC 1.5d)
- [ ] Stage 2a 后: backend E2E 验证 Pydantic v2 序列化不回归 (CC 30min)
- [ ] Stage 2b: category.py + health.py + rfm.py (CC 2d)
- [ ] `openapi-typescript` codegen 中间层 (CC 4h, DX 阻断)
- [ ] `calculations.py:49-58` docstring 与实现对齐 (CC 10min, 二次 bug 防线)

### P3 AI 友好 (Stage 3)
- [ ] W16: `composables/useFormat.ts` 4 函数 (CC 2h)
- [ ] W17: 替换 50+ 处散落 `*100` (CC 3h)
- [ ] W18: TypeScript Branded Types (CC 4h)
- [ ] W19: ESLint `no-mixed-ratio-unit` AST 级别 (CC 4h, dry-run 1 周)
- [ ] W20: CLAUDE.md 加 Ratio Convention 章节 (CC 30min, 位置待定)
- [ ] W21: pre-commit hook 跑 contract test (CC 2h)

### P4 Excel / Trust
- [ ] Excel 改"双列" 决策 (CC 待 PM 拍, 老板 pivot 需求)
- [ ] 4 页面 banner 3 天后收起 (CC 5min, 时间触发)

---

## 18. Total Effort (汇总)

| 阶段 | 任务数 | CC | 人 | 墙钟 |
|---|---|---|---|---|
| Sprint 13 (Stage 1) | 15+5 (含 deprecation) | 1.5d | 0.5d | 1-2 天 |
| Sprint 14 (Stage 2) | 6 + codegen | 3-4d | 1.5d | 3-4 天 |
| Sprint 15 (Stage 3) | 6 | 5d | 2d | 5-7 天 |
| **总计** | 27+ | **9-10.5d** | **4d** | **9-13 天** |

---

## 19. Final Gate ✅ 已拍板 (2026-06-10)

| # | 决策点 | 用户选择 | 落地 |
|---|---|---|---|
| 1 | Sprint 节奏 | **3 阶段分 sprint (推荐)** | Sprint 13 止血 / Sprint 14 契约 / Sprint 15 AI 风格 |
| 2 | Excel 格式 | **改双列 (数值 + 标签) 推荐** | W10/W11 输出两列: 数值列 numFmt 数字 / 标签列文本 '5.0pp' |
| 3 | 信任修复 | **CHANGELOG + 4 页面 banner 3 天 (推荐)** | CHANGELOG 强条目 + 一次性 banner 3 天后自动收起 |
| 4 | Stage 3 范围 | **全做 (useFormat + Branded + Lint) 推荐** | Sprint 15 三件全做, 5-7 天 |

### Sprint 13 启动命令 (按 CLAUDE.md 12 步流程)

```bash
# ① 切 feature branch (用户当前在 main)
git checkout -b fix/sprint13-ratio-governance

# ②-⑤ 写代码 (15 工单 + Sprint 13.5 deprecation + banner)
# P0:
#   W1: MetricCard.vue:17
#   W2: YOYBadge.vue:17
#   W6: audience_summary._extract_metrics:293-309 8 个 ratio 字段
#   W7: visitor_service.py:70,86 (孪生)
#   W8: R/M/FIntervalTab + ValueTierTab 8 处 unit='pp'
#   W13: 两组件 JSDoc
#   W14: MetricCard.test.ts + YOYBadge.test.ts 6+6 单测
#   Sprint 13.5: docs/reference.md:148 deprecation 表
#   CHANGELOG: ratio 口径统一条目
#   Banner: 4 页面一次性 3 天
# P1:
#   W3-W5: SamplingView / RFMSegmentDrilldown / ProductCustomerTab
#   W9: MarketBasketTab
#   W10/W11: Excel 双列 (数值 + 标签)
#   W12: churn.py:336 完整 is_new
#   W15: E2E 4 spec
#   VisitorTrendView caller 同步改 unit (Eng 漏标)
#   None 透传显示 '—'

# ③ 跑 pytest
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q

# ④ /review skill
# ⑤ 修 review 问题
# ⑥ commit
git add <specific files>  # 永远不要 git add -A
git commit -m "fix: ratio 口径统一 — 33 处 100× + 1 处 10000× + 4 处 Excel + 8 处 unit 漏标"

# ⑦ push
git push origin fix/sprint13-ratio-governance

# ⑧ /qa skill
# ⑨ merge
git checkout main
git merge fix/sprint13-ratio-governance --no-ff

# ⑩ push main
git push origin main

# ⑪ pull
git pull origin main --ff-only

# ⑫ 重启 + CHANGELOG
kill $(lsof -ti:8000) 2>/dev/null
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> /tmp/fuqin-crm-backend.log 2>&1 &
# 前端
cd frontend-vue3 && npm run dev
```

### Sprint 14 (Stage 2) 启动条件

Sprint 13 收口后, 跑 1 周验证 33 处 bug 修复 + 8 处 unit 漏标 + Excel 双列 + 4 页面 banner, 然后启动 Sprint 14:
- Stage 2a: audience.py + metrics.py 加 `Annotated[float, Field(ge/le)]` (1.5d)
- Stage 2a 后: backend E2E 验证 Pydantic v2 序列化不回归 (0.5d)
- Stage 2b: category.py + health.py + rfm.py (2d)
- `openapi-typescript` codegen 中间层 (DX 阻断, 0.5d)
- `calculations.py:49-58` docstring 与实现对齐 (二次 bug 防线, 0.5h)

### Sprint 15 (Stage 3) 启动条件

Sprint 14 收口后, Stage 2 契约层稳定, 启动 Sprint 15:
- W16: `composables/useFormat.ts` 4 函数
- W17: 替换 50+ 处散落 `*100`
- W18: TypeScript Branded Types (`type Pp = number & { __brand: 'Pp' }`)
- W19: ESLint `no-mixed-ratio-unit` AST 级别
- W20: CLAUDE.md 加 "## Ratio Convention" 章节
- W21: pre-commit hook 跑 contract test
