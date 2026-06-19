# 项目交接文档 (HANDOFF)

> **目标读者**: 项目总指挥 (你) + Claude Code (架构师 + Reviewer + Committer) + Codex app (实施者)
> **生成时间**: 2026-06-19 (Sprint 43.1 收口 + Codex 协作工作流启动)
> **更新者**: Claude Opus 4.8 (Sprint 32-43 系列实战 + Codex 工作流设计)

---

## TL;DR — 工作流概览

| 项 | 值 |
|---|---|
| **项目** | fuqing-crm-analytics (芙清 CRM 数据分析) |
| **main HEAD** | `ae0cc62` (Sprint 50.1 收口, v0.4.14.136) |
| **VERSION** | v0.4.14.136 |
| **Git 标签** | `v0.4.14.133` (Sprint 43) / `v0.4.14.134` (Sprint 43.1) |
| **协作模式** | **Claude 总指挥 + Codex 实施 + user review gate** |
| **Codex 接入** | app 端口 (macOS), 本地编辑文件, 不连 GitHub (OAuth 审核问题) |
| **沟通语言** | 中文 (跟 user 一直) |

---

## 🎯 新工作流 (Claude 总指挥 + Codex 实施)

### 角色分工

| 角色 | 职责 | 工具 |
|---|---|---|
| **你 (总指挥)** | review + go/no-go gate | 复制 HANDOFF → Codex, 看完 push 结果确认 |
| **Claude Code (架构师 + Reviewer + Committer)** | Stage 1 架构 + Stage 3 review + Stage 4 commit + push | SSH key (~/.ssh/id_ed25519_github) |
| **Codex app (实施者)** | Stage 2 复杂代码 + debug (GPT-5.5 强项) | 本地文件编辑 (不动 git) |

### 工作流 (Codex 额度够时)

```
你: "做 Sprint XX"
   ↓
Claude (Stage 1):
   ├─ 写架构 + 代码骨架 + HANDOFF-TO-CODEX.md
   ├─ 输出: 你能直接复制粘贴给 Codex 的 plan doc
   ↓
你做动作 1: 复制 HANDOFF 给 Codex app (1 分钟)
   ↓
Codex (Stage 2):
   ├─ 读 HANDOFF + 本地代码
   ├─ 编辑本地文件 (跟 VS Code 一样 save)
   ├─ 改完提示你 "OK, 切回 Claude"
   ↓
你做动作 2: 告诉 Claude "Codex 完成"
   ↓
Claude (Stage 3+4):
   ├─ git diff 检查 (跟 HANDOFF 对齐 + 跨 sprint 实战 fix 模式)
   ├─ git commit --no-verify -m "..."
   ├─ git push --no-verify origin main
   ↓
你做动作 3: 看 push 结果确认 (30 秒)
```

### Fallback (Codex 额度不够时)

```
你: "Codex 额度不够, Claude 接手"
   ↓
Claude: 直接 Stage 2 写代码 + Stage 3 review + Stage 4 push
```

### 12 步流程不变的部分 (Claude 做)

```
1. 读 plan + memory
2. 改代码 + 测试  ← Codex (主) / Claude (fallback)
3. 跑 pytest
4. 跑 spec-lint
5. 跑 regression test
6. 跑 e2e (uvicorn + Vite + playwright)
7. VERSION bump (如需要)
8. CHANGELOG
9. TECH-DEBT
10. git commit --no-verify
11. git push --no-verify
12. 写 sprint memory + 更新 MEMORY.md
```

---

## 📋 Claude 第一件事: 读这些文件 (Stage 1 上下文)

按重要性顺序:

1. **`/Users/hutou/.claude/projects/-Users-hutou/memory/MEMORY.md`** (全局工作记忆索引)
   - 用户画像 + 项目 sprint close memory 索引 (Sprint 24-50+ 全部)
   - 30 秒理解整个项目历史

2. **`CLAUDE.md`** (项目根目录, Claude Code **自动加载**)
   - L4.3 (race flake skipif) / L4.4 (production DuckDB skipif) 永久规则
   - L5.1 (CI 留尾 ROI 重评) / L5.2 (spec 写法"环境无关") 永久规则
   - 顶部状态行 + 快速启动命令 (uvicorn + Vite + ETL)

   > ⚠️ **Codex 不会自动读 CLAUDE.md**。Codex 自动注入的是 `AGENTS.md`（本地文件，.gitignore 排除）。
   > CLAUDE.md 和 AGENTS.md 内容相同（AGENTS.md 的自引用已修正为 Codex 版本）。
   > 修改规则时**两个文件都要改**，或改一个后同步到另一个。

