# HOOKS-CHOICE — .githooks vs .pre-commit-config.yaml 拍板

> **Sprint 19 P2-1 拍板**：本仓库 git hook 框架 = **`.githooks` (默认)**, `.pre-commit-config.yaml` 留作选装 (不会默认启用).
> 拍板日期: 2026-06-11. 拍板人: subagent C3 (Sprint 19 P2 批处理).

---

## 1. 拍板结论

| 维度 | 拍板 | 理由 |
|---|---|---|
| **默认框架** | `.githooks` (走 `git config core.hooksPath .githooks`) | 已在 Sprint 3-18 累积 6 件 lint (ruff + bare except + B2 import + B5 test order + pytest orphans + P1-3 ground-truth + vue-tsc), 装 1 次 (`bash scripts/setup-hooks.sh`) 立刻全开. |
| **pre-commit framework** | 选装 | 装包 (`pip install pre-commit`) 才能用, 跟 ruff-pre-commit hook 跟 `ruff` 命令有功能重复. 留 `.pre-commit-config.yaml` 是给希望"走业界标准"的同学/未来维护者备用. |
| **CI 接入** | Sprint 19 P2-3 加 `.github/workflows/pre-commit.yml`, 默认 disable (workflow 文件常驻但不主动跑), 留给"装 framework 的同学"通过 `pre-commit run --all-files` 触发. | 见 P2-3. |

**任何新人 onboarding**:
1. 走 `bash scripts/setup-hooks.sh` (装 `.githooks` 默认路径) — 一步到位.
2. (可选) `pip install pre-commit && pre-commit install` — 装 framework 跑 `.pre-commit-config.yaml` 4 hook.
3. (可选) 在 CI 启用 `.github/workflows/pre-commit.yml` — 装 framework 才能跑.

---

## 2. 两个框架对比

### `.githooks/pre-commit` (默认, 推荐)

**结构**: bash 脚本 + 4 个 Python lint 助手 (check_imports / check_test_order / check_review_ground_truth / pre-commit 主脚本) + `pre-push`.

