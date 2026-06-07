# Sprint 3 — P0+P1 遗留清理

> **立项**: 2026-06-06 21:00
> **来源**: Sprint 2 收口盘点 (e498143 之后, 5 件遗留)
> **北极星**: 5/5 done + CI 真绿 + memory 同步
> **总工时**: ~10.5h (1.5 工作日)
> **完成标准**: 每件走 CLAUDE.md 12 步流程 (branch → review → qa → merge → push → pull → restart) + /document-release
> **收口状态**: 2026-06-07 4/5 done (P0-1 痛点 1 闭环 + P1-1 W3/W4 CI smoke + P1-2 16 root tests isolation + P1-3 ground-truth lint 4 轮修). P0-2 DuckDB 41GB 增量备份 deferred Sprint 4.
> **CI 状态**: 三连绿 (run 27082443532 / 27062413467 / 27063611644)

---

## 5 件事一览

| # | 任务 | 优先级 | 工时 | 可并行? | 依赖 |
|---|---|---|---|---|---|
| **P0-1** | 痛点 1 跑批验证 2 次 (目标 < 35min) | 🔴 P0 | 3h | ❌ 自身 sequential (3 次跑批) | 无 |
| **P0-2** | DuckDB 41GB 增量备份 (launchd daily) | 🔴 P0 | 2h | ✅ | 无 |
| **P1-1** | W3/W4 pipeline CI smoke test (e60dbfd 缺口) | 🟡 P1 | 1.5h | ✅ | 无 |
| **P1-2** | 16 root ./tests/ isolation failures 修或 ignore | 🟡 P1 | 3h | ✅ | 无 |
| **P1-3** | /review 前 git log --all 自动化 lint | 🟡 P1 | 1h | ✅ | 无 |

**并行策略**: 5 件同时开 5 个 worktree, P0-1 单 agent sequential 跑 3 次, 其他 4 件各 1 agent

---

## 任务详细

### P0-1 痛点 1 跑批验证 2 次 (3h)

**触发**: 6/4 baseline 1/3 = real elapsed **63.2min**, 已比 W1 优化前 41min 还慢

**关键步骤**:
1. 读 `data/processed/_baseline/6-4-step-time.json` 找 step 耗时异常 (W1 GROUPING SETS step 7b?)
2. 排查 W1 + 5 hotfix (commit 682f0cd) 是否在 `run_auto_preload`/`run_range_preload` 路径实际生效
3. 跑第 2 次 `--update` (用 homebrew Python 3.14), 记 step_wall_time_sum + real_elapsed
4. 跑第 3 次, 三次取中位数
5. 写 `docs/validation-reports/etl-3-runs-2026-06-XX.md`
6. 更新 `memory/project_etl_perf_plan.md` L95 痛点 1 状态

**验收**:
- ✅ 三次 real elapsed 都 < 35min (目标达成) → 痛点 1 🟢 闭环
- ⚠️ 三次都 ≥ 35min → 显式标"优化未达预期" + 排查结论 (回归点定位)

**风险**: DuckDB 41GB 单文件锁 (uvicorn 66129 持锁), 跑批前需要 pkill -f "uvicorn backend.main:app" → 跑批 → 重启 uvicorn

---

### P0-2 DuckDB 41GB 增量备份 (2h)

**触发**: `data/processed/duckdb_main.db` 41GB 单文件无备份, 故障恢复需 8h+ 全量重跑 ETL

**关键步骤**:
1. 写 `scripts/etl/backup_duckdb.py` (rsync partial + zstd 压缩, 目标 < 10GB/天)
2. 创 `data/backups/.gitkeep` + 7 天保留清理
3. 写 `scripts/etl/com.fuqing.duckdb-backup.daily.plist` (03:30 daily, 错开 ETL 03:00 + backup-cleanup 03:00)
4. `launchctl load` + `launchctl list | grep fuqing` 验证
5. 手动跑 1 次验证: `data/backups/duckdb_2026-06-07.db` 存在 + size 合理
6. 更新 `README.md` 运维安全章节 (4 层防护 → 5 层) + `docs/handoff-2026-06-05.md`

