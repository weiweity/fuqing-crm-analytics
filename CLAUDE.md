# 芙清 CRM — AI 执行手册

> 本文件每次会话自动加载。只放行为规则，不放参考材料。
> 参考手册见 `docs/reference.md`（按需读取）。

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
| 4 | **版本状态** | v0.4.14.16（main，2026-06-07 sprint 8 收口），测试 391+ passed / 12 skipped |
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
| 1. atexit 钩子 | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans` | ETL 进程退出 | 主防线: `FQ_TMP_PREFIXES` 白名单, 24h+ / 5 文件 / 100GB cap |
| 2. zshrc 告警 | `~/.zshrc:_check_fq_tmp_orphans` | zsh 启动 | 人因防线: 50GB+ 告警, 不删 |
| 3. workbuddy cache | `~/.workbuddy/cache/fq-etl-validation/` | 调试主动 cp | 30 天 TTL, 不污染 /tmp |
| 4. launchd weekly | `scripts/etl/cleanup_backups.sh` + plist | 每周日 03:00 | `data/processed/backups/` 7 天保留 |
| 5. launchd daily backup (Sprint 4 P0-2) | `scripts/etl/backup_duckdb.py` + `com.fuqing.duckdb-backup.daily.plist` | 每日 03:30 | 数据灾备: 55GB DuckDB shutil.copy2 + zstd → 21GB |
| 6. **launchd hourly subagent cleanup (Sprint 6 P0-3)** | `scripts/etl/cleanup_subagent.py` + `com.fuqing.tmp-cleanup.hourly.plist` | 每日每 1 小时 (StartInterval=3600) | subagent 路径兜底: 扫 `/private/tmp` + `/tmp` 1h+ 1GB+ 非白名单, 排除项目根 + layer 1 自身状态文件, cap 5 文件 / 100GB. log `/tmp/fuqing-subagent-cleanup.log` |

详细说明见 `README.md` 第 137 行 "运维安全 / 磁盘治理" 段.

---

## 痛点 1 闭环状态 (2026-06-07 sprint 3 + sprint 4 收口)

| 痛点 | 状态 | 证据 |
|---|---|---|
| **痛点 1** (ETL 41min) | 🟡 部分 (代码层闭环, 跑批真验留 Sprint 6) | W1 单步: 3 次跑批 710s / 817s / 879s (平均 13.4 min < 35 min 目标, CV 9.4%). --update 端到端: load.py:550 加 ON CONFLICT (sprint 4 56a35ee hotfix 2) + 改 NOT EXISTS (sprint 5 3b92f1f hotfix 3). 跑批 2 次仍撞, 根因未明 (DuckDB 1.5.2 subquery + ROW_NUMBER 嵌套边界). 报告: `docs/validation-reports/etl-3-runs-2026-06-07.md` |
| 痛点 2 (读到半新半旧) | 🟢 闭环 | W2 原子 manifest + W3 6 断言 quarantine (sprint 1) |
| 痛点 3 (历史 range 重算) | 🟢 闭环 | W4 540 组合预计算 + W5 DuckDB-KV cache 24h TTL + manifest invalidate (sprint 1) |

**3 痛点全解 + 端到端**: 痛点 1 W1 单步 ✅ + --update 端到端 ✅ (sprint 4 56a35ee), 痛点 2 ✅, 痛点 3 ✅.

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

5. **单连接测试不能推广到生产** (D-7 Sprint 7 P2 教训): DuckDB file-backed 模式下, **同一 connection 的 in-memory state 与新 connection 的 file state 行为不一致**. 100/100 单连接单元测试可能完全误导, 真实生产 ETL 总是新连接 per call. Sprint 7 P2 DuckDB 升级测试 1-tx 路线单连接 100/100 通过, 新连接 1/1 失败 (ConstraintException). **任何 ETL 决策必须有"模拟生产"测试** (新连接 + commit/close 模式), 否则 100% 单元测试通过可能完全是误导. 详见 `docs/validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md`.

---

## 接口开发六步

1. **口径先找语义层** — 禁止在 Service 硬编码 SQL 口径
2. **连接规范** — `conn = get_connection()` + `?` 参数化。禁止 `conn.close()`（单例连接由 `close_connection()` 在应用关闭时统一释放）。`execute()`/`fetch*` 已自动串行化，无需额外加锁
3. **渠道展开** — `expand_channels([channel])`
4. **Schema 三同步** — Service → contracts/schemas.py → 前端 types.ts
5. **前端只展示** — 禁止前端算 YOY/占比/客单价
6. **三层验证** — import 测试 + pytest + vue-tsc

**ETL 脚本连接例外条款** (WO-5 P2-#2)：`scripts/etl/*` 是独立离线脚本（不与 backend 同进程），允许 `duckdb.connect(DUCKDB_PATH, config={"memory_limit": ...})` + `conn.close()`，因为：① ETL 跑批时间长（30-60min），同进程单例连接会污染 config；② `read_only=True` 与 `access_mode=READ_WRITE` 互斥，单例会触发 `Can't open a connection to same database file with a different configuration`；③ ETL 完成后进程退出，连接由 OS 回收。单例规则仍适用于 `backend/services/*` 和 `backend/routers/*` 的 Web 请求路径。

详细示例见 `docs/reference.md`。

---

## 快速启动

### 开发环境（Mac）

```bash
# 后端（端口 8000）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 >> /tmp/fuqin-crm-backend.log 2>&1 &

# 前端（端口 5173）
cd frontend-vue3 && npm run dev

# ETL（必须用 homebrew Python 3.14）
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update

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
| `docs/reference.md` | 参考手册（口径/教训/目录结构） | 按需 Read |
| `docs/archive/product/prd-v3.0.md` | 产品需求文档（归档） | 按需 Read |
| `docs/feishu-architecture/` | 系统架构文档（2 份核心） | 按需 Read |
| `docs/document-index.md` | 完整文档索引 | 按需 Read |
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

## Ratio Convention (Sprint 13+)

> 本节是 ratio / pct / ppt 类字段的强契约，Sprint 13 起强制生效。改前端展示、传值、命名必读。

### 字段命名（后端，强制）

| 后缀 | 数值范围 | 是否已 *100 | 示例 |
|---|---|---|---|
| `*_ratio` | 0-1 decimal | **否** | `old_gsv_ratio`, `member_ratio` |
| `*_pct` | 0-100 percentage | **是** | `gsv_yoy_pct`, `member_penetration_pct` |
| `*_ppt` | -100 ~ +100 pp 差 | **是** | `old_gsv_ratio_yoy_ppt`, `lock_rate_yoy_ppt` |
| `*_yoy` / `*_mom` | 按上面 3 种后缀对应 | 视字段而定 | `gsv_yoy` (pct), `old_gsv_ratio_yoy` (ppt) |

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
- None 透传显示 `—`（`humanizeChange` 已加 `v == null` 守卫）

### 禁止（lint 待加）

1. **前端 0 处散落 `* 100`** — caller 自乘，组件不乘
2. **命名冲突** — `*_ratio_yoy` vs `*_yoy_ratio` 强制统一为 `*_yoy_ppt` / `*_yoy_pct`
3. **hardcode 0 占位** — 禁止 `series = [0.0] * len(dates)`（Sprint 13 P3 教训）
4. **Excel numFmt 错配** — pp 字段用 `'0.0"pp"'` 字面量后缀，% 字段用 `'0.0"%"'`

### 文档

- 完整契约: `docs/reference.md` "Ratio Convention (Sprint 13 更新)" 章节
- 字段语义: `backend/semantic/calculations.py` docstring（`yoy_ratio` / `yoy_absolute` / `mom_*`）
- 组件实现: `frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue` JSDoc
- 改版历史: `CHANGELOG.md` v0.4.14.26 (Sprint 12) + v0.4.14.29 (Sprint 13)
- 4 页面 banner: `frontend-vue3/src/components/RatioConventionBanner.vue` (3 天自动消失)
