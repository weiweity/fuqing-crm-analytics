# 导航栏筛选数据不更新 — 修复计划

> 基于 investigator 排查结果 + 代码审计  
> 日期：2026-05-09

---

## 一、根因总结

### 1.1 核心根因（P0）

**AudienceView.vue 中所有 useQuery 的 `queryKey` 使用了普通数组，未用 `computed(() => [...])` 包裹。**

项目历史已知此问题（RIntervalTab.vue 第36行注释有明确记录）：当 `queryKey` 为普通数组且内部包含 `ComputedRef` 时，Vue Query 无法可靠追踪嵌套 computed 的变化。切换 `compareMode` 时，`filterStore.compareParams` 从 `null` 变为 `[string, string]`，但依赖追踪失效，导致**不触发重新请求**。

对比：CategoryView.vue 使用了正确的 `computed(() => [...])` 包裹，因此其 overview 查询可正常响应 compare 切换。

### 1.2 已知缺陷（P1）

`useFilterSync.ts` 未同步 `compareMode` 和 `compareDateRange` 到 URL，导致：
- 刷新页面后对比模式丢失
- 跨页面跳转时对比模式不保持

### 1.3 系统性遗漏（P2）

以下视图的 queryKey **根本未包含 compare 相关参数**，切换 compareMode 时完全不重新请求：
- GeoView.vue（geo-distribution, geo-segment-matrix, geo-trend）
- ChurnView.vue（churn-distribution, churn-risk-users）
- CategoryDetailView.vue（category-daily-trend, category-user-list）
- CategoryFlowTab.vue（category-flow）
- RIntervalTab.vue（rfm-r-flow）
- HealthOverviewTab.vue 的 channel-health-scores 未传 compare

### 1.4 产品层面设计（P3）

以下视图使用**独立的筛选系统**，不响应全局 `compareMode`：
- SamplingView.vue（独立的日期范围、windowDays）
- MarketFocusView.vue（独立的 weeks、channel）
- BreakdownView.vue（独立的表单提交）

---

## 二、修复优先级框架

| 优先级 | 类型 | 影响面 | 修复目标 |
|--------|------|--------|----------|
| **P0 — 阻塞** | Type A | AudienceView.vue 全部5个查询 + 列名变化但数值不变 | 修复 queryKey 包裹方式，确保 compareMode 切换触发请求 |
| **P1 — 高** | Type B | 全站 URL 状态同步 | 补齐 compareMode + compareDateRange 的 URL 同步 |
| **P2 — 中** | Type C | 6个视图/模块的 queryKey | 将 compareParams 纳入 queryKey 和 API 调用 |
| **P3 — 低** | Type D | 3个独立筛选视图 | 产品决策：是否需要接入全局 compareMode |

---

## 三、逐类型修复方案

### Type A: 修复 queryKey 包裹（P0）

**目标文件**: `frontend-vue3/src/views/AudienceView.vue`

**当前代码（错误）**:
```ts
useQuery({
  queryKey: ['audience-summary', queryParams, filterStore.compareParams],
  // ...
})
```

**修复后（正确）**:
```ts
useQuery({
  queryKey: computed(() => ['audience-summary', { ...toValue(queryParams) }, filterStore.compareParams]),
  // ...
})
```

**需修改的查询列表**:
1. `audience-summary`（第175行）
2. `kpi-metrics`（第155行）
3. `daily-trend`（第165行）
4. `visitor-summary`（第193行）
5. `visitor-daily-trend`（第204行）

**验证方式**:
1. 在 AudienceView.vue 页面打开 DevTools Network
2. 切换 compareMode（YOY → MOM → Custom）
3. 确认 `audience-summary` 接口被重新调用，且 `compare_start_date`/`compare_end_date` 参数正确变化
4. 确认表格数值实际变化（不仅是列名）

### Type B: URL 同步补齐（P1）

**目标文件**: `frontend-vue3/src/composables/useFilterSync.ts`

**修复内容**:
1. `syncFromUrl()`: 从 URL query 读取 `compareMode` 和 `compareDateRange`
2. Pinia → URL watch: 将 `filterStore.compareMode` 和 `filterStore.compareDateRange` 加入监听数组和 `router.replace` 的 query 对象
3. 解析/序列化：`compareDateRange` 用 `date_start,date_end` 格式；`compareMode` 直接字符串

**验证方式**:
1. 切换 compareMode 后观察浏览器地址栏是否出现 `?...&compareMode=auto_mom&compareDateRange=2025-04-01,2025-04-30`
2. 刷新页面后确认 compareMode 状态保持
3. 跳转到其他路由后返回，确认 compareMode 保持

### Type C: 补充 compare 参数（P2）

**逐个视图修复**:

对于每个视图，执行以下步骤：
1. 在 `queryParams` computed 中补充 `compareParams` 读取
2. 在 `queryKey` 中加入 compare 相关依赖（或确保 `queryParams` 已包含）
3. 在 API 调用函数中传入 `compare_start_date`/`compare_end_date`
4. 后端接口确认已接收并处理 compare 参数

| 视图/模块 | queryKey | API 传参 | 后端支持 |
|-----------|----------|----------|----------|
| GeoView.vue | 需加入 | 需加入 | 需确认 |
| ChurnView.vue | 需加入 | 需加入 | 需确认 |
| CategoryDetailView.vue | 需加入 | 需加入 | 需确认 |
| CategoryFlowTab.vue | 需加入 | 需加入 | 需确认 |
| RIntervalTab.vue | 需加入 | 需加入 | 需确认 |
| HealthOverviewTab.vue (channel-health-scores) | 需加入 | 需加入 | 需确认 |

**验证方式**:
对每个修复后的视图，切换 compareMode，确认：
1. Network 中对应接口被重新调用
2. 请求参数中包含正确的 `compare_start_date`/`compare_end_date`
3. 返回数据中的对比数值发生变化

### Type D: 独立系统接入决策（P3）

| 视图 | 现状 | 建议 |
|------|------|------|
| SamplingView.vue | 独立日期 + windowDays | 短期：维持独立；长期：评估是否需要 compare 支持 |
| MarketFocusView.vue | 独立 weeks + channel | 短期：维持独立；长期：评估是否需要 compare 支持 |
| BreakdownView.vue | 独立表单提交 | 维持独立（本身就是目标拆解工具，不适用于全局筛选） |

---

## 四、实施顺序建议

1. **先实施 P0（Type A）** — 直接修复用户报告的问题
2. **并行实施 P1（Type B）** — URL 同步与 P0 无冲突
3. **P2（Type C）** 按模块逐个修复，每修复一个立即验证
4. **P3（Type D）** 留待产品决策，不阻塞发布

---

## 五、风险评估

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| 修改 queryKey 包裹方式引入新的 Vue Query 行为差异 | 中 | 每改一个查询立即在浏览器验证 |
| URL 同步新增参数导致现有书签/分享链接失效 | 低 | 新增参数有默认值（auto_yoy），无参时行为不变 |
| 后端部分接口未实现 compare 参数支持 | 中 | P2 实施前逐一验证后端接口签名 |
| 批量修改导致回归 | 低 | 按优先级分批实施，每次改后跑通对应页面 |
