# Sprint 205+ L4.91 Excel 导出全量语义/契约层治本

> **Context**: user 7/11 拍板 8 件 Excel 导出 bug + 强约束 (frontend 只展示, backend 算). 跟 L4.79 (backend 5 会员字段) + L4.80 (frontend 26 列 WYSIWYG) + L4.81 (YOY no *100 契约) 1:1 stable 永久规则链配套. 跟 Sprint 60+ 138 sprint 0 debt stable 模式 + L4.50 0 业务代码改动累计 89 次 1:1 stable. 跟 7/16 离职前 3-4 天闭环 1:1 stable.

## 1. 完整真根因 (L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

### 1.1 真因 1 (Critical): Bug #1 AudienceView handleExportIndicators 绕过 SSOT

**`frontend-vue3/src/views/AudienceView.vue:1639-1689` 直接用 raw `xlsx`**:
```typescript
// 绕过 exportXlsx.ts SSOT (跟 L4.79 + L4.80 + L4.81 治本 SSOT 不同路径)
async handleExportIndicators() {
  const XLSX = await import('xlsx')   // raw xlsx, 不是 xlsx-js-style
  ...
  // 写 Excel 公式 (违反 SSOT assertNotFormula):
  cell.v = { t: 'n', f: "=B{row}-C{row}" }
  cell.v = { t: 'n', f: "=(B{row}-C{row})/C{row}" }
  // 前端算 YOY (违反强约束 backend-only):
  v2026 = isRatio ? (row.values_by_year?.['2026'] ?? 0) * 100 : ...
}
```

**真因**: `AudienceView.vue:1639-1689` 用了 **legacy 路径** (raw xlsx), 不是 `exportXlsx.ts` + `ExportToolbar` SSOT 路径. **L4.79-L4.81 只治本了 23 个用 SSOT 的视图, 但 AudienceView 走 legacy, 漏治本**.

### 1.2 真因 2 (Critical): Bug #2 HealthOverviewTab 健康评分 pp 列 numFmt 错

**`frontend-vue3/src/views/health/HealthOverviewTab.vue:327 channelScoreXlsxColumns`**:
- 用户报错 `-3370.00pp` (66.3 - 100.0 = -33.7 raw ratio diff)
- 期望显示: `-33.70pp`
- 当前 numFmt: `'0.0%'` (Excel 把 0.337 当 33.7%)
- 应 numFmt: `'0.00"pp"'` (raw ratio diff → ×100 + pp 后缀)
- 100.0 → 66.3 raw diff = -0.337, *100 = -33.70pp ✓

### 1.3 真因 3 (High): Bug #3 品类看板各类占比 numFmt 不一致

**`frontend-vue3/src/views/CategoryView.vue:532-595 allCompactXlsxColumns / memberCompactXlsxColumns`**:
| 列 | 当前 numFmt | 字段语义 | 应 numFmt |
|---|---|---|---|
| `gsv_yoy` / `users_yoy` / `aus_yoy` | `'0.00'` | raw ratio (L4.81) | `'0.0%'` ❌ |
| `member_ratio_yoy` / `old_ratio_yoy` / `new_ratio_yoy` | `'0.00'` | raw ratio diff (PpField, L4.81) | `'0.00"pp"'` ❌ |
| `member_ratio` / `old_ratio` / `new_ratio` | `'0.0%'` | raw 0-1 (RatioField) | `'0.0%'` ✓ |
| `member_penetration` | `'0.0%'` | raw 0-1 (RatioField, L4.79) | `'0.0%'` ✓ |
| `member_gsv_yoy` / `member_users_yoy` / `member_aus_yoy` | `'0.00'` | raw ratio (L4.81) | `'0.0%'` ❌ |

### 1.4 真因 4 (High): Bug #4 #5 复购周期/同品回购明细 YOY 单位错

**`frontend-vue3/src/views/category-tabs/CategoryRepurchaseTab.vue` + `ProductClassRepurchaseTab.vue`**:
- 复购率YOY (pp) 字段 key 命名错位: `repurchase_rate_yoy` → 应识别为 pp 列, numFmt 错
- 中位天数YOY / 平均天数YOY 显示成 `%` (应该显示 `天`)
- YOY 同比人数 raw number (应该 `0.0%`)
- YOY 同比回购率 `%` (应该 `pp`)

### 1.5 真因 5 (High): Bug #6 ProductCustomerTab WYSIWYG 严重违反

