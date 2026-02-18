from typing import Any, cast

from robot_automation_studio.params_template import default_params_template_for_action


def test_default_params_template_for_action_click() -> None:
    template = default_params_template_for_action("click")
    assert template is not None
    target = cast(dict[str, Any], template["target"])
    assert target["strategy"] == "uia"


def test_default_params_template_for_action_alias_shortcut() -> None:
    template = default_params_template_for_action("shortcut")
    assert template is not None
    input_payload = cast(dict[str, Any], template["input"])
    assert input_payload["shortcut"] == "CTRL+S"


def test_default_params_template_for_action_double_click_is_coordinate() -> None:
    template = default_params_template_for_action("double_click")
    assert template is not None
    target = cast(dict[str, Any], template["target"])
    assert target["strategy"] == "coordinate"


def test_default_params_template_for_action_run_subflow_points_to_robot_file() -> None:
    template = default_params_template_for_action("run_subflow")
    assert template is not None
    input_payload = cast(dict[str, Any], template["input"])
    path = cast(str, input_payload["path"])
    assert path.endswith(".robot")
