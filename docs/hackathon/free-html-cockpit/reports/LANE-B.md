# LANE-B · 运行时与资源

- 状态：**DONE**（T0 三项浏览器门禁有证据；T3/T4 模块与负测已跑。OCR 审查 11 项已修完并复测。未把 `sandbox` 属性写成 CPU 隔离。）
- 执行日期：2026-09-18
- 执行者：Lane B 独立执行者（本 worktree）
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-B`
- 分支：`codex/free-html/lane-b`
- 开始/结束 HEAD：`b45a27bb9022057ce37aa9123927e8b4663a2720`（未 commit、未 push、未 merge）
- dirty：未跟踪 `dsh-plugins/analytics-workbench/src/free-page/`、施工包 `docs/hackathon/free-html-cockpit/`、既有 `AI-PROMPT.md` / `MAIN-COORDINATOR.md`
- 任务：T0 / T3 / T4；节点 N07 / N09 / N15
- 方案 SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（与 `approved-plan.md` 字节一致）
- 冻结合约：消费 `fixtures/frozen-contract-v0.json`（`free-page-bridge/v1` + MessageChannel）。未发明第二套桥协议。
- 无 `.codegraph/`，未建索引。

## 实际完成

### T0 可行性（先于冻结 D20 实现）

隔离夹具：`src/free-page/runtime/isolation-probe.mjs`。产品预览宿主是 `preview-host.mjs`（N15：停止/重启/恢复）。T0 的宿主 rAF/点击计数只在夹具页，不进 Lane E 挂载面。

目标浏览器实测（Headless Chrome，viewport 1280×800）：

| 门禁 | 结果 |
|---|---|
| 宿主在失控页运行时仍可操作 | **通过**。`while (true) {}` 期间宿主 rAF 49→134，宿主按钮点击计数 0→1，CDP evaluate 未超时 |
| 单页可关闭/重启 | **通过**。停止后 iframe 移除，重启后 iframe 回到 DOM |
| 已保存版本可恢复 | **通过**。srcdoc 含「已保存经营复盘」；恢复截图可见标题与 SVG |

`cpu_isolation` 记为 `observed-host-operable-during-srcdoc-runaway`。这是 **Chrome/153 本次运行的观察**，代码里 `FREE_PAGE_SANDBOX = 'allow-scripts'`（无 `allow-same-origin`）只声明权限/opaque origin，**没有**把 sandbox 属性写成 CPU/进程隔离。

### T3 页面包

- `resource/package-normalize.mjs`：html/css/js 保真、额度、`node_map` 提取、显式资源清单 + sha256
- `resource/resource-cache.mjs`：内容寻址；每次 get 再核 actor/page/version；命中 hash 不能越权
- `resource/network-policy.mjs`：静态扫描 img/script/link/css/js/WS/beacon，不只 `fetch`
- 三类合成样本：杂志 CSS、Canvas 交互、SVG+动画；BoardSpec kind **不是**生成白名单

### T4 运行时

- opaque-origin：`sandbox="allow-scripts"` + srcdoc CSP（`connect-src 'none'` 等）
- `runtime/message-channel.mjs`：握手字段与冻结合约一致；`data.read` / `data.cancel`；禁 `sql` / `save` / `http.fetch` / `credential.read`；错误 nonce → `BRIDGE_NONCE`；dispose 后旧端口 → `BRIDGE_EXPIRED_INSTANCE`；无 C 适配器时 `RESULT_UNAVAILABLE`（不提供 SQL/保存）
- `preview/preview-host.mjs`：N15 停止/重启/恢复已保存版本，与页面 iframe 独立
- 外联负测：动态拼接 `https://example.com` 的页面走真实代理出口；`egress_proxy_hit_count = 0`
- 未改 `html-sandbox.mjs`；旧禁脚本测试仍绿

### 给 Lane E 的挂载点

```js
import { mountPreviewHost } from '../free-page/preview/preview-host.mjs';
```

不要改 `src/client/library-*`。本 lane 不持有资料库业务状态。

### OCR 审查后已修（High/Medium/Low 全修）

1. 完整 HTML 文档先对原始 html/css/js 做外联扫描；head 的 `link`/`script src` 不再静默丢掉。`https://` 拒绝；`resource:` 保留进片段。
2. T0「宿主仍可操作」计数从 `mountPreviewHost` 挪到 isolation-probe 夹具。
3. 资源缓存始终按解析后的 `actorId` 写入/核验，不再因省略 options 而跳过。
4. `attach`/`bindPort` 关闭上一根 MessageChannel，并清 watchdog；二次 dispose 不把实例计数减成负数。
5. isolation-probe 测试现在硬断言 `host_operable` / `close_restart` / `saved_restore`。
6. 非法 base64 返回 `INVALID_PAGE`，不再抛 `atob`。
7. 相对路径 `/` `./` `../` 及无法解析的 URL 默认拦截。
8. 桥 `request` 必须带 identity 形态的 `request_id`；页面 bootstrap 缺省时生成。
9. `initTimeoutMs` 与 `handshakeTimeoutMs` 都用于初始化超时；`maxInstances` 有存活计数。
10. 删除未使用的 `LEAK_RUNTIME_HTML`。
11. srcdoc 对 CSS/JS 中和 `</style>` / `</script>`，避免拆 wrapper。

## 验证证据

