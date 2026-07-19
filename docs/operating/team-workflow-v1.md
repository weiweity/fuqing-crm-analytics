# 团队协作工作流 v1（Team Workflow）

> **最后更新**: 2026-07-19  
> 在「本地即生产 + AI 协作者」约束下，把 12 步仪式压成**可多人执行**的默认流程。  
> 与 `docs/operating/ship.md`、`CLAUDE.md` 并存：**冲突时以本文件「可合并定义」+ 硬 STOP 为准**。

---

## 1. 可合并定义（Definition of Done for merge）

| Check | 是否挡 merge |
|---|---|
| **lint**（ruff） | ✅ 必须绿 |
| **ground-truth-lint** | ✅ 必须绿（或明确 advisory） |
| **test**（pytest + deselect SSOT） | ✅ 必须绿 |
| **e2e** | ⚠️ **默认不挡 merge**（2026-07 起：e2e 预存红；修稳前放 nightly / 独立 track） |
| 改 contract | 必须三同步 + contracts lint |
| 生产 DuckDB / `.env` | 禁止进 PR |

CI required checks 应与上表一致；**禁止**「文档写必须 4/4、实际红着合」双重标准。

---

## 2. 默认开发流程（7 步）

```
① git checkout main && git pull --ff-only
② git checkout -b fix|feature/<topic>-YYYY-MM-DD
③ 实现（小 PR，单主题）
④ 本地：ruff + 相关 pytest（pre-commit / pre-push smart path 已分层）
⑤ git push → 开 PR（填模板）
⑥ CI lint+test 绿 → squash merge（user/指定 owner 拍板）
⑦ 生产机：git pull --ff-only；仅当 backend 行为变才重启 uvicorn
```

### 与旧 12 步关系

| 旧步骤 | v1 |
|---|---|
| `/review` skill | PR 自检清单（见下）；大改可选 skill |
| `/qa` skill | CI + 可选人工点检 |
| merge --no-ff | 默认 **squash**（历史更干净）；重大架构可用 merge commit |
| 每次 CHANGELOG | 用户可见变更才写；hooks 软 WARN 可接受 |
| 每次重启 uvicorn | 仅服务行为变化时 |

**硬 STOP 仍有效**（见 CLAUDE.md）：main 禁止直接业务 commit；push/merge 人拍板；不碰生产 duckdb。

---

## 3. PR 自检清单（替代每次强制 /review）

- [ ] 分支不基于过期 main（已 rebase/merge 最新）
- [ ] 无 `data/`、`outputs/`、`.env`、大 xlsx
- [ ] SQL 走 FilterBuilder / `?` 参数化（L4.5）
- [ ] channel 条件有 `o.` 别名（L4.19）
- [ ] 新增 deselect 只改 `scripts/ci/pytest_c_class_deselects.txt`
- [ ] 相关单测或说明为何只靠 CI
- [ ] Schema 三同步（若动 contract）

---

## 4. 角色与并行（2～4 人）

| 角色 | 可并行 | 约束 |
|---|---|---|
| 前端 | 高 | 少动 contract；预发/ mock |
| 后端业务 feature | 中 | 不锁生产 DuckDB 写；低峰测真连 |
| 平台（CI/hooks/docs） | 高 | 独立 PR |
| 生产发布 owner | **单人** | 仅此人 pull + 重启生产机 |

```
PM/Owner ── 拍板 merge / 发布窗口
    ├── Dev A 前端 PR
    ├── Dev B 后端 PR（预发验证）
    └── Dev C 基建/文档 PR
```

**不要**多人共享同一生产 uvicorn 做开发调试。

---

## 5. 闸门分层（与 #31 / #32 对齐）

| 时机 | 跑什么 |
|---|---|
| pre-commit | hooksPath + CHANGELOG 提示 + 有代码时重检查；docs-only light |
| pre-push | skip / ruff / scoped tests / full（见 `.githooks/pre-push`） |
| CI | lint + test 全量（+ deselect SSOT）；e2e 非默认阻断 |
| 生产 | pull；按需重启 |

Escape（人拥有）：`FQ_PRE_PUSH_SKIP=1` — 须说明原因，禁止常态化。

---

## 6. 后续 backlog

| 项 | 状态 (2026-07-19 backlog workflow) |
|---|---|
| STATUS 顶部短表 | ✅ hygiene #33 已加快照；全文截断仍 P2 |
| e2e 不挡 merge | ✅ lint.yml e2e `continue-on-error: true` |
| TECH-DEBT 短表 | ✅ 开放债表 + `docs/history/TECH-DEBT-HISTORY.md` |
| pre-push .gitignore 等 skip | ✅ path classifier `_SKIP_EXACT` |
| GitHub branch protection required checks | ⚠️ 仓库 **未开** branch protection（`gh api .../protection` → 404，2026-07-19 实证）。有 org 权限时可在 Settings → Branches 设 required: **lint** + **test** only；本 PR 用 e2e `continue-on-error` 等价「e2e 不挡整次 CI」 |
| 预发环境 | 📋 未做 |
| CLAUDE L4 表下沉 | 📋 未做 |
| e2e 修稳 | 📋 未做（登记 #e2e-preexisting） |

---

## 7. 相关链接

- 整洁度：`docs/operating/project-hygiene.md`
- Ship 细节：`docs/operating/ship.md`
- Deselect SSOT：`scripts/ci/pytest_c_class_deselects.txt`
- Hooks：`.githooks/pre-push`、`.githooks/pre-commit`
