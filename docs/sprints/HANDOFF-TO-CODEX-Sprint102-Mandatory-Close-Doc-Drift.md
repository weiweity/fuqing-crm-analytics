# HANDOFF — Sprint 102 必修 2 项文档漂移修复 + L4.x 永久规则 21 stable 维护

> **角色**: Codex Stage 2 实施 (Sprint 102 文档漂移修复 sprint 专家, 跨 sprint 留尾治理 sprint 模式沉淀专家)
> **来源**: Claude Stage 1 架构 (Sprint 101 收口后 /document-release 扫描盘点 + user "A" 拍板)
> **范围**: 留尾治理 sprint 模式 (跟 Sprint 91+99+100+101 一致, 1 sprint 多范围, 0 业务代码)
> **分支**: `fix/sprint102-mandatory-close-doc-drift` (已创建, 基于 main HEAD `c851915`)
> **目标**: Sprint 101 收口后 2 项文档漂移修复 + 跨文档一致性 100% PASS + L4.x 永久规则 21 stable 维护

---

## 0. 背景 (Context)

### Sprint 101 收口后 /document-release 扫描盘点 (ASCII 流程图)

```
Sprint 101 收口后 (main HEAD c851915) 文档扫描
├─ ⚠️ Sprint 98 Handoff untracked 漂移 (475 行 / 20KB, ?? 状态)
│  └─ Sprint 98 收口 (commit 3cd2d87) 漏 commit Handoff
│     Sprint 99+101 收口时 Handoff 都 commit 时一并加入 (模式一致)
│     Sprint 98 Handoff 是唯一未 commit 的 Handoff
├─ ⚠️ SPRINT_INDEX.md 跨文档漂移 (65 行只到 Sprint 66)
│  └─ 缺 Sprint 67+68+91+99+100+101 共 6 sprint
│     跟 MEMORY.md 索引不一致 (MEMORY.md 有 29 个 sprint close memory entry)
└─ ✅ MEMORY.md 23835 bytes L4.13 PASS (留 741 bytes headroom)
   29 个 sprint close memory entry, Sprint 60 之前 21 sprint 合并成指针
```

### Sprint 89-101 留尾治理 sprint 模式库 (ASCII 流程图)

```
Sprint 89 暂收口原则 (0 主动开 sprint, 等真业务)
  ↓
Sprint 90 L4.7 ground-truth-lint + amend 1 commit drift (3 case regression test)
  ↓
Sprint 91 必修 5 反思治根 (D3+D4 标闭环) + 留尾 #11 真修
  ↓
Sprint 92+92.1+92.2 L4.9 实战 fix 模式新增 (lint.yml YAML 错真因真修)
  ↓
Sprint 93 必修 1 真业务 sprint (增量ETL跑不动真因修)
  ↓
Sprint 94 /document-release 跨 sprint 跨文档一致性 SOP
  ↓
Sprint 95+96+96.1+96.2+96.3+96.4+96.5 7 sprint 完整链路 D2 e2e 50+MB OOM 治本真因真发现实战 fix 模式
  ↓
Sprint 97 FilterBuilder 治标推广 + L4.19 channel alias 永久规则
  ↓
Sprint 98 FilterBuilder 真治本 (改 OrderFilters API + 删 14 处 .replace() 重复代码) ← 收口时漏 commit Handoff
  ↓
Sprint 99 L4.20 反 SSOT 漂移永久规则 + check_ssot_drift.py (commit Handoff 时一并加入 ✅)
  ↓
Sprint 100 L4.20 test 1 CI fresh checkout 必修 1 fail 治根 (1 commit amend + 模拟 CI shallow clone)
  ↓
Sprint 101 L4.21 反 sprint 自我反馈闭环永久规则 + Codex 主动扩展 5 项 (commit Handoff 时一并加入 ✅)
  ↓
Sprint 102 (留尾治理 sprint 模式, 0 业务代码, 必修 2 项文档漂移修复)
```

### Sprint 60+ 留尾列表 5 项 闭环状态盘点

```
Sprint 60+ 留尾列表 (5 项, 4 闭环 + 1 推后)
├─ ✅ FilterBuilder 治本 (Sprint 60.1 + 97 + 98)
├─ ✅ L4.7 ground-truth-lint (Sprint 90)
├─ ✅ L4.8 RFM_DEFINITIONS (Sprint 60+)
├─ ✅ 留尾 #11 (Sprint 91 + 99 + 100)
└─ 📋 D1 50m-scale benchmark (待 30M 数据量触发)
```

