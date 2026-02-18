from robot_automation_studio.server import build_help_tooltip_text


def test_build_help_tooltip_text_uses_stripped_summary() -> None:
    assert build_help_tooltip_text("  Run the selected scenario  ") == "Run the selected scenario"


def test_build_help_tooltip_text_uses_fallback_for_blank_summary() -> None:
    assert build_help_tooltip_text("   ") == "No help available for this component."
