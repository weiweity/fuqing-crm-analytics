# Week 1 完成报告

**日期**: 2026-03-28 ~ 2026-03-31
**项目**: 芙清 CRM 客户分析系统
**状态**: ✅ 已完成（含代码审查修复）

> **⚠️ 前端更新（2026-04-16）**：Streamlit 前端已迁移至 Vue3（`frontend-vue3/`），以下内容中的前端描述为当时状态。

---

## 完成内容

### 1. 环境搭建
- [x] Python 3.12 环境确认
- [x] 核心依赖安装 (pandas, duckdb, fastapi, ~~streamlit~~→Vue3, plotly)
- [x] 项目目录结构创建

### 2. 数据管道
- [x] 数据探索：发现数据结构为按年份组织的文件夹
- [x] ETL 管道完成：76个店铺数据文件 + 7个会员文件 → 清洗 → DuckDB
- [x] 成功导入 **7,486,449** 条订单数据
- [x] 时间范围：2020-2026 (1714天)
- [x] 总 GMV：**6.22 亿元**
- [x] SPU 单品匹配（product_id + 时间窗口）
- [x] 渠道判定（关键词 + product_id 双列规则）
- [x] 会员标识（通过文件来源标记 is_member）

### 3. 核心指标 API
- [x] GMV 计算
- [x] 新老客分析（以 2025-01-01 为基准）
- [x] 会员分析（GMV / 订单数 / 渗透率）
- [x] 同环比计算
- [x] 每日趋势数据

### 4. 前端界面
> **已更新**：Streamlit 已迁移至 Vue3（frontend-vue3/）

- [x] ~~Streamlit~~ Vue3 页面框架
- [x] 时间范围选择器
- [x] GMV/订单数/客户数/客单价卡片
- [x] 趋势图展示
- [x] 会员指标卡片

### 5. 代码审查与修复（Team 模式）
- [x] 3 个 P0 修复（API 不匹配 / N+1 查询 / 表结构不同步）
- [x] 2 个 P1 修复（删除半成品文件 / 统一硬编码路径）
- [x] 1 个 P2 修复（中文标识符改英文）
- [x] 自动化定时审查：每周一/三/五 9:00

---

## 数据统计

| 指标 | 数值 |
|------|------|
| 总订单数 | 7,486,449 |
| 总 GMV | ¥622,098,865 |
| 用户数 | 3,269,121 |
| 时间跨度 | 2020-2026 (1714天) |

### 2026年1月示例数据
| 指标 | 数值 |
|------|------|
| GMV | ¥11,894,032 |
| 订单数 | 108,338 |
| 新客数 | 75,465 |
| 老客数 | 20,409 |
| 环比变化 | +28.95% |
| 同比变化 | +4.2% |

---

## 代码审查修复详情

### 🔴 P0 修复（阻塞级，已修）

| # | 问题 | 修复文件 | 修复方案 |
|---|------|---------|---------|
| 1 | FastAPI Pydantic 模型与 metrics_service 返回值字段名不匹配 | `backend/main.py` | `OverviewMetrics` 和 `TrendData` 字段名对齐 service 返回值 |
| 2 | N+1 查询（calculate_new_old_users 对每个用户单独 SQL） | `backend/services/metrics_service.py` | 改为单条 SQL CTE（period_users + all_time_first） |
| 3 | database.py 和 run_etl.py 表结构不同步 | `backend/database.py` | 以 run_etl.py 为准：+user_nickname, +channel, -etl_date, spu_detail→spu_product_subclass |

### 🟡 P1 修复（建议级，已修）

| # | 问题 | 修复文件 | 修复方案 |
|---|------|---------|---------|
| 4 | data_loader.py 是未完成的半成品 | 已删除 | 功能已被 run_etl.py 完全覆盖 |
| 5 | DUCKDB_PATH 硬编码在 3 处 | metrics_service.py, ~~frontend/app.py~~ | 统一从 `backend.config` 导入 |

### 💭 P2 修复（改进级，已修）

| # | 问题 | 修复文件 | 修复方案 |
|---|------|---------|---------|
| 6 | config.py 中文标识符 | `backend/config.py` | `MEMBER_BASE_DATE`, `classify_new_old_user()` |

### 审查中发现的待修项（未修，留给后续）

