# AI 写代码 typo 防御体系 (AI Safety Net)

> 3 层全栈防御, Sprint 33 + 34.1 + 53.5 + 54 闭环。**新人加新 service / 新 endpoint / 新 spec 必读**。

## 1. 背景: 为什么需要 3 层防御

**AI 写代码特别容易出现 typo 类 bug**, 5+ 天才能发现:

| 事故 | Sprint | 根因 | 5+ 天未发现 |
|------|--------|------|-------------|
| `SamplingView.vue` 被清空 32653 → 699 字节 | 32.3 | Claude Opus 4.8 commit 时误清空 | Vite 编译错但 lazy load 跳过未引用 .vue |
| `churn.py:418` count_sql 漏 f 前缀 | 34.1 | 字符串字面量含 `{valid_sql}` 但无 f 前缀 | DuckDB ParserException 但真 SQL 执行才触发 |
| `{channel_filter}` `{exclude_filter}` 占位符漏改 | 54 | Codex Stage 2 删 `{valid_sql}` 但漏改其他 f-string 引用变量 | 真连 test 跑出 NameError |
| `expand_channels` 等 import 多 import | 55.1 | Sprint 53.5/54 加 FilterBuilder 时多 import | CI ruff F401 |

**共同根因**: 静态分析不够 (vue-tsc / ruff / DuckDB parser 都不抓), 必须 e2e / 真连接 regression test 触发。

**实战 fix 模式** (跟 Sprint 41 实战 follow-up 12 修一致):
- 1 字符 fix + lint 钩子机制防御
- "破坏 → 验证 → 恢复" 闭环验证 lint 真能抓

## 2. 3 层防线总览

```
┌────────────────────────────────────────────────────────────┐
│  L1 (Sprint 33 + 34.1 + 36-4) — 静态 lint 钩子            │
│  ├─ frontend: .vue 结构 sanity grep (<template>/<script>) │
│  └─ backend:  SQL f-string 一致性 lint (3 引号含 {var}    │
│      必须 f 前缀) 范围: backend/services + backend/scripts  │
│      + scripts/etl                                          │
│  触发: pre-commit                                             │
│  工具: .githooks/pre-commit:114-145 (frontend)              │
│        backend/scripts/check_sql_fstring_consistency.py     │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│  L2 (Sprint 50+ #S43-L2) — AST parser 升级                 │
│  工具: frontend-vue3/e2e/lint/spec-lint-l2.py             │
│        (tree-sitter-typescript) + spec-lint-l2.sh          │
│  L1 fallback 保留                                            │
│  触发: pre-commit spec-lint hook                            │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│  L3 (Sprint 53.5 → 54 闭环) — FilterBuilder 参数化         │
│  范围: backend/services/** 14 文件 100% 覆盖                │
│  规则: SQL 变量赋值禁止 f-string 内嵌用户输入              │
│  工具: backend/scripts/check_filter_builder_usage.py        │
│        (ground-truth-lint 钩子, 70 files scanned)            │
│  检测: 业务字段 (channel / category_id / level /            │
│        granularity / user_id / segment_id / min_support /  │
│        min_confidence) 是否走 ? 占位符                      │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│  L4 (流程层) — review skill 强制 + workflow 规则            │
│  L4:  SQL 三引号赋值若含 {var} 必须 f 前缀                  │
│  L4.2: 范围扩大 backend/scripts + scripts/etl                │
│  L4.3: 真连 test 必须用 monkeypatch_connection fixture       │
│  L4.4: 真连 test 必须有 _PROD_DUCKDB_AVAILABLE skipif        │
│  L4.5: backend/services 函数必须用 FilterBuilder            │
│  L4.6: worktree 跑 pytest 必须设 DUCKDB_PATH 指向主仓 db   │
│  L5.1: 治本/治标 ROI 重评决策树                              │
│  L5.2: spec 写法"环境无关"原则                               │
└────────────────────────────────────────────────────────────┘
```

