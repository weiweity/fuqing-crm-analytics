# DSH 基座与插件兼容：本地集成验收

日期：2026-09-09。基线 `main` / `origin/main` / HEAD 为 `f818fca245ee27828249c6283055f03b591df6c5`（#110）；版本仍 `0.7.0.0`。候选在 `codex/dsh-compat-integration`，未 commit/push/PR/merge，未部署或替换用户演示。

## 交接与范围

Claude `codex/dsh-base-compat`：17 项指纹全部匹配，显式导入 12 个源码/文档文件。Grok `codex/dsh-plugin-ui-compat`：40 项指纹全部匹配，显式导入 13 个源码/文档文件。没有导入 `.context`、运行状态、数据库、`.venv` 或 node_modules 实体。构建依赖只用本机已安装固定依赖的符号链接。

上游仍为 `d347e703908d0406b7a7ef80e3a0e594d86b2215`；锁文件与固定工具链经过校验。上游未改、未升级。并行交接文档保留原时点，本记录说明集成后变化。

## 修复

- 开发 supervisor 使用排他锁，停止与状态查询使用随机凭据保护的 loopback 控制端点；PID 只作诊断，不凭历史 PID 杀进程。异常退出保留非零退出码。启动超时、取消及过量日志回收自有 child；启动日志有界，ready 后持续排空管道但不保留无界日志。
- Web 只探测自己要绑定的端口，允许 kernel/bridge 先运行。CLI 缺参数直接拒绝；check 默认使用新临时 runtime。显式 runtime 用于重启保留状态。
- 原生开发入口 `--plugin on` 是 **业务 UI-only**：不启动未配置的业务 bridge，也不注入合成固定会话或替换 standard preset。业务计算仍在独立 B0 合成栈验证，未声称完整开发入口已连通真实业务。
- 完整开发入口补两条固定原品牌资产路由，修复 Logo 404；复用原素材的 SHA256 校验，通过上游 WebServer 注册/注销，不修改上游源码，不提供任意文件服务。
- 合成运行配置只接受端口组 4315、4325、4335；kernel、bridge、工具请求、gateway、RPC、Seatbelt 参数及两条故障注入入口一致。默认行为保持 4315–4319。Loader 测试默认独占 4326，不访问原演示 bridge。
- 插件按钮、弹层与字体采用 DSH 令牌；补 HTTP 弹层焦点循环及错误卡整行。DESIGN 已明确 DSH 不强套旧 Vue 主题，因此不重写品牌规范。
- CI 路径分类包含 `scripts/dsh-dev/`，统一 pipeline 加入开发入口单测与 runtime port 验证；依赖编译产物的生命周期测试移到构建之后，干净重建也执行。

## 实际验证层级

| 层级 | 本次结果 |
|---|---|
| 完整 B0 pipeline | 退出码 0：460 Python、225 源 Node、52 编译后、52 干净重建；合同、Ruff、类型与产物一致性通过 |
| 开发入口最终补修 | 16/16，通过超时/过量日志子进程退出、旧 PID 拒绝、端口冲突、固定资产路由与释放；pipeline 的较早 13 项记录保留，最终增量单测单列 |
| CI 路径分类 | 27/27，包含新开发入口必须选择 B0 pipeline |
| 原生开发浏览器 | plugin OFF 原生导航/Settings 可见；ON 品牌/驾驶舱入口出现、Settings 插件清单显示 Running；同 runtime 重启 OFF 后业务入口消失 |
| 原生开发 HTTP | 未认证 401；认证后 DSH boot 200；品牌修复后 PNG 200，3662 bytes；没有模型调用 |
| 合成原生业务闭环 | 4335–4339：首购查询→保存分析→加入驾驶舱→脱离会话重读通过；物理 worker 执行首购 JSON 金标准，模型为本地 stub |
| 响应式 | 390/768/1440 宽度无页面横向溢出，弹层宽度 342/720/1100；桌面按钮实测 36px；真实驾驶舱截图保留 |
| Settings 通用热启停 | 固定上游不提供该控件。`PluginInventorySettingsTab` 明确是 read-only inventory；展开详情不算启停。开关只在启动配置层验证 |
| 未运行 | 真实模型、完整原生工具逐项执行、真实业务 UAT、远端 CI、公网部署；本轮不能宣称“全部 DSH 功能兼容通过” |

合成 run：`run_72708b27e6f1490aa3b5839b008c79b3`。首购 N=30、成熟人数 9，保存至驾驶舱 v2。原生 UI 与业务 HTTP 使用真实执行路径，数值来自合成输入，不是模型生成。

## 运行与停止

在本集成 worktree，使用 Node 24 与显式 Python 3.14。上游覆盖指向主仓已构建 checkout，不复制运行环境。

```sh
export DSH_DEV_UPSTREAM=/absolute/pinned/upstream
node scripts/dsh-dev/cli.mjs check --plugin off
node scripts/dsh-dev/cli.mjs start --plugin on --fresh
# 另一个终端，同工作树：
node scripts/dsh-dev/probe.mjs
node scripts/dsh-dev/cli.mjs status
node scripts/dsh-dev/cli.mjs stop
```

`--extra-patch` 当前接收 JSON 内容的 patch 文件（扩展名可为 yml），不是任意 YAML 解析器。`--detach` 仅表示已派生子进程，必须再查 status；不把派生成功当启动成功。SIGKILL/机器断电可能留下 supervisor.lock；必须先核实运行归属，再人工处置锁，不依据 PID 自动清理。

合成栈命令：`B0_BUILD_UPSTREAM=/absolute/pinned/upstream node scripts/dsh-b0/serve.mjs --python /absolute/python3.14 --port-base 4335 --native-first-purchase`。随后在同 worktree 用 rpc bootstrap/prepare-ui，再启动 gateway（也传上游覆盖）。这是合成验收入口，不能代替完整原生产品入口。

## 审查及证据

使用 `open-code-review-delegate`：OCR 仅做 preview/rule，本 agent 审查实际差异与源码，没有调用外部模型。覆盖清单与最终结果在 `.context/dsh-compat-review/review.json`，候选指纹在同目录 `FILES.sha256`。

证据：`pipeline-final.log`、`dev-final.log`、`path-tests.log`、`base-off-settings.txt`、`base-on-plugins.txt`、`base-off-restored.txt`、`base-on-http.json`、`native-assets-sessionless.txt`、`native-cockpit.png`。品牌 404 的初始负证据保留；最终成功浏览器请求为 200。运行证据来自本地，未伪装成 CI。

本轮临时 dev/B0 实例验收后已停止，运行文件与失败证据保留。旧 8000/5173、4315–4319 继续运行，未切换插件产物。主工作区四个未跟踪文件保留；未删除分支或工作树。
