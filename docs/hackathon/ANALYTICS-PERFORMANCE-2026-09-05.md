# 分析性能工程：首轮实现与后续数据面改造

状态：**DONE_WITH_CONCERNS，首轮本地优化完成；千万行 RFM / 5 人重分析容量尚未验收。**

后续归并：下文保留该轮局部实现与实测时点，未在本次整理时重跑；ETL 诊断见[独立证据](./ETL-DIAGNOSIS-2026-09-05.md)，整数键/共享特征/任务治理/容量的当前顺序见[总待办 W1–W5、V1–V4](./PLAN-CLOSEOUT-2026-09-05.md)。不将该轮 microbenchmark 解释为全链或真实库容量验收。

本轮用户授权把内存、并发、SQL、长客户键与 Rust 选择一起优化。只在现有任务 worktree 本地修改；未启动归档服务、读取 `.env`、扫描/迁移/复制真实库、执行 ETL、修改登录或发布。PC2 已排除，历史 PC2 的固定资源档不作为当前 Mac 默认配置。

## 1. 已实现与未实现

| 工作 | 状态 | 证据/边界 |
|---|---|---|
| 默认资源预算集中管理 | 已实现 | [resource_budget.py](../../backend/resource_budget.py)、[config.py](../../backend/config.py)；原常量 `32GB` 与 helper `8GB` 不一致已用失败测试复现并修复 |
| 缓存库独立小预算 | 已实现 | [dual_conn.py](../../backend/services/dual_conn.py)；原缓存库继承完整分析预算，现在有 `FQ_CACHE_MEMORY_LIMIT` |
| 派样首购聚合避免完整数组 | 已实现 | [sampling_service.py](../../backend/services/sampling_service.py)；两处 `ARRAY_AGG(... ORDER BY pay_time)[1]` 改为 `FIRST(... ORDER BY pay_time)`，原渠道/日期/空值/回购条件不改 |
| 多人分析调度 | 保留原实现并补验证 | 原有 2 槽位、5 秒排队超时、异步借还连接与取消等待不重造；合成小库 5 调用者通过，但不是 5 路重查询 SLA |
| 整数客户键 | 仅合成实验 | 未更改真实 `user_id`、事实表或 ETL；不能把实验当作客户键迁移完成 |
| RFM 快照/派样分析集市、任务去重、独立计算进程 | 待实施 | 按下文工作包推进，不以本次局部修改冒充完整数据面改造 |
| Rust 计算模块 / PostgreSQL / Redis / ClickHouse | 未新增 | 暂无证据要求整套换语言/换引擎；不修改 DSH、数字员工与前端路线 |

## 2. 默认资源策略及运行边界

- 默认分析库预算：检测到的 RAM 的 50%，最高 8 GiB；未知主机退到 2 GiB。Linux 标准 cgroup v1/v2 内存上限参与取最小值，特殊/嵌套容器挂载仍需显式部署预算。
- 默认线程：可见 CPU 数的一半，至少 1、最多 4。不是给每位老板各分配 4 个线程，不声称自动识别所有容器 CPU 配额。
- 默认独立缓存库预算：RAM 的 1/32，最高 256 MiB，不再继承完整分析预算。
- 本机本轮硬件核对：16 GiB、10 个逻辑 CPU。在不设置资源环境变量时，新默认值为业务库 `8192MiB`、4 线程、缓存 `256MiB`。
- `DUCKDB_MEMORY_LIMIT` / `DUCKDB_THREADS` / `FQ_READ_MEMORY_LIMIT` 等显式环境配置仍优先；**本轮未检查或修改实际 `.env`，也未重启服务，不能宣称运行实例已采用新值**。过大的显式设置不会被自动改写。
- 常规连接使用启动时稳定预算。`get_duckdb_memory_limit()` 的离线动态 override 保留，默认 fallback 与常量统一；不在 HTTP 请求中临时修改共享数据库预算。
- 读池继续使用 runtime `SET`，不把资源参数重新塞入同文件连接的 `connect(config=...)` fingerprint。业务读/写保留原有一致设置；独立 cache 设置已验证不改变业务库内存设置。
- `memory_limit` 是引擎 buffer 管理预算，**不是整个进程 RSS 硬上限**。Python 对象、结果转换、部分原生分配、其他数据库及操作系统也消耗内存。测试中 512MB 引擎上限与超过 512MiB 的进程 RSS 同时出现并不矛盾。

## 3. 合成对照结果

