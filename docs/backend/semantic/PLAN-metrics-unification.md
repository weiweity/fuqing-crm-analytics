# 芙清 CRM - 业务口径与计算逻辑统一调整方案

> **文档性质**：技术执行方案  
> **版本**：v1.0  
> **日期**：2026-04-16  
> **状态**：待执行  
> **关联文档**：`docs/PRD-v2.0.md`（产品需求升级）、`docs/ARCHITECTURE-metrics-management.md`（架构设计）

---

## 一、为什么要做这次调整

### 1.1 现状问题（已确认）

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| **口径碎片化** | `is_goujinjin = FALSE AND is_refund = FALSE` 散落在 `metrics/rfm/churn/geo/category/ETL` 6+ 文件中 | 4月14日 GSV Bug 活了4周才发现，改了14处文件 |
| **业务规则硬编码** | 8象限 CASE WHEN SQL 在 4 个 service 里各写一份 | 改人群定义要改 4 个文件，极易不一致 |
| **前后端契约混乱** | Pydantic 模型内联在 `main.py`，和实际返回经常对不上 | 前端调用后只能猜字段，Vue3 页面多次出现类型不匹配 |
| **无指标注册中心** | 没有地方能查"GSV 到底怎么算的" | 新增指标全靠口口相传 |

### 1.2 如果不调整，未来会怎样

- **Week 5 缺口追踪** 需要新增 5-8 个预测指标，如果不统一管理，预计又会在 4-6 个文件中重复写过滤条件
- **Vue3 前端全面替换 Streamlit** 过程中，API 契约问题会被放大，类型错误会阻塞开发
- **你 9 月转 PM** 之后，接手的人无法快速理解业务口径，交接成本极高

---

## 二、调整目标

1. **改一处，全局生效**：GSV/GMV/新老客等核心口径只定义一次
2. **前后端契约 100% 对齐**：Pydantic 模型外置，前端类型从 OpenAPI 自动生成
3. **新增指标有 SOP**：从"改十几个文件"变成"注册指标 → 更新契约 → 前端引用"三步走
4. **人和 AI 都能看懂**：所有指标/维度/人群分层都有文档化定义

---

## 三、SaaS 公司的标准做法

成熟的 SaaS/BI 产品（如 Looker、dbt、Metabase、国内的神策/火山引擎）都会引入 **语义层（Semantic Layer / Metrics Layer）**：

```
数据层(DuckDB) → 语义层(semantic) → 服务层(services) → 契约层(contracts) → 前端(Vue3)
```

**语义层负责**：
- 什么是"有效订单"？
- 什么是"GSV"？公式是什么？
- 什么是"8象限"？阈值是多少？
- 什么是"渠道"？9层漏斗怎么判定？

**契约层负责**：
- API 的 Request/Response 结构是唯一的、文档化的
- 前端通过 `openapi.json` 自动生成 TypeScript 类型，禁止手写 guess

---

## 四、具体调整内容

### 4.1 已经做完的（4月16日）

| 文件 | 内容 | 状态 |
|------|------|------|
| `backend/semantic/filters.py` | 统一 SQL 过滤条件构造器 | ✅ 已创建 |
| `backend/semantic/metrics.py` | 指标注册表（16+ 核心指标） | ✅ 已创建 |
| `backend/semantic/dimensions.py` | 维度注册表（10 个维度） | ✅ 已创建 |
| `backend/semantic/segments.py` | 8象限 + RFM 阈值 + SQL 生成器 | ✅ 已创建 |
| `backend/semantic/channels.py` | 9层渠道漏斗文档化定义 | ✅ 已创建 |
| `backend/semantic/time.py` | MTD/自由模式/MoM/YoY 时间周期构造器 | ✅ 已创建 |
| `backend/contracts/schemas.py` | Pydantic 契约模型迁移目标 | ✅ 已创建 |
| `backend/services/metrics_service_refactored.py` | 语义层使用示例 | ✅ 已创建 |

### 4.2 接下来要做的（分 4 个阶段）

#### Phase 1：核心 Service 迁移（本周，4月16日-4月18日）

**目标**：把最常用的 5 个 service 从"硬编码 SQL"改成"引用语义层"。

| 序号 | 文件 | 调整内容 | 负责人 | 验收标准 |
|------|------|----------|--------|----------|
| 1.1 | `backend/services/metrics_service.py` | 用 `FilterBuilder` 替代所有硬编码 WHERE；用 `DimensionRegistry` 替代 GROUP BY；用 `PeriodBuilder` 替代日期计算 | AI / 你 | 重构前后 `/api/v1/metrics/overview` 返回数值 100% 一致 |
| 1.2 | `backend/services/rfm_service.py` | 用 `SegmentRegistry` 替代 8象限 CASE WHEN；用 `AmountExprBuilder` 替代 GSV 金额表达式 | AI / 你 | RFM 8象限人数与原结果完全一致 |
| 1.3 | `backend/services/churn_service.py` | 用 `OrderFilters.valid_order()` 替代重复的 WHERE 条件 | AI / 你 | 流失分析页面数据无变化 |
| 1.4 | `backend/services/geo_service.py` | 同上 | AI / 你 | 地域分布页面数据无变化 |
| 1.5 | `backend/services/category_service.py` | 同上 | AI / 你 | 品类分析页面数据无变化 |

**执行建议**：每个文件按"备份 → 重构 → 跑单测/手工对比 → 删除备份"四步走。

#### Phase 2：API 契约迁移（下周，4月21日-4月23日）

