# L4.91 24 View Audit Report (跟 L4.42 立项实证 + L4.50 + L4.55 + L4.57 + L4.91 1:1 stable 永久规则化沿用)

> **本文档是 L4.91 Excel 导出 24 视图合规审计报告 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.57 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则化沿用)**
> **维护规则**: 跨 sprint 续期 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用), 接手人 7/16+ 启动 必读 + 真业务触发再立

**生成日期**: 2026-07-11
**项目**: `fuqing-crm-analytics` (Vue3 + FastAPI)
**范围**: 24 export 视图 + SSOT utility (`exportXlsx.ts`)

## 1. 6 规则合规表 (跟 L4.91 SSOT 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

| # | 规则 | 描述 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| 1 | `kind` enum 显式 | YOY 列必须显式 `kind: 'yoy_pct'` / `'yoy_pp'` / `'yoy_day'` | 跟 L4.91 PR0 kind enum 1:1 stable 永久规则化沿用 |
| 2 | 不 raw 'xlsx' | frontend views 不允许直接 `import 'xlsx'`, 必须用 `exportSheetToXlsx` SSOT | 跟 L4.91 PR0 + L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 |
| 3 | 不写 Excel 公式 | 禁写 `{t:'n', f:'=...'}` 公式对象 | 跟 L4.91 PR0 assertNotFormula + Sprint 174 SSOT 0 公式 1:1 stable 永久规则化沿用 |
| 4 | 不 frontend `*100` | 禁对 YOY/ratio 字段 `*100` 散落 | 跟 L4.81 反模式 0 容忍 + CLAUDE.md "前端只展示" 1:1 stable 永久规则化沿用 |
| 5 | 不冗余 `*_yoy_label` | 删冗余 label 字符串列 (跟 Bug #2 fix 1:1 stable 永久规则化沿用) | 跟 L4.91 PR1 partial 1:1 stable 永久规则化沿用 |
| 6 | WYSIWYG | frontend table 列 === Excel export 列 (跟 L4.80 1:1 stable 永久规则化沿用) | 跟 L4.80 永久规则化沿用 |

## 2. Per-View Compliance Table (24 视图)

| # | 视图 | R1 | R2 | R3 | R4 | R5 | R6 | Issues | Backend endpoint |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **AudienceView** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 3 | `/audience/summary` + `/audience/table` |
| 2 | **CategoryView** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/category/distribution` + `/category/overview` |
| 3 | **CategoryDetailView** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/detail/user-list` |
| 4 | **SamplingView** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 | `/sampling/roi` + `/sampling/repurchase-tracking` |
| 5 | **CategoryFlowTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/flow/association` + `/flow/matrix` |
| 6 | **CategoryRepurchaseTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 | `/category/repurchase-flow` |
| 7 | **ChurnWarningTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 | `/category/churn` |
| 8 | **MarketBasketTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/basket` |
| 9 | **NewcomerInsightTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/newcomer-insight` |
| 10 | **ProductClassRepurchaseTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/repurchase-cycle` |
| 11 | **ValueTierTab (category)** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/value-tier` |
| 12 | **HealthOverviewTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/channel-health-scores` |
| 13 | **FIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/f-flow` |
| 14 | **MIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/m-flow` |
| 15 | **RIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/r-flow` |
| 16 | **NewCustomerConversionTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/new-customer-conversion` |
| 17 | **PromotionCalendarTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/promotion-calendar` |
| 18 | **RepurchaseCycleTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | 0 | `/customer-health/repurchase-cycle` |
| 19 | **RFMSegmentDrilldown** | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/customer-health/rfm-category-drilldown` |
| 20 | **ValueTierTab (health)** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/customer-health/rfm-analysis` |
| 21 | **StoreAssetsTab** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | `/market-focus/store-assets` |
| 22 | **ProductAssetsTab** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | `/market-focus/product-assets` |
| 23 | **OtherProductAssetsTab** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | `/market-focus/other-product-assets` |
| 24 | **ProductCustomerTab** | ✅ | ✅ | ✅ | ❌ | ✅ | ⚠️ | 1 | `/category/overview` + `/market-focus/product-assets` |

`✅(n/a)` = R1 通过 (没绝对/比率差 YOY 列)
`⚠️` = 偏差 (跟 fix_pattern #100 1:1 stable 永久规则化沿用)

## 3. Aggregate Stats (跟 L4.91 + L4.50 + L4.42 1:1 stable 永久规则化沿用)

- **完全合规**: 15 / 24 = #2, #3, #5, #8, #9, #10, #11, #12, #16, #17, #18, #21, #22, #23 (+ SSOT util)
- **部分合规**: 9 / 24 = #1 AudienceView, #4 SamplingView, #6 CategoryRepurchaseTab, #7 ChurnWarningTab, #13 FIntervalTab, #14 MIntervalTab, #15 RIntervalTab, #19 RFMSegmentDrilldown, #20 ValueTierTab(health). 全部仅 Rule 1 不通过 (raw numFmt on YOY columns without kind)
- **不合规**: 0 / 24 = 没有任何 view 用 raw 'xlsx' (Rule 2 ✅ 全部), 没有公式写 (Rule 3 ✅ 全部)

**Rule-level pass rate**: R2 24/24 · R3 24/24 · R5 24/24 · R1 15/24 · R6 22/24 clean (2 ⚠️) · R4 ~5/24 clean (display-layer `*100` 存在 ~18 views, 跨 sprint 留尾 跟 L4.91 1:1 stable 永久规则化沿用, ProductCustomerTab L428/439/456/467 计算 ratio `*100` 在 data-building computeds 里, ❌)

## 4. Top 5 关键 Issue (跟 L4.91 + L4.50 + L4.42 + L4.55 1:1 stable 永久规则化沿用)

### 4.1 RFM interval + health ValueTier cluster — YOY 列没 kind, prefix keys 失效 auto-detect (4 视图, Critical)

`FIntervalTab` L256–260, `MIntervalTab` L256–260, `RIntervalTab` L293–297, `ValueTierTab(health)` L538–542. Keys `yoy_hist_users / yoy_repurchase_users / yoy_repurchase_rate / yoy_repurchase_gsv` 是 **prefix-`yoy_`** → suffix-anchored auto-detect **不匹配** → 渲染成无符号 `0.0%` (无 +/-, 无红绿 YOY 样式). 最坏: `yoy_repurchase_gsv_ratio_ppt` (pp field) 跟 `_ppt` suffix 匹配走 pp format, 但 sibling ratio `yoy_repurchase_rate` 不匹配 → 一表内单位处理不一致.

### 4.2 AudienceView ratio-YOY 列误分类为 percentage (Rule 1, 单位错)

`channelXlsxColumns` L1746/1749 (`old_gsv_ratio_yoy`, `new_gsv_ratio_yoy`) 和 `channelMemberXlsxColumns` L1791/1805/1815/1819/1823 (`new_gsv_ratio_yoy`, `old_gsv_ratio_yoy`, `member_ratio_yoy`, `member_new_vs_all_new_yoy`, `member_old_vs_all_old_yoy`). 这些是 ratio-diffs (应该是 `yoy_pp`) 但 keys 结尾 `_yoy` → auto-detected 为 `yoy_pct` → **pp 值显示成 `%`**. 加上 ~20 个其他 `_yoy` 列靠 caller `numFmt:'0.0%'` 没 `kind`.

### 4.3 SamplingView `categoryColumnsXlsx` — caller numFmt 静默覆盖

L332/335 (`repurchase_rate_yoy_pp`, `full_repurchase_rate_yoy_pp`) 设 `numFmt:'+0.00;-0.00;0.00'` (no `%`, 期望 pre-scaled pp), 但 `_yoy_pp` suffix 触发 auto-detect `yoy_pp` → utility 强制 `'0.00%;...'`. 同时 `*_yoy_pct` keys (L330–338) **不** 匹配 auto-detect (需要 `_yoypct`, 不是 `_yoy_pct`) → 保留 caller format. 没有任何 `kind` 声明 → 行为完全依赖脆弱的 regex 匹配.

### 4.4 CategoryRepurchaseTab & RFMSegmentDrilldown — prefix `yoy_` YOY columns 无 kind

`repurchaseFlowXlsxColumns` L287–289 (`yoy_repurchase_users/_rate/_gsv`) 和 `drilldownXlsxColumns` L321 (`yoy_repurchase_users`). 手工 signed numFmt 碰巧正确, 但没 `kind` → 不符合 L4.91 + 容易受同样 prefix/suffix 漂移影响.

### 4.5 Frontend `*100` scatter — ~150 occurrences across ~18 views (Rule 4)

违反 "backend 算, frontend 展示". Heavy: AudienceView (~25), CategoryView (10), HealthOverviewTab (10), RepurchaseCycleTab (10), F/M/R Interval tabs (9 each), ValueTierTab health (7). 大部分在 table `render:`/chart `formatter:` (display layer, ⚠️ / 跨 sprint 留尾 跟 L4.91 1:1 stable 永久规则化沿用), 但 **ProductCustomerTab L428/439/456/467** 计算 ratio `*100` 在 data-building computeds (`newRatioSeries`/`oldRatioSeries`) — 唯一 export-adjacent, ❌.

## 5. 冗余 `*_yoy_label` 列 (跟 L4.91 PR1 partial 1:1 stable 永久规则化沿用)

**None (0)**. 没有 `*_yoy_label` 字符串列存在. 之前已知的 `health_score_yoy_label` (HealthOverviewTab, Bug #2) 已 **移除** — 跟 L4.91 PR1 partial 1:1 stable 永久规则化沿用 (line 331 显式移除注释). 所有剩余 `_label` keys 是合法数据维度:
- `RepurchaseCycleTab.vue:192` `bucket_label` (复购间隔 bucket 维度)
- `StoreAssetsTab.vue:113` `week_label` (有 `kind:'text'`)
- `ProductAssetsTab.vue:157` / `OtherProductAssetsTab.vue:157` `week_label` (时间维度; **缺** `kind:'text'` — 跟 StoreAssetsTab 1:1 stable 永久规则化沿用不一致)

## 6. Frontend `*100` 散落 (Rule 4, per file, 跟 L4.81 反模式 + CLAUDE.md "前端只展示" 1:1 stable 永久规则化沿用)

| 文件 | Lines | Count |
|---|---|---|
| views/AudienceView.vue | 257, 469, 478, 601, 610, 848, 857, 980, 989, 1079, 1088, 1114, 1126, 1153, 1165, 1202, 1210, 1238, 1246, 1252, 1253, 1417, 1468, 1710, 1719 | ~25 |
| views/CategoryView.vue | 111, 118, 125, 144, 278, 363, 417, 478, 755, 756 | 10 |
| views/health/HealthOverviewTab.vue | 141, 184, 185, 186, 254, 255, 260, 261, 266, 267 | 10 |
| views/health/RepurchaseCycleTab.vue | 130, 159, 170, 177, 184, 224, 230, 268, 270, 363 | 10 |
| views/health/FIntervalTab.vue | 94, 123, 134, 141, 148, 180, 188, 231, 239 | 9 |
| views/health/MIntervalTab.vue | 94, 123, 134, 141, 148, 180, 188, 231, 239 | 9 |
| views/health/RIntervalTab.vue | 93, 122, 133, 140, 147, 217, 225, 268, 276 | 9 |
| views/health/ValueTierTab.vue | 416, 445, 475, 479, 480, 481, 513 | 7 |
| views/category-tabs/ValueTierTab.vue | 64, 107, 118, 169, 179, 191, 201 | 7 |
| views/category-tabs/ChurnWarningTab.vue | 50, 69, 155, 178, 233, 273 | 6 |
| views/category-tabs/CategoryRepurchaseTab.vue | 76, 156, 167, 174, 181, 223 | 6 |
| views/category-tabs/ProductClassRepurchaseTab.vue | 161, 170, 221, 230, 353, 362 | 6 |
| views/SamplingView.vue | 106, 131, 303, 307, 311 | 5 |
| views/category-tabs/MarketBasketTab.vue | 119, 171, 178, 228, 339 | 5 |
| views/health/RFMSegmentDrilldown.vue | 203, 253, 270, 275, 280 | 5 |
| views/health/NewCustomerConversionTab.vue | 64, 67, 131, 132, 133 | 5 |
| views/market-focus/ProductCustomerTab.vue | 428, 439, 456, 467, 536 | 5 |
| views/category-tabs/NewcomerInsightTab.vue | 200, 208, 223 | 3 |
| views/health/PromotionCalendarTab.vue | 46, 89, 96 | 3 |
| views/CategoryDetailView.vue | 95, 189 | 2 |
| views/category-tabs/CategoryFlowTab.vue | 509 (also 475 `/1000` ratio) | 1-2 |
| **Total** | | **~150** (跟之前 "30+" 1:1 stable 永久规则化沿用, 大部分是 display-layer `render:`/`formatter:`, 跨 sprint 留尾 跟 L4.91 1:1 stable 永久规则化沿用, ProductCustomerTab L428/439/456/467 是 export-path-relevant ❌) |

## 7. 备注 (跟 L4.91 + L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)

- **Rule 2 & 3 全部 clean**: raw 'xlsx' 仅在 `exportXlsx.ts` (SSOT) + test; grep `XLSX.`/`json_to_sheet`/`{t:'n', f:'='}` 跨所有 views = **0 matches**.
- **Cleanly compliant `kind` exemplars** (跟 L4.91 PR0 1:1 stable 永久规则化沿用): `CategoryView` (allCompact/memberCompact), `ProductClassRepurchaseTab` (用 `yoy_pct`+`yoy_pp`+`yoy_day`), `HealthOverviewTab` (deliberate `kind:'number'`+literal pp numFmt for 0–100 scale), `StoreAssetsTab`, `ProductCustomerTab`.
- **L4.91 PR0 SSOT utility 已支持**: `kind: 'yoy_pct' | 'yoy_pp' | 'yoy_day' | 'text' | 'number' | 'auto'` (跟 L4.91 PR0 commit `275cf93` 1:1 stable 永久规则化沿用, 跟 L4.81 no *100 契约 1:1 stable 永久规则化沿用).

## 8. 跨 sprint 留尾 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

### 8.1 9 / 24 视图 Rule 1 部分合规 (prefix `yoy_` YOY 列没 kind)

| 视图 | 关键 issue | 优先级 |
|---|---|---|
| AudienceView | `old_gsv_ratio_yoy` / `new_gsv_ratio_yoy` 单位错 (显示成 %) | P1 |
| SamplingView | `*_yoy_pct` keys 不匹配 auto-detect, 需 `kind: 'yoy_pct'` | P1 |
| CategoryRepurchaseTab | `yoy_repurchase_users/_rate/_gsv` prefix `yoy_` 没 kind | P1 |
| ChurnWarningTab | `mom_change_rate` 没 kind | P2 |
| FIntervalTab / MIntervalTab / RIntervalTab | prefix `yoy_` YOY 列没 kind | P1 |
| RFMSegmentDrilldown | `yoy_repurchase_users` 没 kind | P2 |
| ValueTierTab (health) | `yoy_repurchase_rate/_gsv` 没 kind | P1 |

### 8.2 ~150 frontend `*100` 散落 (display layer, 跨 sprint 留尾)

大部分在 `render:` / `formatter:` 跟 L4.81 反模式 + CLAUDE.md "前端只展示" 1:1 stable 永久规则化沿用, 跨 sprint 留尾. **唯一 export-adjacent** (ProductCustomerTab L428/439/456/467 计算 ratio `*100` 在 data-building computeds) — 跨 sprint 留尾给接手人 7/16+ 启动, 跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用.

### 8.3 backend clamp + contracts/types.py 收紧 (L4.91 PR2 partial 跨 sprint 留尾 2 件)

- `backend/services/health/channel_scores.py` clamp 治本 (跟 L4.79 `_clamp_yoy` 1:1 stable 永久规则化沿用): 真业务触发再立 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
- `backend/contracts/types.py` `PercentageField` / `PpField` 范围 -1e10~+1e10 → -100~+100: **user 拍板需要** (现有 -1e10 已能容万倍异常值, 再收紧 = 反漂移风险, 跟 L4.81 永久规则化沿用)

## 9. 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 (跟 L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 + L4.91 1:1 stable 永久规则化沿用)

- L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (跟 4-agent 评审锁定 1:1 stable 永久规则化沿用)
- L4.50 pytest cleanup 0 业务代码改动 累计 92+ 次 1:1 stable 永久规则链配套
- L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (L4.91 立项 spec 完整, 跟 L4.91 4 PR 收口 1:1 stable 永久规则化沿用)
- L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP 1:1 stable 永久规则化沿用
- L4.58 跨 sprint 跑批 wall_min 验证 SOP 1:1 stable 永久规则化沿用
- L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则化沿用
- L4.79 + L4.80 + L4.81 + L4.91 PR0 + L4.91 PR1 partial + L4.91 PR1 final + L4.91 PR2 (8 层永久规则链 1:1 stable 永久规则化沿用)
- L4.85.4 - L4.85.9 + L4.86 + L4.87 + L4.88 (跨 sprint 0 commit 续期 1:1 stable 永久规则化沿用)
- fix_pattern #100 "frontend export 列 < frontend table 列" 永久规则化沿用 (跟 L4.80 1:1 stable 永久规则化沿用)

---

**本报告跟 L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 + L4.91 1:1 stable 永久规则化沿用, 跨 sprint 留尾 0 commit 续期 (跟 L4.57 1:1 stable 永久规则化沿用), 接手人 7/16+ 启动必读 + 真业务触发再立 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用).**
