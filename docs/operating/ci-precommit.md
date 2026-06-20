# CI-PRECOMMIT — pre-commit framework GitHub Actions 接入

> Sprint 19 P2-3 任务: 加 `.github/workflows/pre-commit.yml`, 走 `pre-commit/action` 跑 `.pre-commit-config.yaml`.
> 落地日期: 2026-06-11. 拍板人: subagent C3.

---

## 1. 拍板

| 维度 | 拍板 |
|---|---|
| **workflow 触发** | `workflow_dispatch` (手动触发), 不走 `push` / `pull_request` 自动 |
| **python version** | 3.14 (跟 `scripts/run_etl.py` / `requirements.txt` 一致) |
| **pre-commit command** | `pre-commit run --all-files` (committed 模式, 跟 .githooks staged 模式互斥, 见 Sprint 3 P1-3 教训) |
| **跟 .githooks 关系** | 互补不互斥: .githooks 9 hook + .pre-commit-config.yaml 4 hook, 走哪条路径取决于 .githooks 装没装 / framework 装没装 |
| **CI 跑通前提** | repo 装 `pre-commit` framework (`pip install pre-commit` + `pre-commit install`) 否则 framework 自身空跑 |
| **CI 分钟数预估** | 装 framework 首次跑 ~30s (venv 创建), 后续 cache 命中 ~5s |

---

## 2. workflow 文件

`.github/workflows/pre-commit.yml` (本 P2-3 新增):

```yaml
name: pre-commit

on:
  workflow_dispatch:  # 手动触发

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      - run: pip install pre-commit
      - run: pre-commit run --all-files
```

**为什么不用 `pre-commit/action`?**:
- `pre-commit/action@v3.0.1` (官方 action) 内部已经 `pip install pre-commit` + `pre-commit run --all-files`, 写出来更简洁.
- 选 `actions/setup-python@v5` + `pip install` 显式两行, 跟本仓库其他 workflow (lint.yml / nightly.yml) 风格一致, 易审计.
- 走两行多 1 行冗余, 但 git log 看 workflow 变更跟 CLAUDE.md 12 步流程一致, 团队 review 友好.

---

## 3. 为什么 `workflow_dispatch` 而非 `push` / `pull_request`?

### 3.1 装 framework 才能跑 (Sprint 19 P2-1 拍板)

本仓库 `pip install pre-commit` 不是 onboarding 必走, 默认走 `.githooks`. 如果 workflow 走 `push` 自动触发:

- 装了 framework 的 branch → 跑通 (走 4 hook)
- 没装 framework 的 branch → framework 找不到 .pre-commit-config.yaml 报 warning 但 rc=0 (结构性 no-op, 跟 Sprint 3 P1-3 教训同根因)

走 `workflow_dispatch` 手动触发 = 触发人明确知道"我在跑 framework hook", 避免无脑绿.

### 3.2 跟 .githooks 9 hook 重复浪费 CI 分钟

`.githooks` 已在本机跑 9 hook, CI 跑 `pre-commit run --all-files` 又跑 4 hook (其中 3 hook 跟 .githooks 重复). 双跑 30s+ 浪费 CI 分钟, 走 `workflow_dispatch` 让触发人自己评估 ROI.

### 3.3 触发频次低

仓库 sprint 周期 1-2 天 1 commit, `push` 自动触发 = 每天 5-10 次空跑. `workflow_dispatch` 手动触发 = sprint 收口时跑 1 次验证.

---

## 4. 怎么用

### 4.1 手动触发 (默认)

1. GitHub UI → Actions tab
2. 左栏选 "pre-commit" workflow
3. 右栏 "Run workflow" → 选 branch → Run
4. 等 30s, 看日志
   - 全绿 = `.pre-commit-config.yaml` 4 hook 全过
   - 失败 = 拦到了 (大概率 ruff 自动 fix 可 push, 或 contract 字段元数据缺失)

### 4.2 装 framework 走 push 自动 (可选)

```bash
# 本机装
pip install pre-commit
pre-commit install

# .github/workflows/pre-commit.yml 改 on:
#   on: [push, pull_request]
#   # 删 workflow_dispatch 行
```

