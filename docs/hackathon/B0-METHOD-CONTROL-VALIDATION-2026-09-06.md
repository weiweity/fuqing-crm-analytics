# B0 方法包、上下文与当前权限验证

日期：2026-09-06。状态：**COMPONENT_CHECKS_PASS / CURRENT_PERMISSION_FIX_VERIFIED / B0_PARTIAL**。

当前连续执行队列见 [B0 清单](./B0-EXECUTION-CHECKLIST-2026-09-06.md)，最终统一结果见[本地收口报告](./B0-LOCAL-CLOSEOUT-2026-09-06.md)。本报告保留过程计数与红/绿证据，不替代完整业务问数、真实模型或产品 UAT。

## 方法与上下文

- 固定一个 `growth-analysis-b0` 方法小样，属于既有 B0 合成授权范围，不是生产获批经营 SOP。正文、证据引用和无数值示例均受 manifest/hash 约束。
- 构建前拒绝未登记文件、脚本目录、符号链接、硬链接、越界路径、内容变动及超限字节；运行时使用构建内的不可变快照，经 DSH 原生 Skill registry 与 `skill` 工具发现/按需加载。资源由精确键读取，不给模型文件系统或脚本工具。
- 默认文件提供方不扫描个人/项目根，显式 `includeDefaultRoots:false`、空自定义根、关闭 watcher；方法通过原生注册接口贡献，未增加 Agent 循环或长期记忆服务。
- 任务受理的同一事务中绑定方法包版本。首工具前、每次模型步骤及方法资源读取均回查 FastAPI 当前权限和任务状态；已受理但未绑定的旧任务不得事后采用新版本。
- 复用现有 SQLite 幂等表记录模型步骤和方法读取；方法读取与查询共享工具步数。压缩/重启/重复调用不重置原截止时间或预算；方法结果不是数值证据。
- 后端重建固定 fixture 条件、快照/指标/方法版本、完成步骤及证据摘要、parent 关系、未解析条件说明与剩余预算。自然语言条件未解析，不能声称筛选已生效；不存在的批准与长期记忆权限明确为 NONE。

组件证据：23 项包安全测试、13 项 Python 上下文/权限/恢复测试通过。真实固定版本 DSH loop + Skill registry/tool + BasicCompactionEngine 测试通过：故意输入带错误数字/批准/无限预算的摘要，压缩确实替换历史区间，后续步骤仍注入新的后端上下文；撤权模拟拒绝下一次方法读取。该测试的 HTTP 边界是 fixture，不能称为浏览器端到端或真实模型评测。

新增方法后统一 pipeline 曾通过 **164 Python / 123 Node 单元 / 4 原生产物与 loader 测试**，后者在原目录与干净目录各跑一次。干净目录 `clean-build-tx4mc5`。此后新增默认 roots 测试、权限修复和 6 项权限 fence 测试均局部通过；最终统一流水线尚待重跑，不混合统计。

## DEBUG REPORT：网关持续权限缺口

| 项 | 证据 |
|---|---|
| Symptom | 任务 T04 检查发现，权限后端不可用时已登录浏览器仍能读部分元数据/会话流 |
| Root cause | `gateway.mjs` 原来只验证本机 Cookie；部分 HTTP、WS 握手/消息/推送未回查当前后端权限 |
| Reproduction | 新隔离实例 `runtime-95yKIA`；暂停经 PID/命令核验的本次 kernel 后，HTTP 元数据仍 200，已有 WS 仍输出会话数据；未发送任何问题，finally 已恢复该 PID |
| Fix | 所有已认证 HTTP 与 WS 握手重查后端；连接内输入/输出分别有界串行、逐条验权；空闲连接定期核验并在失权时关闭，不缓存正向授权。连接/流/排队数量有硬上限 |
| Regression | 相同 live probe：HTTP 403、已有 WS 不再送数据；另 6 项测试覆盖撤权、异常/非法授权值、队列溢出、排队期间撤权、空闲撤权、晚到结果 |
| Related | 既有合同 §5.1/V25 的逐操作/重连权限要求；不是新增生产认证系统 |
| Status | **DONE**：这个已复现缺口的修复与同场景复验通过；完整 B0/多用户生产安全审计仍未完成 |

修复前证据：`runtime-95yKIA/permission-probe-1788680718801.json`（FAIL）。修复后：`runtime-95yKIA/permission-probe-1788680913579.json`（PASS）。均在 `.context/dsh-b0/` 下，未复制口令、Cookie 或真实文件内容。

当前控制面扩展实测 **46 PASS / 0 FAIL**，报告 `runtime-95yKIA/gateway-smoke-report-1788681289601.json`。包括正常 HTTP 元数据、自己的会话与历史、四类 WS 流、两个实际创建并经原生列表核验的外部合成会话隔离、原生凭据隔离、Fetch/上传/文件引用拒绝、未知/配置/模型/命令操作拒绝、跨源及超大 body。没有合法 prompt、模型调用或业务导出；MCP 未启用，单列 NOT ENABLED。

外部合成会话的首次准备脚本漏传 `session/list._request`，列表核验报错；两会话已创建，未重复创建。修正协议参数后仅重新列出并核验，保留同一实例。

## 后续复验结果与保留边界

- 更新后 preset 的原生七问 PASS；11 次本地 mock 请求全部核对当前后端上下文、原始截止时间与三个固定工具。浏览器只调用查询，方法读取/compaction 仍为独立组件层证据。
- T05 资产/BI 合同接缝/原品牌与三档视口、深浅主题已复验；控制面扩展为当前实例 51 PASS / 0 FAIL，清单见[当前控制面](./B0-CONTROL-MANIFEST-2026-09-06.md)。
- 最终 pipeline 于 2026-09-06T08:45:12.997Z 通过：164 Python / 133 Node / 5 原生产物及装配测试，原目录和干净目录各跑后者；浏览器产物与 `clean-build-DPNRQY` 一致。临时服务已停止，4315–4319 无监听。
- 历史监督器退出根因继续 OPEN；本次权限修复不改变其状态。
- 没有 commit、push、PR、merge、远端 CI、部署、真实库/ETL 或收费模型调用。