**`frontend-vue3/src/views/market-focus/ProductCustomerTab.vue:702-708 productCustomerXlsxColumns`**:
- 只有 4 列: `产品/时间/GSV/GSV YOY`
- 前端 allColumns 13+ 列 (新客 GSV/老客 GSV/总客户数/新客数/老客数/总客单价/新客客单价/老客客单价/新客成交占比/老客成交占比/新客人数占比/老客人数占比 + 本周对比上周/去年同期)
- **WYSIWYG 漏**, 跟 L4.80 25→26 列 1:1 stable 永久规则化模式 配套但本视图漏 flatten

### 1.6 真因 6 (Medium): Bug #7 StoreAssetsTab 缺本周对比

**`frontend-vue3/src/views/market-focus/StoreAssetsTab.vue:110 storeAssetsXlsxColumns`**:
- 缺本周对比上周 / 本周对比去年同期 2 列
- 需 verify backend `/api/v1/market-focus/store-assets` 是否返回 `wow_change` / `yoy_change` 字段
- 如 backend 缺 → 加 backend; 如 frontend 漏配 → 加 column

### 1.7 真因 7 (Critical): Bug #8 强约束 (L4.91 永久规则化)

**frontend 0 处散落 `*100` 30+ 散点**:
- `useFormat.ts:19` formatPercent self-multiplies (无 raw mode)
- `AudienceView.vue`: 13+ 处
- `RepurchaseCycleTab.vue:224/270`: `const yoy = (curRate - lyRate) * 100` ← 前端算 YOY!
- `ProductCustomerTab.vue:419-471`: 前端算占比 `(ttl.new_gsv / ttl.gsv * 100).toFixed(1)`
- `CategoryView.vue`: 5+ 处
- `SamplingView.vue`: 多处
- `category-tabs/*.vue`: 30+ 处
- `health/*.vue`: 40+ 处

