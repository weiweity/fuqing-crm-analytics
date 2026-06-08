# Sprint 10 Plan: codex 0.137.0 重塑版 (2.5 天精炼)

## 上下文 (Context)

**原 Sprint 10 计划 12 件任务, codex 0.137.0 交叉审核 (2026-06-08) 找出 4 个关键问题**:

1. **Option A 内部矛盾**: 删 `idx_orders_order_unique` UNIQUE INDEX, 但 `load.py:616` 已经在用 `ON CONFLICT (order_id, sub_order_id) DO NOTHING` 依赖这个 index. 删 index → L616 增量路径立即断. 真修法: 保留 index, 改 L616 `ON CONFLICT` → `WHERE NOT EXISTS` (跟 staging 模式一致).
2. **is_member 根因误判**: 原计划假设 UNIQUE INDEX race 致 is_member corruption. codex 指出真根因是 staging INSERT (`load.py:616` 的 `INSERT INTO orders ({cols_joined}) SELECT {cols_joined} FROM {tmp_table} ON CONFLICT DO NOTHING`) 把 raw parquet 的 is_member 写入 — 首次写入时 is_member 就是 False (member xlsx 没 JOIN), DO NOTHING 跳过现有行 → 永远修不回来. Option C (staging UPDATE band-aid) 治标不治本.
3. **Phase 4 调研 = 浪费**: B5 (is_member 派生字段) Sprint 5 已验, B6 (uvicorn 持锁) `lsof` 5 min 出结果, 不需要 2h 调研.
4. **Phase 5 = 卫生工作**: A3 (前端 E2E) / A4 (cleanup.md 5→6 层) / B8 (运维成熟度评审) 是 hygiene, 不是 Sprint 10 范围.

**重塑原则**: 砍掉内部矛盾的任务, 治根路径, 已知答案不调研, hygiene 留 Sprint 11+.

## Sprint 9 已完成 (committed, merged)

- `cedcbbb` fix(etl): watchdog 2GB→8GB + cache key 错配 + W3 valid_sql + W4 8GB
- `799339b` docs(changelog): v0.4.14.19
- `35d109a` merge to main, pushed, uvicorn 9010 加载

## 重塑后的 Sprint 10 范围 (5 件, 2.5 天)

| # | 任务 | 工时 | 优先级 | 状态 |
|---|---|---|---|---|
| **B6-lite** | uvicorn 持锁 `lsof` 调查 (PID 9010 确认) | 15m | P1 | ✅ 已 done |
| **B1** | preflight: prod 删 UNIQUE INDEX + L616 改 NOT EXISTS + 16GB→8GB + W3 fixture + RSS 硬限 | 30m | P0 | pending |
| **B3** | 6/8 daily backup 补跑 + size>0 验证 + launchd sendmail loud-fail | 1h | P1 | pending |
| **A2** | D-7 sim-prod: 新连接 100+ 跑批 (DuckDB 1.5.2 race 验证) | 0.5d | P1 | pending |
| **B2-merged** | 修 upsert 不覆盖 is_member + 从 membership_mark replay (Option C + Alternative 1 合并) | 1d | P0 | pending |

总工时: 2.5 天 (P0+P1 混合, 没有 P2/P3 hygiene)

## 已删 (defer to Sprint 11+)

| 旧任务 | 原因 | 移到 |
|---|---|---|
| **B4** Option A 删 UNIQUE INDEX | 与 L616 ON CONFLICT 路径矛盾, codex 拒绝 | — (留 index, 改 NOT EXISTS) |
| **B5** Alternative 1 调研 1h | Sprint 5 已验, 答案已知, 直接并入 B2-merged | B2-merged (1d, 直接实施) |
| **B6** uvicorn 持锁 2h 调研 | 缩成 15m lsof, 已 done | B6-lite ✅ |
| **B7** DuckDB 1.5.4/1.5.5 升级调研 | 不是当前 sprint 优先级, 1.5.3 已验仍 fail | Sprint 11 调研 |
| **A3** 前端 vitest+playwright E2E | hygiene, 跟当前 P0 is_member bug 无关 | Sprint 11 tech debt Friday |
| **A4** cleanup.md 5→6 层附录 | hygiene, 跟当前 P0 is_member bug 无关 | Sprint 11 tech debt Friday |
| **B8** 5+6 层防护 → 运维治理成熟度评审 | 一周, 跟当前 P0 is_member bug 无关 | Sprint 12 |

