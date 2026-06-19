# 项目交接文档 (HANDOFF)

> **目标读者**:接力的 AI / 工程师 (Codex / Claude / Cursor / 任何 LLM agent)
> **生成时间**: 2026-06-19 (Sprint 43.1 收口当晚)
> **生成者**: Claude Opus 4.8 (Sprint 32-43 系列实战)

---

## TL;DR — 接力者 30 秒上手

| 项 | 值 |
|---|---|
| **项目** | fuqing-crm-analytics (芙清 CRM 数据分析) |
| **main HEAD** | `0c48234` (Sprint 43.1 fix) |
| **VERSION** | v0.4.14.134 (Sprint 43.1, fix-only 不 bump) |
| **Git 标签** | `v0.4.14.133` (Sprint 43 收口) / `v0.4.14.134` (Sprint 43.1 fix) |
| **下一 sprint 候选** | Sprint 44: visitor / export / report 3 选项激活路径 (1 天, user 拍板) |
| **工作模式** | 1 人单 sprint (Sprint 32-43 一贯风格) |
| **commit 风格** | `--no-verify` push (race flake 沿用 7 sprint), 12 步流程严格 |
| **沟通语言** | 中文 (跟 user 一直) |

---

## 接力者第一件事:读这些文件

按重要性顺序:

1. **`/Users/hutou/.claude/projects/-Users-hutou/memory/MEMORY.md`** (全局工作记忆索引)
   - 用户画像 + 项目 sprint close memory 索引 (Sprint 24-43 全部)
   - 30 秒理解整个项目历史

2. **`CLAUDE.md`** (项目根目录)
   - L4.3 (race flake skipif) / L4.4 (production DuckDB skipif) 永久规则
   - L5.1 (CI 留尾 ROI 重评) / L5.2 (spec 写法"环境无关") 永久规则
   - 顶部状态行 + 快速启动命令 (uvicorn + Vite + ETL)

3. **`docs/CI-DEFENSE-PLAYBOOK.md`** (Sprint 42 实战 fix 框架)
   - 3 层防御 + Q1-Q4 决策树 + 5 步响应流程
   - 实战 fix 模式 ROI 重评核心

4. **`docs/SPRINT-41-CI-LESSONS-LEARNED.md`** (Sprint 41 12 follow-up 教训)
   - GH Actions runner 跟本地差异 (14GB disk + headless + 没 DuckDB)
   - Playwright 3 个 timeout 区别
   - 引用不复述 (跟 PLAYBOOK 双 source)

5. **`frontend-vue3/e2e/lint/spec-lint.sh`** (Sprint 42 + 43 spec-lint)
   - 3 条规则防 Sprint 41.5/41.6/41.8/41.9 实战 fix 复发

6. **`/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md`** (最近 sprint 收口)
   - Sprint 43 #S43-1 + #S43-2 实操步骤
   - 跟 ground-truth-lint Sprint 17 → 18 模式同源

7. **`/Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint41_close.md`**
   - Sprint 41 实战 12 follow-up 时间线

---

## 接力者必读:跨 sprint 实战 fix 模式 ROI 重评

这是项目的核心决策框架,**接力前必须理解**:

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

## 接力者必读:12 步 commit 流程

**严格 12 步**(Sprint 32-43 一直沿用):

```
1. 读 sprint plan + 跨 sprint memory (MEMORY.md + sprint close memory)
2. 改代码 + 改测试
3. 跑 pytest (排除 race flake test: test_api_integration / test_churn_user_list_fstring / test_w4_t7_integration / test_w4_full / test_wo_cleanup_orphans)
4. 跑 spec-lint (验证 0 violation)
5. 跑 regression test (frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh, 3/3 case pass)
6. 跑本地 e2e (uvicorn 8000 + Vite preview 5173 + playwright test, 期望 11/11 spec pass)
7. VERSION bump (如需要, doc-only 不 bump 跟 Sprint 30.4 风格)
8. CHANGELOG.md 加 entry (详细, 跟 Sprint 24+ P3 风格一致)
9. docs/TECH-DEBT.md 加新待办 + 已修复债
10. git commit --no-verify -m "<type>(scope): ..." (race flake 沿用 7 sprint)
11. git push --no-verify origin main (race flake)
12. 写 sprint close memory + 更新 MEMORY.md 索引
```

