from __future__ import annotations

import pytest

from robot_automation_studio.models import Scenario, Step
from robot_automation_studio.variable_resolution import resolve_scenario_variables


def test_resolve_scenario_variables_applies_profile_overrides() -> None:
    scenario = Scenario(
        name="Resolve profile",
        target_window_hint="${window_hint}",
        variables=[
            {"id": "window_hint", "type": "string", "required": True, "default": "Unity"},
            {"id": "menu_title", "type": "string", "required": True, "default": "File"},
        ],
        profiles={"jp": {"description": "JP", "variables": {"window_hint": "Unity JP"}}},
        execution={"active_profile": "jp"},
        steps=[
            Step(
                action="click",
                title="Menu click",
                params={
                    "title": "${menu_title}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    resolved = resolve_scenario_variables(scenario)

    assert resolved.target_window_hint == "Unity JP"
    assert resolved.steps[0].params["title"] == "File"
    assert scenario.target_window_hint == "${window_hint}"


def test_resolve_scenario_variables_fails_for_unknown_profile() -> None:
    scenario = Scenario(
        name="Unknown profile",
        target_window_hint="Unity",
        variables=[{"id": "window_hint", "type": "string", "required": True, "default": "Unity"}],
        profiles={"default": {"description": "", "variables": {}}},
        steps=[],
    )

    with pytest.raises(ValueError, match="Unknown profile"):
        resolve_scenario_variables(scenario, active_profile="missing")


def test_resolve_scenario_variables_fails_for_missing_required_variable() -> None:
    scenario = Scenario(
        name="Missing required",
        target_window_hint="Unity",
        variables=[{"id": "required_title", "type": "string", "required": True, "default": ""}],
        steps=[
            Step(
                action="click",
                title="Click required",
                params={
                    "title": "${required_title}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    with pytest.raises(ValueError, match="required variable"):
        resolve_scenario_variables(scenario)


def test_resolve_scenario_variables_fails_for_unresolved_placeholder() -> None:
    scenario = Scenario(
        name="Unresolved",
        target_window_hint="Unity",
        steps=[
            Step(
                action="click",
                title="Click unresolved",
                params={
                    "title": "${undefined_value}",
                    "automation_id": "MainMenuFile",
                    "class_name": "MenuItem",
                    "control_type": "MenuItem",
                },
            )
        ],
    )

    with pytest.raises(ValueError, match="Unresolved placeholder"):
        resolve_scenario_variables(scenario)
