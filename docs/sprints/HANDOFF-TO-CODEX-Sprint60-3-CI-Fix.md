# HANDOFF — Sprint 60.3 CI 爆红修复

> **角色**: Codex Stage 2 实施  
> **来源**: Claude Stage 1 架构  
> **范围**: 只治标 (方案 A), 不动业务代码, 不改数据结构  
> **分支**: `fix/ci-lint-and-e2e-2026-06-21` (已创建)  
> **目标**: 让 GitHub Actions main 分支 lint + e2e 不再红, 恢复 CI 信号可用性

---

## 0. 背景 (Context)

GitHub Actions 最近 5 个 run 全红：

| Run | Workflow | Commit | 失败原因 |
|-----|----------|--------|---------|
| 27903913572 | CI | `ea44dd4` Sprint 60+ 收口 | 仍在跑, 预计 ruff 失败 |
| 27903913556 | e2e | `ea44dd4` | `actions/upload-artifact@v3` 已弃用, 4s 自动失败 |
| 27903024298 | CI | `fa6e69f` Sprint 60.2 merge | ruff 8 errors |
| 27903024319 | e2e | `fa6e69f` | e2e 12/12 失败 + upload-artifact@v3 弃用 |

**决策**: 用户选择 **方案 A (治标)**:
1. 修 lint error, 让 CI lint job 绿
2. 升 `upload-artifact@v3` → `v4`
3. e2e job 加 `continue-on-error: true` (跟 Sprint 41 一致), 避免缺 production DuckDB 导致 main 持续红

**后续治本** (不在本次): CI e2e 真实数据缺失问题需要 mock data / seed DuckDB / 数据切片, 单独开 Sprint 评估 ROI。

---

## 1. 任务清单 (Must Do)

### T1 — 修 ruff lint error

涉及 2 个文件：

#### 1.1 `scripts/status_update.py`

当前 5 个 PEP8 错误：

```
E401  line 14: import argparse, os, re, subprocess, sys, tempfile
E702  line 147: print("--- current ---"); print(current)
E702  line 148: print("--- expected ---"); print(new_block.rstrip("\n"))
E701  line 162: try: os.unlink(tmp)
E701  line 163: except OSError: pass
```

**修复要求** (保持行为完全一致)：

```python
# line 14 拆成多行
import argparse
import os
import re
import subprocess
import sys
import tempfile

# line 147-148 去分号
        print("--- current ---")
        print(current)
        print("--- expected ---")
        print(new_block.rstrip("\n"))

# line 161-164 去单行 try/except
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
```

**验证**: `ruff check scripts/status_update.py` 必须 0 errors。

#### 1.2 `backend/tests/test_status_update.py`

当前 3 个错误：

```
F401  line 8: import sys
F541  line 37: f-string without placeholder
F541  line 38: f-string without placeholder
```

**修复要求**:

```python
# 删除 line 8: import sys

# line 37-38 去掉 f 前缀 (字符串里无占位符)
        status_text = (
            "<!-- STATUS-AUTO-START -->\n| a | 1 | x |\n<!-- STATUS-AUTO-END -->\n"
            "<!-- STATUS-AUTO-START -->\n| b | 2 | y |\n<!-- STATUS-AUTO-END -->\n"
        )
```

**验证**: `ruff check backend/tests/test_status_update.py` 必须 0 errors。

---

### T2 — 修 e2e workflow

文件: `.github/workflows/e2e.yml`

#### 2.1 升级 upload-artifact

找到 line 116：

```yaml
      - name: Upload auto-recovery log on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: ci-auto-recovery-log
          path: /tmp/auto_recover_ci.log
```

改为 `actions/upload-artifact@v4`:

```yaml
      - name: Upload auto-recovery log on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: ci-auto-recovery-log
          path: /tmp/auto_recover_ci.log
```

#### 2.2 e2e job 加 continue-on-error

在 job 级别加 `continue-on-error: true`, 让 e2e job 失败不阻塞整个 workflow：

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    continue-on-error: true   # ← 新增
    env:
      ...
