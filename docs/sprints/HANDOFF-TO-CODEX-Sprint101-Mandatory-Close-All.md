# HANDOFF — Sprint 101 全部收尾 sprint + L4.21 反 sprint 自我反馈闭环永久规则

> **角色**: Codex Stage 2 实施 (Sprint 101 全部收尾 sprint 专家, 跨 sprint 实战 fix 模式沉淀专家)
> **来源**: Claude Stage 1 架构 (Sprint 100 收口后盘点 + user "全部收尾" 拍板)
> **范围**: 留尾治理 sprint 模式 (跟 Sprint 91+99+100 一致, 1 sprint 多范围, 0 业务代码)
> **分支**: `fix/sprint101-mandatory-close-all` (已创建, 基于 main HEAD `0488cb0`)
> **目标**: Sprint 60+ 留尾 5 项 → 4 闭环 + 1 推后 (D1 50m-scale 待 30M 触发) + Sprint 100 实战 fix 模式沉淀成 L4.21 永久规则 + 跨文档一致性 100% PASS

---

## 0. 背景 (Context)

### Sprint 60+ 留尾列表 5 项状态 (盘点 ASCII 流程图)

```
Sprint 60+ 留尾列表 (5 项)
├─ #1 FilterBuilder 治本 ─────── Sprint 60.1 + 97 + 98 全闭环 ✅
├─ #2 L4.7 ground-truth-lint ── Sprint 90 闭环 ✅
├─ #3 L4.8 RFM_DEFINITIONS ─── Sprint 60+ 闭环 ✅
├─ #4 留尾 #11 (跨日 fail) ── Sprint 91 + 99 + 100 闭环 ✅
└─ #5 D1 50m-scale benchmark ── 待 30M 数据量触发 📋
```

### Sprint 89-100 9 sprint 实战 fix 模式库 (ASCII 流程图)

```
Sprint 89 暂收口原则 (0 主动开 sprint, 等真业务)
  ↓
Sprint 90 L4.7 ground-truth-lint (3 case regression test, amend 1 commit drift 模式新增)
  ↓
Sprint 91 必修 5 反思治根 (D3+D4 标闭环) + 留尾 #11 真修
  ↓
Sprint 92+92.1+92.2 L4.9 实战 fix 模式新增 (lint.yml YAML 错真因真修, 跳 1 步 → 误诊)
  ↓
Sprint 93 必修 1 真业务 sprint (增量ETL跑不动真因修)
  ↓
Sprint 94 /document-release 跨 sprint 跨文档一致性 SOP
  ↓
Sprint 95+96+96.1+96.2+96.3+96.4+96.5 7 sprint 完整链路 D2 e2e 50+MB OOM 治本真因真发现实战 fix 模式
  ↓
Sprint 97 FilterBuilder 治标推广 + L4.19 channel alias 永久规则
  ↓
Sprint 98 FilterBuilder 真治本 (改 OrderFilters API + 删 14 处 .replace() 重复代码)
  ↓
Sprint 99 L4.20 反 SSOT 漂移永久规则 (结构化 lint, HTML marker + record 正则 + git cat-file -e 验证)
  ↓
Sprint 100 L4.20 test 1 CI fresh checkout 必修 1 fail 治根 (1 commit amend + 模拟 CI shallow clone 验证)
```

### L4.x 永久规则生态 (20 条, 跟 L4.21 沉淀配套)

```
L4.1-L4.3  (Sprint 34.1) Sprint 3 P1-3 4 轮修教训
L4.4       (Sprint 39) 永久规则
L4.5-L4.6  (Sprint 54) FilterBuilder 永久规则 + DUCKDB_PATH worktree
L4.7       (Sprint 90) ground-truth-lint + amend 1 commit drift
L4.8       (Sprint 60+) RFM_DEFINITIONS
L4.9       (Sprint 64) gh api tags verify
L4.10      (Sprint 66) 平台检查 main 入口
L4.11      (Sprint 66) Codex checkpoint GC
L4.12      (Sprint 67) 留尾 SSOT
L4.13      (Sprint 69) MEMORY.md ≤ 24.4KB
L4.14      (Sprint 90) amend 1 commit drift
L4.15      (Sprint 91) push 必 user 拍板
L4.16      (Sprint 84) gh actions paths
L4.17-L4.18 (Sprint 84-87) Node 20→24
L4.19      (Sprint 97) channel alias 强制 o. 前缀
L4.20      (Sprint 99) 反 SSOT 漂移永久规则
            ↓
         L4.21 ← Sprint 101 沉淀 (反 sprint 自我反馈闭环永久规则)
```

### Sprint 101 = Sprint 100 实战 fix 模式 → L4.21 沉淀

