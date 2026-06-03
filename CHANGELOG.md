# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **ETL 3 件 P0/P1 修复合集（cli.py / _timer.py / daily_metrics）** —
  ① `scripts/etl/cli.py:678-683` **P0** `--full / --inc` 静默 noop bug：之前
  `if args.full: _mode = 'full'` 只设变量从未调用 `run_full_etl()`，导致
  `python scripts/run_etl.py --full` 啥都不干就退出。修复加 mode 字符串
  转换 + PerfTimer + 实际调用 run_full_etl，并打印明显的 `=== ETL 跑批 ===`
  标记。② `scripts/etl/_timer.py:267-270` **P1** `save_baseline` `run_id="1/3"`
  硬编码默认值：调用方未传具体值时 existing_runs dedup 按 run_id 单字段
  匹配 → 第 2 次跑批 run_id='1/3' 覆盖第 1 次。这是 origin/main run 1
  (01:41 wall=180.2min) 被 QW2 验证跑批 (12:48 wall=52.6min) 覆盖丢失的
  根因（前一个 chore/qw2-etl-baseline-run-2 手动 git show 合并修了数据
  但代码 bug 未修）。修复改默认 `run_id=None` → 自动读
  `len(existing_runs)+1` 作为 `(N+1)/3`。③ `scripts/etl/load.py:160`
  + `scripts/etl/pipeline.py:399/432` **P1** `daily_metrics` 表
  `old_user_count` 硬编码 `0`：3 处 SQL 改用 `LEFT JOIN user_first_purchase`
  按 `first_pay_date = DATE(pay_time)` 判定新客 / `<` 判定老客，同时
  `new_user_gmv` / `old_user_gmv` 也按同口径算（之前都是 0 死代码注释
  自承「待业务确认后重写」）。健壮性：信息模式表检查 user_first_purchase
  存在性，不存在则 fallback 旧逻辑不阻塞 ETL。同时调整 pipeline.py
  调用顺序：删除 Step 5 metrics 调用，新增 Step 6.7 在 user_first_purchase
  + user_recency 之后调，保证 metrics SQL 跑时依赖表已建好。pytest
  backend/tests/ 153 passed / 8 skipped 全过。

### Performance
- **QW0 严格 Phase 2：第 2 次 Mac baseline run 跑批入仓** — `data/processed/etl_perf/baseline_2026_06_03.json` 追加 run 2/3：wall=52.6min（cleanup 后 orders 表 2.9M 行的增量 ETL，31 个 per_step 节点），相比 run 1/3 (180.2min, cleanup 前 10.6M 行全量 ETL) **3.4x 提速**。提速来源：① cleanup 移除 7.7M order_id=sub_order_id 重复行 → Step 4 反向同步省时；② parquet 缓存命中 251/251 → Step 1 全店读 0 重读。**关键 bug 发现**：`scripts/etl/_timer.py:267` `save_baseline()` 默认 `run_id="1/3"` + 调用方未传具体值 → 同 baseline_date 多次跑批互相覆盖（origin/main 的 run 1 被 12:48 那次覆盖了），手动 git show 取回 run 1 + 改 run_id=2/3 追加合并；`wall_time_stdev` gate 标 skipped 并加 note 说明 run 1+2 数据规模不同 stdev 无意义。剩余 4 次 baseline（Mac ×1 + Windows ×3）+ median 计算 留 task #24/#34；`save_baseline` run_id 自增 fix 留 task #59 / `fix/timer-run-id-autoincrement` 分支单独 12 步。

### Changed
- **`.gitignore`：屏蔽 `.claude/`（gstack 工具配置）+ `scripts/etl/_cleanup_staging.py`（一次性维护脚本，按文件头自述「脚本本身不入 git」，本地保留作工具避免下次 dup key 时重写）** — 收尾 QW2 验证后工作区 3 个未跟踪文件的归类决策。

### Fixed
- **CHANGELOG.md 残留 merge conflict marker 清理（QW2 Phase 2 merge 后遗）** — commit `9c3f0ad` (QW2 Phase 2 merge) 残留 `<<<<<<< HEAD` / `=======` / `>>>>>>> origin/fix/qw2-phase2-cache-writes` marker 在第 17/18/23 行，本次 chore 顺手清理。QW2 Phase 1 条目已删（Phase 1 在 commit 链中已被 revert ×2：`6669816 Revert "Merge fix/duckdb-readonly-uvicorn"` + `c934324 Revert "docs(changelog): QW2 Phase 1"`），CHANGELOG 只保留实际生效的 Phase 2 条目。

