# 功能包清单（可单独卸载）

目标：按功能拆包。卸一个包，该功能的 UI、工具、合同和对应 FastAPI 路由一起消失，而不是只卸 6677 壳、后端还在。

当前不是这样。`dsh-plugins/analytics-workbench` 是一个大包；存板／422／问数在 `backend/`；比赛看板在 `frontend-vue3`。卸伸美包只回到官方 DSH web 壳。

本文件定边界。品牌、WATERFALL、FUNNEL、人群行动、问数、组板已拆成独立 Cordis 包。比赛看板保持 `frontend-vue3`／15173 独立进程，不进 DSH。

## 卸不掉的内核（不是功能包）

这些不是「不想要某个功能就卸」：

| 内核 | 位置 | 说明 |
|---|---|---|
| DSH 官方壳 | 钉住上游 `0.1.6-alpha.2` | 不改上游源码 |
| FastAPI 鉴权／会话 | `backend/routers/auth.py` 等 | 各包共用登录与权限 |
| B0 SQLite | 运行时状态／已存板 | 板数据在卸包后仍在磁盘，只是没有 UI |
| 归档 DuckDB | `data/processed/fuqing_crm.duckdb` | 不进 Git；卸包不删库 |
| `scripts/dsh-dev` | 6677 起停 | 装配器，不是业务功能 |

## 功能包（目标）

每一包将来应是：**一个 DSH Cordis 包 + 它自己的 FastAPI 路由（若有）+ 合同**。装卸单位是包，不是散文件。

| 包（拟名） | 现在散落 | 卸掉应消失 | 建议顺序 |
|---|---|---|---|
| **品牌覆盖** | `@shine-mage/dsh-shine-brand`：标题／欢迎语／favicon／侧栏名。静态资源仍是 overlay `analytics-dev-brand-assets`。驾驶舱内 h2／logo mark 仍在 workbench | 卸 `shine-brand-ui` 后文档标题与侧栏名回官方；资源行仍可单独在 overlay | 1 已拆包 |
| **WATERFALL** | `@shine-mage/dsh-shine-waterfall`：几何、目录供给、`SHINE_WATERFALL` 门控。`channel_bridge` 计算仍在 FastAPI GSV v5。画布几何仍随 workbench bundle | 卸 `shine-waterfall-ui` 后 GENERATE／目录不再提供 WATERFALL；`--waterfall off` 时未知单位不再作为瀑布供给。已存块仍能解析 | 2 已拆包 |
| **FUNNEL** | `@shine-mage/dsh-shine-funnel`：几何、目录供给、`SHINE_FUNNEL` 门控。购买频次仍在 FastAPI GSV v5。几何仍随 workbench bundle | 卸 `shine-funnel-ui` 后 GENERATE／目录不再提供 FUNNEL | 3 已拆包 |
| **人群行动** | `@shine-mage/dsh-shine-crowd-action`：6677 页签入口。`ActionsWorkbench` 仍随 workbench bundle | 卸 `shine-crowd-action-ui` 后驾驶舱不再出现「人群行动」页签 | 4 已拆包 |
| **问数／诊断** | `@shine-mage/dsh-shine-query`：工具注册门控。实现仍随 workbench；FastAPI 诊断路由默认仍在 | 卸 `shine-query-ui` 后会话不再注册问数／诊断工具 | 5 已拆包 |
| **驾驶舱组板** | `@shine-mage/dsh-shine-board`：组板工具与「生成驾驶舱」门控。画布仍随 workbench bundle | 卸 `shine-board-ui` 后不再注册组板工具、不出现生成驾驶舱 | 6 已拆包 |
| **比赛看板** | `frontend-vue3`、15173、品类脱敏。页脚外链，不进 DSH profile | 停 15173 即整站消失；卸伸美 DSH 包不影响 15173 | 7 已定为独立进程，不迁 |

六类 METRIC／LINE／BAR／TABLE／TEXT／EVIDENCE 与 PROCESS／TIMELINE 先留在 **驾驶舱组板**，不要按组件再切，否则画布合同会碎。

## 卸载机制（目标 vs 现在）

现在：`--plugin on` 默认再装 shine-funnel。`--funnel off` 可单独卸。overlay 仍只插 `analytics-dev-brand-assets`。`--plugin off` 禁用全部 shine UI id。另有 `SHINE_FUNNEL`。

目标：`scripts/dsh-dev/overlay`（或 profile bundles）里 **每包一行**。不写那一行 = 未安装。对应 FastAPI 路由随包注册，不进总 `main.py` 默认全集。

已存 SQLite 板：卸组板包后只读失败或隐藏，不自动删盘。

## 明确不做

- 不把旧 Vue 全量 CRM（PAUSED Goal）收进功能包。
- 不改 DSH 上游。
- 不把 131GB 归档变成插件资源。
- 不改 6677。
- 不把比赛看板收进 DSH 组合；继续独立 15173。

## 迁移顺序

1. 本清单（本文）。
2. 品牌覆盖 `@shine-mage/dsh-shine-brand`（已拆；默认随 `--plugin on` 安装，`--shine-brand off` 可单独卸）。
3. WATERFALL 包 `@shine-mage/dsh-shine-waterfall`（已拆；默认随 `--plugin on` 安装，`--waterfall off` 可单独卸）。
4. 人群行动 `@shine-mage/dsh-shine-crowd-action`（已拆；默认随 `--plugin on` 安装，`--crowd-action off` 可单独卸）。
5. 问数 `@shine-mage/dsh-shine-query` 与组板 `@shine-mage/dsh-shine-board`（已拆；`--query off`／`--board off` 可单独卸）。
6. 比赛看板继续独立 15173，不进 DSH。FUNNEL `@shine-mage/dsh-shine-funnel` 已拆。
