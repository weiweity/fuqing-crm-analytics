# `@shine-mage/dsh-shine-waterfall`

WATERFALL 功能包：贡献瀑布几何、目录供给、未知金额 422。可单独装卸，不改 DSH 上游。

`--plugin on` 默认再 `dsh plugin add` 本包（路径是仓库 `dsh-plugins/shine-waterfall`）。`--waterfall off` 只装 workbench／品牌，并 disable 残留的 `shine-waterfall-ui`。`--plugin off` 会连 workbench 一起关，不是只卸瀑布。

卸掉本包后：GENERATE／目录不再提供 WATERFALL；未知单位不再作为瀑布供给（`SHINE_WATERFALL=off`）。已存 SQLite 板里的 WATERFALL 块仍能解析，画布几何仍随 workbench 打进 bundle。FastAPI 18082 默认仍计算 `channel_bridge`（环境未设时 `SHINE_WATERFALL` 默认 on），与 6677 装卸分开。
