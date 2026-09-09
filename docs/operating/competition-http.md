# Competition 合成 HTTP 的状态与调用约定

实现入口为 `backend/analytics_competition_app.py`，前缀 `/api/v1/analytics/competition`。本文记录 2026-09-10 审查修复后的运行时包络，不改变冻结 C0 合同、其 hash 或离线 OpenAPI 的 `paths: {}`。调用方类型位于插件的 `src/client/competition-board/types.ts`；C0 schema 继续由既有离线生成器核验。

## 看板读取与成板

`GET /boards/{board_id}`、样式预览和版本保存返回 `{spec, blocks, ...}`。`spec` 遵循 `competition-board/v1`；`blocks` 是按保存版本及当前权限解析的板块。可用板块包含 `block_id`、`result_id`、`analysis_ref`、`layout`、`display_overrides`、`source_status: "OK"`，以及新增的 C0 `result` 投影。该投影来自板块绑定的保存分析版本，`result_id` 保留板块认可时的标识。

读取器把包络保留为 `{...spec, blocks}` 供组件使用。组件按 `block_id` 恢复布局、展示标题和结果，不依赖当前结果列表的排序；列表中没有旧结果也能重开。来源不再可见或绑定损坏时，板块标为 `UNAVAILABLE`，不显示其他结果或 C0 样例填充。投影仍是有限合成元数据；不据此宣称真实业务数值已经接入。

一次成板意图拥有新的 `batch_id`、各项 `operation_id` 和幂等 key。相同选择、布局的失败重试使用完全相同的请求；浏览器同一标签页通过按 actor/permission_scope 分区的 sessionStorage 保留未确认意图，组件重挂载也可恢复。后端回执成功且看板重读成功后清理该意图，下次创建分配新 ID。更改选择或布局表示新意图。浏览器存储不是权限凭据，后端仍独立授权及校验载荷。

HTTP `previewBatch` 只作本地 C0 请求校验；`applyBatch` 才 POST `/batches`。避免一次点击分别在“预览”和“应用”发送两次写请求。批次各操作独立提交，PARTIAL 保留原请求重试。

## 取消与持久化

`POST /batches/{id}/cancel` 和 `POST /attempts/{id}/cancel` 要求当前 `dashboard:update` 及业务数据域权限。取消按 actor、目标种类和 ID 记录到资产 SQLite 的 metadata；状态 schema 仍为 v1。

- 取消事务先提交：返回 200/CANCELLED，后续操作必须在发布写事务内检查取消记录并返回 409/CANCELLED；应用重建、进程退出后仍有效。
- 发布事务持锁：取消无法取得锁时返回可重试的 503/STATE_UNAVAILABLE，不承诺取消成功。
- 已完成发布：返回 409/ALREADY_PUBLISHED；取消不能撤销已保存版本。
- 批次中已在取消前提交的板块保留，取消只阻止之后的发布；不把它描述成整个批次原子回滚。

无需迁移现有数据库。旧二进制虽能打开同一 schema，却忽略取消记录；若降级必须保留取消检查，否则不能沿用本版本的取消保证。

## 候选与行动草稿

候选 ID 一旦写入就绑定权限域、cohort 与完整候选快照。同 ID 完全相同的请求可重放；跨域冲突返回 403，同域改动内容返回 409/CONFLICT。读取还核验 JSON 内容和授权列是否一致，旧版本遗留的不一致记录返回 503/STATE_UNAVAILABLE，不自动改写归档状态。

`GET /drafts/current` 返回 `{http_api: "CONNECTED", draft, candidates, cohort}`。有结果时三项分别为最新可见草稿、其绑定候选快照与 cohort；无结果时三项为 null。查询仅选当前 actor 拥有且权限域仍可见的版本，要求 `cohort:read` 与 `draft:write`。其中“当前”为最近写入的可见草稿版本。

首次预览候选后可填写对照设计、停止条件并 POST `/drafts`。新草稿省略 `draft_id`；更新携带 `draft_id`、`base_version`、`candidate_set_id`、`permission_scope`。重开后客户端恢复这些标识，避免把更新错误地当新建。重新预览得到新候选会退出旧草稿编辑，允许为新候选创建草稿。

文案更新保留候选和证据；`rule_changed: true` 使已有草稿过期；复核可设置 `REVIEW_PENDING`，过期草稿不会因此复活。所有路径保持 `auto_send: false`。

## 诊断会话

`POST /diagnosis/capabilities`、`/diagnosis/step`、`/diagnosis/patch` 接收可选 `session_id`，必须匹配 `[A-Za-z0-9_.:-]{1,128}`。原生 DSH 工具从执行上下文的 `agent.session.id` 注入该字段，覆盖模型参数中的同名值。

状态按 `(actor_id, session_id)` 隔离；每次请求使用 registry 当前身份。权限改变时丢弃继承条件、证据和在途编辑目标，保留该会话已经消耗的预算，重新授权。独立原生会话从新预算开始，不能继承另一会话的条件。

HTTP 兼容调用未传 `session_id` 时视作单次独立请求；需要 `INHERIT` 的调用必须显式保持同一个 ID。进程内会话空闲 30 分钟回收，最多同时保留 256 个会话；上限内不驱逐活跃会话来重置预算，超限返回可重试 429/BUSY。会话状态本身不跨应用进程保存，与必须持久化的取消记录分开。

## 验证范围

回归入口为 `backend/tests/test_competition_review_regressions.py`、插件 `competition-board-dom.test.mjs` 和 `batch-intent.test.mjs`；共用接缝仍运行 `scripts/dsh-b0/pipeline.mjs --check`。实际结果以本轮修复记录为准，合成组件/HTTP 验证不能替代真实浏览器三角色 UAT、T13 真实模型或 T16 容量测试。
