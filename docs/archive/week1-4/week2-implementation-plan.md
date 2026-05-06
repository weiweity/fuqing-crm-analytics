# Week 2 RFM 模型实施计划

**版本**: v1.0
**日期**: 2026-03-31
**状态**: Team 设计完成，待实施

---

## 1. 决策点：两种评分方案对比与选择

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **NTILE(5) 百分位分箱**（rfm-calculations） | 数据驱动，不受极值影响，自动化 | 阈值不直观，业务解释成本高 | 数据分布稳定，长期运营 |
| **固定阈值分箱**（rfm-segmentation-strategy） | 阈值直观，业务可解释、可配置 | 受极值影响，需人工维护 | 业务口径明确，需人工干预 |

**建议采用：双模式并存**
- **默认模式**：NTILE(5) 百分位分箱（自动、数据驱动）
- **业务模式**：固定阈值（业务可配置，通过 YAML 调整）

前端同时支持两种模式切换。

---

## 2. RFM 定义（统一）

| 维度 | 定义 | 计算 |
|------|------|------|
| **R** | 最近一次购买距分析日的天数 | `分析日 - MAX(pay_time)` |
| **F** | 分析周期内有效订单数 | `COUNT(DISTINCT order_id)` |
| **M** | 分析周期内累计消费金额 | `SUM(actual_amount)` |

- **默认分析周期**：90 天（日常运营）
- **618 大促周期**：180 天（覆盖去年双11至今年618）
- **分析基准日**：可配置（默认当天）

---

## 3. DuckDB 表设计

```sql
-- RFM 预计算表
CREATE TABLE IF NOT EXISTS user_rfm (
    user_id            VARCHAR,
    user_nickname      VARCHAR,
    analysis_date      DATE,           -- 分析日期
    metric_type        VARCHAR,        -- 'GMV' 或 'GSV'
    lookback_days       INTEGER,       -- 回顾天数
    recency_days       INTEGER,       -- R 原始值
    frequency          INTEGER,        -- F 原始值
    monetary           DECIMAL(12,2), -- M 原始值
    r_score            TINYINT,       -- R 分值 1-5
    f_score            TINYINT,       -- F 分值 1-5
    m_score            TINYINT,       -- M 分值 1-5
    rfm_tier           VARCHAR,       -- 人群标签（中文）
    rfm_tier_en        VARCHAR,       -- 人群标签（英文）
    segment_id         TINYINT,       -- 象限编号 1-8
    first_order_date   DATE,
    last_order_date    DATE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, analysis_date, metric_type, lookback_days)
);

CREATE INDEX IF NOT EXISTS idx_rfm_tier ON user_rfm(rfm_tier);
CREATE INDEX IF NOT EXISTS idx_rfm_date ON user_rfm(analysis_date, metric_type);
```

---

## 4. 8 象限分层（统一命名）

| 象限ID | 命名 | R | F | M | 贡献价值 |
|--------|------|---|---|---|---------|
| 1 | 钻石会员 | 4-5 | 4-5 | 4-5 | 高 |
| 2 | 潜力新贵 | 4-5 | 1-3 | 4-5 | 高 |
| 3 | 忠实金主 | 1-2 | 4-5 | 4-5 | 中 |
| 4 | 频次买家 | 1-2 | 4-5 | 1-3 | 中 |
| 5 | 豪气新客 | 4-5 | 1-3 | 4-5 | 中 |
| 6 | 清新路人 | 4-5 | 1-3 | 1-3 | 低 |
| 7 | 沉睡土豪 | 1-2 | 1-3 | 4-5 | 中 |
| 8 | 流失用户 | 1-2 | 1-3 | 1-3 | 低 |

---

## 5. 实施任务分解

### Phase A：基础设施（Day 1）
- 创建 `user_rfm` 表 → `database.py`
- YAML 策略配置 → `strategy_config.yaml`

### Phase B：计算层（Day 1-2）
- `calculate_rfm_scores()` - 百分位模式 + 固定阈值模式
- `get_rfm_distribution()` - 象限统计
- `refresh_rfm_table()` - 预计算表刷新
- `calculate_618_rfm()` - 618 版
- `add_campaign_tags()` - 618 专项标签

### Phase C：导出层（Day 3）
- `export_segment_packages()` - 人群包导出
- Excel 多 Sheet 格式（分象限、618专项）
- 618 人群包导出

### Phase D：前端层（Day 4-5）
> **已废弃 Streamlit**：当前前端为 Vue3 + ECharts 5，原 `frontend/` 已迁移至 `frontend-vue3/`

- Vue3 RFM 页面（5个Tab）
- RFM 分布图表（3D散点/热力图/直方图）
- 象限矩阵图（8色编码）
- 象限策略卡片
- 人群导出组件
- 与现有 `frontend-vue3/` 集成

### Phase E：联调测试（Day 5）
- RFM SQL 与 DuckDB 验证
- 象限人数/GMV 交叉核对
- Excel 导出格式核验
- 性能测试（采样方案）

---

## 6. 文件清单（Week 2 新增/修改）

```
backend/services/rfm_service.py   [新增] RFM 计算核心服务
backend/database.py               [修改] 添加 user_rfm 表创建

frontend-vue3/src/views/           [修改] RFM 分析页面
frontend-vue3/src/components/
  rfm_charts.vue                 [新增] RFM 图表组件
  rfm_strategy.vue               [新增] 象限策略卡片组件
  rfm_export.vue                 [新增] 导出功能组件
frontend-vue3/src/api/            [新增] RFM API 调用层

data/packages/                    [新增] 人群包导出目录
strategy_config.yaml             [新增] RFM 策略配置
```

---

## 7. ETL 重构（Week 3 前置任务）

当前痛点：渠道规则高频调整需重跑全量 ETL。

| 规则 | 当前 | 改造后 |
|------|------|---------|
| 渠道规则 | 写入 `orders.channel`，ETL 时计算 | 查询时实时计算（`channel_rules` 表） |
| SPU 规则 | 写入 `orders.spu_*` | 已有数据不变；新数据 ETL 时匹配 |

**Week 2 期间暂不改动 ETL**，聚焦 RFM 功能。ETL 重构作为 Week 3 前置。

---

## 8. 验收标准

- [ ] R/F/M 三维度得分正确（NTILE 模式 + 固定阈值模式并存）
- [ ] 8 象限分层正确，各有人群数量/GMV 统计
- [ ] 618 版 RFM（180天周期）可导出
- [ ] 618 专项标签（加购未购/收藏未购等）可计算
- [ ] Excel 人群包导出格式正确（分 Sheet、颜色标记）
- [ ] Vue3 RFM 页面各 Tab 正常展示
- [ ] 1399 万用户级别查询不超时（采样/预计算方案）
- [ ] 象限运营策略建议展示完整
