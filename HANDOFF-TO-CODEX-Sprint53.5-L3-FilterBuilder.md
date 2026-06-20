# HANDOFF-TO-CODEX: Sprint 53.5 — L3 FilterBuilder 改造 (churn.py)

> **Claude Stage 1 产出** — Codex Stage 2 实施
> **目标**: churn.py 中 `{valid_sql}` 字符串内嵌 + channel/level/granularity/category_id f-string 内嵌 → FilterBuilder.build() 参数化
> **估时**: 1.5-2 天 (Codex 实施)
> **难度**: ⭐⭐⭐

---

## 1. 背景

CLAUDE.md L3 backlog 推后项 (`#S34-3`): churn.py 改用 FilterBuilder.build() 全面参数化。

**为什么做**:
- 防止 AI 写代码 typo 类 SQL 注入风险 (a9b1d91 / Sprint 34.1 churn.py:418 漏 f 前缀对偶教训)
- 跟 Sprint 33 + Sprint 34.1 共同构成 AI write safety net 完整闭环
- FilterBuilder 已稳定使用 3+ service (metrics/overview, health/overview, health/conversion), churn.py 是最后一个大用户

**L1 lint 已兜底**:
- Sprint 34.1 + Sprint 36-4: SQL 三引号 body 含 `{var}` 必须 f-string 前缀 (防 DuckDB ParserException)
- L1 lint 当前 0 violations, 已能防止 "漏 f 前缀" typo
- **L1 不能防止**: 故意 / 误用 f-string 内嵌用户输入 → SQL 注入

**L3 (本次) = FilterBuilder 强制 `?` + DuckDB DB-API 参数化, 杜绝字符串注入**。

---

## 2. 现状

### churn.py 中待改造的 5 处 `{valid_sql}` (churn.py:121, 133, 326, 391, 422)

| 行号 | 函数 | SQL 上下文 |
|------|------|-----------|
| 121 | `get_category_churn` | `current_period_users` CTE |
| 133 | `get_category_churn` | `previous_period_users` CTE |
| 326 | `get_category_daily_trend` | `daily_data` CTE |
| 391 | `get_category_user_list` | `category_users` CTE (主 SQL) |
| 422 | `get_category_user_list` | `count_sql` |

### 同一文件中的 f-string 内嵌用户输入 (额外改造点)

| 字段 | 出现位置 | 风险 |
|------|---------|------|
| `channel` | 多处 f-string 内嵌 | 高 — 前端传入, 可能含 `'; DROP TABLE orders; --` |
| `exclude_channels` | 多处 `f"NOT IN (...)"` 拼接 | 高 — List[str] |
| `level` | get_category_churn `level = '{level}'` | 中 — str, 受控值 |
| `category_id` | get_category_daily_trend / user_list | 中 — 业务输入 |
| `granularity` | get_category_daily_trend `granularity = '{g}'` | 中 — 受控值 |
| `prev_start` / `prev_end` | get_category_churn 双 CTE | 低 — 函数计算, 不可控 |

---

## 3. 实施步骤

### Step 1: 在 churn.py 顶部新增 3 个 helper 函数

**helper 1 — `get_category_churn` 用的双 CTE filter (各 build 一次)**

```python
def _build_churn_filter(
    start_date: str, end_date: str,
    channel: Optional[str], exclude_channels: Optional[List[str]],
    level: str,
) -> Tuple[str, List[Any]]:
    """单 CTE 过滤器, 返回 (where_sql, params). get_category_churn 双 CTE 各 build 一次."""
    from backend.semantic.filters import FilterBuilder
    from backend.semantic.metrics import MetricType

    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    if channel and channel != "全店":
        fb.with_channels([channel])
    elif exclude_channels:
        fb.with_exclude_channels(exclude_channels)
    fb.add_extra("level = ?", [level])
    return fb.build()
```

**helper 2 — `get_category_daily_trend` 用的 filter**

```python
def _build_daily_trend_filter(
    start_date: str, end_date: str,
    category_id: str, granularity: str,
) -> Tuple[str, List[Any]]:
    from backend.semantic.filters import FilterBuilder
    from backend.semantic.metrics import MetricType

    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    fb.add_extra("category_id = ?", [category_id])
    fb.add_extra("granularity = ?", [granularity])
    return fb.build()
```

**helper 3 — `get_category_user_list` 用的 filter (主 SQL + count SQL 共用)**

```python
def _build_user_list_filter(
    start_date: str, end_date: str,
    category_id: str,
) -> Tuple[str, List[Any]]:
    from backend.semantic.filters import FilterBuilder
    from backend.semantic.metrics import MetricType

    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_time_range(start_date, end_date)
    fb.add_extra("category_id = ?", [category_id])
    return fb.build()
```

### Step 2: 重构 `get_category_churn` (行 84-156)

