# HANDOFF — Sprint 97 FilterBuilder channel 别名推广 (12 service 全量 post-processing)

> **角色**: Codex Stage 2 实施
> **来源**: Claude Stage 1 架构
> **范围**: 治标推广 (方案 C, user 拍板), 全 12 service channel 加 `o.` 表别名, 防 DuckDB Binder "Ambiguous reference to column name 'channel'"
> **分支**: `fix/sprint97-filter-builder-table-alias` (待 Codex 创建)
> **目标**: 5 个 FilterBuilder service + 2 个手工拼 service 加 post-processing; 5 个 service (含 Sprint 60.1 已修 2 个) verify 不漏; 加 ground-truth-lint 防回归

---

## 0. 背景 (Context)

Sprint 60.1 治本修了 2 个 endpoint (`distribution.py` + `overview.py` value-tier) channel 缺 `o.` 别名导致 DuckDB Binder 500 错误. 但**留尾**: 14+ service 中还有 7 个 service 有同样 bug, 风险是触发同样的 Binder 500.

**根因 (Sprint 60.1 close memory)**:
```python
# OrderFilters.channel_in 在 backend/semantic/filters.py:126-132 输出:
return f"channel IN ({placeholders})", db_names
# ↑ 无 o. 别名, 跟 LEFT JOIN user_rfm r 共存时 DuckDB 抛 Binder Error
```

**决策 (user 拍板 Q1=C + Q2=B)**:
1. **Q1=C**: 不改 `OrderFilters.channel_in/not_in` (保留原样), 而是把 Sprint 60.1 治标 `where_sql.replace("channel IN (", "o.channel IN (")` 推广到全 12 service (7 个新修 + 5 个 verify 不漏)
2. **Q2=B**: Sprint 97 一并修 audience_summary + sampling 2 个手工拼 `channel IN (` 的 service

**后续治本 (不在本次)**: 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default `"o"`), 1 处改动 cover 全 FilterBuilder 调用. 推后评估 ROI, 留尾给 Sprint 98+.

---

## 1. 任务清单 (Must Do)

### T1 — 5 个 FilterBuilder service 加 post-processing

每个 service 在 `fb.build()` 后立刻加 2 行 `.replace()`. 模板:

```python
where_sql, params = fb.build()
# Sprint 97 fix: channel 加 o. 前缀, 配 LEFT JOIN user_rfm r 兼容 (避免 channel 字段 ambiguous)
where_sql = where_sql.replace("channel IN (", "o.channel IN (")
where_sql = where_sql.replace("channel NOT IN (", "o.channel NOT IN (")
```

#### T1.1 `backend/services/flow_service.py` (4 处 FilterBuilder.build)

| # | 行号 | 上下文 |
|---|------|--------|
| 1 | 41-46 | `_flow_period_filter` helper, return `fb.build()` |
| 2 | 60-63 | 第二个 FilterBuilder helper, return `fb.build()` |
| 3 | 153 | `fb_fm` for F/M metric |
| 4 | 161 | `fb_r` for R metric |

**实施**: 找到 4 个 `return fb.build()` 或 `where_sql, params = fb.build()`, 各自加 2 行 `.replace()`.

#### T1.2 `backend/services/asset_service.py` (1 处)

| # | 行号 | 上下文 |
|---|------|--------|
| 1 | 108-114 | `_build_xxx_filter` helper, return `fb.build()` |

#### T1.3 `backend/services/metrics/overview.py` (7 处)

| # | 行号 | 上下文 |
|---|------|--------|
| 1 | 24-31 | 第一个 fb.build() |
| 2 | 75-82 | 第二个 fb.build() |
| 3 | 126-134 | 第三个 fb.build() |
| 4 | 164-171 | 第四个 fb.build() |
| 5 | 372-379 | 第五个 fb.build() |
| 6 | 409 | `fb_ly` (last year) for YOY |
| 7 | 479-482 | 第七个 fb.build() |

**实施**: 找到 7 个 `where_sql, params = fb.build()` 或 `where_sql, where_params = fb.build()`, 各自加 2 行 `.replace()`.

#### T1.4 `backend/services/churn_service.py` (2 处)

| # | 行号 | 上下文 |
|---|------|--------|
| 1 | 61-65 | 第一个 fb.build() |
| 2 | 89-93 | 第二个 fb.build() |

#### T1.5 `backend/services/geo_service.py` (1 处)

