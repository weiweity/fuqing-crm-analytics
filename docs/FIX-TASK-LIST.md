# 芙清 CRM 代码质量修复任务清单

> **归档状态：全部完成，本文档已归档**
>
> 生成日期: 2026-05-31
> 审查日期: 2026-05-31 (/autoplan review)
> 归档日期: 2026-05-31
> 总计任务: 17 项
> 预估总工作量: 37-54 小时
> 状态: **已完成** — 全部 17 任务执行完毕

---

## 第一阶段：安全问题修复（P0）

### 1. [P0] 替换弱密码并实现密码哈希存储

- [x] **涉及文件**: `.env`, `backend/auth/password.py`(新建), `backend/routers/auth.py`
- **问题描述**: `admin:123456` 和 `fqsw:fqsw888` 为极弱密码，且密码以明文存储
- **修复步骤**:
  1. 新建 `backend/auth/password.py`，使用 **bcrypt**（不是 SHA-256）实现 `hash_password()` 和 `verify_password()`
  2. 生成强密码替换弱密码
  3. `.env` 中 `FQ_CRM_PASSWORDS` 改为哈希格式
  4. 修改认证逻辑调用 `verify_password()`
  5. 更新 `.env.example` 中的格式说明
- **验证**: `pytest backend/tests/ -v` — 149 passed
- **预计工作量**: 3-4 小时

### 2. [P0] 重新生成 HEALTH_API_KEY

- [x] **涉及文件**: `.env`
- **问题描述**: HEALTH_API_KEY 明文存储，强度不足
- **修复步骤**:
  1. 执行 `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` 生成新密钥
  2. 替换 `.env` 中的值
- **预计工作量**: 0.5 小时

### 3+4. [P0] API Key Header 传输 + 速率限制（合并，同文件）

- [x] **涉及文件**: `backend/routers/health.py`（第 66 行、第 329-346 行）
- **问题描述**: API Key 通过 URL Query 传输 + 无速率限制
- **修复步骤**:
  1. `Query(default=None)` 改为 `Header(...)`（第 330、342 行）
  2. `_check_api_key` 中使用 `hmac.compare_digest()` 替代 `!=`（防时序攻击）
  3. 添加 `_failed_attempts` 字典和速率限制（10次/5分钟）
  4. 更新前端调用为 `X-API-Key` 请求头
- **验证**: `pytest backend/tests/ -v` — 149 passed
- **预计工作量**: 2-3 小时

### 5. [P0] 将 SQL 字符串拼接改为参数化查询

- [x] **涉及文件**: `backend/services/health/rfm_category_drilldown.py`
- **问题描述**: `exclude_channels` 和 `rfm_segment` 通过手动转义拼接 SQL
- **修复步骤**:
  1. 新建 `_build_exclude_condition()` 返回参数化子句
  2. `rfm_literal` 改为 `?` 占位符
  3. `_R_SEGMENT_CASE_WHEN` 中 `name_cn` 做转义
- **预计工作量**: 4-6 小时

### 6. [P0] 实现 DuckDB 单例连接管理

- [x] **涉及文件**: `backend/db/connection.py`, `backend/main.py`, 所有 service 层
- **问题描述**: 每次请求新建连接，无连接池
- **修复步骤**:
  1. 重写为全局单例 + `threading.Lock`（双重检查锁定）
  2. 新增 `close_connection()`
  3. `main.py` 注册 `shutdown` 事件
  4. `grep -r "conn.close" backend/` 找到所有关闭调用，逐一移除
  5. 代码注释说明单线程限制（DuckDB 单连接，适合当前 ~10 并发用户）
- **验证**: `pytest backend/tests/ -v` — 149 passed
- **预计工作量**: 2-3 小时

---

## 第二阶段：性能问题修复（P1）

### 7. [P1] 合并 overview.py 的 9 次独立查询为 3 次

- [x] **涉及文件**: `backend/services/metrics/overview.py`（第 183-231 行）
- **问题描述**: 3 个时间段各 3 次查询，共 9 次
- **修复步骤**:
  1. 新建 `_query_period()` 单次返回全部指标
  2. 用 CTE 合并查询逻辑
  3. 复用同一连接
- **预计工作量**: 4-6 小时

### 8. [P1] 合并 geo_service.py 的循环查询为 2 条 SQL

- [x] **涉及文件**: `backend/services/geo_service.py`（第 405-452 行）
- **问题描述**: 按月循环执行 SQL，N 次查询
- **修复步骤**:
  1. `DATE_TRUNC('month')` 一次性查出所有月份
  2. Python 字典映射替代循环
- **预计工作量**: 3-4 小时

### 9. [P1] 用 groupby 替换 flow_service.py 的 N*N 过滤

- [x] **涉及文件**: `backend/services/flow_service.py`（第 264-271 行、第 370-376 行）
- **问题描述**: 121 次 DataFrame 全量过滤
- **修复步骤**:
  1. `groupby(["from_segment", "to_segment"]).size()` 一次性聚合
  2. 向量化操作计算留存/升级/降级
- **预计工作量**: 2-3 小时

### 10. [P1] 为 churn_service.py 添加时间窗口

- [x] **涉及文件**: `backend/services/churn_service.py`（4 个函数）
- **问题描述**: 全表扫描 + `LAG()` 窗口函数
- **修复步骤**:
  1. 添加 `lookback_start = analysis_date - timedelta(days=730)`
  2. WHERE 中添加 `AND o.pay_time >= ?`
- **预计工作量**: 3-4 小时

---

## 第三阶段：架构问题修复（P2）

