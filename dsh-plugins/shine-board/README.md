# `@shine-mage/dsh-shine-board`

驾驶舱组板：生成／预览／确认、画布、六类+PROCESS/TIMELINE。可单独装卸，不改 DSH 上游。

`--plugin on` 默认再 `dsh plugin add` 本包。`--board off` 不注册组板工具、不出现「生成驾驶舱」。`--plugin off` 会连 workbench 一起关。

画布实现仍随 workbench bundle。已存 SQLite 板不自动删。FastAPI 组板路由默认仍在。