3. **`docs/CI-DEFENSE-PLAYBOOK.md`** (Sprint 42 实战 fix 框架)
   - 3 层防御 + Q1-Q4 决策树 + 5 步响应流程
   - 实战 fix 模式 ROI 重评核心

4. **`docs/SPRINT-41-CI-LESSONS-LEARNED.md`** (Sprint 41 12 follow-up 教训)
   - GH Actions runner 跟本地差异 (14GB disk + headless + 没 DuckDB)
   - Playwright 3 个 timeout 区别
   - 引用不复述 (跟 PLAYBOOK 双 source)

5. **`HANDOFF-TO-CODEX.md`** (新写, Stage 1 输出给 Codex 的 plan doc 模板)
   - Claude 用这个模板生成 HANDOFF 给 Codex
   - GPT-5.5 强项能理解复杂架构

6. **`/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md`**
   - 最近 sprint 收口 + Codex 工作流启动记录

7. **`/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint41_close.md`**
   - Sprint 41 实战 12 follow-up 时间线

---

## 🎓 Claude 必读: 跨 sprint 实战 fix 模式 ROI 重评

这是项目的核心决策框架,**生成 HANDOFF 之前必须理解**:

```
Q1: 本地能跑通吗?
  能 → C 类 (环境差异)
  不能 → A/B 类 (修代码/spec)

Q2: 根因是 spec/代码 还是环境?
  spec/代码 → 修
  环境 → Q3 评估

Q3: 治本 1-2 天能闭环吗?
  能 + 治本后 0 复发 → 治本
  不能 (基础设施限制) → 治标

Q4: 治标会反复出现吗?
  会 → 写 lessons learned + trigger 评估
  不会 → 治标闭环
```

**共同模式**(跨 sprint 实战):

| Sprint | 现象 | N follow-up | 决策 |
|---|---|---|---|
| Sprint 38 | pytest race flake | 5 (32.3/34.1/36-1/37/38) | 治标 + 永久规则 |
| Sprint 41 | GH Actions e2e CI | 12 (41.1-41.12) | advisory + 永久规则 |
| Sprint 42 | spec-lint 起步 | — | 预防层 (playbook + lint) |
| Sprint 43 | spec-lint 改 blocking | 1 (43.1 fix 1h) | 治本 + 永久规则 |

**N > 5 还没闭环 → 改治标/advisory 0→1 是务实选择**(不是失败,是务实)。

---

## 🛠️ Codex 第一件事: 读 HANDOFF-TO-CODEX.md (Stage 2 输入)

**不要**让 Codex 读全部 5 个文件 — Codex 只做 Stage 2 实施,**只读**:
1. **HANDOFF-TO-CODEX.md**(当前 sprint 的 plan doc, Claude Stage 1 生成)
2. **CLAUDE.md L5.1 + L5.2**(spec 写法原则 + CI 留尾 ROI 重评)
3. 涉及的具体文件 (HANDOFF 里指明)

GPT-5.5 强项 = 复杂代码 + debug。给它严谨的 plan doc + 实施步骤, 它能直接产出。

---

## 🛠️ 开发环境命令 (Claude 验证用)

### 启 backend (port 8000)

```bash
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
export FQ_CRM_PASSWORDS="admin:123456"
export ETL_MIN_DISK_GB=0  # 跳过 50GB disk check (本地不跑 ETL)
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 >> /tmp/uvicorn.log 2>&1 &
```

### 启 frontend (port 5173)

```bash
nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort > /tmp/vite-preview.log 2>&1 &
```

### 跑 e2e (期望 11/11 spec pass)

```bash
npx playwright test
```

### 跑 pytest (排除 race flake)

```bash
PYTHONPATH=. pytest backend/tests/ -q \
  --ignore=backend/tests/test_api_integration.py \
  --ignore=backend/tests/test_churn_user_list_fstring.py \
  --ignore=backend/tests/test_w4_t7_integration.py \
  --ignore=backend/tests/test_w4_full.py \
  --ignore=backend/tests/test_wo_cleanup_orphans.py
```

---

## 📁 repo 关键路径

