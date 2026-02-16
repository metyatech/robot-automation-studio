from __future__ import annotations

from robot_automation_studio.models import Scenario, Step
from robot_automation_studio.profile_diff import build_profile_diff


def test_build_profile_diff_returns_changed_paths() -> None:
    scenario = Scenario(
        name="Profile diff",
        target_window_hint="${unity_window_hint}",
        variables=[
            {"id": "unity_window_hint", "type": "string", "required": True, "default": "Unity"},
            {"id": "menu_title", "type": "string", "required": True, "default": "File"},
        ],
        profiles={
            "a": {"description": "A", "variables": {"unity_window_hint": "Unity A"}},
            "b": {"description": "B", "variables": {"unity_window_hint": "Unity B"}},
        },
        steps=[
            Step(
                action="click",
                title="Click menu",
                params={
                    "title": "${menu_title}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    diff = build_profile_diff(scenario, base_profile="a", compare_profile="b")

    assert diff
    changed_paths = {item.path for item in diff}
    assert "metadata.target_window_hint" in changed_paths


def test_build_profile_diff_returns_empty_for_same_profile() -> None:
    scenario = Scenario(name="No diff", target_window_hint="Unity", steps=[])
    diff = build_profile_diff(scenario, base_profile="", compare_profile="")
    assert diff == []