| # | 行号 | 上下文 |
|---|------|--------|
| 1 | 33-40 | `fb.build()` 后直接 return |

---

### T2 — 2 个手工拼 service 加 `o.` 前缀 (Q2=B)

#### T2.1 `backend/services/metrics/audience_summary.py:209, 214`

当前:
```python
where_parts.append(f"channel IN ({placeholders})")   # line 209
where_parts.append(f"channel NOT IN ({placeholders})")  # line 214
```

改为:
```python
where_parts.append(f"o.channel IN ({placeholders})")
where_parts.append(f"o.channel NOT IN ({placeholders})")
```

**注意**: `audience_summary.py` line 205 还有 `where_parts.append("channel = ?")`, 也需改:
```python
where_parts.append("o.channel = ?")  # Sprint 97 fix
```

#### T2.2 `backend/services/sampling_service.py:85`

当前:
```python
WHERE channel IN ({ch_placeholders})
```

改为:
```python
WHERE o.channel IN ({ch_placeholders})
```

---

### T3 — Verify Sprint 60.1 已修 5 个 service 不漏

Sprint 60.1 已用 post-processing 修过, 但 verify 仍然合规:

| # | 文件 | 行号 | 状态 |
|---|------|------|------|
| 1 | `backend/services/category_service/distribution.py:69-70` | Sprint 60.1 治标, 2 行 `.replace()` | ✅ 已有, 保留 |
| 2 | `backend/services/category_service/overview.py` (value-tier) | Sprint 60.1 治标 | ✅ 已有, 保留 |
| 3 | `backend/services/category_service/overview.py` (wool-party) | Sprint 60.1 治标 | ✅ 已有, 保留 |
| 4 | `backend/services/health/tier_flow.py:70-83` | 手工拼 `o.channel`, 已对 | ✅ 已有, 保留 |
| 5 | `backend/services/health/rfm_analysis/period.py:83-115` | 手工拼 `o.channel`, 已对 | ✅ 已有, 保留 |
| 6 | `backend/services/category_service/basket.py:105-112` | 手工拼 `o.channel`, 已对 | ✅ 已有, 保留 |

**验证方式**: `grep -n "channel IN (\|channel NOT IN (" backend/services/**/*.py` 应该**全部**含 `o.channel IN/NOT IN`, 0 个无别名.

---

### T4 — 加 ground-truth-lint 防回归 (L4.5)

新建 `backend/scripts/check_channel_alias.py` (跟 `check_sql_fstring_consistency.py` 同模式):

