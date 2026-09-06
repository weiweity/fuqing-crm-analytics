# Figma 可编辑稿同步清单

## 当前交付 · 2026-09-05

- [1440px 董事会组件稿](https://www.figma.com/design/MMLOikxeuI904BNPw7Ebi2?node-id=50-2)
- [1800px 宽屏组件稿](https://www.figma.com/design/MMLOikxeuI904BNPw7Ebi2?node-id=43-2)
- [Foundations](https://www.figma.com/design/MMLOikxeuI904BNPw7Ebi2?node-id=21-10)
- 分支：`codex/shine-mage-figma-refinement`；基线：`de2d785`。
- 本轮完成本地视觉实现与可编辑设计交付，没有 commit、push、PR 或公网部署。

两版页面均由组件实例组合，非整页图片：各 216 个节点、111 个文本节点、17 个实例。递归检查确认经营指标、跨渠道率、三条问题、五阶段状态和 90/10 参数无缺失；常规布局无越界。字体与玻璃渲染存在浏览器/Figma 差异，不声称像素级完全一致。

![1440px 组件稿](./assets/shine-mage-board-1440-20260905.png)

## 变量与样式

`frontend-vue3/src/theme.ts` 是唯一运行时视觉来源。Figma 使用两层镜像，不另立业务口径。

| 资产 | 实际数量 | 说明 |
|---|---:|---|
| Primitives | 167 | 37 COLOR、86 FLOAT、44 STRING |
| Semantic Tokens | 167 | 逐项 alias 到 Primitives；CSS code syntax |
| Text Styles | 10 | Noto Sans SC 与 Outfit |
| Paint Styles | 6 | 背景、主/次渐变、指标、回答、Chip |
| Effect Styles | 8 | 玻璃、焦点、按钮、导航、信号、指标 |
| 原子组件集 | 4 | BrandMark、NavItem、PromptChip、ActionButton |
| 业务主组件 | 6 + 4 | 六个 Vue 模块主组件，另有四个 1440px 尺寸主组件 |

变量使用明确 scope，无 ALL_SCOPES；334 个变量的 alias 与 Web code syntax 已读取核验。相对布局、CSS 表达式保留 STRING 来源，不能冒充可直接绑定的几何 FLOAT。编辑器画布底色不支持变量绑定，仅由主题值派生；设计节点继续使用变量/样式。CSS 饱和度、连续字重和渲染引擎差异不等于 Figma 原生等价能力。

## 五模块与代码映射

| 需求模块 | Vue 实现 | Figma 主组件 |
|---|---|---|
| Header | `components/NavBar.vue` + `BrandMark.vue` | `39:5` + `32:7` |
| HeroMetric | `features/mission/components/MissionHero.vue` + `ImpactForecast.vue` | `39:25` + `39:54` |
| ChannelTable | `features/mission/components/ChannelPortfolio.vue` | `41:5` |
| QuerySection | `features/mission/components/BusinessQuery.vue` | `41:66` |
| ApprovalWorkflow | `features/mission/components/MissionActionRail.vue` | `42:18` |

每类组件有独立页面、用法/来源说明和变量绑定；原子组件标签具有可编辑文字属性。组件状态只描述视觉，不执行后端业务。1440px 的几何差异落在专用主组件，避免依赖不稳定的实例内部尺寸覆盖。此表是文档映射，不是已发布的原生 Code Connect 注册。

## 已批准的素材与字体差异

用户明确回复“允许，继续目标”，批准先用原图反白与 Figma 中文替代字体。

- Logo 来自[江华审稿室 3:4](https://www.figma.com/design/LLNttmGDtQWM7oRYzdFDhT?node-id=3-4)，源文件未改动。
- 原图 249×45 PNG、3662 字节，图像 hash `0b8cd2ee21956ff364ce8765b675f452947e9366`。
- SHA-256：`21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000`。本地资产与 Figma 原图逐字节一致。
- Web 用 CSS `brightness(0) invert(1)`；Figma 用原图 alpha mask。仍是 PNG，不是矢量。
- Web 普通宽 177px、compact 宽 140px，按 249:45 比例。8px 留白是当前实现值，不宣称官方 VI 安全区。
- 桌面副标题位于 Logo 右侧，字号 11px、间距 12px；720px 及以下仍按现有规则隐藏副标题。Web 与 Figma 已同步并复核。
- Figma 中文用 Noto Sans SC；英文/指标用 Outfit。Web Outfit 已同源捆绑，中文继续现有系统回退栈；未捆绑普惠体 3.0。
- 本机浏览器实测 PNG 正常加载、反白生效，177px 宽对应约 31.98px 高。

## 捕获与清理

旧一次性链接过期；新链接成功捕获合成数据董事会，节点曾为 `31:2`，仅用于布局对照。正式组件稿完成后已移除临时捕获节点，本地对照截图留存。

临时捕获脚本已移出项目，`index.html` 与 `vite.config.ts` 恢复原状，开发页 CSP 不留 Figma 放行项。原始审稿室、真实数据库、登录权限与审批机制均未改动。

## 本地验收与边界

- 23 个测试文件、192 项单元测试通过；vue-tsc、Vite build 与 diff whitespace 检查通过。
- 390px CSS 视口复核：documentWidth=390，五个面板均 342px，六项导航和审批入口完整；渠道表在 288px 容器中内部滚动 720px，不把整页撑宽。移动仿真只作为布局证据，不冒充真实触屏 E2E。
- 对照 `de2d785`：九个业务 Vue 文件的 script/template 均未改变；BrandMark 仅按批准替换品牌资产与展示结构。
- 此前本地登录、三种问数、审批、196 行合成人群 CSV 下载及重置已实际验证；没有短信/CRM 触达。
- 真实约 131G DuckDB 未使用；公网部署、提交/推送、PR 和原生组件库发布均不在本轮操作中。
- 构建大 chunk、既有 Node/Vue 测试警告仍存在，不宣称全仓无警告或生产验收完成。

## 历史关口

机器可读资产 ID、样式、页面与验收数量见 [FIGMA-ASSETS-2026-09-05.json](./FIGMA-ASSETS-2026-09-05.json)。

初始发现时文件为空，随后确认五模块范围、江华 PNG 来源和字体替代。早期“待素材确认/未写入”是历史快照，现状以本页顶部和同目录视觉验收记录为准。
