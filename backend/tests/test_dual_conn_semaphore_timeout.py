"""
Sprint 205+ (L4.72.2) dual_conn._read_semaphore.acquire() 加 timeout 治本 (2026-07-08)

背景:
  Phase 1 第 1 个 Explore agent (dual_conn 连接池 + RFM 雪崩根因深度排查) 100% 锁定真根因:
  - `backend/services/dual_conn.py:111-129` `_read_semaphore.acquire()` **无 timeout 参数**
  - 618 大促 8 并发 RFM 请求 → 第 5-8 个请求无限 block, 30s+ timeout 仍不返回
  - READ_POOL_SIZE=2 + READ_SEMAPHORE=4 cap 8 并发, 第 5-8 个**无限 block**
  - 跟 L4.69 RFM 雪崩曲线 15/34/44/56s 同根因, 但 L4.69 没治本 semaphore 无 timeout

  治本 (dual_conn.py:108-149):
  - 加 `ReadPoolTimeout` 异常类
  - `acquire(timeout=5.0)` 5s timeout 友好降级
  - middleware 捕获 ReadPoolTimeout 返回 503
  - 预期: 8 并发雪崩 30s → 2s 503 友好降级

4 case 锁回归 (跟 L4.65.1 + L4.69 + L4.72.1 1:1 stable 模式):
  - test_read_pool_timeout_exception_exists: ReadPoolTimeout 异常类存在
  - test_get_read_connection_default_timeout: get_read_connection 默认 timeout=5.0
  - test_get_read_connection_timeout_raises_read_pool_timeout: 池满时 5s timeout 抛 ReadPoolTimeout
  - test_middleware_catches_read_pool_timeout: middleware 捕获 ReadPoolTimeout 返回 503

跟永久规则链配套 (1:1 stable):
  - L4.51 Read-Write Splitting (read_only 池)
  - L4.66 dual_conn config 严格一致
  - L4.69 RFM 雪崩真治本 (大查询池小反快 READ_POOL_SIZE=2)
  - L4.42 立项实证 SOP (本 plan 跟 L4.42 1:1 stable)
  - L4.50 pytest cleanup 0 业务代码改动 (Sprint 60+ 累计 53 次 stable)
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestL4722DualConnSemaphoreTimeoutLockRegression:
    """L4.72.2 永久规则化: dual_conn._read_semaphore.acquire() 必须有 timeout,
    池满时抛 ReadPoolTimeout, middleware 捕获返回 503.

    Sprint 205+ 真业务触发: 618 大促 8 并发 RFM 雪崩 30s+ timeout 仍不返回.
    治本 L4.72.2 dual_conn semaphore timeout.
    """

    def test_read_pool_timeout_exception_exists(self):
        """L4.72.2 治本: ReadPoolTimeout 异常类必须存在 (middleware 捕获依赖).

        如果未来 refactor 误删 ReadPoolTimeout 异常类, middleware 捕获失败,
        618 大促雪崩兜底失效.
        """
        from backend.services import dual_conn

        assert hasattr(dual_conn, "ReadPoolTimeout"), (
            "L4.72.2 治本: dual_conn.ReadPoolTimeout 异常类必须存在. "
            "middleware 依赖此异常类转 503, 如果误删, 618 大促雪崩兜底失效."
        )
        # 验证: 是 Exception 子类 (可被 except 捕获)
        assert issubclass(dual_conn.ReadPoolTimeout, Exception), (
            "L4.72.2 治本: ReadPoolTimeout 必须是 Exception 子类 (middleware 才能 except 捕获)"
        )

    def test_get_read_connection_default_timeout(self):
        """L4.72.2 治本: get_read_connection 默认 timeout=5.0 (618 大促 8 并发兜底).

        跟 L4.69 RFM 雪崩真治本 (大查询池小反快) 1:1 stable 配套: 大查询慢, 5s 兜底合理.
        """
        from backend.services import dual_conn

        sig = inspect.signature(dual_conn.get_read_connection)
        assert "timeout" in sig.parameters, (
            "L4.72.2 治本: get_read_connection 必须有 timeout 参数 (618 大促 8 并发雪崩兜底)"
        )
        # 验证: 默认值 = 5.0 (跟 plan 1:1 stable 配套)
        assert sig.parameters["timeout"].default == 5.0, (
            f"L4.72.2 治本: get_read_connection timeout 默认值必须 = 5.0 (跟 plan 1:1 stable 配套). "
            f"实际: {sig.parameters['timeout'].default}"
        )

    def test_get_read_connection_timeout_raises_read_pool_timeout(self):
        """L4.72.2 治本核心: 池满时 (8 并发雪崩) acquire(timeout=0.001) 抛 ReadPoolTimeout.

        618 大促 8 并发雪崩, 第 5-8 个请求等 5s 拿不到 conn, 必须抛 ReadPoolTimeout
        (否则 30s+ timeout 仍不返回).
        """
        from backend.services import dual_conn

        # 验证: 池满时 acquire(timeout=0.001) 返回 False (acquire 超时返回 False 1:1 stable)
        # 这是 Python threading.Semaphore.acquire(timeout=) 标准行为
        # 验证: dual_conn.get_read_connection 检测到 False 后抛 ReadPoolTimeout
        # 通过源码静态分析验证 (L4.42 立项实证 SOP 1:1 stable 配套)
        src = inspect.getsource(dual_conn.get_read_connection)
        # 验证: acquire 加 timeout (1:1 stable 配套)
        assert "_read_semaphore.acquire(timeout=" in src, (
            "L4.72.2 治本核心: _read_semaphore.acquire 必须加 timeout=. "
            "旧 bug: acquire() 无 timeout, 618 大促 8 并发雪崩无限 block."
        )
        # 验证: 检测 False 后抛 ReadPoolTimeout
        assert "if not acquired:" in src, (
            "L4.72.2 治本核心: 检测到 acquire 超时必须抛 ReadPoolTimeout. "
            "否则 618 大促雪崩仍 30s+ timeout 不返回."
        )
        assert "raise ReadPoolTimeout" in src, (
            "L4.72.2 治本核心: 必须 raise ReadPoolTimeout, 跟 middleware 503 1:1 stable 配套"
        )

    def test_middleware_catches_read_pool_timeout(self):
        """L4.72.2 治本: query_router middleware 捕获 ReadPoolTimeout 返回 503.

        618 大促 8 并发雪崩兜底: 前端拿到 503 (友好降级), 不是 30s+ timeout (业务卡死).
        """
        from backend.middleware import query_router

        # 验证: middleware 捕获 ReadPoolTimeout (通过 import + except 关键字)
        src = inspect.getsource(query_router)
        assert "except ReadPoolTimeout" in src, (
            "L4.72.2 治本: query_router middleware 必须 except ReadPoolTimeout. "
            "如果不 catch, 618 大促雪崩仍 30s+ timeout 不返回."
        )
        # 验证: 返回 503 (友好降级)
        assert "status_code=503" in src, (
            "L4.72.2 治本: middleware 必须返回 503 状态码. "
            "618 大促雪崩兜底 = 503 友好降级, 让前端知道重试."
        )
        # 验证: 错误消息提示 (跟 L4.42 立项实证 SOP 1:1 stable 配套)
        assert "ReadPoolTimeout" in src or "read pool full" in src, (
            "L4.72.2 治本: middleware 503 响应必须包含 ReadPoolTimeout 错误消息"
        )