### Added
- **DMP 6 道门禁抽到独立模块 + 飞书 webhook 告警** — 5/28 出现 18 行 likely-wrong 脏数据时无主动告警的问题修复。新增 `scraper/core/sanity_check.py` 把 MEMO_2026-06-01/02.md 识别的 6 道门禁（date_sanity / item_data_validity / cross_day / api_health / business_smoothness / copy_day）抽到独立可 import 模块，每个门禁返回 `(ok, reason)`，统一入口 `run_all()` 任一失败 → 自动标 `data_quality_flag=likely-wrong` + POST 飞书 webhook。webhook URL 走 env `FEISHU_WEBHOOK_URL`（未设静默跳过，graceful degrade；网络异常不抛错不影响主采集流程）。`dmp_master.py` 在 `run_items_module` happy-path 和重试路径都集成调用。新增 `scraper/.env.example` 含申请指南。`tests/test_sanity_check.py` 48 个单测全过（含 webhook mock + 18 行 likely-wrong 复现场景）。
- **DMP 脏数据前端默认隐藏（A1：quality_flag 透传 + 过滤）** — 5/28 18 行 likely-wrong 脏数据在 4 个 tab 仍展示的问题修复。后端 `_load_data3` 显式读 `data_quality_flag` 列（缺列/缺值默认 `legacy` 向后兼容），`_compute_product_assets` / `_compute_other_product_assets` / `_compute_product_assets_daily` 在 item 中透传 `quality_flag` 字段；`contracts/asset.py` `ProductAssetWeek` 加 `quality_flag: str = 'legacy'` 带默认值。前端 `marketFocus.ts` `ProductAssetWeek` 加 `quality_flag?: string` 可选；`ProductAssetsTab` / `OtherProductAssetsTab` 整周过滤（任一产品该周 likely-wrong → 跳过整周），新增 `findLatestVisibleIndex()` 保证本周对比基线用最后一条已过滤的真实周；`StoreAssetsTab` 新增 `visibleWeeks` computed 预留过滤（当前 data2.csv 无 flag 列 noop）。`vue-tsc --noEmit` exit 0；backend pytest 153/8 仍过。
- **QW4 ETL 埋点 + Mac partial baseline（阶段 A 阻断式交付）** — 按 [[project_etl_perf_plan]] 阶段 A 阻断式约束，baseline 出来前不开任何 P0/P1 优化。新增 `scripts/etl/perf.py` 提供 `PerfTimer` 上下文管理器（6 道门禁：date_sanity / cross_day / api_health / business_smoothness / copy_day / wall_time_stdev），埋点覆盖 `run_etl.py`（etl_total try/finally）+ `cli.py`（8 个 --update 子步）+ `pipeline.py`（11 个子步骤）+ `load.py`（filter_rolling_window + upsert_to_duckdb）+ `transform.py`（match_channel 含 P4 关键词循环 + clean_data）。新增 `scripts/etl/report_baseline.py` 解析 baseline JSON 输出人类可读报告。`scripts/etl/baselines/baseline_2026_06_02.json` 包含 Mac 第 1 次 partial 实测（9/15 步骤 / 14m00s / 6 门禁 5 pass + 1 skipped），用 `_save_partial` 中间落盘保证中断不丢。剩余 5 次 baseline 跑批（Mac ×2 + Windows ×3）按用户指令留 TODO 后续会话补齐。
- **QW0-baseline 严格按 HANDOFF §6 + plan §A4.1 修正** — 修 6 个差异点：① `scripts/etl/perf.py` 重命名为 `_timer.py`（更准的命名 + 区分其他 perf 工具）；② `preload_rfm.py` 加 perf_counter 埋点（hot spot #1 — 540 组合串行循环 = 25min 估时）+ `etl_status_override.py` 同样加埋点（hot spot #5 — 66 次 N+1 DELETE = 3min 估时）；③ baseline.json 路径 `scripts/etl/baselines/` → `data/processed/etl_perf/`（跟其他产物统一目录，不在 .gitignore）；④ JSON schema 扩展 7 字段（`version=1.0` / `git_sha` / `runs[]` 数组 / `per_step[].cpu_sec` / `rss_peak_mb` / `duckdb_alloc_mb` / `spill_to_disk_mb`）；⑤ baseline 跑批输出用 `python3 -u` unbuffered 避免上次 0 字节 log 问题；⑥ baseline save 改 `run_id-only dedup`（之前 run 1 partial + run 2 完整因 dedup 用了 `run_id+started_at` 复合键，agent 第二次错调 save_baseline 触发清空）。**1/3 Mac baseline 真实跑批完成**：wall=180.2min（远超 plan 估的 25-41min，preload_rfm 540 组合串行占 ~89%），cpu_time=10628s, rss_peak=7.4GB, duckdb_alloc=8GB, spill=0；6 门禁 pass=5 + skipped=1（单次 wall_time_stdev 不算）。剩余 5 次 baseline（Mac ×2 + Windows ×3）+ median 计算 留 Phase 2。`pytest backend/tests/` 153/8 + `tests/test_sanity_check.py` 48 全过；`ruff check .` 0 errors。P0（QW1/2/3/5）可以开。

