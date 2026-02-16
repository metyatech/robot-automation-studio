from __future__ import annotations

from robot_automation_studio.models import Scenario, Step
from robot_automation_studio.preflight_validation import validate_scenario


def test_validate_scenario_returns_no_issue_for_valid_scenario() -> None:
    scenario = Scenario(
        name="Valid scenario",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click file menu",
                params={
                    "title": "File",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is True
    assert report.issues == []


def test_validate_scenario_reports_unresolved_placeholder() -> None:
    scenario = Scenario(
        name="Invalid scenario",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click unresolved",
                params={
                    "title": "${missing_value}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert "Unresolved placeholder" in report.issues[0].message
