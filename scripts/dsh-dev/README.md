# dsh-dev

本地完整 DSH web 基座入口。不是 B0 合成笼，不管理 8000/5173/4315–4319。

固定上游：`deepseek-ai/deepseek-harness@d347e703908d0406b7a7ef80e3a0e594d86b2215`。Node 24。

## 命令

```bash
# 只读诊断：启动就绪 / 认证说明 / 陈旧构建 / 端口归属。不绑定端口、不向任何 PID 发信号。
node scripts/dsh-dev/cli.mjs diagnose --upstream /absolute/pinned/dsh

node scripts/dsh-dev/cli.mjs check --plugin off --upstream /absolute/pinned/dsh
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
| 8000 / 5173 | 用户已有 Mission/Vite | 禁止停止或复用 |
| 4315–4319 | B0 合成笼 | 禁止停止或复用 |
| **14327** | 比赛轨独立 DSH | 允许作为 `--web-port`；默认不启动 |
| 15173 | 比赛轨 Vite 预留 | 本入口不绑定 |

`start` 在目标端口已被占用时失败（`assertFree`），不会去杀占用者。`stop` 只向本工作树 `current.json` 里的 supervisor control 发 Bearer，不根据 PID 杀进程。

## 认证

未带 cookie 的 `GET /` 必须 401。启动日志里的 `?token=` 只用于一次兑换 HttpOnly cookie，随后 303 到 `/`。文档、诊断 JSON 和 probe 输出不得打印 token。禁止关认证绕过。

## 真实模型与比赛工具

用户在本实例 Settings → Models 配置 provider；开发入口不从其他工作树或 shell 复制模型密钥。若运行机器需要额外信任链，可显式设置 `NODE_EXTRA_CA_CERTS=/absolute/public-ca-bundle.pem`。只接受绝对路径，Node 仍验证证书；不得用关闭 TLS 校验代替。2026-09-10 的候选通过 `/etc/ssl/cert.pem` 完成真实 DeepSeek-V4-Flash 调用。

同时显式设置 `COMPETITION_HTTP_BASE`、`COMPETITION_HTTP_TOKEN` 后，单一业务插件入口注册诊断工具。宿主注入当前会话和取消信号；每次 HTTP 最长 5 秒。结构化条件由后端严格验证，模型不能注入身份或权限。该连接本身不保证业务计算完成，当前诊断服务仍有合成 fixture 返回；见 [T13 记录](../../docs/hackathon/evidence/product-readiness-2026-09-10/T13-LIVE.md)。浏览器构建也需使用相同的 HTTP 配置；普通离线 pipeline 会重新生成默认构建，用户验收前须按实例配置重建。

## 构建检查

诊断检查：固定 SHA / lock SHA-256、`apps/cli/lib/bin.js`、`apps/web/dist/index.html`、源码是否新于产物、插件 `lib/index.js`。缺产物时标 stale，不在本入口执行 `pnpm install` 或 `pipeline --prepare`。

本工作树若 Logo PNG 仍是 Git LFS 指针，诊断记 `lfs_pointer`，不自动 smudge，也不把指针字节当 PNG 提供。

## 合成 quickstart（准备完成的机器）

1. Node 24 + 已 pin 且已构建的上游。
2. `diagnose` 中 upstream=ready、4327 归 user_demo、14327=free。
3. 需要独立实例时：`--web-port 14327 --plugin on|off`，结束必须 `stop` 或杀掉本 supervisor PID。
4. 用 `probe.mjs` 确认 401/兑换/200。真实模型、浏览器原生矩阵仍单独标 NOT_RUN。
