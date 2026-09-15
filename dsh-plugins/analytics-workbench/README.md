# DSH Analytics Workbench · B0 only

固定上游：`deepseek-ai/deepseek-harness@183f08e9c6dde7e36cd2318eaee70b0da08fb35e`（sdk `0.1.5-rc.1`，见 `toolchain.json`）。私有本地验证包，不发布 npm，不包含模型密钥或真实数据。2026-09-06 已接独立 FastAPI B0 任务内核、固定方法包与当前权限接缝；完整 B0 仍为 PARTIAL，见[当前收口报告](../../docs/hackathon/B0-LOCAL-CLOSEOUT-2026-09-06.md)。

## 本轮组件库合同与实现（2026-09-14）

目标与验收以 [TODOS 的 M1 核心交付](../../docs/hackathon/TODOS.md#m1-核心交付) 为准，代码落点与CI见 [STATUS](../../STATUS.md)及 [#134](https://github.com/weiweity/fuqing-crm-analytics/pull/134)。9 月 15 日 S3 原型与正式壳续验见 [S3-ACCEPTANCE](../../docs/hackathon/S3-ACCEPTANCE-2026-09-15.md)。下方分项测试数／“待验”是各阶段历史证据语境，当前停点以 STATUS/TODOS 为准；不代表无代码平台已经完成。

目录 SSOT：[`src/board-spec/component-catalog.json`](src/board-spec/component-catalog.json)，版本 `board-components/v1`。新组件块显式携带 `library_version`，由 `parseBoardSpec` 校验、`interpretBoard` 调用只读投影、`LibraryComponentBody` 渲染；运行时无 Figma 请求。原生 Connection 环境已接新版画布及目录/生成工具；无该服务的旧 fixture 仍走兼容渲染。S2-C1 已存板 catalog 已合 [#136](https://github.com/weiweity/fuqing-crm-analytics/pull/136)；2026-09-14 同一 6677 上其余五类编辑、LINE 换数与当前模型板回退已记账。开放项（正式壳 B3 九态仍 PARTIAL、R-1、UAT、G1–G6）看 STATUS/TODOS，不要求重新选模型。

### 六类首批合同

通用表现属性：`subtitle`（≤240 Unicode 码点）、`tone=neutral/accent/muted`、`density=comfortable/compact`。标题属于块的 `title`；布局为整数 `x/y/w/h`，12 列，逻辑行高 40px、间隔 16px，总高上限 2000 行。新画布已接连续拖动/缩放和键盘，前后端拒绝越界与重叠，邻居不自动推移。尺寸不是 Figma 固定像素的永久产品限制；可见边缘长画布滚动已有浏览器证据，触控/全部边界待 C5 继续验。

| 类型 / Figma 组件集 | AI 可改的表现属性（除通用项） | 数据要求 | 最小 / 默认尺寸（w×h） |
|---|---|---|---|
| METRIC / `145:30` | `show_comparison`；`value_format=standard/compact` | scalar：已供给值、可选对比值、明确单位或 null | 3×3 / 4×4 |
| LINE / `147:91` | `show_legend`、`show_points`；`line_style=solid/dashed` | 有序序列；缺失点断线，无序分类明确拒绝 | 4×5 / 6×7 |
| BAR / `149:90` | `orientation=horizontal/vertical`；`show_values` | 分类序列；正负值共用零轴，缺失不画零 | 4×4 / 6×6 |
| TABLE / `150:2091` | `columns`（≤12）；`page_size`（5–100）；`sort_field`、`sort_direction=asc/desc` | 仅能选/排绑定结果中的列；空值排序在末尾 | 4×4 / 6×7 |
| TEXT / `151:2016` | `content`（≤4000）；`align=start/center`；`text_style=body/callout` | 纯说明文本，无数据依赖；明确标非核验数字，不执行标记或脚本 | 3×3 / 6×5 |
| EVIDENCE / `153:2026` | `summary`（≤1000）；`expanded` | 来源标签及证据条目来自结果；可改摘要不冒充来源原文 | 3×3 / 6×5 |

组件集位于 [当前 Figma 文件](https://www.figma.com/design/PS8LQRBiuoY6uNxugWjbT3)。六张工程属性表已同步至原组件页（METRIC `227:2`、LINE `227:3`、BAR `228:2`、TABLE `228:3`、TEXT `228:4`、EVIDENCE `228:5`），明确当前字段与未来差距；它们是显式合同，不是 Code Connect，也不代表 Figma 已暴露每个属性开关。六类代表性修改均已接正式主流程：指标标题、趋势图例、对比数值标签、明细可见列、说明正文、证据说明；后续验收见 [TODOS](../../docs/hackathon/TODOS.md#m1-验收门槛)。实际点击/滚动、跨多项修改组合及完整视觉仍待验；原双序列设计示例不等于代码已支持多序列。

2026-09-13 原生属性补齐：下列四项已绑定各自五态组件，并通过真实 Figma 实例 `setProperties` 开关及截图验证。正式原型保持80帧/两个入口；LINE/BAR/TABLE各59实例几何和显示读回不变。EVIDENCE另外三个隐藏实例的查询返回有差异，祖先隐藏与整屏截图确认未泄露内容，未伪报逐字相同。

| Figma 原生属性 | 运行时对应 | 当前设计边界 |
|---|---|---|
| LINE `ShowLegend` | `props.show_legend` | 不改曲线；点标记、线型和公共样式仍待设计绑定 |
| BAR `ShowValues` | `props.show_values` | 隐藏标签后柱形随可用宽度同比例伸展；纵向变体仍待完善 |
| TABLE `ShowShareColumn` | 当前示例 `props.columns` 包含/排除占比列 | 仅是列选择的代表投影，不是任意数组编辑器；行值保留 |
| EVIDENCE `Expanded` | `props.expanded` | 隐藏范围/时间/限制详情，说明、结果引用和来源保留 |

验证实例分别为 `309:2`、`312:9498`、`314:9519`、`317:9541`，位于各自组件页右侧，非新的正式原型入口。公共 subtitle/tone/density、全部状态/属性组合和完整代码视觉对应仍开放；设计里的 PreviewValue/Source 等样例编辑属性不扩大模型写事实的权限。

任意 CSS/字体/颜色、事实值、查询条件、结果 ID 或脚本不能塞入 `props`；未知属性返回明确错误。视觉使用 `competition-shell/tokens.ts` 的 `--sm-*` 品牌令牌，不把 Figma 在线资源当运行时依赖；全部间距/尺寸令牌及视觉对应仍需收敛。

### 数据与修改边界

扩展目录 revision 2 阶段追加 `PROCESS` / `TIMELINE`（当前 revision 4 另含下文 WATERFALL/FUNNEL），保留 `board-components/v1` 和原六类顺序。二者复用同一生成、点选编辑、预览、确认、取消、保存及版本回退协议；不是另一个执行引擎。Figma 已有 [流程组件集](https://www.figma.com/design/PS8LQRBiuoY6uNxugWjbT3?node-id=271-2) / [时间线组件集](https://www.figma.com/design/PS8LQRBiuoY6uNxugWjbT3?node-id=276-2)，各含默认、选中、加载、空、错误五态与属性验证实例；目录 `design_status=PARTIAL`，不是完整设计验收。

Figma 的 TEXT 属性覆盖标题、副标题及代表节点/事件的标签、说明；流程参与者和两类详情有 BOOLEAN 开关。流程图与下方说明共用节点标签。Figma 为三节点/四事件代表样例，不会因直接改日期文字自动重算时间轴，也不自动重接连线；运行时由 `nodes/edges/events` 结构和几何函数计算。全部动态属性、尺寸/密集内容变体及整板 AI 编辑原型仍待对齐，不能把实例属性验证冒充 Code Connect 或真实模型执行。

| 扩展类型 | AI 可编辑结构 / 显示属性 | 数据与安全规则 | 最小 / 默认尺寸 |
|---|---|---|---|
| PROCESS | `nodes`（0–40，唯一 id、label、可选 owner/detail）；`edges`（0–100，from/to、可选 label）；`show_owners/show_details` | 规划说明，不绑定结果或执行 SOP；拒绝悬空、重复连线。支持显式分支、返回、自循环、独立节点；有向图由结构生成，编号对应完整说明，不是图片 | 4×5 / 6×8 |
| TIMELINE | `events`（0–40，唯一 id、有效 YYYY-MM-DD、label、可选 detail）；`timezone=Asia/Shanghai/UTC`；`show_details` | 规划日历日，不推测时刻或冒充已核验事件。真实日期比例、同日分组、近日期标记分层；原始事件完整保留 | 4×5 / 6×8 |

两类都支持通用品牌属性；节点/事件 id 为字母开头的 ASCII 字母数字/下划线/连字符，≤64；标题 ≤160，owner ≤80，detail ≤1000。数组属性整项替换，不暗中合并；删节点需同时更新相关连线，服务端会对合并后的完整结构再校验。空结构显示明确空态，日期/属性错误拒绝且不覆盖已保存板。`source_result_id` 必须缺省或 null，不能借用 GSV 为规划背书。

扩展验证：58 项后端（共享21个跨语言结构用例、独立进程重开、取消/保存/回退等）、48 项相关 Node/编译 DOM、完整 pipeline/干净重建和实际 ToolRuntime→原生认证→HTTP→SQLite 八类编辑链通过。日志为 `.context/checks/ai-cockpit-goal/structured-components-{focused,pipeline-final,http}.log`；详细范围及失败证据见 TODOS E1。真实浏览器仅验隔离画布显示/节点跳转/日期比例和 1440/390 视口，不代表真实模型或完整 DSH 交互通过。

隔离复现（Node24，绝对 Python3.14；PTY 运行，输入空行结束并回收自己的 HTTP/SQLite）：

```bash
FQ_B0_PYTHON=/Users/hutou/homebrew/opt/python@3.14/bin/python3.14 node dsh-plugins/analytics-workbench/test/library-layout-browser-probe.mjs --structured
```

该入口会创建临时合成板、提供本地 Outfit 字体，不使用已有模型配置、不改6677。仍待 Figma 完整属性/整板状态对齐、真实模型编辑、密集图/全部长内容与窄屏滚动验收；漏斗/瀑布后续增量如下。

### 贡献瀑布（WATERFALL v1，catalog revision 3）

[Figma 组件集 `289:402`](https://www.figma.com/design/PS8LQRBiuoY6uNxugWjbT3?node-id=289-402) 含默认、选中、键盘焦点、加载、空、错误六态及展示开关/390宽验证实例。复用现有品牌变量与文字样式，`design_status=PARTIAL`：完整 tone/density 变体、整板编辑前后原型和实际滚动仍待验；Figma 修改数据文字不会自动重算几何，不是 Code Connect。

| 合同项 | 当前能力与边界 |
|---|---|
| AI 展示修改 | 通用 `title/subtitle/tone/density`；`show_values` 和 `show_table` 均为 boolean，默认 true。前者隐藏数值标签，后者默认收起明细，明细仍可打开 |
| 数据 | `reconciled_waterfall`：`unit`、`start/end={label,value}`、`contributions=[{label,value}]`；最多200项，有限数值、标签唯一，累计与终点对账。事实不能经 `props` 写入 |
| 数据来源 | `competition-gsv-facts/v4` 的 `channel_bridge`，复用同次问数的有效订单净额，明确渠道、同单位与同期间范围；旧v1/v2/v3仍可读取，但不能由双期总量伪造贡献 |
| 不可用 | 期间未覆盖、金额单位未知、订单渠道混杂/非法或超过200项时，目录结果不提供 WATERFALL 能力；生成明确失败，已有板不被覆盖 |
| 渲染 | 原生 SVG 柱、累计连接、零轴、显式正负号及分页明细；保留零项，不按固定模板合并“其他”。通用几何支持负起点/跨零，当前GSV供给仍按实际业务口径 |
| 尺寸 | 最小4×5，默认6×8；完整步骤与明细局部横向滚动，不截断源结构 |

这是可加和的渠道净额差，不是营销因果归因。修改期间/筛选须由原问数能力取得新结果，表现修改不重新查数。读取已保存板不要求模型在线。

隔离瀑布复现使用同一浏览器探针，将上面的 `--structured` 改为 `--waterfall`；只建小型合成环境，PTY 输入空行回收。最新139项相关后端、完整流水线、九类实际工具HTTP链和Figma映射后38项回归的范围/失败证据见 TODOS E1 瀑布条目；不能替代真实模型或本人 UAT。

### 人群漏斗（FUNNEL v1，catalog revision 4）

首个结果供给为“本期购买频次”，不是访客转化、历史首购或时间间隔分析。复用同次问数的有效订单：同一销售范围内，按客户去重，分别统计至少1/2/3笔有效订单的人数；同日不同订单分开计，子单合并，全退订单不计，部分退款后净额为正才计。日期/销售范围/显式派样排除和退款截止日均沿原结果合同，不另加模型 SQL。

| 合同项 | 当前能力与边界 |
|---|---|
| AI 展示属性 | 通用标题、副标题、tone/density；`show_values/show_rates` 默认 true；`rate_basis=previous/first` 默认 previous，分别表示占上一阶段/占首阶段 |
| 只读事实 | `nested_customer_counts`：unit 固定“人”、cohort_label、counting_rule、2–12个 `{label,count}`；唯一非空标签、安全整数且人数非递增。注册组件支持扩展阶段，当前计算源明确只供给购买频次三阶段，不虚构访客事件 |
| 来源 | computed facts v5 `current_purchase_frequency`；当前/对比期新增 `customer_count_unavailable_reason`。有效订单存在缺失/空白客户或同订单多身份时，该期客户数为 null 并记录原因，金额仍从同一有效订单汇总；不把未知身份算成一个人 |
| 不可用 | 本期未覆盖、身份不明/混杂或旧v1–v4结果不供给漏斗。生成明确返回数据错误，不静默改图、不拿金额代替人数 |
| 零值与比例 | 已覆盖空人群保留真实零人数；分母零或首阶段没有上一阶段时比例为 null，显示说明而不是0%。比例由人数计算，AI不能提交比例或改分母事实 |
| 渲染与尺寸 | 原生可编辑结构化HTML条形，条宽按首阶段比例，零值不画假宽度；完整人数/比例明细可展开，标签隐藏不删除明细。最小4×5、默认6×8，复用品牌变量 |
| 设计与验收 | Figma组件集 `297:2`（专页 `294:2`），目录保持 `PARTIAL`：六态×两种比例口径、标题/副标题及人数/比例开关、390px实例已读回并截图检查。明细展开、完整tone/density、密集阶段和整板原型仍开放；不替代Web、真实模型或本人UAT |

实现使用同一注册目录、组件校验、目标绑定编辑、预览/确认/取消、SQLite保存和版本回退；Skill为cg-v5。没有引入diagram-design源码、依赖或任意脚本。v1–v4原始结果与摘要继续原样读取。具体运行证据和未完成项见TODOS漏斗条目。

### 共享结果投影

- `board-component-facts/v1` 是只读渲染输入，由业务结果适配层供给，不能让 AI 写 facts。包含所需的 `scalar`、`series`、可选 `time_series`、`table`、`evidence` 形状；LINE 优先读取显式 `time_series`，BAR 保留原分类 `series`，畸形日序列不回退为两期对比。具体校验在 `component-view.mjs`。源数据通过块的 `source_result_id` 查自有键，忽略原型继承键。
- 数值按供给单位原值展示，不凭名称推断倍率。旧 GSV 适配保留数值，但缺单位时显示“单位未声明”，不擅自补“元”或乘 100。新 HTTP 适配从服务端按身份与会话精确读取已保存 computed result，声明元/分时原数保留；两期对比只声明分类序列，不能当连续趋势。新的 Agent 生成链仍待 C3。
- LINE 最多 366 点、BAR 最多 200 点；表最多 12 列、10000 行（分页展示），证据最多 40 条。超过合同明确拒绝，不静默截断。数字必须有限，数值字符串不强转，null 不改成 0。长趋势保留全部数据点，图例显示范围/点数/缺失数，可展开每页 10 条的数值明细，不堆叠几百个图例标签。
- `set_props` 合并目标组件登记属性，校验 `base_version` 后返回新 spec；不改其他块或 facts。DOM 已覆盖六类表现修改的取消、应用与本地回退，但其提案 transport 是 mock，不是有界真实 AI 或服务端持久化验证。
- 更换指标、日期、维度、筛选或新增数据列不是表现修改。后续工具必须取得相应核验结果，不把 `set_metric_ref` 的旧兼容能力当成新结果授权。

### 本轮验证证据

完整 `pipeline.mjs --check` 已通过：合成 Python 480 项；Node 分阶段 28、228、61、182 项，干净重建后再跑 61 项（重复层不计成独立覆盖）。流水线原来漏收 `src/board-spec`；本轮已加入，并在日志确认实际运行组件合同、投影与六类 DOM 编辑测试。

本地证据：`.context/checks/ai-cockpit-goal/component-library-pipeline.log` 为早期组件阶段记录。保留 Python 20 条警告及退出时 SQLite 未关闭连接警告、React `act`/旧 props 警告；不声称零警告，不以这次结果关闭真实模型、浏览器或完整产品验收。A2 新的完整宿主证据与范围见下节；当前构建结果以 TODOS 最新条目为准。

### 原生画布／对话组合（A2，仍待完整验收）

`cockpit-composition.mjs/tsx` 使用官方 `shell.overlay` 放置画布；原生 `main/conversation` 继续拥有唯一会话、消息和 composer，原生 rightbar 检查器保留。集中适配只识别固定 `183f08e9` 的 `main → main.conversation` 两层 `display:contents` 插槽包装，给原生根设置本插件拥有的属性/CSS 变量，不克隆、搬移或重建聊天。结构不符明确提示独立驾驶舱备选，不强行覆盖未知壳。

中心区至少 968px 时并排（画布最小 560px、对话最小 400px、分隔条 8px）；窄区切换画布／对话，不改变保存布局。对话可折叠和连续调宽，键盘方向键 16px、Shift 64px、Home/End 到边界。关闭/卸载恢复原生属性并清理监听。底栏入口实测保持原输入 DOM；侧栏 main 入口经原生导航重挂载聊天，实测草稿保留，不能称两入口都保持 DOM 身份。

完整 DSH + 正式插件 + 独立合成 HTTP/SQLite 已实测：无模型凭据读取已保存板、并排、键盘与鼠标连续调宽、Esc恢复、折叠不丢草稿、390px双视图、原生文件rightbar三栏共存及全屏/关闭恢复。证据见TODOS A2与 `.context/checks/ai-cockpit-goal/a2-pointer-rightbar-browser.md`。这是预置合成会话/看板，不是AI生成验收。早期插拔残留已归因测试辅助模块的包归属；隔离其包边界后，禁用/官方移除恢复DSH壳、装回可重开同一v1，12项针对性回归通过。运行中模型会话、触控与最终Figma视觉仍未通过。

显式验证入口（不写 dsh-dev current、不用 --fresh、不使用现有模型配置）：

```bash
FQ_B0_PYTHON=/Users/hutou/homebrew/opt/python@3.14/bin/python3.14 node dsh-plugins/analytics-workbench/test/native-composition-browser-probe.mjs
```

Node 24；默认只申请空闲 4328，不复用 4327。输出不带凭据的本机bootstrap入口。`restart`只重启本次DSH；`plugin-on`/`plugin-off`切换该隔离profile的配置，off是禁用，不删除依赖；实际官方remove的验证单独记账。空行回收本次DSH/HTTP并留下诊断目录，不是UAT入口。测试专用诊断与固定合成历史seed路由由额外patch挂载、经过原生认证；seed仅POST、固定会话及临时工作区，并等待原生持久化确认，产品包不加载它。`test/helpers/package.json` 必须保留独立name且不声明dsh.client：DSH按最近命名包识别file模块，缺此边界会让host-only测试模块意外重新登记业务客户端。

### 服务端保存接缝（C2/C3 已接前端，原生浏览器待验）

`backend/contracts/board_spec.py` 从同一组件目录构造严格合同；`board_spec_routes.py` 接入独立 competition app。启用须显式传入私有 `board_state_dir`；合成启动脚本将其设为既有 state 根下的 `board-documents/`，不会读真实数据库。运行该脚本仍是显式启动动作，本轮只运行隔离测试服务。

| API（前缀 `/api/v1/analytics/board-spec`） | 行为 |
|---|---|
| GET `/context?session_id=...&offset=...` | 当前身份/同一会话结果分页与组件目录；不查询新数据、不跨会话兜底 |
| POST `/previews` | 接收 title/session_id/blocks，绑定服务端结果，保存 30 分钟有效的草稿；不发布看板 |
| GET `/previews/{id}`；POST `/previews/{id}/cancel` | 重读草稿或取消；取消不改变已保存版本 |
| POST `/previews/{id}/confirm` | 必须 `Idempotency-Key`；事务内验证 base_version，发布一次；重复确认不增版本 |
| GET `/boards`；GET `/boards/{id}?version=N` | 私有看板列表、当前或指定历史快照；无需模型在线 |
| GET `/boards/{id}/versions` | 版本历史，limit 1–100、offset 分页 |
| POST `/boards/{id}/patch-preview` | base_version/block_id/changes，只改指定块；props 不能夹带事实或查询 |
| POST `/boards/{id}/layout-preview` | base_version/layouts，边界、尺寸和整板碰撞校验后形成草稿 |
| POST `/boards/{id}/rollback-preview` | base_version/to_version，恢复旧内容并追加单调新版本；不删除历史 |

独立文件 `board_documents.sqlite3`（新 application_id/schema，不迁移旧 C0 或旧 CRM）。快照包含配置、事实与所需权限范围，当前身份每次读取/确认/重放都校验；客户端不提交 owner、事实或已保存版本。私有目录 0700、库 0600；每次操作独立连接并关闭。单事务提交 head/revision/receipt/draft 状态，写入失败不改变 head，陈旧版本返回 409，不自动覆盖。

表现编辑使用保存时的事实快照，不重新计算；显式换 `source_result_id` 必须重新通过当前身份、同一原生会话的结果查验。六类之外的新结构需要扩展同一目录、数据适配与校验，不通过任意 HTML/脚本旁路。当前 computed v3 提供本期逐日 GSV，六类基础组件可共用一次受控问数。完整 G1 自主选型仍待验；9-14 有界真实模型编辑见 STATUS，不以本节历史「待验」覆盖。

逐日合同：`competition-gsv-facts/v3` 在 v2 金额单位基础上要求 `current_daily`（DAY / Asia/Shanghai / status / unavailable_reason / points）。支付日聚合复用同次计算已读的有效订单，退款按结果截止日回扣原支付日，不是现金流水。覆盖内无有效订单为零，截止日后为 null；日期须完整、连续、有序，日金额/订单数与本期汇总一致，分布也参与 evidence digest。最多 366 日；超长窗口保留有效汇总，但日序列明确 `UNSUPPORTED_RANGE/RANGE_EXCEEDS_366_DAYS`，目录不推荐 LINE，不截断或私自改粒度。结果信封仍为 computed-result/v1，`row_count=2` 指双期汇总，不是日点数量。

兼容与回退：原 v1/v2 结果和证据原样可读，无日序列时不凭总额插值；用户需要趋势才重新问数。v1/v2 golden 文件保留，新增 `daily-results.json` 由原 `unit-fixtures.py` 生成。离线生成 `competition-computed-contract.mjs --write|--check --python /absolute/python3.14` 同步 OpenAPI/TS，不改冻结 C0。旧程序未必能读 v3，代码回退须保留 v3 reader 或隔离恢复与旧代码匹配的状态；不得删除/改写新结果冒充双向兼容。

离线同步：`node scripts/dsh-b0/board-spec-contract.mjs --write|--check --python /absolute/python3.14`（Node 24；生成阶段禁止网络、SQLite 和子进程）。产物为 `analytics-board-spec.openapi.json` 和插件 `board-spec-contract.generated.d.ts`；不启动旧 CRM，也不改旧 Vue 类型。

后端最新独立回归 35 项通过、1 条 Starlette TestClient/httpx 弃用警告，证据 `.context/checks/20260912T191259751651Z/summary.json`。包含真实小 SQLite、新进程重开、无计算源读取、同会话分页/绑定、撤权、并发确认、幂等、取消/过期与事务故障。此前 C2 pipeline 日志 `board-documents-pipeline.log` 是历史证据；C3 本轮 pipeline 结果看 TODOS，不能用旧绿灯覆盖新改动。

### 原生生成与浏览器保存通道（C3 部分）

- Skill 仍是同一 DSH 的 `competition-growth` 方法包（cg-v5），不是独立 Agent。`competition_board_catalog` 返回当前会话结果/组件目录，`competition_board_generate` 只返回 `PREVIEW_READY`、`published=false`；无模型确认工具。顶层 native dispatch 显式生成 `presentationMeta`，供原生工具卡打开预览。
- `board-browser-api.ts` 使用官方 `Connection.fetch.register` 的 POST `/api/shine-mage-board` 精确扩展；UI 经 `callBoardConnection` 使用原生 `connection.rpc.call` 信封，业务操作包在 `{operation,payload}` 中。浏览器 cookie、Host/Origin、缓冲上限和取消信号由同一 DSH `/api` 载体负责，业务层校验原生信封、目标方法和操作白名单。原独立 `/shine-mage-board/*` 注册在完整宿主中出现 `webServer without inject`，不再使用；回归 fixture 把 webServer 改为独立服务 fiber，避免 root 假服务掩盖作用域问题。不提供通用 URL、SQL、模型直写或 owner 字段；业务 token 仅留在 Host，仍不冒充多租户认证完成。
- `LibraryCockpitPanel` 展示服务端预览/快照；确认使用稳定幂等键。确认回执不明时显示“保存结果待核对”，不能断言未保存；可只读核对，或显式重试同一次确认。APPLIED还需读到不低于应用版本的快照，PENDING仍保留未知状态；取消不会撤销已应用内容。刷新失败保留已确认快照，旧回执不能覆盖较新版本。取消和回退均核对目标；未确认草稿切换有明确放弃提示。重新打开通过服务读取，不需要调用模型。
- dock 调用原生 `session.prompt`，不再只限几个 B0 fixture session；切换会话后不展示前一会话的迟到状态。六类 DOM 已验证没有另建 textarea。完整原生页面、PTC 嵌套调用展示、真实模型选型/编辑及并排仍待完成；连续布局的独立浏览器验证见下。

独立完整后端集成命令（先运行插件 build；Node 24，Python 须有现有完整后端依赖）：

```bash
FQ_B0_PYTHON=/absolute/python3.14 node --test dsh-plugins/analytics-workbench/test/library-board-http.integration.mjs
```

测试自建私有合成库和临时端口，结束仅停止本次实例。真实 ToolRuntime + Connection + HTTP + SQLite 已跑通问数/目录/生成/确认/布局预览/取消/回退/新客户端重开；不是付费模型或浏览器测试。原生认证负测和组件/客户端测试随 pipeline 运行。

保存故障复现：同一 `test/library-layout-browser-probe.mjs --failures`（Node24、`FQ_B0_PYTHON`绝对路径、PTY）。终端支持一次性 `fault confirm-before`、`fault confirm-after`、`fault get`、`fault list`；`inspect`只读实际服务，空行回收。代理只在测试目录，不能装进产品或指向真实服务。真实浏览器已验拒绝写入、落盘后丢回执、只读核对/幂等重试、刷新失败保留、重开及回退；不是完整宿主或模型验收。证据见TODOS保存回执未知条目。

### 指定组件 AI 编辑（C4 部分）

画布每块有“用 AI 修改”入口。UI 先创建服务端编辑上下文，再打开看板所属的原生会话，通过官方 `session.prompt` 告知选中目标并询问修改要求；不提交未经用户要求的改动、不增加第二套 composer。原会话不可用时明确报错，保存内容仍可查看。右侧原生会话与画布并排仍属 A2 未完成工作，当前转入对话不代表最终 UX 已收口。

- `competition_board_edit_context` 只读已选组件、绑定 facts 和目录；`competition_board_edit` 只接收 `edit_context_id + changes`，宿主注入真实执行会话。board/block/base_version 从服务端 UI 选择取得，模型不能重选目标或调用确认工具。
- 表现改动复用已存事实。数据改动须先受控问数并绑定对应新 `source_result_id`；其他块继续保留原来源。LINE 已接受控逐日计算与实际工具编辑链。9-14 有界真实模型编辑与 9-15 S3 正式壳代表路径见 STATUS/S3-ACCEPTANCE；完整视觉、G1 与本人 UAT 仍待验。
- 编辑上下文有效期 30 分钟；同一 owner/native session 只允许一个待处理选择。草稿和上下文联动取消，生成过程中取消在事务提交前再次检查；过期/撤权/陈旧版本/重复提案拒绝。新页可恢复待处理上下文或从工具卡检查预览，不重建选择；UI 在切对象前要求确认取消，取消失败保留旧目标。
- UI 展示指定块修改前后属性对照，再确认保存。返回看板的“检查 AI 修改预览”也能恢复已结束/过期的编辑状态；不能因刷新失败丢掉当前快照或待确认草稿。

新增 API（沿用同一认证前缀）：

| API | 权责 |
|---|---|
| POST `/boards/{id}/edit-context` | UI 选择 base_version/block_id；会话来自已保存看板 |
| GET `/boards/{id}/edit-context` | UI 恢复当前编辑；明确返回 `{context: null}` 或已保存的上下文，不是缺失响应 |
| GET `/edit-contexts/{id}?session_id=...` | 宿主带实际原生会话读取所选块与 facts |
| POST `/edit-contexts/{id}/propose` | 宿主带实际会话和 changes 生成 PATCH 预览，不修改 head |
| POST `/edit-contexts/{id}/cancel` | UI 取消上下文及其待确认预览，不回滚已应用修改 |

存储兼容：同一私有 `board_documents.sqlite3` 增加 `edit_contexts` 表与 `metadata.edit_context_schema=1`，安装在事务内；不改写既有 head/revision/receipt，保留 v1 快照读取格式。旧版本会忽略新表，但不会提供编辑上下文功能；未知扩展版本拒绝启动，不自动重建状态。回退时保留整个私有状态目录，不删除表/文件；正式切换或发布仍需单独授权。

当前证据：157 项相关后端检查（`.context/checks/20260912T205322676863Z/summary.json`），包含计算/取消/存储/HTTP/兼容/图表口径及新进程恢复；14 项解码/投影与 6 项编译 DOM 通过。`daily-series-http.log` 证明真实 ToolRuntime/原生认证/HTTP/SQLite 下六类表现编辑的取消/应用均复用一个结果，LINE 改日期重新问数只更换所选块来源，保存重开及回退通过。完整 pipeline `daily-series-pipeline.log` 及干净重建通过，保留既有警告。本节 9-12 工具链证据不代替后来的真实模型与浏览器证明；当前停点见 STATUS/TODOS（UAT 与 G1–G6 仍未勾选）。

### 连续布局与隔离浏览器验证

查看模式没有拖动手柄；“调整布局”进入本地草稿。拖动/缩放手柄连续移动，方向键一格、Shift 五格，Esc 取消正在进行的手势。碰撞不给落位，不推移邻居。多次调整后“检查布局”生成服务端预览，再“确认保存”；取消恢复已保存版本，布局不修改 facts。窄画布查看使用单列阅读，编辑保留可滚动 12 列网格，响应式不写回布局。

按住可见边缘可连续滚动；触发边界按画布、可视窗口及裁切父容器的交集计算，不要求用户把指针移到屏幕外。跟随预览在网格内裁切，不额外撑宽/撑高滚动空间；取消后重新编辑不保留旧的未保存播报。隔离浏览器已验1440宽纵向持续/反向和390宽横向止界；触控、父级滚动中的坐标一致性与全部物理边界仍待验。

独立浏览器入口（完整 Python 依赖，Node 24）：

```bash
FQ_B0_PYTHON=/Users/hutou/homebrew/opt/python@3.14/bin/python3.14 node dsh-plugins/analytics-workbench/test/library-layout-browser-probe.mjs
```

打开输出的本机 URL，选择“隔离布局验证看板”。入口只创建本次私有合成状态，显式测试引导仅在 test helper 启用，不装入生产插件。其页面不仿制 DSH 对话，不能用于证明原生壳/模型通过。在启动终端按 Enter 结束，读回最终快照并回收本次服务和临时库。持久化、取消、关闭重开、回退及长画布可见边缘滚动已通过实际浏览器操作；完整用户 UAT、触控/全部边界/原生壳内布局仍开放。

当前验证日志：`.context/checks/ai-cockpit-goal/library-generation-http-integration.log` 与 `library-generation-pipeline-r2.log`。后者含 Python 480、Node 分层 28/229/61/197、干净构建重复 61；35 项新后端回归在独立完整后端解释器运行，不混入 minimal B0 数量。警告和首次失败日志保留，尚无本轮真实模型/浏览器 UAT 通过声明。

构建不再将 `COMPETITION_HTTP_BASE/TOKEN` 编译进公共 JS。带合成哨兵配置的真实构建及 JS/SourceMap 检查通过。旧 C0 overlay 仍有显式直连配置接缝，认证迁移/部署兼容待核验；不要恢复内联 token，也不要声称旧 HTTP 资产流程已由新看板集成覆盖。

### 侧栏比赛看板入口（2026-09-15）

侧栏底部在同一 `sidebar.footer.action` 槽新增第二个入口「比赛看板」（id=`shine-mage.analytics-b0.legacy-board`、order=20；原入口 id=`shine-mage.analytics-b0.footer`、order=10，选择改按稳定 id 而非 slot 名）。它在新标签页打开旧 CRM 前端 `http://127.0.0.1:5173/`，即 `scripts/ops/start-stack.sh` 服务的前端。

- 用真实锚点而不是 `window.open`：弹窗策略拦截不会让按钮静默失效，中键与状态栏预览也仍可用。`target="_blank"` + `rel="noopener noreferrer"` 与两档文案（宽栏「比赛看板」／收窄「看板」）由 `test/plugin-ui-lifecycle.test.mjs` 的编译后 DOM 断言覆盖，该测试在 `window.open` 被调用时直接失败。
- 看板仍是独立应用、独立进程与独立登录：DSH 不内嵌、不代理，也不放松旧前端的 `frame-ancestors 'none'`。
- 地址按 `start-stack.sh` 的默认 `FQ_FRONTEND_PORT=5173` 写死；改该变量后此入口不跟随。`--strictPort` 让端口冲突表现为启动失败，而不是在 5173 上静默服务另一个应用；前端未启动时用户看到浏览器自身的连接失败页，插件不接管。

## v0.8 实际能力与边界（历史基线）

- 根 Host 入口 `lib/index.js` 同时提供 UI discover 与私有原生协议桥，不登记工具、不保存业务账本或循环调用模型。桥只接受本次运行能力，返回原请求关联的原生日志及 `whenIdle + flush` 退出证据。
- 独立 `lib/tool.js` 默认登记 `analytics_b0_query`，参数只有 `{"query":"channel_repeat_rate"}`。从可信原生 call/turn 查找原 requestId，在 FastAPI 预留步骤后取得固定 `STUB / SYNTHETIC_FIXTURE`：100 位合成客户、25 位复购、25%，日期 2026-09-01。调用私有 loopback 接口；无 SQL、真实文件查询、任意网络或本地备用结果路径。`B0_RUNTIME_FAMILY=channel_followup` 时改为登记 `analytics_channel_followup_query`（完整 G2 请求，固定 `/internal/native/channel-followup`，输出 typed receipt）。B0 fixture 工具卡仍保留；渠道后续购买查询卡见 G4b，资产保存见 `--native-query-assets`。
- 独立 `lib/skills.js` 默认注册固定 `growth-analysis-b0` 及精确资源工具；整包包含 `SKILL.md`、证据引用与无数字示例，`skill-package.lock.json` 冻结全部字节。query-mode 另有不可变 `channel-followup-query` 包与 `query-skill-package.lock.json`。构建拒绝越界、软/硬链接、额外文件/脚本、超限和引用漂移；运行时读取不可变快照。每步与方法读取都回查后端权限、版本和预算，不新增通用文件工具或 Agent loop。
- 客户端登记品牌 `sidebar.brand.mark/name` 及原四项 `sidebar.footer.action`、`shell.overlay`、`tool.call.toolview`、`conversation.input.dock`；品牌单槽使用 `priority:-10` 先于上游默认贡献，不修改上游代码。等待 owner 声明后登记；两个 root 插槽共享 `defineStore`。任务状态栏只读 FastAPI 投影，展示最近三个 run 的状态、阶段和步数；断线明确标记旧快照，刷新不重新提交。
- UI-B01 最小适配：客户端只在 `ctx.sessions.list.phase === 'ready'` 且指定 `session-b0-synthetic-primary` 同时存在于 Host `ids/byId` 时，通过公开 `ctx.sessions.open(id)` 自动选中一次。不会调用 `create`、操作 DOM、选任意其他会话，或在用户后续切换时抢回焦点；目标缺失继续等待，选择失败只报告一次并无 fallback。每次插件重新加载/页面刷新会重新校验，这是 B0 固定主会话接缝，不是业务 run 自动受理实现。
- 默认“我的驾驶舱 · B0”打开源码内置 finite mock：一个板块的手工标题预览、应用、撤销未应用草稿与页面刷新恢复；不依赖活动会话/模型。不是 AI 局部编辑，也不是完整可组装驾驶舱。
- 仅当 `serve.mjs --native-query-assets` 且 GET `/b0/assets` 返回 `http_api=CONNECTED` 时，同一入口改走 HTTP overlay：列出已保存 SNAPSHOT，对唯一私人驾驶舱 add/copy/remove/layout/preview/undo。浏览器不带 backend bearer；GET 列表不自动建板。无板时加入会先 `POST /b0/dashboards` 再建预览；预览/保存 409 后重读，不保留过期 pending。kernel 不可用时 `/b0/assets` 为 `UNAVAILABLE`，不报 CONNECTED，入口回退 mock。`test/asset-overlay.test.mjs` 用 mock transport 覆盖上述编译后 DOM，不是浏览器 E2E。
- mock 路径的 localStorage 仅存 `analytics-b0-ui/v1 + title` 两字段，不缓存授权、身份、结果或业务资产。HTTP overlay 的权威资产在独立 SQLite（`analyses/` 与 `cockpit/`）；分析库读取与驾驶舱写入是先后事务，不是跨库原子。
- 侧栏「驾驶舱」面板（`sidebar.panellist` id=`cockpit` + `main` key=`cockpit`）的默认初值就是一块合成样例看板：`src/board-spec/demo-board.mjs` 的 `board_demo_channel_gsv_2026_08`，3 个 METRIC 加 LINE/BAR/TABLE/EVIDENCE/LINK，数字全部来自冻结的固定 `source_result_id`。标题带「样例」、证据块标 `SYNTHETIC`，明示不是真实经营数据；它只是前端 store 初值，不写业务库、不执行查询，聊天下「生成驾驶舱」会把它换成对话产物。
- 聊天下「生成驾驶舱」只预览草案，确认后才写入画布（`GENERATE_BOARD`）。没有可绑定的核验结果就拒绝整板，不画 0%。点选卡片后旁路问数只建议 `PATCH_BLOCK`（`set_title` / `set_kind` / `set_metric_ref` / `set_layout`），再确认才落盘；「这个数字是多少」走绑定刷新，不改标题。HTTP：`POST /api/v1/analytics/board-spec/ask` 只返回 patch，不写 facts、不接飞书。
- 画布 closed kinds：`METRIC` `BAR` `LINE` `TABLE` `EVIDENCE` `html_sandbox` `LINK`。刷新按块上的 `source_result_id` 重绑数字，不是写死 `r1`。回退走 history 上一版。`html_sandbox` 用 srcdoc + CSP（无 script）；刷新不跟随跳转、不打内网。
- 聊天下「生成飞书文档 / 生成多维表」只往板上加 LINK 占位（`example.invalid`），不接飞书 token。
- 侧栏「数据员工」面板（`sidebar.panellist` id=`staff` + `main` key=`staff`）是旁路 fixture，不另开一套聊天；广场入口可 `sessions.create()` 回到对话。
- 底栏「我的驾驶舱」有 `layout.selectPanel('cockpit')` 就切侧栏面板；没有 layout 才打开 overlay。底栏另有「比赛看板」，只在新标签页打开独立前端，不切面板、不开 overlay。
- 驾驶舱可经公开 `sessions.clear()` 脱离当前会话，关闭时仅恢复仍存在的原选择，不创建/删除/取消会话；未应用草稿退出需确认，Tab 双向保持在弹层、关闭后归还固定入口焦点。原始品牌静态路径与完整条件往返标本由固定网关服务；后者不是实际同条件 BI，不加载旧 Vue/Pinia。
- 工具卡只读取 `block.meta` 的精确版本化结果；处理中/失败/未知格式分开，不从模型文本猜成功。默认不开放保存、导出或审批。`--native-query-assets` 下可将 SUCCEEDED 查询保存为 SNAPSHOT 并加入驾驶舱；仍无导出/审批。“停止查询”取消当前卡片所属会话，不取页面第一个 `data-session-id`。

## 固定构建与验证

从工作树根运行，使用 Node 24 与显式 Python 3.14+ 路径。版本闭包在 `toolchain.json`、`build-tools/pnpm-lock.yaml` 和 `scripts/dsh-b0/requirements.lock` 冻结。下面的 `--check` 不安装依赖，不启动 CRM 或模型；真实 Loader 测试默认短暂监听私有 4326，supervisor 测试选择空闲 4328/4329 并自行关闭。端口冲突直接失败，不终止别人。

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