## NOT in scope (defer)

- DuckDB 1.5.2 升级到 1.5.3+ (Sprint 11 单独 sprint)
- rfm_query_cache.data_version column 漂移 (production schema 漂移, 不影响前端)
- 前端 YOYBadge pp 模式 (PR#23 已合)
- 本地领先 origin 3 commit 未 push (Sprint 7/8 期间用户本地 commit)
- Alternative 1 full 实施 (4-6h 治根, 已在 B2-merged 内部完成, 不再单独 sprint)
- 50M 行 scale 架构重构 (Sprint 13+)

## What already exists (复用现有代码)

- `scripts/etl/load.py:_upsert_to_duckdb_body` (Fix A 拆 2 tx, 保留)
- `scripts/etl/pipeline.py:_mark_all_files_processed` (cache key 修复后一致)
- `backend/services/health/rfm_analysis/cache.py:_open_write_conn` (READ_WRITE pattern)
- `backend/db/memory_monitor.py:_RSS_ALERT_BYTES` (8GB 修复)
- `scripts/etl/load.py:605-622 _copy_df_to_duckdb` (L616 改 NOT EXISTS 目标位置)
- `scripts/etl/load.py:132, 448` (orders table column list, 含 is_member)

## 风险与权衡

| 风险 | 概率 | 缓解 |
|---|---|---|
| B1 prod DROP INDEX 影响 L616 ON CONFLICT 路径 (历史事实) | 高 | B1 同时改 L616 ON CONFLICT → WHERE NOT EXISTS, 保持等效语义 |
| B2-merged 一次性 replay 全表 is_member 在 10.6M 行慢 | 中 | 分批 UPDATE, 每批 100K 行 |
| B2-merged replay 跟 staging INSERT 新数据时序冲突 | 低 | replay 在 ETL 跑批之前 (--update mode), 跑批后用 staging JOIN 修 |
| A2 sim-prod 100+ 跑批暴露新 bug | 中 | 跑批前先 B1 (preflight), 暴露即修 |
| B3 backup launchd 失败根因不在 exit code | 中 | 先补跑, 根因排查留 Sprint 11 |

## 验证标准 (success criteria)

- [ ] production DuckDB 不再含 `idx_orders_order_unique` (B1 prod migration)
- [ ] `load.py:616` 用 `WHERE NOT EXISTS` 替代 `ON CONFLICT` (B1 code change)
- [ ] `precompute_fact_rfm.py` async 跑批 `memory_limit = 8GB` (B1 code change)
- [ ] W3 6 断言 fixture schema 跟 production 一致 (B1 test sync)
- [ ] `memory_monitor.py` RSS > 12GB 硬限告警 (B1 second-level alert)
- [ ] is_member=True 实际行数 > 0 (B2-merged replay 验证)
- [ ] 6/4-6/7 每天 is_member=True + False 混合 (跟源数据一致)
- [ ] frontend dashboard 会员 GSV/新老客/占比 不再全 0
- [ ] pytest backend/tests/ 391+ passed 维持
- [ ] A2 sim-prod 100+ 跑批 0 fail, 0 lock conflict
- [ ] 6/8 daily backup 文件存在 (data/processed/backups/fuqing_crm_2026-06-08.duckdb.zst)
- [ ] backup_duckdb.py 加 file size > 0 验证
- [ ] launchd plist 加 failure sendmail loud-fail

## 实施步骤 (2.5 天)

### Step 0: B6-lite (15m) — ✅ 已 done
1. `lsof data/processed/fuqing_crm.duckdb`
2. 确认 PID 9010 (uvicorn) 持锁
3. 记录到 CLAUDE.md "跑 ETL 前必须 kill 9010"

### Step 1: B1 preflight (30m, P0)
1. `git checkout -b feature/sprint10-upsert-fix` (已建)
2. kill uvicorn PID 9010 (B1 prod migration 需要 DB 锁)
3. `ALTER TABLE orders DROP INDEX IF EXISTS idx_orders_order_unique` (production 库)
4. `load.py:616` `ON CONFLICT (order_id, sub_order_id) DO NOTHING` → `WHERE NOT EXISTS (SELECT 1 FROM orders o2 WHERE o2.order_id=... AND o2.sub_order_id=...)`
5. `precompute_fact_rfm.py:42, 423, 456` `DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC` 16GB → 8GB
6. `test_w3_dq_assertions.py` 其他 5 断言 fixture 同步 production schema (跟 Sprint 9 W3 维修模式一致)
7. `memory_monitor.py` 加 second-level alert: `RSS > 12GB` 硬限 sys.exit(1)
8. pytest 跑 6 断言 fixture 全绿
9. git commit + push + merge to main + 重启 uvicorn

### Step 2: B3 backup loud-fail (1h, P1)
1. `python3 scripts/etl/backup_duckdb.py` 立即补跑 6/8 backup
2. 验证 `data/processed/backups/fuqing_crm_2026-06-08.duckdb.zst` 存在 + size > 0
3. `backup_duckdb.py` 加 `assert zst_size > 0 else sys.exit(2)`
4. 排查 launchd 03:30 失败根因 (查 `/tmp/com.fuqing.duckdb-backup.daily.log`)
5. launchd plist 加 `KeepAlive=false` + `RunAtLoad=false` + sendmail on failure
6. git commit + push + merge to main

### Step 3: A2 D-7 sim-prod (0.5d, P1)
1. 写 `backend/tests/sim_prod_etl.py`: 100+ 次 `--update` ETL, 每次用新连接 + commit/close
2. 跑批前 snapshot: row count + is_member 分布
3. 跑批后 verify: row count + is_member 分布 + W3 6 断言 + W4 fact_rfm 增量
4. pytest 0 fail
5. 跑批期间监控 RSS, 确认 8GB cap 不撞
6. git commit + push + merge to main

### Step 4: B2-merged (1d, P0)
1. **修 upsert SQL** (`load.py:616`): staging INSERT 前先 LEFT JOIN membership_mark 取 is_member
   ```sql
   INSERT INTO orders ({cols_joined}, is_member)
   SELECT s.{cols_joined}, COALESCE(m.is_member, FALSE)
   FROM {tmp_table} s
   LEFT JOIN membership_mark m ON s.user_id = m.user_id
   ON CONFLICT (order_id, sub_order_id) DO NOTHING
   -- 等等, B1 已改 NOT EXISTS, 这里也需要相应改
   ```
2. **生成 membership_mark 表**: 读 78 会员 xlsx → user_id → is_member 字典 → CREATE TABLE membership_mark (user_id VARCHAR PRIMARY KEY, is_member BOOLEAN)
3. **一次性 replay 全表 is_member** (10.6M 行):
   ```sql
   UPDATE orders o
   SET is_member = COALESCE(m.is_member, FALSE)
   FROM membership_mark m
   WHERE o.user_id = m.user_id
     AND o.is_member != COALESCE(m.is_member, FALSE)
   ```
4. **分批执行**: 每批 100K 行, commit per batch, 防 OOM
5. **验证**: 
   - `SELECT COUNT(*) FROM orders WHERE is_member = TRUE` > 0
   - 6/4-6/7 每天 `is_member=True + False` 混合
   - frontend dashboard 会员 GSV/新老客/占比 不再全 0
6. pytest + frontend E2E (curl /api/v1/dashboard/member-gmv)
7. git commit + push + merge to main + 重启 uvicorn

### Sprint 11+ 候选 (defer, 不在 Sprint 10 范围)
- DuckDB 1.5.4+ 升级 full (1d)
- A3 前端 vitest+playwright E2E
- A4 cleanup.md 5→6 层附录
- B8 运维治理成熟度评审
- 50M 行 scale 架构 (Sprint 13+)

## Code Review Note (2026-06-08 codex 0.137.0)

- Codex ran consult on 5 min timeout, output 6,526 tokens
- Findings: 4 critical (internal contradiction + root cause misidentification + waste research + hygiene scope)
- Recommendation accepted: 12 件 → 5 件, 2.5 天
- Codex 0.137.0 配置仅 cosmetic warning (`--enable web_search_cached` 弃用), 不影响功能, 跳过
- Codex 0.137.0 + MiniMax provider (`wire_api="responses"` + `env_key="MINIMAX_API_KEY"`) 链路 OK, link test 90s 通过
- Codex 0.137.0 shell tool 拼接 bug (`cat && -n` join) 已修, 正确用 `/bin/zsh -lc`
