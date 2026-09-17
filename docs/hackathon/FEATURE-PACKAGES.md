# 功能包清单（可单独卸载）

目标：按功能拆包。卸一个包，该功能的 UI、工具、合同和对应 FastAPI 路由一起消失，而不是只卸 6677 壳、后端还在。

当前不是这样。`dsh-plugins/analytics-workbench` 是一个大包；存板／422／问数在 `backend/`；比赛看板在 `frontend-vue3`。卸伸美包只回到官方 DSH web 壳。

本文件只定边界和迁移动作。**未迁代码。** 下一刀另授权。

## 卸不掉的内核（不是功能包）

这些不是「不想要某个功能就卸」：

| 内核 | 位置 | 说明 |
|---|---|---|
| DSH 官方壳 | 钉住上游 `0.1.6-alpha.1` | 不改上游源码 |
| FastAPI 鉴权／会话 | `backend/routers/auth.py` 等 | 各包共用登录与权限 |
| B0 SQLite | 运行时状态／已存板 | 板数据在卸包后仍在磁盘，只是没有 UI |
| 归档 DuckDB | `data/processed/fuqing_crm.duckdb` | 不进 Git；卸包不删库 |
| `scripts/dsh-dev` | 6677 起停 | 装配器，不是业务功能 |

## 功能包（目标）

每一包将来应是：**一个 DSH Cordis 包 + 它自己的 FastAPI 路由（若有）+ 合同**。装卸单位是包，不是散文件。

| 包（拟名） | 现在散落 | 卸掉应消失 | 建议顺序 |
|---|---|---|---|
| **品牌覆盖** | `client/brand-surface`、`client/competition-shell`、`scripts/dsh-dev` overlay 品牌行 | 伸美皮肤，官方壳默认外观 | 1（最小、无 FastAPI） |
| **WATERFALL** | `board-spec/waterfall.*`、catalog WATERFALL、`backend/.../computed.py` 的 `channel_bridge`、`MONEY_UNIT_UNKNOWN` 422 | 目录项、渲染、未知单位失败合同 | 2（合同岛，测试已独立） |
| **FUNNEL** | `board-spec/funnel.*`、catalog FUNNEL、首购相关供给 | 漏斗块与对应问数形状 | 3 |
| **人群行动** | `client/competition-actions`、#166 入口 | 6677 内打开人群行动 | 4 |
| **问数／诊断** | `query-tool.ts`、`first-purchase-query-tool.ts`、`skills/*`、`competition-agent`、FastAPI 诊断／GSV／RFM | 会话里的问数工具与结果 | 5 |
| **驾驶舱组板** | `board-spec/*` 其余、`client/board-spec-canvas`、`library-*`、生成／预览／确认 | 画布与六类+PROCESS/TIMELINE | 6（最大，依赖问数结果） |
| **比赛看板** | `frontend-vue3`、15173、品类脱敏 | 页脚「比赛看板」整站 | 7（今天不是 DSH 插件；可继续当独立进程，或做成可选包） |

六类 METRIC／LINE／BAR／TABLE／TEXT／EVIDENCE 与 PROCESS／TIMELINE 先留在 **驾驶舱组板**，不要按组件再切，否则画布合同会碎。

## 卸载机制（目标 vs 现在）

现在：一个 `--plugin-path` + `cordis.patch.yml` 一行 `analytics-workbench-ui`；另有 `DSH_ANALYTICS_UI_ONLY`、`COMPETITION_HTTP_*`。

目标：`scripts/dsh-dev/overlay`（或 profile bundles）里 **每包一行**。不写那一行 = 未安装。对应 FastAPI 路由随包注册，不进总 `main.py` 默认全集。

已存 SQLite 板：卸组板包后只读失败或隐藏，不自动删盘。

## 明确不做

- 不把旧 Vue 全量 CRM（PAUSED Goal）收进功能包。
- 不改 DSH 上游。
- 不把 131GB 归档变成插件资源。
- 本 PR 不切代码、不改 6677。

## 迁移顺序

1. 本清单（本文）。
2. 品牌覆盖单独 bundle 行（行为不变，只改装配）。
3. WATERFALL 包（带着 422 合同和测试一起走）。
4. 人群行动。
5. 问数 vs 组板拆开。
6. 比赛看板是否进 DSH 组合，另议。
