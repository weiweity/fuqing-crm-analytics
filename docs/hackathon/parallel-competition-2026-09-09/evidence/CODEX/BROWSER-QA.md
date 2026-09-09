# 合并前独立浏览器 QA · 2026-09-09

范围：PR #112 synthetic 认可成板，以及原生 DSH 入口可访问性。浏览器为 GStack Chromium，独立 DSH 4329 / API 18083；固定上游 d347e703908d0406b7a7ef80e3a0e594d86b2215、Node 24.19.0。基线提交 3db12f7；本次源码修复绑定 BROWSER-QA-SOURCES.json，最终 Git 提交包含本报告。

## 实际发现与修复

1. 高：首屏整屏深色、按钮不可点击。ThemeProvider 在原生 shell.overlay 中即使 dialog 关闭也生成整屏有背景的盒子。仅在 overlay 容器使用 display: contents，保留子业务视图主题与原生 dialog。baseline.png 保留失败，native-home.png 为修复结果。
2. 独立复现限制：合成 HTTP CORS 只接受 14327。新增 COMPETITION_SYNTH_WEB_ORIGIN，默认保持 14327，只接受隔离 loopback DSH 端口，拒绝通配符、公网、4327/8000/5173。HTTP 测试文件 10 passed，包括来源边界。
3. 干净安装缺少 fs-ext 原生扩展。固定依赖不变，在独立上游目录用现有 Node 头文件和 libuv 编译，无复制其它工作树 node_modules：
   `PATH=/Users/hutou/homebrew/opt/node@24/bin:$PATH CPPFLAGS=-I/Users/hutou/homebrew/opt/libuv/include npm_config_nodedir=/Users/hutou/homebrew/opt/node@24 npm rebuild fs-ext --offline`

## 浏览器验证结果

- 未认证 401，启动兑换 303，认证后 200；未填写模型密钥，选择 Configure later。
- 1440 首屏正常可见，标题为伸美 AI 增长董事会，问候语可读，footer 实际点击打开驾驶舱。
- 选择 COMPLETE 合成结果。暂停自有 18083 后点击成板：出现 FAILED，dialog 保持打开（retry-failure.png）。恢复同一状态目录的 API，再次点击成功成板（board-success.png）。
- 同页返回聊天，再次点击 footer → 认可成板 → 编辑看板，显示「8月GSV诊断板」、TABLE、COMPLETE、行数 1（board-reopened.png）。没有重新加载页面来恢复入口。
- 浏览器 GET /boards 返回 items 长度 1，board_3214bbbd13f32407b2644cf427242b5d，version=1、persisted=true。失败重试未重复成板。
- Settings 的 General / Models / Plugins / Agent presets 入口显示；General 面板实际可达。Standard mode 菜单展开包含四种原生模式；New session 按钮可点击并返回输入首屏，未发送模型请求。
- 1024 与 390 视口实际检查。390 侧栏收起后首屏可读（native-390-settled.png），业务 dialog 宽342、scrollWidth342，body宽390，没有横向溢出（board-390.png）。截图需等待侧栏动画稳定；即时截图会保留中间帧，不能用作稳定态证据。
- Logo 请求成功且截图可见；主线请求指向18083。原生 /b0/assets 404 仍存在，UI 明确区分未接线的 B0 与比赛资产；故控制台并非零错误。断网负测另有预期 ERR_CONNECTION_REFUSED。

本轮合并范围 QA 通过；不是整产品验收通过。原生全套会话/工具/权限行为未完整执行，T17 仍 PARTIAL；Ant Design 接入、完整品牌覆盖、真实数据和 A3 MCP 仍按原清单保留。T13/T15/T16 未运行。

健康分不覆盖未测项：已测功能、布局回归已关闭；控制台因既存 B0 404 保留问题。未执行性能与完整可访问性审计，不计算容易误导的全产品综合分。

## 复现配置

在固定工具链已准备的独立工作树中：

```bash
COMPETITION_HTTP_BASE=http://127.0.0.1:18083 \
COMPETITION_HTTP_TOKEN=b0-competition-synth-token-32chars \
node dsh-plugins/analytics-workbench/build.mjs

COMPETITION_SYNTH_PORT=18083 \
COMPETITION_SYNTH_WEB_ORIGIN=http://127.0.0.1:4329 \
COMPETITION_SYNTH_STATE=.context/qa-browser-state \
PYTHON_DOTENV_DISABLED=1 .context/reproduce-backend/bin/python scripts/competition-synth-http.py

COMPETITION_HTTP_BASE=http://127.0.0.1:18083 \
COMPETITION_HTTP_TOKEN=b0-competition-synth-token-32chars \
node scripts/dsh-dev/cli.mjs start --plugin on --web-port 4329 --fresh --detach
node scripts/dsh-dev/probe.mjs
```

浏览器使用本实例私有启动地址兑换认证，不记录启动 token。按上述用户操作验证；不得仅用 HTTP 200 或 DOM 存在替代点击和截图。构建时所用 token 是代码内公开的 synthetic 默认值，不能用于真实服务。验收后已停止本轮4329/18083并恢复不注入连接参数的默认插件构建；没有停止4327/8000/5173或Grok的14327/18082。
