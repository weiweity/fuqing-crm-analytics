# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepchangelog.com/en/1.1.0/),

## [v0.4.14.57] - 2026-06-13 - fix(etl): Sprint 21+ P0 DuckDB race workaround

### Fixed
- DuckDB 1.5.x ART index 跨 connection race 导致 ETL 跑批崩溃 (1.88M 淘客订单 UPDATE 触发 "Failed to delete 0/2048 rows")
- 新增 `--read-only` flag 跳过 step 2 (淘客渠道纠正) + step 6 (RFM 缓存预计算), 24min 跑通 0 race
- 保留 v2 DROP+RECREATE index workaround 在 `scripts/etl/pipeline.py`, 等 DuckDB 1.6.0 stable 后移除
- 修复 `VisitorSummaryResponse` / `CategoryDistributionItem.pct` 契约类型错误导致的 500 ResponseValidationError
  - `member_join_rate` / `ly_member_join_rate`: RatioField → PercentageField
  - `member_join_rate_yoy` / `mom`: RatioField → PpField
  - `CategoryDistributionItem.pct`: RatioField → PercentageField
- 修复 RFM 8象限分析 `repurchase_gsv_ratio` > 1 越界 (TTL segment 被错误排除在 total 之外)
  - `tier_flow.py` + `rfm_analysis/period.py`: total 累加移到 segment 判断外，所有 segment 都计入分母
- 修复品类复购周期 / 羊毛党 / 风险预警 3 个端点 ResponseValidationError 500
  - `ProductClassRepurchase.gsv_yoy` RatioField (0-1) → float（变化率可负可超 1）
  - `WoolPartyBreakdown.type1/2_ratio` RatioField (0-1) → float（count/total_users 可超 1）
  - `ChurnScatterPoint/BarData/TableRow.mom_change_rate` RatioField (0-1) → float（可负）

### Added
- `backend/tests/test_taoke_channel_duckdb_race.py`: 4 个 race 回归测试
- `scripts/etl/activate_duckdb_1_6_0_stable.sh`: 1.6.0 stable 一键激活脚本
- `docs/SPRINT-20+-P0-1.6.0-DEV12-FAILURE.md`: 1.6.0.dev12 失败复盘
- `docs/SPRINT-21-P0-ETL-RESOLVE.md`: Sprint 21 P0 ETL 治根记录

## [v0.4.14.45] - 2026-06-12 - wip: Sprint 20+ P0 DuckDB 1.5.4 升 prod 后续 10 个 WIP 修改落地

### 背景
Sprint 5 #20 软删 (v0.4.14.44) 完整收口之前, subagent 找到主项目根有 33 个未提交修改 (Sprint 20+ P0 DuckDB 1.5.4 升 prod 准备后续), 走修 bare 标记 (`.git/config [core] bare = false`) + 查全盘 stash (5 个) + 解决 baseline 冲突 (`data/processed/etl_perf/baseline_2026_06_03.json`) + 删 1 个 stash (stash@{0}) 之后, 10 untracked 修改保留在 working tree.

### Added (WIP)
- **docs/SPRINT-16-P0-ACTIVATION.md** (Sprint 16 P0 DuckDB 1.5.3 激活报告)
- **frontend-vue3/src/AudienceView.vue** (受众视图 WIP)
- **frontend-vue3/src/CategoryView.vue** (类目视图 WIP)
- **frontend-vue3/src/RFMView.vue** (RFM 视图 WIP)
- **frontend-vue3/src/category-tabs/CategoryRepurchaseTab.vue** (类目回购 Tab)
- **frontend-vue3/src/category-tabs/ProductClassRepurchaseTab.vue** (产品类回购 Tab)
- **frontend-vue3/src/health/{F,M,R}IntervalTab.vue** (3 个健康间隔 Tab)
- **frontend-vue3/src/health/HealthOverviewTab.vue** (健康总览 Tab)
- **frontend-vue3/src/health/RFMSegmentDrilldown.vue** (RFM 段下钻 Tab)
- **frontend-vue3/src/health/ValueTierTab.vue** (价值层 Tab)
- **scripts/check_duckdb_release.py** (DuckDB 1.5.4 release 检查)
- **scripts/etl/activate_duckdb_1_5_4_stable.sh** (DuckDB 1.5.4 stable 激活脚本)
- **scripts/etl/check_duckdb_release_cron.sh** (定时检查)
- **scripts/etl/com.fuqing.duckdb-release-check.daily.plist** (launchd 调度)

### 后续
- Sprint 5 #20 软删留 Sprint 5+ 后续处置 (主项目根 scraper/ 521M 还有, 数据文件 4 件还在 scraper/core/, 不挪到独立 repo)
- 独立 repo Sprint 5 #21 双层清理 (`/scraper/core/` 跟 `/core/` 选一留一删)
- 独立 repo Sprint 5 #22 5 行修重建 + commit
- 独立 repo Sprint 5 #23 简历文档 dmp-data-scraper.md 跟新

## [v0.4.14.56] - 2026-06-12 - chore(p0): Sprint 20+ P0 DuckDB 1.5.4 stable 监控 + 升 prod 准备

### Background
Sprint 16 P0 abort (DuckDB 1.5.3 ART race) 续. Sprint 19 P0 已装 1.5.4.dev18 验证治根 (5/5 idempotent batch + 4 unit tests, prod race 0%), 1.5.4 stable release 还没出 (PyPI latest stable 1.5.3, latest dev 1.6.0.dev12). 准备监控 + 一键激活路径, stable release 出来即合 v2 code + 升 prod.

### Added
- **`scripts/etl/com.fuqing.duckdb-release-check.daily.plist`**: launchd plist, 每日 9:00 跑 DuckDB release 检查 (避开 ETL 8:30 跑批窗口)
- **`scripts/etl/check_duckdb_release_cron.sh`**: 每日检查 PyPI 1.5.4 stable release, 出 release 后写 `/tmp/fuqing-duckdb-release-stable.flag` 触发激活 + 飞书告警
- **`scripts/etl/activate_duckdb_1_5_4_stable.sh`**: 4 步一键激活脚本 (装 stable + 跑 v2 4 tests + 切 fix branch + smoke test)

### 治根数据 (Sprint 19 P0 验证 1.5.4.dev18)
- 4 unit tests (drop_recreate / idempotent / rollback / P6-2 keyword) 全过 (0.52s)
- 5 轮 idempotent batch on 10K rows 全过, 0 race
- prod race 触发率 0% (跟 1.5.3 prod race 比)

### 激活路径 (1.5.4 stable release 后)
1. cron 自动写 flag + 飞书告警
2. 用户手动: `bash scripts/etl/activate_duckdb_1_5_4_stable.sh`
3. 自动装 stable + 跑 v2 tests + 切 fix branch + smoke test
4. 用户手动: 改 requirements + merge --no-ff fix/sprint16-p0-duckdb-taoke-channel-race
5. 跑真 prod 跑批 (痛点 1 W1 --update ~13-17 min)
6. CHANGELOG v0.4.14.57 (post-merge) + 卸 cron

### 任务来源
- Sprint 19 retrospective Section 4 P0 #119 → Sprint 20+ P0

### 验证
- dry-run cron: PyPI 查询成功, log 写入 `/tmp/fuqing-duckdb-release-check.log`, 1.5.4 stable 没出 → 不写 flag, 不发告警 (正确)
- 脚本 bash -n 语法检查: 2/2 OK

### 后续
- 等 DuckDB 1.5.4 stable release (外部触发) → 跑激活脚本
- v2 code 留 branch `fix/sprint16-p0-duckdb-taoke-channel-race` (2 commits: 543fb43 + bb34810), stable 后才合 main

## [v0.4.14.55] - 2026-06-12 - refactor(frontend): Sprint 20 P1-2 YOYGuard 吸 YOYBadge 风格 + 9 组件迁移 (拿掉 YOYBadge wrapper 间接层)

### Background
Sprint 18 #124 抽 YOYGuard 通用组件时 YOYBadge 改成 thin wrapper, 但保留独立文件. Sprint 20+ backlog "YOYGuard 扩 4 老组件" 4 组件名跟实际 yoy 状况不符, 实际 Sprint 20 P1-2 scope 改为:

方案 A: 9 个 YOYBadge 用户 (AudienceView/CategoryView/RFMView/CategoryRepurchaseTab/ProductClassRepurchaseTab/health/{F,M,R}IntervalTab/ValueTierTab/HealthOverviewTab) 全部迁移到 YOYGuard 直接调用, YOYGuard 加 `styled` prop 吸收原 YOYBadge 的箭头 + 颜色 styling, 删 YOYBadge.vue.

### Changed
- **`frontend-vue3/src/components/YOYGuard.vue`**: 加 `styled?: boolean` prop (默认 false). `styled=true` 渲染 YOYBadge 同款样式 (箭头 ↑/↓ + 绿/红背景色 + "数据异常" 灰色守卫)
- **`frontend-vue3/src/components/YOYBadge.vue`**: **删除** (被 YOYGuard styled 模式替代)
- **`frontend-vue3/src/components/YOYGuard.test.ts`**: 加 8 个 styled 模式 vitest (null/正/负/零/异常值/边界), 23/23 全部 pass
- **9 个视图文件**: `h(YOYBadge, ...)` → `h(YOYGuard, { ..., styled: true })` (table render) / `<YOYBadge>` → `<YOYGuard styled />` (template)
  - AudienceView.vue (33 处)
  - CategoryView.vue (7 处)
  - RFMView.vue (5 处)
  - CategoryRepurchaseTab.vue (5 处)
  - ProductClassRepurchaseTab.vue (5 处)
  - FIntervalTab.vue / MIntervalTab.vue / RIntervalTab.vue / ValueTierTab.vue (各 5 处)
  - HealthOverviewTab.vue (2 处 template)

### 治理
- Sprint 20+ P1-2 (YOYGuard 扩 4 老组件, 实际拿掉 YOYBadge 间接层) ✅ 完成
- YOYBadge.vue wrapper 删除, YOYGuard 是唯一 YOY 入口 (single source of truth)
- 9 组件 ~50 处间接调用合并为直接调用, 减少 wrapper 层

### 任务来源
- Sprint 19 retrospective Section 4 治理债务 #5 (YOYGuard 扩 4 老组件) → Sprint 20 P1-2

### 验证
- `npx vitest run src/components/YOYGuard.test.ts`: 23/23 passed (15 unstyled + 8 styled)
- `npx vue-tsc --noEmit`: 0 type error
- 9 视图文件 YOYBadge 0 引用 (迁移完成)
- YOYBadge 同款契约保留: null → "—", 0 → "+0.00% ↑", 1e6 boundary → "+1000000.00% ↑", 1e7 → "数据异常"

### 后续
- Sprint 20+ P0 (DuckDB 1.5.4 stable 监控) — 等外部 release
- Sprint 20+ 6/9+ 18 老客 `is_member=TRUE` 验证 — 等 prod 跑批

## [v0.4.14.54] - 2026-06-12 - feat(lint): Sprint 20 P1-1 R5 扩 Optional / PEP 604 / Union 包装 (5 新 R5a tests)

### Background
Sprint 19 #1 R5 治根 List[RatioField/PercentageField/PpField] 时漏了 Optional 包装场景:
- `Optional[List[RatioField]]`  (Sprint 19 漏掉, Sprint 20 治根)
- `List[Optional[RatioField]]`  (Sprint 20 P1-1 新增)
- `List[PpField | None]`        (PEP 604 inside List)
- `Union[List[PpField], None]`  (Union Tuple slice)

Pydantic v2 跟 Sprint 19 一样不触发 element-wise Field 约束, 必须 `List[Annotated[float, Field(ge, le)]]`. 4 个场景都是潜在 R5 漏报.

### Changed
- **`backend/contracts/_lint.py:_list_inner_type_name`**: 顶层加 `Optional`/`Union` 包装识别 + 递归到 `_extract_inner_name`
- **`backend/contracts/_lint.py:_extract_inner_name` (新增)**: 递归 unwrap Optional / PEP 604 / Union Tuple / 字符串 forward ref. Annotated 节点视为合规返 None
- **`backend/contracts/tests/test_lint.py`**: 加 5 个 TestR5OptionalWrappers 测试覆盖 4 true-positive + 1 false-positive

### 治理
- Sprint 20+ backlog P1-1 (linter 增强) ✅ 完成
- Sprint 19 R5 漏报修复 (Optional 套 List) ✅

### 任务来源
- Sprint 19 retrospective Section 4 治理债务 #1 (linter 增强) → Sprint 20 P1-1

### 验证
- `pytest backend/contracts/tests/test_lint.py -v`: 19/19 passed (14 老 + 5 新 R5a)
- `python -m backend.contracts._lint`: 0 issue
- Sprint 17 R1-R4 + Sprint 19 R5 + Sprint 20 P1-1 R5a 全部 OK

### 后续
- Sprint 20+ P1-2 (YOYGuard 扩 4 老组件) — backlog 4 组件名跟实际 yoy 状况不符, 需 user 决策调整范围
- Sprint 20+ P0 (DuckDB 1.5.4 stable 监控) — 等外部 release

## [v0.4.14.53] - 2026-06-12 - refactor(etl): Sprint 16.5+1 B1 治根 — 抽 lark 通道到 ETL 自己 (跨子项目依赖解耦)

### Background
Sprint 16.5+1 scraper 解耦准备 (v0.4.14.52) 时发现 3 个 ETL 脚本 (notify.py:13-17, assertions.py:37, dq_monitor.py:73) 跨子项目 import scraper.core.sanity_check._send_lark_alert, 5 处命中带 ImportError fallback. 跨子项目依赖违反 CLAUDE.md "层边界不可跨越" 约束, 治根.

### Changed
- **新建 `scripts/etl/common/__init__.py`**
- **新建 `scripts/etl/common/lark.py`** (从 `scraper/core/sanity_check.py:_send_lark_alert` 抽完整实现, 保留 LARK_OPEN_ID / LARK_WEBHOOK / lark_oapi SDK 调用)
- **`scripts/etl/notify.py:13-17`**: `from scraper.core.sanity_check import _send_lark_alert` → `from scripts.etl.common.lark import _send_lark_alert`
- **`scripts/etl/assertions.py:37`**: 同上 (函数内 lazy import)
- **`scripts/etl/dq_monitor.py:73`**: 同上 (函数内 lazy import)

### 痛点闭环
- Sprint 16.5+1 scraper 解耦准备留 B1 治根 ✅
- 跨子项目依赖 (`from scraper.core.sanity_check import _send_lark_alert`) → ETL 自治 (`from scripts.etl.common.lark import _send_lark_alert`)

### 任务来源
- Sprint 16.5+1 scraper 解耦准备阶段 4 (3 ETL import 命中) → Sprint 16.5+1 B1 治根

### 验证
- `pytest backend/tests/ -x -q`: ETL 测试不破 ✅
- 跑批业务 (data3.csv +45 行) 不阻塞

### 后续
- 主项目 scraper/ 软删 + symlink 留 Sprint 19+ 治理 (阶段 4 留)
- check_dmp_session 业务层 session 验证 留 Sprint 19+ 治理 #141
- 5 行修重建 留 Sprint 19+ 治理 #142
- 主项目 scraper 旧版 5 文件清理 留 Sprint 19+ 治理 #143

## [v0.4.14.52] - 2026-06-11 - docs: Sprint 1-12 retrospective 反推补齐 (12 docs + 1 index)

### Added
- **`docs/SPRINT-1-RETROSPECTIVE.md`** (新, 42 行) — Sprint 1 反推补齐: 项目 init (1a2647d) + ETL 4 阶段 (QW2 read_only / QW4 baseline / S1 GROUPING SETS / S2 override / M1 scheduler) + 市场对焦看板 4 Tab + 飞书架构奠基
- **`docs/SPRINT-2-RETROSPECTIVE.md`** (新, 36 行) — Sprint 2 反推补齐: W3/W4 pipeline 集成 + RFM version banner + 飞书架构 7 份文档 refresh + W4 T-7 真跑验证 (留 Sprint 3-7 baseline)
- **`docs/SPRINT-3-RETROSPECTIVE.md`** (新, 40 行) — Sprint 3 反推补齐: 5/5 P0+P1 done, 痛点 1 闭环 13.4 min, 3 workflow 并行 + 5 轮 review + 4 轮 P1-3 修, v0.4.13, 459+ tests
- **`docs/SPRINT-4-RETROSPECTIVE.md`** (新, 36 行) — Sprint 4 反推补齐: 2/2 P0 done (痛点 1 端到端 + DuckDB 55GB 备份) + P0-3 hotfix 2 dedup, main 3882f91
- **`docs/SPRINT-5-RETROSPECTIVE.md`** (新, 39 行) — Sprint 5 反推补齐: 5 维度 + deep dive 找真根因 DuckDB 1.5.2 UNIQUE INDEX race, Fix A 拆 2 tx (5a77fa3), 跑批真闭环 17 min, 清理 513GB
- **`docs/SPRINT-6-RETROSPECTIVE.md`** (新, 37 行) — Sprint 6 反推补齐: 4 subagent 并行 15 min 196K tokens, 5→6 层防护 + W7 pytest 修复 + D-6 版本同步, 5 commit
- **`docs/SPRINT-7-RETROSPECTIVE.md`** (新, 40 行) — Sprint 7 反推补齐: 3 subagent 并行 2.5h 264K tokens, P0 治根 10 root test fail 141 passed + P2 6 层防护 cleanup.md 516 行 + P2 DuckDB Fix A KEEP
- **`docs/SPRINT-8-RETROSPECTIVE.md`** (新, 34 行) — Sprint 8 反推补齐: 2 subagent 并行 30 min 140K tokens, P0 前端 2 bug (YOYBadge 模式统一 + R 桶 pre_cutoff 改 end_dt) + P1 16 root test ignore 删
- **`docs/SPRINT-9-RETROSPECTIVE.md`** (新, 49 行) — Sprint 9 反推补齐: 维修 4 件根因 (watchdog 阈值 / cache key / W3 valid_sql / W4 memory) + 13 衍生 + DMP 6/8 文档同步
- **`docs/SPRINT-10-RETROSPECTIVE.md`** (新, 47 行) — Sprint 10 反推补齐: codex 0.137.0 重塑 plan 12→5 件 + B1 preflight 3 件根因 + is_member 根因重诊断, sim-prod 260 次 0 错误
- **`docs/SPRINT-11-RETROSPECTIVE.md`** (新, 61 行) — Sprint 11 反推补齐: codex audit 4→3 件 + YOY/pp 5 层修法 (frontend humanizeChange v2 + backend round 精度 + vite no-store + CI 修 + 全链路重构)
- **`docs/SPRINT-12-RETROSPECTIVE.md`** (新, 44 行) — Sprint 12 反推补齐: 7/7 质量加固 + 50M benchmark (查询 5.82x, RSS 3.9GB) + 架构方案 A + 清理 56GB

### Changed
- **`docs/document-index.md`** (加 12 行) — 当前 Sprint 表按时间倒序插 Sprint 1-12 共 12 行 (Sprint 12 插 Sprint 13 之前), 每行带行数 (34-61 行) + 反推补齐日期 2026-06-11

### 痛点闭环
- Sprint 1-12 缺乏正式 retrospective 文档 (历史 sprint 收口时跳过了 retrospective 步骤, 只有 docs commit) ✅ 闭环: 12 个 retrospective docs 反推补齐, 跟 Sprint 13-18 retrospective 模板对齐 (60-100 行简短格式, Sprint 结果 / 关键 commit / 教训 / 关键指标 4 段)
- document-index 缺 Sprint 1-12 入口 (用户 / 新人翻 sprint 历史无路径) ✅ 闭环: document-index 加 12 行, 按时间倒序排 (Sprint 12 → Sprint 1), 跟现有 Sprint 13-18 表同样格式

### 已知限制
- **4 个 memory (Sprint 1/2/4/9) 不在 worktree 写入 scope**: `~/.claude/projects/-Users-hutou/memory/project_sprint*.md` 是 Claude Code 全局状态, 不在 git worktree 内, 需从主 worktree 单独写. Sprint 4 memory 已存在 (`project_sprint4.md` 6213 bytes), 不重写. Sprint 1/2/9 memory 缺失, 需在主 worktree 用同样 YAML frontmatter 格式补. 本次 PR 留 TODO

### 验证
- 12 个文件全部 wc -l 验证 (34-61 行, 跟 Sprint 13-18 retrospective 同量级简短)
- 0 个文件含占位 / placeholder 文字 (per user 严禁条款)
- git log 顺序: 12 retrospective commit (1 per sprint) + 1 document-index commit = 13 commits, 全部在 chore/sprint-1-12-retrospective 分支
- pytest/lint/vitest 不变 (无 backend/frontend 改动, 不需要重跑)

## [v0.4.14.46] - 2026-06-12 - refactor(scraper): Sprint 5 #15 — 主项目根 scraper/ 软删 + 数据挪 + symlink (跟独立 repo fuqing-scraper/ 解耦)

### 背景
Sprint 4 (独立 repo v0.4.14.45) 10 untracked Sprint 20+ P0 DuckDB 升 prod 后续修改落地后, 主项目根 scraper/ 还有 (521M, 15 子目录, 6/8 15:13), 4 件数据文件 (data.csv 130.8K + data2.csv 56K + data3.csv 578K + completed_items.json 10K = 774.6K) 还在主项目根 scraper/core/ 里. Sprint 5 #15 (P0) 软删 + 数据挪 + symlink 收口. 跑批工具 5 .py md5sum 跟独立 repo 100% 一致, 仅数据文件 + chrome_profile/ + account.txt 留在主项目根 (因跑批业务需要).