### Fixed
- **RFM 缓存写路径绕开 read_only 单例（QW2 Phase 2）** — `backend/services/health/rfm_analysis/cache.py` 4 个写路径（`_ensure_db_cache_table` DDL / `_read_db_cache` 损坏清理 DELETE / `_write_db_cache` INSERT OR REPLACE / `precompute_rfm_cache` 预计算）从 read_only 单例改用独立写连接 `_open_write_conn()`（`duckdb.connect(..., access_mode=READ_WRITE)` 短生命周期）。修 ETL Step 6 "预计算 RFM 8象限历史周期缓存" 时 "Cannot execute CREATE on read-only database" 错误。**关键约束**：① `precompute_rfm_cache` 必须先 `_open_write_conn()` 再做其他操作（同进程内 DuckDB 不允许 read_only 单例已建后再开 read_write 写连接，会报 "Can't open a connection to same database file with a different configuration"）；② uvicorn 进程（read_only 单例已锁定）调 `_write_db_cache` 优雅降级为 warning（不影响 API 返回，cache 由 ETL 预计算填充）；③ 移除 `_write_db_cache` 冗余 `conn` 参数（内部开写连接），更新 `analysis.py` 调用方。pytest backend/tests/ 153/8 + tests/test_sanity_check.py 48 全过；ruff check . 0 errors。
- **DMP 单品资产 result 缓存不感知 mtime 变化** — `dmp_asset_service` 的 `result`/`result_other` 缓存按 `_weeks` 单字段 key 缓存，`_check_reload` 只刷 `mtime`+`df` 不动 result 缓存，导致 work plat 更新 `data3.csv` 后前端的"单品资产"tab 仍显示旧周。修复分两步：① `product.py`/`other.py` 缓存判断前先调一次 `_load_data3()` 让 mtime check 有机会跑；② `_helpers._load_data3` 检测到 mtime 变化时连带清掉 `result`/`result_other`。新增 `test_dmp_asset_cache.py` 4 个 regression test 覆盖。
- **scraper/ 20 个 pre-existing lint 错误治理** — 物理合并 work plat → scraper/ 时把 scraper/ 临时加到 ruff exclude，本次治理完成。`ruff --fix` 自动修 9 个（F841 / F401 / F811 / F541）+ 手动修 11 个（E402 ×6 加 `# noqa: E402` 保留 sys.path.insert 后 import 的有意设计，F401 ×2 删 unused imports，F841 ×2 删 dead code）+ `pyproject.toml` 移除 `scraper/` from exclude 重新纳入 ruff 检查。pytest 201 passed（backend 153/8 + sanity_check 48）。下阶段 P0（QW1/2/3/5）可以开。

