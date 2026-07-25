"""Static contract for Windows Task Scheduler install XML rewrite (PR3 M1).

install_windows.ps1 must:
1. replace REPLACE_WITH_FQ_ETL_SERVICE_USER (not only legacy SYSTEM)
2. rewrite any <Command>...</Command> to absolute venv python
3. assert no placeholder / SYSTEM left before Register-ScheduledTask
"""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import pytest

REPO = Path(__file__).resolve().parents[2]
SCHEDULER = REPO / "scripts" / "etl" / "scheduler"
PS1 = SCHEDULER / "install_windows.ps1"
XML = SCHEDULER / "etl_daily_taskscheduler.xml"
README = SCHEDULER / "README.md"


@pytest.fixture(scope="module")
def ps1_text() -> str:
    assert PS1.is_file(), f"missing {PS1}"
    return PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def xml_text() -> str:
    assert XML.is_file(), f"missing {XML}"
    return XML.read_text(encoding="utf-8")


def test_xml_template_uses_placeholder_not_system(xml_text: str):
    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER" in xml_text
    assert not re.search(r"(?i)<UserId>\s*SYSTEM\s*</UserId>", xml_text)
    assert re.search(r"<Command>[^<]+</Command>", xml_text)
    assert re.search(r"<WorkingDirectory>[^<]+</WorkingDirectory>", xml_text)


def test_ps1_replaces_placeholder_and_legacy_system(ps1_text: str):
    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER" in ps1_text
    # explicit placeholder replace
    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER</UserId>" in ps1_text
    # legacy SYSTEM still handled
    assert "<UserId>SYSTEM</UserId>" in ps1_text
    # must not rely only on literal <Command>python</Command>
    assert "Command>python</Command>" not in ps1_text or re.search(
        r"Command>\[\\^<\]\*</Command>|Command>\[\^<\]\*</Command>",
        ps1_text,
    )
    # regex rewrite of any Command / WorkingDirectory
    assert re.search(r"<Command>\[\^<\]\*</Command>", ps1_text)
    assert re.search(r"<WorkingDirectory>\[\^<\]\*</WorkingDirectory>", ps1_text)


def test_ps1_hard_asserts_no_placeholder_or_system(ps1_text: str):
    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER" in ps1_text
    assert re.search(
        r"(?i)UserId>\\s\*\(SYSTEM\|NT AUTHORITY",
        ps1_text,
    ) or "SYSTEM|NT AUTHORITY\\SYSTEM|S-1-5-18" in ps1_text
    assert "Principal" in ps1_text
    assert "≠ SYSTEM" in ps1_text or "!= SYSTEM" in ps1_text or "notmatch" in ps1_text.lower()


def test_ps1_uses_xml_escape_for_user_and_paths(ps1_text: str):
    assert "SecurityElement]::Escape" in ps1_text
    assert "EscapedUser" in ps1_text
    assert "EscapedPython" in ps1_text
    assert "EscapedRoot" in ps1_text


def test_readme_mentions_principal_check():
    text = README.read_text(encoding="utf-8")
    assert "Principal" in text
    assert "SYSTEM" in text
    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER" in text


def _rewrite_xml_like_ps1(
    xml: str,
    *,
    service_user: str,
    venv_python: str,
    project_root: str,
) -> str:
    """Mirror install_windows.ps1 rewrite rules in pure Python for contract tests."""
    esc_user = xml_escape(service_user)
    esc_py = xml_escape(venv_python)
    esc_root = xml_escape(project_root)

    out = xml.replace(
        "<UserId>REPLACE_WITH_FQ_ETL_SERVICE_USER</UserId>",
        f"<UserId>{esc_user}</UserId>",
    )
    out = out.replace("<UserId>SYSTEM</UserId>", f"<UserId>{esc_user}</UserId>")
    # lambda repl: Windows 路径反斜杠不得进 re 模板
    out = re.sub(r"<UserId>[^<]*</UserId>", lambda _m: f"<UserId>{esc_user}</UserId>", out, count=1)
    out = re.sub(r"<Command>[^<]*</Command>", lambda _m: f"<Command>{esc_py}</Command>", out)
    out = re.sub(
        r"<WorkingDirectory>[^<]*</WorkingDirectory>",
        lambda _m: f"<WorkingDirectory>{esc_root}</WorkingDirectory>",
        out,
    )
    out = out.replace(
        "<RunLevel>HighestAvailable</RunLevel>",
        "<RunLevel>LeastPrivilege</RunLevel>",
    )
    return out


@pytest.mark.parametrize(
    "service_user,xml_seed",
    [
        (r".\fuqing-etl", "placeholder"),
        (r"DOMAIN\svc-etl", "system"),
        (r"svc&etl", "placeholder"),  # XML special char
    ],
)
def test_xml_rewrite_contract(xml_text: str, service_user: str, xml_seed: str):
    venv = r"D:\fuqin-date\fuqing-crm-analytics\.venv\Scripts\python.exe"
    root = r"D:\fuqin-date\fuqing-crm-analytics"

    seed = xml_text
    if xml_seed == "system":
        seed = seed.replace(
            "<UserId>REPLACE_WITH_FQ_ETL_SERVICE_USER</UserId>",
            "<UserId>SYSTEM</UserId>",
        )

    out = _rewrite_xml_like_ps1(
        seed,
        service_user=service_user,
        venv_python=venv,
        project_root=root,
    )

    assert "REPLACE_WITH_FQ_ETL_SERVICE_USER" not in out
    assert not re.search(r"(?i)<UserId>\s*SYSTEM\s*</UserId>", out)
    assert f"<UserId>{xml_escape(service_user)}</UserId>" in out
    assert f"<Command>{xml_escape(venv)}</Command>" in out
    assert f"<WorkingDirectory>{xml_escape(root)}</WorkingDirectory>" in out
    assert "<RunLevel>LeastPrivilege</RunLevel>" in out
    assert not re.search(r"(?i)<Command>\s*python(\.exe)?\s*</Command>", out)
