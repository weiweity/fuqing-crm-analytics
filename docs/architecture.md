# 芙清 CRM 客户分析系统 - 技术架构文档

**版本**: v1.0  
**日期**: 2026-03-27  
**架构师**: AI Engineering Team  
**状态**: 已确认

---

## 1. 架构概述

### 1.1 设计原则
1. **本地优先**：所有数据处理在本地完成，不依赖外部 SaaS
2. **高性能**：2GB 数据秒级查询响应
3. **可扩展**：模块化设计，支持 Week 1-5 渐进式迭代
4. **易维护**：代码清晰，文档完善，方便后续交接

### 1.2 技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| 数据处理 | Python + Polars | Polars 比 Pandas 快 10-50 倍，适合大文件 |
| 数据库 | DuckDB | 本地高性能分析型数据库，2GB 数据秒查 |
| 后端 API | FastAPI | 现代、异步、自动生成文档 |
| 前端界面 | Vue3 + ECharts 5 | 现代化前端，Tailwind CSS 样式，Pinia 状态管理 |
| 导出能力 | python-pptx + openpyxl | 自动生成 PPT/Excel |
| AI 能力 | OpenAI API | 自然语言查询，智能洞察 |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层 (Presentation)                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Vue3     │  │   飞书机器人  │  │  PPT/Excel  │          │
│  │   Web 界面   │  │   推送服务   │  │   导出器    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼──────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                      API 层 (FastAPI)                            │
├───────────────────────────┼─────────────────────────────────────┤
│  ┌──────────────┐  ┌──────┴──────┐  ┌──────────────┐            │
│  │  指标 API    │  │  RFM API    │  │  预测 API    │            │
│  │  /metrics    │  │  /rfm       │  │  /forecast   │            │
│  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘            │
└─────────┼─────────────────┼─────────────────┼────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                   业务逻辑层 (Services)                          │
├───────────────────────────┼─────────────────────────────────────┤
│  ┌──────────────┐  ┌──────┴──────┐  ┌──────────────┐            │
│  │ DataService  │  │ RFMService  │  │  AIService   │            │
│  │  数据查询    │  │  RFM计算    │  │  AI 问数    │            │
│  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘            │
└─────────┼─────────────────┼─────────────────┼────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                   数据访问层 (Data Access)                       │
├───────────────────────────┼─────────────────────────────────────┤
│                    ┌──────┴──────┐                              │
│                    │    DuckDB   │                              │
│                    │  分析数据库  │                              │
│                    └──────┬──────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                   数据源层 (Data Sources)                        │
├───────────────────────────┼─────────────────────────────────────┤
│  ┌──────────────┐  ┌──────┴──────┐  ┌──────────────┐            │
│  │ 店铺数据库   │  │  会员数据库  │  │  清洗后数据  │            │
│  │  (xlsx)      │  │   (xlsx)    │  │   (DuckDB)  │            │
│  └──────────────┘  └─────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流架构

### 3.1 数据清洗流程 (Week 1)

```
原始 xlsx 文件 (76个)
       │
       ▼
┌──────────────┐
│  数据读取    │  ← Polars 读取，比 Pandas 快 10-50 倍
│  (Polars)    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  数据清洗    │  ← 时间格式化、金额标准化、去重
│  (Python)    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  数据加载    │  ← 写入 DuckDB
│  (DuckDB)    │
└──────┬───────┘
       │
       ▼
清洗后的 DuckDB 数据库
```

### 3.2 查询流程

```
用户请求
    │
    ▼
FastAPI 路由
    │
    ▼
Service 层业务逻辑
    │
    ▼
DuckDB SQL 查询
    │
    ▼
返回 JSON/图表数据
```

---

## 4. 数据库设计

### 4.1 核心表结构

```sql
-- 订单主表
CREATE TABLE orders (
    order_id VARCHAR PRIMARY KEY,
    sub_order_id VARCHAR,
    user_id VARCHAR NOT NULL,
    order_time TIMESTAMP NOT NULL,
    pay_time TIMESTAMP,
    ship_time TIMESTAMP,
    order_type VARCHAR,
    order_status VARCHAR,
    product_id VARCHAR,
    product_title VARCHAR,
    sku_id VARCHAR,
    sku_name VARCHAR,
    quantity INTEGER,
    amount DECIMAL(10,2),
    refund_amount DECIMAL(10,2),
    actual_amount DECIMAL(10,2),
    province VARCHAR,
    city VARCHAR,
    source VARCHAR,
    is_member BOOLEAN,
    etl_date DATE  -- 数据导入日期
);

-- 用户汇总表（每日更新）
CREATE TABLE user_summary (
    user_id VARCHAR PRIMARY KEY,
    first_order_date DATE,
    last_order_date DATE,
    total_orders INTEGER,
    total_amount DECIMAL(12,2),
    is_member BOOLEAN,
    r_score INTEGER,  -- RFM 得分
    f_score INTEGER,
    m_score INTEGER,
    rfm_segment VARCHAR,  -- RFM 分层
    etl_date DATE
);

-- 每日指标表
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    gmv DECIMAL(12,2),
    order_count INTEGER,
    new_user_count INTEGER,
    old_user_count INTEGER,
    member_gmv DECIMAL(12,2),
    avg_order_value DECIMAL(10,2)
);
```

