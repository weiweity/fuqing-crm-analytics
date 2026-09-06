# B0 工具卡状态 DOM 增量验证

日期：2026-09-06；承接“当前进度执行”，完成 T08。**组件状态缺口已补证，UI-B02 / 整体 B0 仍 PARTIAL**：本轮不是原生会话故障全链路验收，也没有进入 B1–B4。

## 实际改动

- 新增[编译组件测试夹具](../../dsh-plugins/analytics-workbench/test/tool-card-harness.mjs)和[9 项回归](../../dsh-plugins/analytics-workbench/test/tool-card-dom.test.mjs)：加载当前 `lib/client.js`，使用固定上游 React/ReactDOM 渲染实际注册的工具卡，不另写一张模拟卡。
- 新增[离线浏览器检查](../../scripts/dsh-b0/tool-card-dom-smoke.mjs)：同一编译组件和其内嵌 CSS 生成本地无脚本页面；逐卡滚入视口，检查文字、可见性、状态角色、溢出及不存在业务操作。页面明确标为 `COMPONENT DOM / SYNTHETIC / NO RUNTIME`。
- [统一流水线](../../scripts/dsh-b0/pipeline.mjs)纳入新增脚本语法与 9 项编译组件回归，原目录和干净目录均执行。无业务代码、CSS、上游源码或数据库改动。

## 证据与结果

| 层级 | 本轮结果 |
|---|---|
| 组件回归 | 8 个状态 + 1 个独占工具 key 注册检查，9 PASS / 0 FAIL |
| 浏览器 DOM | 1440×1200、390×844 两档，各 8 状态全部可见且无横向溢出；页面仅 1 张成功卡、无业务操作控件；两张全页截图已人工视觉核对 |
| Python / 源 Node | 164 PASS（pytest 报告 1 warning） / 133 PASS |
| 编译/装配 | 原目录 14 PASS；干净目录 14 PASS；其中新增组件 9 项，不把它们全部称作原生装配测试 |
| 类型与构建 | Ruff、完整 Host/client 类型、真实 Cordis loader、干净构建逐字节一致均通过；未安装/升级依赖 |

8 状态是：加载、成功、工具失败、未知 schema 版本、缺少元数据、额外字段、篡改数值、失败标记伴随合法旧元数据。后 6 种均不显示 25% 成功事实；原始错误详情及 HTML 注入标本不进入输出。运行状态也不提前显示结果。

本地证据（相对 worktree）：

- `.context/dsh-b0/tool-card-dom-7jqgS4/report.json`，时间 `2026-09-06T10:15:53.152Z`；同目录 `index.html`、`1440x1200.png`、`390x844.png`。
- `.context/dsh-b0/build-evidence.json`，本轮时间 `2026-09-06T10:16:44.630Z`，干净构建 `clean-build-XiUowY`。该统一入口未来可能更新，以此时间与产物 hash 区分本轮。
- 浏览器所用 `client.js` SHA-256 为 `85adb016fa059cb8774c2a1febdb40de3fb4da7e46c9bdf958d6c21dfd0da208`，与本轮最终干净构建以及 T01–T07 收口产物一致。

## 不扩大证据层级

测试输入按固定上游 `RunningToolCall` / `ToolResultNode` 结构经 JSON 往返交给组件，验证不改写 owner 输入。注册接缝使用测试夹具：只证明插件仅声明 `analytics_b0_query`，没有注册其他 key 或通配卡；**不冒充真实 slot engine 的其他卡片动态共存实测**。React SSR 后的浏览器 DOM 不包括原生事件流、客户端 hydration、上下文切换或并发状态更新。

原生成功卡与七问链路沿用[T01–T07 报告](./B0-LOCAL-CLOSEOUT-2026-09-06.md)，本轮没有重跑七问。原生工具失败/未知版本等事件至卡片的完整旅程仍未执行，不能用模型 500 或当前离线页面替代。历史监督器退出根因仍 **OPEN / NOT REPRODUCED**，本轮没有新复现证据，不关闭稳定性关卡。

## 收尾与下一项

本轮未启动 DSH Web/API/mock；编译装配测试自己的临时 loader 随测试退出。结束核验 4315–4319 无监听；只关闭本轮测试标签页 2，既有标签页 1 保留。分支和 HEAD 不变，暂存区无变更；没有 commit、push、PR、部署、真实库读写、ETL、付费模型或对外消息。

下一项仍在 B0：设计有界的原生工具状态事件注入验证，并实测其他 key 卡片共存。它需要保持真实事件/owner 绑定与合成数据边界，不通过扩大通用工具权限、生产错误注入或替换原生 renderer 来变绿。历史稳定性仅在有新证据或明确复查方案时推进。
