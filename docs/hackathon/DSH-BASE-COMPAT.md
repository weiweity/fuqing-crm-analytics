# DSH 完整基座兼容（本地开发环境）

> 下文保留并行候选交接时点；集成后的修复与实际验收以 [Codex 集成记录](./DSH-COMPAT-INTEGRATION-2026-09-09.md) 为准。

日期：2026-09-09。状态：`LOCAL_CANDIDATE / PARTIAL`。

本文件是 `codex/dsh-base-compat` 轨交付说明，不是完整产品验收、不是真实模型通过、不是公网或业务 UAT。入口：[cli.mjs](../../scripts/dsh-dev/cli.mjs)。固定上游：`deepseek-ai/deepseek-harness@d347e703908d0406b7a7ef80e3a0e594d86b2215`。

结论：B0 `scripts/dsh-b0/serve.mjs` 是合成验证笼，不是产品基座。完整基座 = 固定版本原生 DSH web profile（`dsh-base` + `dsh-web-app`），业务插件通过 `--patch` 可选插入。本轨未把「源码未改 / 插件能加载 / 单测通过」写成完整兼容。

## 1. 范围与非范围

做了：

- 从核实的 `main` `f818fca`（#110）建独立 worktree / 分支 `codex/dsh-base-compat`，未改主工作区。
- 按上游源码建立原生功能矩阵，每项给出入口、依赖、环境限制、B0 定制影响和四档判定。
- 区分 B0 演示隔离与产品安全边界；没有通过删除权限控制假装功能完整。
- 新增 `scripts/dsh-dev/`：固定 SHA、插件 on/off、端口 4325–4329、只管理本轨进程。
- 本地验证：pin、dump-config、启动、未认证 401、认证后 DSH boot、停止、同目录重启。

没做 / 未宣称：

- 不 commit / push / PR / merge。
- 不停止 8000 / 5173 / 4315–4319，不覆盖 B0 `current.json` 或 `runtime-5GAr1z`。
- 不调用真实模型、不处理真实数据、不复制 `node_modules` 或上游树。
- 不改 `dsh-plugins/analytics-workbench` 业务实现，不改 `scripts/dsh-b0/`，不改上游。
- 不把 B0 Seatbelt、固定会话、网关白名单、mock LLM 当成产品默认。

判定用语只使用：**通过 / 失败 / 依赖外部条件未验 / 仅源码确认**。

## 2. 基线

| 项 | 值 |
|---|---|
| 仓库 `main` / `origin/main` / 本轨 HEAD | `f818fca`（#110） |
| 上游 SHA | `d347e703908d0406b7a7ef80e3a0e594d86b2215` |
| 上游 lock SHA-256 | `2c903ab870f821ee2db62fa9417d11b1c2b9c65fbeec30e851ddc53c4cc8c383` |
| Node | 24.19.0 |
| pnpm | 11.7.0（toolchain.json） |
| Python | 3.14.4（本轨启动不需要；Grok 接 kernel 时再用） |
| 上游复用路径 | 主工作区 `.context/dsh-b0/upstream`（worktree 无副本，禁止复制） |
| 本轨端口 | 4325 kernel 预留 / 4326 bridge 预留 / **4327 web** / 4328 gateway 预留 / 4329 mock 预留 |
| 外埠（禁止占用或停止） | 8000、5173、4315–4319 |
| 本轨状态目录 | worktree `.context/dsh-dev/`（gitignore） |

预期基线 `f818fca` 与实际一致，未回退。

## 3. 原生功能矩阵

依据固定上游 `packages/bundle/base/cordis.patch.yml`、`packages/bundle/web-app/cordis.patch.yml`、`apps/cli`。Web 把大量工具从 Host 平面挪到 shipped preset（`standard` / `ptc` / `minimal` / `cordis`），这是产品设计，不是 B0 限制。

