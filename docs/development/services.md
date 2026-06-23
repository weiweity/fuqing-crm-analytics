# Services 开发指南

> 新增 backend service 的 pattern + 命名规范。FilterBuilder 强制 + facade 反模式。

## 1. Service 目录结构

```
backend/services/
├── asset_focus_service/    (Sprint 55.5 rename from sample_asset_service)
├── breakdown_service/
├── category_service/       (Sprint 55.5 单文件 → 子包, __init__.py re-export)
├── health/
├── metrics/
├── rfm/
└── *.py                    (churn_service, flow_service, geo_service, sampling_service, ...)
```

**新增 service**:
- 复杂度 ≥ 3 个函数 → 建子包 `myservice/__init__.py + helpers.py + main.py`
- 复杂度 ≤ 2 个函数 → 单文件 `my_service.py`

## 2. FilterBuilder 强制 (L4.5)

新 service 函数必须用 `FilterBuilder.build()` + `?` 参数化。详见:
- `docs/architecture/AI_SAFETY_NET.md` §3
- `CLAUDE.md` L4.5 永久规则

## 3. 命名反模式 (Sprint 55.5 治根)

| ❌ 反模式 | ✅ 正例 | 教训 |
|-----------|---------|------|
| `sample_asset_service/` (误导成 demo) | `asset_focus_service/` | Sprint 55.5 rename |
| `category_service.py` + `category_service/` (单文件 + 子包重名) | 只用子包, `__init__.py` re-export | Sprint 55.5 facade 删 |

### 改名流程 (asset_focus_service rename 实战 4 步)

1. `git mv backend/services/old_name backend/services/new_name`
2. `sed -i '' 's/backend\.services\.old_name/backend.services.new_name/g' backend/routers/*.py backend/tests/*.py`
3. 全仓 `grep -rn old_name --include="*.py" --include="*.md"` 验证 0 残留
4. 1 commit per logical change, commit message 用 `refactor: rename old_name → new_name (原因)`

## 4. 14 个现有 service

| Service | 入口 | 业务领域 |
|---------|------|----------|
| `asset_focus_service` | `asset_focus_service/__init__.py` | DMP 资产聚焦 |
| `breakdown_service` | `breakdown_service/__init__.py` | 拆解分析 |
| `category_service` | `category_service/__init__.py` | 品类分析 (churn/distribution/basket/...) |
| `health` | `health/__init__.py` | 健康度指标 |
| `metrics` | `metrics/__init__.py` | 核心 metrics 计算 |
| `rfm` | `rfm/__init__.py` | RFM 分层 |
| `churn_service.py` | (单文件) | 流失率 |
| `flow_service.py` | (单文件) | 流向分析 |
| `geo_service.py` | (单文件) | 地域分析 |
| `sampling_service.py` | (单文件) | 抽样 |
| `asset_service.py` | (单文件, DMP 资产) | DMP 资产 (跟 asset_focus_service 是不同概念) |
| `export_service.py` | (单文件) | 导出 |
| `report_service.py` | (单文件) | 报告 |
| `visitor_service.py` | (单文件) | 访客分析 (数据接入 `/audience` 末尾访客段 `AudienceView.vue:1887-1958`, 无独立路由, Sprint 104 删 `/visitor` 路由别名, 后端 100% 保留) |

## §5 asset_* 服务概念边界 (Sprint 55.5 rename + Sprint 57 沉淀)

### 5.1 命名差异（避免误用）

| 服务 | 路径 | 形态 | 用途 | exports |
|------|------|------|------|---------|
| **`asset_service`** | `backend/services/asset_service.py` | 单文件 facade | DMP 资产摘要 / 趋势，全店概览口径 | `get_asset_summary`, `get_asset_trend` |
| **`asset_focus_service`** | `backend/services/asset_focus_service/` | 子包，`__init__.py` re-export | DMP 资产聚焦，7 核心单品 + 8 其他单品 | `get_store_assets`, `get_product_assets`, `get_other_product_assets` |

### 5.2 何时用哪个

- **`asset_service`**：用于概览页、经营看板、全店资产走势分析，关注的是聚合后的资产口径。
- **`asset_focus_service`**：用于 DMP 营销页、单品投放页、资产聚焦明细，关注的是具体单品集合。
- 两者名字都带 `asset`，但业务语义不同，不能把“全店摘要”误当成“单品聚焦”。
- 若需求描述里出现“总览 / 趋势 / 全店”，优先考虑 `asset_service`。
- 若需求描述里出现“核心单品 / 其他单品 / 聚焦 / 投放”，优先考虑 `asset_focus_service`。

### 5.3 调用场景示例

```python
# 场景 1: 全店资产汇总（概览页）
from backend.services.asset_service import get_asset_summary

summary = get_asset_summary(start_date="2026-06-01", end_date="2026-06-30")
# 返回: dict，通常包含 gmv / order_count / user_count / 走势数据

# 场景 2: 7 大核心单品资产聚焦（DMP 营销页）
from backend.services.asset_focus_service import get_store_assets

focused = get_store_assets(store_id="store_001", period="2026-06")
# 返回: list[dict]，包含 7 核心单品资产详情

# 场景 3: 8 个其他单品资产聚焦（DMP 营销页）
from backend.services.asset_focus_service import get_other_product_assets

other = get_other_product_assets(store_id="store_001", period="2026-06")
# 返回: list[dict]，包含 8 其他单品资产详情
```

### 5.4 rename 历史（Sprint 55.5 实战）

- 原名：`sample_asset_service/`，当时命名会让人误以为是 demo 或 sample 代码。
- 改名 sprint：Sprint 55.5（P0 命名重构）。
- commit：`bd95cd8`，对应 `refactor: rename sample_asset_service → asset_focus_service`。
- 影响：8 个文件通过 `sed` 改 import，外加 `routers/market_focus.py`、`test_dmp_asset_cache.py` 的 7 处引用，以及 `backend/README.md`。
- 验证：全仓 `grep sample_asset_service` 结果为 0 残留。
- 来源：`~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint55_5_close.md`。

### 5.5 命名混淆防御（跨 sprint 复用）

- 命名相似不代表概念相同，后续 sprint 最容易在“资产”这个词上误用。
- 典型误用是把 `asset_service.get_asset_summary` 当成单品资产聚焦接口，结果数据范围直接错位。
- 防御方式是三层一起保留：命名差异表、调用场景示例、rename 历史。
- 这不是一次性说明，而是后续新增/改造 service 时的固定检查项。
- 与 CLAUDE.md 中的 L4.5 永久规则保持一致：新 service 必须先确认口径，再补文档表格行，避免命名漂移。

## 关联文档

- `docs/architecture/AI_SAFETY_NET.md` — FilterBuilder pattern
- `CLAUDE.md` §"AI 写代码 typo 防御规范" L4.5
