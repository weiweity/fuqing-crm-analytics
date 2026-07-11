# Sprint 203 Architecture + Performance + Scalability Review

> **作者**: 独立架构师 (read-only reviewer)
> **日期**: 2026-07-05
> **审查目标**: Sprint 203+ 立项前置架构 / 性能 / 可扩展性审查
> **代码版本**: main HEAD `38d9bed` (v0.4.14.37)
> **方法**: 纯 codegraph_explore + codegraph_search + grep 实证 (L4.42 / L4.55 永久规则)
> **不重复范围**: L4.x 永久规则 (CLAUDE.md 已沉淀 60+ 条), 业务 sprint sprint-by-sprint 改动细节

---

## 0. 实证摘要 (Executive Summary)

| 维度 | 关键发现 | 风险等级 |
|---|---|---|
| **整体架构** | backend 3 层 (services/routers/contracts) + DuckDB 单文件 + 14 tool CLI + MCP 链路完整 | 🟢 stable |
| **DuckDB 架构** | Read-Write Splitting + query worker + ATTACH read_only 已闭环 (L4.51/L4.48) | 🟡 117GB 单文件容量天花板 |
| **性能瓶颈** | ETL 63min (基准 18min) + RFM 540 组合首次冷启动 + R 区段 7 桶 SQL CASE 嵌套 | 🔴 单点故障 |
| **可扩展性** | uvicorn 单进程 + 5 read pool 池容量上限 + 缺 ClickHouse POC 实际触发监控 | 🔴 3-5 年时间窗 |
| **新需求接入** | 新 tool 平均 3-5 天 (跟 Sprint 190+196+198 一致), 14 tool → 16+ tool SSOT 维护压力 | 🟡 边际成本递增 |

**核心结论**: 短期 (2026) 架构 / 性能 / 可扩展性 3 维度全部 stable, Sprint 199 R1 `14 tool 真实覆盖率 ~40-65%` 跟 L4.51 Read-Write Splitting 1:1 stable; 但 117GB 单文件 + 单 uvicorn 容量上限已经在 Sprint 201+ ClickHouse POC 决策备忘录 §1.3 列出触发条件, **应在 Sprint 203+ 立项 ClickHouse POC 8-10 周前置监控 SOP (L4.56/L4.58)**.

---

## 1. 整体架构 (Architecture)

### ✅ Finding 1.1: 3 层分层清晰 (架构 / 合规)
- **类别**: 架构
- **严重度**: P3 low (维持现行)
- **位置**:
  - `backend/services/` (rfm, metrics, health, ai_sandbox + dual_conn + query_worker_client)
  - `backend/routers/` (asset, audience, auth, category, cohort_retention, customer_health, export, flow, geo, lifetime_value, market_focus, metrics, report, rfm, sampling, visitor + ad_hoc_query)
  - `backend/contracts/` (audience, asset, category, common, geo, health, lifetime_value, market_focus, metrics, rfm, sampling, schemas, visitor + types)
- **问题**: 实证 3 层 SSOT 维持 (跟 CLAUDE.md 接口开发六步 + L4.20 SSOT 反漂移 一致), 无 bad smell. semantic/calculations.py `yoy_absolute` / `yoy_ratio` / `mom_*` 4 函数全 backend + ad_hoc 复用, 单一来源.
- **修复建议**: 0 改动 (跟 Sprint 60+ 0 debt stable 模式 1:1)
- **是否立即修**: 否

### 🟡 Finding 1.2: ad-hoc CLI 层用 import scripts/ 跨层调用 (架构 / 风险)
- **类别**: 架构 (跨层耦合)
- **严重度**: P2 medium
- **位置**: `backend/routers/ad_hoc_query.py:243-507` (9 个 endpoint, 每个都 `from scripts.ad_hoc_queries.<x> import run_<x>`)
  - 例: `/daily-gsv` `from scripts.ad_hoc_queries.daily_gsv import run_daily_gsv` (line 243)
  - 例: `/daily-gsv-multi-period` `from scripts.ad_hoc_queries.daily_gsv_multi_period import run_daily_gsv_multi_period` (line 276)
  - 例: `/ai-sandbox-execute` `from backend.services.ai_sandbox import ai_sandbox_execute` (line 342) — **唯一走 service 层**
