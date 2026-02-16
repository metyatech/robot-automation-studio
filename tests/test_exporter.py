from pathlib import Path

import pytest

from robot_automation_studio.exporter import (
    export_all,
    generate_robot_suite,
    validate_step_exportability,
)
from robot_automation_studio.models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
)


def build_scenario() -> Scenario:
    scenario = Scenario(
        name="Unity Editor Basic Flow",
        target_window_hint="Unity",
        metadata={
            UNITY_EXECUTION_MODE_KEY: "attach",
        },
        variables=[
            {"id": "unity_window_hint", "type": "string", "default": "Unity"},
            {"id": "unity_project_path", "type": "path", "default": ""},
        ],
        execution={
            "mode": "attach",
            "attach": {"window_hint_var": "unity_window_hint"},
            "launch": {"unity_project_path_var": "unity_project_path"},
        },
        steps=[
            Step(
                action="click",
                title="Open menu",
                params={
                    "title": "File",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                    "wait_seconds": 0.8,
                },
            ),
            Step(
                action="drag",
                title="Drag item",
                params={
                    "source_title": "TailLength",
                    "source_automation_id": "TailLength",
                    "target_title": "PreviewArea",
                    "target_automation_id": "PreviewArea",
                    "wait_seconds": 0.8,
                },
            ),
            Step(action="shortcut", title="Save", params={"shortcut": "CTRL+S"}),
        ],
    )
    return scenario


def test_generate_robot_suite_contains_expected_keywords() -> None:
    text = generate_robot_suite(build_scenario(), suite_name="unity-editor-basic")

    assert "*** Test Cases ***" in text
    assert "TRY" in text
    assert "FINALLY" in text
    assert "Attach To Running Unity Editor" in text
    assert "Click Unity Element" in text
    assert "Drag Unity Element To Element" in text
    assert "Send Unity Shortcut" in text
    assert "Emit DOCMETA" in text
    assert "Require Unity Project Path" in text


def test_generate_robot_suite_does_not_force_focus_before_steps() -> None:
    text = generate_robot_suite(build_scenario(), suite_name="unity-editor-basic")
    assert "Focus Unity Window" not in text


def test_generate_robot_suite_launch_mode_contains_start_and_stop() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "launch"
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = "D:/projects/avatar-work"
    scenario.execution["mode"] = "launch"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "Start Unity Editor    project_path=${unity_project_path}" in text
    assert "Stop Unity Editor" in text
    assert "Attach To Running Unity Editor" in text
    assert "unity_project_path is required when unity_mode is launch." in text


def test_generate_robot_suite_with_project_path_ensures_unity_bridge_package() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = "D:/projects/avatar-work"
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "launch"
    scenario.execution["mode"] = "launch"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "IF    '${unity_project_path}' != ''" in text
    assert "Ensure Unity Bridge UPM Package    ${unity_project_path}" in text


def test_generate_robot_suite_normalizes_windows_project_path_for_robot() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = r"D:\VRChatProjects\Ryuon"
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "launch"
    scenario.execution["mode"] = "launch"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "${unity_project_path}=    Set Variable    D:/VRChatProjects/Ryuon" in text


def test_generate_robot_suite_handles_hierarchy_path_click() -> None:
    scenario = Scenario(
        name="Hierarchy Select",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Select Tail",
                params={"hierarchy_path": "AvatarRoot/Hair/Tail", "wait_seconds": 0.2},
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="hierarchy-select")

    assert (
        "Wait Until Keyword Succeeds    45 sec    1 sec    Select Unity Hierarchy Object"
        "    hierarchy_path=AvatarRoot/Hair/Tail    timeout_seconds=4.0"
    ) in text
    assert "Click Unity Element" not in text


