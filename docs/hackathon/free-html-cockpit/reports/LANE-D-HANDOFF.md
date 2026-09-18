# 给主协调 Agent 的交接提示词

把下面整段交给主协调 Agent。不要让它重做 Lane D 业务实现；不要让它改 D 的 owner paths（除非 P12 集成时按 A→B→C→D→E→F 移植）。

```text
Lane D（源码定位与编辑）已在独立 worktree 交付并可给 P12 收口。你是主协调，不要重新设计产品，不要改 DSH 上游，不要写 manifest 以外的 lane 业务文件（manifest 仅你可更新）。

工作树：/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-D
分支：codex/free-html/lane-d
HEAD 仍为基线 b45a27bb9022057ce37aa9123927e8b4663a2720（未 commit / 未 push）
approved-plan SHA256：47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb
报告：docs/hackathon/free-html-cockpit/reports/LANE-D.md
状态：DONE（确定性 fixture；真实 AI / 真浏览器 / A 持久化 / 完整 B0 pipeline 均为 NOT_RUN）

Owner 实现（仅这些路径）：
- dsh-plugins/analytics-workbench/src/free-page/source-index/
- dsh-plugins/analytics-workbench/src/free-page/patch/
- dsh-plugins/analytics-workbench/src/free-page/edit/
- 测试入口（现有 pipeline 已扫 tests/）：dsh-plugins/analytics-workbench/tests/free-page-edit.test.mjs
Lane E 公开 adapter：src/free-page/edit/adapter.mjs
存储 mock：createMemoryPageStore（A 的 page_documents 未在本树落地）

已核验命令（Node 24.19.0，34 pass，exit 0）：
/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/src/free-page/source-index/source-index.test.mjs dsh-plugins/analytics-workbench/src/free-page/patch/patch.test.mjs dsh-plugins/analytics-workbench/src/free-page/edit/edit.test.mjs dsh-plugins/analytics-workbench/src/free-page/edit/d48-scope.test.mjs
以及：
/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/tests/free-page-edit.test.mjs

OCR delegate 审核后已返修并回归：选区外无标记插入拒绝；区域 JS 改 document.body 须 SCOPE_REQUIRES_CONFIRMATION；连续本地编辑重绑 range；D9 丢回执复用原 save_* 幂等键；kind 不得静默改写；canvas 未变不按写死 r_chart；@media 视为共享 CSS。

请主协调做的事：
1. 核对 D 未越界（未改 library-board-client、html-sandbox、pipeline.mjs、manifest.json、DSH 上游、6677）。
2. P12 移植时按 A→B→C→D→E→F，把 createMemoryPageStore 换成 A 的 page_documents；保持 PATCH/SAVE、PENDING|APPLIED|CANCELLED、原幂等键、CAS、INVALID_PAGE（不要 INVALID_BOARD）。
3. 把 src/free-page 纳入 scripts/dsh-b0/pipeline.mjs 扫描；纳入后删掉或改掉 tests/free-page-edit.test.mjs 的再导出，避免 34 项跑两遍。
4. Lane E 只 import adapter.mjs。hasActiveEditContext ≠ dirty。N08 可见浏览/编辑 UI 仍是 E/P08。N10 接现有 DSH session，不要第二 Agent。
5. D48：MAPPING_STALE 禁止静默整页；整页仅 user_switched / switchWholePage()；共享 CSS/JS 用 SCOPE_REQUIRES_CONFIRMATION + 匹配 impact_hash。
6. P13 才跑三类真实 AI 样本。不要把 D 的 fixture 绿记成真实模型通过。
7. 未授权不要 commit / push / merge / 切现役服务。
```
