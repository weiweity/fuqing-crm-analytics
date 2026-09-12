# DSH Analytics Workbench · B0 only

固定上游：`deepseek-ai/deepseek-harness@183f08e9c6dde7e36cd2318eaee70b0da08fb35e`（sdk `0.1.5-rc.1`，见 `toolchain.json`）。私有本地验证包，不发布 npm，不包含模型密钥或真实数据。2026-09-06 已接独立 FastAPI B0 任务内核、固定方法包与当前权限接缝；完整 B0 仍为 PARTIAL，见[当前收口报告](../../docs/hackathon/B0-LOCAL-CLOSEOUT-2026-09-06.md)。

## 实际能力与边界

- 根 Host 入口 `lib/index.js` 同时提供 UI discover 与私有原生协议桥，不登记工具、不保存业务账本或循环调用模型。桥只接受本次运行能力，返回原请求关联的原生日志及 `whenIdle + flush` 退出证据。
- 独立 `lib/tool.js` 默认登记 `analytics_b0_query`，参数只有 `{"query":"channel_repeat_rate"}`。从可信原生 call/turn 查找原 requestId，在 FastAPI 预留步骤后取得固定 `STUB / SYNTHETIC_FIXTURE`：100 位合成客户、25 位复购、25%，日期 2026-09-01。调用私有 loopback 接口；无 SQL、真实文件查询、任意网络或本地备用结果路径。`B0_RUNTIME_FAMILY=channel_followup` 时改为登记 `analytics_channel_followup_query`（完整 G2 请求，固定 `/internal/native/channel-followup`，输出 typed receipt）。B0 fixture 工具卡仍保留；渠道后续购买查询卡见 G4b，资产保存见 `--native-query-assets`。
- 独立 `lib/skills.js` 默认注册固定 `growth-analysis-b0` 及精确资源工具；整包包含 `SKILL.md`、证据引用与无数字示例，`skill-package.lock.json` 冻结全部字节。query-mode 另有不可变 `channel-followup-query` 包与 `query-skill-package.lock.json`。构建拒绝越界、软/硬链接、额外文件/脚本、超限和引用漂移；运行时读取不可变快照。每步与方法读取都回查后端权限、版本和预算，不新增通用文件工具或 Agent loop。
- 客户端登记品牌 `sidebar.brand.mark/name` 及原四项 `sidebar.footer.action`、`shell.overlay`、`tool.call.toolview`、`conversation.input.dock`；品牌单槽使用 `priority:-10` 先于上游默认贡献，不修改上游代码。等待 owner 声明后登记；两个 root 插槽共享 `defineStore`。任务状态栏只读 FastAPI 投影，展示最近三个 run 的状态、阶段和步数；断线明确标记旧快照，刷新不重新提交。
- UI-B01 最小适配：客户端只在 `ctx.sessions.list.phase === 'ready'` 且指定 `session-b0-synthetic-primary` 同时存在于 Host `ids/byId` 时，通过公开 `ctx.sessions.open(id)` 自动选中一次。不会调用 `create`、操作 DOM、选任意其他会话，或在用户后续切换时抢回焦点；目标缺失继续等待，选择失败只报告一次并无 fallback。每次插件重新加载/页面刷新会重新校验，这是 B0 固定主会话接缝，不是业务 run 自动受理实现。
- 默认“我的驾驶舱 · B0”打开源码内置 finite mock：一个板块的手工标题预览、应用、撤销未应用草稿与页面刷新恢复；不依赖活动会话/模型。不是 AI 局部编辑，也不是完整可组装驾驶舱。
- 仅当 `serve.mjs --native-query-assets` 且 GET `/b0/assets` 返回 `http_api=CONNECTED` 时，同一入口改走 HTTP overlay：列出已保存 SNAPSHOT，对唯一私人驾驶舱 add/copy/remove/layout/preview/undo。浏览器不带 backend bearer；GET 列表不自动建板。无板时加入会先 `POST /b0/dashboards` 再建预览；预览/保存 409 后重读，不保留过期 pending。kernel 不可用时 `/b0/assets` 为 `UNAVAILABLE`，不报 CONNECTED，入口回退 mock。`test/asset-overlay.test.mjs` 用 mock transport 覆盖上述编译后 DOM，不是浏览器 E2E。
- mock 路径的 localStorage 仅存 `analytics-b0-ui/v1 + title` 两字段，不缓存授权、身份、结果或业务资产。HTTP overlay 的权威资产在独立 SQLite（`analyses/` 与 `cockpit/`）；分析库读取与驾驶舱写入是先后事务，不是跨库原子。
- 侧栏「驾驶舱」面板（`sidebar.panellist` id=`cockpit` + `main` key=`cockpit`）的默认初值就是一块合成样例看板：`src/board-spec/demo-board.mjs` 的 `board_demo_channel_gsv_2026_08`，3 个 METRIC 加 LINE/BAR/TABLE/EVIDENCE/LINK，数字全部来自冻结的固定 `source_result_id`。标题带「样例」、证据块标 `SYNTHETIC`，明示不是真实经营数据；它只是前端 store 初值，不写业务库、不执行查询，聊天下「生成驾驶舱」会把它换成对话产物。
- 驾驶舱可经公开 `sessions.clear()` 脱离当前会话，关闭时仅恢复仍存在的原选择，不创建/删除/取消会话；未应用草稿退出需确认，Tab 双向保持在弹层、关闭后归还固定入口焦点。原始品牌静态路径与完整条件往返标本由固定网关服务；后者不是实际同条件 BI，不加载旧 Vue/Pinia。
- 工具卡只读取 `block.meta` 的精确版本化结果；处理中/失败/未知格式分开，不从模型文本猜成功。默认不开放保存、导出或审批。`--native-query-assets` 下可将 SUCCEEDED 查询保存为 SNAPSHOT 并加入驾驶舱；仍无导出/审批。“停止查询”取消当前卡片所属会话，不取页面第一个 `data-session-id`。

