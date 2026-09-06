# 视觉收口验收 · 2026-09-05

## 当前结论（后续各节为分轮历史证据）

- 最新前端验证：23 文件、192 项单测通过，vue-tsc／Vite 构建与 `git diff --check` 通过；既有构建体积与 Node/Vue 警告未消除。
- 已使用现有本地账号完成登录、三类问数、审批、合成 CSV 下载与演示重置；页面恢复等待 CEO 审批。没有真实短信／CRM 触达。
- 已修复仓库根启动时 Tailwind 样式缺失、390px 移动网格内层裁切和导航弹层裁切。桌面及移动局部交互验证通过，不等于所有页面／设备的完整验收。
- 用户已批准江华审稿室原始 PNG 反白与 Figma 中文 Noto Sans SC 替代；本地已替换自绘标志。PNG 不冒充矢量，普惠体未捆绑。
- Figma 两版完整组件稿（1440px / 1800px）已写入并截图检查：各 111 个文本节点、17 个实例，关键字段无缺失、常规布局无溢出；334 个变量、24 个样式。详见 [当前设计交付](./FIGMA-SYNC.md)。
- 当前仍是本地未提交分支，没有 push、PR 或公网部署。归档真实数据库未使用。

## 本轮范围

分支 `codex/shine-mage-figma-refinement`，基于 `de2d785`。整理前端样式 SSOT、字体加载、交互视觉、契约测试和 Figma 组件交付；没有修改后端、数据、权限或审批行为。九个业务 Vue 文件的 script/template 与基线完全一致；BrandMark 的展示结构按批准替换。没有提交／推送或部署。下方各轮测试数字和未完成关口均是历史快照，最新现状以上方结论和 FIGMA-SYNC.md 为准。

## 已验证

| 检查 | 结果 | 证明范围 |
|---|---|---|
| Figma 当前会话身份与 metadata | 成功 | 连接和目标文件读取可用，不代表写入已完成 |
| Figma Plugin API 清点 | 空白页 `0:1`；无本地组件、变量、文字或效果样式 | 可编辑稿未完成 |
| 尺寸迁移 | 97 个 dimension tokens，10 个 Vue 文件 | 字号、间距、宽高、字距、位移和视口单位集中到主题 |
| 静态等价核验 | 10/10 文件通过 | 把新尺寸变量展开后，完整 Vue 源文件与迁移前逐字符一致；script/template 未改 |
| 令牌专项测试 | 2 文件，22 测试通过 | 色值、尺寸引用、变量存在性、媒体查询断点与应用到 root |
| 完整前端单测 | 21 文件，173 测试通过 | 当前前端测试覆盖的行为；不是完整交互验收 |
| `npm run build` | vue-tsc 与 Vite 构建通过 | 类型与打包；仍有现有大 chunk 提示 |
| `git diff --check` | 通过 | 无空白格式错误 |
| 本地启动 | 启动脚本复用 API `49602:8000`，恢复前端 `9432:5173` | 当时监听与脚本健康检查；PID 后续须重新验证 |

测试时存在 Node `--localstorage-file` 未提供有效路径警告，未导致测试失败。没有因此修改运行环境。

## 首轮未完成项（历史快照；已解决项以当前结论为准）

1. 官方 VI／Logo 素材尚未定位；现有 BrandMark 是代码 SVG，不能宣称官方原稿一致。
2. 前端 Outfit 已在下述字体补齐中完成实际加载；普惠体尚未捆绑。Figma 字体清单未包含要求的普惠体或现有中文系统回退字体，不能宣称所有设备均使用普惠体。
3. Figma 建库 Phase 0 范围确认已发给用户，未开始 Foundations 或组件写入。
4. 桌面／移动端视觉截图、字体落地、交互与各项业务指标完整性验收仍待后续执行。
5. 捕获 ID `6da37edf-8802-4c12-b4c0-201804bedf52` 仅已分配，未注入捕获脚本、未提交页面；不能当作已运行的捕获任务，不能重复提交同一 ID。

后续继续从 [Figma 同步清单](./FIGMA-SYNC.md) 的 Phase 0 确认关口开始；主题值唯一来源仍为 `frontend-vue3/src/theme.ts`。

## 字体补齐 · 同日续轮

