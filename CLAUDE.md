# Sample CRM — AI 执行手册

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
| 4 | **版本状态** | v0.4.14.138（main @ 2c24fb4，2026-06-19 Sprint 52 收口: visitor 路由激活 + 50m scale benchmark + commit-msg diff 一致性 WARN hook），测试 ~659 passed / 17 skipped + e2e 本地 12/12 pass (CI advisory) + L2 spec-lint 5/5 + L1 fallback 3/3 pass |
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
| **sprint 收口** | merge --no-ff 到 main | 必跑 /ship skill (留 audit trail) | post-merge hook 未追加 `.ship-audit.log` → 视为 sprint 没收口 (Meta-Sprint /ship 接入,见 `docs/SHIP.md`) |
| **改 contract 字段** | 增删改 `backend/contracts/*.py` 字段 (类型/范围/命名) | 跑 `python -m backend.contracts._lint` + **pre-commit hook 自动拦截** (Sprint 18 #142) | 未跑 lint → 禁止 commit (见 `docs/LINTING.md` + `docs/PRE-COMMIT.md`) |
| **改 git hooks** | 增删改 `.githooks/*` / `.pre-commit-config.yaml` | 默认走 `.githooks` (装轻量零依赖, 9 件 lint), `.pre-commit-config.yaml` 选装 (装 framework 才能用) | 走错路径 → 跟 Sprint 3-18 治理脱节 (见 `docs/HOOKS-CHOICE.md` Sprint 19 P2-1) |

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
| L3 (可选) | 弃 `{valid_sql}` 字符串内嵌, 全面 `FilterBuilder.build()` 参数化 | — | Sprint 35+ backlog | — |
| **L4 (流程)** | **/review checklist**: SQL 三引号赋值若含 `{var}` 必须 f 前缀 | review skill 强制 | **Sprint 34.1** | 本节 |
| **L4.2 (流程)** | **任何 Python 写三引号 SQL 字符串 (跨 backend/services/backend/scripts/scripts/etl 范围), 若 body 含 `{identifier}` 必须 f 前缀** | review skill 强制 (Sprint 36-4 范围扩大) | **Sprint 36.4** | 本节 |
| **L4.3 (流程)** | **真连 DuckDB test 必须有 `pytestmark = pytest.mark.skipif(_IN_XDIST_PARALLEL, reason="race flake")`** (跨 `test_api_integration.py:55` + `test_churn_user_list_fstring.py:55,77` + `test_w4_t7_integration.py:147,181,197,228` + `test_w4_full.py:319` `skip_if_duckdb_locked`). DuckDB 文件锁 exclusive, pytest-xdist 多 worker 跑同一文件 100% race flake (Sprint 32.3/34.1/36-1/37/38 5 sprint 复发). 真治本 = per-test tmp DuckDB ATTACH 模式 (留 Sprint 36.x+ backlog, Sprint 38 调研 ROI 重评为低) | review skill 强制 | **Sprint 38** | 本节 |
| **L4.4 (流程)** | **真连 DuckDB test 必须有 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE, reason="production DuckDB 不可用")`** (跨 `test_api_integration.py` + `test_churn_user_list_fstring.py` + `test_w4_t7_integration.py`). CI runner / fresh checkout 没 production DuckDB → 真连空 DuckDB → CatalogException fail (Sprint 32-38 7+ sprint CI 一直红). `_PROD_DUCKDB_AVAILABLE` 定义在 `backend/tests/conftest.py:_detect_prod_duckdb_available()` | review skill 强制 | **Sprint 39** | 本节 |
| **L5.1 (流程)** | **CI 留尾 ROI 重评规则**: 治本 < 1 天闭环 + 治本后 0 复发 → 治本; 治本 > 2 天 OR 治本不现实(基础设施) → 治标. Sprint 32.1 留尾 7 sprint ROI 重评为低, 改 advisory. Sprint 38 race flake 治本 ROI 低(DuckDB 文件锁 exclusive), 改治标. Sprint 41 e2e CI 12 follow-up 仍 fail, 改 advisory. **决策树**: Q1 本地能跑吗? → Q2 根因是 spec 还是环境? → Q3 治本 1-2 天能闭环吗? → Q4 治标会反复出现吗? 详细 `docs/CI-DEFENSE-PLAYBOOK.md` | review skill 强制 | **Sprint 42** | 本节 |
| **L5.2 (流程)** | **spec 写法"环境无关"原则**: ① 不 hardcode 业务数据长度(`toBe(5)` 禁, 用 `length > 0` 替); ② 不 `waitForTimeout(N)` 死等(用 `waitForSelector` / `expect.toBeVisible` 替); ③ `page.request` 加 Authorization header(从 sessionStorage 拿 `fq_crm_auth_token`). 配合 `frontend-vue3/e2e/lint/spec-lint-l2.sh` pre-commit hook (L2 默认, L1 fallback). **Sprint 43 #S43-1**: spec-lint 改 blocking 模式; **Sprint 50.1**: 默认升 L2 AST parser | review skill 强制 | **Sprint 43 / Sprint 50.1** | 本节 |

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
| `docs/AUTOMATION.md` | Claude Code 自动化配置 | 按需 Read |
| `docs/SHIP.md` | /ship skill 使用文档 | 按需 Read |
| `docs/LINTING.md` | ground-truth-lint 规则 | 按需 Read |
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

## Sprint 16.5 收口 (2026-06-11) — 摘要

3/4 治理完成 + 1 NO-OP。详见 `CHANGELOG.md` v0.4.14.40 + v0.4.14.41。

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
- Lint 规则: `docs/LINTING.md` (Sprint 17 #121 新建, 给 ground-truth-lint 提供语义)
- 全量 audit: `CHANGELOG.md` v0.4.14.41 (Sprint 17 #120 新建, 9 contract 全量)
- 组件实现: `frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` JSDoc
- 改版历史: `CHANGELOG.md` v0.4.14.26 (Sprint 12) + v0.4.14.29 (Sprint 13) + v0.4.14.41 (Sprint 17)
- 4 页面 banner: `frontend-vue3/src/components/RatioConventionBanner.vue` (3 天自动消失)

---


## 历史 Sprint 记录

Sprint 28-32 收口详情见 `CHANGELOG.md` v0.4.14.101-v0.4.14.118 + `~/.claude/projects/-Users-hutou/memory/` sprint close files.