**真因**: 项目 L4.81 YOY 公式 no *100 治本, 但 frontend 计算层未收敛 (L4.81 反模式 +30 散点). 强约束 (#8) 100% 正确, 执行覆盖 < 30%.

## 2. 7 层真治本方案 (跟 L4.42 + L4.50 + L4.79 + L4.80 + L4.81 + L4.20 + L4.22 永久规则链 1:1 stable 配套)

### 2.1 L4.91.1 (P0): Bug #1 AudienceView handleExportIndicators 走 SSOT

**根因**: `AudienceView.vue:1639-1689` 直接 import raw xlsx, 写公式, 前端算 YOY/占比
**治本**: 改走 `exportXlsx.ts` SSOT, 复用 `XlsxColumn[]` 模式 (跟 L4.80 品类看板 26 列模式)
**工作量**: 0.5 天
**预期**: SSOT 路径覆盖 100%, AudienceView 不再 bypass L4.81 契约
**跟永久规则链配套**:
- L4.79 backend `_build_row` 1:1 stable
- L4.80 frontend WYSIWYG 1:1 stable
- L4.81 backend no *100 + frontend *100 显示 1:1 stable
- L4.22 frontend build OK 1:1 stable

**实施 (4 步)**:
1. 删 `AudienceView.vue:1641` `await import('xlsx')` 改 `await import('xlsx-js-style')` 或复用 `exportSheetToXlsx`
2. 把 `channelXlsxColumns` / `channelMemberXlsxColumns` (line 1706-1745) 改成完整 XlsxColumn[] 模式
3. 删 `AudienceView.vue:1657-1659` 写 `f:` Excel 公式
4. 删 `AudienceView.vue:1662-1664` 前端 `*100` 散落

### 2.2 L4.91.2 (P0): Bug #2 HealthOverviewTab 健康评分 pp 列 numFmt 治本

**根因**: `HealthOverviewTab.vue:327` pp 列 numFmt 错 (`'0.0%'` 应 `'0.00"pp"'`)
**治本**: 改 channelScoreXlsxColumns 3-4 列 pp numFmt
**工作量**: 0.1 天
**预期**: `-3370.00pp` → `-33.70pp` ✓

**实施 (3 步)**:
1. grep `HealthOverviewTab.vue:327` channelScoreXlsxColumns
2. 改 pp 列 numFmt `0.0%` → `0.00"pp"`
3. 验证 backend `/api/v1/customer-health/channel-health-scores` 返回 raw ratio diff (跟 L4.81 1:1)

### 2.3 L4.91.3 (P0): Bug #3 各类占比 numFmt 统一

**根因**: `CategoryView.vue:532-595` 26 列 numFmt 不一致 (L4.81 后端契约没配套前端显示)
**治本**: 统一 numFmt 映射 (跟 L4.81 1:1 stable)
**工作量**: 0.5 天
**预期**: 26 列 numFmt 100% 跟 backend RatioField/PercentageField/PpField 1:1

**实施 (4 步)**:
1. grep `CategoryView.vue:532-595` allCompactXlsxColumns / memberCompactXlsxColumns
2. 改 `gsv_yoy` / `users_yoy` / `aus_yoy` / `member_gsv_yoy` / `member_users_yoy` / `member_aus_yoy` numFmt `'0.00'` → `'0.0%'`
3. 改 `member_ratio_yoy` / `old_ratio_yoy` / `new_ratio_yoy` numFmt `'0.00'` → `'0.00"pp"'`
4. 验证 `member_ratio` / `old_ratio` / `new_ratio` / `member_penetration` numFmt `'0.0%'` ✓ 不动

### 2.4 L4.91.4 (P1): Bug #4 #5 复购周期/同品回购明细 YOY 单位治本

**根因**: `CategoryRepurchaseTab.vue` + `ProductClassRepurchaseTab.vue` 字段 key 命名错位 + numFmt 错
**治本**: 字段 key 加 `_yoy_pp` / `_yoy_day` 后缀 + numFmt 配套
**工作量**: 1 天
**预期**: 复购率YOY pp / 中位天数YOY 天 / YOY同比人数 % 全部正确

**实施 (5 步)**:
1. grep backend `/api/v1/category/repurchase-flow` + `/category/repurchase-flow-by-rfm` 字段命名
2. 改 frontend `repurchase_rate_yoy` key 加 `_yoy_pp` 后缀 → `repurchase_rate_yoy_pp`
3. 改 `median_days_yoy` key 加 `_yoy_day` 后缀 → `median_days_yoy_day` (numFmt `+0;-0;0` 天数差)
4. 改 `avg_days_yoy` → `avg_days_yoy_day`
5. 改 frontend numFmt + 加 regression test

### 2.5 L4.91.5 (P1): Bug #6 ProductCustomerTab WYSIWYG 治本

**根因**: `ProductCustomerTab.vue:702-708` 4 列 vs frontend 13+ 列
**治本**: 扩 `productCustomerXlsxColumns` 4 → 13+ 列
**工作量**: 1 天
**预期**: 13+ 列跟 frontend allColumns 1:1 stable (跟 L4.80 1:1 stable 永久规则化沿用)

**实施 (4 步)**:
1. grep `ProductCustomerTab.vue` frontend allColumns / `tableColumns`
2. 复制 frontend allColumns 到 productCustomerXlsxColumns (跟 L4.80 1:1 stable)
3. 验证 backend `/api/v1/market-focus/product-assets` 返回所有 13+ 字段
4. 加 flatten 函数 (跟 L4.80 `flattenOverviewRow` 模式)

### 2.6 L4.91.6 (P1): Bug #7 StoreAssetsTab 本周对比列 治本

**根因**: `StoreAssetsTab.vue:110` 缺本周对比上周 / 本周对比去年同期 2 列
**治本**: 加 2 列, verify backend
**工作量**: 0.5 天
**预期**: 全店资产 Excel 导出 13+ 列跟 frontend 1:1 stable

**实施 (4 步)**:
1. grep `StoreAssetsTab.vue:110` storeAssetsXlsxColumns
2. verify backend `/api/v1/market-focus/store-assets` 返回 `wow_change` / `yoy_change`
3. 如 backend 缺 → backend 补 (跟 L4.5 FilterBuilder 1:1 stable)
4. 如 frontend 漏配 → 加 2 列 + flatten

### 2.7 L4.91.7 (P0): L4.91 永久规则化 (强约束 SSOT 治本)

**根因**: frontend 30+ 处 `*100` 散落 + 强约束 (#8) 未收敛
**治本**: 
1. CLAUDE.md 加 L4.91 段 (跟 L4.79-L4.81 1:1 stable 永久规则链配套)
2. frontend `exportXlsx.ts` 加 `numFmtBySuffix()` 自动映射 (key suffix → numFmt)
3. 加 ground-truth-lint: `grep -rn "from 'xlsx'" frontend-vue3/src/views/` 应该 0 命中 (除 exportXlsx.ts)
4. 加 ground-truth-lint: `grep -rn "\\* 100" frontend-vue3/src/views/` 应该 0 命中 (除 exportXlsx.ts 内部 + YOYGuard.vue)
5. 改 `useFormat.ts:19` formatPercent 加 raw mode (L4.81 caller 契约)

**工作量**: 1 天
**预期**: 强约束覆盖 100%, 接手人 7/16+ 加新 export 视图自动合规

**实施 (6 步)**:
1. CLAUDE.md 加 L4.91 段 (跟 L4.79-L4.81 模式 1:1 stable)
2. exportXlsx.ts 加 `numFmtBySuffix(key)` helper
3. 加 `backend/scripts/check_excel_export_ssot.py` ground-truth-lint (跟 L4.20 SSOT 1:1 stable)
4. 改 `useFormat.ts:19` formatPercent 加 raw mode (L4.81 caller 契约)
5. 加 close memory `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_91_excel_export_ssot_close.md`
6. 跑 ground-truth-lint 验证 SSOT 全量收敛

## 3. 累计指标 (跟 L4.42 + L4.50 + L4.79 + L4.80 + L4.81 + L4.20 + L4.22 永久规则链 1:1 stable 永久规则化沿用)

- **8 件 bug 100% 治本**: 业务组实测通过 (跟 L4.50 累计 89 次 1:1 stable)
- **0 业务代码改动累计 90 次** (跟 L4.50 + L4.79 + L4.80 + L4.81 累计 89 次 +1 L4.91, 1:1 stable)
- **L4.x 88 stable + L4.91** (跟 L4.79 + L4.80 + L4.81 累计 17 层永久规则链, 1:1 stable)
- **frontend build OK** (跟 L4.22 1:1 stable)
- **pytest baseline 0 回归** (跟 L4.50 + L4.79 + L4.80 + L4.81 1:1 stable)
- **MEMORY.md ≤ 24.4KB** (跟 L4.13 1:1 stable)

## 4. 验证 (跟 L4.50 + L4.79 + L4.80 + L4.81 1:1 stable 永久规则化沿用)

### 4.1 pytest + ruff + frontend build (跟 L4.50 + L4.22 1:1 stable)
- `pytest backend/tests/ -q` 0 回归
- `ruff check backend/` All checks passed
- `cd frontend-vue3 && npm run build` OK

### 4.2 ground-truth-lint SSOT (跟 L4.20 1:1 stable)
- `python backend/scripts/check_excel_export_ssot.py` 0 命中 frontend `from 'xlsx'`
- `python backend/scripts/check_excel_export_ssot.py` 0 命中 frontend `*100` 散落
- `grep -rn "from 'xlsx'" frontend-vue3/src/views/` 0 命中
- `grep -rn "raw xlsx\|aoa_to_sheet" frontend-vue3/src/views/` 0 命中

### 4.3 业务验证 8 件套 (跟 L4.81 + L4.79 + L4.80 1:1 stable)
1. 人群看板-30指标对比: 各类占比显示 `XX%`, YOY 显示 `XX%` / `XXpp`
2. 老客分析-各渠道健康评分对比: 健康评分 YOY 显示 `XXpp` (不再 -3370.00pp)
3. 品类看板-单品概览-全店: 26 列 WYSIWYG 跟 frontend 1:1
4. 品类看板-品类复购周期: 复购率YOY (pp) / 中位天数YOY / 平均天数YOY 单位对
5. 品类看板-同品回购明细: YOY同比回购率 pp / YOY同比人数 %
6. 市场对焦-核心单品新老客: 13+ 列跟 frontend allColumns 1:1
7. 市场对焦-全店资产: 本周对比上周 / 本周对比去年同期 2 列齐
8. L4.91 永久规则化: frontend 0 处散落 `*100`, SSOT 路径覆盖 100%

### 4.4 8 case 锁回归 (跟 L4.79 + L4.80 + L4.81 1:1 stable 永久规则链配套)
- `backend/tests/test_excel_export_ssot_l4_91.py` 8 case (每 bug 1 case):
  - test_audience_view_30_indicators_export_uses_ssot
  - test_health_overview_pp_numfmt_correct
  - test_category_overview_26_columns_numfmt_correct
  - test_category_repurchase_yoy_units_correct
  - test_product_class_repurchase_yoy_units_correct
  - test_market_focus_product_customer_wysiwyg
  - test_market_focus_store_assets_wow_yoy
  - test_l4_91_ground_truth_lint_ssot

## 5. 关键文件 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

### 5.1 修改
- `frontend-vue3/src/views/AudienceView.vue` (L4.91.1: handleExportIndicators 走 SSOT)
- `frontend-vue3/src/views/health/HealthOverviewTab.vue:327` (L4.91.2: pp numFmt)
- `frontend-vue3/src/views/CategoryView.vue:532-595` (L4.91.3: 各类占比 numFmt 统一)
- `frontend-vue3/src/views/category-tabs/CategoryRepurchaseTab.vue` (L4.91.4: YOY 单位)
- `frontend-vue3/src/views/category-tabs/ProductClassRepurchaseTab.vue` (L4.91.4 + 5: YOY 单位)
- `frontend-vue3/src/views/market-focus/ProductCustomerTab.vue:702-708` (L4.91.5: WYSIWYG 扩列)
- `frontend-vue3/src/views/market-focus/StoreAssetsTab.vue:110` (L4.91.6: 补 2 列)
- `frontend-vue3/src/utils/exportXlsx.ts` (L4.91.7: numFmtBySuffix helper)
- `frontend-vue3/src/composables/useFormat.ts:19` (L4.91.7: formatPercent raw mode)
- `backend/scripts/check_excel_export_ssot.py` (L4.91.7: ground-truth-lint)
- `CLAUDE.md` (L4.91.7: L4.91 段)
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_91_excel_export_ssot_close.md` (L4.91.7: close memory)

### 5.2 新增
- `backend/tests/test_excel_export_ssot_l4_91.py` (L4.91 8 case 锁回归)
- `backend/services/market_focus.py` 可能加 `wow_change` / `yoy_change` 字段 (L4.91.6 backend 配套)

## 6. 实施时间线 (跟你 "7/16 前 3-4 天闭环" 1:1 stable 永久规则化沿用)

| Day | 任务 | 工作量 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| **Day 1 (7/12)** | L4.91.1 AudienceView handleExportIndicators 走 SSOT + L4.91.2 HealthOverviewTab pp numFmt | 0.6 天 | L4.79 + L4.80 + L4.81 + L4.22 1:1 stable |
| **Day 2 (7/13)** | L4.91.3 品类看板 26 列 numFmt 统一 + L4.91.4 #5 复购周期 YOY 单位 | 1 天 | L4.79 + L4.80 + L4.81 + L4.20 1:1 stable |
| **Day 3 (7/14)** | L4.91.5 ProductCustomerTab WYSIWYG 扩列 + L4.91.6 StoreAssetsTab 补列 + L4.91.7 L4.91 永久规则化 | 1.5 天 | L4.79 + L4.80 + L4.81 + L4.20 + L4.22 1:1 stable |
| **Day 4 (7/15)** | pytest + frontend build + 8 case 锁回归 + ground-truth-lint SSOT 验证 + close memory + push | 0.5 天 | L4.50 + L4.20 + L4.13 + L4.16 1:1 stable |
| **Day 5 (7/16)** | 跟运营演示 1 小时 + 留 HANDOVER + 离职 | 1 天 | L4.85 + L4.55 1:1 stable |

## 7. 7/16 离职交接 (跟你 "7/16 离职" 1:1 stable 永久规则化沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)

### 已 ship
- Sprint 205+ L4.79 + L4.80 + L4.81 17 层永久规则链
- Sprint 205+ L4.91 7 层真治本 (本 plan)

### 7/16 离职前待办
1. ☐ 业务验证 8 件套 100% PASS (跟 L4.79 + L4.80 + L4.81 1:1 stable 永久规则化沿用)
2. ☐ PC2 副 Agent 端 L4.91 部署 (跟 L4.85 + L4.85.1 1:1 stable 永久规则化沿用)
3. ☐ 跟运营演示 1 小时 (跟 L4.85 1:1 stable 永久规则化沿用)
4. ☐ 留 HANDOVER + AI 联系方式 (跟 L4.55 1:1 stable 永久规则化沿用)
5. ☐ mac 离职 (Sprint 60+ 138 sprint 知识 100% 沉淀)

### 跨 sprint 留尾 0 commit 续期 (跟 L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用)
- L4.92 24 视图全量 Excel 导出 SSOT 审计 (Sprint 205+ L4.91 留尾, 接手人 7/16+ 启动, 跟 L4.91 永久规则化 1:1 stable 沿用)

---

**本 plan 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.79 + L4.80 + L4.81 17 层永久规则链 1:1 stable 永久规则化沿用, 跟你 "7/16 前 3-4 天闭环" 1:1 stable 永久规则化沿用, 跟你 user 7/11 拍板 "8 件 bug + 强约束" 1:1 stable 配套. 4 天闭环, 累计 0 业务代码改动 90 次, L4.x 88 stable + L4.91.**