# Figma 可编辑稿同步清单

## 目标文件

- 文件：`伸美 AI 增长董事会 · Hackathon`
- URL：<https://www.figma.com/design/MMLOikxeuI904BNPw7Ebi2/伸美-AI-增长董事会-·-Hackathon?node-id=0-1>
- File key：`MMLOikxeuI904BNPw7Ebi2`

当前文件已经创建并命名，但 2026-09-05 的 Figma MCP 请求持续在 `https://chatgpt.com/backend-api/ps/mcp` 返回 transport error。因此不能把“空文件已创建”写成“可编辑设计稿已完成”。本清单是恢复后唯一同步入口。

## 运行时单一事实来源

视觉数值以 `frontend-vue3/src/theme.ts` 为准，Figma Variables 和 Styles 只做镜像，不另起一套色值。

| Token | Value | Figma 用法 |
|---|---|---|
| `color.primary` | `#805D9D` | Imperial Purple；主按钮、活动导航 |
| `color.secondary` | `#D3C3E8` | Soft Lilac；边界、次级文字 |
| `color.accent` | `#F2FFDC` | Signal Lime；决策信号、关键状态 |
| `color.background` | `#09050D` | Deep Plum；画布背景 |
| `radius.panel` | `18px` | 主玻璃面板 |
| `radius.action` | `12px` | 主操作按钮 |
| `blur.panel` | `26px` | Liquid Glass 背景模糊 |

## 页面与组件

创建一个 `1440px` 宽、纵向 Auto Layout 的桌面 Frame，并按下列顺序建立可复用组件：

1. `Header / Default`：魔法帽、`SHINE MAGE`、`伸美集团 · CRM 增长分析平台`、六项导航、当前用户。
2. `HeroMetric / Mission`：Mission ID、等待 CEO 审批、经营冲突标题、直播规模与货架质量证据、AI 建议。
3. `HeroMetric / ExpectedImpact`：`EXPECTED IMPACT`、`¥701`、可激活人群 `196`、预估增量客户 `+5.7`、假设提升 `+3.3`、90/10。
4. `ChannelTable / Default`：直播、货架、淘客的首付费用户、二单率、跨渠道率、180 天净价值；货架标记“粘性第一”。
5. `QuerySection / Default`：受控问数输入框、三枚建议问题胶囊、数据来源与受限语义层说明。
6. `ApprovalWorkflow / Waiting`：状态轨迹和帝王紫主按钮 `审批并生成 DRAFT_EXPORT (90% EXPERIMENT · 10% HOLDOUT)`。

组件必须使用 Auto Layout、Variables 和可复用 Styles；不扁平化为图片。所有经营数字、说明、按钮和风险边界必须完整保留。

## 同步与验收顺序

1. 先读取目标文件的页面、变量、样式与实例，确认没有可复用资产后再创建。
2. 创建 `Shine Mage` collection、颜色/圆角/模糊变量和文字/阴影样式。
3. 每次只创建一个逻辑模块，并记录所有返回的 node ID。
4. 每个模块创建后立即截图核验；发现偏差只修改对应 node，不重建整页。
5. 最后导入或重建当前本地页面快照，用实例替换重复结构。
6. 验收必须同时满足：文件非空、组件可编辑、Variables 可复用、首屏数据无缺失、桌面截图与本地页面一致。

## 不能误报的边界

- Figma 文件创建成功不等于设计同步完成。
- 本地浏览器截图不等于可编辑组件。
- Figma transport error 不影响本地 Vue 视觉实现、测试和演示，但它仍是提交材料中的独立未完成项。
