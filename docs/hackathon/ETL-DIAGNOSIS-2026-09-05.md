# ETL 诊断留存：数据流、增量边界与优化顺序

日期：2026-09-05。状态：`DIAGNOSIS_RECORDED / REFACTOR_NOT_STARTED`。

用户认可上一轮排查方向，现将证据归档并接入[总待办 W1–W5](./PLAN-CLOSEOUT-2026-09-05.md)。本轮复核关键源码位置，只做文档留存；没有运行 ETL、扫描/复制/改写真库、安装 Rust/Polars 或做新的全链性能测试。

## 1. 结论与可信边界

现有证据支持优先调整**数据流和增量计算边界**：减少重复读入/预热、限制连接中间结果、先完成事实纠正再更新下游。尚不能证明“DuckDB 引擎不够用”或“将 Python 全部改成 Rust 就会解决”。

很多计算已经调用原生 SQL、pandas 向量运算和 Parquet；Python 脚本入口并不表示每一行都由 Python 循环计算。没有真实分阶段 profile，不能把耗时全部归因于语言，也不能给出整体提速倍数。

已识别执行入口为 `scripts/run_etl.py` 调用 `scripts/etl/cli.py` 的 `main()`；`--update` 还会串联渠道纠正、状态/退款更新、预计算和预加载。**本轮未执行该入口，连 `--help` 也未执行**：入口 `finally` 含连接真实路径、清理表和 CHECKPOINT 的逻辑。历史 shell 包装器还包含服务起停，不是安全诊断命令。

## 2. 源码发现

下列“风险”是源码推导，不冒充真实数据已发生损坏或已测出耗时占比。行号用于定位本次快照，代码改变后应重新核验。

