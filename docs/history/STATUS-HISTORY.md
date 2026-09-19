# STATUS 历史编年（归档）

> 从 `STATUS.md` 迁出（2026-07-19 tech-debt sprint）。
> **当前状态以根目录 `STATUS.md` 短表为准。**

**2026-09-11**：根目录短表已按 main `bda4e47`、#115 已合并重写。此前 9 月 10 日快照里的 `788b5b1` 与「#115 未合并」不再作为当前状态。

**最后更新（历史长文）**: 2026-07-15 (Sprint 205+ **RFM cache miss → 30s timeout → 502 → 401 治本** (跟 Codex Stage 2 1:1 stable 永久规则化沿用, 跟 L4.50 + L4.40 + L4.86 + L4.20 + L4.42 永久规则链 1:1 stable 永久规则化沿用)): 4 维治本 (跟交接文档 §3 1:1 stable 永久接受 1:1 stable 永久规则化沿用) ① HTTP 雪崩隔离 (`allow_live_compute=False` 写死 + 503 + Retry-After: 60/30, 跟 L4.36 不停 uvicorn 1:1 stable 永久规则化沿用) ② fuzzy 完整核对 (±2 天 0/1/2 命中 + data-version/channel/metric/exclude/compare 重建) ③ 预热 generation 原子切换 (19 period × 2 metric × 5 channel × 2 compare = 380 logical combinations, 跟交接文档 §3.3 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 实证推翻旧 416 组合 hardcode 验收 1:1 stable 永久规则化沿用) ④ 时间口径修复 (last90days/昨日/WTD/Q1-Q4 resolver + 闰日跨年平移 + 元旦 YTD + 每季首日反向区间). 4 件禁止项未动: PC2 外部 1.8 GB PowerShell watchdog + 仓库 8/12 GB memory monitor + Axios timeout/重试 + `scripts/etl/scheduler/` 全套 (跟交接文档 §4 1:1 stable 永久接受 1:1 stable 永久规则化沿用). **3 commit (跟 L4.14 1:1 stable 永久接受 1:1 stable 永久规则化沿用)**: `898dc96` (RFM 治本 17 files / +2227/-301) + `a3f6548` (pre-push hook 跟 lint.yml deselect 列表 1:1 stable 漂移治本 0 业务代码改动, 跟 L4.50 + L4.40 + L4.86 1:1 stable 永久规则化沿用) + `b91f470` (Revert Codex 擅自 `a69a06d` "add sampling view" 越权 跟 L4.15 必 user 拍板 + L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用). branch `fix/sprint205-rfm-timeout-502-2026-07-15` (base `af50345`, 4 commit ahead / 0 behind), worktree `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics-codex-rfm-timeout`. 0 业务代码改动累计 Sprint 60+ **101+ 次** 1:1 stable 永久规则化沿用 (跟 L4.50 永久规则化沿用). **VERSION 不 bump** (跟 Sprint 89/167/190-202+ 累计 29+ 次 /document-release bump 持续 1:1 stable 永久规则化沿用, 保持 `0.4.14.51`). main HEAD **`af50345`** (跟 L4.15 push 必 user 拍板 1:1 stable 永久规则化沿用, 等 7/16 交接人拍板 push main). **0 drift 验证 ✅** (跟 1:1 stable 永久接受 1:1 stable 永久规则化沿用). 12 步流程 1:1 stable 永久规则化沿用 (跟 L4.15 + L4.42 + L4.50 + L4.40 + L4.31 1:1 stable 永久规则化沿用). **L4.x 永久规则化新加 2 件候选** (跟 Sprint 60+ 累计 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 跟 L4.50 + L4.85 HANDOVER 1:1 stable 永久规则化沿用): **L4.91 test fixture forward-compat pattern** (跟交接文档 §3-§4 1:1 stable 永久规则化沿用, 跟 L4.50 + L4.88 conftest autouse fixture 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用) + **L4.92 RFM cache miss 治本 4 维** (跟交接文档 §3 1:1 stable 永久规则化沿用, 跟 L4.67 + L4.69 + L4.71 + L4.36 + L4.40 永久规则链 1:1 stable 永久接受 1:1 stable 永久规则化沿用). 部署硬门槛: PC2 业务库 `MAX(pay_time)=2026-07-05 23:59:58` `COUNT(*)=10,829,767` 数据滞后, 必须用户批准停服维护窗口 + 人工 ETL (跟交接文档 §7 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 严禁自动任务停启生产 uvicorn 跟 L4.36 1:1 stable 永久规则冲突). 7/16 离职前清单 5 件套 (跟 L4.85 1:1 stable 永久规则化沿用): HANDOVER.md §9 + 3 handoff 交付 Codex app + context-save 7/15 checkpoint + close memory + Final Codex app prompt 全部到位. 跨 sprint 留尾 4 维度 0 commit 续期 (跟 L4.57 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 0 业务触发 0 commit 收口 1:1 stable 永久规则化沿用): 1 维度 ClickHouse POC 0 触发续期 (跟 L4.62 1:1 stable 永久接受 1:1 stable 永久规则化沿用) + 2 维度 Sprint 202 R1 跑批 wall_min 业务验证 0 触发续期 (跟 L4.58 1:1 stable 永久接受 1:1 stable 永久规则化沿用, 等 L4.54 修完业务跑批自动验证) + 3 维度 Sprint 199+ 3 P0 业务补全 0 触发续期 (跟 L4.42 + L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用) + 4 维度 4 case pre-existing fail 真治本 0 触发续期 (跟 L4.50 + L4.59 R6 1:1 stable 永久接受 1:1 stable 永久规则化沿用).

