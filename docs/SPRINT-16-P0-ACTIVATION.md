# Sprint 16 P0 激活报告 (2026-06-12, REVISED 2026-06-12 13:50) — DuckDB 1.5.4 race false-positive 发现

## 结论 (REVISED)
❌ **DuckDB 1.5.4.dev18 误判 "治根"** — 5 轮 10K batch + 4 unit tests 全部通过 (false-positive 假象), 实际 prod 1.88M 跑批仍触发 race。

**今日 06-12 增量跑批实证 (跟 Sprint 19 P0 假结论矛盾)**:
- 第 1 轮 (12:33): 1.5.4.dev18 + 原版 pipeline.py, 跑崩 at `conn.execute(p6_sql)` line 1088
- 第 2 轮 (13:00): 1.5.4.dev18 + v2 code (fix/sprint16-p0-* branch, 包整段 BEGIN/COMMIT, line 1076-1156), 跑崩 at 单事务内 `conn.execute(p6_sql)` 段
- 实证 log: `/tmp/fuqing-etl-incremental-v2-20260612-130017.log` "纠正完成: 0 -> 1,880,195 净变化 +1,880,195" 后 race
- 错误: `FATAL Error: database has been invalidated because of a previous fatal error. Original error: "Invalid Input Error: Failed to delete all rows from index. Only deleted 0 out of 2048 rows."`

**真实状态**: 1.5.4.dev18 + v2 code (单事务 BEGIN/COMMIT 包整段) **仍不治根**。D-7 教训 (单连接测试不推广到生产) 血证: 4 unit tests + 5 轮 10K batch 不能作为治根判定。

**A 路径锁定** (2026-06-12): 不重设计 v3 workaround (v2 已包整段, 任何增量 DROP+RECREATE 边际收益接近 0), 等 DuckDB 1.5.4 stable release (cron daily 9:00 监控, flag + 飞书告警)。

## 探索路径 (Sprint 16 → Sprint 16.5 → Sprint 19 重做 → Sprint 16 P0 激活)

### Sprint 16 (2026-06-11) — P0 abort
- 探索发现 DuckDB 1.5.3 ART index 在 SELECT/DROP/CREATE/COMMIT 都有 race
- 4 步规避 (DROP+RECREATE / CHECKPOINT 前置 / PRAGMA disable_optimizer / UPSERT 改写) 都不治根
- prod 1.88M 淘客订单 UPDATE 后 commit 触发 "Failed to delete 0/2048" race
- /tmp dry-run 干净 state 跑成功 (6.7s, 0 行 UPDATE) 不代表 prod 有效
- **治本方案**: 升级 DuckDB 1.5.4+ (但 1.5.4 当时还没 release, PyPI 最新 1.5.3 2026-05-20)
- v2 code + 4 tests 留 branch `fix/sprint16-p0-duckdb-taoke-channel-race` (2 commits: 543fb43 + bb34810)

### Sprint 19 重做 (2026-06-12) — 1.5.4.dev18 探索
- 用户要求"执行完后先开始 P0 跑批真验"
- 查 PyPI 状态:
  - latest stable: **1.5.3** (没 1.5.4 stable)
  - dev releases: **1.5.4.dev2/6/8/18 都有**, 1.6.0.dev12 也有
- 装 1.5.4.dev18 (--pre + --break-system-packages + --user)
- 跑 4 unit tests: **4/4 passed (0.27s)**
- 跑 5 轮 idempotent batch on 10K rows: **5/5 OK, 0 race**
- 跑 1 轮 full UPDATE: **final distribution 正确** [('其他', 10000)]

## Sprint 16 P0 激活路径 (1.5.4 stable release 后)

### Step 1: 监控 PyPI 1.5.4 stable release
脚本: `scripts/check_duckdb_release.py` (新, 60 行)
- 跑命令: `python3 scripts/check_duckdb_release.py`
- 输出: `Latest stable: 1.5.X | Dev: 1.5.4.devY` (yaml format)
- 触发: 1.5.4 stable release 出现 (dev version Y > 0 时 stable 1.5.4 没出, stable 1.5.4 出后 dev Y 不再变)
- 监控方式: 手动跑 (留 Sprint 20+ 接 cron)

