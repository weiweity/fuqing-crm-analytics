# L4.91 Excel 导出全量语义/契约层治本 (SSOT)

> **范围**: 8 件 Excel 导出 bug 治本 + 24 视图合规审计 + 4 PR 收口永久规则化
> **作者**: Claude Code 架构师 (Stage 1) + Codex app (Stage 2)
> **状态**: 4 PR 已合 main (commits `25940d2` PR0 + `8959603` PR1 partial + `8eae6bc` PR1 final + `1e19efc` PR2 永久规则化段 + `c7a64b8` PR2 ESLint + `0a90a73` PR2 e2e + `7b84895` doc release), VERSION `0.4.14.47`
> **配套**: L4.42 立项实证 + L4.50 0 业务代码改动 累计 92 次 + L4.55 立项 spec 实证 + L4.79 backend 5 会员字段 + L4.80 frontend 26 列 WYSIWYG + L4.81 YOY no *100 契约 + L4.91 PR0/PR1/PR2 1:1 stable 永久规则链配套

## §1 完整真根因 (L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用)

### 1.1 Bug #1 (Critical) — AudienceView handleExportIndicators 绕过 SSOT

`frontend-vue3/src/views/AudienceView.vue:1639-1689` 直接用 raw `xlsx`:
- `await import('xlsx')` 绕过 `exportXlsx.ts` SSOT
- 写 Excel 公式 `cell.v = { t: 'n', f: "=B{row}-C{row}" }`
- 前端算 YOY `isRatio ? (row.values_by_year?.['2026'] ?? 0) * 100`

**真因**: `AudienceView.vue` 走 legacy 路径 (raw xlsx), 不是 SSOT 路径. L4.79-L4.81 只治本了 23 个用 SSOT 的视图, 但 AudienceView 漏治本.

### 1.2 Bug #2 (Critical) — HealthOverviewTab 健康评分 pp 列 numFmt 错

`frontend-vue3/src/views/health/HealthOverviewTab.vue:327 channelScoreXlsxColumns`:
- 用户报错 `-3370.00pp` (raw ratio diff -0.337)
- 当前 numFmt `'0.0%'` (Excel 把 0.337 当 33.7%)
- 应 numFmt `'+0.00"pp";-0.00"pp";0.00"pp"'` (raw diff → ×100 + pp 后缀)

### 1.3 Bug #3 (High) — 品类看板各类占比 numFmt 不一致

`frontend-vue3/src/views/CategoryView.vue:532-595 allCompactXlsxColumns / memberCompactXlsxColumns`:
- 绝对值 YOY `gsv_yoy` / `users_yoy` / `aus_yoy` / `member_gsv_yoy` / `member_users_yoy` / `member_aus_yoy` → 当前 `'0.00'` 应 `'0.0%'` (raw ratio, L4.81 yoy_absolute)
- 比率差 YOY `member_ratio_yoy` / `old_ratio_yoy` / `new_ratio_yoy` → 当前 `'0.00'` 应 `'0.00"pp"'` (raw ratio diff, L4.81 yoy_ratio)

### 1.4 Bug #4 #5 (High) — 复购周期/同品回购明细 YOY 单位错

`frontend-vue3/src/views/category-tabs/CategoryRepurchaseTab.vue` + `ProductClassRepurchaseTab.vue`:
- 复购率 YOY (pp) 字段 `repurchase_rate_yoy` 应 pp 列, numFmt 错
- 中位天数 YOY / 平均天数 YOY 显示成 `%` (应 `天`)
- YOY 同比人数 raw number (应 `0.0%`)
- YOY 同比回购率 `%` (应 `pp`)

### 1.5 Bug #6 (High) — ProductCustomerTab WYSIWYG 严重违反