| # | 优先级 | 问题 | 建议 |
|---|--------|------|------|
| 7 | P1 | parquet COPY 无去重能力（增量 ETL 需唯一索引） | 加 `CREATE UNIQUE INDEX ON orders(order_id, sub_order_id)` |
| 8 | P1 | CSV 渠道规则列名硬编码（按位置索引） | 改为按列名映射 |
| 9 | P2 | 渠道规则写死 ETL，无法高频调整 | 四阶段重构方案阶段二 |

---

## 当前文件结构

```
fuqing-crm-analytics/
├── backend/
│   ├── __init__.py
│   ├── config.py              # 配置（路径 / 基准日期 / 新老客判定）
│   ├── database.py            # DuckDB 表结构（与 run_etl.py 同步）
│   ├── main.py                # FastAPI 后端（Pydantic 已对齐）
│   └── services/
│       ├── __init__.py
│       └── metrics_service.py # 核心指标（N+1 已消除，路径已统一）
├── frontend-vue3/            # Vue3 前端（Streamlit 已迁移至此处）
├── scripts/
│   ├── explore_data.py        # 数据探索
│   ├── quick_explore.py       # 快速数据探索
│   ├── run_etl.py             # ETL 管道（主数据流）
│   ├── test_api.py            # API 测试
│   └── verify_system.py       # 系统验证
├── data/
│   └── processed/
│       └── fuqing_crm.duckdb  # 数据库 (~2GB)
├── docs/
├── requirements.txt
├── WEEK1-REPORT.md            # 本报告
├── README.md
└── start-all.bat / start-frontend.bat / run-etl.bat  # Windows 启动脚本
```

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 数据处理 | Python + Pandas + DuckDB | Polars 已弃用（data_loader.py 已删除） |
| 后端 | FastAPI + Pydantic | 模型已对齐，可启用 |
| 前端 | ~~Streamlit + Plotly~~ → Vue3 + ECharts 5 | 已迁移 |
| 导出 | python-pptx + openpyxl | Week 4 使用 |

---

## 数据库表结构

### orders（32列）

```
order_id, sub_order_id, user_id, user_nickname,
order_time, pay_time, ship_time,
order_type, order_status,
product_id, merchant_code, product_title,
sku_id, sku_code, sku_name,
quantity, amount, refund_status, refund_amount, actual_amount,
province, city,
influencer_name, influencer_id, live_room_id, video_id,
traffic_source, traffic_type, seller_note,
year, month, is_member,
spu_category, spu_type, spu_tier, spu_product_class, spu_product_subclass,
spu_cosmetic, spu_spec,
channel
```

### daily_metrics（每日预计算指标）

### spu_mapping（SPU 单品匹配规则）

### user_summary（用户汇总，当前为空表）

---

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 新老客基准日期 | 2025-01-01 | 此日期前有订单为老客 |
| 数据年份范围 | 2025-2026 | config.py YEAR_RANGE |
| 数据库路径 | data/processed/fuqing_crm.duckdb | 统一从 config 导入 |

---

## 启动方式

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
# 后端（端口8000）
~/.workbuddy/binaries/python/envs/default/bin/python backend/main.py
# 前端（端口5173）
cd frontend-vue3 && npm run dev
# 浏览器打开 http://localhost:5173
```

---

## 四阶段重构计划（Week 2+）

| 阶段 | 内容 | 状态 |
|------|------|------|
| 一 | DuckDB 规则表 + 断点表 + 增量 ETL | ⏳ 待开始 |
| 二 | 渠道规则查询时计算 | ⏳ 待开始 |
| 三 | 增量 ETL + 中断续跑 | ⏳ 待开始 |
| 四 | polars 读 Excel（可选提速） | ⏳ 待开始 |

---

## 五周总计划

| 周次 | 主题 | 核心交付 | 状态 |
|------|------|---------|------|
| Week 1 | 核心指标看板 | GMV/新老客/会员/同环比 | ✅ 已完成 |
| Week 2 | RFM 模型 | 客户分层、618 人群包 | 🔜 下一步 |
| Week 3 | 人群流转 | 流转矩阵、资产分析 | ⏳ 待开始 |
| Week 4 | 人群画像 | 地域/时段/品类分析、PPT导出 | ⏳ 待开始 |
| Week 5 | 缺口追踪 | 预测、预警、每日推送 | ⏳ 待开始 |

---

## 自动化

- **代码审查**: 每周一/三/五 9:00 自动执行（审查 SQL 注入 / N+1 / 硬编码 / 表结构一致性）

---

**Week 1 完成！准备进入 Week 2: RFM 模型与 618 决策**