| 发现 | 源码位置 | 影响与需要验证的内容 |
|---|---|---|
| 文件年龄过滤没有接入真正读取集合 | [ingest.py](../../scripts/etl/ingest.py#L179) 生成 `_all_data_files`，后续重新枚举读取文件 | 日志称跳过旧文件不代表实际未读；也不能直接接上 30 天硬截断，以免漏晚到/修正 |
| SPU 先按商品做多对多连接，再过滤时间 | [transform.py](../../scripts/etl/transform.py#L258) | 中间行数可远大于最终匹配；改为范围连接/预规范化前必须保留原优先级和时间边界，不能盲换 ASOF |
| 增量新单只按全局最大支付时间识别 | [load.py](../../scripts/etl/load.py#L388) | 晚到历史新订单可能既不进入追加，也不进入 30 天刷新；“窗口外且已存在”的日志没有订单存在性证明 |
| 淘客纠正本身是全量重标 | [pipeline.py](../../scripts/etl/pipeline.py#L1184)、[重标实现](../../scripts/etl/pipeline.py#L1282) | 重置现有淘客后重新应用规则，并有索引移除/重建；需比较变更集合，不只是重复优化同一次全量 UPDATE |
| 下游预计算与事实最终纠正顺序分散 | [pipeline.py](../../scripts/etl/pipeline.py#L636)、[CLI 更新流程](../../scripts/etl/cli.py#L836) | pipeline 内部分首购/汇总计算早于 CLI 后续渠道和退款步骤；相关结果可能落在不同事实版本，须按依赖验证，不推断所有缓存一定陈旧 |
| 无新增事实仍可运行昂贵后置工作 | [cli.py](../../scripts/etl/cli.py#L839)、[预计算](../../scripts/etl/cli.py#L938)、[预加载](../../scripts/etl/cli.py#L964) | `force_continue=True`、RFM 预计算与 preload 需按输入/规则/as_of 失效传播；日期推进可能仍需更新 R，不能简单“零新单全部跳过” |
| RFM 预热覆盖很多逻辑组合 | [cache.py](../../backend/services/health/rfm_analysis/cache.py#L929) | 标注 380 个逻辑组合，日期别名有去重，不等于必定 380 次独立重查询；应共享基础事实并测实际执行数 |
| 历史 ID 集合与多份 DataFrame 驻留 | [pipeline.py](../../scripts/etl/pipeline.py#L88)、[订单集合](../../scripts/etl/pipeline.py#L257)、[ingest.py](../../scripts/etl/ingest.py#L327) | Python 侧全历史集合、拼表/拷贝等可增大峰值内存；使用投影、批量列式/数据库集合运算前需保留去重语义 |
| 刷新删除与插入的事务边界分开 | [load.py](../../scripts/etl/load.py#L510) | 故障可能暴露删除已提交但插入未完成的窗口；用隔离小库故障注入与新连接验证，不能在真库上试 |
| 计时范围不等于完整退出耗时 | [run_etl.py](../../scripts/run_etl.py#L86)、[性能计时器](../../scripts/etl/_timer.py) | 总计时先结束，之后仍有存储清理/检查点；`ru_maxrss` 是进程历史高水位，不能解释成每一步独立峰值 |

## 3. 上一轮的隔离复现

这是上一轮会话中已执行的最小复现摘要，**本轮未重新运行**。当时通过提取指定函数/语句、伪文件/读取器或合成 DataFrame 隔离真实入口，未导入有真实库副作用的 ETL 流程。一次性复现脚本及完整阶段测量附件尚未持久化，W1 要将其固化成可重复回归测试；因此不将此摘要充当完整测试包或性能基线。

| 样例 | 观察结果 | 能证明 / 不能证明 |
|---|---|---|
| 伪造 60 天旧文件，替换 Excel 读取器 | 日志跳过 1 个，读取器仍调用 1 次并返回 1 行 | 证明该样例的过滤/读取集合断开；未读取实际 Excel 或测真实导入耗时 |
| 从未见过的 60 天前订单，最大支付时间为昨日 | 追加 0、刷新 0 | 证明支付时间规则会排除该输入；不代表已核对线上漏单数量 |
| 1 万订单、同一商品 20 个互不重叠版本 | 连接产生 20 万行，时间过滤后 1 万行 | 证明候选中间结果放大；不是千万行实际内存或总 ETL 耗时 |

现有 [sampling FIRST 合成基准](./ANALYTICS-PERFORMANCE-2026-09-05.md)是另一条证据，只覆盖指定聚合，不可嫁接为本 ETL 的性能结论。源码中历史“63 分钟”“15 分钟”等注释不作为本轮实测。

## 4. 目标改造合同

1. 输入统一记录来源身份、内容 hash、schema/规则版本，已解析的标准列式数据复用；现有 Parquet/bulk SQL 可复用，不再平行建设另一套无关联缓存。
2. 明确订单头、订单明细与客户身份映射粒度；订单金额不按明细重复加和，长 `user_id` 不截断。稳定代理键保留授权身份域内的跨渠道关联。
3. 依据新增/变更输入、业务更新字段及规则变化识别受影响订单与客户；涵盖晚到、历史修正和退款。需要回看完整历史时显式安排，不能靠 30 天墙钟窗口猜测。
4. 渠道、商品角色、退款等事实最终确定后，再按同一版本更新共享客户/渠道/商品后续购买特征。RFM 窗口与 as_of 有合同，避免按每个 UI 组合重复扫描全部订单。
5. 校验后发布版本化分析产物；读者固定数据版本，失败保留上一有效版本。这里的版本化不是复制整座归档数据库；物理产物粒度与回收策略在设计阶段核定。
6. Python 负责编排、SQL/原生组件负责受测计算。先 profile 再判断是否引入 Polars/fastexcel 或局部 Rust；Excel 类型、超长 ID、日期、空值与金额精度必须先有一致性测试。

该合同是待落地的方向，未增加双写、Redis、集群或独立数仓远端仓库。W1–W5 与新分析 E-T1 使用同一事实/指标主源；真实库迁移需要另行授权。

## 5. 依据与交叉验证

下列来源在上一轮 2026-09-05 排查中核验，本轮仅归档，不声称重新检索或新增性能实证。不同组织才算独立来源；能力声明和原理说明不能代替本项目 benchmark。

| 支持的判断 | 两个独立组织的依据 | 适用限制 |
|---|---|---|
| 优先减少解析/传输，复用列式与原生引擎，而非按脚本语言决定重写 | [DuckDB 导入性能指南](https://duckdb.org/docs/current/guides/performance/import)、[Polars Excel IO](https://docs.pola.rs/user-guide/io/excel/) | 说明可用路径；未证明 fastexcel 对本公司文件完全兼容或一定更快 |
| 多对多中间结果、投影/过滤位置会影响内存和执行 | [pandas 合并指南](https://pandas.pydata.org/docs/user_guide/merging.html)、[Polars Lazy 优化](https://docs.pola.rs/user-guide/lazy/optimizations/) | 支持中间规模与下推优化原理；具体 SPU 重构必须保留现有选择规则 |
| 增量设计和读取/写入边界需要明确，不等于把 Python 换 Rust | [dbt 增量模型](https://docs.getdbt.com/docs/build/incremental-models)、[DuckDB 并发说明](https://duckdb.org/docs/current/connect/concurrency) | 前者支持变更集合/唯一键设计，后者说明访问模式；不是推荐安装 dbt，也不概括所有 DuckDB 扩展部署为同一种并发能力 |

补充源码依据：[Polars 官方仓库](https://github.com/pola-rs/polars)说明 Rust 引擎与 Python 接口；[duckdb-rs](https://github.com/duckdb/duckdb-rs)是 DuckDB 的 Rust 接口，不是换了一个计算引擎；[DuckDB 索引指南](https://duckdb.org/docs/current/guides/performance/indexing)说明索引适用范围及维护代价。同组织材料不另算独立交叉来源。

## 6. 收尾边界

本诊断不报告“ETL 已修复”或“千万行已扛住”。下一步是 W1 的可重复小样与 W2 数据合同，在获准实施范围内分步落地；本轮仅留证与排期，不执行原 ETL、不清库、不安装守护进程、不迁移目录、不提交或发布。