```

**原因**: CI runner 没有 `data/processed/fuqing_crm.duckdb` (被 `.gitignore` 排除, 114GB), e2e spec 需要真实数据渲染页面, 在 CI 跑不通。Sprint 41 已确认此限制, 当时也是 `continue-on-error: true`。本次先恢复该策略, 避免 main 持续红。

**验证**: 本地可跑 `python3 -m py_compile scripts/status_update.py backend/tests/test_status_update.py` 无语法错误。GitHub Actions 验证需 push 后由 CI 跑。

---

### T3 — 更新 STATUS.md

文件: `STATUS.md`

找到 "ruff lint" 行 (line 30 附近)：

```markdown
| ruff lint | **2 fixed, 3 留尾 (Sprint 60+)** | Sprint 60+ 修 2 F841 ... |
```

改为反映本次修复：

```markdown
| ruff lint | **0 errors** | Sprint 60.3 修 5 处 status_update.py PEP8 + 3 处 test_status_update.py 留尾 |
```

找到 "GH Actions CI" 行 (line 34 附近)：

```markdown
| GH Actions CI | **4/4 pass (期望)** | Sprint 58 #1 OOM 治本 ... |
```

改为：

```markdown
| GH Actions CI | **3/4 pass + e2e advisory** | Sprint 60.3 修 lint + 升 upload-artifact@v4; e2e 因 CI 缺 production DuckDB 恢复 `continue-on-error: true` (Sprint 41 同策略) |
```

---

### T4 — 更新 docs/TECH-DEBT.md

文件: `docs/TECH-DEBT.md`

找到 "Sprint 60+ 留尾" section (line 10 附近), 更新 ruff 留尾状态：

```markdown
- 📋 **Sprint 60+ ruff 留尾 3** (Sprint 60+ 收口实战新增): `test_status_update.py:8 F401 sys` + `37+38 F541 extraneous f prefix` (Sprint 59 #6 status_update.py test 留尾, Sprint 60.3 闭环, 0.5h)
```

改为：

```markdown
- ✅ **Sprint 60+ ruff 留尾 3 闭环**: `test_status_update.py:8 F401 sys` + `37+38 F541 extraneous f prefix` (Sprint 60.3 修)
- 📋 **CI e2e 真实数据缺失**: CI runner 无 `data/processed/fuqing_crm.duckdb`, e2e 恢复 `continue-on-error: true` 治标, 治本需 seed/mock DuckDB (推后评估)
```

---

### T5 — 更新 CHANGELOG.md

在 `CHANGELOG.md` 顶部新增 Sprint 60.3 entry (按现有格式)：

```markdown
## [0.4.14.148] - 2026-06-21

### Fixed
- Sprint 60.3 修 CI lint 8 errors (`scripts/status_update.py` 5 PEP8 + `backend/tests/test_status_update.py` 3 ruff)
- 升 `actions/upload-artifact@v3` → `v4` 修复 e2e workflow 自动失败

### Changed
- e2e CI job 恢复 `continue-on-error: true`: CI runner 缺 production DuckDB, 先治标避免 main 持续红, 后续 Sprint 评估 seed/mock 数据治本
```

---

### T6 — bump VERSION

文件: `VERSION`

`0.4.14.147` → `0.4.14.148`

---

## 2. 禁止事项 (Must NOT Do)

- ❌ 不要改业务代码 (backend/services/, backend/routers/, frontend-vue3/src/)
- ❌ 不要改 Pydantic contract
- ❌ 不要尝试在 CI 里跑 ETL 生成真实数据 (本次范围外)
- ❌ 不要把 production DuckDB 提交到 git
- ❌ 不要改 e2e spec 本身
- ❌ 不要删 `Setup DuckDB ATTACH` 步骤 (保留, 后续治本时可用)

---

## 3. 验证步骤 (Codex 完成后必须跑)

```bash
# 1. ruff 验证
ruff check scripts/status_update.py backend/tests/test_status_update.py
# 期望: 0 errors

# 2. Python 语法验证
python3 -m py_compile scripts/status_update.py
python3 -m py_compile backend/tests/test_status_update.py

# 3. status_update.py 回归测试
PYTHONPATH="$(pwd)" pytest backend/tests/test_status_update.py -v
# 期望: 3/3 pass

# 4. GitHub Actions workflow YAML 语法检查 (可选)
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/e2e.yml'))"

# 5. 全量 pytest (本地有 production DuckDB 时)
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
# 期望: 748/21 baseline
```

---

## 4. Commit 规范

分 2 个 commit (按逻辑拆分)：

**Commit 1**:
```
fix(ci): Sprint 60.3 修 ruff 8 errors

- scripts/status_update.py: 拆多行 import / 去分号 / 去单行 try-except
- backend/tests/test_status_update.py: 删未使用 sys import / 去多余 f 前缀
```

**Commit 2**:
```
ci(e2e): 升 upload-artifact@v4 + 恢复 continue-on-error

- actions/upload-artifact@v3 → v4 (GitHub 弃用自动失败)
- e2e job 加 continue-on-error: true, CI runner 缺 production DuckDB,
  先恢复 Sprint 41 策略避免 main 持续红
```

**Commit 3** (文档收口):
```
chore(release): Sprint 60.3 CI fix 收口 — VERSION bump + STATUS + CHANGELOG + TECH-DEBT
```

---

## 5. 后续治本方案 (Claude Stage 4 会写入 TECH-DEBT.md)

e2e CI 真实数据缺失是结构性问题, 3 个候选方案待后续 Sprint 评估：

| 方案 | 说明 | ROI/风险 |
|------|------|---------|
| A. 提交 seed DuckDB | 把一小部分脱敏数据做成 10-50MB seed DB 提交到 `frontend-vue3/e2e/data/` | 简单, 但大文件进 git, 数据更新麻烦 |
| B. CI 跑 ETL 生成 mock | workflow 里跑简化 ETL 生成 1M 订单量 | 30-60min, 占 CI 时间, 但数据可控 |
| C. e2e spec 降级为纯 UI smoke | 不依赖 API 数据, 只验证路由/组件/无控制台 error | 覆盖弱, 但最稳, 适合 CI nightly |

推荐后续由产品经理拍板: 是接受 CI e2e advisory (继续 continue-on-error), 还是投入 1-2d 做 seed 数据让 e2e blocking。

---

## 6. 完成定义 (Definition of Done)

- [ ] `ruff check scripts/status_update.py backend/tests/test_status_update.py` → 0 errors
- [ ] `backend/tests/test_status_update.py` 3/3 pass
- [ ] `.github/workflows/e2e.yml` 使用 `upload-artifact@v4`
- [ ] `.github/workflows/e2e.yml` e2e job 有 `continue-on-error: true`
- [ ] `VERSION` = `0.4.14.148`
- [ ] `CHANGELOG.md` / `STATUS.md` / `docs/TECH-DEBT.md` 已更新
- [ ] 3 个 commit 已 push 到 `fix/ci-lint-and-e2e-2026-06-21`
- [ ] 告知 Claude "Codex 完成", 等待 Stage 3 review
