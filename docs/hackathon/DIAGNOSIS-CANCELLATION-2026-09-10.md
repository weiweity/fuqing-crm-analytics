# 诊断取消的持久化修复

继 [GSV 数值接线](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md) 后，实际 Node transport 在计算中收到 AbortSignal，虽然调用方已返回 AbortError，后端仍保存 1 条结果。失败证据保留在 `evidence/diagnosis-integration-2026-09-10/cancellation-before.txt`。这次修复使确认取消与保存争用同一短事务：取消先提交则拒绝保存，保存先完成则返回 ALREADY_PUBLISHED。

取消标记写入既有诊断 metadata，按当前 actor、宿主 session 和 request 隔离，不迁移表、不删除已保存证据。取消端点绕开正在计算的会话锁；客户端使用独立 2 秒 signal 等待回执。回执失败只标 UNCONFIRMED，继续诊断使用新 request_id。HTTP 计算仍限 5 秒，不为取消重跑模型或计算。

验证使用 OS 分配的 loopback 端口、独立合成源和临时私有 SQLite。测试先让真实计算停在保存前，再中断实际 Node transport，收到取消回执后释放计算；同时覆盖 5 秒超时、跨进程重读、权限、跨会话隔离、已发布结果、SQLite 写锁与错误回执。测试服务和子进程均由 fixture 回收，未操作用户端口。

完整日常后端 **2320 passed / 77 skipped**，新增取消测试 5 项均通过；完整 B0 pipeline PASS，含 4 项取消回执测试、类型检查和干净构建。源码及结果见[绑定记录](evidence/diagnosis-integration-2026-09-10/cancellation-verification.json)。B0 在独立的 competition-cancel-verification 树执行，源码字节与开发树核对，避免构建改写 4325 正在使用的 lib。该检查不包含新增付费模型调用。

当前结论为取消的 transport/HTTP/SQLite 边界已修复；不把它升级成浏览器停止按钮全路径或完整 T17 通过。产品的 T13 完整诊断、用户本人 T15、T16 正式数据范围与阈值、业务默认值、旧 MCP、主题和发布条件继续沿[七阶段账本](PRODUCT-READINESS-2026-09-10.md)处理。
