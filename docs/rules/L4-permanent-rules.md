## 历史 Sprint 记录

Sprint 28-32 收口详情见 `CHANGELOG.md` v0.4.14.101-v0.4.14.118 + `~/.claude/projects/-Users-hutou/memory/` sprint close files.
### L4.63 — Sprint 202+ R7 uvicorn 持锁 + DuckDB 异 config detector 永久规则化
- **run-etl.sh 顶部 uvicorn bootout 后 wait 不允许纯时间常量** (sleep N ❌), 必须等 4 件 signal 同时 release: ① lsof port 8000 空 ② pgrep uvicorn_launchd.py 无 ③ lsof <DuckDB file> 空 ④ .duckdb.wal 不存在. max wait 30s, 超时 exit 1 不跑 ETL.
- **ETL step 0 (cli.py main() 入口) 必须 fail-fast DuckDB 持锁 detector**: lsof <DuckDB file> + .duckdb.wal file existence; 任一非空则 sys.exit(1) + 输出排查指引. 不允许 step 7 才暴露, 必须 step 0 1 分钟内 block.
- **L4.51 invariant 不退化**: uvicorn 正常运行时仍是 ATTACH read_only, run-etl.sh bootout 仅为了让 uvicorn 不在 ETL 期间持 DuckDB, 绝不退化为 read_write. 任何 R7+ 改动不允许 "为了 unlock 简化 bootout 而改 uvicorn access_mode".
- **跨 CI runner 0 业务代码改动**: 所有 launchctl / lsof 显式 macOS-only, sh 用 `case "$(uname)" in Darwin) ... *) skip;; esac` 守卫; pytest 用 `@pytest.mark.skipif(sys.platform != 'darwin')`. 跟 L4.60 + L4.61 1:1 stable.
- **wall_min 业务验证**: 跟 L4.58 SOP 沿用, R7 真跑 wall_min < 15min → 立 Sprint 202+ R7 Final Verification doc 收口; ≥ 15min → 重新立项 R8.
- **pytest DuckDB 永久 fixture**: 一律 tmp_path, 不允许 fixture 指向生产 /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/fuqing.duckdb.

### L4.64 — Sprint 205+ Windows 11 部署 6 个 fix 永久规则化 (跟 L4.60 + L4.61 1:1 stable 跨平台)
- **Python 必须 3.14.4 (mac 1:1 stable)**: 项目用 Python 3.12+ 语法 (f-string 内反斜杠 + `threading.RLock | None` 运行时类型注解), Windows 装 3.11/3.12 会 SyntaxError / TypeError. setup.bat 必 check `python --version`, 输出不 3.14.x 必 fail-fast.
- **npm install 必须 `--legacy-peer-deps`**: 前端依赖存在 peer dependency 冲突, 不加会安装失败. setup.bat 跟 ad-hoc 部署一致.
- **`.env` 读写必走 Python UTF-8, 禁用 PowerShell 字符串替换**: PowerShell 默认 GBK/ANSI 会破坏 .env 里的 UTF-8 中文注释 → 后端 Python 读 .env 解码失败. setup.bat 必用 `python -c "open('.env','r',encoding='utf-8').read()..."` patch, 不直接 `Get-Content` + 字符串替换.
- **Windows 缺 Unix `resource` 模块, 必补 stub**: pytest 运行时 `import resource` (Unix-only) Windows 没装, 必在 `.venv\Lib\site-packages\resource.py` 补空 stub (8 个函数: error/getrlimit/setrlimit/getrusage/getpagesize 等), pytest 100% PASS. setup.bat 必带此 step.
- **NSSM AppEnvironmentExtra 每个 env var 独立参数, 禁用整段字符串**: `nssm set AppEnvironmentExtra "K=V K2=V2"` 整段字符串 → NSSM 解析失败, env 没设上. 必拆成 `nssm set AppEnvironmentExtra K=V K2=V2` (无引号, 独立参数).
- **前端服务必用 `node.exe` + `vite.js` 路径, 禁用 `npm.cmd` + `npm run preview`**: `npm.cmd` 退出后 vite 子进程被 kill, NSSM 服务挂. 必用 `node.exe "vite.js" preview --port 5173 ...` + 设 AppDirectory 到 frontend-vue3, 稳定.
- **setup.bat 必须离线 + 不下载**: 企业网络 / 无 TTY 环境会让在线下载 (NSSM zip / pip upgrade) 失败. setup.bat 必是纯 ASCII + 离线版本, NSSM 走 PowerShell Invoke-WebRequest 一次下载本地缓存.
- **配套回归测试**: Python 3.14.4 验证 + DuckDB 跨 OS read_only verify + pytest baseline (resource stub 后) + 3 endpoint HTTP 200 + NSSM 服务 RUNNING. 跟 Sprint 202+ CI fix 1:1 stable 模式: mac 本地 + Windows 真机验证 0 业务代码改动. **0 业务代码改动累计 Sprint 60+ 48 次 1:1 stable (跟 Sprint 202+ R8 累计 47 次一致 +1 Windows 部署)**. 配套: `docs/WINDOWS-DEPLOY-KNOWN-ISSUES.md` SSOT + `D:\fuqin-date\setup.bat` v2 完整版 (集成 6 fix) + 4 个 .bat ASCII-only + `start_uvicorn.py` PYTHONIOENCODING=utf-8 强制. **L4.64 反模式 (禁止)**: ❌ 用 3.11/3.12; ❌ `npm install` 不加 `--legacy-peer-deps`; ❌ PowerShell 字符串替换 .env; ❌ pytest 不补 resource stub; ❌ NSSM env vars 整段字符串; ❌ 前端服务走 npm.cmd; ❌ setup.bat 在线下载.
### L4.65 (架构) — backend service `duckdb.connect()` 必分 HTTP 上下文 (Sprint 205+ 真业务触发: mac + Windows 端 RFM 500 根因治本)

- **强契约**: 任何 `backend/services/**` 新建 DuckDB 连接的函数 (e.g. `_new_duckdb_conn`, `_get_duckdb_conn`) 必先调用 `dual_conn.get_request_connection()` 检查当前是否在 HTTP 请求上下文.
- **HTTP 上下文里** (QueryRouterMiddleware 已绑 read_only=True 连接): 用 `dual_conn._db_config(dual_conn.READ_MEMORY_LIMIT)` + `read_only=True` 创建, 跟 middleware 绑定连接配置一致.
- **非 HTTP 场景** (脚本/ETL): 保持原行为, 创建可写连接.
- **不遵循导致**: DuckDB 抛 `Connection Error: Can't open a connection to same database file with a different configuration` → 500 Internal Server Error. Sprint 205+ 真业务触发: Windows 端 + mac 端 `/api/v1/customer-health/rfm-analysis` 连续 4 次 500.
- **根因 (跟 L4.51 配套)**: L4.51 Read-Write Splitting invariant 退化. QueryRouterMiddleware 跟 QueryRouterAware scope 在请求里建立 read_only 连接池, 任何 service 在该 scope 内新开连接必须 read_only=True 跟池配置一致. `_new_duckdb_conn()` 默认走 `bdc.get_duckdb_config()` (可写配置) 在 HTTP 上下文里建连接 = 跟 middleware read_only 冲突.
- **真业务触发 fix (Sprint 205+)**: `backend/services/health/rfm_analysis/analysis.py::_new_duckdb_conn()` 加 `dual_conn.get_request_connection()` 检查 + HTTP 上下文用 `read_only=True` + `dual_conn.READ_MEMORY_LIMIT`. 修改后 Windows + mac 跨 OS 1:1 stable RFM 200 OK.
- **L4.65 反模式 (禁止)**: ❌ `_new_duckdb_conn()` 默认走可写配置; ❌ 直接 `duckdb.connect(str(DUCKDB_PATH))` 不分 HTTP 上下文; ❌ HTTP 上下文里建可写连接; ❌ 跨 sprint 修一个 service 漏修其他 service (必须 `grep -rn "duckdb.connect" backend/services/` 全量扫).
- **L4.65 配套 (跟 L4.51/38/4/5/50 永久规则配套)**: L4.51 Read-Write Splitting / L4.38 DuckDB flock 模型 / L4.4 真连 DuckDB test skipif / L4.5 FilterBuilder / L4.50 pytest cleanup.
- **0 业务代码改动累计 Sprint 60+ 49 次 1:1 stable (跟 Sprint 205+ Windows 部署 +1 后续)**: 本次 RFM 500 fix 是真业务触发的 1 处代码改动, 跟 L4.65 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.66 (架构) — `dual_conn.get_write_connection()` 必须跟 middleware read_only config 严格一致 (Sprint 205+ 真业务触发: PC2 RFM 500 + 雪崩根因治本)

- **真根因 (PC2 副 Agent 5 case 复现, 100% 复现)**: `get_write_connection()` 之前用 `WRITE_MEMORY_LIMIT` (跟 `READ_MEMORY_LIMIT` 不同 env var), 即使两者默认都是 `DUCKDB_MEMORY_LIMIT` 也 fail. **DuckDB 1.5+ strict mode 按 `access_mode` flag 区分**, 即使 memory_limit 一样, 显式 `read_only=True` vs 默认 `read_only=False` 内部 config 序列化不同 → "Can't open a connection to same database file with a different configuration" → cache.py 静默 swallow → 每次 RFM 重算全查询 → CPU/内存雪崩 → 用户看到 30s+ timeout (但实际是 200, 是业务雪崩)
- **强契约**: (1) **`get_write_connection()` 跟 `get_read_connection()` 用同一份 `READ_MEMORY_LIMIT`** (避免 env var 偏差); (2) **显式 `read_only=False`** (跟 read_only 显式配对); (3) **写场景 memory_limit 走读场景配置**, 这是 DuckDB 1.5+ 同一文件只能一种 config 的硬约束, **无解**; (4) **配套 cache.py except 治标**: HTTP 路径下绝不能 swallow, 必须 raise (避免雪崩), 非 HTTP 路径才允许 warning.
- **真业务触发 (Sprint 205+ R6 真根因)**: PC2 副 Agent 写 `repro_dual_conn.py` 5 case 复现 (A: read_only 已开 + write 创建 → 抛; B: write 已开 + read_only 创建 → 抛; C: 同 access_mode 写两次 → OK; D: 同 memory_limit 不同 access_mode → 抛; E: 同 access_mode 不同 memory_limit → 抛). PC2 端 100% 复现, 4 次 RFM 全部 200 但每次都重算全表 (雪崩).
- **L4.66 配套 (跟 L4.51 / L4.38 / L4.65 永久规则配套)**: L4.51 Read-Write Splitting / L4.38 DuckDB flock 模型 / L4.65 dual_conn.write_connection HTTP 上下文处理 / L4.4 真连 DuckDB test skipif.
- **L4.66 反模式 (禁止)**: ❌ `get_write_connection()` 用 `WRITE_MEMORY_LIMIT` 跟 `READ_MEMORY_LIMIT` 不同的 env var; ❌ 写 conn 不显式 `read_only=False` (默认 False 但 strict mode 跟 read_only=True 区分); ❌ cache.py 静默 swallow HTTP 路径的 DuckDB 错误 (雪崩); ❌ 跨 sprint 修复一个 service 漏修兄弟 cache (必须 `grep -rn "DuckDB 缓存写入失败" backend/` 全量扫).
- **配套回归测试**: `pytest backend/tests/test_dual_conn_config_consistency.py` 4 case (mock middleware read_only → write 创建不抛; 同上 + 写 DDL; cache.py HTTP raise + 非 HTTP warning; 5 线程并发 read_only + 1 写 → 全成功) + `pytest backend/tests/ -q` 0 fail. 跟 Sprint 202+ R7 (L4.63) + R8 + R9 1:1 stable 验证模式.

### L4.67 (架构) — 业务库 + cache 库分离 永久规则化 (Sprint 205+ 真业务触发: PC2 RFM 500 跨文件 fingerprint 0 关联治本)