**装的 hook 列表** (Sprint 18 #142 累积):
1. **CHANGELOG 跟随** — 改 `.py` / `docs/` 必须同步改 `CHANGELOG.md` (P2 散点).
2. **bare except 拦截** — 扫 `except:` 防静默吞噬 (Sprint 4 P2 散点).
3. **ruff check** — lint, `--quiet` 模式.
4. **B2 import 完整性** — `.githooks/check_imports.py` 扫 3rd-party imports 跟 `requirements.txt` 对账 (Sprint 4 B2 根因预防).
5. **B5 test order lint** — `.githooks/check_test_order.py` 扫 N-index 断言 (Sprint 4 B5 教训, WARN 不阻断).
6. **pytest cleanup orphans** — `pytest backend/tests/test_wo_cleanup_orphans.py -q` (Sprint v0.4.7).
7. **P1-3 review ground-truth lint** — `.githooks/check_review_ground_truth.py` 拦 `未集成 / 不存在 / 占位` 触发词必须有 git log 实证 (Sprint 3 P1-3 教训).
8. **Sprint 14 A.2 contract 同步 WARN** — 改 `backend/contracts/*.py` 提醒跑 codegen (不阻断, WARN).
9. **vue-tsc 真编译** — 改 `frontend-vue3/src/**.vue` 强制 `vue-tsc --noEmit` (Sprint 14 教训, 阻断).

**安装**: `git config core.hooksPath .githooks` (one-line, 无 framework 依赖).

**优点**:
- 零依赖 (纯 bash + Python stdlib + ruff 已装).
- 装一次立刻全开 9 件 lint, 跟 `scripts/setup-hooks.sh` 一步到位.
- 跟 CLAUDE.md "CI/CD 防线" 表一致.

**缺点**:
- 不是业界标准 framework, 维护者需读 bash 脚本了解具体拦截.
- 没法在 GitHub Actions 直接复用 (需另写 workflow).

### `.pre-commit-config.yaml` (选装, 不默认启用)

**结构**: 1 个 ruff hook (astral-sh/ruff-pre-commit) + 2 个 local hook (pytest cleanup orphans + contract ground-truth lint). 4 件 hook 总数.

**优点**:
- 业界标准 (`pre-commit` framework 跨语言跨项目).
- 跟 GitHub Actions 集成开箱 (`pre-commit/action`).
- ecosystem hook 库丰富 (mypy / black / isort / 各种语言).

**缺点**:
- **装包才能用** (`pip install pre-commit`), 新人 onboarding 缺一步.
- **跟 `.githooks` 重复拦截**: ruff / pytest orphans / contract ground-truth lint 都有双份. 跑双份浪费时间, 跑单份可能漏 lint.
- **没拦**: bare except / B2 import / B5 test order / P1-3 ground-truth / vue-tsc — 这些 `.githooks` 有但 `.pre-commit-config.yaml` 没.
- **维护者认知负担**: 改 hook 要同步 2 处, 容易漂移.

---

## 3. 为什么不上 `.pre-commit-config.yaml`?

### 3.1 框架依赖负担

`pre-commit` framework 装包后, 第一次跑 `pre-commit run` 会创建隔离 venv 装 ruff / pytest, **本机 5-10s 起步, CI 30s+**. 本仓库 `ruff` + `pytest` 早已在 `requirements.txt` / `pyproject.toml` 装好, 走 framework 重复装浪费.

### 3.2 功能覆盖度低

`.pre-commit-config.yaml` 只有 4 件 hook, `.githooks` 有 9 件. 走 framework 漏 lint, 走双份浪费时间. 不上.

### 3.3 历史教训

Sprint 3 P1-3 教训 #3 (CLAUDE.md "Sprint 3 P1 三件 4 轮修教训"):
> CI 跑 committed 模式 vs 本地 staged 模式互斥: `check_review_ground_truth.py` 旧实现只读 `git diff --cached` → CI 跑已 commit 文件永远 0 字节 → 永远 rc=0, 是结构性 no-op.

`pre-commit` framework 跑 hook 默认 staged 模式, 跟 `pre-commit/action` 跑 `--all-files` 行为不同. 加 `language: system` 走本机命令虽然统一, 但又退化成"类 `.githooks`"的 bash 模式, 失去 framework 价值.

### 3.4 跟 Sprint 3-18 治理脱节

本仓库已有 9 件 lint 散落在 `.githooks/*`, 加 `.pre-commit-config.yaml` = **重复维护 4 件 + 缺 5 件** = 治理倒退. 留作选装 = 未来维护者愿意走"业界标准路线"时直接 `pre-commit install`, 不会打断当前 9 件 lint.

---

## 4. 怎么用 (新人 onboarding)

### 4.1 默认路径 (1 分钟)

```bash
cd "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"
bash scripts/setup-hooks.sh        # 装 .githooks 路径
git commit -m "feat: xxx"           # 9 件 lint 自动跑
```

### 4.2 选装路径 (3 分钟, 不推荐)

```bash
pip install pre-commit
pre-commit install                  # 装 .pre-commit-config.yaml 4 hook
# 注: 跟 .githooks 重复, ruff / pytest orphans 跑 2 次
```

### 4.3 CI 集成 (Sprint 19 P2-3)

`.github/workflows/pre-commit.yml` 已加, 默认 disable 状态 — workflow 文件常驻不主动跑, **只在装了 framework 的 repo 分支 (e.g. 未来切到 `ci/use-pre-commit-framework` 分支) 才有效**. 改 `on: [push, pull_request]` 为 `on: workflow_dispatch` 即可手动触发.

详见 `docs/operating/ci-precommit.md` (Sprint 19 P2-3).

---

## 5. 改 hook 流程

| 改什么 | 改 `.githooks/`, 走 setup-hooks.sh 重装 (无需 commit) |
|---|---|
| 加新 hook (e.g. mypy) | 写 `.githooks/check_mypy.py` + 加进 `.githooks/pre-commit`. 同步 (可选) 加进 `.pre-commit-config.yaml` 给选装用户. |
| 改 hook 逻辑 | `.githooks/check_*.py` 是纯 Python, 加 `# noqa: BLE001` 兜底. 同步 (可选) 改 `.pre-commit-config.yaml` 同一段 entry. |
| 拦新触发词 (e.g. P1-3 词表) | 改 `.githooks/check_review_ground_truth.py` 跟白名单常量. 不需同步 pre-commit (P1-3 本身就是 `.githooks` 专属). |

**单一源真值**: `.githooks/*` 是 9 件 lint 的真值, `.pre-commit-config.yaml` 是 partial mirror (4 hook).

---

## 6. 拍板签字

| 角色 | 决策 | 日期 |
|---|---|---|
| AI (subagent C3) | 拍板 `.githooks` 优先 + `.pre-commit-config.yaml` 选装 | 2026-06-11 |
| 用户 (后续可推翻) | TBD | (主分支上 review 时确认) |

---

**相关文档**:
- `CLAUDE.md` "CI/CD 防线" 表 — 4 层 hook 总结
- `docs/operating/ci-precommit.md` (Sprint 19 P2-3) — GitHub Actions workflow 拍板
- `docs/operating/linting.md` (Sprint 17 #121) — ground-truth-lint 规则
- `docs/operating/pre-commit.md` (Sprint 18 #142) — 接入 pre-commit hook 教训

**Sprint 19 P2-1 完成**: `.githooks` 拍板, `.pre-commit-config.yaml` 选装, CLAUDE.md "AI 执行检查点" 改 contract 字段行加 1 行说明.
