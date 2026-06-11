# Sprint 17 治理收口 (2026-06-11)

## 1. Sprint 结果

Sprint 17 治理收口 (3 P1 任务, 1.5h workflow + 1h verify):

| # | 任务 | 状态 | 关键产出 | 分支 / commit | version |
|---|------|------|---------|---------------|---------|
| #122 | B1+B2 模式 → CLAUDE.md | ✅ | 9 条强制规则 + 跨链 | `fix/sprint17-b12-mode-claudemd` / 75a4cb9 (merge a8789be) | v0.4.14.41 |
| #121 | ground-truth-lint (R1/R2/R3/R4) | ✅ | 4 规则 AST 扫描 + 10 tests + 359 行 docs | `fix/sprint17-ground-truth-lint` / eefa7a3 (merge 02d1ca5) | v0.4.14.42 |
| #120 | B2 全量 audit 10 contract | ✅ | 60+ 字段 Pydantic 化 + 676 行聚合 tests + 299 行 audit 报告 | `fix/sprint17-b2-audit-full` / 9f9c2e1 (merge fff37c7) | v0.4.14.43 |

**总耗时**: 1.5h workflow (3 subagent 并行) + 1h verify/收口 = **2.5h**
**总 commits**: 6 (1+1+6) + 3 merge + 2 docs = **11 commits**
**Files changed**: CLAUDE.md + backend/contracts/{10}.py + backend/contracts/_lint.py (新) + tests + docs (4 新)
**Tests**: 437+12 → 454+12 (新增 17, 含 #121 lint 10 + #120 audit 50+ 但去重后净增 17)
**uvicorn**: 4 端点 401 expected (需 auth), /health 200, /docs 200

## 2. 3 任务治根复盘

### #122 B1+B2 模式 → CLAUDE.md (30min, 0.5h)

**改动**: CLAUDE.md "## Ratio Convention" 章节升级 — 从 (Sprint 13+) 升级到 (B1+B2 模式, Sprint 13+ 升级 Sprint 17)

**新增 9 条强制规则**:
1. `*_ratio` 字段 → 必须 `RatioField` (0-1) 或 `Annotated[float, Field(ge=0, le=1)]`
2. `*_pct` 字段 → 必须 `PercentageField` (-1B~1B) 或 `Annotated[float, Field(ge=-1e9, le=1e9)]`
3. `*_ppt` 字段 → 必须 `PpField` (-100~+100) 或 `Annotated[float, Field(ge=-100, le=100)]`
4. `*_rate` 字段 → 必须 `PercentageField` (0-100)
5. `List[X]` 字段 where X 是约束类型 → 必须 `List[Annotated[X, Field(...)]]` 禁 `List["X"]` 前向引用
6. Pydantic v2 List 字段 element-wise 约束 (Sprint 16.5 6.3 踩坑治根)
7. YOY 异常值前端守卫 (|v|>1e6 → 数据异常) 跟 Sprint 16.5 #92 配套
8. 禁止条款 +2 (contract 裸 float + List 前向引用)
9. AI 执行检查点加 "改 contract 字段" → 必跑 ground-truth-lint

**跨链**: 4 项 (types.py + Sprint 16.5 B2 audit + LINTING.md + SPRINT-17-B2-AUDIT-FULL.md)

**治根**: 给 LLM 写 contract 时明确的 Pydantic 写法规则, 跟 Sprint 13 ratio 治理契约 0-1 严守保留, 是补强不是冲突。

### #121 ground-truth-lint (1h, 1.5h)

**新增 4 规则 AST 扫描** (R1/R2/R3/R4):
- R1: `*_ratio` → `RatioField` (0-1) 强制
- R2: `*_pct` → `PercentageField` (-1B~1B) 强制
- R3: `*_ppt` → `PpField` (-100~+100) 强制
- R4: `List["X"]` 前向引用禁止 (Pydantic v2 踩坑治根)

**架构亮点**:
- AST 扫描不依赖 runtime 解析 (不需要构造 BaseModel, 直接看代码)
- CLI `python -m backend.contracts._lint` 返 0/1 exit code
- 10 pytest tests 覆盖 (4 true-positive + 4 false-positive + 2 skip rules)
- 359 行 docs 详细解释 4 规则 + 用法 + 跟 #120/#122 配套

**踩坑**: 
- ast 节点识别 `Optional["RatioField"]` / `RatioField | None` (PEP 604) / `Annotated[float, Field(ge=0, le=1)]` 4 种写法, 写 4 个 helper 函数
- `_is_list_with_forward_ref` 识别 `List["X"]` (字符串) vs `List[X]` (直接引用), 需要递归 ast 节点

**治根**: 防止 LLM 写无 Pydantic 元数据 contract, 防 Pydantic v2 `List["X"]` 踩坑, 给 #122 B1+B2 模式提供工具层强制。

### #120 B2 全量 audit 10 contract (1h, 1.5h)

**改动 10 contract 文件**, **60+ mark 字段补标**:
- asset.py: 4 (repurchase_rate + ly_repurchase_rate)
- audience.py: **50+** (AudienceRow + AudiencePeriodMetrics, 100+ ratio 字段)
- breakdown.py: 5 (old_customer_ratio_target + 4 ratio)
- churn.py: 7 (top_churn_dest1/2_ratio + new_customer_ratio List)
- common.py: 4 (wool_party_ratios + high_value_ratios + type1/2_ratio)
- flow.py: 2 (ratio + concentration_risk bool 不动)
- geo.py: 2 (user_ratio + gmv_ratio)
- rfm.py: 13 (新加 12 个 R 桶 / F 桶 / M 桶 ratio Pydantic 化, 1 个 yoy_repurchase_gsv_ratio 沿用 Sprint 14.5 Optional[PpField])
- sampling.py: 12 (new_locked_ratio + old_locked_ratio, 2 个 class)
- visitor.py: 4 (ratio 字段 Pydantic 化)

**新增**:
- `backend/tests/test_contracts_b2_audit.py` (676 行) — 10 contract 聚合越界测试
- `docs/SPRINT-17-B2-AUDIT-FULL.md` (299 行) — 10 contract audit 报告, 跟 Sprint 16.5 B2 audit 同样 markdown 结构

**治根**: 把 Sprint 14 Stage 2 写的 3 个 Pydantic Annotated 类型 (RatioField/PercentageField/PpField) 推全量应用, 跟 Sprint 15 B1 (is_member per-user 反向回填) 配套形成 B1+B2 双管齐下治理。

## 3. 决策审计

| 决策 | 选项 | 拍板 | 理由 |
|------|------|------|------|
| Sprint 17 任务范围 | A) #120+#121+#122 / B) 只 #120 / C) #120+#121 | **A** | 3 件 P1 都是 Sprint 16.5 留的债务, 一起收口效率最高 (3 subagent 并行 1.5h) |
| ground-truth-lint 文件位置 | A) `backend/contracts/_lint.py` / B) `backend/lint/contracts.py` | **A** | 跟 types.py / 3 B2-done contract 同目录, 跟 contract 文件物理临近, 跑起来方便 |
| Linting 工具类型 | A) AST 静态扫描 / B) 运行时 schema 验证 / C) mypy plugin | **A** | AST 静态扫描最准 (直接看代码), 运行时验证太重 (需要 import 所有 contract), mypy plugin 集成复杂 |
| List 字段 element-wise 约束 | A) `List["PercentageField"]` / B) `List[Annotated[float, Field(ge, le)]]` | **B** | A 不触发 element-wise 约束 (Pydantic v2 知识点), B 才是正确写法 (Sprint 16.5 6.3 踩坑治根) |
| 26 YOY ratio 字段残留 | A) Sprint 17 治根 / B) 留 Sprint 18 改命名 / C) 留 Sprint 18 扩 lint 白名单 | **B** | 命名/语义冲突需要更大 refactor (改 5+ 处 R 桶 ratio 字段命名), Sprint 17 已收 60+ 字段, 26 留 Sprint 18 |
| uvicorn restart 时机 | A) Sprint 17 末尾 / B) Sprint 18 / C) 不 restart (旧 service) | **A** | 4 端点 401 expected (需 auth), service alive, 但 contract 改动要让 reload 生效 |

