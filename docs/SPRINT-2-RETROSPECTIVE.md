# Sprint 2 Retro — 4 任务: pipeline 集成 + RFM banner + 飞书 refresh + W4 T-7 验证 (2026-05 下)

> Sprint 2 = 4 任务并行: W3/W4 pipeline 集成 + RFM version banner + 飞书架构文档 refresh + W4 T-7 验证

## 1. Sprint 结果

Sprint 2 是 Sprint 1 收口后的集成 sprint, 完成 4 项关键交付: 把 ETL 4 阶段 (Sprint 1 写的 QW2/QW4/S1/S2) 集成到 W3/W4 pipeline 主流程, 加 RFM cache version banner 提升调试可见性, 重写飞书架构文档 (背景/角色/系统图/集成点), 在 T-7 (生产日 7 天前) 跑 W4 真验证一次.

**主要交付** (从 git log 反推 + Sprint 3 4-done 文档对照):
- W3 (W3 = W3=ETL QW4 baseline window 3) / W4 (W4=ETL S1 GROUPING SETS window 4) pipeline 集成 commit
- RFM version banner 接入前端 (RFM cache 命中显示 algo_version)
- 飞书架构 7 份文档 refresh: 00-system-overview + 01-roles + 02-system-diagram + 03-data-flow + 04-integration-points + 05-faq + 06-troubleshooting
- W4 T-7 真跑验证 (生产日 7 天前, 1 次真跑, 4/4 PASS)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `f8a707e` (retrospective commit 反推) | docs: sprint2 收口 | 收口 |
| `cedcbbb` (Sprint 9 反推时同段时间) | fix(etl): Sprint 9 维修 | 衍生 |
| (W3/W4 pipeline 集成) | feat(etl): W3/W4 pipeline 集成 | W3/W4 |
| (RFM version banner) | feat(frontend): RFM version banner | RFM banner |
| (飞书架构 refresh) | docs(feishu-architecture): 7 份文档 refresh | 飞书 |
| (W4 T-7 验证) | docs(validation-reports): W4 T-7 验证 | W4 T-7 |

## 3. 教训

1. **W3/W4 集成要先于 Sprint 3 跑批**: Sprint 2 提前集成让 Sprint 3 第一次跑批就 13.4 min 真闭环, 避免 Sprint 3 边集成边跑批.
2. **T-7 验证是 "金标准"**: Sprint 2 留的 W4 T-7 真跑报告 (`docs/validation-reports/w4-full-t7-2026-06-06.md`) 在 Sprint 3-7 一直被引用作 baseline, 是后续 sprint 的"地面真相".

## 4. 关键指标

- **commits**: 30-40 (W3/W4 pipeline + RFM banner + 飞书 7 doc + W4 T-7)
- **主要文件**: `scripts/etl/w3_*.py` + `scripts/etl/w4_*.py` (pipeline 集成) + `frontend-vue3/src/components/RFMCacheVersion.vue` (banner) + `docs/feishu-architecture/0[0-6]-*.md` (7 份) + `docs/validation-reports/w4-full-t7-2026-06-06.md`
- **version**: pre-versioning
- **tests**: 沿用 Sprint 1 (50-100 量级, pytest count 增长慢)
