# 芙清 CRM 客户分析系统

> 内部运营中台工具 · 数据驱动的客户洞察 · 每日 9 点自动推送

---

## 项目简介

芙清 CRM 客户分析系统是为芙清电商运营团队打造的内部数据中台，处理 **1030 万订单 / 410 万用户**（2020-2026）的数据规模，提供实时的客户洞察能力。

### 核心价值

- ⏰ 每日 9 点自动推送运营洞察
- 📊 口径唯一可信，改一处全局生效
- 🔍 多维度分析：老客健康 / 市场对焦 / 品类 / 人群 / 地域
- 📤 一键导出复盘数据

### 当前状态

- ✅ 语义层 / 契约层 / 服务层 / 前端 Vue3 全部上线
- ✅ 核心看板：指标概览 / 老客健康分析 / 市场对焦 / 品类 / 人群
- ✅ ETL 增量更新正常（截至 2026-04-28）

---

## 快速开始

### 启动服务

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" \
  nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend \
  >> /tmp/fuqin-crm-backend.log 2>&1 &
cd frontend-vue3 && npm run dev
```

- 后端 API: http://localhost:8000
- 前端界面: http://localhost:5173
- API 文档: http://localhost:8000/docs

### ETL 增量更新

```bash
PYTHONPATH="$(pwd)" \
  ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --update
```

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 数据处理 | Python + Pandas + DuckDB |
| 后端 API | FastAPI + Pydantic |
| 前端界面 | Vue3 + Vite + ECharts 5 + Tailwind CSS + naive-ui |
| 状态管理 | Pinia + TanStack Query |
| 语义层 | backend/semantic/（口径唯一真实数据源） |
| 契约层 | backend/contracts/schemas.py（Pydantic → OpenAPI → TypeScript） |

---

## 项目结构

```
fuqing-crm-analytics/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口
│   ├── semantic/               # 语义层（口径定义唯一来源）
│   │   ├── filters.py          # 订单过滤条件
│   │   ├── metrics.py          # 指标注册表
│   │   ├── dimensions.py       # 维度定义
│   │   ├── segments.py         # RFM 分群定义
│   │   ├── channels.py         # 渠道映射
│   │   ├── calculations.py     # 同比/占比计算
│   │   └── time.py             # 时间周期计算
│   ├── contracts/              # 契约层（Pydantic 模型）
│   │   └── schemas.py          # API 请求/响应模型
│   ├── services/               # 业务逻辑层
│   │   ├── metrics_service.py  # 指标概览
│   │   ├── health_*.py         # 老客健康分析（6 个子服务）
│   │   ├── flow_service.py     # 人群流转
│   │   ├── geo_service.py      # 地域分析
│   │   └── category_service.py # 品类分析
│   ├── routers/                # API 路由
│   ├── db/                     # 数据库连接
│   ├── cache/                  # 缓存模块
│   └── tests/                  # 单元测试
├── frontend-vue3/              # Vue3 前端
│   ├── src/
│   │   ├── views/              # 页面组件
│   │   ├── components/         # 公共组件
│   │   ├── api/                # API 调用
│   │   └── stores/             # Pinia 状态
│   └── e2e/                    # E2E 测试
├── scripts/                    # 脚本（ETL、数据生成等）
├── config/                     # 配置（健康评分、RFM 阈值等）
├── data/                       # 数据（raw/processed/parquet/cache）
├── docs/                       # 文档
│   ├── DOCUMENT-INDEX.md       # 📖 文档导航（必读）
│   ├── PRD-v3.0.md             # 产品需求文档
│   ├── 飞书版架构文档/          # 系统架构文档（7 份）
│   ├── semantic/               # 语义层设计文档
│   └── archive/                # 历史文档归档
├── designs/                    # 设计稿和截图
└── exports/                    # 导出文件
```

---

## 架构原则

1. **语义层唯一真实数据源**：口径只定义一次，禁止在 Service 中硬编码 SQL
2. **双保险过滤**：`is_refund=FALSE` 且 `order_status!='交易关闭'`
3. **契约层外置**：所有 Pydantic 模型统一从 contracts/schemas.py 导入
4. **前端只做展示**：禁止前端计算 YOY/占比等业务指标
5. **连接零泄漏**：DuckDB 连接必须 try/finally 关闭

---

## 文档导航

详细文档分类和状态请查看 [📖 文档索引](./docs/DOCUMENT-INDEX.md)

### 核心文档速查

| 文档 | 说明 |
|---|---|
| [docs/PRD-v3.0.md](./docs/PRD-v3.0.md) | 产品需求文档 |
| [docs/飞书版架构文档/00-系统总览.md](./docs/飞书版架构文档/00-系统总览.md) | 系统架构总览 |
| [docs/飞书版架构文档/07-常见问题汇总.md](./docs/飞书版架构文档/07-常见问题汇总.md) | Bug 修复记录和经验教训 |
| [docs/ai-constraints.md](./docs/ai-constraints.md) | AI 协作规范 |
| [docs/DOCUMENT-INDEX.md](./docs/DOCUMENT-INDEX.md) | 完整文档索引 |

---

## 测试

### 后端单元测试

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

当前测试覆盖：
- `test_exceptions.py` - 异常类型和 HTTP 状态码映射
- `test_segments.py` - RFM 分群注册表和阈值定义
- `test_flow_service.py` - 人群流转服务

### E2E 测试

```bash
cd frontend-vue3
npx playwright test
```

当前 E2E 覆盖：
- `customer-health.spec.ts` - 老客健康页面路由和 Tab 渲染

---

## 核心数据指标

| 指标 | 口径 |
|---|---|
| GSV | 剔除购物金 + 退款的有效订单金额 |
| GMV | 剔除购物金，含退款的订单金额 |
| 新老客 | cutoff = 查询起始日 - 1 天，此前有购买 = 老客 |
| RFM | R=最近购买天数, F=购买频次, M=消费金额 |

---

## 变更历史

| 日期 | 事件 |
|---|---|
| 2026-03-27 | 项目启动，v1.0 架构设计 |
| 2026-04-16 | v3.0 架构重构（语义层 + 契约层） |
| 2026-04-20 | Vue3 前端上线，RFM 8 象限重构 |
| 2026-04-28 | 安全加固（API Key、SQL 注入、CORS） |
| 2026-04-29 | ETL 增量更新完成，1030 万条数据 |
| 2026-05-04 | 文档整理，创建文档索引 |