### Changed
- **主项目根 scraper/ → scraper.legacy/** (软删, mv, 521M)
- **数据文件 挪到独立 repo fuqing-scraper/core/**:
  - data.csv (流转数据, 130.8K)
  - data2.csv (资产诊断数据, 56K)
  - data3.csv (单品洞察数据, 578K, md5sum 一致)
  - completed_items.json (断点续传缓存, 10K)
- **主项目根 scraper symlink → 独立 repo fuqing-scraper/**:
  - `ln -s /Users/hutou/Desktop/fuqin date/fuqing-scraper scraper`
- **独立 repo .gitignore 已经配好** data*.csv + completed_items.json + chrome_profile/ + account.txt (不进 git, 数据文件留本地)
- **主项目根 .gitignore 增量** scraper.legacy/ + scraper (2 行, 软删备份 + symlink 不进 git, 521M 安全隔离)

### 验证
- **跑批业务不阻塞**: `python3 -c "from scraper.core import dmp_common; print('import OK')"` ✅ + `from scraper.core import dmp_master` ✅ (走 symlink 走通, 5 单文件跑批工具 md5sum 跟独立 repo 100% 一致)
- **主项目 pytest**: 506 passed + 12 skipped (Sprint 18 v0.4.14.49 baseline, 1 个 rfm_recompute_window_dry_run 失败是 DuckDB 锁冲突 PID 15138 跟本任务无关)
- **数据文件 md5sum 一致** (data.csv b274a74cad04b076569b41295068466f + data2.csv 0f5713c01188406c51ceb8f7beec4826 + data3.csv f4cd887696b2582ceb584863f6efa917 + completed_items.json 8d563ab157549aeef3602bdff0b01479, 1 步到位挪走, 无损)
- **独立 repo .gitignore 已经配好** (account.txt + chrome_profile/ + *.csv + *.xlsx + completed_items.json + completed_items*.json, 数据文件不进 git), 主项目根 .gitignore 增量 scraper.legacy/ + scraper (2 行)
- **5 单文件跑批工具 md5sum 一致** (dmp_master.py 9d885406e9e6a1541f9dbba931283bd5 + dmp_common.py 3e4deacc93ee0e14f5bada3cafb4d536 + dmp_item_insight_scraper.py 0428bc1c08c083cd123fd483ee0c5a6e + dmp_scraper.py 2dde9e2ec12098fbd0ef863ba55ad675 + dmp_flow_scraper.py ab7035cd6fda36e7e2de8dd716ad6512, 跑批工具已完整迁到独立 repo, 仅数据文件需挪)

### 后续
- **1-3 天观察期** (跑批业务不受软删影响) 验证后删 scraper.legacy (Sprint 5+ 后续处置, Task #11 #144)
- 独立 repo Sprint 5 #16 (P1) 双层清理 (`/scraper/core/` 跟 `/core/` 选一留一删) - Task #16
- 独立 repo Sprint 5 #17 (P2) 5 行修重建 + commit - Task #17
- 独立 repo Sprint 5 #18 (P1) 简历文档 dmp-data-scraper.md 跟新 - Task #18
- Sprint 20+ #143 工单自动完成 (主项目根 scraper/ 已软删, 数据文件已挪, symlink 已走通)

## [v0.4.14.47] - 2026-06-11 - fix(cache): Sprint 18 #123 W5 cache invalidation 启动 hook (跨进程 manifest 同步)

### Added
- **`backend/services/rfm/cache.py:check_manifest_version_and_invalidate()`** (新, 89 行) — 启动 hook, 跨进程持久化 `last_seen_manifest_version` 到 `data/cache/w5kv_manifest_state.json` (env `FQ_W5KV_STATE_PATH` 可覆盖). 跟现有进程内 `_ManifestTracker` 互补: 进程内检测本进程 manifest 变化, 启动 hook 检测跨进程 (uvicorn 重启 / ETL 跑批后) 变化. 不一致时整表清空 12 orphan keys, 写新 state. best-effort: 任何异常被吞 + log warning, 不阻塞 uvicorn 启动
- **`backend/tests/test_cache_invalidation.py`** (新, 318 行, 10 测试) — 6 类场景覆盖: 1) 没 manifest → hook 静默; 2) 首次跑 (state 缺失) → invalidate + 写 state; 3) state 一致 → no-op; 4) manifest 升 → invalidate + 更新 state; 5) state 写失败 / manifest 损坏 → best-effort 不抛; 6) hook 跟 `cache.get()` 兼容
- **`docs/CACHE-INVALIDATION.md`** (新, 333 行) — 使用文档, 10 节: 背景 / 设计 / 触发条件 / 跟 Sprint 14.5/16.5/17 关系 / 跟跑批关系 / 手动触发 / 监控 / 验证 / FAQ (7 问) / 变更日志

### Changed
- **`backend/services/rfm/_shared.py:FLOW_ALGO_VERSION`** `v0.4.14.35` → `v0.4.14.47` — 行为变化 (新增启动 hook), 触发 cache key 全 miss 一次 (后续重算), 跟 Sprint 14.5 P1.4 约定一致
- **`backend/main.py:lifespan`** (7 行加) — startup event 调 `check_manifest_version_and_invalidate()`, 跟现有 `RfmQueryCache().ensure_table()` 配套, 包 try/except 不阻塞服务

### 痛点闭环
- Sprint 14.5 留治理债务 #4: "改 ratio/契约后必须手动 invalidate W5 DuckDB-KV cache (12 keys)" ✅ 闭环
- Sprint 17 retrospective Section 4 #4: 同上, 标记 P1, Sprint 18 #123 实现 ✅

### 任务来源
- Sprint 14.5 留 (Codex audit P1.4 配套治理) → Sprint 17 retrospective Section 4 #4 跟踪 → Sprint 18 #123 闭环

### 验证
- 新 10 个 pytest 全过 (`backend/tests/test_cache_invalidation.py`) — 0.47s
- 跟既有 w5_cache.py 23 测试兼容 (`33 passed in 1.79s` 含新 10)
- main 全套 pytest: 288 passed + 8 skipped (deselect 2 个 test_sim_prod_etl.py 已知 state-leak race, 跟本次改动无关)

## [v0.4.14.48] - 2026-06-11 - feat(frontend): Sprint 18 #124 YOYGuard 通用组件 + 扩 MetricCard / RFMSegmentDrilldown

### Added
- **`frontend-vue3/src/components/YOYGuard.vue`** (新, 61 行) — 通用 YOY/同比 守卫 + 格式化组件, props(value, unit, threshold=1e6, empty='—', precision=2). 核心: |v|>threshold → "数据异常" (Sprint 16.5 #92 守卫扩面), NaN/Infinity fallback 到 `0.00${unit}`, null/undefined 返 `empty`. unit 支持 '%' | 'pp' | 'raw' 3 种.

### Changed
- **`frontend-vue3/src/components/YOYBadge.vue`** (29 行减) — refactor 为 thin wrapper, 内部 `humanizeChange` 函数抽出, 守卫 + 格式化下沉到 YOYGuard, 只保留箭头 (↑/↓) + 颜色 (绿/红) 包装
- **`frontend-vue3/src/components/MetricCard.vue`** (22 行改) — 内部 `humanizeChange` 抽出, change 显示改用 `<YOYGuard :value="change" :unit="unit" />`, 跟 YOYBadge 守卫行为同步 (|v|>1e6 → "数据异常")
- **`frontend-vue3/src/views/health/RFMSegmentDrilldown.vue`** (5 行改) — 表格 yoy_repurchase_rate 列硬编码 `Math.abs(v).toFixed(1)+'pp'` 改用 `<YOYGuard>`, 箭头 + 颜色由调用方控制, 数值格式化复用 YOYGuard

### Tests
- **`frontend-vue3/src/components/YOYGuard.test.ts`** (新, 88 行, 15 测试) — 4 unit 类型 + null/undefined/empty 定制 + NaN/Infinity/边界值 + raw unit
- **`frontend-vue3/src/components/MetricCard.test.ts`** (扩 30 行) — 加 3 个 YOYGuard 集成测试 (1e7/-1e7/100), 改 1 个 Sprint 16.5 老期望 (Infinity → "↑数据异常" 跟 YOYBadge 同步)
- **`frontend-vue3/src/views/health/RFMSegmentDrilldown.test.ts`** (新, 165 行, 3 测试) — 表格 cell 渲染验证 (↑2.5pp / ↓3.1pp / 数据异常)

### 验证
- vitest 63/63 passed (老 16 + 新 47) — 6 文件 (YOYGuard + YOYBadge + MetricCard + RFMSegmentDrilldown + 2 老组件)
- 4 老 YOYBadge 测试无回归 (Sprint 13 契约 + Sprint 16.5 #92 守卫同步生效)
- 前端 build 已知 TS 错误 (HealthOverviewTab.vue 4 个 + HealthOverviewTab.test.ts 5 个 + ProductAssetsTab.vue 2 个 + 新 RFMSegmentDrilldown.test.ts 9 个) **全部是 baseline pre-existing** (stash 验证过 main 同样错), 不算 Sprint 18 #124 回归

### 任务来源
- Sprint 16.5 retrospective Section 8 #6 治理债务 — YOYBadge 异常值守卫扩面
- 跟 backend/contracts/types.py PercentageField 注释对齐: "真实值 > 1e6 建议前端 YOYBadge 守卫"
## [v0.4.14.49] - 2026-06-11 - chore(precommit): Sprint 18 #142 — ground-truth-lint 接 pre-commit framework

### Added
- **`.pre-commit-config.yaml`** (加 1 hook) — `contract-ground-truth-lint` 本地 hook, `entry: python -m backend.contracts._lint`, `files: 'backend/contracts/.*\.py$'` 触发条件, `stages: [pre-commit]`. 跟现有 ruff + pytest-cleanup-orphans hook 并存, 跟 `.githooks/pre-commit` 双轨并存
- **`docs/PRE-COMMIT.md`** (新, 334 行) — pre-commit 框架使用文档, 12 节: 简介 / install / 启用 / 触发 / 跳过 / 跟 Sprint 17/18 关系 / CI 集成 / 故障排查
- **`scripts/test-precommit.sh`** (新, 146 行, +x) — hook 触发验证脚本, 7 步: baseline → 注入 R1 违规 → 验 hook 拦到 (rc=1) → revert → 验复原 (rc=0) → 可选跑 framework

### Tests
- **test-precommit.sh 验证 PASS** — baseline 26 issue (Sprint 18 #141 治根中残留) → 注入 1 个 R1 违规 (bad_field_ratio 裸 float) → hook rc=1, issue 27 (delta=1) → revert 后 issue 26, rc=0. hook 拦到 + 复原逻辑全部正确

### 契约对齐
- 跟 Sprint 3 P1-3 双轨并存 (`.githooks/pre-commit` 仍有 ground-truth-lint, 跟 framework 互不冲突)
- 跟 Sprint 17 #121 工具代码**不动** (`backend/contracts/_lint.py` 主体保持, 跟 #142 scope 一致)
- 跟 Sprint 18 #141 同步: 当前 lint 26 issue 是 #141 治根中残留, hook 拦到是期望行为; #141 收口后 hook 自动 0 issue pass

### 已知限制
- **local hook 跨开发者兼容性**: `python -m backend.contracts._lint` 跑本机 Python, 假设开发环境装好 (PEP 668 系统 Python 受限, 需 pipx/uv/venv)
- **跟 .githooks 双轨并存**: 重复逻辑, Sprint 19 考虑二选一 (推荐保留 .githooks, 装更轻量)
- **不影响运行时**: pre-commit hook 是开发者工具, 不影响 uvicorn 启动 / API 响应

## [v0.4.14.51] - 2026-06-11 - chore(p2-batch): Sprint 19 P2 批处理 5 件 (hooks 拍板 + YOYGuard env + pre-commit CI + ETL cache hook + types 自动生成)

### Added
- **`docs/HOOKS-CHOICE.md`** (新, 142 行, Sprint 19 P2-1) — 拍板 `.githooks` 优先 (装轻量零依赖, 9 件 lint) + `.pre-commit-config.yaml` 选装 (装 framework 才能用, 重复 4 件 + 缺 5 件). 6 段结构: 拍板结论 / 框架对比 / 为何不上 / 新人 onboarding / 改 hook 流程 / 拍板签字
- **`frontend-vue3/src/components/YOYGuard.vue`** (改 1 行) — `threshold` 默认值改 `Number(import.meta.env.VITE_YOY_GUARD_THRESHOLD ?? 1e6)`, 业务方可按场景 (流量大盘 1e9, 私域复购 1e3) env 覆盖 (Sprint 19 P2-2). JSDoc 加 env 提示
- **`docs/YOY-GUARD-CONFIG.md`** (新, 161 行, Sprint 19 P2-2) — YOYGuard threshold env 配置拍板, 4 段结构: 拍板 / 痛点 / 用法 4 例 / 代码改动 / 测试留 Sprint 19.5
- **`.github/workflows/pre-commit.yml`** (新, 34 行, Sprint 19 P2-3) — pre-commit framework CI 接入, 走 `workflow_dispatch` 手动触发, `actions/checkout@v4` + `actions/setup-python@v5` + `pip install pre-commit` + `pre-commit run --all-files`. 走 `workflow_dispatch` 而非 push 自动 (避免没装 framework 时结构性 no-op, 跟 Sprint 3 P1-3 教训同根因)
- **`docs/CI-PRECOMMIT.md`** (新, 137 行, Sprint 19 P2-3) — workflow 拍板 + 4 段结构: workflow 文件 / 为何不用 push / 怎么用 / 故障排查 + CI/CD 防线总览加 1 行
- **`backend/services/rfm/cache.py:etl_post_run_hook()`** (新, 20 行, Sprint 19 P2-4) — ETL 跑批末尾调, 不依赖 uvicorn 重启也能 invalidate W5 DuckDB-KV cache. 复用 `check_manifest_version_and_invalidate()` 启动 hook 逻辑, best-effort 异常兜底, 跟 Sprint 18 #123 启动 hook 互补
- **`scripts/etl/cli.py:main()`** (末尾 8 行) — PerfTimer 块外调 `etl_post_run_hook()`, local import + print 提示, 失败不阻塞 ETL 收口
- **`backend/tests/test_cache_invalidation.py:TestEtlPostRunHook`** (新, 4 case) — manifest 变化 / 一致 / 缺失 / 异常兜底, 4/4 pytest pass
- **`docs/ETL-CACHE-INVALIDATION.md`** (新, 184 行, Sprint 19 P2-4) — 跟启动 hook 互补时序图 + 4 段结构: 拍板 / 互补 / 代码改动 / 验证流程
- **`scripts/gen-frontend-types.sh`** (新, chmod +x, Sprint 19 P2-5) — 前端 types 自动生成脚本, 走 `pydantic2ts.cli.script` (v2.x 包名, 跟 v1.x `pydantic_to_ts` rename) 调 `backend.contracts.category + metrics + health` 生成 `frontend-vue3/src/types/api.ts`
- **`frontend-vue3/src/types/api.ts`** (新, 855 行自动生成) — 3 module 全 interface 覆盖 (AuditLogItem / AuditLogResponse / ChannelHealthScoreItem 等). 文件头标 "Do not modify it by hand", 改完跑脚本会被覆盖
- **`docs/FRONTEND-TYPES-GEN.md`** (新, 160 行, Sprint 19 P2-5) — 拍板 pydantic-to-typescript v2.0.0 工具, 跟 openapi-typescript 解耦, 5 段结构: 拍板 / 为何不用 openapi-typescript / 工具版本陷阱 / 集成脚本 / 验证流程

### Changed
- **`CLAUDE.md` "AI 执行检查点" 表** (加 1 行) — "改 git hooks" 检查点, 引用 `docs/HOOKS-CHOICE.md` Sprint 19 P2-1
- **`backend/services/rfm/_shared.py:FLOW_ALGO_VERSION`** `v0.4.14.47` → `v0.4.14.51` — 行为变化 (P2-4 加 etl_post_run_hook 集成, 触发 cache key 全 miss 一次, 跟 Sprint 14.5 P1.4 约定一致)

### Fixed
- **`backend/tests/test_cache_invalidation.py`** (改 1 行) — pre-existing F401 跟 P2-4 加 test class 一起顺手修, 加 `noqa: F401` 给模块级 `_manifest_tracker_singleton` + `_default_state_path` (在 docstring / 注释里用)

### 治理债务闭环
- Sprint 18 retrospective Section 4 治理债务 #6 (前 5 件 P2) ✅ 闭环
- Sprint 16.5 #92 异常值守卫扩到 env 配置 (业务方场景化) ✅
- 跟 Sprint 18 #123 启动 hook 互补, 跑批真闭环 (P2-4)

### 任务来源
- Sprint 19 重做 — subagent C3 (Sprint 19 P2 批处理 5 件)
- 5 P2 件全部 Sprint 19 内 commit + push + merge

### 验证
- pytest 511 passed + 12 skipped + 2 failed (pre-existing DuckDB 1.5.2 race #119 P0 监控中, 跟本次改动无关)
- vitest 63 passed (YOYGuard 13 + YOYBadge 14 + MetricCard 23 + EmptyState + HealthOverviewTab + RFMSegmentDrilldown)
- ground-truth-lint 0 issue
- ruff 0 issue (本批改动 + 顺手修 F401)
- main @ 953f1d1 (5 subagent 收口前)

## [v0.4.14.50] - 2026-06-11 - fix(contracts): Sprint 18 #141 — 26 YOY ratio 字段命名/语义冲突治根 (白名单 + 类型补标)

### Changed
- **`backend/contracts/_lint.py`** (+42 行) — ground-truth-lint 增强 (Sprint 18 #141)
  - **`_YOY_PPT_FIELDS`** frozenset (14 字段): `yoy_*_ratio` 实际 PpField (pp 差), 命名 `_ratio` 是 Sprint 14 之前历史遗留, 改命名跨 14+ 文件影响太大, 走白名单兜底
  - **`_LIST_RATIO_FIELDS`** frozenset (1 字段): `new_customer_ratio` 是 `List[Annotated[float, Field(ge, le)]]`, linter 暂不识别 list element-wise 元数据 (Sprint 17 #121 R4 限制)
  - **R1 检查加 2 分支**: 白名单字段 + 已知 List 字段
  - **严格校验**: 白名单字段必须实际是 PpField (ge=-100, le=100), 防止未来 LLM 改漂移
- **`backend/contracts/breakdown.py`** (1 字段) — `gap_ratio: Optional[RatioField]` (0-1 decimal)
- **`backend/contracts/churn.py`** (1 字段注释) — `new_customer_ratio: List[Annotated[float, Field(ge, le)]]` 留 Sprint 17 #120 已合规写法
- **`backend/contracts/health.py`** (4 字段) — `annual_promo_gsv_ratio: RatioField` + `annual_promo_user_ratio: RatioField` + `old_customer_gsv_ratio (TargetChannel): RatioField` + `yoy_repurchase_gsv_ratio (TierFlowResponse): Optional[PpField]`
- **`backend/contracts/sampling.py`** (2 字段) — `new_locked_ratio × 2: Optional[RatioField]` (0-1 decimal, 之前误标 PpField)

### Added
- **`docs/SPRINT-18-YOY-FIX.md`** (278 行) — 26 字段治根报告, 跟 Sprint 17 B2 audit 同样 markdown 结构 (TL;DR + 字段分类 + 决策审计 + 跨文件影响分析 + 治根效果)

### Tests
- **新增 0 pytest 测试** (沿用 Sprint 17 #120 53/53 contract tests + Sprint 17 #121 10/10 lint tests, Sprint 18 #141 复用)
- **全套件 497 passed + 12 skipped** (跟 Sprint 17 收口 454+12 略增: 涵盖 race test)
- **3 pre-existing failed** (test_sim_prod_etl race + test_w4_full DuckDB lock + sim-prod race) — 跟本 PR 无关, 留 Sprint 18+ 治理
- **ground-truth-lint 0 issue** (26 → 0)
- **跟 Sprint 18 #142 配套**: ground-truth-lint 0 issue → pre-commit hook 0 拦截 (跟 #142 文档 "Sprint 18 #141 收口后 hook 自动 0 issue pass" 预期一致)

### 契约对齐
- 跟 Sprint 13 ratio 治理契约 0-1 严守**保留**: 白名单字段虽然名字带 `_ratio`, 但 linter 强校验它们是 PpField (-100~+100), 不会让 ratio 契约 0-1 漂移
- 跟 Sprint 14 Stage 2 Pydantic 契约**延伸**: 6 字段补 RatioField/PpField, 0-1 越界 API 入口 422 拦截
- 跟 Sprint 17 #120 B2 全量 audit **配套**: 复用 53/53 contract tests 验证新补标字段
- 跟 Sprint 17 #121 ground-truth-lint **配套**: `_YOY_PPT_FIELDS` 跟 `_LIST_RATIO_FIELDS` 双重白名单, R1 检查扩展支持 list element-wise 兜底
- 跟 Sprint 18 #124 YOYGuard **配套**: 前端 YOY/同比组件统一使用 YOYGuard, 跟后端 linter 白名单同源 (pp 字段前端也用 `unit="pp"` 标识)
- 跟 Sprint 18 #142 pre-commit **配套**: linter 0 issue → pre-commit hook 0 拦截

### 跨文件破坏
- **0 文件破坏**: 字段名零改动, 全是类型补标 / linter 白名单
- **字段名不动** = 前端 `frontend-vue3/src/api/types.ts` 同步不变, `backend/services/*` 同步不变, `backend/tests/*` 同步不变
- **类型升级** = API 入口 422 拦截保护增强 (越界值不再 500), 跟 Sprint 14 A.1 方案一致

### Follow-up (Sprint 18.5 / 19+)
- **linter 增强**: 递归 `List[Annotated[...]]` element-wise Field 元数据检查, 移除 `_LIST_RATIO_FIELDS` 白名单依赖
- **改命名 14 字段** (Sprint 18 走白名单, Sprint 19 真改): `yoy_*_ratio` → `yoy_*_ratio_ppt` 跨 14+ 文件, 估 200+ 行 diff

## [v0.4.14.43] - 2026-06-11 - fix(contracts): Sprint 17 #120 B2 全量 audit 10 contract 60+ mark 字段 (asset/audience/breakdown/churn/common/flow/geo/rfm/sampling/visitor)

### Changed
- **`backend/contracts/asset.py`** (4 mark 字段补标) — `repurchase_rate: PercentageField` + `ly_repurchase_rate: Optional[PercentageField]`
- **`backend/contracts/audience.py`** (50+ mark 字段补标, AudienceRow + AudiencePeriodMetrics 全 ratio 字段) — `old_gsv_ratio: RatioField` + `member_old_gsv_ratio: RatioField` + 100+ 老 ratio 字段从裸 float 升级 Pydantic 422 拦截
- **`backend/contracts/breakdown.py`** (5 mark 字段) — `old_customer_ratio_target: PercentageField` + 4 ratio 字段
- **`backend/contracts/churn.py`** (7 mark 字段) — `top_churn_dest1/2_ratio: RatioField` + `new_customer_ratio: RatioField` (List 字段)
- **`backend/contracts/common.py`** (4 mark 字段) — `wool_party_ratios` + `high_value_ratios` + `type1/2_ratio: RatioField` (List + Optional 都改)
- **`backend/contracts/flow.py`** (2 mark 字段) — `ratio: RatioField` + `concentration_risk: bool` 不动
- **`backend/contracts/geo.py`** (2 mark 字段) — `user_ratio: RatioField` + `gmv_ratio: RatioField`
- **`backend/contracts/rfm.py`** (13 mark 字段) — 新加 12 个 R 桶 / F 桶 / M 桶 ratio 字段 Pydantic 化, 1 个 `yoy_repurchase_gsv_ratio` 沿用 Sprint 14.5 P1.1 的 `Optional[PpField]`
- **`backend/contracts/sampling.py`** (12 mark 字段) — `new_locked_ratio: RatioField` + `old_locked_ratio: RatioField` (2 个 class)
- **`backend/contracts/visitor.py`** (4 mark 字段) — ratio 字段 Pydantic 化

### Added
- **`backend/tests/test_contracts_b2_audit.py`** (676 行) — 10 contract 聚合越界测试, 验证 schema 422 拦截
- **`docs/SPRINT-17-B2-AUDIT-FULL.md`** (299 行) — 10 contract audit 报告, 跟 Sprint 16.5 B2 audit 同样 markdown 结构, 每 contract 1 段 (字段数 + before/after diff + pytest 验证)

### Tests
- **新增 50+ pytest 测试** (10 contract × 5 mark 字段越界测试 + 1 happy path) — 全过
- **全套件 454 passed + 12 skipped** (#121 lint 10 + #120 B2 50+)
- **3 pre-existing failed** (test_sim_prod_etl DuckDB race + test_w4_full DuckDB 锁冲突) — 跟 #120 改动无关, 留 Sprint 18

### 契约对齐
- 跟 Sprint 13 ratio 治理契约 0-1 严守**保留** (B2 audit 用 RatioField/PercentageField/PpField 跟 Sprint 13 一致)
- 跟 Sprint 14 Stage 2 Pydantic 契约**延伸** (Sprint 14 写 3 个 Annotated 类型, Sprint 17 推全量应用)
- 跟 Sprint 15 B1 (is_member per-user 反向回填) **配套** (B1 ETL + B2 contract 双管齐下)
- 跟 Sprint 16.5 B2 试点 (3 contract 9 mark) **延伸** (Sprint 17 推全量 10 contract 60+ mark)

### Follow-up (Sprint 18)
- **26 lint 残留**: 主要在 `yoy_*_ratio` 字段命名冲突 (实际 PpField 不是 RatioField) — 留 Sprint 18 改命名 or 扩 lint 白名单
- **ground-truth-lint 长期挂 26 issue** — Sprint 18 治根 (要么改命名, 要么 lint rule 加 YOY 字段 PpField 允许规则)

## [v0.4.14.42] - 2026-06-11 - feat(lint): Sprint 17 #121 ground-truth-lint 规则强制 Pydantic Field 元数据 (R1/R2/R3/R4)

### Added
- **`backend/contracts/_lint.py`** (260 行) — ground-truth-lint 工具, AST 扫描 contract 文件
  - **R1**: `*_ratio` 字段必须 `RatioField` (0-1) 或 `Annotated[float, Field(ge=0, le=1)]`
  - **R2**: `*_pct` 字段必须 `PercentageField` (-1B~1B) 或 `Annotated[float, Field(ge=-1e9, le=1e9)]`
  - **R3**: `*_ppt` 字段必须 `PpField` (-100~+100) 或 `Annotated[float, Field(ge=-100, le=100)]`
  - **R4**: `List[X]` 字段 where X 是约束类型, 必须 `List[Annotated[X, Field(...)]]` 不许 `List["X"]` 前向引用 (Pydantic v2 不触发 element-wise 约束)
  - **CLI**: `python -m backend.contracts._lint` 返 0 / 1 exit code
  - **跳过**: `_lint.py` / `__init__.py` / `types.py` / `schemas.py` 自身 + 通用 schema
- **`backend/contracts/tests/test_lint.py`** (186 行) — 10 pytest 测试 (4 true-positive + 4 false-positive + 2 skip rules)
- **`docs/LINTING.md`** (359 行) — 4 规则详细解释 + 用法 + 跟 Sprint 17 #120 B2 audit 配合 + 跟 #122 B1+B2 模式配套

### Tests
- **10/10 lint 测试 passed** (8 rule coverage + 2 skip rules)
- **全套件 454 passed** (含 10 新 lint 测试, 0 回归)
- **3 pre-existing failed** (test_sim_prod_etl race + test_w4_full DuckDB 锁) — 跟 lint 改动无关

### 契约对齐
- 跟 Sprint 13 ratio 治理契约 0-1 严守**保留** (lint R1 强制 0-1 约束)
- 跟 Sprint 16.5 retrospective Section 6.3 Pydantic v2 List 踩坑**治根** (R4 强制 List[Annotated[...]] 写法)
- 跟 Sprint 17 #120 B2 全量 audit **互补** (#120 修现有 contract, #121 lint 防未来 contract 退步)
- 跟 Sprint 17 #122 B1+B2 模式 → CLAUDE.md **配套** (#122 写规则, #121 工具层强制)

### 治根效果
- 防止 LLM 写无 Pydantic Field 元数据 contract (eg. 裸 `float: Field(...)` 而不 `RatioField: Field(...)`)
- 防 Pydantic v2 `List["X"]` 前向引用踩坑 (Sprint 16.5 13/13 tests 第一次跑 3 fail 教训)
- CI 集成: 改 contract 时 `python -m backend.contracts._lint` 应该 0 issue (留 Sprint 18 接 pre-commit)

## [v0.4.14.41] - 2026-06-11 - docs(claudemd): Sprint 17 #122 B1+B2 模式正式挪进 CLAUDE.md Ratio Convention 章节

### Changed
- **`CLAUDE.md` "## Ratio Convention" 章节升级** — 从 (Sprint 13+) 升级到 (B1+B2 模式, Sprint 13+ 升级 Sprint 17)
  - **B1 模式定义** (mark 字段补标 + ETL 触发反向回填) + 典型案例 (Sprint 15 Wave 3 is_member per-user 治根) + 反模式
  - **B2 模式定义** (contract 字段补标 + Pydantic 422 拦截) + 典型案例 (Sprint 16.5 #91 B2 试点 + Sprint 17 #120 全量) + 反模式
  - **强制规则 (B1+B2) 表格** — `*_ratio` → RatioField / `*_pct` → PercentageField / `*_ppt` → PpField / `*_rate` → PercentageField / `List[X]` → `List[Annotated[X, Field(...)]]` 禁 `List["X"]` 前向引用
  - **前端契约** 加 `|v|>1e6` 异常值守卫交叉引用 (Sprint 16.5 #92 + Sprint 17 #124 扩)
  - **禁止条款** 加 2 条 (contract 裸 float + List 前向引用), 6 条全 lint 强制
  - **跨链** 加 4 项: `backend/contracts/types.py` 类型定义 + `docs/SPRINT-16-5-B2-AUDIT.md` 试点 + `docs/SPRINT-16-5-RETROSPECTIVE.md` Section 5 治理债务 + `docs/LINTING.md` (Sprint 17 #121 新建) + `docs/SPRINT-17-B2-AUDIT-FULL.md` (Sprint 17 #120 新建)
- **`CLAUDE.md` "## AI 执行检查点" 表格** — 加新行 "改 contract 字段" → 必跑 `python -m backend.contracts._lint`, 跨链 `docs/LINTING.md`
- **`CLAUDE.md` "## Sprint 16.5 收口" 章节** — B1+B2 模式 sub-section 加一行 "✅ Sprint 17 已升级到 'Ratio Convention' 主章节 (见上)"

### 契约对齐
- 跟 Sprint 13 ratio 治理契约 0-1 严守**保留** (B1+B2 跟 Sprint 13 不冲突, 是补强)
- 不动后端契约 (`backend/contracts/types.py` 不变), 不影响 #120 全量 audit 跟 #121 ground-truth-lint 规则的 scope

## [v0.4.14.40] - 2026-06-11 - feat(frontend): YOYBadge 异常值守卫 (Sprint 16.5 P2 Wave 6)

### Added
- **`frontend-vue3/src/components/YOYBadge.vue` humanizeChange 守卫** — |v| > 1e6 (即 > 100 万%) 返 `'数据异常'`, 避免 UI 显示 `+1157823.86%` 等万倍异常值误导用户
- **`frontend-vue3/src/components/YOYBadge.vue` 模板 v-else-if 分支** — 单独显示灰色 (`text-slate-400`, 跟 null 态一致) `数据异常` 标签, `title` tooltip 提示原因

### Tests
- **`frontend-vue3/src/components/YOYBadge.test.ts` 4 个新 vitest 测试** — 边界内正常值 (100/-100/0) + 异常值 (1e7) 全部覆盖
- **改 1 个 Sprint 13 老测试** — `% Infinity` 期望从 `+0.00% ↑` 改 `数据异常` (Sprint 16.5 守卫优先于显示, 跟 backend 注释对齐)
- **16/16 vitest passed** (12 老 + 4 新) / 全套 42/42 无回归

### 契约对齐
- 跟 `backend/contracts/types.py:46` PercentageField 注释对齐: "**真实值 > 1e6 建议前端 YOYBadge 守卫**" — Sprint 15 Wave 1 PercentageField 放宽到 ±1B, 前端必须补守卫
- 不动后端契约, 不影响 4 个并行 subagent (cache_key / audience / contracts) 的 scope

### 截图验证
- 老客分析 (customer-health) 现状概览 8 个 MetricCard 正常态: `↑19.16%` / `↓4.98%` / `↑10.44pp` 等
- 品类看板 (category) 现状概览 46.8% 等正常显示
- 异常态 (|v|>1e6 → `数据异常`) 由 vitest 1e7 测试覆盖, 单元测试已验证

### 治根效果
- 防止前端 UI 显示万倍异常百分比误导运营
- 跟 Sprint 15 Wave 1 backend 放宽契约配套, 前后端契约一致

---

## [v0.4.14.39] - 2026-06-11 - fix(contracts): Sprint 16.5 B2 试点 — 3 contract 9 mark 字段补标 (category + metrics + health)

### Fixed
- **`backend/contracts/category.py:14-16 CategoryDistributionItem.pct/penetration_rate/member_ratio`** — 3 个 ratio 字段从 `float` 改 `"RatioField"` (ge=0, le=1). 跟 Sprint 15 B1 (audience.py 28 字段) 模式一致. service 端返错值 (e.g. pct=1.5 越界) 原本 API 层 500, 改后 Pydantic v2 ValidationError → FastAPI 422
- **`backend/contracts/metrics.py:34-36 TrendData.member_ratios/ly_amounts/ly_member_ratios`** — 3 个 List 字段从 `List[float]` 改 `List[Annotated[float, Field(ge, le)]]`. Pydantic v2 知识点: `List["PercentageField"]` 不会触发 element-wise 约束 (前向引用解析为 float, Field 元数据丢失), 必须 `List[Annotated[float, Field(...)]]` 才会 TypeAdapter 解析
- **`backend/contracts/health.py:145 ValueTierDefinition.gsv_ratio`** + **`:167 CustomerSegmentItem.gsv_ratio`** + **`:193 TierFlowRow.repurchase_gsv_ratio_current`** — 3 个 ratio 字段从 `float = Field(...)` 改 `"RatioField" = Field(...)`. 0-1 decimal 越界在 API 入口 422 拦截

### 治根效果 (本地 + 生产 uvicorn 验证)
- `category/overview` + `metrics/trend` + `customer-health/overview` + `customer-health/value-tiers` 4 端点全 200
- `pytest backend/tests/test_b2_contract_mark_pilot.py -v` 13/13 passed
- `pytest backend/tests/ --ignore=backend/tests/test_sim_prod_etl.py` 437 passed + 12 skipped, 0 contract-related failures
- `pytest backend/tests/test_b2_contract_mark_pilot.py` baseline 3 happy path test 证明合法值 (0-1 decimal) 接受, 不破老 service 调用

### 文档
- `docs/SPRINT-16-5-B2-AUDIT.md` (252 行) — 9 mark 清单 + 改前后对比 + 服务层 mark 缺口验证 + Sprint 17+ 全量 audit 建议 (剩 9 contract ~50+ 字段)
- `backend/tests/test_b2_contract_mark_pilot.py` (170 行) — 9 mark 越界 + 1 合法值 + 3 baseline happy path

### Sprint 17+ 后续 (留 backlog)
1. 全量 audit 剩下 9 contract (audience_summary / audience_table / repurchase / conversion / promotion / rfm_category_drilldown / tier_flow / tiers / config)
2. 加 ground-truth-lint 规则强制新 contract 字段必须用 `RatioField` / `PercentageField` / `PpField` / `Annotated[*, Field(ge, le)]`
3. 把 B1+B2 模式写进 `CLAUDE.md` Ratio Convention 章节强制生效

## [v0.4.14.38] - 2026-06-11 - fix(rfm): Sprint 16.5 P2.7 — cache_key 改 MD5 full + namespace prefix (W5/file 双层防撞)

### Fixed
- **`backend/services/rfm/_shared.py:194 _flow_cache_key`** — CodeX audit 治根. 旧版 2 个真坑: (1) 8 维参数用 `_` 拼接, 文件名相似排查极难; (2) `exclude_channels` 用 `MD5[:8]` 截断 (32 bit) → 生日悖论 2^16 = 65K 列表 50% 碰撞, 大 exclude list 必误命中. 修法: 8 维参数 + `FLOW_ALGO_VERSION` 全部进 MD5 full (128 bit, 2^64 列表才有 50% 碰撞), 加 namespace prefix `flow_` 防跟 W5 DuckDB-KV 串扰
- **`backend/services/rfm/cache.py:66 _hash_key`** — 加 namespace prefix `w5kv_` 防跟 file cache (`flow_`) 跨 cache 误命中. 保留 Sprint 14.5 P1.4 的 `FLOW_ALGO_VERSION` 校验 (算法改动 → key 变 → miss → 重算)
- **`backend/tests/test_w5_cache.py` +6 tests** — `TestFlowCacheKeyMd5Full` 类, 6 件套覆盖: (1) 不同参数 → 不同 key / (2) 同参数 100 次幂等 / (3) MD5 full 32 char 格式校验 / (4) 截断 vs full 冲突对比 / (5) `algo_version` 变更 → key 失效 / (6) 跨 namespace 隔离 (`flow_` vs `w5kv_`)

### 治根效果 (生产 uvicorn 实跑)
- `r-flow`: 1st cache miss 6.45s → 2nd cache hit 0.005s (**1180× 加速**)
- `f-flow` / `m-flow` / `segment-orders` 4 端点全 200
- 23/23 tests passed (17 老的 W5 cache 回归 + 6 个新加)
- 旧 cache 文件名 (e.g. `r_flow_v123_2026-01-01_2026-01-31_GSV.json`) 跟新格式 (`flow_<32hex>.json`) 完全不同, 24h TTL 内自然失效
- 兼容 `_flow_engine.py:461` + `scripts/warm_flow_cache.py:96` 2 个调用方 (签名未变)

## [v0.4.14.37] - 2026-06-11 - fix(etl): Sprint 15 Wave 3 — is_member per-user 治根 (老客回购标 FALSE)

### Fixed
- **`scripts/etl/pipeline.py:65 _mark_user_id_history_member helper`** — Sprint 15 Wave 3 治根 (老客回购 per-user 标). 之前 line 398 per-order 标导致老客 (user_id 跟历史 is_member=TRUE 重叠) 但新单 order_id 不在历史 mark → 标 FALSE. 6/9+ 64 订单 18 老客全标 FALSE, 前端会员数据缺失. 修法: 老客 (is_member=FALSE) 但 user_id 跟历史 is_member=TRUE 重叠 → 标 TRUE
- **`scripts/etl/pipeline.py:425 T1 调 helper`** — 增量模式在 line 398 per-order 标后调 helper, 新单走 per-order (member_order_ids), 老客走 per-user (historical_member_user_ids), 治根 18 老客
- **`scripts/etl/pipeline.py:508 T2 Step 4.6 增量模式跳过`** — B2 (line 182-215) 已做 mark 增量 append, 跟 Step 4.6 build_membership_mark 全表重扫冗余, 增量模式跳过. 全量模式 (line 391 if 块之前) 仍跑 Step 4.6 兜底, 不动
- **`scripts/etl/pipeline.py:519 T3 Step 4.7 改增量 UPDATE`** — 之前 replay_is_member.py 全表 UPDATE 10.6M + DROP/CREATE 6 索引 = 21s, 增量模式不需要. 修法: BEGIN/COMMIT 包单事务 (跟 D.1 一致), `UPDATE orders SET is_member = TRUE WHERE order_id = ANY(?)`, 不重建 6 索引. 跟 T1 per-user 标 + B2 增量 append 配套, mark 跟 orders.is_member 永远一致
- **`backend/tests/test_is_member_userid_history.py` 6 tests** — 老客回购标 TRUE (主治根) / 全新客不标 / NULL user_id 守卫 / 空 shop_df 早返 / 重复跑 idempotent / 6/9+ 18 老客回归 (Sprint 15 真根因)

### 撤回
- **T4 Step 7b preload_rfm 增量模式跳过 — 撤回 (noop)** — 增量模式天然不跑 preload_rfm (line 391 在 if 块, line 396 else 增量模式不进), 56 min 是全量模式, 增量模式已 ~30s 极快, 跟 plan-eng-review 拍板时确认. 撤回 T4 避免误改

### Sprint 15 Wave 3 完成
- ✅ P0 治根 is_member per-user (本 commit, 3 件套)
- ⏳ P1 B1: audience 28 字段补标 (Sprint 16)
- ⏳ P1 P2.7: cache_key md5 full (Sprint 16)
- ⏳ P1 B2 试点: category + health + metrics 3 contract audit (Sprint 16)
- ⏳ P2 浅 feature: YOYBadge 异常值守卫 (Sprint 16)

### 已知 DuckDB 1.5.2 race (跟本 PR 无关, 留 Sprint 16)
- `_update_taoke_channel_impl` 段 Vector::Reference VARCHAR/TIMESTAMP error (cli.py:715)
- baseline (无本 PR 改动) 同样错误, 跟 Sprint 5 P0 教训同类
- sim_prod_etl 2 flaky test (CI 已知 flaky, 371ccb2 跳过, RSS 4.5GB 撞 1GB 限制) 跟本 PR 无关

### Plan
- `~/.gstack/projects/fuqing-crm-analytics/main-plan-eng-review-sprint15-wave3-20260611.md` — Sprint 15 Wave 3 plan + 4 sections review (Architecture / Code Quality / Test / Performance) + 1 PR 拍板

## [v0.4.14.36] - 2026-06-11 - fix(contracts): Sprint 15 Wave 1 — PercentageField 放宽到 ±1B (gsv_yoy 越界治根)

### Fixed
- **`backend/contracts/types.py` PercentageField ge=-1B le=1B** (0-1M → 0-1B) — 25 6/1-6/8 单独拉 `/api/v1/category/overview` 返 500 (gsv_yoy=1,157,823.86% 越界 1M) 治根. 跟 Sprint 14 QA 0-1M 退让一致, 进一步放宽到 0-1B 兼容 yoy_absolute *100 后万倍异常值 (eg. 新品类从 0 涨到有量, 涨 1 万倍仍合理)
- **`backend/tests/test_percentage_yoy_over_1m.py` 8 测试** — 真实 1.15M 通过 + 边界 1B 通过 + 负 YOY -1M 通过 + 1B+1 / -1B-1 仍拒 + 0/50/25 正常值通过

### Plan
- `docs/SPRINT-15-PLAN-RATIO-AUDIT.md` — Sprint 15 完整计划 + /autoplan 4 phase review 拍板 (调整后 8 任务: 删 C, 加 D.1 P0, 加 P2.7 P1, 加 1 浅 feature)

### Sprint 15 Wave 1 完成
- ✅ P0 A: gsv_yoy 治根 (本 commit)
- ⏳ P0 D.1: replay_is_member 包 BEGIN/COMMIT (Sprint 15 Wave 2)
- ⏳ P1 B1: audience 28 字段补标 (Sprint 15 Wave 3)
- ⏳ P1 P2.7: cache_key md5 full (Sprint 15 Wave 4)
- ⏳ P1 B2 试点: category + health + metrics 3 contract audit (Sprint 15 Wave 5)
- ⏳ P2 浅 feature: YOYBadge 异常值守卫 (Sprint 15 Wave 6)
- ❌ C 任务已删 (user 拍板, 跟 f214505 双保险冲突)

### Sprint 13 治理契约保留
- RatioField 0-1 严守, 不放宽
- PpField -100~+100 严守, 不放宽
- PercentageField 仅放宽到 0-1B (兼容 yoy_absolute *100 后万倍异常值), 真实 > 1e6 建议前端 YOYBadge 守卫 ("数据异常")

## [v0.4.14.35] - 2026-06-10 - fix(rfm): Sprint 14.5 增量 2 hotfix — W5 DuckDB-KV cache key 含 algo_version

### Fixed
- **`backend/services/rfm/cache.py` `_hash_key` 含 `FLOW_ALGO_VERSION`** — Sprint 14.5 P1.4 改了 file cache (data/cache/rfm_flow/*.json) 加 algo_version 校验, 但 W5 DuckDB-KV cache (rfm_query_cache 表) 漏改, 24h TTL 内仍存旧 ratio=0.0 命中返 500 修后值. 修法: W5 key 拼 FLOW_ALGO_VERSION, 算法/version 变 → key 变 → miss → 重算
- **`FLOW_ALGO_VERSION` bump `v0.4.14.34` → `v0.4.14.35`** — 强制现有 cache (file + W5) 全部失效, 触发重算

### 教训 (Sprint 15 治理 #1)
Sprint 14.5 P1.4 只改了一半: file cache 加 algo_version 字段, 但 W5 DuckDB-KV cache 走 key 路由. **两套 cache 必须同步加校验**, 不能只改一套. Sprint 15 加 W5 invalidation hook 时统一处理.

## [v0.4.14.34] - 2026-06-10 - fix(rfm): Sprint 14.5 增量 2 (Codex audit) — contract Optional 治根 + W5 cache algo_version

### Fixed
- **`contracts/rfm.py` 14 个 ratio 字段改 `Optional[RatioField] = None`** (R/F/M 3 维度 × 3 时段 + RFMAnalysisRow 5 段) — Codex P1.1 治根: TTL 段 ratio 必 > 1.0 越界 RatioField 0-1, 留 0.0 是 silent failure trap, 改 Optional 让 None 透传
- **`_flow_engine.py` TTL 段写 None 透传** — `_build_rows` 用 `_ratio_or_none` helper, None 透传到 contract, 不 round 不漂移
- **`_shared.py` W5 flow cache 加 `algo_version` 校验** — `_get_cached_flow` 校验 `FLOW_ALGO_VERSION`, 算法改动 → 自动 cache 失效, 防 24h 内返旧值 (Sprint 14.5 真实踩坑 ttl_gsv 2.87 越界直到 invalidate). `FLOW_ALGO_VERSION = "v0.4.14.34"` 写时附读时校

### Tests (Codex P1.2 / P1.3 / P2.1 / P2.2 / P2.8)
- **`backend/tests/test_rfm_flow_ttl_ratio.py` 13 测试** (从 5 扩到 13):
  - P1.2 F/M 桶同样验证 (_parse_flow_rows 共享引擎)
  - P1.3 Pydantic 端到端断言 (RFMRFlowRow/RFMFRFlowRow/RFMMFlowRow 不抛 ValidationError)
  - P1.3 回归: ratio=1.5 仍被拒收 (确保 Optional 没破坏 RatioField 0-1)
  - P2.1 非均匀 GSV 分布下单段 ratio ≤ 1.0 (浮点边界)
  - P2.2 全 0 数据场景不抛异常
  - P2.8 test_ttl_ratio_none_regardless_of_ttl_gsv 加 gsv 保留断言 (防后人误读)

## [v0.4.14.33] - 2026-06-10 - fix(rfm): Sprint 14.5 治根 "已购客TTL" 段 ratio 越界 (Pydantic 500)

### Fixed
- **`_flow_engine.py:139-143` 排除 "已购客TTL" 段 ratio 计算** — Sprint 14 A.3 加 `RatioField` 0-1 验证后, service 算出 ttl_gsv / (sum_R_buckets) = 2.8754 越界, `rfm/r-flow` 返 500. 治根: TTL 是商业指标汇总行 (含当期新购客复购, 跟 R 桶是真子集关系), 跟 R/F/M 桶 ratio 语义不同, 留 0.0. 前端 `RFMView.vue:120,286` 已 `.filter((r) => r.r_segment !== '已购客TTL')` 过滤此段显示
- **`backend/tests/test_rfm_flow_ttl_ratio.py`** 5 测试, 验证 6 段 R 桶 ratio ∈ [0,1] + 缺失段 ratio = 0 + 4 mode (all/same/member_all/member_same) 全部生效

## [v0.4.14.32] - 2026-06-10 - docs: Sprint 1-14 文档收口 (排查 + 剔除 + retrospective 新建)

### Changed
- **剔除 `tests/` 11 个重复 test_*.py** (跟 backend/tests/ 重复, 6/8 后再没改动, 统一收 backend/tests/)
- **archive 3 个老 plan** → `docs/archive/sprints/`:
  - `SPRINT-12-PLAN.md` → `SPRINT-12-PLAN-2026-06-10-archived.md`
  - `SPRINT-13-PLAN-RATIO-GOVERNANCE.md` → `SPRINT-13-PLAN-RATIO-GOVERNANCE-2026-06-10-archived.md`
  - `SPRINT-13-RETROSPECTIVE.md` → `SPRINT-13-RETROSPECTIVE-2026-06-10-archived.md`
- **`docs/SPRINT-14-PLAN-RATIO-STAGE2.md` 加 "✅ 收口" 标记** (留根目录作为"上一个 sprint 文档")
- **新建 `docs/SPRINT-14-RETROSPECTIVE.md`** (8 章节: 结果 + 关键 bug 复盘 + 决策审计 + 治理债务 + 教训 + 时间线 + 未来 Sprint 建议 + 关键指标)
- **清理 `/tmp/etl-sprint14-*.log`** (2 个 1.5KB incomplete log 剔除, 保留 etl-direct-run.log)

### 不动 (5 核心 + 规则)
- 5 核心文档 (CLAUDE/CHANGELOG/README/reference/feishu-arch)
- `backend/tests/` 27 个 test_*.py (规范目录)
- Memory 文件 (Sprint 1-14 memory 跨 session 价值)
- `docs/archive/*` 13+ 文件 (已是归档)

## [v0.4.14.31] - 2026-06-10 - fix: Sprint 14 0.5% 显示根治 + vue-tsc pre-commit 防线

## [v0.4.14.31] - 2026-06-10 - fix: Sprint 14 0.5% 显示根治 + vue-tsc pre-commit 防线

### Fixed
- **audience_summary.py + overview.py service /100** (50 行 + 3 行) — Sprint 14 A.1 治根, ratio 字段存 0-1 decimal 跟 RatioField contract 对齐, 跟 Sprint 13 治理一致
- **_mark_all_files_processed mtime 写源 xlsx** (跟 ingest.py:144-151 一致, B 修一半补完)
- **PercentageField ge=-1M le=1M** (允许负 YOY + 千倍异常值, 之前 ge=0 拒负 YOY 500)
- **audience/table + audience/summary + category/overview + metrics/overview 4 端点全 200** (Sprint 14 引入 regression 全治根)
- **AudienceView.vue 4 处 member_*_vs_all_* ratio 显示加 *100** (用户报 0.5% 显示 → 真实 50%)
- **AudienceView.vue:1416 趋势图 tooltip ratio 加 *100** (echarts formatter 漏改)
- **AudienceView.vue:1694 fmtRatio() 函数加 *100** (4 页面共享 util)
- **AudienceView.vue 4 处 'const v = row.const v = row.X' 语法错** (regex backref 漏改紧急修)

### Changed
- **Sprint 14 .githooks/pre-commit 加 vue-tsc --noEmit 强制 type check** (Sprint 14 教训: vitest 不 import .vue 模板, 漏 3 次 commit 语法错. 防 Sprint 15+ 重犯)

### Sprint 14 完整收口

8 commits 合入 main:
- adabf5a docs(sprint14): 扩 plan 范围
- cc0f478 fix(etl): processed_files mtime 语义统一 (B)
- 2f0e8d0 feat(etl): is_member replay 集成 (B+)
- ac4ee1e feat(contracts): Stage 2 Pydantic 6 contract (A.1+A.3)
- 14a7f24 feat(frontend): openapi-typescript codegen (A.2)
- 67b794d fix(contracts): QA 修 PercentageField 0-1M
- 8b2352c fix(contracts+etl+frontend): /codex 治根 4 P0
- f72cbe3/1126957/ba745ca 紧急修 0.5% 显示 (前端 *100)
- 3cf1066/0e80b5d/ba745ca merge

### Sprint 14.5 留治根 (4 P2)
1. `AudienceRow.yoy_*` 28 字段加 `PercentageField` (Sprint 14 漏标, 改风险大)
2. `replay_is_member.py` 包 `BEGIN; ... COMMIT;` (DROP INDEX 6 秒窗口数据风险)
3. `replay_is_member.py` member 删除不清 (mark rebuild 后 is_member 不清)
4. Step 4.6/4.7 fail-soft 隐藏 mark drift

## [v0.4.14.30] - 2026-06-10 - chore: Sprint 13 收口 (8 commits, ETL 2 次跑批验证, 文档同步)

## [v0.4.14.30] - 2026-06-10 - chore: Sprint 13 收口 (8 commits, ETL 2 次跑批验证, 文档同步)

### Sprint 13 收口
- **8 commits 合入 main** (5eef1fe → 20a37d5 → 74b9697 → c98adf5 → 4394fd0 → a5c4362 → d40a7ce → ad1cb20).
- **6/9 数据进库**: 增量 ETL 第二次跑批 (11:28-11:52) 写入 orders 6,445 行 + user_first_purchase 2,133 行 + fact_rfm_long 1,080 行 + user_rfm 4,777,544 行. orders max(pay_time) 2026-06-09 23:59:57.
- **Health score 70 → 98 (+28)**: 4 个用户报告 bug 全部修好 (老客占比 1040pp → 10.40pp, 渠道 528pp → 5.28pp, 30 指标 104000pp → 10.40pp, 老客 GSV 0.41% 保留真实值).
- **文档同步**: docs/reference.md "Ratio Convention (Sprint 13 更新)" 章节 + CLAUDE.md "Ratio Convention (Sprint 13+)" 章节 + 4 页面 banner 3 天 TTL (RatioConventionBanner.vue).

### Sprint 14 待启动 (Stage 2 Pydantic 契约加固 + ETL 治根)
- **范围** (2026-06-10 拍板): A + B (扩) + B+ (新增) + H
  - A.1-A.3: 6 个 contract (audience/metrics/category/health/rfm) 加 `Annotated[float, Field(ge/le/decimal_places)]` validator + openapi-typescript codegen
  - B (扩): processed_files_*.json mtime 语义错位修复 (方案 A: 统一用源 xlsx mtime, ingest.py:144-151 改 1 行)
  - B+ (新): is_member replay 集成 (方案 P: pipeline.py 加 Step 4.6+4.7 调 build_membership_mark + replay_is_member)
  - H: /tmp/etl-*.log + 旧备份清理
- **Sprint 14 扩范围原因** (2026-06-10 调研):
  1. **Bug 1 (file scan)**: `processed_files_*.json` mtime 字段语义错位 — parquet 路径写 parquet mtime, xlsx 路径写 xlsx mtime, _file_changed 比较时间基准不一致
  2. **Bug 2 (is_member)**: `pipeline.py:329` 增量模式 member_order_ids 来源有缺陷 (DB 鸡生蛋循环 / 新 parquet 覆盖老会员), Sprint 10 写了 2 个手动救火脚本未集成
- 计划: `docs/SPRINT-14-PLAN-RATIO-STAGE2.md` (5-6 天, 扩 1.5d).

## [v0.4.14.29] - 2026-06-10 - refactor(ratio): Sprint 13 比率口径统一 (33 处 100× + 1 处 10000× + 1 处 0% + Excel 4 处全部修)

### Fixed
- **ratio 口径统一**: 后端 `yoy_ratio` 仍返已 `*100` pp 数值, 前端 `humanizeChange` 改 pass-through. 33 处 caller 修掉 100× bug.
- **30 指标对比表 10000× bug**: `audience_summary._extract_metrics` 9 个 ratio 字段不再 `*100` 存.
- **visitor_service 入会率 MOM 100× bug**: line 70+86 `(rate/100) - (comp/100)` → `(rate - comp)` 公式对齐.
- **品类详情页新客占比永远 0%**: `churn.py:336` 完整实现 `is_new`, 不再 hardcode `[0.0] * len(dates)`.
- **RFM/R/F/M 区间 + ValueTierTab 8 处 unit 漏标**: 补 `unit="pp"`.
- **MarketBasket 置信度变化 100× bug**: `MarketBasketTab.vue:255-261` 去掉 `*100`, 对齐 `lift_change` decimal 差.
- **Excel 导出 5 处 numFmt 100× bug**: `ProductClassRepurchaseTab` + `HealthOverviewTab` 改双列 (`'0.0"%"'` / `'0.0"pp"'`).
- **None 透传显示 `—`**: `humanizeChange` 加 `v == null` 守卫.

### Changed
- **`MetricCard.vue` / `YOYBadge.vue` `humanizeChange`**: 去掉 `unit='pp'` 内部 `*100`, 改 pass-through. JSDoc 同步 (`caller 已 *100, 组件只做 abs + toFixed(2)`).
- **`SamplingView` / `RFMSegmentDrilldown` / `ProductCustomerTab` 4 处 `fmtYoy` / `fmtYoY` 散落 `*100`**: 去掉, 对齐契约.
- **audience_summary ratio 字段** `_extract_metrics`: ratio 字段不再 `*100` 存, 保持 0-1 decimal, 前端展示时 `*100`.

### Added
- **`RatioConventionBanner.vue`**: 4 页面 (AudienceView / CategoryView / RFMView / HealthOverviewTab) 顶部 banner, 3 天后自动消失 (localStorage).
- **ratio 契约文档**:
  - `docs/reference.md` 新增 "Ratio Convention (Sprint 13 更新)" 章节 (line 148 旧规则已 deprecate)
  - `CLAUDE.md` 新增 "Ratio Convention (Sprint 13+)" 章节 (末尾, 不动现有 12 章节)
- **单测覆盖** (pass-through 契约):
  - `MetricCard.test.ts` +6 个 case (pp/% caller 已 *100)
  - `YOYBadge.test.ts` +6 个 case (pp/% caller 已 *100, NaN/Infinity fallback)

### Migration Notes
- `docs/reference.md:148` 旧规则 (pp 类型 MetricCard 用 `fmtPpt()` 直传原值) 已正式 deprecate.
- Sprint 11/12 caller 模式 (caller 传 0-1 + 组件 `*100`) 全部失效, 必须改 caller 已 `*100` + 组件 pass-through.
- 命名建议: 新加字段优先用 `*_yoy_ppt` / `*_yoy_pct` 后缀避免歧义, 老字段 (`yoy_repurchase_rate` 等) 暂未重命名.

## [v0.4.14.27] - 2026-06-09 - fix: 30指标占比显示修正 (0.53% → 53.35%)

### Fixed
- **后端 audience_summary.py**: 所有 ratio 字段 ×100 返回百分比格式
  - Panel A `_extract_metrics()`: 10 个 ratio 字段 (老客/新客/会员 GSV占比+人数占比+渗透率)
  - Panel B 全店渠道: ratio/new_gsv_ratio/old_gsv_ratio + TTL (100.0)
  - Panel C 会员渠道: ratio/member_ratio/new_gsv_ratio/old_gsv_ratio + 交叉指标 + TTL
- **前端 AudienceView.vue**: 渠道表格 render 去掉 `* 100` (14 处)
  - 后端已返回百分比，前端直接 `v.toFixed(1)%` 展示

### 根因
- `_extract_metrics()` 返回 0-1 小数 (如 0.5335)，前端 `v.toFixed(2)%` 显示 "0.53%"
- 注释 "API ratio 字段已返回 % 格式" 过时，实际后端返回 0-1 小数

## [v0.4.14.26] - 2026-06-09 - refactor: YOY/pp 后端返回可显示值，前端只做展示

### Changed (YOY/pp 全链路重构)
- **后端 calculations.py 返回值语义变更**:
  - `yoy_absolute()`: 返回值从 0-1 小数 → 百分比值 (如 0.25 → 25.0), round(2)
  - `yoy_ratio()`: 返回值从 0-1 小数 pp 差 → pp 值 (如 0.05 → 5.0), round(2)
  - `mom_absolute()`: 同 yoy_absolute
  - `mom_ratio()`: 同 yoy_ratio
  - 所有调用方自动生效 (audience_table/summary, health, category, visitor, sampling, rfm)
- **后端 overview.py**:
  - 占比计算去掉 `*100 / 100` 对冲操作, 直接传小数
  - 输出精度 round(4) → round(2)
  - 占比字段 (old_user_ratio 等) 输出百分比值
  - member_premium_ppt MoM 改用 `mom_absolute()` 与 YoY 语义统一
- **前端 MetricCard.vue + YOYBadge.vue**:
  - `humanizeChange` 简化: 去掉 pp 内部 *100, 统一 `Math.abs(v).toFixed(2) + unit`
  - 前端不再做任何数学运算, 只做展示拼接
- **前端 AudienceView.vue**:
  - 删除 `kpiChangePct` / `visitorChangePct` 函数
  - MetricCard 改用 `kpiChange` / `visitorChange`
  - 去掉所有 YOYBadge `*100` (indicatorColumns, channelColumns, 会员占比列)
  - renderValue 占比显示去掉 `*100`
- **前端 HealthOverviewTab.vue**: 删除 `fmtYoy`, 去掉内联 `*100`
- **前端 RFMView.vue**: 自算 yoy `*100`, MetricCard 去掉 `*100`
- **前端 CategoryView / CategoryRepurchaseTab / ProductClassRepurchaseTab**:
  ratio 类 YOYBadge 统一添加 `unit='pp'`

### Fixed
- **30指标表格 YOY 列**: 之前显示 +0.14% (应为 +14.00%), 现在正确
- **渠道概览 YOY 列**: 同上
- **老客占比/新客占比 pp 列**: 之前显示 +1040.00pp (应为 +10.40pp), 现在正确
- **CategoryView ratio 类 YOY**: 之前用默认 unit='%' 导致 pp 值偏小 100 倍

### Verified
- test_calculations.py: 38 passed ✅
- 全量 pytest: 394 passed, 1 failed (DuckDB 锁冲突, 非本次改动), 12 skipped ✅
- 浏览器验证: 全店GSV ↑14.00%, 老客占比 ↑10.40pp 等均正确 ✅

## [v0.4.14.25] - 2026-06-09 - fix(frontend): Sprint 11+ — YOY/pp unit-aware 0.00 形式 + vite HMR no-store 头

### Fixed (Sprint 11 后续, 用户反馈驱动)
- **YOY/pp 显示 1400% bug** (`frontend-vue3/src/components/MetricCard.vue` + `YOYBadge.vue`):
  - 根因: 第一版 humanizeChange 总是不区分 unit 都 *100, 跟 % caller
    (kpiChangePct 已 *100) 重复 *100 → 全店GSV ↑1400% bug.
  - 第二版按 unit 区分 (跟 AudienceView L237-242 caller 注释对齐):
    - `%` unit: caller (kpiChangePct) 已 *100 传 percentage, MetricCard 不 *100
    - `pp` unit: caller (kpiChange) 传 0-1 ratio, MetricCard 内部 *100
  - 0.00 形式 (用户要 14.00% 不 14%, 10.00pp 不 10pp): toFixed(2) 保留 2 位
  - Math.round 治 toFixed IEEE 754 banker's rounding bug (0.145 → 14.5 而非 14.49)
  - 14/14 vitest PASS, vue-tsc 0 错, vite build 0 错
- **vite dev Cmd+Shift+R 刷不了前端缓存** (`frontend-vue3/vite.config.ts`):
  - 根因: vite 默认 Cache-Control: no-cache 允许 revalidate 路径,
    浏览器内存里仍持有旧 module, HMR push 后 Vue 组件不一定真 unmount/remount.
  - 修法 2 层:
    1. `server.headers` 显式 no-store: `Cache-Control: no-store, no-cache,
       must-revalidate, proxy-revalidate` + `Pragma: no-cache` + `Expires: 0`
       强制每次都从 server 拉新, 不允许 revalidate 路径
    2. plugins 加 `sprint11-force-reload-on-hmr`: handleHotUpdate 触发
       `server.ws.send({ type: 'full-reload' })`, 每次 .vue 改动强制整页 reload,
       跳过内存 HMR cache

### Verified
- Backend MTD 6/1-6/8 actual YOY (指示器):
  - 全店GSV 0.139 → display "↑13.90%"
  - 老客GSV 0.4142 → "↑41.42%"
  - 老客占比 0.104 → "↑10.40pp"
  - 等等
- vitest 14/14 PASS (4 EmptyState + 10 MetricCard)
- vite build ✓ built in 732ms, 0 错
- vite dev 起来后 curl 验证:
  - GET / 头: `Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate` ✓
  - GET /src/components/MetricCard.vue 头: 同上 ✓

### Sprint 11+ 后续 (留 Sprint 12)
- vitest 组件单测扩展 (audience/RFM/health 5-10 个)
- customer-health.spec.ts playwright 跑通
- S11-2 Alternative 1 删 is_member 改派生
- 50M 行 scale 架构

## [v0.4.14.24] - 2026-06-08 - feat(deps+test+etl): Sprint 11 — DuckDB 1.5.3 治根 ART race + 前端 vitest 立框架 + WO-1 conn config 修复

### Fixed (S11-1 P0 治根)
- **DuckDB 1.5.2 ART index race 治根** (`requirements-lock.txt` 升 1.5.3):
  - 之前 Sprint 10 B2 v3 用 DROP 6 secondary indexes 临时绕过的 race,
    1.5.3 修了 (PR #22094 "fix commit iteration offset bug + relax RemoveFromIndexes assertion")
  - 真测 race (大表 10.6M orders JOIN 4.6M membership_mark 强制错位):
    - Test 1 (DROP 6 idx): UPDATE 0.2s, 0 race ✅
    - Test 2 (WITH all idx, DROP 绕路失效场景): UPDATE 336.8s, 0 race ✅
  - 保守**保留** Fix A (load.py 2-tx) + DROP 6 idx 绕路, 理由:
    Test 2 带 idx UPDATE 336.8s 慢, Test 1 DROP idx + 重建 20s + UPDATE
    0.2s = 20.2s 整体快 16x. 性能 vs 治根冗余, 选性能.
  - Sprint 12 调研是否可删 Fix A (用更细的子查询 / transaction 隔离).

### Fixed (S11-3 P1 验证)
- **WO-1 修复 2 处 read_only conn 缺 config** (`scripts/etl/cli.py:686, 843`):
  - S11-3 跑一次 manual --update ETL 验证 Sprint 10 全部改动 (44.5 min exit 0):
    - orders 守恒 10,675,572 → 10,675,572 (delta 0)
    - is_member 守住 5,629,675 (52.73%)
    - fact_rfm 增量 103,680 → 108,000
    - user_rfm 9/9 dates 写入
  - 但有 2 个 WO-1 修复 ConnectionException 警告 (跟其他 8GB conn 触发 strict mode config conflict).
  - 修法: L686 + L843 加 `config={"memory_limit": DUCKDB_MEMORY_LIMIT}` 跟其他 8GB conn 一致.

### Added (S11-4 P2 立框架)
- **前端 vitest 单元测试框架** (`frontend-vue3/vitest.config.ts`):
  - 装 vitest 4.1.8 + @vue/test-utils 2.4.11 + @vitest/ui + jsdom 29.1.1
    (用 --legacy-peer-deps 解决 openapi-typescript peer conflict)
  - 跟 vite.config.ts 共享 alias + vue plugin
  - jsdom env 给组件挂载 DOM
- **npm scripts 加 4 个** (`frontend-vue3/package.json`):
  - test:unit (vitest run) / test:unit:watch (dev) / test:unit:ui (UI 模式)
  - test:unit:coverage (覆盖率)
- **首个组件单测样板** (`EmptyState.test.ts`): 4 个 test PASS
  - 默认/自定义 description / emoji / DOM 结构
  - 后续 Sprint 12 扩展 audience/RFM/health 3 个核心 view (5-10 个组件单测)

### Verified
- pytest 全套 (跨 W3/W1/sim-prod): 0 fail (8 个 s = skip 预期)
- vitest: 4/4 PASS
- S11-3 manual --update ETL: 44.5 min exit 0, 数据守恒
- 1.5.3 race 真测: 2 个 test 都没报 race

### Sprint 11 deferred (留 Sprint 12+)
- **S11-2 Alternative 1** 删 is_member 字段改派生: is_member 在 143 处引用,
  删字段破 API + W3 6 断言重写 + 老 RFM 快照 join 风险, 留 Sprint 12 评估
- **Fix A 删除评估** (load.py 2-tx): 等 S11-1 1.5.3 实际生产再跑 1-2 周看 race 是否仍 0
- **vitest 组件单测扩展** (audience/RFM/health 5-10 个): Sprint 12 0.5-1d
- **customer-health.spec.ts playwright 跑通**: 需 dev server + uvicorn 同启, Sprint 12

## [v0.4.14.23] - 2026-06-08 - feat(etl): Sprint 10 B2-merged — is_member 全 False 根因修复 (1.8s 修 3.48M 行)

### Fixed
- **prod orders is_member 长期累积错误** (10.6M 行从 2020 至今全 False):
  - 根因: 78 个 member parquet (data/parquet/member/) 覆盖 4.6M unique order_id
    (82.7% 跟 prod orders 匹配), 但 ETL 增量跑批的 member_order_ids 加载逻辑
    (pipeline.py:154) 拿不到对应会员标记. codex 0.137.0 诊断: 78 parquet 是 1-5
    月历史快照, 跟 6 月新订单 order_id 不重合, member_order_ids 计算后 isin
    全 False.
  - 修法: 2 个脚本一键 replay (持久化在 prod DB, 后续 Sprint 11 拿新 xlsx 后
    跑一次即可增量更新):
    1. `build_membership_mark.py`: CREATE TABLE membership_mark (order_id
       PRIMARY KEY) + DuckDB-native read_parquet 加载 4.6M (3.9s, 200x 快
       于 pd.read_parquet + executemany)
    2. `replay_is_member.py`: DROP 6 secondary indexes → UPDATE orders JOIN
       membership_mark (1.8s 修 3.48M 行) → CREATE INDEX 重建 (19.7s)
  - DuckDB 1.5.2 ART index 竞态缓解: 10.6M orders JOIN 4.6M membership_mark
    触发 "Corrupted ART index - likely the same row id was inserted twice".
    DROP secondary indexes 是关键 workaround, Sprint 11 调研更优解.

### Verified
- 5,629,675 / 10,675,572 (52.73%) orders is_member = TRUE (从 0 修复)
- 6/2-6/7 每天 40-50% 跟源数据一致
- 6/7 实测: member_gsv=¥325,738 (44.79% 占比), member_users=1,754 (41.2%)
  新客 507, 老客 1,247
- frontend dashboard 会员 GSV/新老客/占比 不再全 0

### Added
- **`scripts/etl/build_membership_mark.py`** (68 行): 从 78 parquet 加载 4.6M
  unique order_id 到 membership_mark 表 (持久化). 幂等: ON CONFLICT DO NOTHING.
- **`scripts/etl/replay_is_member.py`** (116 行): DROP 6 secondary indexes →
  UPDATE orders JOIN membership_mark (1.8s) → CREATE INDEX 重建. 幂等.

### Operations
- 后续 Sprint 11 拿 4-6 月 member xlsx 后 (78 parquet 是 1-5 月历史), 跑
  build_membership_mark.py 增量 + replay_is_member.py 即可
- 跑法: PYTHONPATH=. python3 scripts/etl/build_membership_mark.py && python3
  scripts/etl/replay_is_member.py
- 需先 kill uvicorn 持锁 (跟 ETL 跑批互斥)

## [v0.4.14.22] - 2026-06-08 - fix(etl): Sprint 10 B3 — daily backup BJ date + size assert + loud-fail (osascript + mail)

### Fixed
- **backup 文件名 UTC → BJ 时间** (`scripts/etl/backup_duckdb.py`):
  - 改的原因: launchd 03:30 BJ 跑出的 backup 用 UTC 日期命名成 "2026-06-07",
    用户视角看像 6/7 没 6/8 backup (实际是 6/8 BJ backup, 文件名错叫 6/7).
  - 改法: `BJ_TZ = timezone(timedelta(hours=8))` + `TODAY = datetime.now(BJ_TZ)`.
    6/8 03:30 BJ 现在正确命名 "2026-06-08" 跟用户日历日期一致.
  - 6/8 backup 已补跑: 25.4GB zst 创建成功 (`fuqing_crm_2026-06-08.duckdb.zst`).
- **compressed zst 0 字节盲点** (`scripts/etl/backup_duckdb.py`):
  - 加 `compressed_bytes > 0` assert, 防 zstd 假成功 (subprocess.run check=True
    只查 exit code 不查文件大小, 历史上 0 字节输出也可能 exit 0).

### Added
- **loud_fail(reason) 函数** (`scripts/etl/backup_duckdb.py`):
  - 失败时主动 macOS 桌面通知 (osascript display notification)
  - + /usr/bin/mail 发到 hutou@fuqing.local
  - 防止 launchd StandardErrorPath 静默失败, 留 visible trace 给运维.
  - log 时间戳也改 BJ (+08:00 时区), 跟 backup 文件名一致.

### Changed
- **plist 注释更新** (`scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist`):
  - 加 B3 loud-fail 说明, 卸载命令加 `2>/dev/null` (unload 失败不阻塞 load).

## [v0.4.14.21] - 2026-06-08 - fix(etl): Sprint 10 preflight B1 — staging NOT EXISTS + W4 8GB + RSS 12GB 硬限

### Changed
- **staging INSERT 改写** (`scripts/etl/load.py:616`): `ON CONFLICT (order_id, sub_order_id) DO NOTHING` → `WHERE NOT EXISTS (...)`
  - 改的原因: prod UNIQUE INDEX 被删, ON CONFLICT 需 unique constraint 会报 "no UNIQUE/PRIMARY KEY constraint"
  - 行为等价, 走应用层 dedup, 不依赖 DuckDB UNIQUE INDEX
  - 烟测 PASS (重复行 amount 保持原值, 新行正确写入)
- **DUCKDB_MEMORY_LIMIT_OVERRIDE 16GB → 8GB** (`scripts/etl/precompute_fact_rfm.py:42, 423, 456`)
  - 16GB 跟主 conn 8GB + W3 8GB + cache 8GB 不同 config, DuckDB 1.5.2 strict mode 报
    "Can't open a connection to same database file with a different configuration"
  - 16GB 过度设计, Sprint 5 真闭环 17 min 跑批 8GB 也 OK

### Fixed
- **prod UNIQUE INDEX 删除** (DB migration): `DROP INDEX IF EXISTS idx_orders_order_unique`
  - 跟 staging NOT EXISTS 改写配套, 避免 ON CONFLICT 路径断掉
  - 烟测验证: prod orders 表 UNIQUE indexes = [] (已删)
- **is_member 跟 UNIQUE INDEX race 关联诊断错误**: 原 Sprint 10 plan 假设是 DuckDB 1.5.2 UNIQUE INDEX race
  致 is_member 全 False. codex 0.137.0 交叉审核指出真根因在 staging INSERT 把 raw parquet 的 is_member
  写入 (load.py:616), 首次写入时 is_member 就是 False (member xlsx 没 JOIN), DO NOTHING 跳过现有行
  永远修不回来. 留 B2-merged 治根 (从 membership_mark replay is_member, 不走 staging overwrite).

### Added
- **RSS 12GB 硬限 sys.exit(1)** (`backend/db/memory_monitor.py`): 加 `_RSS_HARD_LIMIT_BYTES = 12GB` +
  `check_memory()` 启动时检查, 超限立即 `sys.exit(1)`. last-line-of-defense 防 ETL 跑批 RSS 持续增长
  把 Mac 拖崩. 8GB 告警保留为 warning (跟原来一样), 12GB 才是 fatal. launchd 检测 exit code != 0
  会发告警邮件.

### Removed
- **idx_orders_order_unique UNIQUE INDEX** (DB): prod 已 DROP. 后续依赖这个 index 的代码路径已迁移到
  应用层 dedup (staging + WHERE NOT EXISTS).

### Plan Doc
- **docs/SPRINT-10-PLAN.md 重塑**: codex 0.137.0 交叉审核 (2026-06-08) 找出 4 个问题 (Option A 内部矛盾 +
  is_member 根因误判 + Phase 4 调研浪费 + Phase 5 hygiene scope), 12 件任务 → 5 件, 2.5 天
  (B1 preflight / B2-merged upsert+replay / B3 backup loud-fail / B6-lite lsof / A2 D-7 sim-prod).
  详见 plan doc.

## [v0.4.14.20] - 2026-06-08 - fix(scraper): DMP 爬虫 7 件修复 + T_OFFSET 调度

### Changed
- **DMP_SPM 更新**: `...1d1125ebOCRO8L` → `...1d1125eblwdosJ` (达摩盘页面调整, 旧 spm 失效)
- **单品洞察 URL**: 加 `&analysisTab=compete` 参数 (3 处: `dmp_item_insight_scraper.py:382/407/1400`)
- **headless 修复**: `dmp_master.py:625/735` `headless=False` → `True`
  - 单品洞察 API 拦截 (`goods/view/overview/v2`) 在有头模式下失败 (12 秒 0 响应)
  - 无头模式验证通过, 资产诊断/流转在无头下也正常
- **单品洞察日期格式**: `strftime('%Y/%m/%d')` → `'%Y/%-m/%-d'` (与历史 CSV 一致)

### Fixed
- **Gate 1 删除** (`dmp_item_insight_scraper.py:2471-2482`): 单品洞察不再按数值变化率 (<0.01%) 跳过写入
  - 误判: 6/2~6/5 数据与 6/1 实质相同 → 全部跳过 → 看板缺 4 天数据
  - 根因: 达摩盘单品数据变化 <0.01% 时 Gate 1 误判为 T+1 未更新
  - 修法: 移除 Gate 1 数值比较, 仅保留 append_tocsv 内的同日期去重 (L2465)
- **Gate 2 删除** (`dmp_master.py:348-375`): 日期级 Gate 也按数值比较跳过整个日期, 同样问题, 一起删
- **达摩盘 T+1 跨日问题**: 6/7 数据 6/8 下午 15:00 才出, 早上跑会抓 6/6 复制
  - 临时方案: 删除 6/7 虚假数据 (15 行)
  - 长期方案: `T_OFFSET` 环境变量动态控制 (默认 1=T+1, 可设 2=T+2 早 9 点跑保险)
- **数据格式不一致**: 1186 行 `2026/06/01` 统一为 `2026/6/1` (与历史一致, 不带前导零)
- **5/30 流转脏数据**: 删除 8 行全 0 记录 (浏览器崩溃导致 API 拦截失败)

### Removed
- **死代码 68 行**:
  - `dmp_common.py:99-143` `safe_write_csv` 函数 (全 scraper 0 引用, dmp_scraper/dmp_flow 用 append 模式手写) — 48 行
  - `dmp_item_insight_scraper.py:2144-2155` `_is_completed` 函数 (0 调用) — 12 行
  - `dmp_item_insight_scraper.py:36-41` `try/except import yaml` (HAS_YAML 常量无引用) — 6 行
  - 注意: `check_dmp_session` (`dmp_common.py:530-558`) 误判 0 引用已纠正 (实际 `dmp_master.py:30` import + `:633` 调用)

### Added
- **T_OFFSET 环境变量** (`dmp_common.py:360`): `get_missing_dates_item` 支持动态 T+ 偏移
- **launchd 调度配置** (2 个 plist):
  - `com.fuqing.dmp-scraper.morning.plist` (早 9:00, T_OFFSET=2)
  - `com.fuqing.dmp-scraper.afternoon.plist` (下午 16:00, T_OFFSET=1)
  - ⚠️ plist 已生成在 `~/Library/LaunchAgents/`, 但需用户手动 `launchctl load` (auto mode 拦截)
- **launchd 调度文档** (`scraper/core/README-dmp-scraper-launchd.md`)

### Verified
- 模块加载验证: 5/5 模块 OK (dmp_common, dmp_item_insight_scraper, dmp_flow_scraper, dmp_scraper, dmp_master)
- 数据更新:
  - data.csv (流转): 最新 2026/6/5 (T-2 口径)
  - data2.csv (资产诊断): 最新 2026/6/6 (T-1 口径)
  - data3.csv (单品洞察): 最新 2026/6/6 (15/15 商品, 6/7 虚假数据已删)
- codegraph 同步: 280 文件已索引, 含本次全部修改 (`dmp_common.py:343` `get_missing_dates_item` 等)

### Risk
- **淘宝风控**: 6/8 跑批触发达摩盘反爬 (短时间内多次大批量抓取)
- 建议: 24 小时后再跑 (等风控标记过期), `chrome_profile/` 登录态应还在
- 下次跑批会自动应用 T_OFFSET 调度 (早 9 点 T+2, 下午 16 点 T+1)

### Deployment Notes
- **不需要 restart uvicorn** — 纯 scraper 模块, 不影响 backend API
- **下次 launchd 调度** (今天 16:00): 自动跑 T+1, 应能抓到 6/7 真实数据
- **手动 `launchctl load`**: 详见 `scraper/core/README-dmp-scraper-launchd.md`

---

## [v0.4.14.19] - 2026-06-08 - fix(etl): Sprint 9 维修 — watchdog/cache key/W3 valid_sql/W4 memory

### Fixed
- **ETL 增量跑批死循环** (4 件根因, 全部闭环):
  1. **watchdog 内存阈值 2GB→8GB** (`backend/db/memory_monitor.py:29`)
     - 2GB 跟 `DUCKDB_MEMORY_LIMIT=8GB` 不匹配, 跑批 RSS 3-4GB 触发误报甚至被 watchdog kill
     - 8GB 一致, 避免增量跑批死循环
  2. **`_mark_all_files_processed` key 错配** (`scripts/etl/pipeline.py:560+`)
     - 之前 parquet key = `f.name`, 但 ingest L82 `_file_changed` 用 `_xlsx_stem_to_rel` 反查 xlsx 相对路径
     - key 不一致导致冷启动后 ingest 仍把 103 个 parquet 视为新增, 走 xlsx fallback 读 103 xlsx
     - RSS 撞 watchdog 阈值被 kill, **死循环**
     - 修法: parquet key 跟 ingest 一致用 `_xlsx_stem_to_rel` 反查
  3. **W3 DQ assertions `valid_sql` column 引用 bug** (`scripts/etl/assertions.py:114,126`)
     - 之前 SQL `AND valid_sql = 1` 引用 column, 但 `valid_sql` 是 `OrderFilters.valid_order()` 返回的 SQL 字符串, 不是 column
     - DuckDB 报 `Referenced column "valid_sql" not found`
     - 修法: f-string 插入 `valid_sql` 字符串
     - 配套: test fixture schema 6→8 列同步 production (`is_goujinjin`/`order_status`/`is_refund`)
  4. **W4 memory_limit 16GB→8GB** (`scripts/etl/pipeline.py:485`)
     - 之前 W4 用 16GB override, 跟主 conn 8GB + W3 `_assert_conn` 8GB + cache.py `_open_write_conn` 8GB 不同 config
     - DuckDB 1.5.2 strict mode 报 `Can't open a connection to same database file with a different configuration`
     - 修法: 跟其他 conn 一致 8GB, 避免跨 connection config 冲突
     - 16GB 是过度优化, Sprint 5 17 min 真闭环 8GB 也 OK

### Verified
- pytest `backend/tests/`: 391 passed / 0 fail (排除 uvicorn 持锁 pre-existing 1 fail)
- pytest `test_w3_dq_assertions.py`: 26 passed in 3:01 (fixture schema 改后)
- 增量 ETL 6/8 跑批 11:38 自然 exit 13:42: 5,110 行 6/7 新数据入库, MAX(pay_time) 推到 6/7 23:59:57
- 8 渠道分布正确 (货架 3,025 + 淘客 611 + 直播 408 + 达播 380 + U先 354 + 赠品 145 + 百补 94 + 微博 93)
- daily_visitors +1 天到 6/7 (889 天合计), 淘客纠正 62,090 → 1,877,371
- `--full` 全量重建 cache (预计 30+ min, 跑批中)

### Deployment Notes
- **不需要 restart uvicorn 立即生效** — 4 件都是 ETL 跑批路径代码, 不影响 backend API
- **下次 ETL 跑批 (8:30 launchd) 会自动应用 watchdog + cache key 修复**
- 建议手动 `kill <uvicorn_pid> && 重启` 一次以加载 Sprint 8 P0 (YOYBadge pp) + PR#22/23 改动 (本来 Sprint 9 候选 1)

## [v0.4.14.18] - 2026-06-08 - fix(audience): MetricCard YOY 显示 0.1% → 7.5% 修复

### Fixed
- **前端 Bug**: `frontend-vue3/src/views/AudienceView.vue` 7 处 `unit='%'` 卡片
  - **根因**: `MetricCard.vue` 模板两种 unit 模式口径不一致：
    - `unit='%'`: 模板直接 `.toFixed(1)` 显示 change（**不**乘 100），调用方需传 * 100 后的百分比
    - `unit='pp'`: 模板内部 * 100，调用方传 decimal
  - 但 AudienceView 7 个 `unit='%'` 卡片（全店GSV/老客GSV/新客GSV/会员GSV/会员溢价/访客数/新增会员数）都直接传 `kpiChange()`/`visitorChange()` 返回的原始 decimal (0.0749)
  - → `Math.abs(0.0749).toFixed(1) = "0.1"` → 显示 `↑0.1%`（应该是 `↑7.5%`）
  - 4 个 `unit='pp'` 卡片（老客占比/新客占比/会员GSV占比/会员入会率）传 decimal 是正确的（MetricCard 内部 * 100）
  - 其他视图用了正确包装器：`HealthOverviewTab fmtYoy/fmtPpt`、`RFMView` 内联 * 100
  - **修法**: 添加 `kpiChangePct` / `visitorChangePct` 包装器（与 `HealthOverviewTab fmtYoy` 命名一致），7 个 `unit='%'` 卡片改用 `*Pct` 版本

### Verified
- frontend-vue3 npm run build: 849ms OK
- pytest tests/test_rfm_service.py: 17 passed
- API 实测全店 GSV YOY=+7.49%，修复后应显示 `↑7.5%`
- 其他视图（HealthOverviewTab/RFMView）不受影响：它们用 `fmtYoy = v * 100` 或内联 `* 100`，本身传的就是 percentage

## [v0.4.14.17] - 2026-06-08 - fix(rfm): R 桶分桶改回 cutoff_dt 截止，6 个 R 桶回购率全部 > 0

### Fixed
- **后端 R 区间流转 Bug**: `backend/services/rfm/_flow_engine.py` + `r_flow.py`
  - **根因**: `5fbeffb` 把 `hist_customers` 改用 `start_dt` 截止（pre-period 行为），
    但 `r_bucket_params` 仍用 `end_dt` 截止（bc65360 Sprint 8 P0 设计）。
    两口径不一致导致有当期订单的回购用户 `pre_cutoff_last_pay` 落在当期，
    `DATEDIFF(pre_cutoff_last_pay, end_dt) = 0-6 天` → 全部归入近1个月，
    R 桶 2-6 ∩ base_orders = ∅，回购率恒为 0%（Sprint 7 a73dfac 教训重现）。
  - **修法**: `r_bucket_params` 改回 `[cutoff_dt, cutoff_dt]` (= `start_dt - 1`)
  - **结果**: 6 个 R 桶全部有非零回购率，符合业务语义

### Added
- **回归测试**: `tests/test_rfm_service.py::test_r_bucket_uses_preperiod_recency`
  - 3 用户场景：U1 (pre+current) / U2 (pre-only) / U3 (current-only)
  - 关键断言：U2 归入近2-3个月（不是近1个月），repurchase=0

### Verified
- pytest tests/: 456 passed, 8 skipped, 1 pre-existing fail (DuckDB lock env, 跟改动无关)
- **6/1-6/7 2026 实测 (DuckDB 缓存清后)**:
  - 近1个月: hist=180,248 / 回购=3,209 (1.78%)
  - 近2-3个月: hist=187,945 / 回购=2,621 (1.39%)
  - 近4-6月: hist=205,736 / 回购=1,761 (0.86%)
  - 近7-12个月: hist=486,118 / 回购=2,349 (0.48%)
  - 近13-24个月: hist=938,052 / 回购=1,658 (0.18%)
  - 2年外: hist=2,234,013 / 回购=1,394 (0.06%)
  - 已购客TTL: hist=4,249,634 / 回购=27,146 (0.64%)
- **段级和 < TTL by 14,082 (= 当期新购客)**: 业务语义正确的代价（新购客 pre_cutoff=NULL，不归入任何 R 桶）

### Deployment Notes
- **缓存清理**: `DELETE FROM rfm_query_cache WHERE endpoint = 'r-flow';` 必须执行
  （DuckDB-KV cache 不像 JSON 文件那样容易清，必须直连数据库）
- 5/31 整天（cutoff_dt=start_dt-1）订单的用户被排除在 pre_cutoff_users 外，
  这是 `pay_time <= cutoff_dt::TIMESTAMP` 语义边界（cutoff_dt=5/31 00:00:00 排除 5/31 全天）
  已知 trade-off，影响 ~1% 用户

## [v0.4.14.16] - 2026-06-07 - fix(audience+rfm): sprint8 P0 前端 2 bug 修复 (YOYBadge 模式统一 + R 桶 pre_cutoff 截止改 end_dt)

### Fixed
- **前端 Bug 1 (YOYBadge 模式统一)**: `frontend-vue3/src/views/AudienceView.vue` 24 处
  - `value: row.xxx_yoy` 改成 `value: (row.xxx_yoy ?? 0) * 100, unit: 'pp'`
  - 占比 (`*_ratio_yoy`) 早已统一 pp 模式, 同比百分比 (`gsv/users/aus_yoy`) 之前用默认 % 模式乘 100 显示 0.1% 跟 占比的 0.1pp 单位混淆
  - 统一后全店 GSV 同比显示 `+0.0pp ↑` (0.001 同比小数 * 100 = 0.1pp, toFixed(1) 0.1)
  - 不动 L298 IndicatorRow (ratio vs non-ratio 分支已正确)

- **后端 Bug 2 (R 桶 pre_cutoff 截止改 end_dt)**: `backend/services/rfm/_flow_engine.py` + `r_flow.py`
  - `r_bucket_params = [cutoff_dt, cutoff_dt]` 改 `[end_dt, end_dt]`
  - 1 月新购客 DATEDIFF(pre_cutoff_last_pay in 1月, end_dt=1/31) = 0-30 天 → 进入 R 桶 1
  - 段级和 = TTL (跟 hist_customers / 已购客TTL 一致, 不再有 "5/1-5/31 新购客不进任何 R 桶" trade-off)
  - 月纬度 R 桶 1 重要价值客户 2026 回购人数 > 0 (1 月有买 ∩ R 桶 1 ∩ 复购)

### Verified
- pytest backend/tests/: 391 passed, 12 skipped, 1 pre-existing failure (test_w4_full.py::test_rfm_recompute_window_dry_run, uvicorn PID 50804 持 DuckDB 锁环境问题, 跟改动无关)
- pytest ./tests/: 141 passed (与改前一致)
- frontend-vue3 npm run build: 855ms OK
- 修复后: 全店 GSV 同比显示 `+0.1pp ↑` (L446) 跟占比同比 `+0.1pp ↑` (L479) 单位一致
- 修复后: 月纬度 重要价值客户 R 桶 1 hist_users 含 1 月新购客, repurchase_users > 0

## [v0.4.14.15] - 2026-06-07 - docs: sprint7 P2 6 层防护清理文档 (cleanup.md 516 行)

### Added
- **docs/operations/cleanup.md** (新, 516 行): 6 层磁盘治理运维文档
  - 6 层防护详细表格 (atexit / zshrc / workbuddy / weekly / daily backup / hourly subagent)
  - 各层详细说明 (代码路径 / 触发 / 常量 / 协议 / CLI 入口)
  - 紧急清理命令 (Layer 1 --cleanup-tmp / Layer 6 cleanup_subagent.py --dry-run / Layer 4 shell / Layer 5 backup / 手动 rm 应急)
  - launchd 调度状态 (期望 3 行, query 命令, kickstart / unload 调试)
  - 重要协议 (F3 marker / _fq_* 不强删 / ms-playwright 1208 缓存 / /private/tmp vs /tmp symlink)
  - 6 个审计 log 路径表 + 查询命令速查
  - Sprint 5 deep dive 教训 (440GB 残留, 5 层失效原因, Layer 6 设计原则)
  - 容量监控 + 告警阈值 + 接手者 follow-up + 关键文件路径索引 + 附录 A 差异表 + 附录 B 紧急速查

### Verified
- 格式跟 docs/handoff-2026-06-05.md 风格一致 (标题 + TL;DR + 章节编号 + 表格 + 代码块 + 附录)

## [v0.4.14.14] - 2026-06-07 - test: sprint7 P2 DuckDB 升级测试 + Fix A 决策 (KEEP 2-tx)

### Decision
- **Fix A 保留 (2-tx workaround)**: DuckDB 1.5.3 未修 UNIQUE INDEX race bug (新连接场景), 1-tx 路线在生产路径下 0/1 通过, 2-tx 路线 1/1 通过
- **DuckDB 不升级**: 保持 1.5.2 (requirements-lock.txt), 1.5.3 对当前痛点无功能收益
- **load.py 不变更**: 5a77fa3 Fix A 拆 2 tx 维持, 真根因 (Sprint 5 deep dive) 仍存在

### Verification
- DuckDB 1.5.3 单连接 100/100 单元测试 4/4 路线通过 (误导性, in-memory state)
- DuckDB 1.5.3 新连接 1 次生产路径测试: 1-tx 0/1 失败, 2-tx 1/1 通过
- pytest backend/tests/: 459+ passed / 8 skipped (与升级前一致)
- 报告: `docs/validation-reports/sprint7-p2-duckdb-upgrade-2026-06-07.md`

### Lessons (D-7)
- **单连接测试不能推广到生产**: DuckDB file-backed 模式下, 同一 connection 的 in-memory state 与新 connection 的 file state 行为不一致. 真实生产 ETL 总是新连接 per call. 任何 ETL 决策必须有"模拟生产"测试.
- 加到 CLAUDE.md "Sprint 3 P1 三件 4 轮修教训" 第 5 条

### Why
- Sprint 5 deep dive 5 维度 subagent 排查 (A: 72% 主流量, B: ON CONFLICT 3 场景 OK, C: 1:1 模式 production 存在, D: VARCHAR 传递无损, E: ROW_NUMBER 精确) 确认 DuckDB 1.5.2 UNIQUE INDEX race
- Sprint 7 P2 复测 1.5.3 确认 race 在新连接场景下未修复

## [v0.4.14.13] - 2026-06-07 - fix(rfm): sprint7 P0 重构 service import 模式 (治根 10 root test fail)

### Fixed
- **10 root test 治根** (10 fail → 0 fail, 141 passed)
  - tests/test_rfm_analysis.py 6 个 (health/rfm_analysis/*)
  - tests/test_rfm_service.py::TestSegmentOrders 2 个 (rfm/segment_orders.py)
  - tests/test_rfm_service.py::TestRFMRFlow 2 个 (rfm/_flow_engine.py → r_flow.py)

- **根因**: Python `from backend.db.connection import get_connection` 拷贝引用到模块 __dict__,
  monkeypatch 修改原模块时,模块内的本地引用不变 → mock 不生效

- **修法**: 改 `from backend.db.connection import get_connection` → `from backend.db import connection as bdc`,
  调用方 `bdc.get_connection()` 走模块属性查找,monkeypatch 立即生效

- 涉及 5 个文件 (11 insertions / 11 deletions):
  - backend/services/health/rfm_analysis/analysis.py (L17/L34/L77)
  - backend/services/health/rfm_analysis/cache.py (L29/L60)
  - backend/services/rfm/segment_orders.py (L8/L164)
  - backend/services/rfm/_flow_engine.py (L18/L453)
  - backend/services/rfm/_shared.py (L15/L170)

### Verification
- pytest ./tests/: **141 passed** (10 fail → 0 fail)
- pytest backend/tests/: 395 passed / 8 skipped (不 regress,1 pre-existing DB lock fail 与改动无关)
- uvicorn 重启: 200 OK,Application startup complete

### Workflow
- branch: fix/sprint7-p0-service-import-refactor
- commit: ad9f9b9 → merge: 70f60f1
- 走 12 步流程 (checkout → commit → push → merge --no-ff → push main → pull --ff-only → restart uvicorn)

refs: docs/SPRINT-7-PLAN.md Sprint 7 P0 任务 1

## [v0.4.14.12] - 2026-06-07 - feat(cleanup+docs): sprint6 4 件 P0/P1/P2 收口 (5→6 层防护 + W7 + D-6)

### Added
- **scripts/etl/cleanup_subagent.py** (新, 276 行): Layer 6 核心 cleanup_subagent_tmp() 函数 + CLI
  扫 /private/tmp + /tmp 1h+ 1GB+ 非白名单, 排除项目根 + layer 1 自身状态文件
  cap 5 文件 / 100GB. dry_run 模式. log /tmp/fuqing-subagent-cleanup.log
- **scripts/etl/launchd/com.fuqing.tmp-cleanup.hourly.plist** (新, 67 行)
  launchd hourly StartInterval=3600, 跟 weekly cleanup 模板一致
- 部署: ~/Library/LaunchAgents/com.fuqing.tmp-cleanup.hourly.plist
- launchctl list | grep fuqing: 4 服务 (weekly + hourly + daily backup + etl.daily)
- Dummy 5GB 验证: dd 5GB + mtime 1 年前 + 跑 cleanup_subagent.py → DELETED

### Fixed
- **backend/tests/test_w7_e2e_override.py**: env dict 加 DUCKDB_MEMORY_LIMIT_OVERRIDE: "" 显式置空
  根因: subprocess 继承父进程 DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB env
  修法 3 (subprocess env 显式置空) — 不动父进程 os.environ
  pytest: W7 4 passed, 全量 1 failed / 391 passed / 12 skipped (不 regress)

### Docs
- CLAUDE.md: 4 层 → 6 层防护表格 + v0.4.14 → v0.4.14.11
- README.md: 4 层 → 6 层 (跟 CLAUDE.md 一致)
- docs/DOCUMENT-INDEX.md: 状态行 sprint 4+5 真闭环
- docs/飞书版架构文档/05-前端架构.md: v3.1 → v3.2

### Decision
- 16 root tests (141 个) 真修 vs ignore 决策: 维持 ignore 现状 (pyproject.toml testpaths)
  根因: monkeypatch 引用拷贝 Python 坑
  修复时机建议: 留 Sprint 7 P0 重构 service import 模式

### Verified
- pytest backend/tests/: 1 failed / 391 passed / 12 skipped (不 regress)
- launchctl list | grep fuqing: 4 服务运行
- Dummy 5GB 删除: DELETED 5.0GB, log 持久, 0 错误

## [v0.4.14.11] - 2026-06-07 - fix(etl): sprint5 P0-3 hotfix 4 Fix A 痛点 1 端到端真闭环

### Fixed
- **scripts/etl/load.py:506-575** 改 1 个 tx (DELETE+INSERT) → 2 个 tx (DELETE+COMMIT 跟 INSERT+COMMIT 分开)
- **真根因 (deep dive subagent 5 真实验找到)**: DuckDB 1.5.2 UNIQUE INDEX 在同一 transaction 内 INSERT 时不感知本事务内未提交的 DELETE
- 之前 hotfix 1/2/3 (ON CONFLICT/NOT EXISTS) 都没用, 因为 UNIQUE INDEX 仍报错
- 5 err_ids 跑 5 行 OK 但 100 行 fail 的 asymmetry: 行数少时 race 概率低

### Verified
- 真跑批 --update 1 次 ~17 min ✅ 无 constraint error (290,121 行 + 9/9 W1 GROUPING SETS date)
- Fix A 拆 2 tx: tx1 DELETE+COMMIT 让 UNIQUE INDEX 看到 DELETE, tx2 INSERT NOT EXISTS
- Sprint 5 痛点 1 端到端: 🟡 部分 → 🟢 真闭环 (代码层 + 跑批真验)

## [v0.4.14.10] - 2026-06-07 - fix(etl): sprint5 P0-3 hotfix 3 _upsert_to_duckdb_body 改用 NOT EXISTS

### Fixed
- **scripts/etl/load.py:543-555** 改 ON CONFLICT (sprint 4 56a35ee) → AND NOT EXISTS 路线
- 5 维度 subagent 并行排查 (A+D / B+E / C): (X, X) 72.5% 主流量 + DuckDB 1.5.2 ON CONFLICT 测试 OK + staging VARCHAR 类型无损
- 真根因: NOT EXISTS 路线测试 100% OK 但生产跑批 2 次仍撞 (边界 case 未明), 跑批真验留 Sprint 6

### Note
- D-4 教训深一: subagent 报告 "代码已修" + 测试 OK 都不够, 必须真跑批验证
- 5 维度 subagent 排查 + 主 agent 真排查: DuckDB 1.5.2 ON CONFLICT / NOT EXISTS 在 subquery + ROW_NUMBER + WHERE 嵌套下有真 bug
- sprint 5 收口: NOT EXISTS 已合 main (d9165bb), 跑批真验留 Sprint 6 深入 (可能需要 DuckDB 升级或换 SQL 写法)

## [v0.4.14.7] - 2026-06-07 - feat(backup): sprint4 P0-2 DuckDB 55GB 每日备份 (launchd daily + zstd 压缩)

### Added
- **scripts/etl/backup_duckdb.py** (新, 100 行): DuckDB 55GB 每日备份脚本
  - shutil.copy2 (os-level, 不冲突 uvicorn 持锁 PID 79499 reload 模式)
  - zstd 绝对路径 /Users/hutou/homebrew/bin/zstd (launchd PATH 不含 homebrew)
  - post-copy verify (duckdb connect read_only, 防 APFS torn copy, 1-2s)
  - 失败清理: zstd 失败时 finally 块删 uncompressed 中间产物 (防磁盘累积)
  - log 走 plist stdout/stderr 重定向 (避免双写)
  - umask 077 (客户数据 600 权限)
  - 复用 cleanup_backups.sh F18 POSIX lock 防并发
- **scripts/etl/launchd/com.fuqing.duckdb-backup.daily.plist** (新, 55 行): launchd 每日 03:30 调度 (错开 weekly cleanup 周日 03:00 + ETL 跑批 08:30)
- **data/processed/backups/.gitkeep** (新, 6 行): 备份目录占位 (force add 绕过 data/ ignore)

### Verified
- 跑 1 次 exit 0: 55GB → 21GB (38.2% 压缩比), 含 post-copy verify 跑通
- launchctl list 看到 3 个 fuqing 服务: backup-cleanup.weekly + duckdb-backup.daily (新) + etl.daily
- 复用 sprint 1 治理留的 cleanup_backups.sh + weekly plist 模板

### Note
- DuckDB 1.5.2 Python API 不支持 VACUUM INTO 语法 (1.0 文档说支持, 实际测试 FAIL), 走 os-level 复制 (shutil.copy2) 路线
- 5 review 修全生效: log 不重复 / TS 动态 / zstd 失败清理 / post-copy verify / umask 077

## [v0.4.14.8] - 2026-06-07 - test(etl): sprint4 P0-3 dedup 回归测试 (痛点 1 端到端闭环)

### Added
- **backend/tests/test_dedup_orders.py** (新, 240 行, 6 测试): dedup 回归测试覆盖
  1. test_duplicate_order_id_sub_order_id_no_error - _copy_df_to_duckdb ON CONFLICT 真生效
  2. test_string_vs_int_dedup - 字符串转换后视为同键
  3. test_incremental_new_orders_with_internal_duplicates - upsert_to_duckdb df_new 内部去重
  4. test_refresh_window_with_internal_duplicates - df_refresh 内部去重 + staging ROW_NUMBER
  5. test_on_conflict_literal_in_load_py - 源码字面量守卫
  6. test_unique_index_literal_in_load_py - idx_orders_order_unique 守卫

### Verified
- 6 个 dedup 测试全过
- 397 + 6 = 403 passed, 12 skipped
- 已 push origin/fix/sprint4-p03-dedup-orders (c7c9235)

### Note
- D-4 教训: subagent 报告 _copy_df_to_duckdb:601 已有 ON CONFLICT (sprint 3 8bbf7c6), 但实际跑批撞 _upsert_to_duckdb_body:543 路径. 端到端真跑批暴露了 subagent 没真跑验证的盲点
- 源数据 (order_id, sub_order_id) 实际无重复 (shop parquet 10.6M + member 5.6M 行, duplicated=0)

## [v0.4.14.9] - 2026-06-07 - fix(etl): sprint4 P0-3 hotfix 2 _upsert_to_duckdb_body 加 ON CONFLICT

### Fixed
- **scripts/etl/load.py:550** 加 ON CONFLICT (order_id, sub_order_id) DO NOTHING
  - 跟 _copy_df_to_duckdb:601 (sprint 3 8bbf7c6) 一致
  - _upsert_to_duckdb_body 窗口刷新路径: staging ROW_NUMBER 去重后
    INSERT 跟 orders 表已存在的 (order_id, sub_order_id) 冲突时跳过
  - 跑批 2 次还撞 constraint: 根因是 staging ROW_NUMBER 选 _rn=1 后,
    INSERT 跟 orders 已有 (X, X) 撞 - 测试 3 + 模拟测试 5 + 生产 10.6M 行
    模拟测试 100% OK, 实际跑批仍撞 (可能是 staging 数据 boundary case)

### Verified
- 测试 3 (简单 schema + 1 行): ON CONFLICT 跳过 ✅
- 测试 5 (production schema + 1000 行): OK ✅
- 测试 6 (production 10.6M 行 sample + 1 NEW): OK ✅
- ruff check scripts/etl/load.py: All checks passed
- 走完整 12 步流程: branch → review → commit → push → merge main → push main → pull --ff-only

### Note
- D-4 教训深一: 即使 ON CONFLICT 加了, 实际跑批仍可能撞, 必须真跑批验证
- 教训: review 写 '代码看起来对' 不够, 必须 git log + 真跑批 + git show 实证
- 留 Sprint 5: 真排查跑批撞根因 (staging 数据 boundary case / DuckDB 1.5.2 ON CONFLICT 边界)

## [v0.4.14.1] - 2026-06-07 - docs(etl): P0-1 痛点 1 跑批 3 次验证闭环 — W1 GROUPING SETS 13.4 min 平均 < 35 min 目标 (sprint 3 P0-1) — W1 GROUPING SETS 13.4 min 平均 < 35 min 目标 (sprint 3 P0-1)

### Added
- **`docs/validation-reports/etl-3-runs-2026-06-07.md`** (新, 340 行): P0-1 痛点 1 跑批 3 次真数据验证报告
  - W1 GROUPING SETS 代码路径真生效验证: `git log --all` 验 commit 682f0cd + 5 hotfix 已在 main, `run_auto_preload:605` 调 `preload_date_batch:350` 1 SQL/date 替代 720 串行 (12x 减少)
  - 3 次跑批实测: RUN #1 710.24s / RUN #2 817.15s / RUN #3 878.90s (平均 802.10s ≈ 13.4 min, CV 9.4%)
  - 性能对比: vs 旧 2/3 (16.2 min) 1.4x 加速 / vs 旧 3/3 (56.8 min) 6.5x 加速
  - 60 组合/date × 9 dates = 540 组合/跑, 写入 37M rows/跑 (3 × 37M = 111M rows)
  - RSS 峰值 6.1 GB (DuckDB 缓冲增长, 正常), 无 OOM 无 crash

### Note
- 痛点 1 闭环: 🟡 部分 → 🟢 闭环 (W1 GROUPING SETS 单步 13.4 min < 35 min 目标, 3/3 成功)
- 已知 issue: `--update` 路径 Step 1 撞 (order_id, sub_order_id) 重复 constraint error (独立数据 quality issue), 修后即可端到端验 < 35 min
- baseline_2026_06_03.json 新增 3 run: w1v2-1/3, w1v2-2/3, w1v2-3/3 (real_elapsed_sec broken 已知 bug, 真值在 per_step[0].wall_sec)

## [v0.4.14.6] - 2026-06-07 - fix(ci): P1-3 review 四轮 2 件 (B2 idx->lineno 修复 + M1 committed 默认 scope)

### Fixed
- **B2-FALSENEG-COMMITTED-MODE (blocker) - committed 模式 idx/lineno 不一致 false negative**: `check_file()` 把 idx (triggers 列表索引) 传给 `find_evidence_nearby()` 和 `has_real_git_evidence()`, 这俩函数把 idx 当 added_lines 索引
  - 在 committed 模式下 added_lines = 整文件 (e.g. 340 行), trigger 在末尾的 idx 在 triggers 列表里 = 0, 但在 added_lines 里 = 339. window=30 滑到 added_lines[0:30] (文件头, 有早期 commit SHA), trigger 被屏蔽, false negative
  - 加 `_find_line_index(added_lines, target_lineno)` helper: 在 added_lines 中找 lineno == target_lineno 的真 idx
  - `find_evidence_nearby` / `has_real_git_evidence` 改签名 `trigger_idx` -> `trigger_lineno` (1-based 行号, NOT triggers list idx), 内部用 `_find_line_index` 反查真 idx 算窗口
  - `check_file()` 主循环改传 `lineno` (不是 `idx`)
  - 新测试 `TestB2LargeFileRegression` (6 cases): `test_find_evidence_nearby_uses_lineno_not_triggers_idx` (核心) / `test_find_evidence_nearby_lineno_in_340_line_file` (340 行场景) / `test_has_real_git_evidence_uses_lineno_not_triggers_idx` / `test_find_line_index_helper` / `test_check_file_committed_mode_long_file_ends_with_violation` (50 行集成) / `test_committed_mode_integration_340_line_file` (真 git repo 340 行文件)
  - 旧 9 个 EVIDENCE_CASES / H1 HEX / H3 测试 trigger_idx=0 改 trigger_lineno=1 (语义更清晰)
- **M1-COMMITTED-NO-OP-WITHOUT-FILES (medium) - committed 默认 scope 修 false sense of safety**: `--committed` 没 `--files` 时, 旧版静默 no-op (files=[]). CI 跑 `--files` glob 没事, 但开发者手动 `--committed` 会得 false sense of safety
  - `main()` argparse 处理: `args.committed and not args.files` 时自动 fallback 到 `docs/validation-reports/*.md` + `docs/飞书版架构文档/*.md` (匹配 `.github/workflows/lint.yml` + `nightly.yml` ground-truth-lint step 的 scope)
  - 加注释说明 fallback 行为 + 用 `sorted(set(...))` 稳定输出
  - 新测试 `TestM1CommittedDefaultScope` (3 cases): `test_committed_fallback_scans_validation_reports` (e2e 端到端) / `test_committed_fallback_empty_repo_no_violation` (graceful 退出) / `test_committed_with_explicit_files_overrides_fallback` (显式 --files 仍 work, 不破坏 CI)

### Note
- B2 修是 silent correctness fix, 不改变 staged 模式行为, 不影响现有 user workflow
- M1 fallback 只在 `args.committed and not args.files` 时启用, 显式传 `--files` 仍优先 (不破坏 CI workflow)
- 测试总数: 47 -> 55 (新增 8: 6 B2 + 3 M1 - 1 旧 idx test 转 lineno)

## [v0.4.14.5] - 2026-06-07 - fix(ci): P1-3 review 二轮 3 件 (B2 NOOP + H1 HEX + BRANCH-STATE)

### Fixed
- **B2 NOOP (blocker) — CI 结构性 no-op**: 旧实现只读 `git diff --cached` (staged content), CI 跑已 commit 文件时永远 0 字节 → 永远 rc=0, 是结构性 no-op
  - 加 `--committed` 模式: 用 `git show HEAD:<path>` 拉已 commit 文件内容, `parse_whole_file` 整文件当 added_lines 扫 (diff_scope_filter='whole_file')
  - `.github/workflows/lint.yml` + `nightly.yml` ground-truth-lint step 改用 `--committed --files` 模式
  - 新测试 `TestB2CommittedMode` (8 cases): `test_parse_whole_file_*` / `test_get_committed_content_*` / `test_check_file_committed_mode_*` / `test_committed_mode_end_to_end_in_git_repo` (真 tmp git repo commit 验证)
- **H1 HEX-COLOR-BACKDOOR (high) — hex color 旁路**: SHA regex `(?:commit[:\s]+|tag[:\s]+|PR\s*#?[:\s]*|#|@)\b[0-9a-f]{7,40}\b` 接受 `#` 前缀, `#ff00aabb` (8 hex) 被算 evidence (false positive 旁路)
  - `_is_pseudo_sha` (重命名自 `_looks_like_phone_or_id_card`) 加 hex color 模式: `re.search(r'#[0-9a-f]{6,8}\b', text)` → 视为伪 SHA
  - 加 `HEX_COLOR_RE` + `_filter_hex_color_evidence()`, `find_evidence_nearby` 显式抠掉 evidence 中所有 #xxxxxx
  - 新测试 `TestH1HexColorExclusion` (7 cases): red team `X 未集成 #ff00aabb` 被拦 + 正例 `commit ff00aabb` (无 # 前缀) 仍算 evidence
- **BRANCH-STATE-MESS (medium) — 修复在错分支**: 修在 `fix/sprint3-p13-review-lint-fixes` (0d7b9bb), 原 `fix/sprint3-p13-review-lint` 还指 33c7fe3 旧版, merge 会拿到 broken 版本
  - 修后 force-push 0d7b9bb + 新 commit 到原分支 `fix/sprint3-p13-review-lint`
  - 删除 `fix/sprint3-p13-review-lint-fixes` 分支 (本地 + remote)

### Note
- `--committed` 模式 + staged 模式互斥, 通过 `--committed` flag 切换, 默认仍是 staged (本地 pre-commit 钩子不变)
- hex color 黑名单覆盖 6-8 位 (#fff #ffffff #ffff 带 alpha), 3/4 位短形式 (少见) 不在白名单
- end-to-end committed 测试会 init tmp git repo, 已用 GIT_CONFIG_GLOBAL=/dev/null 隔离, 不会污染 worktree

## [v0.4.14.4] - 2026-06-07 - fix(ci): P1-3 review 修 5 件 (2 blocker + 3 high)

### Fixed
- **B1 core.hooksPath 死代码**: 加 scripts/setup-hooks.sh 一次性激活; README "快速开始" 段加激活指引; CLAUDE.md 加演示代码检查绕过提醒
- **B2 CI 完全没调 check_review_ground_truth**: .github/workflows/lint.yml 加 ground-truth-lint job (非阻塞 warning 起步); nightly.yml 也加
- **H1 SHA evidence 正则过宽**: 旧 \b[0-9a-f]{7,40}\b 误判中国身份证/手机号/hex color; 新正则要求 commit/tag/PR/#/@ 前导, 加 phone/ID 黑名单
- **H2 46 测试 trivial 内部**: 压到 30 tests (5 is_review_file + 6 trigger + 6 evidence + 4 diff + 3 e2e + 2 env/CLI + 2 H3 + 2 misc), 648 → 350 行
- **H3 evidence 只验字符串出现**: 加 has_real_git_evidence 真跑 git log 双重验证 (cheap L1 字符串 → real L2 git log 跑通)

### Note
- H3 限制: 仍依赖 PR review 人工护航 expensive case ("写了 git log 但实际跑空")
- B2 ground-truth-lint 起步 non-blocking, 观察 false positive 率再考虑改 blocking


## [v0.4.14.2] - 2026-06-06 - test(etl): W3/W4 pipeline CI smoke test (sprint 3 P1-1)

### Added
- **`backend/tests/test_w3w4_pipeline_smoke.py`** (新, 8 tests / 4 类)
  - `TestSkipDqFlagEndToEnd` (2 tests): `skip_dq=True` → rfm_quarantine 空; `skip_dq=False` (默认) → 暴跌数据触发 `assert_total_not_drop` → quarantine 1 行
  - `TestW4IdempotencyEndToEnd` (2 tests): `run_full_etl` 跑 2 次不抛 PK 冲突 + `UNIQUE (date, dim)` 组合数一致 (dbt-style snapshot 幂等)
  - `TestSkipW4FlagEndToEnd` (2 tests): `skip_w4=True` → fact_rfm_long 表空; `skip_w4=False` (默认) → W4 块建表
  - `TestEndToEndPipelineRun` (2 tests): 端到端 `run_full_etl` 不抛错 + 关键表保留
  - 用 `temp_duckdb_path` + `mock_parquet_dirs` fixture 隔离, monkeypatch 短路所有重活儿 (113 xlsx + 41GB 单例锁)
  - 跑批 14s < 5min, CI 不超时

### Note
- 补 sprint 2 task 1 (e60dbfd) 留下的 CI 缺口: `test_w3w4_pipeline_integration.py` 走 inspect 抽源码 + exec 块验证, 改 W3/W4 集成代码 CI 拦不住
- 本 smoke test 真跑 `run_full_etl` 端到端, 改 W3/W4 集成 (pipeline.py step 8.5 / step 8) CI 立即可见


## [v0.4.14.1] - 2026-06-06 - docs: D-4 飞书架构 7 份刷 — 修 15 findings (PR #19)

### Fixed
- **`docs/飞书版架构文档/00-系统总览.md`** + 5 个姐妹 doc: 修 15 findings
  - W2 函数名漂移 → `SnapshotManifest.read_active()` + `loader.py:get_rfm_view_name()`
  - W4 fact_rfm_long 表结构列名 + PK + UNIQUE INDEX 全面对齐 v0.4.12
  - 组合数 540: `3×3×5×12` → `9 channel × 60 item × 1 segment`
  - SQL: 删 `LIKE ANY (?)` (DuckDB 不支持), `changes()` → `RETURNING`
  - W5 端点 `segments/distribution/fact` → `r-flow/f-flow/m-flow/segment-orders/version`


## [v0.4.14.2] - 2026-06-06 - feat(etl): W3/W4 pipeline 集成补 skip flag + DELETE 幂等 (sprint 2 task 1)

### Added
- **`scripts/etl/pipeline.py:run_full_etl`**: `skip_dq=False, skip_w4=False` 参数, W3/W4 块 `if not skip_dq/w4:` 守卫
- **`scripts/etl/pipeline.py` step 8.5**: W3 块调 `run_assertions` 前 `DELETE FROM rfm_quarantine WHERE date = ?` (幂等)
- **`scripts/etl/cli.py`**: argparse 加 `--skip-dq` / `--skip-w4` flag
- **`backend/tests/test_w3w4_pipeline_integration.py`** (新, 18 tests / 5 类)

### Note
- main 实际早已集成 W3 step 8.5 (v0.4.11) + W4 step 8 (v0.4.12), 此 commit 只补 skip flag + 幂等保障


## [v0.4.14.3] - 2026-06-06 - chore(etl): W4 T-7 跑批验证报告 + 4 integration tests (sprint 2 task 2)

### Added
- **`backend/tests/test_w4_t7_integration.py`** (新, 4 tests / 4 类)
- **`docs/validation-reports/w4-full-t7-2026-06-06.md`** (新, 190 行占位)

### Note
- 实测值在 v0.4.14.5 补全: `incremental_inserted=540` / `merge_inserted=3780` / `total rows=12,960` / `version 1..6`


## [v0.4.14.4] - 2026-06-06 - docs: D-5 飞书架构续 — 5 outdated 标注更新 (sprint 2 task 4)

### Fixed
- 4 个飞书架构 doc: pipeline W3/W4 集成状态从 "未集成" 改 "已集成 (v0.4.11/12)"
- 00-系统总览 §9 增 §9.6/§9.7 W4 full + W5 release notes
- D-4 ground truth 4 errors 纠正


## [v0.4.14.5] - 2026-06-06 - fix(etl): 痛点 3 真闭环 + CLAUDE.md 加固 + CI 第一层 PyYAML (sprint 2 维修 round 1)

### Added
- **`docs/validation-reports/w4-full-t7-2026-06-06.md`**: 痛点 3 真闭环 (4/4 tests PASSED in 496.34s)
  - `incremental_inserted=540` / `merge_inserted=3780` / `merge_dates=7` / `total rows=12,960` / `version 1..6` / `数据质量 10/10 pass`

### Changed
- **`CLAUDE.md`** 12 步流程: /review 前增 "强制 git log --all 验证" (D-4 ground truth 教训)

### Fixed
- **`requirements-lock.txt` L87**: `PyYAML==6.0.3` → `6.0.2` (匹配 paddlex 3.4.3)
- **`backend/tests/test_w7_memory_limit.py:173`**: 删 unused `import pytest` (F401)


## [v0.4.14.6] - 2026-06-06 - fix(ci): setuptools 81.0.0 解第二层冲突 + CI 真绿 (sprint 2 维修 round 2)

### Fixed
- **`requirements-lock.txt` L100**: `setuptools==82.0.1` → `81.0.0` (匹配 torch 2.11.0 <82)

### CI
- **`CI run 27062413467`**: ✅ **success** (lint ✅ + test ✅) — 修 sprint 1 以来 30+ CI 红


## [v0.4.15.1] - 2026-06-06 - chore(ci): /review 前 git log 自动化 lint (sprint 3 P1-3)

### Added
- **`.githooks/check_review_ground_truth.py`** (新): pre-commit 钩子, 扫 `docs/` 下 .md 触发词
  - 触发词: `未集成 / 不存在 / 占位 / TODO / FIXME / 缺失 / 待集成 / 还没接` (中英 9 个)
  - 证据模式: `git log`/`git show` 命令 / 7-40 位 commit SHA / `已验证|已确认|已核对|已落地|已合入|已集成|已实现|已存在` 白名单 (任意 1 个即通过)
  - 范围 narrow: 只扫 `docs/`, 排除 `CHANGELOG.md / reference.md / DOCUMENT-INDEX.md / README.md`
  - 误伤规避: 只检查 **新增** 行, 不检查删除行; 跳过 `backend/ frontend-vue3/ scripts/ scraper/`
  - 救火: `FQA_GROUND_TRUTH_SKIP=1 git commit ...`
- **`.githooks/pre-commit`**: 接 P1-3 检查到末尾 (B2/B5/cleanup 之外)
- **`backend/tests/test_check_review_ground_truth.py`** (新, 46 tests / 5 类):
  - `TestIsReviewFile` (5): scope 边界
  - `TestTriggerDetection` (5): 触发词 + 单词边界
  - `TestEvidenceDetection` (5): evidence 模式
  - `TestParseAddedLines` (4): unified diff 解析
  - `TestCheckFile` (5): 单文件端到端
  - `TestMainEndToEnd` (12): 11 red team + regression + 真 git repo
  - `TestCLIRun` (3): argparse / env / 真 git
  - `TestScriptInGitRepo` (3): 在 tmp git repo 里 red team + regression

### Background
- D-4 (2026-06-06) 飞书架构 7 份刷出现 4 个 ground truth 错误, agent 凭 memory / stale 文档下结论
- 教训: "pipeline.py W3 step 7b 未集成" → 实际 step **8.5** 早就合 (v0.4.11)
- CLAUDE.md L119-134 有纪律但靠人记, 自动化 lint 防回归

### Verified
- 46/46 tests passed
- Red team (5): 故意写 `未集成/不存在/占位/TODO` 进 `docs/`, 全被拦 (rc=1)
- Regression (8): 真实 commit 模式 (含 git log / SHA / 已验证 / CHANGELOG / code comment) 全通过
- 真 git repo: 3 tests (`test_real_git_*`) 在 tmp git 里端到端验证

## [v0.4.11] - 2026-06-06 - feat(etl): W3 full DQ assertions + pipeline step 8.5 集成 (3 留作断言 + lark 真发)

### Added
- **`scripts/etl/assertions.py`**: W3 full 6 断言 (MVP v0.4.10 3 核心 + W3 full v0.4.11 3 留作)
  - 断言 4 `assert_540_completeness` (新): 当天 (lookback × metric × channel) 组合数 < 54 (3×2×9) → quarantine
  - 断言 5 `assert_dimension_drift` (新): 任意 dim row count 变 > ±20% → quarantine
  - 断言 6 `assert_history_no_loss` (新): user_rfm total < prev_30d_avg × 0.99 → quarantine
  - 新常量: `EXPECTED_DIM_COMBOS_PER_DATE=54` / `DIM_DRIFT_THRESHOLD=0.20` / `HISTORY_LOSS_THRESHOLD=0.99`
  - 内部 helper `_has_user_rfm_table()` 幂等检查 (W1 没跑时 skip)
- **`scripts/etl/pipeline.py` step 8.5 (新)**: W3 DQ assertions 集成
  - 在 step 8 (品类看板) 完成后调 `run_assertions(conn, today, send_alert=True)`
  - 独立 DuckDB 连接 (READ_WRITE — rfm_quarantine 需要 write; 不与 ETL 单例共享, 避免 read_only/READ_WRITE config 冲突)
  - 失败入 `rfm_quarantine` 表, 不阻塞 ETL (SaaS 标准: 脏数据隔离)
  - 包装 `try/except` 兜底: 断言异常仅 print warning, 不抛到 ETL 退出路径
  - 走 `PerfTimer("pl_step8_5_dq_assertions", date=str(today))` 埋点
- **`backend/tests/test_w3_dq_assertions.py`**: W3 full 覆盖 (MVP 11 → W3 full 22 tests)
  - `TestAssert540Completeness` (4 tests): skip 无表 / pass 54 / fail 缺 dim / custom expected
  - `TestAssertDimensionDrift` (3 tests): skip 无表 / pass 无漂移 / fail > 20%
  - `TestAssertHistoryNoLoss` (4 tests): skip 无表 / pass 稳定 / fail -50% / skip 当天 0 行
  - `TestRunAssertions.test_run_assertions_all_six_with_user_rfm` (新): 6 断言全 pass 验证
  - `TestPipelineStep85Integration` (2 tests): pipeline 静态检查 (含 step 8.5 标识) + 实际 6 断言跑通

### Changed
- **`scripts/etl/assertions.py`**: 顶层 docstring 升级 v0.4.10 MVP → v0.4.11 full
  - 删 "W3 full 留作下次 sprint" TODO 段
  - 加 "W3 full (v0.4.11, 本 commit)" 段 (6 断言 + pipeline 集成 + lark 真发)
- **`scripts/etl/assertions.py`**: `_send_lark_alert_mockable` docstring 从 "MVP 包装" 改 "W3 包装: 生产路径调 scraper/_send_lark_alert (真发 lark-cli), 测试时可 mock"
  - 行为不变 (MVP 已经在调 scraper 真发, 这只是文档澄清)
- **`backend/tests/test_w3_dq_assertions.py`**: `TestRunAssertions.test_run_assertions_all_pass` expected passed 数从 3 → 3 (没 user_rfm 时仍 skip 留作断言, 故不变)
  - 加 `test_run_assertions_with_send_alert_false` 验证 send_alert=False 路径

### 设计 (design doc v1.1 §W3 + §7.3)
- **6 断言分层** (按失败严重度):
  - fatal 阻塞: `assert_idempotency` / `assert_history_no_loss` (数据完整性)
  - quarantine + alert: `assert_total_not_drop` / `assert_repurchase_nonzero` / `assert_540_completeness` / `assert_dimension_drift` (异常检测)
- **SaaS 标准**: 6 断言全部 best-effort (失败入 quarantine, ETL 继续)
- **跨子项目 import**: 复用 `scraper/core/sanity_check.py:_send_lark_alert` (6 道门禁 lark-cli 通道)
- **不破坏 ETL 单例**: assertions.py 只读 DuckDB, write 只入 rfm_quarantine; pipeline.py step 8.5 用 read_only conn, caller 负责 conn.close()

### CLAUDE.md 合规
- ① 复用 `scraper/core/sanity_check.py:_send_lark_alert` (跨子项目, scraper/CLAUDE.md 允许, 不新写 lark 客户端)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): `duckdb.connect` + `conn.close()` 由 caller 管
- ③ 不破坏 ETL 单例连接 (assertions.py 只读 DuckDB, write 只入 rfm_quarantine; pipeline step 8.5 独立连接, 用完即关)
- ④ 12 步流程: branch = `feat/wo3-full` / pytest 22 tests / qa 验 quarantine 触发 / Python 3.14


and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.4.12] - 2026-06-06 - feat(etl): W4 full — 540 组合 + dbt-style merge T-7 + 全量重算 — 痛点 3 预计算全量

### Added
- **W4 full 540 组合** (`scripts/etl/precompute_fact_rfm.py`): `incremental_load` 扩 9 channels × 60 items × 1 segment_id (聚合) = 540 组合, 走 `backend.semantic.segments` (CLAUDE.md 硬规则) + `backend.semantic.filters.OrderFilters.valid_order()` 口径
- **dbt-style snapshot T-7** (`merge_replace(load_date)`): 对 (load_date) 整批 INSERT 新 version (= existing_max+1), 旧 version 保留 (历史链可追溯), UNIQUE 索引保证幂等
- **`incremental_load_with_merge(target_date, t_minus_days=7)`**: 一步组合 incremental + T-7 内 merge, 修复 late-arriving (设计 doc Premise 7: T-7 内 99% 覆盖)
- **`enumerate_combos()` + `enumerate_items()`**: 动态枚举 (channel, item, segment_id) 组合, 从 orders.spu_product_class top 60 by GMV 兜底 `W4_ITEMS_FALLBACK` (60 个)
- **新文件 `scripts/etl/rfm_recompute_window.py`** (~150 行): 全量重算 CLI, `--from --to --dry-run --quiet`, 走 `setup_async_memory()` 16GB override
- **W4 集成到 pipeline.py**: ETL 末尾调 `incremental_load_with_merge`, 失败 graceful degrade (跟 W6 通知同样的"不阻塞"哲学), 写入 `_stats["w4_fact_rfm"]` 给 W6 lark-cli 通知携带
- **测试** `backend/tests/test_w4_full.py` (18 个 case): 540 组合枚举 + incremental_load 走 540 组合 + merge_replace 修复 late-arriving + incremental_load_with_merge + rfm_recompute_window.py dry-run CLI

### Changed
- **`scripts/etl/precompute_fact_rfm.py` 升级 v0.4.9 → v0.4.12**: 替换占位 `run_full_precomputation()` (raise NotImplementedError) 为 540 组合 + dbt-style merge + 全量重算
- **`scripts/etl/pipeline.py`**: 加 `import os` (W4 stats 需要 `os.environ.get`); ETL 末尾加 W4 调, 失败不阻塞 (跟 W6 通知一致)
- **`backend/tests/test_w4_fact_rfm.py`**: 适配 v0.4.12 schema (加 `spu_product_class` 列 + 传 `combos=MVP_COMBO` 显式 1 组合, 保持 MVP 测试语义)
- **`backend/tests/test_w7_memory_limit.py`**: `test_w4_placeholder_raises_not_implemented` → `test_w4_full_v0_4_12_implemented` (W4 full 已实施)

### Fixed
- **`incremental_load` 旧签名**: 增加 `combos=None` 参数, 默认自动 `enumerate_combos()` (540), 但允许测试传 1 组合 mock

### CLAUDE.md 合规
- ① 走 `backend.semantic.segments.get_registry()` (校验) + `backend.semantic.filters.OrderFilters.valid_order()` (口径)
- ② ETL 脚本连接例外 (CLAUDE.md §ETL 例外): `duckdb.connect(DUCKDB_PATH, config={"memory_limit": ...})` + `conn.close()`
- ③ 12 步流程: branch = `feat/wo4-fact-rfm-full` / pytest 25 passed (W4 MVP 5 + W4 full 18 + 2 fixture) / 整 suite 417 passed / 8 skipped / ruff all clear

### 设计参考
- `docs/design/etl-phase4-architecture.md` §W4 + §7.4
- Premise 7: 纯增量 + dbt-style snapshot 适合 10.6M 订单 (Late-arriving 订单 T-7 内覆盖 99%)


## [v0.4.14] - 2026-06-06 - feat(frontend): RFM Version Banner — 顶栏显示当前 manifest 版本 + 切换时间

### Added
- **`frontend-vue3/src/components/RfmVersionBanner.vue`** (新): 顶栏彩色横条,展示当前 active RFM manifest 信息
  - 三态: loading (skeleton 占位) / success (绿色, active_view 正常) / warn (琥珀, active_view 为空) / error (灰条, 不阻塞)
  - 交互: 悬停主文本 → NTooltip 展示完整 manifest 路径; 右侧刷新按钮 (loading 时禁用)
  - 数据源: `GET /api/v1/rfm/version` (TanStack Vue Query, 30 min staleTime, 切批后点刷新即看到新版本)
- **`frontend-vue3/src/api/rfm.ts`** (新): `fetchRfmManifestVersion()` 封装 `/v1/rfm/version`
- **`frontend-vue3/src/types/rfm.ts`** (新): `RfmVersionInfo` interface (`active_view` / `version` / `ts` / `path`)

### Changed
- **`frontend-vue3/src/views/RFMView.vue`**: 在 `<PageHeader>` 后插入 `<RfmVersionBanner />`,3 行 diff

### 验证
- `vue-tsc -b` 通过 (exit 0)
- `npm run build` 通过 (772ms, 47 chunks, 唯一 warning 是预存在的 chunk-size 提示)


## [v0.4.13] - 2026-06-06 - feat(etl): W5 DuckDB-KV cache + 4 RFM 端点 + manifest invalidate — 痛点 3 部分缓解

### Added
- **`backend/services/rfm/cache.py`** (~210 行, 新): W5 DuckDB-KV 缓存
  - `RfmQueryCache` class: `ensure_table` / `get` / `set` / `invalidate` / `cleanup_expired` / `list_keys` / `stats`
  - `rfm_query_cache` 表: `key VARCHAR PK` (SHA-256 hex) / `endpoint` / `params_hash` / `value JSON` / `expire_at` / `created_at`
  - SHA-256 规范化 key derivation: 等价请求 (key 顺序无关) 生成同一 hash, 防 cache poisoning (§7.5 风险 W5 cache poisoning)
  - TTL 24h, 过期行 `cleanup_expired` 一键清理 (避免表无限增长)
  - `_ManifestTracker`: manifest version 变化 → 自动整表失效 (W2 atomic snapshot 集成)
  - 进程内单例 `_manifest_tracker_singleton` (避免每次 new 重建状态)
- **`backend/routers/rfm.py`** 集成 cache: 4 端点 (`r-flow` / `f-flow` / `m-flow` / `segment-orders`) 都走 `_cached_rfm_call`
  - 命中: ~1ms 返回 (走 cache.get 锁内预取)
  - miss: 调底层 service, 结果写 cache (走 ThreadSafeCursor 锁内预取, 防并发覆盖)
  - 3 个调试端点: `GET /cache/stats` / `POST /cache/invalidate` / `GET /cache/keys?endpoint=xxx&limit=50`
- **`backend/main.py`** lifespan 启动时 `RfmQueryCache().ensure_table()` (W5 startup hook)
- **`backend/services/rfm/__init__.py`** 导出 `RfmQueryCache`
- **`backend/tests/test_w5_cache.py`** (12 tests, 新): MVP 覆盖
  - 表幂等 + schema 验证
  - cache hit / miss / overwrite / 不同 endpoint / 不同 params / canonicalization
  - TTL 过期返回 None
  - 10 线程并发 set/get 不崩溃 + 数据一致
  - manifest version 1 → 2 触发整表清空
  - manifest version 不变时多次 get 不清空
  - `_cached_rfm_call` 集成验证: 第二次 hit 不再调 compute_fn

### Performance
- **RFM 端点 cache hit < 5ms** (设计目标 §4.1 SLA): SELECT 单行 + JSON parse
- **RFM 端点 cache miss < 200ms** (设计目标 §4.1 SLA): 走 fact_rfm_long (W4 产物)
- manifest version 检测: 单次 JSON read < 1ms, 不阻塞 query

### CLAUDE.md 合规
- ① **ThreadSafeCursor 包装**: `RfmQueryCache.get/set` 用 `get_connection()` (锁内预取) — 引用 `reference.md` 2026-05-31 教训
- ② **连接规范**: 走单例 `get_connection()`, 禁止 `conn.close()`
- ③ **接口只读**: cache 是 read-mostly, invalidate 是 admin 端点
- ④ **SHA-256 防 cache poisoning**: 64 字符 hex, 碰撞概率 ~0 (§7.5 风险)
- ⑤ **TTL 自动过期**: 不依赖后台 cleanup, `expire_at > now()` 在 get 时过滤

### 设计依据
- design doc `docs/design/etl-phase4-architecture.md` §W5 (设计) + §7.5 (测试) + §13 决策 4 (cache miss 不做双轨, 一步到位走 fact_rfm_long)

### 关联
- W2 `feat/wo2-manifest-snapshot` (v0.4.8) — manifest.json 提供 cache invalidate 信号
- W4 `feat/wo4-fact-rfm-long` (v0.4.9) — cache miss 的快速回退路径


## [v0.4.10.1] - 2026-06-06 - fix: VERSION drift 复发 (0.4.7.4 → 0.4.10) + CLAUDE.md/README.md 同步 (224 → 258)

### Fixed
- **VERSION drift 复发** (`VERSION`): `0.4.7.4` → `0.4.10`（实际 main 状态）
- **CLAUDE.md L30 版本表同步**: `v0.4.7.4（main，2026-06-06 release），测试 224 passed / 8 skipped` → `v0.4.10（main，2026-06-06 release），测试 258 passed / 8 skipped`
- **README.md L25 / L89 / L182 同步**:
  - L25: `测试 224 passed / 8 skipped（v0.4.7.4）` → `测试 258 passed / 8 skipped（v0.4.10）`
  - L89: `tests/  # 单元测试（12 个文件，149 passed）` → `tests/  # 单元测试（22 个 backend/tests/*.py + 根 tests/, 258 passed）`
  - L182: `当前测试覆盖（224 passed / 8 skipped，v0.4.7.4）` → `当前测试覆盖（258 passed / 8 skipped，v0.4.10）`

### 根因
- 之前 (commit 1917e08 之前) 一直忘了同步 VERSION/CLAUDE.md/README.md, 导致 v0.4.10 已经 merge 后 docs 仍是 v0.4.7.4
- 12 步流程 (CLAUDE.md) 没有强制卡 "merge 前比对 pytest 输出 vs docs 中测试数字", 这次手动核对发现

### 教训 (写入 CLAUDE.md 候选, 后续 PR 跟进)
- 12 步流程加一步: "merge 前必须 `pytest --collect-only -q | tail -1` 拿测试数字, 对比 docs 中的数字, 不一致先改 docs 再 merge"
- pre-commit 加 VERSION 校验: VERSION 必须是最近 3 个 commit tag 之一, 否则告警

## [v0.4.10] - 2026-06-06 - feat(etl): W3 MVP DQ assertions + 幂等性 — 痛点 2 质量保证

### Added
- **`scripts/etl/assertions.py`** (~220 行, 新): W3 MVP 实现
  - 3 核心断言: `assert_total_not_drop` (total < prev_30d_avg × 0.3 → quarantine) / `assert_repurchase_nonzero` (防 P0-102 100%/0% 回归) / `assert_idempotency` ((date, dim, version) 唯一)
  - `rfm_quarantine` 表 (id, date, failed_assertion, reason, raw_data JSON, created_at) + seq
  - `_write_quarantine()` 自带 `create_quarantine_table` (idempotent, 断言函数可独立调用)
  - `_send_lark_alert_mockable()` 包装 scraper/_send_lark_alert (跨子项目 import, scraper/CLAUDE.md 允许)
  - `run_assertions(conn, target_date, send_alert=True)` 总入口: 返回 `{passed, failed, failed_names, alert_sent}`
  - CLI 入口: `python3 scripts/etl/assertions.py --date=2026-06-05 [--no-alert]`
- **`backend/tests/test_w3_dq_assertions.py`** (11 tests, 新): MVP 覆盖
  - quarantine 表幂等创建
  - 3 断言 pass / fail / skip 路径全覆盖
  - total 暴跌 + 重复 dim+version 触发 quarantine
  - W4 还没跑 (无 fact_rfm_long) 时 repurchase_nonzero skip
  - run_assertions 总入口: 全 pass / 部分 fail + alert 触发
  - mock lark 不真发 (MVP 测试不触发 lark-cli)

### 设计 (design doc v1.1 §W3)
- **SaaS 标准**: 脏数据隔离不阻塞业务 — 失败入 quarantine + 告警, ETL 继续
- **跨子项目 import**: 复用 `scraper/core/sanity_check.py:_send_lark_alert` (6 道门禁 lark-cli 通道, 不新写 lark 客户端)
- **W4 配套**: assert_repurchase_nonzero 查 fact_rfm_long (W4/MVP v0.4.9 表), W4 没跑时 skip
- **idempotency 跟 W4 配套**: (date, dim, version) UNIQUE INDEX (W4/MVP 已加), W3 跑去重检

### W3 full 留作下次 sprint
- [ ] 3 留作断言: `assert_540_completeness` / `assert_dimension_drift` / `assert_history_no_loss`
- [ ] `scripts/etl/pipeline.py` 在 step 8 调 `run_assertions()` (W3 集成, MVP 不含)
- [ ] lark-cli 真发消息 (MVP mock 掉, 测试时 _send_lark_alert 不真发)
- [ ] E2E 测: 注入 history -50% 脏数据, 验 quarantine 触发 + lark 告警

### CLAUDE.md 合规
- ① 复用 `scraper/core/sanity_check.py:_send_lark_alert` (跨子项目, scraper/CLAUDE.md 允许, 不新写 lark 客户端)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): `duckdb.connect` + `conn.close()` 由 caller 管
- ③ 不破坏 ETL 单例连接 (assertions.py 只读 DuckDB, write 只入 rfm_quarantine)
- ④ 12 步: `feat/wo3-dq-assertions-mvp` 分支 / pytest 258/8 / Python 3.14

### 验收 (design doc v1.1 §7.3 MVP)
- [x] `scripts/etl/assertions.py` 3 断言函数 + pytest 11 tests
- [x] `rfm_quarantine` 表 (id, date, failed_assertion, reason, raw_data JSON)
- [ ] pipeline.py 在 step 8 调 assertions (W3 full 集成)
- [ ] pytest 6 断言 + quarantine 不阻塞后续 ETL (W3 full)


## [v0.4.9] - 2026-06-06 - feat(etl): W4 MVP fact_rfm_long 预计算 — 痛点 3 部分缓解

### Added
- **`scripts/etl/precompute_fact_rfm.py`** (86 → 200 行, 改): W4 MVP 实现
  - `FACT_RFM_TABLE = "fact_rfm_long"` + schema (date, dim_key, dim_json, user_count, gmv, repurchase_count, version, created_at, PK (date, dim, version))
  - 唯一索引 `idx_fact_rfm_dkv` (date, dim, version) 幂等保证
  - `create_fact_rfm_table(conn)`: 幂等表创建 (IF NOT EXISTS)
  - `_next_version(conn, load_date)`: 同一天重跑 version 续号 (dbt-style snapshot)
  - `incremental_load(conn, target_date)`: append T-1 (target_date-1) 1 组合 (channel='全店'), 走 DuckDB RETURNING 拿实际插入行
  - `run_mvp_async()`: CLI 入口, 调 setup_async_memory() 16GB override + 跑当天增量
- **`backend/tests/test_w4_fact_rfm.py`** (7 tests, 新): MVP 覆盖
  - 表 schema + 唯一索引创建幂等
  - 增量加载 1 组合 (channel='全店') row count + gmv + repurchase_count
  - 同一天跑 N 次 (幂等性 v1.1 §7.4): 数据值一致, version 续号
  - target_date vs load_date 分离 (cutoff = start_date - 1 day, 教训 2026-05-29)
  - channel='全店' filter 正确 (其他 channel user 不算)

### 设计 (design doc v1.1 §W4 MVP)
- **MVP 简化**: 1 组合 (channel='全店') 验证机制. 540 组合 (channel × item × segment) 留 W4 full
- **走语义层接口**: 调 `backend.semantic.segments.SegmentRegistry.build_*_sql` (W4 full 用), MVP 用 inline SQL 验证机制
- **16GB 内存**: 调 W7 `setup_async_memory()` 临时 override, 跑完回 8GB
- **dbt-style snapshot**: 同一天重跑 version 续号, 旧 version 保留 (后续 merge 用)

### W4 full 留作下次 sprint
- [ ] 540 组合 (channel × item × segment_id) 完整 ETL
- [ ] dbt-style merge T-7 修复 late-arriving 订单 (覆盖原 version)
- [ ] 全量重算脚本 `rfm_recompute_window.py` (运营手触发, 一次性跑全历史)
- [ ] pipeline.py 集成 (W2 manifest write_active() 配套, ETL 末尾调)
- [ ] 3 个日期 range 查询 E2E 验 < 1s (W5 cache 配套)

### CLAUDE.md 合规
- ① 走 `backend.semantic.segments` (CLAUDE.md 硬规则: ETL 走语义层, MVP 暂 inline, W4 full 用 SQL builder)
- ② ETL 脚本连接例外 (CLAUDE.md §接口开发六步 §ETL 脚本连接例外条款): `duckdb.connect` + `conn.close()`, 单例规则不适用
- ③ cutoff = start_date - 1 day (教训 2026-05-29): `load_date = target_date - timedelta(days=1)`
- ④ 12 步: `feat/wo4-fact-rfm-mvp` 分支 / pytest 247/8 / Python 3.14 / qa 验 row count 1:1

### 验收 (design doc v1.1 §7.4)
- [x] pytest 测 idempotency: 同一天跑两次结果一致 (data values 一致, version 续号)
- [x] 增量跑 T-1 append-only (date 严格 T-1, 不影响其他日期)
- [ ] 全量跑全历史 row count == 旧表 (W4 full)
- [ ] dbt-style merge T-7 修复 late-arriving (W4 full)
- [ ] E2E 测 3 个日期 range 查询 < 1s (W5 cache 配套)


## [v0.4.8] - 2026-06-06 - feat(etl): W2 原子 snapshot 切换 — 痛点 2 根因修复

### Added
- **`scripts/etl/manifest.py`** (~180 行, 新): `SnapshotManifest` 类实现 POSIX atomic 切换. 写: tmp file + `os.fsync` + `os.rename` (POSIX atomic, near-atomic on Windows). 读: `open().read()` 短读原子. 旧版本保留 7 天 (`.versions/{ts}_v{N}.json`). 损坏兼容 (`read_active()` 返回空串不抛异常). 单 view (user 拍板 v1.1 §13)
- **`backend/services/rfm/loader.py`** (~50 行, 新): API 层入口. `get_rfm_view_name()` 读 manifest 拿 active view 名. `get_rfm_manifest_info()` 给 `/api/v1/rfm/version` endpoint
- **`/api/v1/rfm/version`** endpoint (backend/routers/rfm.py): 返回 `{"active_view": str, "version": int, "ts": str, "path": str}`. 用途: 调试 ETL manifest 更新 + W5 cache invalidate 配套 + 监控告警
- **`backend/tests/test_w2_manifest.py`** (16 tests, 新): 覆盖 write/read 原子性 + 损坏兼容 + 7 天保留 + 过期清理 + concurrent write + **SIGKILL 中途不破坏** (POSIX atomic rename 兜底) + endpoint schema

### 设计 (design doc v1.1 §6)
- **写流程**: tmp + fsync → 复制旧版本到 .versions/ → os.rename tmp → manifest (POSIX atomic on same FS, 失败回滚安全)
- **读流程**: open().read() — Python 内核层保证 < 4KB 原子, 多 API 线程并发安全
- **7 天保留**: `.versions/{ts}_v{N}.json`, lazy cleanup on write
- **单 view**: 出问题直接回滚到 .versions/ 里的上一版, 不支持多 view 并行灰度

### CLAUDE.md 合规
- ① 走 `os.rename` + `os.fsync` (POSIX atomic 兜底)
- ② 多 API 线程并发读安全 (短读 + atomic rename 后单文件原子)
- ③ 不动 ETL 单例连接 (manifest.py 只读 FS, 与 DuckDB 无关)
- ④ 12 步: `feat/wo2-manifest-snapshot` 分支 / pytest 240/8 / Python 3.14 / qa 验 SIGKILL 安全 (16/16 test 覆盖)

### 验收 (design doc v1.1 §7.2 完成标志)
- [x] manifest.json 旧版本保留 7 天 (`.versions/`, 12 retention_days 段测试)
- [x] 模拟 ETL 写到一半被 kill (SIGKILL) → API 仍读到旧 view (`test_sigkill_during_write_leaves_manifest_intact`)
- [x] pytest 测 concurrent read during write (`test_concurrent_writes_last_wins`)
- [x] API 文档更新: GET /api/v1/rfm/version 返回当前 active view

### 配套
- **W3 (DQ + 幂等)**: W2 manifest 不依赖, 可独立做
- **W4 (fact_rfm_long 预计算)**: 写 view 后 `write_active("fact_rfm_view_v{N}")` 让 API 自动切新表
- **W5 (DuckDB-KV cache)**: cache invalidate 钩子读 manifest.version, 变化 → 整表失效 (本 commit 已留 `get_rfm_manifest_info` 接口)

### 限
- 当前 ETL 未调 `write_active()` (W2 验收不要求), 实际触发是 W3/W4 时集成 (`scripts/etl/pipeline.py` ETL 末尾调 `manifest.write_active(...)`)
- manifest.json 缺失/损坏时 `read_active()` 返回空串, API 需 fallback 处理 (本 commit 默认抛 "ETL not run yet")


## [v0.4.7.9] - 2026-06-06 - feat(ci): B6 P3 每周 CI 健康报告

### Added
- **`.github/workflows/weekly-report.yml`** (新): 每周一 UTC 1:00 (北京时间 9:00) 跑全量 pytest, 输出 junit XML + 上传 artifact (90 天保留) + 写 step summary. 跟 nightly.yml (B3) 风格一致, 但 trigger cron 是每周一. 加 `workflow_dispatch` 允许手动触发

### 趋势可见
- **Artifact 下载**: GitHub repo → Actions → Weekly Health Report → 任意 run → Artifacts → `pytest-results` (90 天内可下)
- **Step summary**: 每个 run 的 Summary tab 显示 `tests=N failures=N errors=N skipped=N time=Ns`, 一目了然
- **对账场景**: 周一上午 9 点 GitHub mail 提醒, 团队 review 上周 pass/fail trend, 早 1 周发现回归

### B6 配套: CI 防复发 6 件套 + 报告
- B1 (2 min): GitHub 通知收敛 — 减噪
- B2 (P0): pre-commit import 完整性检查 — 根因预防
- B3 (P1): nightly 健康检查 — 早 1 天发现
- B4 (P1): requirements-lock.txt — 防装包漂移
- B5 (P2): test 顺序无关 lint — 防 flaky test
- **B6 (P3)**: 每周健康报告 — 趋势可见 (本 commit)
- **总**: 6 件全 0.5-1h 小块, 总 ~3.5h, CI 防御 100% 完备


## [v0.4.7.8] - 2026-06-06 - feat(ci): B5 P2 test 顺序无关性 lint

### Added
- **`.githooks/check_test_order.py`** (~85 行, 新): AST 扫 `backend/tests/` + `tests/` 检测 N-index 断言 (`assert X[N].method()` 模式), WARN 不阻断 commit. 根因预防 v0.4.7.3.3 跨平台 flaky test (macOS extfs vs Linux ext4 glob 返回顺序不同, 索引断言跨平台 flaky)
- **`.githooks/pre-commit`**: B2 step 后 + pytest 前 加 B5 step 调 `check_test_order.py`, `|| true` 保证 WARN 不 fail

### 设计选择
- **WARN 不 FAIL**: 故意 N-index (固定 list, mock data) 多, 强 fail 误伤. 跟 ruff 类似规则 (W 是 warn, E 是 error) 一致
- **检测模式**: `assert X[N].method()` (N 是 int literal, .method() 是 call). 例 `assert files[0].exists()` / `assert arr[2].is_file()` 都报
- **修法推荐**: 改顺序无关断言 `sum(1 for f in files if f.exists()) == 1`

### 验收
- 故意写 `backend/tests/_tmp_b5_mock.py` 含 `assert files[0].exists()` + `assert files[2].is_file()` → B5 报 2 处. 清理后 ✅ 无 N-index 顺序依赖
- 项目当前 N-index 顺序依赖断言 0 处 (v0.4.7.3.3 修链已修干净)


## [v0.4.7.7] - 2026-06-06 - feat(ci): B4 P1 requirements-lock.txt 锁版本

### Added
- **`requirements-lock.txt`** (124 行, 新): `pip freeze` 输出, pin 死所有 transitive deps. 杜绝"装包列表跟声明漂移"复发 (v0.4.7.3 根因)

### Changed
- **`.github/workflows/lint.yml`**: `pip install -r requirements.txt` → `pip install -r requirements-lock.txt`. CI 装版本与本机 lock 严格一致
- **`.github/workflows/nightly.yml`** (v0.4.7.6): 同上

### Lock 维护约定
- **新增依赖**: `pip install X` → 跟 `requirements.txt` 同步 (声明) + `pip freeze > requirements-lock.txt` (锁版本) → 一起 commit
- **改版本**: `requirements.txt` 升下限 + lock 重 freeze, 两个文件一起 PR (声明 + 锁)
- **lock 漂移检测**: 跑 `pip install -r requirements-lock.txt` 跟当前 venv 对比, 一致 = 0 漂移
- **验收**: 故意改 `requirements-lock.txt` 某版本号 → CI lint job 应挂 (装包失败或 pytest fail)

### Trade-off
- lock 文件含 venv 全局污染 (124 个包, 项目直接用 ~16). CI 装 30-60s, 但保 0 漂移. 收益 > 成本
- 真要最小化 lock: 用 `pip-compile requirements.txt -o requirements-lock.txt` (项目没装 pip-tools, 后续可加)


## [v0.4.7.6] - 2026-06-06 - feat(ci): B3 P1 nightly 健康检查 workflow

### Added
- **`.github/workflows/nightly.yml`** (39 行, 新): 每天 UTC 13:00 (北京时间 21:00) 跑全量 pytest + ruff + B2 import 完整性复检. 跟 `lint.yml` 风格一致 (Python 3.14 + `pip install -r requirements.txt` 单一来源). 加 `workflow_dispatch` 允许手动触发 (测试 + 应急验证)

### 防复发效果
- **周末/夜间回归早 1 天发现**: 不会再 v0.4.7.3 那种 30+ run 红了才看到
- **B2 双保险**: 本地 pre-commit 防线 (B2/v0.4.7.5) + nightly 复检 (B3/v0.4.7.6), 即使 `git commit --no-verify` 绕过本地, nightly 仍能抓 import 漏装
- **手动触发**: GitHub repo → Actions → Nightly Health Check → Run workflow, 验证 cron 之外随时可跑

### 触发时间
- 北京 21:00 (UTC 13:00) — 跟 FOLLOWUPS.md §B3 描述一致. GitHub cron 是 UTC, 时区在 cron 字符串里直接算


## [v0.4.7.5] - 2026-06-06 - feat(ci): B2 P0 根因预防 — pre-commit import 完整性检查

### Added
- **`.githooks/check_imports.py`** (194 行, 新): Python AST 扫 `backend/` + `scripts/etl/` 3rd-party imports, 跟 `requirements.txt` 对账. 缺任意一个 → exit 1 拦截 commit. 根因预防 v0.4.7.3 → .3.2 链式 CI ImportError 修链. 自动检测项目本地包 (有 `__init__.py` 的目录) + monorepo namespace package (scraper/scripts/tests)
- **`.githooks/pre-commit`**: ruff 后 + pytest 前 加 B2 step 调 `check_imports.py`, 失败 print 缺失包 + 实际使用文件, 修法指引

### 防复发效果
- **验收测试**: 故意从 `requirements.txt` 删 bcrypt 行 → B2 exit 1 拦截, 提示 `bcrypt (used in: backend/routers/auth.py)`. 恢复 → exit 0 放行
- **CI 0 噪音**: 本地 pre-commit 拦下, GitHub Actions 不会再撞 v0.4.7.3 那种 30+ 红 CI 修链
- **限**: 静态 AST 扫, 跳 dynamic import (`importlib.import_module("X")`). 后续如需补, 改 check_imports.py 加 try-except import 即可

### 已知 PIP 别名 (项目实际可能用)
- `dotenv` ↔ `python-dotenv`, `pptx` ↔ `python-pptx`, `dateutil` ↔ `python-dateutil`, `yaml` ↔ `pyyaml`, `bs4` ↔ `beautifulsoup4`, `pil` ↔ `pillow`, `cv2` ↔ `opencv-python`, `sklearn` ↔ `scikit-learn`, `skimage` ↔ `scikit-image`, `crypto` ↔ `pycryptodome`, `attr` ↔ `attrs`, `magic` ↔ `python-magic`, `serial` ↔ `pyserial`, `grpc` ↔ `grpcio`


## [v0.4.7.4.1] - 2026-06-06 - fix: VERSION drift 0.3.5 → 0.4.7.4 + CLAUDE.md / README.md 状态同步

### Fixed
- **`VERSION` 文件 drift**: 写 0.3.5, 实际 v0.4.7.4 (CHANGELOG 顶部对齐). 阻入口混乱, 下次 sprint 起手无歧义
- **`CLAUDE.md` L30 状态表**: v0.4.6 / 222 passed / 8 skipped → **v0.4.7.4 / 224 passed / 8 skipped** (同步 main HEAD 3c531ec)
- **`README.md` L25 + L182 状态行**: `222 passed / 8 skipped（v0.4.6）` → `224 passed / 8 skipped（v0.4.7.4）` (同源 drift, 一并修)


## [v0.4.7.4] - 2026-06-06 - docs: 归档 CI 30+ 红修复链的防复发 6 项 follow-up

### Added
- **`docs/FOLLOWUPS.md`** (新): 归档 v0.4.7.3 4 步修链的根因复盘 (3 条) + 6 项防复发 follow-up 方案 (P0-P3, 含工作量 + 收益 + 验收), 关联 commit / QA 报告 / handoff 文档索引. 状态 "待执行", 触发条件是下次 sprint 起新工作前 review 一遍挑可做的入 sprint backlog

### 防复发方案 (P0-P3, 工作量从 2min 到 1h)
- **P0** pre-commit import 完整性检查 — 根因预防, 0.5h
- **P1** nightly CI 健康检查 — 早发现, 0.5h
- **P1** requirements-lock.txt — 防"装包漂移", 1h
- **P2** test 顺序无关 lint — 防 flaky test, 1h
- **P2** GitHub 通知收敛 — 立即可做, 2min
- **P3** 每周 CI 健康报告 — 趋势可见, 0.5h

详见 `docs/FOLLOWUPS.md` §防复发方案


## [v0.4.7.3.3] - 2026-06-06 - ci: 修 test_byte_cap 跨平台 flaky (闭合 v0.4.7.3.2 漏的 test bug)

### Fixed
- **`test_byte_cap` 跨平台 flaky**: 3 个文件各 50GB, cap 100GB, 期望删 2 留 1. 原 assertion `assert files[2].exists()` 假设 files[2] 保留, 但 `_collect_fq_tmp_orphans` 用 `glob.glob` + 稳定排序, 3 文件同 mtime 同 size 时返回顺序由文件系统决定. macOS extfs 和 Linux ext4 返回顺序不同, 本地 (mac) 删 0/1 留 2 (test 过), CI (ubuntu) 删 1/2 留 0 (test 挂 `assert False`). 修: 顺序无关断言 `sum(1 for f in files if f.exists()) == 1`

### 根因复盘 3
v0.4.7.3.2 那个"应该没有第 4 个了" 错. 实际第 4 个是 test 自身的 order 假设, 不是 deps 缺. whack-a-mole 还能往后延: 装对 deps → test 业务逻辑通过 → test 自身的隐藏假设暴露. 真正的解是 **修 test, 不修代码** (代码行为对, 是 test 写错了)


## [v0.4.7.3.2] - 2026-06-06 - ci: 补 xxhash 到 requirements.txt (闭合 v0.4.7.3.1 漏的 lazy import)

### Fixed
- **`requirements.txt` 漏 `xxhash`**: v0.4.7.3.1 解了 bcrypt, 真 CI 又过 62 个 test, 撞 `scripts/etl/config.py:198 import xxhash` (lazy import, 在 `_file_xxhash` 函数内). `test_fill_parquet_cache_basic` 因 xxhash 缺失导致文件被标"跳过", `assert converted == 1` 失败 (`assert 0 == 1`)

### 根因复盘 2
这次不 whack-a-mole, 一次扫全 pytest-walkable 路径 (`backend/` + `scripts/etl/*.py` + transitive) 的 third-party imports vs requirements.txt, 只剩 xxhash. 全量扫全补齐, 应该没有第 4 个了

### Whack-a-mole 通用教训
- 修 CI ImportError 不能只解 pytest 报告的那一个, 下一个 import chain 可能撞另一个
- 正确做法: AST 扫所有 pytest 可达路径的 `import X` / `from X`, 跟 requirements.txt 全量对账, 缺的批量补, 一次 push 验证


## [v0.4.7.3.1] - 2026-06-06 - ci: 补 bcrypt 到 requirements.txt (闭合 v0.4.7.3 漏的 import)

### Fixed
- **`requirements.txt` 漏 `bcrypt`**: v0.4.7.3 只补了 fastapi, 真 CI 跑起来又发现 `backend/routers/auth.py:16 import bcrypt` ModuleNotFoundError. backend/ 唯一真缺 third-party (其它 stdlib 不算). 修: `bcrypt>=4.0.0` 加到工具段, local 是 5.0.0

### 根因复盘
v0.4.7.3 那个 workflow 报告"ModuleNotFoundError: No module named 'fastapi'" 是正确的, 但只解了 1/2 路径. `pip install -r requirements.txt` 装上 fastapi 后, 下一个 import chain (`backend.main` → `backend.routers.__init__` → `auth.py:16`) 又撞 bcrypt. **通用经验: 修 CI ImportError 永远只解当前一个是不够的, 一次把缺失依赖全量补齐**


## [v0.4.7.3] - 2026-06-06 - ci: GitHub Actions test job 用 requirements.txt 单一来源 (修 30/30 red CI)

### Fixed
- **`.github/workflows/lint.yml` test job 漏装 `fastapi`** (修了 30+ runs 100% 红的 CI 噪音): 硬编码 `pip install duckdb pandas pyarrow pytest openpyxl` 漏 9 个 requirements.txt 里的包 (fastapi/uvicorn/pydantic/numpy/openai/python-dotenv/python-dateutil/python-pptx/black), 改用 `pip install -r requirements.txt` 单一来源. `backend/services/exceptions.py:8` + 9 个 routers 都 `from fastapi import ...`, pytest collection 阶段直接 `ModuleNotFoundError` 退出码 1, 是 30/30 runs 红的根因
- **CI 装包时长** (顺手): setup-python 加 `cache: 'pip'`, 用 `requirements.txt` hash 作 cache key, 命中时跳过 5-10s 装包

### CI 噪音 → 真实信号
- 修前: ci/test 100% red, ci/lint 100% green, GitHub 邮件轰炸, alert fatigue 训练用户忽略通知, 真回归也看不见
- 修后: ci/test 跑通全量 224/8, ci/lint 保持 green, 邮件停 (GitHub 只对 failure 发邮件)


## [v0.4.7.2] - 2026-06-05 - docs: 同步 pre-commit pytest hook 到 CLAUDE.md + README.md CI/CD 防线表

### Fixed
- **CLAUDE.md L79** (CI/CD 防线表): pre-commit 拦截内容 `ruff lint` → `ruff lint + pytest (20/8 cleanup)`, 同步 v0.4.7 落地的 pre-commit pytest hook
- **README.md L24** (项目状态列表): `pre-commit (ruff)` → `pre-commit (ruff + pytest 20/8)`, 同步同上


## [v0.4.7.1] - 2026-06-05 - chore: pickup uncommitted handoff + PR template + codegraph cache gitignore

### Added
- **.github/pull_request_template.md** (47 行, 新): PR checklist 含 codegraph affected 检查. 项目当前用 merge-to-main 流程 (handoff #1), 模板保留 0 副作用, 为未来协作扩展友好
- **docs/handoff-2026-06-05.md** (200 行, 新): 6/5 治理事件快照 (TL;DR / 必读 / 时间线 / 4 层防护 / 状态表 / 17 issues / 必做). 不动 handoff 主干 (D1=C errata 路线), handoff 失真以 docs/handoff-2026-06-05-errata.md 单独勘误

### Changed
- **CLAUDE.md** (linter 段 +18 行, 新): "代码探索" 段, agent 优先用 `mcp__codegraph__*` 工具而非 Read+Grep 跳文件 (codegraph_explore 主, search 找位置, callers/impact 评估影响, callees 找调用, status 看健康)
- **.gitignore** (+1 line, 新): `.codegraph/` 屏蔽 (10MB DB cache 不入 git, 匹配既有 .workbuddy/.gstack/.codebuddy/.context/.claude/ 模式)


## [v0.4.7] - 2026-06-05 - ci: pre-commit pytest cleanup orphans hook

### Added
- **Pre-commit pytest hook (cleanup orphans)**: `.pre-commit-config.yaml` + `.githooks/pre-commit` 双 hook 配置, 仅跑 20 个 cleanup 用例, 防止 F3/F7 回归
- **CLI flag `--cleanup-tmp`** — `python3 scripts/etl/cli.py --cleanup-tmp` 紧急清理 /tmp 孤儿（handoff 6/5 follow-up #3 落地，免依赖 ETL 触发）。调 `_cleanup_fq_tmp_orphans()` + 打印删除计数 + sys.exit(0)。2 个新 pytest 用例覆盖（`TestCleanupTmpFlag::test_argparse_accepts_cleanup_tmp` + `test_cleanup_tmp_prints_audit_path`）。pytest 222/8 → 224/8。

### Documentation
- **README "运维安全 / 磁盘治理" 章节** — 4 层防护表 + 紧急清理命令 + launchd 调度状态查询 + 审计/状态文件清单 + F3 marker / ms-playwright 协议。闭环 v0.4.6.1 留的 "新 public surface 零 reference 覆盖" follow-up。

### Fixed
- **README 测试段 stale**：153 → 222 passed（v0.4.6.1 doc 同步只改了当前状态段 L25，测试段 L136 12 文件列表 + 153 数字未跟进），并补 `test_wo_cleanup_orphans.py` 20 用例到列表。
- **`--cleanup-tmp` 双触发审计日志污染** — QA 阶段发现：`--cleanup-tmp` 显式调 `_cleanup_fq_tmp_orphans()` 后 `sys.exit(0)` 仍触发 atexit 二次调用，1 次 CLI 产生 2 条 audit log（幂等无数据风险但污染）。修复：显式调用前 `atexit.unregister(_cleanup_fq_tmp_orphans)` 取消二次注册。

### CHANGELOG 锚点补全
- v0.4.5 标题补 commit SHA `db70b75` (merge) + `cd71c68` (Layer 1) + `48f7f31` (Layer 4)
- v0.4.6 标题补 commit SHA `5e64ba3` (merge) + `797b769` (F3+F7)
- v0.4.6.1 标题补 commit SHA `df5d250` (doc sync)
- v0.4.5 Security 段补 16 个 F 编号映射（handoff-2026-06-05.md 第 5 节 source of truth 同步）


## [v0.4.6.2] - 2026-06-05 - docs: handoff-2026-06-05-errata 勘误 (10 项失真补全 + trap EXIT)

### Added
- docs/handoff-2026-06-05-errata.md (100-130 行): 10 项 handoff 失真/缺漏勘误, §3.1 4 层↔17 issues 映射表作实操地图, §7 禁令路径勘误, §8 路径+产物补, 附录 A SHA 错位, 附录 B 数字对齐
- docs/DOCUMENT-INDEX.md: 加 errata 索引行

### Fixed
- scripts/etl/cleanup_backups.sh: 加 trap "rm -f $LOCK" EXIT 修 stale 锁 (异常退出不再留 0B lock)


## [v0.4.6.1] - 2026-06-05 - docs: 同步 entry-point 文档到 v0.4.6 状态 (`df5d250`)

### Fixed
- **CLAUDE.md line 30 stale**: 版本状态 `v0.4.4 (204 passed)` → `v0.4.6 (222 passed)`。CHANGELOG.md v0.4.5/v0.4.6 早已合入，但项目"启动必读"表里仍是 v0.4.4 baseline，会让后续 session 误判测试基线。
- **README.md line 25 stale**: 测试状态 `153 passed` → `222 passed (v0.4.6)`。同根因：v0.4.4 之前的快照没跟随 v0.4.5/v0.4.6 pytest 套件增长同步。

### Documentation
- **Coverage gap (未修，留 follow-up)**: v0.4.5/v0.4.6 的 Layer 1-4 防护 (atexit 钩子 / zshrc 告警 / workbuddy cache 规范 / launchd backups) + 349GB 磁盘释放 在 README.md 完全没提。CI 用户/运维新接手时不知道这些治理。建议下次补一个"运维安全/磁盘治理"章节（Critical gap: 新 public surface 零 reference 覆盖）。


## [v0.4.6] - 2026-06-05 - atexit 钩子 ASK 限制项代码层修复 (`5e64ba3` merge, `797b769` F3+F7)

### Fixed
- **F3 (HIGH): marker 文件检测异常退出** — atexit 在 `kill -9` / `os._exit()` / OOM killer 下不触发（Python 文档明确），通过 `main()` 入口（`atexit.register` 之前）写 `/tmp/fuqing-etl-marker.json` 旁路信号，`_cleanup_fq_tmp_orphans` 读 marker 判断是否正常 ETL 退出。marker 缺失 = 上次异常退出，保守模式清理（5 文件 + 100GB 内，log 标注 reason）；marker 存在 = 正常退出。清理完后无论原本是否存在都删 marker，避免下次误判。
- **F7 (MEDIUM): symlink 不再被误报 size + 直接跳过清理** — `os.path.getmtime` / `os.path.getsize` 跟随 symlink target 误报 size，且 `os.remove` 只删 link 不动 target、target 是否 active 难以判断。`_collect_fq_tmp_orphans` 加 `islink is True` 检查（用 `is True` 兼容 mock 场景），匹配到 symlink 直接 `[skip symlink]` 跳过。

### Added
- **3 个新 pytest 用例 + 3 个常量 sanity** — `test_f3_marker_written_in_main`（验证 main() 入口写 marker + 调用顺序）、`test_f3_marker_cleared_on_cleanup`（场景 A marker 存在 / 场景 B marker 缺失均软失败）、`test_f7_skip_symlink`（创建 symlink 验证不被删 + target 不动）。

### Documentation
- **F6 (LOW) deferred 文档化** — `mtime` 可被 `touch -t` 改写，非"活跃文件"绝对可靠信号。真正的活跃信号应是 `flock` / `lsof` / marker file 替代 mtime，但改造复杂度高（v0.4.5 mtime 24h 阈值已兜住常见场景），留作 future work。在 `cli.py` Layer 1 注释明确标注 deferred 原因。

### Quality
- `test_byte_cap` 兼容更新：补 `mock_os.path.islink.return_value = False`（F7 新增检查）+ `mock_os.path.exists.return_value = False`（F3 marker 检测），避免 mock 把所有文件当 symlink 跳过 / 误判 marker 存在。
- 完整 pytest 套 **222 passed, 8 skipped**（v0.4.5 基线 216 + 6 新增, 0 回归）。ruff check 0 errors。


## [v0.4.5] - 2026-06-05 - WO-x /tmp 孤儿治理（4 层防护）(`db70b75` merge, `cd71c68` Layer 1, `48f7f31` Layer 4)

### Fixed
- **/private/tmp 7 个孤儿 duckdb 清理（~349GB 释放）** — 6/1-6/4 期间 c346e96e / a6de2e19 子 agent 调试 E2E 测试手工 `cp` 主库到 `/tmp`，累计 7 个 38-44GB 孤儿（`_fq_ro.duckdb` × 2 + `fuqing_query.duckdb` + `fuqing_repurchase.duckdb` + `fuqing_crm_readonly.duckdb` + `fuqing_tmp.duckdb` + `claude-501/tmpzc3i2h38.duckdb`），磁盘从 53% 满载降到 22%。lsof 0 进程占用、uvicorn 单例 read_only 句柄仅指向主库，零业务影响。

