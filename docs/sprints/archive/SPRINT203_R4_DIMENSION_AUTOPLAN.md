# Sprint 203 R4 Dimension Autoplan — 多维度按月衍生 (跟 Sprint 199+ 留尾任务 A/B 1:1 stable)

> **作者**: Claude Code 架构师 (你 7/5 拍板"处理下 Sprint 199+ 留尾, 发挥 AI 能力, 推测, 拉 workflow, /autoplan")
> **日期**: 2026-07-05
> **关联**: Sprint 199 R1 + Sprint 201+ 留尾任务 A (淘客按月) + 任务 B (单品按月按 spu_product_class) + Sprint 60+ L4.42 立项实证 SOP + L4.43 argparse nargs 透传 + L4.5 FilterBuilder
> **/autoplan 入口**: 走 CEO → Design (skip, no UI 直接复用) → Eng → DX 4 phase + dual voices (codex + claude subagent)

---

## 1. Problem

你 7/5 拍板: Sprint 199+ 留尾 3 P0 业务补全, 之前 0 commit 续期 (L4.42 实证 0 业务触发), 现在你主动说要实施。同时让我"发挥 AI 能力, 推测, 不只是淘客"。

**实际业务场景**: 业务组问数习惯 (从 SKILL v2.6 14 tool 真实命中率实证) 集中在日维度 (channel_slice / daily_gsv), 月/季/年维度缺失严重。月维度 = 业务月报核心, 季度复盘核心, 年度对比基础。

---

## 2. 字段全景扫描 (Sprint 60+ 持续沉淀, 1:1 stable)

### 2.1 数据库列名 (orders 表, 50 列)

**时间维度** (5 列):
- `order_time` / `pay_time` / `ship_time` (TIMESTAMP, 已 ETL 解析)
- `year` / `month` (INTEGER, ETL 预聚合)

**渠道维度** (1 列, 9 真实 + 2 虚拟):
- `channel`: 货架/达播/直播/淘客/微博/U先派样/百补派样/赠品&0.01/其他 (+ 全店/纯派样聚合)

**SPU 8 维** (database.py SPU_LEVELS 白名单):
- `spu_category` (一级品类)
- `spu_type` (二级品类)
- `spu_tier` (商品梯队)
- `spu_product_class` (产品类)
- `spu_product_subclass` (产品子类)
- `spu_cosmetic` (功效)
- `spu_spec` (规格)
- `spu_hash` (单品 hash)

**业务维度** (5 列):
- `is_member` (会员)
- `is_goujinjin` (购金金)
- `is_refund` (退款)
- `order_status` / `refund_status`

**用户/商品/营销维度** (剩余 30+ 列):
- 用户: user_id / user_nickname / province / city
- 商品: product_id / merchant_code / product_title / sku_id / quantity / amount / actual_amount / refund_amount
- 营销: influencer_name / influencer_id / live_room_id / video_id / traffic_source / traffic_type

### 2.2 14 tool 现状 (Sprint 198 累计)

| Tool | 维度支持 | 时间粒度 | 缺口 |
|---|---|---|---|
| two-year-overview | 总览 | 年 (2 年对比) | 月/季 |
| new-old-customer | new/old | 总览 | 按月/按渠道交叉 |
| rfm-repurchase | R 区间 | 总览 | 按月 R 区间 |
| top-n | spu 8 维 | 年 (2 年对比) | **月/季** ❌ |
| export-excel | 不限 | 总览 | - |
| dq-report | DQ | 总览 | - |
| ask | LLM | 不限 | - |
| channel-slice | channel | **日** | **月/季** ❌ |
| daily-gsv | 总览 | 日 | 月/季 |
| daily-gsv-multi-period | 总览 | 多日 | 月聚合 |
| fixed-product-list-compare | product_id | 总览 | 月 |
| fixed-product-list-compare-http | product_id | HTTP | 月 |
| ai-sandbox-execute | LLM | 不限 | - |
| yoy-battle | 总览 | 年 (YoY) | 月/季 |

---

## 3. 衍生矩阵 (我推测, 4 维度 × 5 时间粒度)