def test_generate_robot_suite_supports_coordinate_click() -> None:
    scenario = Scenario(
        name="Coordinate Click",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click scene",
                params={
                    "target": {
                        "strategy": "coordinate",
                        "coordinate": {"x_ratio": 0.2, "y_ratio": 0.3},
                    },
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="coordinate-click")
    assert "Click Unity Relative    0.2    0.3" in text


def test_generate_robot_suite_supports_select_hierarchy_action() -> None:
    scenario = Scenario(
        name="Select Hierarchy Action",
        target_window_hint="Unity",
        steps=[
            Step(
                action="select_hierarchy",
                title="Select tail",
                params={
                    "target": {
                        "strategy": "unity_hierarchy",
                        "unity_hierarchy": {"path": "AvatarRoot/Hair/Tail", "match_mode": "exact"},
                    }
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="select-hierarchy")
    assert "Select Unity Hierarchy Object    hierarchy_path=AvatarRoot/Hair/Tail" in text


def test_generate_robot_suite_fails_fast_for_unknown_action() -> None:
    scenario = Scenario(
        name="Unsupported Action",
        target_window_hint="Unity",
        steps=[Step(action="unknown-action", title="Unknown", params={})],
    )

    with pytest.raises(ValueError, match="Unsupported action"):
        generate_robot_suite(scenario, suite_name="unsupported-action")


def test_generate_robot_suite_fails_fast_for_control_step() -> None:
    scenario = Scenario(
        name="Control Scenario",
        target_window_hint="Unity",
        steps=[
            Step(
                kind="control",
                control="parallel",
                title="Parallel",
                params={"steps": []},
            )
        ],
    )

    with pytest.raises(ValueError, match="Unsupported control step"):
        generate_robot_suite(scenario, suite_name="control-scenario")


def test_generate_robot_suite_supports_if_control_step() -> None:
    scenario = Scenario(
        name="If Control",
        target_window_hint="Unity",
        steps=[
            Step(
                kind="control",
                control="if",
                title="Conditional click",
                params={
                    "expression": "True",
                    "steps": [
                        Step(
                            action="click",
                            title="Select tail",
                            params={"hierarchy_path": "AvatarRoot/Hair/Tail"},
                        ).to_dict()
                    ],
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="if-control")
    assert "IF    True" in text
    assert "Select Unity Hierarchy Object    hierarchy_path=AvatarRoot/Hair/Tail" in text
    assert "ELSE IF" not in text


def test_generate_robot_suite_supports_for_each_control_step() -> None:
    scenario = Scenario(
        name="ForEach Control",
        target_window_hint="Unity",
        steps=[
            Step(
                kind="control",
                control="for_each",
                title="Loop items",
                params={
                    "item_variable": "item",
                    "items_expression": "items",
                    "steps": [
                        Step(action="wait_for", title="Wait", params={"seconds": 0.1}).to_dict()
                    ],
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="foreach-control")
    assert "FOR    ${item}    IN    @{items}" in text
    assert "Wait For Seconds    0.1" in text


def test_generate_robot_suite_supports_while_control_step() -> None:
    scenario = Scenario(
        name="While Control",
        target_window_hint="Unity",
        steps=[
            Step(
                kind="control",
                control="while",
                title="While loop",
                params={
                    "expression": "True",
                    "max_iterations": 3,
                    "steps": [
                        Step(action="wait_for", title="Wait", params={"seconds": 0.1}).to_dict()
                    ],
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="while-control")
    assert "WHILE    True    limit=3" in text
    assert "Wait For Seconds    0.1" in text


def test_generate_robot_suite_supports_try_control_step() -> None:
    scenario = Scenario(
        name="Try Control",
        target_window_hint="Unity",
        steps=[
            Step(
                kind="control",
                control="try",
                title="Try catch finally",
                params={
                    "steps": [
                        Step(action="wait_for", title="Try wait", params={"seconds": 0.1}).to_dict()
                    ],
                    "catch_steps": [
                        Step(
                            action="emit_annotation",
                            title="Catch",
                            params={"input": {"annotation": {"type": "note", "label": "catch"}}},
                        ).to_dict()
                    ],
                    "finally_steps": [
                        Step(action="screenshot", title="Finally shot", params={}).to_dict()
                    ],
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="try-control")
    assert "TRY" in text
    assert "EXCEPT" in text
    assert "FINALLY" in text
    assert "Capture Unity Screenshot" in text


def test_generate_robot_suite_supports_double_click_coordinate() -> None:
    scenario = Scenario(
        name="Double Click",
        target_window_hint="Unity",
        steps=[
            Step(
                action="double_click",
                title="Double click scene",
                params={
                    "target": {
                        "strategy": "coordinate",
                        "coordinate": {"x_ratio": 0.4, "y_ratio": 0.7},
                    }
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="double-click")
    assert "Double Click Unity Relative    0.4    0.7" in text


def test_generate_robot_suite_supports_right_click_coordinate() -> None:
    scenario = Scenario(
        name="Right Click",
        target_window_hint="Unity",
        steps=[
            Step(
                action="right_click",
                title="Right click scene",
                params={
                    "target": {
                        "strategy": "coordinate",
                        "coordinate": {"x_ratio": 0.5, "y_ratio": 0.8},
                    }
                },
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="right-click")
    assert "Right Click Unity Relative    0.5    0.8" in text


def test_generate_robot_suite_supports_assert_condition() -> None:
    scenario = Scenario(
        name="Assert Condition",
        target_window_hint="Unity",
        steps=[
            Step(
                action="assert",
                title="Assert true",
                params={"expect": {"condition": "1 == 1", "message": "must be true"}},
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="assert-condition")
    assert "Should Be True    1 == 1    must be true" in text


def test_generate_robot_suite_supports_emit_annotation_action() -> None:
    scenario = Scenario(
        name="Emit Annotation",
        target_window_hint="Unity",
        steps=[
            Step(
                action="emit_annotation",
                title="Emit",
                params={"input": {"annotation": {"type": "click", "label": "Click"}}},
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="emit-annotation")
    assert 'Emit DOCMETA    {"annotation":{"label":"Click","type":"click"}}' in text


def test_validate_step_exportability_fails_for_missing_click_target() -> None:
    step = Step(action="click", title="invalid-click", params={})

    with pytest.raises(ValueError, match="requires target selector"):
        validate_step_exportability(step)


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
    assert "Click Unity Element" in out.robot_path.read_text(encoding="utf-8")


def test_generate_robot_suite_resolves_active_profile_placeholders() -> None:
    scenario = Scenario(
        name="Profile Resolve",
        target_window_hint="${unity_window_hint}",
        metadata={
            UNITY_EXECUTION_MODE_KEY: "launch",
        },
        variables=[
            {"id": "unity_window_hint", "type": "string", "required": True, "default": "Unity"},
            {
                "id": "unity_project_path",
                "type": "path",
                "required": True,
                "default": "",
            },
            {"id": "hierarchy_target", "type": "string", "required": True, "default": "Avatar"},
        ],
        profiles={
            "ryuon": {
                "description": "Ryuon project",
                "variables": {
                    "unity_window_hint": "Unity - Ryuon",
                    "unity_project_path": r"D:\VRChatProjects\Ryuon",
                    "hierarchy_target": "AvatarRoot/Hair/Tail",
                },
            }
        },
        execution={
            "mode": "launch",
            "active_profile": "ryuon",
            "attach": {"window_hint_var": "unity_window_hint"},
            "launch": {"unity_project_path_var": "unity_project_path"},
        },
        steps=[
            Step(
                action="click",
                title="Select hierarchy",
                params={"hierarchy_path": "${hierarchy_target}", "wait_seconds": 0.2},
            )
        ],
    )

    text = generate_robot_suite(scenario, suite_name="profile-resolve")

    assert "${unity_project_path}=    Set Variable    D:/VRChatProjects/Ryuon" in text
    assert "${unity_window_hint}=    Set Variable    Unity - Ryuon" in text
    assert "hierarchy_path=AvatarRoot/Hair/Tail" in text


def test_generate_robot_suite_fails_fast_when_required_variable_missing() -> None:
    scenario = Scenario(
        name="Missing Required",
        target_window_hint="Unity",
        metadata={
            UNITY_EXECUTION_MODE_KEY: "launch",
        },
        variables=[
            {"id": "unity_window_hint", "type": "string", "required": True, "default": "Unity"},
            {
                "id": "unity_project_path",
                "type": "path",
                "required": True,
                "default": "",
            },
        ],
        execution={
            "mode": "launch",
            "attach": {"window_hint_var": "unity_window_hint"},
            "launch": {"unity_project_path_var": "unity_project_path"},
        },
        steps=[
            Step(
                action="click",
                title="Click menu",
                params={
                    "title": "File",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    with pytest.raises(ValueError, match="required variable"):
        generate_robot_suite(scenario, suite_name="missing-required")


def test_generate_robot_suite_fails_fast_for_unresolved_placeholder() -> None:
    scenario = Scenario(
        name="Unresolved Placeholder",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click missing placeholder",
                params={
                    "title": "${missing_title}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    with pytest.raises(ValueError, match="Unresolved placeholder"):
        generate_robot_suite(scenario, suite_name="unresolved-placeholder")
