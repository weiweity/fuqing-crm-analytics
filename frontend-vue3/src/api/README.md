# API 类型使用指南

> 所有类型从 `http://localhost:8000/openapi.json` 自动生成，禁止手写类型。

## 更新类型（后端接口变更后）

```bash
cd frontend-vue3
API_URL=http://localhost:8000/openapi.json npm run gen:types
```

## 使用方式

### 1. API 调用（推荐方式）

```typescript
import { client } from '@/api/client'
import type { OverviewMetrics } from '@/api/types'

// GET 请求 — 使用 client.get()
const { data } = await client.get<OverviewMetrics>('/v1/metrics/overview', {
  params: {
    start_date: '2026-01-01',
    end_date: '2026-01-31',
    metric_type: 'GMV'
  }
})

// data 类型自动推断为 OverviewMetrics
```

### 2. POST 请求

```typescript
import { client } from '@/api/client'

const { data } = await client.post('/v1/export/ppt', {
  start_date: '2026-01-01',
  end_date: '2026-01-31'
})
```

### 3. 直接引用生成类型

```typescript
import type {
  OverviewMetrics,      // 核心指标
  AudienceTableResponse, // 人群看板
  AudienceRow,          // 人群看板单行
  TrendData,            // 趋势数据
  GeoDistributionResponse, // 地域分布
  CategorySegment,       // 品类分段
  ChurnDistribution,    // 流失分布
  RfmSegment,           // RFM 象限
  FlowMatrixResponse,   // 流转矩阵
} from '@/api/types'
```

## 已生成的类型清单

| 类型名 | 用途 |
|--------|------|
| `OverviewMetrics` | 核心指标概览 |
| `AudienceTableResponse` | 人群看板表格 |
| `AudienceRow` | 人群看板单行 |
| `TrendData` | 趋势折线图数据 |
| `GeoDistributionResponse` | 地域分布 |
| `CategoryDistributionResponse` | 品类分布 |
| `ChurnDistribution` | 流失分析 |
| `RfmSegment` | RFM 象限 |
| `FlowMatrixResponse` | 人群流转矩阵 |
| `AssetSummary` | 资产概览 |
| `ReportSummaryResponse` | 报告汇总 |

## 旧代码迁移（手写类型 → 自动生成）

### Before（手写，容易出错）

```typescript
// ❌ 字段名靠猜，IDE 不报错
export function fetchKPIMetrics(params): Promise<{
  gsv: number
  order_count: number
}> {
  return client.get('/v1/metrics/overview', { params }).then((res: any) => ({
    gsv: res.amount,  // 猜字段名
  }))
}
```

### After（自动类型，IDE 补全）

```typescript
// ✅ 类型自动，补全友好
import { client } from '@/api/client'
import type { OverviewMetrics } from '@/api/types'

const { data } = await client.get<OverviewMetrics>('/v1/metrics/overview', {
  params: { start_date: '2026-01-01', end_date: '2026-01-31', metric_type: 'GMV' }
})

// data 类型：OverviewMetrics
// IDE 自动补全：data.amount, data.new_users ...
```

## 规范

1. **禁止手写 API 返回类型** — 所有类型必须从 `types.ts` 导入
2. **修改后端接口后** — 记得 `npm run gen:types` 重新生成
3. **API 契约变更** — 通知前端更新，前端更新 types 后全量编译检查
4. **使用 client.get()** — 不要使用 useApi，项目中统一使用 client.get() 方式

## 认证机制

- Token 存储在 `sessionStorage`
- 401 响应自动触发 refresh
- 失败触发 `auth:expired` 事件

## 响应拦截器

- `client.get()` 返回的是 `response.data` 而非 AxiosResponse
- 直接使用返回值即可，无需 `.data`
