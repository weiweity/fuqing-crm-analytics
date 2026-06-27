"""Sprint 97 channel alias ground-truth-lint regression tests."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/check_channel_alias.py"


def _run_lint(*paths: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), *(str(path) for path in paths)]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def test_rejects_channel_without_alias(tmp_path: Path) -> None:
    service = tmp_path / "bad_service.py"
    service.write_text(
        'sql = "SELECT * FROM orders o WHERE channel IN (?)"\n',
        encoding="utf-8",
    )

    result = _run_lint(service)

    assert result.returncode == 1
    assert "channel alias violations" in result.stdout


def test_accepts_channel_with_o_alias(tmp_path: Path) -> None:
    service = tmp_path / "good_service.py"
    service.write_text(
        'sql = "SELECT * FROM orders o WHERE o.channel IN (?)"\n',
        encoding="utf-8",
    )

    result = _run_lint(service)

    assert result.returncode == 0, result.stdout + result.stderr


def test_all_backend_services_pass() -> None:
    result = _run_lint()

    assert result.returncode == 0, result.stdout + result.stderr
