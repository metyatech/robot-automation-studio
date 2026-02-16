from robot_automation_studio.app_dialogs import format_validation_issues_for_clipboard
from robot_automation_studio.preflight_validation import ValidationIssue


def test_format_validation_issues_for_clipboard_with_items() -> None:
    text = format_validation_issues_for_clipboard(
        [
            ValidationIssue(
                code="steps.invalid",
                location="steps[0].target",
                message="click requires target selector.",
            ),
            ValidationIssue(
                code="profiles.unknown",
                location="execution.active_profile",
                message="Unknown profile: dev",
            ),
        ]
    )

    assert "1. [steps.invalid] steps[0].target" in text
    assert "click requires target selector." in text
    assert "2. [profiles.unknown] execution.active_profile" in text


def test_format_validation_issues_for_clipboard_without_items() -> None:
    text = format_validation_issues_for_clipboard([])
    assert text == "No validation issues."


def test_format_validation_issues_for_clipboard_without_items_custom_text() -> None:
    text = format_validation_issues_for_clipboard(
        [],
        no_issues_text="検証エラーはありません。",
    )
    assert text == "検証エラーはありません。"
