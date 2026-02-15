"""Scenario editing service layer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import Scenario, Step

SUPPORTED_STEP_ACTIONS = {
    "open_url",
    "click",
    "double_click",
    "right_click",
    "drag_drop",
    "shortcut",
    "keys",
    "menu",
    "type",
    "type_text",
    "press_keys",
    "open_menu",
    "select_hierarchy",
    "wait_for",
    "assert",
    "screenshot",
    "start_video",
    "stop_video",
    "emit_annotation",
    "run_subflow",
    # legacy aliases
    "drag",
    "wait",
}

SUPPORTED_STEP_CONTROLS = {
    "if",
    "for_each",
    "while",
    "try",
    "parallel",
    "break",
    "continue",
    "return",
}


def _validate_action(action: str) -> str:
    normalized = str(action).strip().lower()
    if normalized not in SUPPORTED_STEP_ACTIONS:
        raise ValueError(f"Unsupported step action: {action}")
    return normalized


def _validate_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized in {"action", "control", "group"}:
        return normalized
    raise ValueError(f"Unsupported step kind: {kind}")


def _validate_control(control: str) -> str:
    normalized = str(control).strip().lower()
    if normalized not in SUPPORTED_STEP_CONTROLS:
        raise ValueError(f"Unsupported step control: {control}")
    return normalized


class ScenarioEditor:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario

    def add_step(
        self,
        action: str,
        title: str | None = None,
        params: dict[str, Any] | None = None,
        *,
        kind: str = "action",
        control: str | None = None,
    ) -> Step:
        validated_kind = _validate_kind(kind)
        validated_action = _validate_action(action) if validated_kind == "action" else ""
        validated_control = (
            _validate_control(control or "if") if validated_kind == "control" else ""
        )
        step = Step(
            kind=validated_kind,
            action=validated_action,
            control=validated_control,
            title=title or validated_action,
            params=deepcopy(dict(params or {})),
        )
        self.scenario.steps.append(step)
        return step

    def add_control_step(
        self,
        control: str,
        title: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Step:
        return self.add_step(
            action="",
            title=title or control,
            params=params,
            kind="control",
            control=control,
        )

    def add_group_step(
        self, title: str | None = None, params: dict[str, Any] | None = None
    ) -> Step:
        group_params = dict(params or {})
        group_params.setdefault("steps", [])
        return self.add_step(
            action="",
            title=title or "group",
            params=group_params,
            kind="group",
        )

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
        copied = Step(
            id=Step(kind=original.kind, action=original.action, control=original.control).id,
            kind=original.kind,
            action=original.action,
            control=original.control,
            title=original.title,
            description=original.description,
            disabled=original.disabled,
            condition=original.condition,
            continue_on_error=original.continue_on_error,
            annotations=deepcopy(original.annotations),
            params=deepcopy(original.params),
        )
        self.scenario.steps.insert(index + 1, copied)
        return copied

    def update_step(
        self,
        index: int,
        title: str | None = None,
        params: dict[str, Any] | None = None,
        action: str | None = None,
        *,
        kind: str | None = None,
        control: str | None = None,
        description: str | None = None,
        disabled: bool | None = None,
        condition: str | None = None,
        continue_on_error: bool | None = None,
        annotations: list[dict[str, Any]] | None = None,
    ) -> Step:
        step = self.scenario.steps[index]
        if kind is not None:
            step.kind = _validate_kind(kind)
        if title is not None:
            step.title = title
        if params is not None:
            step.params = deepcopy(dict(params))
        if action is not None:
            if step.kind != "action":
                raise ValueError("action can only be set when kind is 'action'.")
            step.action = _validate_action(action)
        if control is not None:
            if step.kind != "control":
                raise ValueError("control can only be set when kind is 'control'.")
            step.control = _validate_control(control)
        if description is not None:
            step.description = description
        if disabled is not None:
            step.disabled = bool(disabled)
        if condition is not None:
            step.condition = condition
        if continue_on_error is not None:
            step.continue_on_error = bool(continue_on_error)
        if annotations is not None:
            step.annotations = deepcopy(annotations)
        return step
