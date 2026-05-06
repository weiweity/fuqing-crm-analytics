# 老客健康分析仪表盘 — 工程 + 设计 Review

> 评审日期: 2026-04-18  
> 评审对象: `design_customer_health_dashboard.md` v1.0  
> 状态: 评审完成，3项调整建议

---

## 一、工程视角审核 (Plan Eng Review)

### Step 0: Scope Challenge

| 检查项 | 结论 |
|--------|------|
| 现有代码复用 | ✅ 复用 `orders`/`user_first_purchase`/`FilterBuilder`/现有前端框架 |
| 最小变化集 | ⚠️ 1个service + 16个schema + 13个前端组件，规模中等偏大 |
| 复杂度触发 | ⚠️ 新增1个service（内含5个模块）、13个Vue组件，建议审视拆分 |
| 搜索检查 | DuckDB内置NTILE/窗口函数 ✅ 无自定义方案 |
| 完整性 | ✅ 文档覆盖Schema/SQL/前端/性能/排期 |

**结论**: 范围合理，但建议将5个Tab的API分批交付（先P1：现状概览+复购周期，后P2：其余3个），降低风险。

---

### 1. Architecture Review

| # | 议题 | 严重度 | 建议 |
|---|------|--------|------|
| 1 | **单文件Service过重** | P2 | `health_service.py` 将包含5个模块×多SQL ≈ 800+行。建议按模块拆分为 `health/overview.py`, `health/repurchase.py` 等，或至少在文件内用 `###` 区域清晰分隔 |
| 2 | **main.py 路由膨胀** | P2 | 追加6个路由到已很大的 main.py（当前~400行）。建议用 `APIRouter` 拆出 `routers/health.py` |
| 3 | **Schema 集中化风险** | P3 | 16个新模型追加到 schemas.py（当前~560行），该文件将膨胀到700+行。建议未来考虑按模块拆分 schemas（但当前项目规模可接受） |
| 4 | **Cohort SQL 数据扫描范围** | P2 | Cohort留存查询需扫描全表做 `DATE_TRUNC` + `DISTINCT` + `LEFT JOIN`，886万订单 × 36个月cohort 可能触及性能瓶颈。建议限制cohort月份范围（如最近12个月） |
| 5 | **大促CSV硬编码路径** | P2 | CSV路径 `/Users/hutou/Desktop/...` 是绝对路径，不同环境会失效。建议改为相对路径或配置化：`PROMOTION_CSV_PATH = config.PROMOTION_CSV_PATH` |
| 6 | **渠道排除重复定义** | P1 | `EXCLUDE_CHANNELS_DEFAULT` 在 health_service.py 重新定义，与 `filters.py` / `metrics_service.py` 的 `_DB_CHANNEL_MAP` 重复。应统一从 `filters.py` 导入 |
| 7 | **前端组件过细拆分** | P3 | 13个组件中部分过于原子（如 AlertBanner、HealthScoreCard），可能导致文件碎片化。建议合并简单组件：AlertBanner → HealthOverviewTab 内联；HealthScoreCard → 用现有图表组件 |

**关键决策**: 是否拆分 `health_service.py`？
- **A)** 保持单文件，用区域注释分隔（简单，适合当前规模）
- **B)** 拆分为 `services/health/` 子目录（更清晰，但增加文件数）
- **建议 A**：当前5个模块都是读操作，SQL逻辑相似，单文件更易维护。当单个模块超过200行时再拆。

---

### 2. Code Quality Review

