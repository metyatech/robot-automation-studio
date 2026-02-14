"""Scenario editing service layer."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .models import Scenario, Step


class ScenarioEditor:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario

    def add_step(
        self, action: str, title: str | None = None, params: dict[str, Any] | None = None
    ) -> Step:
        step = Step(action=action, title=title or action, params=dict(params or {}))
        self.scenario.steps.append(step)
        return step

    def delete_step(self, index: int) -> Step:
        return self.scenario.steps.pop(index)

    def move_step_up(self, index: int) -> None:
        if index <= 0:
            return
        self.scenario.steps[index - 1], self.scenario.steps[index] = (
            self.scenario.steps[index],
            self.scenario.steps[index - 1],
        )

    def move_step_down(self, index: int) -> None:
        if index < 0 or index >= len(self.scenario.steps) - 1:
            return
        self.scenario.steps[index + 1], self.scenario.steps[index] = (
            self.scenario.steps[index],
            self.scenario.steps[index + 1],
        )

    def duplicate_step(self, index: int) -> Step:
        original = self.scenario.steps[index]
        copied = replace(original, id=Step(action=original.action).id)
        self.scenario.steps.insert(index + 1, copied)
        return copied

    def update_step(
        self,
        index: int,
        title: str | None = None,
        params: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> Step:
        step = self.scenario.steps[index]
        if title is not None:
            step.title = title
        if params is not None:
            step.params = dict(params)
        if action is not None:
            step.action = action
        return step
