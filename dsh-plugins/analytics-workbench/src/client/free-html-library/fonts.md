# 自由 HTML 宿主字体（T18）

本文件记录声明栈、许可与加载事实。声明不等于已加载。

## 已生效声明（competition-shell/tokens.ts）

| 角色 | 声明栈 | 加载事实 |
|---|---|---|
| 中文正文 | `Noto Sans SC` → PingFang SC → Hiragino Sans GB → Microsoft YaHei → sans-serif | **未捆绑 Noto 文件**。本机 macOS 无 `Noto Sans SC`；中文会回退到 PingFang SC。 |
| 英文/数字标题 | `Outfit` → Noto Sans SC → PingFang SC → Microsoft YaHei | Outfit 已有仓库内可变字体：`/b0/brand/outfit.ttf`，SHA-256 `fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade`，SIL OFL 1.1。 |
| 代码 | SFMono-Regular → Menlo → Monaco → Consolas | 系统等宽，未另捆绑。 |
| 候选中文 | Alibaba PuHuiTi 3.0 | **不是已生效默认。** 未完成授权、文件校验、加载性能和分发范围核验前不得提升优先级。官方入口：https://www.alibabafonts.com/ 。禁止从不明站点拉取。 |

## Noto Sans SC 接入需求（未执行下载）

Lane E 不自动下载、不安装浮动依赖、不把编辑器字体当作产品资产。

要让声明变成可加载事实，需要协调者授权后放入固定修订文件：

1. 来源：Google Fonts `ofl/notosanssc`（SIL Open Font License 1.1），建议钉 Git 修订并记录上游文件名。
2. 目标路径：由 shine-brand 同源提供 `/b0/brand/noto-sans-sc.woff2` 与 `/b0/brand/noto-sans-sc-ofl.txt`。
3. 记录：字节数、SHA-256、字重范围、`font-display: swap`。`BRAND_DIGESTS.notoSansSc` 目前为 `null`。
4. 有文件后再在 `competition-shell/css.ts` 增加 `@font-face`。现在故意不写 `src:url('/b0/brand/noto-sans-sc.woff2')`，避免 404 被当成已加载。
5. 许可范围：Noto 是 OFL，可随产品分发；仍须保留版权声明。这不等于已完成商用分发核验手续的书面归档。

未捆绑时：生成不阻断；验收记录实际命中字体与回退；不能用字体栈字符串宣称品牌一致性已通过。

旧 Vue 界面继续使用 DESIGN.md 中的普惠体回退栈，本 lane 不全仓替换。
