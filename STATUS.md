# 项目状态 (Project Status)

> **单一 source of truth**. README.md / CLAUDE.md 状态行均链接到这里。Sprint 收口后必更新。

**最后更新**: 2026-06-21 (Sprint 56 Phase 1+2 收口, v0.4.14.140, main HEAD `277a4b1`)

---

## 版本

| 项 | 值 |
|---|---|
| VERSION | `0.4.14.140` |
| git HEAD (main) | `277a4b1` (Sprint 56 Phase 1+2 merge + VERSION bump, ff-merge from `refactor/sprint56-phase1-phase2`) |
| 当前分支 | `main` |
| 最近 sprint | Sprint 56 (CHANGELOG 30 entry 滚动 + 4 stub doc 补实 + DRY 拆解) |
| 收口日 | 2026-06-21 |
| 上次合入 | 4 commit 0 debt (Sprint 56: a145a1a + de40843 + b22dbe9 merge + 277a4b1 VERSION bump) |

---

## 测试状态

| 维度 | 数 | 备注 |
|---|---|---|
| pytest passed | **758** | Sprint 56 收口, doc-only 改动无新增 test, 跟 Sprint 55.5 一致 |
| pytest skipped | **1** | `test_w4_full.py:319` PID 69630 锁 fd, fixture 模式 skip (Sprint 53 治本) |
| pytest failed | **0** | 上次 green 758/759 |
| e2e (Playwright) | **12/12 pass** | Sprint 33.2 router-registered smoke + Sprint 32.2 canvas 修复 |
| ruff lint | **clean** | Sprint 55.1 修 8 F401 + Sprint 55.5 facade 删无 F401 |
| L1 SQL f-string lint | **0 violations** | 101 files scanned, `backend/scripts/check_sql_fstring_consistency.py` |
| L2 AST spec-lint | **0 violation / 0 warn** | `frontend-vue3/e2e/lint/spec-lint-l2.py` 11 spec checked |
| ground-truth-lint (L3) | **0 violations** | `backend/scripts/check_filter_builder_usage.py` 69 files |
| GH Actions CI | **3/4 pass** | lint + ground-truth-lint + pytest pass; e2e 治标 `continue-on-error: true` (50+MB OOM, 跨 sprint #14) |
| pre-commit hooks | **9 件 OK** | `.githooks/pre-commit`, Sprint 50.1 L2 default + L1 fallback |
| vite build | **750ms** | Sprint 56 验证, 0 errors |

---

## 技术债

| 项 | 数 | 详情 |
|---|---|---|
| 当前债数 | **0** | 全部闭环, 详见 `docs/TECH-DEBT.md` |
| 已修复 (历史) | **29 条** | 债 #1-#7 + Sprint 26-55 累计 |
| Sprint 56 留尾 | **5 项** | 4 stub doc 内容已补实; 5 项核心 + 14 项 P2/P3 推 Sprint 57+ |
| 延后决策 | **1 条** | 50m-scale-architecture Phase 1-3 触发条件 = 30M 数据量 (Sprint 52 P2 留尾) |
| Sprint 34+ backlog | **2 条** | 候选 4: CI 跑 e2e (Sprint 32.3 留尾) / 候选 2: commit msg ↔ diff CI check (误报率高推后) |
| Recurring pattern | **2 个** | (a) Recurring race flake 治标 (Sprint 36.5, 治本 Sprint 53 闭环) (b) e2e 50+MB OOM 治标 (Sprint 41-55 跨 sprint 复发) |

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
| 跨 sprint 沉淀 | 12 步流程 + worktree DUCKDB_PATH + Codex 协作工作流 | 持续 | `CLAUDE.md` §0 + L4.x |

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
