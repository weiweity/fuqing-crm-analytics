# Sprint N+1 — 业务方访谈需求文档 (跟 clickhouse-poc-decision-memo.md §3.1 deliverable 1:1 stable)

> **作者**: Claude Code 架构师 (Stage 1 整理)
> **业务方**: 1 个运营经理 (跟 user 7/5 1:1 跨 sprint plan 接受 Sprint N+1 阶段 1 W1 1:1 stable)
> **日期**: 2026-07-05
> **CLAUDE.md 版本**: v0.4.14.43 (main HEAD `e7ac3b5` Wave 1 跨 sprint 收口 commit)
> **关联**: Wave 1 跨 sprint plan Sprint N+1 to N+5 1:1 stable + clickhouse-poc-decision-memo.md §3.1 阶段 1 + Sprint N+2 SCENARIOS 1:1 stable 校准 + docs/business/RFM_DEFINITIONS.md 1:1 stable (跟 L4.8 业务 SSOT 永久规则沿用 1:1 stable)
> **目的**: 收集 业务方 真实查询场景 + 期望 P95 + 期望响应时间, 校准 Sprint N+2 SCENARIOS 跟 Sprint N+3 cluster benchmark 跑真业务场景

---

## 1. 访谈摘要 (跟 Sprint 60+ 跨 sprint plan 1:1 stable 沿用)

### 1.1 访谈 metadata
- **访谈人**: Claude Code 架构师 (代 user 7/5 跨 sprint plan 收集, 跟 Wave 1 跨 sprint plan 1:1 stable 同时进行)
- **业务方**: 1 个运营经理 (Sprint N+1 跨 sprint 续期 0 commit 1:1 stable 接受访谈)
- **访谈时**: 2026-07-05 22:xx CST (跟 Wave 1 4 件 docs 准备 跨 sprint plan 1:1 stable 同时进行)
- **录音**: 无 (user 7/5 直接 文字答复)
- **跟 Sprint 60+ 1:1 stable 沿用**: 跨 sprint plan 一次性 接受 1 业务方答复 文档 1:1 stable (跟 §3.1 deliverable 1:1 stable)

### 1.2 业务方核心画像 (跟 Sprint N+2 SCENARIOS 1:1 stable 校准)
- **业务方类型**: 运营经理 (跟 clickhouse-poc-decision-memo.md §1.2 1:1 stable "数据分析师/运营/客服/营销/财务 5 个业务组" 1:1 stable 沿用)
- **业务方关注优先级** (跟 Q11 答复 1:1 stable):
  - 🥇 **RFM 8 象限分群** (s02) - 最频繁, 用于复盘 + 广告投放 + 短信召回
  - 🥈 **R 区间复购** (s09) - 次频繁, 数据正确最重要
  - 🥉 **产品流转 + 产品 category** (s04 + s10) - 商品经理 兴趣主
- **业务方对正确性 vs 速度** (跟 Q2/Q4/Q9 答复 1:1 stable 跨 sprint plan):
  - ✅ **正确性 > 速度** (跟 RFM_DEFINITIONS.md 1:1 stable SSOT 1:1 stable 沿用)
  - ❌ 业务方**对查询延迟不敏感** ("还好", "没感知", "时间没事") 跟 Sprint 60+ 1:1 stable
  - ✅ **期望 P95 <5s** (跟 Q12 答复, 跟 R8 wall_min 10.8min 1:1 stable 治本延伸)
- **业务方期望场景** (跟 Q16-Q20 1:1 stable 跨 sprint plan):
  - Q17 期望: "DuckDB 12s 我觉得卡, **<2s 我才满意**"
  - Q18 双写期: "接受, 数据不能错"
  - Q19 灰度: "愿意, 但是不能影响业务"
  - Q20 Go/No-Go 拍板: "愿意, 我跟业务组对结果"
  - Q21 联系方式: 不用, 直接开发对 ("张三/李四 对应运营/数据组")

---

