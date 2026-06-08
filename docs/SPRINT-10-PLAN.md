# Sprint 10 Plan: 合并原 Sprint 9 留口候选 + 今天新发现 is_member bug

## 上下文 (Context)

**Sprint 9 收口时 (昨天) 留了 4 件 Sprint 10 候选** (uvicorn 重启 / D-7 应用 / 前端 E2E / cleanup.md) + **今天新发现 is_member 字段全 False (UNIQUE INDEX race)**。本计划把两份合并。

**两份独立来源**:
- **原 Sprint 10 候选** (Sprint 8 收口留口, project_sprint8.md:80-86): uvicorn 重启 (已 done) / D-7 教训应用 / 前端 E2E / cleanup.md 5→6 层附录
- **新 Sprint 10 候选** (今天 6/8 增量 ETL 暴露): is_member 字段全 False / DuckDB 1.5.2 UNIQUE INDEX race / 6/8 daily backup 缺失 / 修法 #4 16GB 残留

## 上下文 (Context)

6/8 跑增量 ETL 时:
1. 6/7 任务 21580 (5,110 行) 入库 ✅
2. **is_member 字段全部 False** ❌ (frontend dashboard 会员 GSV/新老客/占比 全 0)
3. 根因: DuckDB 1.5.2 UNIQUE INDEX race (Sprint 7 已验 1.5.3 仍 fail)
4. 走 Fix A 拆 2 tx 仍然: tx1 DELETE 失败 → database invalidated → tx2 INSERT 回滚

## Sprint 9 已完成 (committed, merged)

- `cedcbbb` fix(etl): watchdog 2GB→8GB + cache key 错配 + W3 valid_sql + W4 8GB
- `799339b` docs(changelog): v0.4.14.19
- `35d109a` merge to main, pushed, uvicorn 9010 加载

## 提议的 Sprint 10 范围 (proposed)

### Option A: 完全绕开 UNIQUE INDEX (推荐, 半天, P0)
- 删 `idx_orders_order_unique` UNIQUE INDEX
- 改用 staging 表 + `INSERT ... ON CONFLICT DO NOTHING` 走应用层去重
- upsert 走 staging + COPY, 不依赖 DuckDB UNIQUE INDEX 去重

### Option B: 升级 DuckDB 1.5.3 重试 (半天, P1)
- Sprint 7 验 1.5.3 仍 fail
- 1.5.4 / 1.5.5 也许修了 UNIQUE INDEX race
- 需要跑 100+ 单元测试 + W1 GROUPING SETS + W4 集成测试

### Option C: 手工 staging UPDATE 修复 is_member (1h, P0 临时)
- 读 78 会员 xlsx → member_order_ids
- staging 表 → SQL UPDATE (不走 UNIQUE INDEX 路径)
- 临时绕过 1.5.2 bug, 等 Option A 闭环

### Option D: 6/8 daily backup 补跑 (5 min, P1)
- launchd 03:30 exit 0 但文件没生成
- 立即补跑 + 排查 launchd 失败根因

## NOT in scope (defer)

