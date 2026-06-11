# Sprint 11 Retro — codex 0.137.0 audit 4→3 件 + YOY/pp 5 层修法 (2026-06-08→09)

> Sprint 11 = codex 0.137.0 audit 重塑 4→3 件 2.5 天 + YOY/pp 5 层修法 (frontend humanizeChange v2 + backend round 精度 + vite no-store + CI 修 + YOY/pp 全链路重构 v0.4.14.26 + 30指标占比显示修正 v0.4.14.27), main d16e27a

## 1. Sprint 结果

Sprint 11 是 sprint 历史上 "codex audit 重塑 4→3 件 2.5 天"代表, 完成 3 件: S11-1 DuckDB 1.5.3 升级 (治根 Sprint 5-10 留的 ART race), S11-3 WO-1 修复 2 处 read_only conn config conflict, S11-4 立 vitest 框架 (1 组件 4 test PASS). 期间 YOY/pp 5 层修法是 Sprint 8 P0 的延伸: frontend humanizeChange v2 + backend round 精度 2→4 位 + vite dev no-store + CI 修 + YOY/pp 全链路重构 v0.4.14.26 + 30 指标占比显示修正 v0.4.14.27.

**主要交付** (3 件重塑 + YOY/pp 5 层修法):
- S11-1: DuckDB 1.5.3 升级 (治根 ART race) (`6e19d80` / `b56d2ac`)
- S11-3: WO-1 修复 2 处 read_only conn config conflict (`e1a99d5` / `dbc6358`)
- S11-4: 立 vitest 框架 (1 组件 4 test PASS) (`d465e03` / `12f4cd7`)
- YOY/pp 5 层修法: frontend humanizeChange v2 (4e902cb / 5e98ed7) + backend round 精度 2→4 位 (f698ea9) + vite dev no-store (634b675 / 682c78f) + CI 修 (21ea619 / c7e57cb / 3a67dad) + 全链路重构 v0.4.14.26 (ebc99f1) + 30 指标占比显示修正 v0.4.14.27 (62cde32 / 9f5c776 / d16e27a)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `d16e27a` | docs: CHANGELOG v0.4.14.27 — 30指标占比显示修正 | 收口 doc |
| `9f5c776` | Merge branch 'fix/audience-ratio-percent' — 30指标占比显示修正 | 衍生 merge |
| `62cde32` | fix: 30指标占比显示修正 — 后端ratio×100返回百分比, 前端去*100 | 衍生 fix |
| `7a34ee5` | chore: cleanup — 删除 SPRINT-10-PLAN, 归档 validation-reports, 更新 etl_perf baseline | 衍生 |
| `ebc99f1` | refactor: YOY/pp 全链路重构 — 后端返回可显示值, 前端只做展示 (v0.4.14.26) | YOY/pp |
| `28783fb` | fix(frontend): 移除 likely-wrong 过滤，直接显示所有数据 | 衍生 |
| `0db00af` | Merge pull request #22 from weiweity/feature/sprint11-ci-red-fix | CI 修 merge |
| `371ccb2` | fix(ci): concurrent test CI 跳过 (本地 PASS, CI 15+ min 死锁) | CI 修 |
| `3a67dad` | fix(test): w7 test 期望 16GB→8GB (跟 Sprint 10 B1 DEFAULT_ASYNC_OVERRIDE 一致) | CI 修 |
| `f698ea9` | fix(backend): overview API yoy_change/mom_change round 精度 2→4 位小数 | YOY/pp |
| `c7e57cb` | fix(ci): concurrent test timeout 保护 (防 CI 死锁) | CI 修 |
| `21ea619` | fix(ci): sprint11+ CI 爆红 — ruff 5 错 + pytest flaky concurrent 修 | CI 修 |
| `92a8d1b` | docs(changelog): v0.4.14.25 sprint11+ YOY/pp unit-aware 0.00 形式 + vite HMR no-store | YOY/pp doc |
| `682c78f` | merge: sprint11 vite dev no-store + HMR full-reload fallback | YOY/pp merge |
| `634b675` | fix(frontend): sprint11 vite dev 显式 no-store 头 + HMR full-reload fallback | YOY/pp |
| `c2958fd` | merge: sprint11 YOY/pp v2 unit-aware 0.00 形式 | YOY/pp merge |
| `a551e2a` | fix(frontend): sprint11 YOY/pp 修法 v2 - unit-aware 区分 *100, 0.00 形式 | YOY/pp |
| `3f2fa93` | merge: sprint11 TS6133 fix MetricCard.test.ts unused param | 衍生 merge |
| `d384c09` | test(frontend): fix TS6133 unused 'label' param in MetricCard.test.ts | 衍生 |
| `5e98ed7` | merge: sprint11 YOY/pp 四舍五入显示 (humanizeChange) | YOY/pp merge |
| `4e902cb` | fix(frontend): sprint11 YOY/pp 显示用 Math.round + auto-trim 整数 trailing zeros | YOY/pp |
| `0bb2b47` | feat(etl): sprint10 add run-etl.sh 手动触发脚本 (Sprint 10 写, Sprint 11 收口阶段补 commit) | 衍生 |
| `34b970a` | docs(changelog): v0.4.14.24 sprint11 DuckDB 1.5.3 治根 + WO-1 conn + vitest 框架 | 收口 doc |
| `12f4cd7` | merge: sprint11 S11-4 立 vitest 框架 (4 test PASS) | vitest merge |
| `d465e03` | test(frontend): sprint11 S11-4 立 vitest+@vue/test-utils 框架 (1 组件 4 test PASS) | vitest 主体 |
| `b56d2ac` | merge: sprint11 S11-1 DuckDB 1.5.3 升级 (治根 ART race) | DuckDB merge |
| `6e19d80` | chore(deps): sprint11 S11-1 DuckDB 1.5.2 → 1.5.3 (治根 ART race) | DuckDB 主体 |
| `dbc6358` | merge: sprint11 S11-3 WO-1 修复 2 处 read_only conn config conflict | WO-1 merge |
| `e1a99d5` | fix(etl): sprint11 S11-3 WO-1 修复 2 处 read_only conn 缺 config | WO-1 主体 |

