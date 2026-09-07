# 合成仓 schema 与失败回滚

当前持久化格式为 `analytics-warehouse-schema/v2`，包含源记录表、记录 hash 和 `warehouse_meta.rules_json`。金额仍为整数分；业务口径未变。

W1/W2 初版及未修复 W3 的 v1 仓不会自动迁移。增量入口先以只读连接检查版本；旧版本在重建 staging 或打开写连接前明确拒绝。保留原仓和 published.json，需要重建时向另一个全新的空目录执行 `run_warehouse_pipeline(source_dir, new_empty_directory, incremental=False)`。该调用只适用于已授权的小型合成源，不是对真实业务库的升级入口，也不覆盖原目录。

v1/v2 的源 JSONL 清单仍可读取，但 schema、总 content_hash 和本次实际读取文件的 SHA-256 必须合法。年龄筛选跳过的订单文件不被读取；published.json 的 `consumed_file_hashes` 和 `skipped_order_files` 明确本次消费范围，`file_hashes` 保留输入清单范围。自定义分片也必须登记到清单。

一个批次的 staging、源表、规则、身份、元数据和事实修改在同一 DuckDB 事务中完成；输入校验或事实更新失败会回滚。父订单以原主键更新，明细/退款关联变更同时重算旧、新目标；商品版本变化覆盖旧、新有效区间。

事务成功提交后才 CHECKPOINT、关闭连接并写发布清单。W5 的版本目录、读者钉版本和跨数据库/清单的原子发布仍未实现，因此不能承诺进程在提交后、清单写完前退出时也能自动恢复。代码回退不代表 v2 数据可由 v1 代码读取。