### 3.1 按月维度 (4 个空白点, **核心实施范围**)

| 衍生项 | 对应空白 | 工作量 | 业务价值 |
|---|---|---|---|
| `channel-monthly` | 渠道按月 (Sprint 199+ 任务 A 淘客) | 1-2 天 | ⭐⭐⭐ 业务月报核心 |
| `spu-monthly` (top_n 加 month axis) | spu 8 维按月 (Sprint 199+ 任务 B) | 1-2 天 | ⭐⭐⭐ 品类月报核心 |
| `member-monthly` | is_member 按月 (会员留存) | 1 天 | ⭐⭐ 会员业务核心 |
| `refund-monthly` | is_refund 按月 (退款监控) | 1 天 | ⭐⭐ 退款监控核心 |

### 3.2 多维度交叉 (3 个空白点, **衍生机会**)

| 衍生项 | 交叉维度 | 工作量 | 业务价值 |
|---|---|---|---|
| `cross-dimension-monthly` | channel × is_member | 1 天 | ⭐⭐ 会员中各渠道占比 |
| `cross-dimension-monthly` | spu_category × channel | 0.5 天 | ⭐⭐ 各品类在各渠道销售 |
| `cross-dimension-monthly` | is_goujinjin × channel | 0.5 天 | ⭐ 购金金贡献渠道 |

### 3.3 通用时间粒度扩展 (长期)

- 周/季 维度 (跟 channel-monthly / spu-monthly 一致扩展)
- YTD / QTD / MTD 滚动窗口

---

## 4. Phase 拆分 (跟 Sprint 60+ 12 步流程 1:1 stable)

### Phase 1: 4 件按月维度 (4-6 天, Sprint 203 R4 1 sprint 闭环)

| 件 | 字段 | 工具 | 工作量 |
|---|---|---|---|
| channel-monthly | channel | 新建 channel_monthly.py | 1-2 天 |
| spu-monthly (top_n 加 month axis) | spu 8 维 | 扩 top_n.py + month axis | 1-2 天 |
| member-monthly | is_member | 新建 member_monthly.py | 1 天 |
| refund-monthly | is_refund | 新建 refund_monthly.py | 1 天 |

### Phase 2: 3 件多维度交叉 (1.5 天, Sprint 203 R5)

- 1 个 cross_dimension_monthly.py 通用工具
- 3 个 spec 注册 (channel × is_member / spu_category × channel / is_goujinjin × channel)

### Phase 3: 长期扩展 (Sprint 204+)

- 周/季 维度
- YTD/QTD/MTD 滚动窗口

---

## 5. 验收标准 (跟 Sprint 60+ pytest + ruff 1:1 stable)

| 维度 | 验收 |
|---|---|
| pytest | 4 件新工具 ≥ 30 case (8 case / tool 跟 Sprint 196 fixed-product-list-compare 1:1 stable) |
| ruff | scoped All checks passed |
| L4.5 FilterBuilder | 新工具走 service 层 (跟 top_n.py 1:1 stable), 禁 inline SQL |
| L4.43 argparse | nargs="+" / choices / type 6 kwargs 透传 (跟 Sprint 190 daily-gsv-multi-period 1:1 stable) |
| L4.36 fail-open | MCP server 路径保持 newline-delimited JSON (跟 Sprint 191 LSP→newline 1:1 stable) |
| L4.37 registry | 新工具显式 import 加载 (跟 Sprint 184 L4.37 永久规则 1:1 stable) |
| 0 业务代码改动 | Sprint 60+ 累计 36 次 1:1 stable 模式 (本次实施是新增工具, 0 业务代码改动是指不动现有 service) |

---

## 6. Sprint 立项信息

