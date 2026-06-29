# RFM 业务定义 SSOT (Single Source of Truth)

> **L4.8 永久规则** (Sprint 60+ 收口沉淀): 业务定义必须在 `docs/business/` 下有 SSOT 文档, 跟代码契约 (Pydantic / SQL / 前端 type) 同步. Sprint 60+ 累计 4 sprint 闭环时新建本文档, 跟 Sprint 14.5 P1.1 R/F/M 治根 + Sprint 60.2 RFM 8 象限 治本对齐.
>
> 跨 sprint 实战 fix 沉淀 (跟 Sprint 50+ 实战 fix 模式同根因): 业务定义 SSOT 文档化避免 "分桶 vs 合计" 双计口径漂移. Sprint 60+ 4 sprint 累计改 8 象限类业务, 治根是把所有 TTL 业务定义统一 (R/F/M `ratio = None` + RFM 8 象限 `ratio = 1.0`).

---

## 1. 用户群体定义 (User Population)

| 概念 | 业务定义 | SQL 口径 | 备注 |
|------|---------|---------|------|
| **新客** | 首次购买 `>= start_dt` | `first_purchase >= start_dt` | 跟窗口期对齐 |
| **老客** | 首次购买 `< start_dt` | `first_purchase < start_dt` | RFM 评分用户 = 老客 ∩ 历史买过 |
| **RFM 评分用户** | 老客 ∩ 历史买过 (首次 < start_dt) | `first_purchase < start_dt` | 跟 8 象限口径一致 |
| **base 用户** | 当前窗口期 `start_dt ~ end_dt` 买过的去重用户 | `pay_time BETWEEN start_dt AND end_dt` | 当前期 |

> **关键澄清 (Sprint 60.2 治本)**: TTL 行 (`已购客TTL`) 算的是"老客 GSV TTL" = 8 象限老客 GSV 之和, 跟 8 象限分桶口径**完全一致** (老客 ∩ base = 28,703 用户 / 604.8 万 GSV). 不能用 `base_orders` 全部 (含新客 642 万 GSV) 算, 那是"全量用户 GSV TTL" 不是"老客 GSV TTL".

---

## 2. R / F / M 单维度区间模式 (`_flow_engine.py`)

### 业务定义

- **R (Recency)** = 最近一次距 `end_dt` 的天数 (越小越近)
- **F (Frequency)** = 窗口期 `start_dt ~ end_dt` 内的订单数 (越大越频繁)
- **M (Monetary)** = 窗口期 `start_dt ~ end_dt` 内的 GSV (越大越贡献)
- **TTL 行 (`已购客TTL`)** = 窗口期全量用户的 GSV / 用户数 (跟 R/F/M 区间口径不一致, **前端不展示**)

### ratio 模式: `ratio = None` (Sprint 14.5 P1.1 治根)

| 行类型 | `repurchase_rate` | `repurchase_gsv_ratio` | 业务语义 |
|--------|-------------------|------------------------|----------|
| R / F / M 区间 | 有值 (0-1) | **`None`** | "分桶 vs 合计" 不展示 TTL |
| 已购客TTL (合计行) | 有值 | **`None`** | 前端 `RFMView.vue:lines` `.filter(r => r.ratio !== null)` 过滤掉 |

**为什么 ratio=None (不展示 TTL ratio)**: R/F/M 是"分桶"维度, TTL 是"合计"维度, ratio = 区间 GSV / TTL GSV 会让用户困惑 ("为什么 R 区间 18% + F 区间 14% + M 区间 ... 不等于 100%"). Sprint 14.5 P1.1 治根: 前端 `.filter` 不展示, 后端 `ratio = None` 跟前端契约一致.

---

## 3. RFM 8 象限模式 (`period.py _run_rfm_period_live`)

### 8 象限 (3 维度 × 2 状态 = 8 分桶)