## 固定构建与验证

从工作树根运行，使用 Node 24 与显式 Python 3.14+ 路径。版本闭包在 `toolchain.json`、`build-tools/pnpm-lock.yaml` 和 `scripts/dsh-b0/requirements.lock` 冻结。下面的 `--check` 不安装依赖，不启动 CRM 或模型，但真实 Loader 测试会短暂监听私有 4316 并自行关闭；端口冲突直接失败，不终止别人。

```bash
node scripts/dsh-b0/pipeline.mjs --check --python /ABSOLUTE/PYTHON3.14
```

首次准备须明确执行 `pipeline.mjs --prepare --python /ABSOLUTE/PYTHON3.14`：只在缺失时拉固定公共 DSH SHA；已有 checkout 必须干净且 SHA/锁文件匹配，不切换或 reset。冻结安装后只重建指定原生依赖和官方 profile；不运行 Git hook 安装器、不改全局配置、不更新上游源码。Python 依赖需预先装在专用环境中，本脚本不会全局安装。

本插件 SDK/React 通过可重建的相对依赖链接绑定固定上游；产物保留标准包导入，无本机绝对 file URL。Host、client 均执行完整 TypeScript 检查（`skipLibCheck: false`），再构建。流水线比较独立干净目录的四个 JS 产物逐字节一致，并分别通过真实 Cordis Loader + 合成服务及原生 Skill/compaction 组件测试。它不是可脱离固定 SDK 运行或已发布的 npm 包。

Browser 编译为 CJS 工厂：`window.__ModuleLoader__.load({id: packageName, factory: require => { ...; return module.exports }})`。仅外置固定上游 `PLATFORM_MODULES` 的八项：React/JSX/ReactDOM/client、Cordis、client-store、ui-slots、ui-primitives；owner 包仅作 `import type`，不被运行时 `require`。不需要 `dsh.client.external` 额外声明。上游 `makeRequire` 按 seed → 已物化模块 → 已注册工厂查找，末尾 `/client` 会映射 package id；不存在通用 Node require。