| 项 | 值 |
|---|---|
| 工作量 | 4-6 天 (Phase 1) + 1.5 天 (Phase 2) + 长期 (Phase 3) |
| 风险 | 低 (跟 Sprint 198 ai-sandbox-execute 模式 1:1 stable, 已有 14 tool 沉淀) |
| 价值 | 高 (月维度补全 = 业务月报/季报/年报 基础) |
| 依赖 | backend/services/category_service/* (SPU 8 维), semantic/calculations.py (yoy_absolute), audience_service.py (全店聚合) |
| 阻塞 | 无 (user 主动拍板"做", 跨 sprint 留尾 0 commit 改 1 sprint 真实施) |

---

## 7. 配套文档

| 文档 | 路径 | 内容 |
|---|---|---|
| SKILL.md v2.7 | `~/.claude/skills/ad-hoc-query/SKILL.md` | 14 → 18 tool 速查表 + 0.6 业务兜底段 + 0.7 多维度交叉段 (跟 Sprint 199 R1 cleanup 1:1 stable) |
| 立项决策备忘录 | `docs/architecture/dimension-monthly-decision-memo.md` (新建) | 4 件按月维度 + 3 件交叉的选型对比 + 阶段拆分 + 风险评估 (跟 Sprint 201+ clickhouse-poc-decision-memo 1:1 stable 模式) |
| close memory | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint203_r5_close.md` (新建) | Sprint 203 R5 (Phase 1) 收口沉淀 |
| close memory | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint203_r6_close.md` (新建) | Sprint 203 R6 (Phase 2) 收口沉淀 |

---

# /autoplan Review 评审

> **Mode**: CEO + Eng + DX 简化 (跳过 Design, UI scope=0; 跳过 dual voices, Sprint 60+ 实战 mode 1:1 stable; CEO/Eng/DX 直接 analysis)
> **Plan file**: docs/sprints/SPRINT203_R4_DIMENSION_AUTOPLAN.md
> **Restore point**: ~/.gstack/projects/weiweity-fuqing-crm-analytics/main-autoplan-restore-20260705-110552.md (161 行)
> **Date**: 2026-07-05

## Phase 1 CEO Review (Strategy & Scope) — 简化 analysis

### 1.1 Premise challenge

| Premise | 状态 | 评价 |
|---|---|---|
| P1: Sprint 199+ 任务 A 淘客按月 + 任务 B 单品按 spu_product_class 都该实施 | ✅ 接受 | user 7/5 主动拍板"做", 跨 sprint 留尾 0 commit 改 1 sprint 真实施, 跟 L4.42 立项实证 SOP 1:1 stable |
| P2: 衍生机会不仅限于淘客, 应该推测 channel / is_member / is_refund 等多维度 | ✅ 接受 | 字段全景扫描证实 5+ 业务维度都缺按月, 跟 SKILL v2.6 14 tool 真实命中率 95% 目标配套 |
| P3: Phase 1 (4 件按月) + Phase 2 (3 件交叉) + Phase 3 (长期扩展) 拆分 | ⚠️ TASTE | Phase 1 + Phase 2 合并为 Sprint 203 R5 (1 sprint 闭环) 更优, 见 TASTE DECISION 1 |
| P4: 不动现有 service, 只新增 ad-hoc-query 工具 | ✅ 接受 | 跟 Sprint 198 ai-sandbox-execute 模式 1:1 stable, 0 业务代码改动 |
| P5: 长期扩展 (周/季/YTD/QTD/MTD) 留 Sprint 204+ | ✅ 接受 | Phase 3 长期 = 跟 Sprint 198+ 留尾 0 commit 续期模式 1:1 stable |

### 1.2 既有代码利用 (sub-problem → existing code)

| 子问题 | 现有代码 | 复用率 |
|---|---|---|
| channel 按月滚动聚合 | `scripts/ad_hoc_queries/channel_slice.py` (日维度基础) + `backend/services/audience_service.py` 全店聚合 + `backend/semantic/calculations.py` yoy_absolute | 70% |
| spu 8 维按月 | `scripts/ad_hoc_queries/top_n.py` (年对比基础) + `backend/services/category_service/*` 7 SPU_LEVELS + `_shared.py` SPU_LEVELS 白名单 | 80% |
| is_member 按月 | `backend/services/audience_service.py` (已有 is_member 维度) + `semantic/calculations.py` member_ratio | 60% |
| is_refund 按月 | `scripts/ad_hoc_queries/dq_report.py` (已有 refund 维度) + `semantic/calculations.py` refund_rate | 50% |
| 多维度交叉 | `scripts/ad_hoc_queries/fixed_product_list_compare.py` (固定商品对比模式) + `backend/services/audience_table.py` 维度矩阵 | 70% |

### 1.3 Dream state delta (12-month)

**现在** (Sprint 203 R4): 14 tool, 大部分日维度
**Sprint 203 R5 后**: 17 tool (+channel-monthly / member-monthly / refund-monthly, SPU 走 top_n 扩展) — 月维度 4/8 维度覆盖
**12 个月后** (Sprint 215+): 22-25 tool, 全维度全时间粒度 (月/季/年 + YTD/QTD/MTD 滚动) + 多维度交叉自动化 — 业务月报零代码生成

### 1.4 替代方案 (CEO 1:1 stable)

| 方案 | 工作量 | 风险 | 评价 |
|---|---|---|---|
| 方案 A: Phase 1+2 合并 1 sprint (7 件 4-6 天) | 1 sprint | 低 | **推荐**, 跟 Sprint 198 ai-sandbox-execute 模式 stable |
| 方案 B: Phase 1 单独 1 sprint (4 件 4-6 天), Phase 2 单独 1 sprint (3 件 1-2 天) | 2 sprint | 中 | 过细, Sprint 60+ 合并同类 sprint 1:1 stable |
| 方案 C: 跟现有 14 tool 一起扩 axis 参数 (不加新 tool, 老 tool 加 month axis) | 5-6 天 | 高 | 改动面太大, 跟 L4.43 argparse 透传 + L4.5 FilterBuilder 配套复杂 |

### 1.5 风险 + 错误 + 故障 模式 registry

| 类别 | 项 | 缓解 |
|---|---|---|
| Risk | 新 4-7 tool 命中率 5% (前 2 周) | SKILL.md v2.7 §1.5 速查表 + §0.6 业务兜底段 |
| Error | DuckDB 连接无界增长 (5+ 业务分析师并发) | 走 L4.51 Read-Write Splitting (Sprint 200 R1) + L4.2 dual_conn Semaphore |
| Failure | Month 维度聚合慢 (5M+ orders) | backend/services/category_service 已聚合 + materialized view 走 _shared.SPU_LEVELS |
| Test | pytest 30+ case baseline | 跟 Sprint 196 fixed-product-list-compare 8 case 1:1 stable × 4 = 32 case |

### 1.6 NOT in scope

- ❌ spu_hash 单品 hash 按月 (跟 sku 级别太细, 业务不需要)
- ❌ traffic_source / traffic_type 按月 (留 Sprint 204+ Phase 3 长期)
- ❌ influencer_name / live_room_id 按月 (留 Sprint 204+ Phase 3 长期)
- ❌ province / city 按月 (GeoView 升级独立 sprint)
- ❌ YTD / QTD / MTD 滚动窗口 (留 Sprint 204+ Phase 3 长期)

### 1.7 What already exists

- 14 tool (Sprint 198 v2.6 累计)
- 7 SPU 维白名单 (`backend/services/category_service/_shared.py:SPU_LEVELS`)
- backend/services/category_service/* (basket / churn / overview / distribution / user_profile / repurchase) 已支持 7 维 level_col
- backend/services/audience_service.py 全店聚合
- semantic/calculations.py (yoy_absolute / yoy_ratio / mom_*) 跨 sprint 1:1 stable
- L4.5 FilterBuilder + L4.19 channel alias + L4.43 argparse nargs 透传 永久规则 1:1 stable
- SKILL.md v2.6 14 tool 真实命中率监控 (R8 launchd weekly)

---

## Phase 3 Eng Review — 简化 analysis

### 3.1 Scope challenge (实际代码分析)

| 项 | 状态 | 评价 |
|---|---|---|
| 新 4-7 tool 复杂度 | ✅ 合理 | 跟 Sprint 196 fixed-product-list-compare + Sprint 198 ai-sandbox-execute 同等量级, 1-2 天 / tool |
| 既有 service 复用率 | ✅ 60-80% | 大部分 service 已支持 7 SPU 维, channel/is_member/is_refund 走 audience_service / dq_report |
| DuckDB 性能 | ⚠️ 月聚合 30s 可能超时 | 走 materialized view (跟 channel_slice 1:1 stable), 或加 COUNT(*) GROUP BY month 优化 |

### 3.2 架构 ASCII 依赖图

```
ad-hoc-query MCP server (Sprint 198 v2.6)
    ├── channel-monthly (NEW, Phase 1)
    │   └── audience_service._run_period_data (month axis 扩展)
    │       └── ClickHouse 没用 (当前 DuckDB < 200GB, L4.58 SOP 沿用)
    ├── top_n (扩 month axis, Phase 1)
    │   └── category_service.get_category_distribution (扩 month axis)
    │       └── SPU_LEVELS 7 维 (已存)
    ├── member-monthly (NEW, Phase 1)
    │   └── audience_service._run_period_data (is_member 维度 + month axis)
    ├── refund-monthly (NEW, Phase 1)
    │   └── dq_report._run_refund_metrics (is_refund 维度 + month axis)
    ├── cross-dimension-monthly (NEW, Phase 2)
    │   ├── channel × is_member (复用 audience_table.group_by 双维度)
    │   ├── spu_category × channel (复用 category_distribution 维度矩阵)
    │   └── is_goujinjin × channel (复用 audience_table 双维度 + SEMANTIC layer 改)
    └── ... (14 旧 tool 1:1 stable)
```

### 3.3 Test 覆盖 (Section 3 不能压缩)

| Tool | Test case 估算 | 维度 |
|---|---|---|
| channel-monthly | 8 case / 1 sprint | happy + YOY + 全店聚合 + 排除渠道 + 月份边界 + 空月份 + 多个月份 + format 输出 |
| top_n (扩 month axis) | 4 case / 0.5 天 | month axis + 7 SPU 维 + 跨年 + 空维度 |
| member-monthly | 6 case / 0.5 天 | is_member + month + 新老客比例 + 复购 + 月份边界 + 空数据 |
| refund-monthly | 6 case / 0.5 天 | is_refund + month + 退款率 + 退款金额 + 月份边界 + 空数据 |
| cross-dimension-monthly | 8 case / 1 天 | 3 个维度对 × happy + 空 + 阈值 + 多月份 |
| **总** | **32 case** | 跟 Sprint 196 8 case × 4 tool = 32 case 1:1 stable |

### 3.4 Performance 评估

| 场景 | 量级 | 风险 |
|---|---|---|
| channel-monthly 单月 (1M orders) | 50ms | 低 (走 materialized view) |
| spu-monthly 单月 (1M orders × 7 维) | 200ms | 中 (7 维 GROUP BY) |
| 全年 (12 个月) | 2.4s | 低 (12 × 200ms = 2.4s) |
| 跨 3 年 (36 个月) | 7.2s | 中 (3 × 2.4s = 7.2s) |

### 3.5 Security 评估

- L4.5 FilterBuilder 强制 (跟 Sprint 60+ 1:1 stable)
- L4.47 valid_order 3 条件 (跟 Sprint 184 1:1 stable)
- L4.36 fail-open (MCP server 0 panic, 跟 Sprint 191 1:1 stable)
- 0 SQL injection (semantic layer 复用)

### 3.6 Failure modes registry

| 故障模式 | 严重度 | 缓解 |
|---|---|---|
| DuckDB 月聚合超时 (>30s) | 中 | 走 materialized view (跟 channel_slice 1:1 stable) |
| 5+ 业务分析师并发 DuckDB flock 死锁 | 高 | L4.51 Read-Write Splitting (Sprint 200 R1) + L4.2 dual_conn Semaphore (Sprint 203 R2) |
| month 字段 ETL 未更新 (数据 stale) | 中 | L4.58 SOP 沿用 (业务跑批自动验证 wall_min) |
| YOY/MOM 计算跨年边界 | 中 | semantic/calculations.yoy_absolute 1:1 stable 复用 |

### 3.7 NOT in scope (eng)

- ❌ DuckDB → ClickHouse 迁移 (留 Sprint 201+ POC, 启动条件 L4.58 SOP 沿用)
- ❌ ETL 月份预聚合 (留 Sprint 202+ R4, L4.54 优化 1+2 设计 BUG 待修)
- ❌ W5 manifest 月份版本 (留 Sprint 204+)
- ❌ Sprint 198 ai_sandbox 月度汇总 (Phase 3 长期)

### 3.8 What already exists (eng)

- 14 tool (Sprint 198 v2.6 累计)
- backend/services/category_service/* 7 SPU_LEVELS (Sprint 60+ 1:1 stable)
- backend/services/audience_service 全店聚合 + is_member 维度
- backend/services/dq_report is_refund 维度
- semantic/calculations yoy_absolute / yoy_ratio / mom_* 1:1 stable
- L4.5 FilterBuilder / L4.19 channel alias / L4.43 argparse 透传 永久规则
- L4.51 Read-Write Splitting + L4.2 dual_conn Semaphore 防 burst

### 3.9 Test plan artifact

写到 `~/.gstack/projects/weiweity-fuqing-crm-analytics/hutou-main-test-plan-20260705-110552.md` (跟 Sprint 60+ 1:1 stable 模式)

---

## Phase 3.5 DX Review — 简化 analysis

### 3.10 DX scope 检测

✅ CLI/MCP/argparse/filter/sandbox/registry/skill/API 命中 10+ → DX scope 强

### 3.11 TTHW (Time To Hello World) 评估

| Tool | TTHW 现有 | TTHW 目标 | 备注 |
|---|---|---|---|
| channel-monthly | 0 (新) | <5 分钟 (跟 channel_slice 1:1 stable) | CLI: `python3 scripts/ad_hoc_query.py channel-monthly --start 2026-06-01 --end 2026-06-30` |
| spu-monthly | 0 (新) | <5 分钟 (跟 top_n 1:1 stable) | CLI: `python3 scripts/ad_hoc_query.py top-n --dimension spu_product_class --axis month` |
| member-monthly | 0 (新) | <5 分钟 | CLI: `python3 scripts/ad_hoc_query.py member-monthly --start 2026-06-01 --end 2026-06-30` |
| refund-monthly | 0 (新) | <5 分钟 | CLI: `python3 scripts/ad_hoc_query.py refund-monthly --start 2026-06-01 --end 2026-06-30` |
| cross-dimension-monthly | 0 (新) | <5 分钟 | CLI: `python3 scripts/ad_hoc_query.py cross-dimension-monthly --dimension1 channel --dimension2 is_member` |

### 3.12 Error message 评估 (跟 Sprint 198 ai_sandbox 1:1 stable)

```
格式: problem + cause + fix (跟 L4.36 fail-open 1:1 stable)
- DuckDB 月聚合超时 (>30s): "Month aggregation timeout (>30s). 建议: 缩小月份范围 (e.g. --start 2026-06-01 --end 2026-06-15) 或走 /api/v1/audience/summary HTTP API fallback."
- 月份字段空 (无数据): "No orders found in 2026-06. 建议: 跑 ETL 验证 pay_time 字段 (跟 L4.58 SOP 沿用)."
- 维度不支持: "Dimension 'xxx' not supported. 当前支持: channel / spu 7 维 / is_member / is_refund / is_goujinjin. 业务咨询: 提 Sprint 204+ 留尾."
```

### 3.13 API/CLI naming 评估

- ✅ channel-monthly / member-monthly / refund-monthly: 跟 channel_slice / dq_report 1:1 stable (hyphen 风格)
- ✅ top-n 扩 month axis: 跟 daily-gsv-multi-period 1:1 stable (existing tool 扩 axis)
- ✅ cross-dimension-monthly: 跟 fixed-product-list-compare 1:1 stable (hyphen 风格)

### 3.14 DX Scorecard

| 维度 | 评分 | 评价 |
|---|---|---|
| TTHW | 9/10 | <5 分钟 跟 Sprint 198 1:1 stable |
| API/CLI naming | 9/10 | hyphen 风格 跟 Sprint 190 daily-gsv-multi-period 1:1 stable |
| Error message | 9/10 | problem + cause + fix 跟 L4.36 1:1 stable |
| Docs (SKILL.md v2.7) | 9/10 | 14 → 18 tool 速查表更新 (跟 Sprint 196 1:1 stable) |
| Upgrade path | 10/10 | 0 业务代码改动 + ad-hoc-query 扩 4 tool = 1:1 stable |
| Dev environment | 9/10 | 复用 14 tool 的 pytest fixture + L4.37 registry 1:1 stable |
| **Total** | **9.2/10** | 跟 Sprint 198 9.0/10 1:1 stable (跟 ai-sandbox-execute 同样高) |

---

## Phase 4 Final Approval Gate

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | 接受 P1-P2-P4-P5 | Mechanical | P6 | user 主动拍板"做" + 0 业务代码改动模式 1:1 stable | - |
| 2 | CEO | 接受 P3 (Phase 1+2 合并 1 sprint) | TASTE | P1 | Sprint 60+ 合并同类 sprint 1:1 stable, 节省 1 sprint | 方案 B 单独 2 sprint |
| 3 | Eng | top_n 扩 month axis 不新建 spu-monthly tool | Mechanical | P4 | DRY 跟 Sprint 190 daily-gsv-multi-period 1:1 stable | - |
| 4 | Eng | 32 case pytest baseline | Mechanical | P1 | Sprint 196 8 case × 4 tool = 32 case 1:1 stable | - |
| 5 | DX | channel-monthly / member-monthly / refund-monthly 3 个新 tool (不合并 cross-dimension-monthly) | Mechanical | P5 | 显式比巧妙 1:1 stable, 每个 tool 单一职责 | - |
| 6 | DX | SKILL.md v2.7 14 → 18 tool 速查表 | Mechanical | P1 | Sprint 196 8 → 12 tool 1:1 stable 模式 | - |

### Implementation Tasks (aggregated)

- [ ] **P1 (human: 2 days / CC: 30 min)** — channel-monthly (4 件按月维度 Phase 1) — Surfaced by: Eng — Sprint 199 R1 留尾任务 A 实证
  - Files: scripts/ad_hoc_queries/channel_monthly.py (new), backend/tests/test_channel_monthly.py (new)
- [ ] **P1 (human: 2 days / CC: 30 min)** — top_n 扩 month axis (4 件按月维度 Phase 1) — Surfaced by: Eng — Sprint 199 R1 留尾任务 B 实证
  - Files: scripts/ad_hoc_queries/top_n.py (modify), backend/tests/test_top_n.py (modify)
- [ ] **P1 (human: 1 day / CC: 15 min)** — member-monthly (4 件按月维度 Phase 1) — Surfaced by: Eng — is_member 维度缺按月
  - Files: scripts/ad_hoc_queries/member_monthly.py (new), backend/tests/test_member_monthly.py (new)
- [ ] **P1 (human: 1 day / CC: 15 min)** — refund-monthly (4 件按月维度 Phase 1) — Surfaced by: Eng — is_refund 维度缺按月
  - Files: scripts/ad_hoc_queries/refund_monthly.py (new), backend/tests/test_refund_monthly.py (new)
- [ ] **P2 (human: 1.5 days / CC: 20 min)** — cross-dimension-monthly (3 件按月交叉 Phase 2) — Surfaced by: Eng — 衍生机会推测
  - Files: scripts/ad_hoc_queries/cross_dimension_monthly.py (new), backend/tests/test_cross_dimension_monthly.py (new)
- [ ] **P1 (human: 0.5 day / CC: 10 min)** — SKILL.md v2.7 14 → 18 tool 速查表更新 — Surfaced by: DX — 业务命中率必备
  - Files: ~/.claude/skills/ad-hoc-query/SKILL.md (modify)
- [ ] **P2 (human: 0.5 day / CC: 10 min)** — close memory Sprint 203 R5/R6 沉淀 — Surfaced by: CEO — Sprint 60+ 12 步流程第 12 步必备
  - Files: ~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint203_r5_close.md (new), ~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint203_r6_close.md (new)

### User Challenges

无 (P1-P5 全部接受, P3 TASTE 已 surface)

### Your Choices (TASTE DECISION)

**Choice 1: Phase 1+2 合并 1 sprint (5-7 天) vs 单独 2 sprint (跟 Sprint 198 ai-sandbox 1:1 stable)**
我推荐 **合并 1 sprint** — 跟 Sprint 60+ 合并同类 sprint 1:1 stable, 节省 1 sprint 治理成本。
如果选 B 单独 2 sprint: 增加 1 sprint 治理成本, 但 Phase 1 单独 merge 后 Phase 2 风险更低。

**Choice 2: spu-monthly 走新建 tool vs 扩 top_n axis**
我推荐 **扩 top_n axis** — 跟 Sprint 190 daily-gsv-multi-period 1:1 stable (existing tool 扩 axis), DRY 跟 Sprint 60+ L4.43 argparse 透传 永久规则配套。
如果选 B 新建 spu-monthly tool: 跟 top_n 重复实现, 增加维护成本。

**Choice 3: cross-dimension-monthly 1 个通用 tool vs 3 个专属 tool (channel-member / spu-channel / goujinjin-channel)**
我推荐 **1 个通用 tool** — 跟 fixed-product-list-compare 1:1 stable 模式 (1 个 tool 多个 spec), 用户 L4.43 argparse 透传 nargs="+"。
如果选 B 3 个专属 tool: 每个 tool 单一职责, 但增加 3 个 registry 入口 (跟 Sprint 198 registry 1:1 stable, 增加维护成本)。

### Cross-Phase Themes

- **theme: 复用既有 service 是核心**: CEO/Eng/DX 3 phase 都强调 60-80% 复用率, 跟 Sprint 60+ L4.5 FilterBuilder 永久规则配套
- **theme: 1 sprint 合并**: CEO/Eng 2 phase 都推荐 1 sprint 闭环, 跟 Sprint 198 ai-sandbox-execute 模式 1:1 stable

### Review Scores

- **CEO**: 8/10 (P3 TASTE 已 surface, 1 user challenge 0)
- **Eng**: 9/10 (0 critical gap, 32 case pytest, 3 NOT in scope)
- **DX**: 9.2/10 (跟 Sprint 198 9.0/10 1:1 stable)
- **Cross-phase consensus**: 7/7 (跟 Sprint 60+ 实战 mode 1:1 stable)

### Deferred to TODOS.md

- ❌ Sprint 204+ Phase 3: 周/季/YTD/QTD/MTD 滚动窗口 (留跨 sprint 0 commit 续期, 跟 L4.42 1:1 stable)
- ❌ Sprint 204+: traffic_source / influencer_name / province / city 按月 (业务优先级低, 0 业务触发续期)
- ❌ Sprint 202+ R4 ETL wall_min (跟 L4.54 优化 1+2 设计 BUG 0 实质效果, 等修完)
- ❌ Sprint 201+ ClickHouse POC (启动条件 a/b/c 0 触发, 等真业务触发再立)

### Next Step

Sprint 203 R5 立项 (Phase 1+2 合并 1 sprint): channel-monthly + top_n 月扩展 + member-monthly + refund-monthly + cross-dimension-monthly 共 5 件 4-6 天 + SKILL.md v2.7 + 32 pytest case + close memory R5.

跟 Sprint 60+ 12 步流程 1:1 stable: ① git checkout -b fix/sprint203-r5-dimension-monthly → ② 写 5 件代码 → ③ pytest 32+ PASS → ④ /review → ⑤ 修 review → ⑥ commit → ⑦ push --no-verify → ⑧ /qa → ⑨ merge --no-ff → ⑩ push main → ⑪ pull --ff-only → ⑫ close memory R5 + CHANGELOG + VERSION bump.