### L4.x 永久规则生态 (21 条 stable, 跟 Sprint 101 L4.21 配套)

```
L4.1-L4.20  (Sprint 34.1 → Sprint 99 累计 20 条)
L4.21       (Sprint 101 反 sprint 自我反馈闭环永久规则, 0 新增 sprint 102 任务)
```

### Sprint 102 = Sprint 101 收口后跨文档漂移修复 (0 业务代码)

Sprint 102 必修 2 项都是修 Sprint 101 收口后跨文档漂移, 0 业务代码改动 (留尾治理 sprint 模式, 跟 Sprint 91+99+100+101 一致). Sprint 102 不会新增 L4.x 永久规则 (L4.1-L4.21 21 条 stable, Sprint 102 维护不新增).

---

## 1. 任务清单 (Must Do)

### T1 — 必修 1: commit Sprint 98 Handoff (修 Sprint 101 收口后漂移, 5min)

Sprint 98 Handoff 是 Sprint 98 收口 (commit `3cd2d87`) 时漏 commit 的 Handoff 文档. Sprint 99 (commit `4b71609`) + Sprint 101 (commit `edb2933`) 收口时 Handoff 都 commit 时一并加入. Sprint 102 必修 1 = 修 Sprint 101 收口后这个未 commit 的漂移.

```bash
# 1. Stage Sprint 98 Handoff 文件 (跟 Sprint 99+101 Handoff 模式 一致)
git add docs/sprints/HANDOFF-TO-CODEX-Sprint98-FilterBuilder-True-Root-Fix.md

# 2. Commit (1 commit 0 debt, 跟 Sprint 100 amend drift L4.14 一致)
git commit -m "chore(sprint): Sprint 98 Handoff commit (修 Sprint 101 收口后漂移, 跟 Sprint 99+101 Handoff Stage 4 commit 时一并加入 模式一致)"

# 3. 验证 commit 成功
git log --oneline -3
```

**T1 验收**: Sprint 98 Handoff 文件 commit 成功, 跟 Sprint 99+101 Handoff 模式一致. `git status` 不再有 `??` untracked.

### T2 — 必修 2: 更新 SPRINT_INDEX.md (修跨文档漂移, 15min, 跟 Sprint 94 /document-release 模式 一致)

SPRINT_INDEX.md 当前只到 Sprint 66, 缺 Sprint 67+68+91+99+100+101 共 6 sprint. Sprint 102 必修 2 = 加这 6 sprint entry (跟 MEMORY.md 索引同步).

文件: `docs/history/SPRINT_INDEX.md`

加 Sprint 67+68+91+99+100+101 6 sprint entry (按版本号倒序):

```markdown
| **101** | v0.4.14.157 | Sprint 101 全部收尾 sprint — L4.21 反 sprint 自我反馈闭环永久规则 + 跨文档一致性 100% PASS + Codex 主动扩展 5 项亮点 | ✅ |
| **100** | v0.4.14.157 | L4.20 test 1 CI fresh checkout 必修 1 fail 治根 (1 commit 0 debt amend, 跟 Sprint 92.2 模式一致) | ✅ |
| **99** | v0.4.14.157 | 留尾 #11 SSOT 漂移闭环 + L4.20 反 SSOT 漂移永久规则 + check_ssot_drift.py | ✅ |
| **91** | v0.4.14.156 | 必修 4 闭环 (留尾治理 sprint 模式, 跟 Sprint 67+68 一致, 1 sprint 多范围) | ✅ |
| **68** | v0.4.14.155 | Sprint 67+68 留尾 SSOT 治理 (L4.12 永久规则 + 4 follow-up gap 闭环, 1 commit amend 0 debt) | ✅ |
| **67** | v0.4.14.155 | Sprint 67 留尾 SSOT 治理 (跟 Sprint 68 amend 闭环) | ✅ |
```

**T2 验收**: SPRINT_INDEX.md 加 6 sprint entry, 跟 MEMORY.md 索引 100% 同步.

### T3 — 必修 3: 跨文档一致性 100% PASS 验证 (5min, 跟 Sprint 94 /document-release 模式一致)

跑 check_ssot_drift.py + 验证 8 项文件一致:

| 文件 | 验证 |
|------|------|
| `VERSION` | `0.4.14.157` (Sprint 102 不 bump, 留尾治理 sprint 模式 跟 Sprint 67+68+91+96+96.5+99+100+101 一致) |
| `CHANGELOG.md` top entry | `## [0.4.14.157] - 2026-06-23 (Sprint 101, ...)` (Sprint 102 不加 entry, 跟 Sprint 67+68+91+96+96.5+99+100+101 留尾治理 sprint 模式一致) |
| `STATUS.md` 最后更新 | Sprint 102 收口 entry (更新到 Sprint 102) |
| `git HEAD (main)` | `c851915` (Sprint 101 merge, Sprint 102 merge 后变 `XXXXX`) |
| `CLAUDE.md L4.x` | 21 stable (Sprint 102 不新增, 维护 21 条) |
| `docs/TECH-DEBT.md` 留尾 #11 | ✅ 闭环 (引用 commit `287efb8`) |
| `docs/history/SPRINT_INDEX.md` | Sprint 101 + 100 + 99 + 91 + 68 + 67 共 6 sprint 新增 (跟 MEMORY.md 索引同步) |
| `pytest baseline` | 819 passed / 23 skipped / 0 failed |

**T3 验收**: 8/8 验证通过, 跨文档一致性 100% PASS.

---

## 2. 验收标准 (Acceptance Criteria)

### 必达项 (跟 Sprint 99+100+101 留尾治理 sprint 模式 一致)

1. ✅ **T1 Sprint 98 Handoff commit** (修 Sprint 101 收口后漂移, 跟 Sprint 99+101 Handoff 模式一致)
2. ✅ **T2 SPRINT_INDEX.md 加 Sprint 67+68+91+99+100+101 6 sprint** (修跨文档漂移, 跟 MEMORY.md 索引同步)
3. ✅ **T3 跨文档一致性 100% PASS** (8/8 文件同步, 跟 Sprint 94 /document-release 模式一致)
4. ✅ **0 业务代码改动** (留尾治理 sprint 模式, 跟 Sprint 67+68+91+96+96.5+99+100+101 一致)
5. ✅ **0 留尾新增** (Sprint 60+ 留尾 5 项仍闭环 + 1 推后, L4.x 永久规则 21 stable 0 新增)
6. ✅ **累计 52 sprint 0 debt 持续** (Sprint 56+60+60.1+60.1.1+60.2+61+...+101+102)
7. ✅ **VERSION 不 bump** (0.4.14.157 持续, 留尾治理 sprint 模式 跟 Sprint 67+68+91+96+96.5+99+100+101 一致)
8. ✅ **pytest baseline 819/23/0 持续** (Sprint 101 baseline 持续, 0 fail)
9. ✅ **check_ssot_drift.py 仍 2 records** (1 ✅ 闭环 + 1 📋 推后), 0 SSOT 漂移
10. ✅ **MEMORY.md L4.13 PASS** (≤ 24576 bytes)

### 不达项 (跟 Sprint 89 暂收口 + Sprint 99+100+101 0 治理 SOP 追加 一致)

- ❌ 0 Sprint 102 真业务代码 (留尾治理 sprint 0 业务代码, 跟 Sprint 99+100+101 模式一致)
- ❌ 0 VERSION bump (留尾治理 sprint 不 bump)
- ❌ 0 L4.x 永久规则新增 (21 stable 维护不新增, 跟 Sprint 89 暂收口 0 治理 SOP 追加 一致)
- ❌ 0 push 触发 (L4.15 push 必 user 拍板, Stage 4 才决定)

---

## 3. Sprint 102 留尾 (0 项, 跟 Sprint 99+100+101 一致)

按 L4.12 留尾 SSOT 治理 + Sprint 89 暂收口原则:

- ✅ Sprint 60+ 留尾 #1-#4 全闭环 (Sprint 60.1+97+98+90+60++91+99+100)
- ✅ L4.20 test 1 CI fresh checkout (Sprint 100)
- 📋 **D1 50m-scale benchmark** (跨 sprint 推后, 触发条件 30M 数据量, 等业务触发)

**Sprint 102 留尾闭环后**, 整个 Sprint 60+ 留尾列表 5 项 → **4 闭环 + 1 推后 (D1)**, 累计 52 sprint 0 debt 持续, L4.x 永久规则 21 stable (Sprint 102 维护不新增).

---

## 4. Stage 4 commit 规范 (跟 Sprint 99+100+101 留尾治理 sprint 模式 + Sprint 100 amend drift L4.14 一致)