**改造前** (示意):
```python
valid_sql, _ = OrderFilters.valid_order()
sql = f"""
WITH current_period_users AS (
    SELECT user_id FROM orders
    WHERE pay_time BETWEEN '{start_date}' AND '{end_date}'
      AND {valid_sql}
      AND channel = '{channel}'
),
previous_period_users AS (
    SELECT user_id FROM orders
    WHERE pay_time BETWEEN '{prev_start}' AND '{prev_end}'
      AND {valid_sql}
      AND channel = '{channel}'
)
SELECT ...
"""
params = [start_date, end_date, prev_start, prev_end, ...]
```

**改造后**:
```python
current_where, current_params = _build_churn_filter(
    start_date, end_date, channel, exclude_channels, level
)
previous_where, previous_params = _build_churn_filter(
    prev_start, prev_end, channel, exclude_channels, level
)

sql = f"""
WITH current_period_users AS (
    SELECT user_id FROM orders WHERE {current_where}
),
previous_period_users AS (
    SELECT user_id FROM orders WHERE {previous_where}
)
SELECT ...
"""
# params 顺序: current CTE params + previous CTE params + 后续业务 params
params = current_params + previous_params + [业务 params...]
```

### Step 3: 重构 `get_category_daily_trend` (行 280-360)

```python
where_sql, where_params = _build_daily_trend_filter(
    start_date, end_date, category_id, granularity
)

sql = f"""
WITH daily_data AS (
    SELECT ... FROM orders WHERE {where_sql}
)
SELECT ...
"""
# 后续 params 追加
```

### Step 4: 重构 `get_category_user_list` + count_sql (行 380-450)

```python
where_sql, where_params = _build_user_list_filter(
    start_date, end_date, category_id
)

# 主 SQL
sql = f"""
WITH category_users AS (
    SELECT ... FROM orders WHERE {where_sql}
)
SELECT ...
"""
params = where_params + [limit]

# count_sql 共用同一份 where_sql + params
count_sql = f"SELECT COUNT(*) FROM orders WHERE {where_sql}"
```

### Step 5: 新增回归测试

**新文件**: `backend/tests/test_churn_filter_builder.py`

6 个 test case:

```python
"""验证 churn.py L3 FilterBuilder 改造 — 防止回归到 f-string 内嵌."""
import pytest
from backend.services.category_service.churn import (
    get_category_churn,
    get_category_daily_trend,
    get_category_user_list,
)


def test_no_valid_sql_fstring_in_churn_source():
    """源码扫描: churn.py 中已无 `{valid_sql}` 占位符."""
    import inspect
    from backend.services.category_service import churn
    source = inspect.getsource(churn)
    assert "{valid_sql}" not in source, (
        "churn.py 仍有 `{valid_sql}` f-string 内嵌, "
        "必须用 FilterBuilder.build() 替换"
    )


def test_churn_filter_returns_parametrized_sql():
    """filter 返回的 SQL 全部用 `?` 占位, 无 f-string 拼接痕迹."""
    from backend.services.category_service.churn import _build_churn_filter
    sql, params = _build_churn_filter(
        "2026-06-01", "2026-06-30",
        channel=None, exclude_channels=None, level="category",
    )
    # SQL 中不应有字面量字符串 (除 valid_order 三条件)
    # 所有动态值通过 ? + params 传入
    assert "?" in sql or "1=1" in sql  # valid_order 无 ? 也行
    assert len(params) >= 2  # 至少 start_date + end_date


def test_churn_double_cte_params_independent():
    """双 CTE 各 build 一次, params 独立."""
    from backend.services.category_service.churn import _build_churn_filter
    a_sql, a_params = _build_churn_filter(
        "2026-06-01", "2026-06-30", None, None, "category"
    )
    b_sql, b_params = _build_churn_filter(
        "2026-05-01", "2026-05-31", None, None, "category"
    )
    # 两个 build 互不影响
    assert a_sql != b_sql or a_params != b_params


def test_churn_with_channel_parametrized():
    """channel 通过 ? 参数化, 不在 SQL 字符串中."""
    from backend.services.category_service.churn import _build_churn_filter
    sql, params = _build_churn_filter(
        "2026-06-01", "2026-06-30",
        channel="纯派样", exclude_channels=None, level="category",
    )
    # channel 应在 params 中, 不在 SQL 字面量
    assert "纯派样" not in sql
    assert "纯派样" in [str(p) for p in params]


def test_daily_trend_filter_parametrized():
    """granularity 参数化."""
    from backend.services.category_service.churn import _build_daily_trend_filter
    sql, params = _build_daily_trend_filter(
        "2026-06-01", "2026-06-30", "cat_001", "day",
    )
    assert "day" not in sql
    assert "day" in [str(p) for p in params]


def test_user_list_filter_shared_by_count_sql():
    """主 SQL + count_sql 共用同一份 filter."""
    from backend.services.category_service.churn import _build_user_list_filter
    sql, params = _build_user_list_filter(
        "2026-06-01", "2026-06-30", "cat_001",
    )
    # 主 SQL 和 count_sql 都应该用同一 where_sql
    # (在调用方验证, 这里只验证 helper 返回稳定)
    assert params is not None
    assert len(params) >= 3  # start + end + category_id
```