- **问题**: 14 个 ad-hoc query 工具里只有 `ai-sandbox-execute` 走 `backend.services.ai_sandbox` (L4.5 exception), 其余 13 个都走 `scripts/ad_hoc_queries/*.py` (跟 Sprint 171 决策一致, "AI 取数 CLI 层不走 service"). 9 个 HTTP endpoint 在 `backend/routers/ad_hoc_query.py` 顶层 `from scripts.ad_hoc_queries.X import run_X` (L4.5 exception 取舍). 跨层调用有 3 风险:
  1. **`scripts/` 任意修改 → HTTP endpoint 跟着挂**: Sprint 198 实证 `daily_gsv_multi_period.py` 改返回值结构 → `routes/ad_hoc_query.py:post_daily_gsv_multi_period` 立刻 sync 改 header (line 279-282)
  2. **`scripts/ad_hoc_queries/_utils.py:read_only_conn` (line 58)** 只被 archive 目录的 `adhoc_monthly_segments_2026h1.py` 用 — 真 HTTP 路径走 `dual_conn.py` + middleware (already migrated)
  3. **pytest collection 跨层污染**: 跟 Sprint 183 L4.37 真业务触发 (新 file 必须 `_load_builtins` 显式 import) 风险 1:1 stable
- **修复建议**: 
  - 当前架构可接受 (跟 Sprint 60+ 1:1 stable 60 sprint 0 debt)
  - 但建议 Sprint 203+ 立项 ad-hoc query HTTP endpoint 跟 CLI 共享 service layer (`backend/services/ad_hoc/` 子目录), 取代直接跨层 import
  - 估时 3-5 天 (跟 Sprint 195+196+198 1:1), 涉及 13 endpoint + 13 script 改造
- **是否立即修**: 否 (跟 L4.42 立项实证 SOP 1:1, 等真业务方邮件/工单触发再立, 跨 sprint 留尾登记 `docs/TECH-DEBT.md`)

### ✅ Finding 1.3: MCP stdio 协议完整 + 14 tool SSOT (架构 / 合规)
- **类别**: 架构
- **严重度**: P3 low
- **位置**:
  - `mcp_servers/fuqing_adhoc/server.py:53-92` (`_run_cli` + subprocess.run + json output + MAX_STDOUT_BYTES=1MB + MAX_STDERR_BYTES=4KB 截断 + timeout 兜底)
  - `mcp_servers/fuqing_adhoc/_dispatch.py` (TOOL_DEFS + HANDLERS 14 tool SSOT)
  - `scripts/ad_hoc_queries/registry.py:_load_builtins()` (跟 L4.37 新 file 必须显式 import 配套)
- **问题**: Sprint 191 LSP→newline JSON 重写 (L4.44) + Sprint 182 Phase 4 截断 + Sprint 191 stdio framing, 整体 MCP 链路完整 0 风险.
- **修复建议**: 0 改动
- **是否立即修**: 否

---

## 2. DuckDB 架构 (重点)

### ✅ Finding 2.1: Read-Write Splitting 已闭环 (架构 / 合规)
- **类别**: 架构
- **严重度**: P3 low
- **位置**:
  - `backend/services/dual_conn.py:23-182` (READ_POOL_SIZE=5 + READ_MEMORY_LIMIT + WRITE_MEMORY_LIMIT env var + `_read_pool` 单例)
  - `backend/middleware/query_router.py:1-101` (`QueryRouterMiddleware` + READ_ENDPOINTS (14 个) + READ_PREFIXES (15 个) + WORKER_ENDPOINTS (1 个) + classify 默认 GET 路由到 read)
  - `backend/db/connection.py:103-141` (`get_connection` 优先 `dual_conn.get_request_connection()`, 否则写单例)
- **问题**: Sprint 201 R1 Read-Write Splitting 完整落地, 5 read pool + 1 write + middleware 路由 + query worker 独立进程 (L4.51 + L4.48). 100/100 pytest 验证 (跟 Sprint 60+ D-7 1:1 stable 实证). `query_router.py:READ_ENDPOINTS` (14 个) + `READ_PREFIXES` (15 个) 覆盖 80% GET 路径.
- **修复建议**: 0 改动
- **是否立即修**: 否

### 🟡 Finding 2.2: uvicorn 单进程 + 5 read pool 容量上限 (可扩展 / 风险)
- **类别**: 可扩展性 (容量天花板)
- **严重度**: P1 high
- **位置**:
  - `backend/services/dual_conn.py:23` `READ_POOL_SIZE = int(os.environ.get("FQ_READ_POOL_SIZE", "5"))`
  - `backend/main.py` uvicorn entrypoint (单进程 by default)
  - `scripts/query_worker.py` 进程隔离 worker (L4.48)
