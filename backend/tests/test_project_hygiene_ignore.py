"""Project hygiene: ignore rules for outputs/ and no root SamplingView stub."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_outputs_ignored_by_gitignore():
    gi = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "outputs/" in gi
    assert "HANDOFF-TO-CLAUDE-*.md" in gi
    assert "HANDOFF-FINAL-*.md" in gi
    assert "scripts/_archive/" in gi


def test_no_root_orphan_sampling_view():
    assert not (REPO / "SamplingView.vue").exists()


def test_hygiene_docs_exist():
    assert (REPO / "docs/operating/project-hygiene.md").is_file()
    assert (REPO / "docs/operating/team-workflow-v1.md").is_file()


def test_tech_debt_is_short_ledger_not_chronicle():
    """Open TECH-DEBT.md must stay a short ledger; history is archived."""
    text = (REPO / "docs/TECH-DEBT.md").read_text(encoding="utf-8")
    assert "开放债" in text
    assert "TECH-DEBT-HISTORY.md" in text
    # long chronicle moved out — keep open file small
    assert text.count("最后更新") <= 3
    assert (REPO / "docs/history/TECH-DEBT-HISTORY.md").is_file()