## Host 挂载与原生验证

构建后将 `lib/index.js` 的绝对 file URL 作为一个新增 Loader row 的 `name`，例如在隔离 profile overlay 中：

```yaml
- name: file:///ABSOLUTE_PLUGIN_DIRECTORY/lib/index.js
```

这里是 row 结构示意；由主任务按实际 profile patch 协议挂载，不直接粘成覆盖全量配置。DSH `client/modules/src/index.ts:786–846` 支持 path/file URL 的 Host row，并向上找到此包的 `package.json`；再按 `exports["./client"]` 找到 `lib/client.js`。避免向上游 clone 或其 node_modules 建链/安装本包。使用 scaffold 时 `extraOverlayPath` 指向该 overlay；若按 package-name 挂载，则需 `extraInstallAnchors` 纳入本包 manifest 的隔离解析闭包，不应全局安装。

隔离 preset 另挂 `lib/tool.js` 和 `lib/skills.js`，并使用固定上游原生 Skill registry/tool；不要同时在 root 和 agent 登记工具。`serve.mjs` 的真实 preset 仅允许 `analytics_b0_query`、`analytics_b0_skill_resource`、`skill`。原生 filesystem provider 的默认根/自定义根/监听关闭，bundled 根为空；固定包由注册接口贡献。metadata 经 `output.presentationMeta` 持久化到 DSH `tool/result`，canonical 返回值不会自动成为卡片数据。不要加入 shell/read/write 等广权工具；profile/网关隔离由主任务负责。

同一包在同一 root Loader 中只挂一次 `lib/index.js`；不要再挂第二个 `lib/bridge.js` 入口。可信监督器提供分离的网关/运行时能力，配置仅写本次私有目录/通过 stdin 交给 Python，不使用全局配置或把真实凭据放入命令行。浏览器只经 4318 网关访问；Node 网关没有第二份 SQLite 任务账本。真实装配、macOS Seatbelt 与起停沿用[集成报告](../../docs/hackathon/B0-DSH-KERNEL-INTEGRATION-2026-09-06.md)，最新七问见收口报告，不运行旧 CRM `start-stack`。

## 验证分层

最新统一流水线包含 164 项 Python、133 项 Node 源测试及 14 项编译/装配检查（5 项既有检查 + 9 项工具卡组件回归，原目录与干净目录各一轮）。[T08 工具卡 DOM 报告](../../docs/hackathon/B0-TOOL-CARD-DOM-2026-09-06.md)记录 8 种状态与两档离线浏览器展示，不是原生故障事件 E2E。原生组件使用真实 Cordis/Skill/compaction，但其后端 HTTP 是 fixture；浏览器七问、独立日志、取消后退出、API/Host 恢复、三档视口与深浅主题另有实测，不混计层级。首次 UI 历史保留在[原 B0 报告](../../docs/hackathon/B0-DSH-VALIDATION-2026-09-05.md)。

原生验证只使用官方本地 mock 加请求级工具 ID 命名空间适配（上游固定重复 `mock-call-1`）。该适配不改参数、事实或业务结果，取消会传到官方 mock 并核对 `client_closed`。查询已接真实只读小型合成 DuckDB worker；资源/提交故障有独立子集证据，不是付费/真实模型、真实业务库、完整 D3/容量矩阵或 B0 全通过证据。浏览器方法调用和压缩整链未验，不以组件通过代替。

可复用固定源码：`docs/cookbook/adding-a-tool.md`、`packages/core/tools/src/schema.ts`、`packages/client/ui-tool/src/client/tool/toolviews/bash-sample.tsx`、`packages/client/store/src/contract.ts`、`packages/client/web/src/platform.ts`、`packages/client/web/src/seed.ts`、`packages/client/modules/src/client/system.ts`。六个 slot 名、工具结果结构与输入区宽度/底色令牌均以固定 SHA 为准。