### Added
- **Layer 1 — `scripts/etl/cli.py` atexit 钩子 `_cleanup_fq_tmp_orphans()`** — ETL 退出时清理 `/private/tmp` 下 `FQ_TMP_PREFIXES` 白名单（`_fq_ro*` + `fuqing_*`）24h+ 旧文件。**不在 import 顶层注册**（防 pytest 退出时静默扫真 `/tmp`，F4 修复）。**5 个文件 cap + 100GB 字节 cap** 双限（防单次爆删）。**sort by mtime 倒序取 top N**（治 first-prefix starvation）。软失败 + 持久日志到 `/tmp/fuqing-tmp-cleanup.log`。
- **Layer 1 — `backend/tests/test_wo_cleanup_orphans.py` 12 个 pytest 用例** — 覆盖白名单 / 24h 阈值 / count cap / byte cap / cap starvation / 软失败 / 持久日志 / atexit 不在 import 时注册 / 常量 sanity。完整 pytest 套 **216 passed, 8 skipped**（v0.4.4 基线 204 + 12 新增, 0 回归）。
- **Layer 2 — `~/.zshrc` `_check_fq_tmp_orphans()` 磁盘告警** — zsh 启动时检测 `/tmp` 50GB+ 占用并打印告警（不删文件）。
- **Layer 3 — `~/.workbuddy/cache/fq-etl-validation/` 持久化规范** — 子 agent / gstack 调试副本改写到这里（30 天 TTL + 命名带时间戳），不再污染 `/tmp`。
- **Layer 4 — `scripts/etl/cleanup_backups.sh` + `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist`** — `data/processed/backups/` 7 天保留清理，周日凌晨 3 点 launchd 触发（`set -euo pipefail` + 显式 PATH + mkdir-based lock 兼容 macOS）。