## 3. L3 FilterBuilder Pattern (Sprint 54 必读)

### 3.1 Before (反例)

```python
# ❌ 错误: f-string 内嵌用户输入 → SQL 注入
def get_category_distribution(channel: str, category_id: str):
    valid_sql, _ = OrderFilters.valid_order()
    sql = f"""
    SELECT * FROM orders
    WHERE pay_time BETWEEN '{start_date}' AND '{end_date}'
      AND {valid_sql}                              # 静态三条件 OK
      AND channel = '{channel}'                    # ❌ 用户输入 f-string
      AND category_id = '{category_id}'            # ❌ 用户输入 f-string
    """
    conn.execute(sql)  # 注入风险
```

### 3.2 After (正例, FilterBuilder 强制)

```python
# ✅ 正确: FilterBuilder.build() + DuckDB ? DB-API
from backend.semantic.filters import FilterBuilder, MetricType

def get_category_distribution(channel: str, category_id: str):
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)              # 内部 valid_order 三条件
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    if category_id:
        fb.add_extra("category_id = ?", [category_id])
    where_sql, params = fb.build()

    sql = f"SELECT * FROM orders WHERE {where_sql}"
    conn.execute(sql, params)  # DuckDB DB-API 隔离注入
```

### 3.3 双 CTE 对称模式 (Sprint 54 实战 fix)

```python
# 双 CTE 各 build 一次, params 独立
current_where, current_params = _build_X_filter(start, end, channel, ...)
previous_where, previous_params = _build_X_filter(prev_start, prev_end, channel, ...)

sql = f"""
WITH current_period AS (
    SELECT * FROM orders WHERE {current_where}
),
previous_period AS (
    SELECT * FROM orders WHERE {previous_where}
)
SELECT ...
"""
conn.execute(sql, current_params + previous_params + [业务 params])
```

### 3.4 FilterBuilder API 速查

| 方法 | 用途 | 内部生成 |
|------|------|---------|
| `with_metric_type(MetricType.GSV)` | 有效订单三条件 | `metric_type='GSV'` (内部含 valid_order) |
| `with_time_range(start, end)` | 时间范围 | `pay_time BETWEEN ? AND ?` |
| `with_channels([ch])` | channel IN | `channel IN (?)` |
| `with_exclude_channels([...])` | channel NOT IN | `channel NOT IN (...)` |
| `with_member_only()` | 会员过滤 | `is_member = TRUE` |
| `with_lookback(date, days)` | 向前 N 天 | `pay_time >= ? - INTERVAL N DAY` |
| `with_segment_id(id)` | 象限筛选 | `r.segment_id = ?` |
| `add_extra("col = ?", [val])` | 业务字段兜底 | 业务字段必须用这个 |

## 4. 防御纵深: 实战 fix 模式 (跨 sprint 必读)

**Sprint 41 实战 follow-up 12 修** (CI 0→1 实战 fix) + **Sprint 55 实战 fix 4 修** (L3 闭环后 CI 实战 fix):

| Sprint | 实战 fix 次数 | 根因分布 |
|--------|---------------|----------|
| 41 | 12 follow-up | disk + npm ci + vue-tsc + uvicorn + token + spec typo + serial + 3 timeout + set -e + advisory |
| 55 | 4 follow-up | HEALTH_API_KEY (env) + F401 (8 unused import) + test_lint debug (诊断) + getpath crash (venv symlink) |

**模式 (L5.1 ROI 重评决策树)**:
```
Q1 本地能跑吗?
  ↓ NO
Q2 根因是 spec 还是环境?
  ↓ 环境 (CI runner / 硬件 / 权限)
Q3 治本 1-2 天能闭环吗?
  ↓ YES → 治本
  ↓ NO OR 不现实 → 治标 (continue-on-error / advisory)
Q4 治标会反复出现吗?
  ↓ NO (1 次性环境差异) → 治标可接受
  ↓ YES (recurring) → 留尾进 Sprint backlog
```