- 同源提供未修改的 Outfit 可变字体，固定 Google Fonts 修订与 SHA-256，110884 字节；Git blob 校验与官方 API 返回值相同。来源与分发许可见字体资产 README。
- `main.ts` 导入 `fonts.css`，注册 100–900 字重及 `font-display: swap`；Outfit 的中文回退统一复用 body 字体栈。
- 新增字体二进制校验、入口导入、字体名称／字重／加载策略与许可测试；完整前端测试更新为 21 文件、174 项通过；类型检查和 Vite 构建通过，输出 `Outfit-Variable-vXxiUg8D.ttf`。
- Chrome 实际字体查询：`.brand-copy strong` 的 10 个 glyph 来自自定义 Outfit（可变字重 650）；`.illustration-copy h1` 的英文来自 Outfit（570），中文来自 PingFang SC Semibold。未以 computed font-family 代替实际字体证据。
- 页面现有登录信息校验失败；本轮没有绕过登录或重置账号，因此字体浏览器核验范围为登录页，不是完整董事会主屏。
- 前端在独立启动命令结束后退出，改为当前终端会话保持后可访问；会话 `50464`，前端 PID `24300`、API PID `49602`。这是临时演示会话，不是 launchd 或生产服务；后续先复查进程再决定是否启动。

## 材质、业务保留与聚焦动效 · 同日续轮

- 玻璃卡片统一改为 3% 白色半透层；预估毛利改为浅紫白渐变与浅紫微光。共享 `.glass-panel` 的六项材质属性由契约测试锁定为主题引用。
- 增加董事会保留性测试，覆盖设计示例 ¥701、196 人群、+5.7 客户、+3.3%、渠道三行与现有跨渠道列、五阶段状态、三条快捷问题、自由输入和审批失败不得导出。另一组 132／+3.9／¥480 数据验证指标未被示例常量替换。这是组件测试证据，不是实际后端或浏览器端到端验收。
- 问数框新增仅聚焦时运行的呼吸光效。周期、静态与峰值阴影统一来自 `theme.ts`；`prefers-reduced-motion: reduce` 下保留静态焦点光圈。契约测试覆盖动画绑定、关键帧和减少动态效果分支；尚未做浏览器动画观感验收。
- 当前重新执行 `npm run test:unit`：21 文件、184 项通过。`npm run build`（含 vue-tsc）及 `git diff --check` 通过；既有 Node localstorage 与大 chunk 警告仍在。
- 当前重新比较 `de2d785`：10/10 个修改的 Vue 文件去除 style 后完全一致，业务 script/template 均未改变。先前“展开尺寸后整文件一致”仅描述尺寸迁移阶段，不覆盖后续有意的材质与动画调整。
- 最新 Figma whoami 与目标页 metadata 均成功；目标页仍为空，写入和可编辑稿均未完成。没有将连接测试等同于设计完成。

### 当轮尚待完成的验收关口（历史快照）

1. Figma 建库范围确认及正式组件／页面写入。
2. 官方 Logo／VI 原稿定位与比例、安全区核验。
3. 使用有效登录会话完成董事会桌面／移动端视觉与完整操作验收；不绕过认证，不用组件测试冒充该项验收。

## 本地实机验收与启动目录修复 · 同日续轮

- 已按用户授权使用运行中 API 的现有配置登录。浏览器实际进入 `/growth-board`，验证 Mission AA9316F2、196／+5.7／¥701／+3.3%、三行渠道数据、五阶段与审批按钮存在；未审批或导出人群。
- 发现本地 dev 与构建不一致：启动脚本从仓库根运行 Vite，Tailwind 默认从进程目录发现配置／扫描 content，导致实际浏览器缺少 `.flex`、`.p-5` 等外壳样式。修复前 main padding 为 0、shell display 为 block、文档 scrollWidth 1852 > innerWidth 1837。
- `postcss.config.js` 显式解析同目录 Tailwind 配置的绝对路径；Tailwind content 改为相对配置目录扫描。这修复了两层目录依赖，不改变业务组件或旧页面筛选操作。
- 新增 `tailwind.cwd.test.ts`，分别从仓库根与前端目录执行真实 PostCSS 配置，验证外壳 utilities 存在且输出完全一致。没有用 CLI `--config` 参数掩盖配置发现问题。
- 仅重启已核验归属的前端进程，沿用 `start-stack.sh`，API PID 49602 保持不变。新前端 PID 63768，临时保持会话 79775。重启后浏览器 main padding 20px、shell display flex、scrollWidth 与 innerWidth 同为 1837，桌面横向溢出消失。
- 点击真实快捷问题“哪个渠道粘性最强？”得到 CHANNEL_QUALITY 诊断，回答包含货架二单率比直播高 6.5 个百分点及受控问题边界。
- 移动预检存在浏览器缩放干扰：请求 390px 视口时实际 innerWidth 487，不能据此宣称 390px 验收通过；已恢复视口，待按实际 CSS 像素完成移动验收。
- 控制台存在扩展脚本触发的 CSP unsafe-eval 报错，未放宽 CSP；不能宣称控制台零错误。
- Logo 来源现已定位为江华审稿室中的 PNG，详见 Figma 同步清单；五模块范围已确认。矢量格式差异、字体映射、Figma 建稿与完整视觉／操作验收仍未关闭。

