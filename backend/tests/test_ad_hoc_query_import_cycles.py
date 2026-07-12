"""Ad-hoc query modules must import independently in a fresh interpreter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SIBLING_QUERY_MODULES = (
    "scripts.ad_hoc_queries.dq_report",
    "scripts.ad_hoc_queries.rfm_repurchase",
    "scripts.ad_hoc_queries.top_n",
    "scripts.ad_hoc_queries.two_year_overview",
)


@pytest.mark.parametrize("module_name", SIBLING_QUERY_MODULES)
def test_export_excel_sibling_query_imports_are_cycle_free(module_name: str) -> None:
    """避免 pytest 已导入模块掩盖 registry 初始化期的循环导入。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from importlib import import_module; import_module({module_name!r})",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"fresh import failed for {module_name}: stderr={result.stderr!r}"
    )