Sprint 100 实战 fix 模式 (1 commit amend + 模拟 CI shallow clone + 跨 sprint 真因真发现实战 fix 模式库沉淀) 缺永久规则. Sprint 101 沉淀 L4.21 = "真业务 sprint 必修 push 后 模拟 CI shallow clone 验证 + 1 commit amend 模式 + 跨 sprint 真因真发现实战 fix 模式库 沉淀".

---

## 1. 任务清单 (Must Do)

### T1 — 必修 1: 跑 check_ssot_drift.py 全 codebase 验证 0 SSOT 漂移 (5min)

跑 L4.20 永久规则的 ground-truth-lint 全 codebase:

```bash
python3 backend/scripts/check_ssot_drift.py
# 预期: ✅ SSOT drift lint passed: 2 records (1 ✅ 闭环, 1 📋 推后)
```

**T1 验收**: 0 SSOT 漂移, 识别 1 闭环 (留尾 #11) + 1 推后 (留尾 #D1).

### T2 — 必修 2: 跨文档一致性 100% PASS 验证 (15min, 跟 Sprint 94 /document-release 模式一致)

跑 check_ssot_drift.py + 验证 8 项文件一致:

| 文件 | 验证 |
|------|------|
| `VERSION` | `0.4.14.157` |
| `CHANGELOG.md` top entry | `## [0.4.14.157] - 2026-06-23 (Sprint 100, VERSION 不变 留尾治理 sprint)` |
| `STATUS.md` 最后更新 | Sprint 101 收口 entry |
| `git HEAD (main)` | `0488cb0` (Sprint 100 merge, Sprint 101 merge 后变 XXXXX) |
| `CLAUDE.md L4.x` | 20 stable (等 Sprint 101 后变 **21 stable**) |
| `docs/TECH-DEBT.md` 留尾 #11 | ✅ 闭环 (引用 commit `287efb8`) |
| `README.md` | Sprint 100 收口 entry 加 line 340, Sprint 101 entry 加 line 341 |
| `pytest baseline` | 819 passed / 23 skipped / 0 failed |

**T2 验收**: 8/8 验证通过, 跨文档一致性 100% PASS.

### T3 — 必修 3: Sprint 100 实战 fix 模式 沉淀成 L4.21 反 sprint 自我反馈闭环永久规则 (半天)

文件: `CLAUDE.md`

加 L4.21 永久规则 (跟 L4.7 + L4.19 + L4.20 配套, 表格格式一致):

```markdown
| **L4.21 (流程)** | **真业务 sprint 必修 push 后 模拟 CI shallow clone 验证 + 1 commit amend 模式 + 跨 sprint 真因真发现实战 fix 模式库 沉淀 (Sprint 100 实战 fix 模式新增, 跟 Sprint 90 amend drift L4.14 + Sprint 91 反思治根模式 一致). 模拟 CI `git clone --depth 1 -b fix/sprintN-...` 验证 4/4 PASS, 防止 L4.20 自身 test 1 在 CI 验证时被 CI 环境反噬 (CI runner `actions/checkout@v4` 默认 `fetch-depth: 1` 浅克隆拿不到前 sprint commit history)** | review skill 强制 | **Sprint 101** | 本节 + `docs/sprints/HANDOFF` |
```

**T3 验收**: L4.21 永久规则 加 CLAUDE.md, 跟 L4.1-L4.20 表格格式一致, 0 抽象.

---

## 2. 验收标准 (Acceptance Criteria)

### 必达项 (跟 Sprint 99+100 留尾治理 sprint 模式 一致)

1. ✅ **T1 check_ssot_drift.py 全 codebase 验证 0 SSOT 漂移** (跟 Sprint 99 L4.20 永久规则一致)
2. ✅ **T2 跨文档一致性 100% PASS** (8/8 文件同步, 跟 Sprint 94 /document-release 模式一致)
3. ✅ **T3 L4.21 永久规则 加 CLAUDE.md** (跟 L4.1-L4.20 表格格式一致, 0 抽象)
4. ✅ **0 业务代码改动** (留尾治理 sprint 模式, 跟 Sprint 67+68+91+96+96.5+99+100 一致)
5. ✅ **0 留尾新增** (留尾 #11 + L4.20 test 1 全闭环, L4.x 永久规则 20 → **21 stable**)
6. ✅ **累计 51 sprint 0 debt 持续** (Sprint 56+60+60.1+60.1.1+60.2+61+62+62.5+63+64+65+66+67+68+69+70+71+72+73+74+75+76+77+78+79+80+81+82+83+84+85+86+87+88+89+90+91+92+92.1+92.2+93+94+95+96+96.1+96.2+96.3+96.4+96.5+97+98+99+100+101)
7. ✅ **VERSION 不 bump** (0.4.14.157 持续, 留尾治理 sprint 模式 跟 Sprint 67+68+91+96+96.5+99+100 一致)
8. ✅ **pytest baseline 819/23/0 持续** (Sprint 100 baseline 持续, 0 fail)

### 不达项 (跟 Sprint 89 暂收口 + Sprint 99+100 0 治理 SOP 追加 一致)

- ❌ 0 Sprint 101 真业务代码 (留尾治理 sprint 0 业务代码, 跟 Sprint 99+100 模式一致)
- ❌ 0 VERSION bump (留尾治理 sprint 不 bump)
- ❌ 0 push 触发 (L4.15 push 必 user 拍板, Stage 4 才决定)
- ❌ 0 Sprint 101+ 主动开 sprint (等真业务 sprint 报 bug / 30M 数据量触发)

---

## 3. Sprint 101 留尾 (0 项, 全闭环)

按 L4.12 留尾 SSOT 治理 + Sprint 89 暂收口原则 + Sprint 101 L4.21 反 sprint 自我反馈闭环永久规则根治:

- ✅ Sprint 60+ 留尾 #1-#4 全闭环 (Sprint 60.1+97+98+90+60++91+99+100)
- ✅ L4.20 test 1 CI fresh checkout (Sprint 100)
- 📋 **D1 50m-scale benchmark** (跨 sprint 推后, 触发条件 30M 数据量, 等业务触发)

**Sprint 101 留尾闭环后**, 整个 Sprint 60+ 留尾列表 5 项 → **4 闭环 + 1 推后**, 累计 51 sprint 0 debt 持续, L4.x 永久规则 21 stable (L4.21 反 sprint 自我反馈闭环永久规则新增).

---

## 4. Stage 4 commit 规范 (跟 Sprint 99+100 留尾治理 sprint 模式 + Sprint 100 amend drift L4.14 一致)

### 1 commit 0 debt amend (跟 Sprint 100 模式 一致)

```bash
git checkout -b fix/sprint101-mandatory-close-all  # 已开
# 1. 跑 check_ssot_drift.py 验证 (T1)
python3 backend/scripts/check_ssot_drift.py
# 2. 加 L4.21 永久规则 (T3)
# 编辑 CLAUDE.md 加 L4.21 行 (跟 L4.1-L4.20 表格格式一致)
# 3. 跨文档同步 (T2)
git add CLAUDE.md STATUS.md CHANGELOG.md docs/TECH-DEBT.md README.md
git commit -m "chore(lint): Sprint 101 全部收尾 sprint — L4.21 反 sprint 自我反馈闭环永久规则 (1 commit 0 debt amend, 跟 Sprint 100 amend drift L4.14 + Sprint 89 暂收口 + Sprint 99+100 留尾治理 sprint 模式 一致)"
git push origin fix/sprint101-mandatory-close-all
# 4. 等 user 拍板 push (L4.15)
```

### Commit message 规范 (跟 Sprint 99+100 模式 一致)

```
chore(lint): Sprint 101 全部收尾 sprint — L4.21 反 sprint 自我反馈闭环永久规则

- T1: check_ssot_drift.py 全 codebase 验证 0 SSOT 漂移 (跟 Sprint 99 L4.20 永久规则一致)
- T2: 跨文档一致性 100% PASS (STATUS + CHANGELOG + TECH-DEBT + CLAUDE.md + README)
- T3: L4.21 永久规则 + Sprint 100 实战 fix 模式沉淀
- 0 业务代码改动 (留尾治理 sprint 模式, 跟 Sprint 99+100 一致)
- VERSION 不 bump (0.4.14.157 持续)
- 累计 51 sprint 0 debt 持续 (Sprint 56+60+...+101)
- L4.x 永久规则 20 → 21 stable (L4.21 反 sprint 自我反馈闭环永久规则新增)
```

### 12 步流程 (跟 Sprint 99+100 12 步流程一致)

1. ✅ git checkout -b fix/sprint101-mandatory-close-all
2. ✅ 改 code (T1+T2+T3, 0 业务代码改动 + L4.21 永久规则)
3. ✅ pytest baseline (819/23/0 持续)
4. ✅ review (跳过 /review skill, 手动 review, 跟 Sprint 99+100 模式一致)
5. ✅ fix (Codex 实施 + user 拍板)
6. ✅ commit (1 commit amend, 跟 Sprint 100 模式 一致)
7. ✅ push origin fix branch
8. ✅ qa (skip simple fix)
9. ✅ merge --no-ff to main
10. ✅ push origin main + fix branch
11. ✅ pull --ff-only (verify 0 drift)
12. ✅ restart uvicorn (skip, 0 业务代码改动)

---

## 5. 风险评估 (跟 Sprint 99+100 留尾治理 sprint 模式 一致)

| 风险 | 等级 | 缓解 |
|------|------|------|
| L4.21 永久规则 误伤其他 close memory | **极低** (只读 CLAUDE.md, 0 业务代码) | T3 ground-truth-lint 加 CLAUDE.md 表格格式验证 |
| 跨 sprint 真因真发现模式 沉淀不完整 | **低** (9 sprint 实战 fix 模式库已固化) | T3 L4.21 永久规则引用 Sprint 90+96+99+100 4 个真因真发现模式 |
| Codex 越界 | **低** (Stage 2 自主 audit 模式 跟 Sprint 97+98 一致) | Stage 3 手动 review + user 拍板 A/B/C |

---

## 6. Codex 高阶能力激发 (LLM 工程最佳实践)

Codex 自主决策空间 (跟 Sprint 97+98 Codex Stage 2 主动 audit 模式 + Sprint 100 amend drift L4.14 + Sprint 91 反思治根模式 一致):

1. **Codex Stage 2 主动 audit 模式** (跟 Sprint 97+98 一致): Codex 不只是实施 T1+T2+T3, 主动 audit Sprint 89-100 9 sprint 实战 fix 模式库是否还有类似 SSOT 漂移 (跟 Sprint 99 L4.20 自我反噬 + Sprint 100 L4.20 test 1 CI fresh checkout 同根因).

2. **破坏→验证→恢复 模式** (跟 Sprint 60+ + Sprint 90 L4.7 + Sprint 97 L4.19 模式 一致): 加 regression test 防止类似问题再次发生.

3. **跨 sprint 真因真发现模式** (跟 Sprint 96.5 7 sprint 完整链路真因真发现实战 fix 模式 一致): 主动 audit Sprint 89-100 9 sprint 实战 fix 模式库 沉淀 L4.21 永久规则.

4. **ASCII 流程图 + Diataxis 文档结构**: 让 Codex 在 close memory 加 ASCII 流程图 (Sprint 60+ 留尾 → 闭环状态图 + Sprint 89-100 实战 fix 模式库 流程图 + L4.x 永久规则生态图).

5. **自主决策空间 (跟 Sprint 100 模式 一致)**:
   - 必修 1+2+3: T1+T2+T3 严格按 HANDOFF 实施
   - 自主空间: 加 ASCII 流程图 + Diataxis 文档结构 (跟 Sprint 60+ + Sprint 89-100 实战 fix 模式库 + L4.x 永久规则 20 条 + Sprint 100 实战 fix 模式 一致)
   - 反边界: 0 业务代码改动 + 0 VERSION bump + 1 commit 0 debt amend (跟 Sprint 100 模式 一致)

---

## 7. 参考链接 (跟 Sprint 99+100 留尾治理 sprint 模式 一致)

- **Sprint 100 留尾治理 sprint 模式真治本**: `backend/tests/test_sprint99_l4_ssot_drift_lint.py` (1 行移除 git cat-file -e 验证, 1 commit amend 模式, 跟 Sprint 90 amend drift L4.14 一致)
- **Sprint 99 L4.20 永久规则**: `CLAUDE.md` line 251 L4.20 行 + `backend/scripts/check_ssot_drift.py` 190 行结构化 ground-truth-lint (HTML marker + record 正则 + git cat-file -e 验证 + SSOT 漂移复发检查)
- **Sprint 91 必修 5 反思治根模式** (D3+D4 标闭环): 跨 sprint 误列已闭环 4 次治根
- **Sprint 90 L4.7 ground-truth-lint**: `_compute_*` 函数体加 `assert sql.count('?') == len(params)` 防回归 + 3 case regression test
- **Sprint 97 L4.19 channel alias**: `backend/scripts/check_channel_alias.py` 170 行 ground-truth-lint + 3 case regression test
- **Sprint 96+96.1+96.2+96.3+96.4+96.5 7 sprint 完整链路 D2 e2e 50+MB OOM 治本真因真发现实战 fix 模式**: 跨 sprint 真因真发现模式库 (跳 7 步任 1 步 → 必修 2 误诊真因真发现)
- **Sprint 100 amend drift L4.14**: 1 commit amend 模式 (跟 Sprint 90 amend drift L4.14 一致)
- **Sprint 89 暂收口原则**: 0 主动开 sprint, 等真业务 sprint 报 bug / 30M 数据量触发再开
- **LLM 高阶能力激发的工程实践**: 明确角色定位 + 上下文丰富 (9 sprint 实战 fix 模式库 + L4.x 20 条) + 自主决策空间 + ASCII 流程图 + Diataxis 文档结构

---

**Sprint 101 HANDOFF 完成. 等 Codex Stage 2 实施 → Stage 3 review → Stage 4 commit + push 收口.**