# 芙清 CRM — 契约层文档

**版本**: v3.1（2026-06-06 补 RFMVersionResponse + /api/v1/rfm/version）
**对应文件**: `backend/contracts/schemas.py`
**核心原则**: 所有 Pydantic 模型必须从 `contracts/schemas.py` 导入，禁止在 `main.py` 内联定义。

---

## 1. 契约层架构

```
backend/contracts/
├── __init__.py
└── schemas.py          # 所有 Pydantic Request/Response 模型
```

```
main.py  ──import──▶  backend.contracts.schemas
                              │
                              ├── OverviewMetrics
                              ├── AudienceTableResponse
                              ├── GeoDistributionResponse
                              ├── CategoryResponse
                              ├── ChurnResponse
                              ├── RFMSegmentResponse
                              └── ...（20+ 个模型）
```

---

## 2. 契约层验收标准

| 检查项 | 标准 |
|--------|------|
| `main.py` 无内联 Pydantic 模型 | `class XXXResponse(BaseModel)` 在 `main.py` 中出现 = 不合规 |
| `schemas.py` 覆盖全部 API | 每个 API endpoint 的 Request/Response 都在 `schemas.py` |
| OpenAPI 完整导出 | `GET /openapi.json` 返回完整 JSON |

---

## 3. 核心模型一览

### 3.1 指标概览

```python
class OverviewMetrics(BaseModel):
    gsv: float           # GSV（有效销售额，剔除退款）
    gsv_order_count: int # GSV订单数
    gmv: float           # GMV（含退款）
    order_count: int     # GMV订单数
    total_users: int     # 购买人数
    new_users: int       # 新客人数
    old_users: int       # 老客人数
    new_gsv: float       # 新客GSV
    old_gsv: float       # 老客GSV
    member_gsv: float    # 会员GSV
    member_users: int     # 会员人数
    avg_order_value: float # 客单价
    gsv_yoy: Optional[float] = None  # GSV同比
    gsv_mom: Optional[float] = None  # GSV环比
```

### 3.2 人群看板

```python
class AudienceTableResponse(BaseModel):
    columns: List[str]          # ["渠道", "GSV", "订单数", "人数", ...]
    data: List[List[Any]]       # [[达播, 123456, 234, 567], ...]
    total_gsv: float
    total_orders: int
    total_users: int
```

### 3.3 地域分布

```python
class GeoDistributionResponse(BaseModel):
    provinces: List[ProvinceStats]  # [{name: "广东", value: 123456}, ...]
    cities: Optional[List[CityStats]] = None
```

### 3.4 RFM 象限

```python
class RFMSegmentResponse(BaseModel):
    segments: List[SegmentStats]  # [{id: 1, name: "钻石会员", count: 123, gsv: 456789, color: "#FF6B6B"}, ...]
    total_users: int
    avg_r_score: float
    avg_f_score: float
    avg_m_score: float
```

### 3.5 流失分析

```python
class ChurnResponse(BaseModel):
    churn_rate: float            # 流失率
    at_risk_count: int           # 濒临流失人数
    dormant_count: int           # 已流失人数
    dynamic_threshold: int       # 动态流失阈值（天数）
    segments: List[SegmentStats] # 各象限流失分布
```

---

## 4. 前端类型自动生成

### 4.1 工作流

```
backend/main.py 运行（端口 8000）
        │
        ▼
  GET /openapi.json
        │
        ▼
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
        │
        ▼
src/api/types.ts（1786行 TypeScript 类型）
        │
        ▼
前端 Vue3 组件直接引用生成的类型
```

### 4.2 生成命令