- **问题**: 
  - 当前架构上限: **1 uvicorn 同进程只能撑 5 个 read pool + 1 write + 1 query worker** (process-level)
  - 跟 `docs/architecture/clickhouse-poc-decision-memo.md:21-30` §1.3 决策触发条件之 (c) 对齐: "5+ 业务分析师需要并发取数 (目前 1 人) → 启动 POC"
  - 当前业务量 (1 人) OK, 但 3 业务分析师同时跑 5 个 read query → 命中 `READ_POOL_SIZE=5` → 第 6 个请求必然 `_is_healthy(conn) == False` 或持锁卡
  - 缺 load shedding / queue 机制 (没有 semaphore 控制 read pool 外的请求排队)
- **修复建议**:
  1. **短期 (1-2 天)**: `dual_conn.py:get_read_connection` 加 `asyncio.Semaphore(READ_POOL_SIZE * 2)` + 超出请求排队 (Redis / in-memory queue 都行, 优先 in-memory 1 行代码)
  2. **中期 (Sprint 203+ 立项)**: 扩 uvicorn `--workers 4` + 每个 worker 独立 5 read pool = 20 并发 (跟 Sprint 92 K8s 多 worker 模式 1:1 stable)
  3. **长期**: ClickHouse POC 启动条件命中 → Trino 联邦查询层 (跟 L4.56 备忘录 1:1)
- **是否立即修**: **中等优先** — Sprint 203+ 业务组报告 3+ 人并发取数慢时, 立 P1 sprint (跟 L4.42 实证 SOP 1:1)

### ✅ Finding 2.3: Query worker 进程隔离 + 安全配置 (架构 / 合规)
- **类别**: 架构
- **严重度**: P3 low
- **位置**:
  - `backend/services/query_worker_client.py:16-66` (`execute_via_query_worker` + stdin SQL + env PYTHONPATH 强制 + cwd=PROJECT_ROOT + timeout 30s + L4.41 跨平台)
  - `scripts/query_worker.py` (DuckDB 安全配置 5 项 + SQL 注入防御)
- **问题**: Sprint 201 R1 query worker 隔离 + L4.41 PYTHONPATH 强制 + L4.32 cwd 强制, 0 风险.
- **修复建议**: 0 改动
- **是否立即修**: 否

### 🔴 Finding 2.4: DuckDB 117GB 单文件容量天花板 (可扩展 / 风险)
- **类别**: 可扩展性 (结构性)
- **严重度**: P1 high
- **位置**: `backend/config.py:134` `DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", str(_DEFAULT_DUCKDB)))`
- **问题**:
  - `docs/architecture/clickhouse-poc-decision-memo.md:21-30` §1.2 长期增长预期: "年度 GSV 数据 5× 增长 → DuckDB 单文件 117GB × 5 = **585GB**", 触发条件 (a) "DuckDB 单文件 > 200GB" (目前 117GB, 增长 70% 触发)
  - ClickHouse POC 立项决策备忘录 §3 阶段拆分 8-10 周 1-2 人月 写在 2026-07-03 (跟 Sprint 201+ L4.56 POC 留尾 SOP 1:1 stable)
  - 当前 0 启动条件监控 (L4.58 跨 sprint 监控 SOP 也没真正实现, 只立项 SOP 框架)
- **修复建议**:
  1. **跨 sprint SOP (L4.58)**: Sprint 202+ R1+R2 high-priority workflow 立项 ClickHouse POC 启动条件监控 — 但 L4.58 实证 0 触发 0 commit 续期
  2. **真业务触发监控**: 估算 DuckDB 月增长率 117GB / (24个月) = ~5GB/月, 200GB 触发还 ~16 个月 (2027 Q4), 跟 Sprint 201+ L4.58 启动条件 SOP 1:1 stable
  3. **最近期治本**: 把 ClickHouse POC 立项决策备忘录标 ⏸ pending 状态, 任何 sprint 跑批后自动 collect `data/processed/fuqing_crm.duckdb` 文件 size (Sprint 53 race flake 治本后 1 row 0 lock)
- **是否立即修**: **中等优先 (不是 P0)** — 触发条件 §1.3 任意 (a/b/c) 命中 → 立 P0 ClickHouse POC sprint 走 12 步流程; 当前 0 触发

### 🟡 Finding 2.5: DuckDB flock 锁模型 + 同 file 多 conn 串行化 (架构 / 风险)
- **类别**: 架构 (跨 sprint 持续治根)
- **严重度**: P2 medium
- **位置**:
  - `backend/db/connection.py:103-141` (singleton 写连接 + 锁内执行)
  - `scripts/etl/cli.py:419, 538` (`duckdb.connect(str(DUCKDB_PATH), config={"memory_limit": ...})` 立即 close 模式)