| id | 能力 | 入口 | 依赖 | 当前环境 | B0 定制影响 | 验证方式 | 判定 |
|---|---|---|---|---|---|---|---|
| cli-web | Web 启动器 | `dsh web`；`--host --port --no-open`；拒绝 `0.0.0.0` | 已构建 frontend dist、`$DSH_HOME`、loopback | 本轨可跑 | B0 改到 4317 + Seatbelt + mock | `cli.mjs start` → 4327 监听 | **通过** |
| launch-auth | 启动 token → HttpOnly cookie | `dsh-web-app` 打印带 token 的 URL | 浏览器或 HTTP 跟随 303 | 本轨可跑 | B0 另做 4318 `?b0=` 网关 | 无 cookie `GET /` = 401；兑换后 200 | **通过** |
| sessions-create | 创建/采用会话 | `session-controller` `create` | 可写 sessions、agent-presets | 未做浏览器点击 | B0 不补丁 create；UI 自动选固定会话 | RPC `session.create` | **仅源码确认** |
| sessions-list-open | 列表/打开/follow | `session.list/page/follow` | JSONL persistence | dump 有 controller | B0 网关只放行固定 sessionId | dump-config 含 `session-controller` | **仅源码确认** |
| sessions-archive | 归档/重命名/fork | `workspace.archiveSession`；无 `session.delete` | workspace storage | 未点 UI | B0 未补丁这些 remote | 源码 + dump | **仅源码确认** |
| conversation | prompt / cancel / follow | session-controller + ui-conversation | **LLM** | 无真实密钥、无 mock | B0 把 `llm-deepseek` 指到 :4319 mock | 需模型 | **依赖外部条件未验** |
| agent-presets | shipped preset | web-app `default: standard`；四套 shipped | `$DSH_HOME/.agent-presets` 可选 | dump：`default: standard` | B0：`analytics-b0` + `includeShippedRoot/UserRoot=false` | dump-config | **通过**（配置层） |
| tools-bash-fs | bash/read/write/edit/grep/glob | Host 行 web 侧 disabled；**standard preset 再挂** | `DSH_PERMISSION_MODE`、cwd | 无会话点击 | B0 换掉 shipped preset，工具随 analytics-b0 | 标准会话工具目录 | **仅源码确认** |
| tools-web-search | `web_search` | `web-search-deepseek` `DEEPSEEK_API_KEY` | 网络 + 密钥 | 启动时剥离密钥 | B0 `disabled: true` | 有密钥后工具调用 | **依赖外部条件未验** |
| tools-web-fetch | `web_fetch` | `web-fetch-http` | 公网 HTTP(S) | 未出站验证 | B0 `disabled: true` | 公网 URL；非公网应拒 | **依赖外部条件未验** |
| tools-skill | Skill 目录 | `skill-filesystem` + `tool-skill` | 项目 `.dsh/skills` 等 | dump 有行 | B0 禁用 Host skill-filesystem，改用打包 skill | dump + 源码 | **仅源码确认** |
| settings | locale/theme/font/chat | `$DSH_HOME/settings.yaml`；Models 页写密钥 | 运行中的 web | dump 有 `settings` / `credentials` | B0 网关 `writable:false` 且命名空间裁剪 | dump-config | **仅源码确认** |
| sidebar-brand | 官方品牌槽 | `sidebar.brand.mark/name` | web roster | 未截图 | B0 插件 `priority:-10` 换成「伸美 · B0」 | 浏览器 | **仅源码确认** |
| directory-picker | 工作区/目录选择 | `host-directory-picker-auto` | 本机对话框或 browse | dump 行存在且未 disabled | B0 禁用该行 + `nativeOpen:false` | dump-config | **通过**（配置层） |
| plugin-loading | `--patch` file URL / `dsh plugin` | Loader + `plugin-inventory` | 已构建 `lib/index.js` | `--plugin on` dump 含 `analytics-workbench-ui` | B0 额外 disable inventory-deepseek | dump-config plugin on/off | **通过**（配置层） |
| telemetry | OTLP，默认 FEEDBACK_ONLY | `session-telemetry-otel` | 网络；`DSH_TELEMETRY_DISABLED` 退出 | 本轨设 `DSH_TELEMETRY_DISABLED=1`（进程隔离，不是删插件） | B0 直接 disable 该行 | 源码 | **仅源码确认** |
| session-title-llm | 首句标题 | `session-title-llm` | LLM | dump 有完整 config | B0 disable，只留 fallback | dump-config | **通过**（配置层） |
| compaction | `/compact` + pruner | Host disabled；preset 再挂 | LLM + standard 类 preset | 无长会话 | B0 视 analytics-b0 是否再挂 | 源码 | **仅源码确认** |
| onboarding | Models 欢迎/密钥 | ui-onboarding + credentials | 可选真实密钥 | 未点 Models 页 | B0 mock 密钥绕开官方 onboarding | 源码 | **仅源码确认** |
| model-catalog | 模型目录/thinking | `llm-deepseek`；默认 `deepseek-v4-flash` | `DEEPSEEK_API_KEY` 或 settings | 无密钥、未改 baseURL | B0 mock + thinking off + 禁 `llm-pi-ai` | dump 无 mock baseURL | **依赖外部条件未验** |
| native-vs-web | 仅 cli+web，无桌面应用 | profiles: web/headless/sdk/sdk-minimal/acp | 启动器 | 本轨只验 web | B0 是 web 上的 `--patch` | `ls apps` = cli+web | **仅源码确认** |
| hmr | client-hmr | web 始终挂载，无 `dev:web` 则空转 | 源码 watcher | 未跑 `pnpm run dev:web` | B0 disable `client-hmr` | dump 有 client-hmr | **仅源码确认** |
| mock-vs-real | 官方 mock vs 真实 API | 真实：无内联 key；mock：`packages/test-support/llm-mock-server` | 密钥或 mock 进程 | 本轨**不**起 mock | B0 把 mock 当成运行路径 | dump 无 4319/B0_MOCK | **通过**（配置层） |