### 1 commit 0 debt amend (跟 Sprint 100+101 模式 一致)

```bash
git checkout -b fix/sprint102-mandatory-close-doc-drift  # 已开
# 1. Stage Sprint 98 Handoff (T1)
git add docs/sprints/HANDOFF-TO-CODEX-Sprint98-FilterBuilder-True-Root-Fix.md
# 2. 更新 SPRINT_INDEX.md (T2)
# 编辑 docs/history/SPRINT_INDEX.md 加 Sprint 67+68+91+99+100+101 6 sprint entry
# 3. 跨文档同步 (T3)
git add docs/history/SPRINT_INDEX.md STATUS.md CHANGELOG.md docs/TECH-DEBT.md
git commit -m "chore(sprint): Sprint 102 必修 2 项文档漂移修复 + L4.x 永久规则 21 stable 维护 (1 commit 0 debt amend, 跟 Sprint 100 amend drift L4.14 + Sprint 99+100+101 留尾治理 sprint 模式 一致)"
git push origin fix/sprint102-mandatory-close-doc-drift
# 4. 等 user 拍板 push (L4.15)
```

### Commit message 规范 (跟 Sprint 99+100+101 模式 一致)

```
chore(sprint): Sprint 102 必修 2 项文档漂移修复 + L4.x 永久规则 21 stable 维护

- T1: commit Sprint 98 Handoff (修 Sprint 101 收口后漂移, 跟 Sprint 99+101 Handoff 模式一致)
- T2: SPRINT_INDEX.md 加 Sprint 67+68+91+99+100+101 6 sprint (修跨文档漂移)
- T3: 跨文档一致性 100% PASS (8/8 文件同步, 跟 Sprint 94 /document-release 模式一致)
- 0 业务代码改动 (留尾治理 sprint 模式, 跟 Sprint 67+68+91+96+96.5+99+100+101 一致)
- VERSION 不 bump (0.4.14.157 持续)
- 累计 52 sprint 0 debt 持续 (Sprint 56+60+...+101+102)
- L4.x 永久规则 21 stable 0 新增 (维护不新增, 跟 Sprint 89 暂收口 0 治理 SOP 追加 一致)
```

### 12 步流程 (跟 Sprint 99+100+101 12 步流程一致)

1. ✅ git checkout -b fix/sprint102-mandatory-close-doc-drift
2. ✅ 改 code (T1+T2+T3, 0 业务代码改动)
3. ✅ pytest baseline (819/23/0 持续)
4. ✅ review (跳过 /review skill, 手动 review, 跟 Sprint 99+100+101 模式一致)
5. ✅ fix (Codex 实施 + user 拍板)
6. ✅ commit (1 commit amend, 跟 Sprint 100+101 模式 一致)
7. ✅ push origin fix branch
8. ✅ qa (skip simple fix)
9. ✅ merge --no-ff to main
10. ✅ push origin main + fix branch
11. ✅ pull --ff-only (verify 0 drift)
12. ✅ restart uvicorn (skip, 0 业务代码改动)

---

## 5. 风险评估 (跟 Sprint 99+100+101 留尾治理 sprint 模式 一致)

| 风险 | 等级 | 缓解 |
|------|------|------|
| Sprint 98 Handoff commit 冲突 | **极低** (单文件添加, 0 冲突) | T1 单文件 git add, 跟 Sprint 99+101 Handoff 模式一致 |
| SPRINT_INDEX.md 排序错误 | **极低** (按版本号倒序, 6 sprint 加在 Sprint 66 后面) | T2 按 Sprint 66 → 67 → 68 → 91 → 99 → 100 → 101 顺序加 |
| 跨文档漂移复发 | **极低** (T3 跨文档一致性 100% PASS 验证) | T3 8/8 文件同步验证 + check_ssot_drift.py 2 records PASS |
| Codex 越界 | **低** (Stage 2 自主 audit 模式 跟 Sprint 99+100+101 一致) | Stage 3 手动 review + user 拍板 A/B/C |

---

## 6. Codex 高阶能力激发 (LLM 工程最佳实践)

Codex 自主决策空间 (跟 Sprint 99+100+101 + L4.21 反 sprint 自我反馈闭环永久规则 一致):

1. **Codex Stage 2 主动 audit 模式** (跟 Sprint 97+98+101 一致): Codex 不只是实施 T1+T2+T3, 主动 audit Sprint 101 收口后是否还有其他文档漂移 (类似 Sprint 98 Handoff untracked 漂移).