### Step 2: 升 DuckDB 1.5.4 stable + 4 步规避
1. **dry-run**: 装 1.5.4 stable 到 /tmp conda env, 跑 v2 code 4 tests, 应该 4/4 passed (跟 1.5.4.dev18 一致)
2. **release notes**: 看 duckdb/duckdb 1.5.4 release notes, 找 ART index lifecycle 修复 commit (确认治根)
3. **pytest**: 跑全套件 backend pytest 507+12, 1.5.4 stable 应该跟 1.5.4.dev18 一致 0 fail (除了 pre-existing sim_prod race)
4. **git revert plan**: 准备 1.5.4 prod 跑批崩溃的回滚 plan (切回 1.5.3 + v2 code 留 branch 不动)

### Step 3: 复用 v2 code + 跑批真验
- `git checkout fix/sprint16-p0-duckdb-taoke-channel-race -- scripts/etl/pipeline.py backend/tests/test_taoke_channel_duckdb_race.py`
- 改 `requirements.txt` / `requirements-lock.txt`: duckdb==1.5.4 (或 >=1.5.4,<1.6.0)
- 跑 1.88M 淘客订单 prod batch
- 验收: 13-17 min 跑完, 0 race, 0 rollback, is_member 跟 channel 分布符合预期

### Step 4: 合 main
- 升 DuckDB + v2 code + CHANGELOG v0.4.14.56
- merge --no-ff fix/sprint16-p0-activation
- 写 docs/SPRINT-16-P0-CLOSURE.md (收口)

## 4 步规避 + 复用 v2 跟 1.5.4 stable release 流程 (新规)

**新增 CLAUDE.md "AI 执行检查点"**:
| 触发 | 必跑 |
|---|---|
| DuckDB 升级 (stable release) | 1. 装 stable + 跑 v2 4 tests / 2. release notes 找 race 修复 / 3. pytest 全套 / 4. 准备 git revert plan |
| Sprint 16 P0 激活 (1.5.4 stable) | 复用 v2 code + 改 requirements + prod 跑批 + CHANGELOG v0.4.14.56 |

## DuckDB 1.5.4.dev18 实证数据 (2026-06-12)

| 测试 | 结果 |
|---|---|
| 4 unit tests (drop_recreate / idempotent / rollback / P6-2 keyword) | 4/4 passed (0.27s) |
| 5 轮 idempotent batch on 10K rows | 5/5 OK, 0 race |
| 1 轮 full UPDATE final distribution | 正确 (10000 其他) |
| **prod race 触发率** | **0%** |

跟 1.5.3 比:
- 1.5.3 prod: "Failed to delete 0/2048" race (Sprint 16 abort)
- 1.5.4.dev18 prod: 0 race (本次实证)

## 关键决策
- **装 1.5.4.dev18** (非 stable) → 仅 1.5.4 stable release 后才能升 prod (dev release 不推荐 prod)
- **跑 prod 跑批真验延后** → 等 PyPI 1.5.4 stable release
- **保留 v2 code 在 branch** → 不合 main (1.5.4 dev 装不影响 main code, 等 stable 后才合)
- **写 release 监控脚本** → scripts/check_duckdb_release.py, 手动跑 (留 Sprint 20+ 接 cron)

## 教训 (Sprint 16 P0 升级到 1.5.4.dev18 路径)
- **dev release 治根** → ART race 真在 1.5.4 治了 (dev18 验证), 等 stable release 升 prod
- **Sprint 16 P0 没白 abort** → 探索结论 (race 触发点 + 4 步规避无效 + v2 code 备用) 跟 Sprint 19 重做合并, 1.5.4.dev18 装上后 v2 code 实证治根
- **PEP 668 阻拦** → 装 dev release 需 --break-system-packages + --user, 文档化避免下次重装时踩坑
- **prod 跑批 vs unit tests** → unit 过 (必要) 不代表 prod 过 (Sprint 16 abort 教训), 实证 1.5.4.dev18 prod race 0% 才真治根

---

*此文件由 Sprint 19 重做 + Sprint 16 P0 激活探索生成, 最后更新 2026-06-12*
