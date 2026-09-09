# 原生观察结果遇到状态写锁的恢复

视觉提交 `fa8978b` 的正常 pre-push 在首购原生锁竞争测试返回 409 EXECUTION_UNKNOWN，476 passed / 1 failed；上传尚未开始。之前本地完整 B0 曾通过，失败不能用此前成功覆盖。

失败的小型测试库记录 RUNNING → UNKNOWN → CANCELLING，worker 因 EXECUTION_UNKNOWN 被停止。原异常未被记录，不能断言当时精确哪个调用抛错。独立复现确认共享 RunDispatcher 有一个相关缺陷：收到相关联的 Host RUNNING 证据后，写本地状态发生 503 STATE_UNAVAILABLE，被宽泛异常处理改写成 UNKNOWN；若锁随后释放，这个错误状态可以落盘，使物理 worker 误以为执行失去可信状态。

修复仅将原始 SQLite DatabaseError 或 503 STATE_UNAVAILABLE 继续交给 tick 现有暂停入口，保留原 intent、状态和执行，不重新发送 dispatch。真正的 Host 断连、非法证据和其他语义错误仍走原 UNKNOWN 处理。没有放宽权限、取消或提交结果的边界，没有增大重试预算。

回归在临时真实 SQLite 中，在 Host 返回 RUNNING 后持有写锁，真实 observe 超时后释放锁。修复前断言失败；修复后锁期间快照不变、暂停新准入，恢复后同一 intent 且仅一次 dispatch，事件中没有 UNKNOWN/CANCELLING。首轮恢复断言要求整个快照完全不变，但有效确认会推进 DISPATCHING → ACCEPTED；已改为校验状态、原 intent、dispatch 次数与事件，锁期间完全不变断言仍保留。

相关两文件 23 passed / 1 warning。完整后端与 B0 将由正常 pre-push 检查；当前不是已推送或远端 CI 通过的声明。具体源文件、失败库时序及日志摘要见 [observation-lock.json](evidence/visual-readiness-2026-09-10/observation-lock.json)。本轮未切换 4325/18083 或调用模型。

## 远端 worker 监控读锁追加

`4d8a968` 的正常本地推送检查通过：受影响后端 12 passed，完整 B0 478 Python passed，类型、组件、干净重建和 LFS 上传成功。远端 [CI 34414999794](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34414999794) 的 B0 构建成功，完整 Python 任务在 `test_result_and_closed_without_process_exit_cannot_complete` 失败。堆栈明确为 WorkerManager.execute 的监控循环调用 worker_records，抛出 sqlite3.OperationalError: database is locked；不是前述观察状态分类的同一个位置。

监控循环原本对无法核验的进程/状态错误走受控停止，但漏掉 sqlite3.DatabaseError。补入同一异常集合，沿既有 terminate/kill、真实退出与落盘门禁返回 EXECUTION_UNKNOWN；不把锁错误当作成功，也不放任无法核验权限和期限的 worker 继续运行。没有新增错误枚举、存储格式或无限重试。

新增回归在真实 SQL 子进程发出 CLOSED_FRAME_NOT_EXIT 且仍存活时，向唯一监控读取边界注入远端记录的 SQLite 异常。修复前原异常穿透；修复后返回 AnalyticsError，子进程以 -9 退出、持久记录 EXITED 且释放 active_slot，steps.result_json 仍为空。查询 worker、基础 worker、首购原生及原生运行时共 76 passed / 1 warning；Ruff 与差异检查通过。此测试只在驱动故障边界注入异常，不能描述为真实 SQLite 写锁测试；真实写锁证据在前节。

同轮只读核对旧 MCP：2 个已有回归通过，确认截断已标失败、超大中文 JSON 返回完整错误；串行 300 秒 CLI、取消及完整结果交付仍 PARTIAL。比赛运行时通过已配置 HTTP 直连，不经过旧 stdio。未启动旧 MCP 或读取真实数据库。

源码及原始日志摘要见 [worker-read-recovery.json](evidence/visual-readiness-2026-09-10/worker-read-recovery.json)。本追加还需自己的正常推送和远端检查；不沿用 `4d8a968` 的局部成功。用户 4325/18083 保留原版本与 Models 配置，未切换。

## 原生测试探针的管道关闭竞态

`bcbad29` 的 [CI 34415937002](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34415937002) B0 成功，Python 第二组完成 97 项后触发 900 秒超时。按同一收集顺序，下一个是 `test_close_kills_this_instance_sql_hold_child`；没有远端线程堆栈，故这是定位推断。原第二组在 macOS 本地 393 passed / 1 warning，未重现 Linux 卡死。

独立确定性回归确认资源归属错误：真实 SQL 子进程进入屏障后，协调器 close 杀掉子进程，也关闭了已交给 worker selector 的 stdout/stderr。现协调器只停止自有子进程并关闭探针专用管道，由 WorkerManager 读到 EOF 后关闭协议流；独立 ProbeLauncher 默认仍完整清理。回归修复前 1 failed，修复后相关 51 passed / 1 warning，确认真实 -9 退出及两条管道都能排空到 EOF。

检查入口增加 pytest 的 60 秒线程堆栈输出，保留 900 秒组超时与原测试选择；已有 runner 回归 44 passed。该补丁修复测试探针的生命周期，不扩大产品运行时异常处理。源文件和日志摘要见 [probe-pipe-ownership.json](evidence/visual-readiness-2026-09-10/probe-pipe-ownership.json)。本次还需正常推送和新 SHA 的 CI；4325/18083 与模型配置保持原状。