### 4.2 索引设计

```sql
-- 时间索引（用于时间范围查询）
CREATE INDEX idx_orders_time ON orders(order_time);
CREATE INDEX idx_orders_pay_time ON orders(pay_time);

-- 用户索引（用于用户分析）
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_user_summary_id ON user_summary(user_id);
```

---

## 5. API 设计

### 5.1 核心指标 API

```python
# GET /api/v1/metrics/overview
# 获取核心指标概览
{
    "date_range": {"start": "2025-01-01", "end": "2025-01-31"},
    "gmv": 1234567.89,
    "order_count": 1234,
    "avg_order_value": 1000.00,
    "new_users": 567,
    "old_users": 890,
    "member_gmv": 987654.32,
    "mom_change": {  # 环比
        "gmv": 0.15,
        "order_count": 0.10
    },
    "yoy_change": {  # 同比
        "gmv": 0.25,
        "order_count": 0.20
    }
}

# GET /api/v1/metrics/trend
# 获取趋势数据（用于图表）
{
    "dates": ["2025-01-01", "2025-01-02", ...],
    "gmv": [10000, 12000, ...],
    "orders": [100, 120, ...]
}
```

### 5.2 RFM API

```python
# GET /api/v1/rfm/segments
# 获取 RFM 分层结果
{
    "segments": [
        {"name": "高价值活跃", "count": 123, "gmv": 456789},
        {"name": "高价值沉睡", "count": 45, "gmv": 123456},
        ...
    ]
}

# GET /api/v1/rfm/distribution
# 获取 R/F/M 分布
{
    "recency": {"R0-30": 100, "R31-60": 80, ...},
    "frequency": {"F1": 200, "F2-3": 150, ...},
    "monetary": {"M0-100": 300, "M100-300": 200, ...}
}
```

### 5.3 AI 问数 API

```python
# POST /api/v1/ai/query
# 自然语言查询
{
    "question": "上个月新客有多少？"
}

# 返回
{
    "answer": "2025年12月新客数为 567 人",
    "sql": "SELECT COUNT(DISTINCT user_id) FROM ...",
    "data": {"new_users": 567}
}
```

---

## 6. 前端界面设计（Vue3）

### 6.1 页面结构

> **注意**：Streamlit 版本已废弃，当前前端为 Vue3 + ECharts 5，部署于 `frontend-vue3/` 目录。

### 6.2 导航结构

- **仪表盘** (Week 1): 核心指标概览
- **RFM 分析** (Week 2): 客户分层与策略
- **人群流转** (Week 3): 流转矩阵与资产
- **人群画像** (Week 4): 地域/时段/品类分析
- **缺口追踪** (Week 5): 预测与预警

---

## 7. 部署架构

### 7.1 本地部署

```
你的电脑 (Windows/Mac)
    │
    ├── Python 3.10+
    ├── DuckDB (本地数据库文件)
    ├── FastAPI (后端服务, 端口8000)
    ├── Vue3 + Vite (前端 dev server, 端口5173)
    └── 原始 xlsx 文件
```

### 7.2 启动方式

```bash
# 1. 启动后端 API（端口8000）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
~/.workbuddy/binaries/python/envs/default/bin/python backend/main.py

# 2. 启动前端 Vue3（端口5173）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3"
npm run dev

# 3. 浏览器打开 http://localhost:5173
```

---

## 8. 性能优化策略

### 8.1 数据层面
- 使用 Polars 替代 Pandas 读取大文件
- DuckDB 列式存储，查询性能优异
- 预计算每日指标，避免实时聚合

### 8.2 查询层面
- 常用查询结果缓存
- 分页加载大数据集
- 异步查询避免阻塞

### 8.3 前端层面
- 图表懒加载
- 数据按需加载
- 本地缓存配置

---

## 9. 安全设计

- **本地运行**：不对外暴露端口
- **数据隔离**：原始数据与清洗数据分离
- **访问控制**：本地使用，无需登录

---

## 10. 扩展性设计

### 10.1 数据源扩展
- 预留接口支持其他店铺数据导入
- 支持增量数据更新

### 10.2 功能扩展
- 模块化 Service 设计，方便新增分析维度
- 插件化 AI 能力，支持切换不同模型

### 10.3 部署扩展
- 当前：本地单机
- 未来：可迁移至服务器，支持多人协作