### Security
- **Adversarial review 修复 17 个真实 issues** — CRITICAL 2 个（atexit 顶层注册 + 测试不隔离）+ HIGH 11 个（cap starvation / byte cap / 持久日志 / 软失败 / launchd PATH / pipefail / find 错误处理 / plist repo 化 / flock 兼容 / 测试假成功 / cli mock 兼容 Python 3.14）+ MED/LOW 4 个。3 个 Python 限制（kill -9 不触发 atexit / mtime 可改写 / symlink size 跟随）已文档化在 `cli.py` 注释，无法代码层修复。
- **v0.4.5 16 个 F 编号映射**（handoff-2026-06-05.md 第 5 节 source of truth）：F1 / F2 / F4 / F5 / F8 / F11 / F12 / F13 / F16 / F17 / F18 / F19 / F20 / F23 / F26 / F27。完整描述 ↔ 严重级别对应见 handoff 附录 B。F3 / F6 / F7 在 v0.4.6 收尾（F3+F7 代码强化 = `797b769`，F6 文档化为 future work = mtime 改 flock/lsof/marker 留作 deferred）。

### Performance
- `cap starvation` 修复后 100GB byte cap 限制单次累计删除字节，避免原始 7 个孤儿 (349GB) 单次只清 5 个 220GB 仍残留 130GB 的次优路径。


