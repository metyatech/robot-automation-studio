import pytest

from robot_automation_studio.editor import ScenarioEditor
from robot_automation_studio.models import Scenario, Step


def test_editor_add_delete_move_update() -> None:
    scenario = Scenario(name="test", steps=[Step(action="click", params={"title": "Inspector"})])
    editor = ScenarioEditor(scenario)

    step = editor.add_step(
        action="click",
        title="Click",
        params={"title": "Hierarchy", "automation_id": "Hierarchy"},
    )
    assert len(editor.scenario.steps) == 2
    assert step.title == "Click"
    assert step.kind == "action"

    editor.move_step_up(1)
    assert editor.scenario.steps[0].action == "click"

    editor.update_step(
        0,
        title="Click Updated",
        params={"title": "Inspector", "automation_id": "Inspector"},
    )
    assert editor.scenario.steps[0].title == "Click Updated"
    assert editor.scenario.steps[0].params["automation_id"] == "Inspector"

    editor.delete_step(0)
    assert len(editor.scenario.steps) == 1
    assert editor.scenario.steps[0].action == "click"


def test_editor_rejects_unsupported_action_on_add() -> None:
    editor = ScenarioEditor(Scenario(name="test"))

    with pytest.raises(ValueError, match="Unsupported step action"):
        editor.add_step(action="invalid-action", title="Invalid", params={})


def test_editor_rejects_unsupported_action_on_update() -> None:
    editor = ScenarioEditor(
        Scenario(name="test", steps=[Step(action="click", params={"title": "Inspector"})])
    )

    with pytest.raises(ValueError, match="Unsupported step action"):
        editor.update_step(0, action="invalid-action")

    step = editor.scenario.steps[0]
    assert step.action == "click"
    assert step.params == {"title": "Inspector"}


def test_editor_can_add_and_update_control_and_group_steps() -> None:
    editor = ScenarioEditor(Scenario(name="test"))

    control = editor.add_control_step(
        "for_each",
        title="Loop",
        params={"items_expression": "${items}", "item_variable": "item", "steps": []},
    )
    group = editor.add_group_step(title="Group", params={"steps": []})

    assert control.kind == "control"
    assert control.control == "for_each"
    assert group.kind == "group"

    editor.update_step(
        0,
        kind="control",
        control="if",
        description="control desc",
        condition="x > 0",
        continue_on_error=True,
        annotations=[{"type": "label", "text": "demo"}],
    )
    updated = editor.scenario.steps[0]
    assert updated.control == "if"
    assert updated.description == "control desc"
    assert updated.condition == "x > 0"
    assert updated.continue_on_error is True
    assert updated.annotations[0]["type"] == "label"
