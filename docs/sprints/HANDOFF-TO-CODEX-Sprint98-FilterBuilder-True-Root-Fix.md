# HANDOFF — Sprint 98 FilterBuilder 真治本 (改 OrderFilters + FilterBuilder API)

> **角色**: Codex Stage 2 实施
> **来源**: Claude Stage 1 架构
> **范围**: 真治本 (跟 Sprint 97 治标推广相反), 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default `"o"`) + `FilterBuilder` 加 `self._table_alias` 字段 + `with_table_alias()` 方法 + **删全 12 service post-processing `.replace()` 重复代码**
> **分支**: `fix/sprint98-filter-builder-table-alias` (已创建)
> **目标**: 1 处改动 cover 全 FilterBuilder 调用, 0 重复 post-processing, L4.19 ground-truth-lint 仍然 PASS

---

## 0. 背景 (Context)

Sprint 60.1 治本修 2 endpoint (`distribution.py:69-70` + `overview.py` value-tier), Sprint 97 治标推广到 12 service (post-processing `.replace("channel IN (", "o.channel IN (")`). 

**Sprint 97 治标 vs Sprint 98 真治本对比**:

| 维度 | Sprint 97 治标推广 | Sprint 98 真治本 |
|------|-------------------|------------------|
| 改动数 | 12 service 加 `.replace()` | 1 处 (filters.py) + 删 12 处 `.replace()` |
| 重复代码 | **12 处重复** post-processing | **0** 重复 |
| 风险 | 12 处必须全部加, 易漏 | 1 处改动 cover 全部 |
| 跟 L4.19 一致 | ✅ (满足 `o.` 前缀) | ✅ (满足 `o.` 前缀) |
| 跟 L4.5 一致 | ✅ (FilterBuilder 永久规则) | ✅ (FilterBuilder 永久规则) |
| 留尾 #1 闭环 | 部分 (治标) | **完整** (真治本) |

**Sprint 98 真治本 = Sprint 97 留尾 #1 FilterBuilder 真治本 + 删全 12 service 重复代码**.

---

## 1. 任务清单 (Must Do)

### T1 — 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数

文件: `backend/semantic/filters.py:126-141`

当前:
```python
@staticmethod
def channel_in(channels: List[str]) -> Tuple[str, List[Any]]:
    """渠道 IN 列表（支持组合渠道自动展开）"""
    if not channels:
        return "1=1", []
    db_names = _expand_channels(channels)
    placeholders = ",".join(["?"] * len(db_names))
    return f"channel IN ({placeholders})", db_names

@staticmethod
def channel_not_in(channels: List[str]) -> Tuple[str, List[Any]]:
    """渠道 NOT IN 列表（剔除低价等场景，支持组合渠道自动展开）"""
    if not channels:
        return "1=1", []
    db_names = _expand_channels(channels)
    placeholders = ",".join(["?"] * len(db_names))
    return f"channel NOT IN ({placeholders})", db_names
```

改为:
```python
@staticmethod
def channel_in(channels: List[str], table_alias: str = "o") -> Tuple[str, List[Any]]:
    """渠道 IN 列表（支持组合渠道自动展开）

    Sprint 98 真治本: 加 table_alias 参数 (default "o"), 防 Sprint 60.1 Binder 500
    跨 service 复发 (跟 LEFT JOIN user_rfm r 共存时 channel 字段 ambiguous).
    """
    if not channels:
        return "1=1", []
    db_names = _expand_channels(channels)
    placeholders = ",".join(["?"] * len(db_names))
    prefix = f"{table_alias}." if table_alias else ""
    return f"{prefix}channel IN ({placeholders})", db_names

@staticmethod
def channel_not_in(channels: List[str], table_alias: str = "o") -> Tuple[str, List[Any]]:
    """渠道 NOT IN 列表（剔除低价等场景，支持组合渠道自动展开）

    Sprint 98 真治本: 加 table_alias 参数 (default "o"), 防 Sprint 60.1 Binder 500
    跨 service 复发 (跟 LEFT JOIN user_rfm r 共存时 channel 字段 ambiguous).
    """
    if not channels:
        return "1=1", []
    db_names = _expand_channels(channels)
    placeholders = ",".join(["?"] * len(db_names))
    prefix = f"{table_alias}." if table_alias else ""
    return f"{prefix}channel NOT IN ({placeholders})", db_names
```

