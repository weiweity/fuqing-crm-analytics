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
| 4 | **版本状态** | v0.4.14.33（main @ f8e9235 + Sprint 190 — 运营真业务触发 × 2 bugfix + 1 endpoint. SKILL.md §1.5.1 关键词同义词库 + §1.5.2 工具缺位自检 (防 WorkBuddy 误判"daily-gsv-multi-period 工具缺位"). scripts/ad_hoc_query.py argparse adapter L4.43 bugfix 透传 nargs (Sprint 183 daily-gsv-multi-period 实装未透传导致 unrecognized arguments). backend/routers/ad_hoc_query.py: 加 /daily-gsv-multi-period endpoint (9 → 10 业务 endpoint 总数). 修后 uvicorn launchctl kickstart -k 实测 10 endpoint 加载. pytest 14 skipped / 0 failed (Sprint 188 B1 同 SKIPPED 模式, 生产 DuckDB 锁). 累计 118 sprint 0 debt 持续 (跨 Sprint 60+ 0 debt stable 模式 +12 sprint), L4.x 36→**37 stable** (新增 L4.43 argparse adapter 透传永久规则), fix_pattern #74 沉淀, /document-release 累计 21 次. |

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
| **L4.43 (架构)** | **argparse adapter 必须透传 spec.nargs / choices / type / action** (Sprint 190 真业务触发: scripts/ad_hoc_query.py:62-76 adapter 吞了 `argparse_kwargs["nargs"]`, 导致 daily-gsv-multi-period `--periods start end start end` 多次传报 unrecognized arguments. 真因: Sprint 183 daily-gsv-multi-period 用了 nargs="+" 模式, 但 register argparse 时 adapter 没把 nargs 透传给 argparse). **预防**: 任何 QuerySpec → argparse 转换层必须白名单透传 6 个 kwargs: required/default/choices/type/nargs/action, 缺哪条报 missing-field warning. 跟 L4.5 FilterBuilder + L4.25 防串台同位 (`scripts/ad_hoc_queries/*` 是 CLI 层). 1 case 实跑 daily-gsv-multi-period --periods 4 日期成功. | review skill 强制 | **Sprint 190** | `scripts/ad_hoc_query.py` 任何 argparse adapter, 任何 CLI 参数 spec |**Sprint 183 WorkBuddy AI 跑 /ad-hoc-query 4 根因沉淀** (防止 AI 重复):
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
