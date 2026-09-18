# 主协调审查 · Lane F

- 状态：**PARTIAL**（T21–T28 模块证据齐；真实 DSH 浏览器宿主 / 触控窄屏 NOT_RUN）
- 工作树：`…/fuqing-crm-analytics-free-html-F`，HEAD `a3a9b428`，**已本地 commit，未 push**
- 报告：`reports/LANE-F.md`
- 越界：无。`library-workspace.tsx` / `cockpit-composition.tsx` / `html-sandbox` / `pipeline.mjs` 与主仓相同。DSH 上游无 dirty。改了 `library-board-client.mjs` / `.d.mts` / `index.tsx` 作为离开接缝，可接受。
- 6677 PID **8758** 未动

## 本轮复跑

Node **v24.19.0**。leave + navigation + `library-board-client` **86 pass**；`leave-prompt` **11 pass**。未重跑声称的 218 全量（环境依赖 antd DOM），以本轮 97 项 leave 相关 + 既有 P12 树回归为准。

OCR 14 条 + 自查 layout-only 谎报保存：代码里看得到 `observeExternal`、`idempotency_key` 强制匹配、`layout_unsaved`。

## 定夺（integration note 1）

**由 P12 改，不让 F 越界。** `library-workspace.tsx` 的 `beforeunload` 已在集成树改为 `library.hasUnsavedChanges()`。干净 `editContext` 不再武装浏览器离开提醒。回归测试 `beforeunload follows hasUnsavedChanges and ignores a clean editContext` 在 P12 树 **pass**。

Lane E 工作树未改该文件（其 `library-board-client` 还没有 `hasUnsavedChanges`）。note 2（`openCockpitPanel` 进入路径）保持现状。note 3（干净树需 bindToolchain）记入 P12。

## 接缝限制（不能当已通过）

原生侧栏行点击无法否决，只能 epoch 观测。脏稿时侧栏点击留页 **不成立**。真实 iframe/MessageChannel 全局面板/会话、375/768 触控 **NOT_RUN**。