- DuckDB 1.5.2 升级到 1.5.3+ (Option B 单独 sprint)
- rfm_query_cache.data_version column 漂移 (production schema 漂移, 不影响前端)
- 前端 YOYBadge pp 模式 (PR#23 已合)
- 本地领先 origin 3 commit 未 push (Sprint 7/8 期间用户本地 commit)

## What already exists (复用现有代码)

- `scripts/etl/load.py:_upsert_to_duckdb_body` (Fix A 拆 2 tx)
- `scripts/etl/pipeline.py:_mark_all_files_processed` (cache key 修复后一致)
- `backend/services/health/rfm_analysis/cache.py:_open_write_conn` (READ_WRITE pattern)
- `backend/db/memory_monitor.py:_RSS_ALERT_BYTES` (8GB 修复)

## 风险与权衡

| 风险 | 概率 | 缓解 |
|---|---|---|
| 删 UNIQUE INDEX 性能下降 | 中 | staging 表 + application-level dedup, 实测性能 |
| staging 表 + COPY 在大表 (10.6M 行) 慢 | 中 | temp-table + 分批 |
| 升级 DuckDB 引入新 bug | 高 (1.5.3 仍 fail 已知) | 1.5.4/1.5.5 实测 |
| 手工 staging UPDATE 跟 Option A 路径不一致 | 低 | 文档化 + Option A 闭环后用 Option A 路径 |
| 6/8 daily backup launchd 失败根因排查耗时 | 中 | 优先补跑, 排查留 Sprint 11 |

## 验证标准 (success criteria)

- [ ] is_member=True 实际行数 > 0 (跟历史 11:38 跑批前一致)
- [ ] 6/4-6/7 每天 is_member=True + False 混合 (跟源数据一致)
- [ ] frontend dashboard 会员 GSV/新老客/占比 不再全 0
- [ ] pytest backend/tests/ 0 fail (排除 pre-existing)
- [ ] launchd 8/30 自动跑批不撞锁, 不重蹈 6/7 死循环
- [ ] 6/8 daily backup 文件存在 (data/processed/backups/)

## 合并 Sprint 10 范围 (12 件任务)

### A. 原 Sprint 9 留口候选 (4 件)

| # | 任务 | 工时 | 来源 | 优先级 |
|---|---|---|---|---|
| A1 | uvicorn 重启 (加载 Sprint 8 P0 + PR#22/23 改动) | 5 min | Sprint 8 收口 | ✅ 已 done (PID 9010) |
| A2 | **D-7 教训应用**: 跑所有 ETL 决策"模拟生产"测试 (DuckDB 1.5.2 新连接 vs 单连接) | 1d | Sprint 8 收口 | P1 |
| A3 | **前端 E2E 测试** (vitest + playwright 跑 1 次 npm run test) | 0.5d | Sprint 8 收口 | P2 |
| A4 | **Sprint 6 6 层防护 cleanup.md 增 5→6 层附录 + 维护** | 0.5d | Sprint 8 收口 | P2 |

### B. 今天新发现 (autopilot 提议, 8 件)

| # | 任务 | 工时 | 来源 | 优先级 |
|---|---|---|---|---|
| B1 | **P0-0 preflight**: 修 3 HIGH 隐藏问题 (production UNIQUE INDEX migration / load.py:616 ON CONFLICT / precompute_fact_rfm.py 16GB 残留) + W3 其他 5 断言 fixture 同步 | 30 min | autopilot Eng | P0 |
| B2 | **Option C-revised** 修 is_member (3h) 让 dashboard 当下能用 | 3h | autopilot CEO | P0 |
| B3 | **Option D + loud-fail**: 6/8 daily backup 补跑 + backup_duckdb.py 加 file size > 0 验证 + launchd 失败 sendmail | 1h | autopilot CEO/Eng | P1 |
| B4 | **Option A full** 删 UNIQUE INDEX + migration + 改 ON CONFLICT → NOT EXISTS + 简化 Fix A | 1d | autopilot Eng | P0 |
| B5 | **Alternative 1 调研** is_member 改派生 (删字段, SQL LEFT JOIN membership_mark) | 1h | autopilot CEO | P2 (Sprint 11 input) |
| B6 | **ETL 跑批期 uvicorn 持锁调查** (autopilot CEO user challenge #3) | 2h | autopilot CEO | P1 |
| B7 | **DuckDB 1.5.4/1.5.5 升级调研** (sprint 11 单独跑, 100+ 单元测试 + W1/W4 集成测试) | 1d | autopilot CEO/Eng | P3 |
| B8 | **5/5+6 层防护 → 运维治理成熟度评审** (autopilot CEO user challenge #4) | 1 周 | autopilot CEO | P3 (Sprint 12) |

## NOT in scope (defer)

- Alternative 1 full 实施 (治根, sprint 11)
- DuckDB 1.5.4+ 升级 full (sprint 11 调研后定)
- rfm_query_cache schema 重新核对 (误判, sprint 11)
- precompute_fact_rfm.py 16GB override 残留彻底修 (B1 preflight 已修)
- W3 其他 5 断言 fixture 同步 (B1 preflight 已修)
- 50M 行 scale 架构重构 (Sprint 13+)

## 实施步骤 (合并 + 排序)

### Phase 0: P0-0 preflight (30 min, B1)
1. ALTER TABLE orders DROP INDEX IF EXISTS idx_orders_order_unique (production 库)
2. load.py:616 ON CONFLICT → WHERE NOT EXISTS
3. precompute_fact_rfm.py:42,423,456 DUCKDB_MEMORY_LIMIT_OVERRIDE_ASYNC 16GB → 8GB
4. test_w3_dq_assertions.py 其他 5 断言 fixture 同步 production schema
5. memory_monitor.py 加 second-level alert (RSS > 12GB 硬限)

### Phase 1: 立即修 is_member (3h, B2)
1. 读 78 会员 xlsx → member_order_ids
2. staging 表 → SQL UPDATE (不走 _upsert_to_duckdb_body 路径, 避免 UNIQUE INDEX race)
3. 验证 is_member=True 实际行数 > 0
4. 验证 frontend dashboard 会员数据不再全 0

### Phase 2: 6/8 backup + loud-fail (1h, B3)
1. 立即补跑 backup_duckdb.py 生成 6/8 zst
2. 排查 launchd 03:30 失败根因
3. backup_duckdb.py 加 file size > 0 验证
4. launchd plist 加 failure sendmail

### Phase 3: Option A full (半天, B4)
1. load.py:112,262,325 删 idx_orders_order_unique 创建
2. load.py:_create_indexes (L256-265) 删 UNIQUE INDEX 那行
3. 简化 load.py:507-571 Fix A 拆 2 tx → 单 tx
4. pytest backend/tests/ 391 passed 维持
5. frontend dashboard 验证 is_member 跟 production 一致

### Phase 4: Alternative 1 调研 (1h, B5) + uvicorn 持锁调查 (2h, B6)
- 给 Sprint 11 提供 input

### Phase 5: D-7 教训应用 (1d, A2) + 前端 E2E (0.5d, A3) + cleanup.md (0.5d, A4)
- Sprint 9 留口 3 件 (uvicorn 重启已 done)

### Sprint 11+ 候选 (defer)
- Alternative 1 full (4-6h, 治根)
- DuckDB 1.5.4/1.5.5 升级 full (1d, B7)
- rfm_query_cache schema 重新核对 (半天)
- 50M 行 scale 架构 (sprint 13+)

## 验证标准 (success criteria)

- [ ] is_member=True 实际行数 > 0 (跟历史一致)
- [ ] 6/4-6/7 每天 is_member=True + False 混合
- [ ] frontend dashboard 会员 GSV/新老客/占比 不再全 0
- [ ] pytest backend/tests/ 0 fail
- [ ] launchd 8/30 跑批不撞锁
- [ ] 6/8 daily backup 文件存在
- [ ] D-7 "模拟生产" 测试通过 (新连接 100+ 跑批)
- [ ] 前端 vitest+playwright E2E 全过
- [ ] cleanup.md 6 层附录完成
- [ ] production DuckDB 不再含 idx_orders_order_unique
- [ ] precompute_fact_rfm.py async 跑批 memory_limit = 8GB
- [ ] W3 6 断言 fixture schema 跟 production 一致