上游缺口（不是本轨能补的上游补丁）：

- 没有桌面应用；没有 `session.delete`（只有 archive）。
- 全文会话搜索默认 `openAt: never`。
- `web-search-exa` / `perplexity` 存在但未进 `dsh-base`。
- 生产 CLI 没有 `--plugin`；`pluginInventory` 只读；本包装不上 `dsh.bundle`。
- `extraOverlayPath` / `extraInstallAnchors` 只存在于 e2e scaffold。

## 4. B0 演示限制（不要抄进产品基座）

来源：`scripts/dsh-b0/serve.mjs`、`gateway-policy.mjs`、`sandbox.sb`。

### 4.1 测试隔离（完整基座不应复制）

- 硬编码端口 4315–4319、`mkdtemp runtime-*`、合成 workspace。
- 官方 mock LLM + `B0_MOCK_KEY` + 有限 wire script。
- 固定会话 `session-b0-synthetic-primary`（及 query 双会话）。
- 禁用 11 个 Host 行：`session-title-llm`、`llm-pi-ai`、`web-search-deepseek`、`web-fetch-http`、`session-telemetry-otel`、`session-log-deepseek`、`plugin-package-inventory-deepseek`、`agent-instructions`、`skill-filesystem`、`client-hmr`、`directory-picker`。
- `agent-presets` 整段替换为 `analytics-b0`，关掉 shipped/user root。
- `session-controller.nativeOpen: false`。
- macOS Seatbelt `sandbox.sb`（deny-default，只放行 B0 端口）。这是演示隔离，不是 DSH 产品沙箱。
- 合成 fixture / 驾驶舱 finite mock / `?b0=` 一次性口令。
- 活体 `current.json` → `runtime-5GAr1z`。**禁止复制或停止那些 PID。**

### 4.2 产品安全边界（完整基座必须保留）

- 开发环境**不是**公开免登录：原生 DSH 无 cookie 访问 `/` 为 **401**，必须走启动 token 兑换。
- 只绑 `127.0.0.1`；拒绝 `0.0.0.0`。
- 不把内核 Bearer、启动 token 写进交接文档或截图。
- 不把用户 HOME 里的 API 密钥带进进程；本轨启动剥离 `DEEPSEEK_API_KEY` 等。
- 不删除 DSH 自身的 permission / approval / sandbox-policy（`workspace-write` + `ask`）。
- 不通过放开网关白名单或关掉 cookie 来「补全功能」。

`agent-instructions` 在**原生 web-app** 里本来就会 Host disabled（改挂 preset）。B0 再 disable 一次是重复隔离。本轨 overlay **不会**再 disable 这 11 行。

## 5. 开发入口