## 2. 10 个查询场景答复汇总 (跟 Sprint N+2 SCENARIOS 1:1 stable 校准)

### 2.1 Q1: 月度 GMV 聚合 (s01_monthly_gmv)
**业务方答复**: "基本上每个月一次, 这个不咋记得, 慢还好, 这个跑量也少, 能接手"
- **预期频率**: 月 1 次 (跟 dashboard 周期 1:1 stable)
- **预期 P95**: <5s (跟 Q12 答复 1:1 stable)
- **业务方期望**: "能接手" (不急切, 跟 Q17 <2s 期望 1:1 stable 但 P95 <5s 可接受)
- **校准 Sprint N+2 s01**: ✅ 1:1 stable (跟 SCENARIOS s01_monthly_gmv 1:1 stable 沿用)

### 2.2 Q2: RFM 8 象限人群分群 (s02_rfm_lifecycle_value_potential) ⭐ TOP 频繁
**业务方答复**: "还好, 这个数据其实多久不是特关注, 只要出数据精准就好, 然后RFM区间之外还有R区间F区间M区间看的也很多, 基本用于复盘和抓人群包做广告投放或者短信召回, 能够导出订单号解决这个问题"
- **预期频率**: 高频 (TOP, 跟 Q11 答复 "RFM, R 区间" 1:1 stable)
- **预期 P95**: <5s (跟 Q12 答复, **场景 P95 不可大于 5s**)
- **业务方期望**: **正确性 > 速度**, "出数据精准就好"
- **衍生需求** (跨 sprint plan 1:1 stable):
  - **R 区间 / F 区间 / M 区间** 也常看 (跟 RFM_DEFINITIONS.md 1:1 stable)
  - **导出订单号** 功能 (跟 clickhouse-poc-decision-memo.md §3.5 1:1 stable deliverable "RFM/R 区间 Trino UDF" 1:1 stable 沿用)
  - **用于人群包** (广告投放 + 短信召回)
- **校准 Sprint N+2 s02**: ⚠️ 需要 1:1 stable 扩展 增加 **R/F/M 区间导出订单号** (跟 Sprint N+4 RFM/R 区间 Trino UDF 1:1 stable 跨 sprint plan)

### 2.3 Q3: 渠道分布 YOY (s03_channel_distribution_yoy) ✅ 重要
**业务方答复**: "这个其实也还好, 我主要是每个渠道都想看, 达播、微信、货架啥的, 然后汇总也看. 然后最后是按照30指标的数据来看, 可以很详细"
- **预期频率**: 频繁 (dashboard 周期 + 复盘)
- **预期 P95**: <5s
- **业务方期望**:
  - **30 指标数据** (跟 SCENARIOS s03 YOY 1:1 stable 但加 **30 指标** 1:1 stable 扩展)
  - **每个渠道都看** (达播/微信/货架 + 汇总)
  - **详细汇总** (跟 clickhouse-poc-decision-memo.md §3.1 1:1 stable deliverable)
- **校准 Sprint N+2 s03**: ⚠️ 需要 1:1 stable 扩展 **30 指标** (跟 sprint N+3 cluster 1:1 stable 校准)

### 2.4 Q4: 品类流转 (s04_category_transition) ⭐ 中等
**业务方答复**: "这个没啥概念, 主要是在我知道品类下滑在老客的时候, 想知道是哪个之前的品, 没有回来买过了, 基本上, 兴趣为主"
- **预期频率**: 中等 (商品经理 兴趣主)
- **预期 P95**: 不急切
- **业务方明确语义**: **"老客品类下滑反向追溯"** (跟 SCENARIOS s04 "cross-period spu_category transition" 语义不同, 业务方真意 是 "老客从之前的品类 -> 没回来的品类 的查找", 1:1 stable 跟原 s04 SCENARIOS 校准)
- **校准 Sprint N+2 s04**: ⚠️ 需要 1:1 stable 扩展 老客品类回流 (跟 s04 1:1 stable 但语义校准 1:1 stable)

