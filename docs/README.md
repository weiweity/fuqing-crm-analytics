# Docs 索引

> 文档按 lifecycle 分层, 新人 5 分钟找到入口。Sprint 54 起 (L3 FilterBuilder 100% 闭环) 架构师推荐分层。

## 一图流

```
fuqing-crm-analytics/docs/
├── README.md                          ← 你在这里
│
├── architecture/                      [系统设计 - 为什么]
│   ├── AI_SAFETY_NET.md              (L1 lint + L2 AST + L3 FilterBuilder 3 层防线)
│   ├── DATA_PIPELINE.md              (ETL 4 阶段: W1-W4)
│   ├── TEST_INFRASTRUCTURE.md        (Sprint 53 race flake fixture 模式 + L4.3/L4.4/L4.6)
│   └── 50m-scale-architecture.md     (Sprint 52 P2 留尾, 30M 数据触发)
│
├── data/                              [数据目录布局]
│   └── data-layout.md                (data/cache exports parquet processed raw 5 区用途+读写+清理)
│
├── operating/                         [操作手册 - 怎么用]
│   ├── ship.md                       (原 SHIP.md, 12 步流程)
│   ├── linting.md                    (原 LINTING.md, ground-truth-lint 规则)
│   ├── pre-commit.md                 (原 PRE-COMMIT.md, hook 框架)
│   ├── automation.md                 (原 AUTOMATION.md, Claude Code 自动化)
│   ├── ci-defense-playbook.md        (原 CI-DEFENSE-PLAYBOOK.md, L5.1 ROI 重评)
│   ├── ci-precommit.md               (原 CI-PRECOMMIT.md, GitHub Actions 配置)
│   ├── ci-e2e-history.md             (原 CI-E2E-HISTORY.md, Sprint 41 实战 follow-up 12)
│   ├── hooks-choice.md               (原 HOOKS-CHOICE.md, .githooks vs .pre-commit-config)
│   └── (frontend-types-gen.md / yoy-guard-config.md 已于 Sprint 61 清理, 改用 .claude/skills/regen-types/ + pre-commit hook)
│
├── development/                       [开发指南 - 怎么改]
│   ├── testing.md                    (test 怎么写, mock data, race flake 模式)
│   ├── services.md                   (新增 service 的 pattern, FilterBuilder 强制)
│   └── ratio-convention.md           (B1+B2 ratio/pct/ppt/rate 命名规范)
│
└── history/                           [历史归档]
    └── SPRINT_INDEX.md               (Sprint 1-55 索引, 27+ memory file 入口)
```

## 何时用哪个

| 你想... | 看 |
|--------|-----|
| 了解项目全貌 | `README.md` (项目根) |
| 跑 sprint 收口 | `operating/ship.md` |
| 加新 service | `development/services.md` + `architecture/AI_SAFETY_NET.md` |
| 写新 test | `development/testing.md` |
| 改 contract ratio 字段 | `development/ratio-convention.md` |
| 排查 CI 失败 | `operating/ci-defense-playbook.md` + `operating/ci-e2e-history.md` |
| 看历史 sprint | `history/SPRINT_INDEX.md` (高密度索引) |
| 状态总览 (版本/测试/debt) | `STATUS.md` (项目根, 单一 source of truth) |
| data/ 目录布局 | `data/data-layout.md` (cache/exports/parquet/processed/raw) |

## 跨 sprint 维护规则

**每个 Sprint 收口必做**:
1. `CHANGELOG.md` 加 entry (近 30 entry 滚动)
2. `TECH-DEBT.md` 更新 (新债 / 已修数)
3. `STATUS.md` 更新 (版本 + pytest + debt + e2e 状态行)
4. `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint{N}.md` 写收口记忆
5. `HANDOFF-*.md` 用完即删 (一次性)

**跨 sprint 留尾意识** (L4.5 + L5.1 应用):
- 改 docs 之前先 `git log --oneline -- <doc_path>` 看历史
- 任何"未集成"/"不存在"结论必须有 `git log` 实证
- 大改前 `git stash` → 新分支 → 完整 12 步流程

## 推荐下一步 (Sprint 56+ 评估)

1. ~~**重构 docs/ 到 operating/ development/ architecture/ history/ 子目录**~~ ✅ Sprint 55 闭环
2. ~~**新增 STATUS.md**~~ ✅ Sprint 56 闭环 (本 sprint 4 doc 任务闭环, 见项目根 `STATUS.md`)
3. **新增 history/SPRINT_INDEX.md** (索引 27+ memory file) — 减少冷启动 token

按用户节奏, **本 Sprint 不强推** (跨 sprint recurring 风险, 跟 Sprint 41 实战 fix 模式一致)。
