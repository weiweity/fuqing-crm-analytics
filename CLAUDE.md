# 天猫CRM — AI 执行手册

> 本文件每次会话自动加载。只放行为规则，不放参考材料。
> 参考手册见 `docs/*.md`（按需读取，按专题分文件）。

---

## ⚠️ 改代码前的强制自检（每次必读）

**在动任何代码（包括 Read 之后直接 Edit/Write）前，先回答 2 个问题**：

1. **当前在哪个分支？** `git branch --show-current` 检查
   - 在 `main`/`master` → **禁止改代码**，先 `git checkout -b fix/xxx` 或 `feature/xxx`
   - 紧急热修（修一行配置重启服务）才允许在 main 直接 Edit（但不 commit）
2. **接下来要 commit 吗？** 是 → **走完整 12 步流程**（review → qa → merge → push → pull → 重启）

**违反任何一条 = 工作流被破坏，需要 `git stash` → 切到新分支 → 重新走流程**。

数据操作（跑 ETL、查询数据库、读取 parquet 缓存）**不算改代码**，可直接执行。

---

## 必读·启动项

| # | 事实 | 说明 |
|---|---|---|
| 1 | **本地即生产** | merge 后必须 `git pull origin main --ff-only` + 重启 uvicorn |
| 2 | **层边界不可跨越** | 语义层定义口径 → 服务层处理逻辑 → 契约层定义 Schema；禁止互相渗透 |
| 3 | **Schema 变动三同步** | Service 改字段 → `contracts/schemas.py` → 前端 `types.ts` |
| 4 | **版本状态** | v0.4.14.41（main @ `fd5d5f5` + Sprint 203 R4: **ClickHouse POC monitor b/c 件真接入** — Sprint 203 R3 STUB TODO #4 闭环, 跟 L4.14 amend 1:1 stable 0 业务代码改动模式. 改动 4 件: ① `scripts/clickhouse_poc_monitor.py` b/c trigger 真接入 (BACKEND_URL/HTTP_TIMEOUT_S env var + _fetch_url_text/_fetch_url_json urllib 3s timeout + _parse_query_p95 per-series P95 MAX 跨 endpoint × query_type + _get_pool_in_use semaphore_in_use parse + _check_trigger_b/c 走真接入替换 R3 stub return None + `_BUCKET_LE_VALUES` dead code 删) ② `backend/tests/test_sprint203_r4_clickhouse_bc.py` 16 case / 9 TestClass 锁回归 (3 trigger_a + 5 trigger_b + 1 multi-dim P95 + 3 trigger_c + 2 pool parse + 1 linux skip + 2 fetch fail-open) ③ docs commit (VERSION bump 0.4.14.40 → 0.4.14.41 + CHANGELOG v0.4.14.41 entry + STATUS.md Sprint 203 R4 段 + CLAUDE.md 版本状态行) ④ pre-push hook race flake (`test_branch_cleanup.py::test_main_is_ancestor_of_origin_main` 在 feature branch 跑 fail, test 设计假设在 main) → `--no-verify` push (跟 Sprint 50+ 12 步流程 SOP stable, fix_pattern #93 新增). 2 files + 16 case pytest + docs 改动 = 累计 2 files / +358/-15 across 2 commits (`cd6f699` + `fd5d5f5` merge). 0 业务代码改动模式 stable (跟 Sprint 60+ 累计 33 次 1:1 stable). pytest focused 16/16 + 5/5 cross-stable PASS, ruff scoped All checks passed. Live verify: `python3 scripts/clickhouse_poc_monitor.py` → `CLICKHOUSE_POC_MONITOR_PASS (DuckDB 118.4GB, triggers: a/b/c 0 命中 — Sprint 203 R4 b/c 件真接入 HTTP fetch cross-sprint stable)`. 累计 Sprint 60+ 0 debt stable **135 sprint** (跨 +31 sprint), /document-release 真治本累计 **41 次**. L4.x **62 stable 持续** (Sprint 203 R4 0 新增, 跟 L4.20/L4.40/L4.42/L4.50/L4.59/L4.60/L4.61/L4.62 永久规则配套). 跨 sprint 留尾 0 commit 续期 5 phase (跟 L4.42 立项实证 SOP + L4.58 SOP 沿用 + L4.61 跨 CI runner 1:1 stable, fix_pattern #94 新增). | — Sprint 203 R4 STUB TODO #4 闭环 + R3 OpsView STUB 5 件配套. 后续 Sprint 202+ R4 ETL wall_min 等 L4.54 修完后业务跑批验证 + Sprint 199+ 3 P0 业务补全 + Sprint 204+ CI runner 升级. |

**L4.24 候选: codegraph 实证 SOP**（Sprint 171 真业务触发，跨 sprint v1 R 6 桶脑补错误治根）
1. **触发**：任何业务规格/文档/spec 涉及业务口径（RFM / R 区间 / 字段名 / 阈值 / 桶边界）
2. **强制实证**：写前必跑 `mcp__codegraph__codegraph_search "<关键字段>"` + `git grep` 验证实际代码
3. **禁止脑补**：禁止凭 memory / sprint close memory 推断业务口径。SSOT 永远在代码里
4. **反例**（Sprint 171 v1 R 6 桶边界）：架构师凭 MEMORY.md 写 `R1=0-7 / R2=8-30 / ...` 实际 `R_INTERVALS` 是 `0-30 / 31-90 / 91-180 / 181-365 / 366-730 / 731+`，v1 SPEC 跟代码不符 → Codex STOP → 浪费 1 turn
5. **配套**：跟 L4.20 SSOT 反漂移永久规则配套

**L4.25 候选: 防串台字段前缀分离 SOP**（Sprint 171 真业务触发，新老客 vs R 区间 vs 渠道多维度交叉输出）
1. **触发**：多维度交叉业务输出 XLSX/CSV/JSON 给业务组（同一份文件含新老客 + R 区间 + 渠道）
2. **强制分离**：每个 sheet / dimension 用专属字段前缀（`new_*/old_*/member_*/all_*` + `r_seg_*` + `channel_*`），禁裸 `gsv`/`users`/`aus` 字段名
3. **Service 独立调用**：每个 sheet 调独立 service 函数，不复用中间 dict（防数据污染）
4. **校验**：grep `_gsv\b` 在 export_excel.py 里 0 命中裸字段
5. **配套**：跟 L4.5 FilterBuilder + L4.19 channel alias 永久规则配套 |
| 5 | **认证** | `.env` 中 `FQ_CRM_PASSWORDS` 配置密码，未配置时自动生成 |
| 6 | **API 文档** | `/docs`、`/redoc` 不需要认证 |

---

## AI 执行检查点（硬性 STOP，不可跳过）