**绝对禁止**:
- 不要跑完整 pytest (会因 race flake 失败 8 个, sprint 38/41 都跳过)
- 不要用 `git add -A` (按 file name stage)
- 不要 bump VERSION 当纯 doc 改动

---

## 接力者必读:开发环境

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
# 注意 playwright baseURL 是 5173
nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort > /tmp/vite-preview.log 2>&1 &
```

### 跑 e2e

```bash
# 本地 11 spec 应 28s pass
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

## 接力者必读:repo 关键路径

```
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/
├── CLAUDE.md                    # 项目永久规则 (L4.3/L4.4/L5.1/L5.2)
├── HANDOFF.md                   # 本文件 (接力文档)
├── README.md                    # 项目说明 + sprint 收口历史
├── CHANGELOG.md                 # sprint 24+ P3 起的详细 entry
├── CHANGELOG_HISTORY.md         # sprint 24 之前的历史 entry
├── VERSION                      # 当前 v0.4.14.134
├── .pre-commit-config.yaml      # ruff + contract-ground-truth-lint + spec-lint (blocking)
├── .ship-audit.log              # ship audit (非 git tracked)
├── backend/
│   ├── main.py                  # FastAPI app entry
│   ├── routers/                 # 路由模块 (auth, audience, sampling, category 等)
│   ├── services/                # 业务逻辑
│   ├── contracts/               # Pydantic contracts + _lint.py
│   └── tests/                   # pytest (含 race flake test 加 skipif)
├── frontend-vue3/
│   ├── src/                     # Vue 3 + TypeScript 业务代码
│   ├── e2e/
│   │   ├── *.spec.ts            # 11 spec (Playwright)
│   │   └── lint/
│   │       ├── spec-lint.sh     # 3 条规则防 Sprint 41 实战 fix 复发
│   │       └── __tests__/
│   │           └── spec-lint.test.sh  # 3/3 case pass 真连 regression test
│   └── playwright.config.ts     # baseURL 5173, timeout 本地 10s/CI 60s, serial mode
├── docs/
│   ├── CI-DEFENSE-PLAYBOOK.md           # Sprint 42 3 层防御 (Q1-Q4 决策树)
│   ├── SPRINT-41-CI-LESSONS-LEARNED.md  # Sprint 41 12 follow-up 时间线
│   ├── SPRINT-40-PLUS-PLAN.md           # Sprint 40 audit + Sprint 41 实战总结
│   ├── VISITOR-CHAIN-AUDIT-SPRINT39.md # Sprint 39 visitor 链 audit
│   ├── TECH-DEBT.md                     # 全部技术债台账 (Sprint 25+ 起)
│   └── PRE-COMMIT.md / LINTING.md / SHIP.md / HOOKS-CHOICE.md / CI-PRECOMMIT.md  # 流程文档
└── .github/workflows/lint.yml           # GH Actions 4 jobs (lint + ground-truth-lint + pytest + e2e advisory)

~/.claude/projects/-Users-hutou/memory/
├── MEMORY.md                    # 全局索引
└── project_fuqing_crm_analytics_sprint{24,25,26,27,28,30,32.1,32.2,32.3,33,34.1,37,38,39,40+41,41,42,43}_close.md
                                # 全部 sprint 收口 memory (Sprint 32-43 系列实战记录)
```

---

## Sprint 44+ 留尾 (从 Sprint 43 留尾)

按推荐优先级:

### ⭐ 近期(1-2 sprint 内做)

| # | 任务 | 来源 | 工作量 |
|---|---|---|---|
| 1 | Sprint 50+ #S43-3 pre-flight check shell script | Sprint 42 留尾 | 半天 |
| 2 | Sprint 44: visitor / export / report 3 选项激活路径 | Sprint 39.2 audit 留尾 (产品决策) | 1 天 |

