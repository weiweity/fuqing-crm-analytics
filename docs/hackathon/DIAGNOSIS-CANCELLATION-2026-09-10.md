# 诊断取消的持久化修复

继 [GSV 数值接线](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md) 后，实际 Node transport 在计算中收到 AbortSignal，虽然调用方已返回 AbortError，后端仍保存 1 条结果。失败证据保留在 `evidence/diagnosis-integration-2026-09-10/cancellation-before.txt`。这次修复使确认取消与保存争用同一短事务：取消先提交则拒绝保存，保存先完成则返回 ALREADY_PUBLISHED。

取消标记写入既有诊断 metadata，按当前 actor、宿主 session 和 request 隔离，不迁移表、不删除已保存证据。取消端点绕开正在计算的会话锁；客户端使用独立 2 秒 signal 等待回执。回执失败只标 UNCONFIRMED，继续诊断使用新 request_id。HTTP 计算仍限 5 秒，不为取消重跑模型或计算。

验证使用 OS 分配的 loopback 端口、独立合成源和临时私有 SQLite。测试先让真实计算停在保存前，再中断实际 Node transport，收到取消回执后释放计算；同时覆盖 5 秒超时、跨进程重读、权限、跨会话隔离、已发布结果、SQLite 写锁与错误回执。测试服务和子进程均由 fixture 回收，未操作用户端口。

完整日常后端 **2320 passed / 77 skipped**，新增取消测试 5 项均通过；完整 B0 pipeline PASS，含 4 项取消回执测试、类型检查和干净构建。源码及结果见[绑定记录](evidence/diagnosis-integration-2026-09-10/cancellation-verification.json)。B0 在独立的 competition-cancel-verification 树执行，源码字节与开发树核对，避免构建改写 4325 正在使用的 lib。该检查不包含新增付费模型调用。

当前结论为取消的 transport/HTTP/SQLite 边界已修复；不把它升级成浏览器停止按钮全路径或完整 T17 通过。产品的 T13 完整诊断、用户本人 T15、T16 正式数据范围与阈值、业务默认值、旧 MCP、主题和发布条件继续沿[七阶段账本](PRODUCT-READINESS-2026-09-10.md)处理。


## Git 与独立候选

代码已提交并推送为 `d9c9162266667251db1a69645fbe1d2f01216ae0`，并入已有 [draft PR #115](https://github.com/weiweity/fuqing-crm-analytics/pull/115)。commit/pre-push hooks 均执行；首次简短提交说明被 commit-msg 拒绝后补写具体变更与验证，未绕过门禁。Git 调用仅临时指向当前工作树自身 hooks，未写入 Git 配置。独立 diagnosis 开发树保留在同一代码提交，交付分支为 competition-product-readiness。

4325/18083 已切到该代码提交；新 PID 为 DSH 64225（supervisor 64210）、API 64190，均在 readiness 树管理。原 Models runtime 仍为 `.context/dsh-dev/runtime-Cn0Ifc`，没有复制配置。切换前 5 个 SQLite 共 258048 字节备份并在新目录恢复；新应用重开后所有结果、看板和当前草稿响应与切换前一致。线上候选取消回执和同键 409 已验，未新增可见结果；浏览器 BAR 重开保留 400/300/100/33.33%，dialog 仍打开。

[切换和恢复证据](evidence/diagnosis-integration-2026-09-10/cancellation-candidate-switch.json)绑定源码、产物和状态。原先 4327/8000/5173/14327 的 PID 保持不变。该记录写入时远端 CI 34408763075 仍在运行，不能沿用 #115 旧 HEAD 的成功；最新远端状态以 PR 当前 SHA 为准。旧代码不识别取消标记，备份可读不代表完整降级可写，正式发布仍未完成。