环境：本地 Homebrew Python 3.14.4、现有 DuckDB `1.5.4.dev18`；未安装/升级引擎。两种 SQL 各在全新子进程运行，每组 5 次，2 线程、512MB 原生预算，禁磁盘溢写。时间为 SQL 执行加结果提取的中位数，不包含造数、身份结果标准化和摘要计算。

数据只由 `range()` 生成。字符串键为 128 字符合成标签；客户数 = 行数 / 10，每客户分布到两个派样渠道；订单时间在测试中有序且唯一。不是实际品牌分布、千万行宽表或高倾斜负载。

| 合成行数 / 客户键 | 原数组 SQL | 新首条 SQL | 结果核对 |
|---|---:|---:|---|
| 10 万 / 128 字符 | 67.71 ms | 20.93 ms | SHA256 相同 |
| 50 万 / 128 字符 | 308.36 ms | 82.62 ms | SHA256 相同 |
| 50 万 / 整数 | 277.76 ms | 57.15 ms | 标准化 SHA256 与字符串两组也相同 |
| 100 万 / 128 字符 | 内存不足 | 内存不足 | 无完整结果，不能做同规模等价判断 |
| 100 万 / 整数 | 内存不足 | 118.88 ms | 新查询返回 20 万组；旧查询无完整结果，不能声称两者同规模等价已通过 |

50 万字符串键场景，进程峰值 RSS 为 **710.56 → 553.20 MiB**；整数键场景为 **575.50 → 408.98 MiB**。这些是单进程高水位，包含合成表、结果及摘要标准化，并非聚合算子自身的内存，也不是多次进程运行的统计区间。100 万整数＋首条的峰值为 682.58 MiB。

物理计划观察：新 SQL 出现 `arg_min` 原生聚合，旧数组 SQL 没有。50 万组的标准化结果摘要：`dc71052dec12320fa8d9a1eec0aa3a86b03c67dfd742de0f27b797dc92e50623`。本轮被测服务源码 SHA256：`f7626ec05b9f3eab5f960deb5df69416f882418d2f29160fc54f2f3490f2e5e6`。

结论只覆盖 **派样服务内的首购用户 SQL**。这不是整张派样看板的 3.7 倍提速，更不是 RFM 性能结果。100 万行的受限内存失败也不能反推 DuckDB 天生扛不住千万行：这里刻意把整个合成表放在内存，并禁用溢写。实验用于暴露数据表示与中间状态的差异。

### 复跑入口

从本 worktree 根执行：

```bash
/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/benchmark_sampling_first.py --rows 100000
/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/benchmark_sampling_first.py --rows 500000
/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/benchmark_sampling_first.py --rows 500000 --key-type integer
/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/benchmark_sampling_first.py --rows 1000000
/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/benchmark_sampling_first.py --rows 1000000 --key-type integer
```

[探针](../../scripts/diagnostics/benchmark_sampling_first.py) 没有数据库路径参数，拒绝超过 100 万行；资源耗尽输出 `out_of_memory`，当前 SQL 也失败则退出非零。不会自动加内存、允许溢写或重试到成功。这里的整数键只在 fixture 中生成，未接入运行中的软件。

## 4. 回归与口径保护

本轮先复现：默认值 `8GB != 32GB`、缓存独立预算未生效、服务仍使用完整数组。修正测试探针的函数定位后，完成实现及回归：

- **65 项 pytest 通过**，涵盖新资源/首购测试、旧 W7 override、连接兼容、取消等待、池满超时及 RFM 三期串行回归。
- **12 项原 RFM 离线控制流探针通过**；它使用 fake，不算原生 RFM SQL 或性能测试。
- Ruff、已跟踪 diff / 新文件空白检查、Python 语法检查通过；本文件 7 个本地链接目标存在，服务源码哈希已复核。
- 完整派样服务输出在合成小库上与旧 SQL 比较，覆盖品类/层级、同比/环比；不是仅比较一列聚合值。
- 覆盖空窗口、NULL 品类转“未知”、空字符串、同客户跨渠道、赠品收货日期、窗口外订单、缺少付款时间，以及有界排队/归还。
- 同一付款时间下多个不同商品，旧 SQL 本身没有二级排序键。此次保留“任取最早时间并列项”的既有语义；测试不伪造确定性归因。若要稳定归属到某商品，需要业务明确订单行 tie-break 规则，不能暗中添加一个排序字段。

安全复跑（不会加载 `.env`，生产可用性探测只看到不存在的临时路径）：

