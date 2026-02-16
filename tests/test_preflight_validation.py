from __future__ import annotations

import shutil

import pytest

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
    assert report.issues[0].location == "steps[0].target.uia.title"


def test_validate_scenario_reports_required_variable_location() -> None:
    scenario = Scenario(
        name="Missing required variable",
        variables=[
            {
                "id": "unity_project_path",
                "type": "path",
                "required": True,
                "default": "",
            }
        ],
        steps=[],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert "required variable" in report.issues[0].message
    assert report.issues[0].location == "variables.unity_project_path.default"


def test_validate_scenario_reports_unknown_profile_location() -> None:
    scenario = Scenario(
        name="Unknown profile",
        execution={"active_profile": "missing-profile"},
        steps=[],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert "Unknown profile" in report.issues[0].message
    assert report.issues[0].location == "execution.active_profile"


def test_validate_scenario_collects_multiple_issues() -> None:
    scenario = Scenario(
        name="Multiple issues",
        execution={"active_profile": "missing-profile"},
        variables=[
            {"id": "unity_project_path", "type": "path", "required": True, "default": ""},
        ],
        steps=[
            Step(action="click", title="invalid-click-a", params={}),
            Step(action="click", title="invalid-click-b", params={}),
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    codes = {issue.code for issue in report.issues}
    locations = {issue.location for issue in report.issues}
    assert "profiles.unknown" in codes
    assert "steps.invalid" in codes
    assert "execution.active_profile" in locations
    assert "steps[0].target" in locations
    assert "steps[1].target" in locations


def test_validate_scenario_reports_nested_control_step_location() -> None:
    scenario = Scenario(
        name="Nested control issue",
        steps=[
            Step(
                kind="control",
                control="for_each",
                title="Loop",
                params={
                    "item_variable": "item",
                    "items_expression": "items",
                    "steps": {"not": "a list"},
                },
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert report.issues[0].location == "steps[0].steps"


@pytest.mark.parametrize("timeout_value", ["abc", True])
def test_validate_scenario_reports_invalid_subflow_timeout_location(
    timeout_value: object,
) -> None:
    scenario = Scenario(
        name="Invalid subflow timeout",
        execution={"subflow_timeout_seconds": timeout_value},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert any(
        issue.code == "execution.subflow_timeout.invalid"
        and issue.location == "execution.subflow_timeout_seconds"
        for issue in report.issues
    )


def test_validate_scenario_reports_missing_ffmpeg_for_start_video(
    monkeypatch,
) -> None:
    scenario = Scenario(
        name="Missing ffmpeg",
        steps=[
            Step(
                action="start_video",
                title="Start capture",
                params={"input": {"path": "videos/run.mp4"}},
            )
        ],
    )
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert report.issues[0].code == "tooling.ffmpeg_missing"
    assert report.issues[0].location == "steps[0].input.path"
    assert "winget install Gyan.FFmpeg" in report.issues[0].message


def test_validate_scenario_allows_start_video_when_ffmpeg_available(
    monkeypatch,
) -> None:
    scenario = Scenario(
        name="ffmpeg available",
        steps=[
            Step(
                action="start_video",
                title="Start capture",
                params={"input": {"path": "videos/run.mp4"}},
            )
        ],
    )
    monkeypatch.setattr(shutil, "which", lambda _name: "C:/ffmpeg/bin/ffmpeg.exe")

    report = validate_scenario(scenario)
    assert report.is_valid is True
    assert report.issues == []


def test_validate_scenario_reports_missing_ffmpeg_for_nested_start_video(
    monkeypatch,
) -> None:
    scenario = Scenario(
        name="Missing ffmpeg nested",
        steps=[
            Step(
                kind="control",
                control="if",
                title="If",
                params={
                    "expression": "True",
                    "steps": [
                        Step(
                            action="start_video",
                            title="Start capture",
                            params={"input": {"path": "videos/run.mp4"}},
                        ).to_dict()
                    ],
                },
            )
        ],
    )
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert report.issues[0].code == "tooling.ffmpeg_missing"
    assert report.issues[0].location == "steps[0].steps[0].input.path"


@pytest.mark.parametrize("timeout_value", [0, 86401])
def test_validate_scenario_reports_out_of_range_subflow_timeout_location(
    timeout_value: int,
) -> None:
    scenario = Scenario(
        name="Subflow timeout out of range",
        execution={"subflow_timeout_seconds": timeout_value},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert report.issues[0].code == "execution.subflow_timeout.invalid"
    assert report.issues[0].location == "execution.subflow_timeout_seconds"


def test_validate_scenario_allows_variable_placeholder_for_subflow_timeout() -> None:
    scenario = Scenario(
        name="Variable subflow timeout",
        variables=[{"id": "subflow_timeout", "type": "number", "required": True, "default": "120"}],
        execution={"subflow_timeout_seconds": "${subflow_timeout}"},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is True
    assert report.issues == []


def test_validate_scenario_allows_spaced_placeholder_for_subflow_timeout() -> None:
    scenario = Scenario(
        name="Variable subflow timeout with spaces",
        variables=[{"id": "subflow_timeout", "type": "number", "required": True, "default": "120"}],
        execution={"subflow_timeout_seconds": " ${subflow_timeout} "},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is True
    assert report.issues == []


def test_validate_scenario_rejects_mixed_placeholder_text_for_subflow_timeout() -> None:
    scenario = Scenario(
        name="Variable subflow timeout invalid mixed",
        variables=[{"id": "subflow_timeout", "type": "number", "required": True, "default": "120"}],
        execution={"subflow_timeout_seconds": "${subflow_timeout}s"},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is False
    assert len(report.issues) >= 1
    assert any(
        issue.code == "execution.subflow_timeout.invalid"
        and issue.location == "execution.subflow_timeout_seconds"
        for issue in report.issues
    )


def test_validate_scenario_allows_whitespace_subflow_timeout() -> None:
    scenario = Scenario(
        name="Whitespace subflow timeout",
        execution={"subflow_timeout_seconds": "   "},
        steps=[
            Step(
                action="run_subflow",
                title="Run child",
                params={"input": {"path": "flows/child.robot"}},
            )
        ],
    )

    report = validate_scenario(scenario)
    assert report.is_valid is True
    assert report.issues == []
