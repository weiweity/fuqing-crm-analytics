# Sprint 12 计划 — 质量加固 + 架构调研

**立项时间**: 2026-06-09
**目标**: 消除技术债、建立测试防线、调研 50M 行架构

---

## 任务总览

| # | 任务 | 优先级 | 工作量 | 状态 |
|---|------|--------|--------|------|
| 1 | MetricCard pp 单测修复 | P0 | 30min | ✅ d07bf9b |
| 2 | vitest 组件单测扩展 | P1 | 1d | ⬜ |
| 3 | playwright E2E 跑通 | P1 | 0.5d | ⬜ |
| 4 | 数据质量监控告警 | P1 | 1d | ⬜ |
| 5 | 50M 行 benchmark | P2 | 2d | ⬜ |
| 6 | 50M 行架构方案 | P2 | 1d | ⬜ |

**总工作量**: ~6d
**依赖**: Task 2/3 依赖 Task 1，Task 6 依赖 Task 5

---

## Task 1: MetricCard pp 单测修复

**目标**: 修复 `humanizeChange` 对 pp 单位未 ×100 的问题

**根因**: Sprint 11 YOY/pp 重构时，pp 单位的 ×100 逻辑遗漏实现

**修改文件**:
- `frontend-vue3/src/components/MetricCard.vue:13-17`

**修改内容**:
```typescript
// 修改前
function humanizeChange(v: number, unit: '%' | 'pp'): string {
  if (!Number.isFinite(v)) return `0.00${unit}`
  const raw = Math.abs(v)
  return `${raw.toFixed(2)}${unit}`
}

// 修改后
function humanizeChange(v: number, unit: '%' | 'pp'): string {
  if (!Number.isFinite(v)) return `0.00${unit}`
  const raw = Math.abs(v)
  const display = unit === 'pp' ? raw * 100 : raw
  return `${display.toFixed(2)}${unit}`
}
```

**验收标准**:
- [ ] `change: -0.5381, unit: 'pp'` 显示 `↓53.81pp`
- [ ] `change: 0.10, unit: 'pp'` 显示 `↑10.00pp`
- [ ] `change: 14, unit: '%'` 显示 `↑14.00%`（不受影响）
- [ ] `npx vitest run src/components/MetricCard.test.ts` 全绿

---

## Task 2: vitest 组件单测扩展

**目标**: 为核心展示组件建立单元测试防线

### 2a: YOYBadge 组件测试

**新建文件**: `frontend-vue3/src/components/YOYBadge.test.ts`

**测试用例**:
- `value: 14, unit: '%'` → `+14.00% ↑`
- `value: -7, unit: '%'` → `7.00% ↓`
- `value: 0.10, unit: 'pp'` → `+10.00pp ↑`
- `value: -0.5381, unit: 'pp'` → `53.81pp ↓`
- `value: null` → `—`
- `value: 0` → `+0.00% ↑`

**验收**: `npx vitest run src/components/YOYBadge.test.ts` 全绿

### 2b: HealthOverviewTab 测试

**新建文件**: `frontend-vue3/src/views/health/HealthOverviewTab.test.ts`

**测试用例**:
- `fmtPercent(0.5335)` → `53.4%`
- `fmtPercent(null)` → `—`
- `fmtCount(1234)` → `1,234`
- `fmtCount(null)` → `—`

**验收**: `npx vitest run src/views/health/HealthOverviewTab.test.ts` 全绿

### 2c: AudienceView 渲染测试

**新建文件**: `frontend-vue3/src/views/AudienceView.test.ts`

**测试用例**:
- `renderValue` 对 `kind: 'ratio'` 显示 `53.35%`
- `renderValue` 对 `kind: 'count'` 显示 `1,234`
- `renderValue` 对 `kind: 'money'` 显示 `¥559.2万`
- `renderValue` 对 `kind: 'aus'` 显示 `¥123.4`

**验收**: `npx vitest run src/views/AudienceView.test.ts` 全绿

---

## Task 3: playwright E2E 跑通

**目标**: `customer-health.spec.ts` 在本地和 CI 都能跑通

**输入**:
- `frontend-vue3/e2e/customer-health.spec.ts`
- `frontend-vue3/playwright.config.ts`

**验收标准**:
- [ ] 本地 `npx playwright test` 全绿
- [ ] 前端+后端都能正常启动
- [ ] 测试覆盖：健康概览页面加载、数据展示、同比显示

