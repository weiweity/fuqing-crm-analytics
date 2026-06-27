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
    """W7 DUCKDB_MEMORY_LIMIT_OVERRIDE 端到端验证 (FIX-S2, P1-#8 名实相符).

    P1-#8 治本: 4 个测试**真开 DuckDB** + 验 PRAGMA memory_limit, 不再只 print helper.
    """

    def test_duckdb_actual_memory_limit_default_8gb(self):
        """subprocess 真开 DuckDB, 无 override env, memory_limit 应 ≈ 8GB (DuckDB reserve ~7%).

        通过 duckdb_settings() 查 memory_limit 字段 (DuckDB 1.5.2 有此 catalog function).
        DuckDB 8GB config 实际报告 "7.4 GiB" (reserve 系统开销), 所以用范围断言.

        FIX-S6-subagent-4: 显式置空 DUCKDB_MEMORY_LIMIT_OVERRIDE, 防父进程 env
        (e.g. P0-3 跑批时 export=16GB) 通过 `**os.environ` 漏给 subprocess, 导致断言看
        到 14.9 GiB 而非 7.4/8 GiB. 空串 = `get_duckdb_memory_limit` fallback 到默认 8GB.
        """
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "import duckdb; "
             "from backend.config import get_duckdb_memory_limit; "
             "conn = duckdb.connect(':memory:', config={'memory_limit': get_duckdb_memory_limit()}); "
             "ml = conn.execute(\"SELECT value FROM duckdb_settings() WHERE name='memory_limit'\").fetchone()[0]; "
             "print(f'MEMORY_LIMIT={ml}')"],
            cwd=PROJECT_ROOT,
            env={**os.environ,
                 "DUCKDB_MEMORY_LIMIT_OVERRIDE": "",
                 "DUCKDB_MEMORY_LIMIT": "8GB",
                 "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        # 接受 DuckDB 报告的 "7.4 GiB" 或 "8.0 GiB" (config 解析有 ~7% 系统开销 reserve)
        assert any(v in result.stdout for v in ["MEMORY_LIMIT=7.4 GiB", "MEMORY_LIMIT=8.0 GiB"]), (
            f"DuckDB 实际 memory_limit 不是 ~8GB: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_duckdb_actual_memory_limit_override_16gb(self):
        """subprocess 真开 DuckDB, OVERRIDE=16GB, memory_limit 应 ≈ 16GB.

        治 P1-#8: 端到端真开 DuckDB 验 8GB→16GB override 链路, 不再只 print helper.
        """
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "import duckdb; "
             "from backend.config import get_duckdb_memory_limit; "
             "conn = duckdb.connect(':memory:', config={'memory_limit': get_duckdb_memory_limit()}); "
             "ml = conn.execute(\"SELECT value FROM duckdb_settings() WHERE name='memory_limit'\").fetchone()[0]; "
             "print(f'MEMORY_LIMIT={ml}')"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DUCKDB_MEMORY_LIMIT_OVERRIDE": "16GB",
                 "DUCKDB_MEMORY_LIMIT": "8GB", "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        assert any(v in result.stdout for v in ["MEMORY_LIMIT=14.9 GiB", "MEMORY_LIMIT=16.0 GiB"]), (
            f"DuckDB 实际 memory_limit 不是 ~16GB: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_duckdb_actual_memory_limit_empty_override_falls_back(self):
        """subprocess 真开 DuckDB, OVERRIDE='  ' 空白, memory_limit 应 fallback 8GB."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "import duckdb; "
             "from backend.config import get_duckdb_memory_limit; "
             "conn = duckdb.connect(':memory:', config={'memory_limit': get_duckdb_memory_limit()}); "
             "ml = conn.execute(\"SELECT value FROM duckdb_settings() WHERE name='memory_limit'\").fetchone()[0]; "
             "print(f'MEMORY_LIMIT={ml}')"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DUCKDB_MEMORY_LIMIT_OVERRIDE": "  ",
                 "DUCKDB_MEMORY_LIMIT": "8GB", "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess 失败: {result.stderr}"
        assert any(v in result.stdout for v in ["MEMORY_LIMIT=7.4 GiB", "MEMORY_LIMIT=8.0 GiB"]), (
            f"空白 override 未 fallback 到 8GB: stdout={result.stdout!r}"
        )

    def test_preload_rfm_cli_help_works(self):
        """subprocess 真跑 preload_rfm.py --help, exit 0 + 列出 --lookback (验 12 步 CLI 链路)."""
        result = subprocess.run(
            [sys.executable, "scripts/etl/preload_rfm.py", "--help"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": PROJECT_ROOT},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"preload_rfm.py --help 失败: stderr={result.stderr!r}"
        )
        assert "--lookback" in result.stdout, (
            f"preload_rfm.py 缺 --lookback 参数: stdout={result.stdout!r}"
        )
        # WO-2 加的 _valid_lookback 描述应出现在 --lookback 行
        assert "1-3650" in result.stdout, (
            f"preload_rfm.py --lookback 缺 [1,3650] 边界说明: stdout={result.stdout!r}"
        )