```python
"""Sprint 97 ground-truth-lint: channel IN/NOT IN 必须含 o. 表别名.

防 Sprint 60.1 Binder 500 回归: 跟 LEFT JOIN user_rfm r 共存时
DuckDB 抛 'Ambiguous reference to column name "channel"' (Sprint 60.1 close memory).

规则: backend/services/**/*.py 所有 'channel IN (' / 'channel NOT IN (' / 'channel = ?'
字符串必须含 'o.channel' 前缀 (orders o 别名).

Sprint 60.1 治标模式: where_sql.replace("channel IN (", "o.channel IN (")
"""

import re
import sys
from pathlib import Path

# 匹配 channel 单独出现 (非 o.channel / r.channel / user_rfm.channel)
# 排除 SQL 注释 (-- 开头) 和 f-string 里的 'o.channel' 已知正确用法
PATTERN_NO_ALIAS = re.compile(
    r"""(?<![\w.])channel\s+(?:IN|NOT\s+IN|=)\s*\(?""",
    re.VERBOSE,
)

SKIP_FILES = {
    # Sprint 60.1 治标 replace 模板 (允许 channel IN 出现, 因为 replace target)
    "backend/services/category_service/distribution.py",
    # 测试文件允许 (test_filters.py 测 OrderFilters.channel_in 原样输出)
    "backend/tests/test_filters.py",
    "backend/tests/test_check_channel_alias.py",
}


def check_file(path: Path) -> list[str]:
    if path.name in SKIP_FILES or str(path) in SKIP_FILES:
        return []
    if "test_" in path.name or "tests/" in str(path):
        return []  # 测试文件跳过
    errors = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        # 跳过含 o.channel / r.channel / user_rfm.channel / {var} channel 的行
        if "o.channel" in line or "r.channel" in line or "user_rfm.channel" in line:
            continue
        # 跳过 SQL 注释行
        if line.strip().startswith("--") or line.strip().startswith("#"):
            continue
        m = PATTERN_NO_ALIAS.search(line)
        if m:
            errors.append(f"{path}:{i}: {line.strip()}")
    return errors


def main() -> int:
    backend = Path("backend/services")
    if not backend.exists():
        print("ERROR: backend/services not found", file=sys.stderr)
        return 1
    all_errors = []
    for py_file in backend.rglob("*.py"):
        all_errors.extend(check_file(py_file))
    if all_errors:
        print(f"❌ Found {len(all_errors)} channel alias violations:")
        for e in all_errors:
            print(f"  {e}")
        return 1
    print("✅ channel alias lint passed: all channel IN/NOT IN/= contain o. prefix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**配套测试** `backend/tests/test_check_channel_alias.py` (跟 `test_check_sql_fstring_consistency.py` 模式一致):
- case 1: 故意加 `channel IN (` 无别名 → 期望 rc=1
- case 2: 故意改回 `o.channel IN (` → 期望 rc=0
- case 3: 扫全 `backend/services/` → 期望 rc=0 (Sprint 97 实施后)

---

### T5 — 加 regression test 验证 7 个 service

新建 `backend/tests/test_sprint97_channel_alias_coverage.py`:

```python
"""Sprint 97 regression test: 7 个 service 的 channel IN/NOT IN/= 都含 o. 前缀.

防止 Sprint 60.1 Binder 500 bug 跨 service 漏修.
"""

import re
from pathlib import Path

SERVICES_WITH_FILTERBUILDER = [
    "backend/services/flow_service.py",
    "backend/services/asset_service.py",
    "backend/services/metrics/overview.py",
    "backend/services/churn_service.py",
    "backend/services/geo_service.py",
]

SERVICES_MANUAL = [
    "backend/services/metrics/audience_summary.py",
    "backend/services/sampling_service.py",
]

PATTERN = re.compile(r"channel\s+(?:IN|NOT\s+IN|=)\s*\(")


def test_filter_builder_services_have_o_alias():
    """5 个 FilterBuilder service 加 post-processing 后, SQL 必须含 o.channel."""
    for svc in SERVICES_WITH_FILTERBUILDER:
        text = Path(svc).read_text(encoding="utf-8")
        # 找 fb.build() 后 5 行内必须有 .replace("channel IN (", "o.channel IN (")
        assert '.replace("channel IN (", "o.channel IN (")' in text, \
            f"{svc} 缺 FilterBuilder post-processing for channel IN"
        assert '.replace("channel NOT IN (", "o.channel NOT IN (")' in text, \
            f"{svc} 缺 FilterBuilder post-processing for channel NOT IN"


def test_manual_services_have_o_prefix():
    """2 个手工拼 service 加 o. 前缀后, SQL 字面量必须含 o.channel."""
    for svc in SERVICES_MANUAL:
        text = Path(svc).read_text(encoding="utf-8")
        # 找所有 channel IN/NOT IN/=, 期望全部含 o.channel
        for i, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line) and "o.channel" not in line:
                raise AssertionError(f"{svc}:{i} 含无别名 channel: {line.strip()}")


def test_no_regression_in_sprint60_1_services():
    """Sprint 60.1 已修 5 个 service 不漏."""
    for svc in [
        "backend/services/category_service/distribution.py",
        "backend/services/category_service/overview.py",
        "backend/services/health/tier_flow.py",
        "backend/services/health/rfm_analysis/period.py",
        "backend/services/category_service/basket.py",
    ]:
        text = Path(svc).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line) and "o.channel" not in line and "r.channel" not in line:
                # 允许 Sprint 60.1 治标 replace target (distribution.py:69 已知)
                if svc.endswith("distribution.py") and "channel IN (" in line and "replace" in line:
                    continue
                raise AssertionError(f"{svc}:{i} 含无别名 channel: {line.strip()}")