| # | 议题 | 严重度 | 建议 |
|---|------|--------|------|
| 8 | **SQL 中渠道名硬编码** | P1 | SQL中多次出现 `channel NOT IN ('u先派样', ...)` 字符串。应使用 `OrderFilters.channel_not_in()` 生成，避免口径不一致 |
| 9 | **DATE_SUB 兼容性** | P2 | SQL中 `DATE_SUB(?, INTERVAL ? DAY)` 是MySQL语法，DuckDB 使用 `?::DATE - INTERVAL '? days'`。需修正为 DuckDB 兼容语法 |
| 10 | ** health_score 公式未归一化** | P2 | `health_score` 直接加权（复购率0-1 × 0.25 + 占比0-1 × 0.20...），但各指标量纲不同（复购率是0-1，AUS趋势可能是-0.5~+0.5）。建议先对各指标做 Min-Max 归一化到0-1再加权 |
| 11 | **DuckDB 的 `EXTRACT(DAY FROM interval)`** | P2 | `EXTRACT(DAY FROM (pay_time - prev_pay_time))` 在 DuckDB 中返回 interval 的天数部分，跨月可能不准确。应使用 `DATEDIFF('day', prev_pay_time, pay_time)` |
| 12 | **缺失错误处理** | P2 | 文档中所有 SQL 未标注错误处理（如空结果、除零）。实际实现时需补充 `safe_ratio` 调用 |
| 13 | **前端 store 命名冲突** | P3 | `useHealthDashboardStore` 可能与现有命名风格不一致。建议检查现有 stores 命名规范 |

---

### 3. Test Review

| 检查项 | 状态 |
|--------|------|
| 单元测试覆盖 | ⚠️ 文档未提及测试计划。建议补充：每个SQL查询至少1个集成测试（DuckDB内存模式） |
| E2E测试 | ⚠️ 5个Tab的用户流程需要至少1个E2E测试（点击Tab→数据加载→图表渲染） |
| 边缘case | ⚠️ 未覆盖：空数据（新系统无历史数据）、单用户cohort、全渠道排除后的空结果 |

**建议补充的测试**：
1. `test_health_overview_empty_data`：空表返回默认值，不抛异常
2. `test_health_repurchase_single_user`：只有1个用户时的复购率=0
3. `test_health_cohort_small_range`：2个月cohort范围，验证矩阵维度正确

---

### 4. Performance Review

| # | 议题 | 影响 | 建议 |
|---|------|------|------|
| 14 | **Cohort留存全表扫描** | 高 | 当前SQL扫描全表后做 `DATE_TRUNC`。建议添加 `pay_time >= start_month` 过滤，减少扫描量 |
| 15 | **复购间隔窗口函数** | 中 | `LAG() OVER (PARTITION BY user_id)` 需全表排序。建议先按user_id + pay_time建组合索引（如果DuckDB支持）或限制分析周期 |
| 16 | **NTILE 计算** | 低 | `NTILE(20) OVER (ORDER BY gsv)` 需全排序，但84万用户数据量可控 |
| 17 | **前端并发请求** | 中 | 5个Tab同时加载时可能触发5个并发请求。建议实现Tab懒加载（首次切换时才请求） |

---

### 工程审核总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构合理性 | 7/10 | 建议用APIRouter拆分路由，Cohort SQL需加时间过滤 |
| 代码质量 | 6/10 | 3处DuckDB语法兼容性问题，渠道硬编码需修正 |
| 测试覆盖 | 4/10 | 文档未包含测试计划，需补充 |
| 性能 | 6/10 | 2处全表扫描风险，需限制查询范围 |
| **综合** | **6/10** | **可实施，但需修正P1/P2问题后再编码** |

---

## 二、设计视角评分 (Plan Design Review)

### 0. 初始评分

**设计完整性: 5/10**

原因：文档描述了数据和功能，但未描述用户**看到什么**、**感受到什么**、**如何交互**。缺少视觉层次、状态设计、空状态处理。

---

### Pass 1: Information Architecture（信息架构）

**评分: 4/10 → 建议到 7/10**

**问题**：
- Tab顺序未说明逻辑（是按使用频率？按决策链路？）
- "现状概览"作为日报，用户首次进入应该看到什么？（健康分大图？告警横幅？）
- 缺少全局筛选器与分析周期的关系说明（顶部日期筛选如何影响各Tab？）