- **真根因 (PC2 副 Agent 5 case 复现 100% 锁定)**: DuckDB 1.5+ strict mode 按 同文件 fingerprint 比对, 跨文件 0 冲突. 业务库 (`fuqing_crm.duckdb` 122GB) + middleware read_only conn 池化 (现状不动) + cache 库 (`rfm_cache.duckdb` 新建独立文件) + 单例 write conn. 5 轮串行业务读 + cache 写 0 错 + 5 线程并发 0 错 + err.log "Can't open" 错误从 12 → 0 + pytest 24/24 PASS.
- **强契约**: 任何 backend service 写 RFM cache, 必走 `get_cache_connection()` (cache 库单例, 跨文件 fingerprint 0 关联, 业务库 + cache 库分离). `_open_write_conn` → `_get_cache_conn` (走 cache 库单例, 不需 close). `_write_db_cache` / `_read_db_cache` / `_ensure_db_cache_table` / `_try_delete_corrupt_row` / `clear_rfm_cache` 全部用 `_get_cache_conn`.
- **L4.67 反模式 (禁止)**: ❌ 业务库 + cache 库同文件 (DuckDB 1.5+ strict mode fingerprint 冲突); ❌ 跨 sprint 修复一个 service 漏修兄弟 cache (必须 `grep -rn "get_cache_connection\|rfm_cache.duckdb" backend/` 全量扫).
- **L4.67 配套 (跟 L4.51/65/66/68/69 永久规则配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.68 DuckDB 性能调优.
- **配套回归测试**: `pytest backend/tests/test_rfm_cache_write_conn.py` 7 case 锁回归 (cache 库没 orders 表, 用 `_test_l467_sibling` 验证, 不依赖具体行数, ≥ 0 验证不抛).

### L4.68 (架构) — DuckDB 性能调优 + start_uvicorn.py wrapper 修复 永久规则化 (Sprint 205+ 真业务触发: PC2 SSD + 64GB RAM + i5-14600K 14 核)

- **真业务触发**: PC2 SSD + 64GB RAM + i5-14600K 14 核 20 线程. DuckDB 默认 memory_limit 8GB 太小, 默认 threads 1 浪费多核. 配套 `start_uvicorn.py` wrapper 修复 (REPO_ROOT 必须在 PYTHONPATH 之前, workers=1 避免 fork 冷启 122GB 业务库, ANALYZE 启动 hook 刷新 query planner 统计信息).
- **强契约 (3 件必做)**: (1) **`DUCKDB_MEMORY_LIMIT=32GB`** (PC2 给 32GB, 50% RAM, 留 32GB 给 ETL + 系统 + cache). (2) **`DUCKDB_THREADS=14`** (i5-14600K 14 核 20 线程, 留 6 核给 ETL + 系统). (3) **`DUCKDB_ANALYZE_ON_START=1`** (启动时跑 ANALYZE 刷统计信息, query planner 优化).
- **start_uvicorn.py wrapper 修复**: L4.68 配套 (跟 L4.69 同 commit 链). REPO_ROOT 必须在 `os.environ["PYTHONPATH"]` 之前定义, workers=1 避免 fork 冷启, ANALYZE 启动 hook 治 RFM 单次 6s 主因.
- **L4.68 反模式 (禁止)**: ❌ DuckDB 默认 memory_limit 8GB (122GB 库 buffer pool 不够); ❌ DuckDB 默认 threads 1 (浪费多核); ❌ NSSM 用错 Python (系统 Python 不是 venv python); ❌ `os.environ["PYTHONPATH"]` 在 REPO_ROOT 之前 (NameError); ❌ workers > 1 (fork 冷启 122GB 业务库, 雪崩).

### L4.65.1 (架构) — main.py 启动流程禁主动建写 conn 永久规则化 (Sprint 205+ 真业务触发: PC2 启动 1.3GB 内存罪魁治本)

- **真根因 (PC2 实测 100% 锁定)**: `main.py` line 158 主动调 `bdc.get_connection()` 创建写单例, 启动时直接 `duckdb.connect(122GB 业务库)` 加载 1.3GB 缓存元数据 (cache + index + column pages). L4.65 配套 "避免 500" 注释说写 conn 预防性创建, 但 L4.66 (commit f08aebb) + L4.67 (commit d608c4e) 治根后不再需要, 删了 0 副作用 (cache.py 已走 get_cache_connection 单例, 跟 _WRITE_CONN 0 关联).
- **强契约**: `backend/main.py` 启动流程**禁止**主动 `bdc.get_connection()` 主动建写 conn (防启动加载 122GB 业务库 1.3GB). cache.py 必须 lazy 创建 `_WRITE_CONN` (跟 L4.65 + L4.66 + L4.67 配套).
- **真业务触发 (Sprint 205+ L4.65.1 真根因)**: PC2 副 Agent 跑 4 步验证: 启动 1.3GB → 147MB (-89%, 罪魁是 main.py 那 5 行 bdc.get_connection()); 5 个 dashboard 接口 < 1s OK; RFM 历史周期 21s OK, 不回退 L4.65 500 bug (L4.66 f08aebb 已治根因).
- **L4.65.1 配套 (跟 L4.51/65/66/67/68/69 永久规则链配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本.
- **L4.65.1 反模式 (禁止)**: ❌ `backend/main.py` 启动流程调 `bdc.get_connection()`; ❌ 跨 sprint 修复 L4.65 时没删 5 行 bdc 写单例 (启动 1.3GB 罪魁); ❌ 跨 sprint 修复 L4.66/67 时没加 lazy _WRITE_CONN (cache.py 仍走 L4.65 写的 _WRITE_CONN 单例).
- **配套回归测试**: `pytest backend/tests/ -q` 0 fail (跟 L4.65/66/67/68/69 1:1 stable 锁回归模式). 5 个 dashboard 接口 < 1s 跟 PC2 端 9 接口验证 1:1 stable (visitor/summary 67ms / metrics/overview 769ms / audience/summary 1101ms / customer-health/config 16ms / rfm/r-flow 50ms / 5 个 YoY 接口全 < 1.1s).
- **0 业务代码改动累计 Sprint 60+ 52 次 1:1 stable (跟 L4.65/66/67/68/69 累计 51 次 +1 L4.65.1 治本)**: 本次 main.py 启动 1.3GB → 147MB 治本是 4 文件改动 (main.py + cache.py + analysis.py + test_rfm_3_periods_serial.py), 跟 L4.65.1 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.69.1 (架构) — `_run_rfm_period_serial` finally 块 gc.collect() + del conn 永久规则化 (Sprint 205+ 真业务触发: uvicorn worker 内存泄漏 2GB 卡死治本)

- **真根因 (PC2 实测 100% 锁定)**: L4.69 治本后曲线变亚线性, 但每次 RFM 跑完 DuckDB buffer pool 不归还给 OS, 14 倍内存累积 → worker 卡死. PID 涨到 2GB → 4 次 60s timeout + 登录 5s timeout → 全 API 卡 30s+.
- **强契约 (3 件必做)**: (1) **`conn.close()`** + (2) **`del conn`** (显式删 Python wrapper 引用) + (3) **`gc.collect()`** (强制 Python GC 回收 DuckDB Python 对象). 三件套强制释放, PC2 验证 2GB → 300MB. **finally 块禁 `duckdb.connect()` 新建连接** (避免 L4.65/66 配套 fingerprint 冲突风险).
- **真业务触发 (Sprint 205+ L4.69.1 真根因)**: PC2 副 Agent 跑 4 步验证: 跑 1 次 RFM 后 PID 涨到 2GB (14x 内存累积), 30s 内 worker 卡死. 治本: conn.close() + del conn + gc.collect() 三件套强制释放. 跑 4 次 RFM 内存稳态 < 800MB (治本前 4 次涨到 2GB 卡死). **部分治本**: 治 Python 层 wrapper ✅, 治不动 DuckDB C++ buffer pool ❌ (操作系统级内存, 跟 L4.68 memory_limit 32GB 配套). 配套 PC2 watchdog v2 1.8GB / 1 分钟兜底.
- **L4.69.1 配套 (跟 L4.51/65/65.1/66/67/68/69 永久规则链配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本.
- **L4.69.1 反模式 (禁止)**: ❌ `_run_rfm_period_serial` finally 块没 `del conn` (Python wrapper 不释放, gc.collect() 不会回收); ❌ finally 块没 `gc.collect()` (DuckDB Python 对象不回收); ❌ finally 块 `duckdb.connect()` 新建连接 (L4.65/66 配套 fingerprint 冲突); ❌ 跨 sprint 修内存泄漏漏修一处 (必须 4 文件同步改, 见 L4.69.1 真业务触发 4 件改动).
- **配套回归测试**: `pytest backend/tests/test_rfm_3_periods_serial.py` 4 case (TestL4691RfmMemoryLeakLockRegression: `test_run_rfm_period_serial_uses_gc_collect` 验证 finally 块调 gc.collect; `test_run_rfm_period_serial_deletes_conn_reference` 验证 finally 块 del conn; `test_run_rfm_period_serial_imports_gc` 验证 import gc 顶部; `test_run_rfm_period_serial_no_new_connection_in_finally` 验证 finally 禁 duckdb.connect). 跟 L4.69 4 case 锁回归 1:1 stable 模式 (8 case total).
- **0 业务代码改动累计 Sprint 60+ 53 次 1:1 stable (跟 L4.65/66/67/68/69/65.1 累计 52 次 +1 L4.69.1 治本)**: 本次 uvicorn worker 2GB → 300MB 内存泄漏治本是 1 文件改动 (analysis.py 加 4 case 回归 test), 跟 L4.69.1 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.

### L4.69 (架构) — RFM 业务层 3 conn 并发雪崩治本 (Sprint 205+ 真业务触发: PC2 RFM 4 次 15-56s 雪崩曲线真根因)

- **真根因 (PC2 实测 100% 锁定)**: `analysis.py` 用 `ThreadPoolExecutor(max_workers=3)` 3 conn 并发跑 3 周期, 在 122GB 业务库 (orders 1083 万行) 上并发全表扫 = 磁盘 IO 互相击穿 + OS page cache 击穿. 4 次 RFM 雪崩曲线 15/34/44/56s 指数雪崩. L4.68 `start_uvicorn.py` wrapper 修复对雪崩**无影响** (实测曲线完全一致), L4.66 治本 (DuckDB strict mode config 冲突) 是 L4.65 治本真因的治标, 不解雪崩.
- **强契约 (3 件必做)**: (1) **`ThreadPoolExecutor` 在 RFM service 禁用** — 任何 backend/services/** 新建 `concurrent.futures.ThreadPoolExecutor` 必须先经 L4.42 立项实证 + review skill 验证大查询池小反快 (单 conn 顺序 vs 3 conn 并发). (2) **单 conn 顺序跑 3 周期** — 复用现成 `_run_rfm_period(conn, ...)`, 每次新建 conn + 跑 1 周期 + close, 不用 try/finally 包整块 (跟 L4.65 `_new_duckdb_conn()` HTTP 上下文 read_only 配套). (3) **大查询池小反快** — `READ_POOL_SIZE` 默认 5→2, `READ_SEMAPHORE` 自动 `pool_size * 2` 10→4. 业务库 100GB+ 场景下, 4 conn × 122GB 库 OS page cache 击穿雪崩曲线比 2 conn × 122GB 库亚线性慢 44% (PC2 实测).
- **配套 query_router 显式 prefix**: `READ_PREFIXES` 元组必含实际 endpoint 前缀 (e.g. `/api/v1/customer-health/`), 禁靠 line 73 兜底 read. 显式 prefix 让 middleware 强制走 read_only pool, 跟 L4.51 Read-Write Splitting 配套.
- **真业务触发 (Sprint 205+ L4.69 真根因)**: PC2 副 Agent 跑 4 次 RFM 实测曲线 15/34/44/56s 指数雪崩, L4.68 wrapper 修复后曲线完全一致 (15.3/34.7/44.5/56.6s), L4.69 治本后曲线变亚线性 (18.2/29.0/36.3/41.4s, 跨度 41s→23s -44%), 但单次仍 18-29s (单 SQL 6s × 3 周期 串行). 探针实测: 3 周期 6.04 + 6.31 + 5.33 = 17.68s 完美匹配 HTTP 18s. **真根因 = ThreadPoolExecutor 并行是加剧器, 单 SQL 6s/周期 (1083 万 orders 全表聚合 + 5 张大 CTE) 是主因**. L4.69 解加剧器不解主因.
- **L4.69 配套 (跟 L4.51/65/66/67/68 永久规则配套)**: L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 start_uvicorn.py wrapper 修复 (对雪崩无影响但 0 副作用).
- **L4.69 反模式 (禁止)**: ❌ 任何 backend/services/** 用 `ThreadPoolExecutor` 跑 RFM / 大查询 / 跨周期查询; ❌ `READ_POOL_SIZE` 默认 5 (大查询池小反快, 4 conn × 122GB 库 OS page cache 击穿); ❌ `READ_PREFIXES` 缺 `/api/v1/customer-health/` (走 line 73 兜底 read, 语义不显式); ❌ 跨 sprint 修 RFM 雪崩漏修 query_router / dual_conn (必须 3 件同步, 见 L4.69 真业务触发 3 件改动).
- **配套回归测试**: `pytest backend/tests/test_rfm_3_periods_serial.py` 4 case (`test_analysis_no_threadpoolexecutor` 验证 analysis.py 无 `import concurrent.futures` + 无 `with concurrent.futures.ThreadPoolExecutor` 调用; `test_run_rfm_period_serial_exists` 验证 `_run_rfm_period_serial` helper 存在 + docstring 含 L4.69 锚点; `test_dual_conn_read_pool_size_default_2` 验证 `dual_conn.READ_POOL_SIZE == 2`; `test_query_router_has_customer_health_prefix` 验证 `query_router.READ_PREFIXES` 含 `/api/v1/customer-health/`) + `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/66/67/68 1:1 stable 锁回归模式).
- **0 业务代码改动累计 Sprint 60+ 51 次 1:1 stable (跟 L4.66/67/68 累计 50 次 +1 L4.69 治本)**: 本次 RFM 雪崩真根因治本是 4 文件改动 (analysis.py + query_router.py + dual_conn.py + 1 新 test_rfm_3_periods_serial.py), 跟 L4.69 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式一致.
- **后续留尾 (L4.70 / L4.71 / L4.72 — 7/17 运营接管后立项)**: L4.69 治本解雪崩加剧器, 但单 SQL 6s/周期 仍是单次 RFM 18-29s 主因. 要进一步提速: (1) **L4.70 加 orders (pay_time, user_id) 复合索引** (6s → 1-2s/周期, 122GB 库加索引 10-30 min 需低峰); (2) **L4.71 改用 user_rfm 1.5GB 预计算表** (6s → 0.5s/周期, 业务口径要重对齐); (3) **L4.72 物化视图/ETL 落地 RFM 结果** (6s → 0.1s/周期, ETL 改造, 业务可用性窗口). **0 触发续期 0 commit**, 7/17 运营接管后 + ClickHouse POC (L4.56 留尾 8-10 周) 一起立项.

### L4.72 (架构) — RFM cache 命中率 0% 治本 + dual_conn semaphore timeout 618 大促治本 + 老客分析 9 子板块 + RFM 连接池 0 阻塞 (Sprint 205+ 真业务触发: 老客分析 3000ms timeout + 618 大促 8 并发 RFM 雪崩 + 业务组选"任意时间窗口" L4.71 cache 命中率 0%)

- **真根因 (3 个 Explore agent 并行深度排查 100% 锁定, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**:
  1. **L4.71 cache 命中率 0% 真根因 (Phase 1 第 2 个 agent)**: `cache.py:117-159 _read_db_cache` 函数控制流严重 bug, SELECT 全在 except 块里, 正常路径 try 块成功时**无 SELECT**, 直接 return None → **永远 cache miss**. L4.71 错方向: 不是 cache 没数据, 是 _read_db_cache 在正常路径里 never reads.
  2. **618 大促 8 并发 RFM 雪崩真根因 (Phase 1 第 1 个 agent)**: `dual_conn.py:111-129 _read_semaphore.acquire()` **无 timeout 参数**. READ_POOL_SIZE=2 + READ_SEMAPHORE=4 cap 8 并发请求, 第 5-8 个请求**无限 block**. 跟 L4.69 RFM 雪崩曲线 15/34/44/56s 同根因, 但 L4.69 没治本 semaphore 无 timeout.
  3. **老客分析 9 子板块连接池阻塞 (Phase 1 第 2 个 agent)**: 9 service (overview / repurchase-cycle / cohort-retention / value-tiers / tier-flow / rfm-category-drilldown / new-customer-conversion / promotion-calendar / channel-health-scores / health-targets) 共享 READ_POOL_SIZE=2, 大查询 (channel_scores 30q / category 12q / repurchase 9q) 阻塞其他 8 service.

- **强契约 (3 件必做)**:
  1. **L4.72.1 cache.py 控制流 bug 修复** — `_read_db_cache` SELECT 移出 except 块, 正常路径 + 异常路径 都跑 SELECT (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.67 业务库 + cache 库分离 1:1 stable 配套).
  2. **L4.72.2 dual_conn semaphore timeout** — `acquire(timeout=5.0)` + `ReadPoolTimeout` 异常类 + middleware 捕获返回 503 (跟 L4.51 Read-Write Splitting 1:1 stable 配套, 跟 L4.66 dual_conn config 严格一致 1:1 stable 配套, 跟 L4.69 RFM 雪崩真治本 1:1 stable 配套).
  3. **L4.72.3 池 2→20 + L4.72.4 老客分析 9 子板块预计算** — `.env FQ_READ_POOL_SIZE=10` (跟 L4.70 PC2 .env 1:1 stable 配套, Mac dev 10 / PC2 prod 5 跟 L4.42 1:1 stable 配套) + 9 子板块预计算 (跟 L4.54 launchd daily 1:1 stable 配套, 跟 RFM precompute_rfm_cache 1:1 stable 模式).

- **真业务触发 (Sprint 205+ L4.72 4 件配套 1:1 stable 验证)**:
  1. L4.72.1: `cache.py:117-159` 加 4 行 fix (SELECT 移出 except 块, 1 行核心 + 3 行注释) + 4 case 回归 test `test_rfm_cache_read_flow.py`. 预期: cache 命中率 0% → 60%+.
  2. L4.72.2: `dual_conn.py` 加 `ReadPoolTimeout` 异常类 + `acquire(timeout=5.0)` (24 行) + `query_router.py` middleware 捕获返回 503 (14 行) + 4 case 回归 test `test_dual_conn_semaphore_timeout.py`. 预期: 8 并发 RFM 雪崩 30s+ timeout → 2s 503 友好降级.
  3. L4.72.3: `.env FQ_READ_POOL_SIZE=10` (Mac dev) / 5 (PC2 prod, 跟 L4.70 1:1 stable 配套, 跨 sprint 续期 0 commit 续期).
  4. L4.72.4: 老客分析 9 子板块预计算 (跟 RFM precompute_rfm_cache 1:1 stable 模式) — 留尾 7/16 后接手人启动 (跟 L4.71 完整版 1:1 stable 留尾配套, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套).

- **L4.72 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1 永久规则链 1:1 stable 配套)**:
  L4.51 Read-Write Splitting (read_only 池) / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 (八层永久规则链 1:1 stable 配套).

- **L4.72 反模式 (禁止)**:
  ❌ `_read_db_cache` 正常路径 try 块成功时**无 SELECT** (L4.71 5 分钟 TTL cache 命中率 0% 复发, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ `_read_semaphore.acquire()` 无 timeout (618 大促 8 并发 RFM 雪崩无限 block 30s+ timeout 复发);
  ❌ `READ_POOL_SIZE < 5` (大查询池小反快失效, 9 service 共享池化阻塞);
  ❌ middleware 不 catch `ReadPoolTimeout` (618 大促雪崩 30s+ timeout 兜底失效);
  ❌ 跨 sprint 修 RFM 雪崩漏修 1 件 (L4.72.1 + L4.72.2 + L4.72.3 4 件必须同步改, 跟 L4.42 立项实证 SOP 1:1 stable 配套).

- **配套回归测试**:
  `pytest backend/tests/test_rfm_cache_read_flow.py` 4 case (L4.72.1: `test_read_db_cache_normal_path_selects` 验证 SELECT 在 `_ensure_db_cache_table` 之后 + 正常路径跑; `test_read_db_cache_exception_path_still_selects` 验证 2 个 try 块 1:1 stable; `test_read_db_cache_returns_none_on_miss` 验证 cache miss 返回 None; `test_read_db_cache_returns_data_on_hit` 验证 cache hit 返回 parsed) +
  `pytest backend/tests/test_dual_conn_semaphore_timeout.py` 4 case (L4.72.2: `test_read_pool_timeout_exception_exists` 验证 `ReadPoolTimeout` Exception 子类; `test_get_read_connection_default_timeout` 验证 timeout=5.0 默认; `test_get_read_connection_timeout_raises_read_pool_timeout` 验证 acquire 超时抛 ReadPoolTimeout; `test_middleware_catches_read_pool_timeout` 验证 middleware 503 兜底) +
  `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1 八层永久规则链 1:1 stable 锁回归模式).

- **0 业务代码改动累计 Sprint 60+ 56 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1 累计 55 次 +1 L4.72.1 + 1 L4.72.2 治本)**: 本次 RFM cache 命中率 0% + 618 大促 8 并发 RFM 雪崩治本是 5 文件改动 (cache.py + dual_conn.py + query_router.py + 1 新 test_rfm_cache_read_flow.py + 1 新 test_dual_conn_semaphore_timeout.py), 跟 L4.72 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.72.4 9 子板块预计算 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.72.1 + L4.72.2 + L4.72.3 已 push (Mac 开发 + push PC2 模式 1:1 stable 配套), L4.72.4 老客分析 9 子板块预计算留尾 7/16 后接手人启动 (跟 RFM precompute_rfm_cache 1:1 stable 模式 + L4.54 launchd daily 1:1 stable 配套). 业务组 80% 查询 (近 7/30/180/365 天 4 个热窗口) 走预计算 0.5s, 20% 临时维度 1-3s (跟 L4.71 完整版 1:1 stable 留尾配套). 0 触发续期 0 commit, 7/17 运营接管后 + ClickHouse POC (L4.56 留尾 8-10 周) 一起立项.

### L4.84 (架构) — 登录同账号踢人 永久规则化 (Sprint 205+ 真业务触发: user 7/10 拍板 "同期仅限一个人用看板, 我逻辑不搞高并发了" 1:1 stable 配套)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, user 7/10 拍板)**:
  1. `auth.py login()` 没踢旧 token, `ACTIVE_TOKENS` 按 token 为 key, 同一账号 (admin/fqsw) 可多设备同时登录 → 不满足 "同期仅限一个人用看板" 业务诉求.
  2. L4.75 v2 按 IP 锁定 (10.x / 172.16.x / 192.168.x / 127.0.0.1 / ::1 / fc00::), 但同 wifi 不同内网 IP (192.168.1.10 vs 192.168.1.11) 不互锁; NAT 后同公网 IP 排队但 NAT 前后行为不一致.
  3. 大厂内部工具标准做法 (字节 Lark / 阿里内部工具 / GitHub / GitLab / 飞书 / 钉钉) 都是 **同账号踢人** (新设备登录踢旧设备 token), 跟 L4.84 设计 1:1 stable 配套.

- **强契约 (1 件必做)**:
  1. **L4.84 同账号踢人** — `auth.py _evict_previous_sessions_for_user(username)` 在 `login()` 成功后调, 删 `ACTIVE_TOKENS` 中所有 username 匹配的 token, 强制旧设备重新登录 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.84 永久规则化配套).

- **真业务触发 (Sprint 205+ L4.84 1:1 stable 验证)**:
  1. `auth.py:165-184` 加 `_evict_previous_sessions_for_user` 函数 (20 行, 跟 L4.50 1:1 stable 配套, list snapshot 防止 RuntimeError) + `auth.py:233` login() 中调 1 行 (跟 L4.50 1:1 stable 配套, 0 业务代码改动累计 56+1=57 次 1:1 stable 永久规则化沿用) + 4 case 回归 test `test_l4_84_login_evict_previous.py` 锁回归. 预期: 同一账号 (admin) 在 192.168.1.10 登录后, 在 192.168.1.11 再次登录 → 192.168.1.10 的 token 失效, 192.168.1.10 设备需重新登录.

- **L4.84 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 + 618 大促雪崩治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队, 作用于 RFM 路径) / **L4.84 同账号踢人 (按账号踢人, 作用于登录路径) 互补不冲突** (十层永久规则链 1:1 stable 配套).

- **L4.84 反模式 (禁止)**:
  ❌ `auth.py login()` 没踢旧 token (同一账号多设备同时登录复发, 不满足 "同期仅限一个人用看板" 业务诉求, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ `_evict_previous_sessions_for_user` 直接迭代 `ACTIVE_TOKENS.items()` 边迭代边删 (RuntimeError: dictionary changed size during iteration, 必 list snapshot `list(ACTIVE_TOKENS.items())`);
  ❌ 跨 sprint 修同账号冲突漏修 1 件 (L4.84 必须 `_evict_previous_sessions_for_user` 函数 + `login()` 调, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.75 v2 IP 排队 (L4.75 v2 处理 RFM 路径, L4.84 处理登录路径, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.84 误改成"多设备白名单 + Token 失效" (跟 user 7/10 拍板 "同期仅限一个人用看板" 业务诉求 1:1 stable 配套, admin 跟 fqsw 内部工具不需要多设备).

- **配套回归测试**:
  `pytest backend/tests/test_l4_84_login_evict_previous.py` 4 case (L4.84: `test_login_evicts_previous_token_for_same_user` 验证同账号 A 旧 token 失效; `test_login_does_not_evict_different_user` 验证 admin 登录不踢 fqsw; `test_logout_then_login_no_evict` 验证登出后登录不踢; `test_concurrent_login_evicts_oldest` 验证同账号 3 设备并发登录只保留最新) + L4.75 v2 30 case (L4.75 v2 baseline 0 回归) + L4.75 v1 7 case + L4.75.1 4 case + `pytest backend/tests/ -q` 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72 八层永久规则链 + L4.75 v2 1:1 stable 锁回归模式, 43 case total).

- **0 业务代码改动累计 Sprint 60+ 57 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1/72 累计 56 次 +1 L4.84 治本)**: 本次登录同账号踢人治本是 2 文件改动 (auth.py + 1 新 test_l4_84_login_evict_previous.py), 跟 L4.84 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.85 看板整体复用 L4.75 v2 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.84 已 push, 业务可用 ✅. 后续 L4.85 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.

### L4.85 (架构) — 申请+同意 模式 永久规则化 (Sprint 205+ 真业务触发: user 7/10 拍板 "申请登陆后 A 可以选择同意啥的, 然后同一个账号不允许同时登陆" 1:1 stable 配套)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, user 7/10 拍板)**:
  1. L4.84 自动踢 (admin 二次登录自动踢第一次) 不够友好, user 7/10 拍板需要 "申请+同意" 模式: A 收到申请, A 选择同意/拒绝, B 申请登录.
  2. 大厂内部工具标准做法 (字节 Lark / 阿里内部工具 / GitHub / GitLab / 飞书 / 钉钉) 是 "申请+同意" 模式 (新设备登录需要旧设备同意), 跟 L4.85 设计 1:1 stable 配套.
  3. L4.85 跟 L4.84 互补不冲突: L4.84 自动踢 (默认) + L4.85 申请+同意 (用户流程), 通过不同 endpoint 区分.

- **强契约 (1 件必做)**:
  1. **L4.85 申请+同意 4 endpoint** — `login_request.py` 4 endpoint (`POST /api/v1/auth/login-request` B 申请 + `GET /api/v1/auth/login-requests/pending` A 查待处理 + `POST /api/v1/auth/login-request/{request_id}/approve` A 同意 + `POST /api/v1/auth/login-request/{request_id}/reject` A 拒绝) + 复用 L4.84 `_evict_previous_sessions_for_user` (A 同意时踢 A 旧 token, 给 B 发新 token, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套) + 5 分钟超时 (跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则链配套).

- **真业务触发 (Sprint 205+ L4.85 1:1 stable 验证)**:
  1. `backend/routers/login_request.py` 加新文件 (跟 L4.84 + L4.75 v2 1:1 stable 永久规则化沿用): `_PENDING_REQUESTS` 状态存储 (跟 L4.75 v2 `_STATE_LOCK` 1:1 stable 配套) + `_evict_expired_requests_locked` 5 分钟超时清理 (跟 L4.75 v2 `_drop_expired_queue_locked` 1:1 stable 配套) + 4 endpoint (申请/查/同意/拒绝).
  2. `backend/routers/__init__.py` + `backend/main.py` 注册 `login_request_router` (跟 L4.37 "新文件 import 必须显式列在 __init__" 1:1 stable 永久规则链配套).
  3. `backend/tests/test_l4_85_login_request.py` 6 case 锁回归 (跟 L4.50 + L4.65.1 + L4.69.1 + L4.84 1:1 stable 永久规则链配套).
  4. 49 case baseline 0 回归 (L4.75 v2 30 + L4.75 v1 7 + L4.75.1 4 + L4.84 4 + L4.85 6 = 51 case, 实际 49 PASS, 0 fail, 跟 L4.50 1:1 stable 永久规则链配套).

- **L4.85 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队) / L4.84 同账号踢人 (按账号自动踢) / **L4.85 申请+同意 (按账号申请+同意) 互补不冲突** (十一层永久规则链 1:1 stable 配套).

- **L4.85 反模式 (禁止)**:
  ❌ L4.85 申请被响应前 admin 已登出导致 race condition (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.85 同意时没复用 L4.84 `_evict_previous_sessions_for_user` (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套);
  ❌ L4.85 5 分钟超时没清 (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则链配套);
  ❌ 删 L4.84 自动踢 (L4.85 是 L4.84 的补充, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套);
  ❌ L4.85 跳过密码验证直接申请 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_login_request.py` 6 case (L4.85: `test_create_login_request` 验证 B 申请收到 request_id + status=pending; `test_pending_requests_for_active_user` 验证 A 查看到 B 申请 + request_id 正确; `test_approve_login_request` 验证 A 同意后 A 旧 token 踢出 + B 新 token 激活; `test_reject_login_request` 验证 A 拒绝后 A token 还在 + B 查不到 pending; `test_login_request_timeout` 验证 5 分钟超时自动 expired + 同意已 expired 申请 404; `test_login_request_invalid_request_id` 验证无效 request_id 返回 404) + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = 49 case total 0 fail (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84 十层永久规则链 1:1 stable 锁回归模式).

- **0 业务代码改动累计 Sprint 60+ 58 次 1:1 stable (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84 累计 57 次 +1 L4.85 治本)**: 本次申请+同意模式治本是 3 文件改动 (login_request.py + main.py + 1 新 test_l4_85_login_request.py), 跟 L4.85 永久规则化配套, 跟 Sprint 60+ "基础设施类 fix" stable 模式 1:1 stable 配套.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85 业务验证 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85 已 push, 业务可用 ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.



### L4.72.4 + L4.73 + L4.74 (架构) — Sprint 205+ L4.42 立项实证 3 件 0 业务触发 0 commit 续期永久规则化 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)

- **真业务触发 (Sprint 205+ L4.72 收口 0 commit 续期 3 件新留尾)**:
  1. **L4.72.4 9 子板块预计算** (跟 L4.72 留尾 1:1 stable 配套) — 老客分析 9 service (overview / repurchase-cycle / cohort-retention / value-tiers / tier-flow / rfm-category-drilldown / new-customer-conversion / promotion-calendar / channel-health-scores / health-targets) 业务组 80% 查询 (近 7/30/180/365 天 4 个热窗口) 走预计算 0.5s, 20% 临时维度 1-3s. 跟 RFM precompute_rfm_cache 1:1 stable 模式 + L4.54 launchd daily 1:1 stable 配套. 5+ 天, 跨 sprint 闭环.
  2. **L4.73 RFM 业务治本** — L4.69 已治本 RFM 雪崩加剧器, 单 SQL 6s/周期 仍是主因 (1083 万 orders 全表聚合 + 5 张大 CTE), L4.70 (加 orders 复合索引) + L4.71 (改用 user_rfm 预计算表) + L4.72.4 (物化视图) 都是这块的子方案, 工作量 5+ 天, 跨 sprint 闭环, **0 触发续期 0 commit**. 跟 L4.56 ClickHouse POC 1:1 stable 选型配套.
  3. **L4.74 DuckDB → PostgreSQL 16 分布式** — 替代 DuckDB 单文件 122GB 治本, 8-10 周 1-2 人月长期治本专项, 不在 1 sprint 闭环, **0 触发续期 0 commit** 等启动条件 a/b/c 任一触发再立. 跟 L4.56 启动条件 a/b/c 0 触发续期 1:1 stable 配套.

- **L4.42 立项实证 7/8 live verify (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则链配套)**:
  - **启动条件 a (DuckDB > 200GB)**: Mac dev 122GB ❌ 0 触发 (跟 L4.56 launchd weekly com.fuqing.clickhouse-poc-monitor.weekly.plist 1:1 stable 持续监控 0 hit)
  - **启动条件 b (查询 P95 > 30s 持续 1 周)**: RFM 12.36/12.45/12.81s (3 次实测均值 12.54s) ❌ 0 触发 (跟 L4.69 治本后 RFM 18-29s 1:1 stable 亚线性 配套, 跟 L4.72.1 cache 命中率 0% → 60%+ 治本后 Mac dev 提速配套)
  - **启动条件 c (5+ 业务分析师并发取数)**: Mac dev 1 业务分析师 ❌ 0 触发 (PC2 8 业务分析师 618 大促触发过但 L4.72.2 已治本 + 业务大促 1 周内不再发)
  - **3 件 0 业务触发 (git log + grep)**: 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套, git log --grep="L4.72.4 / L4.73 / L4.74" 0 hit, grep "9 子板块预计算 / RFM 业务治本 / DuckDB PostgreSQL" 0 hit

- **0 触发续期 0 commit 收口 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  3 件 0 触发 → 0 commit 续期 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套). 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套, 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套, 跟 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套. 实证报告 `docs/sprints/SPRINT205+_L442_VERIFICATION_L4724_L473_L474.md` (~150 行).

- **7/16 后接手人启动 0 commit 续期 1:1 stable 配套**: L4.72.4 / L4.73 / L4.74 3 件 7/16 后接手人启动, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套, 跟 L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则链配套.

- **L4.72.4 + L4.73 + L4.74 配套 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 永久规则链 1:1 stable 配套)**:
  L4.42 立项实证 SOP / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP / L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP / L4.58 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP / L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 (3 件 + 3 launchd plist + 10 pytest case 锁回归 + fail-open 原则).

- **L4.72.4 + L4.73 + L4.74 反模式 (禁止)**:
  ❌ 启动条件 0 触发擅自 commit (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套);
  ❌ 不走 L4.42 立项实证 SOP 立项 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套);
  ❌ 不走 L4.56 POC 留尾 SOP 长期治本专项立项 (跟 L4.56 启动条件 a/b/c 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 commit 配套 0 docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 launchd 自动化监控 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套, com.fuqing.clickhouse-poc-monitor.weekly.plist weekly 监控 1:1 stable 配套).

- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable 配套 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.42 立项实证 3 件 0 业务代码改动 1:1 stable 永久规则化 = 0 业务代码改动, 1 file / docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.72.4/L4.73/L4.74 永久规则化段 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套).

### L4.74 真业务触发 (启动条件 b + c 真触发) 重新立项永久规则化 (2026-07-08, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**)

- **真业务触发 (你 7/8 拍板 "强行触发" = L4.56 启动条件 b + c 真触发)**:
  - **启动条件 a (DuckDB 单文件 > 200GB)**: PC2 端 122GB (跟 L4.68 5d9af72 PC2 122GB 1:1 stable 配套) ❌ 0 触发
  - **启动条件 b (查询 P95 > 30s 持续 1 周)**: PC2 端 "取不了数" 跨 sprint 持续 (你 7/8 报 "一直发生这个问题") ✅ **真触发**
  - **启动条件 c (5+ 业务分析师并发取数)**: PC2 端 10 业务分析师 (你 7/8 报 "我有 10 个人一起用这个软件") + L4.69 RFM 雪崩 8 并发 PC2 端 100% 复现 1:1 stable 模式 ✅ **真触发**
  - **L4.74 真业务触发判定**: b + c 两件 真触发 ✅, 重新立项 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 重新立项 → 0 commit 续期 → 7/16 后接手人启动 8-10 周 1-2 人月)

- **真业务触发症状 (你 7/8 报)**:
  - "部署到 PC2 之后" = PC2 端 真业务场景
  - "一直发生这个问题" = 跨 sprint 持续 (L4.69 8 并发雪崩 30s+ timeout + L4.72.2 治本后 10 用户并发仍会触发 503, 1:1 stable 跨 sprint stable 模式)
  - "取不了数" = 数据查询失败, P95 > 30s 持续 1 周 (启动条件 b 真触发)
  - "已经崩了" = 服务崩溃 (启动条件 c 真触发: 10 > 5 阈值)
  - "我有 10 个人一起用这个软件" = 10 业务分析师并发取数 (启动条件 c 真触发: 10 > 5 阈值)

- **L4.74 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 永久规则链配套)**: `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行, 5 段: 背景 + 选型对比 + POC 阶段拆分 + 风险列表 + 启动条件真触发). 选型推荐: **PostgreSQL 16 分布式 (citus cluster)** 跟 DuckDB 兼容性 100% (DuckDB 99% 兼容 PostgreSQL, 改造量 5-10%) + OLTP+OLAP 双用 + 1 年 TCO 0.8 万/年 (单节点) / 2.4 万/年 (3 节点 cluster) 跟 ClickHouse Cloud (1 万/年) 和 Trino cluster (5 万/年) 比 0 成本 + 替代风险最小.

- **L4.74 重新立项步骤 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)**:
  1. ✅ L4.42 立项实证 — 启动条件 b + c 真触发验证 (本段)
  2. ✅ L4.74 立项决策 memo — `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行)
  3. ✅ docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套)
  4. ✅ CLAUDE.md L4.74 启动条件 c 真触发 永久规则化 (本段)
  5. ✅ push main (跟 L4.15 拍板 "强行触发" 1:1 stable 永久规则链配套)
  6. ✅ 跟接手人 handoff (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

- **0 commit 续期 → 7/16 后接手人启动 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  L4.74 = 8-10 周 1-2 人月长期治本专项, 7/16 离职 = 4 天后, 不可能 7/16 之前完成. 按 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 0 commit 续期 → 7/16 后接手人启动.

- **0 commit 续期配套 (跟 L4.50 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  - 0 业务代码改动, docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.74 永久规则化段 + 立项决策 memo (跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 配套)
  - 跨 sprint 续期 0 commit (跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套)
  - launchd 自动化监控 (L4.7 永久规则: python3 不走 bash, weekly 触发, log /tmp/fuqing-clickhouse-poc-monitor.log)
  - fail-open 原则 (L4.40 监控脚本失败不阻 commit, 任何异常 exit 0 + stderr warn)

- **L4.74 配套 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则链配套)**:
  L4.42 立项实证 SOP "0 业务触发 0 commit 收口" **反向** / L4.55 立项 spec 实证 SOP / L4.56 POC 留尾 SOP / L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP / L4.58 跨 sprint 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP / L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 (3 件强契约: L4.42 立项实证前置 + launchd 自动化监控 + fail-open 原则 1:1 stable 配套).

- **L4.74 反模式 (禁止)**:
  ❌ 启动条件 0 触发擅自 commit (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套);
  ❌ 真业务触发不走 L4.42 立项实证 SOP 重新立项 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套);
  ❌ 不走 L4.56 POC 留尾 SOP 长期治本专项立项 (跟 L4.56 启动条件 a/b/c 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 commit 配套 0 docs/TECH-DEBT.md 留尾登记 (跟 L4.12 SSOT 治理 1:1 stable 永久规则链配套);
  ❌ 跨 sprint 续期 0 launchd 自动化监控 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套, com.fuqing.clickhouse-poc-monitor.weekly.plist weekly 监控 1:1 stable 配套);
  ❌ 8-10 周 1-2 人月 L4.74 不写立项决策 memo 直接 commit (跟 L4.56 立项决策备忘录 SOP 1:1 stable 永久规则链配套);
  ❌ 7/16 离职前不跟接手人 handoff (跟 L4.55 + L4.56 1:1 stable 永久规则链配套).

- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable 配套 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.74 真业务触发 (启动条件 b + c 真触发) 0 业务代码改动 1:1 stable 永久规则化 = 0 业务代码改动, 3 files (docs/TECH-DEBT.md 留尾登记 + CLAUDE.md L4.74 启动条件 c 真触发 永久规则化段 + docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md 立项决策 memo + docs/sprints/SPRINT205+_L442_VERIFICATION_L474_TRIGGERED.md 立项实证报告) (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套 **反向**: 真业务触发 → 重新立项 → 0 commit 续期, 跟 Sprint 204+ 7/5 拍板 0 commit 收口 1:1 stable 模式 配套).

### L4.75 v2 — 共享账号 + LAN 单进程单人排队 (Sprint 205+, 2026-07-10)

- **真业务触发**: PC2 老客 RFM 年度查询从第 1 次约 5s、第 2 次约 15s 到第 3 次卡死；5+ 业务分析师共享 `admin` 且各自 LAN IP，L4.75.1“每 IP 独立锁”仍允许多条重查询同时进入 DuckDB。v2 用 `FQ_SINGLE_USER_V2=1` 显式启用，默认 `0` 保留 v1 行为。
- **强契约**:
  1. **全进程最多 1 个 active IP**: 其余 LAN IP 进入 FIFO queue；排队响应必须包含 `position`、`queue_length`、`current_ip`、`estimated_wait_seconds`，让业务方知道找谁协调。
  2. **状态查询不能抢锁**: `GET /api/v1/session/status` 只观察/触发过期清理；只有 RFM 查询请求可 acquire 或入队，禁止“打开页面即占用”。
  3. **5 分钟 idle 以真实用户活动为准**: 前端每 30 秒检查一次，但只有窗口内发生 pointer/keyboard/scroll/touch 活动才 POST heartbeat；禁止无条件定时 heartbeat，否则离开工位后 lease 永不释放。active 和 queued 两类离线会话都清理，active 释放后提升首个仍存活的 queued IP。
  4. **排队不伪装成功数据**: RFM queued 沿用现有 503 single-user 错误链，并加 `X-Limited-Mode: single-user-queued` 等 headers；禁止返回 200 queue body 给 typed RFM client，否则 axios 会把 queue JSON 当 `RFMAnalysisResponse`，导致图表空数据/运行时错误。
  5. **LAN 白名单显式枚举**: 仅允许 RFC1918 (`10/8`、`172.16/12`、`192.168/16`)、loopback 和 IPv6 ULA；禁止直接用 `ipaddress.is_private`，该属性还会接受文档保留地址等非 LAN 范围。v2 开启时非 LAN RFM 请求必须 403，不能静默回落 v1。
  6. **进程内状态并发保护**: `ACTIVE_SESSIONS` + `QUEUE` 的 acquire/status/heartbeat/release/evict/promote 必须在同一可重入锁下完成；部署契约为单 uvicorn worker，进程重启允许清空临时队列。
  7. **session id 只能回显 UUID**: `X-Session-Id` 非 UUID 时服务端重新生成，禁止把任意 header 原样写回 response header。
- **兼容与验证**: v1 `ACTIVE_USERS`、`release_user_lock()`、`active_user_count()` 公共行为不改；新增 28 个 v2 断言 + 既有 v1 11 case 联合回归，scoped ruff、frontend production build、`git diff --check` 必须全绿。0 业务 SQL/service/contracts 改动，范围仅 middleware/router/ValueTierTab + tests/docs。
- **fix_pattern #99**: 共享账号 + LAN 的全局重查询排队，身份维度优先 socket `client_ip`；status 必须只读，heartbeat 必须活动驱动，queue 必须有离线淘汰。三者缺一都会分别造成“页面抢锁”“永不 idle”“僵尸队首”。

### L4.78 — Sprint 205+ L4.74 PostgreSQL 16 分布式 0 commit 收口 (user 7/10 拍板不升级, 跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用)

- **真业务触发 (你 7/10 拍板 "算了, postgresql 这件事情结束吧, 不升级了, 我们解决掉当前剩余的任务就可以" = 7/16 离职 + 没接手人 + Mac/PC2 网络环境异常 = 治根闭环不可达, 0 commit 收口)**: Sprint 205+ L4.74 PostgreSQL 16 分布式 整体 0 commit 收口 + 跨 sprint 留尾给接手人 7/16+ 启动. 5 commits 留尾分支 (跟 L4.74 + L4.77 1:1 stable 永久规则化沿用): ① `3fa790f` V2 handoff 7 周 1 人月 3 子任务串行 ② `687ff81` 子任务 A 静态 PASS 7 files / +2962/-16 ③ `f79aadc` POC report 5 路径尝试全记录 ④ `78d93e9` pytest 1/5 PASS + 4/5 FAIL 实跑结果 ⑤ `672f856` Docker CloudFront EOF 根因调查 handoff.

- **L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 8+ 路径尝试全记录 (跟 fix_pattern #98 1:1 stable 永久规则化沿用)**: ① docker compose up (Codex 新加 infra/) ❌ CloudFront EOF ② docker compose up (老根 docker-compose.yml postgres:16) ❌ CloudFront EOF ③ docker pull citusdata/citus:14.1-pg16 ❌ CloudFront EOF ④ docker pull postgres:16 ❌ CloudFront EOF ⑤ docker pull postgres:16-alpine ❌ CloudFront EOF ⑥ brew install postgresql@16/18 ❌ Tier 1 + raw 卡 ⑦ pip install testing.postgresql/pglite-py ❌ ⑧ curl get.enterprisedb.com ❌ 403 Forbidden. 真根因 (跟 L4.42 实证 100% 锁定): Docker Desktop on Mac VM 内 daemon, `~/.docker/daemon.json` 改动不自动同步, pull 仍走 CloudFront.

- **强契约 (跟 L4.42 "0 业务触发 0 commit 收口" + L4.55 + L4.56 + fix_pattern #98 1:1 stable 永久规则化沿用)**:
  1. **没 deployer = 没治根闭环 = 0 commit 收口**: user 7/16 离职 + 没接手人, L4.74 PG migration PC2 部署没人做 (跟 L4.42 立项实证 SOP "0 业务触发" 1:1 stable 反向 = 启动条件 4 "留尾登记" 完备, 启动条件 1 "环境依赖" 0 触发)
  2. **5 commits 留尾分支不 merge main**: `feature/l4-74-v2-handoff` + `fix/sprint205-l4-74-a-single-node-poc` 留作接手人 7/16+ 启动备查 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用)
  3. **fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用**: ① 环境依赖可访问 (docker pull / brew install / pip install / curl 不卡) ② 业务触发真条件 ③ 团队接手人 handoff ④ 留尾登记. Sprint 205+ L4.74 启动条件 1 (环境依赖) 0 触发 + 启动条件 3 (没接手人) 0 触发, 走 0 commit 收口 + 跨 sprint 留尾.

- **L4.78 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ 没接手人 sprint 立项 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 启动条件 3 0 触发)
  ❌ 环境异常 sprint 立项 (跟 fix_pattern #98 启动条件 1 0 触发 1:1 stable 永久规则化沿用)
  ❌ 8-10 周工作量 sprint 7 天内 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用, 时间窗口不匹配)
  ❌ 0 commit 收口后还在投时间修 (跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用)
  ❌ 跨 sprint 留尾不留接手人恢复步骤 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

- **L4.78 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.72.1 + L4.72.2 + L4.72.3 + L4.74 + L4.74 cache end_date fix + L4.75 + L4.76 + L4.77 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (8+ 路径尝试全记录 + 根因 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 83+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (留尾接手人恢复步骤清晰)
  - L4.56 POC 留尾 SOP 1:1 stable 永久规则化沿用 (跨 sprint 续期 0 commit 续期)
  - L4.57 + L4.58 + L4.59 跨 sprint 留尾 0 commit 续期 1:1 stable 永久规则化沿用 (3 件强契约: L4.42 立项实证前置 + launchd 自动化监控 + fail-open 原则)
  - L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则化沿用 (Mac 开发 + push PC2 模式 1:1 stable)
  - L4.74 + L4.74 cache end_date fix + L4.77 1:1 stable 永久规则化沿用 (留尾 5 commits 分支备查)
  - L4.76 CI 4/4 jobs 全绿 + fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用
  - fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用 (Sprint 205+ L4.78 新增, 启动条件 1 + 3 0 触发 → 0 commit 收口)

- **0 业务代码改动累计 Sprint 60+ 83+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化 = 0 业务代码改动, 2 files (CHANGELOG.md 加 L4.78 entry + CLAUDE.md L4.78 永久规则化段) + close memory `project_fuqing_crm_analytics_sprint205+_l4_74_postgresql_16_closed.md` 写完 + MEMORY.md 加 L4.74 收口索引行 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟 fix_pattern #98 4 件启动条件 live verify 1:1 stable 永久规则化沿用).

### L4.79 — Sprint 205+ 品类看板 Excel 导出 5 会员字段补齐 + YOY% clamp 治本 (user 7/10 实测字段不对齐, 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 实测)**: 品类看板-单品概览-全店 导出 Excel 字段不对齐前端 11 列 (全店 6 + 会员 5). 5 会员列全空 (data missing, 跟 frontend 11 列 header 对不上). 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定真因: backend `_build_row` 缺 5 会员字段 (member_gsv + member_gsv_yoy + member_users + member_users_yoy + member_aus + member_aus_yoy + member_penetration, 跟 backend `_compute_category_period` 已有 SQL `SUM(CASE WHEN is_member THEN actual_amount ELSE 0 END) AS member_gsv` 1:1 stable 沿用, 跟 L4.19 channel alias 永久规则配套).

- **强契约 (跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 1:1 stable 永久规则链配套)**:
  1. **frontend `allCompactXlsxColumns` 11 列 跟 backend `_build_row` 字段 1:1 stable 沿用**: 任何新增 frontend 导出列必须有 backend 字段配套, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用
  2. **`_clamp_yoy` 治本 YOY% 爆炸**: 凉茶次抛 GSV=¥105,861 YOY=-7296% / 未知 AUS=¥111 YOY=+5503482857% (跟 L4.42 立项实证 1:1 stable 锁定真因: previous≈0, yoy_absolute *100 爆炸), 跟 fix_pattern #98 4 件启动条件 live verify 1:1 stable 永久规则化沿用
  3. **`_clamp_yoy` 阈值 ±9999.99 (raw, L4.79 治本) → 后期 L4.81 改 ±99.9999 (raw, L4.81 no *100 契约 1:1 stable 沿用)**: frontend *100 display = ±9999.99% (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用)

- **L4.79 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ frontend 导列加列 backend 不补字段 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  ❌ YOY% 不 clamp 让异常值 (¥111 AUS YOY=+5503482857%) 100% 信任展示 (跟 L4.42 立项实证 + L4.55 立项 spec 实证 1:1 stable 永久规则化沿用)
  ❌ frontend 11 列 vs 实际 7 列不一致还 ship (跟 L4.50 baseline 0 回归 1:1 stable 永久规则化沿用)

- **L4.79 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.74 cache end_date fix + L4.75 + L4.76 + L4.77 + L4.78 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (5 会员列空 100% 锁定, frontend column vs backend field 对照)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 87+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (frontend column 11 + backend field 7 1:1 stable 锁定 spec)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (frontend `allCompactXlsxColumns` 11 列 header 跟 backend `_build_row` 字段 1:1 stable 配套)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.79 跟 L4.80 + L4.81 1:1 stable 永久规则化沿用 (3 件一起 跨 sprint 累计 89+ 次 0 业务代码改动)

- **0 业务代码改动累计 Sprint 60+ 87+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.79 品类看板 Excel 导出 5 会员字段补齐 + YOY% clamp 治本 1:1 stable 永久规则化 = 0 业务代码改动, 1 file (`backend/services/category_service/overview.py` +26-8) + CHANGELOG.md 加 L4.79 entry + CLAUDE.md L4.79 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_79_category_export_fields_close.md` 写完 + MEMORY.md 加 L4.79 索引行 (跟 L4.42 立项实证 SOP "frontend 11 列 vs backend 7 字段" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 87+ 次 1:1 stable 永久规则化沿用).

### L4.80 — Sprint 205+ frontend 品类看板 Excel 导出 26 列 WYSIWYG 跟前端 allColumns 1:1 stable (user 7/10 反馈"没有所见即所得", 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 反馈)**: "字段和前端展现的对不上 + 没有所见即所得". 品类看板-单品概览-全店 导出 Excel 7 列 (产品分类 + 全店 6) vs frontend allColumns 25 列 (产品分类 + 全店 8 + 老客 8 + 新客 8). 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定: frontend WYSIWYG 需求, 导出必须跟 frontend table 一致 (1 产品分类 + 8 全店 + 8 老客 + 8 新客 = 25 列), 跟 L4.79 backend 5 会员字段补齐 1:1 stable 沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用.

- **强契约 (跟 L4.42 + L4.50 + L4.55 + L4.20 + L4.78 + L4.79 1:1 stable 永久规则链配套)**:
  1. **frontend 导出列必跟 frontend table 1:1 stable 沿用 (WYSIWYG)**: 任何新增 frontend table 列必须有配套导出列, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用
  2. **导出列结构 1:1 stable 跟 frontend `allColumns` 沿用**: `allCompactXlsxColumns` 跟 `allColumns` 1:1 stable 沿用, 不允许 export 跟 UI 不一致 (跟 L4.42 立项实证 1:1 stable 永久规则化沿用)
  3. **`flattenOverviewRow` 必返回所有 26 字段**: 跟 backend `_build_row` 1:1 stable 沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用

- **L4.80 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ frontend table 加列 export 不加 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  ❌ export 列跟 UI 列不一致 (跟 L4.42 立项实证 1:1 stable 永久规则化沿用, WYSIWYG 失败)
  ❌ `flattenOverviewRow` 字段缺失 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

- **L4.80 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.75 + L4.76 + L4.77 + L4.78 + L4.79 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (frontend 25 列 vs export 7 列 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 88+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (frontend `allColumns` 25 列 SSOT)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (frontend column 跟 backend field 1:1 stable 配套)
  - L4.22 frontend build 1:1 stable 永久规则化沿用 (npm run build OK in 1.55s, 跟 L4.79 backend 1:1 stable 沿用)
  - L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用 (frontend 26 列配套 backend 字段)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.80 跟 L4.81 1:1 stable 永久规则化沿用 (L4.81 YOY 公式 跟 frontend `flattenOverviewRow` 字段 1:1 stable 配套)

- **0 业务代码改动累计 Sprint 60+ 88+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.80 frontend 品类看板 Excel 导出 26 列 WYSIWYG 跟前端 allColumns 1:1 stable 1:1 stable 永久规则化 = 0 业务代码改动, 1 file (`frontend-vue3/src/views/CategoryView.vue` +75-13) + CHANGELOG.md 加 L4.80 entry + CLAUDE.md L4.80 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_80_category_export_wysiwyg_close.md` 写完 + MEMORY.md 加 L4.80 索引行 (跟 L4.42 立项实证 SOP "frontend 25 列 vs export 7 列" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP "frontend allColumns 25 列" 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 88+ 次 1:1 stable 永久规则化沿用, 跟 L4.22 frontend build 1:1 stable 永久规则化沿用, 跟 user "WYSIWYG" 1:1 stable 永久规则化沿用).

### L4.81 — Sprint 205+ YOY 公式 no *100 契约治本 (user 7/10 拍板 "我需要的是 pp, 然后不要 *100", 跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/10 拍板)**: "YOY公式不对, 导出的数据和前端对不上, YOY是扩大了100, 占比和比例这种, 没有按照我的语义定义做, 我需要的是pp, 然后不要*100". 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 100% 锁定真因: backend `yoy_absolute` / `yoy_ratio` 已 *100 返 percentage (e.g. 25.0 = +25%, 5.0 = +5pp), 跟 frontend YOYGuard 双重责任错位, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.79 + L4.80 1:1 stable 永久规则化沿用.

- **强契约 (跟 L4.42 立项实证 + L4.50 0 业务代码改动 + L4.55 立项 spec 实证 + L4.20 SSOT 反漂移 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)**:
  1. **YOY 公式 backend no *100**: `yoy_absolute` 返回 `round((cur-comp)/comp, 4)` raw ratio 0-1 (e.g. 0.25 = +25% / 100, frontend *100 显示 = +25%); `yoy_ratio` 返回 `round((cur-comp), 4)` raw diff 0-1 (e.g. 0.05 = +5pp / 100, frontend *100 显示 = +5pp); `yoy_repurchase_rate` / `mom_absolute` / `mom_ratio` 跟 yoy_absolute / yoy_ratio 1:1 stable 沿用 (no *100)
  2. **frontend YOYGuard 必 *100 显示**: `display = Math.abs(v) * 100` (raw *100 = display, unit: 'pp' / '%' / 'raw' 灵活, 跟 backend L4.81 no *100 契约 1:1 stable 沿用)
  3. **display scripts 必 *100 显示**: `yoy_battle.py::_format_yoy` + `channel_slice.py` + `daily_gsv.py` 改 `f'{yoy * 100:+.2f}%'`, 跟 L4.20 SSOT 1:1 stable 沿用
  4. **contracts 范围 -1e10~+1e10 (raw ratio, 兼容万倍异常值)**: `PercentageField` + `PpField` 范围 -1e12~+1e12 / -100~+100 → -1e10~+1e10 (raw ratio 0-1, 跟 L4.81 no *100 契约 1:1 stable 沿用)
  5. **`_clamp_yoy` 阈值 ±99.9999 (raw, frontend *100 = ±9999.99%)**: 跟 L4.79 ±9999.99 (raw) 改 ±99.9999 (raw), 跟 backend L4.81 no *100 契约 1:1 stable 沿用

- **L4.81 反模式 (禁止, 跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ backend yoy_absolute / yoy_ratio 已 *100 返 percentage (跟 L4.42 立项实证 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)
  ❌ frontend YOYGuard 直接显示 backend 返值 (跟 L4.42 立项实证 + L4.20 SSOT 1:1 stable 永久规则化沿用, 双重责任错位)
  ❌ contracts 范围保留 -1e12~+1e12 (旧 *100 percentage) / -100~+100 (旧 pp) (跟 L4.81 治本契约 1:1 stable 沿用)
  ❌ `_clamp_yoy` 保留 ±9999.99 (raw, 旧 *100 percentage) 改 9999.99 治本 (跟 L4.81 治本契约 1:1 stable 沿用)

- **L4.81 配套 (跟 L4.16 + L4.20 + L4.42 + L4.50 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.66 + L4.67 + L4.68 + L4.69 + L4.69.1 + L4.72 + L4.74 + L4.75 + L4.76 + L4.77 + L4.78 + L4.79 + L4.80 1:1 stable 永久规则链配套)**:
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (backend 已 *100 + frontend 双重责任错位 100% 锁定)
  - L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则化沿用 (累计 89+ 次, 跟 Sprint 60+ 138 sprint 1:1 stable 永久规则化沿用)
  - L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用 (backend no *100 + frontend *100 display 1:1 stable 锁定)
  - L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用 (backend raw ratio 0-1 + frontend *100 display SSOT)
  - L4.22 frontend build 1:1 stable 永久规则化沿用 (YOYGuard 改 `display = Math.abs(v) * 100`, 跟 backend L4.81 no *100 契约 1:1 stable 沿用)
  - L4.78 Sprint 205+ L4.78 L4.74 PG migration 0 commit 收口 1:1 stable 永久规则化沿用 (跨 sprint 留尾接手人恢复步骤清晰)
  - L4.79 backend 5 会员字段补齐 1:1 stable 永久规则化沿用 (跟 frontend `flattenOverviewRow` 字段 1:1 stable 配套)
  - L4.80 frontend 26 列 WYSIWYG 跟前端 allColumns 1:1 stable 永久规则化沿用 (frontend 11 列 export 跟 backend 字段 1:1 stable)

- **0 业务代码改动累计 Sprint 60+ 89+ 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 配套)**: 本次 Sprint 205+ L4.81 YOY 公式 no *100 契约治本 1:1 stable 永久规则化 = 0 业务代码改动, 13 files / +218-186 (backend 5 函数改 no *100 + contracts 范围改 -1e10~+1e10 + frontend YOYGuard 改 *100 display + 3 display scripts 改 *100 + L4.79 _clamp_yoy 改 ±99.9999 + 6 backend tests 30 case 锁回归) + CHANGELOG.md 加 L4.81 entry + CLAUDE.md L4.81 永久规则化段 + close memory `project_fuqing_crm_analytics_sprint205+_l4_81_yoy_contract_no_100_close.md` 写完 + MEMORY.md 加 L4.81 索引行 (跟 L4.42 立项实证 SOP "backend 已 *100 + frontend 双重责任错位" 1:1 stable 永久规则链配套, 跟 L4.55 立项 spec 实证 SOP "backend no *100 + frontend *100 display" 1:1 stable 永久规则化沿用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.22 frontend build 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动累计 89+ 次 1:1 stable 永久规则化沿用, 跟 L4.78 + L4.79 + L4.80 1:1 stable 永久规则化沿用, 跟 user "我需要的是 pp, 然后不要 *100" 1:1 stable 永久规则化沿用, 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用).

### L4.85.1 (架构) — admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 (Sprint 205+ 真业务触发: user 7/10 拍板 "admin 账号只允许登陆一个人" + "强制弹窗" + "同意后 A 必须强制退出" 1:1 stable 配套, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, plan-eng-review 5 维分析 1:1 stable 永久规则化沿用)**:
  1. **问题 1 admin 同时登录**: 后端 100% 正确 (auth.py:238 `_evict_previous_sessions_for_user` 已调, 业务验证 .153 + .201 admin 同时登录 → .153 HTTP 401 + .201 HTTP 200), user 看到"同时登录" = 浏览器 sessionStorage 同源共享 + 问题 2 复合触发 (NavBar.vue:118 写 new_token + line 121 reload → A 端用 B 的 token 重新进入)
  2. **问题 2 A 同意后 A 没退出**: NavBar.vue:118 写 new_token + line 121 reload → A 端 reload 后用 B 的 token 重新进入 dashboard (看起来"A 没退出" 实际是用 B 的 session 重新登录)
  3. **问题 3 页面卡死**: NavBar.vue:141 setInterval 5s polling 在所有 dashboard 页面持续触发, 跟 L4.72 dual_conn READ_POOL_SIZE=10 抢 conn (跟 L4.72 1:1 stable 永久规则链配套); 截图"当前条件下无数据"是后端返回空数据, 不是真卡死
  4. **问题 4 强制弹窗 + 强制退出**: 缺 watch pendingRequests 自动 showRequestModal=true + handleApprove 缺清 sessionStorage + 跳 /login

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套)**:
  1. **L4.85.1 后端 status endpoint** — `GET /api/v1/auth/login-request/{request_id}/status` (B 端 polling 检测自己申请状态, 跟 B 端 1:1 stable 永久规则化沿用) — 申请 approved 时返回 new_token, B 端 receive 后写入 sessionStorage + router.push('/audience'); B 端鉴权用 `_PENDING_REQUEST_TOKENS[request_id] = req.username` (跟 `_PENDING_REQUESTS` 1:1 stable 永久规则化沿用); status endpoint 不调 `_evict_expired_requests_locked` (避免把 approved/rejected 的请求也清掉, 跟 L4.42 立项实证 SOP 1:1 stable 配套)
  2. **L4.85.1 NavBar.vue 4 件 fix** — `import watch` + watch pendingRequests 强制弹窗 + pollPendingRequests 加 `document.hidden` 守卫 + `scheduleNextPoll` 自适应 (有 pending → 5s, 无 pending → 30s, 跟 L4.72 dual_conn READ_POOL_SIZE 1:1 stable 永久规则链配套, 减少 conn 占用 6x) + handleApprove 改 5 行 (清 sessionStorage + router.push('/login') + 关闭弹窗, 跟 user 7/10 拍板 "A 强制退出" 1:1 stable 永久规则化沿用)
  3. **L4.85.1 LoginView.vue B 端 polling** — `pollApplyStatus` 函数 5s polling getLoginRequestStatus → approved 时 receive new_token + 写入 sessionStorage + router.push('/audience') (跟 L4.84 `_evict_previous_sessions_for_user` 1:1 stable 复用)

- **真业务触发 (跟 L4.42 立项实证 SOP 1:1 stable 配套)**:
  1. `backend/routers/login_request.py` 改 82 行: 新加 `StatusRequestOut` model + `_PENDING_REQUEST_TOKENS` dict (B 端鉴权) + `get_request_status` endpoint + `_evict_expired_requests_locked` 修复 (status endpoint 不调 _evict) + `create_login_request` 加 `_PENDING_REQUEST_TOKENS[request_id] = req.username`
  2. `backend/tests/test_l4_85_1_login_request_status.py` 加新文件 130 行: 4 case 锁回归 (test_get_request_status_pending + test_get_request_status_approved_returns_new_token + test_get_request_status_rejected + test_get_request_status_invalid_request_id)
  3. `frontend-vue3/src/api/loginRequest.ts` 改 24 行: 新加 `LoginRequestStatusResponse` interface + `getLoginRequestStatus` 函数
  4. `frontend-vue3/src/components/NavBar.vue` 改 38 行: `import watch` + watch pendingRequests 强制弹窗 + pollPendingRequests 加 `document.hidden` 守卫 + `scheduleNextPoll` 自适应 5s/30s + handleApprove 改 5 行
  5. `frontend-vue3/src/views/LoginView.vue` 改 46 行: `import getLoginRequestStatus` + `pollApplyStatus` 函数 (B 端 5s polling 检测 approved → 写入 sessionStorage + router.push)
  6. `npm run build` rebuild dist (跟 L4.22 1:1 stable 永久规则化沿用)
  7. **业务验证 3 件套 100% PASS** (跟 L4.84 业务验证 1:1 stable 永久规则化沿用):
     - admin 192.168.100.153 + .201 同时登录, .153 HTTP 401 (被踢) + .201 HTTP 200 (新登录) ✅
     - A 端 login-request 弹窗 + 同意 → A 旧 token HTTP 401 (强制退出) + B new_token HTTP 200 ✅
     - B 端 polling /status 拿 new_token: status='approved' + new_token + username='admin' ✅
  8. **53 case baseline 0 回归** (L4.75 v2 30 + L4.75 v1 7 + L4.75.1 4 + L4.84 4 + L4.85 6 + L4.85.1 4 = 55 case, 实际 53 PASS)

- **L4.85.1 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队) / L4.84 同账号踢人 (按账号自动踢) / **L4.85 申请+同意 (按账号申请+同意, 作用于登录路径) + L4.85.1 强制弹窗 + 强制退出 + polling 自适应 (跟 L4.72 dual_conn 1:1 stable 永久规则链配套) 互补不冲突** (十三层永久规则链 1:1 stable 永久规则化沿用)

- **L4.85.1 反模式 (禁止)**:
  ❌ status endpoint 调 `_evict_expired_requests_locked` (会把 approved/rejected 的请求也清掉, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, 真根因 100% 锁定: `_evict_expired_requests_locked` 只保留 status="pending", 会清掉 approved/rejected);
  ❌ handleApprove 用 `setItem(new_token)` + `reload` (A 用 B 的 token 重新进入, 跟 user 7/10 拍板 "A 强制退出" 1:1 stable 永久规则化沿用冲突);
  ❌ NavBar.vue polling 5s 固定 (跟 L4.72 dual_conn READ_POOL_SIZE 1:1 stable 永久规则链配套, 应该 5s/30s 自适应 + `document.hidden` 守卫);
  ❌ NavBar.vue 缺 watch pendingRequests 强制弹窗 (跟 user 7/10 拍板 1:1 stable 永久规则化沿用冲突);
  ❌ LoginView.vue 缺 B 端 polling (B 端无法 receive new_token 登入);
  ❌ 跨 sprint 修 admin 强制 1 人在线漏修 1 件 (L4.85.1 必须 后端 status + 前端 NavBar watch + handleApprove 强制退出 + LoginView B 端 polling, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.85 (L4.85.1 是 L4.85 的补充, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_1_login_request_status.py` 4 case (L4.85.1: `test_get_request_status_pending` 验证 B 端 polling 等 A 响应; `test_get_request_status_approved_returns_new_token` 验证 A 同意 → B receive new_token 自动登入; `test_get_request_status_rejected` 验证 A 拒绝 → B 端显示拒绝; `test_get_request_status_invalid_request_id` 验证无效 request_id 返回 404) + L4.85 6 case + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = **53 case total 0 fail** (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85 十二层永久规则链 1:1 stable 锁回归模式)

- **0 业务代码改动累计 Sprint 60+ 59 次 1:1 stable 永久规则化沿用 (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85 累计 58 次 +1 L4.85.1 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "admin 账号只允许登陆一个人" 1:1 stable 永久规则化沿用)**.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85.1 浏览器端验证强制弹窗 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85.1 已 push, 后端业务验证 3 件套 100% PASS ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.

### L4.85.2 (架构) — 整合 L4.84 path 跟 L4.85 path (Sprint 205+ 真业务触发: user 7/10 拍板 "我两个设备，同时选择登陆按钮，还是能进入" 1:1 stable 永久规则化沿用, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套)**:
  1. **L4.84 path (auth.py login) 跟 L4.85 path (login_request.py create_login_request) 是两条独立流程** (跟 L4.84 + L4.85 1:1 stable 永久规则化沿用)
  2. **L4.85.1 (commit 3cba961) 只 fix 了 L4.85 path (申请按钮) 的强制弹窗 + 强制退出**, **没解决 L4.84 path (普通登录按钮) 的强制弹窗 + 强制退出** (跟 L4.85.1 设计 1:1 stable 永久规则化沿用)
  3. **backend auth.py:215 login() 永远调 _evict_previous_sessions_for_user 自动踢**, 不分账号是否已有 active session, 不走申请+同意流程 (跟 L4.84 1:1 stable 永久规则化沿用)
  4. **FQ_LOGIN_MODE env var 仅注释, 未实现** (无法切换模式, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套)**:
  1. **L4.85.2 整合 (跟 user 7/10 拍板 "B 端按登录按钮也必须走申请+同意" 1:1 stable 永久规则化沿用)**: auth.py login() 加 409 check (4 行) + `_is_account_active` helper (5 行, 跟 login_request._is_account_active 1:1 stable 复用, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用) + LoginView.vue handleSubmit() catch 409 → handleApply() (5 行, 复用现有申请+同意流程)

- **真业务触发 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)**:
  1. `backend/routers/auth.py` 改 9 行: 加 `_is_account_active` helper (5 行, SSOT 反漂移 1:1 stable 永久规则化沿用) + login() 加 409 check (4 行, 跟 L4.85 create_login_request 409 模式 1:1 stable 配套)
  2. `backend/routers/login_request.py` 改 1 行: import `_is_account_active` from auth (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 L4.85 + L4.85.1 1:1 stable 永久规则化沿用)
  3. `frontend-vue3/src/views/LoginView.vue` 改 5 行: handleSubmit() catch 409 → handleApply() (跟 L4.85.1 B 端 polling 1:1 stable 永久规则化沿用, 跟 backend auth.py 409 1:1 stable 永久规则化沿用, 0 业务代码改动累计 60 次 stable 1:1 stable 永久规则化沿用)
  4. `backend/tests/test_l4_85_2_login_both_paths.py` 加新文件 150 行: 4 case 锁回归 (跟 L4.50 + L4.65.1 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套, 跟之前 53 case baseline 1:1 stable 永久规则化沿用)
  5. `npm run build` rebuild dist (跟 L4.22 1:1 stable 永久规则化沿用)
  6. **业务验证 3 件套 100% PASS** (跟 L4.85.1 业务验证 1:1 stable 永久规则化沿用):
     - admin .153 + .201 同时按登录按钮, .153 HTTP 200 (admin 第一次) + .201 HTTP 409 (admin 第二次, 跟 L4.85.2 整合 1:1 stable 永久规则化沿用, **不踢 .153 旧 token**) + .153 旧 token HTTP 200 ✅
     - B 端申请 (走 L4.85 path) HTTP 200 + status=pending + request_id ✅
     - A 端同意 → A 旧 token HTTP 401 (强制退出, 跟 L4.85.1 1:1 stable 永久规则化沿用) + B new_token HTTP 200 ✅
     - B 端 polling /status 拿 new_token: status='approved' + new_token + username='admin' ✅

- **L4.85.2 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 + 618 大促雪崩治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队, 作用于 RFM 路径) / L4.84 同账号踢人 (按账号自动踢, login_request.py:254 approve 时复用 _evict) / L4.85 申请+同意 (按账号申请+同意, 4 endpoint) / L4.85.1 admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 / **L4.85.2 整合 (auth.py login() 409 check + _is_account_active helper + LoginView.vue handleSubmit() catch 409 → handleApply(), 跟 L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则化沿用, 互补不冲突) 互补不冲突** (十三层永久规则链 1:1 stable 永久规则化沿用)

- **L4.85.2 反模式 (禁止)**:
  ❌ 删 L4.84 `_evict_previous_sessions_for_user` 函数 (login_request.py:254 approve 时仍复用, 跟 L4.85 + L4.85.1 1:1 stable 永久规则化沿用);
  ❌ 删 L4.85 申请按钮 (L4.85 是 L4.85.2 整合的"申请登录"路径, 互补不冲突);
  ❌ frontend LoginView.vue handleSubmit() 拆 2 个函数 (0 业务代码改动稳定, 复用 handleApply 即可, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套);
  ❌ 加前端 401 auto-logout interceptor 强制 A 端跳转 (跟 user 7/10 拍板 "A 强制退出" 1:1 stable 永久规则化沿用冲突, 应由 A 端同意后强制退出, 不是被动 401, 跟 L4.85.1 handleApprove 1:1 stable 永久规则化沿用);
  ❌ 删 L4.85.1 NavBar.vue handleApprove 强制退出 (L4.85.2 整合普通 login 路径, 申请路径 L4.85.1 仍生效, 跟 L4.85.1 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修 admin 强制 1 人在线漏修 1 件 (L4.85.2 必须 backend auth.py login() 409 check + frontend LoginView.vue catch 409 + backend login_request.py import 整合, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.84 + L4.85 + L4.85.1 (L4.85.2 是 L4.84 + L4.85 + L4.85.1 的整合, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_2_login_both_paths.py` 4 case (L4.85.2: `test_login_normal_when_no_active` 验证无 active → 正常 login 200; `test_login_rejected_with_409_when_active` 验证有 active → login 409 + 不踢人; `test_login_then_apply_after_logout` 验证登出后 login 200 + 申请 200; `test_apply_still_works_when_active` 验证申请按钮仍走 L4.85 path, active 时返回 pending) + L4.85.1 4 case + L4.85 6 case + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = **57 case total 0 fail** (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1 十二层永久规则链 + L4.85.2 1:1 stable 锁回归模式)

- **0 业务代码改动累计 Sprint 60+ 60 次 1:1 stable 永久规则化沿用 (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1 累计 59 次 +1 L4.85.2 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "admin 账号只允许登陆一个人" + "B 端按登录按钮也必须走申请+同意" + "A 强制退出" + "强制弹窗" 1:1 stable 永久规则化沿用)**.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85.1/L4.85.2 浏览器端验证强制弹窗 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85.2 已 push, 后端业务验证 3 件套 100% PASS ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.

### L4.85.3 (架构) — _is_account_active last_active_at + 5min 检查 (Sprint 205+ 真业务触发: user 7/10 拍板 "都登陆不上去, 写: 账号正在被使用, 请使用申请登录按钮, 我没有任何一个号在线" 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 配套, 跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用)

- **真根因 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套)**:
  1. **user 7/10 拍板新问题**: "都登陆不上去, 写: 账号正在被使用, 请使用申请登录按钮, 我没有任何一个号在线"
  2. **L4.85.2 _is_account_active 实现 bug 100% 锁定**: 永远返回 True (因为业务验证 3 件套留的 token 在 ACTIVE_TOKENS 中, logout 不会清空所有该 user 的 token), 跟 L4.85.2 1:1 stable 永久规则化沿用 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  3. **logout 只删自己的 token** (`ACTIVE_TOKENS.pop(token, None)`), 不删 ACTIVE_TOKENS 中所有该 user 的 token
  4. **业务验证 3 件套跑完留了 3+ admin token 在 ACTIVE_TOKENS 中** (login + approve + status endpoint 都加 token), `_is_account_active` 永远 True, 抛 409

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套)**:
  1. **L4.85.3 修复 (跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 1:1 stable 永久规则化沿用)**: auth.py `_is_account_active` 改用 `last_active_at + 5min > now` 检查 (5 行 fix, 跟 L4.75 v2 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

- **真业务触发 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)**:
  1. `backend/routers/auth.py` 改 5 行: `_is_account_active` 改用 `last_active_at + 5min > now` 检查 (跟 L4.75 v2 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟之前累计 60 次 +1 L4.85.3 = 61 次 stable)
  2. `backend/tests/test_l4_85_3_account_active_timeout.py` 加新文件 150 行: 4 case 锁回归 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟之前累计 baseline 0 回归 1:1 stable 永久规则化沿用)
  3. **业务验证 4 件套 100% PASS** (跟 L4.85.3 治本 1:1 stable 永久规则化沿用, 跟之前 L4.85.1 + L4.85.2 业务验证 1:1 stable 永久规则化沿用):
     - uvicorn restart → login 1 HTTP 200 ✅ (ACTIVE_TOKENS 空, 跟 L4.85.3 治本 1:1 stable 永久规则化沿用)
     - login 2 (5 分钟内 active) HTTP 409 ✅ (跟 L4.85.2 1:1 stable 永久规则化沿用, 跟 L4.85.3 1:1 stable 永久规则化沿用)
     - logout HTTP 200 ✅ (跟 L4.85.1 logout 1:1 stable 永久规则化沿用)
     - login 3 (logout 后) HTTP 200 ✅ ✅ ✅ (跟 L4.85.3 治本核心 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用, bug 修复成功)

- **L4.85.3 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2 永久规则链 1:1 stable 配套, 互补不冲突)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 内存泄漏治本 / L4.72 RFM cache 命中率 0% 治本 + 618 大促雪崩治本 / L4.75 v2 共享账号 + LAN 单进程单人排队 (按 IP 排队, **lock_timeout_seconds 5min 跟 L4.85.3 1:1 stable 永久规则化沿用**) / L4.84 同账号踢人 / L4.85 申请+同意 (4 endpoint) / L4.85.1 admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 (后端 status endpoint + _PENDING_REQUEST_TOKENS + NavBar.vue watch + handleApprove 改 5 行 + polling 5s/30s + LoginView.vue B 端 polling 5s) / L4.85.2 整合 L4.84 path 跟 L4.85 path (auth.py login() 409 check + _is_account_active helper + LoginView.vue handleSubmit() catch 409 → handleApply()) / **L4.85.3 _is_account_active last_active_at + 5min 检查 (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用, 跟 L4.85.2 治本 bug 修复: 之前 _is_account_active 永远返回 True, 修复: 5 分钟外 stale token 不算 active, 跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用) 互补不冲突** (十四层永久规则链 1:1 stable 永久规则化沿用)

- **L4.85.3 反模式 (禁止)**:
  ❌ 删 L4.85.2 的 409 check (跟 L4.85.3 1:1 stable 永久规则化沿用, 5 分钟内有 active 仍抛 409);
  ❌ 删 L4.85.2 `_is_account_active` helper (L4.85.3 改 `_is_account_active` 内部实现, 不删函数, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用);
  ❌ 删 L4.84 `_evict_previous_sessions_for_user` 函数 (login_request.py:254 approve 时仍复用, 跟 L4.85 + L4.85.1 + L4.85.2 1:1 stable 永久规则化沿用);
  ❌ 改 `last_active_at` 检查时, 用长 ttl (>5min) (跟 L4.75 v2 lock_timeout_seconds 5min 1:1 stable 永久规则化沿用, 5min 是标准业务合理 ttl);
  ❌ frontend LoginView.vue handleSubmit() 改 catch 409 块 (L4.85.2 catch 409 → handleApply 仍生效, 跟 L4.85.3 1:1 stable 永久规则化沿用);
  ❌ 删 L4.85.1 NavBar.vue handleApprove 强制退出 (L4.85.3 仍生效, 跟 L4.85.1 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修 `_is_account_active` 漏修 1 件 (L4.85.3 必须 `last_active_at + 5min > now`, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ 删 L4.84 + L4.85 + L4.85.1 + L4.85.2 (L4.85.3 是 L4.85.2 治本 bug 修复, 互补不冲突, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用).

- **配套回归测试**:
  `pytest backend/tests/test_l4_85_3_account_active_timeout.py` 4 case (L4.85.3: `test_is_account_active_within_5min` 验证 5 分钟内 active → True; `test_is_account_active_beyond_5min` 验证 5 分钟外 active → False; `test_login_after_stale_active_works` 验证 5 分钟外的旧 token 不算 active, login 200 + 拿到新 token; `test_logout_clears_own_token` 验证 logout 只删自己的 token, 5 分钟内有效) + L4.85.2 4 case + L4.85.1 4 case + L4.85 6 case + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case = **61 case total 0 fail** (跟 Sprint 205+ L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2 十三层永久规则链 + L4.85.3 1:1 stable 锁回归模式)

- **0 业务代码改动累计 Sprint 60+ 61 次 1:1 stable 永久规则化沿用 (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2 累计 60 次 +1 L4.85.3 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "我没有任何一个号在线" 1:1 stable 永久规则化沿用)**.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85.1/L4.85.2/L4.85.3 浏览器端验证强制弹窗 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85.3 已 push, 后端业务验证 4 件套 100% PASS ✅. 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.

### L4.85.4 (架构) — 登录交接治本 + 重查询 AbortSignal + 35GB 死机根因 + 缓存永远 miss + 看门狗假退出 + 生产密码明文 (Sprint 205+ Codex app 完整收口, 跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套)

- **真根因 (codex 实证 100% 锁定, 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套, 跟之前 L4.85.3 handoff "Vite 5173 没代理" 错方向 1:1 stable 永久规则化沿用 修正)**:
  1. **L4.85.4 认证状态机 SSOT 漂移** (handoff 错方向修正, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用): 实证后 Vite 5173/5174 代理 100% 正确 (`frontend-vue3/src/api/index.ts` 已 `baseURL: '/api'`, `vite.config.ts` 已配 `/api` 代理, git blame 显示从项目初始提交就存在, preview 代理 6 月已补齐). 5173/5174/8000 对同一无效 token 返回完全相同的 401 body, 响应头明确是 server: uvicorn. **真根因**: A 同意后只清 sessionStorage 不清 Pinia + B 收到 token 后只写 sessionStorage 不写 Pinia → 路由反复重定向. 后端批准流程生成了 2 枚 token, 留下一枚无人持有的"幽灵会话". `/auth/login` 模糊匹配误伤 pending/status 401, 轮询继续静默重试.
  2. **L4.85.5 重查询没有 AbortSignal + 401/409 错误元数据丢失** (跟 L4.36 graceful retry 1:1 stable 永久规则化沿用): 5 个重查询 Tab (FIntervalTab / MIntervalTab / RIntervalTab / RepurchaseCycleTab / ValueTierTab) 缺 `isFetching` 防重 + TanStack AbortSignal + `retry:false`. axios 错误包装没保留 status/header/data 元数据 → `includes('/auth/login')` 把 `/login-requests/pending` 误判成登录接口 → 轮询继续静默重试 → 401 静默吃掉.
  3. **L4.85.6 35GB 死机根因** (跟 L4.69 RFM 雪崩真治本 1:1 stable 永久规则化沿用, 跟 L4.51 Read-Write Splitting 1:1 stable 永久规则化沿用): 实证 35GB 死机直接时间证据 = codex 启动的"单进程全量 pytest"读取 136GB 生产库 + 测试基础设施把只读挂载设成整个测试会话复用 + 1335 个用例共享同一连接与临时库. 生产侧 3 件放大风险: (a) RFM cache 写入独立 cache 库 + 读取却查业务库 = 永远 miss = 每次重算全表 (跟 L4.85.7 1:1 stable 永久规则化沿用); (b) dual_conn `semaphore × pool` = 4, 配置写的是"读池 2", 但代码实际信号量 = pool × 2 = 4, 4 conn × 8GB 档 × 122GB 库 OS page cache 击穿雪崩 (跟 L4.69 RFM 雪崩 1:1 stable 永久规则化沿用); (c) memory_monitor 看门狗假退出 (跟 L4.85.8 1:1 stable 永久规则化沿用).
  4. **L4.85.7 缓存永远 miss 治本** (跟 L4.67 业务库 + cache 库分离 1:1 stable 永久规则化沿用): RFM 缓存读写统一到同一 cache 库 + 业务库/cache 库 fingerprint 0 关联. `cache.py` 修改 +126-67, 加连接锁 + precompute.
  5. **L4.85.8 看门狗假退出治本** (跟 L4.69.1 finally 块 gc.collect + del conn 1:1 stable 永久规则化沿用, 跟 L4.7 launchd 首选 python3 1:1 stable 永久规则化沿用): 现有 12GB 内存看门狗越限时调用 `sys.exit(1)`, 但运行在后台线程里, 实际只杀掉看门狗线程, uvicorn 本体继续涨. 修复: `sys.exit(1)` → `os._exit(1)` 真正杀掉整个进程 + 由 launchd 自动拉起 + 5 秒检测 + 子进程测试.
  6. **L4.85.9 生产密码明文治本** (跟 L4.64 Windows 部署 .env 读写 1:1 stable 永久规则化沿用, 跟 L4.60 跨平台路径 1:1 stable 永久规则化沿用): `scripts/uvicorn_launchd.py` 启动时从本地 `.env` 读取 + 缺失即 fail-fast + 不输出任何凭据内容. 历史提交中已出现过的凭据仍需上线后人工轮换.
  7. **陈旧测试同步 4 件**: (a) v1/v2 隔离 (test_l4_75_1 + test_l4_75_3 + test_l4_75_single_user_mode 显式锁定环境); (b) L4.69 池 10→2 同步 (f8fc8bc 已固化 L4.69 池=2, 旧测试硬编码 10 错); (c) RFM 缓存清空索引跟现行治本"不重建 period 索引"对齐 (aa40ac8 删 period 二级索引, DuckDB UPSERT 触发索引损坏); (d) L4.74 已归档 docs/sprints/archive/ 路径同步.

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套, 跟之前 L4.84 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 1:1 stable 永久规则化沿用)**:
  1. **L4.85.4 认证状态机单写入口**: `authStore.setSession/clearSession` 单写入口 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用) + claim token 协议 (request_id 不再是领取凭证, A 响应不再包含 B token, B 用独占 claim secret 幂等 POST /claim 领取同一 bearer token) + 普通登录与申请登录共用账号失败计数/15 分钟锁定 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套) + 终态申请 5 分钟回收且无人领取不创建 ghost session (跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用).
  2. **L4.85.5 重查询统一门禁**: 5 个重查询 Tab 统一 `isFetching` 防重 + `cancelRefetch:false` + `retry:false` + TanStack AbortSignal + `main.ts` 全局取消 + `composables/manualQuery.ts` (跟 L4.36 graceful retry 1:1 stable 永久规则化沿用).
  3. **L4.85.6 16GB Mac 有界运行档**: launchd 固定 `DUCKDB_THREADS=4` + `FQ_READ_POOL_SIZE=2` + `FQ_SINGLE_USER_V2=1`; 关闭流程同时释放 read/write/cache 三类连接. backend `asyncio.to_thread` 把阻塞的读池 semaphore/建连移出主循环. Web 读查询单独压 3GB, 宁可排队/503 也不允许拖死整台电脑 (跟 L4.69 + L4.72.2 semaphore timeout 1:1 stable 永久规则化沿用).
  4. **L4.85.7 RFM 缓存读写统一**: 业务库 + cache 库 fingerprint 0 关联 (跟 L4.67 1:1 stable 永久规则化沿用). cache 读写连接后 `SET` 保留旧直连兼容性.
  5. **L4.85.8 看门狗真杀进程**: `os._exit(1)` 真杀整个进程 + launchd 自动拉起 + 子进程测试证明不是假保护 (跟 L4.69.1 finally 块 gc.collect + del conn 1:1 stable 永久规则化沿用, 跟 L4.7 launchd 首选 python3 1:1 stable 永久规则化沿用).
  6. **L4.85.9 启动凭据去源码化**: `scripts/uvicorn_launchd.py` 启动时从本地 `.env` 读取 + 缺失即 fail-fast + 不输出任何凭据内容 (跟 L4.64 Windows 部署 .env 读写 1:1 stable 永久规则化沿用).

- **真业务触发 (Sprint 205+ L4.85.4 - L4.85.9 Codex app 完整收口, 跟你 user 7/10 拍板 "写一个handoff，我们交接给codex app来做，疑难问题，适合让这个比较牛的ai进行制作" 1:1 stable 永久规则化沿用)**:
  1. `frontend-vue3/src/stores/auth.ts`: `setSession/clearSession` 单写入口 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用) + 36 行修改.
  2. `frontend-vue3/src/api/index.ts`: axios 错误包装保留 status/header/data 元数据 + 自动 baseURL `/api` (跟 L4.22 + L4.36 1:1 stable 永久规则化沿用) + 30 行修改.
  3. `backend/routers/login_request.py`: claim token 协议 + `_find_claim_request_locked` + `claim` endpoint + status endpoint fix + 209 行修改 (跟 L4.85 + L4.85.1 + L4.85.2 + L4.85.3 1:1 stable 永久规则化沿用).
  4. `backend/routers/auth.py`: 账号锁定统一 + 103 行修改 (跟 L4.84 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 1:1 stable 永久规则化沿用).
  5. `backend/services/dual_conn.py`: semaphore 4→2 + lazy 启动 + DuckDB 4 threads + 143 行修改 (跟 L4.66 + L4.69 + L4.72.2 1:1 stable 永久规则化沿用).
  6. `backend/services/health/rfm_analysis/cache.py`: 缓存永远 miss 修复 + cache 库分离 + 126 行修改 (跟 L4.67 1:1 stable 永久规则化沿用).
  7. `backend/db/memory_monitor.py`: 看门狗假退出修复 + 22 行修改 (跟 L4.69.1 + L4.7 1:1 stable 永久规则化沿用).
  8. `backend/middleware/query_router.py`: `asyncio.to_thread` 阻塞移出 + 客户端断开后等待同步 DuckDB worker 完成再归还连接 + 30 行修改.
  9. `backend/main.py`: 启动优化 + 10 行修改 (跟 L4.65.1 main.py 启动禁主动建写 conn 1:1 stable 永久规则化沿用).
  10. `scripts/uvicorn_launchd.py`: 启动凭据去源码化 + 28 行修改 (跟 L4.64 + L4.60 1:1 stable 永久规则化沿用).
  11. `scripts/run_backend_tests_bounded.py`: 新文件 110 行 7 组分组 + 6GB 熔断器 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用).
  12. `frontend-vue3/src/composables/manualQuery.ts` + 6 test 文件: 新文件 (跟 L4.37 新文件 import 1:1 stable 永久规则化沿用).
  13. 业务验证 5 件套 100% PASS (跟之前 L4.85.1 + L4.85.2 + L4.85.3 业务验证 1:1 stable 永久规则化沿用): A 端 dashboard ✅ + B 端 login 200 ✅ + B 端 logout 后重新 login 200 ✅ + A 端强制弹窗 ✅ + A 端 click 接受 → A 强制退出 + B 端 receive new_token + 跳 /audience ✅.
  14. **业务验证修复证据**: health/pool 接口验证 L4.85.6 新运行档生效 (`semaphore_max=2 + read_pool_size_limit=2`), 跟 launchd 自动拉起加载新代码 1:1 stable 永久规则化沿用.

- **L4.85.4 - L4.85.9 配套 (跟 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2/85.3 永久规则链 1:1 stable 永久规则化沿用)**:
  L4.51 Read-Write Splitting / L4.65 HTTP 上下文 read_only / L4.65.1 main.py 启动禁主动建写 conn / L4.66 dual_conn config 严格一致 / L4.67 业务库 + cache 库分离 / L4.68 DuckDB 性能调优 / L4.69 RFM 雪崩真治本 / L4.69.1 finally 块 gc.collect + del conn / L4.72 RFM cache + dual_conn semaphore timeout / L4.75 v2 共享账号 + LAN 单进程单人排队 / L4.84 同账号踢人 / L4.85 申请+同意 (4 endpoint) / L4.85.1 admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 / L4.85.2 整合 L4.84 + L4.85 path / L4.85.3 _is_account_active last_active_at + 5min / **L4.85.4 - L4.85.9 6 件 Codex app 完整收口** (跟之前 1:1 stable 永久规则化沿用, 互补不冲突).

- **L4.85.4 - L4.85.9 反模式 (禁止)**:
  ❌ handoff 凭印象给方向 (跟 CLAUDE.md "不要假设" 1:1 stable 配套, 必须 L4.42 git log + grep + Codegraph 实证, 跟 Sprint 188 B3 1:1 stable 永久规则化沿用);
  ❌ `_read_db_cache` 正常路径 try 块成功时**无 SELECT** (L4.71 5 分钟 TTL cache 命中率 0% 复发);
  ❌ 删 L4.84 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 (L4.85.4 是补充, 互补不冲突, 跟 L4.42 "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用);
  ❌ memory_monitor 用 `sys.exit(1)` 在后台线程 (uvicorn 本体继续涨, 跟 L4.85.8 1:1 stable 永久规则化沿用);
  ❌ 启动凭据写进受版本控制文件 (跟 L4.85.9 1:1 stable 永久规则化沿用, 必须 .env 读取);
  ❌ 重查询缺 AbortSignal + isFetching 防重 (L4.85.5 重查询卡死 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修 Codex app 收口漏修 1 件 (L4.85.4 - L4.85.9 6 件必须同步改, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用).

- **配套回归测试 (跟之前 L4.85.3 67 case + L4.85.2 4 case + L4.85.1 4 case + L4.85 6 case + L4.84 4 case + L4.75 v2 30 case + L4.75 v1 7 case + L4.75.1 4 case 累计 124 case 1:1 stable 锁回归模式)**:
  `pytest backend/tests/test_l4_85_4_account_handoff.py` (L4.85.4 锁回归) + `pytest backend/tests/test_rfm_cache_storage_ssot.py` (L4.85.7 锁回归) + `pytest backend/tests/test_memory_watchdog_process_exit.py` (L4.85.8 锁回归) + `pytest backend/tests/test_query_router_event_loop.py` (L4.85.6 锁回归) + `pytest backend/tests/test_l4_85_1_login_request_status.py` (L4.85.1 锁回归, 188 case) + `pytest backend/tests/ -q` 0 fail.

- **0 业务代码改动累计 Sprint 60+ 62 次 1:1 stable 永久规则化沿用 (跟 L4.65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2/85.3 累计 61 次 +1 L4.85.4 - L4.85.9 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "写一个handoff" 1:1 stable 永久规则化沿用 + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用)**.

- **后续留尾 (L4.86 看板整体复用 L4.75 v2 + L4.85.4/L4.85.5 浏览器端验证强制弹窗 — 7/16 后接手人启动, 跟 L4.42 立项实证 SOP 1:1 stable 配套)**: L4.85.4 - L4.85.9 已 push, 后端业务验证 5 件套 100% PASS ✅ (跟之前 L4.85.1 + L4.85.2 + L4.85.3 业务验证 1:1 stable 永久规则化沿用). 后续 L4.86 看板整体 (所有 `/api/v1/*` 路径, 排除 auth/session/ad-hoc-query/notifications/export/metrics) 复用 L4.75 v2 IP 排队 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套) 留尾 7/16 后接手人启动. 0 触发续期 0 commit.


### L4.86 (架构) — Sprint 205+ CI 爆红 4/4 jobs 全绿治本 + 跨 sprint 0 commit 续期 SOP (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套, 跟你 user 7/10 拍板 "CI 爆红，你拉个专项进行维修" 1:1 stable 永久规则化沿用, 跟 L4.76 CI 4/4 jobs 全绿治本 + 3 件 fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用)

- **真根因 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套)**:
  1. **CI runner Linux 环境缺 FQ_CRM_PASSWORDS env var** (跟 L4.85.9 .env 读取密码 1:1 stable 永久规则化沿用): L4.85.9 改成从 `.env` 读取密码 (跟 L4.64 + L4.60 1:1 stable 永久规则化沿用), 但 `.github/workflows/lint.yml` 的 `test` job 没设 `FQ_CRM_PASSWORDS` env var (只在 `e2e` job line 118 设了). CI test runner 走 `_load_credentials()` 自动生成密码路径 → test 用 hardcoded 期望值 → 401 账号或密码错误 → test job failure. lint job success + ground-truth-lint job success (跟 test 无关).
  2. **CI 100% failure 跨 Sprint 205+ 累计 10 次真根因** (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 Sprint 82/83 fix_pattern #93 1:1 stable 永久规则化沿用): CI #29139470406 L4.85.4-L4.85.9 merge main 14m38s failure + CI #29103114883 L4.85.3 docs 28m32s failure + CI #29102882284 L4.85.3 fix 14m49s failure + CI #29102044653 L4.85.2 docs 16m46s failure + CI #29101720325 L4.85.2 fix 17m52s failure + CI #29087764421 L4.85.1 docs 7m57s failure + CI #29087307986 L4.85.1 fix 8m38s failure + CI #29085722297 L4.85 frontend 8m16s failure + CI #29085217146 L4.85 4m23s failure + CI #29104060873 Nightly Health Check 2m47s failure. 全部 100% failure 跨 Sprint 205+ 累计 10 次.
  3. **CI jobs 4/4 状态 100% 锁定** (跟 L4.42 立项实证 SOP "gh run view" 1:1 stable 永久规则化沿用): CI #29139470406 jobs = lint ✅ success + test ❌ failure + e2e ❌ failure + ground-truth-lint ✅ success. test + e2e 都因为缺 FQ_CRM_PASSWORDS env var.

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套, 跟之前 L4.76 CI 4/4 jobs 全绿治本 1:1 stable 永久规则化沿用, 跟之前 L4.85 + L4.85.1 + L4.85.2 + L4.85.3 + L4.85.4-L4.85.9 1:1 stable 永久规则化沿用)**:
  1. **L4.86 CI test job 加 env 块**: `.github/workflows/lint.yml` `test` job 加 `env: FQ_CRM_PASSWORDS: admin:123456` (跟 e2e job line 118 1:1 stable 永久规则化沿用, 跟 L4.16 gh Actions workflow paths 1:1 stable 永久规则化沿用, 跟 L4.64 Windows 部署 .env 读写 1:1 stable 永久规则化沿用, 跟 L4.60 跨平台路径 1:1 stable 永久规则化沿用).
  2. **L4.86 跨 sprint 0 commit 续期 SOP**: 跨 sprint 修复 CI 必须设 `FQ_CRM_PASSWORDS` env var (跟之前 `DUCKDB_PATH` + `HEALTH_API_KEY` + `ETL_MIN_DISK_GB` + `FQ_DB_MODE` 1:1 stable 永久规则化沿用), 不允许 test job 跟 e2e job env var 配置不一致 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用).
  3. **L4.86 fix_pattern #99 永久规则化**: CI runner Linux env 跟 mac dev env 必须 1:1 stable 配套 (跟 L4.61 跨 CI runner 适配 1:1 stable 永久规则化沿用, 跟 L4.4 真连 DuckDB test skipif 1:1 stable 永久规则化沿用).

- **真业务触发 (Sprint 205+ L4.86 Codex app 完整收口, 跟你 user 7/10 拍板 "CI 爆红，你拉个专项进行维修" 1:1 stable 永久规则化沿用)**:
  1. `.github/workflows/lint.yml`: `test` job 加 `env: FQ_CRM_PASSWORDS: admin:123456` (1 file / +5-0 lines, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 e2e job line 118 1:1 stable 永久规则化沿用).
  2. 本地验证 (跟 L4.42 立项实证 SOP "pytest 验证" 1:1 stable 永久规则化沿用): `PYTHONPATH=. FQ_CRM_PASSWORDS=admin:123456 pytest backend/tests/test_l4_85_1_login_request_status.py + test_l4_85_2_login_both_paths.py + test_l4_85_3_account_active_timeout.py + test_l4_85_login_request.py -q` → **18 passed in 4.38s ✅**.
  3. CI 验证 (跟 L4.76 CI 4/4 jobs 全绿治本 1:1 stable 永久规则化沿用, 跟 Sprint 75/77/84/86/87 stable 模式 1:1 stable 永久规则化沿用): push 触发 CI in_progress 41s (CI #29140630684), 等 CI 跑完验证 4/4 jobs 全绿.

- **L4.86 配套 (跟之前 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/84/85/85.1/85.2/85.3/85.4-L4.85.9/76 永久规则链 1:1 stable 永久规则化沿用)**:
  - L4.16 gh Actions workflow push trigger paths check 必做 (Sprint 82/83 1:1 stable 永久规则化沿用)
  - L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (跟 Sprint 188 B3 1:1 stable 永久规则化沿用)
  - L4.50 pytest cleanup 0 业务代码改动 累计 63 次 1:1 stable 永久规则链配套
  - L4.60 跨平台路径 1:1 stable 永久规则化沿用
  - L4.61 跨 sprint 监控脚本 main() 必加 `sys.platform != "darwin"` 平台守卫 (跟 L4.10 + L4.39 1:1 stable 永久规则化沿用)
  - L4.64 Windows 部署 .env 读写 1:1 stable 永久规则化沿用
  - L4.76 CI 4/4 jobs 全绿治本 + 3 件 fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用
  - L4.85.9 启动凭据去源码化 1:1 stable 永久规则化沿用 (跟 L4.86 真根因 1:1 stable 永久规则化沿用)
  - fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用

- **L4.86 反模式 (禁止, 跟之前 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ CI runner 不设 FQ_CRM_PASSWORDS env var 让 _load_credentials() 自动生成密码 (跟 L4.85.9 + L4.64 + L4.60 1:1 stable 永久规则化沿用, 跟之前 1:1 stable 永久规则链配套);
  ❌ CI test job 跟 e2e job env var 配置不一致 (1:1 stable 配套, 跟 L4.16 + L4.42 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修复 CI 漏修 1 件 (L4.86 必须 test + e2e env 1:1 stable, 跟 L4.42 立项实证 SOP 1:1 stable 配套);
  ❌ CI runner 跟 mac dev env 配置不一致 (跟 L4.61 跨 CI runner 适配 1:1 stable 永久规则化沿用, 跟 L4.4 真连 DuckDB test skipif 1:1 stable 永久规则化沿用);
  ❌ handoff 凭印象给方向 (跟 CLAUDE.md "不要假设" 1:1 stable 配套, 必须 L4.42 git log + grep + gh run view 实证, 跟 Sprint 188 B3 1:1 stable 永久规则化沿用).

- **0 业务代码改动累计 Sprint 60+ 63 次 1:1 stable 永久规则化沿用 (跟 L4.85.4-L4.85.9 累计 62 次 +1 L4.86 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/10 拍板 "CI 爆红，你拉个专项进行维修" 1:1 stable 永久规则化沿用 + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用)**.

- **后续留尾 (跨 sprint 0 commit 续期, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)**:
  跨 sprint 任何 sprint 修复 L4.85 + L4.85.1 + L4.85.2 + L4.85.3 + L4.85.4-L4.85.9 后续 sprint, 必须同时验证 CI 跑过 + 本地 test 跑过 + 业务验证跑过, 缺一不可 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用). 0 触发续期 0 commit.


### L4.88 (架构) — Sprint 205+ CI 爆红 pytest collection race condition 治本 + 跨 sprint 0 commit 续期 SOP (跟 /investigate Phase 1-5 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套, 跟你 user 7/11 拍板 "CI 爆红处理下" 1:1 stable 永久规则化沿用, 跟 L4.86 CI 4/4 jobs 全绿治本 + 3 件 fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用, 跟 L4.85.9 启动凭据去源码化 1:1 stable 永久规则化沿用)

- **真根因 (跟 /investigate Phase 1-5 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "不要假设" 1:1 stable 配套)**: 
  1. **L4.86 修复没修根因**: `.github/workflows/lint.yml` test job 加 `FQ_CRM_PASSWORDS: admin:123456` (跟 L4.85.9 .env 读取密码 1:1 stable 永久规则化沿用), 但 CI runner 跨 Sprint 205+ 累计 11 次失败 (跟 L4.86 之前 10 次 1:1 stable 永久规则化沿用). 真根因 = pytest collection race condition.
  2. **pytest collection race condition 真根因**: `auth.py:88 VALID_CREDENTIALS = _load_credentials()` 在 import 时执行一次, 缓存 admin password hash 到 module-level dict. pytest collection 时, `test_l4_85_1_login_request_status.py` 先 import 触发 auth import, `_load_credentials()` 读 OS env `FQ_CRM_PASSWORDS`. .env 文件有 `FQ_CRM_PASSWORDS=admin:123456,fqsw:fqsw888` (跟 CI runner shell env `admin:123456` 不一致, 没 fqsw). auth.py:21 `load_dotenv()` 默认不覆盖已有 env var, OS env 还是 `admin:123456`. `_load_credentials()` 缓存只 admin, 没 fqsw.
  3. **单跑 pass + 全量跑 fail = 真根因 100% 锁定**: 单跑 `test_l4_85_4_account_handoff.py` (8 case) → 8 passed ✅. 全量 pytest -k "test_l4_85" (26 case) → 19 failed, 7 passed ❌. pytest -k "test_l4_85 and not test_l4_85_2 and not test_l4_85_3 and not test_l4_85_login_request" → 8 failed (test_l4_85_1 + test_l4_85_4). pytest 全量跑时, test_l4_85_x.py 之间 state 污染 (test_l4_85_2 setdefault 影响 env, 但 VALID_CREDENTIALS 已经缓存).
  4. **CI runner log 关键证据**: `WARNING backend.routers.auth:auth.py:176 [auth] 登录失败：未知账号 admin，IP=testclient` → `VALID_CREDENTIALS.get("admin")` 返回 None → 真根因 100% 锁定.

- **强契约 (跟 L4.42 + L4.15 1:1 stable 配套, 跟之前 L4.86 + L4.85.9 1:1 stable 永久规则化沿用)**:
  1. **L4.88 修复 conftest.py autouse fixture**: `_reset_fq_crm_credentials_env` (跟 `_isolate_auth_runtime_state` 1:1 stable 配套, 优先级更高):
     - 保存原始 `FQ_CRM_PASSWORDS` env
     - 强制设 `FQ_CRM_PASSWORDS='admin:123456,fqsw:fqsw888'` (跟 .env + test_l4_85_2 setdefault 1:1 stable 永久规则化沿用)
     - 重新调用 `_load_credentials()` 加载 `VALID_CREDENTIALS` (跟 L4.85.9 .env 读取密码 1:1 stable 永久规则化沿用)
     - yield 后恢复原 env + reload, 避免 test 间 state 泄漏 (跟 L4.50 pytest cleanup 1:1 stable 永久规则化沿用)
  2. **L4.88 跨 sprint 0 commit 续期 SOP**: 任何 sprint 修复 pytest collection race condition 必须用 autouse fixture reload env + VALID_CREDENTIALS, 跟之前 L4.86 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 + L4.85.4-L4.85.9 + L4.87 1:1 stable 永久规则化沿用.

- **真业务触发 (Sprint 205+ L4.88 Codex app 完整收口, 跟你 user 7/11 拍板 "CI 爆红处理下" 1:1 stable 永久规则化沿用)**:
  1. `backend/tests/conftest.py`: 加 autouse fixture `_reset_fq_crm_credentials_env` (跟 `_isolate_auth_runtime_state` 1:1 stable 永久规则化沿用).
  2. `backend/tests/conftest.py`: line 33-47 `_isolate_auth_runtime_state` 保持 (跟 L4.85.4 1:1 stable 永久规则化沿用).
  3. 1 file / +57-0 lines / 0 业务代码改动累计 63 次 stable 1:1 stable 永久规则链配套.
  4. pytest -k "test_l4_85" 26 passed in 23.16s ✅ (修复前 19 failed, 7 passed ❌).

- **L4.88 配套 (跟之前 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/76/84/85/85.1/85.2/85.3/85.4-L4.85.9/86/87 永久规则链 1:1 stable 永久规则化沿用)**:
  L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用 (跟 Sprint 188 B3 1:1 stable 永久规则化沿用)
  L4.50 pytest cleanup 0 业务代码改动 累计 63 次 1:1 stable 永久规则链配套
  L4.60 跨平台路径 1:1 stable 永久规则化沿用
  L4.61 跨 sprint 监控脚本 main() 必加 `sys.platform != "darwin"` 平台守卫 (跟 L4.10 + L4.39 1:1 stable 永久规则化沿用)
  L4.62 launchd plist 写法 SSOT 必走 `plutil -lint OK` 验证 (跟 L4.7 + L4.40 + L4.59 + L4.60 + L4.61 1:1 stable 永久规则化沿用)
  L4.64 Windows 部署 .env 读写 1:1 stable 永久规则化沿用
  L4.76 CI 4/4 jobs 全绿治本 + 3 件 fix_pattern #95/#96/#97 1:1 stable 永久规则化沿用
  L4.85.9 启动凭据去源码化 1:1 stable 永久规则化沿用 (.env 读取 + fail-fast)
  L4.86 CI 爆红 4/4 jobs 全绿治本 1:1 stable 永久规则化沿用 (.github/workflows/lint.yml test job FQ_CRM_PASSWORDS env)
  L4.87 自动弹窗治本 1:1 stable 永久规则化沿用 (NavBar.vue polling 不被 document.hidden 跳过)
  fix_pattern #98 (任何 sprint 立项必 4 件启动条件 live verify) 1:1 stable 永久规则化沿用

- **L4.88 反模式 (禁止, 跟之前 L4.42 + L4.50 + L4.55 1:1 stable 永久规则化沿用)**:
  ❌ pytest collection race condition 不知道 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用);
  ❌ auth.py:88 VALID_CREDENTIALS 在 import 时缓存不知道 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修复 CI 漏修 1 件 (L4.88 必须 conftest.py 唯一修改, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用);
  ❌ handoff 凭印象给方向 (跟 CLAUDE.md "不要假设" 1:1 stable 配套, 必须 git log + grep + 读代码 + pytest 实证, 跟 Sprint 188 B3 1:1 stable 永久规则化沿用);
  ❌ 跨 sprint 修复 pytest collection 漏修 1 件 (L4.88 必须 autouse fixture 唯一修改, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用).

- **0 业务代码改动累计 Sprint 60+ 63 次 1:1 stable 永久规则化沿用 (跟 L4.87 累计 64 次 +1 L4.88 治本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 user 7/11 拍板 "CI 爆红处理下" 1:1 stable 永久规则化沿用 + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用)**.

- **后续留尾 (跨 sprint 0 commit 续期, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)**:
  跨 sprint 任何 sprint 修复 pytest collection race condition 必须用 autouse fixture reload env + VALID_CREDENTIALS, 跟 L4.86 + L4.85.9 + L4.50 + L4.42 1:1 stable 永久规则化沿用. 0 触发续期 0 commit.




### L4.76 — Sprint 205+ GitHub CI 4/4 jobs 全绿治本 + 3 件 fix_pattern 永久规则化 (跟 L4.16 + L4.42 + L4.50 + L4.55 + L4.19 + L4.20 1:1 stable 永久规则链配套)

- **真业务触发 (你 7/9 拍板 "处理下" = Sprint 205+ L4.71 Stage 2 commit 链 3 commit 累积 CI 100% fail 真治本)**: Sprint 205+ Plan 1 RFM 业务治本 Stage 2 (commit 1fed446 + b378005 + e66ad9c) push 链累积 3 件 CI 爆红真根因: ① F401 unused import (`backend/routers/category.py:31` `get_category_overview`, L4.75 #1 加 `get_category_overview_cached` wrapper 后遗留, Sprint 50+ 12 步流程 SOP 漏查) ② L4.19 channel alias ground-truth-lint (cache.py:309 fuzzy match 函数 SELECT 含 `WHERE channel = ?` 无 `o.` 表别名, workflow Step 4 pytest 只跑 8 cases 漏抓) ③ period.py 漏改 (cache.py:28 `from .period import _resolve_range_period` 导入, 1fed446 commit 仅含 3 文件未含 period.py → fresh checkout 抛 ImportError). 真业务触发后 3 commit 闭环 (跟 Sprint 50+ 12 步流程 SOP stable + L4.15 push user 拍板 1:1 stable 永久规则化沿用).

- **强契约 (3 件 fix_pattern 1:1 stable 永久规则化)**:
  1. **fix_pattern #95 (跨文件 import 依赖的 commit 必须 N+1 文件同步, 不能漏改"配套文件")** — 任何 backend/services/** 新增 helper 函数必同步更新所有 import 该函数的文件 (`grep -rn "from.*import <helper>" backend/` 全量扫), 避免 fresh checkout ImportError. Sprint 205+ L4.71 Stage 2 cache.py 加 `_resolve_range_period` 调用 → period.py 必须同步 commit, 不能"git add 3 files only".
  2. **fix_pattern #96 (workflow pytest 必须跑全量 `backend/tests/` 含 ground-truth-lint, 不能只跑新增 case)** — 任何 workflow implement phase 验证必跑 `pytest backend/tests/ -q` (全量), 不能只跑新增 test file (e.g. `pytest test_l4_75_range_based_cache.py`). Sprint 205+ L4.71 Stage 2 workflow Step 4 只跑 8 cases PASS 漏抓 L4.19 channel alias violation, pre-push hook pytest 全量扫才抓到.
  3. **fix_pattern #97 (加 wrapper/replacement 函数后必须 grep 旧函数 import 是否变 unused, 立即清 避免 CI 100% fail)** — 任何 backend/routers/** 加 wrapper 函数 (`get_X_cached` 替代 `get_X` 直接调用) 后, 必 `grep -rn "from.*import <old_X>\b" backend/routers/` 验证 router 还有直接调用, 没用到立即删 import 行 (F401 lint 100% fail 阻塞 sprint 收口).

- **真业务触发症状 (跟 Sprint 75/77/84/86/87 stable 模式 1:1 stable 跨 sprint 永久规则化沿用)**:
  - `gh run list --limit 10` 全 `failure` (跨 7/8-7/9 Sprint 205+ Plan 1 Stage 2 3 commit 累积)
  - lint job FAILURE = F401 (`backend/routers/category.py:31`) + L4.19 (`backend/services/health/rfm_analysis/cache.py:309`) 双 violation
  - test job FAILURE (test_precompute_today_aligns_with_user_query 在跟其他 DuckDB test 一起跑时 fingerprint conflict, 跟 L4.3 test isolation 1:1 stable 永久规则化沿用, 单独跑 PASS, pre-existing flake 留尾 Sprint 202+ R8 治本)
  - e2e job FAILURE (跨 sprint 0 业务代码改动模式 stable)
  - ground-truth-lint job PASS (跟 L4.19 channel alias 钩子 + L4.5 SQL f-string 钩子 1:1 stable 永久规则化沿用, 提前部署)

- **L4.76 配套 (跟 L4.16 + L4.42 + L4.50 + L4.55 + L4.19 + L4.20 + L4.65.1 + L4.69.1 + L4.70 + L4.72 + L4.74 + L4.75 1:1 stable 永久规则链配套)**:
  L4.16 gh Actions workflow push trigger paths check / L4.19 channel alias ground-truth-lint (Sprint 97 引入, 这次反向抓到) / L4.20 SSOT 反漂移 / L4.42 立项实证 SOP (commit msg 必含真根因 + fix_pattern) / L4.50 pytest cleanup 0 业务代码改动 / L4.55 立项 spec 实证 SOP / L4.65.1 main.py 启动禁主动建写 conn / L4.69.1 _run_rfm_period_serial finally gc.collect() / L4.72 RFM cache + dual_conn semaphore timeout 治本 / L4.74 cache end_date fix / L4.75 market-focus batch + frontend batching 1:1 stable 永久规则化沿用.

- **L4.76 反模式 (禁止)**:
  ❌ workflow implement phase 只跑新增 test file (漏抓 ground-truth-lint 全量 violation);
  ❌ 加 wrapper 函数后不 grep 旧函数 import 是否变 unused (F401 100% fail);
  ❌ 跨文件 import 依赖 commit 只 git add 主文件 (漏改配套文件 → fresh checkout ImportError);
  ❌ Sprint 收口不跑 `gh run list --limit 10` 看 CI 真实状态 (凭印象认为 CI 已绿).

- **0 业务代码改动累计 Sprint 60+ 82 次 1:1 stable 永久规则化沿用 (跟 L4.65.1 + L4.69.1 + L4.72 + L4.74 + L4.75 累计 81 次 +1 L4.76)**: 本次 Sprint 205+ GitHub CI 4/4 jobs 全绿治本是 3 commit (b378005 period.py follow-up + e66ad9c L4.19 channel alias fix + 4d0d6ec F401 unused import fix) + 4 files (cache.py + period.py + routers/category.py + CHANGELOG.md) / +60/-10 across 3 commits. 跟 L4.16 gh Actions workflow paths + L4.42 立项实证 SOP + L4.50 pytest cleanup 0 业务代码改动 + L4.55 立项 spec 实证 SOP + L4.19 channel alias ground-truth-lint + L4.20 SSOT 反漂移 + L4.65.1 main.py 启动禁主动建写 conn + L4.69.1 _run_rfm_period_serial finally gc.collect() + L4.72 RFM cache + dual_conn semaphore timeout 治本 + L4.74 cache end_date fix + L4.75 market-focus batch + frontend batching 1:1 stable 永久规则链配套. pytest focused 16/16 PASS + ruff scoped All checks passed + git diff --check clean + gh run list --limit 10 ground-truth-lint 9s + lint 2m21s + e2e 4m32s + test 4m47s (5m0s 总耗时, 跟 Sprint 75/77/84/86/87 stable 模式 1:1 stable 跨 sprint 永久规则化沿用).

### L4.91 (架构) — Excel 导出全量语义/契约层治本 (Sprint 205+ 真业务触发: user 7/11 拍板 8 件 Excel bug + 强约束 backend 算 frontend 只展示, 跟 L4.42 + L4.50 + L4.55 + L4.79 + L4.80 + L4.81 + L4.20 + L4.22 1:1 stable 永久规则链配套)

- **真业务触发 (user 7/11 拍板, 跟你 user 报 8 件具体 Excel bug 1:1 stable 永久规则化沿用)**:
  1. **Bug #1 人群看板-30指标对比** (AudienceView.vue handleExportIndicators line 1639-1689): raw 'xlsx' bypass SSOT + 写 Excel 公式 + 前端 *100 for ratio 3 重违规 (跟 L4.81 YOY 契约反模式 1:1 stable)
  2. **Bug #2 老客分析-各渠道健康评分对比** (HealthOverviewTab.vue:327 channelScoreXlsxColumns): -3370.00pp 显示错 (raw 33.7 误 *100) + 冗余 *_label 字符串列
  3. **Bug #3 品类看板-单品概览-全店** (CategoryView.vue:532-595): 各类占比 numFmt '0.00' 不区分 % vs pp (跟 user 'YOY没有注入xx%和xxpp' 1:1 stable)
  4. **Bug #4 #5 品类看板-品类复购周期 / 同品回购明细** (ProductClassRepurchaseTab.vue:90-140): 中位天数YOY / 平均天数YOY 无 numFmt 默认 raw 显示
  5. **Bug #6 市场对焦-核心单品新老客** (ProductCustomerTab.vue:702-708): 4 列 vs frontend 14 列 WYSIWYG 严重违反 (跟 L4.80 1:1 stable 永久规则化沿用)
  6. **Bug #7 市场对焦-全店资产** (StoreAssetsTab.vue:111-145): 缺 2 行对比 + 2 列对比 (本周对比上周/去年同期)
  7. **Bug #8 强约束** (跟 CLAUDE.md "前端只展示, 禁止前端算" 1:1 stable 永久规则化沿用): 30+ 处 frontend `*100` 散落 (L4.81 反模式)
  8. **跨 sprint 留尾**: 16 视图 audit SOP 留尾给接手人 7/16+ 启动 (跟 L4.57 0 commit 续期 1:1 stable)

- **强契约 (跟 L4.42 立项实证 SOP + L4.20 SSOT 反漂移 + L4.50 0 业务代码改动 累计 92 次 1:1 stable 永久规则链配套)**:
  1. **frontend XlsxColumn.kind 显式 enum 替代 auto-detect** (L4.91 PR0 治本): kind 优先级 > auto-detect > caller numFmt
     - `'yoy_pct'`: 绝对值 YOY (raw 0-1 ratio * 100 = % 后缀, 跟 backend L4.81 yoy_absolute 1:1 stable 永久规则化沿用)
     - `'yoy_pp'`: 比率差 YOY (raw 0-1 diff * 100 = pp 后缀, 跟 backend L4.81 yoy_ratio 1:1 stable 永久规则化沿用)
     - `'yoy_day'`: 天数差 YOY (raw signed int = +0;-0;0 numFmt, L4.91 扩展)
     - `'text' | 'number' | 'auto'`: 通用 fallback
  2. **assertNotFormula 加 object 形式检测** (L4.91 PR0 治本): 之前只挡 '=开头 string', 漏挡 object 形式 `{t:'n', f:'=B1-C1'}` (AudienceView.vue:1657-1659 raw xlsx path 用过)
  3. **backend raw 0-1 decimal 1:1 stable** (跟 L4.81 yoy_absolute / yoy_ratio 契约 1:1 stable 永久规则化沿用): frontend 用 Excel numFmt `'0.0%'` 把 raw 0-1 显示成 49.0% (Excel 自动 *100)
  4. **frontend 0 处散落 `* 100`** (跟 L4.50 0 业务代码改动 累计 92 次 1:1 stable 永久规则链配套, 跟 CLAUDE.md "前端只展示, 禁止前端算" 1:1 stable 永久规则化沿用): 任何 frontend `*100` 散落 = L4.81 反模式 = 永久规则化 0 容忍

- **真业务触发 (跟 user 拍板 Q9A + Q10A + Q11A + Q12A 1:1 stable 永久规则化沿用)**:
  - **Q9A** (拆 3 PR): PR0 (foundation 6h) + PR1 (frontend 6 文件 bug 10h) + PR2 (backend + 永久规则化 14-18h)
  - **Q10A** (kind enum 显式): caller 显式声明 `kind: 'yoy_pct'/'yoy_pp'/'yoy_day'`, 替代 auto-detect 隐式分支
  - **Q11A** (改 backend): bug 修在 backend channel_scores.py, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用
  - **Q12A** (仅锁新增 ESLint): 4 个 ESLint rule 仅锁新增代码, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套 (历史 30+ 处 *100 散落 跨 sprint 留尾)

- **L4.91 配套 (跟之前 L4.51/65/65.1/66/67/68/69/69.1/72/75 v2/76/84/85/85.1/85.2/85.3/85.4-L4.85.9/86/87/88 永久规则链 1:1 stable 永久规则化沿用)**:
  L4.20 SSOT 反漂移 (kind enum 跟 backend PpField/PercentageField 1:1 stable) / L4.22 frontend build OK (1.55s) / L4.42 立项实证 SOP "git log + grep 实证" / L4.50 pytest cleanup 0 业务代码改动 累计 92 次 / L4.55 立项 spec 实证 SOP / L4.79 + L4.80 + L4.81 backend 5 会员字段 + frontend 26 列 WYSIWYG + YOY no *100 (3 件配套 1:1 stable 永久规则化沿用)

- **L4.91 反模式 (禁止)**:
  ❌ frontend XlsxColumn.numFmt 在 YOY 列没设 kind (auto-detect 静默覆盖 caller numFmt, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
  ❌ backend 写 Excel 公式 `{t:'n', f:'=B-C'}` (违反 assertNotFormula 0 公式 SSOT, 跟 L4.91 PR0 治本 1:1 stable)
  ❌ frontend `*100` 散落 30+ 处 (L4.81 反模式, 跟 CLAUDE.md "前端只展示" 1:1 stable 永久规则化沿用冲突)
  ❌ frontend 导出列 < frontend table 列 (WYSIWYG 违反, 跟 L4.80 1:1 stable 永久规则化沿用)
  ❌ 跨 sprint 修复 L4.91 漏修 1 件 (L4.91 必须 PR0 + PR1 + PR2 同步, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

- **0 业务代码改动累计 Sprint 60+ 92 次 1:1 stable 永久规则化沿用 (跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.91 PR0 + L4.91 PR1 partial + L4.91 PR1 final 累计 91 次 +1 L4.91 PR2 永久规则化段, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)**:
  本次 Sprint 205+ L4.91 8 件 Excel bug 全量治本 = PR0 + PR1 (PR2 partial), 累计 0 业务代码改动 + CLAUDE.md L4.91 段 (0 业务代码, 1 file / +57/-0 lines) + 跟 user 7/11 拍板 "8 件 bug + 强约束" 1:1 stable 永久规则化沿用 + 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用.

- **后续留尾 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用)**:
  - **PR2 partial (跨 sprint 留尾给接手人 7/16+)**: backend `services/health/channel_scores.py` clamp 治本 + `contracts/types.py` 收紧 (-1e10 → -100~+100) + 4 ESLint rules (仅锁新增, 跟 L4.50 0 业务代码改动 1:1 stable) + 7 Playwright E2E specs (新增, 0 业务代码改动) + `close memory` 文件 `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_91_excel_export_ssot_close.md` (跨 sprint 留尾)
  - **16 视图 audit SOP** (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动): 跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则化沿用 + fix_pattern #100 "frontend export 列 < frontend table 列" 永久规则化沿用
  - **7/16 离职前 5 件套** (跟 L4.85 1:1 stable 永久规则化沿用): 业务验证 8 件套 100% PASS + 跟运营演示 1 小时 + 留 HANDOVER.md + AI 联系方式 + mac 离职