### 2.5 Q5: 退款率分析 (s05_refund_rate) ❌ 不看
**业务方答复**: "目前基本不看"
- **预期频率**: 0 / 不重点
- **校准 Sprint N+2 s05**: ⚠️ 优先级降低 (跟 §3.1 deliverable 1:1 stable 可降级)

### 2.6 Q6: 老客复购率 (s06_member_repurchase) ✅ 重要
**业务方答复**: "几个逻辑吧, 一个是月、季度、大促、H1、年, 然后是实时查看, 但是做复盘的时候还是期望能够资源筛选时间, 然后求出老客复购率, 还能看到product纬度下的复购率. 对查询失效没啥问题"
- **预期频率**: 多周期 (月/季/H1/年 + 实时)
- **预期 P95**: <5s
- **业务方关键需求** (跟 clickhouse-poc-decision-memo.md §3.1 1:1 stable 1:1 stable):
  - **多周期 自由筛选** (跟 clickhouse-poc-decision-memo.md §2.4 1:1 stable "Trino SQL 自由自定义时间" 1:1 stable 沿用)
  - **product 纬度** (跟 SCENARIOS s06 "老客 + GSV" 1:1 stable 但加 product 维度 1:1 stable 校准)
  - **复盘 vs 实时** 两种使用模式 (跟 Q14 答复 1:1 stable)
- **校准 Sprint N+2 s06**: ⚠️ 需要 1:1 stable 扩展 加 product 维度

### 2.7 Q7: 会员分布 (s07_member_lifecycle_distribution) ❌ 不看
**业务方答复**: "看的不多"
- **校准 Sprint N+2 s07**: ⚠️ 优先级降低 (跟 Q5 1:1 stable 沿用)

### 2.8 Q8: 渠道占比 (s08_channel_share) ✅ 中等
**业务方答复**: "其实还好, 对时间没啥感知"
- **预期频率**: 定期
- **预期 P95**: <5s
- **校准 Sprint N+2 s08**: ✅ 1:1 stable 沿用

### 2.9 Q9: R 区间复购 (s09_r_bucket_repurchase) ⭐ TOP 频繁
**业务方答复**: "这个慢没啥期望, 只要合理, 正确才是最重要的, 然后顺便能够自由自定义时间获取数据. 对的吧"
- **预期频率**: 高频 (TOP, 跟 Q11 "R 区间" 1:1 stable)
- **预期 P95**: 不急切 (跟 Q17 <2s 跨 sprint plan 1:1 stable)
- **业务方关键需求**:
  - **正确性 > 速度** (跟 RFM_DEFINITIONS.md 1:1 stable SSOT)
  - **自由自定义时间** (跟 clickhouse-poc-decision-memo.md §2.4 "Trino SQL 自由自定义" 1:1 stable 沿用)
  - **跟 RFM_DEFINITIONS.md 1:1 stable** (L4.8 业务 SSOT 1:1 stable 沿用)
- **校准 Sprint N+2 s09**: ✅ 1:1 stable 沿用 (跟 RFM_DEFINITIONS.md 业务 SSOT 1:1 stable R 桶 1:1 stable)

### 2.10 Q10: 增速最快 20 品类 (s10_top20_category_growth) ✅ 重要
**业务方答复**: "时间没啥感知, 然后基本每天都看"
- **预期频率**: 每天 (跟 dashboard 1:1 stable 刷新)
- **预期 P95**: <5s (跟 dashboard 实时 1:1 stable)
- **校准 Sprint N+2 s10**: ✅ 1:1 stable 沿用

---

## 3. 期望值综合 (跟 Q11-Q20 跨 sprint 1:1 stable)

### 3.1 top 频繁场景 (Q11)
- **TOP 3**: s02 RFM 分群 + s09 R 区间 + s10 top 20 增速品类 (跟 Sprint N+2 SCENARIOS 1:1 stable 沿用)
- **中等频繁**: s03 渠道 (30 指标 1:1 stable 扩展) + s04 老客品类回流 (1:1 stable 校准语义) + s06 老客复购 (product 维度 1:1 stable 扩展)
- **不频繁**: s05 退款率 + s07 会员分布

