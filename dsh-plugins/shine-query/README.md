# `@shine-mage/dsh-shine-query`

问数／诊断：会话里的 query 工具、诊断 step、skills。可单独装卸，不改 DSH 上游。

`--plugin on` 默认再 `dsh plugin add` 本包。`--query off` 不注册问数／诊断工具。`--plugin off` 会连 workbench 一起关。

工具实现仍随 workbench bundle。FastAPI 18082 诊断路由默认仍在。