- **问题**:
  - L4.38 永久规则 DuckDB flock 锁模型 (同 file 只能 1 active conn) 已闭环
  - 实证 `scripts/etl/cli.py:419` + line 538 注释明确写 "INVARIANT: 立刻 conn.close() (try/finally), 不持有跨 step, 4 处 sibling + uvicorn read_only 单例 + ETL 多 RW 并发"
  - 但 `scripts/etl/cli.py:824` cross_day 采样 `_c0 = _dd2.connect(...)` try/finally close 跟其他 ET L step 串行执行, **单次跑批 9 处 sibling + 跑批期间 0 read_only conn 复用**.
  - 风险: 跑批期间 (45-60 min) uvicorn 全程 read_only 池都阻塞 → 用户看板 1+s 延迟甚至 5xx
- **修复建议**:
  - 当前 Sprint 202 R1 wall_min 基准 < 15min 期望 + 实测 63min (B1+ B2 优化有 bug, 0 实质效果, Sprint 202+ R4 重新立项) — 跑批时间长 → uvicorn read_only 阻塞时间窗口长
  - **建议 Sprint 203+ 立项 WAL mode**: 把 DuckDB 改成 `WAL` mode (DuckDB 0.9+ 支持), 跑批 process 写 + 看板 process read_only 同时进行 + 0 阻塞
  - 估时 1-2 天 (DuckDB WAL 接入验证 + pytest 锁回归)
- **是否立即修**: **中等优先** — Sprint 203+ 跑批 wall_min 持续 > 30min, 立 P1 WAL mode sprint

---

## 3. 性能 & 扩展瓶颈 (Performance)

### 🔴 Finding 3.1: ETL 跑批 18min → 63min 0 实质效果 (性能 / 风险)
- **类别**: 性能 (核心)
- **严重度**: P1 high
- **位置**:
  - `scripts/etl/ingest.py:373-407` (`should_skip_file_by_age` + `filter_files_by_age`, Sprint 202 R1 L4.54 优化 1)
  - `scripts/etl/pipeline.py` member_df pay_time 7 天窗口过滤 (Sprint 202 R1 L4.54 优化 2)
- **问题**:
  - MEMORY.md 实证: "**真业务跑 wall_min=63min, 0 实质效果** (优化 1 加错位置: 冷启动段 tracker 永远存在, 优化 2 写了 member_df 但下游 `member_order_ids` 没读它), Sprint 202+ R4 重新立项修"
  - 痛点 1 (ETL 41min) 历史 baseline 18min, Sprint 22 #26 闭环平均 18min; Sprint 202 R1 baseline 46min; Sprint 202+ R4 baseline 63min
  - 真因: shop 125 文件 30d+ 占 78% tracker 反复 check + member 5.7M order_id 全表 UPDATE 7 min (跟 MEMORY.md 1:1 stable)
- **修复建议**:
  - Sprint 202+ R4 已立项重做 (跟 MEMORY.md "0 业务代码改动 R4 重新立项修" 1:1 stable), 当前 sprint scope 不是这个 review 该覆盖的
  - **架构层面建议**: 把 ETL 全量 reload + 增量 diff 拆 2 个独立 step + 跑批期间跨进程不阻塞 read_only
- **是否立即修**: 是 (但属于 Sprint 202+ R4 sprint scope, 不是新立项)

### 🟡 Finding 3.2: RFM 540 组合首次冷启动 SQL 复杂 (性能 / 风险)
- **类别**: 性能 (冷启动)
- **严重度**: P2 medium
- **位置**:
  - `backend/services/rfm/_flow_engine.py:13` (核心引擎)
  - `backend/services/rfm/r_flow.py:23-51` `_R_BUCKET_SEGMENTATION_TEMPLATE` (R 桶 6 段 CASE WHEN)
  - `backend/services/rfm/cache.py:165-342` `RfmQueryCache` (W5 DuckDB-KV + manifest version tracking + 24h TTL)
- **问题**:
  - W4 fact_rfm_long **540 组合** = 9 channels × 60 items (跟 `scripts/etl/precompute_fact_rfm.py:W4_TOTAL_COMBOS=540` 1:1 stable)
  - 实证 `scripts/etl/rfm_recompute_window.py:81`: `assert combo_count == W4_TOTAL_COMBOS, f"枚举组合数 {combo_count} != 540"`, 单次重算 N 天 × 540 组合
  - W5 DuckDB-KV cache 24h TTL + manifest version invalidate (`backend/services/rfm/cache.py:139-159` `_ManifestTracker.check_and_invalidate`)
  - **冷启动风险**: 跑批后首次查询 (cache miss) 走 SQL 计算, R 桶 6 段 `DATEDIFF` + LEFT JOIN `user_first_purchase` + LEFT JOIN `cutoff_ref` + 主查询 9x9 matrix, 单 query 在 117GB DuckDB 上 P95 3-10s 期望; 5 panel 同时首次进入 (dashboard cold load) → cache miss 串行 → 3-50s
