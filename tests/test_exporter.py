from pathlib import Path

from robot_automation_studio.exporter import export_all, generate_robot_suite
from robot_automation_studio.models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
)


def build_scenario() -> Scenario:
    return Scenario(
        name="Unity Editor Basic Flow",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Open menu",
                params={
                    "x_ratio": 0.07,
                    "y_ratio": 0.05,
                    "box_width": 180,
                    "box_height": 48,
                    "wait_seconds": 0.8,
                },
            ),
            Step(
                action="drag",
                title="Drag item",
                params={
                    "from_x_ratio": 0.22,
                    "from_y_ratio": 0.43,
                    "to_x_ratio": 0.68,
                    "to_y_ratio": 0.45,
                    "wait_seconds": 0.8,
                },
            ),
            Step(action="wait", title="Wait", params={"seconds": 1.25}),
            Step(action="shortcut", title="Save", params={"shortcut": "CTRL+S"}),
        ],
    )


def test_generate_robot_suite_contains_expected_keywords() -> None:
    text = generate_robot_suite(build_scenario(), suite_name="unity-editor-basic")

    assert "*** Test Cases ***" in text
    assert "TRY" in text
    assert "FINALLY" in text
    assert "Attach To Running Unity Editor" in text
    assert "Click Unity Relative" in text
    assert "Drag Unity Relative" in text
    assert "Send Unity Shortcut" in text
    assert "Emit DOCMETA" in text
    assert "Require Unity Project Path" in text


def test_generate_robot_suite_launch_mode_contains_start_and_stop() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "launch"
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = "D:/projects/avatar-work"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "Start Unity Editor    project_path=${unity_project_path}" in text
    assert "Stop Unity Editor" in text
    assert "Attach To Running Unity Editor" in text
    assert "unity_project_path is required when unity_mode is launch." in text


def test_export_all_writes_robot_and_json(tmp_path: Path) -> None:
    scenario = build_scenario()
    out = export_all(
        scenario=scenario,
        output_dir=tmp_path,
        suite_name="unity-editor-basic",
    )

    assert out.robot_path.exists()
    assert out.json_path.exists()
    assert out.json_path.name.endswith(".scenario.json")
    assert "Click Unity Relative" in out.robot_path.read_text(encoding="utf-8")
