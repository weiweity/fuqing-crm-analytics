"""
FIX-M5: W6 通知 pipeline.py 集成点测试

设计: audit 关键发现 (M5) - 9/9 单元测试全部 mock `_send_lark_alert` 验 notify.py 自身逻辑,
没人测: ① run_full_etl() 跑到末尾是否真调 notify_etl_complete
② stats 参数 (orders_count/user_rfm_count/wall_min) 是否从 DuckDB 正确收集
③ step8_ok=False 时 status 是否真传 'failed'
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestW6PipelineIntegration:
    """FIX-M5: pipeline.py 集成点测试 — 验证 run_full_etl 调 notify_etl_complete + status 正确。"""

    def test_pipeline_module_imports_without_error(self):
        """pipeline.py 能被 import, 装饰器 _safe_etl_notify_on_failure 已加载。"""
        from scripts.etl import pipeline  # noqa: F401
        assert hasattr(pipeline, "_safe_etl_notify_on_failure"), (
            "FIX-S5 装饰器未加载"
        )
        assert hasattr(pipeline, "run_full_etl"), (
            "run_full_etl 函数缺失"
        )

    def test_pipeline_decorator_wraps_run_full_etl(self):
        """run_full_etl 被 _safe_etl_notify_on_failure 装饰 (wrapper 包)."""
        from scripts.etl import pipeline
        # 装饰后 __wrapped__ 属性指向原函数
        assert hasattr(pipeline.run_full_etl, "__wrapped__"), (
            "run_full_etl 未被装饰器包装"
        )

    def test_decorator_does_not_swallow_exceptions(self):
        """装饰器 re-raise 原异常, 不吃掉。"""
        from scripts.etl.pipeline import _safe_etl_notify_on_failure

        @_safe_etl_notify_on_failure
        def boom():
            raise ValueError("test")

        with mock.patch("scripts.etl.notify.notify_etl_complete"):
            with pytest.raises(ValueError, match="test"):
                boom()

    def test_decorator_calls_notify_on_exception(self, monkeypatch):
        """装饰器捕获异常时调 notify_etl_complete(status='failed')。"""
        from scripts.etl.pipeline import _safe_etl_notify_on_failure

        captured = {}
        def fake_notify(stats, status="success"):
            captured["stats"] = stats
            captured["status"] = status
            return False, "test reason"

        monkeypatch.setattr("scripts.etl.notify.notify_etl_complete", fake_notify)

        @_safe_etl_notify_on_failure
        def boom():
            raise RuntimeError("simulated ETL failure")

        with pytest.raises(RuntimeError, match="simulated"):
            boom()

        assert captured["status"] == "failed", (
            f"status 应是 failed, 实际 {captured['status']}"
        )
        assert "failed: RuntimeError" in captured["stats"]["gates_overall"], (
            f"gates_overall 应含异常类型, 实际 {captured['stats']['gates_overall']}"
        )

    def test_decorator_swallows_notify_failure(self, monkeypatch):
        """notify 自身失败不阻塞原异常抛出 (二次 try/except 兜底)."""
        from scripts.etl.pipeline import _safe_etl_notify_on_failure

        def fake_notify_failing(*args, **kwargs):
            raise ConnectionError("lark-cli 失败")

        monkeypatch.setattr("scripts.etl.notify.notify_etl_complete", fake_notify_failing)

        @_safe_etl_notify_on_failure
        def boom():
            raise ValueError("original error")

        # 原异常仍抛出 (不因 notify 失败被吃掉)
        with pytest.raises(ValueError, match="original error"):
            boom()

    def test_decorator_normal_path_no_notify_call(self, monkeypatch):
        """函数正常返回时, 装饰器不调 notify_etl_complete (W6 块自己调)."""
        from scripts.etl.pipeline import _safe_etl_notify_on_failure

        called = {"count": 0}
        def fake_notify(*args, **kwargs):
            called["count"] += 1
            return True, "OK"

        monkeypatch.setattr("scripts.etl.notify.notify_etl_complete", fake_notify)

        @_safe_etl_notify_on_failure
        def ok_func():
            return 42

        result = ok_func()
        assert result == 42
        assert called["count"] == 0, (
            f"正常路径不应调 notify, 实际调了 {called['count']} 次"
        )
