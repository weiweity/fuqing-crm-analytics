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

**L4.8 永久规则 (跟 Sprint 50.5 L4.5 + L4.6 永久规则一致)**: 任何业务定义变更 (R / F / M / 8 象限 / ratio 模式 / 强截断 0-1) 必先更新本文档, 跟 Pydantic 契约 + SQL 口径 + 前端 filter 同步, 避免 Sprint 60+ 累计 4 sprint 治本跨 sprint 留尾循环.