## 5. 防御纵深: L4 流程规则

| 规则 | 触发 | 跨 sprint 来源 |
|------|------|---------------|
| L4 | `/review` checklist: SQL 三引号含 `{var}` 必须 f 前缀 | Sprint 34.1 |
| L4.2 | 范围扩大到 backend/scripts + scripts/etl | Sprint 36-4 |
| L4.3 | 真连 test 必须用 `monkeypatch_connection` fixture | Sprint 38→53 |
| L4.4 | 真连 test 必须有 `_PROD_DUCKDB_AVAILABLE` skipif | Sprint 39 |
| **L4.5** | backend/services 函数必须用 FilterBuilder, 禁止 f-string 内嵌用户输入 | **Sprint 54** |
| **L4.6** | worktree 跑 pytest 必须设 DUCKDB_PATH 指向主仓 db | **Sprint 54** |
| L5.1 | 治本/治标 ROI 重评决策树 | Sprint 42 |
| L5.2 | spec 写法"环境无关"原则 | Sprint 43 / 50.1 |

## 6. 实战教训 (跨 sprint 复用)

1. **静态分析不够** (Sprint 32.3 / 34.1 同根因): vue-tsc / DuckDB parser 都不抓 typo 类 bug. 必须 lint 钩子扫源码层
2. **真编译/真执行才能发现** (Sprint 32.3 vite build lazy load 跳过 / Sprint 34.1 DuckDB ParserException): e2e / 真连接 regression test 触发
3. **"破坏 → 验证 → 恢复" 循环** (Sprint 24+ P3 单连接教训): 单测能 "跑通" 不证明 "抓到 typo", 必须故意改坏验证 test 真 FAIL, 再恢复验证 PASS
4. **pre-commit hook 是 commit 路径关键** (Sprint 3 P1-3 4 轮修): Sprint 33 (.vue) + Sprint 34.1 (.sql) + Sprint 53.5/54 (L3 FilterBuilder) 共同构成
5. **CI 实战 fix 1+ 次** (Sprint 41 12 follow-up / Sprint 55 4 follow-up): 治本 < 1 天 → 治本; 不现实 → 治标
6. **debug print 暴露真因** (Sprint 55.2 → 55.3): 本地复现不了 CI 错误 → 加 stderr capture → 拿到 OS-level 真因 → 治本
7. **Codex Stage 2 容易漏改 f-string 引用变量** (Sprint 54): 删 `{valid_sql}` 但 SQL 模板还引用 `{channel_filter}` / `{exclude_filter}` → Stage 3 review 必 grep `{` 全检查
8. **worktree pytest 环境隔离** (Sprint 54 L4.6): worktree 共享 .git 但不共享 `data/processed/` → 显式 `DUCKDB_PATH` 指向主仓

## 6.1 ground-truth-lint 完整指南 (L3 FilterBuilder, Sprint 54 闭环, Sprint 57 沉淀)

> 本节是 ground-truth-lint 工具链的完整使用手册, 把 Sprint 54 实战闭环 + Sprint 50+ 工具链演进沉淀, 给后续 sprint 加新 service 时直接参考。

### 6.1.1 工具链清单

