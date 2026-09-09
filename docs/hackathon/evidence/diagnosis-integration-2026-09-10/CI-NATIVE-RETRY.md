# 首购原生 CI 瞬态状态回归

2026-09-10，基线 `afb62b0`。代码提交 `d9c9162` 的 [CI 34408763075](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34408763075) 成功；仅追加交付记录后的 [CI 34409208987](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34409208987) 在首购原生 HTTP 测试失败，B0、lint 和 contract 检查成功。失败响应为 `503 STATE_UNAVAILABLE`、`retryable=true`，测试原本要求单次立即返回 200。远端日志未包含底层 SQLite 异常，不能断言远端具体哪个数据库操作被锁。

## 修正与独立复现

仅调整测试，生产行为未变：对同一个 session/request/call 的执行请求，最多在 5 秒窗口内重试合同允许的 `503 STATE_UNAVAILABLE + retryable=true` 或 `202 IN_FLIGHT`。其他错误立即返回，超时仍失败；最终正确 facts、run_id 和结果复用断言保留。

新增真实小型 SQLite 写锁回归：先将隔离任务调度至 RUNNING，持有 EXCLUSIVE 写事务时 HTTP 返回 503；释放锁后原调用成功，重放得到 REUSE_RESULT，runtime_work 与 worker_records 均恰好一条。第一次复现准备停在 QUEUED，WAL 允许读取并返回 202，因此断言失败；修正准备步骤后得到预期的写锁路径。这些结果不证明所有 worker 中途故障均可恢复。

原始证据保留在本工作树：

- `.context/ci-34409208987-failed.log`：远端失败。
- `.context/ci-native-retry.log` 与 `.context/ci-native-retry-check/summary.json`：首次探针 5 passed / 1 failed。
- `.context/ci-native-retry-running.log` 与 `.context/ci-native-retry-running-check/summary.json`：完整首购原生文件 11 passed，单组 2.765 秒，进程树 RSS 峰值 187432960 字节。该资源数只描述测试进程，不作为 T16 产品容量证据。

## 提交前审查

PASS（限本次测试差异）：没有放宽最终业务结果或权限断言，没有跳过用例，没有新增生产重试，没有改调用标识或接受任意 5xx。真实锁测试覆盖恢复与不重复启动 worker；持续故障仍会在有界等待后失败。新提交远端 CI 必须单独核验，不能沿用前一个 SHA 的成功结论。