```bash
test_run_dir=$(mktemp -d /tmp/fq-resource-tests.XXXXXX)
PYTHON_DOTENV_DISABLED=1 \
DUCKDB_PATH="$test_run_dir/not-present.duckdb" \
FUQING_DB_PATH="$test_run_dir/not-present.duckdb" \
CACHE_DUCKDB_PATH="$test_run_dir/cache.duckdb" \
FQ_CRM_PASSWORDS='fixture:synthetic-only' PYTHONDONTWRITEBYTECODE=1 \
/Users/hutou/homebrew/bin/python3 -m pytest \
  backend/tests/test_analytics_resource_budget.py \
  backend/tests/test_sampling_first_aggregate.py \
  backend/tests/test_w7_memory_limit.py \
  backend/tests/test_query_router_event_loop.py \
  backend/tests/test_dual_conn_semaphore_timeout.py \
  backend/tests/test_rfm_3_periods_serial.py -q -p no:cacheprovider

/Users/hutou/homebrew/bin/python3 -B scripts/diagnostics/verify_rfm_execution_contract.py
```

## 5. 整体优化路线，不整套 Rust 重写

保留 [统一分析工作台](./UNIFIED-ANALYTICS-PLAN.md) 的业务路线；把本轮证据接入 [本地数据面验收](./RUNTIME-VALIDATION-PLAN.md)，不以 UI 或语言重写替代数据工程。

| 顺序 | 下一工作包（未实施） | 验收要求 |
|---|---|---|
| P1 | 稳定整数 `customer_key` + 客户身份映射 | 一次建立并持续维护；不截断密文、不以无碰撞验证的 hash 直接当唯一键；保留可控映射与跨店关联，明确身份命名空间；先在合成数据验证 |
| P2 | RFM/生命周期客户指标快照 + 派样首购/后购分析集市 | 优先复用现有 `user_rfm` / 缓存设计，业务口径以 semantic 与现行服务为准；区分分群截止日与后续观察期，不把未来购买泄露进历史分群；窗口、渠道、商品、数据版本改变时不能误用快照 |
| P3 | 独立计算任务与结果复用 | 先返回任务 ID；有界队列/并发、超时、取消完成确认、失败恢复；同条件去重必须包含品牌/店铺授权范围、过滤条件、指标版本、数据快照；不靠限制账号人数来充当算力治理 |
| P4 | 阶段化性能测量与 10 人 / 峰值 5 路验证 | 分开排队、SQL、结果提取、Python 转换、序列化和总耗时；测原生进程 RSS、临时磁盘、冷/热、倾斜客户、取消后资源、控制接口；千万行测试另设预算，不默认跑真实库 |
| P5 | 有证据才替换局部组件 | Python 自定义变换占主要成本时比较向量化/Polars/Rust 模块；SQL 主导时先改数据和执行计划；优化后仍不达容量目标再同机同口径比较服务型 OLAP |

其中首次商品归属的并列规则、可查询历史窗口、金额/订单粒度若需改变，先由业务确认。真实数据迁移与 ETL 执行仍需独立授权。这轮不自动部署 PostgreSQL、Redis、分库分表或新增 Rust 运行时。

Rust 的角色是**可替换的计算热点实现**，不是顶层产品架构。当前派样实验证明，不改 Python/FastAPI 就能改变原生引擎的耗时和内存；还没有 Rust vs Python 的实测，不能承诺 Rust 收益。后续需要 FFI 时先固定输入/输出契约，保持批量传递，避免逐行跨语言调用，并将编译、跨平台打包和故障恢复成本计入选择。

## 6. 外部依据与本项目推断

独立组织交叉验证，不把同一公司的官网和 GitHub 当作两方：

- DuckDB 官方指出排序聚合、多个阻塞算子及不可溢写的 list 状态存在内存风险，建议用执行计划定位。[调优指南](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads)；官方同时说明部分内存不受 buffer manager 上限控制。[OOM 指南](https://duckdb.org/docs/current/guides/troubleshooting/oom_errors)
- Kimball 建议数仓自行管理整数代理键，避免直接依赖多个业务系统的自然键。[维度代理键](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/dimension-surrogate-key/)

这两方分别支撑计算状态治理和身份建模，结合本地同预算实验，支持“数据模型与聚合方式优先于换调用语言”的项目判断；**不是两方都证明 Rust 无用，也不证明本项目已具备千万行多人服务能力**。客户实体稳定键与 SCD 版本行代理键应区分，不能把 Kimball 维度版本键直接当作跨期客户身份。

## 7. 交付边界

代码和合成验证在本地任务分支，保留其他未提交改动。无 commit/push/merge、无服务重启、无公网、无真实数据写入、无新 Rust 依赖。最终业务验收尚缺：完整 RFM 金标准、千万订单行目标数据分布、端到端时延、真实取消与隔离、多品牌权限及本地交互验收。