**验收**: 1 次真跑成功 (备份文件 ≥ 30GB) + launchd 调度就绪 + 7 天保留 cleanup 测试

**风险**: 41GB 备份占磁盘, 需提前 `df -h` 检查 (data 盘应 ≥ 200GB 空闲)

---

### P1-1 W3/W4 pipeline CI smoke test (1.5h)

**触发**: sprint 2 task 1 (e60dbfd) 合了 step 7b/8 skip flag + 幂等, 但 CI 不跑 ETL pipeline, 改 W3/W4 集成代码不会被 CI 拦

**关键步骤**:
1. 读 `scripts/run_etl.py` + `scripts/etl/pipeline.py` 找最小可 mock 入口
2. 写 `backend/tests/test_w3w4_pipeline_smoke.py` (mock parquet, 跑 pipeline.run 5min):
   - step 7b `--skip-dq` flag 生效
   - step 8 W4 幂等 (跑 2 次行数不变)
   - 1 断言 quarantine 触发能进 `rfm_quarantine` 表
3. 加进 `.github/workflows/lint.yml` (或新 workflow)
4. 本地 `pytest backend/tests/test_w3w4_pipeline_smoke.py -v` 跑通
5. PR + CI 绿

**验收**: pytest 新文件通过 + CI run 显示这个 test 跑过 + 用 ruff lint 过

---

### P1-2 16 root ./tests/ isolation failures 修或 ignore (3h)

**触发**: `./tests/` 根目录 16 测试跑失败 (CI scope `pytest backend/tests/` 不影响, 但本地体验污染)

**关键步骤**:
1. `cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" && pytest ./tests/ --collect-only` 列出 16 个
2. 跑 1 次看具体失败原因 (分类型: fixture scope 冲突 / DuckDB lock / 状态污染)
3. 决策:
   - **修**: 加 `conftest.py` fixture scope=session / 临时 DuckDB 路径
   - **ignore**: `pyproject.toml` `[tool.pytest.ini_options]` addopts = `"--ignore=./tests/"` 或 testpaths = `["backend/tests"]`
4. PR + 验证 CI 没坏 (`pytest backend/tests/ -x -q` 仍全绿)

**验收**: `pytest ./tests/` 全绿 **或** 默认配置不再扫 root

---

### P1-3 /review 前 git log --all 自动化 lint (1h)

**触发**: CLAUDE.md L119-134 有纪律但靠人记 (D-4 教训: 4 个 ground truth 错误)

**关键步骤**:
1. 写 `.githooks/check_review_ground_truth.py` (pre-commit 钩子)
2. 扫 `git diff --staged` 找触发词: "未集成" / "不存在" / "占位" / "TODO" / "FIXME" + 强制要求 reviewer 输出附件 `git log <path>`
3. 触发词出现但没附件 → commit 拒绝 + 提示跑 git log
4. 加进 `.githooks/pre-commit`
5. **故意写个假 "X 未集成" commit 验证被拦** (red team test)
6. 真实 commit 不被误拦 (regression test)
7. PR + CI 绿

**验收**: 故意假 ground truth 被拦 + 真实 commit 通过

---

## 工作流

每件走 CLAUDE.md 12 步流程:

```
① git checkout -b fix/sprint3-p01-etl-validation
② 写代码 (按上面步骤)
③ pytest backend/tests/ -x -q
④ /review skill (前必跑 git log --all 验证)
⑤ 修复 review 问题
⑥ git commit -m "fix(etl): sprint3 P0-1 ..."
⑦ git push origin fix/sprint3-p01-etl-validation
⑧ /qa skill
⑨ git checkout main && git merge fix/sprint3-p01-etl-validation --no-ff
⑩ git push origin main
⑪ git pull origin main --ff-only
⑫ kill 并重启 uvicorn + 更新 CHANGELOG.md
```

**5 件并行 (4 worktree + 1 sequential)**:
- worktree 1: P0-2 DuckDB 备份 (agent A)
- worktree 2: P1-1 W3/W4 CI smoke (agent B)
- worktree 3: P1-2 16 tests isolation (agent C)
- worktree 4: P1-3 /review lint (agent D)
- main agent: P0-1 痛点 1 跑批 sequential (因为 3 次跑批不能并行, 也用同一 DuckDB 实例)