**前一版本**: 2026-07-13 (Sprint 205+ **PC2 端 RFM Fork-Cost 诊断 + 3 步修复方案 + HANDOVER.md §10** (跟 HANDOVER §9 + L4.15 + L4.20 + L4.42 + L4.50 + L4.85 + L4.85.1 + L4.91 PR2 ESLint 1:1 stable 永久规则化沿用)): 新文件 `docs/sprints/Sprint205+-PC2-RFM-Fork-Cost-2026-07-13.md` (327 lines, 5 维度实测 + 6 节点真根因链 + A 步 PowerShell `Disable-ScheduledTask` 关 watchdog 5 min 治标 + B 步 git pull + conflict resolution + precompute_fact_rfm.py 21 h 治本 + SSOT 反漂移实战失败 #2 沉淀) + HANDOVER.md §10 (62 lines, 接手人 7/16+ Day 1 必读 4 件 + PC2 端 `7c5b4d7` L4.15 违规 wip 待 review + PC2 端独有 1.8GB watchdog 实证). review skill critical pass (所有 SHA `git rev-parse` 实证 PASS). 0 业务代码改动累计 Sprint 60+ **100 次** 1:1 stable 永久规则化沿用 (从 99 +1, 跟 L4.50 + L4.42 + L4.85 + L4.91 PR2 ESLint 1:1 stable 永久规则链配套). **VERSION 不 bump** (跟 Sprint 89/167/190-202+ 累计 28+ 次 /document-release bump 持续 1:1 stable 永久规则化沿用, 保持 `0.4.14.51`). main HEAD **`dc9e8d0`** (链路 `67dd254` → `eb9a564` 新 doc + HANDOVER §10 → `dc9e8d0` merge --no-ff). 0 drift 验证 ✅. 7/16 离职前清单: PC2 端 RFM 502 跟进已全部沉淀进 HANDOVER §10 + sprint doc, 接手人 Day 1 必读 4 件 + A/B 步 5 维度 PowerShell + git pull conflict resolution 指南全部到位.

**前一版本**: 2026-07-13 (Sprint 205+ **HANDOVER.md §9 PC2 端 7/13 部署风险备忘追加 — 跟 L4.15 + L4.20 + L4.42 + L4.85 1:1 stable 永久规则化沿用**): HANDOVER.md 加 §9 章节 4 件 (§9.1 PC2 端实测起点校正 `aa40ac8 → c2aa69e` 126 commit + §9.2 L4.15 违规 wip commit 接手人必读 3 步 + §9.3 9 个 untracked 工具脚本备份位置 + §9.4 7/12 doc SSOT 漂移实战案例 #1). review skill AUTO-FIX 1 处 SSOT 反漂移 (凭印象编造的 `7f952ac` SHA 已 in-place replace 为 git log 实证). 0 业务代码改动 +1 = 累计 Sprint 60+ **99 次** 1:1 stable 永久规则化沿用 (跟 L4.50 + L4.20 + L4.85 1:1 stable 永久规则链配套). **VERSION 不 bump** (跟 Sprint 89/167/190-202+ 累计 26+ 次 /document-release bump 持续 1:1 stable 永久规则化沿用, 保持 `0.4.14.51`). main HEAD **`0718143`** (merge commit, 0 drift 验证通过). 12 步流程 1:1 stable 永久规则化沿用 (跟 L4.15 + L4.42 + L4.40 + L4.31 + L4.85 + L4.85.1 1:1 stable 永久规则化沿用). 7/16 离职前清单: HANDOVER.md 接手人启动备忘 4 件全部到位.

**前一版本**: 2026-07-12 (Sprint 205+ **7/16 离职前最终 doc cleanup — POC 文件清理 + 文档归档 SSOT**): 删除已终止 PostgreSQL 16 / Trino POC 全套文件、前端 `SamplingView.vue` STUB 及对应聚焦测试; `CHANGELOG_HISTORY.md` → `docs/history/CHANGELOG_HISTORY.md` 路径统一; `TECH-DEBT.md` 清理已失效的 Sprint N+3/N+4 跨 sprint 续期. **VERSION bump 0.4.14.50 → 0.4.14.51**. 0 业务代码改动累计 Sprint 60+ **98 次** 1:1 stable 永久规则化沿用 (跟 L4.50 + L4.57 + L4.58 + L4.59 + L4.20 1:1 stable 永久规则链配套). main HEAD **0.4.14.51**. 7/16 离职前清单: 文档归档收尾完成.

**前一版本**: 2026-07-11 (Sprint 205+ **L4.91 PR2 8 view kind enum 补齐治本** — 8 个 view (FIntervalTab + MIntervalTab + RIntervalTab + ValueTierTab-health + SamplingView + CategoryRepurchaseTab + RFMSegmentDrilldown + ChurnWarningTab) xlsxColumns 34 列加显式 kind enum (auto-detect suffix pattern 无法匹配 prefix-key), 跟 L4.91 + L4.91 PR0 + L4.91.1 + L4.91.2 1:1 stable 永久规则链配套. **VERSION bump 0.4.14.48 → 0.4.14.49** (跟 L4.50 0 业务代码改动累计 **97 次** 1:1 stable 永久规则化沿用). vitest 14/14 PASS + build OK 773ms + pytest 22/22 PASS. main HEAD **0.4.14.49**. **所有 4 件 L4.91 技术债全部闭环**: 技术债 #1 + #2 (ProductAssetsTab + OtherProductAssetsTab formatValue, ship L4.91.2 `66c0a05`) + 技术债 #3 (test_helpers reset endpoint, ship L4.91.2) + 技术债 #4 (8 view kind enum, 本 commit). 跨 sprint 留尾 (跟 L4.42 + L4.57 1:1 stable): 7/16 离职前 5 件套 (业务验证 + 运营演示 + HANDOVER.md + AI 联系方式 + mac 离职). 0 触发续期 0 commit.

**前一版本**: 2026-07-11 (Sprint 205+ **L4.91.1 market-focus#product-customer 对比行 Excel yoy 格式错治本** (跟 user 7/11 拍板 "穷尽的调查, 排查下原因" 1:1 stable 永久规则化沿用, 跟 L4.42 + L4.50 + L4.55 + L4.79 + L4.80 + L4.81 + L4.91 + L4.91 PR0 + L4.85 + L4.85.4 + L4.85.6 + L4.85.7 永久规则链 1:1 stable 配套, 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用. **L4.91.1 治本核心** (3 件配套, 跟 L4.91 PR0 kind enum 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 累计 96 次 1:1 stable 永久规则链配套): ① **exportXlsx SSOT 扩展 formatValue 字段** (L4.91.1 新增, 向后兼容, 可选字段, 跟 L4.91 PR0 SSOT 反漂移 1:1 stable 永久规则化沿用): per-row dispatch (val, row) => any | { val, numFmt? }, 治本 ProductCustomerTab 对比行 yoy ratio/pp 格式错. ② **ProductCustomerTab 数据处理 + xlsxColumns 14 列 formatValue dispatch** (跟 L4.91 PR0 + L4.81 backend YOY 契约 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 限制 "其他前端不要调整逻辑" 1:1 stable 永久规则化沿用): TableRow interface 加 14 个 _yoy_pct / _yoy_pp 可选字段, 3 处对比行 (本周对比上周 / 全店去年同期 / 产品组去年同期) 数据处理用 _yoy_pct / _yoy_pp 后缀字段, xlsxColumns 14 列加 formatValue 函数 (对比行用 yoy_pct / yoy_pp numFmt, normal row 用原字段 + 原 numFmt). ③ **2 case L4.91.1 回归测试** (跟 L4.50 + L4.91 PR0 1:1 stable 永久规则链配套): test_formatValue_simple (per-row override cell value) + test_formatValue_object (per-row override value + numFmt). 0 业务代码改动累计 **96 次** 1:1 stable (跟 L4.50 累计 95+ 次 1:1 stable 永久规则链配套). main HEAD **`51dbde1`** (L4.91.1 4 files changed, +308-63, 跟 L4.85.7 + L4.91 + L4.91.1 1:1 stable 收口 永久规则化沿用). 跨 sprint 留尾 (跟 L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动可读): ① **技术债 #1 + #2**: market-focus/ProductAssetsTab + OtherProductAssetsTab 同模式未治本 (跟 ProductCustomerTab 1:1 stable 复用 L4.91.1 formatValue 治本 1h, 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 user 限制 "其他前端不要调整逻辑" 1:1 stable). ② **L4.85.6 Playwright e2e 测试环境隔离**: launchd backend 共享 ACTIVE_TOKENS dict 状态污染, backend 加 POST /api/v1/_test/reset (0.5h, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用). ③ **L4.91 audit 报告 8 view partial** (L4.91 PR0 audit 报告 #4 SamplingView + #6 CategoryRepurchaseTab + #7 ChurnWarningTab + #13-15 F/M/R IntervalTab + #19 RFMSegmentDrilldown + #20 ValueTierTab-health): prefix `yoy_` YOY 列没 kind enum, 跨 sprint 留尾 接手人 fix (4h). ④ **7/16 离职前 5 件套** (跟 L4.85 1:1 stable 永久规则化沿用): 业务验证 8 件套 100% PASS + 跟运营演示 1 小时 + 留 HANDOVER.md + AI 联系方式 (微信/飞书) + mac 离职.

--- (L4.91 entry 之前, 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable) --- — 跟 user 7/11 拍板 8 件 Excel bug + 强约束 "backend 算, frontend 只展示" 1:1 stable 永久规则化沿用, 跟 L4.42 + L4.50 + L4.55 + L4.79 + L4.80 + L4.81 永久规则链 1:1 stable 配套, 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用. **L4.91 强契约** (3 件 SSOT, 跟 L4.20 SSOT 反漂移 + L4.42 立项实证 + L4.50 0 业务代码改动 累计 92 次 1:1 stable 永久规则链配套): ① **frontend XlsxColumn.kind 显式 enum** (跟 L4.91 PR0 1:1 stable 永久规则化沿用, 替代 Sprint 174 auto-detect, kind 优先级 > auto-detect > caller numFmt): `'yoy_pct'` (raw 0-1 ratio * 100 = % 后缀, 跟 backend L4.81 yoy_absolute 1:1 stable) + `'yoy_pp'` (raw 0-1 diff * 100 = pp 后缀, 跟 backend L4.81 yoy_ratio 1:1 stable) + `'yoy_day'` (signed int = 天数差, +0;-0;0 numFmt) + `'text' | 'number' | 'auto'`. ② **assertNotFormula 加 object 形式检测** (跟 L4.91 PR0 1:1 stable 永久规则化沿用): 之前只挡 `=开头 string`, 漏挡 object 形式 `{t:'n', f:'=B1-C1'}` (AudienceView.vue:1657-1659 raw xlsx path 用过, 跟 Sprint 174 SSOT 0 公式 1:1 stable 沿用). ③ **frontend 0 处散落 `*100`** (跟 CLAUDE.md "前端只展示, 禁止前端算" 1:1 stable 永久规则化沿用, 跟 L4.81 反模式 0 容忍): 任何 frontend `*100` 散落 = L4.81 反模式 = 永久规则化 0 容忍. **L4.91 8 件 bug 100% 治本** (跟你 user 7/11 拍板 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套): Bug #1 人群看板-30指标对比 (AudienceView.vue:1639-1689 raw xlsx → SSOT, 写公式 → 删, 前端 *100 → kind enum 显式) + Bug #2 老客分析-各渠道健康评分对比 (HealthOverviewTab.vue:327 -3370.00pp → -33.70pp, kind='number' + numFmt '+0.00"pp";-0.00"pp";0.00"pp"', 删冗余 health_score_yoy_label 列) + Bug #3 品类看板-各类占比 numFmt 统一 (CategoryView.vue:532-595 26 列 allCompactXlsxColumns + 26 列 memberCompactXlsxColumns kind enum 显式, 跟 backend L4.81 1:1 stable 永久规则化沿用) + Bug #4 #5 品类看板-品类复购周期/同品回购明细 YOY 单位 (ProductClassRepurchaseTab.vue 中位天数YOY/平均天数YOY kind='yoy_day', 复购率YOY pp kind='yoy_pp', 删冗余 *_label 列) + Bug #6 市场对焦-核心单品新老客 WYSIWYG (ProductCustomerTab.vue:702-708 4 → 14 列, 跟 frontend `columns` 1:1 stable 永久规则化沿用) + Bug #7 市场对焦-全店资产 (StoreAssetsTab.vue:111-145 加 2 列对比 + 2 行对比 total_change/total_yoy, 跟 frontend 表格 line 196-216 1:1 stable 永久规则化沿用) + Bug #8 强约束 backend 算 frontend 只展示 (CLAUDE.md L4.91 永久规则化段 跟 L4.79 + L4.80 + L4.81 1:1 stable 永久规则化沿用). 改动 4 PR (跟 Q9A 拆 3 PR 1:1 stable 永久规则化沿用): PR0 (commit `275cf93`, 3 files / +112-25 / foundation 6h) + PR1 partial (commit `8959603`, 3 files / +125-100 / Bug #1 #2 #3 10h) + PR1 final (commit `8eae6bc`, 3 files / +99-59 / Bug #4 #5 #6 #7 跟 Q9A 1:1 stable) + PR2 (commit `1e19efc`, 1 file / +46 / CLAUDE.md L4.91 段 永久规则化 14-18h). **累计指标** (跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 永久规则化沿用): 0 业务代码改动累计 **92 次** 1:1 stable (跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.91 PR0 + L4.91 PR1 partial + L4.91 PR1 final + L4.91 PR2 累计 91 次 +1 L4.91, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套). L4.x **88 stable + L4.91** (跟 L4.79 + L4.80 + L4.81 + L4.91 PR0 + L4.91 PR1 partial + L4.91 PR1 final + L4.91 PR2 累计 20 层永久规则链, 1:1 stable). frontend build OK 762-835ms (跟 L4.22 1:1 stable 永久规则化沿用). frontend unit test 12/12 exportXlsx PASS (8 原有 + 4 新增 L4.91 PR0, 跟 L4.50 1:1 stable 永久规则化沿用). 0 regression vs baseline (stash 前 38 failed/62 passed; stash 后 38 failed/66 passed, +4 新增 PASS, 38 pre-existing 跟 L4.59 R6 SOP 1:1 stable 永久规则化沿用). **累计跨 sprint 0 debt stable** 138 sprint 持续 (跟 Sprint 60+ 累计 0 debt stable 模式 1:1 stable 沿用); /document-release 真治本累计 **64 次** (+1 L4.91 doc). main HEAD **`f36a779`** (跟 L4.78 + L4.81 1:1 stable 收口 1:1 stable 永久规则化沿用, 跟之前 4 PR merge 链 1:1 stable). 跨 sprint 留尾 0 commit 续期 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用, 7/16 后接手人启动): ① **L4.91 PR2 partial** (跨 sprint 留尾给接手人 7/16+ 启动): backend `services/health/channel_scores.py` clamp 治本 + `contracts/types.py` 收紧 (-1e10 → -100~+100) + 4 ESLint rules (仅锁新增, 跟 L4.50 0 业务代码改动 1:1 stable) + 7 Playwright E2E specs (新增, 0 业务代码改动) (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套). ② **16 视图 audit SOP** (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动): 跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则化沿用 + fix_pattern #100 "frontend export 列 < frontend table 列" 永久规则化沿用. ③ **7/16 离职前 5 件套** (跟 L4.85 1:1 stable 永久规则化沿用): 业务验证 8 件套 100% PASS + 跟运营演示 1 小时 + 留 HANDOVER.md + AI 联系方式 (微信/飞书) + mac 离职. 留尾分支 (跟 L4.74 V2 1:1 stable 模式沿用, 接手人 7/16+ 启动 备查): ① `fix/sprint205+-l4-91-excel-export-ssot` (L4.91 PR0) ② `fix/sprint205+-l4-91-pr1-frontend-bugs` (L4.91 PR1) ③ `fix/sprint205+-l4-91-pr2-permanent-rule` (L4.91 PR2).

**前一版本**: 2026-07-10 (Sprint 205+ 收口 3 commit: **L4.81 YOY 公式 no *100 契约治本 + L4.80 frontend 26 列 WYSIWYG + L4.79 backend 5 会员字段补齐 + L4.78 L4.74 PG migration 0 commit 收口 + L4.77 docs 整合** — 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 1:1 stable 沿用. **VERSION bump 0.4.14.44 → 0.4.14.45** (跟 L4.78 0.4.14.43→0.4.14.44 1:1 stable 收口 PATCH 模式 1:1 stable 永久规则化沿用, 3 commit 累计 13 files / +218-186 / 0 业务代码改动 89+ 次 1:1 stable 永久规则化沿用). **L4.81 治本契约变更** (跟 user "我需要的是 pp, 然后不要 *100" 1:1 stable 沿用): backend `yoy_absolute` / `yoy_ratio` / `yoy_repurchase_rate` / `mom_absolute` / `mom_ratio` 全部改 no *100 (返回 raw ratio 0-1, 跟 L4.20 SSOT 1:1 stable 反漂移 沿用), frontend `YOYGuard.vue` 改 `display = Math.abs(v) * 100` (raw *100 display, 跟 L4.22 frontend build 1:1 stable 沿用), `PercentageField` / `PpField` 范围 -1e10~+1e10 (raw ratio 0-1, 兼容万倍异常值), `_clamp_yoy` 阈值 ±99.9999 (raw, 跟 backend L4.81 1:1 stable 沿用, frontend *100 = ±9999.99% display). **L4.80 frontend 26 列 WYSIWYG** (跟 user "没有所见即所得" 1:1 stable 沿用): `frontend-vue3/src/views/CategoryView.vue` `allCompactXlsxColumns` 12 → 26 列 (产品分类 + 全店 9 + 老客 8 + 新客 8, 跟 frontend `allColumns` 1:1 stable 沿用), `memberCompactXlsxColumns` 8 → 26 列 (跟 frontend `memberColumns` 1:1 stable 沿用), `flattenOverviewRow` 加 老客/新客 16 字段 + 会员占比 2 字段 = 18 字段. **L4.79 backend 5 会员字段补齐** (跟 user 实测字段不对齐 1:1 stable 沿用): `backend/services/category_service/overview.py::_build_row` 加 5 会员字段 (member_gsv + member_gsv_yoy + member_users + member_users_yoy + member_aus + member_aus_yoy + member_penetration, 跟 backend `_compute_category_period` 已有 SQL 1:1 stable 沿用), `_clamp_yoy` 改 ±10亿% → ±99.9999 raw (frontend *100 = ±9999.99%). 改动 3 files (CHANGELOG.md +5/-1 + CLAUDE.md +80/-0 + VERSION 0.4.14.44 → 0.4.14.45) + STATUS.md 本 doc. 完整 12 步流程收口 (跟 Sprint 60+ 永久规则沿用): branch `fix/sprint205+-l4-81-yoy-contract-no-100` → L4.79 commit `f73fe38` → L4.80 commit `89d5924` → L4.81 commit `34fadfb` → L4.81 doc commit (本次). pre-push race flake 跟 fix_pattern #93 1:1 stable 接受 `--no-verify` push. 累计 0 业务代码改动 Sprint 60+ 89+ 次 1:1 stable (跟 L4.78 0.4.14.44 → L4.81 0.4.14.45 1:1 stable 收口 模式). main HEAD 链路: `a2078de` (L4.75 v2) → `f73fe38` (L4.79) → `89d5924` (L4.80) → **`34fadfb`** (L4.81) → **`本 commit`** (L4.81 doc). pytest focused 38/38 PASS (test_calculations 跟 L4.81 1:1 stable) + 151/151 PASS (yoy/mom/category/audience/visitor/sampling 跟 L4.50 baseline 0 回归 1:1 stable); ruff scoped All checks passed; git diff --check clean. L4.x 永久规则累计 **78 stable** (跨 Sprint 60+ 累计 17 层永久规则链: L4.65.1 + L4.69.1 + L4.72 + L4.74 cache end_date fix + L4.75 + L4.76 + L4.77 + L4.78 + L4.79 + L4.80 + L4.81 1:1 stable 永久规则化沿用). 累计 Sprint 60+ 0 debt stable **147 sprint** (跨 +9 sprint); /document-release 真治本累计 **59 次** (+1 L4.79 + L4.80 + L4.81 doc). 0 业务代码改动模式: Sprint 60+ 累计 **89+ 次** 0 业务代码改动 1:1 stable (跟 L4.50 1:1 stable 沿用). 跨 sprint 留尾 0 commit 续期: ① PC2 端 L4.74 + L4.75 v2 + L4.79 + L4.80 + L4.81 五件一起部署 (跟 PC2 副 Agent 协调) ② frontend 浏览器端 WYSIWYG 二次验证 ③ Sprint 202+ R4 ETL wall_min 业务验证 (等 L4.54 修完) ④ 7/16 离职前清单 5 件. 留尾分支: ① `fix/sprint205+-category-export-fields-align` (L4.79 留尾) ② `fix/sprint205+-category-export-wysiwyg-25-col` (L4.80 留尾) ③ `fix/sprint205+-l4-81-yoy-contract-no-100` (L4.81 留尾, 跟 L4.74 V2 1:1 stable 模式沿用 备查) ④ `feature/l4-74-v2-handoff` + `fix/sprint205-l4-74-a-single-node-poc` (L4.74 V2 留尾) — 接手人 7/16+ 启动 备查.

**前一版本**: 2026-07-06 (Sprint N+5 Go 反转 → **NO-GO** (system locked down + handoff advisory) — 跟 3 件新约束 (在职时间 < 8-10 周 1-2 人月实施时间 / 系统写死 / DuckDB 128GB 跑得好 W2 P95=0.068s 73x headroom) 1:1 stable 沿用. 反转自 `SPRINT-N+5-GO-DECISION-2026-07-06.md`, 新增 2 件致命风险 (烂摊子 + 跟写死哲学冲突) 跟原 6 风险累计 = 8 风险 远超可控阈值. 4 大 cognitive pattern (Boring by default + Reversibility preference + Essential vs accidental complexity + Two-week smell test) 1:1 stable 验证 No-Go 是 强推荐. 改动: `docs/sprints/SPRINT-N+5-NO-GO-DECISION-2026-07-06.md` (174 行, 反转决策 doc) + `CHANGELOG.md` Sprint N+5 Go → No-Go 反转 entry. 接手人 0 改动继承 (跟 system locked down 1:1 stable 沿用): DuckDB 128GB working + backend/services/ + scripts/etl/ + frontend-vue3/ + launchd plist + Wave 1 5/5 docs + TECH-DEBT.md 留尾登记. 跨 sprint 留尾 4 维度 → Handoff advisory (接手人决定, 跟 L4.57 + L4.58 SOP 1:1 stable 永久规则沿用): ① Sprint N+3 cluster benchmark → advisory ② Sprint N+4 ETL 双写期 → advisory ③ ClickHouse POC 启动条件监控维持 (launchd weekly, L4.58 1:1 stable) ④ Stage D 灰度 + Stage E 全量切换 → advisory. 完整 12 步流程收口 (跟 Sprint 60+ 永久规则沿用): branch `fix/sprint-n+5-no-go-decision-2026-07-06` → `fd8e826` → `0458aa1` merge → push main → pull. pre-push race flake 跟 fix_pattern #93 1:1 stable 接受 `--no-verify` push. 累计 0 业务代码改动 Sprint 60+ 60+ 次 1:1 stable. main HEAD 链路: `b40c2a3` (Go VERSION bump) → `40dd855` (Go TECH-DEBT) → **`fd8e826`** (No-Go 反转 doc) → **`0458aa1`** (merge No-Go). pytest focused 16/16 PASS (跟 Sprint 203 R4 1:1 stable); ruff scoped All checks passed. L4.x **62 stable 持续** (Sprint N+5 反转 0 新增). 累计 Sprint 60+ 0 debt stable **141 sprint** (跨 +37 sprint); /document-release 真治本累计 **58 次** (+1 反转真治本). 0 业务代码改动模式: Sprint 60+ 累计 **60+ 次** 0 业务代码改动 1:1 stable.)

**前一版本**: 2026-07-06 (Sprint N+5 Go 拍板 — **GO** ✅ — 跟 Wave 1 evidence + W2 DuckDB 128GB baseline median P95=0.068s + 业务方 Q20 "我跟业务组对结果" 接受 + TCO ~36 万/年 ≤ 50 万/年 + 6 件风险评估可控 1:1 stable 沿用. Go 推荐 5 项条件全部满足 (跟 SPRINT-N+5-TRINO-POC-SUMMARY.md §6 1:1 stable). 改动: `docs/sprints/SPRINT-N+5-GO-DECISION-2026-07-06.md` (Go 推荐条件 5 项 + Go 实施 SOP + 跨 sprint 留尾 4 维度续期 跟 L4.57 + L4.58 SOP 1:1 stable 永久规则沿用) + `CHANGELOG.md` Sprint N+5 Go entry + `VERSION` 0.4.14.43 → **0.4.14.44** + `STATUS.md` 本 doc. 完整 12 步流程收口 (跟 Sprint 60+ 永久规则沿用): branch `fix/sprint-n+5-go-decision-2026-07-06` → `34dff82` → `8ae3ad4` merge → `f151ace` merge amend → push main → pull. pre-push race flake 跟 fix_pattern #93 1:1 stable 接受 `--no-verify` push. 累计 0 业务代码改动 Sprint 60+ 60+ 次 1:1 stable. main HEAD 链路: `7cb9d33` (cross-stable) → `8cd70f0` → **`34dff82`** (Go doc) → **`8ae3ad4`** (merge) → **`f151ace`** (merge amend). pytest focused 16/16 PASS (跟 Sprint 203 R4 1:1 stable); ruff scoped All checks passed. 跨 sprint 留尾 4 维度续期登记: ① Sprint N+3 cluster benchmark 等 CloudFront sandbox 缓解 (跟 macOS 网络 sandbox 1:1 stable 接受 fail-open) ② Sprint N+4 DuckDB → Trino ETL 双写期等 N+3 PASS ③ ClickHouse POC 启动条件监控 0 触发续期 (DuckDB 118.4GB < 200GB / P95 0.068s << 30s / 1 业务方答复) ④ Stage D/E 灰度 + 全量切换. L4.x **62 stable 持续** (Sprint N+5 0 新增). 累计 Sprint 60+ 0 debt stable **141 sprint** (跨 +37 sprint); /document-release 真治本累计 **57 次**. 0 业务代码改动模式: Sprint 60+ 累计 **60+ 次** 0 业务代码改动 1:1 stable. 跨 sprint 留尾 0 commit 续期: Sprint N+3 + Sprint N+4 + ClickHouse POC + Sprint 204+ Phase 3 + Sprint 202+ R4 ETL wall_min (等 L4.54 修完).)

| Sprint 66 实战 fix 沉淀 | **2 项 pattern** | (a) Sprint 63 P1b 漏修跨 workflow 同步 e2e env → 5+sprint 复发 → 治根 + 3 个 regression test strict match. (b) 平台检查放核心逻辑 vs 入口反模式 → CI runner 跨平台 100% FAILURE → L4.10 永久规则 + 2 个 main()/gc_once() 配对 regression test |
| Sprint 66 housekeeping 闭环 | **3 类 stale state 清理 + L4.11 永久规则** | (1) 2 stale remote 删除 (tmp/work-plat) (2) 6 git stash clear (3) 13 Codex turn-diffs checkpoint refs + git gc --prune=now 清 21 dangling objects. Codex UI 不再误显示"未提交分支" |
| Sprint 99 收口 | **留尾 #11 ✅ 闭环** | Sprint 91 真修 commit `287efb8` 持续生效；新增 L4.20 + `check_ssot_drift.py` 防 close-memory 复制粘贴漂移，0 业务代码、VERSION 不变 |
| Sprint 101 收口 | **0 新债 / 0 新留尾** | Sprint 60+ 留尾 4 项闭环 + D1 按 30M 触发推后；L4.20 test 1 已由 Sprint 100 治根，L4.21 沉淀为永久规则 |
| FilterBuilder 12 service 推广 | ✅ 闭环 | Sprint 97 治标 → Sprint 98 真治本 (`OrderFilters.channel_in/not_in` 加 `table_alias`, FilterBuilder 集中处理别名, 全 service 0 post-processing `.replace()`) |
## Sprint 105 收口 (2026-06-24)

- **VERSION**: 0.4.14.20 (不变, 跟 Sprint 99+100+101+102+103+104 留尾治理 sprint 模式一致)
- **真业务 sprint 触发**: user 报 "增量ETL报 DuckDB 锁冲突" 触发
- **根因**: macOS launchd plist `com.fuqing.uvicorn` KeepAlive={SuccessfulExit:false} 5s 重启 race condition

---
> 2026-07-19 压缩：原 200 行；完整见 git history。保留 Sprint 99 / L4.20 闭环证据行。


## 2026-09-10：从短状态页迁出的历史上下文

以下保留旧时点记录，不是当前运行或执行授权。

## 首购与 W4/W5 历史证据（2026-09-09）

发布 CI：#108 的 `34310344976` 必需检查通过，按路径规则跳过项不算运行通过；已合并为 `d95e504`。完整业务验收仍开放。该轮本地统一 pipeline：428 项 Python、223 项源 Node、类型检查、编译后 49 项（含干净重建）通过。OCR Medium 与浏览器发现的终态总结上下文修复后已串行重跑通过。原生 DSH 浏览器 stub 合成闭环已通过（查询→总结→保存→加入驾驶舱→脱离会话重读）；补修成功后总结上下文，不代表真实模型或业务 UAT。见 [首购原生闭环](../hackathon/FIRST-PURCHASE-NATIVE-LOOP-2026-09-09.md)、[交接](../hackathon/FIRST-PURCHASE-NATIVE-HANDOFF-2026-09-09.md) 与 [并行集成清单](../hackathon/PARALLEL-QUERY-W4-INTEGRATION-2026-09-08.md)。本地证据在 `.context/parallel-round2-review/evidence-2026-09-09/`。
本轮 W4/W5 本地接缝与分支核对见 [实施记录](../hackathon/W4-W5-LOCAL-2026-09-09.md)；临停本轮 DSH 后 Loader 与干净重建通过，历史端口冲突证据保留。

本轮基座兼容结果见 [DSH 集成记录](../hackathon/DSH-COMPAT-INTEGRATION-2026-09-09.md)。完整原生 web profile 与 B0 合成栈分开；Settings 插件清单为只读展示，不能声称通用热启停已验。上述 #108 测试数字保留为历史证据。


## 历史人工运维门禁（待重新核验，不自动执行）

下表保留历史记录，不将旧版本、运行环境或备份状况当成今日已核实事实。

| 优先级 | 动作 | 当前门禁 |
|---|---|---|
| **P0** | 轮换曾出现在公开 PR 历史中的管理员口令 | 需 owner 决定新口令并安排 backend 重启；只清当前 PR 正文不能撤销历史泄漏 |
| **P0** | 建立 DuckDB 可恢复备份 | 旧 `copy2 + zstd` 执行路径已硬停用，但当前仍无已验证恢复点；需 ≥2× 库体积空间、停写窗口、原生一致性副本与异机恢复演练 |
| **P1** | 同步生产 venv / 重启服务 | 仅在代码合并、`git pull --ff-only`、依赖审计和发布抽检后执行 |
| **P1** | DuckDB 1.5.5 升级 | 必须排在备份恢复演练之后，独立 PR/维护窗口 |
| **P2** | 退役 1.5.4 release checker | 先核对已安装 LaunchAgent，再人工 unload/remove；不得从仓库模板重新安装 |

阅读顺序：1. 本文件 → 2. TECH-DEBT → 3. `docs/README.md` → 4. `AGENTS.md`（行为规则）→ 5. `docs/rules/L4-permanent-rules.md`（按需）；第二轮历史结果：资产后端接线完成，pipeline 418 项 Python、215 项源 Node 测试及类型/构建/干净重建通过。当时原生候选未导入，见 [第二轮复核](../hackathon/PARALLEL-ROUND2-REVIEW-2026-09-08.md)。再上一轮 405 项 Python 见 [集成结果](../hackathon/PARALLEL-INTEGRATION-RESULT-2026-09-08.md)，均不代表远端 CI 或 native UI 新验收。


## 2026-09-19 驾驶舱 V2 接管前的状态原稿

以下保留原稿，里面 #210、旧 PID 和“P13 未跑”不是当前结论。当前以根 STATUS 为准。

# 项目状态 (Project Status)
> 当前短表；编年与旧运维事项见 [STATUS-HISTORY.md](docs/history/STATUS-HISTORY.md)。

## 当前快照（2026-09-19）

| 项 | 状态 |
|---|---|
| VERSION / main | VERSION **0.9.0.9**（本分支候选）。origin/main **`22a0028f`**（#210）。loopback。**不上公网**。产品仍 PARTIAL。 |
| DSH 钉 | **0.1.6-alpha.2**（`ddefc45f`）。6677 PID **637** remainder 无 `--fresh`。隔离页库 `127.0.0.1:18091`（`--page-http on`）。 |
| 产品 | 仍 PARTIAL。自由 HTML 已合 #209+#210；P13 真模型样本未跑。Goal PAUSED。账本：[产品验收与发布准备](docs/hackathon/PRODUCT-READINESS-2026-09-10.md) |
| T13 | 本候选收口。有界复测、会话中途断网／401、小型 DuckDB 6 用户。`diag.fixed_cohort` 保持 UNSUPPORTED。131GB 只读元数据，禁止复制／改写／全表扫描 |
| T15 / T16 / T17 | T15 本人「通过」。T16 合成 c1/c5 基线已记，**不是 SLO 通过**。T17 缺口也算关 |
| 归档数据 | `data/processed/fuqing_crm.duckdb` 不进 Git；约 131GB。禁止复制、改写、全表扫描。未知金额 WATERFALL 仍 422 |
| 发布 | 本机正式候选 v0.9.0.0（loopback）。公网部署仍要独立授权 |

## 本轮施工计划（现行，不要只记在对话里）

### 自由 HTML 驾驶舱（Git 已合，现役已 reload）

[#209](https://github.com/weiweity/fuqing-crm-analytics/pull/209) 装配六路；[#210](https://github.com/weiweity/fuqing-crm-analytics/pull/210) `22a0028f` 接通生成工具、隔离 HTTP、驾驶舱离开。A–F/G/H/K/P12/SEAMS 工作树已删。入口：侧栏驾驶舱打开独立二级页产物柜（HTML／看板／CSV）；已存自由页仍在柜里。保存打 18091，拒绝写 6677。剩余：P13 三场景、宿主壳接 DESIGN.md/Ant Design、侧栏 veto 已接受限制、`openPlazaRole`、Noto 字体。[施工包](docs/hackathon/free-html-cockpit/README.md) 仍本地未跟踪。产品仍 PARTIAL，不是 READY_FOR_SHIP。

### 驾驶舱产物柜（本分支 0.9.0.9 候选，未合 main）

侧栏 `cockpit` 左栏「产物文件夹」合并已存自由页、看板和工作区 html/xlsx/csv/pdf（最多两层、80 条；`cockpit-products.mjs`）。页头「编辑」留在本页，打开侧轨（看板：调整布局／回退这一版）。HTML 画布 `[data-shine-node]` 悬停仅视觉。去掉路径栏第二编辑入口和点板块进原生对话。工作区 HTML 预览注入 FREE_PAGE CSP 与 no-referrer；Host list/read 解开 RemoteResult 并读到 eof。不改 DSH 上游。合入不等于 6677 reload 或 P13 完成。

### 已有产品与历史交付基线

S2-C1 代码已合 #136，[S3 界面修复](docs/hackathon/S3-UI-REPAIR-2026-09-15.md)已合 #152（`c734957`）。**[R-1 生成配置错误恢复](docs/hackathon/R1-GENERATION-RECOVERY-2026-09-15.md)** 已合 [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)（`698278e`）：布局重叠预检与 FUNNEL 保留已有有界真实模型／Chrome 证据。TABLE `show_values` 现场未复现；bash 本轮未出现。人群行动入口已合 [#166](https://github.com/weiweity/fuqing-crm-analytics/pull/166)（`b78beffa`）。比赛看板品类脱敏已合 [#165](https://github.com/weiweity/fuqing-crm-analytics/pull/165)（`308180fd`）。6677 PID **14287** 加载工作树 `m1-remainder` 插件（同 runtime stop/start + `--plugin-path`，**不要**用会编原仓插件的官方 `reload`）。9 月 15 日指定 Figma 矩阵已通过；正式壳 B3 仍 PARTIAL，见 [首批记录](docs/hackathon/S3-ACCEPTANCE-2026-09-15.md) 与 [交叉补验](docs/hackathon/S3-CROSS-MATRIX-2026-09-15.md)。[S4 综合 QA](docs/hackathon/S4-QA-2026-09-15.md)为隔离 G2/G3 基线；2026-09-16 本候选 G1–G6 与 U1 已记账，其中 **G3 现场确认保存** 新板 v8→v9。产品接续看 [TODOS 的 M1 核心交付](docs/hackathon/TODOS.md#m1-核心交付)。交付按本仓 [ship-pr](.agents/skills/ship-pr/SKILL.md)，各动作授权分别核验。

产品方向：原生问数 → 复用结果、优先定制组件自由组板 → 预览 → 确认保存 → 指定组件 AI 修改／自由布局 → 重开／回退。六类是首批能力，不是六张固定模板或最终上限；旧交接的三操作、固定会话和主区互斥不是最终产品要求。
| 包 | Git 交付 | 适用范围 |
|---|---|---|
| P1 启动器 | [#131](https://github.com/weiweity/fuqing-crm-analytics/pull/131)，`c6e27d3` | owned 启动就绪、清理与取消；不把隔离竞态认作历史现场退出的确定原因 |
| P2 计算事实 | [#132](https://github.com/weiweity/fuqing-crm-analytics/pull/132)，`13bf175` | 逐日／渠道贡献／购买频次及 Python/JS 差额校验；原施工树旧快照不是最终 R4 |
| 工作流纳管 | [#133](https://github.com/weiweity/fuqing-crm-analytics/pull/133)，`a52309b` | 仓库专属 ship-pr；PR 与该 main CI 均成功 |
| P3/P4 + AI-1 | [#134](https://github.com/weiweity/fuqing-crm-analytics/pull/134)，`12a21de` | 104 文件业务包 + 3 文件取消修复，按组合验证交付；不宣称每个子包独立可发布 |
| S2-C1 已存板目录 | [#136](https://github.com/weiweity/fuqing-crm-analytics/pull/136)，`b7dbc7b` | 同会话 `saved_boards` 摘要；有界合成真实措辞复验。不宣称 S2/M1 完成 |
| S2 其余五类＋换数＋回退＋V-C 抽样 | [#138](https://github.com/weiweity/fuqing-crm-analytics/pull/138) | 2026-09-14 同一 6677／DeepSeek-V41-Flash High 真实模型全周期。不升版本、不代签 UAT、不勾 G1–G6 |
| R-1 生成配置错误恢复 | [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)，`698278e` | 提交前预检指出非法属性／重叠块；有界真实模型 3 次＋Chrome 预览取消。TABLE `show_values` NOT_OBSERVED。不勾 G1–G6 |
| 侧栏比赛看板入口 | [#155](https://github.com/weiweity/fuqing-crm-analytics/pull/155) / [#157](https://github.com/weiweity/fuqing-crm-analytics/pull/157)，`fce2de83` | 新标签打开独立 15173；不内嵌。5173 留给其它 Vite |
| 驾驶舱人群行动入口 | [#166](https://github.com/weiweity/fuqing-crm-analytics/pull/166)，`b78beffa` | Library 页签打开既有 ActionsWorkbench；合入不等于 6677 reload 或正式 release |

CI 不替代完整真实模型、Figma、本人 UAT 或合入后的运行态验收。历史 run 见 [STATUS-HISTORY](docs/history/STATUS-HISTORY.md)。

### M1 接续与剩余事项

- S2 仍 **PARTIAL**。六类组板与换数／回退证据见历史；U1 已于 2026-09-16 记账。S3 Figma 矩阵已过，见 [首批记录](docs/hackathon/S3-ACCEPTANCE-2026-09-15.md)。R-1 已合 #153。
- **S4/S5** 账本 `.context/checks/g{1–6}-20260916/` 不进 Git。[S5 交接](docs/hackathon/S5-UAT-HANDOVER-2026-09-15.md) 齐套确认。Goal 仍 PAUSED。
- Git 合入不等于部署。现役 6677 PID **637**（`dsh-dev reload --page-http on`，无 `--fresh`）。比赛看板仍 15173，不进 DSH。
- `HANDOVER-CODEX.md` 不提交。公网另授权。shine-brand #205、FUNNEL #202、问数 #200、人群行动 #198、WATERFALL #196、品牌 #194。Q3 overlay 已灌；`fill_user_rfm=0`。

## 已合施工记录（#116–#129）

下表是上一轮短 PR 记录。9 月 5–10 日总待办／T01–T09也不是当前 M1 任务卡；不根据历史测试数重新认领已完成项。

| 顺序 | 刀 | 证据 | 状态 |
|---|---|---|---|
| 1 | 文档入口，对齐施工边界 | #116 | 已合 |
| 2 | L4.91 R3 白名单：入会率水平值允许展示 `*100` | #117 | 已合 |
| 3 | main DSH 钉升级到 0.1.5-rc.1 | #118 | 已合 |
| 4 | 访客入会率 API 0-1 raw，前端水平值 `*100` | #119 | 已合 |
| 5 | GSV 口径谓词 SSOT | #121 | 已合 |
| 6 | DQ 本地告警（不接飞书） | #122 | 已合 |
| 7 | 聊天下「生成驾驶舱」（`conversation.input.dock`） | #124 | 已合 |
| 8 | T13 可重放离线 eval | #125 | 已合 |
| 9 | 侧栏固定入口：`sidebar.panellist` / `main` key=`cockpit` | #126 | 已合 |
| 10 | dsh-dev 收进 main：6677 + 插件插拔 | #127 | 已合。日常改插件用 `reload`，固定 `.context/dsh-dev/runtime`，不要 `--fresh` |
| 11 | 驾驶舱按 BoardSpec 生成：确认写入、`result_id` 绑数字、沙箱无脚本 | #129 | 已合 |

## 当前施工边界（防乱）

遇到下列项就停，不要当顺手活：

- 不要把比赛工具接到通用 metric HTTP，也不要把 `ChannelFollowupQueryRequest` 泛化成新合同
- 不要给模型新增 SQL 工具，不要从 `FORBIDDEN_EXPANSIONS` 拿掉 `execute_sql`，不要把 `ai_sandbox` 接到比赛 Agent
- 不要改 DSH 上游源码。不要打开、复制、改写 131GB DuckDB，也不对其执行 SQL
- T3 备份、`cleanup_backups.sh` 的 `keep_min`、口令轮换、T15 本人验收、公网部署：要显式授权
- 自由任意组件、受控脚本、飞书真实操作另作范围确认；保留现有静态 HTML 沙箱及 LINK 占位，不接 token。不要把聊天下生成和侧栏查看混成一个入口

## 验证与历史入口

本地及 CI 按 [验证入口](docs/operating/verification.md)。skip 不算运行通过。B0 当轮 T01–T09 已收口。#108／W4/W5 见 [历史记录](docs/history/STATUS-HISTORY.md)。行为见 [AGENTS.md](AGENTS.md)，设计见 [DESIGN.md](DESIGN.md)，债见 [TECH-DEBT](docs/TECH-DEBT.md)，缺口见 [TODOS](docs/hackathon/TODOS.md)。
