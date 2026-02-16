"""Scenario variable/profile resolution helpers."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .models import Scenario

_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_-]*)\}")


def resolve_scenario_variables(
    scenario: Scenario,
    *,
    active_profile: str | None = None,
) -> Scenario:
    """Return a resolved scenario copy for export/run.

    - Applies variable defaults.
    - Applies profile overrides when an active profile is selected.
    - Expands `${variable_id}` placeholders in run/export-relevant payload sections.
    - Fails fast for unknown profiles, missing required variables, and unresolved placeholders.
    """

    payload = scenario.to_dict()
    resolved_payload = resolve_scenario_payload(payload, active_profile=active_profile)
    return Scenario.from_dict(resolved_payload)


def resolve_scenario_payload(
    payload: dict[str, Any],
    *,
    active_profile: str | None = None,
) -> dict[str, Any]:
    """Resolve variables/placeholders in a raw scenario payload dictionary."""

    scenario_payload = deepcopy(payload)
    variable_defs = _collect_variable_definitions(scenario_payload.get("variables"))
    selected_profile = _selected_profile_name(
        execution=scenario_payload.get("execution"),
        active_profile=active_profile,
    )
    overrides = _profile_overrides(
        profiles=scenario_payload.get("profiles"),
        selected_profile=selected_profile,
        variable_defs=variable_defs,
    )
    resolved_values = _resolve_variable_values(variable_defs, overrides=overrides)
    _validate_required_variables(variable_defs, resolved_values)

    execution_payload = dict(scenario_payload.get("execution") or {})
    if selected_profile:
        execution_payload["active_profile"] = selected_profile
    else:
        execution_payload.pop("active_profile", None)
    scenario_payload["execution"] = execution_payload

    variables_payload = scenario_payload.get("variables")
    if isinstance(variables_payload, list):
        for item in variables_payload:
            if not isinstance(item, dict):
                continue
            variable_id = str(item.get("id") or "").strip()
            if variable_id in resolved_values:
                item["default"] = deepcopy(resolved_values[variable_id])

    for key in (
        "name",
        "description",
        "metadata",
        "execution",
        "recording",
        "outputs",
        "extensions",
    ):
        if key in scenario_payload:
            scenario_payload[key] = _resolve_payload_value(
                scenario_payload[key],
                resolved_values=resolved_values,
                path=key,
            )
    if "steps" in scenario_payload:
        scenario_payload["steps"] = _resolve_payload_value(
            scenario_payload["steps"],
            resolved_values=resolved_values,
            path="steps",
        )
    if "tags" in scenario_payload:
        scenario_payload["tags"] = _resolve_payload_value(
            scenario_payload["tags"],
            resolved_values=resolved_values,
            path="tags",
        )
    return scenario_payload


def _collect_variable_definitions(raw_variables: Any) -> dict[str, dict[str, Any]]:
    if raw_variables is None:
        return {}
    if not isinstance(raw_variables, list):
        raise ValueError("variables must be a list of objects.")

    definitions: dict[str, dict[str, Any]] = {}
    for item in raw_variables:
        if not isinstance(item, dict):
            continue
        variable_id = str(item.get("id") or "").strip()
        if variable_id == "":
            raise ValueError("Variable id is required.")
        if variable_id in definitions:
            raise ValueError(f"Duplicate variable id: {variable_id}")
        definitions[variable_id] = deepcopy(item)
    return definitions


def _selected_profile_name(execution: Any, active_profile: str | None) -> str:
    if active_profile is not None:
        return str(active_profile).strip()
    if not isinstance(execution, dict):
        return ""
    return str(execution.get("active_profile") or "").strip()


def _profile_overrides(
    *,
    profiles: Any,
    selected_profile: str,
    variable_defs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if selected_profile == "":
        return {}
    if not isinstance(profiles, dict):
        raise ValueError(f"Unknown profile: {selected_profile}")
    profile_payload = profiles.get(selected_profile)
    if not isinstance(profile_payload, dict):
        raise ValueError(f"Unknown profile: {selected_profile}")
    raw_overrides = profile_payload.get("variables")
    if raw_overrides is None:
        return {}
    if not isinstance(raw_overrides, dict):
        raise ValueError(f"Profile '{selected_profile}' must define variables as an object.")
    overrides: dict[str, Any] = {}
    for key, value in raw_overrides.items():
        variable_id = str(key or "").strip()
        if variable_id == "":
            raise ValueError(f"Profile '{selected_profile}' contains an empty variable key.")
        if variable_id not in variable_defs:
            raise ValueError(
                f"Profile '{selected_profile}' contains unknown variable '{variable_id}'."
            )
        overrides[variable_id] = deepcopy(value)
    return overrides


def _resolve_variable_values(
    variable_defs: dict[str, dict[str, Any]],
    *,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    raw_values: dict[str, Any] = {}
    for variable_id, definition in variable_defs.items():
        raw_values[variable_id] = deepcopy(definition.get("default"))
    for variable_id, value in overrides.items():
        raw_values[variable_id] = deepcopy(value)

    resolved: dict[str, Any] = {}
    stack: list[str] = []

    def resolve_variable(variable_id: str) -> Any:
        if variable_id in resolved:
            return deepcopy(resolved[variable_id])
        if variable_id not in raw_values:
            raise ValueError(f"Unresolved placeholder: ${{{variable_id}}}")
        if variable_id in stack:
            cycle = " -> ".join([*stack, variable_id])
            raise ValueError(f"Circular variable reference detected: {cycle}")
        stack.append(variable_id)
        try:
            resolved_value = _resolve_payload_value(
                raw_values[variable_id],
                resolved_values=resolved,
                resolver=resolve_variable,
                path=f"variables.{variable_id}.default",
            )
        finally:
            stack.pop()
        resolved[variable_id] = deepcopy(resolved_value)
        return deepcopy(resolved_value)

    for variable_id in raw_values:
        resolve_variable(variable_id)
    return resolved


def _validate_required_variables(
    variable_defs: dict[str, dict[str, Any]],
    resolved_values: dict[str, Any],
) -> None:
    for variable_id, definition in variable_defs.items():
        if not bool(definition.get("required", False)):
            continue
        value = resolved_values.get(variable_id)
        if _is_missing_required(value):
            raise ValueError(f"required variable '{variable_id}' is missing.")


def _is_missing_required(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _resolve_payload_value(
    value: Any,
    *,
    resolved_values: dict[str, Any],
    path: str,
    resolver=None,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_payload_value(
                item,
                resolved_values=resolved_values,
                path=f"{path}.{key}" if path else str(key),
                resolver=resolver,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_payload_value(
                item,
                resolved_values=resolved_values,
                path=f"{path}[{index}]",
                resolver=resolver,
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, str):
        return deepcopy(value)
    return _resolve_string_value(
        value,
        resolved_values=resolved_values,
        path=path,
        resolver=resolver,
    )


def _resolve_string_value(
    text: str,
    *,
    resolved_values: dict[str, Any],
    path: str,
    resolver=None,
) -> Any:
    full = _PLACEHOLDER_RE.fullmatch(text)
    if full is not None:
        variable_id = full.group(1)
        value = _resolve_variable_reference(
            variable_id,
            resolved_values=resolved_values,
            path=path,
            resolver=resolver,
        )
        return deepcopy(value)
    if _PLACEHOLDER_RE.search(text) is None:
        return text

    def replace(match: re.Match[str]) -> str:
        variable_id = match.group(1)
        value = _resolve_variable_reference(
            variable_id,
            resolved_values=resolved_values,
            path=path,
            resolver=resolver,
        )
        if value is None:
            return ""
        return str(value)

    return _PLACEHOLDER_RE.sub(replace, text)


def _resolve_variable_reference(
    variable_id: str,
    *,
    resolved_values: dict[str, Any],
    path: str,
    resolver,
) -> Any:
    if variable_id in resolved_values:
        return deepcopy(resolved_values[variable_id])
    if resolver is None:
        raise ValueError(f"Unresolved placeholder: ${{{variable_id}}} at {path}")
    return resolver(variable_id)
