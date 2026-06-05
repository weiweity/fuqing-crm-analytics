"""
FIX-S2: W7 override 机制 E2E 测试

验证: export DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB 后, 跑真 Python 进程 (subprocess)
调 get_duckdb_memory_limit() 看到 16GB (而非默认 8GB)。

设计: audit 关键发现 (S2) — 之前 13 单元测试全用 monkeypatch, 0 端到端验证。
"""
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
PROJECT_ROOT = str(ROOT)


class TestW7E2EOverride:
    """W7 DUCKDB_MEMORY_LIMIT_OVERRIDE 端到端验证 (FIX-S2)。"""

    def test_subprocess_sees_override_16gb(self):
        """subprocess 跑真 Python, 设 DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB,
        get_duckdb_memory_limit() 应返回 16GB (非默认 8GB)。"""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from backend.config import get_duckdb_memory_limit; "
             "print(f'MEMORY={get_duckdb_memory_limit()}')"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DUCKDB_MEMORY_LIMIT_OVERRIDE": "16GB",
                 "DUCKDB_MEMORY_LIMIT": "8GB", "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        assert "MEMORY=16GB" in result.stdout, (
            f"override 未生效: stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_subprocess_no_override_falls_back_to_8gb(self):
        """无 override env, subprocess get_duckdb_memory_limit() 应返回 8GB。"""
        env_no_override = {k: v for k, v in os.environ.items()
                          if k != "DUCKDB_MEMORY_LIMIT_OVERRIDE"}
        env_no_override["DUCKDB_MEMORY_LIMIT"] = "8GB"
        env_no_override["PYTHONPATH"] = PROJECT_ROOT
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from backend.config import get_duckdb_memory_limit; "
             "print(f'MEMORY={get_duckdb_memory_limit()}')"],
            cwd=PROJECT_ROOT,
            env=env_no_override,
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        assert "MEMORY=8GB" in result.stdout, (
            f"默认 8GB 失败: stdout={result.stdout!r}"
        )

    def test_subprocess_empty_override_falls_back(self):
        """override=空字符串 subprocess get_duckdb_memory_limit() 应返回默认 8GB。"""
        env = {**os.environ, "DUCKDB_MEMORY_LIMIT_OVERRIDE": "",
               "DUCKDB_MEMORY_LIMIT": "8GB", "PYTHONPATH": PROJECT_ROOT}
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from backend.config import get_duckdb_memory_limit; "
             "print(f'MEMORY={get_duckdb_memory_limit()}')"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        assert "MEMORY=8GB" in result.stdout

    def test_pipeline_py_imports_with_override_16gb(self):
        """E2E 验证: pipeline.py 能在 OVERRIDE=16GB env 下成功 import (不抛 + 走 helper)。"""
        # 直接跑 import pipeline 模块; 顶部不触发 print (line 48 在 run_full_etl 函数内)
        # 但模块加载本身会跑 line 9-14 import, 包括我们新增的 get_duckdb_memory_limit import
        result = subprocess.run(
            [sys.executable, "-u", "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from scripts.etl.pipeline import get_duckdb_memory_limit; "
             "print(f'PIPELINE_GETTER={get_duckdb_memory_limit()}')"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DUCKDB_MEMORY_LIMIT_OVERRIDE": "16GB",
                 "DUCKDB_MEMORY_LIMIT": "8GB", "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"pipeline import 失败: stderr={result.stderr!r}"
        )
        assert "PIPELINE_GETTER=16GB" in result.stdout, (
            f"pipeline 内部 helper 未生效: stdout={result.stdout!r}"
        )
