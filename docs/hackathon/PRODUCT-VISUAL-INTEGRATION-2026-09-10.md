# 原生主题与 Ant Design 接入

从 #115 的 `afb62b0` 创建独立 `competition-visual-readiness` 工作树。4325/18083 继续运行已交付代码；本树验证通过前不切换候选。目标仍是七阶段完整产品验收，本增量处理 DESIGN 的原生与业务品牌一致性，不用更改截图或强制关闭原生功能代替实现。

## 已核验的接缝

- 固定 DSH `d347e703` 提供 `theme.overrideTokens(source, {token: {light, dark}})` 和 `theme/change`，ui-layout 的 ThemePresenter 管理 DOM。通过官方服务叠加品牌令牌，卸载时只撤销自己的层；保留 Light/Dark/System 和字体设置，不散改上游。
- 当前运行页 `html.style.colorScheme=light`，业务 ThemeProvider 固定深色且未注入真实 ConfigProvider，形成外浅内深。新增的业务主题应跟随原生已解析模式，不能只把全局 CSS color-scheme 写成 dark。
- Ant Design 固定为 `5.29.3`，npm 发布记录的 gitHead 为 `14f397749dca177e5495dc9d1c2f7debfb639545`，React/React DOM peer >=16.9；复用当前固定 React 18.3.1 和对应类型。按[官方主题接口](https://5x.ant.design/docs/react/customize-theme-cn/)使用 ConfigProvider、默认/深色算法与集中 token，按[CSS 变量隔离规则](https://5x.ant.design/docs/react/css-variables-cn/)区分模式 key。
- 安装只发生在本树 build-tools，锁定版本并禁用生命周期脚本；固定上游、Node、TypeScript 和 React 版本不升级。`pnpm peers check` 的唯一问题是原有 openapi-typescript 7.13.0 声明 TS ^5.x，而工具链固定 TS 6.0.3；不把它误报为本次 React/AntD 冲突，仍由实际合同和类型检查核验。

## 实施与验收

1. 锁定 AntD 和同版本 React 依赖，扩充已有依赖装配与干净构建；运行时仍使用 DSH 提供的单一 React，不能把第二份 React 打进包。
2. 集中映射原生品牌 tokens，业务 ConfigProvider 跟随原生模式。深色沿 DESIGN；浅色用同一品牌的 Ink White/Deep Plum 对调背景与主文本，保留品牌紫与对比度，不覆盖用户设置或引入新品牌。
3. 将业务操作、表单、状态与选项接到实际 AntD 组件，保持受控数据流、权限、幂等、错误和焦点语义。主视图使用业务词语，技术标识放入可展开证据区域。
4. 验证 Settings 模式切换、刷新、弹层打开/关闭、键盘、390/1024/1440、长文本/空/加载/权限错误；原生会话、工具、模型和权限入口仍可达。继续补原生取消的浏览器全路径，不用 transport 单测替代。
5. 按实际改动跑 B0、依赖审计及相关行为回归，保留失败证据、包体积与前端基线；review 后再整合 Git、切换候选、记录 CI 和发布边界。用户本人 T15 与正式 T16 仍等待既有问题答复。

## 本增量已实现

本树已快进到 CI 修复基线 `e63df18`，以下为其上的视觉增量。原生与业务主题通过官方服务同步；真实 AntD ConfigProvider、Button、Radio、Checkbox、Input 和 TextArea 已接入。图表类型仍使用保留原有语义的原生 select。没有修改 DSH 源码，没有引入第二份 React 运行时。

严格类型检查保留 `skipLibCheck=false`。AntD/rc-picker 的两处发布声明通过绑定版本和摘要的 d.ts 补丁兼容固定 React 18，原因、实际实现及移除条件见 [补丁说明](../../dsh-plugins/analytics-workbench/build-tools/patches/README.md)。构建复用前核对依赖清单、锁和补丁，干净目录仍逐字节比较 JS。浏览器 bundle 使用 production/minify，源码映射保留。

依赖审计发现原 openapi-typescript 链的 js-yaml 4.3.1 高危公告，已限定 override 到 4.3.2；官方 registry 审计结果为 0。已有在线 `--prepare` 纳入该锁的审计，离线 `--check` 不联网。未新建 CI job。

## 浏览器实际结果

临时实例为 4328/18084，状态位于本树 `.context/visual-synth`；只使用合成源，没有配置或调用模型。合成 GSV 查询经正式 HTTP 计算得到 410/305，选择结果成板，TABLE 改 BAR 后保存，刷新重开仍为 BAR 和相同数值。同一页关闭后 footer 可重开；Tab/Shift+Tab 均留在 dialog。

原生 Settings 的 Light/Dark/System 均可见；初始 System 解析为浅色，分别手选 Dark、Light 并刷新后保持，业务区同步。没有模拟操作系统主题变化，不能据此声称 System 自动切换全路径通过。

已查看 1440/1024/390 截图。390 宽页面无横向溢出，dialog 可视宽与 scrollWidth 均为 342；拖动/缩放控件在该宽度隐藏。旧通用 input CSS 曾把 Radio 撑大，绝对定位 resize 曾与窄屏内容重叠；均已修复，失败图保留。

| 证据 | 层级 |
|---|---|
| [browser-check.json](evidence/visual-readiness-2026-09-10/browser-check.json) | HTTP 运行配置、合成板版本、主题、尺寸、焦点与浏览器构建摘要 |
| [light-board-1440.png](evidence/visual-readiness-2026-09-10/screenshots/light-board-1440.png) | 修复 Radio 前的失败图 |
| [dark-editor-390.png](evidence/visual-readiness-2026-09-10/screenshots/dark-editor-390.png) | 修复窄屏控件重叠前的失败图 |
| [dark-bar-390-fixed.png](evidence/visual-readiness-2026-09-10/screenshots/dark-bar-390-fixed.png) | 修复后窄屏 BAR |
| [light-bar-reopen-1440.png](evidence/visual-readiness-2026-09-10/screenshots/light-bar-reopen-1440.png) | 浅色刷新重开 BAR |
| [dark-settings-1440.png](evidence/visual-readiness-2026-09-10/screenshots/dark-settings-1440.png) | 原生深色设置 |
| [dark-board-1024.png](evidence/visual-readiness-2026-09-10/screenshots/dark-board-1024.png) | 1024 宽可读性检查；技术文案仍开放 |

临时实例已通过自有 supervisor / 经端口和 cwd 核验的 Python 停止；状态、失败记录和截图保留。4325/18083 用户候选与其他既有实例未切换。Logo 仅从本机已有 LFS 对象 checkout，摘要 `21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000`；未读取其他工作树的运行时品牌文件。

## 检查与开放项

编译后的看板/行动/overlay 回归 29 passed，包含真实 AntD 渲染、模式切换不卸载、失败重试不重复成板。最初 jsdom 缺少 SVGElement 造成测试失败，已补实际 jsdom 类型并在结束时恢复全局对象，未降低业务断言。日志仍有 React act 提示，不能写成零告警。

完整 B0 最终检查 PASS：477 Python passed（10 warnings），Node 各阶段为 21/225/56/67/56 passed，包含重复的干净构建阶段，不相加当作独立用例总数。严格 host/client 类型检查、全部既有合同检查及六个 JS 产物逐字节重建一致。pytest 结束时还报告 SQLite 连接未关闭的 finalization 警告；本增量没有修改对应后端，保留日志，不能声称零警告。

源文件与构建摘要、阶段结果、告警和审计见 [verification.json](evidence/visual-readiness-2026-09-10/verification.json)。默认 client 为 455651 bytes，gzip 为 137644 bytes；这不是页面性能或正式 T16 结论。复现使用 Node 24 和固定上游，运行 `B0_BUILD_UPSTREAM=/absolute/pinned/upstream node scripts/dsh-b0/pipeline.mjs --check --python /absolute/b0-python3.14`。依赖审计在 build-tools 运行 `corepack pnpm audit --prod --audit-level=high --registry=https://registry.npmjs.org`；本轮冻结锁的 offline install 和该审计均通过。

提交前按 gstack review checklist 核对主题订阅/卸载、表单受控状态、权限与持久化接缝、固定依赖及构建副作用，未发现本视觉增量新的阻断项；未进行第二模型审查。旧基线 `e63df18` 的 [CI 34410948184](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34410948184) 已成功；不能将它当作本视觉增量的远端 CI。

以下仍开放：原生权限/运行中撤权和浏览器 Stop 全路径；首次欢迎历史误报根因；业务文案与可展开证据整理；全部状态的 DESIGN 检查；旧 MCP 与完整诊断；业务默认值/UNKNOWN；用户本人 T15、正式 T16。控制台可见未接线的 B0 assets/dashboards/analyses 404，本轮未将其记录为比赛 API 失败，也未声称控制台无错误。整产品继续 PARTIAL。
