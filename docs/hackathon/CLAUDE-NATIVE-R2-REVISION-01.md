# Claude 原生 R2：候选绑定返修提示词

请修复下面这份候选，不使用旧 round2，不重新导入已变化的集成工作区。

- worktree：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics/.claude/worktrees/codex-first-purchase-native-r2`
- branch：`codex/first-purchase-native-r2`
- HEAD：`3ec1c866aa794baee6c0ebb7205aee375db1a49f`
- 有效基线：本候选已导入的 34 文件，保留 `.context/parallel-round2/BASELINE.sha256`。
- 返修前 `FILES.sha256` 文件本身 SHA256：`fc1589ca678b75da363146e5c8bf377ba678e6c9d74d59bbb5c4528788df7446`。先核对，漂移则说明。
- Codex 已独立集成 Grok 资产轨并修改共享来源接口；不要覆盖这些修改，也不要把当前集成目录套回旧 34 文件清单。

## 已复现的阻断项

1. **P1｜插件无法通过正式类型检查。** `src/first-purchase-query-model.d.mts` 漏导出 `FIRST_PURCHASE_RECEIPT_LIMIT`，`first-purchase-query-tool.ts:6` 报 TS2724。decoder 返回 object 的声明还需与实际 receipt 类型一致；修复后执行完整 host/client typecheck 与编译后 DOM，不能只跑 JS decoder 或跳过编译检查。
2. **P1｜运行中停止找不到实际 run。** `backend/analytics_first_purchase_native.py:82–100,118–123,164–165` 在 submit_and_execute 完成后才 bind_run。Codex 在真实 worker:spawned 暂停时，active_slot=1，但 context.active_run_id=null、run_ids=[]；gateway 的无活动任务分支会直接认可取消，没取消物理任务。必须在执行前取得共享内核的持久 run/session/request 绑定，context/cancel 按它找任务；不能加第二套账本，也不能以 request_id 冒充 run_id。
3. **P1｜未登记原生请求可执行，重启丢映射。** `native_step:163` 自行填写 pending，未经 prompt 登记的请求得到 200 并启动 worker；同状态目录重建 app 后 context.run_ids=[]。prompt/run/context 必须使用共享内核持久绑定、当前权限、实际状态，拒绝未登记或跨会话请求，重启后可重建已有 run 的关联。用临时状态库测试新 app / 新进程，不靠 module dict。
4. **P1｜方法包和预算没有接入原生运行上下文。** `run_context:137–154` 只检查内存映射并固定返回 RUNNING，不读取共享 run/attempt、预算或完成步骤；配置 digest 全 a 时，共享 runtime.binding 的 method 仍是 adapter 常量 `20a830ed0bae56127dad967b0a5761e8a9f5871a570411d63688dc1a4120dd25`。真实方法包摘要必须绑定至该 run，context 通过共享内核当前权限/预算机制重建；model/method unit 不能无限重复获取许可，终态不能报 RUNNING。
5. **P1｜同键在途重试误报失败。** `native_step:166–170` 对仍在运行的同 key 返回 409 TOOL_FAILED/retryable=false；Codex 已复现只有一个 worker、第一次仍可成功，但第二次被判失败。明确在途 receipt/202 或有界恢复协议并让工具消费它，稳定使用原 key/run，不能改成新 key 重算或无限等待。

复现源与日志（只读）：
`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/parallel-query-w4-integration/.context/parallel-round2-review/`
- `probe_native.py` / `probe-native.log`：真实小型 JSON worker、独立临时 SQLite，无真实库。
- `typecheck.mjs` / `typecheck.log`：候选插件源码副本 + 既有固定依赖，未修改你的候选。
- `received-candidates.json`：逐文件原始 SHA256。

## 修改边界与验收

你负责 native adapter、工具/卡片、serve/gateway 与专属测试。jobs.py、共享 FirstPurchaseRuntime、worker、codec 等共用接缝仍由 Codex 负责；需要的接口请给出精确签名、持久语义及可应用的独立补丁说明，不通过内存字典或取消校验绕过。可以先完成编译、协议与不依赖共享层的检查；依赖未接通处准确标 NOT RUN。

取消应覆盖 worker 真正在途、退出确认、用户看到的状态；幂等覆盖并发与重启；上下文覆盖撤权、预算及真实终态；回归渠道。编译测试必须加载实际编译产物。禁止以松化类型、any、跳过断言或硬编码成功关闭问题。

保留 JSON 金标准，缺角色不可提供保存有效分析操作。查询卡片仅传受控 run 引用，资产内部不改；catalog 暂不升级，浏览器和真实模型未执行就不报通过。

仍不 commit/push/PR/merge、真实模型/数据操作、停止旧演示、升级依赖或删除分支。更新 HANDOFF/INTEGRATION/EVIDENCE/FILES.sha256/CHANGES，记录旧候选摘要与新增验证，由用户转交。
