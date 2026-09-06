# autoplan 实施检查表
日期：2026-09-05。Status: C-T1_PARTIAL / OTHER_PACKAGES_NOT_STARTED。原11个工作包来自autoplan JSONL聚合（当时去重键为component+sorted(files)+title）；本轮工程复审将8组增量检查点人工映射回同一工作包，不宣称新增JSONL自动聚合仍恰为11行。工作包仍CEO2/Design2/Eng5/DX2。

当前跨计划顺序见[总待办](./PLAN-CLOSEOUT-2026-09-05.md)。新增架构 A、数仓/ETL W、多人验证 V 与本表交叉映射；W2/W4 与 E-T1 共用数据口径，V1/V2 纳入 E-T5。保留本表原 11 包，不重复计工作量、不把旧估时当作新增范围的日历承诺。D1–D4 已确认并完成四节静态审核；没有勾选任何产品包完成。[worker/故障报告](./B0-WORKER-FAULT-VALIDATION-2026-09-06.md)包含真实只读小合成执行及本地故障测试；最新[监督器复查](./B0-SUPERVISOR-RECHECK-2026-09-06.md)取得七问单次 PASS，历史退出原因未解，B0 PARTIAL；未作独立模型复核。

执行更新：[B0报告](./B0-DSH-VALIDATION-2026-09-05.md)保留早期两轮部分验证；后续[本地收口](./B0-LOCAL-CLOSEOUT-2026-09-06.md)与[T08](./B0-TOOL-CARD-DOM-2026-09-06.md)已补业务 run/原生七问、取消恢复、worker、方法/压缩组件、品牌/BI 接缝及工具卡组件 DOM 子集。当前 C-T1 仍 PARTIAL；其余包部分前置子集已有实现，但原 11 个完整产品包均未完成，不用早期快照覆盖当前证据。

本清单不自动授权真库操作、commit/push/merge、公网或消息；目前仅B0的安装、小样代码及临时合成运行获准。部分拟新增路径仍不存在；交互主源见[DSH设计](./DSH-UI-INTERACTION-SPEC.md)。D-T1/D-T2采用已核验目录dsh-plugins/analytics-workbench，不并建Vue聊天前端；旧Vue仅保留及适配标准BI。插件现有B0小样不能当D-T1/D-T2产品包已完成。

用户确认D08驾驶舱及A1先受理后派发；[工程静态复审](./AI-ENGINEERING-REVIEW-2026-09-05.md)已完成，增量检查点如下。仍为原11个工作包，不新增平台；D-T2及增量估时待B0后重估，旧合计不能直接作为新范围承诺。正式产品实现和整体验收尚未开始。

## 执行顺序与依赖
D1 更新（用户已确认）：C-T1/B0 内先完成 E-T1/E-T2/X-T1 的**最小 FastAPI 任务合同与内核片段**（登记、派发、查询、取消、重启恢复），Node 只保留协议转发；见[增量审核记录](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)。这不是另加工作包，不代表完整金标准/资产/营销实现已授权或完成。

D2–D4 更新（2026-09-06，均已确认）：插件同仓/固定版本/官方装配/统一构建与 CI，真实落盘/进程故障测试，以及独立 B0 资源配置/FastAPI 单一预算执行，与前置内核同批交付。4 个增量检查点及拟文件/验收落点见[审核 Implementation Tasks](./ENGINEERING-INCREMENTAL-REVIEW-2026-09-05.md)；它们映射本表原包，不重复计为新增产品包。独立 B0 不复用旧 BI 配置，原预算重启不复位，确认执行退出才回收额度；内核账本/HTTP/离线类型、DSH 七问接线、本地统一/干净构建及资源/故障子集已有证据，远端 CI 与完整矩阵未验收。实现入口使用独立 `backend/analytics_app.py`，避开旧 routers 包初始化，不修改旧 BI 路由。

前置片段与C-T1承载验证 → E-T1剩余合同/金标准 → E-T2与D-T1（按合同并行） → D-T2/E-T4/E-T3 → X-T1合同接线 → E-T5/X-T2 → C-T2本地验收与文案。X-T1的恢复合同与前置任务内核共同冻结，不能最后补丁；这里只将最终接线验收列后。