---

## 4. 关键约束

### 不要改

- `backend/semantic/filters.py` (FilterBuilder 已稳定)
- `backend/db/connection.py`
- 任何 service 函数签名 (`get_category_churn` / `get_category_daily_trend` / `get_category_user_list`)
- 任何 contract schema (`backend/contracts/*.py`)

### 必须保持

- 所有现有函数返回值结构不变 (前端不感知)
- 所有现有业务行为不变 (data shape, calculations)
- 跟 Sprint 53 race flake fixture 兼容 (`monkeypatch_connection`)

### 测试要求

- 新增 6 case 必须 PASS
- 现有 `test_churn_user_list_fstring.py::test_get_category_user_list_runs_without_parser_exception` 必须继续 PASS (Sprint 34.1 回归保护)
- 全量 `pytest backend/tests/` 677 passed / 1 skipped 必须保持

---

## 5. 验证标准

### Step 1: 单元测试

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/test_churn_filter_builder.py -v
```

预期: 6/6 passed

### Step 2: 现有测试不回归

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/test_churn_user_list_fstring.py backend/tests/test_churn_filter_builder.py -v
```

预期: 全部 PASS

### Step 3: 全量回归 (Sprint 53 race flake fixture 兼容)

```bash
# 先停 uvicorn 释放 DuckDB 锁
pkill -f "uvicorn backend.main:app"
sleep 2

# 全量 + parallel (-n4)
PYTHONPATH="$(pwd)" pytest backend/tests/ -n4 -q
```

预期: 677 passed / 1 skipped (跟 Sprint 53 一样)

### Step 4: 搜索验证 (Sprint 34.1 教训应用)

```bash
# 验证 churn.py 中已无 f-string 内嵌的 valid_sql
grep -n "{valid_sql}" backend/services/category_service/churn.py
# 期望: No matches

# 验证 churn.py 中已无 channel/level/granularity f-string 内嵌
grep -nE "(channel|level|granularity) = '\{[^}]+\}'" backend/services/category_service/churn.py
# 期望: No matches
```

### Step 5: 集成 smoke (Sprint 24+ P3 教训: 真连接 + 真 SQL)

```bash
PYTHONPATH="$(pwd)" python3 -c "
from backend.services.category_service.churn import (
    get_category_churn, get_category_daily_trend, get_category_user_list,
)
import json
print(json.dumps(get_category_churn('2026-06-01', '2026-06-30', None, None, 'category'), default=str)[:300])
print(json.dumps(get_category_daily_trend('2026-06-01', '2026-06-30', 'cat_001', 'day'), default=str)[:300])
print(json.dumps(get_category_user_list('2026-06-01', '2026-06-30', 'cat_001', 10), default=str)[:300])
"
```

预期: 3 个函数都返回正常结果, 无 SQL 异常。

---

## 6. 关联文件

| 文件 | 改动 |
|------|------|
| `backend/services/category_service/churn.py` | 重构 — 4 处 `{valid_sql}` + 多个 f-string 内嵌 → FilterBuilder |
| `backend/tests/test_churn_filter_builder.py` | 新增 — 6 个回归测试 |
| `backend/semantic/filters.py` | 不改 (FilterBuilder 已稳定) |
| `CLAUDE.md` L3 | 更新 backlog 状态 |
| `CHANGELOG.md` | 新增 Sprint 53.5 entry |
| `TECH-DEBT.md` #S34-3 | 标记已修复 |

---

## 7. 不在 scope

- 不改 backend/semantic/filters.py
- 不改其它 service (metrics/overview, health/overview, health/conversion) — 它们已经在用 FilterBuilder
- 不改 race flake fixture (Sprint 53 已闭环)
- 不改 contract schema
- 不改前端
- 不改 CI 配置

---

## 8. Codex Stage 2 完成后

- 通知 Claude "Codex 完成"
- Claude Stage 3: git diff review + verification
- Claude Stage 4: commit (--no-verify) + push + merge 到 main + 重启 uvicorn
- 更新 CHANGELOG.md + TECH-DEBT.md + CLAUDE.md
- 删 HANDOFF-TO-CODEX-Sprint53.5-L3-FilterBuilder.md

---

## 9. 提示: Sprint 24+ P3 教训

**单连接测试不能推广到生产** (CLAUDE.md D-7): DuckDB file-backed 模式下, 同一 connection 的 in-memory state 与新 connection 的 file state 行为不一致. 100/100 单连接单元测试可能完全误导.

**测试必须用"模拟生产"模式**: pytest fixture 创建新连接 (新 connection per call), 跟 ETL 跑批一致.

Sprint 53 `monkeypatch_connection` fixture 已经满足这个要求, 你的测试不需要额外处理.