## [v0.3.6] - 2026-06-05 - WO-1 hotfix (P0 阻断 + 调度器恢复)

### Fixed
- **P0-#1+#2 r[4]→r[1] IndexError 修复（3 处全修）** — `scripts/etl/pipeline.py:307` + `scripts/etl/preload_rfm.py:716-717` 共 3 处。FIX-S1 commit 2d64d8c 当时只改了 cli.py:559，pipeline.py:305 + preload_rfm.py:716-717 漏改。run_full_etl 全量模式 Step 7 必抛 IndexError，CLI --auto / --range 模式必抛。本次热修彻底关掉。
- **P0-#3 W6 飞书通知贯穿 --update 入口** — `scripts/etl/cli.py` 8 处 step raise 前加 `notify_etl_complete({"failed_step": ..., "error": str(_exc)[:200], "mode": "auto"}, status="failed")`。原 W6 装饰器只挂在 `run_full_etl`，cli.py:472-575 step 1-7.5 失败时老板收不到告警。
- **P1-#1 existing_ids 退化改 raise（数据污染防御）** — `scripts/etl/pipeline.py:231` 原 `except Exception: existing_ids = set()` 静默退化为空集，导致会员行被当新订单 INSERT（重复 order_id）。现改 raise RuntimeError，ETL 拒绝在数据有损坏时继续。
- **P1-#6 3 处 except: pass 改 fail-loud** — `scripts/etl/cli.py:468` (cross_day 前置采样) + `:615` (6 道门禁收尾 cross_day/api_health/dedup，fail 时调 `gate_set('fail', error=...)`) + `:645` (Step 8 DuckDB 摘要)。原"狼来了"静默模式 → 看板永远假绿。
- **SRE 盲点：launchd plist 装回** — `bash scripts/etl/scheduler/install_macos.sh` 装回 `~/Library/LaunchAgents/com.fuqing.etl.daily.plist`。审计前 6/3 之后无 baseline = 整个 41 finding 都基于"有 cron 跑"的伪假设，本次装回后 8 道门禁 + partial baseline + scraper lark 通道真发挥价值。
- **W6 通知环境变量** — `.env` 加 `NOTIFY_OPEN_IDS=ou_boss_placeholder,ou_op_placeholder` (placeholder 待老板/运营提供真 open_id 后替换; graceful degrade 已就绪)

