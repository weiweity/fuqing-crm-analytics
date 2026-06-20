"""Sprint 54 ground-truth-lint regression test: 验证 check_filter_builder_usage.py 真能抓 f-string 内嵌用户输入.

跟 Sprint 34.1 / Sprint 36-4 实战 "破坏 → 验证 → 恢复" 循环一致:
- 故意制造 f-string 内嵌用户输入 → 验证 rc=1
- 删除违规 → 验证 rc=0
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_lint(tmp_path: Path) -> int:
    """跑 ground-truth-lint, 返回 exit code."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "check_filter_builder_usage.py"
    result = subprocess.run(
        [sys.executable, str(script), "--files", str(tmp_path / "test_service.py")],
        capture_output=True,
        text=True,
    )
    return result.returncode


def test_lint_passes_clean_code(tmp_path: Path) -> None:
    """干净代码 (FilterBuilder + ? 占位) → rc=0."""
    code = '''
from backend.semantic.filters import FilterBuilder, MetricType

def get_data(channel: str):
    fb = FilterBuilder()
    fb.with_metric_type(MetricType.GSV)
    fb.with_channels([channel])
    where_sql, params = fb.build()
    sql = f"SELECT * FROM orders WHERE {where_sql}"
    return sql, params
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 0, f"Expected rc=0 for clean code, got rc={rc}"


def test_lint_catches_fstring_channel_injection(tmp_path: Path) -> None:
    """f-string 内嵌 channel → rc=1 (注入风险)."""
    code = '''
def get_data(channel: str):
    sql = f"SELECT * FROM orders WHERE channel = '{channel}'"
    return sql
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 1, f"Expected rc=1 for f-string channel, got rc={rc}"


def test_lint_catches_fstring_user_id_injection(tmp_path: Path) -> None:
    """f-string 内嵌 user_id → rc=1."""
    code = '''
def get_user_data(user_id: int):
    sql = f"SELECT * FROM orders WHERE user_id = {user_id}"
    return sql
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 1, f"Expected rc=1 for f-string user_id, got rc={rc}"


def test_lint_catches_fstring_level_injection(tmp_path: Path) -> None:
    """f-string 内嵌 level → rc=1."""
    code = '''
def get_category_data(level: str, category_id: str):
    sql = f"SELECT * FROM orders WHERE level = '{level}' AND category_id = '{category_id}'"
    return sql
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 1, f"Expected rc=1 for f-string level/category_id, got rc={rc}"


def test_lint_allows_valid_where_clause_reference(tmp_path: Path) -> None:
    """{valid_where_clause} 是 FilterBuilder 输出, 不是用户输入 → rc=0."""
    code = '''
from backend.semantic.filters import FilterBuilder

def get_data():
    fb = FilterBuilder()
    fb.with_metric_type("GSV")
    valid_where_clause, params = fb.build()
    sql = f"SELECT * FROM orders WHERE {valid_where_clause}"
    return sql
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 0, f"Expected rc=0 for FilterBuilder output reference, got rc={rc}"


def test_lint_allows_time_range_reference(tmp_path: Path) -> None:
    """{start_date}/{end_date} 是函数参数, FilterBuilder 已处理 → rc=0."""
    code = '''
def get_data(start_date: str, end_date: str):
    sql = f"SELECT * FROM orders WHERE pay_time BETWEEN '{start_date}' AND '{end_date}'"
    return sql
'''
    (tmp_path / "test_service.py").write_text(code)
    rc = run_lint(tmp_path)
    assert rc == 0, f"Expected rc=0 for time range (not user input injection), got rc={rc}"