| 层级 | 工具 | 扫描范围 | 验证位置 | Sprint 来源 |
|------|------|----------|----------|------------|
| **L1 backend** | `backend/scripts/check_sql_fstring_consistency.py` | `backend/services/**` + `backend/scripts/**` + `scripts/etl/**` | pre-commit | Sprint 34.1 + Sprint 36-4 |
| **L1 frontend** | `.githooks/pre-commit` grep `<template>/<script>` | `frontend-vue3/src/views/**/*.vue` | pre-commit | Sprint 33 |
| **L2 spec** | `frontend-vue3/e2e/lint/spec-lint-l2.py` (AST) + `spec-lint-l2.sh` wrapper | `frontend-vue3/e2e/specs/**/*.spec.ts` | pre-commit | Sprint 50+ + Sprint 50.1 |
| **L3 service** | `backend/scripts/check_filter_builder_usage.py` (ground-truth-lint) | `backend/services/**` 70 files | pre-commit + CI | Sprint 53.5 → Sprint 54 |
| **L1 contract** | `backend/contracts/_lint.py` | `backend/contracts/*.py` | pre-commit + CI | Sprint 17 #121 + Sprint 18 #142 |

### 6.1.2 L3 FilterBuilder 闭环度 (Sprint 54 验证)

**当前覆盖率**: **14/14 service** (Sprint 54 收口, `commit 84a7b88`)

```bash
$ python3 backend/scripts/check_filter_builder_usage.py --committed
Scanning 69 files in backend/services/...
[OK] 69/69 files use FilterBuilder.build() pattern
0 violations found.
```

**14 service 清单** (跨 sprint 实战 fix 累计):

| Service | 入口 | Sprint 闭环 | 关键改动 |
|---------|------|------------|----------|
| `metrics/overview.py` | `__init__.py` | Sprint 33-54 累计 | FilterBuilder 标准模式 |
| `health/overview.py` | `__init__.py` | Sprint 54 Lane A | `_build_filter()` helper |
| `health/conversion.py` | `__init__.py` | Sprint 54 Lane B | 双 CTE 参数化 |
| `category_service/churn.py` | `__init__.py` | Sprint 53.5 | 5 处 `{valid_sql}` → `_build_*_filter` |
| `category_service/distribution.py` | `__init__.py` | Sprint 54 Lane C | `_build_distribution_channel_filter` (Stage 3 抓 1 bug) |
| `category_service/...` (其它 9 service) | `__init__.py` | Sprint 54 Lane A/B/C 并行 | ~100 处 `{valid_sql}` 全部消除 |
| ... | ... | ... | ... |

### 6.1.3 L3 检测规则 (反例 vs 正例)

**反例** (Sprint 53.5 旧, f-string 内嵌用户输入):

```python
# ❌ WRONG: SQL 注入风险 + AI typo 5+ 天未发现
def get_category_distribution(channel: str, category_id: str):
    valid_sql, _ = OrderFilters.valid_order()
    sql = f"""
    SELECT * FROM orders
    WHERE pay_time BETWEEN '{start_date}' AND '{end_date}'
      AND {valid_sql}
      AND channel = '{channel}'              # ❌ 用户输入 f-string
      AND category_id = '{category_id}'      # ❌ 用户输入 f-string
    """
    conn.execute(sql)
```

**正例** (Sprint 54 治本, FilterBuilder + ? 参数化):

```python
# ✅ RIGHT: FilterBuilder.build() + DuckDB ? DB-API
from backend.semantic.filters import FilterBuilder, MetricType

def get_category_distribution(channel: str, category_id: str):
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    if category_id:
        fb.add_extra("category_id = ?", [category_id])
    where_sql, params = fb.build()

    sql = f"SELECT * FROM orders WHERE {where_sql}"
    conn.execute(sql, params)  # DuckDB DB-API 隔离注入
```

### 6.1.4 L3 实战 fix 模式 (5 步)

跟 Sprint 41 实战 follow-up 12 修 + Sprint 55 实战 fix 4 修模式一致:

```
1. 改前 git log 验证 (CLAUDE.md D-4 教训)
   ↓
   git log main --oneline -- backend/services/X.py  # 验证当前状态
2. 实施: 把 f-string 拼接改成 FilterBuilder.build()
   ↓
   改 where_sql 拼接 + params 独立传
3. 跑批验证 (Sprint 24+ P3 单连接教训)
   ↓
   python3 -c "from backend.services.X import Y; print(Y(...))"
4. 加回归测试 (Sprint 36.4 "破坏→验证→恢复" 模式)
   ↓
   backend/tests/test_X_filter_builder.py (≥ 6 case)
5. 跑 ground-truth-lint 验证 0 violations
   ↓
   python3 backend/scripts/check_filter_builder_usage.py
```

