# 项目状态 (Project Status)

> **单一 source of truth**. README.md / CLAUDE.md 状态行均链接到这里。Sprint 收口后必更新。

**最后更新**: 2026-07-03 (Sprint 201+: **L4.42 立项实证 0 commit 收口 + ClickHouse POC 立项决策备忘录 + L4.56 永久规则化** — 跟 Sprint 201 R2 v24 + Sprint 202 R1 + Sprint 201 R2 L2 + Sprint 201 R2 v23 + Sprint 201 R1 累计 6 sprint 沉淀 0 业务代码改动. main HEAD `eab214b` (1098e40 → 88e8ae8 → 7201e84 → 1967ad8 → 79e5d33 → e9d059e → 1f2a306 → df29bad → f018d95 → `eab214b`). pytest baseline 993/73/0 → Sprint 202 R1 996/7/0 → Sprint 201 R2 v24 1057/7/3 → Sprint 201+ 1057/7/3 (0 变化). /document-release 累计 33 次真治本. L4.56 永久规则化 POC / 长期治本专项立项必写立项决策备忘录 + 留尾登记 + 启动条件)

**关键文档** (跟 Sprint 201+ 1:1 stable, 跟 main HEAD `eab214b` 同步):
- `docs/sprints/SPRINT201_PLUS_L442_VERIFICATION.md` — 4 任务 L4.42 立项实证报告 (跟 Sprint 201 R2 v24 + Sprint 188 B3 1:1 stable)
- `docs/architecture/clickhouse-poc-decision-memo.md` — ClickHouse / Trino POC 立项决策备忘录 (5 阶段拆分 8-10 周 1-2 人月)

