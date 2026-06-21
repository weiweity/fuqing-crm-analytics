# 项目状态 (Project Status)

> **单一 source of truth**. README.md / CLAUDE.md 状态行均链接到这里。Sprint 收口后必更新。

**最后更新**: 2026-06-21 (Sprint 58 工具链实战 fix 闭环收口, v0.4.14.142, main HEAD `17b5361`)

---

## 版本

| 项 | 值 |
|---|---|
| VERSION | `0.4.14.142` |
| git HEAD (main) | `17b5361` (Sprint 58 #2 阶段 B merge, commit-msg blocking 升级) |
| 当前分支 | `main` |
| 最近 sprint | Sprint 58 (工具链实战 fix: #4 CI e2e 持久化 + #1 OOM 治本 + #2 commit-msg blocking hook) |
| 收口日 | 2026-06-21 |
| 上次合入 | 7 commit 0 debt (Sprint 58: 09e2a18 + b567a68 #1 amend + 5c3794b + 6a5b12b #2A + 11416b5 + 17b5361 #2B + VERSION bump 待 commit) |

---

## 测试状态

| 维度 | 数 | 备注 |
|---|---|---|
| pytest passed | **754** | Sprint 58 收口, Sprint 58 doc + code 改动无新增 test (pytest 数字跟 Sprint 57 持平) |
| pytest skipped | **1** | `test_w4_full.py:319` PID 锁 fd, fixture 模式 skip (Sprint 53 治本) |
| pytest failed | **0** | 上次 green |
| e2e (Playwright) | **11/11 spec-lint / 期望 e2e 实测 12/12** | Sprint 33.2 router-registered smoke + Sprint 32.2 canvas 修复 |
| ruff lint | **clean** | Sprint 55.1 修 8 F401 + Sprint 55.5 facade 删无 F401 |
| L1 SQL f-string lint | **0 violations** | 101 files scanned, `backend/scripts/check_sql_fstring_consistency.py` |
| L2 AST spec-lint | **0 violation / 0 warn** | `frontend-vue3/e2e/lint/spec-lint-l2.py` 11 spec checked |
| ground-truth-lint (L3) | **0 violations** | `backend/scripts/check_filter_builder_usage.py` 69 files |
| GH Actions CI | **4/4 pass (期望)** | Sprint 58 #1 OOM 治本 (DuckDB ATTACH read_only) + #4 auto-recovery, e2e 治本不再需要 `continue-on-error` |
| pre-commit hooks | **10 件 OK** | `.githooks/pre-commit` (9 件) + `.githooks/commit-msg` (Sprint 58 #2 升级 blocking, 误报率 0%) |
| vite build | **750ms** | Sprint 58 验证, 0 errors |
| commit-msg blocking 误报率 | **0/14 = 0%** | Sprint 58 #2 阶段 B 验证 N=20 commit sample (6 merge skip, 14 普通 commit 全 pass) |

---

## 技术债

| 项 | 数 | 详情 |
|---|---|---|
| 当前债数 | **0** | 全部闭环, 详见 `docs/TECH-DEBT.md` |
| 已修复 (历史) | **29 条** | 债 #1-#7 + Sprint 26-55 累计 |
| Sprint 58 留尾 | **4 项** | Sprint 59 收割季 (#6 STATUS 自动化 + #5 CHANGELOG 阈值收紧 + #8 audit 措辞精确化) + #3 50m scale 调研推后 |
| Sprint 58 闭环 | **3 项** | #4 CI e2e 持久化 (12+4 follow-up + auto_recover_ci.sh + e2e.yml auto-recovery) + #1 OOM 治本 (DuckDB ATTACH + workers 1 + timeout 60s) + #2 commit-msg blocking hook (误报率 0%) |
| 延后决策 | **1 条** | 50m-scale-architecture Phase 1-3 触发条件 = 30M 数据量 (Sprint 52 P2 留尾) |
| Sprint 34+ backlog | **1 条** | 候选 4: CI 跑 e2e (Sprint 58 期望 4/4 pass 闭环) |
| Recurring pattern | **1 个** | (a) race flake 治本 (Sprint 36.5, 治本 Sprint 53 闭环) ✅ 闭环 (b) e2e 50+MB OOM 治本 Sprint 58 #1 闭环, 跨 sprint 5+ 复发 #14 终止 |

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
- [CHANGELOG.md](CHANGELOG.md) — 近 30 entry 滚动 (v0.4.14.119+)