## 精确移动视口、导航与执行闭环 · 同日续轮

- CDP 设置移动视口后实测 `innerWidth=390`。修复前 `.intelligence-grid` 外宽 342px，而 `1fr` 的隐式最小尺寸被渠道表撑到 774px，问数区也被裁切；文档无外层溢出不能证明内部可见。
- 响应式轨道改为 `minmax(0, 1fr)`，实测渠道与问数卡均为 342px、问数表单 292px。新增 CSS AST 契约测试，禁止回归到 auto min-content 的单列轨道。
- 导航弹层原先受 `.navbar-main { overflow: hidden }` 裁切：菜单范围内的 `elementFromPoint` 命中背后的董事会。修复后桌面命中“现状概览”菜单项；390px 下六个主导航换行完整展示，菜单 x=12、width=366，位于视口内且命中菜单内容。Escape 后菜单关闭。仅修改样式，未改菜单文字、路由或业务脚本。
- 浏览器实际问数：CHANNEL_QUALITY 返回货架较直播二单率高 6.5pp；LIFECYCLE_DISTRIBUTION 返回 464 位待补货客户；PRODUCT_ROLE 返回舒缓面膜更适合老客激活。移动高层点击曾受仿真坐标影响，后两项通过键盘 Enter 验证，不宣称真实触屏端到端验收完成。
- `/approve`、`/audience-export` 与草稿下载均 HTTP 200。生成 `draft-aa9316f2-8`，196 行合成用户、实验组 175／对照组 21；90/10 是分配规则，实际整数人数不是精确 90%／10%。未改分配算法。
- CSV 响应为 `text/csv`，表头 `synthetic_user_id,mission_id,experiment_arm`，实际数据行 196。响应 provenance 为 synthetic、contains_real_data=false、syn-commerce-1.0.0，与 AA9316F2 数据版本一致。不记录用户行明细或登录凭据。
- 已通过现有“重置演示”按钮恢复 AWAITING_APPROVAL，下载按钮变回审批按钮；生成的测试草稿状态已被重置，可重新审批生成。已清除设备视口覆盖，返回桌面演示。未删除真实数据或手动清理下载文件。
- 最新测试：22 文件、187 项通过，vue-tsc／Vite 构建和 `git diff --check` 通过。Figma 建库按技能要求停在素材／字体差异确认关口，没有用本地验收冒充可编辑稿完成。

## 展示字体一致性 · 同日续轮

- 原始要求逐项复核发现，收益数字虽已用 Outfit，英文模块标签和流程编号仍沿用等宽字体。8 个 Vue 文件的展示标签、序号及实验比例现改为 `--sm-font-display`；技术指标版本号、查询 intent 和 provenance 保留等宽表示，不改业务内容。
- 新增 CSS AST 契约测试，逐项锁定导航、收益、命题、渠道、问数、审批、页面与登录页的英文展示选择器。
- 浏览器 `CSS.getPlatformFontsForNode` 实测：EXPECTED IMPACT（15 glyphs）、CHANNEL ASSET TRUTH（19）、DISCOVERED（10）、¥701（4）、28.0%（5）均来自已加载的自定义 Outfit，可变字重正确生效。不是仅检查 CSS 字体声明。
- 复核 390px 视口：文档宽 390px、网格及两张卡均 342px，六个导航入口均处于视口范围。设备覆盖已清除。
- 最新完整前端测试 22 文件／188 项通过，类型检查、构建、diff 格式检查通过。对基线 `de2d785` 再次验证 10/10 个 Vue 的业务 script/template 原样保留。
- 再读 Figma metadata：目标 `0:1` 仍为空白页。未收到 PNG 反白及 Figma 中文字体替代的确认，未进行替代或写稿；不能标记完整目标完成。

## 核心交付文件索引

以下是工作树中的实际 Vue 文件，不另抄一份可能过期的组件代码。将其作为当前实现使用，不代表官方 Logo／Figma 验收已完成。

| 要求模块 | 实际源码（相对仓库根） |
|---|---|
| 主题 SSOT | `frontend-vue3/src/theme.ts` |
| Header | `frontend-vue3/src/components/NavBar.vue` + `BrandMark.vue` |
| HeroMetric | `frontend-vue3/src/features/mission/components/MissionHero.vue` + `ImpactForecast.vue` |
| ChannelTable | `frontend-vue3/src/features/mission/components/ChannelPortfolio.vue` |
| QuerySection | `frontend-vue3/src/features/mission/components/BusinessQuery.vue` |
| ApprovalWorkflow | `frontend-vue3/src/features/mission/components/MissionActionRail.vue` |
| 页面组装 | `frontend-vue3/src/views/GrowthBoardView.vue` |
