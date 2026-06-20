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
| `visitor_service.py` | (单文件) | 访客分析 |

## 关联文档

- `docs/architecture/AI_SAFETY_NET.md` — FilterBuilder pattern
- `CLAUDE.md` §"AI 写代码 typo 防御规范" L4.5