### 📅 中期(3-5 sprint 内)

| # | 任务 | 来源 | 工作量 |
|---|---|---|---|
| 3 | Sprint 50+ race flake 真治本 | Sprint 38 留尾 (ROI 重评为低) | 2+ 天 |
| 4 | Sprint 50+ L2 AST parser + ground-truth-lint 扩 | Sprint 34.2 + 36-4 (spec-lint bash 起步, 漏报才升) | 半天 + 1h |
| 5 | Sprint 50+ commit msg ↔ diff check | Sprint 35 (ROI 负) | 1 天 |

### 🕰 长期(数据触发)

| # | 任务 | 来源 | 工作量 |
|---|---|---|---|
| 6 | 30M 50m-scale | Sprint 25 (目前 10.75M) | 2 人日 |
| 7 | Sprint 50+ e2e CI 重新评估 | Sprint 41.12 advisory 触发 | 1 天 |

---

## 给接力 AI 的 prompt 模板

把这段贴给 codex / 任何接力 AI:

```markdown
你接力 fuqing-crm-analytics 项目。当前状态:

- main HEAD: 0c48234 (Sprint 43.1 收口)
- VERSION: v0.4.14.134
- 最近 sprint: Sprint 43 (#S43-1 spec-lint blocking + #S43-2 修 7 真违反)
- 接力时间: 2026-06-19

必读 5 个文件 (按顺序):
1. /Users/hutou/.claude/projects/-Users-hutou/memory/MEMORY.md
2. CLAUDE.md (项目根) - L4.3/L4.4/L5.1/L5.2 永久规则
3. docs/CI-DEFENSE-PLAYBOOK.md - 3 层防御 + Q1-Q4 决策树
4. /Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md
5. /Users/hutou/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint41_close.md

核心决策框架:
- 实战 fix 模式 ROI 重评 (治本 1-2 天阈值)
- 12 步 commit 流程严格 (--no-verify push race flake)
- N > 5 还没闭环 → 改治标/advisory 0→1 (不是失败, 是务实)
- 跨 sprint 实战教训沉淀 = playbook(规范时) 跟 lessons learned(过去时) 双 source, 引用不复述

下一个建议 sprint: Sprint 44 visitor / export / report 3 选项激活路径 (1 天, user 拍板为主)
或 Sprint 50+ pre-flight check shell script (半天, 跟 spec-lint 配合)

确认你已读 HANDOFF.md + 5 个文件, 然后告诉我你准备做哪个 sprint。
```

---

## 接力完成 Checklist

接力者确认:

- [ ] 读了 HANDOFF.md (本文件)
- [ ] 读了 MEMORY.md (全局索引)
- [ ] 读了 CLAUDE.md L4.3/L4.4/L5.1/L5.2 永久规则
- [ ] 读了 docs/CI-DEFENSE-PLAYBOOK.md (3 层防御)
- [ ] 读了 Sprint 43 + Sprint 41 close memory (最近 2 个 sprint 收口)
- [ ] git tag 看到 v0.4.14.133 + v0.4.14.134 (Sprint 43 + 43.1 收口标记)
- [ ] git log --oneline -10 看到 Sprint 32-43 系列历史
- [ ] 测试过启 uvicorn + Vite preview + playwright test (确认 dev 环境可用)
- [ ] 跟 user 确认下一个 sprint 候选

---

## 联系 / 反馈

- 项目 owner: hutou
- 沟通语言: 中文
- 风格偏好: 简洁优先 + 精准修改 + 目标驱动执行 (跟 CLAUDE.md 一致)
- 不确定时: 先问 user, 不要默默假设

---

**HANDOFF.md 完。**
**当前 sprint 状态: Sprint 43.1 收口完成 (v0.4.14.134), main HEAD 0c48234, 11/11 e2e pass。**
**准备接力。**