### Changed
- **Monorepo 化：物理合并 work plat/DMP_test_package → `fuqing-crm-analytics/scraper/`** — 按"方案 B"（Q0 业务价值调研后采纳）合并 scraper 代码到 monorepo。`backend/config.py` DMP_DATA_DIR 默认值改为 monorepo 相对路径 `scraper/core`（`.env` 环境变量仍可覆盖，向后兼容 work plat 旧位置）。`pyproject.toml` ruff 临时排除 `scraper/`（原 DMP_test_package 19 个 pre-existing lint 错误不在本次范围，留到 task 14 "work plat 6 道门禁 + 飞书 webhook" 阶段统一治理）。数据物理迁移（work plat/core/data2.csv 等）未做，下次 checkpoint 单独进行。Q0 调研报告：见 `docs/dmp-poc/达摩盘官方API评估报告v1.0.md`。
- **数据物理迁移：work plat/core/data*.csv → scraper/core/data*.csv** — `data2.csv` (56711B/760行)、`data3.csv` (580572B/7044行)、`data.csv` (130667B/2273行) 全部从 work plat 旧位置搬到 monorepo 内的 `scraper/core/`。`.env` DMP_DATA_DIR 同步更新。work plat 旧位置已空，scraper/core 是唯一数据源。uvicorn 重启后 service 层 3 个 tab 全部 05/25-05/31 正常。

### Fixed
- **DMP_DATA_DIR 空字符串 fallback bug** — `backend/config.py:120` 之前用 `Path(os.environ.get("DMP_DATA_DIR", str(_DEFAULT_DMP_DIR)))`，当 `.env` 设 `DMP_DATA_DIR=`（空字符串）时 `os.environ.get` 返回空字符串不会 fallback 到默认值，`Path("")` 解析为 `Path(".")` 当前目录。改为先 `.strip()` 再判空，空则用 monorepo 默认 `scraper/core`。

## [0.3.4] - 2026-06-01

### Fixed
- **ETL 增量主键冲突** — 修复 `upsert_to_duckdb` 在 shop+member 合并数据时（高度重叠场景）写入 DuckDB 触发主键约束违反的 bug。修复：在去重前将 `order_id`/`sub_order_id` 统一转为字符串（防 float vs string 漏判），全新订单路径改用 staging 表 + ON CONFLICT DO NOTHING 模式，刷新路径在事务内通过 staging 表 + ROW_NUMBER() 去重后再写入，保持原子性。

### Changed
- **CLAUDE.md 加改代码前强制自检段** — 防止 AI 在 main 分支直接改代码的反模式。改 Edit/Write 前先答 2 问：当前在哪个分支？接下来要 commit 吗？

### Performance
- **Parquet缓存修复** — 修复 `_mark_all_files_processed` 只存mtime不存hash的bug，统一Parquet缓存key格式，增量ETL时间从10分钟降到1分钟
- **RFM SQL重写** — 合并 `hist_customers_all` + `hist_customers_same` 为单个CTE，使用GROUPING SETS消除TTL CTE，CTE数量从15个减少到5个
- **品类GROUPING SETS** — 品类预计算从4次独立查询优化为2次GROUPING SETS查询，扫描次数减少50%
- **RFM并行化** — 使用ThreadPoolExecutor并行执行3个周期查询，3x加速
- **DuckDB内存优化** — 添加 `DUCKDB_MEMORY_LIMIT` 环境变量配置（默认8GB），创建内存监控模块，避免Swap
- **内存监控** — 新增 `backend/db/memory_monitor.py` 模块，实时监控DuckDB内存使用，防止Swap

### Security
- **弱密码替换** — `admin:123456` / `fqsw:fqsw888` 替换为强密码，使用 bcrypt 哈希存储
- **API Key Header 传输** — `/config/history` 和 `/config/audit-log` 的 API Key 从 Query 参数改为 `X-API-Key` 请求头，防止日志泄露
- **API Key 时序攻击防护** — `!=` 比较改为 `hmac.compare_digest()` 常量时间比较
- **API Key 速率限制** — 新增滑动窗口限速（10次/5分钟/IP），防止暴力枚举
- **SQL 参数化** — `rfm_category_drilldown.py` 中 `rfm_segment` 和 `exclude_channels` 从字符串拼接改为 `?` 占位符参数化查询

