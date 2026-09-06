# B0 当前控制面清单

固定上游：DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。适用范围：**本机单一合成身份与指定工作区**；不是生产权限或渗透测试认证。

机器执行策略：[gateway-policy.mjs](../../scripts/dsh-b0/gateway-policy.mjs)、[gateway.mjs](../../scripts/dsh-b0/gateway.mjs)。本清单用于审阅，不是新的可调用 API。每次修改操作、参数或路由，须同步对应正反例，未知操作默认拒绝。

## 鉴权与传输

- 浏览器只获得本实例业务 Cookie（HttpOnly、SameSite=Strict）；原生 DSH 凭据、FastAPI runtime/gateway 能力凭据留在各自服务端。
- 仅监听 loopback。Host、Origin、Sec-Fetch-Site 按当前同源规则限制；本地能力不是正式 CEO 身份。
- 所有已认证 HTTP、WS 握手，以及既有 WS 输入/输出逐条重查 FastAPI 当前许可。不缓存正向授权；连接失权或许可服务不可用即关闭，恢复须重新连接。
- 空闲 WS 每秒核验；每连接输入/输出有界串行队列各 16，最多 8 连接、8 活动流、64 个生命周期流 ID。已取消/已结束的 ID 不得复用。
- HTTP body / WS frame 上限各 65,536 字节；不接受二进制 WS。所有拒绝输出剥离上游错误详情、路径和凭据。

## HTTP 操作

| 类别 | 允许项与参数 | 返回或边界 |
|---|---|---|
| 原生元数据 POST | `session/modelCatalog`、`agentPresets/list`、`settings/describe`、`session/canOpenWorkspacePath`、`settings/canOpenAgentPresetDirectory`；仅空 `args` | 固定模型/预设、小型只读 UI 命名空间；原生目录打开能力为 false |
| 原生列表 POST | `session/list`，仅 `args._request={}` | 只返回固定主会话；已实际创建的两个外部合成会话不出现 |
| 历史 POST | `session/page`，指定主 session address、throughSeq，可选 beforeSeq/maxMessages | 非负游标、有界最多 100 条、地址非子 agent；不猜其他会话 |
| 发问 POST | `session/prompt`，固定 session、合法 requestId、`mode=queue`、一个 1–8000 字文本、允许时区 | queue 是当前原生 wire 形态，业务仍限制单个在途任务；先经 FastAPI 持久受理，不把原生 accepted 标完成；不开放 steer/队列编辑 |
| 停止 POST | `session/cancel`，仅主 session ID | 网关查当前执行中的 run，按版本及稳定 key 发取消；未退出不标 CANCELLED |
| 业务只读 GET | `/b0/context`、`/b0/runs/run_<32hex>` | 后端按当前归属和权限返回；客户端不能指定 owner 或执行操作 |
| 静态 GET | `/`、DSH 固定构建 `/assets/` 与 favicon；插件 URL 仅精确 boot manifest 集合 | 不提供通用代理；宿主重启仅允许同模块/同内容批次的新 boot nonce |
| 品牌 GET | `/b0/brand/logo.png`、`/favicon.svg` | 只读原始固定 hash 素材；不接路径参数 |
| BI 合同样例 GET | `/b0/board-sample?ref=b0-condition-specimen-v1` | 唯一固定合成引用；无脚本、无查询、无旧 Vue/Pinia。附加旧筛选、任意 return、重复/未知引用均拒绝；不是实际 run 解析器 |

以上 POST 使用精确 JSON-RPC envelope，URL 与 method 必须一致，顶层未知字段拒绝，API URL 不得携带 query。不开放其余工作区/会话创建、删除、fork、rename、search、模型/预设切换、配置写入、凭据、命令执行、动态插件检查/安装、文件操作。

## WS mux 与 Fetch

唯一入口 `/api/remote.mux`：

| 流 | 输入 | 允许输出 |
|---|---|---|
| `$events` | 空 args | 最小 ready；synthetic home；不透传全局命令/事件 |
| `session/control` | 空 args | 主会话的队列/任务/投影状态 |
| `workspace/follow` | 空 args | 当前工作区、主会话归属；过滤外部工作区/归档成员 |
| `session/follow` | 主 session address、有界 maxMessages、可选 assistantStream | 主会话 snapshot/records/events，拒绝外部或子 agent 地址 |
| `cancel` 帧 | 当前连接的活动 streamId | 只取消订阅，不等于业务取消；之后不可复用 ID |

RemoteFetch/上传/下载私有文件全部拒绝，包括真实 `session/uploadFileBinary` 的 GET/POST 和将它伪装成 JSON-RPC。普通静态文件与品牌素材不算开放 RemoteFetch。旧 `/audience` 及私有 BI 页面仍拒绝。

MCP：**NOT ENABLED**。没有为补测试安装 MCP、动态工具发现或第二套 Agent Loop。

## 当前证据与剩余边界

[gateway-smoke.mjs](../../scripts/dsh-b0/gateway-smoke.mjs)在每个显式指定的当前运行目录留下独立报告，覆盖正常元数据、自己历史、四类 WS、两个真实原生合成外部会话、跨源/越权/未登记/过大输入/编码绕过及 BI 样例路径。它绝不发送合法 prompt，原生合法发送/停止/恢复由独立七问报告证明。

[control-permission-probe.mjs](../../scripts/dsh-b0/control-permission-probe.mjs)暂停并最终恢复经 PID/命令核验的本次合成权限后端，复验 HTTP 与已建立 WS 的 fail-closed；真实权限撤销另有 Python 当前权限测试。这两层证据不能冒充生产身份目录撤权或完整多用户审计。

当前报告与逐门结论以 [B0 连续执行清单](./B0-EXECUTION-CHECKLIST-2026-09-06.md)所指最终报告为准。被拒绝的原生管理插件在浏览器控制台可能产生预期 403；不静默抹去错误，也不为消除控制台信息而开放权限。
