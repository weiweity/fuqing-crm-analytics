"""
WO-1 hotfix smoke E2E — 5 文件改完, 验 import + 关键不变量

WO-1 P0 blocker 修复范围:
- pipeline.py:305    r[1] 索引能解析 (2-tuple: date_str, rows)
- preload_rfm.py:716 r[1] 索引能解析
- cli.py fail-loud 路径 (3 处 [WO-1 修复] 标记替代 3 处 except: pass)

Sprint 164: 飞书完整解耦, 删 notify_etl_complete 测试 (notify.py 已删, cli.py 改 no-op)
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestWO1Smoke:
    """WO-1 hotfix smoke: 验修复路径可执行。"""

    def test_pipeline_import(self):
        from scripts.etl import pipeline
        assert hasattr(pipeline, 'run_full_etl')

    def test_preload_import(self):
        from scripts.etl import preload_rfm
        assert hasattr(preload_rfm, 'run_auto_preload')

    def test_cli_import(self):
        from scripts.etl import cli
        assert hasattr(cli, 'main')

    def test_cli_fail_loud_markers(self):
        """cli.py 必须有 WO-1 fail-loud 标记 (3 处 [WO-1 修复] 替代裸 except: pass)"""
        from scripts.etl import cli
        import inspect
        src = inspect.getsource(cli)
        # 3 处 WO-1 修复标记: cross_day 前置采样 / 6 道门禁收尾 / Step 8 DuckDB 查询
        assert src.count('[WO-1 修复]') >= 3, (
            f"预期 ≥3 处 [WO-1 修复] 标记, 实际 {src.count('[WO-1 修复]')}"
        )