```

---

### T6 — 更新 STATUS.md

找到 "channel 别名" 或 "FilterBuilder" 行:

```markdown
| FilterBuilder 治本 (Sprint 60+ 留尾) | 📋 留尾 | Sprint 60.1 治标 2 endpoint, 12 service 推广给 Sprint 97 |
```

改为:

```markdown
| FilterBuilder 12 service 推广 | ✅ 闭环 | Sprint 97 修 5 FilterBuilder + 2 手工拼 + verify 5, 加 L4.5 ground-truth-lint 防回归 |
```

---

### T7 — 更新 docs/TECH-DEBT.md

找到 "Sprint 60+ 留尾" section (line 10 附近), 更新 FilterBuilder 治本状态:

```markdown
- 📋 **FilterBuilder 治本** (Sprint 60+ 留尾): 加 `o.channel` 前缀 (14+ service audit)
```

改为:

```markdown
- ✅ **FilterBuilder 12 service 推广闭环 (Sprint 97)**: 5 FilterBuilder service 加 post-processing + 2 手工拼 service 加 o. 前缀 + verify 5 已修, L4.5 ground-truth-lint 防回归
- 📋 **FilterBuilder 真治本推后**: 改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数 (default "o"), 1 处改动 cover 全 FilterBuilder 调用 (评估 ROI 中)
```

加 L4.19 永久规则 (跟 L4.5 配套):

```markdown
| **L4.19 (流程)** | **任何 service 输出 SQL 含 `channel IN/NOT IN/=` 必须有 `o.` 表别名** (防 Sprint 60.1 Binder 500 bug 跨 service 复发). 配套 `backend/scripts/check_channel_alias.py` ground-truth-lint 钩子 + `backend/tests/test_check_channel_alias.py` regression. Sprint 97 收口新增. | review skill 强制 | **Sprint 97** | 本节 + `backend/services/**` |
```

---

### T8 — 更新 CHANGELOG.md

在 `CHANGELOG.md` 顶部新增 Sprint 97 entry:

```markdown
## [0.4.14.156] - 2026-06-23

### Fixed
- Sprint 97 FilterBuilder 12 service channel 别名推广 (治标 C 方案): 5 FilterBuilder service + 2 手工拼 service 加 `o.` 表别名, 防 DuckDB Binder "Ambiguous reference to column name 'channel'" 跨 service 复发