## 4. 治理债务 (留 Sprint 18+)

| # | 任务 | 优先级 | 阻塞 | 备注 |
|---|------|--------|------|------|
| 1 | **26 YOY ratio 字段命名冲突治根** | 🔴 P0 | ground-truth-lint 长期挂 26 issue | 主要在 `yoy_*_ratio` 实际 PpField 不是 RatioField, 改命名 or 扩 lint 白名单 |
| 2 | ground-truth-lint 接 pre-commit hook | 🟡 P1 | 改 contract 时手动跑 lint 易忘 | CI 拦截 + pre-commit 自动跑 (参考 Sprint 3 P1-3) |
| 3 | Sprint 16 P0 重启 (DuckDB 1.5.4) | 🔴 P0 | Sprint 15 Wave 3 跑批真验 | 等 duckdb/duckdb#X release 1.5.4, 复用 v2 代码 + 4 tests |
| 4 | W5 cache invalidation hook | 🟡 P1 | 改 ratio/契约后必须手动 invalidate | Sprint 14.5 留, 跟 manifest 同步 |
| 5 | YOYBadge 守卫扩 MetricCard / RFMSegmentDrilldown | 🟢 P2 | RFMSegmentDrilldown 还用 `+Math.abs(v).toFixed(1)+'pp'` 老逻辑 | 跟 Sprint 16.5 YOYBadge 守卫模式统一 |
| 6 | ground-truth-lint 报告: 26 issue 分类 + 修复路径 | 🟡 P1 | Sprint 18 P0 #1 依赖 | 输出 docs/SPRINT-18-LINT-FOLLOWUP.md |