2. **破坏→验证→恢复 模式** (跟 Sprint 60+ + Sprint 90 L4.7 + Sprint 97 L4.19 + Sprint 99 L4.20 + Sprint 101 L4.21 模式 一致): 加 regression test 防止类似问题再次发生.

3. **跨 sprint 真因真发现模式** (跟 Sprint 96.5 7 sprint 完整链路真因真发现实战 fix 模式 一致): 主动 audit Sprint 101 收口后跨文档漂移根因 = Handoff untracked 漂移 (Sprint 98 收口时漏 commit Handoff).

4. **ASCII 流程图 + Diataxis 文档结构**: 让 Codex 在 close memory 加 ASCII 流程图 (Sprint 101 收口后 2 项漂移诊断 + 修复流程 + L4.x 永久规则 21 stable 维护).

5. **自主决策空间 (跟 Sprint 100+101 模式 一致)**:
   - 必修 1+2+3: T1+T2+T3 严格按 HANDOFF 实施
   - 自主空间: 加 ASCII 流程图 + Diataxis 文档结构 (跟 Sprint 60+ + Sprint 89-101 实战 fix 模式库 + L4.x 永久规则 21 条 + Sprint 101 Codex 主动扩展 5 项亮点 一致)
   - 反边界: 0 业务代码改动 + 0 VERSION bump + 1 commit 0 debt amend (跟 Sprint 100+101 模式 一致)

---

## 7. 参考链接 (跟 Sprint 99+100+101 留尾治理 sprint 模式 一致)

- **Sprint 101 留尾治理 sprint 模式真治本**: 5 项 Codex 主动扩展亮点 (CLAUDE.md 版本状态 + CHANGELOG.md 修复 Sprint 100 排序漂移 + STATUS.md 多字段 + TECH-DEBT.md 留尾总表 + L4.20 test 1 entry)
- **Sprint 100 留尾治理 sprint 模式真治本**: `backend/tests/test_sprint99_l4_ssot_drift_lint.py` (1 行移除 git cat-file -e 验证, 1 commit amend 模式, 跟 Sprint 90 amend drift L4.14 一致)
- **Sprint 99 L4.20 永久规则**: `CLAUDE.md` line 251 L4.20 行 + `backend/scripts/check_ssot_drift.py` 190 行结构化 ground-truth-lint (HTML marker + record 正则 + git cat-file -e 验证 + SSOT 漂移复发检查)
- **Sprint 101 L4.21 永久规则**: `CLAUDE.md` line 252 L4.21 行 (反 sprint 自我反馈闭环永久规则, 引用 Sprint 100 amend drift L4.14 + Sprint 91 反思治根模式)
- **Sprint 91 必修 5 反思治根模式** (D3+D4 标闭环): 跨 sprint 误列已闭环 4 次治根
- **Sprint 90 L4.7 ground-truth-lint**: `_compute_*` 函数体加 `assert sql.count('?') == len(params)` 防回归 + 3 case regression test
- **Sprint 97 L4.19 channel alias**: `backend/scripts/check_channel_alias.py` 170 行 ground-truth-lint + 3 case regression test
- **Sprint 96+96.1+96.2+96.3+96.4+96.5 7 sprint 完整链路 D2 e2e 50+MB OOM 治本真因真发现实战 fix 模式**: 跨 sprint 真因真发现模式库 (跳 7 步任 1 步 → 必修 2 误诊真因真发现)
- **Sprint 100 amend drift L4.14**: 1 commit amend 模式 (跟 Sprint 90 amend drift L4.14 一致)
- **Sprint 89 暂收口原则**: 0 主动开 sprint, 等真业务 sprint 报 bug / 30M 数据量触发再开
- **Sprint 102 Sprint 60+ 留尾列表 (4 闭环 + 1 推后)**: Sprint 60.1+97+98+90+60+91+99+100 4 项闭环 + D1 50m-scale 1 项推后
- **LLM 高阶能力激发的工程实践**: 明确角色定位 + 上下文丰富 (9 sprint 实战 fix 模式库 + L4.x 21 条) + 自主决策空间 + ASCII 流程图 + Diataxis 文档结构

---

**Sprint 102 HANDOFF 完成. 等 Codex Stage 2 实施 → Stage 3 review → Stage 4 commit + push 收口.**