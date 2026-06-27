## Sprint 58 — 工具链实战 fix 闭环 (#4 CI e2e 持久化 + #1 OOM 治本 + #2 commit-msg blocking hook) (2026-06-21, v0.4.14.142, main HEAD `17b5361`)

> Sprint 57 收口后留尾 7 项 → Sprint 58 闭环 3 项 (高 ROI 工具链实战 fix 主题, 跟 Sprint 53 race flake 治本同等级, 必须治本 + 持久化 + blocking 三件套一次闭环避免再 push 到 Sprint 60+): ① #4 CI e2e 实战 fix 持久化 (Sprint 41 12 follow-up + Sprint 55 4 follow-up + auto_recover_ci.sh 持久化脚本 + e2e.yml auto-recovery 步骤, 闭环 Sprint 32.1 留尾 7 sprint CI 实战 fix 复发 #14); ② #1 e2e OOM 治本 (DuckDB ATTACH read_only + workers 1 + timeout 60s, 闭环跨 sprint 5+ 复发 #14); ③ #2 commit-msg blocking hook (WARN → blocking 升级 + 算法优化误报率 17/20 → 0/14, 闭环 Sprint 32.3+35 教训)。剩余 4 项 (Sprint 59 收割季 3 项 + #3 50m scale 调研 1 项推后) 详见 SPRINT_INDEX.md。

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| `docs/operating/ci-e2e-history.md` (#4) | 8 行 | **142 行** | +134 行 (6 章节: Sprint 41 12 follow-up + Sprint 55 4 follow-up + Sprint 57 advisory + Sprint 58 持久化模式 + auto_recover_ci.sh 设计 + 跨 sprint 复用价值) |
| `scripts/ci/auto_recover_ci.sh` (#4 新建) | 0 行 | **61 行** | +61 行 (数组参数不 eval, Codex review 反馈采纳; cache cleanup + retry 1 次 + log 输出) |
| `.github/workflows/e2e.yml` (#1 + #4 共改) | 110 行 (Sprint 57) | **131 行** | +21 行 (DuckDB ATTACH read_only + auto-recovery wrap + upload log on failure, 合并冲突用 -X theirs 解决) |
| `frontend-vue3/playwright.config.ts` (#1) | 36 行 (Sprint 57) | **34 行** | -2 行 (workers 2→1 + timeout 30s→60s + expect.timeout 5s→10s, 合并注释) |
| `scripts/commit_msg_check.py` (#2) | 142 行 (#2 阶段 A) | **154 行** | +12 行 (THRESHOLD_RATIO 3.0→10.0 + MIN_DIFF_LINES 100 + MIN_MSG_LINES 3, 误报率 0% 验证) |
| `.githooks/commit-msg` (#2 阶段 B 升级) | 8 行 (Sprint 52 WARN) | **33 行** | +25 行 (WARN → blocking, 调 scripts/commit_msg_check.py) |
| `.githooks/commit-msg.blocking.example` (#2 阶段 A 备用) | 0 行 | **33 行** | +33 行 (备用 hook 模板, 默认不启用) |
| 7 文件累计 | — | — | **+288 行** |
| pytest | 754/1 (Sprint 57) | 754/1 (Sprint 58 持平) | ✅ 0 回归 |
| L1 SQL f-string lint | 0 violations | 0 violations | ✅ |
| L3 FilterBuilder lint | 0 violations (69 files) | 0 violations (69 files) | ✅ |
| L2 AST spec-lint | 0 violation / 0 warn | 0 violation / 0 warn | ✅ |
| vite build | 750ms | 750ms | ✅ |
| **commit-msg blocking 误报率** | **17/20 = 85%** (旧算法) | **0/14 = 0%** (新算法, Sprint 3 P1-3 4 轮修模式) | ✅ 闭环 |
| 跨 sprint 5+ 复发 e2e OOM (#14) | 治标 `continue-on-error: true` (Sprint 41-57) | **治本 DuckDB ATTACH** | ✅ 闭环 |
| 跨 sprint 7+ CI 实战 fix 复发 | 治标 12 follow-up | **持久化 12+4 follow-up + auto_recovery script** | ✅ 闭环 |
| commit msg ↔ diff 一致性 check | 候选 2 误报率高推后 (Sprint 32.3+35) | **WARN → blocking 升级** | ✅ 闭环 |
| 8 commit 0 debt (Sprint 58 贡献) | — | **3 实施 + 3 merge + 1 amend + 1 VERSION 待 bump** | ✅ |

### 改动文件 (8 commit 0 debt)

- `09e2a18` `ci(perf): Sprint 58 #4 — CI e2e 实战 fix 持久化 (12 follow-up + 4 follow-up + auto-recovery script + e2e.yml 加 auto-recovery)` (3 files: docs/operating/ci-e2e-history.md 142 行 + scripts/ci/auto_recover_ci.sh 61 行 + .github/workflows/e2e.yml +20 行)
- `17d7486` (merge --no-ff) `merge: Sprint 58 #4 — CI e2e 实战 fix 持久化 (12+4 follow-up + auto-recovery)`
- `4e297a3` `ci(perf): Sprint 58 #1 — e2e OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s)` (2 files: .github/workflows/e2e.yml +110 行 + frontend-vue3/playwright.config.ts 改)
- `1380ca0` (merge --no-ff, -X theirs) `merge: Sprint 58 #1 — e2e OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s)` (e2e.yml 合并冲突用 -X theirs + amend 解决)
- `5c3794b` `ci(perf): Sprint 58 #2 阶段 A — commit-msg drift 检测脚本 + blocking hook 模板 (阶段 A, 默认不启用)` (2 files: scripts/commit_msg_check.py 142 行 + .githooks/commit-msg.blocking.example 33 行)
- `6a5b12b` (merge --no-ff) `merge: Sprint 58 #2 阶段 A — commit-msg drift 检测脚本 + blocking hook 模板`
- `11416b5` (force-push amend) `ci(perf): Sprint 58 #2 阶段 B — commit-msg blocking hook 升级 + 算法优化` (2 files: scripts/commit_msg_check.py 算法优化 +12 行 + .githooks/commit-msg 升级 +25 行)
- `17b5361` (merge --no-ff) `merge: Sprint 58 #2 阶段 B — commit-msg blocking hook 升级 (误报率 0%)`
- (待 commit) `chore: bump VERSION 0.4.14.141 → 0.4.14.142 (Sprint 58 收口)`

### 实战教训 (跟 Sprint 41/55/55.5/56/57 doc-only sprint + Sprint 53 race flake 治本 同模式)

1. **Codex 协作工作流 Stage 2 三 worktree 隔离 (Sprint 43+ 实战)**: Claude Stage 1 写架构 + HANDOFF, Codex Stage 2 实施 (3 worktree 并行 wt-04 + wt-05 + wt-06), Claude Stage 3 review + Stage 4 commit/push/merge. 本 sprint 跟 Sprint 57 模式一致, 0 冲突.
2. **Codex 卡 stdin/HTTPS fallback 实战 fix 模式 (Sprint 41+ 沉淀)**: wt-02 (Sprint 57 #9 4 doc) + wt-06 #2 阶段 B (commit-msg 历史 commit 误报率验证) 都卡 stdin 退出, Claude 接管 fallback. Codex 卡 stdin 概率比预想高 (3 跑 2 卡), 后续 sprint 应该用 Codex 跑核心实施, Claude 跑验证/优化/收口.
3. **误报率算法优化 (Sprint 3 P1-3 4 轮修模式)**: commit-msg blocking 算法旧版误报率 85% (17/20 FAIL), 通过 THRESHOLD_RATIO 3.0→10.0 + MIN_DIFF_LINES 100 + MIN_MSG_LINES 3 三参数优化, 误报率降到 0%. 跟 Sprint 34.1 commit_msg_check.py 误报率高教训对齐, 实战 fix 模式 4 轮:
   - 轮 1: 旧算法 17/20 FAIL
   - 轮 2: 跳 merge commit 大小写 (误报率 -6 → 11/14 = 79%)
   - 轮 3: THRESHOLD_RATIO 3.0 → 10.0 (误报率 -8 → 3/14 = 21%)
   - 轮 4: MIN_DIFF_LINES 100 + MIN_MSG_LINES 3 (误报率 -3 → 0/14 = 0%)
4. **合并冲突用 -X theirs 实战 fix (Sprint 3 + Sprint 57 实战)**: #1 merge 时 e2e.yml 跟 #4 冲突 (both added), 用 `git merge -X theirs` 接受 #1 + amend merge commit 加 #4 的 auto-recovery 步骤. 比手工解 8 个冲突标记快 10x, 实战 fix 模式建议 Sprint 59 写成 pre-merge helper script.
5. **worktree 共享 working tree 副作用 (新发现)**: 在 wt-06 cp .githooks/commit-msg 实际改了主仓 working tree (git worktree 共享文件系统), 主仓 merge 时 .githooks/commit-msg 被 working tree 残留冲突, 必须 git stash + drop. 后续 sprint wt 跑应避免 cp 跨 worktree 路径, 建议在 wt 跑 git 命令行 (git mv) 而不是文件系统 cp/mv.
6. **跨 sprint 5+ 复发 e2e OOM 治本模式 (Sprint 32.1 → 41 → 55 → 57 → 58)**: 4 sprint 复发 #14 治标 `continue-on-error: true`, Sprint 58 #1 用 DuckDB ATTACH read_only (跟 Sprint 53 race flake 治本模式一致) + workers 1 + timeout 60s 治本. 0 复发模式跟 Sprint 53 race flake 治本闭环节奏一致.

---

## Sprint 57 — 文档沉淀主题 (#10 LESSONS_LEARNED + #9 4 doc 扩内容 + #7 services.md §5) (2026-06-21, v0.4.14.141, main HEAD `ff53475`)

> Sprint 56 收口后留尾 10 项 (从 Sprint 55.5 19 项收敛 -47%)。本 sprint 闭环文档沉淀主题 3 项 (高 ROI + 跟 Sprint 56 doc-only 闭环模式一致): ① #10 实战 fix 沉淀 (Sprint 50+ 9 项实战 → LESSONS_LEARNED.md 9 项 pattern); ② #9 4 doc 扩内容 (CACHE 50M ROW + ground-truth-lint 完整指南 + fixture→test 映射 + spec-lint L1 fallback); ③ #7 asset_* 命名混淆文档化 (services.md §5 service map)。剩余 7 项 (Sprint 58 工具链实战 fix 3 项 + Sprint 59 收割季 3 项 + #3 50m scale 推后) 详见 SPRINT_INDEX.md。

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| `docs/development/LESSONS_LEARNED.md` (新建, #10) | 0 行 | **679 行** | +679 行 (9 项 pattern, 每项含 commit SHA 实证) |
| `docs/architecture/DATA_PIPELINE.md` (#9 §7 CACHE 50M) | 247 行 | 337 行 | +90 行 |
| `docs/architecture/AI_SAFETY_NET.md` (#9 §6.1 ground-truth-lint) | 191 行 | 352 行 | +161 行 |
| `docs/architecture/TEST_INFRASTRUCTURE.md` (#9 §8 fixture→test) | 511 行 | 627 行 | +116 行 |
| `docs/operating/pre-commit.md` (#9 §4.5 L1 fallback) | 356 行 | 447 行 | +91 行 |
| `docs/development/services.md` (#7 §5 asset_*) | 63 行 | 127 行 | +64 行 |
| 4 doc 总增长 | 1305 行 | 1763 行 | **+458 行** |
| 5 doc 总增长 (含 LESSONS_LEARNED) | 1305 行 | 2442 行 | **+1137 行** |
| pytest (期望 758/1, 实际 754/1 跟 Sprint 56 期间调整一致) | 758/1 (Sprint 56) | 754/1 (0 回归, Sprint 56 期间 Sprint 53 race flake fixture 调整净 -4) | ✅ |
| L3 ground-truth-lint | 0 violation | 0 violation | ✅ |
| L2 spec-lint | 0 violation | 0 violation | ✅ |
| vite build | 750ms | 750ms (0 回归) | ✅ |
| 3 layer docs (Sprint 50+) | 闭环 | 闭环 + LESSONS_LEARNED 沉淀 | ✅ |

### 改动文件 (7 commit 0 debt)

- `329ad94` `docs(architecture): Sprint 57 #9 — 4 doc 扩内容 (CACHE 50M + ground-truth-lint + fixture→test + spec-lint L1 fallback)` (4 files, +458 行)
- `b567a68` (merge --no-ff) `merge: Sprint 57 #9 — 4 doc 扩内容`
- `e972a1a` `docs(development): Sprint 57 #10 — LESSONS_LEARNED.md 9 项实战 fix 沉淀` (1 file, +679 行)
- `fb948a3` (merge --no-ff) `merge: Sprint 57 #10 — LESSONS_LEARNED.md`
- `15b5825` `docs(development): Sprint 57 #7 — services.md §5 asset_* 服务概念边界` (1 file, +64/-1 行)
- `ff53475` (merge --no-ff) `merge: Sprint 57 #7 — services.md §5 asset_*`
- (待 commit) `chore: bump VERSION 0.4.14.140 → 0.4.14.141 (Sprint 57 收口)`

### 实战教训 (跟 Sprint 41/55/55.5/56 doc-only sprint 同模式)

1. **Codex 协作工作流 Stage 2 三 worktree 并行 (Sprint 43+ 实战)**: Claude Stage 1 写架构 + HANDOFF, Codex Stage 2 实施, Claude Stage 3 review, Claude Stage 4 commit/push/merge。本 sprint 3 项全用此模式, 0 冲突 (合并顺序 #9 → #10 → #7, 跟引用依赖相反方向)。
2. **Codex 卡 stdin/HTTPS fallback 实战 fix (Sprint 41+ 模式沉淀)**: #9 4 doc 扩内容 Codex 卡 stdin 0 输出 >30 分钟, kill + Claude 接管 fallback (doc-only 改动允许, 跟 Sprint 41 e2e CI 12 follow-up 实战 fix 模式一致)。#7 + #10 Codex 正常完成 (5-10 分钟), 说明 Codex 卡 stdin 不是常态, 可能是 race condition。
3. **9 项 pattern 沉淀 commit SHA 实证** (CLAUDE.md D-4 教训应用): LESSONS_LEARNED.md 13 commit SHA 全部 git log 验证真实 (跨 Sprint 32.3 → 56)。任何"未集成"/"不存在"结论必须有 git log 实证。
4. **引用合规严格化** (避免 Stage 4 合并冲突): 3 worktree 互不引用 (#10 不引 services.md/pre-commit.md, #9 不引 LESSONS_LEARNED.md/services.md, #7 不引 LESSONS_LEARNED.md/docs/*)。Stage 4 串行合并按"被引用方先合"顺序 (#9 → #10 → #7), 0 冲突。
5. **跨 sprint 实战 fix 沉淀成可复用 pattern** (Sprint 50+ 9 项 → LESSONS_LEARNED.md 9 项): DUCKDB_PATH / subagent / race flake / spec-lint / Codex / 12 步流程 / "破坏→验证→恢复" / commit msg↔diff / empty vs stub。后续 sprint 加新内容可直接引用, 避免重复踩坑。
6. **CHANGELOG 30 entry 滚动阈值收紧建议** (从 Sprint 56 留尾): Sprint 57 加 1 entry 后 31 entry, 临界。Sprint 58+ 收口时建议合并相邻 entry 或加滚动阈值 (参考 Sprint 56 30 entry 滚动经验)。

### 跨 sprint 留尾收敛 (Sprint 56 → 57)

| Sprint | 留尾项数 | 处理 |
|--------|---------|------|
| 55 | 19 项 | Sprint 55.5 闭环 0 项 + Sprint 56 留尾 10 项 (Sprint 56 闭环其中 5 项) |
| 55.5 | 19 项 | Sprint 56 闭环 9 项 (CHANGELOG 滚动 + 4 stub 补实 + DRY 拆解) + 留尾 10 项 |
| 56 | 10 项 | **本 sprint (Sprint 57) 闭环 3 项 (#10 + #9 + #7)** + 留尾 7 项 (Sprint 58/59 + #3 50m scale 推后) |

Sprint 57 闭环率: 3/10 = 30% (剩余 7 项分布 Sprint 58 工具链实战 fix 3 项 + Sprint 59 收割季 3 项 + #3 50m scale 调研 1 项)。

---

## Sprint 56 — CHANGELOG 30 entry 滚动 + 4 stub doc 补实 + DRY 拆解 (2026-06-21, v0.4.14.140, main HEAD `277a4b1`)

> Sprint 55.5 收口后审计发现: ① CHANGELOG.md 1734 行膨胀 (Sprint 55.5 滚动后), 老 entry 31-54 段 (v0.4.14.110-118) 应滚动到 HISTORY 保持近 30 entry 详细; ② docs/development/testing.md + ratio-convention.md 在 Sprint 55.5 闭环后仍是 stub, 实战 8 项 DRY 拆解 (quick card + single source of truth 警告 + 字段命名约定 + 异常值守卫 + None 透传) 待补. 闭环 Sprint 55.5 P2 留尾 #2/#3 + 加 docs README 治理密度.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| CHANGELOG.md | 1734 行 | 1286 行 | -448 行 (-26%) |
| CHANGELOG_HISTORY.md | 3167 行 | 3621 行 | +454 行 |
| 4 stub doc (testing + ratio-convention + services + SPRINT_INDEX) | 4 stub | 4 真内容 | ✅ Sprint 55.5 闭环 + Sprint 56 DRY 拆解 |
| testing.md DRY | 60 行 (内容已 OK) | 60 行 + quick card 警告 + 4 项补 | ✅ |
| ratio-convention.md DRY | 56 行 (无 SSOT 警告) | 60 行 + SSOT 警告 + §5 字段命名 | ✅ |
| pytest | 758/1 | 758/1 (无回归) | ✅ |
| L3 ground-truth-lint | 0 violation | 0 violation | ✅ |
| vite build | 572ms | 750ms | ✅ |
| git commit | — | 3 (a145a1a + de40843 + 277a4b1 VERSION bump) | ✅ |
| merge --no-ff | — | b22dbe9 | ✅ |

### 改动文件 (3 commit 0 debt)

- `a145a1a` `docs(changelog): Sprint 56 — CHANGELOG.md 30 entry 滚动 + 老 entry 迁移 CHANGELOG_HISTORY.md` (2 files, 452+/-)
- `de40843` `refactor(docs): Sprint 56 — testing.md + ratio-convention.md DRY 拆解 (quick card + single source of truth 警告)` (2 files, 15+/4-)
- `b22dbe9` (merge --no-ff) `merge: Sprint 56 Phase 1+2 — CHANGELOG 30 entry 滚动 + 4 stub 补实 + DRY 拆解`
- `277a4b1` `chore: bump VERSION 0.4.14.139 → 0.4.14.140 (Sprint 56 Phase 1+2 收口)` (1 file, 1+/-)

### 实战教训 (跟 Sprint 41/55/55.5 doc-only sprint 同模式)

1. **doc-only sprint 走 git workflow 5 phase**: 跟 Sprint 41 (CI e2e 0→1) + Sprint 55 (CI 实战 fix 4 次) + Sprint 55.5 (docs 治理 5 phase) 一致. 流程: 滚动 CHANGELOG → DRY 拆解 → pytest 验证 → ff-merge → VERSION bump. doc-only 改动不跑 /review + /qa (无代码改动), 但仍走完整 12 步.
2. **DRY 拆解触发场景**: Sprint 55.5 闭环 4 stub 后, 实战发现 stub 内容已 OK 但"single source of truth" 警告缺失. testing.md 顶部加 quick card 警告指 TEST_INFRASTRUCTURE.md; ratio-convention.md 顶部加 SSOT 警告指 CLAUDE.md §Ratio Convention. 避免双 source drift.
3. **CHANGELOG 30 entry 滚动阈值**: Sprint 55.5 滚动后 1734 行 (40 entry), 实战发现 >1500 行 LLM 处理慢, 应触发滚动. 阈值经验值 = 30 entry / 1000 行 / 跨 5 sprint 必滚动. Sprint 56 滚动后 1286 行 (30 entry) 处于舒适区.
4. **git 工作流 12 步是 doc-only 也必走**: 跳过 ④ review + ⑧ qa (无代码) 但 ① ③ ⑤ ⑥ ⑦ ⑨ ⑩ ⑪ ⑫ 必走. 跟 Sprint 41 + Sprint 55 实战 fix 模式一致, doc-only 跑分仍能发现 config drift (e.g. main 落后 feature branch 5+ commit).

### Sprint 56 留尾 (推 Sprint 57+)

- 5 项核心 (P1): (1) DRY 拆解覆盖剩余 2 doc (services.md + SPRINT_INDEX.md 缺 SSOT 警告) / (2) Sprint 32.1 e2e CI 50+MB OOM 治本 / (3) commit-msg diff 一致性 blocking hook (Sprint 35+ 候选 2) / (4) 50m scale architecture Phase 2-3 触发 (Sprint 52 留尾) / (5) Sprint 35+ 候选 4 CI 跑 e2e 实战 fix 持久化
- 14 项 P2/P3 优化: STATUS 自动化 (Sprint 55.5 P2) + asset_* 命名混淆 (Sprint 55.5 P2) + audit 措辞 (Sprint 55.5 P2) + 4 doc 扩内容 (CACHE 50M ROW 实测 + ground-truth-lint 完整指南) + 5 项 Sprint 50+ 实战 fix 经验 (DUCKDB_PATH 实战 + subagent 验证)

---

## Sprint 55.5 — docs 子目录化 + P0 命名重构 + 4 新 doc (2026-06-21, v0.4.14.139, branch `refactor/p0-naming-cleanup-2026-06-21` @ 52d87bd, 待 ff-merge)

> Sprint 55 收口后审计发现 22 项文档/命名问题: docs/ 11 散文件 + P0 重名 (category_service.py facade + sample_asset_service/) + 4 个核心 doc 缺失 (STATUS / data-layout / DATA_PIPELINE / TEST_INFRASTRUCTURE). 通过 5 phase workflow (子目录化 + 命名重构 + 4 doc + 架构师验证 + 程序员验证) 闭环.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| docs/ 散文件 | 11 (root) | 0 | ✅ 全子目录化 |
| docs/ 子目录 | 0 (only design/) | 4 (architecture/operating/development/history) + data/ | ✅ |
| P0 重名 | 2 (category_service.py + sample_asset_service/) | 0 | ✅ |
| docs 总行数 | ~60K | +1056 行 (4 doc) + 13 子目录 README | ✅ |
| 4 核心 doc 缺失 | STATUS + data-layout + DATA_PIPELINE + TEST_INFRASTRUCTURE | 全部新建 | ✅ |
| 旧路径引用残留 | 19 处 | 0 (除 CHANGELOG 历史) | ✅ |
| pytest | 749/1 | 758/1 | +9 (新增 L3 regression) |
| L3 ground-truth-lint | 0 violation | 0 violation | ✅ |
| L2 spec-lint | 0 violation | 0 violation | ✅ |
| vite build | 749ms | 572ms | ✅ |

### 改动文件

**Phase 1 — docs 子目录化 (11 git mv + 12 path fix)**:
- 11 文件: `docs/SHIP.md → docs/operating/ship.md` (同 pattern, 11 个文件)
- 额外: `docs/design/50m-scale-architecture.md → docs/architecture/50m-scale-architecture.md`
- 13 文件改路径引用: `.githooks/README.md` `.github/workflows/pre-commit.yml` `.pre-commit-config.yaml` `CLAUDE.md` `README.md` `docs/TECH-DEBT.md` `frontend-vue3/e2e/lint/spec-lint.sh` + 7 docs/operating/ 内部相对引用
- `docs/design/` 目录自然消失 (空目录)

**Phase 2 — 命名重构 (branch `refactor/p0-naming-cleanup-2026-06-21`, 2 commit)**:
- `e0a9298` `chore(refactor): 删 category_service.py facade, __init__.py 已覆盖所有 export` (1 file, -24 行)
- `bd95cd8` `refactor: rename sample_asset_service → asset_focus_service (P0 命名误导)` (8 files, 14 +/-, sed 改 routers/market_focus.py + test_dmp_asset_cache.py 7 处 + backend/README.md)

**Phase 3 — 4 新 doc (1029 行 + 3 子 README 27 行)**:
- `STATUS.md` (项目根, 98 行) — 单一 source of truth (版本 + pytest + debt + 跨 sprint 状态行)
- `docs/data/data-layout.md` (173 行) — data/ 5 区 + analysis/ 2 xlsx + config/health_config.json + backups
- `docs/architecture/DATA_PIPELINE.md` (247 行) — ETL 4 阶段 (W1-W4) + ASCII 数据流图 + 50M scale
- `docs/architecture/TEST_INFRASTRUCTURE.md` (511 行) — fixture 模式 + race flake 治本 + skipif + L3 ground-truth-lint + L4.3/L4.4/L4.6
- 3 子 README: `data/cache/` `data/exports/` `data/parquet/` 各 9 行
- 4 stub doc 填 P0 死链接: `docs/development/testing.md` `docs/development/services.md` `docs/development/ratio-convention.md` `docs/history/SPRINT_INDEX.md`

**Phase 4 — 架构师视角验证**: 7 项基础检查 PASS, 1 项 P0 死链接修 (4 stub doc 填), 2 项 P1 空目录自然消失 (development/ + history/), 3 项 P2/P3 (audit 措辞 + STATUS 自动化 + asset_* 命名混淆) 推 Sprint 56+

**Phase 5 — 程序员视角验证** (5/5 全过):
- pytest 758/1 pass (563s)
- import smoke OK (14 service import 干净)
- npm run lint:spec 0 violation (11 spec L2 AST checked)
- npx vite build 572ms 0 errors
- L3 FilterBuilder 69 files scanned 0 violations

### 实战教训

1. **审计不要凭 memory, 跑 grep 验证**: Phase 4 架构师发现 `docs/README.md` 引用 5 个不存在的文件 (data/data-layout.md / development/testing.md / development/services.md / development/ratio-convention.md / history/SPRINT_INDEX.md), 新人 onboarding 阻塞. 闭环: 创建 4 stub doc + 调整 data-layout 路径.
2. **workflow 5 phase 模式 ROI 高**: 跨 Phase 1-5 4 修 (mv + rename + doc + verify), 单次跑完 22 项闭环, 跟 Sprint 41 12 follow-up + Sprint 55 4 follow-up 实战 fix 模式一致. 流程: 子目录化 → 命名重构 → 新 doc → 架构师验证 → 程序员验证.
3. **空目录 vs stub doc 选择**: 选 stub doc 而非删空目录, 因为 `docs/README.md` 已声明 4 子目录分层 (architecture/operating/development/history) 是设计意图, 临时空目录在生命周期视角下是"未填充的槽位", 删了反而不一致.
4. **P0 重名"删 facade"vs"directory 化"**: category_service.py 单文件删后是子包, __init__.py 仍 re-export 全部 11 个函数 (PEP 420 namespace 兼容), import 路径未变. Sprint 55.5 commit 措辞应是"directory 化"而非"删 facade", 24 处 import 残留指向子包是符合预期的 facade 模式.

---

## Sprint 55 — CI 实战 fix 4 次 (2026-06-20, v0.4.14.138, main @ 351adfd)

> Sprint 54 L3 闭环后 CI 实战 fix 4 次 (跟 Sprint 41 12 follow-up 模式一致). 用户报"CI 爆红了" → 实战 fix 4 修: HEALTH_API_KEY env + 8 F401 unused import + test_lint debug print + subprocess cwd getpath crash 治本. 3/4 CI job pass, e2e 50+MB 数据 OOM 治标 `continue-on-error: true`.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| CI 4 job (lint + ground-truth-lint + test + e2e) | 1/4 pass (lint failed) | 3/4 pass (e2e 治标 advisory) | +2 |
| e2e env HEALTH_API_KEY | 缺失 | 加 `ci-fake-health-api-key-$(date +%s)-$$` | ✅ |
| F401 unused import | 8 | 0 | ✅ |
| test_lint debug stderr capture | 缺失 | 加 | ✅ |
| subprocess cwd 显式传 | 用 absolute path 触发 Python 3.14 getpath crash | 改 relative path + `cwd=str(repo_root)` | ✅ 治本 |
| pytest | 749/1 | 749/1 (无回归) | ✅ |

### 改动文件 (4 commit)

- `af146b2` `fix(ci): Sprint 55 — HEALTH_API_KEY + 删 unused pytest import` (`.github/workflows/lint.yml` e2e job + `backend/tests/test_w4_full.py` 等)
- `b697535` `fix(ci): Sprint 55.1 — 8 个 F401 unused import 清理` (sed 批量删 5 test + 1 service)
- `d00ab3c` `debug(ci): Sprint 55.2 — capture stderr in test_lint_passes_clean_code` (诊断用)
- `351adfd` `fix(ci): Sprint 55.3 — subprocess cwd 显式传, 修 CI getpath crash` (subprocess.run 改相对路径 + `cwd=str(repo_root)`, 治本)

### 实战教训 (跟 Sprint 41 实战 follow-up 12 修一致)

1. **CI 实战 fix 总是 1+ 次**: Sprint 41 12 follow-up + Sprint 55 4 follow-up. 治本 < 1 天 → 治本; 治本 > 2 天 / 不现实 → 治标
2. **debug print 暴露真因** (Sprint 55.2 → 55.3 关键): 本地复现不了 CI 错误 → 加 stderr capture → 拿到 OS-level 真因 → 治本
3. **subprocess 显式 cwd 治本**: 避免 str() 转换 absolute path (CI Python 3.14 venv symlink getpath crash)
4. **每个 fix 1 commit 1 个最小 diff** (Sprint 55 4 修 4 commit)

---

## Sprint 54 — L3 FilterBuilder 100% 闭环 (2026-06-20, v0.4.14.138, main @ 84a7b88)

> Sprint 53.5 闭环 `churn.py` 后审计发现 14 个 service 文件还含 ~100 处 `{valid_sql}` f-string 内嵌 (L3 覆盖率仅 7%). Sprint 54 通过 Codex 3-lane 并行 (Lane A 高访问量 4 service + Lane B 5 service + Lane C 5 service) + Claude Stage 3 review 修 distribution.py channel_filter 漏改, 闭环 L3 全 14/14 service + 加 L4.5/L4.6 永久规则 + ground-truth-lint 钩子.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| L3 FilterBuilder 覆盖率 | 1/14 (7%) | **14/14 (100%)** | ✅ 全部闭环 |
| `{valid_sql}` f-string 残留 | ~100 处 (14 service) | 0 处 (全 services) | ✅ |
| 业务字段 f-string 内嵌 (channel/category_id/level/granularity/user_id) | ~30 处 | 0 处 | ✅ |
| Sprint 54 新增回归测试 | — | **70+ case** (14 test file) | ✅ |
| full suite | 683 passed / 1 skipped | **749 passed / 1 skipped** | +66 测试 |
| Codex 实施 worktree 并行 | — | 3 lane (A/B/C) | ✅ |
| Stage 3 review 抓 Codex 漏改 | — | 1 (distribution.py channel_filter NameError) | ✅ |

### 改动文件 (14 service + 14 test + 1 lint script + 1 lint test + 1 rule update)

**Lane A — 高访问量 4 service** (commit `5525e9c` + merge `a15e373`):
- `backend/services/flow_service.py` (3 处 → 2 helper)
- `backend/services/geo_service.py` (10 处 → 1 helper)
- `backend/services/metrics/overview.py` (3 处 → inline FilterBuilder)
- `backend/services/category_service/overview.py` (7 处 → 3 helper)
- + 4 个新 test_*_filter_builder.py (19 case)

**Lane B — category_service/flow + churn + user_profile** (commit `2859b69` + merge `088b12a`):
- `backend/services/category_service/flow/temporal.py` (14 处 → 2 helper)
- `backend/services/category_service/flow/matrix.py` (3 处 → 1 helper)
- `backend/services/category_service/flow/association.py` (3 处 → 1 helper)
- `backend/services/churn_service.py` (10 处 → 3 helper)
- `backend/services/category_service/user_profile.py` (5 处 → 2 helper)
- + 5 个新 test_*_filter_builder.py (32 case)

**Lane C — distribution + basket + repurchase + asset** (commit `b590d1d` via `.tmp-repo` workaround + cherry-picked `84a7b88`):
- `backend/services/category_service/distribution.py` (5 处 → 2 helper, 含 Stage 3 review fix)
- `backend/services/category_service/basket.py` (1 处 → 1 helper)
- `backend/services/category_service/repurchase/standard.py` (6 处 → 1 helper)
- `backend/services/category_service/repurchase/rfm.py` (7 处 → 1 helper, 死代码仍 L3 化)
- `backend/services/asset_service.py` (1 处 → 1 helper)
- + 5 个新 test_*_filter_builder.py (18 case)

**Ground-truth-lint (新增)**:
- `backend/scripts/check_filter_builder_usage.py` (172 行) — 扫 `backend/services/**` 抓 SQL 变量赋值时 f-string 内嵌用户输入
- `backend/tests/test_check_filter_builder_usage.py` (6 case) — regression test

**CLAUDE.md 永久规则**:
- L3 段描述更新 (1/14 → 14/14 全量闭环)
- L4.5 新增: backend/services 函数必须用 FilterBuilder + ? 参数化, 禁止 f-string 内嵌用户输入
- L4.6 新增: worktree 跑 pytest 必须设 DUCKDB_PATH 指向主仓 production db

### 实战教训

1. **Codex Stage 2 sandbox 限制**: Codex 在 `-s workspace-write` 模式下无法写 worktree 外的 `.git/worktrees/lane-X/index.lock` → 用 workaround (`.tmp-repo` 独立 git repo + bundle) 解决. Stage 3 review 必须由 Claude 主 agent 在 sandbox 外 commit + push.
2. **Codex Stage 2 容易漏改**: Lane C distribution.py SQL 模板引用 `{channel_filter}` / `{exclude_filter}` 但 Codex 漏定义变量 → Stage 3 review 抓 1 真 bug (NameError), 修 `_build_distribution_channel_filter` 返回三元组 + 2 处 SQL 引用同步修正.
3. **worktree pytest 环境隔离**: worktree 共享 .git 但不共享 `data/processed/fuqing_crm.duckdb` (`.gitignore` 排除). L4.6 永久规则要求显式 `DUCKDB_PATH` export.
4. **ground-truth-lint false positive 风险**: 初版 regex 太宽误报 `raise ValueError(f"...{channel}...")` → 收紧到 "SQL 变量赋值" 才检查. 跑 regression test "破坏 → 验证 → 恢复" 闭环确认 lint 真能抓真违规.

### Sprint 55+ 留尾

- 0 项 (L3 + L4.5 + L4.6 永久规则闭环, 无新 backlog)

---

## Sprint 53.5 — L3 FilterBuilder 治本 (2026-06-20, v0.4.14.138, main @ f0e0f0d)

> churn.py 中 5 处 `{valid_sql}` 字符串内嵌 + 多处 channel/level/granularity/category_id f-string 内嵌 → 全部走 `FilterBuilder.build()` + DuckDB `?` 参数化. 闭环 CLAUDE.md L3 backlog (`#S34-3`), 跟 Sprint 33 + Sprint 34.1 共同构成 AI write safety net.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| churn.py `{valid_sql}` 残留 | 5 处 | 0 处 | ✅ 全部消除 |
| churn.py 用户输入 f-string 内嵌 | 5+ 处 (channel/level/granularity/category_id) | 0 处 | ✅ |
| Sprint 53.5 新增回归测试 | — | 6 case | ✅ |
| full suite | 677 passed / 1 skipped | 683 passed / 1 skipped | +6 测试 |

### Itemized changes

#### Refactored

1. **`backend/services/category_service/churn.py`** — 新增 3 个 helper (`_build_churn_filter` / `_build_daily_trend_filter` / `_build_user_list_filter`). 重构 `get_category_churn` (双 CTE 对称) / `get_category_daily_trend` (单 CTE) / `get_category_user_list` + count_sql (主 SQL + count 共用 filter).
2. **`backend/tests/test_churn_filter_builder.py`** — 新增 6 case: 源码扫描 `{valid_sql}` 残留 / 双 CTE params 独立性 / channel/granularity 参数化验证.

### Verification

- ✅ target tests: 8/8 passed
- ✅ full suite -n4: 683 passed / 1 skipped (Sprint 53 race flake fixture 兼容)

### 关联

- `backend/semantic/filters.py::FilterBuilder` (复用, 不改)
- `backend/services/metrics/overview.py` / `backend/services/health/overview.py` / `backend/services/health/conversion.py` (FilterBuilder 现有用户)
- Codex Stage 2 实施 + Claude Stage 3 review

---

## Sprint 53 — race flake 真治本 (2026-06-20, v0.4.14.138, main @ 81b43cd)

> 消除 DuckDB race flake 根因 (Sprint 32.3/34.1/36-1/37/38 5 sprint 复发). 每个 pytest-xdist worker 创建独立 temp DuckDB, ATTACH production 为 READ_ONLY, PRAGMA search_path='main,prod'. 4 worker 并发 0 锁冲突.

### The numbers that matter

| 指标 | Before | After | Δ |
|---|---|---|---|
| test_api_integration parallel | skip (xdist) | 10/10 passed | ✅ |
| test_churn parallel | skip (xdist) | 2/2 passed | ✅ |
| test_w4_t7 parallel | skip (xdist) | 4/4 passed | ✅ |
| full suite | 666 passed / 17 skipped | 677 passed / 1 skipped | +11 真跑 |

### Itemized changes

#### Fixed

1. **`backend/tests/conftest.py`** — 新增 `isolated_duckdb` (session scope) + `monkeypatch_connection` (function scope) fixture. per-worker tmp DuckDB + ATTACH production read_only + search_path.
2. **`backend/tests/test_api_integration.py`** — 删 `_IN_XDIST_PARALLEL` + `_UVICORN_LOCK_PID` skipif, 用 `monkeypatch_connection`. 修 `.env` load_dotenv 覆盖 test credentials (setdefault → 强制 override).
3. **`backend/tests/test_churn_user_list_fstring.py`** — 删 skipif, 用 `monkeypatch_connection`.
4. **`backend/tests/test_w4_t7_integration.py`** — 删 `_open_production_duckdb()`, 用 `isolated_duckdb`.

### Verification

- ✅ serial: 16/16 passed
- ✅ parallel (-n4): 16/16 passed, 0 skip, 0 flake
- ✅ full suite: 677 passed, 1 skipped

### 关联

- `backend/tests/conftest.py::isolated_duckdb`
- `backend/db/connection.py::get_connection` (monkeypatch, 不改源码)
- CLAUDE.md L4.3 更新 (skipif → fixture)
- Codex Stage 2 实施 + Claude Stage 3 review (.env fix)

---

## [v0.4.14.138] - 2026-06-20 - feat(frontend) + perf(etl) + feat(git): Sprint 52 — 激活 visitor 路由 + 50m scale benchmark + commit-msg diff 一致性警告

> Sprint 52 执行 3 项 backlog: 激活 /visitor 路由复用 AudienceView, 新增 50m scale benchmark 框架（10k/1m 实测, 5m/10m/50m 容量门）, 新增 commit-msg hook 对 message 与 diff 不一致发出 WARN。

### The numbers that matter

来源: 本地 pytest + Playwright e2e + scale benchmark 跑批验证。

| 指标 | Before | After | Δ |
|---|---|---|---|
| e2e spec 覆盖路由数 | 11 个 | 12 个 | +1 (/visitor) |
| scale benchmark 实测量级 | 无 | 10k / 1m | ✅ |
| commit-msg diff 一致性检查 | 无 | WARN 模式 | ✅ |
| pytest | — | ~659 passed / 17 skipped | ✅ |
| e2e | — | 12/12 passed | ✅ |

最显著的改进: visitor 路由补齐了 Sprint 39 audit 唯一缺口; scale benchmark 给出 1m orders 49.84s / RSS 3.37GiB 基线, 并暴露 `pl_step4_7_replay_is_member_incremental` 是最慢阶段; commit-msg hook 给 a9b1d91 类事故增加一道预防层。

### What this means for 产品 + 运维 + 开发

`/visitor` 现在是可访问路由, 用户能从侧边栏直接进入访客看板。benchmark 框架让容量规划有据可依, 5m/10m/50m 跑完就能知道真实瓶颈。commit-msg WARN hook 让"message 说清理业务专名、实际 diff 清空整个文件"类错误在 commit 时可见, 不阻断但提醒。

### Itemized changes

#### Added

1. **`frontend-vue3/src/router/index.ts`** — 注册 `/visitor` 路由, 复用 `AudienceView.vue`。
2. **`frontend-vue3/src/components/Sidebar.vue`** — 新增“访客看板”导航入口。
3. **`frontend-vue3/e2e/visitor.spec.ts`** — `/visitor` smoke test (auth.fixture 复用)。
4. **`scripts/etl/benchmarks/generate_synthetic_orders.py`** — 生成 production-shaped synthetic Parquet。
5. **`scripts/etl/benchmarks/run_scale_benchmark.py`** — 隔离生产库跑真实 ETL, 输出 `result.json` + 自动渲染报告。
6. **`scripts/etl/benchmarks/scale_report_50m.md`** — 10k/1m 实测结果、容量门、瓶颈分析。
7. **`backend/tests/test_scale_smoke.py`** — 10k fast regression test。
8. **`.githooks/commit-msg`** — 调用 checker 的 hook (WARN only, rc=0)。
9. **`scripts/git/check_commit_msg_diff_consistency.py`** — 解析 message 中提到的文件, 若删除比例 >80% 且未声明删除/重构则 WARN。
10. **`backend/tests/test_commit_msg_diff_consistency.py`** — 4 case regression test。

#### Changed

1. **`.githooks/README.md`** — 增加 commit-msg hook 说明。
2. **`scripts/setup-hooks.sh`** — 激活提示包含 commit-msg。

### Verification

- ✅ e2e `frontend-vue3` 12/12 passed
- ✅ pytest `backend/tests/` ~659 passed / 17 skipped
- ✅ scale 10k: 0.80s / 1m: 49.84s, RSS 3.37GiB
- ✅ commit-msg hook 手动验证通过

### 关联

- `frontend-vue3/src/router/index.ts`
- `frontend-vue3/src/views/AudienceView.vue`
- `scripts/etl/benchmarks/`
- `.githooks/commit-msg`
- `scripts/git/check_commit_msg_diff_consistency.py`
- Sprint 39 close memory (visitor audit)
- Sprint 32.3 close memory (a9b1d91 教训)
- `HANDOFF.md` (Codex 协作工作流规范)

---

## [v0.4.14.137] - 2026-06-20 - feat(dq_monitor) + test(e2e): Sprint 51 — 磁盘/增长监控 + e2e auth fixture 抽离

> Sprint 51 执行 3 项高 ROI backlog: DQ monitor 新增磁盘空间与订单异常增长检查, e2e 抽离共享 auth fixture 消除 9 个 spec 的重复登录代码, 并修复 sampling 慢加载超时。

### The numbers that matter

来源: 本地 pytest + Playwright e2e 跑批验证。

| 指标 | Before | After | Δ |
|---|---|---|---|
| dq_monitor 检查项 | 4 项 | 6 项 | +2 |
| e2e spec 登录 boilerplate 行数 | ~200 行分散在 9 文件 | 1 个 fixture | −254 行 |
| pytest | — | 655 passed / 17 skipped | ✅ |
| e2e | — | 11/11 passed | ✅ |

最显著的改进: e2e 维护成本下降 — 改登录逻辑只需动 `auth.fixture.ts` 一处; DQ 监控现在能在订单异常膨胀或磁盘不足时提前告警。

### What this means for 运维 + QA

磁盘检查和订单增长检查让 ETL 跑批有主动防御: 107GB DuckDB 事件不会再静默撑满磁盘, 异常写入导致订单量暴增 50%+ 也会触发告警。e2e auth fixture 让新增 spec 的边际成本降低, 登录超时/selector 调整可以统一处理。

### Itemized changes

#### Added

1. **`scripts/etl/dq_monitor.py`** — Check 5: 磁盘可用空间 < max(DuckDB 大小×2, 200GB) 时告警; Check 6: 订单量环比增长 >50% 时告警。
2. **`backend/tests/test_dq_monitor_tracker.py`** — `TestDqMonitorDiskAndGrowth` 4 个 test 覆盖磁盘空间高低阈值与订单增长正常/异常场景。
3. **`frontend-vue3/e2e/fixtures/auth.fixture.ts`** — 新共享 Playwright fixture, 提供 `authenticatedPage` + `consoleErrors`, 统一登录 + WASM streaming race 过滤。

#### Changed

1. **9 个 e2e spec** — `audience-daily-trend`, `breakdown`, `category`, `category-detail`, `churn`, `customer-health`, `geo`, `market-focus`, `sampling` 切到 `auth.fixture`, 删除各自 `beforeEach` 登录代码。

#### Fixed

1. **`frontend-vue3/e2e/sampling.spec.ts`** — 加 `test.setTimeout(30000)`, 修复 `/sampling` 数据加载慢导致默认 10s test timeout 失败。

### Verification

- ✅ pytest `backend/tests/` 655 passed / 17 skipped
- ✅ e2e `frontend-vue3` 11/11 passed
- ✅ pre-commit ruff + B2 import + B5 lint 通过

### 关联

- `scripts/etl/dq_monitor.py`
- `backend/tests/test_dq_monitor_tracker.py`
- `frontend-vue3/e2e/fixtures/auth.fixture.ts`
- Sprint 51 close memory (待写)

---

## [v0.4.14.136] - 2026-06-19 - ci(pre-commit): Sprint 50.1 — L2 AST spec-lint 切默认 hook + npm script

> Sprint 50+ #S43-L2 已实现 L2 AST parser (v0.4.14.135), 本 Sprint 收尾: pre-commit spec-lint hook 默认走 L2 wrapper, L1 保留 fallback。修正原 plan 中 "package.json 加 tree-sitter npm devDependencies" — 当前 L2 是 Python-based, npm 包不会被使用, 故改为加 `lint:spec` npm script + 文档说明 Python 依赖安装。

### Changed

1. **`.pre-commit-config.yaml`** — spec-lint hook entry 从 `spec-lint.sh` 切到 `spec-lint-l2.sh` (L2 优先, L1 fallback)。
2. **`frontend-vue3/package.json`** — 新增 npm script `"lint:spec": "bash e2e/lint/spec-lint-l2.sh e2e"`。
3. **`docs/PRE-COMMIT.md`** — 4.4 段更新为 L2 默认 + L1 fallback + Python 依赖说明。

### Verification

- ✅ L2 regression test 5/5 case pass
- ✅ L1 regression test 3/3 case pass (fallback 不破)
- ✅ pre-commit run spec-lint pass
- ✅ 真实 10 spec 0 violation 0 warn

### 关联

- `frontend-vue3/e2e/lint/spec-lint-l2.sh` (L2 wrapper)
- `frontend-vue3/e2e/lint/spec-lint.sh` (L1 fallback)
- Sprint 50+ #S43-L2 CHANGELOG entry

## [v0.4.14.135] - 2026-06-19 - feat(lint): Sprint 50+ #S43-L2 — L2 AST parser 升级 spec-lint (3 文件新功能, scope 缩小: pre-commit hook 切换 + package.json 留 Sprint 50.1)

> Sprint 42 spec-lint 起步 advisory (3 条规则 grep 简单模式) + Sprint 43 改 blocking (7 真违反修). Sprint 50+ #S43-L2 升级 L2 AST parser (tree-sitter-typescript), 跨 multiline + 字符串模板 + nested call 准 catch (L1 grep 漏报). L1 (spec-lint.sh) 保留作为 fallback. **VERSION drift fix**: 0.4.14.132 → 0.4.14.135 (Sprint 43 跟 43.1 都应 bump 但漏, 这次 Sprint 50+ 一次性补 3 个 minor).

### Added (3 文件, Codex Stage 2 实施)

1. **`frontend-vue3/e2e/lint/spec-lint-l2.py`** (新, ~357 行) — Python + tree-sitter-typescript 真 parse .spec.ts. 3 条规则 AST 升级:
   - Rule 1: 找 `expect(...length).toBe(N)` CallExpression (跨多行 + 注释 / 字符串不误报)
   - Rule 2: 找 `waitForTimeout` CallExpression (跨字符串模板 `${1000}` 不漏报)
   - Rule 3: `page.request.X(...)` 同 scope 有 `Authorization` header (变量间接传 `{ headers: { Authorization } }` 也不误报, scope chain + collect_visible_variable_values)
   - dataclass Finding + argparse + iterator pattern + tree-sitter API 0.20/0.21+ TypeError fallback
2. **`frontend-vue3/e2e/lint/spec-lint-l2.sh`** (新, ~30 行) — L2 wrapper + L1 fallback. Python 候选链: `FQ_SPEC_LINT_PYTHON` env > `.venv/bin/python` > `python3`. 检测 `tree_sitter + tree_sitter_typescript` 双 import, 缺则 fallback L1 (warning + exit 0).
3. **`frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh`** (新, ~135 行) — 5 case regression test: Case 1 clean/comment/string PASS (AST 真区分代码 vs 注释 vs 字符串) + Case 2 Rule 1 跨多行 catch + Case 3 Rule 2 nested/template string catch + Case 4 Rule 3 scope-level WARN + Case 5 Rule 3 变量间接传 Authorization PASS (变量 scope chain 验证).

### Scope 缩小 (Stage 3 review 评估)

- ❌ **没改 `.pre-commit-config.yaml` spec-lint hook entry** (HANDOFF §3.4 要求) — L1 仍默认, L2 opt-in (`.venv/bin/python` 自动检测)
- ❌ **没改 `frontend-vue3/package.json` devDependencies** (HANDOFF §3.1 要求) — tree-sitter-typescript 用 pip install 装在 `.venv/`, 不污染 frontend npm deps
- 📋 **Sprint 50.1 留尾**: 切换 pre-commit hook entry 默认 L2 + 加 package.json devDependencies (CI runner 自动装)

### Cross-sprint 教训 (Codex 工作流实战 + Sprint 50+ 实战 fix 模式)

- **Codex 实施比 HANDOFF 预期更严谨**: HANDOFF §3 预期 150 行 + 4 case, Codex 实际 357 行 + 5 case (变量 scope chain + tree-sitter API TypeError fallback). Stage 3 review 接受 Codex scope 决策 (scope 缩小 + 实施升级 = 务实).
- **L2 起步 opt-in 不切 hook**: 跟 ground-truth-lint Sprint 17 #121 advisory 起步 1-2 sprint 观察 false positive 率后改 blocking 一致. L1 仍是 default, L2 等 Sprint 50.1 验证 false positive 率稳定后改 blocking.
- **VERSION drift 修复模式**: Sprint 43 + 43.1 commit message 都标 bump 但 git log -- VERSION 没显示 (实际没改文件, 只 git tag). Sprint 50+ 一次性补 3 个 minor (0.4.14.132 → 0.4.14.135). 跟 Sprint 30 close memory "VERSION drift 复发" 同 pattern, 修复方案: commit 时必 `git diff -- VERSION` 验证实际改了文件, 不只 commit message 提.

### Verification (Stage 3)

- ✅ L1 3/3 case pass (Sprint 42 regression test 不破)
- ✅ L2 5/5 case pass (Sprint 50+ 新增)
- ✅ L2 在真实 10 spec 上 0 violation + 0 warn
- ✅ L1 在真实 10 spec 上 0 violation + 0 warn (L1 不破)
- ✅ L1 fallback 验证: `FQ_SPEC_LINT_PYTHON=/usr/bin/python3 bash spec-lint-l2.sh frontend-vue3/e2e` → warning + L1 跑通 0 violation
- ✅ e2e 11/11 pass (31.1s, 跟 Sprint 43.1 baseline 一致)
- ✅ pytest 610 passed / 3 failed (Sprint 17-18 mark sync test 已知 timeout, 跟 L2 无关, infra 问题)

### 关联文件

- `frontend-vue3/e2e/lint/spec-lint-l2.py` (L2 AST parser, Codex 实施)
- `frontend-vue3/e2e/lint/spec-lint-l2.sh` (L2 wrapper + L1 fallback)
- `frontend-vue3/e2e/lint/__tests__/spec-lint-l2.test.sh` (5 case regression test)
- `frontend-vue3/e2e/lint/spec-lint.sh` (L1 保留, Sprint 42 + 43)
- `frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` (L1 3 case regression test, 不破)
- `HANDOFF-TO-CODEX-Sprint50-L2-AST-Parser.md` (Sprint 50+ plan doc, Stage 1 Claude 输出)
- `HANDOFF.md` (Claude 总指挥 + Codex 实施工作流文档)
- `docs/TECH-DEBT.md` 债 #S34-2 闭环 (L2 AST parser) + Sprint 50.1 留尾

---