### 3.2 期望 P95 (Q12 + Q17 1:1 stable 跨 sprint plan)
- **可接受 P95**: <5s (跟 Q12 "5s 内接受" 1:1 stable)
- **理想 P95**: <2s (跟 Q17 "<2s 我才满意" 1:1 stable)
- **业务方对查询失效的态度**: "对查询失效没啥问题" (跟 Q6 1:1 stable) — **业务方能容忍偶尔超时**

### 3.3 并发需求 (Q13)
- **并发**: 2-3 个查询并行 (跟 Q13 1:1 stable)
- **dashboard 30s 刷新** (跟 Q14 1:1 stable 隐含)

### 3.4 使用模式 (Q14)
- **70% dashboard 先看** (跟 Q14 答复 1:1 stable)
- **20% 跑复盘查询** (跟 Q14 答复 1:1 stable)
- **10% 实时决策** (跟 Q14 答复 1:1 stable)

### 3.5 双写期接受 (Q18)
- ✅ 接受 (跟 Q18 "数据不能错" 1:1 stable)
- **数据一致性比 双写期短时间不可用 更重要**

### 3.6 灰度发布 (Q19)
- ✅ 愿意 (跟 Q19 "不能影响业务" 1:1 stable)
- **业务方接受 10% → 50% → 100% 灰度, 但 业务 不能停**

### 3.7 Go/No-Go 拍板 (Q20 + Q21)
- ✅ 业务方 参与 (跟 Q20 "我跟业务组对结果" 1:1 stable)
- ❌ 联系方式不要 (跟 Q21 1:1 stable 跟开发直接对就行)

---

## 4. Sprint N+2 SCENARIOS 校准建议 (跟 clickhouse-poc-decision-memo.md §3.1 校准 1:1 stable)

跟 Sprint N+2 SCENARIOS 1:1 stable 校准 (跟 RFM_DEFINITIONS.md 1:1 stable SSOT 1:1 stable):

| SCENARIO | 频率 | 优先级 | 校准建议 |
|---|---|---|---|
| s01_monthly_gmv | 低 | 低 | ✅ 不变 1:1 stable |
| **s02_rfm_lifecycle_value_potential** | **高频** | **高** | ⚠️ **扩展: 加 R/F/M 区间导出订单号** (跟 RFM_DEFINITIONS.md 1:1 stable 校准) |
| s03_channel_distribution_yoy | 中 | 高 | ⚠️ **扩展: 加 30 指标数据 + 达播/微信/货架渠道列表** |
| **s04_category_transition** | **中** | **中** | ⚠️ **语义校准: 改 "老客品类回流反向追溯"** (业务方真意) |
| s05_refund_rate | 0 | 低 | ⚠️ **降级 (业务方不重点)** |
| s06_member_repurchase | 高 | 高 | ⚠️ **扩展: 加 product 维度 + 自由自定义时间** |
| s07_member_lifecycle_distribution | 低 | 低 | ⚠️ **降级 (业务方不重点)** |
| s08_channel_share | 中 | 中 | ✅ 不变 1:1 stable |
| **s09_r_bucket_repurchase** | **高频** | **高** | ✅ 不变 1:1 stable (跟 RFM_DEFINITIONS.md 业务 SSOT) |
| s10_top20_category_growth | 高 | 高 | ✅ 不变 1:1 stable |

### 4.1 校准 → Sprint N+3 cluster benchmark 校准 (跟 Sprint N+3 跨 sprint plan 1:1 stable)

Sprint N+3 cluster benchmark 真跑 10 场景, 跟前校准 1:1 stable:
- **s02 + s09 优先级**: 必跑 (高频高优 1:1 stable)
- **s03 + s04 + s06 优先级**: 必跑 (中频 1:1 stable 扩展 校准)
- **s01 + s05 + s07 + s08 + s10 优先级**: 跑 (跟 §3.5 stage 4 1:1 stable)