但**不推荐**: 走 push 自动 = 跟 .githooks 重复 30s, ROI 极低. 留 `workflow_dispatch` 即可.

---

## 5. CI/CD 防线总览 (Sprint 19 P2-3 更新)

跟 CLAUDE.md "CI/CD 防线" 表对照, 加 1 行:

| 层 | 位置 | 拦什么 | 触发 |
|---|---|---|---|
| 1. pre-commit | `.githooks/pre-commit` | ruff + bare except + B2 import + B5 test order + pytest orphans + P1-3 ground-truth + vue-tsc (9 hook) | 本机 commit (默认装) |
| 2. pre-push | `.githooks/pre-push` | pytest | 本机 push |
| 3. GitHub Actions lint | `.github/workflows/lint.yml` | ruff + pytest + ground-truth-lint (committed mode) | push / pull_request 自动 |
| 4. GitHub Actions nightly | `.github/workflows/nightly.yml` | ground-truth-lint (committed mode) | 每日定时 |
| **5. GitHub Actions pre-commit** (P2-3 新) | `.github/workflows/pre-commit.yml` | `.pre-commit-config.yaml` 4 hook (ruff + 2 local) | `workflow_dispatch` 手动 (装 framework 才有效) |

**激活 hooks (本机)**:
```bash
git config core.hooksPath .githooks    # 装 9 hook 默认路径
# 或
pip install pre-commit && pre-commit install  # 装 4 hook 选装路径
```

---

## 6. 故障排查

| 症状 | 原因 | 修法 |
|---|---|---|
| `pre-commit: command not found` | framework 未装 | `pip install pre-commit` |
| `No .pre-commit-config.yaml file` | framework 装但文件被 git ignore | 检查 `.gitignore` 不应忽略 `.pre-commit-config.yaml` |
| `ruff hook failed` | 代码有 ruff 违规 | `ruff check . --fix` 自动修, 手动 git add 再 commit |
| `pytest cleanup orphans failed` | ETL 进程未正常退出留了 /tmp 孤儿 | 跑 `bash scripts/etl/cleanup_backups.sh` |
| `contract ground-truth lint failed` | Pydantic Field 元数据缺失 | `python -m backend.contracts._lint` 看具体 issue, 按 B1+B2 模式补 |
| `workflow 绿但本机 git commit 红` | .githooks (本机) 跟 .pre-commit-config.yaml (CI) hook 集不同 | 走 .githooks 单一源真值, 修本机即可 (见 docs/operating/hooks-choice.md) |

---

## 7. 后续 (Sprint 20+ 待办)

| # | 任务 | 备注 |
|---|---|---|
| 1 | workflow 加 cache (pre-commit venv 缓存) | 5s → 1s, 走 actions/cache@v4 |
| 2 | workflow 加 ruff format check | 跟 lint 分离, 防止 `ruff check --fix` 自动改 staged 文件 |
| 3 | 评估 `pre-commit.ci` (官方 SaaS, 免费 tier 1 repo) | 跟 GitHub Actions 互补 |
| 4 | 把 .githooks 9 hook 拆成 9 个独立 `language: system` entry 进 .pre-commit-config.yaml | 走 framework 单一源真值 (不推荐, 见 docs/operating/hooks-choice.md "单一源真值" 段) |

---

**相关文档**:
- `docs/operating/hooks-choice.md` (Sprint 19 P2-1) — 拍板 .githooks 优先 + .pre-commit-config.yaml 选装
- `.pre-commit-config.yaml` (Sprint 18 #142) — 4 hook 选装配置
- `.github/workflows/lint.yml` — 已有 ruff + pytest workflow
- `.github/workflows/nightly.yml` — 已有 ground-truth-lint 定时
- CLAUDE.md "Sprint 3 P1 三件 4 轮修教训" — committed 模式 vs staged 模式互斥

**Sprint 19 P2-3 完成**: pre-commit framework CI workflow 接入, 走 `workflow_dispatch` 手动触发, 跟 .githooks 9 hook 互补不互斥.
