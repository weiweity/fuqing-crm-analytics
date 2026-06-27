"""test_status_update.py — Sprint 59 #6 status_update.py 回归测试

Codex review #13 反馈: marker 缺失 / 重复 / pytest 输出变化必须有回归保护.
3 case: marker 缺失 / marker 重复 / pytest 输出变化不 crash.
"""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "status_update.py"


def _run_in(tmp_path, status_text):
    """Helper: write STATUS.md to tmp_path, run --check with STATUS_MD env override, return CompletedProcess."""
    (tmp_path / "STATUS.md").write_text(status_text, encoding="utf-8")
    return subprocess.run(
        ["python3", str(SCRIPT), "--check"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
        env={"STATUS_MD": str(tmp_path / "STATUS.md"), "PATH": os.environ.get("PATH", "")},
    )


def test_marker_missing_raises(tmp_path):
    """STATUS.md 缺 <!-- STATUS-AUTO-START --> 标记时 returncode != 0."""
    result = _run_in(tmp_path, "# Status\n\nno marker here\n")
    assert result.returncode != 0, f"expected non-zero rc, got {result.returncode}"
    assert "marker" in result.stderr.lower(), f"expected marker error, got: {result.stderr!r}"


def test_marker_duplicate_raises(tmp_path):
    """STATUS.md 有多个 <!-- STATUS-AUTO-START --> 标记时 returncode != 0."""
    status_text = (
        "<!-- STATUS-AUTO-START -->\n| a | 1 | x |\n<!-- STATUS-AUTO-END -->\n"
        "<!-- STATUS-AUTO-START -->\n| b | 2 | y |\n<!-- STATUS-AUTO-END -->\n"
    )
    result = _run_in(tmp_path, status_text)
    assert result.returncode != 0, f"expected non-zero rc, got {result.returncode}"
    assert (
        "duplicate" in result.stderr.lower()
        or "marker" in result.stderr.lower()
    ), f"expected duplicate/marker error, got: {result.stderr!r}"


def test_pytest_output_change_adapts(tmp_path):
    """pytest 输出格式变化 / collection 失败时, status_update.py 不 crash (no traceback)."""
    # 在 tmp_path 跑让脚本读不到 backend/tests/, pytest --co 输出不可预测
    (tmp_path / "conftest.py").write_text("# empty\n", encoding="utf-8")
    (tmp_path / "test_dummy.py").write_text("def test_x(): assert False\n", encoding="utf-8")

    # STATUS.md 加占位符 (跳过 marker 校验失败, 测下游抓取 warning)
    status_text = (
        "<!-- STATUS-AUTO-START -->\n| a | ? | x |\n<!-- STATUS-AUTO-END -->\n"
    )
    result = _run_in(tmp_path, status_text)
    # 不应 crash (rc 可以是 0/1/2, 但 stderr 不应有 Python traceback)
    assert "Traceback" not in result.stderr, (
        f"unexpected traceback in stderr: {result.stderr!r}"
    )
    # 应有 WARNING (pytest collected pattern not matched), 因为 tmp_path 没 backend/tests/
    assert "WARNING" in result.stderr, (
        f"expected WARNING about pytest collection, got: {result.stderr!r}"
    )