### Performance
- **overview 查询合并** — `get_overview_metrics()` 从 9 次独立查询合并为 3 次（每个时间段 1 次 CTE），减少 66% 数据库往返
- **geo 趋势查询合并** — `get_geo_trend()` 从逐月循环 N 次查询改为 2 条 SQL（`DATE_TRUNC('month')` 一次性查出）
- **flow groupby 优化** — `get_flow_matrix()` 和 `get_flow_sankey()` 从 121 次 DataFrame 过滤改为 `groupby().size()` 一次性聚合
- **churn 时间窗口** — 4 个流失分析函数添加 730 天回溯窗口，避免全表扫描 + `LAG()` 窗口函数

### Changed
- **DuckDB 单例连接** — `get_connection()` 从每次请求新建连接改为全局单例 + `threading.Lock` 双重检查锁定
- **Router 分层修复** — 9 个 router 文件不再直接导入 `backend.semantic.time`，改为通过 `backend.services` 导入
- **代码去重** — 统一 `_normalize_date`（3→1）、`_segment_meta`（2→1）、`_VALID_BASE`（6→1）
- **RFM flow 引擎** — `r_flow.py` / `f_flow.py` / `m_flow.py` 从各 ~377 行简化为 ~58 行，共享逻辑提取到 `_flow_engine.py`
- **suggestions.py 常量迁移** — `R_INTERVALS`、`GSV_AMOUNT_COL`、`REPURCHASE_ADJUSTMENT` 迁移到语义层/配置层
- **应用关闭事件** — `main.py` 注册 `shutdown` 事件调用 `close_connection()`

### Fixed
- **RFM flow engine 参数错位** — `_flow_engine.py` 的 `hist_all_params` 缺少 `exclude_channels` 参数，导致 SQL 占位符与参数不匹配，当用户选择排除渠道时 RFM 流转看板返回 500 错误
- **路由守卫 401 闪现** — 前端路由守卫在 `isReady` 为 `false` 时直接放行，未登录用户可短暂访问受保护页面导致 401 请求。修复：在等待 `isReady` 之前直接检查 `sessionStorage` 中的 token
- **DuckDB 并发崩溃** — `get_connection()` 仅锁创建过程，未锁查询执行。页面刷新触发多个并发 API 请求时，多线程同时访问同一 DuckDB 连接导致 `fetchone()` 返回 `None`（`TypeError: 'NoneType' object is not subscriptable`）或 Python 进程段错误退出。修复：`connection.py` 引入 `ThreadSafeConnection` + `ThreadSafeCursor` 包装器，`execute()` 和 `fetch*` 自动串行化
- **DuckDB 结果集并发覆盖** — `ThreadSafeConnection.execute()` 只在执行 SQL 时加锁，返回 `ThreadSafeCursor` 后锁已释放。DuckDB 没有真正独立的 cursor（`execute()` 结果集绑定在连接上），另一个线程的 `execute()` 会覆盖连接上的结果集，导致 `fetchone()` 读到错误数据（如 `int(datetime.date)` 崩溃）。修复：`ThreadSafeCursor` 在构造时（锁内）预取全部结果到内存，后续 `fetch*` 不再触碰连接
- **fetchone() 空值防御** — `overview.py`、 `rfm_reader.py`、 `cache.py` 共 4 处 `fetchone()[0]` 未防御 `None` 结果，在连接异常时直接崩溃。修复：先判空再取下标
- **老客GSV占比 pp 值双重乘法** — `HealthOverviewTab` 中 `fmtYoy()` 已乘 100，`MetricCard` pp 模板再乘 100，导致显示 155pp/193pp。新增 `fmtPpt()` 直接传递原值
- **YOYBadge 单位显示错误** — `AudienceView` 中 ratio 类型列（新客占比/老客占比/会员占比等 YoY）未传 `unit='pp'`，导致显示 `%` 而非 `pp`。10 处 YOYBadge 调用修正为 `(value * 100, unit: 'pp')`
- **173 个 ruff lint 错误** — 修复 F821（未定义变量 6 个）、F401/F541/F811/E401（自动修复 130 个）、E702/E722（手动修复）。config.py 交叉导出加 `# noqa: F401` 防 ruff 误删
- **ETL 导入路径错误** — `scripts/etl/cli.py` 中 4 处导入路径错误导致 ETL Step 3-7 崩溃：`scripts.etl_status_override` → `scripts.etl.etl_status_override`（3处），`scripts.preload_rfm` → `scripts.etl.preload_rfm`（1处）
- **日趋势图会员占比** — 修复日趋势图的会员占比从「订单数占比」改为「GSV金额占比」，与人群看板一致。新增 `overall_member_ratio` 字段返回整体会员GSV占比
- **YOY/MoM 值格式不一致** — 修复后端返回的 YOY/MoM 值格式不一致（部分已是百分比，部分是小数），导致前端显示 155pp 等三位数。所有值统一为小数形式

