# 并行候选本地修复 01

> 历史阶段证据：后续已由 Codex 完成本地修复与集成，无需转交。当前结果见 [集成报告](./PARALLEL-INTEGRATION-RESULT-2026-09-08.md)。

状态：LOCAL_REPAIRS_PASS / SHARED_RUNTIME_PENDING。本轮按用户指示由 Codex 修复，替代两份外发返修提示；提示保留为历史问题记录，无需转交。

候选按 FILES.sha256 逐文件校验后显式导入 11 个业务/测试/fixture 文件；未导入交接目录、依赖或状态文件，原工作区保持不变。

## 修复

- F1：独立首购验证账本执行前以同 run 的私有文件描述符 flock 非阻塞争用；活跃同键重试返回 retryable 503，不再重复计算。锁覆盖计算和终态落盘，finally/进程退出释放，锁文件不 unlink。真实子进程在 RUNNING 后 os._exit(73)，重开仍恢复原 run。此锁仅修复候选适配，不新增调度状态表，也不代替未来共用 RunStore/WorkerManager。
- F2：features_sha256 统一为实际 JSONL UTF-8 字节摘要，manifest 声明编码；_finish 和 writer 共用序列化。writer 一次序列化并校验，再写同一份 bytes。内部行发生修改或摘要不匹配时，创建任何产物前拒绝。空集摘要为零字节 SHA256。不是 W5 发布方案。

## 本轮验证

bounded runner 对 test_analytics_first_purchase_http.py、test_analytics_first_purchase.py、test_analytics_customer_features_w4.py：41 passed，1 warning，退出码 0。包含同键活跃并发、真实进程退出恢复、JSONL 摘要、改值/坏摘要拒绝和空集。Ruff 和 git diff --check 通过。

证据：.context/checks/20260908T140516377549Z/summary.json。未跑 native/browser/完整 B0 pipeline；共用运行层尚未修改，不宣称其已集成。未 commit/push/PR/merge，不改用户演示。

下一步：首购共享账本/物理 worker、运行结果合同与接线仍开放；catalog 保持 DEFERRED。W4 为独立本地特征模块，不自动接首购查询或 W1–W3 发布。产品仍 PARTIAL。
