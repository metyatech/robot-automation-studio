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
            ),
            Step(
                action="drag",
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
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params["automation_id"] == "MainMenuFile"

    raw = scenario.to_dict()
    assert raw["schema_version"] == SCHEMA_VERSION
    assert raw["target"] == "unity"
    assert raw["metadata"][TARGET_WINDOW_HINT_KEY] == "Unity"


def test_step_has_stable_default_title() -> None:
    step = Step(action="click", params={"title": "Inspector"})
    assert step.title == "click"


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
        "metadata": {},
        "steps": [],
    }

    with pytest.raises(ValueError) as error:
        Scenario.from_dict(payload)
    assert "Unsupported schema_version" in str(error.value)