**最后**: /document-release 同步 README/CLAUDE.md/DOCUMENT-INDEX/CHANGELOG

---

## 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DuckDB 41GB 锁冲突 (uvicorn 持锁) | 高 | 跑批/W3W4 smoke 卡住 | pkill uvicorn → 操作 → restart uvicorn |
| 备份 41GB 占满磁盘 | 中 | 备份失败 + 生产停 | 跑前 `df -h`, 备份用 zstd 压缩 |
| /review 自动化钩子误拦真实 commit | 中 | workflow 阻塞 | red team + regression test 双向验证 |
| 痛点 1 跑批 3 次都 > 35min | 中 | P0-1 失败 → 需排查回归点 | 跑前 git log 验 W1 commit 682f0cd 在 preload 路径 |
| 16 tests 修比 ignore 难得多 | 高 | 3h 可能不够 | 先 try ignore 路线 (1h), 修留 Sprint 4 |

---

## 验收总览 (2026-06-07 sprint 3 收口 4/5)

| 任务 | 状态 | 关键交付 | 合并 commit |
|---|---|---|---|
| **P0-1** 痛点 1 跑批验证 | ✅ **done** (闭环 🟢) | W1 GROUPING SETS 3 次跑批 13.4 min 平均 < 35 min 目标, CV 9.4%. 报告 `docs/validation-reports/etl-3-runs-2026-06-07.md` 340 行 | `d34fda7` (docs) |
| **P0-2** DuckDB 41GB 增量备份 | ⏳ **deferred Sprint 4** | 41GB 备份占磁盘风险, 待 `df -h` 验证后启动. 立项保留, 排 Sprint 4 第 1 件 | n/a (未启动) |
| **P1-1** W3/W4 pipeline CI smoke test | ✅ done | `test_w3w4_pipeline_smoke.py` 8 tests 真跑 `run_full_etl` 端到端, monkeypatch 短路重活 (113 xlsx + 41GB 锁), 跑批 14s < 5min | `67689fd` (merge) + `c875f2d` (feat) + `5cce5fb` (review fix 10) + `83d000c` |
| **P1-2** 16 root ./tests/ isolation | ✅ done | `pyproject.toml` `[tool.pytest.ini_options]testpaths` 收窄到 `["backend/tests"]`, 16 个 root 隔离失败不再污染默认 pytest 收集 | `ecc3483` (merge) + `83d000c` (fix) |
| **P1-3** /review 前 git log 自动化 lint | ✅ done (4 轮修) | `.githooks/check_review_ground_truth.py` 28 tests 覆盖 5 类 (B1 core.hooksPath / B2 NOOP / H1 hex / H2 trivial / H3 真 git 验证). CI lint.yml + nightly.yml 用 `--committed --files` 模式 | `79fab8fb` (merge) + `33c7fe3` (feat) + `0d7b9bb` (5 件) + `3324b18` (3 件) + `f385cc4` (2 件) |

**收口合计**: 4 commits (P0-1/P1-1/P1-2/P1-3) + 9 个 fix commits (review 修) → main 79fab8fb ahead 5 commits from e498143 (sprint 2 收口)
**/document-release**: 4 文档同步 (README/CLAUDE.md/DOCUMENT-INDEX/CHANGELOG) + 1 自检 (本文件)
**memory**: project_sprint3.md + project_etl_perf_plan.md + MEMORY.md 索引同步

```
[P0-1] 痛点 1 三次跑批真数据 + 状态更新  → ✅ done (d34fda7)
[P0-2] data/backups/duckdb_*.db 真存在 + launchd scheduled  → ⏳ deferred Sprint 4
[P1-1] pytest backend/tests/test_w3w4_pipeline_smoke.py -v PASS + CI 跑  → ✅ done (67689fd)
[P1-2] pytest ./tests/ 全绿 or 默认 ignore  → ✅ done (ecc3483)
[P1-3] red team 假 "未集成" 被拦 + 真实 commit 通过  → ✅ done (79fab8fb)

[Final] 4/5 done + /document-release 4 文件 1 自检 + memory 同步 ✅
```