| 检查 | 准确命令/操作 | 环境/夹具 | 结果/退出码 | 证据路径 |
|---|---|---|---|---|
| 工具链核对 | `node -v`；`python3 --version`；读 `toolchain.json` | Node **v24.19.0**（`node@24`）、Python 3.14.4、DSH 0.1.6-alpha.2 / `ddefc45f`；宿主 pnpm 11.19.0 未升降 | 已核对 | — |
| 冻结合约常量 | `node --test …/frozen-contract.test.mjs` | `fixtures/frozen-contract-v0.json` | pass | 测试本身 |
| T3/T4 单测 + 旧沙箱回归 | 见下方完整命令（不含 probe 时 26 pass） | Apple M5 · Darwin 25.5.0 arm64 | **exit 0** | — |
| T3/T4 + T0 Chrome | 见下方完整命令（含 probe 27 项） | Chrome/153.0.8010.48 Headless · 1280×800 | **27/27 pass，exit 0**（OCR 修复后复测） | 本表下一行 |
| T0 浏览器三项门禁 | 同上命令内 `isolation-probe.test.mjs`；也可单独 `node …/isolation-probe.mjs` | 自有 127.0.0.1 随机端口（本次 harness 59711 / proxy 59712）；**未碰 6677** | gates 全 true；probe 脚本 exit 0 | `reports/lane-b/t0-evidence.json` |
| 外联负测 | 动态拼接 URL 的页面 + HTTP/CONNECT 代理 | 代理记录 example.com；loopback 转发 | `egress_proxy_hits: []` | 同上 |
| 旧 html-sandbox 禁脚本 | `node --test …/html-sandbox.test.mjs` | 未改该文件 | 10 pass | — |

完整命令（仓库根，Node 24）：

```bash
export PATH="/Users/hutou/homebrew/opt/node@24/bin:$PATH"
PLUGIN="dsh-plugins/analytics-workbench/src/free-page"
node --test --test-timeout=120000 \
  "$PLUGIN/resource/frozen-contract.test.mjs" \
  "$PLUGIN/resource/package-normalize.test.mjs" \
  "$PLUGIN/resource/resource-cache.test.mjs" \
  "$PLUGIN/resource/network-policy.test.mjs" \
  "$PLUGIN/runtime/isolation-policy.test.mjs" \
  "$PLUGIN/runtime/message-channel.test.mjs" \
  "$PLUGIN/runtime/session.test.mjs" \
  "$PLUGIN/runtime/error-boundary.test.mjs" \
  "$PLUGIN/runtime/isolation-probe.test.mjs" \
  "$PLUGIN/preview/srcdoc-builder.test.mjs" \
  "$PLUGIN/preview/preview-host.test.mjs" \
  "dsh-plugins/analytics-workbench/src/board-spec/html-sandbox.test.mjs"
```

浏览器：Google Chrome **153.0.8010.48**（HeadlessChrome/153.0.0.0），viewport 1280×800。iframe 实宽约满 1280 夹具栏。截图：

- `reports/lane-b/t0-saved.png` — 已保存页标题 + SVG
- `reports/lane-b/t0-runaway.png` — 失控循环中宿主 ticks/click 仍在涨
- `reports/lane-b/t0-restored.png` — 停止/重启后恢复同一已保存页

恢复时延（本次）：`recovery_ms = 1113`。机器：Apple M5。

现役 6677：PID **8758**，施工前后未变。

## 未完成与失败

无失败项。以下 **NOT_RUN**，不报通过：

- `scripts/dsh-b0/pipeline.mjs` 未把 `src/free-page` 列入扫描目录（当前只扫 `src/board-spec` / `src/client` / `src/competition-agent` / `tests`）
- P12 真浏览器集成旅程（生成→绑定→选区→D6/D9→重开）
- P13 真实模型三个样本
- headed（有窗口）Chrome；读屏/键盘/200%/D38 宽度矩阵
- Lane C 的真实 `data.read`（本 lane 在无 adapter 时返回 `RESULT_UNAVAILABLE`）
- Lane A 的 SQLite 落盘；预览宿主只在内存里记住 `savedPackage`
- 全量 B0 pipeline / 干净重建

静态扫描承认：`['ht','tps://example.com/'].join('')` 能绕过源码扫描；运行时 CSP + 代理负测覆盖该缺口。watchdog ping **不能**打断 `while (true)`；终止手段是移除/替换 iframe。本次 Chrome 观察宿主仍可点「停止页面」。

## 交给下一批次 / integration notes

1. **P12**：把 `src/free-page` 加入 `scripts/dsh-b0/pipeline.mjs` 的 test 扫描。Lane B 未改 pipeline。
2. **Lane C**：给 `createPageSession({ adapter: { read, cancel } })` 接只读 `data.read`。不要新增 `sql` / `save` / `http.fetch`。
3. **Lane A**：落地后用生成类型替换 `frozen-contract.mjs` 的手写常量；破坏性改字段 BLOCKED。
4. **Lane E**：挂载 `mountPreviewHost`；不要把 BoardSpec 目录当页面白名单。
5. **不要**把 `html-sandbox.mjs` 扩成自由页运行时；不要为自由页去 `allow-scripts` 改旧测试。
6. 无本地 commit 授权：以本 worktree 未跟踪目录交接，不要猜提交。

## 进程与文件归属

- 本次 Chrome / 夹具 HTTP / 出口代理均随 probe 结束关闭；user-data-dir 已删。
- 现役 6677 PID 8758 未切换、未 reload。
- 未读 131GB DuckDB，未改 DSH 上游，未写 `manifest.json`，未 `pnpm add`，未公网发布。
