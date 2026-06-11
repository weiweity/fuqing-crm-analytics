# Sprint 7 Retro — P0 治根 10 root test fail + P2 6 层防护 (2026-06-07)

> Sprint 7 = 3 subagent 并行 2.5h 264K tokens, P0 治根 10 root test fail 141 passed + P2 6 层防护 cleanup.md 516 行 + P2 DuckDB Fix A KEEP, 9 commit 70f60f1/0286263/fe2087a/315c565/47578d0

## 1. Sprint 结果

Sprint 7 是 sprint 历史上 "3 subagent 并行 2.5h 264K tokens" 最大量 sprint, 完成 P0 治根 10 root test fail (重构 service import 模式, 141 passed) + P2 6 层防护清理文档 516 行 + P2 DuckDB 升级测试 (Fix A 决策 KEEP 2-tx, 不升级 1.5.3). 期间 P0 治根是 Sprint 3 留的 16 root test 的延伸, 141 passed 是 base.

**主要交付** (1 P0 治根 + 2 P2):
- P0: 重构 service import 模式, 治根 10 root test fail → 141 passed (70f60f1 / ad9f9b9)
- P2-1: 6 层防护清理文档 516 行 (fe2087a / 8e54c16)
- P2-2: DuckDB 升级测试 + Fix A 决策 KEEP 2-tx, 不升级 1.5.3 (beadaa3)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `70f60f1` | merge: sprint7 P0 重构 service import 模式 (治根 10 root test fail) | P0 merge |
| `ad9f9b9` | fix(rfm): sprint7 P0 重构 service import 模式 (治根 10 root test fail) | P0 主体 |
| `5b846f2` | docs: CHANGELOG v0.4.14.13 sprint7 P0 重构 service import 模式 | P0 CHANGELOG |
| `0286263` | docs: merge sprint7 P0 CHANGELOG v0.4.14.13 | P0 doc merge |
| `fe2087a` | merge: docs/sprint7 P2 6 层防护清理文档 | P2-1 merge |
| `8e54c16` | docs: sprint7 P2 6 层防护清理文档 (516 行) | P2-1 主体 |
| `315c565` | Merge branch 'test/sprint7-p2-duckdb-upgrade' | P2-2 merge |
| `beadaa3` | test: sprint7 P2 DuckDB 升级测试 + Fix A 决策 (KEEP 2-tx, 不升级 1.5.3) | P2-2 主体 |
| `47578d0` | docs: sprint7 CHANGELOG v0.4.14.15 (P2 6 层防护清理文档) | P2-1 CHANGELOG |

## 3. 教训

1. **"重构 service import 模式" 是真治根**: Sprint 7 P0 把 service import 从 `from backend.x import y` 改成 `from .x import y` (相对导入), 治根 10 root test fail + 解决循环导入. 后续 Sprint 17 #120 写 contract 才能跨 service 引用.
2. **"KEEP Fix A 2-tx 不升级 DuckDB"**: Sprint 7 P2 跑 1.5.3 升级测试, 决策 KEEP 1.5.2 + Fix A 2-tx. 后续 Sprint 11 实际升级 1.5.3 才走通, 期间 Sprint 7-10 都用 1.5.2. 决策 KEEP 让 sprint 不冒险, 留 Sprint 11 升级窗口.
3. **3 subagent 并行 2.5h 264K tokens**: Sprint 7 创单 sprint token 记录, 后续 Sprint 18 (4 subagent 2h) 接近. 关键是任务可拆 (P0 治根 / P2-1 doc / P2-2 test 3 件独立).

## 4. 关键指标

- **commits**: 9 main commits (3 merge + 1 fix + 1 test + 4 docs)
- **主要文件**: `backend/services/rfm/*.py` (import 模式重构) + `docs/cleanup.md` (516 行新) + `backend/tests/test_duckdb_upgrade.py` (升级测试) + `docs/SPRINT-7-RETROSPECTIVE.md` (补齐)
- **version**: v0.4.14.13 (P0) + v0.4.14.15 (P2-1)
- **tests**: 141 passed (root test) + Sprint 3-6 既有 459+ passed
- **main commit**: `47578d0`
