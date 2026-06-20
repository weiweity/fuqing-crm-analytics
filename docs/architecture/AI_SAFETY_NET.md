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

## 7. 相关文档

- `operating/linting.md` — ground-truth-lint 规则详细
- `operating/ci-defense-playbook.md` — L5.1 ROI 重评详细决策树
- `operating/ci-e2e-history.md` — Sprint 41 实战 follow-up 12 修完整记录
- `CHANGELOG.md` Sprint 33 / 34.1 / 36-4 / 50+ / 50.1 / 53.5 / 54 entry
- `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{33,34_1,53_5,54,55}.md` 跨 sprint 实战教训