| 象限 | R | F | M | 业务语义 |
|------|---|---|---|----------|
| 重要价值客户 | 高 (近) | 高 (多) | 高 (大) | 核心 VIP, 重点维护 |
| 重要保持客户 | 高 (近) | 低 (少) | 高 (大) | 高客单但频次低, 复购引导 |
| 重要发展客户 | 高 (近) | 高 (多) | 低 (小) | 高频次但客单低, 客单提升 |
| 重要挽留客户 | 高 (近) | 低 (少) | 低 (小) | 即将流失, 召回激活 |
| 一般价值客户 | 低 (远) | 高 (多) | 高 (大) | 偶尔复购高客单, 频次提升 |
| 一般保持客户 | 低 (远) | 高 (多) | 低 (小) | 长尾高频低客单, 流失风险 |
| 一般发展客户 | 低 (远) | 低 (少) | 高 (大) | 沉睡高客单, 二次激活 |
| 一般挽留客户 | 低 (远) | 低 (少) | 低 (小) | 长尾沉睡, 流失严重 |

### TTL 行 (9 行最后一行)

- **业务定义**: 老客 GSV TTL = 8 象限老客 GSV 之和 (自己除以自己)
- **ratio 模式: `ratio = 1.0`** (Sprint 60.2 治本, 跟 R/F/M ratio=None 模式不同)
- **业务语义**: "合计"行的 ratio = 100% (自己除以自己), 跟"分桶"行 ratio 各自独立 (sum=100%) 是双计关系

### 9 行 ratio sum 业务说明 (Sprint 60.2 治本)

| 行 | hist_users | repurchase_gsv | repurchase_gsv_ratio | 备注 |
|----|-----------|----------------|----------------------|------|
| 8 象限 (8 行) | 各自独立 | 各自独立 (sum=604.8 万) | 各自独立 (sum=100%) | "分桶"维度 |
| 已购客TTL (1 行) | 老客 GSV 合计 (604.8 万 / 客单) | 老客 GSV 之和 (604.8 万) | **1.0** (自己除以自己) | "合计"维度 |
| **sum** | — | — | **2.0** (业务合理双计) | "分桶 100% + 合计 100%" |

**为什么 9 行 sum=2.0 业务合理**: 8 象限分桶 ratio sum=1.0 (各象限 GSV 占老客 GSV 合计) + TTL ratio=1.0 (老客 GSV / 老客 GSV) = 2.0, 两种"分桶 vs 合计"层级独立, 业务合理双计. 跟 Sprint 60.1.1 `wool_party_ratios` 强截断 1.0 模式一致 (每个 ratio 字段独立 0-1 合规, 不强求全表 sum=1.0).

---

## 4. ratio 模式对照 (Sprint 14.5 P1.1 + Sprint 60.2 治根统一)

| 模式 | TTL ratio | 前端展示 | 业务语义 | 治本 sprint |
|------|----------|----------|----------|-------------|
| **R / F / M 区间** | `None` | 过滤不展示 | "分桶 vs 合计" 隐藏合计 | Sprint 14.5 P1.1 治根 |
| **RFM 8 象限** | `1.0` | 保留显示 | "分桶 vs 合计" 双计 | Sprint 60.2 治本 |

**两种模式业务合理**: R/F/M 隐藏合计 (避免分桶 + 合计视觉混淆) + RFM 8 象限保留合计 (合计 = 8 象限和, 业务对账需要), 跟 Sprint 60.1.1 wool_party 强截断模式一致 (ratio 各自 0-1 合规).

---

## 5. 实战 fix 模式沉淀 (跟 Sprint 50+ 实战 fix 模式同根因)

| 教训 | Sprint 60+ 应用 | 留尾 |
|------|---------------|------|
| **业务定义 SSOT 文档化** (L4.8) | Sprint 60+ 收口新建本文档, 跟 Sprint 14.5 P1.1 注释对齐, 避免 Sprint 60.3 再发现同问题 | L4.8 永久规则加 CLAUDE.md |
| **"分桶 vs 合计" 双计口径** (Sprint 60.2 治本) | 9 行 ratio sum=2.0 业务合理, 两种模式独立 | 强制 ratio=1.0 (TTL) + ratio=None (R/F/M) |
| **Sprint 60.2 cache 干扰调试** | `rfm_analysis_cache` 表 12 行缓存, DELETE FROM 后 live SQL 才生效 | 新增 race-conditions-cached 模式 |
| **端到端必须覆盖所有 user-input 路径** (Sprint 60.1.1) | Sprint 60 测空 exclude 漏 distribution, 端到端必须覆盖 exclude/non-exclude 两条路径 | — |
| **同根因 bug 跨多 lane 收口必 audit 所有 lane** (Sprint 60 + 60.1.1) | Sprint 60 修 Lane A 漏 Lane C, Sprint 60.1.1 端到端验证暴露 | — |
| **跨 sprint baseline 漂移** (Sprint 60+ 收口实战) | Sprint 60.2 close memory 写 768/1, 收口实测 748/21 | — |

