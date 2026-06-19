# Pre-Commit Hooks — 芙清 CRM (Sprint 18 #142)

> 在 `git commit` 之前自动跑 ground-truth-lint, 拦截 LLM / human dev 写不合规的 contract 字段.

## 1. 简介

### 1.1 背景

Sprint 17 #121 加了 `backend/contracts/_lint.py` ground-truth-lint, 4 条规则 (R1-R4) 强制
contract ratio/pct/ppt 字段用 Pydantic `RatioField` / `PercentageField` / `PpField` 或
`Annotated[float, Field(ge, le)]`. Sprint 18 #142 把这个 lint 接进 `pre-commit` framework,
在 `git commit` 之前自动跑, 拦截不合规 commit.

### 1.2 跟 Sprint 3 P1-3 关系

Sprint 3 P1-3 已经接了 ground-truth-lint 钩子 (在 `.githooks/pre-commit` 里). Sprint 18 #142
改用 `pre-commit` framework, 跟现代 Python 生态 (pre-commit.com) 对齐, 跟 ruff / 其它 hook
统一管理.

### 1.3 跟现有 CI/CD 防线关系

| 层 | 位置 | 拦什么 | Sprint 18 #142 改动 |
|----|------|--------|---------------------|
| pre-commit (local) | `.githooks/pre-commit` | ruff + pytest (20/8 cleanup) + ground-truth lint (P1-3 sprint 3) | **保留** (向后兼容) |
| pre-commit (framework) | `.pre-commit-config.yaml` | ruff + ground-truth-lint (Sprint 18 #142) | **新增** contract-ground-truth-lint hook |
| pre-push | `.githooks/pre-push` | pytest | 不动 |
| GitHub Actions | `.github/workflows/lint.yml` | ruff + pytest + ground-truth-lint (committed mode) | 不动 |
| GitHub Actions | `.github/workflows/nightly.yml` | ground-truth-lint (committed mode) | 不动 |

**关键**: 现有 `.githooks/pre-commit` 仍然有 ground-truth-lint 逻辑 (P1-3 sprint 3 时代).
Sprint 18 #142 在 `.pre-commit-config.yaml` 加相同 hook. 两个 hook 互补 — 一边用 framework
(pre-commit.com), 一边用 git 自带 hooks. 任何一边启用都能拦截.

## 2. 安装

### 2.1 装 pre-commit framework (一次性)

```bash
# 推荐: 用 pipx 装 (系统隔离)
pipx install pre-commit

# 或: 用 uv tool
uv tool install pre-commit

# 或: 用 pip 装 (需要 --break-system-packages or venv)
pip3 install --user pre-commit

# 验装成功
pre-commit --version
# 期望: pre-commit 3.x 或 4.x
```

### 2.2 装 framework 自带 hook 环境 (一次性)

```bash
# 在 repo root 跑, pre-commit 会读 .pre-commit-config.yaml, 装 ruff 环境
pre-commit install

# 期望: 看到 "pre-commit installed at .git/hooks/pre-commit"
# (跟 .githooks 独立, 互不覆盖 — pre-commit framework 装到 .git/hooks/pre-commit,
#  跟 .githooks 不冲突, 取决于 git config core.hooksPath)
```

**注意**: 如果项目用 `git config core.hooksPath .githooks` (芙清 CRM 默认), 那
pre-commit framework 装的 `.git/hooks/pre-commit` **会被忽略** (因为 git 只看
`core.hooksPath` 指向的目录). 见 §5 跟 .githooks 兼容性.

## 3. 启用

### 3.1 模式 A: 跟现有 .githooks 一起用 (推荐)

保持 `git config core.hooksPath .githooks`, 跑:

```bash
# 一次性激活 .githooks (项目默认, 但要确认)
git config core.hooksPath .githooks
bash scripts/setup-hooks.sh  # 装 git hook 环境
```

`.githooks/pre-commit` 仍然跑 ruff + pytest (20/8 cleanup) + ground-truth-lint. 不需要
pre-commit framework. Sprint 18 #142 加 `.pre-commit-config.yaml` 是给用 pre-commit
framework 的人用.

### 3.2 模式 B: 切到 pre-commit framework (可选)

如果团队决定迁移到 pre-commit framework:

```bash
# 1. 卸 .githooks
git config --unset core.hooksPath
# (或: git config core.hooksPath .git/hooks)

# 2. 装 pre-commit framework
pipx install pre-commit
pre-commit install

# 3. 跑验证
pre-commit run --all-files
# 期望: ruff + contract-ground-truth-lint 全过
```

**当前状态 (Sprint 18)**: 芙清 CRM 默认用 `.githooks/` (模式 A). Sprint 18 #142
**双轨并存** — 不动 `.githooks/`, 在 `.pre-commit-config.yaml` 加同样 hook 供愿意
切到 framework 的开发者用.

## 4. 触发什么

### 4.1 Hook 列表 (`.pre-commit-config.yaml`)

```yaml
- ruff: ruff lint (v0.15.15) + auto-fix
- pytest-cleanup-orphans: 跑 test_wo_cleanup_orphans.py 验 ETL 清理
- contract-ground-truth-lint (Sprint 18 #142): 跑 python -m backend.contracts._lint
```

### 4.2 触发时机

| 操作 | 触发 hook |
|------|-----------|
| `git commit` | pre-commit (default) |
| `git commit --no-verify` | **跳过** (紧急用, 但 Sprint 18 #142 强烈不建议) |
| `pre-commit run --all-files` | 手动跑全部 hook, 不需要 commit |
| `pre-commit run contract-ground-truth-lint` | 只跑 contract hook |
| `pre-commit run spec-lint` | 只跑 e2e spec hook (Sprint 42 #S42-1) |

### 4.3 contract-ground-truth-lint 怎么跑

```bash
# Hook entry
entry: python -m backend.contracts._lint
language: system
pass_filenames: false
files: 'backend/contracts/.*\.py$'
```

### 4.4 e2e spec 写法 lint (L2 AST parser)

Sprint 50.1 起, pre-commit 默认跑 L2 AST parser (`frontend-vue3/e2e/lint/spec-lint-l2.sh`):

```bash
# 直接跑 (从项目根目录运行, L2 可用时走 L2, tree-sitter 不可用时自动 fallback L1)
bash frontend-vue3/e2e/lint/spec-lint-l2.sh

# 或从 frontend-vue3 目录用 npm script (script 内已传 e2e 参数)
cd frontend-vue3
npm run lint:spec
```

L2 依赖 Python 包 `tree-sitter` + `tree-sitter-typescript`。如果本地没装, wrapper 会 fallback 到 L1 (`spec-lint.sh`) 并提示:

```bash
pip install tree-sitter tree-sitter-typescript
```

规则:
- Rule 1 (FAIL): 不 hardcode 业务数据长度 (`expect(...length).toBe(N)`)
- Rule 2 (FAIL): 不 `waitForTimeout` 死等
- Rule 3 (WARN): `page.request` 缺 `Authorization` header

Regression tests:
- `bash frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` (L1, 3 case)
- `bash frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh` (L2, 5 case)

## 5. 跳过

### 5.1 单次跳过

```bash
git commit --no-verify -m "emergency: hotfix"
# 跳过所有 pre-commit hook
```

### 5.2 只跳过 contract hook

```bash
SKIP=contract-ground-truth-lint git commit -m "..."
# 跳过 contract hook, 其它 (ruff 等) 仍跑
```

### 5.3 跳过的合法场景

- **hotfix production**: 紧急修一行配置, lint 还没更新 → `--no-verify`
- **批量重命名**: e.g. 改 `yoy_*_ratio` → `yoy_*_ppt` 涉及 26 字段, 中间态 lint 会
  fail → 改完再一次性 commit, 不用 `--no-verify`
- **worktree 测试**: 临时改 worktree 验证, 不想 commit 拦截 → `--no-verify`

### 5.4 不应跳过的场景

- 写新 contract 不知道合不合规 → 应跑 lint 学规则, 不应跳过
- Sprint X 跑批后忘了清 lint issue → 应修 issue, 不应跳过

## 6. 跟 Sprint 17/18 关系

### 6.1 Sprint 17 #121 (ground-truth-lint 工具)

Sprint 17 #121 写了 `backend/contracts/_lint.py` 工具. Sprint 18 #142 把它接进
pre-commit framework. 工具代码本身**没动** (跟 #142 scope 一致: "不要动 _lint.py
主体").

### 6.2 Sprint 18 #141 (26 YOY 命名冲突治根)

Sprint 18 #141 把 26 个 `yoy_*_ratio` 字段 (实际是 PpField 不是 RatioField) 改命名
为 `yoy_*_ppt` (or 改 _lint.py 加 YOY 白名单). #142 跟 #141 同步:

| #141 状态 | #142 状态 | lint 行为 |
|-----------|-----------|-----------|
| 26 issue 残留 (主分支) | 装了 hook | hook fail 拦 commit (期望行为) |
| 26 issue 修完 | 装了 hook | hook pass 0 issue (期望行为) |

**当前** (Sprint 18 #141 进行中): lint 仍有 26 issue, hook 触发会 fail. 这是
**期望** — 治根靠改命名, hook 是辅助. Sprint 18 收口时 #141 修完 → lint 0 issue
→ hook 自动 pass.

### 6.3 Sprint 3 P1-3 (ground-truth-lint 第一版)

Sprint 3 P1-3 在 `.githooks/pre-commit` 写 ground-truth-lint 钩子. Sprint 18 #142
**复制** 到 `.pre-commit-config.yaml` 供 framework 用户用. 两者并存, 不冲突.

### 6.4 Sprint 16.5 #91 (B2 试点)

Sprint 16.5 #91 找 9 mark 字段补 Pydantic 标. Sprint 18 #142 hook 跑会拦任何
**未来** 9 字段式漏标 — 是 B2 模式治根的延伸.

## 7. CI 集成

### 7.1 GitHub Actions 怎么用

`lint.yml` 已经跑 `python -m backend.contracts._lint` 在 CI. Sprint 18 #142 不改
CI (跟 plan 一致, "不要动 CI").

如果将来想把 pre-commit framework 接到 CI:

```yaml
# .github/workflows/lint.yml
- name: Run pre-commit
  uses: pre-commit/action@v3.0.1
  with:
    extra_args: --all-files --show-diff-on-failure
```

但当前 CI 直接跑 `python -m backend.contracts._lint` 更直接, 没必要绕 framework.

### 7.2 本地 vs CI 行为一致

| 场景 | 本地 pre-commit framework | CI (lint.yml) |
|------|---------------------------|----------------|
| 改 contract 加漏标字段 | hook fail, commit 拦 | CI fail, PR 拦 |
| 改 contract 全合规 | hook pass, commit 通过 | CI pass, PR 通过 |

两处行为一致 — 都是跑 `python -m backend.contracts._lint` 看 0 issue.

## 8. 故障排查

### 8.1 `pre-commit: command not found`

装 framework. 见 §2.1.

### 8.2 Hook 跑 timeout

`pre-commit` default timeout 120s. `python -m backend.contracts._lint` 应该 1-2s 内
跑完. 如果 timeout:

```bash
# 手动跑看时间
time python -m backend.contracts._lint
# 期望 < 5s
```

如果慢 (>30s), 检查:
- 是不是 import 了重模块 (e.g. pandas / duckdb)
- 是不是 contract 文件太多 (Sprint 18 有 14 contract 文件, 应该 < 1s)

### 8.3 Hook 跟 .githooks/pre-commit 冲突

不冲突. pre-commit framework 装到 `.git/hooks/pre-commit`, `.githooks/pre-commit`
只在 `core.hooksPath=.githooks` 时生效. 两者二选一.

```bash
# 看当前是哪个生效
git config core.hooksPath
# 期望输出: .githooks (芙清 CRM 默认) 或 empty (用 framework)

# 切到 framework
git config core.hooksPath .git/hooks
pre-commit install
```

### 8.4 Hook 报错 "无法 import backend.contracts._lint"

`pre-commit` framework 跑 hook 时 **不自动设 PYTHONPATH**. 当前 `entry:
python -m backend.contracts._lint` 假设从 repo root 跑 (有 PYTHONPATH) 或 python
默认能找到 `backend`. 如果 import 失败, 改 entry:

```yaml
entry: bash -c 'PYTHONPATH="$(pwd)" python -m backend.contracts._lint'
```

或装成 console_script (e.g. `fq-crm-lint`) 加到 pyproject.toml `[project.scripts]`.

**当前** (Sprint 18 #142): 用 `python -m backend.contracts._lint`, 假设从 repo root
跑 (pre-commit framework 默认 cwd = repo root). 验证: 见 `scripts/test-precommit.sh`.

## 9. 验证 hook 触发

跑 `scripts/test-precommit.sh` 验证:

```bash
bash scripts/test-precommit.sh
# 期望输出:
#   1) baseline: lint passes (after #141 done) or fails (with 26 issue)
#   2) bad change: lint fails with N issue
#   3) revert: lint passes again
```

详细见 `scripts/test-precommit.sh` 注释.

## 10. 已知限制

### 10.1 local hook 跨开发者兼容性

`pre-commit` framework 装 hook 时, **不会** 自动装 Python 包. local hook
`python -m backend.contracts._lint` 跑本机 Python 3.x 解释器. 如果开发者没装
Python 或装在 venv 里, hook 跑失败.

解决:
- 改用 Docker image hook (复杂)
- 改用 `language: python` + `additional_dependencies` (framework 自动装, 但慢)
- 文档说明开发者需要 Python 3.10+ + `pip install -e .` (当前方案)

### 10.2 跟 .githooks 双轨并存的负担

`.githooks/pre-commit` 跟 `.pre-commit-config.yaml` 都有 ground-truth-lint. 二者
重复. Sprint 19 考虑二选一 (推荐保留 .githooks, 它装更轻量).

### 10.3 不影响运行时

pre-commit hook 是**开发者工具**, 不影响 backend runtime. backend 跑
`uvicorn backend.main:app` 时不跑 pre-commit. 所以 hook 加错 (e.g. entry 写错)
**不会** 引起生产 500 / 422. 但可能拦 developer 提 PR → 治根靠改 hook entry.

## 11. 变更历史

| 版本 | 日期 | 改动 | 作者 |
|------|------|------|------|
| v0.4.14.46 | 2026-06-11 | Sprint 18 #142 — .pre-commit-config.yaml 加 contract-ground-truth-lint hook + docs + test script | subagent #142 |

## 12. 相关链接

- 工具代码: `backend/contracts/_lint.py` (Sprint 17 #121, 260 行)
- 工具文档: `docs/LINTING.md` (Sprint 17 #121, 4 条规则详细)
- 配对配置: `.githooks/pre-commit` (Sprint 3 P1-3, ground-truth-lint 第一版)
- 配对配置: `.pre-commit-config.yaml` (Sprint 18 #142, framework 版)
- 任务来源: `CHANGELOG.md` v0.4.14.41 (Sprint 17 #121)
- 计划: Sprint 18 Plan agent 段 B
- 26 命名冲突治根: Sprint 18 #141
- B1+B2 模式: `CLAUDE.md` Ratio Convention 章节 (Sprint 17 #122)