### Added
- L4.19 永久规则 + `backend/scripts/check_channel_alias.py` ground-truth-lint 防回归
- `backend/tests/test_sprint97_channel_alias_coverage.py` 7 case regression
```

---

### T9 — bump VERSION

文件: `VERSION`

`0.4.14.155` → `0.4.14.156`

---

## 2. 禁止事项 (Must NOT Do)

- ❌ 不要改 `backend/semantic/filters.py` 的 `OrderFilters.channel_in/not_in` 实现 (Q1=C 治标推广, 不动 FilterBuilder 内部, 留尾给 Sprint 98+)
- ❌ 不要改 `FilterBuilder` class (同上)
- ❌ 不要改 `backend/contracts/*.py` (不动 Pydantic schema)
- ❌ 不要改 frontend 代码 (Vue 3)
- ❌ 不要在 main 分支直接 commit (CLAUDE.md 强制自检: 必须 `git checkout -b fix/sprint97-filter-builder-table-alias`)
- ❌ 不要 git push (Stage 2 Codex 不动 git, Claude Stage 4 才 push, L4.15 push 必 user 拍板)
- ❌ 不要改 Sprint 60.1 已修 5 个 service 的 post-processing 代码 (保留 verify)

---

## 3. 验证步骤 (Codex 完成后必须跑)

```bash
# 1. ground-truth-lint 验证 (T4)
PYTHONPATH="$(pwd)" python3 backend/scripts/check_channel_alias.py
# 期望: ✅ channel alias lint passed

# 2. Sprint 97 regression test (T5)
PYTHONPATH="$(pwd)" pytest backend/tests/test_sprint97_channel_alias_coverage.py -v
# 期望: 3/3 pass

# 3. ground-truth-lint test (T4 配套)
PYTHONPATH="$(pwd)" pytest backend/tests/test_check_channel_alias.py -v
# 期望: 3/3 pass

# 4. 全量 filter builder test (不漂移)
PYTHONPATH="$(pwd)" pytest backend/tests/test_filters.py backend/tests/test_distribution_filter_builder.py backend/tests/test_category_overview_filter_builder.py backend/tests/test_metrics_overview_filter_builder.py -v
# 期望: 全 pass (baseline 18/18 + Sprint 60.1 5/5 + Sprint 97 7/7 = ~30 pass)

# 5. 全量 pytest (本地有 production DuckDB 时, baseline 不能漂移)
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
# 期望: 741 passed / 21 skipped / 0 failed (跟 Sprint 96.5 baseline 一致)

# 6. ruff lint 验证
ruff check backend/services/ backend/scripts/check_channel_alias.py backend/tests/test_sprint97_channel_alias_coverage.py
# 期望: 0 errors (新增文件遵循现有 PEP8)

# 7. 端到端验证 (本地有 uvicorn + production DuckDB 时)
# 跟 Sprint 60.1 close memory 12/12 curl 200 验证模式一致
# 期望: distribution 4/4 + value-tier 4/4 + user-reported 4 endpoint 全 200
```

---

## 4. Commit 规范

按 CLAUDE.md "commit 混多个不相关功能" 禁止原则, 拆 3 个 commit:

**Commit 1** (7 个 service 改动):
```
fix(filter-builder): Sprint 97 channel 别名推广 (5 FilterBuilder + 2 手工拼)

- flow_service.py: 4 处 FilterBuilder.build() 后加 .replace("channel IN/NOT IN (", "o.channel IN/NOT IN (")
- asset_service.py: 1 处
- metrics/overview.py: 7 处
- churn_service.py: 2 处
- geo_service.py: 1 处
- metrics/audience_summary.py: line 205/209/214 加 o. 前缀
- sampling_service.py: line 85 加 o. 前缀
- 防 DuckDB Binder 500 跨 service 复发 (跟 Sprint 60.1 distribution.py:69-70 同模式)
```

**Commit 2** (L4.19 防回归):
```
chore(lint): Sprint 97 L4.19 channel alias ground-truth-lint 防回归

- 新增 backend/scripts/check_channel_alias.py (扫 backend/services/ 全量)
- 新增 backend/tests/test_check_channel_alias.py 3 case regression
- 新增 backend/tests/test_sprint97_channel_alias_coverage.py 7 service coverage
```

**Commit 3** (文档收口):
```
chore(release): Sprint 97 收口 — VERSION bump + STATUS + CHANGELOG + TECH-DEBT + L4.19

- VERSION 0.4.14.155 → 0.4.14.156
- STATUS.md FilterBuilder 治本状态更新
- CHANGELOG.md Sprint 97 entry
- docs/TECH-DEBT.md 加 L4.19 永久规则 + Sprint 60+ 留尾 #1 闭环 + 真治本留尾
```

---

## 5. 后续治本方案 (Claude Stage 4 会写入 TECH-DEBT.md)

Q1=C 是治标推广, 真治本是改 `OrderFilters.channel_in/not_in` 加 `table_alias` 参数:

| 方案 | 说明 | 估时 | ROI |
|------|------|------|-----|
| **真治本** | 改 `OrderFilters.channel_in/not_in(channels, table_alias="o")` + FilterBuilder 加 `self._table_alias` + `with_table_alias()` 方法 + 删全 12 service 的 post-processing | 半天 | 高 (1 处改动 vs 12 处, 0 重复) |
| **保持治标** | 维持 Sprint 97 状态, 接受 ground-truth-lint 防回归 | 0 | 中 (lint 防漏, 但治标代码残留) |

**推荐**: Sprint 98+ 评估做真治本, 删全 12 处 post-processing 重复代码. 留尾给后续 sprint.

---

## 6. 完成定义 (Definition of Done)

- [ ] 5 个 FilterBuilder service 加 post-processing (T1)
- [ ] 2 个手工拼 service 加 `o.` 前缀 (T2)
- [ ] Sprint 60.1 已修 5 个 service verify 不漏 (T3)
- [ ] `backend/scripts/check_channel_alias.py` ground-truth-lint 实现 (T4)
- [ ] `backend/tests/test_check_channel_alias.py` 3 case pass (T4)
- [ ] `backend/tests/test_sprint97_channel_alias_coverage.py` 7 case pass (T5)
- [ ] `STATUS.md` 更新 FilterBuilder 治本状态 (T6)
- [ ] `docs/TECH-DEBT.md` 加 L4.19 永久规则 (T7)
- [ ] `CHANGELOG.md` Sprint 97 entry (T8)
- [ ] `VERSION` = `0.4.14.156` (T9)
- [ ] 全量 pytest 741/21/0 baseline 不漂移 (验证 §3.5)
- [ ] ruff 0 errors (验证 §3.6)
- [ ] 端到端 12/12 curl 200 (验证 §3.7, 本地有 uvicorn 时)
- [ ] 3 个 commit 已 push 到 `fix/sprint97-filter-builder-table-alias` (Stage 4 走)
- [ ] 告知 Claude "Codex 完成", 等待 Stage 3 review
