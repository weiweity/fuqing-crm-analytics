# Sprint 4 Retro — 2/2 P0 done, 痛点 1 端到端 + DuckDB 55GB 备份 (2026-06-07)

> Sprint 4 = 2/2 P0 done: 痛点 1 端到端 (留 Sprint 3 P0-1 延伸) + P0-2 DuckDB 55GB 每日备份 + P0-3 hotfix 2 dedup 端到端, 5 review 修全生效

## 1. Sprint 结果

Sprint 4 完成 2/2 P0: P0-1 痛点 1 端到端代码闭环 (Sprint 3 启动) 真正验 + 文档收口, P0-2 DuckDB 55GB 每日备份 (launchd daily + zstd 压缩), 加上 P0-3 hotfix 2 `_upsert_to_duckdb_body` 加 ON CONFLICT 治根 dedup race. 期间 5 轮 review 修全生效, 5 GB→55 GB 备份扩量 (覆盖 1 个月历史 + 当前生产).

**主要交付** (2/2 P0 + 1 治根):
- P0-1: 痛点 1 端到端 (Sprint 3 启动, Sprint 4 收口)
- P0-2: DuckDB 55GB 每日备份 (launchd daily + zstd 压缩)
- P0-3: hotfix 2 dedup 端到端 (`_upsert_to_duckdb_body` 加 ON CONFLICT)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `3882f91` | merge: SPRINT-4 收口文档同步 (2/2 P0 done, 痛点 1 端到端 + DuckDB 55GB 备份) | 收口 merge |
| `4d20f99` | docs: SPRINT-4 收口 (2/2 P0 done, 痛点 1 端到端 + DuckDB 55GB 备份) | 收口 doc |
| `ec9c28b` | merge: P0-3 hotfix 2 _upsert_to_duckdb_body ON CONFLICT (sprint 4 dedup 端到端) | P0-3 |
| `56a35ee` | fix(etl): sprint4 P0-3 hotfix 2 _upsert_to_duckdb_body 加 ON CONFLICT | P0-3 |
| `a3def1c` | merge: P0-2 DuckDB 55GB 每日备份 (launchd daily + zstd 压缩, 5 review 修全生效) | P0-2 |
| `06bb580` | feat(backup): sprint4 P0-2 DuckDB 55GB 每日备份 (launchd daily + zstd 压缩) | P0-2 |

## 3. 教训

1. **"5 review 修全生效" 留文档**: P0-2 备份脚本经过 5 轮 review 才合 main, 期间每轮 review 改的细节都进 commit message. Sprint 4 之后 "review 轮数" 成了 P0 任务的标准工作量估算.
2. **P0-3 hotfix 2 = "真治根"**: ON CONFLICT 加在 `_upsert_to_duckdb_body` 是 dedup race 的真治根, 之前 Sprint 3 的 race "绕开" 路线被 Sprint 5 进一步 5 维度 + deep dive 找真根因 (UNIQUE INDEX race) 取代.

## 4. 关键指标

- **commits**: 6 main commits (3 merge + 3 fix/feat)
- **主要文件**: `scripts/backup/duckdb_daily.sh` (55GB launchd daily) + `scripts/etl/_upsert_to_duckdb_body.py` (ON CONFLICT) + `docs/SPRINT-4-RETROSPECTIVE.md` (Sprint 4 收口, 这是补齐的 retrospective, 当时是 4d20f99 的 docs 简化版)
- **version**: v0.4.14 (沿用 Sprint 3, 没新 version bump)
- **tests**: 沿用 Sprint 3 459+ passed
- **main commit**: `3882f91`