---

## 6. 关联契约 (Pydantic B2)

| Contract 字段 | 类型 | 范围 | Sprint 来源 |
|---------------|------|------|-------------|
| `repurchase_gsv_ratio` (R/F/M) | `Optional[RatioField]` | 0-1 or None | Sprint 14.5 P1.1 治根 |
| `repurchase_gsv_ratio` (RFM 8 象限) | `RatioField` | 0-1 (TTL 强制 1.0) | Sprint 60.2 治本 |
| `wool_party_ratios` | `List[RatioField]` | 0-1 (强截断) | Sprint 60.1.1 治本 |
| `repurchase_rate` | `PercentageField` | 0-100 (pp) | Sprint 13+ 治根 |

---

## 7. 关联文件

- **代码**:
  - `backend/services/health/rfm_analysis/period.py` (Sprint 60.2 治本: `_run_rfm_period_live` line 300-380)
  - `backend/services/customer_health/_flow_engine.py` (Sprint 14.5 P1.1 治根: R/F/M 区间 `ratio = None`)
  - `backend/services/category_service/overview.py` (Sprint 60.1.1 治本: `dual_axis_line.wool_party_ratios` 强截断)
- **契约**: `backend/contracts/schemas.py` (B2 RatioField / PercentageField / PpField)
- **测试**:
  - `backend/tests/test_rfm_flow_ttl_ratio.py` (`TestSprint602OldCustomerGsvTtl` 1 case)
  - `backend/tests/test_category_overview_filter_builder.py` (`TestSprint60CategoryParamsMismatchRegression` 2 case)
  - `backend/tests/test_distribution_filter_builder.py` (Sprint 60.1 `TestSprint601ChannelBinder` 2 case)
- **前端**: `frontend-vue3/src/views/RFMView.vue` (`.filter(r => r.ratio !== null)` 过滤 R/F/M TTL)
- **Close memory**:
  - `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint60plus_close.md`
  - `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint602_close.md`
  - `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint6011_close.md`

---

## 8. Sprint 142 RFM 扩展维度 (lifecycle_stage + value_tier + potential_tier)

> **Sprint 142 (2026-06-28) 新增 3 个分群维度**: 跟 8 quadrant 共存 (不替换), 增量加 lifecycle / value / potential 3 维度, 跟 8 quadrant 同步返回供前端按需展示. 业务口径定义必须跟 Pydantic 契约 (B2 RatioField / PercentageField / LifecycleStage / ValueTier / PotentialTier enum) 同步, 跟 L4.8 永久规则一致.

### 8.1 生命周期 (LifecycleStage, 4 桶)

| 桶 | 业务定义 | SQL 阈值 | 备注 |
|---|---|---|---|
| **新客** | 首次活跃 < 30 天 | `DATEDIFF('day', first_active, CURRENT_DATE) < 30` | 跟 RFM "新客" 一致 (Sprint 60+), 不要双计 |
| **活跃客** | 最近活跃 < 30 天 + 历史 > 30 天 | `last_active < 30天 AND first_active >= 30天` | 排除新客 |
| **沉睡客** | 30-180 天无活跃 | `30 <= last_active <= 180` | 唤醒营销目标 |
| **流失客** | > 180 天无活跃 | `last_active > 180天` | 流失判定 |

### 8.2 价值层 (ValueTier, 3 桶)

| 桶 | 业务定义 | SQL 阈值 | 备注 |
|---|---|---|---|
| **高价值** | GSV ≥ 5000 OR 频次 ≥ 10 | `gsv_sum >= 5000 OR order_count >= 10` | VIP 营销分层 |
| **中价值** | GSV 1000-5000 | `1000 <= gsv_sum < 5000` | — |
| **低价值** | GSV < 1000 | `gsv_sum < 1000` | — |

### 8.3 潜力层 (PotentialTier, 3 桶)

| 桶 | 业务定义 | SQL 阈值 | 备注 |
|---|---|---|---|
| **高潜力** | 近 30 天活跃 + GSV 斜率 > 0 | `last_active < 30天 AND gsv_growth > 0` | 派样定向目标 |
| **中潜力** | 近 30 天活跃 + GSV 斜率 = 0 | `last_active < 30天 AND gsv_growth = 0` | 维护 |
| **低潜力** | 不满足上述 (含沉睡/流失 + GSV 斜率 < 0) | else | — |