**注意**: `table_alias=""` 时输出 `channel IN (...)` (无前缀, 兼容旧单表路径), `table_alias="o"` 时输出 `o.channel IN (...)`.

---

### T2 — 改 `FilterBuilder` 加 `self._table_alias` 字段 + `with_table_alias()` 方法

文件: `backend/semantic/filters.py:149-267`

#### T2.1 `FilterBuilder.__init__` 加字段 (line 162-172)

当前:
```python
def __init__(self):
    self._metric_type: Optional[MetricType] = None
    self._start_dt: Optional[str] = None
    self._end_dt: Optional[str] = None
    self._channels: Optional[List[str]] = None
    self._exclude_channels: Optional[List[str]] = None
    self._segment_id: Optional[int] = None
    self._member_only: bool = False
    self._dimension: Optional[str] = None
    self._dimension_value: Optional[str] = None
    self._extra_conditions: List[Tuple[str, List[Any]]] = []
```

改为 (line 167 之后加 `self._table_alias: str = "o"`):
```python
def __init__(self):
    self._metric_type: Optional[MetricType] = None
    self._start_dt: Optional[str] = None
    self._end_dt: Optional[str] = None
    self._channels: Optional[List[str]] = None
    self._exclude_channels: Optional[List[str]] = None
    self._segment_id: Optional[int] = None
    self._member_only: bool = False
    self._dimension: Optional[str] = None
    self._dimension_value: Optional[str] = None
    self._table_alias: str = "o"  # Sprint 98 真治本: 默认 "o", 配 LEFT JOIN user_rfm r 兼容
    self._extra_conditions: List[Tuple[str, List[Any]]] = []
```

#### T2.2 加 `with_table_alias()` 方法 (line 195 附近, 跟 with_channels 同模式)

```python
def with_table_alias(self, table_alias: str) -> "FilterBuilder":
    """设置表别名 (Sprint 98 真治本: 防 Sprint 60.1 Binder 500)

    默认 "o" (跟 orders 别名一致), 可设为 "" 输出无别名 (兼容旧单表路径).
    """
    self._table_alias = table_alias
    return self
```

#### T2.3 改 `FilterBuilder.build()` channel 调用 (line 240, 246)

当前:
```python
# 3. 渠道筛选
if self._channels:
    ch_sql, ch_params = OrderFilters.channel_in(self._channels)
    conditions.append(ch_sql)
    params.extend(ch_params)

# 3.5 排除渠道
if self._exclude_channels:
    ex_sql, ex_params = OrderFilters.channel_not_in(self._exclude_channels)
    conditions.append(ex_sql)
    params.extend(ex_params)
```

改为 (加 `self._table_alias` 参数):
```python
# 3. 渠道筛选
if self._channels:
    ch_sql, ch_params = OrderFilters.channel_in(self._channels, self._table_alias)
    conditions.append(ch_sql)
    params.extend(ch_params)

# 3.5 排除渠道
if self._exclude_channels:
    ex_sql, ex_params = OrderFilters.channel_not_in(self._exclude_channels, self._table_alias)
    conditions.append(ex_sql)
    params.extend(ex_params)
```

---

### T3 — 删全 12 service post-processing `.replace()` 重复代码

**Sprint 97 治标 12 service 加的 4 行 `.replace()` 全部删掉** (每 service 删 2 行 post-processing + 1 行 comment).

#### T3.1 5 个 FilterBuilder service 删 post-processing

