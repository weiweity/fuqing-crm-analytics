# 首购查询与 W4 并行集成清单

日期：2026-09-08。状态：LOCAL_INTEGRATION_PASS / UNCOMMITTED。
基线：3ec1c866aa794baee6c0ebb7205aee375db1a49f，VERSION 0.6.3.0。
协调分支：codex/parallel-query-w4-integration。已导入候选并完成两项本地修复、共享内核/HTTP 接线及回归。
基线 CI 34228499035 为 SUCCESS；不是新候选或本轮业务回归通过。

## 归属与任务账本

| 负责人 | 允许范围 | 交付 / 当前状态 |
|---|---|---|
| Claude | 首购专属适配、独立 HTTP factory、专属测试；已有首购合同必要改动须显式说明 | HANDOFF、FILES.sha256、INTEGRATION、EVIDENCE；已收到，Codex 本地修复通过 |
| Grok | 新 W4 模块、手算金标准与专属测试；复用现有 W1–W3，不改仓 schema | 同上；已收到，Codex 本地修复通过 |
| Codex | 本文件、STATUS、hackathon README、总待办；收到候选后负责共享接线及回归 | 共享接线、离线合同、pipeline 与交付文档已完成 |

Codex 专属共用修改：catalog.py、jobs.py、worker.py、backend/analytics_worker.py、共用 HTTP/runtime 注册、serve/gateway、合同生成入口、前端注册、pipeline/CI 路径选择。VERSION/CHANGELOG 在实际用户行为变更后按需更新，本次文档不升版本。
首购与 W4 可并行交付；首购先沿用现有首购 JSON snapshot，不依赖未验收 W4。第三查询族、W5、真实模型、部署不在本轮。
主工作区 ARCHIVE.md 与三份未跟踪 Goal 文档保留，未复制进此候选。

## 首购最小接缝（集成前源码核对，保留历史）

1. v0.6.3.0 的合同为 backend/contracts/analytics_first_purchase.py，schema analytics-first-purchase-path/v1；计算入口 backend/services/analytics/first_purchase/compute.py:execute_first_purchase_path_query。它是纯 JSON 变换，不是既有 DuckDB family_first_purchase.py 的同名结果替换。交接必须说明采用合同及旧实现关系。
2. catalog.py 当前仍把 first_purchase_product_path 和 candidate_handoff_audience 标为 DEFERRED。离线金标准存在不能直接开放运行能力；仅在对应受控路径完整通过后调整首购登记，保持候选人群拒绝。
3. 集成前 jobs.py 的 RunStore family 仅 b0/channel_followup，持久 metadata、schema、绑定和结果解释依赖 family。worker.py 的 WorkerManager 对渠道使用确切 ChannelFollowupFixture 类型，结果类型为 ChannelFollowupResult 或 AnalyticsB0Result。不能把首购当渠道装入旧 codec，也不能通过默认 else 落入 B0。
4. 集成检查点：新 family 的持久辨识与 reopen、fixture descriptor、结果严格校验、权限/owner/current capability、幂等 key、取消/退出/lease、失败映射需一并覆盖；不复制第二套任务状态机。是否需要修改旧 DB schema 必须单独说明，不默认迁移。
5. analytics_query_app.py 现有只读 conversation/run 与 versioned cancel 路径带登记 session 和 conversation owner 绑定。新 HTTP factory 不应借接线开放任意 session CRUD；内部派发需当前权限验证，不以 filter_hash 充当认证。
6. 缺商品角色应按首购合同拒绝，facts=null；空成熟分母为 null，不能转为成功的 0%。合同/OpenAPI/TS 使用离线生成，不启动 CRM。
7. HTTP 层通过后仍不宣称 native UI、保存分析或驾驶舱支持首购；这些入口需逐层核对结果类型和信任来源，未覆盖就保持不开放。

## W4 最小接缝（源码核对）

1. warehouse/facts.py 的 fact_order_header 以 (synthetic_user_id, order_id) 为主键，含 customer_key、identity_domain、permission_scope、gross_paid_minor、refund_minor_as_of、net_paid_minor、is_valid。金额聚合不能从订单明细重复累计。
2. 保留 W1–W3 现有 schema/事务/增量接口。W4 新模块消费明确的已完成版本，不修改旧导入入口；结果显式绑定 as_of、规则/数据版本和权限域。
3. refund_minor_as_of / net_paid_minor 是既有时点事实。交接必须证明请求 as_of 与事实构建时点一致，或有合同允许的重建方式；不得仅过滤 paid_at 就把晚到退款带入旧时点，也不能声称任意历史时间旅行。
4. 输出首末购、订单数、净金额及距末购时间所用有效订单规则必须写明。无新单而日期推进、同刻多单、退款和跨域拒绝均用手算小样验证；本轮不新增 RFM 桶、不自动喂给首购运行接口。
5. 若现有仓不足以支持要求的历史版本/身份域，交付清楚拒绝或限制，不偷偷改 W1–W3，不宣称 W5 发布完成。

## 候选接收与验收顺序

- [x] 独立 worktree、主线/远端/未跟踪与端口核对。
- [x] 状态文档当前描述修正，历史证据保留。
- [x] 文件归属及共用接缝准备。
- [x] 收到 Claude 路径，核对 HEAD/base、Git diff、未跟踪清单、FILES.sha256 与实际字节。
- [x] 收到 Grok 路径，同上；识别混入共用文件，不盲目覆盖。
- [x] 先集成首购：显式文件清单，合同/worker/HTTP 与旧 B0/渠道回归。
- [x] 再集成 W4：手算金标准、权限/as_of/日期推进；持久化时新增连接读取验证。
- [x] 共用改动按 docs/operating/verification.md 选择检查；B0 实际改动跑统一 pipeline，不能以源测试子集代替编译/装配。
- [x] 记录实际结果、SHA256、层级和未完成项，给出可转交返修提示。

不导入 .context、node_modules、运行状态或真实库；收到的证据只作为复核输入，关键行为独立验证。没有候选时不提前填写通过状态。

## 运行环境收尾方案（仅提案，未执行）

核验 PID 36717（Python）/36727（Node）监听 127.0.0.1:8000/5173；lsof cwd 都指向 ../.worktrees/hackathon-mission-mvp，已核对该路径的 Path.exists() 为 False（2026-09-09）。这是残留旧演示，不是 v0.6.3.0 运行证据。源码目录消失不代表进程已退出，也不能断言数据库已丢失。

在用户明确批准结束演示后：先重新核对 PID、创建时间、cwd、监听和打开文件，检查主线 scripts/ops/stop-stack.sh 能否准确识别这两实例。脚本若不能识别，不对其他端口或同名进程批量终止；提供绑定当前 PID/启动指纹的精确终止方案后执行对应授权。若仍有被删除的打开状态文件，先说明保存选择，不能直接停止使唯一内容不可恢复。停止后核验端口与 owner。重建当前版本演示属于另一步授权，不能顺带启动或恢复旧服务。

本轮不停止、不重启、不读取数据库内容、不修改服务配置。

本次接收结论见 [复核 01](./PARALLEL-REVIEW-01-2026-09-08.md)。该复核当时尚未导入业务文件；后续已完成集成。

当前修复结果见 [本地修复 01](./PARALLEL-REPAIR-01-2026-09-08.md)；无需再转交返修提示。

最终状态以 [本轮集成结果](./PARALLEL-INTEGRATION-RESULT-2026-09-08.md) 为准；旧修复报告中的临时账本已由共享 RunStore 替换。