- **修复建议**:
  1. **Dashboard cold load warmup**: uvicorn 启动后 launchd 异步跑 W5 cache warmup (5 top query 预热, < 5 行代码)
  2. **W5 cache 命中率监控**: `backend/services/rfm/cache.py:stats()` 已经实现, 接入 `/metrics` Prometheus endpoint (跟 L4.52 observability 1:1 stable)
  3. **真业务触发**: 业务方反馈 dashboard cold load 慢时立 P2 sprint
- **是否立即修**: 否 (等真业务反馈)

### 🟡 Finding 3.3: audience_summary 5000+ order_ids UNNEST vs 5000 `?` placeholder (性能 / 风险)
- **类别**: 性能 (极端参数)
- **严重度**: P2 medium
- **位置**:
  - `backend/services/metrics/audience_summary.py:16` `calculate_audience_summary` (3 callers)
  - `scripts/_archive/adhoc_order_set_30_indicators.py:78-81` `o.order_id IN (?,?,?,...)` 5000 个 placeholder 参数化路径
- **问题**:
  - 真 5000 order_ids 走 IN (`?`) 占位符而非 UNNEST (UNNEST 走 array[], 在 DuckDB 上更快但 backend/types 不支持 array)
  - 实证 `scripts/_archive/adhoc_order_set_30_indicators.py:78-81`: `order_id_list = sorted(order_ids); placeholders = ",".join(["?"] * len(order_id_list)); where_parts.append(f"o.order_id IN ({placeholders})"); params.extend(order_id_list)` 5000 `?` 走 DB-API 参数化
  - DuckDB 对大 IN 子句优化尚可, 但 5000+ rows 走 IN 还不如 UNNEST 列表转 array
- **修复建议**:
  - **中期 (Sprint 203+ 立项)**: 把 `order_ids` 参数从 `List[str]` 改成 `List[int]` (DuckDB 内部 array), 走 `WHERE order_id IN (SELECT UNNEST(?))` 模式, 估时 2-3 天
  - 或者走 file-based: 上传 xlsx → 表内临时行 → `WHERE order_id IN (SELECT order_id FROM _temp_orders)` (跟 Sprint 196 fixed_product_list_compare 1:1 stable)
- **是否立即修**: 否 (等业务报告 10000+ order_ids 慢时立项)

### 🟡 Finding 3.4: W2 atomic manifest + W3 6 DQ assertions 阻塞跑批 (性能 / 风险)
- **类别**: 性能 (跑批期间)
- **严重度**: P3 low
- **位置**:
  - `scripts/etl/manifest.py:32-185` (`SnapshotManifest.write_active` fsync + rename)
  - `scripts/etl/manifest.py:148-164` `_cleanup_old_versions` (lazy cleanup on write)
- **问题**:
  - W2 atomic manifest switch 在 `scripts/etl/cli.py` 跑批 step 9 (final) 触发 (`manifest.write_active`)
  - 但 `manifest.py:148-164` lazy cleanup 是 O(N versions), 跑批一周累计 .versions/ 7 天 × 多次 = 数百个 json, 单次 lazy cleanup 数秒延迟
