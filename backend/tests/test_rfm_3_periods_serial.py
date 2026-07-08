"""
Sprint 205+ (L4.69) RFM 3 周期串行执行 永久规则化 (2026-07-08)

背景:
  Sprint 205+ PC2 RFM 雪崩真根因 = analysis.py ThreadPoolExecutor(max_workers=3)
  3 conn 在 122GB 业务库上并发全表扫 = 磁盘 IO 互相击穿 + OS page cache 击穿.
  4 次 RFM 雪崩曲线 15/34/44/56s 指数雪崩, L4.69 wrapper 修复无效.

治本:
  - analysis.py: ThreadPoolExecutor → 单 conn 顺序跑 3 周期
    (新加 _run_rfm_period_serial helper, 每次新建 conn 跑 1 周期, OS page cache 复用)
  - query_router.py: READ_PREFIXES 加 "/api/v1/customer-health/" (显式 read_only)
  - dual_conn.py: READ_POOL_SIZE 5→2, semaphore 10→4 (大查询池小反快)
  - 配套: L4.65 (HTTP 上下文 read_only) + L4.66 (dual_conn config 严格一致) + L4.67 (cache 库分离)
  - 配套: L4.68 (start_uvicorn.py wrapper 修复, 对雪崩无影响但 0 副作用)

回归 test (本文件):
  锁 L4.69 治本核心 = analysis.py 不能再用 ThreadPoolExecutor, 必须用 _run_rfm_period_serial
  顺序跑 3 周期. 防 Sprint 210+ 误改回 (跟 L4.65/66/67 锁回归模式 1:1 stable).
"""
import inspect

from backend.services.health.rfm_analysis import analysis


class TestRFM3PeriodsSerialLockRegression:
    """L4.69 永久规则化: analysis.py 不能再用 ThreadPoolExecutor (雪崩根因).

    Sprint 205+ 真业务触发: PC2 4 次 RFM 15-56s 雪崩, L4.68 wrapper 修复无效.
    真根因 = analysis.py 用了 ThreadPoolExecutor(max_workers=3) 并发 3 conn 跑 3 周期.
    治本 = 单 conn 顺序跑 3 周期 (新加 _run_rfm_period_serial helper).
    """

    def test_analysis_no_threadpoolexecutor(self):
        """L4.69 治本核心: analysis.py 不能再用 ThreadPoolExecutor (3 conn 并发雪崩根因).

        如果未来 refactor 误改回 ThreadPoolExecutor, 122GB 业务库 IO 击穿 → 雪崩复发.
        检查 2 件: (1) 不能 import concurrent.futures; (2) 不能用 `with concurrent.futures.ThreadPoolExecutor` 调用.
        docstring 提 "ThreadPoolExecutor" 字面量 OK (教学用).
        """
        src = inspect.getsource(analysis)
        # (1) 检查 import 已删
        assert "import concurrent.futures" not in src, (
            "⚠️ L4.69 治本: analysis.py 禁止 `import concurrent.futures` "
            "(3 conn 并发在 122GB 业务库上 = 磁盘 IO 击穿 + OS page cache 击穿, "
            "PC2 实测 4 次 RFM 15-56s 雪崩). 改完 ThreadPoolExecutor 后必须删 import."
        )
        # (2) 检查实际调用已删 (with ThreadPoolExecutor pattern)
        assert "with concurrent.futures.ThreadPoolExecutor" not in src, (
            "⚠️ L4.69 治本: analysis.py 禁止 `with concurrent.futures.ThreadPoolExecutor` 调用 "
            "(3 conn 并发雪崩根因). 必须用 _run_rfm_period_serial 单 conn 顺序跑 3 周期."
        )

    def test_run_rfm_period_serial_exists(self):
        """L4.69 治本: _run_rfm_period_serial helper 函数必须存在 (单 conn 顺序封装).

        验证 helper 函数导入成功 + 有 docstring 提 L4.69 (Sprint 210+ 误删回归 test 失败).
        """
        assert hasattr(analysis, "_run_rfm_period_serial"), (
            "L4.69 治本: _run_rfm_period_serial helper 必须存在 "
            "(analysis.py ThreadPoolExecutor → 串行的核心封装)"
        )
        doc = analysis._run_rfm_period_serial.__doc__ or ""
        assert "L4.69" in doc, (
            "L4.69 治本: _run_rfm_period_serial docstring 必须提 L4.69 锚点 "
            "(Sprint 210+ 误删回归 test 失败)"
        )

    def test_dual_conn_read_pool_size_default_2(self):
        """L4.69 治本: dual_conn.READ_POOL_SIZE 默认 = 2 (5→2, 大查询池小反快).

        PC2 实测: pool=2 时 RFM 4 次 < 5s 稳态, pool=5 时 15-56s 雪崩 (IO 击穿).
        """
        from backend.services.dual_conn import READ_POOL_SIZE
        assert READ_POOL_SIZE == 2, (
            f"L4.69 治本: dual_conn.READ_POOL_SIZE 必须 = 2 (默认), 实际 {READ_POOL_SIZE}. "
            f"5→2 是 L4.69 治本核心 (大查询池小反快, 避免 4 conn × 122GB 库 OS page cache 击穿)."
        )

    def test_query_router_has_customer_health_prefix(self):
        """L4.69 治本: query_router.READ_PREFIXES 必含 /api/v1/customer-health/ (显式 read_only).

        之前 /api/v1/customer-health/rfm-analysis 走 line 73 兜底 read, 语义不显式.
        显式 prefix 后, middleware 强制走 read_only pool (跟 L4.51 Read-Write Splitting 配套).
        """
        from backend.middleware.query_router import QueryRouterMiddleware
        assert "/api/v1/customer-health/" in QueryRouterMiddleware.READ_PREFIXES, (
            "L4.69 治本: query_router.READ_PREFIXES 必含 /api/v1/customer-health/ "
            "(显式 read_only, RFM 走 read_only pool 配套 pool=2)."
        )