| 序号 | 文件 | 调整内容 | 验收标准 |
|------|------|----------|----------|
| 2.1 | `backend/main.py` | 所有内联 Pydantic Response 模型迁移到 `backend/contracts/schemas.py`；main.py 只保留路由和依赖注入 | `main.py` 中无 `class XXXResponse(BaseModel)` 定义 |
| 2.2 | `backend/contracts/schemas.py` | 补全所有缺失的 Response 模型；字段名和实际返回 100% 对齐 | `/openapi.json` 能完整导出所有接口定义 |

#### Phase 3：前端类型自动生成（4月24日-4月30日）

| 序号 | 调整内容 | 验收标准 |
|------|----------|----------|
| 3.1 | 在 `frontend-vue3/` 安装 `openapi-typescript` | `package.json` 中有 `openapi-typescript` devDependency |
| 3.2 | 配置脚本：`npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts` | 执行后生成 `src/api/types.ts`，无报错 |
| 3.3 | 选 1-2 个简单页面（如 Dashboard 概览页），把手写类型替换为自动生成类型 | TypeScript 编译通过，页面渲染正常 |
| 3.4 | 逐步推广到所有页面，删除手写 guess 的类型定义 | 全量替换后 `npm run build` 通过 |

#### Phase 4：ETL 对齐 + 规范落地（5月初）

| 序号 | 调整内容 | 验收标准 |
|------|----------|----------|
| 4.1 | `scripts/run_etl.py` 中的 `clean_data()` 和渠道判定逻辑，至少把判定条件字符串抽到 `semantic/filters.py` 做常量管理 | ETL 和 Service 层的"有效订单"定义引用同一出处 |
| 4.2 | 在 PR 规范中增加一条：禁止在 Service 中硬编码 `order_status LIKE '%成功%'` 或 `is_goujinjin = FALSE` | Code Review 有据可依 |
| 4.3 | 更新 README 和 HANDOFF 文档，说明新增指标的 SOP | 新加入的 AI/开发能在 10 分钟内理解流程 |

---

## 五、调整后的开发流程（新增指标 SOP）

### 5.1 以前（痛苦模式）

```
产品经理说："我要加一个'直播 GSV'指标"
→ 改 metrics_service.py
→ 改 rfm_service.py（如果 RFM 也要看）
→ 改 run_etl.py（如果 ETL 也要算）
→ 改 main.py（加 Response 字段）
→ 告诉前端："你加个字段叫 live_gsv，类型是 number"
→ 前端猜字段名、猜类型、手写 TypeScript 类型
→ 联调发现字段名写成了 liveGsv，返工
```

### 5.2 以后（标准模式）

```
产品经理说："我要加一个'直播 GSV'指标"
→ Step 1: 在 backend/semantic/metrics.py 注册 "live_gsv"
→ Step 2: 在 backend/contracts/schemas.py 的响应模型里加字段
→ Step 3: 在 Service 里用 MetricRegistry.get("live_gsv").sql_expr 引用
→ Step 4: 后端启动后，前端执行 npm run gen:types 自动生成 TS 类型
→ Step 5: 前端直接使用类型安全的 API 调用
→ 联调一次过
```

---

## 六、风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 重构引入数值偏差 | 中 | 高 | 每个 service 重构后必须对比原结果，抽样 3-5 个接口 |
| 前端类型生成失败 | 低 | 中 | 先选 1 个简单页面试点，不一次性全量替换 |
| 时间不够，只做了一半 | 中 | 高 | 按 Phase 1→2→3→4 顺序执行，即使只做 Phase 1 也能解决 80% 的口径问题 |
| ETL 和 Service 层 Pandas/SQL 差异大，无法完全复用 | 高 | 低 | ETL 至少做到"常量统一"（同一套过滤字符串），不强求完全复用 FilterBuilder |

---

## 七、执行清单（可直接复制到 todo）

```markdown
- [ ] Phase 1.1 重构 metrics_service.py（人群看板核心）
- [ ] Phase 1.2 重构 rfm_service.py
- [ ] Phase 1.3 重构 churn_service.py
- [ ] Phase 1.4 重构 geo_service.py
- [ ] Phase 1.5 重构 category_service.py
- [ ] Phase 2.1 迁移 main.py 内联 Pydantic 模型到 contracts/schemas.py
- [ ] Phase 2.2 验证 /openapi.json 完整性
- [ ] Phase 3.1 前端配置 openapi-typescript
- [ ] Phase 3.2 生成 src/api/types.ts
- [ ] Phase 3.3 选 1-2 页面试点替换手写类型
- [ ] Phase 4.1 ETL 过滤条件常量化
- [ ] Phase 4.2 更新 PR 规范和 README
```

---

## 八、需要你现在做的决策

1. **Phase 1 是否由 AI 直接执行？**
   - 选项 A：AI 直接逐个重构 5 个 service 文件（推荐，预计 1-2 小时完成）
   - 选项 B：AI 只给出重构示例，你手动执行

2. **契约层迁移是否优先做？**
   - 选项 A：先做契约层（先定接口，再改服务，顺序更稳）
   - 选项 B：先做服务层（更快看到口径统一效果，契约层后置）

3. **Vue3 前端类型生成何时启动？**
   - 选项 A：等契约层和 Service 层都完成后再做
   - 选项 B：现在就用现有 `main.py` 的模型先生成一版 `types.ts`，提前跑通链路

**我的建议**：选 A+A+A（AI 直接执行全部，先做契约层再做服务层，前端类型等后端稳了再生成）。

如果你确认，我立刻开始执行 Phase 1 + Phase 2。
