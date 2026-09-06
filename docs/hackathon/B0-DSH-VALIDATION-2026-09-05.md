# B0：固定DSH本地承载验证

日期：2026-09-05。状态：**PARTIAL / INTEGRATION_GATE_OPEN**。两轮本地合成/stub验证已结束，临时服务已停止；B0整体未通过，不进入B1–B4产品实现。

历史报告：下文是当时快照，不覆盖后续任务内核、方法包和 UI 修复。当前逐门状态与最终证据见[2026-09-06 本地收口](./B0-LOCAL-CLOSEOUT-2026-09-06.md)；原有 FAIL/PARTIAL 和未运行项保留。

结论：**保留DSH原生Web＋一个业务插件，不需要据此更换底座或fork核心。** 已证明安装构建、公开插槽、指定会话自动进入、合成工具卡和有限隔离。主要未闭合项是业务run状态、取消及恢复，不是缺一个聊天界面。Node网关只作B0协议样板，不能升级为第二套业务后端。

## 授权与边界

用户在工程复审后确认“可以，继续推进”，明确授权本B0：安装固定DSH、编写最小验证插件并临时启动。仅合成数据与模拟模型；不调用付费模型、不读取真实DuckDB、不运行旧ETL、不公开端口、不部署、不发送消息、不commit/push/merge。正式B1–B4实现和收费模型/公网关仍独立。

- 软件工作树：`codex/shine-mage-figma-refinement`，初始HEAD `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642`，保留既有脏改动。
- 上游固定：DeepSeek Harness `d347e703908d0406b7a7ef80e3a0e594d86b2215`，依赖安装目录 `.context/dsh-b0/upstream`（忽略，不复制进软件源码或数据目录）。
- 验证盒最多6工作小时；下载、安装、原生接缝、安全负测、渲染分别留证据，未测不填PASS。
- 已有本地演示PID 36717/36727，分别监听127.0.0.1:8000/5173；进程归属已核验本工作树。此次不占用、不停止、不重配它们。
- B0运行时采用独立配置/状态/工作目录、清洁进程环境和宿主隔离；不导入个人DSH/模型配置或挂载其他项目。启动和停止只针对本次有PID/启动指纹的进程，验证结束恢复冷存。

## 验证顺序

1. 核验固定源码与依赖锁，使用上游构建/原生测试接缝，不修改核心壳。
2. 明确禁用工具和控制面清单；用零密钥模拟provider，先证明私有目录/网络边界。
3. 最小业务插件：固定工作区、原生输入与业务工具卡、固定资产入口/overlay及局部编辑预览。
4. 原生发送/停止/重试与小样run映射；HTTP/WS/Fetch正常和越权路径，Skill固定装配与恢复。
5. 390/768/1440视口、键盘、原Logo/favcion接缝；旧Vue筛选隔离只给独立样例，不开放旧CRM。
6. 留存逐项PASS/FAIL/NOT RUN证据，停止本次服务；若硬门需fork/换壳/扩大权限，停止并请用户判断。

## 实测结果与未通过项

以下PASS仅指对应小样，不表示V01–V30、正式FastAPI身份、真实模型或产品全链通过。[可随仓库留存的脱敏证据摘要](./assets/b0/evidence.json)不含凭据、请求头或原始模型请求。

| 项目 | 状态 | 实际证据 / 限制 |
|---|---|---|
| 固定DSH构建 | PASS | 官方仓库固定SHA，依赖锁不变，上游工作树无改动；完整build退出0，非核心fork |
| UI-B01 首次进入 | PASS（小样） | 新隔离runtime预建空白primary；插件等Host list ready后用公开`sessions.open()`选中，浏览器未点目录即能原生发送；刷新已有历史也恢复。固定ID仅用于B0，不是正式身份合同 |
| UI-B02 工具卡 | PARTIAL | 真正原生tool调用→版本化meta→自有key卡片成功，显示100/25/25%合成样例；加载中、工具失败、未知版本的完整DOM组合仍未测，模型500不等于工具卡失败 |
| UI-B03 业务操作映射 | **未通过** | 原生send经网关留下1行派发记录；相同序列化请求202同run、换内容409。但原生界面不显示业务run，终态/取消空窗/独立观察/恢复未实现，完成后第二个新请求仍被403拒绝 |
| UI-B04 固定驾驶舱 | PASS（承载小样） | 根级固定入口、overlay、无活动会话查看静态fixture、单板块标题预览/应用/撤销草稿/刷新恢复；Esc关闭并归还焦点。不是业务资产库、AI编辑、数据刷新或完整板块组合 |
| UI-B05 控制面 | PASS（有限负测） | HTTP/WS/Fetch实测修复后29/29；业务cookie直连DSH的根/API/WS仍401，跨会话/文件/配置写入被拒绝；仅单合成actor，不是生产安全认证 |
| UI-B06 同条件BI | NOT RUN | 未改旧Vue全局筛选；未实现隔离看板与条件往返，跳转仍未开放 |
| UI-B07 品牌/可用性 | PARTIAL | 工具成功卡和驾驶舱在390/768/1440实际截图查看，390无横向溢出；标题编辑/Tab/Esc有证据。仍为DSH原Logo/favicon；完整主题、对比度、触控与reduced-motion未验收 |
| Skill / compaction / MCP | NOT RUN | B0关闭默认Skill roots，只挂固定persona和一个工具；未验证获批Skill包装配及压缩恢复；未加MCP或其他Agent运行时 |

