# R-1 生成配置错误恢复（2026-09-15）

本地修复与隔离原生工具／HTTP 回归完成，B0 完整检查与干净重建通过。基线为已合 S3 的 `c734957`（#152），分支 `codex/fix-r1-board-generation`。修复提交 `dccc80e` 已提交、推送至草稿 [PR #153](https://github.com/weiweity/fuqing-crm-analytics/pull/153)，推送门禁通过。真实模型行为复验仍 **NOT_RUN**；尚未切换运行环境或合并，产品保持 **PARTIAL**。

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
| 真实模型／Chrome | 本次未跑；单测不能保证模型以后不会尝试 bash，或不会误删组件 |

本轮新增集成测试首次运行的普通工具对照因测试替身缺少 SDK `output.render` 失败，补齐测试替身后通过；该次不是业务守卫放行失败，不抹去失败记录。两个新源回归在添加前置校验前失败，修复后通过。

隔离测试使用临时小型合成源和状态，结束后回收本次拥有的服务。未操作原运行实例、真实 DuckDB、Figma、用户保存版本或模型配置。原目录的 S3 未提交副本与 HANDOVER 保留。

## 交付与剩余

本地详细记录位于本工作树 `.context/checks/r1-board-generation-20260915/`，不进 Git。提交前 `/review` 已完成 OCR preview/rule：5 个代码/配置文件全部审查，另手审 6 个 Markdown，无未闭合高风险问题。PR 与当前 HEAD 的 CI 状态、最终合并回执以 [#153](https://github.com/weiweity/fuqing-crm-analytics/pull/153) 为准；CI 不能替代真实模型 QA。

运行只读预检通过：现有 6677 仍加载原目录插件，默认模型为 `deepseek-official/deepseek-flash`，业务服务已配置；这不验证凭据有效性或实际模型请求。说明板 v15 与原板 v9 的正文指纹已留存，未新增版本。已准备临时切换与恢复方案：确认窗口后使用候选插件与原持久 runtime，新会话最多 3 次提示，只检查并取消新预览，结束恢复原插件并核对已存正文。当前窗口待确认，合并前 QA 保持开放。

R-1 代码恢复链已具备隔离证据，真实模型行为仍待固定候选、有界调用与明确运行窗口复验。85 历史导航、S4、S5 用户 UAT 和 G1–G6／U1 继续独立挂账；不重跑 Figma/B3 全矩阵，不代签验收。
