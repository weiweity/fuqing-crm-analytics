# Sprint 57 架构设计 — 文档沉淀主题

> **Sprint 57 实施架构 (2026-06-21, v0.4.14.140 起步)**
> 主题: 跨 sprint 留尾 10 项收敛 — 文档沉淀主题 (Sprint 57) + 工具链实战 fix (Sprint 58) + 收割季 (Sprint 59)
> 本文档覆盖 Sprint 57 三项 doc-only 改动 (#10 + #9 + #7)

---

## Context

Sprint 56 收口后 (v0.4.14.140, main HEAD `d995d29`), 跨 sprint 留尾 10 项 (从 Sprint 55.5 19 项收敛 -47%)。
Sprint 57 闭环 **3 项 doc-only** (高 ROI + 跟 Sprint 56 doc-only 闭环模式一致):

- **#10** 实战 fix 沉淀 (9 项 pattern → `docs/development/LESSONS_LEARNED.md`, ≥ 500 行)
- **#9** 4 doc 扩内容 (CACHE 50M ROW + ground-truth-lint + fixture→test 映射 + spec-lint L1 fallback)
- **#7** asset_* 命名混淆文档化 (`docs/development/services.md` §5 扩内容)

**为什么不直接 commit 到 main** (CLAUDE.md L0 + feedback_workflow):
- Sprint 43+ 实战沉淀: Codex Stage 2 协作走 3 个 git worktree 隔离实施, Stage 3 一次性 review, Stage 4 串行合并
- doc-only 风险低, 但 #10 9 项 pattern 沉淀内容互相引用, worktree 隔离避免 Stage 4 合并冲突
- 12 步流程 ④ review + ⑧ qa 必走 (即使 doc-only, Sprint 41 + 55 实战 fix 模式)

---

## 现状 (跟 Sprint 56 闭环产物对照)

### Sprint 56 闭环产物 (Sprint 57 输入)

| 产物 | 行数 | 用途 | Sprint 57 扩内容 |
|------|------|------|------------------|
| `docs/development/testing.md` | 60 行 | quick card (L4.3/L4.4) | #9 链 fixture→test 映射 (扩 §1) |
| `docs/development/services.md` | 63 行 | 14 service 表格 | #7 扩 §5 asset_* 概念边界 |
| `docs/development/ratio-convention.md` | 56 行 | SSOT 警告 + B1/B2 链 | (不动, 已 SSOT) |
| `docs/history/SPRINT_INDEX.md` | 50 行 | Sprint 索引 + 维护规则 | (不动, 维护规则已加) |
| `docs/architecture/TEST_INFRASTRUCTURE.md` | 511 行 | fixture + race flake | #9 扩 §3 fixture→test 映射表 |
| `docs/architecture/DATA_PIPELINE.md` | 247 行 | ETL 4 阶段 | #9 加 §6 CACHE 50M ROW 实测数据 |
| `docs/architecture/AI_SAFETY_NET.md` | (待查) | L1/L2/L3 防御 | #9 扩 ground-truth-lint 完整指南 |
| `docs/operating/pre-commit.md` | (待查) | pre-commit hook | #9 加 spec-lint L1 fallback 触发条件 |

### 当前 worktree 状态 (Stage 2 起点)

```
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics                 d995d29 [main]
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-01  d995d29 [feat/sprint57-01-lessons-learned]
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-02  d995d29 [feat/sprint57-02-doc-extend]
/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-03  d995d29 [feat/sprint57-03-asset-service-map]
```

**Stage 2 起点**: 3 个 worktree 全部从 main HEAD `d995d29` 切出, 各自独立 commit, Stage 4 串行合并到 main。

---

## 三项改动清单

### #10 实战 fix 沉淀 (worktree 01, 1.5d)

**新建文件**: `docs/development/LESSONS_LEARNED.md` (目标 ≥ 500 行, 9 项实战 fix pattern)

**9 项 pattern 大纲** (Sprint 50+ 实战沉淀):

| # | Pattern | 实战 sprint | 关键证据 |
|---|---------|------------|----------|
| 1 | DUCKDB_PATH 实战 fix (worktree 跨仓跑 pytest) | Sprint 53 → 54 | Sprint 53 close memory + 4 worker 0 锁冲突 |
| 2 | subagent 验证模式 (Stage 3 review) | Sprint 43+ | Stage 3 review 必跑子 agent 实测 |
| 3 | race flake 治本 pattern | Sprint 53 闭环 | per-worker tmp + ATTACH read_only + search_path |
| 4 | spec-lint blocking 升级 (L1 → L2) | Sprint 43 → 50.1 | L2 AST 0 violation + L1 fallback |
| 5 | Codex 工作流持久化 | Sprint 43+ | Claude Stage 1 + Codex Stage 2 + Stage 3+4 |
| 6 | 12 步流程 + 5 follow-up 实战 fix | Sprint 41 + 55 | 4 commit 0 debt + 12 follow-up 模式 |
| 7 | "破坏 → 验证 → 恢复" 循环 | Sprint 34.1 → 36.4 | 单测真 FAIL 验证 |
| 8 | commit msg ↔ diff 一致性 check | Sprint 32.3 + 35 | a9b1d91 教训 (commit msg 说"清理" 实际 diff 1398 行) |
| 9 | empty directory vs stub doc 选择 | Sprint 55.5 沉淀 | stub 内容保留设计意图 |

**模板** (每项 pattern):
```markdown
## Pattern N: <name>

### 触发场景
<什么情况下用>

### 实战 sprint
<sprint 名 + commit SHA>

### 实施步骤 (Codex 模板)
1. ...
2. ...

### 验证命令
```bash
<具体命令 + 预期输出>
```

### 教训
<踩过的坑 + 治本 vs 治标决策>
```

**引用关系** (避免 Stage 4 合并冲突):
- 不引用 #9 / #7 内容 (避免双向依赖)
- 引用 CLAUDE.md L4.x 永久规则 (单向引用, 安全)
- 引用 docs/architecture/TEST_INFRASTRUCTURE.md §X (单向引用, 安全)

### #9 4 doc 扩内容 (worktree 02, 1d)

**改动清单**:

| 文件 | 章节 | 扩内容 | 行数目标 |
|------|------|--------|----------|
| `docs/architecture/DATA_PIPELINE.md` | §6 (新) | CACHE 50M ROW 实测数据 (Sprint 30.1 W4 实战) | +50 行 |
| `docs/architecture/AI_SAFETY_NET.md` | §4 (扩) | ground-truth-lint 完整指南 (L1/L2/L3 + 14 service 覆盖率) | +80 行 |
| `docs/architecture/TEST_INFRASTRUCTURE.md` | §5 (新) | fixture→test 映射表 (3 fixture × 14 service) | +60 行 |
| `docs/operating/pre-commit.md` | §3 (扩) | spec-lint L1 fallback 触发条件 (L2 失败时) | +30 行 |

**实测数据来源** (验证 accuracy):
- CACHE 50M ROW: Sprint 30.1 W4 540 combo batch INSERT (4,320→1 次 conn.execute, 50.4× 加速)
- ground-truth-lint: Sprint 54 L3 FilterBuilder 100% 闭环 (14/14 service, 0 violations, 69 files scanned)
- fixture→test: Sprint 53 race flake 治本 (per-worker tmp DuckDB + ATTACH read_only + PRAGMA search_path)
- spec-lint L1 fallback: Sprint 50.1 L2 wrapper 切换 + L1 保留 fallback

**引用关系**:
- #9 §4 (TEST_INFRASTRUCTURE) 引用 #9 §6 (DATA_PIPELINE) 单向引用 (同 worktree 内部, 安全)
- #9 不引用 #10 LESSONS_LEARNED.md (避免 #10 未完成时 #9 引用空文件)
- #9 不引用 #7 (独立)

### #7 asset_* 命名混淆文档化 (worktree 03, 0.5d)

**改动文件**: `docs/development/services.md` §5 扩内容 (当前 §5 已有短描述, 扩成完整 service map)

**扩内容结构**:

```markdown
## §5 asset_* 服务概念边界 (Sprint 57 沉淀)

### 5.1 命名差异 (避免误用)
| 服务 | 路径 | 用途 | exports |
|------|------|------|---------|
| `asset_service` | `backend/services/asset_service.py` | DMP 资产摘要/趋势 (单文件 facade) | get_asset_summary, get_asset_trend |
| `asset_focus_service` | `backend/services/asset_focus_service/` | DMP 资产聚焦 (子包, 7 core + 8 other 单品) | get_store_assets, get_product_assets, get_other_product_assets |

### 5.2 调用场景示例
```python
# 场景 1: 全店资产汇总 (概览页)
from backend.services.asset_service import get_asset_summary
summary = get_asset_summary(start_date, end_date)

# 场景 2: 7 大核心单品资产聚焦 (DMP 营销页)
from backend.services.asset_focus_service import get_store_assets
focused = get_store_assets(store_id, period)
```

### 5.3 rename 历史 (Sprint 55.5 实战)
- 原名: `sample_asset_service/` (命名误导, 业务是 DMP 资产聚焦不是 sample demo)
- 改名: Sprint 55.5 commit `bd95cd8` (P0 命名重构)
- 教训: 命名相似但不同概念时, 加 service map 文档化避免误用
```

**引用关系**:
- #7 引用 CLAUDE.md §0 (Sprint 55.5 close memory)
- #7 不引用 #10 / #9 (独立)

---

## 跨 doc 引用关系图 (避免 Stage 4 合并冲突)

```
CLAUDE.md (主索引, 不动)
    │
    ├─→ docs/development/LESSONS_LEARNED.md (#10 新建)
    │       │
    │       ├─→ docs/architecture/TEST_INFRASTRUCTURE.md (§X 单向引用)
    │       ├─→ docs/architecture/AI_SAFETY_NET.md (§X 单向引用)
    │       └─→ docs/architecture/DATA_PIPELINE.md (§X 单向引用)
    │
    ├─→ docs/architecture/TEST_INFRASTRUCTURE.md (#9 §5 新 fixture→test 映射表)
    │       │
    │       └─→ docs/architecture/DATA_PIPELINE.md (§X 单向引用, 同 worktree)
    │
    ├─→ docs/architecture/DATA_PIPELINE.md (#9 §6 CACHE 50M ROW)
    ├─→ docs/architecture/AI_SAFETY_NET.md (#9 §4 ground-truth-lint)
    └─→ docs/development/services.md (#7 §5 asset_* 概念边界)
```

**关键不变量**:
- #10 → #9 单向引用 (#10 不引用 #9 内容, 避免 #10 完成时 #9 未完成导致死链接)
- #9 内部 4 doc 互引 (同 worktree, 合并无冲突)
- #7 独立 (不引用 #9 / #10)

**Stage 4 合并顺序** (避免 doc 引用断裂):
1. worktree 02 (#9 4 doc 扩内容) 先合 — 提供 ground-truth 数据
2. worktree 01 (#10 LESSONS_LEARNED.md) 接着合 — 引用 #9 内容有保障
3. worktree 03 (#7 asset_* 服务 map) 最后合 — 独立

---

## 验收标准

### 单元 + 集成

```bash
# pytest 持续 (doc-only 0 回归)
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q   # 758/1 持续

# 前端 build 持续
cd frontend-vue3 && npx vite build                  # 750ms 持续

# L2 spec-lint
cd frontend-vue3 && npm run lint:spec               # 0 violation

# L3 ground-truth-lint
python3 backend/scripts/check_filter_builder_usage.py  # 0 violations (69 files)
```

### 文档完整性

```bash
# #10 9 项 pattern 完整性
test -f docs/development/LESSONS_LEARNED.md
test $(wc -l < docs/development/LESSONS_LEARNED.md) -ge 500  # ≥ 500 行
grep -c "^## Pattern" docs/development/LESSONS_LEARNED.md       # ≥ 9 项

# #9 4 doc 扩内容数据准确性
grep -q "CACHE 50M" docs/architecture/DATA_PIPELINE.md
grep -q "ground-truth-lint" docs/architecture/AI_SAFETY_NET.md
grep -q "fixture→test 映射" docs/architecture/TEST_INFRASTRUCTURE.md  # 或等价表达
grep -q "L1 fallback" docs/operating/pre-commit.md

# #7 asset_* 概念边界
grep -q "asset_focus_service" docs/development/services.md
grep -q "asset_service" docs/development/services.md
test $(grep -c "^### " docs/development/services.md) -ge 5  # 至少 5 个 ### 子章节
```

### 引用完整性 (Stage 4 合并后)

```bash
# 跨 doc 引用无死链接
grep -r "LESSONS_LEARNED" docs/ | grep -v "LESSONS_LEARNED.md"  # 引用方列表
# 期望: CLAUDE.md 有 1 行引用, 其他 doc 0 行 (避免双向依赖)

# 内部引用一致
for f in docs/architecture/*.md docs/development/*.md docs/operating/*.md; do
  # 检查每个 .md 引用的其他 .md 文件存在
  grep -oE '\([a-z/-]+\.md\)' "$f" | sort -u | while read ref; do
    test -f "docs/${ref#(}" || echo "BROKEN: $f → ${ref}"
  done
done
```

---

## 关键风险与缓解

| 风险 | 缓解 |
|------|------|
| #10 LESSONS_LEARNED.md 写空话 (泛泛而谈无证据) | 模板强制要求"实战 sprint + commit SHA + 验证命令"三件套, Stage 3 review 验证 |
| #9 CACHE 50M ROW 数据陈旧/不准确 | 必须 Sprint 30.1 close memory + W4 batch INSERT 实战 commit 实证 |
| #9 fixture→test 映射表跟实际 test 不一致 | 跑 `pytest --collect-only` 拿真实 test list 填表 |
| #7 asset_* code snippet 引用错误 import path | Stage 3 review 必跑 `python3 -c "from backend.services.asset_service import get_asset_summary"` 验证 |
| Stage 4 三 worktree 合并冲突 (CLAUDE.md 同时被 #10 + #7 引用) | 合并顺序: #9 → #10 → #7, 每次合并后跑 `grep -r "BROKEN"` 检查 |
| Codex 越权跑 git commit/push | HANDOFF 明确约束 "Codex 只读 + 写文件, 不跑 git", Stage 3 review 检查 `git status` |

---

## Stage 2 Codex 启动指引

### 通用约束 (所有 HANDOFF 共享)

```text
1. 你只能 Read/Write/Edit 文档文件 (.md), 不跑 git 命令
2. 不修改 backend/ frontend/ scripts/ .githooks/ .github/ config 文件
3. 不修改 pytest / vite / spec-lint / ground-truth-lint 相关文件
4. 完成后通知 Claude (在 HANDOFF 文件末尾写 "Stage 2 完成" 段)
5. 等待 Stage 3 review 后才能算 sprint 收口
```

### 三个 HANDOFF 路径

| 项 | worktree | HANDOFF 路径 |
|-----|----------|--------------|
| #10 | wt-sprint57-01 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-01/HANDOFF-TO-CODEX-Sprint57-01.md` |
| #9 | wt-sprint57-02 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-02/HANDOFF-TO-CODEX-Sprint57-02.md` |
| #7 | wt-sprint57-03 | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics.wt-sprint57-03/HANDOFF-TO-CODEX-Sprint57-03.md` |

### 启动命令 (用户决策)

Claude 已写好 3 份 HANDOFF, 用户可以:
- (A) Claude 直接启动 Codex (用户说 "开始" 触发)
- (B) 用户手动 review HANDOFF 后启动 Codex
- (C) 用户先看 ARCHITECTURE + 3 份 HANDOFF 全览后再决策

---

## 估算

- **Stage 1 (本文档 + 3 份 HANDOFF)**: 已完成 (Claude, 30 min)
- **Stage 2 (Codex 3 worktree 并行)**: 1.5-2d
- **Stage 3 (Claude review + 修 bug)**: 1h
- **Stage 4 (commit + push + merge + STATUS/CHANGELOG)**: 1h
- **总 Sprint 57**: 2-3 天闭环

---

## 状态

**Stage 1 完成**: ARCHITECTURE-Sprint57.md + 3 份 HANDOFF 已写, 3 个 worktree 已创建, 待 Codex Stage 2 启动。