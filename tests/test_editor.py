from robot_automation_studio.editor import ScenarioEditor
from robot_automation_studio.models import Scenario, Step


def test_editor_add_delete_move_update() -> None:
    scenario = Scenario(name="test", steps=[Step(action="wait", params={"seconds": 1.0})])
    editor = ScenarioEditor(scenario)

    step = editor.add_step(action="click", title="Click", params={"x_ratio": 0.1, "y_ratio": 0.2})
    assert len(editor.scenario.steps) == 2
    assert step.title == "Click"

    editor.move_step_up(1)
    assert editor.scenario.steps[0].action == "click"

    editor.update_step(0, title="Click Updated", params={"x_ratio": 0.2, "y_ratio": 0.3})
    assert editor.scenario.steps[0].title == "Click Updated"
    assert editor.scenario.steps[0].params["x_ratio"] == 0.2

    editor.delete_step(0)
    assert len(editor.scenario.steps) == 1
    assert editor.scenario.steps[0].action == "wait"