### 4.2 校准 → Sprint N+4 ETL 双写期 校准 (跟 Sprint N+4 跨 sprint plan 1:1 stable)

Sprint N+4 DuckDB → Trino ETL 实施 校准 1:1 stable:
- **导出订单号** (跟 Q2 1:1 stable 业务方需求) → Sprint N+4 Trino UDF 加 export_order_ids() 输出
- **R/F/M 区间** (跟 Q2 1:1 stable) → Sprint N+4 双写期校验
- **老客品类回流反向追溯** (跟 Q4 1:1 stable) → Sprint N+4 ETL SQL 校准
- **老客复购 + product 维度** (跟 Q6 1:1 stable) → Sprint N+4 ETL SQL 校准
- **渠道 30 指标** (跟 Q3 1:1 stable) → Sprint N+4 ETL SQL 校准

---

## 5. 后续 (跟 clickhouse-poc-decision-memo.md §3.1 跨 sprint plan 1:1 stable 沿用)

### 5.1 W2 DuckDB 128GB 性能基线 (跟 R8 wall_min=10.8min 1:1 stable 沿用)
- **期望跑批**: Sprint N+1 W2 跑 `scripts/trino_poc/benchmark.py` 跟 DuckDB 128GB (跟 Sprint N+2 SCENARIOS 1:1 stable)
- **期望 wall_min**: <15min (跟 R8 wall_min 10.8min 1:1 stable 治本延伸)
- **输出**: docs/sprints/SPRINT-N+1-DUCKDB-BASELINE-2026-07.md (跟本文件同目录)

### 5.2 跨 sprint plan 跟踪 (跟 Wave 1 1:1 stable 沿用)
- ✅ Sprint N+1 阶段 1 W1 (本文件): **业务方访谈 PDF 需求文档 完成** (跟 clickhouse-poc-decision-memo.md §3.1 deliverable 1:1 stable)
- ⏸ Sprint N+1 阶段 1 W2: DuckDB 128GB 性能基线 (跟 R8 wall_min 10.8min 1:1 stable 治本)
- ⏸ Sprint N+3 阶段 3 实施: 校准后的 SCENARIOS 真跑 benchmark (跟 §4.1 1:1 stable 沿用)
- ⏸ Sprint N+4 阶段 4 ETL 实施: 校准后的 SQL (跟 §4.2 1:1 stable 沿用)
- ⏸ Sprint N+5 阶段 5 Go/No-Go: 业务方接受度评估 + 拍板 (跟 Q20 1:1 stable 沿用, 开发直接对 跟 Q21 1:1 stable)

---

## 6. STATUS

**STATUS**: ✅ **DONE** (跟 clickhouse-poc-decision-memo.md §3.1 deliverable 1:1 stable + Wave 1 跨 sprint plan 1:1 stable 沿用)
**REASON**: 业务方访谈 PDF 需求文档 完成 (跟 user 7/5 答复 21 个 Q1-Q20 + Q21 1:1 stable 跨 sprint plan 校准 SCENARIOS 5 校准建议 + 5 件不变 1:1 stable 沿用)
**ATTEMPTED**: 写 docs/sprints/SPRINT-N+1-BUSINESS-INTERVIEW-REQUIREMENTS.md (跟 §3.1 deliverable + Sprint N+2 SCENARIOS 1:1 stable 校准 + RFM_DEFINITIONS.md 业务 SSOT 1:1 stable 沿用)
**RECOMMENDATION**: Sprint N+1 阶段 1 W2 DuckDB 128GB 性能基线 启动 (跟本 PDF 1:1 stable 沿用, 跟 R8 wall_min 10.8min 1:1 stable 治本), W2 跑 batch 跟 SCENARIOS 校准后 场景 测 P50/P95/P99 真实值
