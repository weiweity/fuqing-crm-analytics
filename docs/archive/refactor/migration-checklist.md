# 口径统一重构 - 迁移清单

> **最后更新**: 2026-05-04  
> **实际状态**: 大部分已完成，部分条目已过时需重新评估

---

## 已完成 ✅

- [x] 诊断所有 Service 中的硬编码口径问题
- [x] 创建 `backend/semantic/` 语义层（6 个模块：filters/metrics/dimensions/segments/channels/time）
- [x] 创建 `backend/contracts/schemas.py` 契约层
- [x] 输出架构文档 3 份 + 飞书版 7 份
- [x] 重构 `metrics_service.py` — 使用 FilterBuilder / OrderFilters（12 处引用）
- [x] 重构 `churn_service.py` — 使用 OrderFilters（9 处引用）
- [x] 重构 `geo_service.py` — 使用 OrderFilters（4 处引用）
- [x] 重构 `category_service.py` — 使用 OrderFilters / FilterBuilder（13 处引用）
- [x] `flow_service.py` — 使用语义层，无硬编码 SEGMENT_MAP
- [x] `main.py` — 从 `backend.contracts` 导入 Response 模型（1 处引用）
- [x] 前端类型生成 — `frontend-vue3/src/api/types.ts` 已存在

## 部分完成 / 需要评估 ⚠️

### P0-3: rfm_service.py 语义层迁移
- **状态**: ⚠️ 部分完成
- **已做**: 使用 `PeriodBuilder`、`calculations`、`_expand_channels`（8 处引用）
- **未做**: `_segment_case_when()` 和 `_score_case_when()` 仍在 Service 内硬编码，未迁移到 `SegmentRegistry`
- **影响**: 两处维护源（`rfm_service.py` 和 `semantic/segments.py`）
- **建议**: 将 `_segment_case_when()` 替换为 `SegmentRegistry.build_segment_case_when_sql()`

### P0-4~6: 其他 Service 硬编码残留
- **状态**: ⚠️ 仍有残留
- `category_service.py` 第 2315/2346 行：仍有内联 `is_goujinjin = FALSE AND order_status != '交易关闭' AND is_refund = FALSE`
- `rfm_service.py` 第 211/224/237 行：仍有内联 `is_goujinjin = FALSE`
- `metrics_service.py` 第 1054 行：仍有内联三条件

> **说明**: 这些硬编码与 `OrderFilters.valid_order()` 语义一致，功能上无 bug，但违反了"口径只定义一次"原则。低风险，可逐步替换。

## 待执行（按优先级）

### P1: ETL 对齐
- [ ] `scripts/run_etl.py` 中的 `clean_data()`
  - 购物金/退款判定逻辑目前不引用 `semantic/filters.py`（0 处引用）
  - ETL 是 Pandas 层，与 SQL 层的语义层设计不同，直接引用不现实
  - **建议**: 至少将判定条件常量抽到 `semantic/filters.py` 做声明式管理

### P2: API 契约迁移
- [x] `main.py` 已从 `backend.contracts` 导入 Response 模型
- [ ] 验证 `/openapi.json` 输出完整且字段正确（需启动服务后手动验证）

### P3: 前端类型生成
- [x] `src/api/types.ts` 已存在
- [ ] openapi-typescript 配置化（目前可能是手动生成）
- [ ] 选取 1-2 个页面试点替换手写类型为自动生成类型

### P4: 验收
- [x] 跑通 `backend/main.py` + 前端构建（已在运行中）
- [ ] 对比重构前后 API 返回（抽样 3-5 个接口），确保数值 100% 一致
- [x] 更新 README 中的架构说明

## 测试覆盖（2026-05-04 新增）

| 测试文件 | 测试数 | 覆盖模块 |
|---|---|---|
| `test_exceptions.py` | 6 | 异常类型与 HTTP 状态码 |
| `test_segments.py` | 14 | RFM 分群注册表 |
| `test_flow_service.py` | 6 | 人群流转服务 |
| `test_calculations.py` | 38 | YOY/MOM/safe_ratio/单位转换 |
| `test_filters.py` | 27 | OrderFilters/FilterBuilder/AmountExprBuilder |
| `test_time.py` | 22 | PeriodBuilder 所有周期模式 |
| `test_channels.py` | 12 | 渠道漏斗定义和映射 |
| `test_api_integration.py` | 10 | FastAPI 集成测试（DB 存在时运行） |
| **合计** | **140** | |
