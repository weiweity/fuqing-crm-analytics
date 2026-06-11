# Sprint 16.5 README — 等 DuckDB 1.5.4 Release 后激活

## 背景
Sprint 15 Wave 3 (v0.4.14.37) 治根 is_member per-user 后, 跑批真验卡在 DuckDB 1.5.3 ART index race
(`Vector::Reference VARCHAR/TIMESTAMP` + `Failed to delete 0/2048 rows`). Sprint 16 P0 探索 3 个 workaround
(DROP+RECREATE / CHECKPOINT 前置 / v2 综合) 全部失败, 根因是 DuckDB 1.5.3 ART index lifecycle
整体 race, 治本需 1.5.4 release.

## Sprint 16 P0 中止决策 (2026-06-11, user 拍板 A)
- 不 commit 到 main (workaround 在 1.5.3 上反复崩)
- 留 `fix/sprint16-p0-duckdb-taoke-channel-race` 分支 + v2 代码 + 4 tests
- Sprint 15 Wave 3 跑批真验 + 跑批真验 18 老客验证 跟 1.5.4 release 一起做
- main 不动 (1694c8b 仍是 Sprint 15 Wave 3 v0.4.14.37)

## Sprint 16.5 激活路径 (1.5.4 release 后)
1. **监控**: PyPI duckdb 1.5.4 release (现 1.5.3 2026-05-20) + DuckDB GitHub release notes
2. **升级**: `requirements.txt` + `requirements-lock.txt` bump duckdb 到 1.5.4, 跑 `pip install -U duckdb==1.5.4`
3. **4 步规避** (跟 Sprint 5 跑批真验 4 步规避 一致):
   - Step 1 dry-run: `cp data/processed/fuqing_crm.duckdb /tmp/dryrun.duckdb` 跑 v2 序列
   - Step 2 release notes: 查 1.5.4 changelog, 确认 ART race / stale index 修复
   - Step 3 pytest: `cd backend && pytest tests/test_taoke_channel_duckdb_race.py -v` (4 tests 全过)
   - Step 4 git revert plan: 单独 commit 一次性 revert, 跑通即保留
4. **复用 v2 代码**: `git checkout fix/sprint16-p0-duckdb-taoke-channel-race -- scripts/etl/pipeline.py backend/tests/test_taoke_channel_duckdb_race.py`
5. **prod 跑批真验**: `python scripts/etl/pipeline.py --update --days 1` + 6 道门禁 + 18 老客 is_member=TRUE
6. **/qa 4 端点回归**: dashboard / audience / category / health
7. **commit + push + merge main + CHANGELOG v0.4.14.38**

## 留 commit 清单
- `fix/sprint16-p0-duckdb-taoke-channel-race` 分支 HEAD: `wip(sprint16-p0): preserve DuckDB 1.5.x ART race 治根 v2`
- 含 2 文件: `scripts/etl/pipeline.py` (60+/6-) + `backend/tests/test_taoke_channel_duckdb_race.py` (新建 168 行)

## Sprint 16 P0 探索教训 (写 memory)
- **D-7 教训延伸**: /tmp dry-run 6.7s 跑通 (干净 state, 0 行 UPDATE) 不能推广到 prod (1.88M UPDATE 触发 commit race). 干 state 跑通 vs prod 真验是不同问题
- **race 反复触发是 lifecycle 整体 bug**: Sprint 10 fix 修了一个症状, Sprint 16 P0 暴露 3 个不同症状 (SELECT/DROP/COMMIT). 治标不治本, 必须升 DuckDB
- **workaround 在生产前必跑 4 步规避**: 升版本 + 跑批真验是 destructive sequence, 必须 dry-run + pytest + revert plan 配套
- **3 race 症状全在 DuckDB 1.5.3 ART index 内部 bug**: 跟代码无关, 跟数据量有关 (1.88M UPDATE 触发, 0 行不触发). 等 1.5.4 release

## Sprint 16.5 P0 状态
- **未激活** (等 1.5.4 release)
- 当前 Sprint 16.5 转治理 P1/P2 backlog (#89/#90/#91/#92), 跟 DuckDB 升级解耦