## 3. 教训

1. **"codex audit 重塑 4→3 件" 是 Sprint 10 模式延伸**: Sprint 11 沿用 Sprint 10 codex 0.137.0 重塑 plan, 4→3 件 2.5 天, 关键 3 件独立可并行 (DuckDB 升级 / WO-1 read_only conn / vitest 框架).
2. **YOY/pp 5 层修法是 Sprint 8 P0 反弹**: Sprint 8 P0 YOYBadge 模式统一, Sprint 11 发现后端 round 精度 (2→4) + frontend humanizeChange v2 + vite no-store + CI 修 + 全链路重构 5 层都要修. 1 个前端 bug 跨 5 层, 留 Sprint 12-14 继续.
3. **DuckDB 1.5.3 升级治根 ART race**: Sprint 11 S11-1 升级 DuckDB 1.5.3 治根 Sprint 5-10 留的 ART race. Sprint 16 才发现 1.5.3 也有 race (留 Sprint 16 中止, 等 1.5.4).

## 4. 关键指标

- **commits**: 30+ main commits (3 主体 + 27 衍生)
- **主要文件**: `requirements.txt` (DuckDB 1.5.3) + `scripts/etl/read_only_conn.py` (WO-1 修) + `frontend-vue3/vitest.config.ts` (vitest 框架) + `frontend-vue3/src/components/YOYBadge.vue` (humanizeChange v2) + `frontend-vue3/src/api/*.ts` (round 精度) + `frontend-vue3/vite.config.ts` (no-store) + `docs/SPRINT-11-RETROSPECTIVE.md` (补齐)
- **version**: v0.4.14.24 (Sprint 11 DuckDB) + v0.4.14.25 (YOY/pp 形式) + v0.4.14.26 (全链路重构) + v0.4.14.27 (30 指标修正)
- **tests**: 沿用 141+ root test passed + 459+ 既有 + 4 vitest 新
- **main commit**: `d16e27a` (收口)