### 6.1.5 跟 L1 + L2 关系 (3 层防御 100% 闭环)

```
Layer 1 (Sprint 33 + 34.1 + 36-4): 静态 lint 钩子
  ├─ L1 frontend: .vue 结构 sanity
  └─ L1 backend: SQL f-string 一致性 (三引号含 {var} 必须 f 前缀)
                ↓
Layer 2 (Sprint 50+): AST parser 升级 (frontend e2e spec)
                ↓
Layer 3 (Sprint 53.5 → 54): FilterBuilder 参数化 (后端 service 层)
                ↓
Layer 4 (流程): review skill 强制 (L4.0 - L5.2)
```

**跨层关系**: L1 抓 SQL 字符串拼接 typo (f 前缀漏写), L3 抓业务字段 f-string 内嵌 (channel/category_id 等用户输入)。两层互补, L1 抓 typo, L3 抓 pattern 违反。

### 6.1.6 新 service 函数 L3 强制规则

**L4.5 永久规则** (CLAUDE.md):

> 任何 backend/services 函数必须用 `FilterBuilder` + `?` 参数化, 禁止 f-string 内嵌用户输入 (channel / category_id / level / granularity / user_id / segment_id 等)。

**新增 service 检查清单**:

```bash
# 1. 写完后跑 ground-truth-lint 验证
python3 backend/scripts/check_filter_builder_usage.py

# 2. 期望输出
[OK] 70/70 files use FilterBuilder.build() pattern
0 violations found.

# 3. 如果有 violation, 改完再跑 (Sprint 36.4 "破坏→验证→恢复" 模式)
#    故意改坏 → 验证 test FAIL → 恢复 → 验证 PASS
```

### 6.1.7 跨 sprint 实战教训

1. **Sprint 33 + 34.1 + 53.5 → 54 三层防御 100% 闭环**: L1 lint + L2 AST + L3 FilterBuilder 共同构成 AI write safety net
2. **Stage 3 review 必跑子 agent 实测** (Sprint 43+): Codex Stage 2 容易漏改 f-string 引用变量 (e.g. 删 `{valid_sql}` 但漏改 `{channel_filter}`), Stage 3 review grep `{` 全检查
3. **worktree pytest 环境隔离** (Sprint 54 L4.6): worktree 共享 .git 但不共享 `data/processed/` → 显式 `DUCKDB_PATH` 指向主仓
4. **单测"破坏 → 验证 → 恢复"** (Sprint 36.4): 单测能 "跑通" 不证明 "抓到 typo", 必须故意改坏验证 test 真 FAIL, 再恢复验证 PASS

### 6.1.8 相关文档

- `backend/scripts/check_filter_builder_usage.py` — L3 ground-truth-lint 工具源码
- `docs/architecture/TEST_INFRASTRUCTURE.md` §4 — ground-truth-lint 钩子位置
- `docs/operating/linting.md` — ground-truth-lint 规则详细
- `CLAUDE.md` L4.5 — backend/services FilterBuilder 强制规则
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{53_5,54,55}.md` — L3 闭环实战 fix

---

## 7. 相关文档

- `operating/linting.md` — ground-truth-lint 规则详细
- `operating/ci-defense-playbook.md` — L5.1 ROI 重评详细决策树
- `operating/ci-e2e-history.md` — Sprint 41 实战 follow-up 12 修完整记录
- `CHANGELOG.md` Sprint 33 / 34.1 / 36-4 / 50+ / 50.1 / 53.5 / 54 entry
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{33,34_1,53_5,54,55}.md` 跨 sprint 实战教训