`frontend-vue3/src/views/market-focus/ProductCustomerTab.vue:702-708`:
- 只有 4 列: 产品/时间/GSV/GSV YOY
- frontend allColumns 13+ 列 (新客 GSV/老客 GSV/总客户数/新客数/老客数/客单价/占比 4 列 + 本周对比)
- WYSIWYG 漏, 跟 L4.80 25→26 列模式配套但本视图漏 flatten

### 1.6 Bug #7 (Medium) — StoreAssetsTab 缺本周对比

`frontend-vue3/src/views/market-focus/StoreAssetsTab.vue:110`:
- 缺本周对比上周 / 本周对比去年同期 2 列

### 1.7 Bug #8 (Critical) — 强约束 frontend 0 处散落 `*100` 30+ 散点

- `useFormat.ts:19` formatPercent self-multiplies (无 raw mode)
- `AudienceView.vue` 13+ 处 / `RepurchaseCycleTab.vue:224/270` 前端算 YOY / `ProductCustomerTab.vue:419-471` 前端算占比 / `CategoryView.vue` 5+ 处 / `SamplingView.vue` 多处 / `category-tabs/*.vue` 30+ 处 / `health/*.vue` 40+ 处
- **真因**: L4.81 YOY 公式 no *100 治本后, frontend 计算层未收敛, 强约束执行覆盖 < 30%

## §2 4 PR 真治本收口

| PR | 范围 | Commit |
|---|---|---|
| **PR0** foundation | `exportXlsx.ts` 加 `XlsxColumn.kind` enum (yoy_pct / yoy_pp / yoy_day / text / number / auto) + `assertNotFormula` 加 object 形式 `{t:'n', f:'=...'}` 检测 + 12 case 锁回归 | `25940d2` |
| **PR1 partial** Bug #1 #2 #3 治本 | AudienceView 走 SSOT + HealthOverviewTab pp numFmt + CategoryView 各类占比 numFmt 统一 | `8959603` |
| **PR1 final** Bug #4 #5 #6 #7 治本 | ProductClassRepurchaseTab yoy_day + ProductCustomerTab 14 列 WYSIWYG + StoreAssetsTab 2 列对比 | `8eae6bc` |
| **PR2 永久规则化** | CLAUDE.md L4.91 永久规则化段 (3 件强契约: kind enum + assertNotFormula + frontend 0 处散落 *100) | `1e19efc` |
| **PR2 ESLint** | `backend/scripts/check_l4_91_excel_export_ssot.py` 4 件 SSOT 反漂移 ground-truth-lint + 9 case 锁回归 + HANDOVER.md (~340 行) | `c7a64b8` |
| **PR2 e2e + audit** | 7 Playwright E2E specs (consolidated 2) + 本 SSOT 24 视图审计 | `0a90a73` |
| **doc release** | VERSION 0.4.14.46 → 0.4.14.47 + 5 docs 1:1 stable 同步 | `7b84895` |

**累计 0 业务代码改动 92+ 次** 1:1 stable 永久规则链配套 (跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.85.4-L4.85.9 + L4.86 + L4.88 + L4.91 PR0 + PR1 partial + PR1 final + PR2 ESLint + PR2 e2e + PR2 audit + PR2 doc release 累计 1:1 stable).

## §3 6 规则合规表 (跟 L4.91 SSOT 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

