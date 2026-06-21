# Sprint 58 架构设计 — 工具链实战 fix 闭环 (CI e2e 持久化 + OOM 治本 + commit-msg blocking)

> **Sprint 58 实施架构 (2026-06-21, v0.4.14.141 起步, main HEAD `e77f2de`)**
> 主题: 工具链实战 fix 闭环 (3 项串行, 4d, 12 步流程必走, 涉及 CI 改动高风险)
> Sprint 57 留尾 7 项 → Sprint 58 闭环 3 项 (#4 + #1 + #2), 留 Sprint 59/60+ 共 4 项 (#6 + #5 + #8 + #3)

---

## Context

Sprint 57 收口后留尾 7 项 (从 Sprint 56 留尾 10 项 -30%)。Sprint 58 闭环**3 项串行** (高 ROI 工具链实战 fix 主题, 跟 Sprint 53 race flake 治本同等级, 必须治本 + 持久化 + blocking 三件套一次闭环避免再 push 到 Sprint 60+)。

**为什么 Sprint 58 必须做**:
- **#4 持久化**: Sprint 41 12 follow-up 实战 fix 治标未持久化导致 Sprint 55 复发 5+ 次, 这次必须治本避免循环
- **#1 OOM 治本**: 跨 sprint 5+ 复发 (#14, Sprint 32.1 → 41 → 55 → 57), 跨 sprint recurring e2e CI 50+MB OOM 治标 `continue-on-error: true`
- **#2 blocking**: Sprint 52 WARN hook 已实装, 但 WARN → blocking 升级未做, 误报率高推后至今 (Sprint 32.3+35 教训)

**目标**:
- 闭环 Sprint 41+55+57 跨 sprint 治标 → Sprint 58 治本
- pytest / e2e / CI 三件套一次收口, 0 复发
- CI runner 实测 PASS (50+MB 数据 OOM 治本)
- commit-msg blocking hook 误报率 ≤ 5% (N≥20 commit 验证)

---

## 现状

### Sprint 57 闭环产物 (Sprint 58 输入)

| 产物 | 状态 | Sprint 58 用 |
|------|------|-------------|
| `docs/development/LESSONS_LEARNED.md` (9 项实战 fix pattern) | ✅ Sprint 57 收口 | Pattern #6 "12 步流程 + 5 follow-up 实战 fix 模式" + Pattern #7 "破坏→验证→恢复" + Pattern #8 "commit msg↔diff 一致性 check" |
| `docs/operating/ci-e2e-history.md` (Sprint 41 12 follow-up 记录) | ✅ Sprint 41 创建 | #4 持久化基于此扩展 |
| `docs/architecture/50m-scale-architecture.md` (50M benchmark) | ✅ Sprint 52 创建 | #1 OOM 治本参考 |

### 当前 worktree 状态 (Stage 2 起点)

```
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics                  e77f2de [main]
(Sprint 58 启动后创建 3 个 worktree)
  feat/sprint58-04-e2e-persist       #4 CI e2e 持久化
  feat/sprint58-01-oom-fix          #1 e2e OOM 治本
  feat/sprint58-02-commit-msg-block #2 commit-msg blocking
```

**Stage 2 起点**: main HEAD `e77f2de` 切出 3 个独立 worktree, 各自 commit, Stage 4 串行合并 (跟 Sprint 57 模式一致)。

---

## 三项改动清单 (串行)

### 串行依赖图

```
wt-04 (#4 CI e2e 持久化)
    ↓ 收口 + 12 步流程 (commit + push + merge)
    ↓ 提供持久化 reference + auto-recovery script
wt-05 (#1 OOM 治本)
    ↓ 依赖 #4 持久化 (避免再复发)
    ↓ 切片 + DuckDB ATTACH + CI runner 适配
    ↓ 跑 N 次 e2e 收 sample (验证 #2 误报率基础)
wt-06 (#2 commit-msg blocking)
    ↓ 依赖 #1 sample (验证 blocking 误报率 ≤ 5%)
    ↓ WARN → blocking (跟 Sprint 52 WARN hook 升级)
```

**为什么串行不能并行**:
- #1 OOM 治本不持久化, 下次 sprint 又复发 (Sprint 41 治标教训)
- #2 blocking 升级前需要 #1 收 N 次 commit sample 验证误报率
- 12 步流程不能省 review/qa (CI 改动高风险)

### #4 CI e2e 实战 fix 持久化 (worktree-04, 1d)

**新建/扩**:
- `docs/operating/ci-e2e-history.md` (扩): Sprint 41 12 follow-up + Sprint 55 4 follow-up + Sprint 57 实战 fix 完整历史 + 持久化 reference
- `scripts/ci/auto_recover_ci.sh` (新建): CI runner fail 时自动 recovery (cache cleanup + retry)
- `.github/workflows/e2e.yml` (改): 加 auto-recovery 步骤 + `docs/operating/ci-e2e-history.md` SSOT 链 (Codex 反馈修复: 避免断链引用)

**关键技术决策**:
- **持久化模式**: Sprint 41 12 follow-up 实战 fix 写入 `docs/operating/ci-e2e-history.md` + `scripts/ci/auto_recover_ci.sh` (跟 Sprint 25 backup 系统持久化模式一致)
- **auto_recovery 范围**: cache cleanup + pytest rerun + retry 1 次 (不破坏 e2e 测试完整性)
- **CI runner 适配**: 50MB / 100MB / 500MB 三档 memory limit 区分 (跟 50m-scale-architecture.md 对齐)

**验证**:
- 本地模拟 CI runner fail → auto_recover_ci.sh 自动 recovery → pytest 重新 PASS
- GitHub Actions 跑 5 次连续 PASS (无 fail 触发 auto-recovery)

### #1 e2e OOM 治本 (worktree-05, 2d, 依赖 #4)

**改**:
- `frontend-vue3/e2e/data/` (改): 切片策略 (e2e data 50MB → 5-10MB 子集)
- `.github/workflows/e2e.yml` (改): 加 DuckDB ATTACH read_only 步骤 (跟 Sprint 53 race flake 治本模式一致)
- `frontend-vue3/playwright.config.ts` (改): `workers: 1` + `timeout: 60000` 降低内存峰值

**关键技术决策**:
- **DuckDB ATTACH read_only 模式**: 跟 Sprint 53 race flake 治本一致 (per-worker tmp + ATTACH production read_only), 让 CI runner 不需要复制 50MB data, 走 read_only ATTACH
- **切片策略**: 保留 11 spec 全覆盖, 但每个 spec 用 5-10MB 数据子集 (跟 prod 数据 schema 一致)
- **不要做的事**:
  - 不 bump VERSION (`continue-on-error: true` 治本比 Sprint 55 治标更彻底, 不需要 bump)
  - 不删除任何 e2e spec (保持 11 spec 全覆盖, 只改 data + runner config)

**验证**:
- GitHub Actions 跑 5 次连续 PASS (50+MB 数据 OOM 治本, 无需 `continue-on-error`)
- 本地 `pytest backend/tests/` + `npx playwright test` 全绿

### #2 commit-msg blocking hook (worktree-06, 1d, 依赖 #1)

**改**:
- `.githooks/commit-msg` (改): WARN → blocking (Sprint 52 WARN hook 升级)
- `scripts/commit_msg_check.py` (新建): commit-msg drift 检测 (跟 Sprint 35 教训一致, a9b1d91 commit msg 说"清理"但实际 diff 1398 行)
- `.githooks/pre-commit` (改): 加 commit-msg check 链路

**关键技术决策**:
- **升级前 N=20 commit sample 验证**: 收 #1 实施后 20+ commit, 跑 WARN hook, 统计误报率 ≤ 5% 才升级 blocking
- **误报率超标 fallback**: 误报率 > 5% 优化 hook regex / 加白名单, 继续收集 20+ commit 重测
- **不要做的事**:
  - 不改 Sprint 52 WARN hook 现有逻辑 (只升级 WARN → blocking)
  - 不强制 skip (`--no-verify` 紧急 hotfix 仍允许, Sprint 18 #142 实践)

**验证**:
- N=20 commit 跑 hook 误报率 ≤ 5% (实测统计)
- 故意 commit 1 个 msg-drift 案例 → hook 拦 commit (验证 blocking)
- 故意 commit 1 个正常案例 → hook 不拦 (验证 happy path)

---

## 跨 sprint 引用关系图 (避免 Stage 4 合并冲突)

```
CLAUDE.md (主索引, 不动)
    │
    ├─→ docs/operating/ci-e2e-history.md (#4 扩)
    │       │
    │       ├─→ docs/architecture/TEST_INFRASTRUCTURE.md (单向引用, 已存在)
    │       └─→ docs/architecture/50m-scale-architecture.md (单向引用, 已存在)
    │
    ├─→ .github/workflows/e2e.yml (#1 + #4 共改, 协调)
    │       │
    │       └─→ docs/architecture/50m-scale-architecture.md (单向引用)
    │
    ├─→ .githooks/commit-msg (#2 改)
    │       │
    │       └─→ scripts/commit_msg_check.py (新建)
    │
    └─→ scripts/ci/auto_recover_ci.sh (#4 新建)
```

**关键不变量**:
- #4 + #1 共改 `.github/workflows/e2e.yml` (Stage 4 合并 #1 前先 #4 merge, #1 在 #4 基础上改 e2e.yml, 避免冲突)
- #2 独立 (只改 `.githooks/commit-msg` + 新建 `scripts/commit_msg_check.py`)
- 引用合规: 3 项互不引用 `#10 LESSONS_LEARNED` / `#9 docs/architecture/*` (Sprint 57 改动, 不可回引)

---

## Stage 4 合并顺序 (避免 doc 引用断裂)

1. **wt-04 (#4 CI e2e 持久化)** 先合 — 提供持久化 reference + auto-recovery script
2. **wt-05 (#1 OOM 治本)** 接着合 — 在 #4 基础上改 e2e.yml (避免 e2e.yml 合并冲突)
3. **wt-06 (#2 commit-msg blocking)** 最后合 — 独立 (只改 hooks)

合并顺序关键: **持久化方先合** (#4 → #1), 0 冲突 (跟 Sprint 53 race flake 治本 + Sprint 57 三 worktree 模式一致).

---

## 验收标准

### pytest + lint 持续

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q   # 758/1 持续 (跟 Sprint 57 一致)
cd frontend-vue3 && npx vite build                  # 750ms 持续
python3 backend/scripts/check_filter_builder_usage.py  # 0 violations
npm run lint:spec                                   # L2 AST 0 violation
```

### CI runner 实测

```bash
# GitHub Actions 跑 e2e job 5 次连续 PASS (无 fail)
gh workflow run e2e.yml
gh run watch --exit-status  # 等 5 次连续成功
```

### commit-msg 误报率

```bash
# 收 #1 实施后 N=20 commit, 跑 hook 统计误报率
for i in {1..20}; do
  git commit --allow-empty -m "test $i" 2>&1 | tee /tmp/hook-output-$i.log
done
# 期望: 误报 ≤ 1/20 (5%)
```

---

## 关键风险与缓解

| 风险 | 缓解 |
|------|------|
| #1 DuckDB ATTACH 在 CI runner 不稳定 (跟 Sprint 38 ROI 重评错误教训) | Claude 主跑 Stage 2, Stage 3 架构师双验证 (Sprint 53 实战 fix 模式) |
| #2 blocking hook 误报率高 | N=20 commit sample 验证, 误报率 > 5% 优化 regex + 加白名单 (Sprint 3 P1-3 4 轮修模式) |
| #1 + #4 共改 .github/workflows/e2e.yml 合并冲突 | Stage 4 合并顺序: #4 先合 → #1 在 #4 基础上改 (worktree 派生), 0 冲突 |
| 串行 4d 时间紧 | 12 步流程不能省 review/qa, 但 #1 + #2 可并行 (Claude 主跑 Stage 2), #4 必先收口 |
| e2e 切片覆盖率不足 | 11 spec 全覆盖 + 5-10MB 数据子集 schema 一致, pytest 真连 fixture 验证 |
| auto_recovery 引入副作用 | cache cleanup + retry 1 次, 不修改测试逻辑 (Sprint 25 backup 7 天清理模式一致) |

---

## Stage 2 Codex 启动指引

### 通用约束 (所有 HANDOFF 共享)

```text
1. 你只能 Read/Write/Edit 文件 (.md / .yml / .ts / .sh / .py), 不跑 git 命令
2. 不修改 backend/ frontend/ scripts/etl/ .githooks/(只改 hooks 不动路径)/ config 文件 (除明确指定)
3. 完成后通知 Claude (在 HANDOFF 文件末尾写 "Stage 2 完成" 段)
4. 等待 Stage 3 review 后才能算 sprint 收口
5. N=20 commit 误报率验证如果 > 5%, 立即通知 Claude (不要继续实施)
```

### 3 个 HANDOFF 路径

| 项 | worktree | HANDOFF 路径 |
|-----|----------|--------------|
| #4 | wt-sprint58-04 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint58-01.md` |
| #1 | wt-sprint58-05 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint58-02.md` |
| #2 | wt-sprint58-06 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/HANDOFF-TO-CODEX-Sprint58-03.md` |

---

## 估算

- **Stage 1** (本文档 + 3 份 HANDOFF): 已完成 (Claude, 30 min)
- **Stage 2** (Codex 实施 3 worktree 串行): 4d (跟 Sprint 53 race flake 治本节奏一致)
- **Stage 3** (Claude review + 修 bug): 1h
- **Stage 4** (commit + push + merge + STATUS/CHANGELOG): 1h
- **总 Sprint 58**: 4-5 天闭环

---

## 状态

**Stage 1 完成**: ARCHITECTURE-Sprint58.md + 3 份 HANDOFF 已写, 待 Codex consult 审核 + 用户审批后启动 Codex Stage 2 实施。

---

**Sprint 58 关键里程碑**:
- 跟 Sprint 53 race flake 治本同等级, 必须 1 sprint 闭环
- 跨 sprint 5+ 复发 OOM 治本 + Sprint 41 12 follow-up 持久化, 闭环后 0 复发
- 工具链实战 fix 主题, 跨 sprint 留尾 7 → 4 项 (-43%)