### 自动选择为什么不是补丁绕过

原生`ui-workspace`只复用空白session；历史非空就尝试create，与正确的拒绝策略相冲突。此次插件调用公开`ISessions.open(id)`，只选择Host返回列表中同时存在于ids/byId的指定primary，一次选择后不抢回用户导航；不存在时不猜其他ID、不创建、不伪造blank、不用DOM点击。服务端仍限制会话归属。

源码接缝（均为上述固定SHA）：`packages/api/session-controller/src/client/contract/sessions.ts:40–44`、`client/sessions/service.ts:270–272`；原生创建路径`packages/client/ui-workspace/src/client/navigation.ts:99–109`。业务插件目录冻结为`dsh-plugins/analytics-workbench/`，原Vue聊天前端未另建。

### 业务run为什么还不能报通过

第二轮浏览器请求：`531ad162-7801-4727-a64a-e3f5d7f7643b`；B0 journal：`b0-run-3ca3cb10380c2184a21c07a1`。

- 网关在转发前提交SQLite `DISPATCH_INTENT`、请求hash与原回执；同一原始序列化请求重放返回202同run，变更内容返回409。mock只有2次调用（工具选择＋最终回复），没有因重放新增派发。
- journal最终仍为`DSH_ACCEPTED`，不是`SUCCEEDED`；`inFlight`尚未根据终态回收，后续新请求403。这个结果是已知未完成项，不是期望的连续问数行为。
- run ID目前在响应头，原生客户端只消费JSON结果；完整产品还要让用户看到真实受理任务及阶段。
- 当前hash按JSON序列化计算，不是正式语义规范化；业务先返回202再异步派发、请求丢失恢复、超时UNKNOWN、run级停止与重启恢复仍待合同实现。
- 关联不能用“session最后一个turn结束”：原`requestId`在`user/message.data.source.rpcId`，须按同session有序seq关联打开的turn。首个user/message前取消/失败还有inbox空窗；session cancel保留inbox，不能当该业务请求已取消。
- 上游turn边界并不等待存储flush。第一轮同时核对WS及合成持久日志；仍不拿原生终态代替公司业务资产与审批事实。

固定源码依据：`api/session-controller/src/commands.ts:314–317,454–472`；`core/agent-loop/src/agent.ts:267–331`；`core/agent/src/inbox.ts:71–76,177–187`；`core/session/src/types.ts:269–274`。此结论经独立子任务只读复核，不声称跨模型共识。

## 版本、安装和代码面

- DSH `0.1.3-alpha.1`，SHA `d347e703908d0406b7a7ef80e3a0e594d86b2215`。
- Node `24.19.0`：`/Users/hutou/homebrew/opt/node@24/bin/node`；pnpm `11.7.0`位于隔离tooling目录。lockfile SHA256 `2c903ab870f821ee2db62fa9417d11b1c2b9c65fbeec30e851ddc53c4cc8c383`。
- 官方pnpm包校验SHA512后安装；`install --frozen-lockfile --ignore-scripts`，未运行全局Git hook安装。必要fs-ext/koffi/node-pty单独构建，使用现有Python3.14/libuv头文件；未改用户全局配置。
- TLS曾因Node证书链失败；使用系统已有`/etc/ssl/cert.pem`作为额外CA解决，未关闭TLS验证。
- `dsh-plugins/analytics-workbench/`：一个root UI入口、一个独立agent工具、三个原生slot及一次选会话适配。`lib/`为忽略的本机产物，不是可发布包；未进行全量TypeScript类型检查。
- `scripts/dsh-b0/`：固定CLI/模拟provider/OS隔离启动、有限RPC/WS代理策略、传输清洗与合成probe。只验证接缝；不复制到正式业务服务后就宣称生产可用。
- 上游源码、依赖、私有launch文件和原始合成运行日志均留`.context/dsh-b0/`且被Git忽略；只保留脱敏摘要与截图到文档。真实131GB归档库未读取、复制或改写。

## 验证分层与失败留存