## 5. 学到的教训

### 5.1 Workflow subagent 中断恢复模式 (Sprint 17 新增)

**问题**: Sprint 16.5 workflow 4 subagent 完美跑通 (1.5h, 468K tokens). Sprint 17 workflow 3 subagent 跑 1.5h, 2 个 subagent 报 "API Error: ConnectionRefused" 失败 (实际工作已完成但 verify 阶段断了).

**根因**: subagent API 中断发生在 commit + lint run 之间, 工作已落 git 但 merge step 未跑.

**恢复模式**:
1. **worktree 清理**: `git worktree remove --force` + `git worktree prune`
2. **branch 状态确认**: `git log fix/...-X --oneline` 看分支 commit 完整
3. **rebase 验证**: `git checkout fix/...-X && git rebase main` 重放 commit 到最新 main
4. **测试**: pytest + ground-truth-lint 验证 commit 内容
5. **merge**: `git checkout main && git merge --no-ff fix/...-X -m "..."`
6. **CHANGELOG 补**: 跟 normal 12 步流程一样, merge 后补 CHANGELOG
7. **push + retrospective**: 收口

**教训**: 
- **branch 是 subagent 工作的真保险**: API 断不丢工作
- **rebase 比 merge conflict 简单**: 3 个 subagent 各自独立, worktree 隔离, rebase 几乎都 conflict-free
- **手动 verify 阶段不可或缺**: workflow verify agent 断电, 我手动跑了 pytest + ground-truth-lint + 4 端点 verify

### 5.2 B1+B2 模式 codify 进 CLAUDE.md 是治理关键

**问题**: Sprint 13 写的 ratio 治理契约只在 reference.md 跟 types.py 注释里, LLM 写新 contract 时不知道该用 Pydantic 元数据, Sprint 16.5 B2 试点后才补 #91.

**根因**: 文档跟工具层强制分离, 文档里说"必须用 Pydantic"但没工具拦截.

**治根**: Sprint 17 三件套:
- **#122**: 文档层强制 (CLAUDE.md "Ratio Convention" 章节 9 条规则)
- **#121**: 工具层强制 (ground-truth-lint AST 扫描 R1/R2/R3/R4)
- **#120**: 应用层落地 (10 contract 60+ 字段 Pydantic 化)

**效果**: LLM 写新 contract 时, 文档说"必须用", 工具说"必须跑", 应用说"已经做" — 三层防护.

### 5.3 Pydantic v2 List 字段 element-wise 约束 (Sprint 16.5 6.3 治根)

**问题**: `List["PercentageField"]` 不触发 element-wise 约束 (前向引用解析为 float, Field 元数据丢失).

**Sprint 16.5 踩坑**: 13 tests 第一次跑 3 fail, 改 `List[Annotated[float, Field(ge, le)]]` 后 13/13 passed.

**Sprint 17 治根**: 
- #121 ground-truth-lint R4 强制 List 写法检查
- #122 CLAUDE.md 文档化 Pydantic v2 知识点
- 防止未来 LLM 踩同样坑

### 5.4 命名/语义冲突 (Sprint 17 新发现)

**问题**: 26 lint issue 残留, 主要在 `yoy_*_ratio` 字段. 这些字段实际是 `PpField` (-100~+100) 不是 `RatioField` (0-1), 但命名 `_ratio` 让 lint R1 误报.

**本质**: 命名约定跟实际语义不匹配, 是历史遗留 (Sprint 14 之前 ratio 字段没用 Pydantic 时, 命名没这么严).

