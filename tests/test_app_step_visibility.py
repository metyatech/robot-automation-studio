from robot_automation_studio.server import step_editor_visibility_for_kind


def test_step_editor_visibility_for_action() -> None:
    assert step_editor_visibility_for_kind("action") == {
        "show_action": True,
        "show_control": False,
        "show_condition": False,
    }


def test_step_editor_visibility_for_control() -> None:
    assert step_editor_visibility_for_kind("control") == {
        "show_action": False,
        "show_control": True,
        "show_condition": True,
    }


def test_step_editor_visibility_for_group_and_unknown() -> None:
    assert step_editor_visibility_for_kind("group") == {
        "show_action": False,
        "show_control": False,
        "show_condition": False,
    }
    assert step_editor_visibility_for_kind("unknown") == {
        "show_action": True,
        "show_control": False,
        "show_condition": False,
    }