```bash
cd /Users/hutou/Desktop/fuqin\\ date/fuqing-crm-analytics/frontend-vue3
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

> ⚠️ 前端**禁止手写** TypeScript 类型，所有类型必须从 OpenAPI 自动生成。

---

## 5. 已有模型清单

| 模型名 | 用途 | 状态 |
|--------|------|------|
| `OverviewMetrics` | 指标概览 | ✅ |
| `AudienceTableResponse` | 人群看板 | ✅ |
| `GeoDistributionResponse` | 地域分布 | ✅ |
| `GeoSegmentResponse` | 地域人群 | ✅ |
| `CategoryDistributionResponse` | 品类分布 | ✅ |
| `CategorySegmentResponse` | 品类人群 | ✅ |
| `ChurnResponse` | 流失分析 | ✅ |
| `FlowMatrixResponse` | 流转矩阵 | ✅ |
| `AssetSummaryResponse` | 资产总览 | ✅ |
| `RFMSegmentResponse` | RFM 象限 | ✅ |
| `ReportSummaryResponse` | 报告摘要 | ✅ |
| `AudienceKPIResponse` | 人群 KPI | ✅ |
| `TrendResponse` | 趋势数据 | ✅ |
| `MetricType` | 指标类型枚举 | ✅ |
| `PeriodType` | 周期类型枚举 | ✅ |
| `SegmentOption` | 象限选项 | ✅ |
| `HealthOverviewMetrics` | 老客健康概览 | ✅ |
| `RepurchaseCycleOverview` | 复购周期概览 | ✅ |
| `CohortRetentionResponse` | Cohort留存率 | ✅ |
| `ValueTierResponse` | 价值分层 | ✅ |
| `TierFlowResponse` | 梯队流转 | ✅ |
| `RFMAnalysisResponse` | RFM分析（8象限） | ✅ |
| `NewCustomerConversionResponse` | 新客转化 | ✅ |
| `PromotionCalendarResponse` | 推广日历 | ✅ |
| `ChannelHealthScoresResponse` | 渠道健康评分 | ✅ |
| `HealthTargetsResponse` | 健康目标 | ✅ |
| `ConfigHistoryResponse` | 配置历史 | ✅ |
| `ConfigRestoreResponse` | 配置恢复 | ✅ |
| `AuditLogResponse` | 审计日志 | ✅ |
| `RFMConfigResponse` | RFM配置 | ✅ |
| `RFMVersionResponse` | RFM manifest 版本（W2 配套, v0.4.8+） | ✅ |

---

## 6. RFM Version Endpoint（v0.4.8+）

> W2 manifest 原子切换后，前端 / 监控 / 测试需要能查询当前 RFM 快照版本。

### 6.1 Endpoint

```http
GET /api/v1/rfm/version
```

**Response（200）**:
```json
{
  "active_view": "user_rfm_20260605_143022",
  "version": 42,
  "ts": "2026-06-05T14:30:22+00:00",
  "path": "data/processed/manifest.json"
}
```

### 6.2 实际实现（无 Pydantic 模型，直接返回 dict）

```python
# backend/routers/rfm.py
@router.get("/version")
def get_rfm_manifest_version():
    """返回当前 active manifest 信息 (active_view / version / ts / path).
    用途:
    - 调试 ETL 跑批后 manifest 是否更新
    - W5 cache invalidate 配套 (manifest 变化触发整表失效)
    - 监控告警 (active_view 空 = ETL 还没跑过)
    """
    return get_rfm_manifest_info()  # 走 backend/services/rfm/loader.py
```

> ⚠️ 当前 main 上 `/api/v1/rfm/version` **没有** Pydantic `response_model` 包装（直接返回 dict）。W5 设计稿里规划了 `RFMVersionResponse`（含 `is_healthy` / `previous_version` / `fact_rfm_long_rows` 等字段），但 W5 未合 main。

### 6.3 用途

| 用途 | 调用方 |
|------|--------|
| 运维检查当前 RFM 快照 | `curl /api/v1/rfm/version` |
| 监控告警（ETL 跑批后） | `active_view` 空 = ETL 还没跑过 |
| 前端 cache invalidation | `version` 变化时强制刷新 TanStack Query 缓存（W5 落地后） |
| 测试断言 | 单元测试 `assert version >= 1` |
| W5 配套 | `_ManifestTracker.current_version()` 比较触发整表失效 |

### 6.4 与 W2 / W3 / W4 的协作

```python
# backend/routers/rfm.py:GET /api/v1/rfm/version
@router.get("/version")
def get_rfm_manifest_version():
    return get_rfm_manifest_info()
    # → SnapshotManifest(path).read_full() + info["path"] = str(path)
```

- **W2 配套**：`SnapshotManifest.read_full()` 走 POSIX atomic 读（< 4KB 短读原子）
- **W3 配套**：W3 quarantine 状态通过另外的 SQL 查询（`/api/v1/rfm/version` 当前不返回 `is_healthy`）
- **W4 配套**：W4 full 后可加 `fact_rfm_long_rows` 字段（当前 main 不返回）

### 6.5 测试

```python
# backend/tests/test_w2_manifest.py
def test_rfm_version_endpoint(client, tmp_path):
    # 写一个真 manifest.json
    sm = SnapshotManifest(tmp_path / "manifest.json")
    sm.write_active("user_rfm_20260605_test")
    r = client.get("/api/v1/rfm/version")
    assert r.status_code == 200
    data = r.json()
    assert data["active_view"] == "user_rfm_20260605_test"
    assert data["version"] >= 1
```