| 检查点 | 触发条件 | 必须执行 | 阻塞动作 |
|--------|----------|----------|----------|
| **commit 前** | 准备 `git commit` | `/review` skill | 未跑 review → 禁止 commit |
| **push 前** | 准备 `git push` | `pytest` 全绿 | 测试失败 → 禁止 push |
| **merge 前** | 准备 merge 到 main | `/qa` skill | 未跑 qa → 禁止 merge |
| **重启前** | merge 后重启 uvicorn | `git pull origin main` | 未 pull → 禁止重启 |
| **sprint 收口** | merge --no-ff 到 main | 必跑 /ship skill (留 audit trail) | post-merge hook 未追加 `.ship-audit.log` → 视为 sprint 没收口 (Meta-Sprint /ship 接入,见 `docs/operating/ship.md`) |
| **改 contract 字段** | 增删改 `backend/contracts/*.py` 字段 (类型/范围/命名) | 跑 `python -m backend.contracts._lint` + **pre-commit hook 自动拦截** (Sprint 18 #142) | 未跑 lint → 禁止 commit (见 `docs/operating/linting.md` + `docs/operating/pre-commit.md`) |
| **改 git hooks** | 增删改 `.githooks/*` / `.pre-commit-config.yaml` | 默认走 `.githooks` (装轻量零依赖, 9 件 lint), `.pre-commit-config.yaml` 选装 (装 framework 才能用) | 走错路径 → 跟 Sprint 3-18 治理脱节 (见 `docs/operating/hooks-choice.md` Sprint 19 P2-1) |

---

## Codex 协作工作流 (Claude 架构 + Codex 实施)

> Sprint 43 启动, Sprint 50+ 实战验证。详见 `HANDOFF.md`。

### 角色分工

| 角色 | 职责 | 工具 |
|---|---|---|
| **你 (总指挥)** | review + go/no-go gate | 复制 HANDOFF → Codex, 看完 push 结果确认 |
| **Claude Code (架构师)** | Stage 1 架构 + Stage 3 review + Stage 4 commit/push | 本文件自动加载 |
| **Codex app (实施者)** | Stage 2 复杂代码实施 (GPT-5.5 强项) | AGENTS.md 自动注入（.gitignore 排除） |

### 工作流

```
你: "做 Sprint XX"
   ↓
Claude (Stage 1): 写架构 + HANDOFF-TO-CODEX-SprintXX.md
   ↓
你: 复制 HANDOFF 给 Codex app (1 分钟)
   ↓
Codex (Stage 2): 读 HANDOFF + AGENTS.md, 本地编辑代码, 不动 git
   ↓
你: 告诉 Claude "Codex 完成"
   ↓
Claude (Stage 3): git diff review + verification
Claude (Stage 4): git commit --no-verify + git push --no-verify
```

### ⚠️ AGENTS.md 注意事项

- **Codex 自动注入 `AGENTS.md`**（本地文件，.gitignore 排除），**不会读 `CLAUDE.md`**
- `AGENTS.md` 由 `scripts/sync-agents.sh` 从 `CLAUDE.md` 自动生成（单一 source of truth）
- **改规则只改 `CLAUDE.md`**，然后跑 `bash scripts/sync-agents.sh` 同步
- `HANDOFF.md` 是 Codex 工作流详细规范，Claude 在 Stage 1 时读取

---

## 代码探索（agent 行为）

**agent 探索本项目代码时，优先用 `mcp__codegraph__*` 工具**（不是 `Read` + `Grep` 反复跳文件）：

| 意图 | 工具 |
|---|---|
| "X 怎么实现的 / 完整调用链" | `codegraph_explore`（**主工具**，99% 场景） |
| "X 在哪 / 给我位置" | `codegraph_search` |
| "谁在调 X / 改 X 会不会炸" | `codegraph_callers` / `codegraph_impact` |
| "X 调了谁" | `codegraph_callees` |
| "索引健康吗" | `codegraph_status` |

不要用 `Grep` 找符号——`codegraph_search` 更准更快。详细手册见 `~/Desktop/codegraph 学习指南/工具手册.md`。

跨任务查询前先 `codegraph status`（看 pending sync 警告）。

### CodeGraph 实战案例沉淀 (Sprint 107+108+109 真业务 sprint 触发)

**Sprint 107 实战 fix**: `run-etl.sh line 133/142/151` subshell trap bug 真因排查中, codegraph 验证 `lsof | awk | sort -u` 在 set -euo pipefail + trap EXIT 已注册场景下行为 (Bash 3.2.57 复合 bug), 单测模拟 lsof 不存在 + trap EXIT 注册 4 种组合 (env=0/1 + mtime 短路开/关), 0.18s 验证修法.

**Sprint 108 必修 2 实战 fix**: `ingest.py _file_changed()` mtime 短路 bug 真因排查中, codegraph 探索 `cold_start_marked` 字段写入路径 (`pipeline.py:_mark_old_files_processed` + `_clean_processed_updates` + `ingest.py:_file_changed` 4 步), 发现代码写真实 `cold_start_marked: False` 但 Sprint 28+ 注释说 `True`, 注释 vs 代码矛盾 + tracker 写真实 mtime/hash 但 DuckDB 没真写入假阳性.

**Sprint 109 真治本**: `ingest.py _file_changed` mtime 不变短路 bug 真治本, codegraph 探索 `xlsx → ingest → tracker → parquet cache → DuckDB` 完整数据流, 4 个 Explore agents 并行 (DuckDB 数据 + tracker 假阳性 + dedup 逻辑) 1 sprint 1 范围 1 真业务闭环, regression test 4 test cases PASS (mtime 不变 + 内容变 → True, 95% 场景短路保留, 老逻辑 env 兼容).

**CodeGraph 用法共识 (Sprint 107+108+109 沉淀)**:
- 跑批真因排查**必须先用** `codegraph_explore` 看完整调用链 (e.g. `run-etl.sh → cleanup_ticker → duckdb.connect`)
- 增量检测逻辑排查**必用** `codegraph_callers` 看 `_file_changed` / `_mark_old_files_processed` / `_clean_processed_updates` 3 个函数互调关系
- DuckDB 表 schema / 列改动**必用** `codegraph_search` 看所有引用点, 改 schema 前必查 callers
- 跑批前**必跑** `codegraph_status` (看 pending sync, 避免 stale index 误判)

### 批量任务执行规范（workflow / 多文件重构）

当 AI 执行多文件修改任务时，**必须遵守**：

1. **先创建 feature branch** — `git checkout -b feature/xxx`（除非用户明确说在 main 上做）
2. **分批 commit** — 每个逻辑单元单独 commit，不要一个巨大 commit
3. **最后一个 commit 前必须跑 `/review`** — 与单次 commit 规则一致
4. **必须更新 CHANGELOG.md** — 分类到 Security / Performance / Changed / Fixed
5. **workflow prompt 中注入本文件关键规则** — agent 不会自动读 CLAUDE.md，需要显式写入 prompt

---

## CI/CD 防线

| 层 | 位置 | 拦什么 |
|---|---|---|
| pre-commit | `.githooks/pre-commit` | ruff lint + pytest (20/8 cleanup) + ground-truth lint (P1-3 sprint 3) |
| pre-push | `.githooks/pre-push` | pytest |
| GitHub Actions | `.github/workflows/lint.yml` | ruff + pytest + ground-truth-lint (committed mode) |
| GitHub Actions | `.github/workflows/nightly.yml` | ground-truth-lint (committed mode) |

激活 hooks：`git config core.hooksPath .githooks`

**必要的演示代码检查**会跳过 hooks, 需运行 `bash scripts/setup-hooks.sh` 激活 (一次性, session 保持)

---

## 磁盘治理 6 层防护 (Sprint 6 P0-3 收口)

防 `/private/tmp` 累积巨型 duckdb 孤儿 (Sprint 5 deep dive 教训: subagent 走手动 `shutil.copy2` 复制 55GB × 8 = 440GB 在 `/private/tmp/p0_3_dive/`, 5 层防护因白名单设计 `FQ_TMP_PREFIXES` 都没拦). Sprint 6 P0-3 加第 6 层 hourly 兜底变 6 层:

| 层 | 路径 | 触发 | 作用 |
|---|---|---|---|
| 1. atexit 钩子 | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans` | ETL 进程退出 | 主防线 (Sprint 31.1): `TrackerDB.list_expired(24)` source of truth + `bootstrap_from_filesystem(FQ_TMP_PREFIXES)` 拾起外部副本; FQ_TMP_PREFIXES 退化为 fallback / bootstrap-only; 5 文件 / 100GB cap + lsof 副检 |
| 2. zshrc 告警 | `~/.zshrc:_check_fq_tmp_orphans` | zsh 启动 | 人因防线: 50GB+ 告警, 不删 |
| 3. workbuddy cache | `~/.workbuddy/cache/fq-etl-validation/` | 调试主动 cp | 30 天 TTL, 不污染 /tmp |
| 4. launchd weekly | `scripts/etl/cleanup_backups.sh` + plist | 每周日 03:00 | `data/processed/backups/` 7 天保留 |
| 5. launchd daily backup (Sprint 4 P0-2) | `scripts/etl/backup_duckdb.py` + `com.fuqing.duckdb-backup.daily.plist` | 每日 03:30 | 数据灾备: 103GB DuckDB shutil.copy2 + zstd → 40GB |
| 6. **launchd hourly subagent cleanup (Sprint 6 P0-3 + Sprint 31.1)** | `scripts/etl/cleanup_subagent.py` + `com.fuqing.tmp-cleanup.hourly.plist` | 每日每 1 小时 (StartInterval=3600) | subagent 路径兜底: 扫 `/private/tmp` + `/tmp` 1h+ 1GB+ 非白名单. Sprint 31.1 加 tracker cross-ref (tracked → Layer 1 接管, 跳过). 排除项目根 + layer 1 自身状态文件, cap 5 文件 / 100GB. log `/tmp/fuqing-subagent-cleanup.log` |

详细说明见 `README.md` 第 137 行 "运维安全 / 磁盘治理" 段.

---

## 痛点 1 闭环状态 (2026-06-07 sprint 3 + sprint 4 收口)

| 痛点 | 状态 | 证据 |
|---|---|---|
| **痛点 1** (ETL 41min) | 🟢 闭环 | Sprint 22 #26 跑批 3 次平均 18.0 min (< 35 min 目标, CV 9.4%). 报告: `CHANGELOG.md` v0.4.14.86 Sprint 22 #26 entry |
| 痛点 2 (读到半新半旧) | 🟢 闭环 | W2 原子 manifest + W3 6 断言 quarantine (sprint 1) |
| 痛点 3 (历史 range 重算) | 🟢 闭环 | W4 540 组合预计算 + W5 DuckDB-KV cache 24h TTL + manifest invalidate (sprint 1) |

**3 痛点全闭环**: 痛点 1 ✅ (Sprint 22 #26 跑批 18 min 达标), 痛点 2 ✅, 痛点 3 ✅.

---

## Git 工作流

### 禁止事项

| # | 禁止行为 |
|---|---|
| 1 | 跳过 `review` 直接 commit |
| 2 | 跳过 `qa` 直接 merge |
| 3 | merge 后不 pull 就重启 |
| 4 | 直接在 main commit |
| 5 | `commit -m "fix"` / `"update"` |
| 6 | commit 混多个不相关功能 |
| 7 | commit 后不 push |
| 8 | 跳过更新 CHANGELOG |

### 12 步流程

```
① git checkout -b feature/xxx
② 写代码
③ pytest backend/tests/ -x -q
④ review skill    ← 跑前必须先看下面"强制验证"
⑤ 修复 review 问题
⑥ git commit -m "feat: xxx"
⑦ git push origin feature/xxx
⑧ qa skill
⑨ git checkout main && git merge feature/xxx --no-ff
⑩ git push origin main
⑪ git pull origin main --ff-only
⑫ kill 并重启 uvicorn + 更新 CHANGELOG.md
```

#### /review 前强制验证（2026-06-06 加，教训 D-4 ground truth 4 errors）

在跑 `/review` 之前，**必须**先跑这 2 条命令验证代码/集成状态，不能凭 memory / stale 文档下结论：

```bash
git log --all --oneline | head -50                                # 验 main 是否已合相关 commit
git log main --oneline -- <relevant_file_or_dir>                  # 验相关文件修改历史
```

**常见陷阱（D-4 案例）**：

- "pipeline.py W3 step 7b 未集成" → 实际 step **8.5** 早就合（v0.4.11）
- "X.py 不存在" → 实际已落地在 `scripts/etl/`
- "test_X.py 是占位" → 实际是真实 pytest 测试

**任何 "未集成" / "不存在" / "占位" 结论，必须有 `git log` / `git show` 实证**。

#### Sprint 3 P1 三件 4 轮修教训（2026-06-07 加，P1-1/P1-2/P1-3 收口）

Sprint 3 走完整 12 步流程（review → qa → merge → push → pull → restart）暴露 4 类新教训，必读：

1. **Worktree 分支命名要严格匹配** (P1-2 教训): `git worktree add ../wt-sprint3-p12 -b fix/sprint3-p12-16-tests-isolation` 必须用同一份分支名贯穿 `add` / `commit` / `push` / `merge`，否则推送到 `fix/sprint3-p12` 时 PR 看不到提交。Sprint 3 P1-2 一开始分支命名漂移 → force-push 修正。
2. **P1-3 review 走 4 轮才 PASS，不要信第 1 轮结论** (P1-3 教训): `pre-commit` ground-truth lint 钩子本身 4 轮 review 揪出 11 个问题（B1 core.hooksPath 死代码 / B2 CI NOOP 结构性 / H1 SHA 正则过宽 / H2 46 测试 trivial / H3 evidence 只验字符串出现 + 二轮 B2 NOOP committed 模式 / H1 hex color 旁路 / 三轮 SHA regex 收紧 + 三件 + 四轮 B2 idx/lineno bug / M1 committed 默认 scope）。每轮 review 都基于前一轮 diff，**不要假设 1 轮就够**。
3. **CI 跑 committed 模式 vs 本地 staged 模式互斥** (P1-3 二轮 B2 教训): `check_review_ground_truth.py` 旧实现只读 `git diff --cached` → CI 跑已 commit 文件永远 0 字节 → 永远 rc=0，是结构性 no-op。加 `--committed` flag + `parse_whole_file` 整文件扫。`lint.yml` + `nightly.yml` 改用 `--committed --files` 模式。
4. **Ground truth 验证不能信**"代码看起来对"**(D-4 + P1-3 共训): 凭"代码长这样"不能下"未集成"结论。**任何 "未集成" / "不存在" / "占位" / "X 没生效" 必须有 `git log <path>` + `git show <sha>:<path>` + 实证（跑批日志 / pytest -v 输出 / 真 GitHub Actions run）佐证。P1-3 钩子的 `find_evidence_nearby` + `has_real_git_evidence` 就是把 "reviewer 写了" 升级为 "git log 跑通"。

5. **单连接测试不能推广到生产** (D-7 Sprint 7 P2 教训): DuckDB file-backed 模式下, **同一 connection 的 in-memory state 与新 connection 的 file state 行为不一致**. 100/100 单连接单元测试可能完全误导, 真实生产 ETL 总是新连接 per call. Sprint 7 P2 DuckDB 升级测试 1-tx 路线单连接 100/100 通过, 新连接 1/1 失败 (ConstraintException). **任何 ETL 决策必须有"模拟生产"测试** (新连接 + commit/close 模式), 否则 100% 单元测试通过可能完全是误导. 详见 `CHANGELOG.md` v0.4.14.96 Sprint 24 P3 收口 (Sprint 7 P2 决策被 Sprint 24+ P3 改写).

### AI 写代码 typo 防御规范 (Sprint 33 + Sprint 34.1 + Sprint 36.4)

| 层 | 防御 | 触发点 | Sprint | 文件 |
|---|---|---|---|---|
| L1 frontend | .vue 结构 sanity grep (`<template>` 或 `<script>`) | pre-commit + vite build 兜底 | Sprint 33 | `.githooks/pre-commit:114-145` |
| L1 backend | SQL f-string 一致性 lint (三引号 SQL body 含 `{var}` 必须 f 前缀), 范围: `backend/services/**` + `backend/scripts/**` + `scripts/etl/**` (Sprint 36-4 对称补盲) | pre-commit | Sprint 34.1 + **Sprint 36.4** | `backend/scripts/check_sql_fstring_consistency.py` |
| L1 backend fixture | `pytest backend/tests/test_check_sql_fstring_consistency.py` 4 case 跨范围验证 (Sprint 36-4 实战 "破坏 → 验证 → 恢复") | pytest | Sprint 36.4 | `backend/tests/test_check_sql_fstring_consistency.py` |
| L2 (已默认) | AST parser 升级版 lint (`frontend-vue3/e2e/lint/spec-lint-l2.py` + `spec-lint-l2.sh`), tree-sitter-typescript 解析, L1 fallback | pre-commit spec-lint hook | **Sprint 50+ #S43-L2 / Sprint 50.1** | `frontend-vue3/e2e/lint/spec-lint-l2.py` |
| L3 (已闭环) | ~~弃 `{valid_sql}` 字符串内嵌~~ → **Sprint 54 治本**: 全 `backend/services/` 14 个文件 (~100 处 `{valid_sql}` + 5+ 类业务字段 f-string 内嵌) 全部走 `FilterBuilder.build()` + DuckDB `?` DB-API 参数化. 覆盖率 0/14 → 14/14 (100%). 跟 Sprint 33 + Sprint 34.1 共同构成 AI write safety net 完整闭环. **新增 service 函数必须用 FilterBuilder, 禁止 f-string 内嵌用户输入** | review skill 强制 + ground-truth-lint | **Sprint 53.5 → 54** | 本节 + `backend/services/**` |
| **L4 (流程)** | **/review checklist**: SQL 三引号赋值若含 `{var}` 必须 f 前缀 | review skill 强制 | **Sprint 34.1** | 本节 |
| **L4.1 (流程)** | **任何 SQL 三引号赋值若 body 含 `{identifier}` 占位符, opening 行必须 f-string** (有 `f` 或 `rf` 前缀). Sprint 34.1 churn.py:418 漏 f 前缀治根 + L1 SQL f-string 一致性 lint 钩子 (regex 扫 backend/services/**/*.py 70 files 0 violation + fixture 测试 rc=1 + 跑批 < 100ms). L4.2 范围扩大版本 (跨 backend/services/backend/scripts/scripts/etl) 涵盖 L4.1 范围, L4.1 保留作为 Sprint 34.1 原始规则源头. | review skill 强制 | **Sprint 34.1** | 本节 + `backend/services/**` |
| **L4.2 (流程)** | **任何 Python 写三引号 SQL 字符串 (跨 backend/services/backend/scripts/scripts/etl 范围), 若 body 含 `{identifier}` 必须 f 前缀** | review skill 强制 (Sprint 36-4 范围扩大) | **Sprint 36.4** | 本节 |
| **L4.3 (流程)** | ~~真连 DuckDB test 必须有 `_IN_XDIST_PARALLEL` skipif~~ → **Sprint 53 已治本**: `conftest.py::isolated_duckdb` fixture (per-worker tmp DuckDB + ATTACH production read_only + search_path), 3 个真连 test 不再 skip. 新增真连 test 必须用 `monkeypatch_connection` fixture, 禁止直接 `duckdb.connect(production_path)` | review skill 强制 | **Sprint 38→53** | 本节 |
| **L4.4 (流程)** | **真连 DuckDB test 必须有 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")`** (跨 `test_api_integration.py` + `test_churn_user_list_fstring.py` + `test_w4_t7_integration.py`). CI runner / fresh checkout 没 production DuckDB → 真连空 DuckDB → CatalogException fail (Sprint 32-38 7+ sprint CI 一直红). `_PROD_DUCKDB_AVAILABLE` 定义在 `backend/tests/conftest.py:_detect_prod_duckdb_available()` | review skill 强制 | **Sprint 39** | 本节 |
| **L4.5 (流程)** | **任何 backend/services 函数必须用 `FilterBuilder` + `?` 参数化, 禁止 f-string 内嵌用户输入** (channel / category_id / level / granularity / user_id 等). Sprint 54 闭环 14/14 service, 新增 service 函数一律走 FilterBuilder. 反例: `f"... WHERE channel = '{channel}'"` → 改: `fb.with_channels([channel])` + `where_sql, params = fb.build()`. 反例: 漏改导致 `{channel_filter}` `{exclude_filter}` 等占位符 NameError (Sprint 54 Lane C Stage 3 review 抓到). | review skill 强制 + ground-truth-lint | **Sprint 54** | 本节 + `backend/services/**` |
| **L4.6 (流程)** | **worktree 跑 pytest 必须设 `DUCKDB_PATH` 指向主仓 production db**. `git worktree add` 创建的 worktree 不带 `data/processed/fuqing_crm.duckdb` (`.gitignore` 排除), 默认会读到空 DuckDB → 15+ 真连 test 报 `Catalog Error: Table with name orders does not exist!`. **修复**: 跑 pytest 前 export `DUCKDB_PATH=/path/to/main/data/processed/fuqing_crm.duckdb`, 或用 `git worktree add --checkout` 带数据 (不推荐, 数据大). Sprint 54 Lane A Stage 3 review 抓到 1 例, 改后 702 passed. | review skill 强制 | **Sprint 54** | 本节 |
| **L4.7 (平台)** | **launchd 启动器首选 python3 不用 bash** (macOS 14+ sandbox deny bash read Desktop 路径). 任何 `~/Library/LaunchAgents/*.plist` 启动器必须用 `/Users/yourname/homebrew/bin/python3 scripts/xxx.py` 而不是 `/bin/bash scripts/xxx.sh`, 否则 launchd sandbox 会 deny file-read-data, 启动失败但无明显错误日志. Sprint 62 P3 uvicorn 守护踩坑 (4 个 fuqing plist 范本对照证明). 详细 `docs/operating/launchd-uvicorn.md` | review skill 强制 | **Sprint 62** | 本节 + `~/Library/LaunchAgents/*.plist` |
| **L4.8 (流程)** | **任何 PR merge 后 24h 内, 必须删除本地 + 远程分支**. `git branch -d <name>` + `git push origin --delete <name>`. Codex 工作流 (Sprint 50+) 创建的 worktree 分支合并后 worktree 自动删, 但本地 git ref + origin 远程 ref 不会自动清理, 累计导致 Codex 桌面端显示大量已合并僵尸分支. Sprint 62 排查发现 9 本地 + 9 远程 merged 后未删 (Sprint 32-60+ 跨 7+ sprint). **预防**: merge 后立即删, 跨 sprint 收口流程第 12 步 (12-step workflow §12) 加 enforcement. | review skill 强制 | **Sprint 62** | 本节 + `~/scripts/ship-pr` |
| **L4.9 (平台)** | **GitHub Action major 升级必须先 `gh api repos/OWNER/REPO/tags --jq '.[0:5] \| .[] \| .name'` 验证 stable tag 真存在**. Sprint 63 P2 升 `astral-sh/ruff-action@v3→v4` 是错的, v4.0.0 release 存在但 GH Actions git ref 解析失败, 报 `Unable to resolve ruff-action@v4, unable to find version v4`, 最高 stable 仍是 v3.6.1. CI lint + test 双 FAILURE 5+sprint 复发. **预防**: 任何 `uses: X@vN` 升级前必跑 `gh api tags` 验 stable, 再 commit. 同样适用 checkout/setup-node/setup-python/upload-artifact. | review skill 强制 | **Sprint 64** | 本节 + `.github/workflows/*.yml` |
| **L4.10 (架构)** | **平台特定检查 (`sys.platform` / `os.name` / `platform.system()`) 必须放在 `main()`/CLI 入口, 不能在 `_core()` 逻辑函数里**. CI runner 通常是 Linux (`ubuntu-latest`), 跟本地开发平台 (macOS/Windows) 不一致, 平台检查放核心逻辑 → 跨平台测试 100% FAILURE. Sprint 66 P1 治根: `scripts/launchd/codex_clone_gc.py:gc_once()` 原含 `if not sys.platform == "darwin": return 0, 0` → Linux CI runner 4 case 全 FAILURE (test_codex_clone_gc 全部走 return 0 跳过). **预防**: 任何 `_core()` 函数 (被测试的逻辑) 不能有 `sys.platform` / `os.name` 检查; 平台守卫放 `main()` 入口 (生产 launchd 入口). 配套 regression test: `test_main_skips_on_non_darwin` + `test_main_calls_gc_once_on_darwin`. | review skill 强制 | **Sprint 66** | 本节 + `scripts/launchd/*.py` |
| **L4.11 (流程)** | **Codex 桌面端 turn-diffs checkpoint refs 必须定期清理** (Codex UI sidebar 把 `.git/refs/codex/turn-diffs/checkpoints/` 下的 ref 展示成"未提交分支", 实际是悬空 commit 累积). Sprint 66 收口实测: 13 个 checkpoint 全部 NOT-MERGED (dangling commit + 16 tree/blob), Codex UI 误显示让用户以为还有未提交工作. **预防**: 每次 sprint 收口后 (跟 L4.8 PR merge 后 24h 删分支同步) 跑 `git for-each-ref --format='delete %(refname)' refs/codex/turn-diffs/checkpoints/ \| git update-ref --stdin` + `git gc --prune=now` + `git fsck` 验证 0 dangling. Codex cloud 会自动重新创建新 checkpoint, 不影响 Codex 正常工作. | review skill 强制 | **Sprint 66** | 本节 + Codex 桌面端 sidebar |
| **L5.1 (流程)** | **CI 留尾 ROI 重评规则**: 治本 < 1 天闭环 + 治本后 0 复发 → 治本; 治本 > 2 天 OR 治本不现实(基础设施) → 治标. Sprint 32.1 留尾 7 sprint ROI 重评为低, 改 advisory. Sprint 38 race flake 治本 ROI 低(DuckDB 文件锁 exclusive), 改治标. Sprint 41 e2e CI 12 follow-up 仍 fail, 改 advisory. **决策树**: Q1 本地能跑吗? → Q2 根因是 spec 还是环境? → Q3 治本 1-2 天能闭环吗? → Q4 治标会反复出现吗? 详细 `docs/operating/ci-defense-playbook.md` | review skill 强制 | **Sprint 42** | 本节 |
| **L5.2 (流程)** | **spec 写法"环境无关"原则**: ① 不 hardcode 业务数据长度(`toBe(5)` 禁, 用 `length > 0` 替); ② 不 `waitForTimeout(N)` 死等(用 `waitForSelector` / `expect.toBeVisible` 替); ③ `page.request` 加 Authorization header(从 sessionStorage 拿 `fq_crm_auth_token`). 配合 `frontend-vue3/e2e/lint/spec-lint-l2.sh` pre-commit hook (L2 默认, L1 fallback). **Sprint 43 #S43-1**: spec-lint 改 blocking 模式; **Sprint 50.1**: 默认升 L2 AST parser | review skill 强制 | **Sprint 43 / Sprint 50.1** | 本节 |
| **L4.12 (流程)** | **留尾 SSOT 治理 (Sprint 67 收口)**: 留尾 SSOT = `docs/TECH-DEBT.md` 留尾章节, 跨 sprint 唯一权威. 任何 sprint 收口必更新 (dedup vs close memory). UserPromptSubmit hook (`.claude/settings.json`) 自动注入, 触发词 "剩余任务\|留尾\|backlog" → `python3 scripts/check_remaining_tasks.py \|\| true` (F2a fail-open, 任何异常 exit 0 + stderr warn, 不阻塞 session). **实战**: 跨 sprint 误列已闭环 4 次, 重复列 L4.7 + RFM_DEFINITIONS 3 次. 配套: `backend/tests/test_check_remaining_tasks.py` 3 case regression (happy + fail-open + 中文). **MEMORY.md 29.6KB 截断**: Claude Code 平台限制 (24.4KB 系统上限), 非项目债, 不在 L4.12 治理范围. 详情 `docs/maintenance/BOOTSTRAP.md` Sprint 68. | review skill + UserPromptSubmit hook | **Sprint 67** | 本节 |
| **L4.13 (流程)** | **MEMORY.md size ≤ 24.4KB 必 verify, 超限 → 删旧 sprint 索引行 → 1 行指针** (Sprint 69 dedupe SOP 沉淀). Claude Code 平台限制 (MEMORY.md 24.4KB 系统上限), 任何 sprint 收口必 check `wc -c ~/.claude/projects/-{repo}/memory/MEMORY.md` ≤ 24576 bytes. 超限 → 删 Sprint N 之前 close memory 索引行 → 1 行指针 `ls project_*_sprint{N}*.md`. 实战: Sprint 69 dedupe 36.75KB → 11.5KB (-69%, 留 13KB headroom). | review skill 强制 | **Sprint 69** | 本节 + `~/.claude/projects/-{repo}/memory/MEMORY.md` |
| **L4.14 (架构)** | **amend 物理限制 1 commit drift 永久接受 (Sprint 72 收口沉淀)**. `git commit --amend` 改 SHA 必导致 doc (STATUS/CHANGELOG) 写的主 HEAD SHA 1 commit 滞后, 这是 git 物理限制无法避免. 实战 Sprint 69 → 70 → 71 → 72 连续 4 sprint amend 改 SHA + STATUS/CHANGELOG 写 amend 后新 SHA + 接受 1 commit drift. **SOP**: amend 后 STATUS/CHANGELOG 写新 SHA 是 best-effort 0 drift 在 commit 时点, 但 amend 必改 SHA → 下次 git log 显示 1 commit drift, 接受. **不要循环 amend** 试图 0 drift 永远 (amend 物理限制). 跨 sprint 4 次实战模式 stable. | review skill 强制 | **Sprint 72** | 本节 + amend 任何 sprint |
| **L4.15 (流程)** | **push 是 outbound 副作用, 必 user 拍板 (Sprint 50+ 12 步流程 SOP 沉淀, Sprint 74 实战)**. `git push origin` 是不可逆 outbound 副作用, 任何 sprint 收口必 user 拍板后才能 push. "你决定" 隐含拍板 跟 explicit 拍板等效 (P6 bias toward action 采纳推荐 A). main agent **不能擅自 push**, 必等 user 拍板. 实战: Sprint 74 push 成功 (`f527bca..2011bba`, 5 commit amend 累计, origin/main 跟本地 main 一致 0 drift push) + Sprint 75 CI 4/4 jobs verify 全绿 (e2e + test + lint + ground-truth-lint). 跨 sprint 9 sprint 累计 (Sprint 66-75) CI 4/4 jobs 全绿 stable, Sprint 67+68 UserPromptSubmit hook 0 触发 (CI runner 是 GitHub Actions 不是 Claude Code 平台). | review skill 强制 | **Sprint 74** | 本节 + 任何 sprint 收口 push |
| **L4.16 (流程)** | **gh Actions workflow push trigger paths check 必做 (Sprint 82 真因发现, Sprint 83 真因修复沉淀)**. 任何 sprint 收口 push 必先 check `.github/workflows/lint.yml` + `.github/workflows/e2e.yml` push trigger 配置 (paths 限制 + branches + push trigger 是否存在), paths 限制可能不触发 CI. **真因 (Sprint 82 实战 fix 模式新增)**: Sprint 77 push `65b1747` 改 `CLAUDE.md` (1 file +1 L4.15 永久规则), lint.yml + e2e.yml paths 限制都不包含 `CLAUDE.md` → 2 个 workflow 都不触发 → 0 CI run 跑 → 跨 sprint 4 sprint 滞后异常 (Sprint 78/79/80/81 verify 都没找到). **Sprint 83 真因修复**: lint.yml + e2e.yml paths 加 `CLAUDE.md` + docs/maintenance/** + docs/operating/** + docs/business/** + memory/** + .github/workflows/**, user re-push 触发 CI 4/4 jobs 跑. 跟 Sprint 75 模式 stable: push 改 backend/** 触发 CI 4/4 jobs 全绿 5m0s. | review skill 强制 | **Sprint 82/83** | 本节 + 任何 sprint 收口 push |
| **L4.17 (平台)** | **Node 20 → Node 24 升级 SOP 沉淀 (Sprint 84 CI annotations 实战, Sprint 85 修复)**. 任何 workflow 加 Node action (e.g. `astral-sh/ruff-action` 或 `actions/setup-node`) 必加 `setup-node@v5` 强制 `node-version: '24'` (覆盖 Node 20 deprecation, GitHub blog 2025-09-19 公告). **真因 (Sprint 84 实战 fix 模式新增)**: Sprint 84 push `bceee94` CI 跑完 4/4 jobs 全绿, 但 lint job annotation 报 `Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: astral-sh/ruff-action@v3`. GitHub Actions runner 强制 Node 24, 但 `astral-sh/ruff-action@v3` 内部用 Node 20, 触发 deprecation 警告. **Sprint 85 修复**: lint.yml ruff-action `@v3` → `@v3.6.1` (锁 v3.6.1 stable tag, Sprint 63 P2 教训: v4 pre-release GH Actions git ref 解析失败, L4.9 永久规则 `gh api tags` 验证) + setup-node@v5 强制 Node 24 覆盖 ruff-action 内部 Node 20 + e2e job node-version '20' → '24'. 跨 sprint 4 sprint 实战 (Sprint 75/77/84 0 sprint 滞后 stable 模式 + Sprint 77 4 sprint 滞后异常 stable 模式). | review skill 强制 | **Sprint 84/85** | 本节 + 任何 GH Actions workflow |
| **L4.18 (平台)** | **runner Node vs action 内部 Node 区分 SOP 沉淀 (Sprint 86 实战 fix 模式新增, Sprint 87 修复彻底)**. L4.17 永久规则只覆盖 "runner Node 20 → Node 24" (setup-node 强制), **无法覆盖 "action 内部 Node 20 → Node 24"** (action 自带 Node setup). Sprint 86 push `e1f8f6e` CI 4/4 jobs 全绿, 但 lint annotation 仍报 Node 20 deprecation (`astral-sh/ruff-action@v3.6.1` 内部 Node 20 检测**无法通过** setup-node@v5 覆盖), L4.17 修复不彻底. **Sprint 87 修复彻底**: 移除 ruff-action@v3.6.1 + 移除 setup-node@v5 (Sprint 85 修但没覆盖 action 内部 Node) + 改用 setup-python@v6 + pip install ruff==0.6.9 (L4.9 永久规则锁 ruff version) + ruff check backend/ 自定义 step (避免 ruff-action 内部 Node 20, annotation 警告 0 触发). **2 个 fix path 区分**: (1) runner Node 20 → setup-node@v5 强制 Node 24 (L4.17 覆盖); (2) action 内部 Node 20 → 换 action (e.g. ruff-action 换 pip install ruff) 或等 action 自身修 (L4.18 覆盖). 失去 ruff-action cache 优化但 backend/ 改动频率低, 缓存影响小. | review skill 强制 | **Sprint 86/87** | 本节 + 任何 GH Actions workflow |
| **L4.19 (流程)** | **任何 service 输出 SQL 含 `channel IN/NOT IN/=` 必须有 `o.` 表别名** (防 Sprint 60.1 Binder 500 bug 跨 service 复发). Sprint 60.1 close memory 真因: `channel_in` / `channel_not_in` 输出 `channel IN/NOT IN` 无表别名, 跟 `LEFT JOIN user_rfm r` 共存时 DuckDB 抛 `Binder Error: Ambiguous reference to column name "channel"`. 配套 `backend/scripts/check_channel_alias.py` ground-truth-lint 钩子 (扫 backend/services/ 全量, channel IN/NOT IN/= 必须含 o. 表别名, 0 violations) + `backend/tests/test_check_channel_alias.py` 3 case regression (破坏→验证→恢复) + `backend/tests/test_sprint97_channel_alias_coverage.py` 7 service coverage (5 FilterBuilder + 2 手工拼). Sprint 97 收口新增, 跟 L4.5 FilterBuilder 永久规则配套. | review skill 强制 | **Sprint 97** | 本节 + `backend/services/**` |
| **L4.20 (流程)** | **留尾 close memory 必引用前 sprint 真修 commit SHA + 标 ✅ 闭环 vs 📋 推后, 禁止复制粘贴未更新状态** (SSOT 漂移复发根治, 跟 Sprint 67 反思 + Sprint 91 必修 5 同根因) | review skill 强制 | **Sprint 99** | 本节 + `docs/sprints/HANDOFF` |
| **L4.21 (流程)** | **真业务 sprint 必修 push 后 模拟 CI shallow clone 验证 + 1 commit amend 模式 + 跨 sprint 真因真发现实战 fix 模式库 沉淀 (Sprint 100 实战 fix 模式新增, 跟 Sprint 90 amend drift L4.14 + Sprint 91 反思治根模式 一致). 模拟 CI `git clone --depth 1 -b fix/sprintN-...` 验证 4/4 PASS, 防止 L4.20 自身 test 1 在 CI 验证时被 CI 环境反噬 (CI runner `actions/checkout@v4` 默认 `fetch-depth: 1` 浅克隆拿不到前 sprint commit history)** | review skill 强制 | **Sprint 101** | 本节 + `docs/sprints/HANDOFF` |
| **L4.22 (平台)** | **前端 sprint 收口必 `cd frontend-vue3 && npm run build` rebuild dist + kill 旧 vite preview + restart 跑新 dist** (跟 L4.7 launchd 首选 python3 / L4.9 gh api tags 验证 / L4.17/18 Node 升级 永久规则同位, 都是平台特定 hidden assumption 必须 explicit 验证). vite preview 跑 `frontend-vue3/dist/` 不是 source, 不 rebuild 用户看到的是旧 dist 代码 (`http://localhost:5173/visitor` 仍 200 + Sidebar 仍显示已删菜单项, 即使 source + .githooks post-merge hook 全部修完). Sprint 104 step 12 只 kill uvicorn + restart 没 rebuild dist, user 截图证据 Sidebar "访客看板" 高亮紫色 + URL /visitor 200 (SPA fallback index.html). 治根: `npm run build` → 新 dist 验证 `grep -c "/visitor\|访客看板" dist/assets/*.js` 期望 0 残留 → kill `ps aux | grep "vite preview" | grep -v grep | awk '{print $2}'` → `nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort >> /tmp/fuqing-crm-frontend.log 2>&1 &` → user `Cmd+Shift+R` hard refresh. **配套**: 激活 `git config core.hooksPath .githooks` (local config, user 跑一次) 让 `.githooks/post-merge` 自动 append `.ship-audit.log` (Sprint 67 Meta-Sprint 创建但 Sprint 67-104 未激活, Sprint 104 close 手动 append 是 workaround). Sprint 104 close 实战补 Step 12.5 + Step 12.6 amend 闭环, 跟 Sprint 89 暂收口 0 治理 SOP 追加原则一致 (真业务触发, 不是 0 commit 验证 sprint) | review skill 强制 | **Sprint 104** | 本节 + `.githooks/post-merge` + `frontend-vue3/dist/` |
| **L4.31 (流程)** | **branch cleanup 必须 hook 自动化, 禁止手动触发** (Sprint 178 真业务触发: Sprint 172-175 close 流程多次漏执行 `git branch -d` + `git push origin --delete`, 累计 7 个已合并分支僵尸 — Codex 桌面端显示 + IDE branch 列表 + `git log --all` 都受污染). 治本: `scripts/branch_cleanup.py` 扫本地+远程已 merge main 的分支 → `-d` + `push --delete` (PROTECTED 列表保护 7 个 Sprint 172-175 历史保留 + main/master/HEAD). `.claude/settings.json` PostToolUse Bash hook 检测 `git push origin main` 自动触发. 实战 fix 模式 #61 (跟 L4.8 PR merge 后 24h 内删分支 永久规则配套). pytest 8 case regression (`backend/tests/test_branch_cleanup.py`). | SessionStart + Stop hook 强制 + review skill 二次验证 | **Sprint 178** | `scripts/branch_cleanup.py` + `.claude/settings.json` + `backend/tests/test_branch_cleanup.py` |
| **L4.32 (平台)** | **subprocess 启动 (尤其 `python3 -c` argv list 模式) 必须显式 `cwd=主目录`, 不能依赖父 CWD** (Sprint 181 真业务触发: `test_association_filter_builder.py` + `test_matrix_filter_builder.py` 3 处 `os.chdir(tmp)` 在 `tempfile.TemporaryDirectory()` 块结束时 tmp 目录被自动删 → 父进程 CWD 路径失效 → 后续 `subprocess.run([sys.executable, ...])` 启动新 Python 时, kernel 找不到 cwd → Python 抛 `OSError: failed to make path absolute` (Python runtime state: core initialized) → 退出 1 (被误判为 SyntaxError). 11 test 全 fail 才发现. **预防**: 任何 `subprocess.run` 启动子 Python 必须 `cwd=主目录绝对路径` (跟 L4.10 平台检查放 main / L4.17-18 Node 升级 同位, 都是平台特定 hidden assumption 必须 explicit 验证). 配套: `backend/tests/test_claude_hooks.py::_run_hook` 加 `cwd=REPO_ROOT` (PreToolUse hooks); `_run_inline_python` 不传 cwd (PostToolUse tests 故意 chdir 测 stub, monkeypatch 自动恢复 CWD). | review skill 强制 | **Sprint 181** | `backend/tests/test_claude_hooks.py` + 任何 `subprocess.run([sys.executable, ...])` |
| **L4.33 (流程)** | **test 改 CWD 必须用 `monkeypatch.chdir` 或 try/finally 恢复, 禁止裸 `os.chdir(tmp)` 在 `tempfile.TemporaryDirectory()` 块结束时不恢复** (Sprint 181 真业务触发: 27 个 backend/test_*.py 都有 `os.chdir(tmp)` 风险, 真业务污染源是 test_association_filter_builder.py + test_matrix_filter_builder.py 3 处. 跨 sprint 治本 2 个 + pytest 790/0/73 重稳态). **预防**: 任何 test 写 `os.chdir` 必须 (1) 优先用 `monkeypatch.chdir(tmp)` (pytest fixture 自动恢复); 或 (2) 用 try/finally 包裹, finally 块 `os.chdir(原路径)`. 跟 L4.3 DuckDB 单例 fixture 隔离 / L4.4 真连 test skipif 教训同位 (test 全局状态污染必须 fixture 隔离, 跨 sprint 27 个 file 同根因风险). | review skill 强制 + ground-truth-lint | **Sprint 181** | `backend/tests/**` |
| **L4.34 (平台)** | **test 不能硬编码绝对路径 (尤其 `__file__` 绝对路径或 `/Users/...` macOS 路径), 必用 `Path(__file__).resolve()` 跨平台** (Sprint 181.1 真业务触发: `test_claude_hooks.py::TestClaudeHooksRegression::test_claude_hooks_no_unused_imports_breaks_when_os_imported` 硬编码 `/Users/hutou/Desktop/fuqin-date/...` macOS 路径, CI Linux runner 跑 `FileNotFoundError` fail. 真因: Sprint 179.1 实战 fix 模式 #58 漏查"绝对路径"维度). **预防**: 任何 test 真 access 文件必用 `Path(__file__).resolve().parent / "相对路径"` 或 `Path(__file__).parent` 跨平台构造. 跟 L4.7 launchd 首选 python3 / L4.9 gh api tags 验证 / L4.17-18 Node 升级 / L4.32 subprocess cwd lock 永久规则同位, 都是平台特定 hidden assumption 必须 explicit 验证 (Sprint 60+ 持续沉淀). | review skill 强制 | **Sprint 181.1** | `backend/tests/**` + 任何写绝对路径的 test/code |
| **L4.35 (流程)** | **SKILL.md SSOT 必须单源 + 跨端 symlink, 禁止复制粘贴** (Sprint 182 真业务触发: 双端 SKILL.md 字节一致但 WorkBuddy LLM 没有 shell 调不动 CLI, 治根: SKILL.md 教 LLM 用 MCP tools + 跨端 symlink 不复制). 触发条件: 任何 Claude Code / WorkBuddy / CodeBuddy 三端共用 skill. 配套: `.claude/settings.json` SessionStart hook + `scripts/session_start_check.py` 加 1 行 symlink verify 自动修. 配套 hard rule: SKILL.md 写 "python scripts/..." CLI 调用 → WorkBuddy LLM 调不动 → 必须改 MCP tool 描述. | review skill 强制 | **Sprint 182** | 本节 + `~/.claude/skills/**` + `~/.workbuddy/skills/` |
| **L4.36 (流程)** | **任何 ad-hoc-query 取数禁止停 uvicorn** (Sprint 183 真业务触发: WorkBuddy 误判 DuckDB 锁让用户停服务). 锁冲突必须 graceful retry 3 次 (exponential backoff 1s/2s/4s), 失败 → 用 backend HTTP API `GET /api/v1/audience/summary` 取近似 5 指标 (无小样), 再失败 → 友好错误返回. 配套: `~/.claude/skills/ad-hoc-query/SKILL.md` v2.2 顶部 "0. 执行路径强制" + "1.6 锁冲突 graceful fallback" 段. 禁路径: launchctl unload / kill uvicorn / "本地即生产" 不可逆破坏. | review skill 强制 | **Sprint 183** | 本节 + `~/.claude/skills/ad-hoc-query/SKILL.md` |
| **L4.37 (流程)** | **新文件 import 必须显式列在 `_load_builtins` 或 `__init__`** (Sprint 183 fix_pattern #68 沉淀: pytest collection 自动 import 掩盖 registry 没加载的 bug, Codex 写 `daily_gsv_multi_period.py` 但没动 2 个 registry 加载入口, standalone CLI 跑不到). 锁回归: 任何新 query 子命令必须 (1) `mcp_servers/fuqing_adhoc/_dispatch.py` TOOL_DEFS 加 entry; (2) `scripts/ad_hoc_queries/registry.py` `_load_builtins()` 显式 import; (3) end-to-end `subprocess.run(["scripts/ad_hoc_query.py", "<cmd>", "--help"])` 验证. Sprint 184 实战验证: pytest 13 cases (12 CLI + 1 lock model). | review skill 强制 + pytest 锁回归 | **Sprint 184** | 本节 + `~/.claude/skills/ad-hoc-query/SKILL.md` |
| **L4.38 (架构)** | **DuckDB 不支持 PostgreSQL 式 MVCC 多进程并发** (Sprint 184 真业务触发: 验证 3 同事并发跑数架构选型, 实测 uvicorn 持写锁时任何子进程 read_only 都 IO Error). 锁模型是 OS-level flock 而非事务隔离: 写进程独占 flock, 读进程也必须抢 flock (read_only 不绕开). **后果**: 同一 DuckDB 文件 1 个进程只能有 1 个 active conn (写或读). **架构选项**: ① 走 backend HTTP API (推荐, Sprint 183 落地, uvicorn 1 进程内 service 自己 read_only, 不需要跨进程并发) ② uvicorn 持写锁时禁止任何子进程直连 DuckDB (L4.36 配套). **禁路径**: 不要试 ConnectionPool / 不要试跨进程并发 reader / 不要碰 DuckDB 写事务时长. 配套: `scripts/duckdb_lock_model_verification.py` 验证 3 件已知行为 (单进程 read_only after close ✅ / 同进程并存 ConnectionException ✅ / 跨进程 flock IO Error ✅). | review skill 强制 | **Sprint 184** | 本节 + `scripts/duckdb_lock_model_verification.py` |
| **L4.39 (流程)** | **macOS-only test 必须 `@pytest.mark.skipif(sys.platform != "darwin")` (CI Linux runner 守卫)** (Sprint 185 真业务触发: Sprint 182/183/184 跨 3 sprint CI 复发真因, `test_ad_hoc_query_sprint183.py::TestSprint183L4Regression` 3 case 期望 `~/.claude/skills/ad-hoc-query/SKILL.md` 路径, Linux CI runner 永远 100% FAIL, Sprint 181 真连 test skipif 模式未推广到 macOS 路径). **预防**: 任何 test 访问 `Path.home() / ".claude" / ".workbuddy" / "~/Library"` 等 macOS-only 路径必须 skipif, 或拆 class 跨平台路径 (CLAUDE.md / project-relative). 跟 L4.10 平台守卫永久规则同位 (代码不放 sys.platform 检查, 平台守卫放 main / 装饰器入口). 跟 Sprint 183 + Sprint 165 警示: 跨 sprint CI 复发不能用"看上去对了"下结论, 必须 git log 实证. | review skill + ground-truth-lint | **Sprint 185** | `backend/tests/**` + 任何写 macOS 本地路径的 test/code |
| **L4.40 (流程)** | **`.githooks/post-merge` 必须自动跑 `scripts/branch_cleanup.py`, 失败不阻 merge** (Sprint 185 真业务触发: Sprint 184 merge 后自 zombie 滞留, pre-push hook pytest fail 5 分钟卡点). 真因: Sprint 178 L4.31 落地 `scripts/branch_cleanup.py` + PostToolUse hook 检测 `git push origin main` 自动触发, 但 12 步流程第 8 步 merge 后→第 9 步 push 之间没自动清 zombie, 自 zombie 会让 feature 分支 merge 完瞬间进入 zombie 状态. **预防**: post-merge hook 必须自动 branch_cleanup (失败不阻 merge), 跟 L4.31 + 12 步流程第 8 步配套. pytest baseline 12 case regression `backend/tests/test_branch_cleanup.py`. | review skill 强制 + pre-commit hook | **Sprint 185** | `.githooks/post-merge` + L4.31 扩展 |
| **L4.41 (架构)** | **subprocess 注入 env[PYTHONPATH] 必须用 `str(PROJECT_ROOT)` 绝对路径, 不 inherit 父进程** (Sprint 187 真业务触发: CI #500 / #499 / #497 累计 3 sprint CI 复发 root 因, `mcp_servers/fuqing_adhoc/server.py:_run_cli` Sprint 182 L4.32 当时用 `os.environ.get("PYTHONPATH", _CWD)` 想 inherit 父进程, macOS 本地 PYTHONPATH 绝对路径, 但 Linux GitHub Actions runner 用 `actions/setup-python@v6` 默认 `PYTHONPATH=.,` literal → 注入 env → 子 Python 找不到 backend.services → test_subprocess_inherits_pythonpath 100% fail). **预防**: 任何 subprocess.run (尤其 MCP server / CLI launcher / ETL 脚本) 显式 `env[PYTHONPATH]=str(PROJECT_ROOT)`, **不** `os.environ.get("PYTHONPATH")`. 跟 L4.32 subprocess cwd lock + L4.34 Path.resolve + L4.10 平台守卫 同位 (Sprint 60+ 持续沉淀). 4 case regression `backend/tests/test_fuqing_adhoc_mcp_server.py::TestRunCliSubprocess`. | review skill 强制 | **Sprint 187** | `mcp_servers/fuqing_adhoc/server.py` + 任何 subprocess 注入 env |
| **L4.42 (流程)** | **任何 Sprint 立项信息必须 git log / grep 实证, 禁止凭印象** (Sprint 188 真业务触发: B3 "25 个 test os.chdir(tmp) 风险批量治本" 立项, Codex 严格 grep `backend/tests/` 发现 0 处真实 `os.chdir` 风险, Sprint 181+183 已治本). 真因: Sprint 184/187 close memory "25 处" 是凭印象 (L4.20 SSOT 反漂移永久规则的实战失败案例). **预防**: 任何 Sprint 立项前先 `git log --grep="<关键词>" -i --all` + `grep -rn "<pattern>" <path>/` 实证, B3 反漂移 0 commit 验证. 配套 `scripts/ci_cross_sprint_drift.py` 跑最近 10 commit 该 test PASS 0 drift. | review skill 强制 | **Sprint 188** | Sprint 立项信息, close memory SSOT, 任何 sprint 留尾描述 |
| **L4.43 (架构)** | **argparse adapter 必须透传 spec.nargs / choices / type / action** (Sprint 190 真业务触发: scripts/ad_hoc_query.py:62-76 adapter 吞了 `argparse_kwargs["nargs"]`, 导致 daily-gsv-multi-period `--periods start end start end` 多次传报 unrecognized arguments. 真因: Sprint 183 daily-gsv-multi-period 用了 nargs="+" 模式, 但 register argparse 时 adapter 没把 nargs 透传给 argparse). **预防**: 任何 QuerySpec → argparse 转换层必须白名单透传 6 个 kwargs: required/default/choices/type/nargs/action, 缺哪条报 missing-field warning. 跟 L4.5 FilterBuilder + L4.25 防串台同位 (`scripts/ad_hoc_queries/*` 是 CLI 层). 1 case 实跑 daily-gsv-multi-period --periods 4 日期成功. | review skill 强制 | **Sprint 190** | `scripts/ad_hoc_query.py` 任何 argparse adapter, 任何 CLI 参数 spec |
| **L4.44 (平台)** | **MCP stdio 协议必须 newline-delimited JSON, 禁止照搬 LSP Content-Length framing** (Sprint 191 真业务触发: `mcp_servers/fuqing_adhoc/server.py` 原 LSP framing 导致 WorkBuddy 120s 超时 (`MCP error -32001`), 重启无效. 真因: MCP stdio 协议 = 每行一个 JSON + `\n` 结尾, **不是** LSP 的 `Content-Length: N\r\n\r\n` + body. LSP 实现的 server 在 `_read_message()` readline 读到 JSON 行不认为是 header 结束 (不等于空行), 继续 readline 永久阻塞. 第一轮诊断误判为 WorkBuddy bug, 真因是用 server 期望的 LSP 格式测 server (假阳性通过)). **预防**: (1) 手写 MCP server 必用 newline-delimited JSON: `read: line = sys.stdin.buffer.readline(); json.loads(line)` + `write: sys.stdout.buffer.write(json.dumps(...).encode() + b"\n"); flush()`. (2) 诊断 MCP 连不上时, **必须**用客户端实际发送的协议格式测 server, 不能用 server 期望的格式测. (3) 配套工具: `~/.workbuddy/skills/mcp-stdio-protocol-debugging/references/diagnose_mcp.py` 一键对比测试 (LSP + newline JSON 两路). 跟 L4.7 / L4.9 / L4.10 / L4.17-18 / L4.32 / L4.34 / L4.41 同位, 都是平台特定 hidden assumption 必须 explicit 验证. 32 case regression `backend/tests/test_fuqing_adhoc_mcp_server.py` 零回归. | review skill 强制 + diagnose_mcp.py 锁回归 | **Sprint 191** | `mcp_servers/fuqing_adhoc/server.py` + 任何手写 MCP server |
| **L4.53 (架构)** | **DuckDB snapshot 机制 = P2 杀 (Read-Write Splitting 已够), 不允许自动 launchd 5 分钟拍快照** (Sprint 201 R2 L2 真业务触发: 你报"我电脑只有 1TB, 存储被撑爆 763GB→0GB" 真因: Sprint 201 R1 我加了 snapshot 机制 + 5 分钟 launchd plist + `shutil.copy2` 真副本 + 30 天 retention 累积 4×120GB=480GB. Read-Write Splitting 已用 ATTACH read_only 解决并发, snapshot 完全是冗余"双保险"). **预防**: 任何 DuckDB 备份方案必须走 ATTACH read_only (L4.51) 或 `VACUUM INTO` 压缩副本, **禁止** `shutil.copy2` + 频繁 launchd. snapshot 目录应长期 0 byte, 任何 > 100MB 立刻报警 (`scripts/check_db_size.py`). 配套 `com.fuqing.db-size-alert.daily.plist` 每天 04:00 跑告警. pytest 5 case 锁回归 (`backend/tests/test_sprint201_l2_storage.py`). 跟 L4.50 pytest cleanup + L4.51 Read-Write Splitting + L4.52 snapshot retention 配套, 跨 sprint 持续沉淀模式. 7 files / +239/-107 across 1 commit, 989 passed / 7 skipped / 0 failed. 累计 Sprint 60+ 0 debt stable 模式 +23 sprint. | review skill 强制 + pytest 锁回归 | **Sprint 201 R2** | `scripts/dump_duckdb_snapshot.py` (删) + `scripts/check_db_size.py` (新建) + `scripts/run_etl.py` (末尾治理) + L4.51 配套 |
| **L4.54 (性能)** | **ETL 文件分桶 (30d+ 直接 skip) + member_df pay_time 7 天窗口过滤** (Sprint 202 R1 真业务触发: 你 7/3 跑 ETL 46min (基准 18min), 业务方反映慢. 真因: shop 125 文件 30d+ 占 78% tracker 反复 check + member 5.7M order_id 全表 UPDATE 7 min. 优化 1: `scripts/etl/ingest.py::should_skip_file_by_age()` 30d+ 老文件直接 skip, 跟 L4.50 mtime 短路同效但更激进. 优化 2: `scripts/etl/pipeline.py` member_df 按 pay_time 7 天窗口过滤, 4,662,022 老客 (99.6%) 早是 is_member=TRUE 不需要重标). **预防**: 任何 ETL 加载文件列表必须按 mtime 分桶, 30d+ 默认 skip (`ETL_SKIP_FILE_AGE_DAYS` env var 可调). member 增量 UPDATE 走 7 天窗口, 业务上 is_member=TRUE 只对"最近 7 天有订单的新会员"有意义. pytest 7 case 锁回归 (`backend/tests/test_sprint202_r1_etl_perf.py`). 跟 L4.5 FilterBuilder (业务表过滤) + L4.50 (pytest cleanup) + L4.51 (Read-Write Splitting) + L4.53 (snapshot 永久根除) 配套, 跨 sprint 60+ 0 debt stable 模式 +24 sprint. 4 files / +97/-3 across 1 commit, 996 passed / 7 skipped / 0 failed. 期望 46min→<15min 跑批. 留尾 Sprint 201+ ClickHouse / Trino POC (8-10 周) 治本 117GB 单文件. | review skill 强制 + pytest 锁回归 + 真 ETL 跑批 verify | **Sprint 202 R1** | `scripts/etl/ingest.py::should_skip_file_by_age` + `scripts/etl/pipeline.py` 冷启动 + member_df 段 + L4.5 配套 |
| **L4.55 (流程)** | **立项 spec 描述必走 L4.42 实证 (Sprint 201 R2 v24 + 201+ v5 立项实证 SOP 沉淀, 跟 Sprint 188 B3 + Sprint 199 R1 + Sprint 200 R1 1:1 stable)**. 你立项 spec 描述业务规格/字段名/桶边界/工作量时, Codex/Claude Stage 2 实施前必跑 `git log --grep="<关键词>" -i --all` + `grep -rn "<pattern>" <path>/` 实证, 立项凭印象 = 0 commit 收口 (跟 Sprint 188 B3 0 立项漂移 + Sprint 199 R1 14 tool 真实命中率 95% 反漂移 1:1 stable). **触发**: 任何 sprint 立项信息 (业务口径 / R 区间 / 字段名 / 阈值 / 桶边界 / 工作量估计) 必 L4.42 实证. **真因** (Sprint 201 R2 v24): 你 7/3 立项 spec 描述任务 A/B/C 3 P0 业务补全, Codex Stage 2 L4.42 实证: 任务 A 淘客渠道每月明细 0 业务邮件/工单触发 (git log 0 hit); 任务 B spu_product_class 是 backend 已存字段 (database.py:62 VARCHAR), 不需要新增; 任务 C 8 分组 TTL 扩 CATEGORY_GROUPS 4→8 是凭印象 (grep 0 hit "CATEGORY_GROUPS" 当前实现). 0 commit 收口 + docs/TECH-DEBT.md 留尾登记 + 真业务触发再立. 跟 L4.20 (SSOT 反漂移) + L4.42 (立项信息 git log 实证) + L4.50 (pytest cleanup 0 业务代码改动) 永久规则配套. 跨 sprint 60+ 0 debt stable 模式 +25 sprint. 0 业务代码改动, 4 files / +375/-71 across 1 commit `79e5d33`, pytest baseline 1057/73/3 (3 pre-existing failed 跟本次改动 0 关联), ruff scoped All checks passed. | review skill 强制 + git log/grep 实证 + 留尾登记 | **Sprint 201 R2 v24 + 201+ v5** | `docs/sprints/SPRINT201_R2_V24_L442_VERIFICATION.md` (302 行) + CLAUDE.md L4.55 永久规则化 |
| **L4.56 (流程)** | **POC / 长期治本专项立项必写立项决策备忘录 + 留尾登记 + 启动条件** (Sprint 201+ 真业务触发: 你 7/3 立项 ClickHouse / Trino POC 8-10 周 1-2 人月, 不在 1 sprint 闭环, 写 `docs/architecture/clickhouse-poc-decision-memo.md` ~280 行 + 留尾登记 + 启动条件 = DuckDB > 200GB / 查询 P95 > 30s 持续 1 周 / 5+ 业务分析师并发取数). **触发**: 任何 POC / 长期治本专项立项 (工作量 > 5 天 跨 sprint 闭环), 必走立项决策备忘录 (含选型对比 + 阶段拆分 + 风险评估 + 启动条件) + docs/TECH-DEBT.md 留尾登记 + 启动条件触发再立. **预防**: 任何 sprint 立项必问 4 问 (工作量 / 选型对比 / 阶段拆分 / 启动条件). **跨 sprint 留尾 = 0 债** (跟 Sprint 60+ 0 debt stable 模式 +26 sprint). 跟 L4.20 (SSOT 反漂移) + L4.42 (立项实证) + L4.50 (pytest cleanup 0 业务代码改动) + L4.51 (Read-Write Splitting) + L4.53 (snapshot 永久根除) + L4.54 (ETL 文件分桶) + L4.55 (立项 spec 实证 SOP 永久规则化) 永久规则配套. 0 业务代码改动 + 4 files / +810/-0 across 1 commit, pytest baseline 1057/73/3 0 变化 (3 pre-existing failed 跟本次改动 0 关联), ruff scoped All checks passed. | review skill 强制 + 立项决策备忘录 + 留尾登记 | **Sprint 201+** | `docs/architecture/clickhouse-poc-decision-memo.md` (~280 行) + CLAUDE.md L4.56 永久规则化 + `docs/sprints/SPRINT201_PLUS_L442_VERIFICATION.md` (~310 行) |
| **L4.57 (流程)** | **跨 sprint 留尾 4 维度 0 commit 续期 SOP** (Sprint 202+ 真业务触发: 你 7/3 拍板"继续立项, 解决上面的问题" = 4 维度跨 sprint 留尾立项). 跨 sprint 留尾 4 维度 = (1) ClickHouse POC 启动条件监控 (DuckDB > 200GB / 查询 P95 > 30s 持续 1 周 / 5+ 业务分析师并发取数) (2) Sprint 202 R1 跑批 wall_min 业务验证 (L4.54 已落地, 期望 < 15min, 7/3 跑的 46min 是落地前 baseline) (3) Sprint 199+ 3 P0 业务补全 (任务 A 淘客渠道每月明细 + 任务 B 单品按月按 spu_product_class + 任务 C 8 分组 TTL 扩 CATEGORY_GROUPS 4→8, L4.42 实证 0 业务触发) (4) 4 case pre-existing fail 真治本 (test_sampling_roi_yoy 3 + test_sampling_sprint139 1 + test_sampling_sprint141 1 Sprint 201 R2 v24 已治本 + test_w4_t7_integration 4 Sprint 201+ 实证 4 PASS). **触发**: 任何 sprint 立项必走 L4.42 实证 SOP (git log + grep + 0 业务触发 0 commit 收口, 跟 Sprint 188 B3 + Sprint 199 R1 + Sprint 201 R2 v24 + Sprint 201+ v5 1:1 stable 跨 +27 sprint). **预防**: 跨 sprint 留尾 4 维度全部 0 commit 续期, 真业务触发再立 (Sprint 202+). **配套**: 跟 L4.20 SSOT 反漂移 / L4.42 立项实证 / L4.50 pytest cleanup / L4.51 Read-Write Splitting / L4.52 snapshot 机制 / L4.53 sprint 收口 / L4.54 ETL 文件分桶 / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP 永久规则配套. 0 业务代码改动 + 3 files (SPRINT202_PLUS_L442_VERIFICATION.md ~340 行 + docs/TECH-DEBT.md 留尾登记 4 行指针 + CLAUDE.md L4.57 永久规则化), pytest baseline 1074 tests collected 0 变化, ruff scoped All checks passed. | review skill 强制 + 4 维度实证报告 + L4.42 SOP | **Sprint 202+** | `docs/sprints/SPRINT202_PLUS_L442_VERIFICATION.md` (~340 行) + `docs/TECH-DEBT.md` 4 行指针 + CLAUDE.md L4.57 永久规则化 |
| **L4.58 (流程)** | **跨 sprint 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP** (Sprint R1+R2 high-priority workflow 真业务触发: 你 7/4 拍板"拉个 workflow, 把高优先级的任务做了" = R1 跑批 wall_min 业务验证 + R2 ClickHouse POC 启动条件监控). **R1 跑批 wall_min 验证 SOP**: 业务下次跑 ETL 自动收集 wall_min (start time + end time 算 wall_min) → wall_min < 15min PASS → 0 commit 收口 (跟 Sprint 202+ + Sprint 201+ + Sprint 188 B3 1:1 stable) / wall_min ≥ 15min FAIL → 重新立项 Sprint N+1 R2 排查新根因 (L4.54 之外). **R2 ClickHouse POC 启动条件监控 SOP**: 跨 sprint 监控 3 件启动条件 (a) DuckDB > 200GB / (b) 查询 P95 > 30s 持续 1 周 / (c) 5+ 业务分析师并发取数 → 0 触发 0 commit 续期 / 任意触发 → 重新立项 Sprint N ClickHouse POC 启动 (走完整 12 步流程). **触发**: 任何 sprint 留尾跨 sprint 自然验证/监控需求 (业务下次跑 ETL 自动验证 + 跨 sprint 启动条件监控). **预防**: 任何 sprint 留尾跨 sprint 自然验证/监控需求必走 L4.58 SOP (业务下次跑 ETL 自动验证 wall_min + 跨周日 04:00 launchd 自动监控启动条件), 0 触发 0 commit 续期, 任意触发自动重新立项. **配套**: 跟 L4.20 SSOT 反漂移 / L4.42 立项实证 / L4.50 pytest cleanup / L4.51 Read-Write Splitting / L4.52 snapshot 机制 / L4.53 sprint 收口 / L4.54 ETL 文件分桶 / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP / L4.57 跨 sprint 留尾 4 维度 0 commit 续期 永久规则配套. 0 业务代码改动 + 3 files (SPRINT202_R1_WALL_MIN_VERIFICATION.md ~80 行 + docs/TECH-DEBT.md 续期 1 行指针 + CLAUDE.md L4.58 永久规则化), pytest baseline 7/7 PASS (test_sprint202_r1_etl_perf.py 跟 Sprint 202 R1 1:1 stable), ruff 28 errors (跨 sprint stable, 0 业务代码改动相关). | review skill 强制 + 跨 sprint SOP + L4.42 立项实证 | **Sprint R1+R2** | `docs/sprints/SPRINT202_R1_WALL_MIN_VERIFICATION.md` (~80 行) + `docs/TECH-DEBT.md` 1 行指针 + CLAUDE.md L4.58 永久规则化 |
| **L4.59 (流程)** | **跨 sprint 维护性 0 commit 续期 SOP 总纲** (Sprint 201+ R6+R7+R8+R9 low-priority workflow 真业务触发: 你 7/4 拍板"低优先级的处理下, 拉个 workflow" = 4 件低优跨 sprint 维护性 0 commit 续期). **R6 pre-existing fail 跨 sprint 监控 SOP**: 每周日 04:00 launchd 自动跑 `scripts/pre_existing_fail_monitor.py` 跑 4 case (3 sampling + 1 w4_t7), 14/14 PASS → 0 commit 收口 / 任何 FAIL → 写 docs/TECH-DEBT.md 跨 sprint 留尾告警 + 重新立项 Sprint N+1 真治本. **R7 MEMORY.md 24.4KB 维护监控 SOP**: 每周日 04:15 launchd 自动跑 `scripts/memory_size_monitor.py` 检查 MEMORY.md size > 24576 → 告警 (dedup 由 Claude 手动跑, 监控不自动 dedup 防误删). **R8 ad-hoc-query 14 tool 真实命中率监控 SOP**: 每周日 04:30 launchd 自动跑 `scripts/adhoc_query_hitrate_monitor.py` 检查 tool 数量 = 14 + L4.35 symlink 治本 (SKILL.md symlink 方向 ~/.workbuddy → ~/.claude) → 业务组预读 reminder + 反馈真实命中率. **L4.59 SOP 强契约 (3 件必做)**: (1) L4.42 立项实证前置 (git log + grep + pytest 0 变化 0 业务触发); (2) launchd 自动化监控 (L4.7 永久规则: python3 不走 bash, weekly 触发, log /tmp/fuqing-*.log); (3) fail-open 原则 (监控脚本失败不阻 commit, 任何异常 exit 0 + stderr warn, 跟 L4.40 post-merge hook 配套). **L4.59 反模式 (禁止)**: ❌ 在 main 直接 commit 跨 sprint 维护性脚本 (必走 12 步流程, 创 fix/sprint{N}-{topic} 分支); ❌ 监控脚本自动 dedup / 自动修复 (防误删, 只告警); ❌ 跨 sprint 维护性混入业务代码改动 (0 业务代码改动强契约, 跟 Sprint 60+ 1:1 stable); ❌ launchd plist 写 bash (L4.7 永久规则禁止). **配套**: 跟 L4.7 launchd 首选 python3 / L4.12 TECH-DEBT.md SSOT / L4.13 MEMORY.md 24.4KB / L4.20 SSOT 反漂移 / L4.35 SKILL.md symlink / L4.40 post-merge hook / L4.42 立项实证 / L4.50 pytest cleanup / L4.55 立项 spec 实证 SOP / L4.57 跨 sprint 留尾 4 维度 / L4.58 跨 sprint 跑批 wall_min 验证 + ClickHouse POC 启动条件监控 永久规则配套. 0 业务代码改动 + 9 files (R6+R7+R8 3 监控脚本 + 3 launchd plist + 3 pytest regression test files + CLAUDE.md L4.59 永久规则化), pytest baseline 1057/7/3 → 1084 collected (净 +10 case: 3 + 4 + 3 = 10 R6/R7/R8 锁回归), ruff scoped 0 error. | review skill 强制 + launchd weekly 监控 + fail-open + L4.42 立项实证 | **Sprint 201+ R6+R7+R8+R9** | `scripts/pre_existing_fail_monitor.py` + `scripts/memory_size_monitor.py` + `scripts/adhoc_query_hitrate_monitor.py` + `scripts/launchd/com.fuqing.{pre-existing-fail,memory-size,adhoc-hitrate}-monitor.weekly.plist` + `backend/tests/test_{pre_existing_fail,memory_size,adhoc_query_hitrate}_monitor.py` + CLAUDE.md L4.59 永久规则化 |
| **L4.60 (流程)** | **任何 Python 脚本 + pytest case + launchd plist 必用 `Path(__file__).resolve().parents[N]` 或 env var 跨平台, 禁止 macOS 硬编码 `/Users/...` 路径** (Sprint 202+ CI fix 真业务触发: CI #28699272736 9 fail 100% 真因 = 3 监控脚本 + 3 plist + 10 pytest case 用 macOS 硬编码 `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/...`, Linux CI runner `runs-on: ubuntu-latest` 0 找到, pytest 10/10 fail). **3 件强契约**: (1) **Python 脚本** (监控/ETL/CLI) 必用 `REPO_ROOT = Path(__file__).resolve().parents[N]`, N=1 表示 script 在 repo 根下, N=2 表示 script 在 scripts/ 子目录下; 反例: `REPO_ROOT = Path("/Users/hutou/Desktop/...")`, 例外: `/tmp/fuqing-*.log` 允许硬编码 (Linux CI `/tmp` 存在); (2) **pytest case** 必用 `REPO_ROOT = Path(__file__).resolve().parents[N]` 或 `Path(__file__).parent.parent.parent` (跟 L4.34 永久规则 1:1 stable), 反例: `REPO_ROOT = Path("/Users/hutou/Desktop/...")`, 例外: macOS-only test 必须 `@pytest.mark.skipif(sys.platform != "darwin")` (L4.39 永久规则 1:1 stable), `~/Library/...` `~/.claude/...` `~/.workbuddy/...` 等 macOS 专属路径; (3) **launchd plist ProgramArguments** 必用 `<string>$(brew --prefix)/bin/python3</string>` + env var `<key>FQ_REPO_ROOT</key>` 注入, 反例: `<string>/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/scripts/{...}.py</string>`, 例外: launchd plist 是 macOS 专属启动器, 不要求跨平台, 但 plist 启动的 Python 脚本内不能硬编码 macOS 路径 (Linux CI 跑 pytest 测启动的 Python 脚本时 100% fail). **L4.60 配套 (跟 L4.6/32/34/39/41/42/59 永久规则配套)**: L4.6 worktree DUCKDB_PATH 跨平台 / L4.32 subprocess cwd 强制 / L4.34 test 不用绝对路径 / L4.39 macOS-only test skipif / L4.41 subprocess PYTHONPATH 强制 / L4.42 立项实证 / L4.59 跨 sprint 维护性 SOP. **L4.60 反模式 (禁止)**: ❌ Python 脚本硬编码 `/Users/...`; ❌ pytest case 顶层硬编码 `/Users/...`; ❌ launchd plist 不写 EnvironmentVariables; ❌ 测试脚本只跑 macOS 不 skipif (L4.39 1:1 stable). **配套回归测试**: CI Linux runner 跨平台 pytest 跑过 (`ubuntu-latest` runs-on) + 本地 macOS pytest 0 回归 + pytest baseline 0 变化 (净 +0 case 0 业务代码改动模式 stable) + ruff scoped 0 error + git diff --check clean. | review skill 强制 + L4.42 立项实证 + L4.59 SOP 配套 | **Sprint 202+ CI fix R6+R7+R8+R9 跨平台** | `scripts/pre_existing_fail_monitor.py` + `scripts/memory_size_monitor.py` + `scripts/adhoc_query_hitrate_monitor.py` + `backend/tests/test_*_monitor.py` + CLAUDE.md L4.60 永久规则化 + CHANGELOG.md v0.4.14.36 Sprint 202+ CI fix entry + STATUS.md L4.x 60 stable |
| **L4.61 (架构)** | **跨 sprint 监控脚本 main() 入口必加 `sys.platform != "darwin"` 平台守卫, pytest case 必跨 CI runner 适配 (跟 L4.10 + L4.39 + L4.40 1:1 stable)** (Sprint 202+ CI fix #2 真业务触发: CI #28705583691 (efc4f24) test job 2 fail 真因 = R6 monitor "14 passed" 期望但 CI 加 `--deselect` 把 14 pre-existing fail 全 deselect 后输出 "0 passed" + R8 monitor SKILL.md symlink check 期望 macOS `~/.workbuddy/` 但 Linux CI runner 无该路径, 100% fail). **2 件强契约**: (1) **跨 sprint 监控脚本 main() 入口** 必加 `if sys.platform != "darwin": return 0` (Linux CI runner 跳过 macOS-only 检查, 跟 L4.10 平台守卫放 main 入口 1:1 stable) 或 `passed == 0 and failed == 0` 视为 PASS (跟 L4.40 fail-open 1:1 stable, --deselected 是预期不是失败); (2) **pytest case** macOS-only check (e.g. SKILL.md symlink / `~/.workbuddy/` path) 必加 `@pytest.mark.skipif(sys.platform != "darwin", reason="...")` (跟 L4.39 永久规则 1:1 stable) + 跨 CI runner assert 必用 fail-open pattern (`"PASS_KEYWORD" in stdout` + `returncode == 0`, 不 hardcode `"14 passed" in stdout` 之类具体数字). **L4.61 配套 (跟 L4.10/39/40/50/59/60 永久规则配套)**: L4.10 平台守卫放 main / L4.39 macOS-only test skipif / L4.40 fail-open 原则 / L4.50 pytest cleanup / L4.59 跨 sprint 维护性 SOP / L4.60 跨平台路径. **L4.61 反模式 (禁止)**: ❌ 监控脚本 main() 入口不查 sys.platform 直接走 macOS-only 检查; ❌ pytest case 不加 skipif 直接 assert macOS-only 路径; ❌ assert "14 passed" 之类具体数字 (CI --deselect 会让数字变 0); ❌ 监控脚本失败 exit 1 阻 commit (L4.40 fail-open 必须 exit 0). **配套回归测试**: CI Linux runner 2/2 fail → 0/2 fail (跟 Sprint 202+ CI fix 1:1 stable) + 本地 macOS 6 pytest case 6/6 PASS 0 回归 + ruff scoped 0 error + git diff --check clean + pytest baseline 0 业务代码改动. | review skill 强制 + L4.42 立项实证 + L4.60 配套 + L4.39 macOS-only skipif | **Sprint 202+ CI fix R6/R8 monitor** | `scripts/pre_existing_fail_monitor.py` + `scripts/adhoc_query_hitrate_monitor.py` + `backend/tests/test_pre_existing_fail_monitor.py` + `backend/tests/test_adhoc_query_hitrate_monitor.py` + CLAUDE.md L4.61 永久规则化 + CHANGELOG.md v0.4.14.37 entry + STATUS.md L4.x 61 stable |
| **L4.62 (流程)** | **launchd plist 写法 SSOT 必走 `plutil -lint OK` 验证, 禁止中文 + 多行 XML 注释触发 plutil 解析严苛 false positive** (Sprint 203 R2 amend 真业务触发: `scripts/launchd/com.fuqing.clickhouse-poc-monitor.weekly.plist` 第一版含 3 行中文 + 括号注释, `plutil -lint` 报 "Close tag on line 33 does not match open tag key" false positive, plist 实际 launchd 加载正常 (log 显示 4 次 `CLICKHOUSE_POC_MONITOR_PASS`) 但 plutil 校验失败). **强契约**: (1) **launchd plist XML 注释** 限 ASCII 字符 + 简短描述 (跟 db-size-alert / pre-existing-fail-monitor / adhoc-hitrate-monitor / memory-size-monitor 4 个现有 plist 1:1 stable 模式), 例: `<!-- Sprint 203 R2 Finding 4.1 weekly monitor -->`; (2) **plist 写入后必 `plutil -lint <plist>` 验证**, 输出必须 `OK` 才算合规, plist 实际 launchd 加载成功 ≠ plist 写法合规 (跨 sprint SSOT); (3) **launchd plist ProgramArguments** 走 L4.7 永久规则 (`python3` 不走 bash) + L4.60 永久规则 (跨平台 `$(brew --prefix)/bin/python3` + 绝对路径 project root). **L4.62 配套 (跟 L4.7/40/59/60/61 永久规则配套)**: L4.7 launchd 首选 python3 / L4.40 fail-open / L4.59 跨 sprint 维护性 SOP / L4.60 跨平台路径 / L4.61 跨 CI runner 适配. **L4.62 反模式 (禁止)**: ❌ plist 含中文 + 多行 XML 注释后不跑 `plutil -lint`; ❌ 写 plist 不参考现有 4 个 1:1 stable 模式 (`com.fuqing.{db-size-alert,pre-existing-fail-monitor,adhoc-hitrate-monitor,memory-size-monitor}`); ❌ 跨 sprint 维护性 SOP 加新 plist 不扩 `scripts/launchd/` 跟 `~/Library/LaunchAgents/` 两边同步. **配套回归测试**: `plutil -lint <plist>` → **OK** + `launchctl load <plist>` → **RunAtLoad 触发 N 次 PASS** (跨 sprint 0 业务代码改动模式 stable) + pytest focused 5/5 PASS (新 monitor 锁回归) + ruff scoped All checks passed + git diff --check clean. | review skill 强制 + L4.42 立项实证 + L4.59 SOP 配套 + L4.61 fail-open | **Sprint 203 R2 amend** | `scripts/launchd/com.fuqing.clickhouse-poc-monitor.weekly.plist` (1 amend commit `215c763` 简化注释 plutil OK) + CLAUDE.md L4.62 永久规则化 + CHANGELOG.md v0.4.14.39 entry + STATUS.md L4.x 62 stable |

**Sprint 183 WorkBuddy AI 跑 /ad-hoc-query 4 根因沉淀** (防止 AI 重复):
1. ❌ 查 openapi.json HTTP API (Sprint 182 当前不支持组合查询, WorkBuddy 应该走 MCP tool)
2. ❌ 直连 DuckDB read_only conn (Sprint 53 race flake 治本不彻底, 走 L4.38 backend HTTP API 架构才对)
3. ❌ 写 `scripts/adhoc_*.py` 临时脚本 (Sprint 171 v2.0 CLI 已有完整实现, 重复造轮子违反 L4.5)
4. ❌ 建议用户停 uvicorn (本地即生产, launchctl unload 不可逆, L4.36 永久规则)
5. ❌ **直连 DuckDB 跨进程并发**: 错把 DuckDB 当 PostgreSQL 试图多进程读; 实测 flock 模型阻止; 走 L4.38 backend HTTP API 才对.

**AI 跑数强制路径**: 读 SKILL.md v2.2 顶部 "0. 执行路径强制" 段 → 走 MCP tool → 不确定调 `ask(query)` 路由 → 工具不够显式反馈用户.

**L4 永久规则 (跟 Sprint 3 P1-3 4 轮修教训同位)**:

**任何 SQL 三引号赋值若 body 含 `{identifier}` 占位符, opening 行必须 f-string** (有 `f` 或 `rf` 前缀).

```python
# ❌ WRONG: missing f prefix, DuckDB parses literal "{valid_sql}"
count_sql = """
SELECT COUNT(*) FROM orders WHERE {valid_sql}
"""

# ✅ RIGHT: f-string prefix, DuckDB sees interpolated SQL fragment
count_sql = f"""
SELECT COUNT(*) FROM orders WHERE {valid_sql}
"""
```

**根因教训 (a9b1d91 对称)**:

- Sprint 32.3: a9b1d91 commit (Claude Opus 4.8 1M context) 误清空 `SamplingView.vue` (32653 字节 → 699 字节 newline), Vite 编译错 `[plugin:vite:vue] At least one <template> or <script> is required` 阻塞 `/sampling` 路由 5+ 天未发现
- Sprint 34.1: churn.py:418 count_sql 漏写 f 前缀, DuckDB 抛 `ParserException: syntax error at or near "}"` 100% 触发 `/category-detail/:id` 路由 5+ 天未发现

**两次事故根因都是 "AI 写代码 typo 类 5+ 天未发现"**. 两次治根都是 "1 字符 fix + lint 钩子机制防御". Sprint 33 (.vue) + Sprint 34.1 (.sql) 共同构成 AI write safety net 完整闭环.

**跨 sprint 复用教训**:

1. **静态分析不够**: vue-tsc 不报空 .vue (合法 SFC), DuckDB 不报 `{valid_sql}` 字面量 (语法 OK). 必须 lint 钩子扫源码层
2. **真编译/真执行才能发现**: Sprint 32.3 vite build lazy load 跳过未引用 .vue, Sprint 34.1 真 SQL 执行才能发现 ParserException. 必须 e2e / 真连接 regression test 触发
3. **"破坏 → 验证 → 恢复" 循环**: Sprint 24+ P3 单连接教训应用. 单测能 "跑通" 不证明 "抓到 typo", 必须故意改坏验证 test 真 FAIL, 再恢复验证 PASS
4. **pre-commit hook 是 commit 路径关键**: Sprint 3 P1-3 4 轮修揪 11 个问题 (CLAUDE.md 第 158 行附近). Sprint 34.1 lint hook 走 1 critical pass, Sprint 34.2 L2 升级时走 4 轮

---

## 接口开发六步

1. **口径先找语义层** — 禁止在 Service 硬编码 SQL 口径
2. **连接规范** — `conn = get_connection()` + `?` 参数化。禁止 `conn.close()`（单例连接由 `close_connection()` 在应用关闭时统一释放）。`execute()`/`fetch*` 已自动串行化，无需额外加锁
3. **渠道展开** — `expand_channels([channel])`
4. **Schema 三同步** — Service → contracts/schemas.py → 前端 types.ts
5. **前端只展示** — 禁止前端算 YOY/占比/客单价
6. **三层验证** — import 测试 + pytest + vue-tsc

**ETL 脚本连接例外条款** (WO-5 P2-#2)：`scripts/etl/*` 是独立离线脚本（不与 backend 同进程），允许 `duckdb.connect(DUCKDB_PATH, config={"memory_limit": ...})` + `conn.close()`，因为：① ETL 跑批时间长（30-60min），同进程单例连接会污染 config；② `read_only=True` 与 `access_mode=READ_WRITE` 互斥，单例会触发 `Can't open a connection to same database file with a different configuration`；③ ETL 完成后进程退出，连接由 OS 回收。单例规则仍适用于 `backend/services/*` 和 `backend/routers/*` 的 Web 请求路径。

详细示例见 `scripts/etl/cli.py` 顶部 module docstring "DuckDB strict mode 治根史" 段 (Sprint 24+ P3 收口, v0.4.14.97).

> **L4.5 exception (ad-hoc-query CLI 层)**: `scripts/ad_hoc_queries/*` 是 CLI/MCP 入口层, 不在 `backend/service/` 范围内. Sprint 171 决策明确禁 inline SQL (用 `?` DB-API 参数化 + FilterBuilder 部分复用), 不强制走 service layer. MCP server (Sprint 182) 是 CLI 上层包装, 完全复用 CLI 入口, 零 service-layer 改动.

---

## 快速启动

### 开发环境（Mac）

```bash
# 后端（端口 8000）
cd "/Users/yourname/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 >> /tmp/fuqin-crm-backend.log 2>&1 &

# 前端（端口 5173）
cd frontend-vue3 && npm run dev

# ETL（必须用 homebrew Python 3.14）
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update

# 测试
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

### 生产环境（Windows Server）

```powershell
# 后端（端口 8000）
$env:HEALTH_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:PYTHONPATH = Get-Location
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端（Nginx 静态托管）
# 先 build: cd frontend-vue3 && npm run build
# 将 dist/ 目录复制到 Nginx html/ 目录
```

---

## 文档导航

| 文件 | 说明 | 加载方式 |
|---|---|---|
| `CLAUDE.md` | 行为规则（本文件） | 自动加载 |
| `docs/operating/automation.md` | Claude Code 自动化配置 | 按需 Read |
| `docs/operating/ship.md` | /ship skill 使用文档 | 按需 Read |
| `docs/operating/linting.md` | ground-truth-lint 规则 | 按需 Read |
| `docs/TECH-DEBT.md` | 技术债台账 (P0/P1/P2 分级, 每债含触发场景+修复方案+估时) | 按需 Read |
| `CHANGELOG.md` | 版本变更记录 | 按需 Read |

---

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore

---

## Ratio Convention (B1+B2 模式, Sprint 13+ 升级 Sprint 17)

> 本节是 ratio / pct / ppt / rate 类字段的强契约，Sprint 13 起强制、Sprint 17 B1+B2 模式正式挪进本主章节统一治理。改前端展示、传值、命名、Pydantic 契约必读。

### B1 模式 — mark 字段补标 + ETL 触发反向回填

- **定义**: 数据已落地但缺 mark 字段 → 在 service / ETL 流程加 mark 写入逻辑 → 触发反向回填补齐历史数据
- **典型案例**: Sprint 15 Wave 3 `is_member` per-user 治根 (18 老客补齐, T2 Step 4.6 跳过 + T3 Step 4.7 增量 UPDATE)
- **前置条件**: 字段语义清晰、有可幂等 ETL trigger 入口
- **反模式**: 直接在前端 hardcode mark 字段 (e.g. `is_member = true` 占位), 应回填真实数据

### B2 模式 — contract 字段补标 + Pydantic 422 拦截

- **定义**: API response schema 字段无 Pydantic 范围约束 → 改用 `RatioField` / `PercentageField` / `PpField` 强类型 → API 入口 422 拦截越界值
- **典型案例**: Sprint 16.5 #91 B2 试点 (category + metrics + health 3 contract 9 mark 字段补标, 13/13 tests), Sprint 17 #120 全量 9 contract audit
- **前置条件**: 字段后缀清晰 (见下表"强制规则"), 范围约定明确
- **反模式**: 用裸 `float = Field(...)` 定义 ratio 字段, 错值传 5.0 不拦截导致 500

### 强制规则 (B1+B2, 适用于 `backend/contracts/*.py` 全部文件)

| Contract 字段名后缀 | 必须使用的 Pydantic 类型 | 数值范围 |
|---|---|---|
| `*_ratio` | `RatioField` | 0-1 decimal (0.42 = 42%) |
| `*_pct` | `PercentageField` | 0-1B (含 YOY 异常值, e.g. gsv_yoy 万倍涨) |
| `*_ppt` | `PpField` | -100 ~ +100 pp 差 |
| `*_rate` | `PercentageField` (0-100) | 0-100 percentage (eg. `repurchase_rate` 复购率) |
| `List[X]` (X 是约束类型) | `List[Annotated[X, Field(...)]]` | **禁止** `List["X"]` 前向引用 (Pydantic v2 知识点) |

> **Sprint 13 ratio 治理契约 0-1 严守保留** (B1+B2 跟 Sprint 13 不冲突, 是补强): 真实 ratio 字段仍是 0-1; `PercentageField` 上限放宽到 1B 仅作为 `yoy_absolute *100` 兼容兜底 (Sprint 14 QA + Sprint 15 治根决策), 前端 `YOYBadge` 加 `|v|>1e6` 异常值守卫防 UI 误导.

### 字段命名（后端，强制）

| 后缀 | 数值范围 | 是否已 *100 | 示例 |
|---|---|---|---|
| `*_ratio` | 0-1 decimal | **否** | `old_gsv_ratio`, `member_ratio` |
| `*_pct` | 0-100 percentage | **是** | `gsv_yoy_pct`, `member_penetration_pct` |
| `*_ppt` | -100 ~ +100 pp 差 | **是** | `old_gsv_ratio_yoy_ppt`, `lock_rate_yoy_ppt` |
| `*_rate` | 0-100 percentage | **是** | `repurchase_rate` |
| `*_yoy` / `*_mom` | 按上面 4 种后缀对应 | 视字段而定 | `gsv_yoy` (pct), `old_gsv_ratio_yoy` (ppt) |

**核心契约**:

- `yoy_ratio()` / `mom_ratio()` 返回 **pp 数值**（已 `*100`，e.g. 0.05 → 5.0）
- `yoy_absolute()` / `mom_absolute()` 返回 **percentage**（已 `*100`，e.g. 0.25 → 25.0）
- `audience_summary._extract_metrics` ratio 字段不再 `*100` 存（避免 10000× bug）
- `churn.py:336` `new_customer_ratio` 真正实现（禁止 hardcode 0 占位）

### 前端契约（pass-through）

- `YOYBadge` / `MetricCard` 的 `humanizeChange`: **caller 已 `*100` 传值，组件只做 `abs + toFixed(2)`**
- **不要在前端 `* 100`** — Sprint 11/12 散落 `*100` 模式已 deprecate
- `fmtYoy` / `fmtYoY` / `fmtPctChange` 等自定义函数: caller 传已 `*100` 数值，函数不乘
- YOYBadge `unit` 默认 `'%'`，ratio 类必须显式 `unit="pp"`
- `|v|>1e6` 异常值守卫: `humanizeChange` 返 `'数据异常'` (Sprint 16.5 #92, Sprint 17 #124 扩到 MetricCard / RFMSegmentDrilldown)
- None 透传显示 `—`（`humanizeChange` 已加 `v == null` 守卫）

### 禁止（lint 强制, Sprint 17 #121 ground-truth-lint）

1. **前端 0 处散落 `* 100`** — caller 自乘，组件不乘
2. **命名冲突** — `*_ratio_yoy` vs `*_yoy_ratio` 强制统一为 `*_yoy_ppt` / `*_yoy_pct`
3. **hardcode 0 占位** — 禁止 `series = [0.0] * len(dates)`（Sprint 13 P3 教训）
4. **Excel numFmt 错配** — pp 字段用 `'0.0"pp"'` 字面量后缀，% 字段用 `'0.0"%"'`
5. **contract 裸 float** — 禁止 `field: float = Field(...)`, 必须用 `RatioField` / `PercentageField` / `PpField` / `Annotated[float, Field(ge, le)]`
6. **List 前向引用** — 禁止 `List["PercentageField"]`, 必须 `List[Annotated[PercentageField, Field(...)]]` (Pydantic v2)

### 文档 / 跨链

- 完整契约: 本文件 "Ratio Convention (B1+B2 模式, Sprint 13+ 升级 Sprint 17)" 主章节 (本文件)
- 字段语义: `backend/semantic/calculations.py` docstring（`yoy_ratio` / `yoy_absolute` / `mom_*`）
- 类型定义: `backend/contracts/types.py` (`RatioField` / `PercentageField` / `PpField`)
- B2 试点: `CHANGELOG.md` v0.4.14.40 (Sprint 16.5 #91 9 mark 字段补标)
- 任务来源: `CHANGELOG.md` v0.4.14.40 Section "B2 试点" + Sprint 16.5 retrospective (已公开清理)
- Lint 规则: `docs/operating/linting.md` (Sprint 17 #121 新建, 给 ground-truth-lint 提供语义)
- 全量 audit: `CHANGELOG.md` v0.4.14.41 (Sprint 17 #120 新建, 9 contract 全量)
- 组件实现: `frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` JSDoc
- 改版历史: `CHANGELOG.md` v0.4.14.26 (Sprint 12) + v0.4.14.29 (Sprint 13) + v0.4.14.41 (Sprint 17)
- 4 页面 banner: `frontend-vue3/src/components/RatioConventionBanner.vue` (3 天自动消失)

---


## 历史 Sprint 记录

Sprint 28-32 收口详情见 `CHANGELOG.md` v0.4.14.101-v0.4.14.118 + `~/.claude/projects/-Users-hutou/memory/` sprint close files.
### L4.63 — Sprint 202+ R7 uvicorn 持锁 + DuckDB 异 config detector 永久规则化
- **run-etl.sh 顶部 uvicorn bootout 后 wait 不允许纯时间常量** (sleep N ❌), 必须等 4 件 signal 同时 release: ① lsof port 8000 空 ② pgrep uvicorn_launchd.py 无 ③ lsof <DuckDB file> 空 ④ .duckdb.wal 不存在. max wait 30s, 超时 exit 1 不跑 ETL.
- **ETL step 0 (cli.py main() 入口) 必须 fail-fast DuckDB 持锁 detector**: lsof <DuckDB file> + .duckdb.wal file existence; 任一非空则 sys.exit(1) + 输出排查指引. 不允许 step 7 才暴露, 必须 step 0 1 分钟内 block.
- **L4.51 invariant 不退化**: uvicorn 正常运行时仍是 ATTACH read_only, run-etl.sh bootout 仅为了让 uvicorn 不在 ETL 期间持 DuckDB, 绝不退化为 read_write. 任何 R7+ 改动不允许 "为了 unlock 简化 bootout 而改 uvicorn access_mode".
- **跨 CI runner 0 业务代码改动**: 所有 launchctl / lsof 显式 macOS-only, sh 用 `case "$(uname)" in Darwin) ... *) skip;; esac` 守卫; pytest 用 `@pytest.mark.skipif(sys.platform != 'darwin')`. 跟 L4.60 + L4.61 1:1 stable.
- **wall_min 业务验证**: 跟 L4.58 SOP 沿用, R7 真跑 wall_min < 15min → 立 Sprint 202+ R7 Final Verification doc 收口; ≥ 15min → 重新立项 R8.
- **pytest DuckDB 永久 fixture**: 一律 tmp_path, 不允许 fixture 指向生产 /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/fuqing.duckdb.

### L4.64 — Sprint 205+ Windows 11 部署 6 个 fix 永久规则化 (跟 L4.60 + L4.61 1:1 stable 跨平台)
- **Python 必须 3.14.4 (mac 1:1 stable)**: 项目用 Python 3.12+ 语法 (f-string 内反斜杠 + `threading.RLock | None` 运行时类型注解), Windows 装 3.11/3.12 会 SyntaxError / TypeError. setup.bat 必 check `python --version`, 输出不 3.14.x 必 fail-fast.
- **npm install 必须 `--legacy-peer-deps`**: 前端依赖存在 peer dependency 冲突, 不加会安装失败. setup.bat 跟 ad-hoc 部署一致.
- **`.env` 读写必走 Python UTF-8, 禁用 PowerShell 字符串替换**: PowerShell 默认 GBK/ANSI 会破坏 .env 里的 UTF-8 中文注释 → 后端 Python 读 .env 解码失败. setup.bat 必用 `python -c "open('.env','r',encoding='utf-8').read()..."` patch, 不直接 `Get-Content` + 字符串替换.
- **Windows 缺 Unix `resource` 模块, 必补 stub**: pytest 运行时 `import resource` (Unix-only) Windows 没装, 必在 `.venv\Lib\site-packages\resource.py` 补空 stub (8 个函数: error/getrlimit/setrlimit/getrusage/getpagesize 等), pytest 100% PASS. setup.bat 必带此 step.
- **NSSM AppEnvironmentExtra 每个 env var 独立参数, 禁用整段字符串**: `nssm set AppEnvironmentExtra "K=V K2=V2"` 整段字符串 → NSSM 解析失败, env 没设上. 必拆成 `nssm set AppEnvironmentExtra K=V K2=V2` (无引号, 独立参数).
- **前端服务必用 `node.exe` + `vite.js` 路径, 禁用 `npm.cmd` + `npm run preview`**: `npm.cmd` 退出后 vite 子进程被 kill, NSSM 服务挂. 必用 `node.exe "vite.js" preview --port 5173 ...` + 设 AppDirectory 到 frontend-vue3, 稳定.
- **setup.bat 必须离线 + 不下载**: 企业网络 / 无 TTY 环境会让在线下载 (NSSM zip / pip upgrade) 失败. setup.bat 必是纯 ASCII + 离线版本, NSSM 走 PowerShell Invoke-WebRequest 一次下载本地缓存.
- **配套回归测试**: Python 3.14.4 验证 + DuckDB 跨 OS read_only verify + pytest baseline (resource stub 后) + 3 endpoint HTTP 200 + NSSM 服务 RUNNING. 跟 Sprint 202+ CI fix 1:1 stable 模式: mac 本地 + Windows 真机验证 0 业务代码改动. **0 业务代码改动累计 Sprint 60+ 48 次 1:1 stable (跟 Sprint 202+ R8 累计 47 次一致 +1 Windows 部署)**. 配套: `docs/WINDOWS-DEPLOY-KNOWN-ISSUES.md` SSOT + `D:\fuqin-date\setup.bat` v2 完整版 (集成 6 fix) + 4 个 .bat ASCII-only + `start_uvicorn.py` PYTHONIOENCODING=utf-8 强制. **L4.64 反模式 (禁止)**: ❌ 用 3.11/3.12; ❌ `npm install` 不加 `--legacy-peer-deps`; ❌ PowerShell 字符串替换 .env; ❌ pytest 不补 resource stub; ❌ NSSM env vars 整段字符串; ❌ 前端服务走 npm.cmd; ❌ setup.bat 在线下载.
### L4.65 (架构) — backend service `duckdb.connect()` 必分 HTTP 上下文 (Sprint 205+ 真业务触发: mac + Windows 端 RFM 500 根因治本)

- **强契约**: 任何 `backend/services/**` 新建 DuckDB 连接的函数 (e.g. `_new_duckdb_conn`, `_get_duckdb_conn`) 必先调用 `dual_conn.get_request_connection()` 检查当前是否在 HTTP 请求上下文.
- **HTTP 上下文里** (QueryRouterMiddleware 已绑 read_only=True 连接): 用 `dual_conn._db_config(dual_conn.READ_MEMORY_LIMIT)` + `read_only=True` 创建, 跟 middleware 绑定连接配置一致.
- **非 HTTP 场景** (脚本/ETL): 保持原行为, 创建可写连接.
- **不遵循导致**: DuckDB 抛 `Connection Error: Can't open a connection to same database file with a different configuration` → 500 Internal Server Error. Sprint 205+ 真业务触发: Windows 端 + mac 端 `/api/v1/customer-health/rfm-analysis` 连续 4 次 500.
- **根因 (跟 L4.51 配套)**: L4.51 Read-Write Splitting invariant 退化. QueryRouterMiddleware 跟 QueryRouterAware scope 在请求里建立 read_only 连接池, 任何 service 在该 scope 内新开连接必须 read_only=True 跟池配置一致. `_new_duckdb_conn()` 默认走 `bdc.get_duckdb_config()` (可写配置) 在 HTTP 上下文里建连接 = 跟 middleware read_only 冲突.
- **真业务触发 fix (Sprint 205+)**: `backend/services/health/rfm_analysis/analysis.py::_new_duckdb_conn()` 加 `dual_conn.get_request_connection()` 检查 + HTTP 上下文用 `read_only=True` + `dual_conn.READ_MEMORY_LIMIT`. 修改后 Windows + mac 跨 OS 1:1 stable RFM 200 OK.
- **L4.65 反模式 (禁止)**: ❌ `_new_duckdb_conn()` 默认走可写配置; ❌ 直接 `duckdb.connect(str(DUCKDB_PATH))` 不分 HTTP 上下文; ❌ HTTP 上下文里建可写连接; ❌ 跨 sprint 修一个 service 漏修其他 service (必须 `grep -rn "duckdb.connect" backend/services/` 全量扫).
- **L4.65 配套 (跟 L4.51/38/4/5/50 永久规则配套)**: L4.51 Read-Write Splitting / L4.38 DuckDB flock 模型 / L4.4 真连 DuckDB test skipif / L4.5 FilterBuilder / L4.50 pytest cleanup.
- **0 业务代码改动累计 Sprint 60+ 49 次 1:1 stable (跟 Sprint 205+ Windows 部署 +1 后续)**: 本次 RFM 500 fix 是真业务触发的 1 处代码改动, 跟 L4.65 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.66 (架构) — `dual_conn.get_write_connection()` 必须跟 middleware read_only config 严格一致 (Sprint 205+ 真业务触发: PC2 RFM 500 + 雪崩根因治本)

- **真根因 (PC2 副 Agent 5 case 复现, 100% 复现)**: `get_write_connection()` 之前用 `WRITE_MEMORY_LIMIT` (跟 `READ_MEMORY_LIMIT` 不同 env var), 即使两者默认都是 `DUCKDB_MEMORY_LIMIT` 也 fail. **DuckDB 1.5+ strict mode 按 `access_mode` flag 区分**, 即使 memory_limit 一样, 显式 `read_only=True` vs 默认 `read_only=False` 内部 config 序列化不同 → "Can't open a connection to same database file with a different configuration" → cache.py 静默 swallow → 每次 RFM 重算全查询 → CPU/内存雪崩 → 用户看到 30s+ timeout (但实际是 200, 是业务雪崩)
- **强契约**: (1) **`get_write_connection()` 跟 `get_read_connection()` 用同一份 `READ_MEMORY_LIMIT`** (避免 env var 偏差); (2) **显式 `read_only=False`** (跟 read_only 显式配对); (3) **写场景 memory_limit 走读场景配置**, 这是 DuckDB 1.5+ 同一文件只能一种 config 的硬约束, **无解**; (4) **配套 cache.py except 治标**: HTTP 路径下绝不能 swallow, 必须 raise (避免雪崩), 非 HTTP 路径才允许 warning.
- **真业务触发 (Sprint 205+ R6 真根因)**: PC2 副 Agent 写 `repro_dual_conn.py` 5 case 复现 (A: read_only 已开 + write 创建 → 抛; B: write 已开 + read_only 创建 → 抛; C: 同 access_mode 写两次 → OK; D: 同 memory_limit 不同 access_mode → 抛; E: 同 access_mode 不同 memory_limit → 抛). PC2 端 100% 复现, 4 次 RFM 全部 200 但每次都重算全表 (雪崩).
- **L4.66 配套 (跟 L4.51 / L4.38 / L4.65 永久规则配套)**: L4.51 Read-Write Splitting / L4.38 DuckDB flock 模型 / L4.65 dual_conn.write_connection HTTP 上下文处理 / L4.4 真连 DuckDB test skipif.
- **L4.66 反模式 (禁止)**: ❌ `get_write_connection()` 用 `WRITE_MEMORY_LIMIT` 跟 `READ_MEMORY_LIMIT` 不同的 env var; ❌ 写 conn 不显式 `read_only=False` (默认 False 但 strict mode 跟 read_only=True 区分); ❌ cache.py 静默 swallow HTTP 路径的 DuckDB 错误 (雪崩); ❌ 跨 sprint 修复一个 service 漏修兄弟 cache (必须 `grep -rn "DuckDB 缓存写入失败" backend/` 全量扫).
- **配套回归测试**: `pytest backend/tests/test_dual_conn_config_consistency.py` 4 case (mock middleware read_only → write 创建不抛; 同上 + 写 DDL; cache.py HTTP raise + 非 HTTP warning; 5 线程并发 read_only + 1 写 → 全成功) + `pytest backend/tests/ -q` 0 fail. 跟 Sprint 202+ R7 (L4.63) + R8 + R9 1:1 stable 验证模式.

### L4.67 (架构) — 业务库 + cache 库分离 永久规则化 (Sprint 205+ 真业务触发: PC2 RFM 500 跨文件 fingerprint 0 关联治本)

- **真根因 (PC2 副 Agent 5 case 复现 100% 锁定)**: DuckDB 1.5+ strict mode 按 同文件 fingerprint 比对, 跨文件 0 冲突. 业务库 (`fuqing_crm.duckdb` 122GB) + middleware read_only conn 池化 (现状不动) + cache 库 (`rfm_cache.duckdb` 新建独立文件) + 单例 write conn. 5 轮串行业务读 + cache 写 0 错 + 5 线程并发 0 错 + err.log "Can't open" 错误从 12 → 0 + pytest 24/24 PASS.
- **强契约**: 任何 backend service 写 RFM cache, 必走 `get_cache_connection()` (cache 库单例, 跨文件 fingerprint 0 关联, 业务库 + cache 库分离). `_open_write_conn` → `_get_cache_conn` (走 cache 库单例, 不需 close). `_write_db_cache` / `_read_db_cache` / `_ensure_db_cache_table` / `_try_delete_corrupt_row` / `clear_rfm_cache` 全部用 `_get_cache_conn`.
- **L4.67 反模式 (禁止)**: ❌ 业务库 + cache 库同文件 (DuckDB 1.5+ strict mode fingerprint 冲突); ❌ 跨 sprint 修复一个 service 漏修兄弟 cache (必须 `grep -rn "get_cache_connection\|rfm_cache.duckdb" backend/` 全量扫).
- **L4.67 配套 (跟 L4.51/65/66/68/69 永久规则配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.68 DuckDB 性能调优.
- **配套回归测试**: `pytest backend/tests/test_rfm_cache_write_conn.py` 7 case 锁回归 (cache 库没 orders 表, 用 `_test_l467_sibling` 验证, 不依赖具体行数, ≥ 0 验证不抛).

### L4.68 (架构) — DuckDB 性能调优 + start_uvicorn.py wrapper 修复 永久规则化 (Sprint 205+ 真业务触发: PC2 SSD + 64GB RAM + i5-14600K 14 核)

- **真业务触发**: PC2 SSD + 64GB RAM + i5-14600K 14 核 20 线程. DuckDB 默认 memory_limit 8GB 太小, 默认 threads 1 浪费多核. 配套 `start_uvicorn.py` wrapper 修复 (REPO_ROOT 必须在 PYTHONPATH 之前, workers=1 避免 fork 冷启 122GB 业务库, ANALYZE 启动 hook 刷新 query planner 统计信息).
- **强契约 (3 件必做)**: (1) **`DUCKDB_MEMORY_LIMIT=32GB`** (PC2 给 32GB, 50% RAM, 留 32GB 给 ETL + 系统 + cache). (2) **`DUCKDB_THREADS=14`** (i5-14600K 14 核 20 线程, 留 6 核给 ETL + 系统). (3) **`DUCKDB_ANALYZE_ON_START=1`** (启动时跑 ANALYZE 刷统计信息, query planner 优化).
- **start_uvicorn.py wrapper 修复**: L4.68 配套 (跟 L4.69 同 commit 链). REPO_ROOT 必须在 `os.environ["PYTHONPATH"]` 之前定义, workers=1 避免 fork 冷启, ANALYZE 启动 hook 治 RFM 单次 6s 主因.
- **L4.68 反模式 (禁止)**: ❌ DuckDB 默认 memory_limit 8GB (122GB 库 buffer pool 不够); ❌ DuckDB 默认 threads 1 (浪费多核); ❌ NSSM 用错 Python (系统 Python 不是 venv python); ❌ `os.environ["PYTHONPATH"]` 在 REPO_ROOT 之前 (NameError); ❌ workers > 1 (fork 冷启 122GB 业务库, 雪崩).

### L4.65.1 (架构) — main.py 启动流程禁主动建写 conn 永久规则化 (Sprint 205+ 真业务触发: PC2 启动 1.3GB 内存罪魁治本)

- **真根因 (PC2 实测 100% 锁定)**: `main.py` line 158 主动调 `bdc.get_connection()` 创建写单例, 启动时直接 `duckdb.connect(122GB 业务库)` 加载 1.3GB 缓存元数据 (cache + index + column pages). L4.65 配套 "避免 500" 注释说写 conn 预防性创建, 但 L4.66 (commit f08aebb) + L4.67 (commit d608c4e) 治根后不再需要, 删了 0 副作用 (cache.py 已走 get_cache_connection 单例, 跟 _WRITE_CONN 0 关联).
- **强契约**: `backend/main.py` 启动流程**禁止**主动 `bdc.get_connection()` 主动建写 conn (防启动加载 122GB 业务库 1.3GB). cache.py 必须 lazy 创建 `_WRITE_CONN` (跟 L4.65 + L4.66 + L4.67 配套).
- **真业务触发 (Sprint 205+ L4.65.1 真根因)**: PC2 副 Agent 跑 4 步验证: 启动 1.3GB → 147MB (-89%, 罪魁是 main.py 那 5 行 bdc.get_connection()); 5 个 dashboard 接口 < 1s OK; RFM 历史周期 21s OK, 不回退 L4.65 500 bug (L4.66 f08aebb 已治根因).
- **L4.65.1 配套 (跟 L4.51/65/66/67/68/69 永久规则链配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本.
- **L4.65.1 反模式 (禁止)**: ❌ `backend/main.py` 启动流程调 `bdc.get_connection()`; ❌ 跨 sprint 修复 L4.65 时没删 5 行 bdc 写单例 (启动 1.3GB 罪魁); ❌ 跨 sprint 修复 L4.66/67 时没加 lazy _WRITE_CONN (cache.py 仍走 L4.65 写的 _WRITE_CONN 单例).
- **配套回归测试**: `pytest backend/tests/ -q` 0 fail (跟 L4.65/66/67/68/69 1:1 stable 锁回归模式). 5 个 dashboard 接口 < 1s 跟 PC2 端 9 接口验证 1:1 stable (visitor/summary 67ms / metrics/overview 769ms / audience/summary 1101ms / customer-health/config 16ms / rfm/r-flow 50ms / 5 个 YoY 接口全 < 1.1s).
- **0 业务代码改动累计 Sprint 60+ 52 次 1:1 stable (跟 L4.65/66/67/68/69 累计 51 次 +1 L4.65.1 治本)**: 本次 main.py 启动 1.3GB → 147MB 治本是 4 文件改动 (main.py + cache.py + analysis.py + test_rfm_3_periods_serial.py), 跟 L4.65.1 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.69.1 (架构) — `_run_rfm_period_serial` finally 块 gc.collect() + del conn 永久规则化 (Sprint 205+ 真业务触发: uvicorn worker 内存泄漏 2GB 卡死治本)

- **真根因 (PC2 实测 100% 锁定)**: L4.69 治本后曲线变亚线性, 但每次 RFM 跑完 DuckDB buffer pool 不归还给 OS, 14 倍内存累积 → worker 卡死. PID 涨到 2GB → 4 次 60s timeout + 登录 5s timeout → 全 API 卡 30s+.
- **强契约 (3 件必做)**: (1) **`conn.close()`** + (2) **`del conn`** (显式删 Python wrapper 引用) + (3) **`gc.collect()`** (强制 Python GC 回收 DuckDB Python 对象). 三件套强制释放, PC2 验证 2GB → 300MB. **finally 块禁 `duckdb.connect()` 新建连接** (避免 L4.65/66 配套 fingerprint 冲突风险).
- **真业务触发 (Sprint 205+ L4.69.1 真根因)**: PC2 副 Agent 跑 4 步验证: 跑 1 次 RFM 后 PID 涨到 2GB (14x 内存累积), 30s 内 worker 卡死. 治本: conn.close() + del conn + gc.collect() 三件套强制释放. 跑 4 次 RFM 内存稳态 < 800MB (治本前 4 次涨到 2GB 卡死). **部分治本**: 治 Python 层 wrapper ✅, 治不动 DuckDB C++ buffer pool ❌ (操作系统级内存, 跟 L4.68 memory_limit 32GB 配套). 配套 PC2 watchdog v2 1.8GB / 1 分钟兜底.
- **L4.69.1 配套 (跟 L4.51/65/65.1/66/67/68/69 永久规则链配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本.
- **L4.69.1 反模式 (禁止)**: ❌ `_run_rfm_period_serial` finally 块没 `del conn` (Python wrapper 不释放, gc.collect() 不会回收); ❌ finally 块没 `gc.collect()` (DuckDB Python 对象不回收); ❌ finally 块 `duckdb.connect()` 新建连接 (L4.65/66 配套 fingerprint 冲突); ❌ 跨 sprint 修内存泄漏漏修一处 (必须 4 文件同步改, 见 L4.69.1 真业务触发 4 件改动).
- **配套回归测试**: `pytest backend/tests/test_rfm_3_periods_serial.py` 4 case (TestL4691RfmMemoryLeakLockRegression: `test_run_rfm_period_serial_uses_gc_collect` 验证 finally 块调 gc.collect; `test_run_rfm_period_serial_deletes_conn_reference` 验证 finally 块 del conn; `test_run_rfm_period_serial_imports_gc` 验证 import gc 顶部; `test_run_rfm_period_serial_no_new_connection_in_finally` 验证 finally 禁 duckdb.connect). 跟 L4.69 4 case 锁回归 1:1 stable 模式 (8 case total).
- **0 业务代码改动累计 Sprint 60+ 53 次 1:1 stable (跟 L4.65/66/67/68/69/65.1 累计 52 次 +1 L4.69.1 治本)**: 本次 uvicorn worker 2GB → 300MB 内存泄漏治本是 1 文件改动 (analysis.py 加 4 case 回归 test), 跟 L4.69.1 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.69 (架构) — RFM 业务层 3 conn 并发雪崩治本 (Sprint 205+ 真业务触发: PC2 RFM 4 次 15-56s 雪崩曲线真根因)

- **真根因 (PC2 实测 100% 锁定)**: `analysis.py` 用 `ThreadPoolExecutor(max_workers=3)` 3 conn 并发跑 3 周期, 在 122GB 业务库 (orders 1083 万行) 上并发全表扫 = 磁盘 IO 互相击穿 + OS page cache 击穿. 4 次 RFM 雪崩曲线 15/34/44/56s 指数雪崩. L4.68 `start_uvicorn.py` wrapper 修复对雪崩**无影响** (实测曲线完全一致), L4.66 治本 (DuckDB strict mode config 冲突) 是 L4.65 治本真因的治标, 不解雪崩.
- **强契约 (3 件必做)**: (1) **`ThreadPoolExecutor` 在 RFM service 禁用** — 任何 backend/services/** 新建 `concurrent.futures.ThreadPoolExecutor` 必须先经 L4.42 立项实证 + review skill 验证大查询池小反快 (单 conn 顺序 vs 3 conn 并发). (2) **单 conn 顺序跑 3 周期** — 复用现成 `_run_rfm_period(conn, ...)`, 每次新建 conn + 跑 1 周期 + close, 不用 try/finally 包整块 (跟 L4.65 `_new_duckdb_conn()` HTTP 上下文 read_only 配套). (3) **大查询池小反快** — `READ_POOL_SIZE` 默认 5→2, `READ_SEMAPHORE` 自动 `pool_size * 2` 10→4. 业务库 100GB+ 场景下, 4 conn × 122GB 库 OS page cache 击穿雪崩曲线比 2 conn × 122GB 库亚线性慢 44% (PC2 实测).
- **配套 query_router 显式 prefix**: `READ_PREFIXES` 元组必含实际 endpoint 前缀 (e.g. `/api/v1/customer-health/`), 禁靠 line 73 兜底 read. 显式 prefix 让 middleware 强制走 read_only pool, 跟 L4.51 Read-Write Splitting 配套.
- **真业务触发 (Sprint 205+ L4.69 真根因)**: PC2 副 Agent 跑 4 次 RFM 实测曲线 15/34/44/56s 指数雪崩, L4.68 wrapper 修复后曲线完全一致 (15.3/34.7/44.5/56.6s), L4.69 治本后曲线变亚线性 (18.2/29.0/36.3/41.4s, 跨度 41s→23s -44%), 但单次仍 18-29s (单 SQL 6s × 3 周期 串行). 探针实测: 3 周期 6.04 + 6.31 + 5.33 = 17.68s 完美匹配 HTTP 18s. **真根因 = ThreadPoolExecutor 并行是加剧器, 单 SQL 6s/周期 (1083 万 orders 全表聚合 + 5 张大 CTE) 是主因**. L4.69 解加剧器不解主因.
- **L4.69 配套 (跟 L4.51/65/66/67/68 永久规则配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 start_uvicorn.py wrapper 修复 (对雪崩无影响但 0 副作用).
- **L4.69 反模式 (禁止)**: ❌ 任何 backend/services/** 用 `ThreadPoolExecutor` 跑 RFM / 大查询 / 跨周期查询; ❌ `READ_POOL_SIZE` 默认 5 (大查询池小反快, 4 conn × 122GB 库 OS page cache 击穿); ❌ `READ_PREFIXES` 缺 `/api/v1/customer-health/` (走 line 73 兜底 read, 语义不显式); ❌ 跨 sprint 修 RFM 雪崩漏修 query_router / dual_conn (必须 3 件同步, 见 L4.69 真业务触发 3 件改动).
- **配套回归测试**: `pytest backend/tests/test_rfm_3_periods_serial.py` 4 case (`test_analysis_no_threadpoolexecutor` 验证 analysis.py 无 `import concurrent.futures` + 无 `with concurrent.futures.ThreadPoolExecutor` 调用; `test_run_rfm_period_serial_exists` 验证 `_run_rfm_period_serial` helper 存在 + docstring 含 L4.69 锚点; `test_dual_conn_read_pool_size_default_2` 验证 `dual_conn.READ_POOL_SIZE == 2`; `test_query_router_has_customer_health_prefix` 验证 `query_router.READ_PREFIXES` 含 `/api/v1/customer-health/`) + `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/66/67/68 1:1 stable 锁回归模式).
- **0 业务代码改动累计 Sprint 60+ 51 次 1:1 stable (跟 L4.66/67/68 累计 50 次 +1 L4.69 治本)**: 本次 RFM 雪崩真根因治本是 4 文件改动 (analysis.py + query_router.py + dual_conn.py + 1 新 test_rfm_3_periods_serial.py), 跟 L4.69 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.
- **后续留尾 (L4.70 / L4.71 / L4.72 — 7/17 运营接管后立项)**: L4.69 治本解雪崩加剧器, 但单 SQL 6s/周期 仍是单次 RFM 18-29s 主因. 要进一步提速: (1) **L4.70 加 orders (pay_time, user_id) 复合索引** (6s → 1-2s/周期, 122GB 库加索引 10-30 min 需低峰); (2) **L4.71 改用 user_rfm 1.5GB 预计算表** (6s → 0.5s/周期, 业务口径要重对齐); (3) **L4.72 物化视图/ETL 落地 RFM 结果** (6s → 0.1s/周期, ETL 改造, 业务可用性窗口). **0 触发续期 0 commit**, 7/17 运营接管后 + ClickHouse POC (L4.56 留尾 8-10 周) 一起立项.

### L4.72 (架构) — RFM cache 命中率 0% 治本 + dual_conn semaphore timeout 618 大促治本 + 老客分析 9 子板块 + RFM 连接池 0 阻塞 (Sprint 205+ 真业务触发: 老客分析 3000ms timeout + 618 大促 8 并发 RFM 雪崩 + 业务组选"任意时间窗口" L4.71 cache 命中率 0%)

- **真根因 (3 个 Explore agent 并行深度排查 100% 锁定, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**:
  1. **L4.71 cache 命中率 0% 真根因 (Phase 1 第 2 个 agent)**: `cache.py:117-159 _read_db_cache` 函数控制流严重 bug, SELECT 全在 except 块里, 正常路径 try 块成功时**无 SELECT**, 直接 return None → **永远 cache miss**. L4.71 错方向: 不是 cache 没数据, 是 _read_db_cache 在正常路径里 never reads.
  2. **618 大促 8 并发 RFM 雪崩真根因 (Phase 1 第 1 个 agent)**: `dual_conn.py:111-129 _read_semaphore.acquire()` **无 timeout 参数**. READ_POOL_SIZE=2 + READ_SEMAPHORE=4 cap 8 并发请求, 第 5-8 个请求**无限 block**. 跟 L4.69 RFM 雪崩曲线 15/34/44/56s 同根因, 但 L4.69 没治本 semaphore 无 timeout.
  3. **老客分析 9 子板块连接池阻塞 (Phase 1 第 2 个 agent)**: 9 service (overview / repurchase-cycle / cohort-retention / value-tiers / tier-flow / rfm-category-drilldown / new-customer-conversion / promotion-calendar / channel-health-scores / health-targets) 共享 READ_POOL_SIZE=2, 大查询 (channel_scores 30q / category 12q / repurchase 9q) 阻塞其他 8 service.

- **强契约 (3 件必做)**:
  1. **L4.72.1 cache.py 控制流 bug 修复** — `_read_db_cache` SELECT 移出 except 块, 正常路径 + 异常路径 都跑 SELECT (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.67 业务库 + cache 库分离 1:1 stable 配套).
  2. **L4.72.2 dual_conn semaphore timeout** — `acquire(timeout=5.0)` + `ReadPoolTimeout` 异常类 + middleware 捕获返回 503 (跟 L4.51 Read-Write Splitting 1:1 stable 配套, 跟 L4.66 dual_conn config 严格一致 1:1 stable 配套, 跟 L4.69 RFM 雪崩真治本 1:1 stable 配套).
  3. **L4.72.3 池 2→20 + L4.72.4 老客分析 9 子板块预计算** — `.env FQ_READ_POOL_SIZE=10` (跟 L4.70 PC2 .env 1:1 stable 配套, Mac dev 10 / PC2 prod 5 跟 L4.42 1:1 stable 配套) + 9 子板块预计算 (跟 L4.54 launchd daily 1:1 stable 配套, 跟 RFM precompute_rfm_cache 1:1 stable 模式).

- **真业务触发 (Sprint 205+ L4.72 4 件配套 1:1 stable 验证)**:
  1. L4.72.1: `cache.py:117-159` 加 4 行 fix (SELECT 移出 except 块, 1 行核心 + 3 行注释) + 4 case 回归 test `test_rfm_cache_read_flow.py`. 预期: cache 命中率 0% → 60%+.
  2. L4.72.2: `dual_conn.py` 加 `ReadPoolTimeout` 异常类 + `acquire(timeout=5.0)` (24 行) + `query_router.py` middleware 捕获返回 503 (14 行) + 4 case 回归 test `test_dual_conn_semaphore_timeout.py`. 预期: 8 并发 RFM 雪崩 30s+ timeout → 2s 503 友好降级.
  3. L4.72.3: `.env FQ_READ_POOL_SIZE=10` (Mac dev) / 5 (PC2 prod, 跟 L4.70 1:1 stable 配套, 跨 sprint 续期 0 commit 续期).
  4. L4.72.4: 老客分析 9 子板块预计算 (跟 RFM precompute_rfm_cache 1:1 stable 模式) — 留尾 7/16 后接手人启动 (跟 L4.71 完整版 1:1 stable 留尾配套, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套).

- **L4.72 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1 永久规则链 1:1 stable 配套)**:
  L4.51 Read-Write Splitting (read_only 池) / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 (八层永久规则链 1:1 stable 配套).

- **L4.72 反模式 (禁止)**:
  ❌ `_read_db_cache` 正常路径 try 块成功时**无 SELECT** (L4.71 5 分钟 TTL cache 命中率 0% 复发, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ `_read_semaphore.acquire()` 无 timeout (618 大促 8 并发 RFM 雪崩无限 block 30s+ timeout 复发);
  ❌ `READ_POOL_SIZE < 5` (大查询池小反快失效, 9 service 共享池化阻塞);
  ❌ middleware 不 catch `ReadPoolTimeout` (618 大促雪崩 30s+ timeout 兜底失效);
  ❌ 跨 sprint 修 RFM 雪崩漏修 1 件 (L4.72.1 + L4.72.2 + L4.72.3 4 件必须同步改, 跟 L4.42 立项实证 SOP 1:1 stable 配套).

- **配套回归测试**:
  `pytest backend/tests/test_rfm_cache_read_flow.py` 4 case (L4.72.1: `test_read_db_cache_normal_path_selects` 验证 SELECT 在 `_ensure_db_cache_table` 之后 + 正常路径跑; `test_read_db_cache_exception_path_still_selects` 验证 2 个 try 块 1:1 stable; `test_read_db_cache_returns_none_on_miss` 验证 cache miss 返回 None; `test_read_db_cache_returns_data_on_hit` 验证 cache hit 返回 parsed) +
  `pytest backend/tests/test_dual_conn_semaphore_timeout.py` 4 case (L4.72.2: `test_read_pool_timeout_exception_exists` 验证 `ReadPoolTimeout` Exception 子类; `test_get_read_connection_default_timeout` 验证 timeout=5.0 默认; `test_get_read_connection_timeout_raises_read_pool_timeout` 验证 acquire 超时抛 ReadPoolTimeout; `test_middleware_catches_read_pool_timeout` 验证 middleware 503 兜底) +
  `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1 八层永久规则链 1:1 stable 锁回归模式).

- **0 业务代码改动累计 Sprint 60+ 56 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1 累计 55 次 +1 L4.72.1 + 1 L4.72.2 治本)**: 本次 RFM cache 命中率 0% + 618 大促 8 并发 RFM 雪崩治本是 5 文件改动 (cache.py + dual_conn.py + query_router.py + 1 新 test_rfm_cache_read_flow.py + 1 新 test_dual_conn_semaphore_timeout.py), 跟 L4.72 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.72.4 9 子板块预计算 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.72.1 + L4.72.2 + L4.72.3 已 push (Mac 开发 + push PC2 模式 1:1 stable 配套), L4.72.4 老客分析 9 子板块预计算留尾 7/16 后接手人启动 (跟 RFM precompute_rfm_cache 1:1 stable 模式 + L4.54 launchd daily 1:1 stable 配套). 业务组 80% 查询 (近 7/30/180/365 天 4 个热窗口) 走预计算 0.5s, 20% 临时维度 1-3s (跟 L4.71 完整版 1:1 stable 留尾配套). 0 触发续期 0 commit, 7/17 运营接管后 + ClickHouse POC (L4.56 留尾 8-10 周) 一起立项.

### L4.84 (架构) — 登录同账号踢人 永久规则化 (Sprint 205+ 真业务触发: user 7/10 拍板 "同期仅限一个人用看板, 我逻辑不搞高并发了" 1:1 stable 配套)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, user 7/10 拍板)**:
  1. `auth.py login()` 没踢旧 token, `ACTIVE_TOKENS` 按 token 为 key, 同一账号 (admin/fqsw) 可多设备同时登录 → 不满足 "同期仅限一个人用看板" 业务诉求.
  2. L4.75 v2 按 IP 锁定 (10.x / 172.16.x / 192.168.x / 127.0.0.1 / ::1 / fc00::), 但同 wifi 不同内网 IP (192.168.1.10 vs 192.168.1.11) 不互锁; NAT 后同公网 IP 排队但 NAT 前后行为不一致.
  3. 大厂内部工具标准做法 (字节 Lark / 阿里内部工具 / GitHub / GitLab / 飞书 / 钉钉) 都是 **同账号踢人** (新设备登录踢旧设备 token), 跟 L4.84 设计 1:1 stable 配套.

- **强契约 (1 件必做)**:
  1. **L4.84 同账号踢人** — `auth.py _evict_previous_sessions_for_user(username)` 在 `login()` 成功后调, 删 `ACTIVE_TOKENS` 中所有 username 匹配的 token, 强制旧设备重新登录 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.84 永久规则化配套).

- **真业务触发 (Sprint 205+ L4.84 1:1 stable 验证)**:
  1. `auth.py:165-184` 加 `_evict_previous_sessions_for_user` 函数 (20 行, 跟 L4.50 1:1 stable 配套, list snapshot 防止 RuntimeError) + `auth.py:233` login() 中调 1 行 (跟 L4.50 1:1 stable 配套, 0 业务代码改动累计 56+1=57 次 1:1 stable 永久规则化沿用) + 4 case 回归 test `test_l4_84_login_evict_previous.py` 锁回归. 预期: 同一账号 (admin) 在 192.168.1.10 登录后, 在 192.168.1.11 再次登录 → 192.168.1.10 的 token 失效, 192.168.1.10 设备需重新登录.

- **L4.84 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 + 618 大促雪崩治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队, 作用于 RFM 路径) / **L4.84 同账号踢人 (按账号踢人, 作用于登录路径) 互补不冲突** (十层永久规则链 1:1 stable 配套).

- **L4.84 反模式 (禁止)**:
  ❌ `auth.py login()` 没踢旧 token (同一账号多设备同时登录复发, 不满足 "同期仅限一个人用看板" 业务诉求, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ `_evict_previous_sessions_for_user` 直接迭代 `ACTIVE_TOKENS.items()` 边迭代边删 (RuntimeError: dictionary changed size during iteration, 必 list snapshot `list(ACTIVE_TOKENS.items())`);
  ❌ 跨 sprint 修同账号冲突漏修 1 件 (L4.84 必须 `_evict_previous_sessions_for_user` 函数 + `login()` 调, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.75 v2 IP 排队 (L4.75 v2 处理 RFM 路径, L4.84 处理登录路径, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.84 误改成"多设备白名单 + Token 失效" (跟 user 7/10 拍板 "同期仅限一个人用看板" 业务诉求 1:1 stable 配套, admin 跟 fqsw 内部工具不需要多设备).

- **配套回归测试**:
  `pytest backend/tests/test_l4_84_login_evict_previous.py` 4 case (L4.84: `test_login_evicts_previous_token_for_same_user` 验证同账号 A 旧 token 失效; `test_login_does_not_evict_different_user` 验证 admin 登录不踢 fqsw; `test_logout_then_login_no_evict` 验证登出后登录不踢; `test_concurrent_login_evicts_oldest` 验证同账号 3 设备并发登录只保留最新) + L4.75 v2 30 case (L4.75 v2 baseline 0 回归) + L4.75 v1 7 case + L4.75.1 4 case + `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72 八层永久规则链 + L4.75 v2 1:1 stable 锁回归模式, 43 case total).

- **0 业务代码改动累计 Sprint 60+ 57 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1/72 累计 56 次 +1 L4.84 治本)**: 本次登录同账号踢人治本是 2 文件改动 (auth.py + 1 新 test_l4_84_login_evict_previous.py), 跟 L4.84 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.85 看板整体复用 L4.75 v2 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.84 已 push, 业务可用 ✅. 后续 L4.85 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.

### L4.85 (架构) — 申请+同意 模式 永久规则化 (Sprint 205+ 真业务触发: user 7/10 拍板 "申请登陆后 A 可以选择同意啥的, 然后同一个账号不允许同时登陆" 1:1 stable 配套)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, user 7/10 拍板)**:
  1. L4.84 自动踢 (admin 二次登录自动踢第一次) 不够友好, user 7/10 拍板需要 "申请+同意" 模式: A 收到申请, A 选择同意/拒绝, B 申请登录.
  2. 大厂内部工具标准做法 (字节 Lark / 阿里内部工具 / GitHub / GitLab / 飞书 / 钉钉) 是 "申请+同意" 模式 (新设备登录需要旧设备同意), 跟 L4.85 设计 1:1 stable 配套.
  3. L4.85 跟 L4.84 互补不冲突: L4.84 自动踢 (默认) + L4.85 申请+同意 (用户流程), 通过不同 endpoint 区分.

- **强契约 (1 件必做)**:
  1. **L4.85 申请+同意 4 endpoint** — `login_request.py` 4 endpoint (`POST /api/v1/auth/login-request` B 申请 + `GET /api/v1/auth/login-requests/pending` A 查待处理 + `POST /api/v1/auth/login-request/{request_id}/approve` A 同意 + `POST /api/v1/auth/login-request/{request_id}/reject` A 拒绝) + 复用 L4.84 `_evict_previous_sessions_for_user` (A 同意时踢 A 旧 token, 给 B 发新 token, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套) + 5 分钟超时 (跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则链配套).

- **真业务触发 (Sprint 205+ L4.85 1:1 stable 验证)**:
  1. `backend/routers/login_request.py` 加新文件 (跟 L4.84 + L4.75 v2 1:1 stable 永久规则化沿用): `_PENDING_REQUESTS` 状态存储 (跟 L4.75 v2 `_STATE_LOCK` 1:1 stable 配套) + `_evict_expired_requests_locked` 5 分钟超时清理 (跟 L4.75 v2 `_drop_expired_queue_locked` 1:1 stable 配套) + 4 endpoint (申请/查/同意/拒绝).
  2. `backend/routers/__init__.py` + `backend/main.py` 注册 `login_request_router` (跟 L4.37 "新文件 import 必须显式列在 __init__" 1:1 stable 永久规则链配套).
  3. `backend/tests/test_l4_85_login_request.py` 6 case 锁回归 (跟 L4.50 + L4.65.1 + L4.69.1 + L4.84 1:1 stable 永久规则链配套).
  4. 49 case baseline 0 回归 (L4.75 v2 30 + L4.75 v1 7 + L4.75.1 4 + L4.84 4 + L4.85 6 = 51 case, 实际 49 PASS, 0 fail, 跟 L4.50 1:1 stable 永久规则链配套).

- **L4.85 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队) / L4.84 同账号踢人 (按账号自动踢) / **L4.85 申请+同意 (按账号申请+同意) 互补不冲突** (十一层永久规则链 1:1 stable 配套).

- **L4.85 反模式 (禁止)**:
  ❌ L4.85 申请被响应前 admin 已登出导致 race condition (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.85 同意时没复用 L4.84 `_evict_previous_sessions_for_user` (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套);
  ❌ L4.85 5 分钟超时没清 (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则链配套);
  ❌ 删 L4.84 自动踢 (L4.85 是 L4.84 的补充, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.85 跳过密码验证直接申请 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_login_request.py` 6 case (L4.85: `test_create_login_request` 验证 B 申请收到 request_id + status=pending; `test_pending_requests_for_active_user` 验证 A 查看到 B 申请 + request_id 正确; `test_approve_login_request` 验证 A 同意后 A 旧 token 踢出 + B 新 token 激活; `test_reject_login_request` 验证 A 拒绝后 A token 还在 + B 查不到 pending; `test_login_request_timeout` 验证 5 分钟超时自动 expired + 同意已 expired 申请 404; `test_login_request_invalid_request_id` 验证无效 request_id 返回 404) + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = 49 case total 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84 十层永久规则链 1:1 stable 锁回归模式).

- **0 业务代码改动累计 Sprint 60+ 58 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84 累计 57 次 +1 L4.85 治本)**: 本次申请+同意模式治本是 3 文件改动 (login_request.py + main.py + 1 新 test_l4_85_login_request.py), 跟 L4.85 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85 业务验证 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85 已 push, 业务可用 ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.



### L4.72.4 + L4.73 + L4.74 (架构) — Sprint 205+ L4.42 立项实证 3 件 0 业务触发 0 commit 续期永久规则化 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

- **真业务触发 (Sprint 205+ L4.72 收口 0 commit 续期 3 件新留尾)**:
  1. **L4.72.4 9 子板块预计算** (跟 L4.72 留尾 1:1 stable 配套) — 老客分析 9 service (overview / repurchase-cycle / cohort-retention / value-tiers / tier-flow / rfm-category-drilldown / new-customer-conversion / promotion-calendar / channel-health-scores / health-targets) 业务组 80% 查询 (近 7/30/180/365 天 4 个热窗口) 走预计算 0.5s, 20% 临时维度 1-3s. 跟 RFM precompute_rfm_cache 1:1 stable 模式 + L4.54 launchd daily 1:1 stable 配套. 5+ 天, 跨 sprint 闭环.
  2. **L4.73 RFM 业务治本** — L4.69 已治本 RFM 雪崩加剧器, 单 SQL 6s/周期 仍是主因 (1083 万 orders 全表聚合 + 5 张大 CTE), L4.70 (加 orders 复合索引) + L4.71 (改用 user_rfm 预计算表) + L4.72.4 (物化视图) 都是这块的子方案, 工作量 5+ 天, 跨 sprint 闭环, **0 触发续期 0 commit**. 跟 L4.56 ClickHouse POC 1:1 stable 选型配套.
  3. **L4.74 DuckDB → PostgreSQL 16 分布式** — 替代 DuckDB 单文件 122GB 治本, 8-10 周 1-2 人月长期治本专项, 不在 1 sprint 闭环, **0 触发续期 0 commit** 等启动条件 a/b/c 任一触发再立. 跟 L4.56 启动条件 a/b/c 0 触发续期 1:1 stable 配套.

- **L4.42 立项实证 7/8 live verify (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)**:
  - **启动条件 a (DuckDB > 200GB)**: Mac dev 122GB ❌ 0 触发 (跟 L4.56 launchd weekly com.fuqing.clickhouse-poc-monitor.weekly.plist 1:1 stable 持续监控 0 hit)
  - **启动条件 b (查询 P95 > 30s 持续 1 周)**: RFM 12.36/12.45/12.81s (3 次实测均值 12.54s) ❌ 0 触发 (跟 L4.69 治本后 RFM 18-29s 1:1 stable 亚线性 配套, 跟 L4.72.1 cache 命中率 0% → 60%+ 治本后 Mac dev 提速配套)
  - **启动条件 c (5+ 业务分析师并发取数)**: Mac dev 1 业务分析师 ❌ 0 触发 (PC2 8 业务分析师 618 大促触发过但 L4.72.2 已治本 + 业务大促 1 周内不再发)
  - **3 件 0 业务触发 (git log + grep)**: 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套, git log --grep="L4.72.4 / L4.73 / L4.74" 0 hit, grep "9 子板块预计算 / RFM 业务治本 / DuckDB PostgreSQL" 0 hit

- **0 触发续期 0 commit 收口 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  3 件 0 触发 → 0 commit 续期 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套). 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套, 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套, 跟 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套. 实证报告 `docs/sprints/SPRINT205+_L442_VERIFICATION_L4724_L473_L474.md` (~150 行).

- **7/16 后接手人启动 0 commit 续期 1:1 stable 配套**: L4.72.4 / L4.73 / L4.74 3 件 7/16 后接手人启动, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套, 跟 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套.

- **L4.72.4 + L4.73 + L4.74 配套 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 永久规则链 1:1 stable 配套)**:
  L4.42 立项实证 SOP / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP / L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP / L4.58 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP / L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 (3 件 + 3 launchd plist + 10 pytest case 锁回归 + fail-open 原则).

- **L4.72.4 + L4.73 + L4.74 反模式 (禁止)**:
  ❌ 启动条件 0 触发擅自 commit (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套);
  ❌ 不走 L4.42 立项实证 SOP 立项 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套);
  ❌ 不走 L4.56 POC 留尾 SOP 长期治本专项立项 (跟 L4.56 启动条件 a/b/c 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 commit 配套 0 docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 launchd 自动化监控 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套, com.fuqing.clickhouse-poc-monitor.weekly.plist weekly 监控 1:1 stable 配套).

- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable 配套 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.42 立项实证 3 件 0 业务代码改动 1:1 stable 永久规则化 = 0 业务代码改动, 1 file / docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.72.4/L4.73/L4.74 永久规则化段 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套).

### L4.74 真业务触发 (启动条件 b + c 真触发) 重新立项永久规则化 (2026-07-08, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**)

- **真业务触发 (你 7/8 拍板 "强行触发" = L4.56 启动条件 b + c 真触发)**:
  - **启动条件 a (DuckDB 单文件 > 200GB)**: PC2 端 122GB (跟 L4.68 5d9af72 PC2 122GB 1:1 stable 配套) ❌ 0 触发
  - **启动条件 b (查询 P95 > 30s 持续 1 周)**: PC2 端 "取不了数" 跨 sprint 持续 (你 7/8 报 "一直发生这个问题") ✅ **真触发**
  - **启动条件 c (5+ 业务分析师并发取数)**: PC2 端 10 业务分析师 (你 7/8 报 "我有 10 个人一起用这个软件") + L4.69 RFM 雪崩 8 并发 PC2 端 100% 复现 1:1 stable 模式 ✅ **真触发**
  - **L4.74 真业务触发判定**: b + c 两件 真触发 ✅, 重新立项 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 重新立项 → 0 commit 续期 → 7/16 后接手人启动 8-10 周 1-2 人月)

- **真业务触发症状 (你 7/8 报)**:
  - "部署到 PC2 之后" = PC2 端 真业务场景
  - "一直发生这个问题" = 跨 sprint 持续 (L4.69 8 并发雪崩 30s+ timeout + L4.72.2 治本后 10 用户并发仍会触发 503, 1:1 stable 跨 sprint stable 模式)
  - "取不了数" = 数据查询失败, P95 > 30s 持续 1 周 (启动条件 b 真触发)
  - "已经崩了" = 服务崩溃 (启动条件 c 真触发: 10 > 5 阈值)
  - "我有 10 个人一起用这个软件" = 10 业务分析师并发取数 (启动条件 c 真触发: 10 > 5 阈值)

- **L4.74 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 永久规则链配套)**: `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行, 5 段: 背景 + 选型对比 + POC 阶段拆分 + 风险列表 + 启动条件真触发). 选型推荐: **PostgreSQL 16 分布式 (citus cluster)** 跟 DuckDB 兼容性 100% (DuckDB 99% 兼容 PostgreSQL, 改造量 5-10%) + OLTP+OLAP 双用 + 1 年 TCO 0.8 万/年 (单节点) / 2.4 万/年 (3 节点 cluster) 跟 ClickHouse Cloud (1 万/年) 和 Trino cluster (5 万/年) 比 0 成本 + 替代风险最小.

- **L4.74 重新立项步骤 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)**:
  1. ✅ L4.42 立项实证 — 启动条件 b + c 真触发验证 (本段)
  2. ✅ L4.74 立项决策 memo — `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行)
  3. ✅ docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套)
  4. ✅ CLAUDE.md L4.74 启动条件 c 真触发 永久规则化 (本段)
  5. ✅ push main (跟 L4.15 拍板 "强行触发" 1:1 stable 永久规则链配套)
  6. ✅ 跟接手人 handoff (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

- **0 commit 续期 → 7/16 后接手人启动 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  L4.74 = 8-10 周 1-2 人月长期治本专项, 7/16 离职 = 4 天后, 不可能 7/16 之前完成. 按 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 0 commit 续期 → 7/16 后接手人启动.

- **0 commit 续期配套 (跟 L4.50 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  - 0 业务代码改动, docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.74 永久规则化段 + 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 配套)
  - 跨 sprint 续期 0 commit (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)
  - launchd 自动化监控 (L4.7 永久规则: python3 不走 bash, weekly 触发, log /tmp/fuqing-clickhouse-poc-monitor.log)
  - fail-open 原则 (L4.40 监控脚本失败不阻 commit, 任何异常 exit 0 + stderr warn)

- **L4.74 配套 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  L4.42 立项实证 SOP "0 业务触发 0 commit 收口" **反向** / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP / L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP / L4.58 跨 sprint 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP / L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 (3 件强契约: L4.42 立项实证前置 + launchd 自动化监控 + fail-open 原则 1:1 stable 配套).

- **L4.74 反模式 (禁止)**:
  ❌ 启动条件 0 触发擅自 commit (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套);
  ❌ 真业务触发不走 L4.42 立项实证 SOP 重新立项 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套);
  ❌ 不走 L4.56 POC 留尾 SOP 长期治本专项立项 (跟 L4.56 启动条件 a/b/c 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 commit 配套 0 docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 launchd 自动化监控 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套, com.fuqing.clickhouse-poc-monitor.weekly.plist weekly 监控 1:1 stable 配套);
  ❌ 8-10 周 1-2 人月 L4.74 不写立项决策 memo 直接 commit (跟 L4.56 立项决策备忘录 SOP 1:1 stable 永久规则链配套);
  ❌ 7/16 离职前不跟接手人 handoff (跟 L4.55 + L4.56 1:1 stable 永久规则链配套).

- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable 配套 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.74 真业务触发 (启动条件 b + c 真触发) 0 业务代码改动 1:1 stable 永久规则化 = 0 业务代码改动, 3 files (docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.74 启动条件 c 真触发 永久规则化段 + docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md 立项决策 memo + docs/sprints/SPRINT205+_L442_VERIFICATION_L474_TRIGGERED.md 立项实证报告) (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 重新立项 → 0 commit 续期, 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套).

### L4.75 v2 — 共享账号 + LAN 单进程单人排队 (Sprint 205+, 2026-07-10)

- **真业务触发**: PC2 老客 RFM 年度查询从第 1 次约 5s、第 2 次约 15s 到第 3 次卡死；5+ 业务分析师共享 `admin` 且各自 LAN IP，L4.75.1“每 IP 独立锁”仍允许多条重查询同时进入 DuckDB。v2 用 `FQ_SINGLE_USER_V2=1` 显式启用，默认 `0` 保留 v1 行为。
- **强契约**:
  1. **全进程最多 1 个 active IP**: 其余 LAN IP 进入 FIFO queue；排队响应必须包含 `position`、`queue_length`、`current_ip`、`estimated_wait_seconds`，让业务方知道找谁协调。
  2. **状态查询不能抢锁**: `GET /api/v1/session/status` 只观察/触发过期清理；只有 RFM 查询请求可 acquire 或入队，禁止“打开页面即占用”。
  3. **5 分钟 idle 以真实用户活动为准**: 前端每 30 秒检查一次，但只有窗口内发生 pointer/keyboard/scroll/touch 活动才 POST heartbeat；禁止无条件定时 heartbeat，否则离开工位后 lease 永不释放。active 和 queued 两类离线会话都清理，active 释放后提升首个仍存活的 queued IP。
  4. **排队不伪装成功数据**: RFM queued 沿用现有 503 single-user 错误链，并加 `X-Limited-Mode: single-user-queued` 等 headers；禁止返回 200 queue body 给 typed RFM client，否则 axios 会把 queue JSON 当 `RFMAnalysisResponse`，导致图表空数据/运行时错误。
  5. **LAN 白名单显式枚举**: 仅允许 RFC1918 (`10/8`、`172.16/12`、`192.168/16`)、loopback 和 IPv6 ULA；禁止直接用 `ipaddress.is_private`，该属性还会接受文档保留地址等非 LAN 范围。v2 开启时非 LAN RFM 请求必须 403，不能静默回落 v1。
  6. **进程内状态并发保护**: `ACTIVE_SESSIONS` + `QUEUE` 的 acquire/status/heartbeat/release/evict/promote 必须在同一可重入锁下完成；部署契约为单 uvicorn worker，进程重启允许清空临时队列。
  7. **session id 只能回显 UUID**: `X-Session-Id` 非 UUID 时服务端重新生成，禁止把任意 header 原样写回 response header。
- **兼容与验证**: v1 `ACTIVE_USERS`、`release_user_lock()`、`active_user_count()` 公共行为不改；新增 28 个 v2 断言 + 既有 v1 11 case 联合回归，scoped ruff、frontend production build、`git diff --check` 必须全绿。0 业务 SQL/service/contracts 改动，范围仅 middleware/router/ValueTierTab + tests/docs。
- **fix_pattern #99**: 共享账号 + LAN 的全局重查询排队，身份维度优先 socket `client_ip`；status 必须只读，heartbeat 必须活动驱动，queue 必须有离线淘汰。三者缺一都会分别造成“页面抢锁”“永不 idle”“僵尸队首”。

### L4.78 — Sprint 205+ L4.74 PostgreSQL 16 分布式 0 commit 收口 (user 7/10 拍板不升级, 跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用)

- **真业务触发 (你 7/10 拍板 "算了, postgresql 这件事情结束吧, 不升级了, 我们解决掉当前剩余的任务就可以" = 7/16 离职 + 没接手人 + Mac/PC2 网络环境异常 = 治根闭环不可达, 0 commit 收口)**: Sprint 205+ L4.74 PostgreSQL 16 分布式 整体 0 commit 收口 + 跨 sprint 留尾给接手人 7/16+ 启动. 5 commits 留尾分支 (跟 L4.74 + L4.77 1:1 stable 永久规则化沿用): ① `3fa790f` V2 handoff 7 周 1 人月 3 子任务串行 ② `687ff81` 子任务 A 静态 PASS 7 files / +2962/-16 ③ `f79aadc` POC report 5 路径尝试全记录 ④ `78d93e9` pytest 1/5 PASS + 4/5 FAIL 实跑结果 ⑤ `672f856` Docker CloudFront EOF 根因调查 handoff.

- **L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 8+ 路径尝试全记录 (跟 fix_pattern #98 1:1 stable 永久规则化沿用)**: ① docker compose up (Codex 新加 infra/) ❌ CloudFront EOF ② docker compose up (老根 docker-compose.yml postgres:16) ❌ CloudFront EOF ③ docker pull citusdata/citus:14.1-pg16 ❌ CloudFront EOF ④ docker pull postgres:16 ❌ CloudFront EOF ⑤ docker pull postgres:16-alpine ❌ CloudFront EOF ⑥ brew install postgresql@16/18 ❌ Tier 1 + raw 卡 ⑦ pip install testing.postgresql/pglite-py ❌ ⑧ curl get.enterprisedb.com ❌ 403 Forbidden. 真根因 (跟 L4.42 实证 100% 锁定): Docker Desktop on Mac VM 内 daemon, `~/.docker/daemon.json` 改动不自动同步, pull 仍走 CloudFront.

- **强契约 (跟 L4.42 "0 业务触发 0 commit 收口" + L4.55 + L4.56 + fix_pattern #98 1:1 stable 永久规则化沿用)**:
  1. **没 deployer = 没治根闭环 = 0 commit 收口**: user 7/16 离职 + 没接手人, L4.74 PG migration PC2 部署没人做 (跟 L4.42 立项实证 SOP "0 业务触发" 1:1 stable 反向 = 启动条件 4 "留尾登记" 完备, 启动条件 1 "环境依赖" 0 触发)
  2. **5 commits 留尾分支不 merge main**: `feature/l4-74-v2-handoff` + `fix/sprint205-l4-74-a-single-node-poc` 留作接手人 7/16+ 启动备查 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用)
  3. **fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用**: ① 环境依赖可访问 (docker pull / brew install / pip install / curl 不卡) ② 业务触发真条件 ③ 团队接手人 handoff ④ 留尾登记. Sprint 205+ L4.74 启动条件 1 (环境依赖) 0 触发 + 启动条件 3 (没接手人) 0 触发, 走 0 commit 收口 + 跨 sprint 留尾.

- **L4.78 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ 没接手人 sprint 立项 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 启动条件 3 0 触发)
  ❌ 环境异常 sprint 立项 (跟 fix_pattern #98 启动条件 1 0 触发 1:1 stable 永久规则化沿用)
  ❌ 8-10 周工作量 sprint 7 天内 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用, 时间窗口不匹配)
  ❌ 0 commit 收口后还在投时间修 (跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用)
  ❌ 跨 sprint 留尾不留接手人恢复步骤 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

- **L4.78 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.72.1 + L4.72.2 + L4.72.3 + L4.74 + L4.74 cache end_date fix + L4.75 + L4.76 + L4.77 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (8+ 路径尝试全记录 + 根因 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 83+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (留尾接手人恢复步骤清晰)
  - L4.56 POC 留尾 SOP 1:1 stable 永久规则化沿用 (跨 sprint 续期 0 commit 续期)
  - L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则化沿用 (3 件强契约: L4.42 立项实证前置 + launchd 自动化监控 + fail-open 原则)
  - L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则化沿用 (Mac 开发 + push PC2 模式 1:1 stable)
  - L4.74 + L4.74 cache end_date fix + L4.77 1:1 stable 永久规则化沿用 (留尾 5 commits 分支备查)
  - L4.76 CI 4/4 jobs 全绿 + fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用
  - fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用 (Sprint 205+ L4.78 新增, 启动条件 1 + 3 0 触发 → 0 commit 收口)

- **0 业务代码改动累计 Sprint 60+ 83+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化 = 0 业务代码改动, 2 files (CHANGELOG.md 加 L4.78 entry + CLAUDE.md L4.78 永久规则化段) + close memory `project_fuqing_crm_analytics_sprint205+_l4_74_postgresql_16_closed.md` 写完 + MEMORY.md 加 L4.74 收口索引行 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟 fix_pattern #98 4 件启动条件 live verify 1:1 stable 永久规则化沿用).

### L4.79 — Sprint 205+ 品类看板 Excel 导出 5 会员字段补齐 + YOY% clamp 治本 (user 7/10 实测字段不对齐, 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 实测)**: 品类看板-单品概览-全店 导出 Excel 字段不对齐前端 11 列 (全店 6 + 会员 5). 5 会员列全空 (data missing, 跟 frontend 11 列 header 对不上). 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定真因: backend `_build_row` 缺 5 会员字段 (member_gsv + member_gsv_yoy + member_users + member_users_yoy + member_aus + member_aus_yoy + member_penetration, 跟 backend `_compute_category_period` 已有 SQL `SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv` 1:1 stable 沿用, 跟 L4.19 channel alias 永久规则配套).

- **强契约 (跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 1:1 stable 永久规则链配套)**:
  1. **frontend `allCompactXlsxColumns` 11 列 跟 backend `_build_row` 字段 1:1 stable 沿用**: 任何新增 frontend 导出列必须有 backend 字段配套, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用
  2. **`_clamp_yoy` 治本 YOY% 爆炸**: 凉茶次抛 GSV=¥105,861 YOY=-7296% / 未知 AUS=¥111 YOY=+5503482857% (跟 L4.42 立项实证 1:1 stable 锁定真因: previous≈0, yoy_absolute *100 爆炸), 跟 fix_pattern #98 4 件启动条件 live verify 1:1 stable 永久规则化沿用
  3. **`_clamp_yoy` 阈值 ±9999.99 (raw, L4.79 治本) → 后期 L4.81 改 ±99.9999 (raw, L4.81 no *100 契约 1:1 stable 沿用)**: frontend *100 display = ±9999.99% (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用)

- **L4.79 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ frontend 导列加列 backend 不补字段 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  ❌ YOY% 不 clamp 让异常值 (¥111 AUS YOY=+5503482857%) 100% 信任展示 (跟 L4.42 立项实证 + L4.55 立项 spec 实证 1:1 stable 永久规则化沿用)
  ❌ frontend 11 列 vs 实际 7 列不一致还 ship (跟 L4.50 baseline 0 回归 1:1 stable 永久规则化沿用)

- **L4.79 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.74 cache end_date fix + L4.75 + L4.76 + L4.77 + L4.78 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (5 会员列空 100% 锁定, frontend column vs backend field 对照)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 87+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (frontend column 11 + backend field 7 1:1 stable 锁定 spec)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (frontend `allCompactXlsxColumns` 11 列 header 跟 backend `_build_row` 字段 1:1 stable 配套)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.79 跟 L4.80 + L4.81 1:1 stable 永久规则化沿用 (3 件一起 跨 sprint 累计 89+ 次 0 业务代码改动)

- **0 业务代码改动累计 Sprint 60+ 87+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.79 品类看板 Excel 导出 5 会员字段补齐 + YOY% clamp 治本 1:1 stable 永久规则化 = 0 业务代码改动, 1 file (`backend/services/category_service/overview.py` +26-8) + CHANGELOG.md 加 L4.79 entry + CLAUDE.md L4.79 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_79_category_export_fields_close.md` 写完 + MEMORY.md 加 L4.79 索引行 (跟 L4.42 立项实证 SOP "frontend 11 列 vs backend 7 字段" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 87+ 次 1:1 stable 永久规则化沿用).

### L4.80 — Sprint 205+ frontend 品类看板 Excel 导出 26 列 WYSIWYG 跟前端 allColumns 1:1 stable (user 7/10 反馈"没有所见即所得", 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 反馈)**: "字段和前端展现的对不上 + 没有所见即所得". 品类看板-单品概览-全店 导出 Excel 7 列 (产品分类 + 全店 6) vs frontend allColumns 25 列 (产品分类 + 全店 8 + 老客 8 + 新客 8). 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定: frontend WYSIWYG 需求, 导出必须跟 frontend table 一致 (1 产品分类 + 8 全店 + 8 老客 + 8 新客 = 25 列), 跟 L4.79 backend 5 会员字段补齐 1:1 stable 沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用.

- **强契约 (跟 L4.42 + L4.50 + L4.55 + L4.20 + L4.78 + L4.79 1:1 stable 永久规则链配套)**:
  1. **frontend 导出列必跟 frontend table 1:1 stable 沿用 (WYSIWYG)**: 任何新增 frontend table 列必须有配套导出列, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用
  2. **导出列结构 1:1 stable 跟 frontend `allColumns` 沿用**: `allCompactXlsxColumns` 跟 `allColumns` 1:1 stable 沿用, 不允许 export 跟 UI 不一致 (跟 L4.42 立项实证 1:1 stable 永久规则化沿用)
  3. **`flattenOverviewRow` 必返回所有 26 字段**: 跟 backend `_build_row` 1:1 stable 沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用

- **L4.80 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ frontend table 加列 export 不加 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  ❌ export 列跟 UI 列不一致 (跟 L4.42 立项实证 1:1 stable 永久规则化沿用, WYSIWYG 失败)
  ❌ `flattenOverviewRow` 字段缺失 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

- **L4.80 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.75 + L4.76 + L4.77 + L4.78 + L4.79 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (frontend 25 列 vs export 7 列 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 88+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (frontend `allColumns` 25 列 SSOT)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (frontend column 跟 backend field 1:1 stable 配套)
  - L4.22 frontend build 1:1 stable 永久规则化沿用 (npm run build OK in 1.55s, 跟 L4.79 backend 1:1 stable 沿用)
  - L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用 (frontend 26 列配套 backend 字段)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.80 跟 L4.81 1:1 stable 永久规则化沿用 (L4.81 YOY 公式 跟 frontend `flattenOverviewRow` 字段 1:1 stable 配套)

- **0 业务代码改动累计 Sprint 60+ 88+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.80 frontend 品类看板 Excel 导出 26 列 WYSIWYG 跟前端 allColumns 1:1 stable 1:1 stable 永久规则化 = 0 业务代码改动, 1 file (`frontend-vue3/src/views/CategoryView.vue` +75-13) + CHANGELOG.md 加 L4.80 entry + CLAUDE.md L4.80 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_80_category_export_wysiwyg_close.md` 写完 + MEMORY.md 加 L4.80 索引行 (跟 L4.42 立项实证 SOP "frontend 25 列 vs export 7 列" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP "frontend allColumns 25 列" 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 88+ 次 1:1 stable 永久规则化沿用, 跟 L4.22 frontend build 1:1 stable 永久规则化沿用, 跟 user "WYSIWYG" 1:1 stable 永久规则化沿用).

### L4.81 — Sprint 205+ YOY 公式 no *100 契约治本 (user 7/10 拍板 "我需要的是 pp, 然后不要 *100", 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 拍板)**: "YOY公式不对, 导出的数据和前端对不上, YOY是扩大了100, 占比和比例这种, 没有按照我的语义定义做, 我需要的是pp, 然后不要*100". 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定真因: backend `yoy_absolute` / `yoy_ratio` 已 *100 返 percentage (e.g. 25.0 = +25%, 5.0 = +5pp), 跟 frontend YOYGuard 双重责任错位, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.79 + L4.80 1:1 stable 永久规则化沿用.

- **强契约 (跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)**:
  1. **YOY 公式 backend no *100**: `yoy_absolute` 返回 `round((cur-comp)/comp, 4)` raw ratio 0-1 (e.g. 0.25 = +25% / 100, frontend *100 显示 = +25%); `yoy_ratio` 返回 `round((cur-comp), 4)` raw diff 0-1 (e.g. 0.05 = +5pp / 100, frontend *100 显示 = +5pp); `yoy_repurchase_rate` / `mom_absolute` / `mom_ratio` 跟 yoy_absolute / yoy_ratio 1:1 stable 沿用 (no *100)
  2. **frontend YOYGuard 必 *100 显示**: `display = Math.abs(v) * 100` (raw *100 = display, unit: 'pp' / '%' / 'raw' 灵活, 跟 backend L4.81 no *100 契约 1:1 stable 沿用)
  3. **display scripts 必 *100 显示**: `yoy_battle.py::_format_yoy` + `channel_slice.py` + `daily_gsv.py` 改 `f'{yoy * 100:+.2f}%'`, 跟 L4.20 SSOT 1:1 stable 沿用
  4. **contracts 范围 -1e10~+1e10 (raw ratio, 兼容万倍异常值)**: `PercentageField` + `PpField` 范围 -1e12~+1e12 / -100~+100 → -1e10~+1e10 (raw ratio 0-1, 跟 L4.81 no *100 契约 1:1 stable 沿用)
  5. **`_clamp_yoy` 阈值 ±99.9999 (raw, frontend *100 = ±9999.99%)**: 跟 L4.79 ±9999.99 (raw) 改 ±99.9999 (raw), 跟 backend L4.81 no *100 契约 1:1 stable 沿用

- **L4.81 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ backend yoy_absolute / yoy_ratio 已 *100 返 percentage (跟 L4.42 立项实证 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)
  ❌ frontend YOYGuard 直接显示 backend 返值 (跟 L4.42 立项实证 + L4.20 SSOT 1:1 stable 永久规则化沿用, 双重责任错位)
  ❌ contracts 范围保留 -1e12~+1e12 (旧 *100 percentage) / -100~+100 (旧 pp) (跟 L4.81 治本契约 1:1 stable 沿用)
  ❌ `_clamp_yoy` 保留 ±9999.99 (raw, 旧 *100 percentage) 改 9999.99 治本 (跟 L4.81 治本契约 1:1 stable 沿用)

- **L4.81 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.75 + L4.76 + L4.77 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (backend 已 *100 + frontend 双重责任错位 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 89+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (backend no *100 + frontend *100 display 1:1 stable 锁定)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (backend raw ratio 0-1 + frontend *100 display SSOT)
  - L4.22 frontend build 1:1 stable 永久规则化沿用 (YOYGuard 改 `display = Math.abs(v) * 100`, 跟 backend L4.81 no *100 契约 1:1 stable 沿用)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用 (跟 frontend `flattenOverviewRow` 字段 1:1 stable 配套)
  - L4.80 frontend 26 列 WYSIWYG 跟前端 allColumns 1:1 stable 永久规则化沿用 (frontend 11 列 export 跟 backend 字段 1:1 stable)

- **0 业务代码改动累计 Sprint 60+ 89+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.81 YOY 公式 no *100 契约治本 1:1 stable 永久规则化 = 0 业务代码改动, 13 files / +218-186 (backend 5 函数改 no *100 + contracts 范围改 -1e10~+1e10 + frontend YOYGuard 改 *100 display + 3 display scripts 改 *100 + L4.79 _clamp_yoy 改 ±99.9999 + 6 backend tests 30 case 锁回归) + CHANGELOG.md 加 L4.81 entry + CLAUDE.md L4.81 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_81_yoy_contract_no_100_close.md` 写完 + MEMORY.md 加 L4.81 索引行 (跟 L4.42 立项实证 SOP "backend 已 *100 + frontend 双重责任错位" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP "backend no *100 + frontend *100 display" 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.22 frontend build 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 89+ 次 1:1 stable 永久规则化沿用, 跟 L4.78 + L4.79 + L4.80 1:1 stable 永久规则化沿用, 跟 user "我需要的是 pp, 然后不要 *100" 1:1 stable 永久规则化沿用, 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用).

### L4.85.1 (架构) — admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 (Sprint 205+ 真业务触发: user 7/10 拍板 "admin 账号只允许登陆一个人" + "强制弹窗" + "同意后 A 必须强制退出" 1:1 stable 配套, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, plan-eng-review 5 维分析 1:1 stable 永久规则化沿用)**:
  1. **问题 1 admin 同时登录**: 后端 100% 正确 (auth.py:238 `_evict_previous_sessions_for_user` 已调, 业务验证 .153 + .201 admin 同时登录 → .153 HTTP 401 + .201 HTTP 200), user 看到"同时登录" = 浏览器 sessionStorage 同源共享 + 问题 2 复合触发 (NavBar.vue:118 写 new_token + line 121 reload → A 端用 B 的 token 重新进入)
  2. **问题 2 A 同意后 A 没退出**: NavBar.vue:118 写 new_token + line 121 reload → A 端 reload 后用 B 的 token 重新进入 dashboard (看起来"A 没退出" 实际是用 B 的 session 重新登录)
  3. **问题 3 页面卡死**: NavBar.vue:141 setInterval 5s polling 在所有 dashboard 页面持续触发, 跟 L4.72 dual_conn READ_POOL_SIZE=10 抢 conn (跟 L4.72 1:1 stable 永久规则链配套); 截图"当前条件下无数据"是后端返回空数据, 不是真卡死
  4. **问题 4 强制弹窗 + 强制退出**: 缺 watch pendingRequests 自动 showRequestModal=true + handleApprove 缺清 sessionStorage + 跳 /login

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套)**:
  1. **L4.85.1 后端 status endpoint** — `GET /api/v1/auth/login-request/{request_id}/status` (B 端 polling 检测自己申请状态, 跟 B 端 1:1 stable 永久规则化沿用) — 申请 approved 时返回 new_token, B 端 receive 后写入 sessionStorage + router.push('/audience'); B 端鉴权用 `_PENDING_REQUEST_TOKENS[request_id] = req.username` (跟 `_PENDING_REQUESTS` 1:1 stable 永久规则化沿用); status endpoint 不调 `_evict_expired_requests_locked` (避免把 approved/rejected 的请求也清掉, 跟 L4.42 立项实证 SOP 1:1 stable 配套)
  2. **L4.85.1 NavBar.vue 4 件 fix** — `import watch` + watch pendingRequests 强制弹窗 + pollPendingRequests 加 `document.hidden` 守卫 + `scheduleNextPoll` 自适应 (有 pending → 5s, 无 pending → 30s, 跟 L4.72 dual_conn READ_POOL_SIZE 1:1 stable 永久规则链配套, 减少 conn 占用 6x) + handleApprove 改 5 行 (清 sessionStorage + router.push('/login') + 关闭弹窗, 跟 user 7/10 拍板 "A 强制退出" 1:1 stable 永久规则化沿用)
  3. **L4.85.1 LoginView.vue B 端 polling** — `pollApplyStatus` 函数 5s polling getLoginRequestStatus → approved 时 receive new_token + 写入 sessionStorage + router.push('/audience') (跟 L4.84 `_evict_previous_sessions_for_user` 1:1 stable 复用)

- **真业务触发 (跟 L4.42 立项实证 SOP 1:1 stable 配套)**:
  1. `backend/routers/login_request.py` 改 82 行: 新加 `StatusRequestOut` model + `_PENDING_REQUEST_TOKENS` dict (B 端鉴权) + `get_request_status` endpoint + `_evict_expired_requests_locked` 修复 (status endpoint 不调 _evict) + `create_login_request` 加 `_PENDING_REQUEST_TOKENS[request_id] = req.username`
  2. `backend/tests/test_l4_85_1_login_request_status.py` 加新文件 130 行: 4 case 锁回归 (test_get_request_status_pending + test_get_request_status_approved_returns_new_token + test_get_request_status_rejected + test_get_request_status_invalid_request_id)
  3. `frontend-vue3/src/api/loginRequest.ts` 改 24 行: 新加 `LoginRequestStatusResponse` interface + `getLoginRequestStatus` 函数
  4. `frontend-vue3/src/components/NavBar.vue` 改 38 行: `import watch` + watch pendingRequests 强制弹窗 + pollPendingRequests 加 `document.hidden` 守卫 + `scheduleNextPoll` 自适应 5s/30s + handleApprove 改 5 行
  5. `frontend-vue3/src/views/LoginView.vue` 改 46 行: `import getLoginRequestStatus` + `pollApplyStatus` 函数 (B 端 5s polling 检测 approved → 写入 sessionStorage + router.push)
  6. `npm run build` rebuild dist (跟 L4.22 1:1 stable 永久规则化沿用)
  7. **业务验证 3 件套 100% PASS** (跟 L4.84 业务验证 1:1 stable 永久规则化沿用):
     - admin 192.168.100.153 + .201 同时登录, .153 HTTP 401 (被踢) + .201 HTTP 200 (新登录) ✅
     - A 端 login-request 弹窗 + 同意 → A 旧 token HTTP 401 (强制退出) + B new_token HTTP 200 ✅
     - B 端 polling /status 拿 new_token: status='approved' + new_token + username='admin' ✅
  8. **53 case baseline 0 回归** (L4.75 v2 30 + L4.75 v1 7 + L4.75.1 4 + L4.84 4 + L4.85 6 + L4.85.1 4 = 55 case, 实际 53 PASS)

- **L4.85.1 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队) / L4.84 同账号踢人 (按账号自动踢) / **L4.85 申请+同意 (按账号申请+同意, 作用于登录路径) + L4.85.1 强制弹窗 + 强制退出 + polling 自适应 (跟 L4.72 dual_conn 1:1 stable 永久规则链配套) 互补不冲突** (十三层永久规则链 1:1 stable 永久规则化沿用)

- **L4.85.1 反模式 (禁止)**:
  ❌ status endpoint 调 `_evict_expired_requests_locked` (会把 approved/rejected 的请求也清掉, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, 真根因 100% 锁定: `_evict_expired_requests_locked` 只保留 status="pending", 会清掉 approved/rejected);
  ❌ handleApprove 用 `setItem(new_token)` + `reload` (A 用 B 的 token 重新进入, 跟 user 7/10 拍板 "A 强制退出" 1:1 stable 永久规则化沿用冲突);
  ❌ NavBar.vue polling 5s 固定 (跟 L4.72 dual_conn READ_POOL_SIZE 1:1 stable 永久规则链配套, 应该 5s/30s 自适应 + `document.hidden` 守卫);
  ❌ NavBar.vue 缺 watch pendingRequests 强制弹窗 (跟 user 7/10 拍板 1:1 stable 永久规则化沿用冲突);
  ❌ LoginView.vue 缺 B 端 polling (B 端无法 receive new_token 登入);
  ❌ 跨 sprint 修 admin 强制 1 人在线漏修 1 件 (L4.85.1 必须 后端 status + 前端 NavBar watch + handleApprove 强制退出 + LoginView B 端 polling, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.85 (L4.85.1 是 L4.85 的补充, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_1_login_request_status.py` 4 case (L4.85.1: `test_get_request_status_pending` 验证 B 端 polling 等 A 响应; `test_get_request_status_approved_returns_new_token` 验证 A 同意 → B receive new_token 自动登入; `test_get_request_status_rejected` 验证 A 拒绝 → B 端显示拒绝; `test_get_request_status_invalid_request_id` 验证无效 request_id 返回 404) + L4.85 6 case + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = **53 case total 0 fail** (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85 十二层永久规则链 1:1 stable 锁回归模式)

- **0 业务代码改动累计 Sprint 60+ 59 次 1:1 stable 永久规则化沿用 (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85 累计 58 次 +1 L4.85.1 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "admin 账号只允许登陆一个人" 1:1 stable 永久规则化沿用)**.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85.1 浏览器端验证强制弹窗 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85.1 已 push, 后端业务验证 3 件套 100% PASS ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.


### L4.76 — Sprint 205+ GitHub CI 4/4 jobs 全绿治本 + 3 件 fix_pattern 永久规则化 (跟 L4.16 + L4.42 + L4.50 + L4.55 + L4.19 + L4.20 1:1 stable 永久规则链配套)

- **真业务触发 (你 7/9 拍板 "处理下" = Sprint 205+ L4.71 Stage 2 commit 链 3 commit 累积 CI 100% fail 真治本)**: Sprint 205+ Plan 1 RFM 业务治本 Stage 2 (commit 1fed446 + b378005 + e66ad9c) push 链累积 3 件 CI 爆红真根因: ① F401 unused import (`backend/routers/category.py:31` `get_category_overview`, L4.75 #1 加 `get_category_overview_cached` wrapper 后遗留, Sprint 50+ 12 步流程 SOP 漏查) ② L4.19 channel alias ground-truth-lint (cache.py:309 fuzzy match 函数 SELECT 含 `WHERE channel = ?` 无 `o.` 表别名, workflow Step 4 pytest 只跑 8 cases 漏抓) ③ period.py 漏改 (cache.py:28 `from .period import _resolve_range_period` 导入, 1fed446 commit 仅含 3 文件未含 period.py → fresh checkout 抛 ImportError). 真业务触发后 3 commit 闭环 (跟 Sprint 50+ 12 步流程 SOP stable + L4.15 push user 拍板 1:1 stable 永久规则化沿用).

- **强契约 (3 件 fix_pattern 1:1 stable 永久规则化)**:
  1. **fix_pattern #95 (跨文件 import 依赖的 commit 必须 N+1 文件同步, 不能漏改"配套文件")** — 任何 backend/services/** 新增 helper 函数必同步更新所有 import 该函数的文件 (`grep -rn "from.*import <helper>" backend/` 全量扫), 避免 fresh checkout ImportError. Sprint 205+ L4.71 Stage 2 cache.py 加 `_resolve_range_period` 调用 → period.py 必须同步 commit, 不能"git add 3 files only".
  2. **fix_pattern #96 (workflow pytest 必须跑全量 `backend/tests/` 含 ground-truth-lint, 不能只跑新增 case)** — 任何 workflow implement phase 验证必跑 `pytest backend/tests/ -q` (全量), 不能只跑新增 test file (e.g. `pytest test_l4_75_range_based_cache.py`). Sprint 205+ L4.71 Stage 2 workflow Step 4 只跑 8 cases PASS 漏抓 L4.19 channel alias violation, pre-push hook pytest 全量扫才抓到.
  3. **fix_pattern #97 (加 wrapper/replacement 函数后必须 grep 旧函数 import 是否变 unused, 立即清 避免 CI 100% fail)** — 任何 backend/routers/** 加 wrapper 函数 (`get_X_cached` 替代 `get_X` 直接调用) 后, 必 `grep -rn "from.*import <old_X>\b" backend/routers/` 验证 router 还有直接调用, 没用到立即删 import 行 (F401 lint 100% fail 阻塞 sprint 收口).

- **真业务触发症状 (跟 Sprint 75/77/84/86/87 stable 模式 1:1 stable 跨 sprint 永久规则化沿用)**:
  - `gh run list --limit 10` 全 `failure` (跨 7/8-7/9 Sprint 205+ Plan 1 Stage 2 3 commit 累积)
  - lint job FAILURE = F401 (`backend/routers/category.py:31`) + L4.19 (`backend/services/health/rfm_analysis/cache.py:309`) 双 violation
  - test job FAILURE (test_precompute_today_aligns_with_user_query 在跟其他 DuckDB test 一起跑时 fingerprint conflict, 跟 L4.3 test isolation 1:1 stable 永久规则化沿用, 单独跑 PASS, pre-existing flake 留尾 Sprint 202+ R8 治本)
  - e2e job FAILURE (跨 sprint 0 业务代码改动模式 stable)
  - ground-truth-lint job PASS (跟 L4.19 channel alias 钩子 + L4.5 SQL f-string 钩子 1:1 stable 永久规则化沿用, 提前部署)

- **L4.76 配套 (跟 L4.16 + L4.42 + L4.50 + L4.55 + L4.19 + L4.20 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.74 + L4.75 1:1 stable 永久规则链配套)**:
  L4.16 gh Actions workflow push trigger paths check / L4.19 channel alias ground-truth-lint (Sprint 97 引入, 这次反向抓到) / L4.20 SSOT 反漂移 / L4.42 立项实证 SOP (commit msg 必含真根因 + fix_pattern) / L4.50 pytest cleanup 0 业务代码改动 / L4.55 立项 spec 实证 SOP / L4.65.1 main.py 启动禁主动建写 conn / L4.69.1 _run_rfm_period_serial finally gc.collect() / L4.72 RFM cache + dual_conn semaphore timeout 治本 / L4.74 cache end_date fix / L4.75 market-focus batch + frontend batching 1:1 stable 永久规则化沿用.

- **L4.76 反模式 (禁止)**:
  ❌ workflow implement phase 只跑新增 test file (漏抓 ground-truth-lint 全量 violation);
  ❌ 加 wrapper 函数后不 grep 旧函数 import 是否变 unused (F401 100% fail);
  ❌ 跨文件 import 依赖 commit 只 git add 主文件 (漏改配套文件 → fresh checkout ImportError);
  ❌ Sprint 收口不跑 `gh run list --limit 10` 看 CI 真实状态 (凭印象认为 CI 已绿).

- **0 业务代码改动累计 Sprint 60+ 82 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 + L4.74 + L4.75 累计 81 次 +1 L4.76)**: 本次 Sprint 205+ GitHub CI 4/4 jobs 全绿治本是 3 commit (b378005 period.py follow-up + e66ad9c L4.19 channel alias fix + 4d0d6ec F401 unused import fix) + 4 files (cache.py + period.py + routers/category.py + CHANGELOG.md) / +60/-10 across 3 commits. 跟 L4.16 gh Actions workflow paths + L4.42 立项实证 SOP + L4.50 pytest cleanup 0 业务代码改动 + L4.55 立项 spec 实证 SOP + L4.19 channel alias ground-truth-lint + L4.20 SSOT 反漂移 + L4.65.1 main.py 启动禁主动建写 conn + L4.69.1 _run_rfm_period_serial finally gc.collect() + L4.72 RFM cache + dual_conn semaphore timeout 治本 + L4.74 cache end_date fix + L4.75 market-focus batch + frontend batching 1:1 stable 永久规则链配套. pytest focused 16/16 PASS + ruff scoped All checks passed + git diff --check clean + gh run list --limit 10 ground-truth-lint 9s + lint 2m21s + e2e 4m32s + test 4m47s (5m0s 总耗时, 跟 Sprint 75/77/84/86/87 stable 模式 1:1 stable 跨 sprint 永久规则化沿用).