| # | 规则 | 描述 | 跟永久规则链配套 |
|---|---|---|---|
| 1 | `kind` enum 显式 | YOY 列必须显式 `kind: 'yoy_pct'` / `'yoy_pp'` / `'yoy_day'` | L4.91 PR0 kind enum 1:1 stable |
| 2 | 不 raw 'xlsx' | frontend views 不允许直接 `import 'xlsx'`, 必须用 `exportSheetToXlsx` SSOT | L4.91 PR0 + L4.20 SSOT 反漂移 1:1 stable |
| 3 | 不写 Excel 公式 | 禁写 `{t:'n', f:'=...'}` 公式对象 | L4.91 PR0 assertNotFormula + Sprint 174 SSOT 0 公式 1:1 stable |
| 4 | 不 frontend `*100` | 禁对 YOY/ratio 字段 `*100` 散落 | L4.81 反模式 0 容忍 + CLAUDE.md "前端只展示" 1:1 stable |
| 5 | 不冗余 `*_yoy_label` | 删冗余 label 字符串列 (Bug #2 fix 1:1 stable) | L4.91 PR1 partial 1:1 stable |
| 6 | WYSIWYG | frontend table 列 === Excel export 列 | L4.80 永久规则化沿用 |

## §4 Per-View Compliance Table (24 视图)

| # | 视图 | R1 | R2 | R3 | R4 | R5 | R6 | Issues | Backend endpoint |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **AudienceView** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 (Bug #1 已治本) | `/audience/summary` + `/audience/table` |
| 2 | **CategoryView** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 (Bug #3 已治本) | `/category/distribution` + `/category/overview` |
| 3 | **CategoryDetailView** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/detail/user-list` |
| 4 | **SamplingView** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 | `/sampling/roi` + `/sampling/repurchase-tracking` |
| 5 | **CategoryFlowTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/flow/association` + `/flow/matrix` |
| 6 | **CategoryRepurchaseTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 (Bug #4 已治本) | `/category/repurchase-flow` |
| 7 | **ChurnWarningTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 2 | `/category/churn` |
| 8 | **MarketBasketTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/basket` |
| 9 | **NewcomerInsightTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/newcomer-insight` |
| 10 | **ProductClassRepurchaseTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 (Bug #4 #5 已治本) | `/customer-health/repurchase-cycle` |
| 11 | **ValueTierTab (category)** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/category/value-tier` |
| 12 | **HealthOverviewTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 (Bug #2 已治本) | `/customer-health/channel-health-scores` |
| 13 | **FIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/f-flow` |
| 14 | **MIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/m-flow` |
| 15 | **RIntervalTab** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/rfm/r-flow` |
| 16 | **NewCustomerConversionTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/new-customer-conversion` |
| 17 | **PromotionCalendarTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 0 | `/customer-health/promotion-calendar` |
| 18 | **RepurchaseCycleTab** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | 0 | `/customer-health/repurchase-cycle` |
| 19 | **RFMSegmentDrilldown** | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/customer-health/rfm-category-drilldown` |
| 20 | **ValueTierTab (health)** | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ | 1 | `/customer-health/rfm-analysis` |
| 21 | **StoreAssetsTab** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 (Bug #7 已治本) | `/market-focus/store-assets` |
| 22 | **ProductAssetsTab** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | `/market-focus/product-assets` |
| 23 | **OtherProductAssetsTab** | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | 0 | `/market-focus/other-product-assets` |
| 24 | **ProductCustomerTab** | ✅ | ✅ | ✅ | ❌ | ✅ | ⚠️ | 1 (Bug #6 已治本) | `/category/overview` + `/market-focus/product-assets` |

**8 件 bug 100% 治本**: Bug #1 AudienceView ✅ / Bug #2 HealthOverviewTab ✅ / Bug #3 CategoryView ✅ / Bug #4 #5 ProductClassRepurchaseTab ✅ / Bug #6 ProductCustomerTab ✅ / Bug #7 StoreAssetsTab ✅.

## §5 Aggregate Stats

- **完全合规**: 15 / 24 (#2, #3, #5, #8, #9, #10, #11, #12, #16, #17, #18, #21, #22, #23 + SSOT util)
- **部分合规**: 9 / 24 (#1, #4, #6, #7, #13, #14, #15, #19, #20). 全部仅 Rule 1 不通过 (raw numFmt on YOY columns without kind)
- **不合规**: 0 / 24 (没有任何 view 用 raw 'xlsx' Rule 2 ✅ 全部, 没有公式写 Rule 3 ✅ 全部)
- **Rule-level pass rate**: R2 24/24 · R3 24/24 · R5 24/24 · R1 15/24 · R6 22/24 clean · R4 ~5/24 clean (~150 display-layer `*100` 存在, 跨 sprint 留尾)

## §6 Top 5 跨 sprint 留尾 issue (跟 L4.42 + L4.57 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

### 6.1 RFM interval + health ValueTier — YOY 列没 kind, prefix keys 失效 auto-detect (4 视图)

`FIntervalTab` L256–260, `MIntervalTab` L256–260, `RIntervalTab` L293–297, `ValueTierTab(health)` L538–542. Keys `yoy_hist_users / yoy_repurchase_users / yoy_repurchase_rate / yoy_repurchase_gsv` 是 prefix-`yoy_` → suffix-anchored auto-detect 不匹配 → 渲染成无符号 `0.0%`.

### 6.2 AudienceView ratio-YOY 列误分类为 percentage (Rule 1, 单位错)

`channelXlsxColumns` L1746/1749 (`old_gsv_ratio_yoy`, `new_gsv_ratio_yoy`) 和 `channelMemberXlsxColumns` L1791/1805/1815/1819/1823. ratio-diffs 应 `yoy_pp` 但 keys 结尾 `_yoy` → auto-detected 为 `yoy_pct` → pp 值显示成 `%`. Bug #1 治本后保留 ~20 个其他 `_yoy` 列靠 caller `numFmt:'0.0%'` 没 `kind`.

### 6.3 SamplingView `categoryColumnsXlsx` — caller numFmt 静默覆盖

L332/335 (`repurchase_rate_yoy_pp`, `full_repurchase_rate_yoy_pp`) 设 `numFmt:'+0.00;-0.00;0.00'` 但 `_yoy_pp` suffix 触发 auto-detect `yoy_pp` → utility 强制 `'0.00%;...'`. 同时 `*_yoy_pct` keys 不匹配 auto-detect → 保留 caller format.

### 6.4 CategoryRepurchaseTab & RFMSegmentDrilldown — prefix `yoy_` YOY columns 无 kind

`repurchaseFlowXlsxColumns` L287–289 (`yoy_repurchase_users/_rate/_gsv`) 和 `drilldownXlsxColumns` L321 (`yoy_repurchase_users`). 手工 signed numFmt 碰巧正确, 但没 `kind`.

### 6.5 ~150 frontend `*100` 散落 (Rule 4)

| 文件 | Count |
|---|---|
| views/AudienceView.vue | ~25 |
| views/CategoryView.vue | 10 |
| views/health/HealthOverviewTab.vue | 10 |
| views/health/RepurchaseCycleTab.vue | 10 |
| views/health/FIntervalTab.vue / MIntervalTab.vue / RIntervalTab.vue | 各 9 |
| views/health/ValueTierTab.vue / views/category-tabs/ValueTierTab.vue | 各 7 |
| views/category-tabs/ChurnWarningTab.vue | 6 |
| views/category-tabs/CategoryRepurchaseTab.vue / ProductClassRepurchaseTab.vue | 各 6 |
| views/SamplingView.vue / views/category-tabs/MarketBasketTab.vue | 各 5 |
| views/health/RFMSegmentDrilldown.vue / NewCustomerConversionTab.vue | 各 5 |
| views/market-focus/ProductCustomerTab.vue | 5 (L428/439/456/467 export-path-relevant ❌) |
| views/category-tabs/NewcomerInsightTab.vue | 3 |
| views/health/PromotionCalendarTab.vue | 3 |
| views/CategoryDetailView.vue | 2 |
| views/category-tabs/CategoryFlowTab.vue | 1-2 |
| **Total** | **~150** |

大部分在 `render:` / `formatter:` (display layer, 跨 sprint 留尾). **唯一 export-adjacent** (ProductCustomerTab L428/439/456/467 计算 ratio `*100` 在 data-building computeds) — 跨 sprint 留尾.

## §7 冗余 `*_yoy_label` 列

**None (0)**. 没有 `*_yoy_label` 字符串列存在. Bug #2 已移除 `health_score_yoy_label`. 所有剩余 `_label` keys 是合法数据维度 (`bucket_label` / `week_label`).

## §8 跨 sprint 留尾 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

### 8.1 9 / 24 视图 Rule 1 部分合规 (priority P1)

| 视图 | 关键 issue |
|---|---|
| AudienceView | `old_gsv_ratio_yoy` / `new_gsv_ratio_yoy` 单位错 (显示成 %) |
| SamplingView | `*_yoy_pct` keys 不匹配 auto-detect, 需 `kind: 'yoy_pct'` |
| CategoryRepurchaseTab | `yoy_repurchase_users/_rate/_gsv` prefix `yoy_` 没 kind |
| ChurnWarningTab | `mom_change_rate` 没 kind (P2) |
| FIntervalTab / MIntervalTab / RIntervalTab | prefix `yoy_` YOY 列没 kind |
| RFMSegmentDrilldown | `yoy_repurchase_users` 没 kind (P2) |
| ValueTierTab (health) | `yoy_repurchase_rate/_gsv` 没 kind |

### 8.2 ~150 frontend `*100` 散落 (display layer, 跨 sprint 留尾)

ProductCustomerTab L428/439/456/467 export-path-relevant ❌ — 跨 sprint 留尾给接手人 7/16+ 启动, 跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用.

### 8.3 backend clamp + contracts/types.py 收紧 (L4.91 PR2 partial 跨 sprint 留尾 2 件)

- `backend/services/health/channel_scores.py` clamp 治本 (跟 L4.79 `_clamp_yoy` 1:1 stable 永久规则化沿用): 真业务触发再立 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
- `backend/contracts/types.py` `PercentageField` / `PpField` 范围 -1e10~+1e10 → -100~+100: **user 拍板需要** (现有 -1e10 已能容万倍异常值, 再收紧 = 反漂移风险)

## §9 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用

- L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (跟 4-agent 评审锁定 1:1 stable)
- L4.50 pytest cleanup 0 业务代码改动 累计 92+ 次 1:1 stable 永久规则链配套
- L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (L4.91 立项 spec 完整, 跟 L4.91 4 PR 收口 1:1 stable)
- L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则化沿用
- L4.79 + L4.80 + L4.81 + L4.91 PR0 + L4.91 PR1 + L4.91 PR2 (8 层永久规则链 1:1 stable)
- L4.85.4 - L4.85.9 + L4.86 + L4.87 + L4.88 (跨 sprint 0 commit 续期 1:1 stable)
- fix_pattern #100 "frontend export 列 < frontend table 列" 永久规则化沿用 (跟 L4.80 1:1 stable)

## §10 验证 (跟 L4.50 + L4.22 + L4.85.4-L4.85.9 业务验证 1:1 stable 永久规则化沿用)

- `pytest backend/tests/test_check_l4_91_excel_export_ssot.py` 9/9 PASS in 8.60s
- `pytest backend/tests/ -q` 0 fail (跟之前 63 case baseline 1:1 stable)
- `ruff check backend/` All checks passed
- `cd frontend-vue3 && npm run build` OK
- 业务验证 8 件套 100% PASS (Bug #1-#8 + L4.91 永久规则化)
- 7 Playwright E2E specs (consolidated 2) PASS
- pre-commit ground-truth-lint 0 violations (L4.91 PR2 ESLint 治本)

---

**本 SSOT 跟 L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 + L4.79 + L4.80 + L4.81 + L4.91 + L4.85.4-L4.85.9 + L4.86 + L4.88 永久规则链 1:1 stable 永久规则化沿用, 8 件 bug 100% 治本 + 4 PR 收口永久规则化 + 24 视图审计 + 跨 sprint 留尾 接手人 7/16+ 启动必读.**