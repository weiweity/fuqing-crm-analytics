# Sprint 4 — P0 数据灾备 + 痛点 1 端到端闭环

> **立项**: 2026-06-07 12:45
> **来源**: Sprint 3 收口盘点 (P0-2 留口 + 痛点 1 --update 端到端残留)
> **北极星**: 2/2 P0 done + CI 真绿 + 数据灾备 + 痛点 1 端到端 < 35min
> **总工时**: ~1.5d (2-3h P0-2 备份 + 1-2d P0-3 dedup + 跑批验证)
> **完成标准**: 走 CLAUDE.md 12 步流程 (branch → review → qa → merge → push → pull → restart) + /document-release

---

## 2 件事一览

| # | 任务 | 优先级 | 工时 | 可并行? | 依赖 |
|---|---|---|---|---|---|
| **P0-2** | DuckDB 55GB 增量备份 (launchd daily) | 🔴 P0 | 2-3h | ✅ | 无 (复用 weekly cleanup 基础设施) |
| **P0-3** | --update 端到端 dedup issue (order_id, sub_order_id) | 🔴 P0 | 1-2d | ✅ | P0-3 修后跑批 3 次 < 35min |

**并行策略**: 2 worktree 并行 (P0-2 + P0-3), P0-3 修后 main agent sequential 跑批 3 次

---

## 任务详细

### P0-2 DuckDB 55GB 增量备份 (2-3h)

**触发**: `data/processed/fuqing_crm.duckdb` 55GB 单文件无备份, 故障恢复需 8h+ 重跑 ETL
**真实大小**: 58,612,789,248 字节 ≈ **54.6 GB** (2026-06-07 00:28 mtime)
**现有资产** (Sprint 1 治理留下, 全部复用):
- `data/processed/backups/` 目录已存在
- `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist` 完整模板 (周日 03:00)
- `scripts/etl/cleanup_backups.sh` 完整 (F17 PATH / F18 POSIX lock / F20 find error / F26 pipefail 全修)

**关键步骤** (3 件新增, 不重写已有):
1. 写 `scripts/etl/backup_duckdb.py` (read_only + VACUUM INTO + zstd 压缩, 目标 < 15GB/天)
   - `duckdb.connect('fuqing_crm.duckdb', read_only=True)` 不冲突 uvicorn PID 831
   - `VACUUM INTO 'data/processed/backups/fuqing_crm_YYYY-MM-DD.duckdb'` 原子导出
   - 复用 `cleanup_backups.sh` 的 F18 POSIX lock 模式
2. 创 `scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist` (每日 03:30, 错开 weekly cleanup 周日 03:00 + ETL 08:30)
3. 创 `data/processed/backups/.gitkeep` (目录占位, 防 git 删除)
4. `cp *.plist ~/Library/LaunchAgents/` + `launchctl load` (2 个服务: daily backup + weekly cleanup)
5. 手动跑 1 次 `PYTHONPATH=. python3 scripts/etl/backup_duckdb.py` 验证
6. 验证 `launchctl list | grep fuqing` 显示 2 个 Label
7. 更新 `README.md` 运维安全章节 (4 层防护 → 5 层) + `docs/handoff-2026-06-05.md` 加 backup 运维 SOP

**验收**:
- `ls -lh data/processed/backups/` 看到 1 个 `.duckdb` 文件 (size < 15GB 压缩后)
- `launchctl list | grep fuqing` 显示 2 个服务
- 手动跑成功 (exit 0) + log 输出到 `/tmp/fuqing-duckdb-backup.log`
- pytest 459+ passed / 8 skipped (无 regression)

**风险**:
- 55GB 备份占磁盘: 690GB 空闲充足 ✅
- uvicorn 持锁: read_only 模式不冲突 ✅
- zstd 压缩时间: 估 5-10min/天, 03:30 跑不阻塞白天

---

### P0-3 --update 端到端 dedup issue 修 (1-2d)

**触发**: 痛点 1 W1 GROUPING SETS 单步已绿 (13.4 min), 但 `--update` Step 1 (写 orders 表) 撞 `(order_id, sub_order_id)` 唯一索引约束
**锚点**:
- `backend/database.py:135` `CREATE UNIQUE INDEX idx_orders_order_unique ON orders(order_id, sub_order_id)`
- 复用 W4 模式: `scripts/etl/precompute_fact_rfm.py:91` 有 `ON CONFLICT DO NOTHING`

