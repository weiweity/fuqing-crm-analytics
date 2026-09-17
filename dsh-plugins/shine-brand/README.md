# @shine-mage/dsh-shine-brand

伸美品牌覆盖：文档标题、欢迎语、favicon、侧栏产品名。静态 PNG/SVG/字体仍由 `scripts/dsh-dev/brand.mjs`（`analytics-dev-brand-assets`）提供。

`--plugin on` 默认再 `dsh plugin add` 本包（路径是仓库 `dsh-plugins/shine-brand`，不跟 `--plugin-path` 绑兄弟目录）。`--shine-brand off` 只装 workbench，并 disable 残留的 `shine-brand-ui`。`--plugin off` 会连 workbench 一起关，不是只卸品牌。

卸掉本包后，DSH 侧栏名和标题回到官方文案。驾驶舱对话框里的 h2／logo mark 仍在 workbench，下一刀再迁。
