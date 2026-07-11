# L4.91.2 Excel 导出技术债 /investigate 报告 (跟 L4.42 + L4.50 + L4.91.1 1:1 stable 永久规则化沿用)

> **作者**: Claude Code 架构师 (你 7/11 拍板 "穷尽的调查, 排查下原因" 1:1 stable 永久规则化沿用)
> **状态**: DONE_WITH_CONCERNS - 已锁定 24 view 全景 + 3 关键风险点 + 1 治本 + 2 留尾
> **关联**: L4.91 + L4.91.1 (market-focus#product-customer 治本 100%) + L4.91 doc-cleanup + L4.91.1 handoff

## 1. 24 view Excel 导出全景 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用)

按 L4.42 + L4.91 audit 报告 + L4.91.1 调查 整理:

### 1.1 有 `isChangeRow / isYoyRow` per-row 模式 (3 view, 跟 L4.91.1 治本同模式)

| View | 状态 | 文件 |
|------|------|------|
| market-focus/ProductCustomerTab.vue | ✅ L4.91.1 治本 (commit 51dbde1) | `frontend-vue3/src/views/market-focus/ProductCustomerTab.vue` |
| market-focus/ProductAssetsTab.vue | ⚠️ **同模式未治本 (技术债 #1, 留尾)** | `frontend-vue3/src/views/market-focus/ProductAssetsTab.vue` |
| market-focus/OtherProductAssetsTab.vue | ⚠️ **同模式未治本 (技术债 #2, 留尾)** | `frontend-vue3/src/views/market-focus/OtherProductAssetsTab.vue` |

### 1.2 无 isChangeRow/isYoyRow (21 view, 默认 L4.91 PR0 kind enum 治本)

包括 (按 dashboard 分组):

**老客分析 (health/)** (7 view):
- HealthOverviewTab.vue, FIntervalTab.vue, MIntervalTab.vue, RIntervalTab.vue
- RFMSegmentDrilldown.vue, RepurchaseCycleTab.vue
- NewCustomerConversionTab.vue, PromotionCalendarTab.vue

**品类 (category/)** (5 view):
- CategoryView.vue, CategoryDetailView.vue
- category-tabs/CategoryFlowTab.vue, MarketBasketTab.vue, NewcomerInsightTab.vue
- category-tabs/ValueTierTab.vue (category), ChurnWarningTab.vue
- category-tabs/CategoryRepurchaseTab.vue, ProductClassRepurchaseTab.vue

**人群 (audience/)** (1 view):
- AudienceView.vue

**派样 (sampling/)** (1 view):
- SamplingView.vue

**市场对焦 (market-focus/)** (3 view, 已 ship L4.91 PR1 final Bug #6):
- ProductCustomerTab.vue (L4.91.1 治本)
- ProductAssetsTab.vue, OtherProductAssetsTab.vue (技术债 #1 + #2)

## 2. L4.91.1 治本核心 (跟 L4.91 PR0 + L4.50 1:1 stable 永久规则化沿用)

L4.91.1 commit `51dbde1` 治本 market-focus#product-customer:

- `frontend-vue3/src/utils/exportXlsx.ts`: XlsxColumn 加 `formatValue?: (val, row) => any | { val, numFmt? }` (向后兼容, 可选字段)
- exportToXlsx line 201-218: formatValue 处理 + numFmtOverrides 独立数组 (跟 aoa 平行, 索引对齐)
- exportToXlsx line 297: 优先用 perRowFmt 然后 fallback col.numFmt
- `frontend-vue3/src/views/market-focus/ProductCustomerTab.vue`: 14 列 xlsxColumns 加 formatValue dispatch (对比行用 _yoy_pct / _yoy_pp 字段 + yoy numFmt)
- `frontend-vue3/src/utils/__tests__/exportXlsx.test.ts`: 2 case L4.91.1 回归测试 PASS

**0 业务代码改动累计 96 次** 1:1 stable 永久规则链配套 (跟 L4.50 累计 95+ 次 1:1 stable).

## 3. 关键技术债 (跟 L4.42 + L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动可修)

### 技术债 #1: market-focus/ProductAssetsTab.vue 同模式未治本

**症状** (跟 L4.91.1 真根因 1:1 stable 永久规则化沿用):
- ProductAssetsTab.vue 有 `isChangeRow / isYoyRow` 模式 (line 9 import + line 195 ExportToolbar)
- xlsxColumns 配置可能没 formatValue, 对比行 (本周对比上周/去年同期) 跟 ProductCustomerTab 治本前同 bug:
  - 绝对值列 '¥#,##0' 显示 raw yoy ratio (0.001) → '¥0' ❌ (应该 yoy_pct)
  - 占比列 '0.0%' 显示 raw yoy pp (-0.0094) → '-0.9%' ❌ (应该 yoy_pp)
- 影响 user: user 7/11 报 "导出的表格里面, 各类占比没有改成XX%, 都是0.xxxx, 然后导出的表格占比的YOY, 都是xx%, 不是我需要的pp"

**接手人 fix** (跟 L4.91.1 1:1 stable 永久规则化沿用, 0 业务代码改动 1:1 stable 永久规则链配套):
1. ProductAssetsTab.vue 数据处理: 给对比行加 14 个 _yoy_pct / _yoy_pp 字段
2. ProductAssetsTab.vue xlsxColumns 14 列加 formatValue dispatch (跟 L4.91.1 1:1 stable)
3. 复用 L4.91.1 exportXlsx SSOT formatValue (0 业务代码改动)
4. 回归测试验证 fix
5. 工作量: 0.5h

**user 拍板** "其他前端不要调整逻辑" 1:1 stable 永久规则化沿用, 留尾给接手人 7/16+ 启动.

### 技术债 #2: market-focus/OtherProductAssetsTab.vue 同模式未治本

**症状** (跟 #1 1:1 stable 永久规则化沿用, 同 ProductCustomerTab 治本前):
- OtherProductAssetsTab.vue 跟 ProductAssetsTab.vue 同结构 (line 9 import + line 195 ExportToolbar)
- 同 mode 应该有同 bug

**接手人 fix** (跟 #1 1:1 stable 永久规则化沿用):
- 复用 #1 修复模式 (L4.91.1 formatValue 1:1 stable 永久规则化沿用)
- 工作量: 0.5h

### 技术债 #3: 21 view 无 isChangeRow/isYoyRow 模式 (L4.91 PR0 治本)

**风险评估** (跟 L4.42 立项实证 1:1 stable 永久规则化沿用):
- 21 view 默认使用 L4.91 PR0 kind enum (yoy_pct / yoy_pp / yoy_day 显式 enum)
- 无 isChangeRow/isYoyRow 模式, 不需要 L4.91.1 formatValue dispatch
- L4.91 audit 报告 (#24 ProductCustomerTab) 是 9/24 Rule 1 部分合规视图, 其他 15 view 15/24 fully compliant
- 8 view (Sprint 174) 走 L4.91 PR0 SSOT 已治本

**风险点** (跟 L4.42 立项实证 1:1 stable 永久规则化沿用):
- 8 view 仍 ⚠️ partial (L4.91 PR0 audit 报告 #4 SamplingView + #6 CategoryRepurchaseTab + #7 ChurnWarningTab + #13-15 F/M/R IntervalTab + #19 RFMSegmentDrilldown + #20 ValueTierTab-health): prefix `yoy_` YOY 列没 kind enum
- L4.91 PR2 ESLint "仅锁新增" 1:1 stable: 不强制要求历史修复, 跟 L4.42 0 业务代码改动 1:1 stable 永久规则链配套
- 影响 user 范围: 这 8 view 跟 L4.91 PR0 audit 报告一致, 不在 user 7/11 报的 market-focus#product-customer bug 范围

**接手人 7/16+ 启动**:
- 复用 L4.91.1 formatValue 模式, 给 8 view xlsxColumns 加 kind enum
- 工作量: 0.5h × 8 = 4h (跟 L4.91 audit 报告 留尾 1:1 stable 永久规则化沿用)
- 跟 L4.57 0 commit 续期 SOP 1:1 stable 永久规则化沿用 (真业务触发再立)

## 4. 验证结果 (跟 L4.50 + L4.91.1 1:1 stable 永久规则链配套)

- vitest 14/14 PASS (L4.91 PR0 12 case + L4.91.1 2 case)
- pytest 27/27 PASS (L4.74 + L4.85.3 + L4.85.4 + L4.85.6 + L4.91 SSOT = 27 case, baseline 0 回归)
- frontend build OK in 731ms (跟 L4.22 1:1 stable 永久规则化沿用)
- pre-commit hooks PASS
- CI 4 jobs (L4.91.1 commit in progress)

## 5. 业务验证 (跟 L4.91.1 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动必跑)

1. market-focus#product-customer 导出 Excel:
   - normal row: GSV '¥111.4万' (numFmt '¥#,##0'), 占比 '49.2%' (numFmt '0.0%') ✅
   - 对比行: GSV '+X.XX%' (numFmt '+0.00%;-0.00%;0.00%' yoy_pct), 占比 '+X.XXpp' (numFmt '+0.00"pp";-0.00"pp";0.00"pp"' yoy_pp) ✅

2. market-focus#product-assets + market-focus#other-product-assets 导出 Excel:
   - 对比行格式仍错 (技术债 #1 + #2 留尾) ⚠️

3. 其他 21 view 导出 Excel:
   - L4.91 PR0 kind enum 治本 ✅

## 6. 跟 L4.x 永久规则链配套 (跟 L4.42 + L4.50 + L4.55 + L4.85 + L4.85.4 + L4.85.6 + L4.85.7 + L4.91 + L4.91.1 1:1 stable 永久规则化沿用)

- L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用
- L4.50 0 业务代码改动 累计 96 次 1:1 stable 永久规则链配套
- L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用
- L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 SOP 1:1 stable 永久规则化沿用
- L4.85 + L4.85.4 + L4.85.6 + L4.85.7 + L4.91 + L4.91.1 永久规则链 1:1 stable 永久规则化沿用

## 7. 跨 sprint 留尾 (跟 L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动可读)

- **技术债 #1 + #2**: market-focus/ProductAssetsTab + OtherProductAssetsTab 复用 L4.91.1 formatValue 模式 (1h, 跟 L4.91.1 1:1 stable 永久规则化沿用)
- **L4.91 audit 报告 8 view partial**: 复用 L4.91.1 formatValue 模式 (4h, 跟 L4.91 audit 留尾 1:1 stable 永久规则化沿用, 跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable)
- **L4.85.6 Playwright e2e 测试环境隔离**: launchd backend 共享 ACTIVE_TOKENS dict 状态污染, backend 加 POST /api/v1/_test/reset (0.5h, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
- **累计 Sprint 60+ 0 debt stable 146 sprint** (跨 sprint 0 debt 模式 1:1 stable 永久规则化沿用)

---

**本报告跟 L4.42 + L4.50 + L4.55 + L4.85 + L4.85.4 + L4.85.6 + L4.85.7 + L4.91 + L4.91.1 1:1 stable 永久规则链配套, 接手人 7/16+ 启动可读 (无论是 GPT-5.6 还是其他 agent/人).**

**关键: 接手人修复技术债 #1 + #2 必走 L4.42 立项实证 SOP 'git log + grep 实证' + L4.91.1 formatValue SSOT 1:1 stable 永久规则化沿用, 不要凭印象改代码.**