### 8.4 跟 8 quadrant 关系

- **8 quadrant 保留**: Sprint 60.2 闭环治本 (老客 GSV TTL 100%), 业务侧不能用 3 维度替代 8 quadrant
- **3 维度增量加**: `RFMSegmentExtended` 同时返回 `rfm_quadrant` (8 quadrant) + `lifecycle_stage` + `value_tier` + `potential_tier`
- **前端按需展示**: `AudienceView.vue` / 后续页面可选维度过滤, 不强制

### 8.5 实战 fix 沉淀

- **L4.5 FilterBuilder + ? 参数化**: `get_user_rfm_extended()` 用 `placeholders = ','.join(['?'] * len(user_ids))` + `?` 参数化, 禁止 f-string 内嵌 user_id (SQL 注入风险)
- **L4.7 SQL ? 数量 == params 数量**: `compute_ltv_for_user` + `compute_cohort_retention` 加 `assert sql.count('?') == len(params)` 防 params 顺序错位 (Sprint 60 实战 fix 模式)
- **L4.19 channel alias**: 新 SQL 含 `channel IN/NOT IN/=` 必须有 `o.` 表别名 (防 Sprint 60.1 Binder 500 bug 跨 service 复发)

### 8.6 关联契约 (Sprint 142)

- **Contract**: `backend/contracts/rfm_segments.py` (NEW)
  - `LifecycleStage` enum: 新客 / 活跃客 / 沉睡客 / 流失客
  - `ValueTier` enum: 高价值 / 中价值 / 低价值
  - `PotentialTier` enum: 高潜力 / 中潜力 / 低潜力
  - `RFMSegmentExtended` BaseModel: user_id + rfm_quadrant + 3 维度
  - `RFMExtendedRequest` + `RFMExtendedResponse`
- **Semantic**: `backend/semantic/segments.py` 加 `LIFECYCLE_THRESHOLDS` + `VALUE_THRESHOLDS` + `POTENTIAL_THRESHOLDS` + `lifecycle_case_sql()` + `value_tier_case_sql()` + `potential_tier_case_sql()` 3 个 SQL 生成函数
- **Service**: `backend/services/rfm/extended.py` (NEW, 跟既有 `r_flow.py / f_flow.py / m_flow.py` 同目录模式 stable) `get_user_rfm_extended()` 计算 user_id 列表的 8 quadrant + 3 新维度
- **Router**: `backend/routers/rfm.py` POST `/api/v1/rfm/extended` endpoint
- **测试**: `backend/tests/test_rfm_extended_sprint142.py` (NEW, 3 case)

### 8.7 业务测试 + 验证