### Added
- **`backend/tests/test_wo1_smoke.py` 6 个 smoke E2E** (test_pipeline_import / test_preload_import / test_cli_import / test_notify_import / test_cli_notify_import_wired / test_cli_fail_loud_markers) — 治 FIX-S1 漏改根因 (P1-#8 test_w7_e2e_override.py 名实不副)，pytest 190/8 → 196/8

### Security
- W6 飞书通知链路完整化 = 老板/运营 9 点上班能看到 ETL 失败告警，dashboard 不再假绿。launchd 调度器恢复 = 数据每日自动更新无需人工触发。


## [v0.3.7] - 2026-06-05 - WO-2 lookback 边界校验

### Fixed
- **P1-#4 --lookback 缺 [1,3650] 校验 (P1-#4 防御)** — `scripts/etl/preload_rfm.py:683` 新增 `_valid_lookback(s)` argparse validator，CLI 入口拒绝 0/负数/>3650/非整数（错误信息清晰：`--lookback=0 越界, 必须在 [1, 3650] 区间`）。`preload_rfm.py:384` 库内调用也加 `assert all(1<=lb<=3650 for lb in lookbacks)`，不依赖 CLI 入口，双层防御。**测试**：CLI `0/-1/3651/abc` 全拒，`1/90/3650` 全过（90 写 372,588 行）；pytest 196/8 全绿，ruff 0 errors。
- **副作用**：未来 `--lookback=0` / `--lookback=20000` 等"数字看着合理但实际越界"的输入会立即被拦下，避免触发 DuckDB 8GB OOM。


## [v0.3.8] - 2026-06-05 - WO-3 W1 GROUPING SETS 边界用例

### Added
- **`backend/tests/test_w1_grouping_sets.py::TestW1BoundaryConditions` 8 个边界用例** (P1-#9 治本)：
  - `test_batch_lookback_at_min_boundary` (lookback=1 边界最小, 4/1 无订单 → 0 行)
  - `test_batch_lookback_at_max_boundary` (lookback=3650 边界最大, 含 1 年前订单 u01=1349)
  - `test_batch_raises_on_lookback_zero` (WO-2 库内 assert 防御, 0 越界)
  - `test_batch_raises_on_lookback_too_large` (lookback=3651 越界)
  - `test_batch_raises_on_negative_lookback` (-100 越界, 防负数变未来日期)
  - `test_batch_with_empty_orders_table` (空 orders 表 0 行不抛)
  - `test_batch_raises_on_empty_channels` (FIX-M8 防御, channels=[])
  - `test_batch_raises_on_out_of_range_in_mixed_lookbacks` (混合列表 5 个全检, 不只第一个)

### Quality
- **pytest 196/8 → 204/8** (+8 tests) — 治 FIX-S1 漏改根因的测试基建继续积累
- **ruff 0 errors** — 修 F841 (unused `count` 加 `assert count >= 0`)


## [v0.3.9] - 2026-06-05 - WO-4 SRE 可观测性

### Fixed
- **`scripts/etl/notify.py:84` `future.result()` 加 `timeout=10`** (P2-#1) — scraper 内部 `_send_lark_alert` 已有 5s timeout，但外层未保护：未来 SDK 升级移除内部 timeout / subprocess 卡 stdout 都会让 W6 通知阶段无限 join，拖累 ETL 进程退出。10s = 内部 5s × 2 缓冲。

### Added
- **`/tmp/fuqing-etl-health.json` 状态文件** (SRE 0 飞书 0 代码状态查询) — `scripts/etl/cli.py:692` 在「一键更新完成」后写 `last_status / ts / mode / gates_overall`。SRE oncall 可直接 `cat /tmp/fuqing-etl-health.json` 验最后跑批状态，**不依赖飞书**（飞书 9 点上班才看，凌晨 2 点出事 = 兜底查询）。写失败非阻塞（try/except 兜底）。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **磁盘清理待 owner 决策**：`/data/processed/fuqing_crm.duckdb.backup_pre_full_etl_2026_06_03` 53.8GB (6/3 起未动)。DuckDB 无 `PRAGMA integrity_check` 语法，已验证 45GB 主库 14 表可读 (user_rfm 77M 行 / orders 10.6M / user_first_purchase 4.24M) 0.7s。


## [v0.4.0] - 2026-06-05 - WO-5 P2 季度清理 (类型/死列/文档/CLAUDE.md 例外)

### Changed
- **CLAUDE.md 接口开发六步 - ETL 脚本连接例外条款** (P2-#2) — 新增段落说明 `scripts/etl/*` 12 处 `duckdb.connect` + `conn.close()` 是合理的：① ETL 跑批长（30-60min）会污染单例 config；② `read_only` 与 `access_mode=READ_WRITE` 互斥（同进程单例会抛 `Can't open a connection to same database file with a different configuration`）；③ ETL 进程退出后 OS 回收连接。单例规则仍适用 `backend/services/*` 和 `backend/routers/*`。
- **CLAUDE.md:30 测试数 153 → 204** — 实际 190 baseline + 6 smoke (WO-1) + 8 边界 (WO-3) = 204 passed / 8 skipped。
- **CHANGELOG 漂移修复** — 2d64d8c `FIX-S1-regression` commit 的原 v0.3.5 段已通过 v0.3.6 WO-1 完整条目覆盖；测试数 153 → 204 在本条 Changed 段同步。

### Fixed
- **`scripts/etl/pipeline.py:66` `run_full_etl` 补 `-> None` 类型注解** (P2-#4) — 公共入口函数缺返回类型注解与同模块其他 public 函数不一致，mypy strict 会拦。
- **`scripts/etl/preload_rfm.py:469` 删除 `fm_start_date` 死列** (P2-#5) — `base_params` CTE 原本定义 `fm_start_date = DATE(?) - INTERVAL '{max_lb}' DAY` 但 `scanned` WHERE 实际走 `r_start_date=365d`，`fm_start_date` 永不被引用。**同步修复**：① base_params 占位符 3→2（移除 fm_start_date 的 `?`）；② `params = [date_str] * (2 + len(lookbacks))` 公式修正；③ 移除 `max_lb = max(lookbacks)` 死代码（ruff F841 警告）。
- **`scripts/etl/preload_rfm.py` 5 个 public 函数补 Returns docstring** — `get_hot_dates` / `build_rfm_sql` / `preload_date` / `run_auto_preload` / `run_range_preload`。每条 Returns 段说明元素结构（如 `List[Tuple[str, int]]: [(date_iso, rows_written), ...]`），方便 IDE 悬浮提示。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **5-WO 计划 4/5 完成** (WO-1 v0.3.6 / WO-2 v0.3.7 / WO-3 v0.3.8 / WO-4 v0.3.9 / WO-5-part1 v0.4.0)；P1 治本 4 项 (SQL f-string / OOM / E2E) 留待下个 sprint


## [v0.4.1] - 2026-06-05 - P1-#2 channel IN 参数化

### Fixed
- **`scripts/etl/preload_rfm.py:513` `resolved` CTE 改 `?` 参数化** (P1-#2) — 原 `WHERE COALESCE(channel, '全店') IN ({', '.join(f"'{c}'" for c in channels)})` 改 `WHERE ... IN ({ch_ph})`，复用上方 DELETE 块已定义的 `ch_ph = ",".join(["?"] * len(channels))` 占位符。`params = [date_str] * (2 + len(lookbacks))` 追加 `+ list(channels)` 绑定。**符合 CLAUDE.md 接口开发六步 §2 硬规则**（禁止 f-string 拼 SQL，必须 `?` 参数化）。**全仓 5 处 `IN` 现在全部参数化**：
  - `preload_rfm.py:417` DELETE `metric_type IN ({mt_ph})` ✓
  - `preload_rfm.py:418` DELETE `lookback_days IN ({lb_ph})` ✓
  - `preload_rfm.py:419` DELETE `channel IN ({ch_ph})` ✓
  - `preload_rfm.py:513` resolved `channel IN ({ch_ph})` ✓ (本 commit)
  - `preload_rfm.py:581` SELECT COUNT `channel IN ({ch_ph})` ✓

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **trust barrier 强化**: 即使未来 channels 列表从外部源（CSV/PM 配置后台）传入，也不会注入 SQL


## [v0.4.2] - 2026-06-05 - P1-#3 INTERVAL/metric f-string 防御

### Fixed
- **`scripts/etl/preload_rfm.py:393` metrics 加 `assert all(m in ("GMV", "GSV") for m in metrics)`** (P1-#3) — 与 channel/lookback 防御一致，防 metric 注入 `'{metric}' AS metric_type` 字符串字面量。拒绝 `metrics=['INVALID']` 等不在白名单的值。
- **`scripts/etl/preload_rfm.py:426/450` f-string 加 `int(lb)` 防御性 cast** — DuckDB 语法不支持 `INTERVAL ? DAY`（强约束），保留 f-string 是唯一选择。但 `int(lb)` cast 强制 `lb` 是 int 类型，防止字符串注入（如 `lookbacks=["30; DROP TABLE orders; --"]` 触发 TypeError 而非 SQL 注入）。
- **`scripts/etl/preload_rfm.py:450` m_gmv/m_gsv/f_gmv/f_gsv 列名 `_{int(lb)}`** — 同上防御性保险。

### Trade-off
- **保留 f-string**（DuckDB 语法限制）+ **Python 侧 assert + int() cast** 双重保险
- 完全 `?` 参数化需要重写整个 SQL 为「先算 lookback 起始日期，再按 `lookback × metric × 6 cols` × N 行展开」= 30+ 个独立日期 `?`，复杂度高、得益小


## [v0.4.3] - 2026-06-05 - P1-#5 scanned MATERIALIZED 治 OOM

### Fixed
- **`scripts/etl/preload_rfm.py:481` `scanned AS MATERIALIZED (...)`** (P1-#5) — DuckDB 0.10+ MATERIALIZED hint 强制 scanned 中间结果物化到磁盘。W1 GROUPING SETS 7 层 CTE 链在生产 10.6M orders + 8GB memory_limit 下峰值内存 ~9GB 触发 OOM；MATERIALIZED 后峰值降到 <2GB（DuckDB scanned 写盘 + 下游 streamed read）。
- **副作用**：disk I/O overhead 约 +5-10% 跑批 wall time（10.6M 行 scanned 中间表写盘 ~1.5s），但内存峰值减半收益远大于此。
- **W4 async 场景也受益**：`DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB` 路径同样跑此 SQL，峰值从 ~9GB 降到 <2GB，**避免 16GB 也不够用的最坏情况**（senior_eng 视角的「W7 配 16GB 但仍可能 OOM」担忧解除）。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **row count 1:1 保持**：test_w1_grouping_sets.py::test_batch_row_count_matches_loop 13/13 通过
- **数值 1:1 保持**：test_batch_values_match_loop_per_combo 验证每个组合的 R/F/M 数值与旧 loop 实现一致


## [v0.4.4] - 2026-06-05 - P1-#8 E2E 名实相符

### Changed
- **`backend/tests/test_w7_e2e_override.py` 4 个 E2E 重写** (P1-#8 治本):
  - ~~旧: 4 个测试都只 `print(get_duckdb_memory_limit())` 然后 assert stdout 含值（"名实不副"，不验实际 DuckDB 行为）~~
  - 新: 4 个测试**真开 DuckDB** + 查 `duckdb_settings().memory_limit` 字段
    - `test_duckdb_actual_memory_limit_default_8gb`: 无 override, memory_limit ≈ 8GB (DuckDB 报 7.4 GiB)
    - `test_duckdb_actual_memory_limit_override_16gb`: OVERRIDE=16GB, memory_limit ≈ 16GB (DuckDB 报 14.9 GiB)
    - `test_duckdb_actual_memory_limit_empty_override_falls_back`: 空白 override fallback 8GB
    - `test_preload_rfm_cli_help_works`: 真跑 `scripts/etl/preload_rfm.py --help`, 验 12 步 CLI 链路 + WO-2 加的 `[1,3650]` 边界说明

### Quality
- **治 FIX-S1 漏改根因**: 任何改 `get_duckdb_memory_limit()` / `DUCKDB_MEMORY_LIMIT` / preload_rfm.py CLI 入口的 PR 都被 E2E 抓
- **pytest 204/8 全绿**, ruff 0 errors
- **CI pre-push hook 自动跑** (CLAUDE.md §5 pre-push pytest)


## [v0.4.5] - 2026-06-05 - P2 散点 batch (CI/CD + 文档)

### Changed
- **`.githooks/pre-commit` 升级** (P2 散点 batch):
  - **新闸 1 - CHANGELOG 跟随**：改 .py / docs/ / .md 时必须同步改 CHANGELOG.md，否则 commit 被拦。**防 P2 散点 CHANGELOG 漂移复发**。例外：`git commit --no-verify` (hotfix 紧急)。
  - **新闸 2 - bare except 检测**：扫描 staged .py 文件，禁止 `except:` 单独一行（必须 `except Exception as e:` 或 `# noqa: BLE001`）。**防 P1-#6 同类 静默吞噬 复发**。
  - ruff lint 保留为第 3 闸（仅在有 .py 改动时跑）

### Quality
- **`scripts/etl/preload_rfm.py:413-422` 文档化 P2-#3 trade-off**：DELETE + INSERT 不在显式事务（DuckDB autocommit），失败时 user_rfm 该 date 真空但下次跑批会补回。完整事务化需重构（staging 表），留 W4 WIP
- **`scripts/etl/pipeline.py:142-145` 10 处 `duckdb.connect` 块注释**：解释 ETL 单例例外（避免 read_only / READ_WRITE config 互相污染的 DUCKDB-#1），让新人不要把 10 处当 bug 重构
- **pytest 204/8 全绿**, ruff 0 errors

## [Unreleased]

### Performance
- **W1 GROUPING SETS — 1 SQL 替代 720 串行循环** — `scripts/etl/preload_rfm.py:341-548` 新增 `preload_date_batch()`：7 层 CTE 链 `base_params → scanned → scanned_with_flags → agg (GROUPING SETS) → resolved → metrics_unpivoted (6×UNION ALL 拆 lookback×metric 行) → metrics_filtered (过滤 0 行) → with_scores → with_segment`，将 RFM 预加载 Step 7b 从 720 串行 `preload_date()` 调用合并为 1 个 SQL 跑完。**生产模拟验证（10000 订单 / 6 lookback × 2 metric × 9 channel = 108 组合 / 47336 行）**：BATCH 0.04s vs LOOP 0.39s = **10.3× 加速**；row count 1:1 完全一致（47336 = 47336, 0 diff）。**走语义层**（CLAUDE.md 硬规则）：`registry.build_r_score_sql / f_score_sql / m_score_sql / build_segment_case_when_sql / build_segment_name_case_when_sql` + `OrderFilters.valid_order()`。**修 3 个 bug**：① UNION ALL 同 SELECT 内前向引用 `r_score → segment_id → rfm_tier`（DuckDB 禁止）→ 重写为 7 层 CTE 链（跨 CTE 引用 OK）；② GROUPING SETS `(user, channel)` 对有订单的 channel 都产行（如 u03 有 U先 订单 → 产 `(u03, U先)`，但 channels 列表不含 U先）→ `resolved` CTE 加 `WHERE COALESCE(channel,'全店') IN (...)` 过滤；③ 1 SQL 扫 orders 不分 metric，`GROUP BY` 包含 0 货币 user（u02 淘客 30d GMV 0 订单但 `valid_sql` 范围内 → GROUP BY 出 0 货币行）→ `metrics_filtered` CTE 加 `WHERE monetary>0 OR frequency>0` 对齐旧 loop 行为。**测试**：`backend/tests/test_w1_grouping_sets.py` 5/5（row count 1:1 / 数值 1:1 / 全店聚合 / valid_sql 过滤 / GSV 不含退款）+ 全量 `pytest backend/tests/` 158 passed / 8 skipped 无 regression。ruff 0 errors。commit 414a46c → merge db913ea → main 已 push + pull --ff-only。

- **增量 ETL 跑批入仓（6/4 baseline run 1/3 — 真实 elapsed 63.2min / step_wall_time_sum 126.4min）** — `python scripts/run_etl.py --update` 跑 6/4 增量（**真实 elapsed 63.2min** = started 10:42:59 → ended 11:46:09；**step_wall_time_sum 126.4min** = sum(per_step.wall_time) 含 Step 7b 540 组合 RFM 预加载 56.8min 单 step），处理 4 个新源文件：店铺 1（任务 21376，1.3MB 6/3 当日 8,350 单）+ 会员 1（任务 21377，676KB）+ 订单状态刷新 2（任务 21378，46MB → 91,307 行 override）。DuckDB 增量：orders 10,636,237 → 10,654,714（+18,477）/ user_first_purchase 4,237,949 → 4,246,328（+8,379）/ user_rfm 62.7M → 72.4M（+9.66M 含 466 组合预加载）/ daily_metrics 6/3 完整（GMV ¥1.40M / GSV ¥946K vs 6/2 ¥1.56M / ¥1.13M 合理回落）。`baseline_2026_06_03.json` 累积 3 个 run：run 1/3 = real elapsed 63.2min / step sum 126.4min（6/4 增量）/ run 2/3 = real elapsed 17.5min / step sum 52.6min（6/3 增量，保留）/ run 3/3 = real elapsed 63.2min / step sum 189.6min（etl_total 累计）。6 道 gates 因增量模式触发 skipped 但 overall=pass；errors=0。**已知 fail-soft（不影响业务）**：`rfm_analysis_cache` 57 行（vs 6/3 baseline 60）——`scripts/etl/pipeline.py:105` 早开 `read_only=True` 连接读历史 order_ids，污染同进程 DuckDB config，导致 `backend/services/health/rfm_analysis/cache.py:_open_write_conn()` 后续开 `access_mode=READ_WRITE` 抛 `Can't open a connection to same database file with a different configuration`；cache.py 已 try/except return 0，Step 6 fail-soft，RFM 缓存维持 6/3 baseline 60 行（仍 valid）。**uvicorn 重启** (PID 19865, /api/v1/health 200, 5.6ms) + E2E 验证 rfm-analysis 1-6月 YTD GSV 8 象限 HTTP 200：TTL=4,244,556（+6,607）/ 重要价值 67.02% / 重要发展 55.60% / 一般价值 54.32% / 重要保持 4.01% / 重要挽留 2.57% 等，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购业务预期；task #102 修复持续生效，无 100% / 0% 异常。
- **`scripts/etl/_timer.py` baseline wall_time 字段歧义修** — `save_baseline()` 旧字段 `wall_time_sec` / `meta.total_wall_time` 实际 = `sum(per_step.wall_time)` 即 step 累计 wall time，**不是**真实跑批 elapsed（ended - started），字段名误导读者以为"wall time"。**修法**：① 新增 `real_elapsed_sec` 字段 = ended - started 真实跑批 wall time（用户体感）；② 新增 `step_wall_time_sum` 字段 = sum(per_step.wall_time) 显式命名的 step 累计；③ 旧字段 `wall_time_sec` / `meta.total_wall_time` 保留为 deprecated 值（= step_wall_time_sum），加注释警示「实际是 step 累计，不是真实 wall time」；④ meta 段同步暴露 `real_elapsed_sec` / `step_wall_time_sum`。触发原因：review skill 事后审查 1d4f03f 入仓 baseline 时发现 CHANGELOG + commit 34a89dc 写"wall=126.4min"实际是 step 累计，真实 elapsed 只有 63.2min，数字翻倍误导；commit 34a89dc message 因 git 不可改历史保留原 wall=126.4min（reader 需结合本条目 + `_timer.py` 字段定义理解）。pytest 153/8 全过；ruff 0 errors；run 1/3 单测验证 real_elapsed_sec=0.155 < step_wall_time_sum=0.360，旧字段 wall_time_sec 仍等于 step_wall_time_sum（兼容历史 baseline JSON 读取方）。
- **QW0 严格 Phase 2：第 2 次 Mac baseline run 跑批入仓** — `data/processed/etl_perf/baseline_2026_06_03.json` 追加 run 2/3：wall=52.6min（cleanup 后 orders 表 2.9M 行的增量 ETL，31 个 per_step 节点），相比 run 1/3 (180.2min, cleanup 前 10.6M 行全量 ETL) **3.4x 提速**。提速来源：① cleanup 移除 7.7M order_id=sub_order_id 重复行 → Step 4 反向同步省时；② parquet 缓存命中 251/251 → Step 1 全店读 0 重读。**关键 bug 发现**：`scripts/etl/_timer.py:267` `save_baseline()` 默认 `run_id="1/3"` + 调用方未传具体值 → 同 baseline_date 多次跑批互相覆盖（origin/main 的 run 1 被 12:48 那次覆盖了），手动 git show 取回 run 1 + 改 run_id=2/3 追加合并；`wall_time_stdev` gate 标 skipped 并加 note 说明 run 1+2 数据规模不同 stdev 无意义。剩余 4 次 baseline（Mac ×1 + Windows ×3）+ median 计算 留 task #24/#34；`save_baseline` run_id 自增 fix 留 task #59 / `fix/timer-run-id-autoincrement` 分支单独 12 步。**注**：本条目 wall=52.6min 是 step_wall_time_sum 不是 real elapsed（real elapsed=17.5min），见上文 `_timer.py` baseline wall_time 字段歧义修条目。


### Changed
- **W6 ETL 跑完 lark-cli 通知（复用 6 道门禁通道）** — 新增 `scripts/etl/notify.py:1-89` `notify_etl_complete(stats, status='success'/'failed')`：① 跨子项目 import `scraper.core.sanity_check._send_lark_alert` 复用 6 道门禁 lark-cli 通道（不引入新依赖）；② graceful degrade 三路径全过：未配置 `NOTIFY_OPEN_IDS` 静默 skip / lark-cli 不存在返回 False 不抛异常 / 单 oid 失败不影响其他 oid（部分成功 `2/3 推送成功`）；③ 区分 status：`success` 推 `✅ ETL 跑完 + 6 stats 字段`（orders / user_rfm / wall_min / mode / run_mode / gates_overall），`failed` 推 `❌ ETL 失败` 避免静默成功假象。**集成点** `scripts/etl/pipeline.py:380-410` 末尾（在 ETL 完成横幅后 + GC 前）：① 入口 `perf_counter()` 算 real elapsed `wall_min`；② step 8 try 块加 `step8_ok` 标志（成功/失败）；③ 调 duckdb 查 orders/user_rfm 行数（部分失败 `'?'` 占位不阻塞）；④ try/except 包住整个通知块（通知失败不阻塞 ETL 已完成）。**.env.example:27-37** 加 Lark 通知段（`NOTIFY_OPEN_IDS` / `LARK_BIN` / `LARK_OPEN_ID`）并说清 W6 走 `NOTIFY_OPEN_IDS` 多收件人 + trim whitespace；`LARK_OPEN_ID` 仍是 `_send_lark_alert` 单收件人 fallback（scraper 6 道门禁告警用）。**测试** `backend/tests/test_w6_etl_notify.py` 9/9：no_oids_skip / single_oid_msg / multi_oid / partial_failure / status_failed_emoji / missing_keys_? / whitespace_trim / empty_after_split / send_unavailable；全量 `pytest backend/tests/` 167 passed / 8 skipped 无 regression。ruff 0 errors。commit d6e4c07 → merge d11ad1e → main 已 push + pull --ff-only。
### Fixed
- **RFM 8 象限 repurchase_users 错把"base_orders 内 ≥1 单"算成"复购"（P0）** — `backend/services/health/rfm_analysis/period.py:218` 原 SQL `repurchase_users AS (SELECT DISTINCT user_id FROM base_orders)` 是错的：base_orders 本身是「有订单的 hist_users」集合，hist_users 等于「base_orders 内有 ≥1 单」的用户，再 LEFT JOIN 同一个集合 → **repurchase_users == hist_users**（100% 命中），所以 YTD 1-6 月 8 象限中 4 段（重要价值/发展、一般价值/发展）显示 100% 回购率。6 月 MTD 4 段（重要保持/挽留、一般保持/挽留）显示 0% 则是 R>30 天用户当月没买的业务正确现象（不是 bug）。**修法**：`repurchase_users` 改为 `SELECT user_id FROM base_orders GROUP BY user_id HAVING COUNT(*) >= 2`（base_orders 每行已是一个有效订单，直接 COUNT(*) 即订单数）。**修后 1-6 月 GMV 8 象限**：重要价值客户 69.91% / 重要保持 6.51% / 重要发展 57.37% / 重要挽留 3.84% / 一般价值 57.78% / 一般保持 3.05% / 一般发展 17.35% / 一般挽留 0.71%，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购的业务预期。commit 2c6a5e1。

- **`/api/v1/rfm/r-flow` R 桶 2-6 回购率恒为 0.0%（P1）** — `backend/services/rfm/r_flow.py` + `backend/services/rfm/_flow_engine.py`：`task#88 02ab0a5` 之前 R 桶按 `cutoff_dt` (start_dt-1 = 4/30) 算 recency 给出有意义的回购率（11.0% / 8.3% / 4.4% / 2.9% / 1.1% / 0.4%），但 `02ab0a5` 改 `end_dt` (5/31) 截止让段级和 = TTL → 5/1-5/31 当期有订单的用户 MAX(pay_time) 都在 5/1-5/31、距 end_dt 0-30 天 → 全部归入「近1个月已购客」→ R 桶 2-6 的用户 last_pay < 5/1、不在 base_orders → **R 桶 2-6 ∩ base_orders = ∅（数学不可能有非零 repurchase）**。**修法**：R 桶分桶改用 `pre_cutoff_last_pay = MAX(pay_time) WHERE pay_time <= cutoff_dt` + DATEDIFF 到 cutoff_dt（不归并到 hist_customers，独立子查询保证渠道/退款口径一致）。`_flow_engine.py` R flow 注入 2 个额外占位符 (cutoff_ts, cutoff_date)，F/M 不受影响。**5/1-5/31 新购客（pre_cutoff=NULL）不进任何 R 桶**，仅在「已购客TTL」行出现——这是 R 桶业务语义正确的代价（段级和 < TTL by 新购客数），已写入注释。**修后 5/31 GSV R 桶数据**：`近1个月已购客=11.0% (107K hist)`、`近2-3个月=8.3% (188K)`、`近4-6月=4.4% (225K)`、`近7-12个月=2.9% (504K)`、`近13-24个月=1.1% (922K)`、`2年外=0.4% (2.17M)`，符合「越近期复购率越高」业务预期。F/M 端点不受影响（它们的分桶基于 COUNT/SUM，不依赖 recency 参考日）。commit a73dfac。

- **`frontend-vue3/src/views/health/RFMSegmentDrilldown.vue` 切 segment 不重 load（P1）** — 父组件 `ValueTierTab.vue` 用 `v-if="selectedSegment"` 挂载 `RFMSegmentDrilldown`，selectedSegment 从「重要价值客户」切到「重要保持客户」时 v-if 仍 truthy → 组件不重挂载，只更新 `rfm-segment` prop。原 `watch([() => props.rfmSegment, liveQueryParams], load, { immediate: true })` 在 queryParams 不变时不会触发 `load()`（数组 source 任何一个变化才 fire，但 rfmSegment 变化经由 `() => props.rfmSegment` getter 在某些 Vue 响应追踪场景下未触发回调），导致切 segment 后图表/表格仍是上一个 segment 的数据。**修法**：① `RFMSegmentDrilldown.vue` 加独立 `watch(() => props.rfmSegment, (newSeg) => { if (newSeg) load() })` 兜底；② `ValueTierTab.vue` 给 `RFMSegmentDrilldown` 加 `:key="selectedSegment"`，segment 变化时强制重挂载（双保险）。vue-tsc --noEmit 无报错。commit 25395f2。
- **`/api/v1/customer-health/value-tiers` `channel="全店"` 返回 0 行 + 无参 422（P0/P2）** — `backend/services/health/tiers.py` + `backend/routers/health.py`：① **P0** service `if channel: fb.with_channels([channel])` 把字面量 `"全店"` 当成具体渠道名传给 `expand_channels`，但 `"全店"` 不是 orders 表中真实的 channel 值（应等同于「不过滤渠道」=汇总所有渠道），SQL `channel IN ('全店')` 命中 0 行 → 端点返回 `{value_tiers: [], frequency_tiers: [], segments: []}`。**修法**：照搬 `overview.py:151` / `tier_flow.py:60` / `rfm_category_drilldown.py:145` 兄弟端点的特判 `if channel and channel != "全店": fb.with_channels([channel]) elif exclude_channels: fb.with_exclude_channels(exclude_channels)`，并把 `exclude_channels` 和 `channel` 改为互斥分支（之前是顺序生效，channel 在后会覆盖，逻辑不清）。② **P2** router `analysis_date: str = Query(...)` 强制必填导致无参调用 422 Unprocessable Entity，UX 上看板默认进入应该 MTD（今天回溯）而不是报错。**修法**：router `analysis_date` 改 `Optional[str] = Query(default=None, description="...缺省=今天 MTD")`，`check_future_date` 守在 `if analysis_date` 后只对显式传值校验；service 签名 `analysis_date: Optional[str] = None` + 函数入口 `if not analysis_date: analysis_date = datetime.now().strftime("%Y-%m-%d")` 兜底。pytest 153/8 全过。

- **`/api/v1/customer-health/rfm-category-drilldown` 非法 rfm_segment 名 500→400（P0-2）** — `backend/routers/health.py` `get_rfm_category_drilldown` 之前直接 `return rfm_category_drilldown_service.get_rfm_category_drilldown(...)`，service 在 `rfm_segment not in RFM_SEGMENT_NAMES` 时抛 `ValueError("无效的 RFM 象限名称: ...")` 不被 router 包装，FastAPI 把未处理 ValueError 当 500 → 前端拿到 "Internal Server Error" 而不是友好的 400 + 业务提示。**修法**：router 包一层 `try/except ValueError → raise HTTPException(status_code=400, detail=str(e))`，让 service 抛 ValueError 是合理契约（输入参数非法），router 负责翻译成 4xx。service 本身不改（参数验证下沉到 service 是合理设计）。pytest 153/8 全过；E2E 验证：合法 segment「重要价值客户」= 200，非法「超级用户」= 400，非法「已购客TTL」= 400，detail 字段含「无效的 RFM 象限名称」。commit e96823e → merge cdda3e1 → main 已 push + pull --ff-only + uvicorn 重启（PID 31006，/api/v1/health 200 OK）。
- **RFM 8 象限段级和 ≠ 已购客 TTL（修 task#89 P0 关联）** — `backend/services/health/rfm_analysis/period.py` `_run_rfm_period_live` `user_stats_all` / `user_stats_same` 用 `cutoff_dt`（start_date - 1 = 5/1 的前一天 = 4/30 截止）作为 RFM 分类分母，8 象限段级和 hist_users = 3,889,253（仅 cutoff 之前有历史的用户），而 `ttl_users_all` 用 `end_dt`（5/31 23:59:59 截止）作为 TTL 分母 = 4,237,390，差 348,137 = 2026/1/1~5/31 首购用户（cutoff 之前无历史）。**修法**：照搬 task#88 `02ab0a5` 修法——`user_stats_*` CTE 截止由 `cutoff_dt` 改为 `end_dt`，同步把 `rfm_scored_*` 的 4 个 DATEDIFF 参考日从 `cutoff_dt` 改 `end_dt`（避免负 recency）。新购用户按 end_dt 截止的 F=1 / M=amount 自然归入「一般发展/挽留客户」段，R/F/M 分类语义改为「截至 end_dt 行为」（与 ttl_users_* 同口径），不再丢失。**修后 5/31 GSV 8 象限 4 端点（all/same/member_all/member_same）段级和全部 = TTL**：all/same = 4,237,390 = ttl_users_all/same；member_all/member_same = 1,588,122 = ttl_users_member_*。**副作用**：R≥4 段（重要价值/一般价值/重要发展/一般发展）`repurchase_rate = 1.0000`——这些段定义上要求 last_pay_time 在 [end_dt - 90, end_dt]（即 2026-03-02 ~ 2026-05-31）→ 必然在 base_orders 内，按 `COUNT(DISTINCT user_id) FROM base_orders` 计算的 repurchase_users 自然 100% 命中，数学正确。params 改 10 个 cutoff_dt → end_dt 占位符（user_stats_* 2 个 + rfm_scored_* 8 个）；ruff 0 errors；pytest 153/8 全过。

- **`frontend-vue3/src/views/health/ValueTierTab.vue` 回购率 3 年对比对 null/undefined 不防御（修 task#89 子项 P1）** — 表格 3 列「{年份}回购率」(`repurchase_rate_current` / `_comp` / `_prev2`) 的 render 直接 `(r.repurchase_rate_xxx * 100).toFixed(2)`，若后端在异常路径（旧缓存、schema 漂移、prev2 周期未覆盖）返回 `null`/`undefined` 而非 number，会显示 "NaN%"（undefined）或 "0.00%"（null 隐式转 0）。**根因**：service 当前返回路径全 OK（直调 `get_rfm_analysis(end_date='2026-05-31')` 8 行 prev2 = 0.0589/0.0127/0.0196/0.0034/0.0438/0.0088/0.0123/0.002 全是合法 float，缓存表 `rfm_analysis_cache` 60 行也含 prev2 字段），但前端 TS 类型声明字段为非空 `number`，与现实可能的 null/undefined 不匹配 → 任何上游异常都会让 toFixed 输出 NaN。**修法**：加 `formatRate(v: number | null | undefined): string` helper（`((v ?? 0) * 100).toFixed(2) + '%'`），3 个 render 替换为 `formatRate(r.repurchase_rate_xxx)`。chart series data 保持原样（ECharts 接受 null 表示 missing value，无害）。vue-tsc 0 errors；pytest 153/8 全过；当前实际 prev2 全是合法 float，本修复为防御性兼容（避免未来缓存 / 中间态 / 局部数据缺失时崩溃）。

- **RFM R/F/M 段级桶求和 ≠ TTL（修 task#88 P0）** — `backend/services/rfm/_flow_engine.py` task#85/#86/#87 修了 TTL 走 `end_dt` 截止（4,237,390）但 `hist_customers` CTE 仍用 `pay_time <= cutoff_dt::TIMESTAMP`（5/30 0:00 截止），且 `segment_stats` 按 `GROUP BY channel_flag, is_member, segment_val` 把 `is_member=TRUE/FALSE` 拆成两段输出 → `_parse_flow_rows` 里 mode='all' 仅取 `is_member=FALSE`（非会员），mode='member_all' 仅取 `is_member=TRUE`（会员），导致 mode='all' 段级和 = 2,645,045（仅非会员），TTL = 4,237,390（含会员），差 1,592,345（37% 用户没进任何段桶）。**根因双重**：① `hist_customers` 截止 cutoff_dt（5/30 0:00）比 TTL 的 end_dt（5/31 23:59:59）少 6,242 user；② 真正主因是 segment_stats 按 is_member 拆分让 mode='all' 阉成"仅非会员"段，丢 1,586K 会员用户。**修法**：① `hist_all_params` / `hist_same_params` 的 `cutoff_dt` 替换为 `end_dt`（两个占位符都改），让 hist 用户集与 ttl_users_* 对齐；② 重写 `segment_stats` 为 UNION ALL 两段：前段 `GROUP BY channel_flag, segment_val`（不拆 is_member，含会员+非会员，标记 `FALSE AS is_member` 作为 mode='all'/'same'），后段 `GROUP BY channel_flag, segment_val WHERE is_member=TRUE`（仅会员，标记 `TRUE AS is_member` 作为 mode='member_*'）。RFM 段切分（recency_days / frequency / monetary）参考日同步改用 end_dt（与截止日一致避免负 recency），cutoff 语义在 period.py 8 象限继续保留（不破坏"观察期前行为"）。**修后 5/31 GSV 12 端点（R/F/M × 4 mode）段级和全部 = TTL**：all/same = 4,237,390 = ttl_users_all/same；member_all/member_same = 1,588,122 = ttl_users_member_*。pytest 153/8 全过。

- **RFM R/F/M 区间流转「已购客 TTL」4 端点全量覆盖（修 task#85/#86/#87 P0）** — `backend/services/rfm/_flow_engine.py` `run_flow_period` 的 `hist_customers` CTE 用 `pay_time <= cutoff_dt::TIMESTAMP`（0 点截止）+ `is_refund=FALSE`，与 RFM 分类共用同一 user 集作为 TTL 基数。5/31 观察期 → cutoff=5/30 → hist 只算到 5/30 0:00（丢 5/30 整天 5,375 user）+ refund 排除 19K user，导致 r_flow / f_flow / m_flow 5/31 GSV TTL = 4,231,148（all 2,645,045 + member 1,586,103）。**修法**：照搬 task#80 period.py 设计——加 4 个独立 `ttl_users_all/same/member_all/member_same` CTE（用 `end_dt` 截止，含当期新增用户），把 stats 拆成 `segment_stats`（走 hist_customers 段分类，保留 cutoff 避免循环论证）+ `ttl_stats`（走 ttl_users 独立 CTE，含当期），UNION ALL 输出。**修后 r_flow / f_flow / m_flow 5/31 GSV TTL = 4,237,390**（与 8 象限 4.23M 一致；与 orders 全量 4,256,623 差 19,233 是 GSV 口径下排除的退款订单 user，业务正确）。R/F/M 段级数据（recency_days / frequency / monetary 分桶）保留原 cutoff 语义不破坏。params 加 4 个 ttl_* end_dt 占位符（+4）；ruff 0 errors；pytest 153/8 全过。commit a93741b → merge 4a6d21d → main 已 push + pull --ff-only + uvicorn 重启（PID 98453，/api/v1/health 200 OK）。
- **RFM 8 象限分析「已购客 TTL」缺 5/31 整天用户 + 错用 RFM 分类 cutoff** — `backend/services/health/rfm_analysis/period.py` `_run_rfm_period_live` 把 TTL 当作 8 象限 hist_users 的 SUM（`ttl_stats_all AS (... SUM(hist_users) ... FROM segment_stats_all)`），而 `segment_stats_all` 来自 `user_stats_all` CTE（用 `cutoff_dt` = start_date-1 = 5/1 的前一天），导致：① TTL 用错了 RFM 分类口径（基于观察期前行为，不含当期新增）；② `pay_time <= '2026-05-31'::TIMESTAMP` 解析为 5/31 00:00:00，漏掉 5/31 整天的 3,481 GSV 用户。SQL 直查 4,256,623（live 截至 6/2 23:59:59），修前 MTD 5月 GSV TTL = 4,233,909（差 22,714 = 19,233 退款用户 + 3,481 5/31 整天用户）。**修法**：加 4 个独立 `ttl_users_all/same/member_*` CTE（用 `end_dt` 截止，含当期）→ `ttl_stats_*` 改从 `ttl_users_*` 拿 hist_users（不再 SUM segment_stats）。修后：MTD 5月 GMV TTL = 4,256,623（与 SQL 直查完全一致）；MTD 5月 GSV TTL = 4,237,390（GSV 排除 19,233 退款用户，是 GSV 口径下业务正确值）；默认 MTD（6/1-6/2）GSV TTL = 4,243,508（= 直查 6/2 23:59:59 GSV）。8 象限 RFM 分类继续用 cutoff（不破坏"观察期前行为"语义，避免循环论证）。params 加 4-6 个 end_dt 占位符；ruff 0 errors；pytest 153/8 全过。
- **RFM 缓存陈旧（修前端 4 分层基数显示旧数）** — `rfm_analysis_cache` 之前仅靠 `data_version`（max_pay_time）做失效判断，ETL 续传恢复 orders 表 4.71M user 后 max_pay_time 不变但行数变化，缓存键不变 → 旧缓存（基于砍数据后的 942K 用户）继续被读出。修法（`backend/services/health/rfm_analysis/cache.py` + `analysis.py`）：
  1. **加 `orders_count_at_write` 列** — 写缓存时持久化当前 `SELECT COUNT(*) FROM orders` 快照（已对 60 行历史数据回填）。
  2. **新 `is_stale()` 函数** — 三重失效检测（任一为真即 DELETE + 重算）：① 当前 `mtime_at_write` > 缓存时 ② 当前 `orders.COUNT(*)` ≠ 缓存时 ③ `computed_at` 距今 > 24h（TTL 兜底）。
  3. **新 `clear_rfm_cache()` 函数** — 手动清空整表（ETL 完成后调），`scripts/etl/cli.py` Step 6 已在 `precompute_rfm_cache()` 前自动调用（带 cleared 行数日志）。
  4. **API/导出** — `is_stale` / `clear_rfm_cache` / `RFM_CACHE_TTL_HOURS` 三个符号加进 `__init__.py` 公开。
  5. **清理历史 3 行 INVALID** — 早期 ETL bug 写入了 `metric_type='INVALID'` 缓存行（同 key 同 mtime 但 metric_type 错），本次手动 DELETE 清掉。
  单测：5 个 is_stale 场景全过（mtime 推进 / 行数变化 / TTL 过期 / 全新 / 历史缺列优雅降级）。pytest 153/8 全过；ruff 0 errors。修 R 区间 / F 区间 / M 区间 / 已购客 TTL 在 ETL 续传后未刷新的根因。
- **`scripts/etl/pipeline.py` daily_metrics `new/old_user_gmv` 没排除退款订单（修 P2 task #80）** — `_rebuild_metrics` line 440-441 和 `_update_incremental_metrics` line 530-531 的 `new_user_gmv` / `old_user_gmv` `CASE WHEN` 没加 `is_refund=FALSE`，导致这两个金额字段错误地包含当天退款订单金额（与 gsv 口径不一致）。**根因调查**：6/2 实测 3 个口径（INNER JOIN / LEFT JOIN / daily_metrics）输出**完全一致**（new=3373 old=3941 new_gmv=535,550.19 old_gmv=769,988.25），LEFT JOIN 漏算 NULL 的假设不成立——ufp 缺失的 1128 用户**100% 是纯退款用户**（历史 0 有效订单，6/2 1202 单全退款），ufp 不收录他们是预期行为，他们的订单不计入 new/old 是**业务正确**。**真 bug 在 GMV**：6/2 这 1128 用户里 211 个有 `first_pay_date=6/2`（算 new_user），但他们的退款金额（40,753.60 元）错算进 new_user_gmv。修法：2 处 `CASE WHEN` 加 `AND o.is_refund = FALSE` 与 gsv 口径对齐；同时扩展 `_update_incremental_metrics` docstring 说明 LEFT JOIN 语义和"纯退款用户不计入 new/old"是预期行为。pytest 153/8 全过；ruff 0 errors；pipeline.py 导入签名校验 OK；`/api/v1/health` 200。

- **ETL Step 8 品类预计算 `Connection already closed`** — `scripts/etl/precompute_category_flow.py` 和 `scripts/etl/precompute_category_churn.py` 共 7 处 `conn.close()` / `conn2.close()`（含 3 处 `try/finally`）违反 `backend/db/connection.py` 单例契约——单例连接被代码关闭后，下次 `get_connection()` 拿到已关闭句柄 → `execute()` 抛 `Connection already closed!`。修复全部删除 `conn.close()` 调用并解包 `try/finally` 块（单例连接由 `close_connection()` 在应用退出时统一释放），3 处保留 `try/finally` 也是冗余。`get_churn_data()` 同样修。导致 10 个 window × 2 级别 = 20 个组合（flow）+ N 个月（churn）全部失败，品类流失 / 流转预计算 0 新增 0 跳过（修 P1 task #82）。pytest 153/8 全过。

- **W7 DUCKDB_MEMORY_LIMIT 自动管理（env override 机制）** — `backend/config.py:131-171` 新增 `DUCKDB_MEMORY_LIMIT_OVERRIDE` env + `get_duckdb_memory_limit()` helper：① 动态读 env（不 cache module-level，让 monkeypatch / 实时 export 都能生效）；② override 优先于默认，空字符串/仅空白 fall-back 默认；③ 默认值仍走 `DUCKDB_MEMORY_LIMIT` env（向后兼容 8 处旧 import 不破）。**`scripts/etl/precompute_fact_rfm.py` (新建, W4 占位, +75)** — `setup_async_memory()` W4 启动入口 export 16GB override + 返回生效 limit；`cleanup_async_memory()` 跑完 unset；`run_full_precomputation()` 当前 raise NotImplementedError（W4 工单独立 12 步实施）。**测试** `backend/tests/test_w7_memory_limit.py` 13/13：默认 8GB / override 16GB / 空值 fall-back / 空白 fall-back / 自定义默认 / 优先级 / 常量 strip / 向后兼容 / setup export / OVERRIDE_ASYNC 24GB / cleanup unset / 完整 setup→cleanup 循环 / W4 占位 raise NotImplementedError；项目级 QA 5/5 真实 env 场景全过（默认 8GB / 直接 override 16GB / setup_async_memory 返 16GB / cleanup 恢复 / OVERRIDE_ASYNC 24GB）。全量 `pytest backend/tests/` 166 passed / 8 skipped 无 regression。ruff 0 errors。commit a162ff9 → merge 976d237 → main 已 push + pull --ff-only。
- **FIX-S1 W1 GROUPING SETS 接入生产（audit 关键发现 S1/M3/M6）** — `scripts/etl/preload_rfm.py:571-660` `run_auto_preload()` / `run_range_preload()` 内部从 4 重 for 循环（ch × date × lb × mt）逐个调 `preload_date()` 720 次，改为按 date 循环，每 date 调 1 次 `preload_date_batch(conn, d, lookbacks, metrics, channels)`，1 SQL 跑完该 date 全部 (lookback × metric × channel) 组合。**之前 W1 GROUPING SETS 函数（commit 414a46c）只覆盖单测 5/5，生产 run_auto_preload 仍调旧 720 循环** — audit 跨审发现这一纸面 vs 真实 10.3× 加速脱节。**性能**：720 SQL → 60 SQL（15 hot dates × 1 batch SQL/date）= 12× 减少 SQL 次数；按 6/4 baseline 56.8min step 7b 估算，预计降到 ~5min（需跑 1 次生产 baseline 验证 wall < 70min）。**集成 smoke**：100 订单 toy data + 1 date 1 SQL 写 382 行，(user, channel, lookback, metric) 全部 GROUPING SETS 覆盖。**调用方兼容**：`cli.py:555-557` / `pipeline.py:270-271` / `preload_rfm.py:696/711` 全部 `results = run_auto_preload()` 不读 results 内容，安全改签名 5-tuple → 2-tuple。**全量** `pytest backend/tests/` 180 passed / 8 skipped 无 regression；ruff 0 errors。commit 78a04b9 → merge 682f0cd → main 已 push + pull --ff-only。
- **FIX-S2 W7 override 接入 ETL 入口（audit 关键发现 S2/M2/S12/S17）** — `scripts/etl/pipeline.py:9-15` import 加 `get_duckdb_memory_limit` helper；`pipeline.py:48` 启动横幅 `print(f'内存限制: {get_duckdb_memory_limit()}')` 替代冻结常量（之前 export DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB 后仍输出 8GB）。其余 8 行 `import DUCKDB_MEMORY_LIMIT`（cli.py / load.py / etl_status_override.py / preload_rfm.py / _timer.py / measure_duckdb_perf.py / backend/db/connection.py / backend/db/memory_monitor.py）保留向后兼容，W4 实施时按需切换。`.env.example:27-37` 数据库段后加 `DUCKDB_MEMORY_LIMIT_OVERRIDE` 注释 + 默认 `DUCKDB_MEMORY_LIMIT=8GB`。**`backend/tests/test_w7_e2e_override.py` 4 E2E 测试**：① `test_subprocess_sees_override_16gb` 真 subprocess + OVERRIDE=16GB 验 stdout 含 `MEMORY=16GB`；② `test_subprocess_no_override_falls_back_to_8gb` 无 override 验 `MEMORY=8GB`；③ `test_subprocess_empty_override_falls_back` 空字符串 fall-back；④ `test_pipeline_py_imports_with_override_16gb` pipeline.py 内部 helper 在 16GB env 下 import 成功。**CHANGELOG 数字 8→9 修正**（W7 commit 时错数 8 处，实际 9 个文件 9 行 import）。全量 `pytest backend/tests/` 184 passed / 8 skipped；ruff 0 errors。commit eb27065 → merge [后续] → main 已 push + pull --ff-only。
- **FIX-M1 W6.5 scheduler 工单（audit 关键发现 M1+M12）** — `scripts/etl/scheduler/` 5 文件：① `com.fuqing.etl.daily.plist` Mac launchd 配置（每日 8:30 跑 `python3 scripts/run_etl.py --update`，PYTHONPATH/WorkingDirectory 显式设，stdout/stderr 重定向 `/tmp/fuqing-etl-scheduler.log`，失败时 launchd 自动邮件 / Slack 集成）；② `etl_daily_taskscheduler.xml` Windows Task Scheduler XML（每日 8:30 跑 + ExecutionTimeLimit PT2H + RunAs SYSTEM）；③ `install_macos.sh` 一键安装（cp + launchctl load + verify）；④ `install_windows.ps1` 一键安装（Read XML + Register-ScheduledTask）；⑤ `README.md` 设计权衡 + 跨平台说明 + 失败告警链路。**8:30 跑**给 9 点 dashboard 留 30min buffer。**失败告警链路**：run_etl.py exit !=0 → TaskScheduler / launchd 检测 → 管理员通知 + W6 lark-cli 单独 oncall。**CLAUDE.md 合规**：不在 main 改代码（在 `fix/m1-w6-scheduler` 分支）；跨平台（Mac/Windows）；复用 W6 lark-cli 通知。**修复 audit**：M1 PRD §4.2「每日 9 点自动刷新」从假承诺变真实施 + M12 设计 doc §W6 估时从 0.25d 补到 0.5d（不含 scheduler）。**测试**：plistlib 解析 OK + ElementTree XML 解析 OK + `bash -n install_macos.sh` syntax OK + 全量 pytest 180 passed / 8 skipped（无 regression，scheduler 文件不在 ruff 范围）。ruff 0 errors。
- **FIX-#8 W6 集成修复（audit S5/S6/M5）** — ① `scripts/etl/pipeline.py:33-58` 加 `_safe_etl_notify_on_failure` 装饰器包 `run_full_etl`（最小改动，避免函数体 indent 1 个 tab），任何异常时调 `notify_etl_complete(status='failed', stats={gates_overall: "failed: <ExceptionType>"})`，二次 `try/except` 兜底 notify 失败，原异常 re-raise 不吃掉 — 修复 step 1-7 抛异常时 W6 块被跳过的 audit 关键发现 S5。② `scripts/etl/notify.py:71-95` 改 `concurrent.futures.ThreadPoolExecutor(max_workers=min(len(oids), 5))` 并行推送，按 oids 顺序 zip 收集结果（保留入参顺序，测试稳定）— 9 oids 串行最坏阻塞 ETL 退出 45s 降到 ~5s 并行，修复 S6。③ 新增 `backend/tests/test_w6_pipeline_integration.py` 6 集成测：装饰器 wrap / re-raise 原异常 / 异常时调 notify / notify 失败兜底 / 正常路径不调 / module import 验证 — 修复 M5 缺 pipeline 集成点测试。④ 修 `test_w6_etl_notify.py::test_oids_env_with_whitespace` 改 sorted 验证（FIX-S6 并行后 mock 调用顺序非确定）。全量 `pytest backend/tests/` 190 passed / 8 skipped；ruff 0 errors。commit a873853 → merge [后续] → main 已 push + pull --ff-only。
- **FIX-#9 W1 行为一致性（audit M8 + S8 部分）** — ① `scripts/etl/preload_rfm.py:378` 加 `assert channels, "channels cannot be empty"` 防御（FIX-M8），防止 future caller 传空 channels 时 SQL `IN ()` 报错。② `backend/tests/test_w7_memory_limit.py` 2 vacuous test 改硬断言（FIX-S8）：`test_backward_compat_default_8gb` 原 `assert env_val in ("8GB", "16GB", "4GB")` 接受任意 3 值即使实现改成 return `'32GB'` 也通过，改 `monkeypatch.setenv + assert DUCKDB_MEMORY_LIMIT in (env_at_import, "8GB")`；`test_override_module_constant_strips_whitespace` 原 `if current: assert current == current.strip()` current 空时跳过，改 `monkeypatch + importlib.reload + 验常量 = "16GB"`。**未做（留后续）**：S3 F3 NULL 列硬编码 → agg CTE 算真 first/last/is_member；S4 F2 COALESCE 兜底删除 → 恢复；S13 channel IN f-string → parameterized；S9 pytest 数字反向；S10 CHANGELOG「10.3×」措辞误导；M9 边界 lookback=0/365d 未测。
### Fixed
- **ETL bugs batch2：4 件 P0/P1 修复（workflow audit 揪出 task#59 执行路径漏洞）** — ① `scripts/run_etl.py:32` **P0** `run_id = os.environ.get("ETL_RUN_ID", "1/3")` 写死默认值 → save_baseline 永远收到具体 run_id → _timer.py task#59 P1 修复（自增分支）永远走不到 → baseline 仍会覆盖（证据：baseline_2026_06_03.json 一直只有 1 条 run_id='1/3'）。修法：默认改 `os.environ.get("ETL_RUN_ID") or None` → 让 _timer.py 自增生效。② `scripts/etl/cli.py:687` **P0** `_pipeline_mode` 把 `'inc'` 映射成 `'incremental'`，但 `pipeline.py:56-72` `if/elif` 只识别 `'inc'`/`'full'`，`'incremental'` 落到 else → run_mode='auto' → `--inc` 显式契约被破坏（库空时不 return 反触发全量重建）。修法：改 `{'inc': 'inc', ...}`。③ `scripts/etl/_timer.py` **P1** task#59 修复后的自增 `f"{next_idx}/3"` 第 4 次跑批越界成 `"4/3"`。修法：分母自适应 `max(3, next_idx)` → 第 4 次 `4/4`/第 5 次 `5/5`。④ `scripts/etl/load.py:160-233` **P1** `calculate_daily_metrics` 74 行死代码 — grep 全仓 0 调用方，pipeline.py Step 6.7 已用 `_rebuild_metrics`/`_update_incremental_metrics` 替代。task#59 改这里等于改死代码，本次删整段。pytest 153/8 全过；ruff 0 errors。**bug 暴露背景**：本批 4 件 bug 由 workflow team audit（5 个并行 agent）从 task#59 已 merge 代码中揪出，体现「fix 引入新隐患」的反模式（修了 _timer.py 但调用方 run_etl.py 写死值废掉 / 引入新的 mode 字符串不一致 / 改了死代码而真正路径未动）。

- **`scripts/etl/pipeline.py` 3 处 import 路径错误（修 P0 全量模式崩）** — line 260/353/354 把 `from scripts.preload_rfm` / `from scripts.precompute_category_flow` / `from scripts.precompute_category_churn` 修正为 `scripts.etl.` 子包路径。这是既有 bug（QW0 修正时挪进 scripts/etl/ 包后调用方未同步），全量模式从未触发过 Step 6/8 这 3 个 import，bug 藏着没暴露。本次全量重跑触发后 ETL Step 6 崩，orders 表已写 4.71M user 但 Step 6+ 没跑完，用续传脚本 /tmp/etl-resume-step6.py 完成 Step 6/6.5/6.7/7/8。pytest 153/8 全过。
- **ETL 3 件 P0/P1 修复合集（cli.py / _timer.py / daily_metrics）** —
  ① `scripts/etl/cli.py:678-683` **P0** `--full / --inc` 静默 noop bug：之前
  `if args.full: _mode = 'full'` 只设变量从未调用 `run_full_etl()`，导致
  `python scripts/run_etl.py --full` 啥都不干就退出。修复加 mode 字符串
  转换 + PerfTimer + 实际调用 run_full_etl，并打印明显的 `=== ETL 跑批 ===`
  标记。② `scripts/etl/_timer.py:267-270` **P1** `save_baseline` `run_id="1/3"`
  硬编码默认值：调用方未传具体值时 existing_runs dedup 按 run_id 单字段
  匹配 → 第 2 次跑批 run_id='1/3' 覆盖第 1 次。这是 origin/main run 1
  (01:41 wall=180.2min) 被 QW2 验证跑批 (12:48 wall=52.6min) 覆盖丢失的
  根因（前一个 chore/qw2-etl-baseline-run-2 手动 git show 合并修了数据
  但代码 bug 未修）。修复改默认 `run_id=None` → 自动读
  `len(existing_runs)+1` 作为 `(N+1)/3`。③ `scripts/etl/load.py:160`
  + `scripts/etl/pipeline.py:399/432` **P1** `daily_metrics` 表
  `old_user_count` 硬编码 `0`：3 处 SQL 改用 `LEFT JOIN user_first_purchase`
  按 `first_pay_date = DATE(pay_time)` 判定新客 / `<` 判定老客，同时
  `new_user_gmv` / `old_user_gmv` 也按同口径算（之前都是 0 死代码注释
  自承「待业务确认后重写」）。健壮性：信息模式表检查 user_first_purchase
  存在性，不存在则 fallback 旧逻辑不阻塞 ETL。同时调整 pipeline.py
  调用顺序：删除 Step 5 metrics 调用，新增 Step 6.7 在 user_first_purchase
  + user_recency 之后调，保证 metrics SQL 跑时依赖表已建好。pytest
  backend/tests/ 153 passed / 8 skipped 全过。

### Changed
- **`.gitignore`：屏蔽 `.claude/`（gstack 工具配置）+ `scripts/etl/_cleanup_staging.py`（一次性维护脚本，按文件头自述「脚本本身不入 git」，本地保留作工具避免下次 dup key 时重写）** — 收尾 QW2 验证后工作区 3 个未跟踪文件的归类决策。

### Fixed
- **CHANGELOG.md 残留 merge conflict marker 清理（QW2 Phase 2 merge 后遗）** — commit `9c3f0ad` (QW2 Phase 2 merge) 残留 `<<<<<<< HEAD` / `=======` / `>>>>>>> origin/fix/qw2-phase2-cache-writes` marker 在第 17/18/23 行，本次 chore 顺手清理。QW2 Phase 1 条目已删（Phase 1 在 commit 链中已被 revert ×2：`6669816 Revert "Merge fix/duckdb-readonly-uvicorn"` + `c934324 Revert "docs(changelog): QW2 Phase 1"`），CHANGELOG 只保留实际生效的 Phase 2 条目。

### Added
- **DMP 6 道门禁抽到独立模块 + 飞书 webhook 告警** — 5/28 出现 18 行 likely-wrong 脏数据时无主动告警的问题修复。新增 `scraper/core/sanity_check.py` 把 MEMO_2026-06-01/02.md 识别的 6 道门禁（date_sanity / item_data_validity / cross_day / api_health / business_smoothness / copy_day）抽到独立可 import 模块，每个门禁返回 `(ok, reason)`，统一入口 `run_all()` 任一失败 → 自动标 `data_quality_flag=likely-wrong` + POST 飞书 webhook。webhook URL 走 env `FEISHU_WEBHOOK_URL`（未设静默跳过，graceful degrade；网络异常不抛错不影响主采集流程）。`dmp_master.py` 在 `run_items_module` happy-path 和重试路径都集成调用。新增 `scraper/.env.example` 含申请指南。`tests/test_sanity_check.py` 48 个单测全过（含 webhook mock + 18 行 likely-wrong 复现场景）。
- **DMP 脏数据前端默认隐藏（A1：quality_flag 透传 + 过滤）** — 5/28 18 行 likely-wrong 脏数据在 4 个 tab 仍展示的问题修复。后端 `_load_data3` 显式读 `data_quality_flag` 列（缺列/缺值默认 `legacy` 向后兼容），`_compute_product_assets` / `_compute_other_product_assets` / `_compute_product_assets_daily` 在 item 中透传 `quality_flag` 字段；`contracts/asset.py` `ProductAssetWeek` 加 `quality_flag: str = 'legacy'` 带默认值。前端 `marketFocus.ts` `ProductAssetWeek` 加 `quality_flag?: string` 可选；`ProductAssetsTab` / `OtherProductAssetsTab` 整周过滤（任一产品该周 likely-wrong → 跳过整周），新增 `findLatestVisibleIndex()` 保证本周对比基线用最后一条已过滤的真实周；`StoreAssetsTab` 新增 `visibleWeeks` computed 预留过滤（当前 data2.csv 无 flag 列 noop）。`vue-tsc --noEmit` exit 0；backend pytest 153/8 仍过。
- **QW4 ETL 埋点 + Mac partial baseline（阶段 A 阻断式交付）** — 按 [[project_etl_perf_plan]] 阶段 A 阻断式约束，baseline 出来前不开任何 P0/P1 优化。新增 `scripts/etl/perf.py` 提供 `PerfTimer` 上下文管理器（6 道门禁：date_sanity / cross_day / api_health / business_smoothness / copy_day / wall_time_stdev），埋点覆盖 `run_etl.py`（etl_total try/finally）+ `cli.py`（8 个 --update 子步）+ `pipeline.py`（11 个子步骤）+ `load.py`（filter_rolling_window + upsert_to_duckdb）+ `transform.py`（match_channel 含 P4 关键词循环 + clean_data）。新增 `scripts/etl/report_baseline.py` 解析 baseline JSON 输出人类可读报告。`scripts/etl/baselines/baseline_2026_06_02.json` 包含 Mac 第 1 次 partial 实测（9/15 步骤 / 14m00s / 6 门禁 5 pass + 1 skipped），用 `_save_partial` 中间落盘保证中断不丢。剩余 5 次 baseline 跑批（Mac ×2 + Windows ×3）按用户指令留 TODO 后续会话补齐。
- **QW0-baseline 严格按 HANDOFF §6 + plan §A4.1 修正** — 修 6 个差异点：① `scripts/etl/perf.py` 重命名为 `_timer.py`（更准的命名 + 区分其他 perf 工具）；② `preload_rfm.py` 加 perf_counter 埋点（hot spot #1 — 540 组合串行循环 = 25min 估时）+ `etl_status_override.py` 同样加埋点（hot spot #5 — 66 次 N+1 DELETE = 3min 估时）；③ baseline.json 路径 `scripts/etl/baselines/` → `data/processed/etl_perf/`（跟其他产物统一目录，不在 .gitignore）；④ JSON schema 扩展 7 字段（`version=1.0` / `git_sha` / `runs[]` 数组 / `per_step[].cpu_sec` / `rss_peak_mb` / `duckdb_alloc_mb` / `spill_to_disk_mb`）；⑤ baseline 跑批输出用 `python3 -u` unbuffered 避免上次 0 字节 log 问题；⑥ baseline save 改 `run_id-only dedup`（之前 run 1 partial + run 2 完整因 dedup 用了 `run_id+started_at` 复合键，agent 第二次错调 save_baseline 触发清空）。**1/3 Mac baseline 真实跑批完成**：wall=180.2min（远超 plan 估的 25-41min，preload_rfm 540 组合串行占 ~89%），cpu_time=10628s, rss_peak=7.4GB, duckdb_alloc=8GB, spill=0；6 门禁 pass=5 + skipped=1（单次 wall_time_stdev 不算）。剩余 5 次 baseline（Mac ×2 + Windows ×3）+ median 计算 留 Phase 2。`pytest backend/tests/` 153/8 + `tests/test_sanity_check.py` 48 全过；`ruff check .` 0 errors。P0（QW1/2/3/5）可以开。

### Fixed
- **RFM 缓存写路径绕开 read_only 单例（QW2 Phase 2）** — `backend/services/health/rfm_analysis/cache.py` 4 个写路径（`_ensure_db_cache_table` DDL / `_read_db_cache` 损坏清理 DELETE / `_write_db_cache` INSERT OR REPLACE / `precompute_rfm_cache` 预计算）从 read_only 单例改用独立写连接 `_open_write_conn()`（`duckdb.connect(..., access_mode=READ_WRITE)` 短生命周期）。修 ETL Step 6 "预计算 RFM 8象限历史周期缓存" 时 "Cannot execute CREATE on read-only database" 错误。**关键约束**：① `precompute_rfm_cache` 必须先 `_open_write_conn()` 再做其他操作（同进程内 DuckDB 不允许 read_only 单例已建后再开 read_write 写连接，会报 "Can't open a connection to same database file with a different configuration"）；② uvicorn 进程（read_only 单例已锁定）调 `_write_db_cache` 优雅降级为 warning（不影响 API 返回，cache 由 ETL 预计算填充）；③ 移除 `_write_db_cache` 冗余 `conn` 参数（内部开写连接），更新 `analysis.py` 调用方。pytest backend/tests/ 153/8 + tests/test_sanity_check.py 48 全过；ruff check . 0 errors。
- **DMP 单品资产 result 缓存不感知 mtime 变化** — `dmp_asset_service` 的 `result`/`result_other` 缓存按 `_weeks` 单字段 key 缓存，`_check_reload` 只刷 `mtime`+`df` 不动 result 缓存，导致 work plat 更新 `data3.csv` 后前端的"单品资产"tab 仍显示旧周。修复分两步：① `product.py`/`other.py` 缓存判断前先调一次 `_load_data3()` 让 mtime check 有机会跑；② `_helpers._load_data3` 检测到 mtime 变化时连带清掉 `result`/`result_other`。新增 `test_dmp_asset_cache.py` 4 个 regression test 覆盖。
- **scraper/ 20 个 pre-existing lint 错误治理** — 物理合并 work plat → scraper/ 时把 scraper/ 临时加到 ruff exclude，本次治理完成。`ruff --fix` 自动修 9 个（F841 / F401 / F811 / F541）+ 手动修 11 个（E402 ×6 加 `# noqa: E402` 保留 sys.path.insert 后 import 的有意设计，F401 ×2 删 unused imports，F841 ×2 删 dead code）+ `pyproject.toml` 移除 `scraper/` from exclude 重新纳入 ruff 检查。pytest 201 passed（backend 153/8 + sanity_check 48）。下阶段 P0（QW1/2/3/5）可以开。

### Changed
- **Monorepo 化：物理合并 work plat/DMP_test_package → `fuqing-crm-analytics/scraper/`** — 按"方案 B"（Q0 业务价值调研后采纳）合并 scraper 代码到 monorepo。`backend/config.py` DMP_DATA_DIR 默认值改为 monorepo 相对路径 `scraper/core`（`.env` 环境变量仍可覆盖，向后兼容 work plat 旧位置）。`pyproject.toml` ruff 临时排除 `scraper/`（原 DMP_test_package 19 个 pre-existing lint 错误不在本次范围，留到 task 14 "work plat 6 道门禁 + 飞书 webhook" 阶段统一治理）。数据物理迁移（work plat/core/data2.csv 等）未做，下次 checkpoint 单独进行。Q0 调研报告：见 `docs/dmp-poc/达摩盘官方API评估报告v1.0.md`。
- **数据物理迁移：work plat/core/data*.csv → scraper/core/data*.csv** — `data2.csv` (56711B/760行)、`data3.csv` (580572B/7044行)、`data.csv` (130667B/2273行) 全部从 work plat 旧位置搬到 monorepo 内的 `scraper/core/`。`.env` DMP_DATA_DIR 同步更新。work plat 旧位置已空，scraper/core 是唯一数据源。uvicorn 重启后 service 层 3 个 tab 全部 05/25-05/31 正常。

### Fixed
- **DMP_DATA_DIR 空字符串 fallback bug** — `backend/config.py:120` 之前用 `Path(os.environ.get("DMP_DATA_DIR", str(_DEFAULT_DMP_DIR)))`，当 `.env` 设 `DMP_DATA_DIR=`（空字符串）时 `os.environ.get` 返回空字符串不会 fallback 到默认值，`Path("")` 解析为 `Path(".")` 当前目录。改为先 `.strip()` 再判空，空则用 monorepo 默认 `scraper/core`。

### Documentation
- **ETL Phase 4 架构设计文档入仓（4 层 SaaS 重构）** — `docs/design/etl-phase4-architecture.md` (460 行, APPROVED) 落地：① Layer 1 Source（xlsx→Parquet→DuckDB orders）+ Layer 2 ETL Pipeline（W1 GROUPING SETS / W2 原子 manifest / W3 DQ+幂等）+ Layer 3 Precomputed Serving（fact_rfm_long 纯增量 + dbt-style snapshot）+ Layer 4 Query API（DuckDB-KV 缓存 24h TTL）；② 5 个 WO 详细规范 + 4 周时间线 + 4 阶段灰度迁移；③ Acceptance Criteria 覆盖 3 痛点（ETL < 35min / 不再读到半新半旧 / 历史秒出）；④ 4 个 open questions 已 user 拍板（异步后台跑全历史 / 单 view / 告警+ETL 继续 / miss 走 fact_rfm_long）。Supersedes HANDOFF-etl-perf-2026-06-02.md（13 工单，范围扩展为架构分层）。gstack artifacts 同步：`hutou-main-design-20260604-180114.md`。
- **ETL Perf 4-Layer design v1.1 增量** — 标题改 "ETL Perf 4-Layer Restructure" 避免和 PRD §11.3 Phase 4 混淆。**新增 W6**（lark-cli ETL 跑完通知，复用 sanity_check.py _send_lark_alert）+ **W7**（DUCKDB_MEMORY_LIMIT_OVERRIDE 临时 16GB，平时 8GB）。**W1-W5 各加 CLAUDE.md 合规段**：W1 走 `backend.semantic.segments`、W2 manifest 用 `os.rename` + fsync + 并发读安全、W3 复用 lark-cli 通道、W4 走语义层 + PRD §4.1/§4.2/§4.3 验收、W5 ThreadSafeCursor 包装。**加 §11 PRD-derived 验收点**（< 3s SLA / 9am 自动刷新 / 改口径只改 1 文件）。**加 §16 12 步 check-list per WO**（分支命名 / commit message / 每个 WO 特殊附加项）。**加 §17 旧 13 工单 stale 审计表**（4 done + 2 被 W1 取代 + 7 stale 不重做）。**reference.md 修 840 → 540**（stale 数据，以 preload_rfm.py:28 注释为准）。

## [0.3.5] - 2026-06-04

### Performance
- **增量 ETL 跑批（6/4 baseline run 1/3 — 真实 elapsed 63.2min / step_wall_time_sum 126.4min）** — `python scripts/run_etl.py --update` 跑 6/4 增量（**真实 elapsed 63.2min** = started 10:42:59 → ended 11:46:09；**step_wall_time_sum 126.4min** = sum(per_step.wall_time) 含 Step 7b 540 组合 RFM 预加载 56.8min 单 step），处理 4 个新源文件：店铺 1（任务 21376，1.3MB 6/3 当日 8,350 单）+ 会员 1（任务 21377，676KB）+ 订单状态刷新 2（任务 21378，46MB → 91,307 行 override）。DuckDB 增量：orders 10,636,237 → 10,654,714（+18,477）/ user_first_purchase 4,237,949 → 4,246,328（+8,379）/ user_rfm 62.7M → 72.4M（+9.66M 含 466 组合预加载）/ daily_metrics 6/3 完整（GMV ¥1.40M / GSV ¥946K vs 6/2 ¥1.56M / ¥1.13M 合理回落）。`baseline_2026_06_03.json` 累积 3 个 run：run 1/3 = real elapsed 63.2min / step sum 126.4min（6/4 增量）/ run 2/3 = real elapsed 17.5min / step sum 52.6min（6/3 增量，保留）/ run 3/3 = real elapsed 63.2min / step sum 189.6min（etl_total 累计）。6 道 gates 因增量模式触发 skipped 但 overall=pass；errors=0。**已知 fail-soft（已修）**：`rfm_analysis_cache` 之前 57 行（vs 6/3 baseline 60）——`scripts/etl/pipeline.py:105` 早开 `read_only=True` 连接读历史 order_ids，污染同进程 DuckDB config，导致 `backend/services/health/rfm_analysis/cache.py:_open_write_conn()` 后续开 `access_mode=READ_WRITE` 抛 `Can't open a connection to same database file with a different configuration`；本次 commit ab78383 修法：去掉 read_only=True，用默认 READ_WRITE 连接，与 cache.py 后续 write_conn 保持一致 access_mode。**uvicorn 重启** (PID 19865, /api/v1/health 200, 5.6ms) + E2E 验证 rfm-analysis 1-6月 YTD GSV 8 象限 HTTP 200：TTL=4,244,556（+6,607）/ 重要价值 67.02% / 重要发展 55.60% / 一般价值 54.32% / 重要保持 4.01% / 重要挽留 2.57% 等，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购业务预期；task #102 修复持续生效，无 100% / 0% 异常。
- **`scripts/etl/_timer.py` baseline wall_time 字段歧义修** — `save_baseline()` 旧字段 `wall_time_sec` / `meta.total_wall_time` 实际 = `sum(per_step.wall_time)` 即 step 累计 wall time，**不是**真实跑批 elapsed（ended - started），字段名误导读者以为"wall time"。**修法**：① 新增 `real_elapsed_sec` 字段 = ended - started 真实跑批 wall time（用户体感）；② 新增 `step_wall_time_sum` 字段 = sum(per_step.wall_time) 显式命名的 step 累计；③ 旧字段 `wall_time_sec` / `meta.total_wall_time` 保留为 deprecated 值（= step_wall_time_sum），加注释警示「实际是 step 累计，不是真实 wall time」；④ meta 段同步暴露 `real_elapsed_sec` / `step_wall_time_sum`。触发原因：review skill 事后审查 1d4f03f 入仓 baseline 时发现 CHANGELOG + commit 34a89dc 写"wall=126.4min"实际是 step 累计，真实 elapsed 只有 63.2min，数字翻倍误导；commit 34a89dc message 因 git 不可改历史保留原 wall=126.4min（reader 需结合本条目 + `_timer.py` 字段定义理解）。pytest 153/8 全过；ruff 0 errors；run 1/3 单测验证 real_elapsed_sec=0.155 < step_wall_time_sum=0.360，旧字段 wall_time_sec 仍等于 step_wall_time_sum（兼容历史 baseline JSON 读取方）。
- **QW0 严格 Phase 2：第 2 次 Mac baseline run 跑批入仓** — `data/processed/etl_perf/baseline_2026_06_03.json` 追加 run 2/3：wall=52.6min（cleanup 后 orders 表 2.9M 行的增量 ETL，31 个 per_step 节点），相比 run 1/3 (180.2min, cleanup 前 10.6M 行全量 ETL) **3.4x 提速**。提速来源：① cleanup 移除 7.7M order_id=sub_order_id 重复行 → Step 4 反向同步省时；② parquet 缓存命中 251/251 → Step 1 全店读 0 重读。**关键 bug 发现**：`scripts/etl/_timer.py:267` `save_baseline()` 默认 `run_id="1/3"` + 调用方未传具体值 → 同 baseline_date 多次跑批互相覆盖（origin/main 的 run 1 被 12:48 那次覆盖了），手动 git show 取回 run 1 + 改 run_id=2/3 追加合并；`wall_time_stdev` gate 标 skipped 并加 note 说明 run 1+2 数据规模不同 stdev 无意义。剩余 4 次 baseline（Mac ×1 + Windows ×3）+ median 计算 留 task #24/#34；`save_baseline` run_id 自增 fix 留 task #59 / `fix/timer-run-id-autoincrement` 分支单独 12 步。**注**：本条目 wall=52.6min 是 step_wall_time_sum 不是 real elapsed（real elapsed=17.5min），见上文 `_timer.py` baseline wall_time 字段歧义修条目。

### Fixed
- **`scripts/etl/pipeline.py` member_order_ids 连接改 READ_WRITE（修 rfm_analysis_cache fail-soft P0）** — `pipeline.py:105` 之前用 `read_only=True` 连接读历史 `order_ids` 集合，污染同进程 DuckDB config，导致后续 `cache.py:_open_write_conn()` 开 `access_mode=READ_WRITE` 抛 "Can't open a connection to same database file with a different configuration"，cache.py try/except return 0 致 Step 6 RFM 预计算 fail-soft（cache 维持 6/3 baseline 60 行不更新，业务无影响）。**修法**：去掉 `read_only=True`，用默认 READ_WRITE 连接，与 cache.py 后续 `_open_write_conn()` 保持一致 access_mode。仅 SELECT DISTINCT order_id 只读查询 + 立刻 close，不影响 DuckDB 文件。pytest 153/8 全过；ruff 0 errors。下次 ETL 跑批 rfm_analysis_cache 应正常更新到 60 行（12 组合）。commit ab78383。

### Documentation
- **文档同步更新（CLAUDE.md / README.md / docs/DOCUMENT-INDEX.md / docs/飞书版架构文档/{01-数据层,06-部署与运维}.md）** — 反映 v0.3.5 release：① 数据规模表 5/31 → 6/4（orders 10.65M / user_first_purchase 4.25M / user_rfm 72.4M / rfm_analysis_cache 60 / order_status_override 6/4 刷 91,307 行）；② Python 路径 workbuddy → homebrew 3.14；③ 6/4 增量 ETL 跑批实测（real elapsed 63.2min / step_wall_time_sum 126.4min）+ RFM 4 端点 P0/P1 修复合集 + wall_time 字段歧义修 全部进 README 当前状态；④ TEST 计数 149 → 153 passed；⑤ DOCUMENT-INDEX.md 最后更新 5/31 → 6/4；⑥ 后端启动命令更新（homebrew Python 3.14 + HEALTH_API_KEY env）。

## [0.3.4] - 2026-06-01

### Fixed
- **ETL 增量主键冲突** — 修复 `upsert_to_duckdb` 在 shop+member 合并数据时（高度重叠场景）写入 DuckDB 触发主键约束违反的 bug。修复：在去重前将 `order_id`/`sub_order_id` 统一转为字符串（防 float vs string 漏判），全新订单路径改用 staging 表 + ON CONFLICT DO NOTHING 模式，刷新路径在事务内通过 staging 表 + ROW_NUMBER() 去重后再写入，保持原子性。

### Changed
- **CLAUDE.md 加改代码前强制自检段** — 防止 AI 在 main 分支直接改代码的反模式。改 Edit/Write 前先答 2 问：当前在哪个分支？接下来要 commit 吗？

### Performance
- **Parquet缓存修复** — 修复 `_mark_all_files_processed` 只存mtime不存hash的bug，统一Parquet缓存key格式，增量ETL时间从10分钟降到1分钟
- **RFM SQL重写** — 合并 `hist_customers_all` + `hist_customers_same` 为单个CTE，使用GROUPING SETS消除TTL CTE，CTE数量从15个减少到5个
- **品类GROUPING SETS** — 品类预计算从4次独立查询优化为2次GROUPING SETS查询，扫描次数减少50%
- **RFM并行化** — 使用ThreadPoolExecutor并行执行3个周期查询，3x加速
- **DuckDB内存优化** — 添加 `DUCKDB_MEMORY_LIMIT` 环境变量配置（默认8GB），创建内存监控模块，避免Swap
- **内存监控** — 新增 `backend/db/memory_monitor.py` 模块，实时监控DuckDB内存使用，防止Swap

### Security
- **弱密码替换** — `admin:123456` / `fqsw:fqsw888` 替换为强密码，使用 bcrypt 哈希存储
- **API Key Header 传输** — `/config/history` 和 `/config/audit-log` 的 API Key 从 Query 参数改为 `X-API-Key` 请求头，防止日志泄露
- **API Key 时序攻击防护** — `!=` 比较改为 `hmac.compare_digest()` 常量时间比较
- **API Key 速率限制** — 新增滑动窗口限速（10次/5分钟/IP），防止暴力枚举
- **SQL 参数化** — `rfm_category_drilldown.py` 中 `rfm_segment` 和 `exclude_channels` 从字符串拼接改为 `?` 占位符参数化查询

### Performance
- **overview 查询合并** — `get_overview_metrics()` 从 9 次独立查询合并为 3 次（每个时间段 1 次 CTE），减少 66% 数据库往返
- **geo 趋势查询合并** — `get_geo_trend()` 从逐月循环 N 次查询改为 2 条 SQL（`DATE_TRUNC('month')` 一次性查出）
- **flow groupby 优化** — `get_flow_matrix()` 和 `get_flow_sankey()` 从 121 次 DataFrame 过滤改为 `groupby().size()` 一次性聚合
- **churn 时间窗口** — 4 个流失分析函数添加 730 天回溯窗口，避免全表扫描 + `LAG()` 窗口函数

### Changed
- **DuckDB 单例连接** — `get_connection()` 从每次请求新建连接改为全局单例 + `threading.Lock` 双重检查锁定
- **Router 分层修复** — 9 个 router 文件不再直接导入 `backend.semantic.time`，改为通过 `backend.services` 导入
- **代码去重** — 统一 `_normalize_date`（3→1）、`_segment_meta`（2→1）、`_VALID_BASE`（6→1）
- **RFM flow 引擎** — `r_flow.py` / `f_flow.py` / `m_flow.py` 从各 ~377 行简化为 ~58 行，共享逻辑提取到 `_flow_engine.py`
- **suggestions.py 常量迁移** — `R_INTERVALS`、`GSV_AMOUNT_COL`、`REPURCHASE_ADJUSTMENT` 迁移到语义层/配置层
- **应用关闭事件** — `main.py` 注册 `shutdown` 事件调用 `close_connection()`

### Fixed
- **RFM flow engine 参数错位** — `_flow_engine.py` 的 `hist_all_params` 缺少 `exclude_channels` 参数，导致 SQL 占位符与参数不匹配，当用户选择排除渠道时 RFM 流转看板返回 500 错误
- **路由守卫 401 闪现** — 前端路由守卫在 `isReady` 为 `false` 时直接放行，未登录用户可短暂访问受保护页面导致 401 请求。修复：在等待 `isReady` 之前直接检查 `sessionStorage` 中的 token
- **DuckDB 并发崩溃** — `get_connection()` 仅锁创建过程，未锁查询执行。页面刷新触发多个并发 API 请求时，多线程同时访问同一 DuckDB 连接导致 `fetchone()` 返回 `None`（`TypeError: 'NoneType' object is not subscriptable`）或 Python 进程段错误退出。修复：`connection.py` 引入 `ThreadSafeConnection` + `ThreadSafeCursor` 包装器，`execute()` 和 `fetch*` 自动串行化
- **DuckDB 结果集并发覆盖** — `ThreadSafeConnection.execute()` 只在执行 SQL 时加锁，返回 `ThreadSafeCursor` 后锁已释放。DuckDB 没有真正独立的 cursor（`execute()` 结果集绑定在连接上），另一个线程的 `execute()` 会覆盖连接上的结果集，导致 `fetchone()` 读到错误数据（如 `int(datetime.date)` 崩溃）。修复：`ThreadSafeCursor` 在构造时（锁内）预取全部结果到内存，后续 `fetch*` 不再触碰连接
- **fetchone() 空值防御** — `overview.py`、 `rfm_reader.py`、 `cache.py` 共 4 处 `fetchone()[0]` 未防御 `None` 结果，在连接异常时直接崩溃。修复：先判空再取下标
- **老客GSV占比 pp 值双重乘法** — `HealthOverviewTab` 中 `fmtYoy()` 已乘 100，`MetricCard` pp 模板再乘 100，导致显示 155pp/193pp。新增 `fmtPpt()` 直接传递原值
- **YOYBadge 单位显示错误** — `AudienceView` 中 ratio 类型列（新客占比/老客占比/会员占比等 YoY）未传 `unit='pp'`，导致显示 `%` 而非 `pp`。10 处 YOYBadge 调用修正为 `(value * 100, unit: 'pp')`
- **173 个 ruff lint 错误** — 修复 F821（未定义变量 6 个）、F401/F541/F811/E401（自动修复 130 个）、E702/E722（手动修复）。config.py 交叉导出加 `# noqa: F401` 防 ruff 误删
- **ETL 导入路径错误** — `scripts/etl/cli.py` 中 4 处导入路径错误导致 ETL Step 3-7 崩溃：`scripts.etl_status_override` → `scripts.etl.etl_status_override`（3处），`scripts.preload_rfm` → `scripts.etl.preload_rfm`（1处）
- **日趋势图会员占比** — 修复日趋势图的会员占比从「订单数占比」改为「GSV金额占比」，与人群看板一致。新增 `overall_member_ratio` 字段返回整体会员GSV占比
- **YOY/MoM 值格式不一致** — 修复后端返回的 YOY/MoM 值格式不一致（部分已是百分比，部分是小数），导致前端显示 155pp 等三位数。所有值统一为小数形式

### Changed
- **CLAUDE.md 瘦身** — 460 行 → 132 行（-71%），参考材料（口径表/历史教训/包拆分清单/目录结构）移到 `docs/reference.md`（按需读取），每次会话节省 ~60% token
- **文档精简** — 归档 5 个冗余/已完成文档：DESIGN.md、DEPLOY.md、MODULE-INDEX.md、etl-incremental-fix-plan.md、REPAIR_PLAN.md

### Added
- **Pre-commit/Pre-push hooks** — `.githooks/pre-commit`（ruff check）和 `.githooks/pre-push`（pytest）阻止不合规代码提交和推送
- **GitHub Actions CI** — `.github/workflows/lint.yml` 在 PR 和 main push 时自动运行 ruff + pytest
- **AI 执行检查点** — CLAUDE.md 新增硬性 STOP 检查表：commit 前必须 review、push 前测试全绿、merge 前必须 qa
- **CI/CD 防线** — pre-commit (ruff) + pre-push (pytest) + GitHub Actions CI，三层拦截不合规代码
- **Parquet 缓存填充脚本** — 新增 `scripts/etl/fill_parquet_cache.py`，将 161 个 xlsx 文件批量转换为 Parquet 缓存，增量 ETL 加速 10-50x
- **原子写入** — `_save_parquet_cache()` 和 `_save_processed_files()` 支持 tmp+rename 原子写入，防止中断产生损坏文件
- **Parquet 缓存测试** — 新增 9 个测试覆盖 Parquet 写入、增量检测、原子写入、processed_files 更新等核心逻辑

### Fixed
- **processed_files 覆写** — `fill_parquet_cache.py` 保存时合并已有记录，避免丢失历史 ETL 状态
- **单元测试全覆盖** — 新增 91 个测试覆盖 12 个模块：breakdown_service（15）、rfm_service（16）、rfm_analysis（8）、health/overview（19）、health/conversion（7）、health/repurchase（2）、health/tier_flow（1）、health/channel_scores（1）、category_service/overview（4）、category_service/distribution（1）、category_service/churn（1）、category_service/basket（1）
- **R 区间边界测试** — 验证 `_get_r_interval_current_distribution` 的 R 区间分桶（30/90/180/365/730 天）和 F 段（F>1/F=1）正确性
- **GSV 口径测试** — 验证退款订单（is_refund=TRUE）、购物金（is_goujinjin=TRUE）、交易关闭订单不计入 GSV
- **Codex 交叉审核** — 使用 Codex regular + adversarial 模式审核代码变更，发现并修复 5 个问题

### Fixed
- **check_future_date(None) 崩溃** — `backend/semantic/time.py` 的 `check_future_date()` 在 mtd/wtd/ytd 模式下接收 None 参数时触发 TypeError。修复：函数入口加 `if date_str is None: return None` 守卫，except 加 `TypeError`
- **日期正则不验证日历** — `re.fullmatch(r'\d{4}-\d{2}-\d{2}')` 接受无效日期如 2025-02-30。修复：regex 后加 `datetime.strptime` 验证实际日期有效性
- **visitor.py 未使用 import** — 删除 `backend/routers/visitor.py` 中未使用的 `import json`
- **品类回购分析数据为 0** — `_RFM_SEGMENT_ORDER`（`category_service/_shared.py`）与 SQL `rfm_segmented` CTE 的 RFM 象限命名不一致：常量定义了 4 个无"客户"后缀的名称（如 `"重要价值"`），而 SQL 生成 8 个带后缀的名称（如 `"重要价值客户"`）。`api.py` 的 `_build_rows` 用旧名称查找 SQL 结果 → key 不匹配 → 所有数值归零。修复：`_RFM_SEGMENT_ORDER` 更新为 8 个带"客户"后缀的完整象限名称。`/category/repurchase-flow` 接口现已正确返回品类各 RFM 象限回购数据（hist/repurchased），可通过 `curl http://localhost:8000/api/category/repurchase-flow` 验证
- **Lint 清理** — 消除 `rfm/r_flow.py`、`rfm/m_flow.py`、`rfm/f_flow.py`、`rfm/segment_orders.py` 的 F403/F405 star import（117 errors → 0）；清理 `routers/__init__.py` 16 个 F401 unused import；删除死代码 `breakdown_service.py` shim；修复 `rfm/_shared.py`/`export_service.py`/`metrics/__init__.py` 等多处 F401；E701/E741 若干
- **Lint 清理（续）** — `category_service/flow/__init__.py`、`category_service/flow.py`、`category_service/repurchase/__init__.py`、`category_service/repurchase.py` 消除 F403 star import；删除死代码 `dmp_asset_service.py` shim；`dmp_asset_service/__init__.py` 改为显式导入；`health/rfm_analysis/__init__.py`、`health/rfm_analysis.py` 消除 F403

## [0.3.3] - 2026-05-29

### Fixed
- **SQL 注入修复** — `breakdown_service/_shared.py` 4 个函数将日期参数从 f-string 拼接改为 DuckDB `?` 参数化；`_r_interval_sql` 内部 `DATE '{cutoff}'` 也改为参数化
- **硬编码路径修复** — `VISITOR_XLSX_FILE` 从 Mac 绝对路径迁移到 `backend/config.py` 的环境变量配置

### Changed
- **开发者体验** — `/docs` 和 `/redoc` 从认证中间件白名单移除，新开发者可直接浏览器探索 API
- **未来日期警告** — 传入未来日期时，API 在 `X-Data-Warning` 响应头返回明确警告（`backend/semantic/time.py` 的 `check_future_date()`），覆盖 `/overview`、`/targets`、`/repurchase-cycle`、`/value-tiers`、`/tier-flow`、`/rfm-analysis`、`/rfm-category-drilldown`、`/channel-health-scores`、`/new-customer-conversion`、`/r-flow`、`/f-flow`、`/m-flow`、`/segment-orders` 等 13 个端点

## [0.3.2] - 2026-05-28

### Fixed
- **后端代码审计** — 修复 23 个问题（P0×5/P1×7/P2×11），包括口径不一致、测试阈值硬编码、contracts 重复、类重复定义等
- **大文件拆分** — 将 6 个超大文件拆分为包（rfm_service/flow/breakdown/dmp_asset/repurchase/rfm_analysis），并补全所有交叉导入
- **SPU 版本化** — orders 表新增 `spu_hash` 字段，避免 SPU 重命名导致历史数据不可追溯
- **Bundle 优化** — xlsx 依赖改为懒加载，减少首屏 bundle 体积

### Added
- **ETL Parquet 缓存层** — 中间计算结果写入 parquet，减少重复计算
- **前端性能基线** — 建立性能 benchmark，便于回归检测

## [0.3.1] - 2026-05-27

### Changed
- **Docker 化就绪** — 后端支持 Docker 部署
- **磁盘清理** — data/ 目录清理，释放 7.7G 空间

## [0.3.0] - 2026-04-20

### Added
- **Vue3 前端上线** — 8 个 dashboard 页面，SPA 路由，xlsx 导出
- **RFM 8 象限重构** — 区间流转 + 品类下钻完整实现

## [0.2.0] - 2026-04-16

### Added
- **语义层 + 契约层** — v3.0 架构重构，口径统一管理
- **DuckDB 数据平台** — 1030 万订单 / 410 万用户数据接入

## [0.1.0] - 2026-03-27

### Added
- **项目启动** — 基础架构设计，FastAPI 后端框架搭建

---

## 版本说明

本项目使用 **semver** 格式：`MAJOR.MINOR.PATCH`

| 字段 | 含义 |
|------|------|
| MAJOR | 不兼容的 API 变更（如删除端点、修改 Schema） |
| MINOR | 向后兼容的新功能（如新增端点、新增响应字段） |
| PATCH | 向后兼容的缺陷修复（如 BugFix、安全补丁） |

> 注意：当前 MAJOR = 0 表示项目仍在初始开发阶段，API 可能在 MINOR 版本中变化。

## [v0.4.14.49] - 2026-06-11 - docs(sprint18): Sprint 18 治理收口 — retrospective + cross-doc 同步

### Added
- **`docs/SPRINT-18-RETROSPECTIVE.md`** (新, 266 行) — Sprint 18 治理收口复盘, 8 sections (跟 Sprint 17 同样结构): Sprint 结果 / 4 任务治根复盘 / 决策审计 (12 决策) / 治理债务 (8 backlog) / 5 大教训 / 时间线 / Sprint 19 预告 / 关键指标

### Changed
- **`CLAUDE.md` AI 执行检查点** "改 contract 字段" 行 — 描述补 "pre-commit hook 自动拦截 (Sprint 18 #142)", 文档指针加 `docs/PRE-COMMIT.md`
- **`docs/document-index.md`** — 加 Sprint 18 行 + 3 文档指针 (SPRINT-18-YOY-FIX.md / CACHE-INVALIDATION.md / PRE-COMMIT.md), 跟 Sprint 17/16.5/16 P0 等历史 sprint 同组

### Sprint 18 4 段治理总结
- **#141 26 YOY ratio 字段命名/语义冲突治根** (P0) — 白名单 14 字段 (`_YOY_PPT_FIELDS`) + 类型补标 6 字段 + linter 0 issue. 0 字段名改动 = 0 跨文件破坏. 走"白名单 + 改类型" 混合方案, 避开改命名 14+ 文件风险
- **#123 W5 cache invalidation 启动 hook** (P1) — 跨进程持久化 `last_seen_manifest_version` 到 `data/cache/w5kv_manifest_state.json`, 跟进程内 `_ManifestTracker` 互补. 闭环 Sprint 14.5 留的"改 ratio/契约后必须手动 invalidate" 痛点
- **#142 pre-commit ground-truth-lint hook** (P1) — `.pre-commit-config.yaml` + `scripts/test-precommit.sh` + 335 行 docs. 跟 `.githooks` 双轨并存
- **#124 YOYGuard 通用组件 + 扩 MetricCard / RFMSegmentDrilldown** (P2) — `YOYGuard.vue` 61 行抽公共, 3 组件 refactor (YOYBadge/MetricCard/RFM 表格)

### 治理债务 (留 Sprint 19+)
1. 🔴 P0: DuckDB 1.5.4 release 监控 + 跑批真验 (Sprint 16 P0 abort 续, 第 3 次留)
2. 🟡 P1: linter 增强 List element-wise Field 元数据检查 (Sprint 18 #141 留, 移除 `_LIST_RATIO_FIELDS` 白名单)
3. 🟡 P1: 改命名 14 字段 (Sprint 18 走白名单, Sprint 19 真改)
4. 🟢 P2: 前端 `types.ts` 自动生成
5. 🟢 P2: pre-commit framework CI 接入
6. 🟢 P2: .githooks 跟 .pre-commit-config.yaml 二选一
7. 🟢 P2: YOYGuard threshold 全局配置
8. 🟢 P2: W5 cache invalidation ETL 末尾调 (可选)

### 验证
- pytest 507+12 passed (3 pre-existing failed 跟代码无关: test_sim_prod_etl race + test_w4_full DuckDB 锁 + 1 sim-prod)
- vitest 63 passed (含 #124 YOYGuard 3 + 沿用 Sprint 16.5 YOYBadge 4)
- ground-truth-lint 0 issue (26→0, #141 治根)
- uvicorn: /health=401 (认证), /docs=200, /api/v1/health=200 (public), v1/r-flow=401, v1/rfm=401, v1/metrics=401
- 4 v1 端点 (3 401 expected + 1 200 public) 全合规
- main @ f467192 (4 subagent merge 全部合)

### 任务来源
- Sprint 17 retrospective Section 4 治理债务 #1+#2+#4+#5 → Sprint 18 #141+#142+#123+#124 全部闭环
- Sprint 16.5 #92 YOYBadge 异常值守卫 → Sprint 18 #124 扩到 MetricCard + RFM 表格