**建议修复**：
```
页面层次（从上到下）：
1. 全局筛选栏（日期范围、渠道排除）— 影响所有Tab
2. 告警横幅（如有异常，置顶显示）— 仅"现状概览"Tab
3. 健康评分大卡片区（5个核心指标）— "现状概览"
4. 详细内容区（图表/表格）— 随Tab切换
```

---

### Pass 2: Interaction State Coverage（交互状态）

**评分: 3/10 → 建议到 8/10**

**缺失状态表**：

| 功能 | Loading | Empty | Error | Success | Partial |
|------|---------|-------|-------|---------|---------|
| 健康评分加载 | 骨架屏 | "暂无足够数据，请扩大分析周期" | "计算失败，重试" | 显示评分+颜色 | 部分指标可用 |
| Cohort热力图 | 转圈 | "选择更长时间范围" | 报错+重试 | 完整矩阵 | 部分月份缺失 |
| 价值分层表 | 骨架屏 | "该周期无购买用户" | 报错 | 表格+洞察 | — |
| 告警区 | — | "暂无异常，运营良好 👍" | — | 告警卡片列表 | — |

**关键设计**：空状态不是"No data"，而是给用户行动指引。

---

### Pass 3: User Journey & Emotional Arc（用户旅程）

**评分: 4/10 → 建议到 6/10**

**用户情绪曲线**：
```
时间线 →

进入页面："今天老客怎么样？"（期待）
  ↓
看到健康分绿色："还行，快速扫一眼"（安心）
  ↓
看到黄色预警："哪里出了问题？"（警觉）
  ↓
点击告警 → 跳转到对应Tab："让我看看细节"（探索）
  ↓
看到行动建议："知道该干什么了"（掌控）
```

**缺失**：告警到行动的跳转链路未设计。建议：告警卡片可点击，直接切换到对应Tab并高亮相关数据。

---

### Pass 4: AI Slop Risk（AI套路风险）

**评分: 7/10**

**风险检查**：
- ❌ 3列卡片网格？→ 现状概览的5个指标卡可能落入此套路。建议：健康评分用**大环形图**居中，4个指标环绕，形成焦点
- ❌ 装饰性阴影/圆角？→ 需与现有项目设计系统对齐（Naive UI风格）
- ✅ 无紫色渐变
- ✅ 无emoji装饰
- ✅ 无通用SaaS hero

**建议**：健康评分区域避免"5个等大小卡片并排"，改用"1大（环形图）+ 4小（指标）"的非对称布局。

---

### Pass 5: Design System Alignment（设计系统对齐）

**评分: 5/10**

**问题**：
- 文档未引用现有设计系统（Naive UI + 项目自定义主题）
- 未说明颜色语义（健康=绿色/预警=黄色/危险=红色，是否与现有告警颜色一致？）
- 图表库未指定（ECharts? 与现有项目一致？）

**建议**：在文档中追加一节「视觉规范」：
```
## 视觉规范
- 图表库: ECharts 5（与现有项目一致）
- 颜色语义: 健康=#52c41a, 预警=#faad14, 危险=#f5222d（Ant Design语义色）
- 布局: Naive UI n-grid + n-card
- 字体: 系统默认（与现有项目一致）
```

---

### Pass 6: Responsive & Accessibility（响应式与无障碍）

**评分: 3/10 → 建议到 5/10**

**缺失**：
- 未说明移动端适配（Tab切换在移动端如何呈现？）
- 未说明图表响应式（ECharts需监听resize）
- 无障碍：图表需添加 `aria-label` 描述

**建议**：至少补充「Tab在移动端转为下拉选择或横向滚动」。

---

### Pass 7: Unresolved Design Decisions（待解决设计决策）

| 决策 | 如果延期，会发生什么 | 建议 |
|------|---------------------|------|
| 告警→Tab跳转交互 | 用户看到告警后不知道去哪看详情 | 在Phase 1实现 |
| 空状态文案 | 工程师写"暂无数据" | 设计师先出文案 |
| 健康分颜色阈值 | 工程师随意定 | 与运营确认（60分是否太低？） |
| 导出CSV的列顺序 | 用户导出后列顺序混乱 | Phase 2出规范 |

