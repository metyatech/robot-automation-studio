from pathlib import Path

import pytest

from robot_automation_studio.models import (
    SCHEMA_VERSION,
    TARGET_WINDOW_HINT_KEY,
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
    normalize_unity_execution_mode,
)


def test_scenario_json_round_trip(tmp_path: Path) -> None:
    scenario = Scenario(
        name="Unity Tail Workflow",
        target_window_hint="Unity",
        metadata={
            UNITY_EXECUTION_MODE_KEY: "launch",
            UNITY_PROJECT_PATH_KEY: "D:/projects/demo",
        },
        variables=[
            {"id": "unity_window_hint", "type": "string", "default": "Unity"},
            {"id": "unity_project_path", "type": "path", "default": "D:/projects/demo"},
        ],
        execution={
            "mode": "launch",
            "attach": {"window_hint_var": "unity_window_hint"},
            "launch": {"unity_project_path_var": "unity_project_path"},
        },
        steps=[
            Step(
                kind="action",
                action="click",
                title="Click menu",
                params={
                    "title": "File",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            ),
            Step(
                kind="action",
                action="drag_drop",
                title="Drag control",
                params={
                    "source_title": "TailLength",
                    "source_automation_id": "TailLength",
                    "target_title": "PreviewArea",
                    "target_automation_id": "PreviewArea",
                },
            ),
        ],
    )

    path = tmp_path / "scenario.scenario.json"
    scenario.save_json(path)
    loaded = Scenario.load_json(path)

    assert loaded.scenario_id == scenario.scenario_id
    assert loaded.target == "unity"
    assert loaded.name == "Unity Tail Workflow"
    assert loaded.target_window_hint == "Unity"
    assert loaded.metadata[UNITY_EXECUTION_MODE_KEY] == "launch"
    assert loaded.metadata[UNITY_PROJECT_PATH_KEY] == "D:/projects/demo"
    assert loaded.execution["mode"] == "launch"
    assert loaded.variables[0]["id"] == "unity_window_hint"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params["automation_id"] == "MainMenuFile"
    assert loaded.steps[1].action == "drag_drop"

    raw = scenario.to_dict()
    assert raw["schema_version"] == SCHEMA_VERSION
    assert raw["target"] == "unity"
    assert raw["metadata"][TARGET_WINDOW_HINT_KEY] == "Unity"
    assert raw["steps"][0]["kind"] == "action"
    assert raw["steps"][0]["action"] == "click"
    assert raw["steps"][0]["target"]["strategy"] == "uia"


def test_step_has_stable_default_title() -> None:
    step = Step(action="click", params={"title": "Inspector"})
    assert step.title == "click"
    assert step.to_dict()["action"] == "click"


def test_normalize_unity_execution_mode_defaults_to_attach() -> None:
    assert normalize_unity_execution_mode("attach") == "attach"
    assert normalize_unity_execution_mode("launch") == "launch"
    assert normalize_unity_execution_mode("invalid") == "attach"
    assert normalize_unity_execution_mode("") == "attach"


def test_scenario_from_dict_rejects_unknown_schema_version() -> None:
    payload = {
        "schema_version": "9.9.9",
        "scenario_id": "sample",
        "name": "Sample",
        "target": "unity",
        "variables": [],
        "metadata": {},
        "steps": [],
    }

    with pytest.raises(ValueError) as error:
        Scenario.from_dict(payload)
    assert "Unsupported schema_version" in str(error.value)


def test_step_legacy_aliases_are_converted_to_v2_actions() -> None:
    drag_step = Step(
        action="drag",
        title="Drag",
        params={
            "source_title": "Source",
            "source_automation_id": "Source",
            "target_title": "Target",
            "target_automation_id": "Target",
        },
    )
    shortcut_step = Step(action="shortcut", title="Shortcut", params={"shortcut": "CTRL+S"})
    type_step = Step(action="type", title="Type", params={"text": "abc"})
    wait_step = Step(action="wait", title="Wait", params={"seconds": 1.2})

    drag_payload = drag_step.to_dict()
    shortcut_payload = shortcut_step.to_dict()
    type_payload = type_step.to_dict()
    wait_payload = wait_step.to_dict()

    assert drag_payload["action"] == "drag_drop"
    assert shortcut_payload["action"] == "press_keys"
    assert shortcut_payload["input"]["shortcut"] == "CTRL+S"
    assert type_payload["action"] == "type_text"
    assert wait_payload["action"] == "wait_for"
    assert wait_payload["input"]["seconds"] == 1.2


def test_step_double_click_flat_coordinate_params_are_normalized_to_target() -> None:
    step = Step(
        action="double_click",
        title="Double click",
        params={"x_ratio": 0.25, "y_ratio": 0.75},
    )

    payload = step.to_dict()
    assert payload["action"] == "double_click"
    assert payload["target"]["strategy"] == "coordinate"
    assert payload["target"]["coordinate"]["x_ratio"] == 0.25
    assert payload["target"]["coordinate"]["y_ratio"] == 0.75


def test_step_select_hierarchy_flat_params_are_normalized_to_target() -> None:
    step = Step(
        action="select_hierarchy",
        title="Select hierarchy",
        params={"hierarchy_path": "AvatarRoot/Hair/Tail"},
    )

    payload = step.to_dict()
    assert payload["action"] == "select_hierarchy"
    assert payload["target"]["strategy"] == "unity_hierarchy"
    assert payload["target"]["unity_hierarchy"]["path"] == "AvatarRoot/Hair/Tail"
