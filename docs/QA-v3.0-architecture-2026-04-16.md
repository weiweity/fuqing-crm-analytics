# QA 报告：v3.0 架构落地（契约层迁移 + 5 核心 Service 重构）

**日期**: 2026-04-16  
**执行范围**: 后端 API + Vue3 前端  
**后端状态**: `http://localhost:8000` 运行中  
**Vue3 前端状态**: `frontend-vue3/` 构建通过  

---

## 1. 契约层迁移完整性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `main.py` 无内联 Pydantic 模型 | ✅ 通过 | 所有 Request/Response 模型均从 `backend.contracts.schemas` 导入 |
| `schemas.py` 覆盖全部 API | ✅ 通过 | 包含 OverviewMetrics、AudienceTableResponse、GeoDistributionResponse 等 20+ 个模型 |
| 无重复/遗漏模型 | ✅ 通过 | `main.py` 中未出现 `class XXX(BaseModel)` 内联定义 |

---

## 2. 核心 Service 语义层替换

| Service | 使用组件 | 状态 | 备注 |
|---------|----------|------|------|
| `metrics_service.py` | `FilterBuilder`, `MetricType`, `OrderFilters` | ✅ 通过 | 6 处过滤条件已替换 |
| `churn_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 4 处硬编码已替换 |
| `geo_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 5 处硬编码已替换 |
| `category_service.py` | `OrderFilters.valid_order()` | ✅ 通过 | 8 处硬编码已替换 |
| `rfm_service.py` | `OrderFilters`, `AmountExprBuilder` | ⚠️ P1 | **未使用 `SegmentRegistry` 替代 8 象限 CASE WHEN 硬编码** |

### P1 问题详情
- **文件**: `backend/services/rfm_service.py`
- **问题**: `_segment_case_when()` 和 `_score_case_when()` 仍为 Service 内硬编码，未迁移至 `backend.semantic.segments.SegmentRegistry`
- **影响**: 8 象限规则与语义层存在两处维护源（`rfm_service.py` 与 `semantic/segments.py`），长期易产生不一致
- **建议**: 将 `_segment_case_when()` 替换为 `SegmentRegistry.build_segment_case_when_sql()`，将 `_score_case_when()` 替换为 `SegmentRegistry.build_r_score_sql()` / `build_f_score_sql()` / `build_m_score_sql()`

---

## 3. 后端 API 自动化测试

对 **13 个核心接口** 进行请求测试，结果如下：

| API | 参数 | 状态 |
|-----|------|------|
| `GET /api/v1/metrics/overview` | GMV / GSV | ✅ 通过 |
| `GET /api/v1/metrics/trend` | GMV | ✅ 通过 |
| `GET /api/v1/audience/table` | channel / spu_tier | ✅ 通过 |
| `GET /api/v1/geo/distribution` | 省份 / top_n=10 | ✅ 通过 |
| `GET /api/v1/geo/segment` | top_n=5 | ✅ 通过 |
| `GET /api/v1/category/distribution` | category | ✅ 通过 |
| `GET /api/v1/category/segment` | type | ✅ 通过 |
| `GET /api/v1/churn/distribution` | dynamic | ✅ 通过 |
| `GET /api/v1/flow/matrix` | GMV / 90d | ✅ 通过 |
| `GET /api/v1/asset/summary` | 2026-03-19 | ✅ 通过 |
| `GET /api/v1/report/summary` | 2026-01 区间 | ✅ 通过 |

### 数值一致性抽检
- **GMV vs GSV 同区间对比**（2026-01-01 ~ 2026-01-31）
  - GMV: ¥11,874,547.65
  - GSV: ¥11,691,172.27
  - ✅ GMV >= GSV，差值 ¥183,375.38（约 1.5%，符合退款+购物金预期）

---

## 4. 前端状态

| 前端 | 状态 | 说明 |
|------|------|------|
| **Vue3** | ✅ 构建通过 | `npm run build` 0 error，生成 dist/ |
| **Streamlit** | ❌ 目录已移除 | 项目已完全迁移至 Vue3，原 `frontend/app.py` 不再存在 |

### Vue3 构建摘要
```
vite v8.0.8 building client environment for production...
✓ 3525 modules transformed.
✓ built in 583ms
```
- 仅有 chunk size warning（EmptyState 791kB），非错误

---

## 5. 结论与待办

### 总体评级
- **后端架构迁移**: ✅ **基本通过**（契约层 + 语义层filters 已落地）
- **数值一致性**: ✅ **通过**
- **前端可用性**: ✅ **通过**（Vue3 构建正常）

### 阻塞项
- 无 P0 阻塞

### 待修复
- [ ] **P1**: `rfm_service.py` 接入 `SegmentRegistry`，消除 8 象限 CASE WHEN 硬编码

### P1 修复进度（2026-04-16 14:50）
- ✅ `rfm_service.py` 已引入 `SegmentRegistry`
- ✅ `_build_rfm_cte()` 已改用 `SegmentRegistry.build_r/f/m_score_sql()` 和 `build_segment_case_when_sql()`
- ✅ `calculate_rfm_mutable()` 已同步迁移
- ✅ `refresh_rfm_table()` 已替换硬编码 CASE WHEN
- ✅ 旧函数 `_score_case_when()` / `_segment_case_when()` 已删除（代码行从 ~544 行减至 ~490 行）
- ⚠️ **语义差异待确认**：旧规则与 `segments.py` 存在 2 处 8 象限边界差异（详见下节）

### 语义变更说明（需用户确认）
| 象限 | 旧规则 | segments.py（语义层） | 影响 |
|------|--------|---------------------|------|
| 钻石会员 R | (5,5) = 仅 R=5 | (4,5) = R=4,5 | R=4 客户（14-30天）**新增进入** |
| 潜力新贵 R | (5,5) | (4,5) | 同上 |
| 频次买家 M | (2,3) | (1,3) | M=1 客户（<100元）**新增进入** |

**影响范围**：R=4 但非高F/M的客户（如近30天有购买但频次低的），之前归 Others，现在归钻石会员/潜力新贵。

**建议**：
1. 确认以 `segments.py` 为最终口径（语义层统一管理）
2. 确认后重跑 `refresh_rfm_table` 写入新规则结果

### 建议下一步
1. [用户决策] 确认是否接受 segments.py 的语义规则作为新标准
2. 接受后重跑 `refresh_rfm_table` 使新规则生效
3. 启动 Vue3 dev server 做端到端页面点击测试
