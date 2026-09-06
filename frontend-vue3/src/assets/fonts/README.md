# 本地字体资产

## Outfit Variable

- 文件：`Outfit-Variable.ttf`（上游文件重命名；字体二进制未修改）
- 作者仓库：https://github.com/Outfitio/Outfit-Fonts
- 分发来源：https://github.com/google/fonts/tree/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl/outfit
- 原文件名：`Outfit[wght].ttf`
- 固定修订：`8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5`
- 字节数：110884
- SHA-256：`fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade`
- 许可证：`public/licenses/Outfit-OFL.txt`，SIL Open Font License 1.1，保留上游版权声明；构建时原样复制到 `dist/licenses/`，与字体一起分发。
- 接入：`src/styles/fonts.css`，由 `main.ts` 导入；Vite 输出带哈希的同源字体文件。
- 字重：可变范围 100–900；使用 `font-display: swap`，不阻塞业务页面显示。

不得把远程 CDN 可访问性作为字体加载前提。升级字体时应一并更新来源、校验值、字体契约测试并复核排版。

## 中文字体边界

当前未捆绑普惠体 3.0。保留 `theme.ts` 中的普惠体及中文系统无衬线回退。Outfit 不提供中文字符，因此含中文的标题通过 `var(--sm-font-body)` 回退，不能声称普惠体在所有设备都已加载。

普惠体官方入口：https://www.alibabafonts.com/ 。没有从第三方字体下载站拉取未知许可或未知修订的字体。