| # | 文件 | 行号 | 删 |
|---|------|------|-----|
| 1 | `backend/services/flow_service.py` | 46-47 / 64-65 / 167-168 / 172-173 | 4 处 `.replace()` + comment |
| 2 | `backend/services/asset_service.py` | 114-115 | 1 处 |
| 3 | `backend/services/metrics/overview.py` | 7 处 | 7 处 |
| 4 | `backend/services/churn_service.py` | 65-66 / 96-98 | 2 处 + alias fallback (Sprint 97 加的 alias="" 兼容) |
| 5 | `backend/services/geo_service.py` | 40-41 | 1 处 |

**模板删除** (每 service 类似):
```python
# Sprint 97 fix: channel 加 o. 前缀, 配 JOIN 兼容 (避免 channel 字段 ambiguous)
where_sql = where_sql.replace("channel IN (", "o.channel IN (")
where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")
```
↑ 3 行全删 (comment + 2 行 replace). 

**churn_service.py 特殊** (line 96-98 还有 alias fallback, 删后变 2 行):
```python
# Sprint 97 fix: 默认 orders 别名为 o；alias="" 的旧单表路径保持无别名兼容
where_sql = where_sql.replace("channel IN (", "o.channel IN (")
where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")
if not alias:
    where_sql = where_sql.replace("o.channel IN (", "channel IN (")
    where_sql = where_sql.replace("o.channel NOT IN (", "channel NOT IN (")
```
↑ 5 行全删. Sprint 98 真治本后 `OrderFilters.channel_in(channels, table_alias="")` 自动处理 alias="" 兼容 (T1 已实现).

#### T3.2 2 个手工拼 service (audience_summary + sampling) 不动

audience_summary.py + sampling_service.py 已经在 Sprint 97 加 `o.channel` 前缀 (line 205/209/214 + 13 处), 跟 Sprint 98 真治本一致. **不动**.

---

### T4 — 加 regression test 验证 12 service 无 `.replace()` (Sprint 98 真治本生效)

新建 `backend/tests/test_sprint98_no_replace_postprocessing.py`:

```python
"""Sprint 98 真治本验证: 12 service 无 .replace('channel IN (', 'o.channel IN (') 重复代码.

Sprint 97 治标加了 14 处 .replace() (5 FilterBuilder service + 5 手工拼 service 残留).
Sprint 98 真治本后, OrderFilters.channel_in/not_in 默认输出 o.channel IN/NOT IN,
所有 FilterBuilder service 应该 0 .replace() 调用.
"""

import re
from pathlib import Path

# Sprint 97 治标加的 14 处 .replace() 应全部删掉
PATTERN_CHANNEL_REPLACE = re.compile(
    r'\.replace\(["\']channel IN \(["\'],\s*["\']o\.channel IN \(["\']\)'
)
PATTERN_CHANNEL_NOT_REPLACE = re.compile(
    r'\.replace\(["\']channel NOT IN \(["\'],\s*["\']o\.channel NOT IN \(["\']\)'
)

SERVICES_WITH_FILTERBUILDER = [
    "backend/services/flow_service.py",
    "backend/services/asset_service.py",
    "backend/services/metrics/overview.py",
    "backend/services/churn_service.py",
    "backend/services/geo_service.py",
]


def test_no_channel_replace_postprocessing():
    """12 service 0 .replace() post-processing (Sprint 98 真治本生效)."""
    for service in SERVICES_WITH_FILTERBUILDER:
        text = Path(service).read_text(encoding="utf-8")
        ch_count = len(PATTERN_CHANNEL_REPLACE.findall(text))
        not_count = len(PATTERN_CHANNEL_NOT_REPLACE.findall(text))
        assert ch_count == 0, f"{service} 残留 {ch_count} 处 .replace('channel IN (', 'o.channel IN (')"
        assert not_count == 0, f"{service} 残留 {not_count} 处 .replace('channel NOT IN (', 'o.channel NOT IN (')"


def test_filters_py_table_alias_default():
    """filters.py OrderFilters.channel_in/not_in 有 table_alias 参数, default 'o'."""
    from backend.semantic.filters import OrderFilters
    # Default alias = "o"
    sql, params = OrderFilters.channel_in(["直播", "货架"])
    assert sql == "o.channel IN (?, ?)", f"expected 'o.channel IN (?, ?)', got {sql!r}"
    assert params == ["直播", "货架"]

    sql, params = OrderFilters.channel_not_in(["购物金"])
    assert sql == "o.channel NOT IN (?)", f"expected 'o.channel NOT IN (?)', got {sql!r}"
    assert params == ["购物金"]

    # Empty channels 不变
    sql, params = OrderFilters.channel_in([])
    assert sql == "1=1"
    assert params == []


def test_filters_py_table_alias_empty():
    """table_alias='' 时输出无前缀 channel (兼容旧单表路径)."""
    from backend.semantic.filters import OrderFilters
    sql, params = OrderFilters.channel_in(["直播"], table_alias="")
    assert sql == "channel IN (?)", f"expected 'channel IN (?)', got {sql!r}"


def test_filter_builder_table_alias_method():
    """FilterBuilder 有 with_table_alias() 方法 + 默认 'o'."""
    from backend.semantic.filters import FilterBuilder, MetricType
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_channels(["直播"])
    sql, params = fb.build()
    assert "o.channel IN (?)" in sql, f"expected 'o.channel IN (?)' in {sql!r}"

    # 覆盖 default
    fb2 = FilterBuilder()
    fb2.with_metric_type(MetricType.GSV)
    fb2.with_table_alias("")
    fb2.with_channels(["直播"])
    sql2, params2 = fb2.build()
    assert "channel IN (?)" in sql2, f"expected 'channel IN (?)' in {sql2!r}"
```