**Sprint 17 决定**: 26 留 Sprint 18 治根, 不在 Sprint 17 强行处理 (会引入 5+ 处字段重命名, 影响前端 + 后端 service + 跑批 SQL 引用).

**教训**: 命名/语义冲突的治根需要更大 refactor, 应该在 Sprint 18 plan 时单独 design, 不是治根任务的副作用.

## 6. 时间线复盘

| 时间 | 事件 |
|------|------|
| 17:30 | Sprint 17 workflow 启动 (run ID wf_76d1e4d5-f89), 3 phase: Plan/Execute/Verify |
| 17:30-17:45 | Plan & Discover 1 agent 调查 11 contract scope + 4 lint 规则 + CLAUDE.md scope (1 个 markdown 报告) |
| 17:45-19:15 | 3 subagent 并行跑 1.5h, 各自 worktree 隔离 (P2.7 cache_key 跟 Sprint 16.5 类似) |
| 19:15 | workflow 完成, 3/3 subagent 报告 STATUS: DONE |
| 19:15 | workflow verify agent 跑 pytest + uvicorn 端点 verify, 写 retrospective + memory |
| 19:30 | **API Error: ConnectionRefused** (verify agent 阶段), workflow 中断 |
| 19:30-20:00 | 我手动恢复: 清理 worktree → 确认 branch state → rebase 验证 → merge #121 → merge #120 |
| 20:00-20:50 | pytest 全套件 9.5min 跑完 (454 passed + 12 skipped + 3 pre-existing failed) |
| 20:50-20:55 | uvicorn 重启 PID 71040, 4 端点 401 expected (需 auth), health/docs 200 |
| 20:55-21:00 | 写 CHANGELOG v0.4.14.42 + v0.4.14.43, 写 retrospective + memory, 更新 document-index |

**总耗时**: 3.5h (含中断恢复 + pytest 9.5min + verify)

## 7. Sprint 18 预告

**Sprint 18+ 留 backlog (按优先级)**:
1. 🔴 P0: 26 YOY ratio 字段命名冲突治根 (Sprint 17 留)
2. 🟡 P1: ground-truth-lint 接 pre-commit hook (Sprint 17 留)
3. 🔴 P0: DuckDB 1.5.4 release 监控 + 跑批真验 (Sprint 16 P0 abort 续)
4. 🟡 P1: W5 cache invalidation hook (Sprint 14.5 留)
5. 🟢 P2: YOYBadge 守卫扩 MetricCard / RFMSegmentDrilldown

**Sprint 18 计划 (估 4h)**:
- **Wave 1 (2h)**: 26 YOY ratio 字段治根 (重命名 + 扩 lint 白名单)
- **Wave 2 (1h)**: ground-truth-lint 接 pre-commit hook
- **Wave 3 (1h)**: DuckDB 1.5.4 release 监控 cron + 复用 v2 代码

## 8. 关键指标

| 指标 | 值 |
|------|---|
| Sprint 周期 | 3.5h (含中断恢复 + verify) |
| Workflow ID | wf_76d1e4d5-f89 |
| Subagent 数 | 4 (Plan + 3 Execute + Verify 中断) |
| Subagent tokens | ~340K |
| 任务完成 | 3/3 (100%) |
| Commits | 11 (1+1+6 + 3 merge + 1 CHANGELOG) |
| Files changed | 16 (10 contract + 1 _lint + 1 test_lint + 1 LINTING.md + 1 SPRINT-17-B2-AUDIT-FULL.md + 1 test_contracts_b2_audit + 1 CHANGELOG) |
| Lines changed | +2080 (#120 1204 + #121 805 + CHANGELOG 62 + LINTING 9 后续) |
| Tests | 437+12 → 454+12 (+17: #121 lint 10 + #120 B2 50+ 去重净增 17) |
| Pre-existing failed | 3 (test_sim_prod_etl race + test_w4_full DuckDB 锁 + 1 sim-prod) — 跟 Sprint 17 改动无关 |
| uvicorn 端点 | health 200, docs 200, 4 端点 401 expected (需 auth) |
| ground-truth-lint | 26 issue (主要 yoy_*_ratio 命名冲突, 留 Sprint 18) |
| Lint tests | 10/10 passed |
| 12 步流程 | 3/3 subagent 走完, 后端 merge 由我手动恢复 (API 断) |

---

*此文件由 Sprint 17 治理 sprint 收口流程生成, 最后更新 2026-06-11*
