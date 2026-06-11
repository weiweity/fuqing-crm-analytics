# Sprint 8 Retro — P0 前端 2 bug + P1 16 root test 删 (2026-06-07)

> Sprint 8 = 2 subagent 并行 30min 140K tokens, P0 前端 2 bug 修复 (YOYBadge 模式统一 + R 桶 pre_cutoff 改 end_dt) + P1 16 root test ignore 删 (pyproject.toml testpaths 改 default), 4 commit bc65360/90b3ac2/2b00de4/1cf666b

## 1. Sprint 结果

Sprint 8 是 sprint 历史上"小 sprint 快速收口"代表, 2 subagent 并行 30 min 140K tokens 完成 2 件: P0 前端 2 bug 修复 (YOYBadge 模式统一占比/率用 pp 绝对值用 %, R 桶 pre_cutoff 改 end_dt 截止), P1 16 root test ignore 删 (Sprint 3 留的 16 root tests 留了 5 个 sprint 终于真删, pyproject.toml testpaths 改 default). 期间 30 min 是 sprint 最短记录.

**主要交付** (1 P0 + 1 P1):
- P0: 前端 2 bug 修复 (YOYBadge 模式统一 + R 桶 pre_cutoff 改 end_dt) - bc65360
- P1: 删 16 root test ignore 路线 (pyproject.toml testpaths 改 default) - 2b00de4

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `bc65360` | fix(audience+rfm): sprint8 P0 前端 2 bug 修复 (YOYBadge 模式统一 + R 桶 pre_cutoff 截止改 end_dt) | P0 主体 |
| `90b3ac2` | merge: sprint8 P0 前端 2 bug 修复 | P0 merge |
| `2b00de4` | chore(test): sprint8 P1 删 16 root test ignore 路线 | P1 主体 |
| `1cf666b` | merge: sprint8 P1 删 pyproject.toml testpaths (16 root test ignore 路线) | P1 merge |

## 3. 教训

1. **"16 root test 留 5 个 sprint 真删"**: Sprint 3 留的 16 root test ignore 路线 (P1-2) 在 Sprint 8 P1 终于真删, 期间 Sprint 4-7 靠 testpaths 兜底. Sprint 7 P0 重构 service import 模式 (141 passed) 是前置, Sprint 8 P1 才能真删 ignore. 跨 sprint 治理债务闭环需要前置 sprint 治根.
2. **"前端 bug 修复" 是高 ROI 短 sprint**: Sprint 8 P0 修 2 个前端 bug 只 30 min, 价值是修复 R 桶 pre_cutoff 截止错 (Sprint 1 RFM 8 象限沿用的老 bug) + YOYBadge 模式统一. 短 sprint 高 ROI 是 Sprint 8 的核心价值.
3. **30 min 是新基线**: Sprint 8 立下"30 min 2 subagent 并行"基线, 后续 Sprint 11 / 16.5 (1.5h-2h) 比这长, 但 Sprint 8 是"小任务快速收口"代表.

## 4. 关键指标

- **commits**: 4 main commits (2 merge + 2 fix/chore)
- **主要文件**: `frontend-vue3/src/components/YOYBadge.vue` (模式统一) + `frontend-vue3/src/views/audience/*.vue` (R 桶) + `pyproject.toml` (testpaths 改 default) + `docs/SPRINT-8-RETROSPECTIVE.md` (补齐)
- **version**: 沿用 v0.4.14.13/15, 没新 version bump
- **tests**: 沿用 141+ root test passed + 459+ 既有
- **main commit**: `1cf666b`