可能重叠：E-T1/X-T1共享contracts；E-T2/X-T1共享run恢复；D-T1/D-T2/E-T4共享前端目录。保留不同责任任务，不自动合并；同文件由一个集成人协调，不能简单相加估时作为日历承诺。

## Implementation Tasks（聚合）
- [ ] **C-T1 (P1), human: 1-2天 / AI协作: 4-6小时 — carrier-proof** — 验证已选DSH原生界面与单运行时的有限承载
  - 当前：PARTIAL。固定构建、公开插槽/自动进入、原生七问/run取消恢复、方法/compaction组件、品牌/BI合同接缝及工具卡8状态组件DOM已有限定证据；原生故障事件全链、卡片共存与历史监督器根因仍开放，不进入后续正式工作包。
  - 来源：ceo-review；C02/C07：上游网页与桌面不同，需硬门证据
  - 拟改：docs/hackathon/RUNTIME-VALIDATION-PLAN.md

- [ ] **C-T2 (P1), human: 0.5-1天 / AI协作: 2-3小时 — business-acceptance** — 以七项验收重放一条客户路径并校正提交文案
  - 来源：ceo-review；C01/C06/C08：完整闭环、本地不等于提交
  - 拟改：docs/hackathon/CEO-VALUE-PLAN.md、docs/hackathon/SUBMISSION-COPY.md

- [ ] **D-T1 (P1), human: 2-3天 / AI协作: 5-8小时 — chat-canvas** — 实现运行归属清晰的问数画布与全状态体验
  - 来源：design-review；D01/D02/D05：品牌复用、父子运行、小屏与无障碍
  - 拟改：DSH业务插件（B0冻结目录）；不重写旧Vue主题。覆盖工作区就绪、原生发送/停止/重试映射、工具卡codec和三档视口。

- [ ] **D-T2 (P1), 新范围估时待B0后重估（旧有限微调：human 1-2天 / AI协作3-5小时） — saved-cockpit** — 实现固定入口、板块组合及AI局部编辑并核验视觉
  - 来源：design-review及用户D08；保存非审批、局部改动不影响其他板块、日常最新与固定证据分开
  - 拟改：同一DSH业务插件的板块类型注册、资产/驾驶舱/草案视图；支持添加/复制/移除、拖动/缩放和键盘等效、局部配置预览/保存/撤销、筛选作用域、错误隔离。固定入口不依赖活动会话或模型可用。
  - 依赖：GET analyses/dashboards、DashboardSpec、局部PATCH和LATEST_SUCCESS/SNAPSHOT合同与E-T1/X-T1一起冻结；E-T2持久化配置及证据，不能只存在前端。测试见U3b/I3b/I3c/B1b/P1b，均未执行。

- [ ] **E-T1 (P1), human: 2-3天 / AI协作: 4-6小时 — metrics-contracts** — 冻结三类查询合同并实现独立订单金标准
  - 来源：eng-review；E01/E02：净额、时间、分母、证据字段
  - 拟改：backend/contracts/analytics.py、backend/services/analytics/catalog.py、backend/services/analytics/queries.py、backend/tests/test_analytics_metrics.py；合同同时覆盖板块类型/实例、配置操作及数据模式，不让前端自创第二套schema。

- [ ] **E-T2 (P1), human: 3-5天 / AI协作: 6-10小时 — run-assets** — 实现自有运行资产与有界执行取消恢复
  - 来源：eng-review；E02/E04：进程退出、fencing、幂等/缓存域
  - 拟改：backend/services/analytics/assets.py、backend/services/analytics/jobs.py、backend/services/analytics/runtime.py；包含驾驶舱配置版本/局部变更/撤销、最新兼容成功结果解析与历史证据隔离，不新增独立看板调度器。

- [ ] **E-T3 (P1), human: 2-3天 / AI协作: 4-6小时 — decision-binding** — 实现固定人群审批与短事务草稿导出
  - 来源：eng-review；E03：旧导出重选人群与锁内文件IO不可盲用
  - 拟改：backend/services/analytics/decisions.py、backend/tests/test_analytics_binding.py

