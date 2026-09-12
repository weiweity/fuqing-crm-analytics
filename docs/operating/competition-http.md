# Competition 合成 HTTP 的状态与调用约定

实现入口为 `backend/analytics_competition_app.py`，前缀 `/api/v1/analytics/competition`。本文记录 2026-09-10 审查修复后的运行时包络，不改变冻结 C0 合同、其 hash 或离线 OpenAPI 的 `paths: {}`。调用方类型位于插件的 `src/client/competition-board/types.ts`；C0 schema 继续由既有离线生成器核验。同 app 另有 `POST /api/v1/analytics/board-spec/ask`：已认证调用返回 `{patch}` 建议（`set_title` / `set_kind` / `set_metric_ref`），不写看板、不写 facts、不接飞书。

## 看板读取与成板

`GET /boards/{board_id}`、样式预览和版本保存返回 `{spec, blocks, ...}`。`spec` 遵循 `competition-board/v1`；`blocks` 是按保存版本及当前权限解析的板块。可用板块包含 `block_id`、`result_id`、`analysis_ref`、`layout`、`display_overrides`、`source_status: "OK"`，以及新增的 C0 `result` 投影。该投影来自板块绑定的保存分析版本，`result_id` 保留板块认可时的标识。

读取器把包络保留为 `{...spec, blocks}` 供组件使用。组件按 `block_id` 恢复布局、展示标题和结果，不依赖当前结果列表的排序；列表中没有旧结果也能重开。来源不再可见或绑定损坏时，板块标为 `UNAVAILABLE`，不显示其他结果或 C0 样例填充。投影仍是有限合成元数据；不据此宣称真实业务数值已经接入。

一次成板意图拥有新的 `batch_id`、各项 `operation_id` 和幂等 key。相同选择、布局的失败重试使用完全相同的请求；浏览器同一标签页通过按 actor/permission_scope 分区的 sessionStorage 保留未确认意图，组件重挂载也可恢复。后端回执成功且看板重读成功后清理该意图，下次创建分配新 ID。更改选择或布局表示新意图。浏览器存储不是权限凭据，后端仍独立授权及校验载荷。

HTTP `previewBatch` 只作本地 C0 请求校验；`applyBatch` 才 POST `/batches`。避免一次点击分别在“预览”和“应用”发送两次写请求。批次各操作独立提交，PARTIAL 保留原请求重试。

## 图表偏好运行时扩展

原有预览和保存路由同时接受 `competition-board-chart-patch/v1`：必填 `board_id`、`block_id`、`base_version`、`attempt_id`、`idempotency_key`，`intent=STYLE_ONLY`，`chart_type` 限于 TABLE/BAR/LINE/METRIC/EVIDENCE。只修改目标板块的 `plugin`，不改变来源、条件或数值。沿既有权限、取消、版本冲突与幂等事务校验；预览不落盘，保存递增版本，GET 返回已保存偏好。

扩展在 `backend/contracts/competition_chart.py` 单独定义。使用 `node scripts/dsh-b0/competition-chart-contract.mjs --check|--write --python /absolute/python3.14` 离线核验或生成 OpenAPI 与调用方类型；已纳入 B0 pipeline，不改冻结 C0。组件在当前预览保存或放弃前阻止下一次编辑；重开可恢复浏览器草稿，放弃不会覆盖服务端版本。没有数值序列时不绘制猜测图形。

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

新 GSV 数值采用独立的 `competition-computed-result/v1` / `competition-gsv-facts/v1`，生成器为 `scripts/dsh-b0/competition-computed-contract.mjs`。显式配置诊断源和私有结果库后，diag.gsv 及三种双期比较调用 A2 计算；其他未实现诊断标明未接通。来源仅允许受限小型合成快照，不支持 HTTP 输入任意数据库路径。

计算结果在 `diagnosis_results.sqlite3` 冻结保存 facts、resolved_condition 与 digest。相同 actor/session/request 重试重读，条件变更用新 request_id；跨进程恢复不依赖源 DuckDB。省略 session_id 的兼容请求是独立调用，不承诺跨请求重试身份。读取、认可、添加、复制、撤销和重开核对当前权限及 run/result/analysis 绑定。旧 ChannelFollowup 投影继续保留为元数据结果，不用于伪装新计算。

本扩展的 GSV 金额保持原值，change_ratio 为 raw ratio，仅在展示边界转百分比。对比期零值返回空比例及原因；没有覆盖的期间返回 EMPTY，不可认可。原生工具中断等待后，会独立请求下述诊断取消端点；只有后端确认的取消才承诺禁止后续保存。

回归入口为 `backend/tests/test_competition_review_regressions.py`、插件 `competition-board-dom.test.mjs` 和 `batch-intent.test.mjs`；共用接缝仍运行 `scripts/dsh-b0/pipeline.mjs --check`。实际结果以本轮修复记录为准，合成组件/HTTP 验证不能替代真实浏览器三角色 UAT、T13 真实模型或 T16 容量测试。

## 诊断计算取消（2026-09-10 增量）

`POST /diagnosis/cancel` 请求为 `{session_id, request_id}`，两项均为必填的 1–128 位 opaque ID。身份仅取当前 Bearer registry，要求 `analysis:read` 和 `competition-diagnosis-fixture` 数据域；不接受模型提供的 owner 作为授权依据。未接计算服务时返回 503/NOT_CONNECTED。

- 200 回执为 `{session_id, request_id, status: "CANCELLED", late_attempt_publish: false}`。按 actor/session/request 在诊断库 metadata 持久化，取消和 save 共用 BEGIN IMMEDIATE；重复取消幂等。之后相同请求返回 409/CANCELLED，继续诊断必须换 request_id，其他会话和请求不受影响。
- 已保存快照时返回 409/ALREADY_PUBLISHED，保留已发布的结果；写锁竞争返回可重试 503/STATE_UNAVAILABLE。取消端点不等待持有计算任务的会话锁。
- 宿主工具把实际 session_id 和 request_id 发给该端点，取消请求使用新的 2 秒 signal；原计算仍限 5 秒。宿主步骤预算 7.5 秒包含回执等待。中断、超时或丢失响应时只尝试一次取消，不重跑计算。
- 回执丢失、权限失效、服务/写锁不可用或绑定不匹配时，工具错误的 `cancellation.status` 为 UNCONFIRMED，不声称已阻止保存。HTTP 已保存先于取消返回时为 ALREADY_PUBLISHED。浏览器关闭、进程崩溃或不使用本 transport 的客户端断线本身不等于确认取消。

无需表迁移；新进程会读取取消记录。旧计算版本不检查该记录，不能用旧代码继续写同一诊断库并声称保留此保证。原生停止按钮到宿主 signal 的浏览器全路径验收仍与实际 Node transport/HTTP 取消回归分开，见[取消交付](../hackathon/DIAGNOSIS-CANCELLATION-2026-09-10.md)。
