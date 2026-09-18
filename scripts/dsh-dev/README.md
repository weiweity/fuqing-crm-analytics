# dsh-dev

本地完整 DSH web 基座入口。不是 B0 合成笼，不管理 8000/5173/15173/4315–4319。

固定上游：`deepseek-ai/deepseek-harness@ddefc45fbc7f8e46dd73185e68295696d1297887`（0.1.6-alpha.2）。Node 24。后续再升版本仍改 `dsh-plugins/analytics-workbench/toolchain.json` 与本入口 `PINNED_SHA`，不要直接改上游源码。

## 命令

```bash
# 只读诊断：启动就绪 / 认证说明 / 陈旧构建 / 端口归属。不绑定端口、不向任何 PID 发信号。
node scripts/dsh-dev/cli.mjs diagnose --upstream /absolute/pinned/dsh

node scripts/dsh-dev/cli.mjs check --plugin off --upstream /absolute/pinned/dsh
node scripts/dsh-dev/cli.mjs reload
node scripts/dsh-dev/cli.mjs start --plugin on --web-port 6677 --detach
node scripts/dsh-dev/cli.mjs start --plugin off --web-port 6677 --detach
node scripts/dsh-dev/cli.mjs start --plugin off --web-port 14327 --runtime /ABS/.context/dsh-dev/runtime-a4
node scripts/dsh-dev/cli.mjs status
node scripts/dsh-dev/probe.mjs          # 只打 owned current.json；不打印 token
node scripts/dsh-dev/cli.mjs stop       # 只停本工作树 supervisor
```

PATH 上的 Node 若不是 24，check/start 会失败。诊断会指出可用的 node@24 路径。请显式调用，例如：

`/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-dev/cli.mjs diagnose`

## 端口归属

| 端口 | 角色 | 本入口 |
|---|---|---|
| 127.0.0.1:4327 | 用户 DSH 演示 | 禁止停止、复用、HTTP 探测冒充本轨 |
| 8000 / 5173 | 用户已有 Mission/通用 Vite | 禁止停止或复用 |
| 15173 | 比赛看板 Vite（`start-stack` 默认） | 禁止停止或复用；本入口不绑定 |
| 4315–4319 | B0 合成笼 | 禁止停止或复用 |
| **6677** | 本产品本地 DSH（浏览器可开） | `--plugin on` 装伸美包；`--plugin off` 只禁用该包，官方壳还在 |
| **14327** | 比赛轨独立 DSH | 允许作为 `--web-port`；默认不启动 |


`start` 在目标端口已被占用时失败（`assertFree`），不会去杀占用者。`stop` 只向本工作树 `current.json` 里的 supervisor control 发 Bearer，不根据 PID 杀进程。

## 认证

未带 cookie 的 `GET /` 必须 401。启动日志里的 `?token=` 只用于一次兑换 HttpOnly cookie，随后 303 到 `/`。文档、诊断 JSON 和 probe 输出不得打印 token。禁止关认证绕过。

## 真实模型与比赛工具

用户在本实例 Settings → Models 配置 provider；开发入口不从其他工作树或 shell 复制模型密钥。若运行机器需要额外信任链，可显式设置 `NODE_EXTRA_CA_CERTS=/absolute/public-ca-bundle.pem`。只接受绝对路径，Node 仍验证证书；不得用关闭 TLS 校验代替。2026-09-10 的候选通过 `/etc/ssl/cert.pem` 完成真实 DeepSeek-V4-Flash 调用。

同时显式设置 `COMPETITION_HTTP_BASE`、`COMPETITION_HTTP_TOKEN` 后，单一业务插件入口注册诊断及组件库生成工具。宿主注入当前会话和取消信号；每次 HTTP 最长 5 秒。结构化条件由后端严格验证，模型不能注入身份或权限。当前仅合成源，见 [T13 历史记录](../../docs/hackathon/evidence/product-readiness-2026-09-10/T13-LIVE.md)。本轮新看板通过 DSH 认证 Connection RPC 由 Host 转发，浏览器构建不再注入业务 token；无需按凭据重编公共 JS。旧 C0 直连 overlay 的认证迁移和部署兼容仍待验，不以本条声明旧路径可用。启动还须显式配置 BoardSpec 状态目录；功能与证据见 [插件 README](../../dsh-plugins/analytics-workbench/README.md)。

真实模型验收前，可对**明确指定的已运行实例**执行只读通道预检：

```bash
node scripts/dsh-dev/board-model-preflight.mjs --runtime /absolute/runtime --output /absolute/evidence.json
node --test scripts/dsh-dev/board-model-preflight.test.mjs
```

预检仅兑换本地原生认证、读取模型目录与看板 `status`，不创建会话、不发模型请求、不改设置、不重启。拒绝非回环地址，不记录启动 token、cookie 或原始错误响应。退出码 0 只表示 `transport_ready`，2 表示通道条件未满足，1 表示输入/输出失败。**模型目录在未配置密钥时也可能列出路由**；`credentials_verified=false`、`model_execution=NOT_RUN` 必须保留，不能以预检替代真实调用或业务服务连通验证。看板 404 表示该实例未提供当前协议，不自动 reload 已有用户实例。

## 构建检查

诊断检查：固定 SHA / lock SHA-256、`apps/cli/lib/bin.js`、`apps/web/dist/index.html`、源码是否新于产物、插件 `lib/index.js`。缺产物时标 stale，不在本入口执行 `pnpm install` 或 `pipeline --prepare`。

本工作树若 Logo PNG 仍是 Git LFS 指针，诊断记 `lfs_pointer`，不自动 smudge，也不把指针字节当 PNG 提供。

## 合成 quickstart（准备完成的机器）

1. Node 24 + 已 pin 且已构建的上游。
2. `diagnose` 中 upstream=ready、4327 归 user_demo、14327=free。
3. 日常改插件：`node scripts/dsh-dev/cli.mjs reload`（Node 24）。自由 HTML 页库要落盘时加 `--page-http on`（默认 `127.0.0.1:18091`，绝不是 6677）。会构建 workbench、在**固定** `.context/dsh-dev/runtime` 上重启 6677，并打开启动 URL。启动器会自动带 `NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem`，否则 Node 24 连不上 `api.deepseek.com`。不要用 `--fresh`，否则 API Key 和设置里另装的插件会丢。不要用系统里的 `dsh web` 另开一套 home。`--fresh` 只用于故意清空的验收机。插拔伸美：`on`/`off`。不要用 competition-next 工作树起 6677。结束必须 `stop`。
4. 用 `probe.mjs` 确认 401/兑换/200。真实模型、浏览器原生矩阵仍单独标 NOT_RUN。