---

### 设计评分总结

| 维度 | 初始 | 目标 | 关键动作 |
|------|------|------|----------|
| 信息架构 | 4/10 | 7/10 | 补页面层次图、Tab逻辑说明 |
| 交互状态 | 3/10 | 8/10 | 补状态表（重点：空状态、加载态） |
| 用户旅程 | 4/10 | 6/10 | 补告警→行动跳转链路 |
| AI Slop | 7/10 | 8/10 | 健康评分区非对称布局 |
| 设计系统 | 5/10 | 7/10 | 补视觉规范一节 |
| 响应式 | 3/10 | 5/10 | 补移动端Tab方案 |
| 未解决决策 | — | — | 7项决策中3项需在Phase 1解决 |
| **综合** | **4/10** | **6.5/10** | **补齐状态表和视觉规范后可实施** |

---

## 三、关键调整建议（汇总）

### 🔴 必须在编码前修复（P1）

| # | 问题 | 位置 | 修复内容 |
|---|------|------|----------|
| 1 | SQL渠道名硬编码 | 所有SQL示例 | 改为 `OrderFilters.channel_not_in()` |
| 2 | `DATE_SUB` MySQL语法 | 3.3.4 SQL | 改为 DuckDB `?::DATE - INTERVAL '? days'` |
| 3 | `EXTRACT(DAY FROM interval)` | 3.2.4 SQL | 改为 `DATEDIFF('day', ...)` |
| 4 | 渠道排除重复定义 | 5.3 常量 | 从 `filters.py` 导入，不重新定义 |
| 5 | 大促CSV绝对路径 | 10.1 代码 | 改为配置化路径 |

### 🟡 建议同步修复（P2）

| # | 问题 | 修复内容 |
|---|------|----------|
| 6 | main.py 路由拆分 | 使用 `APIRouter` 拆出 `routers/health.py` |
| 7 | health_score 归一化 | 补充 Min-Max 归一化说明 |
| 8 | Cohort SQL 时间过滤 | 添加 `pay_time >= start_month` 减少扫描 |
| 9 | 前端组件合并 | AlertBanner + HealthScoreCard 合并或内联 |
| 10 | 补视觉规范章节 | 颜色语义、图表库、布局规范 |

### 🟢 可在Phase 2优化（P3）

| # | 问题 | 说明 |
|---|------|------|
| 11 | Schema 拆分 | 当 schemas.py 超过800行时按模块拆分 |
| 12 | 前端懒加载 | Tab首次切换时才请求数据 |
| 13 | 测试计划 | 补充 DuckDB 集成测试方案 |

---

## 四、实施建议

### 分批交付方案（推荐）

```
Phase 1（核心日报，~12h）：
  ├─ Schema: HealthOverviewMetrics + HealthAlertItem
  ├─ API: /health/overview
  ├─ 前端: CustomerHealthView + HealthOverviewTab
  └─ 修复: P1问题 + 补状态表

Phase 2（分析工具，~14h）：
  ├─ Schema: 其余14个模型
  ├─ API: /health/repurchase-cycle, /health/value-tiers 等5个
  ├─ 前端: 其余4个Tab
  └─ 优化: P2问题 + 懒加载
```

**好处**：
1. Phase 1 即可交付运营日报（核心价值）
2. 降低一次性变更风险（26h连续开发易出错）
3. 运营可提前使用，反馈驱动Phase 2优化

---

## 五、Review 结论

| Review | 状态 | 说明 |
|--------|------|------|
| 工程审核 | ⚠️ 有条件通过 | 修复5个P1问题后可编码 |
| 设计评分 | ⚠️ 有条件通过 | 补齐状态表+视觉规范后可编码 |
| **综合结论** | **建议分批实施** | Phase 1先交付现状概览，验证后再扩展 |

---

*Review完成。请确认是否接受分批方案，以及P1/P2修复是否由我同步更新到设计文档。*
