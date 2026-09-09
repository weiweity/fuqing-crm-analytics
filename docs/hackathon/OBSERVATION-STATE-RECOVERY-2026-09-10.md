# 原生观察结果遇到状态写锁的恢复

视觉提交 `fa8978b` 的正常 pre-push 在首购原生锁竞争测试返回 409 EXECUTION_UNKNOWN，476 passed / 1 failed；上传尚未开始。之前本地完整 B0 曾通过，失败不能用此前成功覆盖。

失败的小型测试库记录 RUNNING → UNKNOWN → CANCELLING，worker 因 EXECUTION_UNKNOWN 被停止。原异常未被记录，不能断言当时精确哪个调用抛错。独立复现确认共享 RunDispatcher 有一个相关缺陷：收到相关联的 Host RUNNING 证据后，写本地状态发生 503 STATE_UNAVAILABLE，被宽泛异常处理改写成 UNKNOWN；若锁随后释放，这个错误状态可以落盘，使物理 worker 误以为执行失去可信状态。

修复仅将原始 SQLite DatabaseError 或 503 STATE_UNAVAILABLE 继续交给 tick 现有暂停入口，保留原 intent、状态和执行，不重新发送 dispatch。真正的 Host 断连、非法证据和其他语义错误仍走原 UNKNOWN 处理。没有放宽权限、取消或提交结果的边界，没有增大重试预算。

回归在临时真实 SQLite 中，在 Host 返回 RUNNING 后持有写锁，真实 observe 超时后释放锁。修复前断言失败；修复后锁期间快照不变、暂停新准入，恢复后同一 intent 且仅一次 dispatch，事件中没有 UNKNOWN/CANCELLING。首轮恢复断言要求整个快照完全不变，但有效确认会推进 DISPATCHING → ACCEPTED；已改为校验状态、原 intent、dispatch 次数与事件，锁期间完全不变断言仍保留。

相关两文件 23 passed / 1 warning。完整后端与 B0 将由正常 pre-push 检查；当前不是已推送或远端 CI 通过的声明。具体源文件、失败库时序及日志摘要见 [observation-lock.json](evidence/visual-readiness-2026-09-10/observation-lock.json)。本轮未切换 4325/18083 或调用模型。
