# Sprint 10 Retro — codex 0.137.0 重塑 plan 12→5 件 + B1 preflight (2026-06-08)

> Sprint 10 = codex 0.137.0 重塑 plan 12→5件 2.5 天 + B1 preflight done 3 件根因 (staging NOT EXISTS / W4 8GB / RSS 12GB 硬限) + prod UNIQUE INDEX 删除 + is_member 根因重诊断 (staging overwrite, 不是 UNIQUE INDEX race), 3 commit c2a0a7e/8ca218d/98c5e84

## 1. Sprint 结果

Sprint 10 是第一次用 codex 0.137.0 重塑 plan 的 sprint, 12 件 → 5 件 2.5 天, B1 preflight 3 件根因全部完成 (staging NOT EXISTS / W4 8GB / RSS 12GB 硬限). 期间重新诊断 Sprint 5 "UNIQUE INDEX race" 根因, 实际是 staging overwrite, 删 prod UNIQUE INDEX 是另一回事. B2-merged is_member replay (3.48M 行 1.8s 修复) + sim-prod test 260 新连接 0 错误 + B3 backup loud-fail 配套.

**主要交付** (5 件重塑 + 1 重诊断):
- B1 preflight 3 件: staging NOT EXISTS / W4 8GB / RSS 12GB 硬限 (`c2a0a7e`)
- codex 0.137.0 重塑 plan 12→5 件 + CHANGELOG v0.4.14.21 (`8ca218d`)
- B1 preflight merge + 收口 (`98c5e84`)
- (衍生) B2-merged is_member replay (`99c0196` / `4dd66d4` / `b236ee4` v0.4.14.23)
- (衍生) sim-prod test 260 新连接 (`309f43e` / `eb506c6`)
- (衍生) B3 backup loud-fail + BJ date + size assert (`d5691db` / `f3f83b2` / `afbcf3f` v0.4.14.22)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `98c5e84` | merge: sprint10 B1 preflight (staging NOT EXISTS + W4 8GB + RSS 12GB + plan rewrite + v0.4.14.21) | B1 merge |
| `8ca218d` | docs(sprint10): codex 0.137.0 重塑 plan (12→5件 2.5天) + v0.4.14.21 CHANGELOG | plan rewrite |
| `c2a0a7e` | fix(etl): sprint10 preflight — staging NOT EXISTS + W4 8GB + RSS 12GB hard limit | B1 主体 |
| `b236ee4` | docs(changelog): v0.4.14.23 sprint10 B2-merged is_member replay (3.48M 行修复) | 衍生 doc |
| `4dd66d4` | merge: sprint10 B2-merged is_member replay (1.8s 修 3.48M 行, frontend dashboard 恢复) | 衍生 merge |
| `99c0196` | feat(etl): sprint10 B2-merged 修 is_member 全 False (1.8s 修 3.48M 行) | 衍生 fix |
| `309f43e` | merge: sprint10 A2 D-7 sim-prod test (260 新连接跑批 0 错误) | 衍生 merge |
| `eb506c6` | test(sim-prod): sprint10 A2 D-7 sim-prod - 新连接 100+ 跑批 (260 次 0 错误) | 衍生 test |
| `f3f83b2` | merge: sprint10 B3 backup loud-fail (BJ date + size assert + osascript + mail) | 衍生 merge |
| `afbcf3f` | docs(changelog): v0.4.14.22 sprint10 B3 backup loud-fail + BJ date | 衍生 doc |
| `d5691db` | fix(etl): sprint10 B3 backup BJ date + loud-fail (osascript + mail) | 衍生 fix |
| `6ee6531` | fix: CI lint F401 + sort_csv_by_date 名字不匹配 | 衍生 |
| `b499b80` | docs(sprint-10): 合并原 Sprint 9 留口候选 + today 新发现 is_member bug | 衍生 doc |

## 3. 教训

1. **codex 0.137.0 重塑 plan 是新模式**: Sprint 10 立下"codex audit 重塑 12→5 件"工作流, 后续 Sprint 11 (4→3 件 2.5 天) / Sprint 13 (4 phase review) 都沿用. codex 0.137.0 是 plan 阶段 AI 工具, 让 sprint scope 更聚焦.
2. **"is_member 根因重诊断" 教训**: Sprint 5 找的"UNIQUE INDEX race" 根因在 Sprint 10 被重诊断为 "staging overwrite", 删 prod UNIQUE INDEX 不是治根方案. Sprint 5-10 5 个 sprint 后才发现, 说明根因调查需要 sprint 间反复验证.
3. **sim-prod test 260 次 0 错误**: Sprint 10 A2 D-7 sim-prod test 跑 260 次新连接 0 错误, 是项目"高负载稳定" 的金标准, 后续 Sprint 11+ 沿用.

## 4. 关键指标

- **commits**: 13+ main commits (3 B1 主体 + 10 衍生)
- **主要文件**: `scripts/etl/preflight.py` (B1 主体 staging NOT EXISTS) + `scripts/etl/w4_memory_limit.py` (W4 8GB 硬限) + `scripts/etl/rss_limit.py` (RSS 12GB 硬限) + `scripts/etl/sim_prod_test.sh` (260 次跑批) + `scripts/backup/duckdb_daily.sh` (loud-fail) + `docs/SPRINT-10-RETROSPECTIVE.md` (补齐)
- **version**: v0.4.14.21/22/23 (Sprint 10 衍生)
- **tests**: 沿用 141+ root test passed + 459+ 既有
- **main commit**: `98c5e84`
