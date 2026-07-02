from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "user-prompt-template-ad-hoc-query.md"


def test_user_prompt_template_has_daily_gsv_multi_period_strong_prompt() -> None:
    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "必用 daily-gsv-multi-period tool" in content
    assert "不要报\"工具缺位\"" in content


def test_user_prompt_template_has_5_prompt_templates() -> None:
    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert content.count("### 模板 ") >= 5
    for index in range(1, 6):
        assert f"### 模板 {index}:" in content
