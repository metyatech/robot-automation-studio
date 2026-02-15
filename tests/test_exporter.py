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

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "Start Unity Editor    project_path=${unity_project_path}" in text
    assert "Stop Unity Editor" in text
    assert "Attach To Running Unity Editor" in text
    assert "unity_project_path is required when unity_mode is launch." in text


def test_generate_robot_suite_with_project_path_ensures_unity_bridge_package() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = "D:/projects/avatar-work"
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "launch"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "IF    '${unity_project_path}' != ''" in text
    assert "Ensure Unity Bridge UPM Package    ${unity_project_path}" in text


def test_generate_robot_suite_normalizes_windows_project_path_for_robot() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = r"D:\VRChatProjects\Ryuon"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    assert "${unity_project_path}=    Set Variable    D:/VRChatProjects/Ryuon" in text


def test_generate_robot_suite_attach_mode_does_not_ensure_unity_bridge_package() -> None:
    scenario = build_scenario()
    scenario.metadata[UNITY_PROJECT_PATH_KEY] = "D:/projects/avatar-work"
    scenario.metadata[UNITY_EXECUTION_MODE_KEY] = "attach"

    text = generate_robot_suite(scenario, suite_name="unity-editor-basic")

    launch_if_index = text.index("IF    '${unity_mode}' == 'launch'")
    ensure_index = text.index("Ensure Unity Bridge UPM Package    ${unity_project_path}")
    assert ensure_index > launch_if_index


def test_generate_robot_suite_uses_zero_delay_when_not_specified() -> None:
    scenario = Scenario(
        name="No Delay Scenario",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click",
                params={
                    "title": "Inspector",
                    "automation_id": "Inspector",
                },
            ),
            Step(
                action="drag",
                title="Drag",
                params={
                    "source_title": "TailLength",
                    "target_title": "PreviewArea",
                },
            ),
        ],
    )

    text = generate_robot_suite(scenario, suite_name="no-delay")

    assert "Wait For Seconds    0.0" in text


def test_generate_robot_suite_treats_unknown_action_as_unsupported() -> None:
    scenario = Scenario(
        name="Unsupported Action",
        target_window_hint="Unity",
        steps=[Step(action="unknown-action", title="Unknown", params={})],
    )

    text = generate_robot_suite(scenario, suite_name="unsupported-action")

    assert "Unsupported action: unknown-action" in text


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