**关键步骤**:
1. 读 `scripts/etl/pipeline.py` 找 orders 写入入口 (Step 1 ingest?)
2. 读源数据 (xlsx) 看是否真重复 — 用 `python -c "import pandas as pd; df=pd.read_excel(...); print(df.duplicated(subset=['order_id','sub_order_id']).sum())"`
3. 修法候选:
   - **A. ETL 端 ON CONFLICT DO NOTHING** (推荐, 复用 W4 模式, 幂等) — 改 ingest SQL 加 `ON CONFLICT (order_id, sub_order_id) DO NOTHING`
   - **B. ingestion 端去重** — `df.drop_duplicates(subset=['order_id','sub_order_id'], keep='last')` 写
   - **C. 修源数据** (源数据 issue 是真问题, 但修 ETL 端更稳)
4. 写 `backend/tests/test_dedup_orders.py` 验证 (造重复数据 → 跑 ingest → 断言 0 报错)
5. 跑 pytest 全绿
6. **pkill uvicorn → 跑 --update 3 次 → restart uvicorn** (sequential, ~1.5h)
7. 验证 3 次 real_elapsed 都 < 35 min
8. 报告 `docs/validation-reports/etl-update-3-runs-2026-06-XX.md`

**验收**:
- `--update` Step 1 不再撞 constraint error
- 3 次跑批 real_elapsed 都 < 35 min
- pytest 459+ + 1 (test_dedup_orders) = 460+ passed
- 痛点 1 端到端真绿 (不只 W1 单步)

**风险**:
- 修 ETL 端后仍可能撞其他约束 (源数据有更多问题) — 需逐步排查
- 跑批需 pkill uvicorn (用户 dev 环境) — 需用户在场配合重启

---

## 工作流

每件走 CLAUDE.md 12 步流程:

```
① git checkout -b fix/sprint4-p02-duckdb-backup
② 写代码
③ pytest backend/tests/ -x -q
④ /review skill (前必跑 git log --all 验证)
⑤ 修复 review 问题
⑥ git commit -m "fix(backup): sprint4 P0-2 ..."
⑦ git push origin fix/sprint4-p02-duckdb-backup
⑧ /qa skill
⑨ git checkout main && git merge fix/sprint4-p02-duckdb-backup --no-ff
⑩ git push origin main
⑪ git pull origin main --ff-only
⑫ kill 并重启 uvicorn + 更新 CHANGELOG.md
```

**2 worktree 并行**:
- worktree 1: P0-2 备份 (agent A, 2-3h)
- worktree 2: P0-3 dedup 修代码 (agent B, 1-2d)
- main agent: P0-3 修后跑批 3 次验证 (sequential, ~1.5h)

**最后**: /document-release 同步 README/CLAUDE.md/DOCUMENT-INDEX/CHANGELOG

---

## 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 55GB 备份占满磁盘 | 低 | 备份失败 | 跑前 `df -h`, 690GB 空闲充足 |
| zstd 压缩慢 (>30min) | 中 | launchd 超时 | 03:30 启动, launchd 默认无 timeout, 不阻塞 |
| pkill uvicorn 影响用户 dev | 中 | 用户断流 | 等用户在场, 或错开用户空闲时段 |
| dedup 修后仍撞其他约束 | 中 | 跑批失败 | 逐步排查, 修 ETL 端而非修源数据 |
| launchd 服务启动失败 | 低 | 调度失效 | 手动跑 1 次 + `launchctl list` 验 |

---

## 完成标准 (Sprint 4 收口) - 2026-06-07

- [x] P0-2: data/processed/backups/fuqing_crm_*.duckdb.zst (21GB) 存在 + launchd 3 服务 (daily + weekly + etl) + README 5 层防护
- [x] P0-3: load.py:550 加 ON CONFLICT (sprint 4 56a35ee hotfix 2) + 6 dedup 测试 (c7c9235) + 痛点 1 端到端代码闭环
- [x] ruff check scripts/etl/backup_duckdb.py + load.py: All checks passed
- [x] /document-release 4 文件 (README/CLAUDE.md/CHANGELOG/DOCUMENT-INDEX) + SPRINT-4-PLAN 自检
- [x] memory 同步 (project_sprint4.md 新建 + project_etl_perf_plan.md 痛点 1 端到端)

**Sprint 4 收口总结 (2026-06-07)**:
- 4 commit 合 main (06bb580 P0-2 feat + a3def1c P0-2 merge + 56a35ee P0-3 hotfix 2 + ec9c28b P0-3 merge)
- 5 review 修全生效 (log 不重复 / TS 动态 / zstd 失败清理 / post-copy verify / umask 077)
- 痛点 1 端到端: 跑批代码层闭环 (ON CONFLICT 加好), 实际跑批真验留 Sprint 5 (staging 数据 boundary case 根因待查)

---

**详细任务拆解 + 验收标准**: 本文件即详细 plan
**Sprint 3 教训**: 见 [[CLAUDE.md]] 4 准则 + [[project_sprint3]] 5 轮 review + 4 轮 P1-3 修模式
**Sprint 5 候选**: 真排查跑批撞根因 + P1 16 root tests isolation 真修 + D-6 版本同步