class TestL4691RfmMemoryLeakLockRegression:
    """L4.69.1 永久规则化: _run_rfm_period_serial 必须显式 gc.collect() + del conn
    防 uvicorn worker 内存泄漏 (PC2 实测 4 次 RFM 后 PID 2GB 卡死 → 登录 + 全 API 30s+ timeout).

    Sprint 205+ 真业务触发: L4.69 治本后曲线变亚线性, 但每次 RFM 跑完 DuckDB buffer pool
    不归还给 OS, 14 倍内存累积 → worker 卡死. L4.69.1 治本: conn.close() + del conn + gc.collect()
    三件套强制释放, PC2 验证 2GB → 300MB.

    配套 L4.65/66/67/68/69 永久规则链, 跨 sprint 防 Sprint 210+ 误改回 (没 gc.collect → 内存泄漏复发).
    """

    def test_run_rfm_period_serial_uses_gc_collect(self):
        """L4.69.1 治本核心: _run_rfm_period_serial finally 块必须调 gc.collect().

        如果未来 refactor 误删 gc.collect, uvicorn worker 内存泄漏 2GB 卡死复发.
        """
        from backend.services.health.rfm_analysis.analysis import _run_rfm_period_serial
        src = inspect.getsource(_run_rfm_period_serial)
        assert "gc.collect()" in src, (
            "⚠️ L4.69.1 治本: _run_rfm_period_serial finally 块必须调 gc.collect() "
            "(PC2 实测 4 次 RFM 后 PID 2GB 卡死, conn.close() 不够, 必须显式 Python GC)."
        )

    def test_run_rfm_period_serial_deletes_conn_reference(self):
        """L4.69.1 治本: _run_rfm_period_serial finally 块必须显式 `del conn` 删引用.

        conn.close() 不删 Python wrapper 引用, gc.collect() 不会回收.
        """
        from backend.services.health.rfm_analysis.analysis import _run_rfm_period_serial
        src = inspect.getsource(_run_rfm_period_serial)
        assert "del conn" in src, (
            "⚠️ L4.69.1 治本: _run_rfm_period_serial finally 块必须显式 `del conn` "
            "(conn.close() 不释放 Python wrapper, gc.collect() 不会回收 DuckDB 对象)."
        )

    def test_run_rfm_period_serial_imports_gc(self):
        """L4.69.1 治本: analysis.py 顶部必须 import gc.

        如果未来 refactor 误删 `import gc`, NameError 阻断 RFM service.
        """
        from backend.services.health.rfm_analysis import analysis
        src = inspect.getsource(analysis)
        assert "import gc" in src, (
            "⚠️ L4.69.1 治本: analysis.py 顶部必须 `import gc` "
            "(gc.collect() 在 _run_rfm_period_serial finally 块调)."
        )

    def test_run_rfm_period_serial_no_new_connection_in_finally(self):
        """L4.69.1 反模式: finally 块禁止 `duckdb.connect()` 新建连接.

        新建连接会触发 L4.65 (HTTP 上下文 read_only) + L4.66 (config 严格一致) 配套检查,
        跨进程 fingerprint 冲突可能复发. 治本只用 conn.close() + del conn + gc.collect() 三件套.
        """
        from backend.services.health.rfm_analysis.analysis import _run_rfm_period_serial
        src = inspect.getsource(_run_rfm_period_serial)
        # finally 块不能有 duckdb.connect() 调用 (避免 L4.65/66 配套风险)
        # 用 finally 段 (最后 30 行) 范围检查
        finally_section = src.split("finally:")[-1] if "finally:" in src else src
        assert "duckdb.connect" not in finally_section, (
            "⚠️ L4.69.1 反模式: _run_rfm_period_serial finally 块禁止 `duckdb.connect()` "
            "(L4.65 HTTP 上下文 read_only + L4.66 config 严格一致 配套, 新建连接会触发 fingerprint 冲突)."
        )