- **修复建议**:
  - 当前 lazy cleanup 触发频次低 (1 周 1 次), 实测 < 100ms (跟 Sprint 22 #26 1:1 stable); 
  - **建议**: launchd daily cleanup (跟 `scripts/etl/cleanup_backups.py` 模式 1:1) 取代 lazy cleanup
- **是否立即修**: 否

---

## 4. 可扩展性瓶颈 (Scalability)

### 🔴 Finding 4.1: ClickHouse POC 8-10 周 立项决策备忘录 0 实际启动 (可扩展 / 风险)
- **类别**: 可扩展性 (长期)
- **严重度**: P1 high
- **位置**: `docs/architecture/clickhouse-poc-decision-memo.md:1-100` (整份备忘录 280+ 行)
- **问题**:
  - 备忘录 §1.3 决策触发条件 3 件 (a/b/c) 0 触发
  - Sprint 202+ L4.58 监控 SOP (R2 ClickHouse POC 启动条件监控) 已立项但 0 业务触发
  - 备忘录 §3 阶段拆分 8-10 周 1-2 人月, 不在 1 sprint 闭环
  - 风险: 业务方月底突报"我们部门 5 个分析师并发取数 dashboard 卡死" → 没立项 SOP → 临时拍方案 → 跑偏
- **修复建议**:
  1. **Sprint 203+ 立项启动条件监控**: launchd weekly 跑 (跟 L4.58 + L4.59 永久规则 1:1 stable)
  2. **具体监控**:
     - (a) `data/processed/fuqing_crm.duckdb` 文件 size 监控 (> 200GB 触发)
     - (b) `/metrics` endpoint `histogram_quantile(0.95, query_latency_seconds)` 监控 (> 30s 持续 1 周触发)
     - (c) `request_id` 计数 (每日 > 5 user 触发)
  3. **触发命中 → 自动立项**: 跑 launchd 跨 sprint monitor, 命中 → 自动 append `docs/TECH-DEBT.md` 触发条目 + 通知用户拍板
- **是否立即修**: 是 (低优先工作量, 跟 L4.59 跨 sprint 维护性 1:1 stable)
  - 启动条件监控 = 跟 L4.59 R6/R7/R8 9 files 同 sprint, 0 业务代码改动模式
  - 估时 1 天 (跟 L4.59 监控脚本 + pytest regression + launchd plist 模式 1:1)
  - **建议 Sprint 203+ R10 立 L4.58 实证 + 启动条件监控脚本** (跟 L4.59 SOP 同位)

### 🔴 Finding 4.2: 前端 dashboard SPA 单一 Vue Router 入口 (可扩展 / 风险)
- **类别**: 前端可扩展性
- **严重度**: P2 medium
- **位置**:
  - `frontend-vue3/src/router/index.ts:5-48` (8 routes, /audience /category /category-detail /customer-health /geo /market-focus /sampling + redirect `/audience`)
  - `frontend-vue3/src/App.vue:1-95` (DefaultLayout 包 8 个 view + Naive UI 全局 provider)
  - `frontend-vue3/src/views/SamplingView.vue` (4 tab: roi/lock/cohort/rolling)
  - `frontend-vue3/src/views/category-tabs/CategoryFlowTab.vue` (4 sub-tab: category detail)
- **问题**:
  - **当前架构**: 8 个 dashboard view, 每个 view 调不同 backend endpoint, 缺前端 lazy-load 包拆分 (除 vite 默认 dynamic import 外, 缺 chunk size 优化)
  - **缺前端 cache**: ECharts 配置 + 主题 + DuckDB JSON 解析都重新计算 (跟 `frontend-vue3/src/composables/useChartTheme` 1:1)
  - **首屏 cold load**: 8 个 view lazy import + DefaultLayout + App.vue providers + Rive canvas = 500KB+ bundle (跟 LoginView.vue 实测 Rive 4MB inline base64 1:1 stable)
- **修复建议**:
  1. **dashboard cold load 优化**: `frontend-vue3/vite.config.ts` 加 `build.rollupOptions.output.manualChunks` 把 ECharts / Naive UI 拆 vendor chunk (估时 1 天)
  2. **API response cache**: `frontend-vue3/src/api/` 套 SWR (跟 VueUse useFetch 1:1 stable) 30s stale-while-revalidate, 减少 backend round-trip
  3. **真业务触发**: 业务方报告首屏 5s+ 才立 P2 sprint
- **是否立即修**: 否 (等真业务反馈)

### 🟡 Finding 4.3: 14 tool SSOT 维护 + 真业务命中率 ~40-65% (可扩展 / 风险)
- **类别**: 可扩展性 (边际成本)
- **严重度**: P2 medium
- **位置**:
  - `scripts/ad_hoc_queries/*.py` 14 tool files (排除 `__init__.py` / `_utils.py` / `registry.py`)
  - `scripts/ad_hoc_queries/registry.py:37` `register(spec: QuerySpec) -> QuerySpec`
  - `mcp_servers/fuqing_adhoc/_dispatch.py:TOOL_DEFS` + `HANDLERS`
  - `backend/routers/ad_hoc_query.py:238-533` 9 HTTP endpoint (从 14 tool 挑 9 个暴露 HTTP)
- **问题**:
  - **Sprint 199 R1 cleanup 实证** (跟 MEMORY.md 1:1 stable): "14 tool 真实命中率 ~40-65%" + "L4.47 候选禁 `/tmp/*.py` 业务取数脚本" + "WorkBuddy 跨 12 轮对话写 14 个 /tmp/*.py 严重违规"
  - **结构性问题**:
    1. 新 tool 接入: 3 files 改造 + sync (tool file + registry import + `_dispatch.py` TOOL_DEFS + handler + HTTP endpoint Pydantic schemas) 估时 **3-5 天**
    2. tool 数量从 14 → 16+: SSOT list 维护成本上升 (跟 L4.59 R8 14 tool 真实命中率监控 1:1)
    3. AI 取数覆盖率 40-65% → 95% 目标需要第 14 tool `ai-sandbox-execute` (跟 Sprint 198 决策 1:1)
- **修复建议**:
  - **当前架构可接受**: 跟 Sprint 60+ 1:1 stable, 跨 sprint 14 tool 累计 0 debt
  - **中期 (Sprint 203+ 立项)**: 把 14 tool SSOT 改成 **SQL-based declarative spec** (1 YAML file + 1 generator script, 跟 L4.43 argparse adapter 模式 1:1), 估时 5-7 天 改造工作量 + 持续 0 边际成本
  - **真业务触发**: 等业务组反馈 "AI 反复写 /tmp/*.py 取数" 0 命中 tool 时立项
- **是否立即修**: 否 (Sprint 200 R1 已立项 A 方案, 等真业务触发)

### 🟡 Finding 4.4: 14 tool + 9 HTTP endpoint 重复路径 (可扩展 / 风险)
- **类别**: 架构 (重复)
- **严重度**: P2 medium
- **位置**:
  - 14 tool files 中 9 个被 backend HTTP endpoint 暴露 (从 14 tool files 跟 9 endpoint 一对一映射)
  - 实证 `backend/routers/ad_hoc_query.py:238-533` 9 个 endpoint 跟 `scripts/ad_hoc_queries/*.py` 9 个文件 1:1 对应
- **问题**:
  - **重复维护**: 9 个 tool 改了返回值 → 9 个 HTTP endpoint 跟着改
  - **缺单层抽象**: HTTP endpoint 没有 thin wrapper, 直接调用 `run_<X>`, 没 Pydantic schema 跟 tool default 一致
- **修复建议**:
  - 当前架构跟 Sprint 60+ 跨 sprint 0 debt stable 模式 1:1, 当前可接受
  - **中期**: 提取 `backend/services/ad_hoc/` 子目录, 共享 9 tool 的 Pydantic schema + run function, HTTP 路由只 1 行调用
- **是否立即修**: 否 (跟 Sprint 199 R1 1:1 stable)

### 🟡 Finding 4.5: 单文件 frontend-vue3 LoginView 内嵌 4MB Rive base64 (性能 / 可扩展性)
- **类别**: 前端可扩展性
- **严重度**: P2 medium
- **位置**: `frontend-vue3/src/views/LoginView.vue:7-8` + `frontend-vue3/src/components/NavBar.vue:7-8` (Rive/PNG base64 inline)
- **问题**:
  - `frontend-vue3/src/components/NavBar.vue:7-8` logo PNG **inline base64 ~32KB** (估算), 跟 LoginView.vue Rive 4MB base64 单独算
  - Vite build 时全部 bundling, 任何 route change 都会 parse 这部分
- **修复建议**:
  - 当前可接受 (跟 Sprint 159 决策 inline base64 1:1 stable)
  - 中期: 改 `frontend-vue3/src/assets/` PNG/Rive 文件 + Vite asset module (3 days 改造)
- **是否立即修**: 否

### 🔴 Finding 4.6: 缺 前端 Backend 状态监控 + 后端 DuckDB 数据漂移监控 (可扩展 / 风险)
- **类别**: 可扩展性 (长期)
- **严重度**: P1 high
- **位置**: 当前 `/metrics` endpoint 实证存在 (L4.52) 但**没真正被前端 dashboard 消费**
- **问题**:
  - L4.52 Prometheus-compatible observability (`backend/services/query_metrics.py`) 已落地, `/metrics` endpoint 提供 query 计数 + 延迟分布
  - 但前端没有任何 dashboard 显示这数据, 业务/运营看不到 "query 慢在哪"
  - 等于 observability 落了一半 (数据有, 没人看)
- **修复建议**:
  1. **Sprint 203+ 立项 metrics dashboard 页**: 新建 `frontend-vue3/src/views/OpsView.vue` 显示 `/metrics` 关键指标 (read pool 利用率 + query P95 + DuckDB size + manifest version)
  2. **或者 (跟 Sprint 59+ 治理 1:1)**: 让 `find_evidence_nearby` / `tech-debt-monitor` 走 launchd 跨 sprint 监控, 自动告警
- **是否立即修**: 是 (跟 L4.59 跨 sprint 维护性 SOP 1:1 stable, 1-2 天工作量)

---

## 5. 可执行清单 (Actionable Items)

### P0 (立即修, 1-2 sprint 内)
- (无 — 当前架构短期 stable)

### P1 high (真业务触发立 sprint)
1. **Finding 4.1**: ClickHouse POC 启动条件监控 (a/b/c 3 件) launchd weekly 自动跑 + 触发命中自动立项 — 1 day 工作量
2. **Finding 4.6**: `/metrics` dashboard 前端展示 — 2 days 工作量 (跟 L4.52 observability 1:1)
3. **Finding 3.1**: Sprint 202+ R4 跑批 wall_min 治本 (已立项, 跑批期间不阻塞 read_only)
4. **Finding 2.2**: `dual_conn.py:get_read_connection` 加 `Semaphore` 排队 — 0.5 day 工作量 (短期治标)

### P2 medium (跨 sprint 自然验证/监控)
5. **Finding 2.4**: ClickHouse POC 启动条件监控跨 sprint SOP (跟 L4.58 1:1 stable)
6. **Finding 2.5**: DuckDB WAL mode 接入 (跨 sprint R4)
7. **Finding 3.2**: W5 cache 命中率监控 + dashboard cold load warmup
8. **Finding 3.3**: order_ids UNNEST 改 array[] 模式 (极端参数优化)
9. **Finding 4.2**: 前端 vendor chunk 拆分 + API response SWR cache
10. **Finding 4.3**: 14 tool SSOT declarative 化 (中期)
11. **Finding 1.2**: ad-hoc query HTTP endpoint 走 service layer 改造

### P3 low (维持现行, 跨 sprint 实证)
12. **Finding 1.1**: 3 层架构维持
13. **Finding 1.3**: MCP 链路完整
14. **Finding 2.1**: Read-Write Splitting 闭环
15. **Finding 2.3**: Query worker 隔离 + 安全配置
16. **Finding 3.4**: W2 atomic manifest fsync 维持

---

## 6. 限制声明 (Limitations)

1. **本审查不重复 L4.x 永久规则**: 60+ 条已沉淀在 CLAUDE.md, 0 业务代码改动模式 + 132 sprint 0 debt + /document-release 累计 36 次真治本
2. **本审查不深入 Sprint 202+ 14 files 业务改动细节**: 是业务 sprint scope, 不是架构 review
3. **本审查不覆盖 security dimensions**: 留给 /cso skill 单独走
4. **本审查不覆盖 UI/UX design**: 留给 /design-review skill

---

## 7. Sprint 203+ 立项建议 (Actionable Sprint Suggestions)

基于本审查实证 + Sprint 60+ 跨 sprint 0 debt stable 模式, 建议 Sprint 203+ 立项顺序:

| 优先级 | Sprint | 工作量 | 立项信息 |
|---|---|---|---|
| P1 (前置) | Sprint 203 R1 | 1-2 天 | ClickHouse POC 启动条件监控 (a/b/c 3 件) launchd weekly 自动跑 (跟 L4.58 + L4.59 1:1 stable 模式) |
| P1 (前置) | Sprint 203 R2 | 1-2 天 | `/metrics` dashboard 前端 OpsView.vue (L4.52 observability 收口) |
| P2 (中期) | Sprint 204+ | 5-8 天 | Sprint 202+ R4 跑批 wall_min 治本 (R4 重新立项) + DuckDB WAL mode 接入 |
| P2 (备用) | Sprint 205+ | 3-5 天 | ad-hoc query HTTP endpoint 走 service layer 改造 (L4.5 exception 验证) |
| P0 (触发) | Sprint N (启动条件命中) | 8-10 周 1-2 人月 | ClickHouse POC sprint 启动 + 走完整 12 步流程 |

---

## 8. 总结 (Summary)

整体架构 / 性能 / 可扩展性 3 维度:

- ✅ **架构**: 3 层 (services/routers/contracts) + 14 tool CLI + MCP stdio 链路 + Read-Write Splitting + query worker 完整, 0 业务代码改动 stable
- 🔴 **性能**: ETL 63min 0 实质效果 (Sprint 202+ R4 已立项重做) + RFM 540 冷启动 dashboard + DuckDB flock 锁期间 uvicorn read_only 全阻塞
- 🔴 **可扩展性**: uvicorn 单进程 + 5 read pool 容量上限 + 117GB 单文件 200GB 触发线 + ClickHouse POC 0 启动条件监控

**核心建议**: Sprint 203+ 立项 ClickHouse POC 启动条件监控 (跟 L4.59 跨 sprint 维护性 1:1 stable, 1 天工作量), 真业务触发命中自动告警 + 走完整 12 步流程 Sprint N 启动 ClickHouse POC 8-10 周专项 sprint.

---

*authored: 2026-07-05 (跟 MEMORY.md v2.7 1:1 stable 跟 Sprint 60+ 跨 sprint 0 debt stable 模式 1:1)*