**依赖**: Task 1

---

## Task 4: 数据质量监控告警

**目标**: ETL 跑完后自动验证关键指标，异常时飞书告警

### 4a: DQ 监控脚本

**新建文件**: `scripts/etl/dq_monitor.py`

**检查项**:
- orders 表行数（不能比上次少 10%+）
- is_member = TRUE 占比（不能从 50%+ 掉到 10% 以下）
- 最近 7 天有数据（不能断更）
- GSV 不为 0

**验收**: `python3 scripts/etl/dq_monitor.py` 正常输出检查结果

### 4b: 飞书告警集成

**修改文件**: `scripts/etl/dq_monitor.py`

**功能**:
- 检查失败时调用 `lark-cli` 发送告警
- 复用现有 6 道门禁通道
- 告警内容：检查项、当前值、阈值、建议操作

**验收**: `python3 scripts/etl/dq_monitor.py --alert` 发送成功

### 4c: ETL pipeline 集成

**修改文件**: `scripts/etl/pipeline.py`

**功能**:
- ETL 跑完后自动执行 DQ 检查
- 检查失败不阻塞 ETL（quarantine 模式）
- 检查结果写入 `data/processed/dq_report.json`

**验收**: `python3 scripts/etl/pipeline.py --update` 跑完后自动生成 dq_report.json

---

## Task 5: 50M 行 benchmark

**目标**: 用数据回答"DuckDB 单文件能不能撑住 50M 行"

### 5a: 数据生成

**新建文件**: `scripts/etl/benchmark_50m.py`

**功能**:
- 基于现有 10.6M 行数据，生成 50M 行模拟数据
- 保持字段分布一致（渠道、金额、日期等）
- 输出到 `data/processed/fuqing_crm_50m.duckdb`

**验收**: `python3 scripts/etl/benchmark_50m.py` 生成 50M 行数据

### 5b: 查询性能测试

**新建文件**: `scripts/etl/benchmark_queries.py`

**测试场景**:
- 全店复购率查询（10.6M vs 50M）
- RFM 分群查询（10.6M vs 50M）
- 渠道占比查询（10.6M vs 50M）
- 30 指标对比查询（10.6M vs 50M）

**验收**: 每个场景跑 3 次，输出平均耗时

### 5c: 内存和 IO 测试

**新建文件**: `scripts/etl/benchmark_memory.py`

**测试场景**:
- 查询时 RSS 峰值（10.6M vs 50M）
- 冷启动查询耗时（首次 vs 缓存）
- 并发查询性能（1 vs 4 workers）

**验收**: 输出 RSS 峰值和并发性能对比

### 5d: 报告输出

**新建文件**: `docs/validation-reports/benchmark-50m-YYYY-MM-DD.md`

**内容**:
- 测试环境（CPU、内存、SSD）
- 查询性能对比表
- 内存使用对比表
- 结论和建议

**验收**: 报告包含所有测试数据和结论

---

## Task 6: 50M 行架构方案

**前提**: Task 5 benchmark 完成，有数据支撑

**可能的方案**:
- A) 继续用 DuckDB 单文件（benchmark 表现好）
- B) DuckDB 分区（按年/月分区，减少单文件大小）
- C) 迁移到 PostgreSQL（需要评估迁移成本）
- D) 混合方案（热数据 DuckDB，冷数据 Parquet）

**新建文件**: `docs/design/50m-scale-architecture.md`

---

## Wave 编排

### Wave 1: 独立任务并行（Day 1）
- Task 1: MetricCard pp 修 (30min)
- Task 4: 数据质量监控 (1d)
- Task 5: 50M benchmark (2d)

### Wave 2: 依赖任务（Day 2-3）
- Task 2: vitest 组件测试 (1d) — 依赖 Task 1
- Task 3: playwright E2E (0.5d) — 依赖 Task 1

### Wave 3: 架构决策（Day 4）
- Task 6: 50M 架构方案 (1d) — 依赖 Task 5

---

## 决策记录

| 决策 | 结论 | 理由 |
|------|------|------|
| DuckDB 1.5.3 升级 | ❌ 放弃 | 无收益，Fix A 已稳定 |
| is_member 改派生 | ⏸️ defer | 143 处引用，风险大，50M 时再评估 |
| MetricCard pp ×100 | ✅ 代码改 | 用户确认：pp 是百分点差，组件内部 ×100 |
