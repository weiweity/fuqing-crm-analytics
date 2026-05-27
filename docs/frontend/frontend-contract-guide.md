# 前端契约管理指南

## 目标

消除"前端调用后猜字段格式"的问题，实现 100% 类型安全。

---

## 方案：OpenAPI → TypeScript 自动生成

### 1. 安装工具

```bash
cd frontend-vue3
npm install -D openapi-typescript
```

### 2. 配置生成脚本

在 `frontend-vue3/package.json` 的 `scripts` 中添加：

```json
{
  "scripts": {
    "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts"
  }
}
```

### 3. 生成类型

确保后端已启动（`python backend/main.py`），然后执行：

```bash
npm run gen:api
```

### 4. 在前端使用

```typescript
// src/api/types.ts 自动生成，不要手动修改
import { components, paths } from "@/api/types";

// 使用 components 获取 Schema 类型
type AudienceRow = components["schemas"]["AudienceRow"];
type OverviewMetrics = components["schemas"]["OverviewMetrics"];

// 使用 paths 获取 API 路径类型（用于封装 axios/fetch）
type OverviewResponse = paths["/api/v1/metrics/overview"]["get"]["responses"]["200"]["content"]["application/json"];
```

### 5. Axios 封装示例

```typescript
// src/api/client.ts
import axios from "axios";
import type { paths } from "@/api/types";

const api = axios.create({ baseURL: "http://localhost:8000" });

// 泛型封装，自动获得路径、参数、返回类型
export async function get<T extends keyof paths>(
  url: T,
  params?: paths[T]["get"]["parameters"]["query"]
): Promise<paths[T]["get"]["responses"]["200"]["content"]["application/json"]> {
  const { data } = await api.get(url, { params });
  return data;
}

// 使用
import { get } from "@/api/client";

const metrics = await get("/api/v1/metrics/overview", {
  start_date: "2026-01-01",
  end_date: "2026-01-31",
  metric_type: "GSV",
});
// metrics 自动带有 amount, order_count, avg_order_value... 的类型和提示
```

---

## 契约变更流程

当后端新增/修改 API 时：

1. 后端修改 `backend/contracts/schemas.py`
2. 后端重启服务
3. 前端执行 `npm run gen:api`
4. TypeScript 编译器会自动检查前端代码中是否有类型不匹配
5. 修复编译错误，提交 PR

---

## 禁止事项

- ❌ 手写 `interface` 来"猜测"后端返回格式
- ❌ 使用 `any` 接收 API 返回数据
- ❌ 后端变更 API 后不更新 `schemas.py`
