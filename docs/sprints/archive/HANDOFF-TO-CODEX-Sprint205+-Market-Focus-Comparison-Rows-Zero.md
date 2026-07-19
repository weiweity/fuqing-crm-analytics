# HANDOFF-TO-CODEX: 市场对焦 对比行 显示全 0% 修复

> **接手**: Codex app | **main HEAD**: `517093e`

## 根因

`ProductCustomerTab.vue` 的 NDataTable `columns` 定义中，对比行（本周对比上周/本周对比去年同期）的 render 函数使用了原始字段（如 `row.gsv`），而这些字段在对比行中被设为 `0`。应该读取 `_yoy_pct` / `_yoy_pp` 后缀字段。

```javascript
// ❌ 当前 (line 611-613) — row.gsv = 0 for comparison rows
render: (row) => row.isChangeRow || row.isYoyRow
  ? h('span', { class: changeClass(row.gsv) }, fmtYoy(row.gsv))
  : fmtMoney(row.gsv),

// ✅ 应该
render: (row) => row.isChangeRow || row.isYoyRow
  ? h('span', { class: changeClass(row.gsv_yoy_pct ?? 0) }, fmtYoy((row.gsv_yoy_pct ?? 0) * 100))
  : fmtMoney(row.gsv),
```

注意 `fmtYoy` 期望 caller 已 `*100`（见 line 570 注释）。

## 需要修复的 13 列

**绝对值 9 列**（用 `_yoy_pct` 后缀 ×100）：
- GSV: `row.gsv_yoy_pct`
- 新客GSV: `row.new_gsv_yoy_pct`
- 老客GSV: `row.old_gsv_yoy_pct`
- 总客户数: `row.users_yoy_pct`
- 新客数: `row.new_users_yoy_pct`
- 老客数: `row.old_users_yoy_pct`
- 总客单价: `row.aus_yoy_pct`
- 新客客单价: `row.new_aus_yoy_pct`
- 老客客单价: `row.old_aus_yoy_pct`

**占比 4 列**（用 `_yoy_pp` 后缀 ×100, 显示 pp）：
- 新客成交占比: `row.new_ratio_gsv_yoy_pp`
- 老客成交占比: `row.old_ratio_gsv_yoy_pp`
- 新客人数占比: `row.new_ratio_users_yoy_pp`
- 老客人数占比: `row.old_ratio_users_yoy_pp`

## Helper 函数

在 `const columns` 前加：

```javascript
// L4.91 design-review (2026-07-12): 对比行渲染辅助
function _cmpVal(row: TableRow, yoyKey: string): number {
  if (!row.isChangeRow && !row.isYoyRow) return 0
  return (row as any)[yoyKey] ?? 0
}
```

## 修复模式

绝对值列（GSV 为例）：
```javascript
render: (row) => row.isChangeRow || row.isYoyRow
  ? h('span', { class: changeClass(_cmpVal(row, 'gsv_yoy_pct')) }, fmtYoy(_cmpVal(row, 'gsv_yoy_pct') * 100))
  : fmtMoney(row.gsv),
```

占比列（新客成交占比为例）：
```javascript
render: (row) => row.isChangeRow || row.isYoyRow
  ? h('span', { class: changeClass(_cmpVal(row, 'new_ratio_gsv_yoy_pp')) }, fmtPctChange(_cmpVal(row, 'new_ratio_gsv_yoy_pp') * 100))
  : fmtPct(row.new_ratio_gsv),
```

## 行号参考

`ProductCustomerTab.vue`:
- Helper 插入位置: line ~592 (在 `const columns` 之前)
- GSV: line 611
- 新客GSV: line 620
- 老客GSV: line 629
- 总客户数: line 638
- 新客数: line 647
- 老客数: line 656
- 总客单价: line 665
- 新客客单价: line 674
- 老客客单价: line 683
- 新客成交占比: line 692
- 老客成交占比: line 701
- 新客人数占比: line 710
- 老客人数占比: line 719

## 约束

- **不要改** xlsxColumns 的 formatValue（Excel 导出已正确）
- **不要改** wideTable 数据构建（计算逻辑正确）
- **只改** NDataTable columns 的 render 函数
- build 验证: `cd frontend-vue3 && npm run build`