```
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/
├── HANDOFF.md                  # 本文件 (工作流文档)
├── HANDOFF-TO-CODEX.md        # Stage 1 → Codex 的 plan doc 模板
├── CLAUDE.md                   # 项目永久规则 (L4.3/L4.4/L5.1/L5.2)
├── README.md                   # 项目说明 + sprint 收口历史
├── CHANGELOG.md                # sprint 24+ P3 起的详细 entry
├── CHANGELOG_HISTORY.md        # sprint 24 之前的历史 entry
├── VERSION                     # 当前 v0.4.14.134
├── .pre-commit-config.yaml     # ruff + contract-ground-truth-lint + spec-lint (blocking)
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── routers/                # 路由模块 (auth, audience, sampling, category 等)
│   ├── services/               # 业务逻辑
│   ├── contracts/              # Pydantic contracts + _lint.py
│   └── tests/                  # pytest (含 race flake test 加 skipif)
├── frontend-vue3/
│   ├── src/                    # Vue 3 + TypeScript 业务代码
│   ├── e2e/
│   │   ├── *.spec.ts           # 11 spec (Playwright)
│   │   └── lint/
│   │       ├── spec-lint.sh    # 3 条规则防 Sprint 41 实战 fix 复发
│   │       └── __tests__/
│   │           └── spec-lint.test.sh
│   └── playwright.config.ts    # baseURL 5173, timeout 本地 10s/CI 60s, serial mode
├── docs/
│   ├── CI-DEFENSE-PLAYBOOK.md           # Sprint 42 3 层防御 (Q1-Q4 决策树)
│   ├── SPRINT-41-CI-LESSONS-LEARNED.md  # Sprint 41 12 follow-up 时间线
│   ├── SPRINT-40-PLUS-PLAN.md           # Sprint 40 audit + Sprint 41 实战总结
│   ├── VISITOR-CHAIN-AUDIT-SPRINT39.md # Sprint 39 visitor 链 audit
│   ├── TECH-DEBT.md                     # 全部技术债台账 (Sprint 25+ 起)
│   └── PRE-COMMIT.md / LINTING.md / SHIP.md / HOOKS-CHOICE.md / CI-PRECOMMIT.md
└── .github/workflows/lint.yml           # GH Actions 4 jobs (lint + ground-truth-lint + pytest + e2e advisory)

~/.claude/projects/-Users-hutou/memory/
├── MEMORY.md                    # 全局索引
└── project_fuqing_crm_analytics_sprint{24,25,26,27,28,30,32.1,32.2,32.3,33,34.1,37,38,39,40+41,41,42,43}_close.md
```

---

## 🎯 Sprint 44+ 留尾 (从 Sprint 43 留尾)

按推荐优先级:

### ⭐ 近期(1-2 sprint 内做)

| # | 任务 | 来源 | 工作量 | 适合 Codex? |
|---|---|---|---|---|
| 1 | Sprint 44: visitor / export / report 3 选项激活路径 | Sprint 39.2 audit (产品决策) | 1 天 | 部分 (决策需要 user 拍板) |
| 2 | Sprint 50+: pre-flight check shell script | Sprint 42 留尾, 跟 spec-lint 配合 | 半天 | ✅ (bash + 4 项 check, GPT-5.5 强项) |

### 📅 中期(3-5 sprint 内)

| # | 任务 | 来源 | 工作量 | 适合 Codex? |
|---|---|---|---|---|
| 3 | Sprint 50+: race flake 真治本 | Sprint 38 (ROI 重评为低) | 2+ 天 | 部分 (架构调研) |
| 4 | Sprint 50+: L2 AST parser + ground-truth-lint 扩 | Sprint 34.2 + 36-4 | 半天 + 1h | ✅ (复杂 AST 实现) |
| 5 | Sprint 50+: commit msg ↔ diff check | Sprint 35 (ROI 负) | 1 天 | ⚠️ (ROI 负, 跳过) |

### 🕰 长期(数据触发)

| # | 任务 | 来源 | 工作量 |
|---|---|---|---|
| 6 | 30M 50m-scale | Sprint 25 (目前 10.75M) | 2 人日 |
| 7 | Sprint 50+: e2e CI 重新评估 | Sprint 41.12 advisory 触发 | 1 天 |

---

## ✅ 接力完成 Checklist

新接手一次 sprint 时:

- [ ] 跟 Claude 说 "做 Sprint XX" (给方向)
- [ ] Claude 输出 HANDOFF-TO-CODEX.md (Stage 1 产物)
- [ ] 复制给 Codex app (动作 1, 1 分钟)
- [ ] Codex 改完提示你 (动作 2, 等待)
- [ ] Claude review + commit + push (Stage 3+4 自动)
- [ ] 看 push 结果确认 (动作 3, 30 秒)
- [ ] 写 sprint close memory + 更新 MEMORY.md (Step 12)

---

## 联系 / 反馈

- 项目 owner: hutou
- 沟通语言: 中文
- 风格偏好: 简洁优先 + 精准修改 + 目标驱动执行
- 不确定时: 先问 user, 不要默默假设

---

**HANDOFF.md 完。**
**当前 sprint 状态: Sprint 43.1 收口完成 (v0.4.14.134), main HEAD aa18969, 11/11 e2e pass。**
**新工作流就绪: Claude 总指挥 + Codex 实施。**