```bash
# 复用已安装的固定上游，不要复制
export DSH_DEV_UPSTREAM=/ABS/fuqing-crm-analytics/.context/dsh-b0/upstream

node scripts/dsh-dev/cli.mjs check --plugin off
node scripts/dsh-dev/cli.mjs start --plugin off --runtime /ABS/.context/dsh-dev/runtime-live
node scripts/dsh-dev/cli.mjs status
node scripts/dsh-dev/probe.mjs          # 不打印 token
node scripts/dsh-dev/cli.mjs stop
```

可选插件（不改插件业务代码；需要已构建的 `lib/index.js`）：

```bash
node scripts/dsh-dev/cli.mjs check --plugin on \
  --plugin-path /ABS/dsh-plugins/analytics-workbench
```

`--plugin on` 只 `insert` `file:///…/lib/index.js`，**不** disable 原生行、**不**改 `llm-deepseek`、**不**替换 preset roster。工具/skills 不要挂在 root Loader；见第 6 节。

Seatbelt：本轨**不**使用 B0 `sandbox.sb`。产品权限走 DSH `sandbox-policy`。若 Codex 认为 darwin 仍要 OS 级 Seatbelt，应新写映射到 4325–4329 的 profile，不要改 `scripts/dsh-b0/sandbox.sb`。

## 6. 给 Grok 的接缝

| 参数 | 约定 |
|---|---|
| 上游 | `--upstream` 或 `DSH_DEV_UPSTREAM`，SHA 必须是 `d347e7…`；只读，禁止改/升 |
| 运行目录 | worktree `.context/dsh-dev/runtime-*` 或 `--runtime`；**不要**抄 `.context/dsh-b0/runtime-*` |
| Web | `127.0.0.1:4327` |
| 预留 | 4325 kernel / 4326 bridge / 4328 gateway / 4329 mock。本轨默认**不起**这四个 |
| 插件 UI | `--plugin on --plugin-path /ABS/.../analytics-workbench`（该目录要有 `lib/index.js`） |
| 插件工具 | 不要 patch `agent-presets` 整段 config。放到 `$DSH_HOME/.agent-presets/<id>/agent.cordis.yml`，保留 `default: standard` |
| 额外 overlay | `--extra-patch /ABS/file.yml`（必须仍通过 `assertNoB0Disables`） |
| 真实模型 | 保留 Models / `llm-deepseek` 配置入口；本轨标记 **NOT RUN** |
| Kernel | 若要接 FastAPI，Grok 自己占用 4325，且不得使用 4315 或停别人 |

上游缺少的生产级 `--plugin` 开关：用本轨 supervisor 模拟，**不要改上游**。file URL Host 行已是固定 SHA 支持的扩展点（`packages/client/modules` 对 `file:` / 绝对路径走 `locatePkgJson`）。

## 7. 本轨实测（2026-09-09）

| 步骤 | 结果 |
|---|---|
| `node --test scripts/dsh-dev/*.test.mjs` | 10 passed |
| `cli.mjs check --plugin off` | dump 含 `default: standard`、`directory-picker`、`session-title-llm`；无 mock/4319 |
| `cli.mjs check --plugin on` | dump 另含 `analytics-workbench-ui`；仍 `default: standard` |
| `start --plugin off` | `127.0.0.1:4327` 监听；8000/5173/4315/4317 仍在 |
| `probe.mjs` | 未认证 401；token 兑换 303+cookie；认证后 200 + `__DSH_BOOT__`；非 Vue / 非 B0 |
| `stop` | 4327 释放；外埠仍在 |
| 同 `--runtime` 再 start | `dsh-dev-restart-marker` 仍在；probe 再次 401/303/200 |

未运行：真实模型对话、浏览器里新建会话/改设置/选工作区、插件 UI 插槽像素验收、kernel/gateway、付费搜索、公网。

## 8. 文件

新增：

- `scripts/dsh-dev/`（cli、pin、ports、overlay、serve、paths、constants、launch-url、probe 及测试）
- `docs/hackathon/DSH-BASE-COMPAT.md`（本文件）

交接（本地、gitignore）：`.context/dsh-compat-handoff/`。

不改：`AGENTS.md`、`DESIGN.md`、`VERSION`、`CHANGELOG.md`、`STATUS.md`、`docs/hackathon/README.md`、`scripts/dsh-b0/**`、插件业务实现、固定上游。
