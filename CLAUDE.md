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
| 4 | **版本状态** | 以根目录 `VERSION` + `STATUS.md` + `git log -1` 为准（勿在本表硬编码旧号） |

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

### AI 写代码 typo 防御 + L4 永久规则

> **SSOT（全文）**: [`docs/rules/L4-permanent-rules.md`](docs/rules/L4-permanent-rules.md)  
> 本处只保留**硬门禁摘要**。新增 L4 规则：只改 rules 文件，并在下表加 **一行** 指针。

#### L1–L3 安全网（摘要）

| 层 | 要点 | 文件 |
|---|---|---|
| L1 frontend | `.vue` 必须有 `<template>` 或 `<script>` | `.githooks/pre-commit` |
| L1 backend | SQL 三引号含 `{var}` 必须 f 前缀 | `check_sql_fstring_consistency.py` |
| L2 e2e | spec-lint AST（环境无关断言） | `frontend-vue3/e2e/lint/` |
| L3 service | **FilterBuilder + `?` 参数化**，禁 f-string 拼用户输入 | `backend/services/**` |

#### L4 索引（必记硬门禁，细则见 rules）

| ID | 一句话 |
|---|---|
| **L4.1–L4.2** | SQL 三引号 `{ident}` → 必须 `f`/`rf` 前缀 |
| **L4.3–L4.4** | 真连 DuckDB test 用 fixture + prod skipif |
| **L4.5** | Service 必 FilterBuilder；禁 f-string 内嵌输入 |
| **L4.6** | worktree pytest 设 `DUCKDB_PATH` 指主仓 |
| **L4.7** | launchd 用 python3，不用 bash |
| **L4.8 / L4.31 / L4.40** | merge 后删分支；branch_cleanup 自动化 |
| **L4.9 / L4.17–18** | GH Action tag 先验；Node runner vs action 内部分开 |
| **L4.10 / L4.39 / L4.61** | 平台守卫放 main/skipif，不放 core 逻辑 |
| **L4.12–L4.13** | TECH-DEBT SSOT；MEMORY ≤24.4KB |
| **L4.14–L4.15** | amend 1-commit drift 接受；**push 必 user 拍板** |
| **L4.16** | workflow paths 含 CLAUDE/docs 才触发 CI |
| **L4.19** | `channel` SQL 必 `o.` 表别名 |
| **L4.20 / L4.42 / L4.55** | 留尾/立项 **git log+grep 实证**，禁脑补 |
| **L4.32–L4.34 / L4.41 / L4.60** | subprocess cwd/PYTHONPATH；Path 跨平台 |
| **L4.35–L4.38** | skill symlink；禁停 uvicorn；registry 显式 import；DuckDB flock |
| **L4.51 / L4.65–L4.69** | R/W 分离；HTTP 上下文 read_only；RFM 串行；cache 分库 |
| **L4.53–L4.54** | 禁 snapshot 撑盘；ETL 30d skip + member 7d 窗 |
| **L4.56–L4.59** | POC 备忘录；跨 sprint 0-commit 续期 + launchd 监控 |
| **L4.62+** | plist `plutil -lint`；其余见 rules 全文 |
| **L5.1–L5.2** | CI 债 ROI；e2e 环境无关 |

**SQL f-string 硬例子**:

```python
# ❌ count_sql = """... WHERE {valid_sql}"""
# ✅ count_sql = f"""... WHERE {valid_sql}"""
```

**ad-hoc-query**: 走 MCP / HTTP API，禁直连 DuckDB 跨进程、禁停 uvicorn（L4.36/L4.38）。

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

## L4.x 永久规则

> **全文 SSOT**: [`docs/rules/L4-permanent-rules.md`](docs/rules/L4-permanent-rules.md)  
> 摘要索引见上文「AI 写代码 typo 防御 + L4 永久规则」。改规则只改 rules 文件。