### 11. [P2] 消除 Router 层对 semantic 层的直接导入

- [x] **涉及文件**: 9 个 router 文件, `backend/services/__init__.py`
- **问题描述**: 违反分层架构
- **修复步骤**:
  1. 在 `backend/services/__init__.py` 中 re-export `check_future_date` 和 `PeriodBuilder`（不新建文件）
  2. 9 个 router 文件改为 `from backend.services import check_future_date`
  3. `health.py` 的 `RFM_THRESHOLDS, SEGMENTS` 改为从 `backend.services.health.config` 导入
- **验证**: `pytest backend/tests/ -v` — 149 passed
- **预计工作量**: 2-3 小时

### 12. [P2] 统一 `_normalize_date` 函数

- [x] **涉及文件**: `backend/semantic/time.py`, 3 个 service 文件
- **问题描述**: 3 处重复定义，1 处缺兜底
- **修复步骤**:
  1. `semantic/time.py` 添加 `normalize_date()`
  2. 3 个文件改为导入
- **预计工作量**: 1 小时

### 13. [P2] 统一 `_segment_meta` 函数

- [x] **涉及文件**: `backend/semantic/segments.py`, 2 个 service 文件
- **问题描述**: 2 处重复定义
- **修复步骤**:
  1. 移入 `semantic/segments.py`
  2. 2 个文件改为导入
- **预计工作量**: 0.5 小时

### 14. [P2] 统一 `_VALID_BASE` 常量

- [x] **涉及文件**: `backend/semantic/filters.py`, 6 个 service 文件
- **问题描述**: 6 处重复定义
- **修复步骤**:
  1. `semantic/filters.py` 定义 `VALID_ORDER_BASE`
  2. 6 个文件改为导入
- **预计工作量**: 1-2 小时

### 15. [P2] 提取 RFM flow 通用引擎

- [x] **涉及文件**: `backend/services/rfm/` 3 个文件 + 新建 `_flow_engine.py`
- **问题描述**: r_flow/f_flow/m_flow 约 1128 行，90% 重复
- **修复步骤**:
  1. 新建 `_flow_engine.py` 提取通用函数
  2. 3 个文件简化为配置 + 调用（~60 行/个）
- **预计工作量**: 6-8 小时

### 16. [P2] 将 suggestions.py 硬编码常量迁移到语义层

- [x] **涉及文件**: `backend/services/breakdown_service/suggestions.py`, `semantic/segments.py`, `semantic/calculations.py`
- **问题描述**: R_INTERVALS 名称不一致，GSV 口径硬编码
- **修复步骤**:
  1. `R_INTERVALS` 统一到 `semantic/segments.py`
  2. `GSV_AMOUNT_COL` 移入 `semantic/calculations.py`
  3. `REPURCHASE_ADJUSTMENT` 移入配置文件
- **预计工作量**: 2-3 小时

### 17. [P2] 注册应用关闭事件

- [x] **涉及文件**: `backend/main.py`
- **问题描述**: 未注册 shutdown 事件
- **修复步骤**:
  1. 导入 `close_connection`
  2. 添加 `@app.on_event("shutdown")`
- **预计工作量**: 0.5 小时

---

## 进度跟踪

| 阶段 | 任务数 | 预估工时 | 完成数 |
|------|--------|----------|--------|
| 第一阶段：安全 (P0) | 5 | 12-18 小时 | 5/5 |
| 第二阶段：性能 (P1) | 4 | 12-17 小时 | 4/4 |
| 第三阶段：架构 (P2) | 7 | 13-19 小时 | 7/7 |
| **合计** | **16** | **37-54 小时** | **16/16** |

> 注：原任务 3+4 已合并（同文件修改），总任务从 17 降为 16

---

## 依赖关系

```
任务 6（单例连接） ──> 任务 7（合并 overview 查询）
                  ──> 任务 10（churn 时间窗口）

任务 5（参数化 SQL）──> 任务 14（统一 _VALID_BASE）

任务 14（统一 _VALID_BASE）──> 任务 15（RFM flow 引擎）
任务 12（统一 _normalize_date）──> 任务 15
任务 13（统一 _segment_meta）──> 任务 15

任务 11（Router 分层）──> 任务 16（suggestions 常量迁移）
```

建议按依赖顺序执行：先完成被依赖的任务，再处理下游任务。

---

## /autoplan Review Report

> 审查时间: 2026-05-31
> 审查工具: /autoplan (CEO + Eng review pipeline)
> 审查决策: 8 项自动决策，0 项用户挑战

### 关键发现

1. **任务 1 使用 bcrypt 而非 SHA-256** — auth.py 已有 bcrypt 依赖，保持一致
2. **任务 3+4 合并** — 同文件修改，避免合并冲突
3. **任务 6 添加 grep 步骤** — 确保不遗漏 `conn.close()` 调用
4. **任务 11 使用 services/__init__.py** — 不新建 validators.py 文件
5. **所有任务添加 pytest 验证** — 149 passed 作为回归基线
6. **无测试计划** — 原计划缺少测试要求，已补充验证步骤

### 待办事项（TODOS）

| # | 事项 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | HTTP 缓存（ETag/Cache-Control） | P3 | 前端性能优化，非阻塞 |
| 2 | 全局请求超时/限流中间件 | P3 | 系统稳定性，非阻塞 |
| 3 | Async service 函数 | P3 | 高并发优化，当前规模不需要 |
| 4 | DuckDB 连接池（高并发） | P3 | 当前单例足够，~10 用户 |

### 验证命令

每个任务完成后执行：
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

预期结果：149 passed / 8 skipped