- [ ] **E-T4 (P1), human: 1-2天 / AI协作: 2-4小时 — board-adapter** — 接通一个严格同条件的合成标准看板
  - 来源：eng-review；E05：缺省条件清空、来源隔离、固定证据
  - 拟改：frontend-vue3/src/features/analytics/（仅隔离synthetic标准看板）、backend/routers/analytics.py；先隔离App全局旧useFilterSync，不开放旧CRM。

- [ ] **E-T5 (P1), human: 2-4天 / AI协作: 4-6小时 — regression-evals** — 完成新链路回归、模型eval与本地资源验收
  - 来源：eng-review；E06及D08：七项验收/失败路径/至少60次模型变体记录，包含指定板块/全局范围识别；不能只用Chat保存成功证明驾驶舱通过
  - 拟改：backend/tests/test_analytics_jobs.py、backend/tests/test_analytics_access.py、frontend-vue3/e2e/analytics-workbench.spec.ts、docs/hackathon/RUNTIME-VALIDATION-PLAN.md

- [ ] **X-T1 (P1), human: 1-2天 / AI协作: 2-4小时 — api-dx** — 落实访问模式、请求丢失恢复与事件兼容合同
  - 来源：devex-review；X02/X03/X04：身份、重放、游标、旧版本只读
  - 拟改：backend/routers/analytics.py、backend/contracts/analytics.py、docs/hackathon/ANALYTICS-CONTRACTS-DRAFT.md

- [ ] **X-T2 (P1), human: 1-2天 / AI协作: 2-3小时 — developer-docs** — 交付合成起步、离线schema类型与调用/排障样例
  - 来源：devex-review；X01/X05/X06：后续AI不误启动私库或调用不存在接口
  - 拟改：README.md、docs/hackathon/README.md、frontend-vue3/package.json

## 最终交付
- [ ] 7项商业验收逐项有证据，失败/NOT RUN不隐藏。
- [ ] 本地演示与网址提交分开记；公网依赖仍未执行。
- [ ] 新schema、生成类型、接口样例、测试与实际能力文案一致。
- [ ] 当前用户视觉/认证脏改动全部保留，无无关文件覆盖。

## AI工程复审增量检查点（同一工作包内，内核子集已实施，其余待完成）

| 工作包 | 来源发现 | 增量交付 / 通过证据 |
|---|---|---|
| C-T1 | A1–A5 | 固定DSH接缝小样：prompt去重、run级停止、HTTP/WS/Fetch manifest、只读获批Skill装配、compaction恢复；MCP可不装，启用后才增加其必测项；不为通过B0建通用网关平台 |
| D-T1 | A1/Q1/T1/T2 | 原生发送显示真实受理run/phase；工具卡分主/辅结果；模型首工具前失败可恢复，取消不误停其他run；I1b/I2f/I2g |
| D-T2 | Q2/Q3/T3 | 无会话/模型刷新、局部配置hash、预览并发/撤销/复制/晚到结果归属；I3d/I3e及原D08测试 |
| E-T1 | Q1/Q2/Q3 | source_kind/ref、step结果、primary_result_ref、source_result_ref、刷新来源联合、effective_spec_hash及权限/预算schema统一；不新增并行类型主源 |
| E-T2 | A1/A4/A5/Q1/Q2/Q3/P1/P2 | 事务受理+派发意图、固定请求恢复、同执行器QUERY刷新、结果级证据、获批Skill/上下文装配、持久预算与资源门；不引Redis/Celery/新记忆服务 |
| E-T3 | Q1/T1 | CohortBinding与approval_digest包括明确source_result_ref；同run两个人群候选不串导出；I5d及既有三段式导出回归 |
| E-T5 | T1–T3/P1/P2/A2–A5 | 多步骤失败、生命周期故障注入、配置竞争、预算重启、返回体/事件/磁盘压力；测试地图全部新增行及V24–V30，数值/权限零错误，模型费用批准后才测 |
| X-T1 | A1/A2/A3/Q2 | POST /refresh-runs与source联合、原202恢复、逐操作控制面manifest、工具schema漂移与当前权限、分页/限额错误；OpenAPI/TS同hash |

不新增C-T2/E-T4/X-T2工作包，其既有验收、BI适配、文档接手继续有效。新增检查点的完整文件范围/机器任务记录见工程复审附录；文档存在不代表API已实现。B0后按实际接缝与剩余日历重估，若必须删商业验收、换壳或追加费用才停下请用户拍板。
