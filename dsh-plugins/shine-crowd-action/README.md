# `@shine-mage/dsh-shine-crowd-action`

人群行动入口：原生驾驶舱页签「人群行动」。可单独装卸，不改 DSH 上游。

`--plugin on` 默认再 `dsh plugin add` 本包（路径是仓库 `dsh-plugins/shine-crowd-action`）。`--crowd-action off` 卸入口，并 disable 残留的 `shine-crowd-action-ui`。`--plugin off` 会连 workbench 一起关，不是只卸人群行动。

卸掉本包后：6677 驾驶舱不再出现「人群行动」页签。`ActionsWorkbench` 仍随 workbench bundle；CockpitView `surface=competition-actions` 仍可被旧 overlay／测试直接渲染。