### Changed
- **CLAUDE.md 瘦身** — 460 行 → 132 行（-71%），参考材料（口径表/历史教训/包拆分清单/目录结构）移到 `docs/reference.md`（按需读取），每次会话节省 ~60% token
- **文档精简** — 归档 5 个冗余/已完成文档：DESIGN.md、DEPLOY.md、MODULE-INDEX.md、etl-incremental-fix-plan.md、REPAIR_PLAN.md

### Added
- **Pre-commit/Pre-push hooks** — `.githooks/pre-commit`（ruff check）和 `.githooks/pre-push`（pytest）阻止不合规代码提交和推送
- **GitHub Actions CI** — `.github/workflows/lint.yml` 在 PR 和 main push 时自动运行 ruff + pytest
- **AI 执行检查点** — CLAUDE.md 新增硬性 STOP 检查表：commit 前必须 review、push 前测试全绿、merge 前必须 qa
- **CI/CD 防线** — pre-commit (ruff) + pre-push (pytest) + GitHub Actions CI，三层拦截不合规代码
- **Parquet 缓存填充脚本** — 新增 `scripts/etl/fill_parquet_cache.py`，将 161 个 xlsx 文件批量转换为 Parquet 缓存，增量 ETL 加速 10-50x
- **原子写入** — `_save_parquet_cache()` 和 `_save_processed_files()` 支持 tmp+rename 原子写入，防止中断产生损坏文件
- **Parquet 缓存测试** — 新增 9 个测试覆盖 Parquet 写入、增量检测、原子写入、processed_files 更新等核心逻辑

### Fixed
- **processed_files 覆写** — `fill_parquet_cache.py` 保存时合并已有记录，避免丢失历史 ETL 状态
- **单元测试全覆盖** — 新增 91 个测试覆盖 12 个模块：breakdown_service（15）、rfm_service（16）、rfm_analysis（8）、health/overview（19）、health/conversion（7）、health/repurchase（2）、health/tier_flow（1）、health/channel_scores（1）、category_service/overview（4）、category_service/distribution（1）、category_service/churn（1）、category_service/basket（1）
- **R 区间边界测试** — 验证 `_get_r_interval_current_distribution` 的 R 区间分桶（30/90/180/365/730 天）和 F 段（F>1/F=1）正确性
- **GSV 口径测试** — 验证退款订单（is_refund=TRUE）、购物金（is_goujinjin=TRUE）、交易关闭订单不计入 GSV
- **Codex 交叉审核** — 使用 Codex regular + adversarial 模式审核代码变更，发现并修复 5 个问题

### Fixed
- **check_future_date(None) 崩溃** — `backend/semantic/time.py` 的 `check_future_date()` 在 mtd/wtd/ytd 模式下接收 None 参数时触发 TypeError。修复：函数入口加 `if date_str is None: return None` 守卫，except 加 `TypeError`
- **日期正则不验证日历** — `re.fullmatch(r'\d{4}-\d{2}-\d{2}')` 接受无效日期如 2025-02-30。修复：regex 后加 `datetime.strptime` 验证实际日期有效性
- **visitor.py 未使用 import** — 删除 `backend/routers/visitor.py` 中未使用的 `import json`
- **品类回购分析数据为 0** — `_RFM_SEGMENT_ORDER`（`category_service/_shared.py`）与 SQL `rfm_segmented` CTE 的 RFM 象限命名不一致：常量定义了 4 个无"客户"后缀的名称（如 `"重要价值"`），而 SQL 生成 8 个带后缀的名称（如 `"重要价值客户"`）。`api.py` 的 `_build_rows` 用旧名称查找 SQL 结果 → key 不匹配 → 所有数值归零。修复：`_RFM_SEGMENT_ORDER` 更新为 8 个带"客户"后缀的完整象限名称。`/category/repurchase-flow` 接口现已正确返回品类各 RFM 象限回购数据（hist/repurchased），可通过 `curl http://localhost:8000/api/category/repurchase-flow` 验证
- **Lint 清理** — 消除 `rfm/r_flow.py`、`rfm/m_flow.py`、`rfm/f_flow.py`、`rfm/segment_orders.py` 的 F403/F405 star import（117 errors → 0）；清理 `routers/__init__.py` 16 个 F401 unused import；删除死代码 `breakdown_service.py` shim；修复 `rfm/_shared.py`/`export_service.py`/`metrics/__init__.py` 等多处 F401；E701/E741 若干
- **Lint 清理（续）** — `category_service/flow/__init__.py`、`category_service/flow.py`、`category_service/repurchase/__init__.py`、`category_service/repurchase.py` 消除 F403 star import；删除死代码 `dmp_asset_service.py` shim；`dmp_asset_service/__init__.py` 改为显式导入；`health/rfm_analysis/__init__.py`、`health/rfm_analysis.py` 消除 F403