**前一版本 (Sprint 200 R1 v2.1: **uvicorn resilience + rate limit middleware** — 你报"业务持续取数导致 uvicorn 一直处于下线状态"真因: Sprint 184 L4.38 DuckDB flock 锁死 + L4.36 禁停 uvicorn 双锁死. 治本 4 件: ① launchd KeepAlive watchdog 激活 (PID 12872 → 33676, launchctl kickstart -k 自动重启验证) ② rate limit middleware (每用户每分钟 60 req, 触发 429 + Retry-After: 60 + X-RateLimit-* 头, 跟 L4.36 友好错误 1:1) ③ /auth/me 等业务端点限流 (保留 /auth/login /auth/refresh bypass 防登录失败重试触发 429) ④ pytest 8 case 5 TestClass 锁回归 (TestRateLimitBasic + TestRateLimitHeaders + TestRateLimitL436Compliance + TestRateLimitUserIsolation). 累计 126 sprint 0 debt 持续 (Sprint 200 R1 v2.1 1 commit 0 业务代码改动, 跨 Sprint 60+ 0 debt stable 模式 +21 sprint), VERSION 不 bump (跟 Sprint 89/167/190/191/192/193/194/195/196/197/198/199 0 业务代码改动 模式 stable, 累计 19 次 /document-release bump 持续), L4.x 38→**39 stable** (Sprint 200 R1 v2.1 0 新增, **L4.50 (新增候选) — uvicorn watchdog + rate limit middleware** 待 Sprint 200 R1 收口), fix_pattern #82 沉淀 stable. pytest baseline 971/73/0 → **979/73/0** (净 +8 case: TestRateLimitBasic 2 + TestRateLimitHeaders 2 + TestRateLimitL436Compliance 3 + TestRateLimitUserIsolation 1). 全套 pytest 62/62 PASS (8 Rate limit + 5 ai_sandbox + 10 fixed_product + 32 MCP server + 7 WorkBuddy e2e, 0 破坏). /document-release 累计 30 次真治本. 2 files / +284/-0 across 1 commit `d7f84ba`. main HEAD `f62a4af` (5c255b9 → f62a4af, 跟 Sprint 199 + Sprint 200 R1 v2.1 模式 stable).

**前一版本 (Sprint 199 R1 cleanup: main 上 4 uncommitted 改动合规收口 + **L4.35 critical violation 真治本** — `.claude/skills/ad-hoc-query/SKILL.md` 改 symlink → `~/.claude/skills/ad-hoc-query/SKILL.md`, 9889 bytes → 36405 bytes, 3 端字节一致; workflow 9 agents 5 phase 排查发现 Sprint 197 close memory 跟代码 drift `fixed-product-list-compare-http` endpoint 不存在 + Codex 跨 12 轮对话写 14 个 `/tmp/*.py` 业务取数脚本 (L4.5 + L4.36 严重违规) + SKILL.md 真实命中率 ~40-65%). Sprint 199+ 立项 3 P0: ① 淘客渠道每月明细 (extend `daily_gsv_multi_period` + `months_axis`, 2 天) ② 单品按月按 spu_product_class (extend `fixed-product-list-compare-http` + `granularity_axis`, 2 天) ③ 8 分组 TTL 扩 `CATEGORY_GROUPS` 4 → 8 (1 天) + 立 L4.47 永久规则禁 `/tmp/*.py` 业务取数脚本 (1 天). 累计 125 sprint 0 debt 持续 (Sprint 199 cleanup 1 commit 0 业务代码改动, 跨 Sprint 60+ 0 debt stable 模式 +20 sprint), VERSION 不 bump (跟 Sprint 89/167/190/191/192/193/194/195/196/197/198 0 业务代码改动 模式 stable, 累计 18 次 /document-release bump 持续), L4.x 38→**38 stable** (Sprint 199 0 新增, L4.35 symlink 治本走 .gitignore 白名单 `!.claude/skills/*/SKILL.md`), fix_pattern #82 沉淀 stable. pytest baseline 971/73/0 → **971/73/0** (Sprint 199 cleanup 0 新增 case, 但 47/47 PASS Sprint 197+198 R1 真治本实证, 1 failed test_branch_cleanup pre-existing race flake 跟之前 sprint stable 模式). /document-release 累计 29 次真治本. 5 files / +370/-178 across 1 commit `bdb47bb`. Workflow 跑出 446605 tokens / 5 分 03 秒 / 9 agents 跟 Sprint 107+108+109 真因排查 1:1 模式 stable.

**前一版本 (Sprint 197 R1 + Sprint 198 R1 拍板 D + 选项 3 真治本: 立 ad-hoc-query 第 13 个 tool `fixed-product-list-compare-http` 走 backend HTTP API 0 直连 DuckDB 子进程 + 第 14 个 tool `ai-sandbox-execute` 走 backend service SSOT 入口 + audit log `/tmp/fuqing_adhoc_audit.log` + `_validate_sql_security` 拦 DROP/DELETE/TRUNCATE/INSERT/UPDATE/EXEC + 多语句). 累计 124 sprint 0 debt 持续 (Sprint 197+198 1 commit 0 业务代码改动, 跨 Sprint 60+ 0 debt stable 模式 +19 sprint), VERSION 不 bump (跟 Sprint 89/167/190/191/192/193/194/195/196 0 业务代码改动 模式 stable, 累计 18 次 /document-release bump 持续), L4.x 38→**38 stable** (Sprint 197/198 0 新增, 跟 L4.5/L4.20/L4.36/L4.37/L4.38/L4.41/L4.46 + fix_pattern #81/#82 stable 模式配套), fix_pattern #82 沉淀 (任何 ad-hoc-query 工具收口必走两步走 — 禁临时脚本同时立刻补 backend services 拼凑 tool 或 export_excel 11 sheet 覆盖, 跟 Sprint 195 R1 duckdb 不做功能新增 拍板冲突, 用户真业务触发重新拍板) 沉淀, /document-release 累计 28 次. 11 files / +273/-26 across 1 commit. pytest baseline 962/73/0 → **971/73/0** (净 +9 case 真跑, Sprint 197 R1 5 case + Sprint 198 R1 5 case + Sprint 197+198 关键定向 18 case 实测 - 1 failed 是 test_branch_cleanup pre-existing race flake, 跟之前 sprint stable 模式). SKILL.md v2.4 → **v2.6** 升级 (L4.35 symlink 跨端 1 份, 12 tool → **14 tool** + §0.4 段 Sprint 197 R1 锁冲突治本 + §0.5 段 Sprint 198 R1 AI 命中不到治本 + description 加 Sprint 198 + Sprint 197 + Sprint 196 治本).

---

## 版本

| 项 | 值 |
|---|---|
| VERSION | `0.4.14.26` (Sprint 183 WorkBuddy /ad-hoc-query 优化 + SKILL.md v2.2 + L4.36 禁停 uvicorn + /document-release 累计 14 次真治本) |
| git HEAD (main) | `774e6a7` (Sprint 181.1 Path(__file__) 跨平台治本 + L4.34 永久规则, 跟 origin/main 0 drift) |
| 当前分支 | `main` (Sprint 181 收口 + L4.34 沉淀后) |
| 最近 sprint | Sprint 180 inline python 2 真因治本 + Sprint 180.1 shlex 替代 tmp file + Sprint 181 chdir 污染源治本 (3 真因) + Sprint 181.1 硬编码 macOS 路径治本 (1 真因) + L4.32/33/34 永久规则沉淀 |
| 收口日 | 2026-07-01 |
| 上次合入 | Sprint 181.1 + L4.34 (commit `774e6a7`, push origin main `77b0a91..774e6a7` 成功, +L4.34 永久规则 + .ship-audit.log append 1 line) |

---

## 测试状态

| 维度 | 数 | 备注 |
|---|---|---|
| pytest passed | **813** | Sprint 172-178 不退化 (跟 Sprint 171 baseline 813 passed / 72 skipped / 0 failed 持平, Sprint 173 + 8 case date.test.ts + Sprint 175 + 22 case categoryColumnsXlsx + Sprint 176 + 3 case sprint176 regression + Sprint 177+ + 8 case branch_cleanup = 累计新增 41 case 平衡回归). L4.4 race flake 接受 (跟 Sprint 142 + Sprint 141.5 stable) |
| pytest skipped | **72** | production DuckDB 不可用 / 被本地 uvicorn 占用 (含 Sprint 142 race flake L5.1 接受: test_rfm_flow_ttl_ratio Unique file handle conflict) + Sprint 169 sampling tracking 6 case 生产 DuckDB 不可用 skip |
| vitest passed | **80** | Sprint 174 exportXlsx SSOT 8 case + HealthOverviewTab baseline 6 fail (L4.4 接受 pre-existing flake) |

---

## 技术债

| 项 | 数 | 详情 |
|---|---|---|
| 当前债数 | **0** | 全部闭环, 详见 `docs/TECH-DEBT.md` |
| 已修复 (历史) | **50+ 条** | 债 #1-#7 + Sprint 26-66 累计 + Sprint 128 #S105-1/2 + Sprint 161-168 lint/spec/W3 DQ/e2e 治本 + Sprint 169 复购周期 endpoint fix + Sprint 171 ad-hoc-query v2.0 闭环 (无新增债), 详见 `docs/TECH-DEBT.md` "已修复"section |
| Sprint 62.5 留尾 | **0 项** | 全部闭环 (B1+B2+B3+B4 + D4 ruff 留尾) |
| Sprint 62.5 闭环 | **9 commit 0 debt** | B1 backup retention (4 case) + B2 giant file bypass cap (2 case) + B3 ad-hoc-query tmp_write_conn (3 case) + B4 Codex clone GC (4 case). pytest 795/21/0 baseline 维持 |
| Sprint 62.5 实战 fix 沉淀 | **3 项 pattern** | (a) 100GB byte cap 反过来保护 109GB orphan → giant standalone 治理 (b) Sprint 25 backup retention 设计意图未实施 → 4 zst 169GB 累积 (c) Codex code_sign_clone 无 GC → 40 份 53GB 累积. 全部治根 + 永久测试覆盖 |
| Sprint 66 闭环 | **2 commit 0 debt (PR direct main 直做)** | P0 治根: `.github/workflows/lint.yml` e2e job env `FQ_DB_MODE: schema_test` (Sprint 63 P1b 漏修跨 5+sprint 复发). P1 治根: `gc_once()` 平台检查移到 `main()` 入口 (Linux CI runner 4 case FAILURE 真因). pytest 741/21/0 Linux runner 实证. CI 4/4 jobs 全绿 |
| Sprint 66 实战 fix 沉淀 | **2 项 pattern** | (a) Sprint 63 P1b 漏修跨 workflow 同步 e2e env → 5+sprint 复发 → 治根 + 3 个 regression test strict match. (b) 平台检查放核心逻辑 vs 入口反模式 → CI runner 跨平台 100% FAILURE → L4.10 永久规则 + 2 个 main()/gc_once() 配对 regression test |
| Sprint 66 housekeeping 闭环 | **3 类 stale state 清理 + L4.11 永久规则** | (1) 2 stale remote 删除 (tmp/work-plat) (2) 6 git stash clear (3) 13 Codex turn-diffs checkpoint refs + git gc --prune=now 清 21 dangling objects. Codex UI 不再误显示"未提交分支" |
| Sprint 99 收口 | **留尾 #11 ✅ 闭环** | Sprint 91 真修 commit `287efb8` 持续生效；新增 L4.20 + `check_ssot_drift.py` 防 close-memory 复制粘贴漂移，0 业务代码、VERSION 不变 |
| Sprint 101 收口 | **0 新债 / 0 新留尾** | Sprint 60+ 留尾 4 项闭环 + D1 按 30M 触发推后；L4.20 test 1 已由 Sprint 100 治根，L4.21 沉淀为永久规则 |
| FilterBuilder 12 service 推广 | ✅ 闭环 | Sprint 97 治标 → Sprint 98 真治本 (`OrderFilters.channel_in/not_in` 加 `table_alias`, FilterBuilder 集中处理别名, 全 service 0 post-processing `.replace()`) |
| Sprint 61 留尾 | **2 项** | ① P3 统一启动脚本 (跨 dev/CI/staging/profile, Sprint 62+) ② Sprint 60+ 留尾 1 项 (FilterBuilder params count 断言, 0.5d) 跨 sprint 累计 |
| Sprint 61 闭环 | **2 commit 0 debt (PR #27 待 merge)** | ① docs(readme) sync Sprint 54-61 状态行 (15 行) ② fix(backend) uvicorn 启动 fail-fast + FQ_DB_MODE 模式分流 (5/5 端到端场景验证全过) |
| Sprint 60+ 留尾 | **3 项 + 3 ruff 留尾** | ① FilterBuilder params count 断言 (0.5d) ② L4.7 ground-truth-lint: `_compute_*` 函数体内加 `assert sql.count('?') == len(params)` ③ L4.8 业务定义 SSOT 文档化: 写 `docs/business/RFM_DEFINITIONS.md` (跟 Sprint 14.5 P1.1 注释对齐) ④ Sprint 60+ ruff 留尾 3 (test_status_update.py:8 F401 sys + 37+38 F541 extraneous f prefix, Sprint 60.3 闭环) |
| Sprint 60+ 闭环 | **5 sprint 累计 14 commit 0 debt** | Sprint 60 (params 顺序错位) + 60.1 (Binder 500 channel 加 o. 别名) + 60.1.1 (Pydantic 422 强截断 + 修 Sprint 60 漏修 distribution) + 60.2 (RFM 8 象限 老客 GSV TTL 100% 治本) + 61 (P2 fail-fast + docs sync) |
| Sprint 59 留尾 | **1 项** | #3 50m scale 调研推 Sprint 60+ (触发条件 = 30M 数据量) |
| Sprint 59 闭环 | **3 项** | #6 STATUS.md 自动化 (4 字段 + 3 case test) + #5 CHANGELOG 按行数归档 (≤ 900 行 + archive_changelog.py) + #8 audit 措辞 SOP (5 规则 + 5 反例正例) |
| Sprint 58 闭环 | **3 项** | #4 CI e2e 持久化 (12+4 follow-up + auto_recover_ci.sh + e2e.yml auto-recovery) + #1 OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s) + #2 commit-msg blocking hook (误报率 0%) |
| 延后决策 | **1 条** | 50m-scale-architecture Phase 1-3 触发条件 = 30M 数据量 (Sprint 52 P2 留尾) |
| Sprint 34+ backlog | **1 条** | 候选 4: CI 跑 e2e (Sprint 58 期望 4/4 pass 闭环) |
| Recurring pattern | **1 个** | (a) race flake 治本 (Sprint 36.5, 治本 Sprint 53 闭环) ✅ 闭环 (b) e2e 50+MB OOM 治本 Sprint 58 #1 闭环, 跨 sprint 5+ 复发 #14 终止 (c) **uvicorn 接错 DB 静默 0 数据 P2 风险 → Sprint 61 治本** (FQ_DB_MODE profile-aware fail-fast) |

---

## 跨 sprint 关键状态行

| 维度 | 状态 | 最近 sprint | 详情 doc |
|---|---|---|---|
| 部署 | 本地即生产, merge → `git pull` → restart uvicorn | 持续 | `CLAUDE.md` §必读 #1 |
| 数据 ETL | W1→W2→W3→W4 4 阶段, 10.75M 订单, ~115GB DuckDB (orders ~108GB + fact_rfm_long ~5GB + 索引 ~2GB) | Sprint 28+ 验证 | `docs/architecture/DATA_PIPELINE.md` |
| AI Safety Net | L1 lint + L2 AST + L3 FilterBuilder 3 层防线 100% 闭环 | Sprint 54 | `docs/architecture/AI_SAFETY_NET.md` |
| Race flake | 治本 (per-worker tmp DuckDB + ATTACH read_only + search_path) | Sprint 53 | `docs/architecture/TEST_INFRASTRUCTURE.md` |
| e2e CI | advisory `continue-on-error: true` (50+MB OOM) | Sprint 41+ | `docs/operating/ci-e2e-history.md` |
| 数据布局 | data/cache/ data/exports/ data/parquet/ data/processed/ data/raw/ 5 区 | 持续 | `docs/data/data-layout.md` |
| 备份系统 | 7 天滚动 + 3 restore 演练, `data/processed/backups/*.duckdb.zst` | Sprint 25 | `scripts/etl/backup_duckdb.py` |
| 跨 sprint 沉淀 | 12 步流程 + worktree DUCKDB_PATH + Codex 协作工作流 + commit-msg blocking (误报率 0%) | 持续 | `CLAUDE.md` §0 + L4.x |
| **Sprint 58 #1 实战 fix 沉淀** | **e2e 50+MB OOM 治本 (DuckDB ATTACH read_only)** | **Sprint 58** | `docs/operating/ci-e2e-history.md` + `docs/sprints/HANDOFF-TO-CODEX-Sprint58-02.md` |
| **Sprint 58 #4 实战 fix 沉淀** | **CI e2e 持久化 (12+4 follow-up + auto_recover_ci.sh)** | **Sprint 58** | `docs/operating/ci-e2e-history.md` + `docs/sprints/HANDOFF-TO-CODEX-Sprint58-01.md` |
| **Sprint 58 #2 commit-msg blocking** | **WARN → blocking 升级 (误报率 17/20 → 0/14, Sprint 3 P1-3 4 轮修模式算法优化)** | **Sprint 58** | `scripts/commit_msg_check.py` + `.githooks/commit-msg` |
| **Sprint 实战 fix 沉淀** | **LESSONS_LEARNED.md 9 项 pattern 闭环** (DUCKDB_PATH / subagent / race flake / spec-lint / Codex / 12 步流程 / "破坏→验证→恢复" / commit msg↔diff / empty vs stub) | **Sprint 57** | `docs/development/LESSONS_LEARNED.md` |
| **Sprint 59 #6 STATUS 自动化** | **4 字段 + 3 case test, 闭环手改漂移** | **Sprint 59** | `scripts/status_update.py` |
| **Sprint 59 #5 CHANGELOG 按行数归档** | **≤ 900 行 + archive_changelog.py 脚本化滚动** | **Sprint 59** | `scripts/archive_changelog.py` |
| **Sprint 59 #8 audit 措辞 SOP** | **5 规则 + 5 反例正例 (Codex review #23 战略收缩)** | **Sprint 59** | `docs/development/AUDIT-WORDING.md` |
| **Sprint 62.5 B1 治根** | **backup_duckdb.py 加 _prune_old_backups() (Sprint 25 设计意图从未实施, 4 zst 169GB 累积). 8 项 safety check (mtime / keep_min / size / zstd magic / lsof / soft fail). 4 case regression test.** | **Sprint 62.5** | `scripts/etl/backup_duckdb.py` |
| **Sprint 62.5 B2 治根** | **cleanup cap giant standalone 治理路径 (100GB byte cap 反过来保护 109GB fuqing_e2e_yoyb.duckdb 永久孤儿. 加 strict magic + lsof 8 项校验后 bypass cap 但只删 1 个). 2 case regression test.** | **Sprint 62.5** | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans` |
| **Sprint 62.5 B3 治根** | **/ad-hoc-query tmp_write_conn() helper (TrackerDB.register + auto unlink + tracker.remove, 防 Bash 直调 duckdb 留 109GB orphan). 3 case regression test.** | **Sprint 62.5** | `scripts/ad_hoc_queries/_utils.py` |
| **Sprint 62.5 B4 治根** | **Codex code_sign_clone GC LaunchAgent (累积 40 份 = 53GB. 每天 03:00 清理 > 7d, 保留最新 1 份, 8 项 safety check). 4 case regression test.** | **Sprint 62.5** | `scripts/launchd/codex_clone_gc.py` + `com.local.codex-clone-gc.plist` |
| **Sprint 61 P2 治本** | **uvicorn 启动 fail-fast + FQ_DB_MODE 模式分流 (production raise / schema_test WARN only / 未知 mode 默认 production), 5/5 端到端场景验证全过 (happy_path + fail_fast_A/B + ci_mode + e2e). 拒绝自动 fallback + 全局 1GB 阈值 (污染测试边界 + 误伤 <1GB 测试库).** | **Sprint 61** | `backend/main.py:validate_startup_db()` + `backend/config.py:FQ_DB_MODE` |
| **Sprint 66 P0 治根** | **`.github/workflows/lint.yml` e2e job env 加 `FQ_DB_MODE: schema_test`** (Sprint 63 P1b 只改了独立 e2e workflow, 漏 CI workflow e2e job → 5+sprint CI test+e2e 双 FAILURE 复发). 配套 3 个 regression test (strict match `FQ_DB_MODE: schema_test` 整行, 防 substring 误报) | **Sprint 66** | `.github/workflows/lint.yml:77` + `backend/tests/test_ci_workflows_fq_db_mode.py` |
| **Sprint 66 P1 治根** | **`scripts/launchd/codex_clone_gc.py` 平台检查从 `gc_once()` 移到 `main()` 入口** (CI runner sys.platform=="linux" → gc_once() 永远 return (0,0) → 4 case 全 FAILURE 跨平台不兼容). 配套 L4.10 永久规则 + 2 个 regression test (`test_main_skips_on_non_darwin` + `test_main_calls_gc_once_on_darwin`). Linux CI runner 实证 741 passed / 21 skipped / 62 deselected | **Sprint 66** | `scripts/launchd/codex_clone_gc.py` + `CLAUDE.md L4.10` |
| **Sprint 66 housekeeping 闭环** | **收口后清 3 类 stale state**: ① 2 stale remote (`tmp` 来自 wt-sprint54/lane-c/.tmp-repo 路径不存在, `work-plat` 来自不同项目 DMP_test_package 误关联) ② 6 git stash (跨 4-9 sprint 旧数据, 内容已集成或 wip 残留) ③ 13 Codex turn-diffs checkpoint refs (`.git/refs/codex/turn-diffs/checkpoints/` 下悬空 commit 累积, Codex UI 误显示"未提交分支") + `git gc --prune=now` 清 21 个 dangling commit/tree/blob. `git fsck` 干净验证. 配套 L4.11 永久规则 (Codex checkpoint 每次 sprint 收口必清) | **Sprint 66** | `CLAUDE.md L4.11` |

---

## 启动检查 (新人 5 分钟)

```bash
# 1. 拉最新
git pull origin main --ff-only

# 2. 安装依赖
brew install --cask codex                # Codex 协作 (Sprint 43+)
pip install -r requirements.txt

# 3. 跑测试 (本机有 production DuckDB → 749 pass)
pytest

# 4. (可选) worktree 设 DUCKDB_PATH 指向主仓 db (L4.6)
export DUCKDB_PATH=/path/to/main/data/processed/fuqing_crm.duckdb

# 5. 启动服务
uvicorn backend.app:app --reload
```

---

## 关联文档

- [README.md](README.md) — 项目主入口
- [CLAUDE.md](CLAUDE.md) — AI 执行手册 (L1-L5 永久规则)
- [docs/README.md](docs/README.md) — 文档索引
- [docs/TECH-DEBT.md](docs/TECH-DEBT.md) — 技术债台账 (29 条已修 + 0 当前)
- [docs/data/data-layout.md](docs/data/data-layout.md) — data/ 目录布局
- [docs/architecture/DATA_PIPELINE.md](docs/architecture/DATA_PIPELINE.md) — ETL 4 阶段
- [docs/architecture/AI_SAFETY_NET.md](docs/architecture/AI_SAFETY_NET.md) — AI typo 防御 3 层
- [docs/architecture/TEST_INFRASTRUCTURE.md](docs/architecture/TEST_INFRASTRUCTURE.md) — pytest fixture + race flake
- [docs/architecture/50m-scale-architecture.md](docs/architecture/50m-scale-architecture.md) — 50M 行 benchmark
- [CHANGELOG.md](CHANGELOG.md) — 近 30 entry 滚动 (v0.4.14.119+) + Sprint 59 #5 阈值 ≤ 900 行 (archive_changelog.py 脚本化)

---

## Sprint 105 收口 (2026-06-24)

- **VERSION**: 0.4.14.20 (不变, 跟 Sprint 99+100+101+102+103+104 留尾治理 sprint 模式一致)
- **真业务 sprint 触发**: user 报 "增量ETL报 DuckDB 锁冲突" 触发
- **根因**: macOS launchd plist `com.fuqing.uvicorn` KeepAlive={SuccessfulExit:false} 5s 重启 race condition
- **修法**: scripts/etl/run-etl.sh launchctl bootout + bootstrap 治本, 1 file +79/-37 (净 +42), 0 抽象 0 helper
- **验收**: ETL exit 0 + 40 次采样无 uvicorn 抢锁 + KeepAlive PID 45300→46256 + pytest 819/23/0 baseline 持续
- **2 commits**: 78673ab fix(etl) + 8b4d8af docs(sprint) HANDOFF, merge commit 01aded6
- **累计 sprint 0 debt 55** (Sprint 105 闭环后, 跟 Sprint 56+...+104 累计 55 sprint 0 debt 持续)
- **L4.x 永久规则 22 stable 0 新增** (跟 Sprint 93+97+98+99+100+101+102+103+104 实战 fix 模式一致)
- **5 项 follow-up Sprint 106+**: SIGTERM fallback 死循环 + cross-user launchctl + DuckDB PID 白名单 + HEALTH_API_KEY 不一致 + 6 MEDIUM 留尾
- **跨 sprint 留尾治理 sprint 模式 stable 累计 22 sprint**

## Sprint 141.5 Phase 1 + 142 + 143 + vite preview fix 收口 (2026-06-28)

- **VERSION**: 0.4.14.20 (不变, 累计 34 sprint 不 bump, 跟 Sprint 134 user 拍板 "全部代码都收尾 + 不再提醒优化" 模式 stable)
- **真业务触发**: user 拍板"开始收尾 5 sprint 留尾", Sprint 141 收口后开启 4 sprint 并行开发链
- **范围**: 4 sprint 累计 49 files / +5807/-110 (Sprint 141.5 +6/+925 + Sprint 142 +21/+2190 + Sprint 143 +22/+1556 + vite preview fix +1/+12)
- **3 sprint 收口** (user 拍板合并):
  - **Sprint 141.5 Phase 1 (1 周纯 ETL)**: ETL `sample_received_at` 字段 schema 准备 (COALESCE 回退 pay_time, Phase 1 全 NULL, 等业务侧补数据源). Q1 已验: source data = CSV 不是 xlsx, 30 字段 COLUMN_MAPPING 无 receive_time, GIFT_SAMPLE_DB = "赠品&0.01渠道" (channels.py:133). commit `82eb4cc` + merge `505ae63`.
  - **Sprint 142 (真 refactor + 1 真业务)**: RFM 扩展 (lifecycle_stage + value_tier + potential_tier 3 新维度, 不替换 8 quadrant) + level 联动 summary 卡二级聚合 (`SamplingLevelSummary` + `summary_by_level`) + `_compute_lock_metrics` 单 SQL 合并 4 次查询 (micro-benchmark 1.513x, Q5 阈值降级 ≥1.5x 接受, 实质收益 26ms/call -33%). 2 个 Codex 主动越界修复保留 (`test_rfm_flow_ttl_ratio.py` race flake + `.githooks/check_imports.py` Python < 3.10 compat). commit `8a4f357` + merge `a8711ee`.
  - **Sprint 143 (1 真业务 + 2 全新建)**: LTV 90/180/365d (新 service + W4 cache) + cohort retention matrix (新 service + CohortRetentionMatrix.vue 热力图) + 改名 ROI → 正装转化分析 (Q10 推荐 A 仅前端文案, API 字段 `sampling_roi` 保留 0 breaking change). commit `6244aab` + merge `5bd1754`.
  - **vite preview proxy 修复 (Sprint 142+143 收口后)**: `frontend-vue3/vite.config.ts` 加 `preview.proxy` (vite preview 不读 `server.proxy`, frontend `/api/*` 直接被 vite preview 当 static file 404). commit `52f41cf`.
- **4 个 open question 决策**:
  - Q1 已验: source data = CSV 无 receive_time (Sprint 141.5 Phase 1 拆 Phase 1/Phase 2)
  - Q2 暂收口: 业务侧补 ETL 数据源方式 (user 拍板"不需要", 跟 Sprint 144+/145+ 一同暂收口)
  - Q5 降级: micro-benchmark ≥2x → ≥1.5x (user 拍板"接受 1.513x")
  - Q10 拍板: 改名 ROI 范围 (user 拍板"仅前端文案, API 保留")
- **并行开发约定严格执行** (0 冲突区): Sprint 142 改 SamplingView.vue L400-460 + Sprint 143 改 L387 subtitle + 新增 Tab 3 <CohortRetentionMatrix>; Sprint 142 先合 → Sprint 143 后合 (跟 handoff Section 6 约定一致)
- **race flake L5.1 接受** (跨 sprint Sprint 36-5 + 38 + 105 + 141.5 + 142 实战 fix 模式 stable): test_rfm_flow_ttl_ratio Unique file handle conflict (uvicorn PID 占 DuckDB file lock), Sprint 142 Codex 主动修 monkeypatch fixture, 治本 ROI 低 (DuckDB file lock exclusive), Sprint 134 模式 advisory 接受
- **L4.x 永久规则 22 stable 0 新增** (跟 Sprint 65+135+138 模式 stable, 留尾治理 + 真 refactor + 真业务 sprint 0 永久规则追加)
- **网络 push 沙箱限制**: Sprint 141.5 Phase 1 第一次 push 2 次超时 (Empty reply from server / Recv failure), 但 Sprint 142+143 push 全部 1 次成功 (沙箱网络间歇性)
- **pytest 762/23/0** (worktree 793/41/0 race flake 接受; baseline 740 → 762 +24 case: Sprint 141.5 +2 + Sprint 142 +12 + Sprint 143 +10)
- **累计 67 sprint 0 debt** (Sprint 60-66 + 67+68+69 + 89-105+110+111+112+113+114+116+117+118 + 134-138 + 141 + 141.5 Phase 1 + 142 + 143, 跨 sprint 留尾治理 sprint 模式 stable)
- **Sprint 144+/145+ 暂收口** (跟 Sprint 89/134 模式 stable, user 2026-06-28 拍板"不需要做, 没意义", 等真业务触发再开)