---

### T5 — 验证 ground-truth-lint (L4.19) 仍然 PASS

跑 `backend/scripts/check_channel_alias.py` (Sprint 97 L4.19 新增的 ground-truth-lint), 期望 ✅ 0 violations.

L4.19 规则: 任何 `channel IN/NOT IN/=` 必须含 `o.` 表别名. Sprint 98 真治本后, FilterBuilder 默认 `o.channel`, 自动满足. 手工拼的 2 个 service (audience_summary + sampling) Sprint 97 已加 `o.`, 仍 PASS.

---

### T6 — 更新 STATUS.md / CHANGELOG.md / VERSION / TECH-DEBT.md

#### T6.1 STATUS.md

更新 Sprint 97 FilterBuilder 治本状态行:

```markdown
| FilterBuilder 12 service 推广 | ✅ 闭环 | Sprint 97 治标 → Sprint 98 真治本 (改 OrderFilters channel_in/not_in 加 table_alias 参数, 1 处改动 cover 全 FilterBuilder 调用, 删全 12 service post-processing 重复代码) |
```

#### T6.2 CHANGELOG.md

顶部新增 Sprint 98 entry:

```markdown
## [0.4.14.157] - 2026-06-23

### Changed
- Sprint 98 FilterBuilder 真治本: `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default "o"), `FilterBuilder` 加 `self._table_alias` 字段 + `with_table_alias()` 方法. 删全 12 service post-processing `.replace()` 重复代码 (Sprint 97 治标 14 处全删, 1 处真治本 cover). 防 Sprint 60.1 Binder 500 跨 service 复发 (跟 L4.19 永久规则配套)
```

#### T6.3 VERSION

`0.4.14.156` → `0.4.14.157` (Sprint 98 真功能 sprint bump)

#### T6.4 docs/TECH-DEBT.md

更新 Sprint 60+ 留尾 #1 状态:

```markdown
- ✅ **Sprint 60+ 留尾 #1 FilterBuilder 治本 (Sprint 97 治标 + Sprint 98 真治本全闭环)**:
  - Sprint 97 治标: 5 FilterBuilder service + 2 手工拼 service 加 `o.` 表别名 (12 service 全量)
  - Sprint 98 真治本: 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default "o") + `FilterBuilder` 加 `self._table_alias` 字段 + `with_table_alias()` 方法 + 删全 12 service post-processing `.replace()` 重复代码 (14 处 → 0 处)