## [0.3.3] - 2026-05-29

### Fixed
- **SQL 注入修复** — `breakdown_service/_shared.py` 4 个函数将日期参数从 f-string 拼接改为 DuckDB `?` 参数化；`_r_interval_sql` 内部 `DATE '{cutoff}'` 也改为参数化
- **硬编码路径修复** — `VISITOR_XLSX_FILE` 从 Mac 绝对路径迁移到 `backend/config.py` 的环境变量配置

### Changed
- **开发者体验** — `/docs` 和 `/redoc` 从认证中间件白名单移除，新开发者可直接浏览器探索 API
- **未来日期警告** — 传入未来日期时，API 在 `X-Data-Warning` 响应头返回明确警告（`backend/semantic/time.py` 的 `check_future_date()`），覆盖 `/overview`、`/targets`、`/repurchase-cycle`、`/value-tiers`、`/tier-flow`、`/rfm-analysis`、`/rfm-category-drilldown`、`/channel-health-scores`、`/new-customer-conversion`、`/r-flow`、`/f-flow`、`/m-flow`、`/segment-orders` 等 13 个端点

## [0.3.2] - 2026-05-28

### Fixed
- **后端代码审计** — 修复 23 个问题（P0×5/P1×7/P2×11），包括口径不一致、测试阈值硬编码、contracts 重复、类重复定义等
- **大文件拆分** — 将 6 个超大文件拆分为包（rfm_service/flow/breakdown/dmp_asset/repurchase/rfm_analysis），并补全所有交叉导入
- **SPU 版本化** — orders 表新增 `spu_hash` 字段，避免 SPU 重命名导致历史数据不可追溯
- **Bundle 优化** — xlsx 依赖改为懒加载，减少首屏 bundle 体积

### Added
- **ETL Parquet 缓存层** — 中间计算结果写入 parquet，减少重复计算
- **前端性能基线** — 建立性能 benchmark，便于回归检测

## [0.3.1] - 2026-05-27

### Changed
- **Docker 化就绪** — 后端支持 Docker 部署
- **磁盘清理** — data/ 目录清理，释放 7.7G 空间

## [0.3.0] - 2026-04-20

### Added
- **Vue3 前端上线** — 8 个 dashboard 页面，SPA 路由，xlsx 导出
- **RFM 8 象限重构** — 区间流转 + 品类下钻完整实现

## [0.2.0] - 2026-04-16

### Added
- **语义层 + 契约层** — v3.0 架构重构，口径统一管理
- **DuckDB 数据平台** — 1030 万订单 / 410 万用户数据接入

## [0.1.0] - 2026-03-27

### Added
- **项目启动** — 基础架构设计，FastAPI 后端框架搭建

---

## 版本说明

本项目使用 **semver** 格式：`MAJOR.MINOR.PATCH`

| 字段 | 含义 |
|------|------|
| MAJOR | 不兼容的 API 变更（如删除端点、修改 Schema） |
| MINOR | 向后兼容的新功能（如新增端点、新增响应字段） |
| PATCH | 向后兼容的缺陷修复（如 BugFix、安全补丁） |

> 注意：当前 MAJOR = 0 表示项目仍在初始开发阶段，API 可能在 MINOR 版本中变化。
