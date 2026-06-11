# Sprint 5 Retro — 真闭环: UNIQUE INDEX race Fix A 拆 2 tx (2026-06-07)

> Sprint 5 = 5 维度 + deep dive 找到真根因 DuckDB 1.5.2 UNIQUE INDEX race, Fix A 拆 2 tx (5a77fa3) 已合 main, 跑批 1 次真闭环 ~17 min, 清理 513GB

## 1. Sprint 结果

Sprint 5 是 sprint 历史上第一次"真闭环" sprint, 5 维度调查 + deep dive 找到 DuckDB 1.5.2 UNIQUE INDEX race 才是 Sprint 3-4 dedup race 的真根因 (不是 ON CONFLICT 加法). Fix A 把 `_upsert_to_duckdb_body` 拆 2 笔 transaction (先 SELECT, 后 INSERT) 彻底绕开 race window. 跑批 1 次真闭环 ~17 min, 期间释放 513GB 旧备份/旧 log.

**主要交付** (1 P0 治根 + 1 真闭环 + 1 治理):
- P0-3: hotfix 4 Fix A `_upsert_to_duckdb_body` 拆 2 tx (`5a77fa3` 已合 main)
- Sprint 5 跑批 1 次真闭环 ~17 min
- 清理 513GB (旧备份 / 旧 log / 旧 staging)
- Sprint 5 收口 (`f8a707e` docs + `61f2a69` merge)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `61f2a69` | merge: sprint5 P0-3 hotfix 4 Fix A 拆 2 tx (DuckDB UNIQUE INDEX race 修复) | Fix A merge |
| `5a77fa3` | fix(etl): sprint5 P0-3 hotfix 4 Fix A _upsert_to_duckdb_body 拆 2 tx | Fix A 主体 |
| `f8a707e` | docs: sprint5 收口 (NOT EXISTS hotfix 3 + 跑批真验留 Sprint 6) | 收口 doc |
| `d9165bb` | merge: sprint5 P0-3 hotfix 3 NOT EXISTS 路线 | hotfix 3 (前置实验) |
| `3b92f1f` | fix(etl): sprint5 P0-3 hotfix 3 _upsert_to_duckdb_body 改用 NOT EXISTS | hotfix 3 |
| `fc633bc` | docs: sprint5 真闭环 (Fix A 拆 2 tx, 痛点 1 端到端 < 35 min 真闭环) | 收口 doc |

## 3. 教训

1. **"5 维度 + deep dive" 是根因调查标准**: Sprint 5 立下的"5 维度 + deep dive"调查方法 (现象 / 时序 / 依赖 / 复现 / 替代) 成为 Sprint 7-18 所有根因调查的模板. Sprint 7 / 10 / 16 全部沿用.
2. **NOT EXISTS → Fix A 拆 2 tx 的演进**: Sprint 5 走 NOT EXISTS (hotfix 3) → 拆 2 tx (hotfix 4 Fix A) 路径, 后续 Sprint 7 P2 决定 KEEP 拆 2 tx, 不升级 DuckDB 1.5.3. 选 Keep 1.5.2 + 拆 2 tx 比升级 1.5.3 更稳, 避免引入新 race.
3. **真闭环 ~17 min 是 baseline**: Sprint 5 真闭环 17 min 成为后续 sprint 的对照基准. Sprint 11 DuckDB 1.5.3 升级目标 < 17 min, Sprint 12 50M benchmark 沿用.

## 4. 关键指标

- **commits**: 6 main commits (2 merge + 2 fix + 2 docs)
- **主要文件**: `scripts/etl/_upsert_to_duckdb_body.py` (拆 2 tx 核心) + 513GB 旧备份/旧 log 清理 + `docs/SPRINT-5-RETROSPECTIVE.md` (Sprint 5 收口, 这是补齐的 retrospective)
- **version**: v0.4.14.11 (Sprint 5 Fix A)
- **tests**: 沿用 459+ passed
- **main commit**: `fc633bc` (收口)
- **跑批耗时**: ~17 min 真闭环
