# 项目状态 (Project Status)

> **单一 source of truth**. README.md / CLAUDE.md 状态行均链接到这里。Sprint 收口后必更新。

**最后更新**: 2026-06-22 (Sprint 66 收口: CI 维修 P0+P1 治根闭环, v0.4.14.155, main HEAD `61ae76a` + pytest 741/21/0 Linux CI runner 实证, CI 4/4 jobs 全绿)

---

## 版本

| 项 | 值 |
|---|---|
| VERSION | `0.4.14.155` |
| git HEAD (main) | `56fc924` (Sprint 66 收口 merge: P0 lint.yml FQ_DB_MODE + P1 codex_clone_gc 平台检查迁移 main + L4.10 + VERSION bump) |
| 当前分支 | `main` |
| 最近 sprint | Sprint 66 (CI 维修, 2 commit 0 debt, P0 lint.yml FQ_DB_MODE 漏修 5+sprint 复发治根 + P1 codex_clone_gc Linux runner 平台检查反模式治根) |
| 收口日 | 2026-06-22 |
| 上次合入 | Sprint 66 (PR direct `61ae76a`, 2 commit 串行, chore release main 直做模式) |

---

## 测试状态

| 维度 | 数 | 备注 |
|---|---|---|
| pytest passed | **768** | Sprint 61 P2 实施时实测 (pytest 9:10, 21 skipped 含 production DuckDB 不可用) |
| pytest skipped | **21** | Sprint 61 P2 实测: 1 `w4_full:319` PID 锁 fd + 20 production DuckDB 不可用跨 sprint 留尾 |
| pytest failed | **0** | Sprint 66 P1 CI runner 实测 741 passed / 21 skipped / 62 deselected (Linux ubuntu-latest 实证) |
| e2e (Playwright) | **12/12 smoke (blocking)** | Sprint 60.3+ C+: UI smoke + API 5xx 拦截, 不再依赖 production DuckDB |
| ruff lint | **0 errors** | Sprint 60.3 修 5 处 status_update.py PEP8 + 3 处 test_status_update.py 留尾 |
| L1 SQL f-string lint | **0 violations** | 101 files scanned, `backend/scripts/check_sql_fstring_consistency.py` |
| L2 AST spec-lint | **0 violation / 0 warn** | `frontend-vue3/e2e/lint/spec-lint-l2.py` 11 spec checked |
| ground-truth-lint (L3) | **0 violations** | `backend/scripts/check_filter_builder_usage.py` 69 files |
| GH Actions CI | **4/4 pass** | Sprint 66 P0+P1 闭环: lint SUCCESS + ground-truth-lint SUCCESS + test SUCCESS (Linux runner 实证) + e2e SUCCESS (Sprint 66 P1 run #27967486199 / #27967486220) |
| pre-commit hooks | **10 件 OK** | `.githooks/pre-commit` (9 件) + `.githooks/commit-msg` (Sprint 58 #2 升级 blocking, 误报率 0%) |
| vite build | **750ms** | Sprint 58 验证, 0 errors |
| commit-msg blocking 误报率 | **0/14 = 0%** | Sprint 58 #2 阶段 B 验证 N=20 commit sample (6 merge skip, 14 普通 commit 全 pass) |

<!-- STATUS-AUTO-START -->
| pytest collected | **803** | Sprint 59 自动抓 |
| pytest skipped | **0** | Sprint 59 自动抓 |
| 当前债数 | **0** | Sprint 59 自动抓 |
| 最近 sprint | **Sprint 62** | Sprint 59 自动抓 |
<!-- STATUS-AUTO-END -->

---

## 技术债

| 项 | 数 | 详情 |
|---|---|---|
| 当前债数 | **0** | 全部闭环, 详见 `docs/TECH-DEBT.md` |
| 已修复 (历史) | **30 条** | 债 #1-#7 + Sprint 26-58 累计 + Sprint 61 P2 治本 (uvicorn 接错空/过期 DB) |
| Sprint 62.5 留尾 | **0 项** | 全部闭环 (B1+B2+B3+B4 + D4 ruff 留尾) |
| Sprint 62.5 闭环 | **9 commit 0 debt** | B1 backup retention (4 case) + B2 giant file bypass cap (2 case) + B3 ad-hoc-query tmp_write_conn (3 case) + B4 Codex clone GC (4 case). pytest 795/21/0 baseline 维持 |
| Sprint 62.5 实战 fix 沉淀 | **3 项 pattern** | (a) 100GB byte cap 反过来保护 109GB orphan → giant standalone 治理 (b) Sprint 25 backup retention 设计意图未实施 → 4 zst 169GB 累积 (c) Codex code_sign_clone 无 GC → 40 份 53GB 累积. 全部治根 + 永久测试覆盖 |
| Sprint 66 闭环 | **2 commit 0 debt (PR direct main 直做)** | P0 治根: `.github/workflows/lint.yml` e2e job env `FQ_DB_MODE: schema_test` (Sprint 63 P1b 漏修跨 5+sprint 复发). P1 治根: `gc_once()` 平台检查移到 `main()` 入口 (Linux CI runner 4 case FAILURE 真因). pytest 741/21/0 Linux runner 实证. CI 4/4 jobs 全绿 |
| Sprint 66 实战 fix 沉淀 | **2 项 pattern** | (a) Sprint 63 P1b 漏修跨 workflow 同步 e2e env → 5+sprint 复发 → 治根 + 3 个 regression test strict match. (b) 平台检查放核心逻辑 vs 入口反模式 → CI runner 跨平台 100% FAILURE → L4.10 永久规则 + 2 个 main()/gc_once() 配对 regression test |
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