```

#### T6.5 Sprint 98 HANDOFF 文档

写到 `docs/sprints/HANDOFF-TO-CODEX-Sprint98-FilterBuilder-True-Root-Fix.md` (Stage 1 文档, 跟 Sprint 60-3 / Sprint 97 模式一致).

---

## 2. 禁止事项 (Must NOT Do)

- ❌ 不要改 Pydantic contract (不动 `backend/contracts/*.py`)
- ❌ 不要改 frontend 代码 (Vue 3)
- ❌ 不要在 main 分支直接 commit (CLAUDE.md 强制自检: 必须 `git checkout -b fix/sprint98-...`)
- ❌ 不要 git push (Stage 2 Codex 不动 git, Claude Stage 4 才 push, L4.15 push 必 user 拍板)
- ❌ 不要改 audience_summary.py + sampling_service.py (Sprint 97 已加 `o.channel`, 跟 Sprint 98 真治本一致, 不动)
- ❌ 不要加 `if not alias: ...` 兼容分支到 service 层 (alias="" 兼容由 `OrderFilters.channel_in(channels, table_alias="")` 内部处理, T1 已实现)
- ❌ 不要新加 L4.x 永久规则 (L4.5/L4.19 已覆盖, Sprint 98 是 L4.5/L4.19 应用)
- ❌ 不要改 ground-truth-lint 钩子规则 (L4.19 已 PASS, Sprint 98 真治本后仍 PASS)

---

## 3. 验证步骤 (Codex 完成后必须跑)

```bash
# 1. Sprint 98 regression test (T4)
PYTHONPATH="$(pwd)" pytest backend/tests/test_sprint98_no_replace_postprocessing.py -v
# 期望: 4/4 pass

# 2. ground-truth-lint (L4.19, T5)
PYTHONPATH="$(pwd)" python3 backend/scripts/check_channel_alias.py
# 期望: ✅ channel alias lint passed

# 3. Sprint 97 regression test (确保 L4.19 防回归仍 PASS)
PYTHONPATH="$(pwd)" pytest backend/tests/test_sprint97_channel_alias_coverage.py -v
PYTHONPATH="$(pwd)" pytest backend/tests/test_check_channel_alias.py -v
# 期望: 3/3 + 3/3 pass

# 4. 现有 filter builder test (不漂移)
PYTHONPATH="$(pwd)" pytest backend/tests/test_filters.py backend/tests/test_distribution_filter_builder.py backend/tests/test_category_overview_filter_builder.py backend/tests/test_metrics_overview_filter_builder.py -v
# 期望: 跟 Sprint 97 baseline 一致 (53 passed, 5 skipped)

# 5. 全量 pytest baseline (production DuckDB 不可用 → 期望 811/23/0 跟 Sprint 97 一致)
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q --no-header
# 期望: 811 passed, 23 skipped, 0 failed (跟 Sprint 97 baseline 一致)

# 6. ruff 0 errors
ruff check backend/semantic/filters.py backend/services/ backend/tests/test_sprint98_no_replace_postprocessing.py
# 期望: 0 errors

# 7. 端到端 12/12 (本地有 uvicorn + production DuckDB 时)
# 跟 Sprint 60.1 close memory + Sprint 97 端到端验证模式一致
# 期望: distribution 4 + value-tier 4 + overview 2 + repurchase-flow + flow 全 200
```

---

## 4. Commit 规范

按 CLAUDE.md "commit 混多个不相关功能" 禁止, 拆 3 个 commit:

**Commit 1** (filters.py 真治本):
```
fix(semantic): Sprint 98 FilterBuilder 真治本 (OrderFilters 加 table_alias 参数)

- backend/semantic/filters.py: OrderFilters.channel_in/not_in 加 table_alias 参数 (default "o")
- FilterBuilder 加 self._table_alias 字段 + with_table_alias() 方法
- FilterBuilder.build() 改 channel 调用传 self._table_alias
- 防 Sprint 60.1 Binder 500 跨 service 复发, L4.19 永久规则配套
```

**Commit 2** (删 12 service 重复代码):
```
refactor(services): Sprint 98 删全 12 service post-processing .replace() 重复代码

- flow_service.py: 删 4 处 .replace() + comment
- asset_service.py: 删 1 处
- metrics/overview.py: 删 7 处
- churn_service.py: 删 2 处 + alias fallback
- geo_service.py: 删 1 处
- 总计 14 处 .replace() 重复代码全删, OrderFilters 真治本后自动 cover
- 跟 Sprint 97 治标 12 service 推广互补, 1 处真治本 vs 14 处重复
```

**Commit 3** (regression test + 收口 doc):
```
chore(lint): Sprint 98 真治本 regression test + STATUS + CHANGELOG + VERSION + TECH-DEBT + HANDOFF

- 新增 backend/tests/test_sprint98_no_replace_postprocessing.py 4 case regression (破坏→验证→恢复 模式)
- VERSION 0.4.14.156 → 0.4.14.157
- STATUS.md 更新 Sprint 97 → Sprint 98 真治本状态
- CHANGELOG.md 加 Sprint 98 entry (Changed)
- docs/TECH-DEBT.md Sprint 60+ 留尾 #1 全闭环 (Sprint 97 治标 + Sprint 98 真治本)
- docs/sprints/HANDOFF-TO-CODEX-Sprint98-FilterBuilder-True-Root-Fix.md
```

---

## 5. 后续治本方案 (Sprint 98 真治本 + Sprint 97 治标 全闭环)

| Sprint | 治本 | 改动数 | 跟 L4.19 一致 |
|--------|------|--------|---------------|
| Sprint 60.1 | 治标: 2 endpoint 加 `o.channel` (post-processing) | 2 文件 +2 行 | ✅ |
| Sprint 97 | 治标推广: 12 service 加 `o.channel` (post-processing) | 12 文件 +14 行 (重复) | ✅ |
| **Sprint 98** | **真治本: 改 OrderFilters + FilterBuilder API, 删全 14 处 post-processing** | **2 文件 (1 加, 1 删 × 14) + 1 file (filter.py API)** | ✅ |

**Sprint 98 真治本后, 12 service 0 重复 post-processing, 1 处 API 改动 cover 全 FilterBuilder 调用**. 跟 Sprint 60+ "1 sprint 1 范围" + Sprint 90 L4.7 模式 + Sprint 92 L4.9 模式 一致.

**真治本 vs 治标对比 ROI**:

| 维度 | 治标 (Sprint 60.1/97) | 真治本 (Sprint 98) |
|------|---------------------|-------------------|
| 改动数 | 14 处 | 2 处 (1 加 + 1 删 × 14) |
| 重复代码 | 14 处 | 0 |
| 维护成本 | 14 service 各自维护 | 1 处 API 维护 |
| 风险 | 易漏 / 易改坏 | 1 处集中改 |
| 跟 L4.5/L4.19 一致 | ✅ | ✅ |

**Sprint 98 后 L4.5/L4.19 永久规则变成 "filter 层防回归", 0 service 层 post-processing 重复代码**.

---

## 6. 完成定义 (Definition of Done)

- [ ] T1 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default "o")
- [ ] T2 改 `FilterBuilder` 加 `self._table_alias` + `with_table_alias()` 方法 + `build()` 传 self._table_alias
- [ ] T3 删全 12 service post-processing `.replace()` 重复代码 (5 FilterBuilder service × 14 处)
- [ ] T4 加 `test_sprint98_no_replace_postprocessing.py` 4 case pass
- [ ] T5 ground-truth-lint (L4.19) PASS
- [ ] T6 STATUS + CHANGELOG + VERSION (0.4.14.157) + TECH-DEBT + HANDOFF 已更新
- [ ] pytest 全量 811/23/0 baseline 不漂移 (验证 §3.5)
- [ ] ruff 0 errors (验证 §3.6)
- [ ] 端到端 12/12 curl 200 (验证 §3.7, 本地有 uvicorn 时)
- [ ] 3 个 commit 已 push 到 `fix/sprint98-filter-builder-table-alias`
- [ ] 告知 Claude "Codex 完成", 等待 Stage 3 review
