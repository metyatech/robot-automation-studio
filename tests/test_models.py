from pathlib import Path

from robot_automation_studio.models import (
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
                    "x_ratio": 0.07,
                    "y_ratio": 0.05,
                    "box_width": 180,
                    "box_height": 48,
                },
            ),
            Step(
                action="drag",
                title="Drag control",
                params={
                    "from_x_ratio": 0.22,
                    "from_y_ratio": 0.43,
                    "to_x_ratio": 0.68,
                    "to_y_ratio": 0.45,
                },
            ),
        ],
    )

    path = tmp_path / "scenario.json"
    scenario.save_json(path)
    loaded = Scenario.load_json(path)

    assert loaded.name == "Unity Tail Workflow"
    assert loaded.target_window_hint == "Unity"
    assert loaded.metadata[UNITY_EXECUTION_MODE_KEY] == "launch"
    assert loaded.metadata[UNITY_PROJECT_PATH_KEY] == "D:/projects/demo"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params["x_ratio"] == 0.07


def test_step_has_stable_default_title() -> None:
    step = Step(action="wait", params={"seconds": 1.5})
    assert step.title == "wait"


def test_normalize_unity_execution_mode_defaults_to_attach() -> None:
    assert normalize_unity_execution_mode("attach") == "attach"
    assert normalize_unity_execution_mode("launch") == "launch"
    assert normalize_unity_execution_mode("invalid") == "attach"
    assert normalize_unity_execution_mode("") == "attach"