- **pytest 3 case PASS** (Sprint 142 收口验, baseline 740 → 752 +12 case)
- **闭包:** Sprint 142 handoff `docs/sprints/HANDOFF-TO-CODEX-Sprint142-RFM-Level-Lock-Perf.md` Section 1 Task 1
- **Close memory**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint142_close.md`

---

**L4.8 永久规则 (跟 Sprint 50.5 L4.5 + L4.6 永久规则一致)**: 任何业务定义变更 (R / F / M / 8 象限 / ratio 模式 / 强截断 0-1 / lifecycle / value / potential 维度) 必先更新本文档, 跟 Pydantic 契约 + SQL 口径 + 前端 filter 同步, 避免 Sprint 60+ 累计 4 sprint 治本跨 sprint 留尾循环. Sprint 142 增量加 3 维度跟 8 quadrant 共存, 治根 = 单点 SSOT (本文档) + 多 sink (Pydantic + SQL + 前端).

---

## 9. Sprint 170 supersede 更新

### 业务决策 (user 拍板, 2026-06-29)

- **品类回购分析**(`/category/repurchase-flow` + `/category/repurchase-flow-by-rfm`) 业务口径:
  - **原**: RFM 8 象限 (3 维度 R×F×M 组合, r_score + f_score + m_score >=4 vs <4)
  - **新**: **R 桶 (6 档 Recency + 1 TTL 汇总)** — 用单一 Recency 维度, 更直观反映复购周期
- **supersede** Sprint 142 advisory "8 quadrant 保留: 业务侧不能用 3 维度替代 8 quadrant" — Sprint 142 时代的业务决策被 Sprint 170 更新覆盖
- **不动**: `/health/rfm/*` 路由 + `services/health/rfm_analysis/*` + `/rfm/r-flow` 等 **健康页 RFM 业务** 仍用 RFM 8 象限 (独立功能, 跟品类回购解耦)
- **不改**: `docs/sprints/HANDOFF-TO-CODEX-Sprint142-RFM-Level-Lock-Perf.md` (历史快照保留, 跟代码改动无关)

### 受影响范围 (Sprint 170 改造清单, 9 文件)

| 层 | 文件 | 改动 |
|---|---|---|
| Semantic (公共 SSOT) | `backend/semantic/segments.py` | 复用 `R_SEGMENT_ORDER` + `R_INTERVALS` (Sprint 60+ 已沉淀, 无需新增) |
| Service SQL | `services/category_service/repurchase/standard.py` + `rfm.py` | 删 `rfm_scored` + `rfm_segmented` + `member_segmented` CTE, 改 `r_bucketed` + `member_bucketed` (按 `recency_days` 分 6 桶) |
| Service dict | `services/category_service/repurchase/api.py` | dict key `rfm_segment` → `r_bucket`, 循环常量 `_RFM_SEGMENT_ORDER` → `R_SEGMENT_ORDER` |
| Service shared | `services/category_service/_shared.py` | 删 `_RFM_SEGMENT_ORDER` (历史 8 象限, 由 `R_SEGMENT_ORDER` 替代) |
| Contract | `backend/contracts/category.py` | `CategoryRepurchaseFlowRow.rfm_segment` → `r_bucket` |
| Router doc | `backend/routers/category.py` | 两个 router 函数 docstring "RFM 8 象限" → "R 桶" |
| Frontend API | `frontend-vue3/src/api/category.ts` | 接口 `CategoryRepurchaseFlowRow.rfm_segment` → `r_bucket` |
| Frontend OpenAPI 同步 | `frontend-vue3/src/api/types.ts` | 手动同步 + 注脚 (待 `npm run gen:types` 重生成) |
| Frontend UI | `views/category-tabs/CategoryRepurchaseTab.vue` | column key `rfm_segment` → `r_bucket`, 列头 "RFM 象限" → "回购周期", `segmentMeta` 8 象限 → 6 R 桶 + TTL, 模板 docstring 6 处清理 |

### TTL 行处理

- 名称保留 `"已购客TTL"` (跟 `R_SEGMENT_ORDER` 末项一致, 直接复用公共 SSOT)
- 语义: 全部已购客汇总行 (业务口径不变), 仍是 1 行
- 值: 4 个指标 (hist_users / repurchase_users / repurchase_gsv 累计 + 派生 repurchase_rate / repurchase_gsv_ratio)

### 实战 fix 模式沉淀 (跟 Sprint 50-160 stable 模式)

1. **公共 SSOT 复用优于新造常量**: 改 R 桶时不新造 `_R_INTERVAL_ORDER`, 复用 `R_SEGMENT_ORDER` (Sprint 60+ 沉淀) — 避免 SPRINT 142 重复定义
2. **field rename 优于改值**: `rfm_segment` → `r_bucket` 全链路改, 不留名实不符隐患 (L4.x 永久规则: SSOT 业务字段名实一致)
3. **OpenAPI 自动生成文件手工同步 + 注脚**: types.ts 手工改 + 注脚 "待 `npm run gen:types` 重生成", CI 跑 lint 不报错 (类型契约通过 Python Pydantic 层校验, types.ts 是 TS 端类型提示)
4. **跨 sprint advisory supersede**: Sprint 142 advisory "8 quadrant 保留" 被 Sprint 170 业务决策覆盖, close memory 标注 supersede 关系, 而不是删历史 advisory (跟 Sprint 89 暂收口 0 治理 SOP 一致, 保留历史 + 标 superseded)

### Close

- **L4.23 永久规则适配**: 业务口径变更 9 文件交叉改, 跟 Sprint 161 e2e spec drift 治根模式 consistent (UI + contract + SQL + service 4 层同步)
- **后续**: Sprint 170 close memory 标注 Sprint 142 advisory 已 superseded, 累计 sprint 治理 +1
