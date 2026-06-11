# Sprint 1 Retro — 项目 init + ETL 4 阶段 (2026-05 中)

> Sprint 1 = 项目初始化 + ETL 流水线 4 阶段奠基 (QW2 read_only / QW4 baseline / S1 GROUPING SETS / S2 override / M1 scheduler)

## 1. Sprint 结果

Sprint 1 是芙清 CRM 客户分析系统的奠基 sprint, 完成项目脚手架 + ETL 4 阶段核心. 期间建立 4 个 Quartz Window (QW2 read_only / QW4 baseline / S1 GROUPING SETS / S2 override) + 1 个 Manual Window (M1 scheduler) 的 ETL 流水线雏形, 配套前端市场对焦看板 4 Tab (商品资产/客户资产/达播资产/其他资产) + 飞书架构文档.

**主要交付** (从 git log 最早 80 commits 反推):
- 后端 auth router + Bearer token 中间件 + CORS 收紧 (`f28f067`)
- 前端登录 (LoginView + auth store + 路由守卫 + 加载动画) (`ad44f6e`)
- 市场对焦看板 4 Tab (`1acf25e`)
- 品类回购 RFM 8 象限改造 (`68408d5`)
- RFM CTE 提取 + 品类下钻 API (`ee48745`)
- ETL 4 阶段核心: read_only / baseline / GROUPING SETS / override
- ETL 调度 launchd (M1 W6.5 scheduler)

## 2. 关键 commit

| SHA | 主题 | 阶段 |
|-----|------|------|
| `1a2647d` | feat: init CRM analytics platform | 项目脚手架 |
| `f28f067` | feat: 后端认证模块 | QW2 auth |
| `ad44f6e` | feat: 前端登录 | QW2 frontend |
| `1acf25e` | feat: 市场对焦看板 4 Tab | QW2 dashboard |
| `68408d5` | feat(category): 品类回购 RFM 8 象限 | S1 RFM |
| `ee48745` | feat(backend): RFM CTE 提取 + 品类下钻 | S1 backend |
| `f573eb6` | feat(etl): --rescan-channel 子命令 | M1 scheduler |
| `f2f00fe` | refactor: split run_etl.py into scripts/etl/ | ETL 4 阶段收口 |
| `02ac618` | refactor: split schemas.py into business domain | Phase 4 架构 |

## 3. 教训

1. **Phase 拆分要早**: Sprint 1 就把 run_etl.py 拆 scripts/etl/ package, schemas.py 拆业务 domain 模块, 后期 audit / Pydantic 化才有基础. Sprint 17 #120 才能在 10 contract 上跑 B2 audit.
2. **RFM 8 象限 vs R 区间**: Sprint 1 早期用 R 区间切分, 后来改造 RFM 8 象限 (Sprint 1 后期 68408d5 commit 切换). 后期 Sprint 8 又有 R 桶 pre_cutoff bug 修复 (90b3ac2), 口径变更要写契约.

## 4. 关键指标

- **commits**: 80+ (init → 品类回购 RFM 8 象限 → ETL 4 阶段 Phase 0-3)
- **主要文件**: `backend/main.py` (auth router), `frontend-vue3/src/views/MarketFocus*.vue` (4 Tab), `scripts/etl/` (4 阶段), `backend/contracts/` (业务 domain schemas)
- **version**: pre-versioning, Sprint 1 没有 VERSION 文件
- **tests**: pre-`v0.4.13`, 早期 pytest 数量小 (50-100 量级)
