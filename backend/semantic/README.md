# Sample CRM - 语义层

查询口径的入口在 `backend/semantic/`。过滤、时间、YOY 和渠道别名由 Service 调用本层；**出数 SQL 以各 service 为准**，`metrics.py` / `dimensions.py` 注册表未接入查询。

---

## 1. YOY 计算规则（L4.81）

后端返回 **raw ratio，不 ×100**。前端 `YOYBadge` / Excel `yoy_pct` 再 ×100 展示。

### 1.1 绝对值 YOY（金额、人数、客单价等）

**公式**：`(当年 - 去年) / 去年`  
**存**：`0.25` **展示**：`+25%`  
**函数**：`yoy_absolute(cur, comp)`

### 1.2 占比/比率 YOY（老客GSV占比、会员占比等）

**公式**：当年占比 − 去年占比（百分点差，不是相除）  
**存**：`0.05` **展示**：`+5pp`  
**函数**：`yoy_ratio(cur, comp)`

### 1.3 回购率 YOY

**公式**：当年回购率 − 去年回购率  
**函数**：`yoy_repurchase_rate(cur, comp)`（与 `yoy_ratio` 同形）

---

## 2. MOM

与 YOY 相同：绝对值用除法，占比用减法；均为 raw，前端 ×100。

---

## 3. 安全除法

`safe_ratio(numerator, denominator, default=0.0)`：分母为 0 时返回默认值。

---

## 4. 前端展示

- 水平占比：存 0–1 decimal，展示 ×100 加 `%`
- 绝对值 YOY：raw ×100 加 `%`
- 占比 YOY：raw ×100 加 `pp`

---

## 5. 禁止事项

1. Service 不得自写 YOY 函数，必须调用 `calculations.py`
2. 前端不得自己算 YOY；后端返回 raw，前端只做展示换算
3. 占比 YOY 必须用减法
4. 不要把 `metrics.MetricRegistry.get_sql()` 当查询口径；品类老客 GSV 在 `category_service.overview`（`first_pay_date <` 窗口月初前一天；cutoff 当天算新客）
5. 品类看板 SQL 分组与筛选用原名；`display_name` 只用于界面/导出（catalog 撞名加 A/B）
6. `WoolPartyBreakdown` 已去掉 `type1_count`/`type2_count`/`total_count`/`type1_ratio`/`type2_ratio`，改为用户级证据分：`high_risk_count`/`mean_score`/`never_converted_count`/`converted_then_sample_count`/`sample_only_window_count`/`scored_users`/`high_risk_ratio`（`high_risk` = score≥0.70）
7. 流失表含 `mean_hazard`、`high_risk_users`、`high_risk_ratio`（hazard≥0.5）；挽回建议在 dest `display_name` 查找之后再填

---

## 6. 文件结构

```
backend/semantic/
├── __init__.py
├── calculations.py       # YOY / GSV 谓词 SSOT
├── filters.py            # FilterBuilder / OrderFilters
├── time.py               # PeriodBuilder
├── channels.py           # 漏斗与 UI↔DB 别名
├── segments.py           # RFM 8 象限与 R 桶
├── metrics.py            # 指标目录（未接入查询）
├── dimensions.py         # 维度目录（未接入查询）
├── lifetime_value.py
├── analytics_b0.py       # B0 合成样例，不走 FilterBuilder
├── analytics_channel_followup.py
├── analytics_first_purchase_path.py
├── analytics_handoff_audience.py
└── README.md
```

---

## 7. 修改记录

| 日期 | 修改内容 |
|------|---------|
| 2026-04-18 | 初始版本，统一 YOY/占比计算规则 |
| 2026-09-16 | 文档对齐 L4.81 raw YOY；8 象限；注册表标明未接入 |
