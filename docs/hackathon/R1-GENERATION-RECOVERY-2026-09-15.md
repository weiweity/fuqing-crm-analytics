# R-1 生成配置错误恢复（2026-09-15）

本地修复与隔离原生工具／HTTP 回归完成，B0 完整检查与干净重建通过。基线为已合 S3 的 `c734957`（#152）。[PR #153](https://github.com/weiweity/fuqing-crm-analytics/pull/153) 已 squash 合入 `698278e`。有界真实模型 3 次与 Chrome 预览取消已记账；TABLE `show_values` **NOT_OBSERVED**。产品保持 **PARTIAL**。

## 原因与原始证据

9 月 14 日 S2-C1 的两次失败均返回 HTTP 422 / `INVALID_REQUEST` / “请求与当前合同不匹配。”。原始记录位于本机 `.context/checks/s2-c1/live/`，不公开凭据或整份会话。本次只重放已存工具参数，没有发起新的模型请求。

| 旧记录 | 现合同重放结果 | 最小配置修正 |
|---|---|---|
| `generate-events.json` 第一次生成 | `blocks[5].TABLE.props.show_values` 为未登记属性 | 移除该属性，保留 TABLE 及其他五块 |
| `shortcut-events.json` 第一次生成（七块，含 FUNNEL） | LINE 为 `(6,4,6,7)`，TABLE 为 `(6,10,6,6)`，二者在第 10 行重叠 | TABLE 的 y 从 10 改为 11，七块均保留；FUNNEL 与其来源不变 |
| TABLE 失败后的 bash 尝试 | 原回执为方法边界拒绝，观察器以 `unexpected_tool` 取消 | 无 shell 成功执行证据；不把“尝试”记为“越权执行成功” |

旧记录将第二次失败简称为“FUNNEL 合同 422”，本次原参数重放确认是整板布局重叠。历史同轮删除 FUNNEL 后成功，不能据此判定漏斗数据或实现不支持。

## 修复

- `competition_board_generate` 提交 HTTP 前复用组件目录的属性、尺寸校验及画布重叠算法，回执指出 `blocks[i]` 与非法属性或冲突块。`details.phase=preflight` 明确表示请求尚未发往服务端。
- 不丢弃属性、不重排组件、不补 facts、不自动重试。修正请求仍由服务端核对合同、会话、权限和 result_id，仍只产生 PENDING 预览。
- 方法包补充 TABLE 不支持 `show_values`、布局按 `y+h` 检查、保留用户需要的组件、失败只按目录修正一次后停止，以及不得使用 shell／文件工具排查。冻结快照和哈希由既有打包器重生成。
- 原生工具守卫实现未变。新增集成断言覆盖本地拒绝回执后，同 Agent 的 bash 测试替身仍不能执行；未进入业务方法的另一 Agent 可运行无副作用的计数替身。

## 本次验证

| 验证层 | 结果与限度 |
|---|---|
| 原始完整参数重放 | 两个错误可由当前 Python BoardDraft 重现；只修对应配置后均通过合同，含 FUNNEL 的七块全部保留。无服务或模型调用 |
| 工具源回归 | 6 项通过；新增两项确认失败前没有 HTTP、参数未被改写、修正后只提交一次，保留 FUNNEL 及原 result_id |
| 编译与类型 | 固定 DSH `183f08e9`、Node 24、Python 3.14；host/client 完整类型检查与本插件构建通过 |
| 隔离集成 | 已构建原生工具 SDK → FastAPI → SQLite → 认证 RPC 通过。原始非法参数直接到后端仍为 422；修正后 TABLE 与 LINE/FUNNEL/TABLE 均为 PENDING，取消后没有已保存 head；结果仍只有一条。原有确认、布局、回退、点选编辑及重开链继续通过 |
| B0 完整检查 | PASS：486 项 Python、Ruff、源测试、编译后测试、Cordis loader、host/client 类型与干净重建；六个构建产物一致。不是旧 CRM 全套或真实模型验收 |
| 真实模型／Chrome | 3 次提示：问数通过；第一次生成因观察器把 `llm/retry` 当失败中止、未调用 generate；重试 8 次 generate，命中 `COMPONENT_OVERLAP` 预检，FUNNEL 保留，WATERFALL 因无对账贡献被数据合同拒绝。终态未保存 6 块预览，Chrome 打开后取消。TABLE `show_values` NOT_OBSERVED；bash 本轮 0 次。单测仍不能保证以后绝不 bash |

本轮新增集成测试首次运行的普通工具对照因测试替身缺少 SDK `output.render` 失败，补齐测试替身后通过；该次不是业务守卫放行失败，不抹去失败记录。两个新源回归在添加前置校验前失败，修复后通过。

隔离测试使用临时小型合成源和状态，结束后回收本次拥有的服务。未操作原运行实例、真实 DuckDB、Figma、用户保存版本或模型配置。原目录的 S3 未提交副本与 HANDOVER 保留。

## 交付与剩余

本地详细记录位于本机 `.context/checks/r1-board-generation-20260915/`，不进 Git。#153 squash 合入 `698278e`；PR CI [34940883528](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34940883528) 与该 main CI [34950368840](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34950368840) 均成功（`changes` / `b0-contract-build` / `merge-gate`；其余 job 为路径计划 skip）。

有界复验在临时切到候选插件的 6677 上进行，模型 `deepseek-official/deepseek-flash`。预览 `preview_3b87322e3dd841ac9b9db6463bad2e5c` 已取消；说明板 v15 与原板 v9 指纹未变。结束后 6677 恢复原目录插件（web PID 99115），18082 仍 71160。当前运行态不是 `698278e`。

85 历史导航、S4、S5 用户 UAT 和 G1–G6／U1 继续独立挂账；不重跑 Figma/B3 全矩阵，不代签验收。