| 验证 | 结果 | 不代表什么 |
|---|---|---|
| 插件纯函数/编译产物 | 15/15：8项fixture/标题＋5项选会话＋2项编译产物 | 不代替全部DOM状态、TypeScript全检查 |
| 网关策略＋传输helper | 60/60：51项策略＋9项传输边界 | 不代替所有真实传输或生产渗透测试 |
| macOS隔离探针 | 18/18；另4/4原生库/线程探针 | 只覆盖本机Seatbelt小样，不是可直接部署的Linux沙箱 |
| 实际DSH成功 | 唯一广告工具`analytics_b0_query`；结果meta及completed落入合成日志 | 不代表真实经营数值/SQL口径正确 |
| 实际DSH取消 | 先收到mock首chunk，后cancel，日志aborted/user；provider记录client_closed | 不代表business run级取消及inbox恢复 |
| 实际DSH模型错误 | mock HTTP500，日志error/SERVER；无成功工具/完成回复 | 不代表真实收费模型或工具失败卡全部验收 |
| 实际网关 | 首轮28通过/1失败；修复后二轮29/29 | 不隐藏首轮失败；未测试全量资源上限与多用户 |
| 浏览器 | 原生冷进入/发送/成功卡；标题编辑与恢复、三档尺寸、Esc焦点 | 不等于完整产品L3、AI局部编辑、视觉终审 |

首轮失败是二进制`session/uploadFileBinary`在准入前被JSON解析，返回502而非明确403；未上传成功。现改为先判JSON RPC/查询串/Content-Type，再解析正文，真实负测复测通过。另已修复精确plugin batch query清单和HTTP错误结果清洗；启动日志只在完整行识别URL，累计脱敏，不输出分块token。

一次网络调试输出曾带出短期B0入口参数；网关已重启换凭证，最终服务也已停止。未带出真实账号或DSH内部凭证；私有launch文件不进文档/仓库。欢迎提示采用已读后内部预置偏好，浏览器仍无任意设置写权限；中文locale请求未让原生UI全面中文化。原生设置/开发工具部分入口仍可见，后台拒绝带来403控制台噪声，**不能写console clean**。

## 证据位置与复查

- 第一轮：`.context/dsh-b0/runtime-xlXpXV/`，包含native-smoke、修复前/后gateway-smoke、mock-evidence、stopped。
- 第二轮：`.context/dsh-b0/runtime-281P9N/`，包含browser-dispatch、b0-dispatch.sqlite、gateway-evidence、mock-evidence、stopped。
- [冷入口](./assets/b0/cold-entry-1440.png) / [原生首次结果](./assets/b0/cold-entry-first-result-1440.png)。
- 工具卡：[390](./assets/b0/native-tool-card-390.png) / [768](./assets/b0/native-tool-card-768.png) / [1440](./assets/b0/native-tool-card-1440.png)。
- 驾驶舱：[390](./assets/b0/cockpit-390.png) / [768](./assets/b0/cockpit-768.png) / [1440](./assets/b0/cockpit-1440.png)。这些是实际截图，不是最终视觉稿。

以下仅静态/单测，不启动服务；需使用已构建的固定上游依赖：

```bash
/Users/hutou/homebrew/opt/node@24/bin/node --test scripts/dsh-b0/gateway-policy.test.mjs scripts/dsh-b0/transport-safety.test.mjs
/Users/hutou/homebrew/opt/node@24/bin/node --test dsh-plugins/analytics-workbench/test/*.test.mjs
```

`serve.mjs`每次新建独立runtime；模拟响应队列有顺序且会耗尽。`native-smoke.mjs`和`gateway-smoke.mjs`为第一轮指定runtime的一次性取证脚本，不能不改fixture安排就重复跑；报告防覆盖。`rpc.mjs page`明确拒绝仅凭sessionId调用，正确分页示例在native-smoke中。`collect-evidence.mjs`只整理这两轮既有脱敏证据，不启动或重新声称验收。

## 收尾与下一项

两轮DSH子进程均正常退出0；临时4317（DSH）/4318（B0网关）/4319（mock）已停止，B0浏览器标签已关闭。原5173/8000及PID 36727/36717保持原启动时间不变；不停止用户正在查看的旧演示。无commit/push/merge、公网、飞书或短信动作。

**下一项仍是B0业务任务适配小样，不跳到功能堆叠。** 保留FastAPI为唯一业务权威，先明确原生requestId、run、inbox/turn、结果证据和取消/恢复关系；在B0剩余窗口取得最小完整样例后，再判断B1合同实施的准入。没有充分证据要求用户换底座。若需要延长6小时验证盒、fork核心、换壳、放弃业务合同或把Node代理变成第二业务后端，才停下请用户决策。本报告的PARTIAL不是这一批准。
