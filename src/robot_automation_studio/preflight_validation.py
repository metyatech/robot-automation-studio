"""Scenario preflight validation before export/run."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from typing import Any

from .exporter import validate_exportable_scenario, validate_step_exportability
from .models import Scenario

_AT_PATH_RE = re.compile(r"\sat\s([A-Za-z0-9_\[\]-]+(?:\.[A-Za-z0-9_\[\]-]+)*)\.?$")
_MISSING_VARIABLE_RE = re.compile(r"required variable '([A-Za-z0-9_-]+)' is missing")
_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_-]*)\}")


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    location: str = ""


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    resolved_scenario: Scenario | None = None

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def _is_missing_required(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _selected_profile_name(payload: dict[str, Any], active_profile: str | None) -> str:
    if active_profile is not None:
        return str(active_profile).strip()
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return ""
    return str(execution.get("active_profile") or "").strip()


def _collect_variable_definitions(
    payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    raw_variables = payload.get("variables")
    if raw_variables is None:
        return {}, issues
    if not isinstance(raw_variables, list):
        issues.append(
            ValidationIssue(
                code="variables.invalid_type",
                location="variables",
                message="variables must be a list.",
            )
        )
        return {}, issues

    definitions: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw_variables):
        if not isinstance(item, dict):
            continue
        variable_id = str(item.get("id") or "").strip()
        location = f"variables[{index}].id"
        if variable_id == "":
            issues.append(
                ValidationIssue(
                    code="variables.id_required",
                    location=location,
                    message="Variable id is required.",
                )
            )
            continue
        if variable_id in definitions:
            issues.append(
                ValidationIssue(
                    code="variables.duplicate_id",
                    location=location,
                    message=f"Duplicate variable id: {variable_id}",
                )
            )
            continue
        definitions[variable_id] = item
    return definitions, issues


def _collect_profile_issues(
    payload: dict[str, Any],
    *,
    selected_profile: str,
    variable_defs: dict[str, dict[str, Any]],
) -> tuple[list[ValidationIssue], dict[str, Any]]:
    issues: list[ValidationIssue] = []
    if selected_profile == "":
        return issues, {}

    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        issues.append(
            ValidationIssue(
                code="profiles.unknown",
                location="execution.active_profile",
                message=f"Unknown profile: {selected_profile}",
            )
        )
        return issues, {}

    selected_payload = profiles.get(selected_profile)
    if not isinstance(selected_payload, dict):
        issues.append(
            ValidationIssue(
                code="profiles.unknown",
                location="execution.active_profile",
                message=f"Unknown profile: {selected_profile}",
            )
        )
        return issues, {}

    raw_overrides = selected_payload.get("variables")
    if raw_overrides is None:
        return issues, {}
    if not isinstance(raw_overrides, dict):
        issues.append(
            ValidationIssue(
                code="profiles.variables.invalid_type",
                location=f"profiles.{selected_profile}.variables",
                message=f"Profile '{selected_profile}' variables must be an object.",
            )
        )
        return issues, {}

    overrides: dict[str, Any] = {}
    for key, value in raw_overrides.items():
        variable_id = str(key or "").strip()
        location = f"profiles.{selected_profile}.variables.{variable_id or '<empty>'}"
        if variable_id == "":
            issues.append(
                ValidationIssue(
                    code="profiles.variables.empty_key",
                    location=location,
                    message=f"Profile '{selected_profile}' contains an empty variable key.",
                )
            )
            continue
        if variable_id not in variable_defs:
            issues.append(
                ValidationIssue(
                    code="profiles.variables.unknown",
                    location=location,
                    message=(
                        f"Profile '{selected_profile}' contains unknown variable '{variable_id}'."
                    ),
                )
            )
            continue
        overrides[variable_id] = value
    return issues, overrides


def _collect_required_variable_issues(
    variable_defs: dict[str, dict[str, Any]],
    *,
    overrides: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for variable_id, definition in variable_defs.items():
        if not bool(definition.get("required", False)):
            continue
        value = overrides.get(variable_id, definition.get("default"))
        if _is_missing_required(value):
            issues.append(
                ValidationIssue(
                    code="variables.required_missing",
                    location=f"variables.{variable_id}.default",
                    message=f"required variable '{variable_id}' is missing.",
                )
            )
    return issues


def _collect_execution_issues(payload: dict[str, Any]) -> list[ValidationIssue]:
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return []
    raw_timeout = execution.get("subflow_timeout_seconds")
    if raw_timeout in (None, ""):
        return []
    if isinstance(raw_timeout, bool):
        return [
            ValidationIssue(
                code="execution.subflow_timeout.invalid",
                location="execution.subflow_timeout_seconds",
                message="subflow_timeout_seconds must be a positive integer.",
            )
        ]
    if isinstance(raw_timeout, str) and _PLACEHOLDER_RE.search(raw_timeout):
        return []
    try:
        parsed = int(str(raw_timeout).strip())
    except (TypeError, ValueError):
        return [
            ValidationIssue(
                code="execution.subflow_timeout.invalid",
                location="execution.subflow_timeout_seconds",
                message="subflow_timeout_seconds must be a positive integer.",
            )
        ]
    if parsed <= 0:
        return [
            ValidationIssue(
                code="execution.subflow_timeout.invalid",
                location="execution.subflow_timeout_seconds",
                message="subflow_timeout_seconds must be a positive integer.",
            )
        ]
    return []


def _iter_string_leaves(value: Any, *, path: str) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        pairs: list[tuple[str, str]] = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            pairs.extend(_iter_string_leaves(item, path=child_path))
        return pairs
    if isinstance(value, list):
        pairs = []
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]"
            pairs.extend(_iter_string_leaves(item, path=child_path))
        return pairs
    if isinstance(value, str):
        return [(path, value)]
    return []


def _collect_unresolved_placeholder_issues(
    payload: dict[str, Any],
    *,
    variable_defs: dict[str, dict[str, Any]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    known_variable_ids = set(variable_defs.keys())
    for key in (
        "name",
        "description",
        "metadata",
        "execution",
        "recording",
        "outputs",
        "extensions",
        "steps",
        "tags",
        "variables",
        "profiles",
    ):
        if key not in payload:
            continue
        for path, text in _iter_string_leaves(payload[key], path=key):
            for match in _PLACEHOLDER_RE.finditer(text):
                variable_id = match.group(1)
                if variable_id in known_variable_ids:
                    continue
                issues.append(
                    ValidationIssue(
                        code="variables.unresolved_placeholder",
                        location=path,
                        message=f"Unresolved placeholder: ${{{variable_id}}} at {path}",
                    )
                )
    return issues


def _collect_step_exportability_issues(scenario: Scenario) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, step in enumerate(scenario.steps):
        try:
            validate_step_exportability(step, path=f"steps[{index}]")
        except Exception as error:
            message = str(error)
            inferred = _infer_issue_location(message)
            if inferred != "scenario":
                location = inferred
            elif "requires target selector" in message:
                location = f"steps[{index}].target"
            elif "requires input" in message:
                location = f"steps[{index}].input"
            else:
                location = f"steps[{index}]"
            issues.append(
                ValidationIssue(
                    code="steps.invalid",
                    location=location,
                    message=message,
                )
            )
    return issues


def _iter_step_payloads(raw_steps: Any, *, path: str) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(raw_steps, list):
        return []
    collected: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        step_path = f"{path}[{index}]"
        collected.append((step_path, item))
        kind = str(item.get("kind") or "action").strip().lower()
        if kind == "group":
            collected.extend(_iter_step_payloads(item.get("steps"), path=f"{step_path}.steps"))
            continue
        if kind != "control":
            continue
        collected.extend(_iter_step_payloads(item.get("steps"), path=f"{step_path}.steps"))
        collected.extend(
            _iter_step_payloads(item.get("catch_steps"), path=f"{step_path}.catch_steps")
        )
        collected.extend(
            _iter_step_payloads(item.get("finally_steps"), path=f"{step_path}.finally_steps")
        )
        branches = item.get("branches")
        if not isinstance(branches, list):
            continue
        for branch_index, branch in enumerate(branches):
            if not isinstance(branch, dict):
                continue
            collected.extend(
                _iter_step_payloads(
                    branch.get("steps"),
                    path=f"{step_path}.branches[{branch_index}].steps",
                )
            )
    return collected


def _collect_tooling_issues(scenario: Scenario) -> list[ValidationIssue]:
    payload = scenario.to_dict()
    step_payloads = _iter_step_payloads(payload.get("steps"), path="steps")
    start_video_locations: list[str] = []
    for step_path, step_payload in step_payloads:
        kind = str(step_payload.get("kind") or "action").strip().lower()
        if kind != "action":
            continue
        action = str(step_payload.get("action") or "").strip().lower()
        if action != "start_video":
            continue
        start_video_locations.append(f"{step_path}.input.path")
    if not start_video_locations:
        return []
    if shutil.which("ffmpeg") is not None:
        return []
    return [
        ValidationIssue(
            code="tooling.ffmpeg_missing",
            location=start_video_locations[0],
            message="ffmpeg not found in PATH. Install ffmpeg or add it to PATH.",
        )
    ]


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    deduped: list[ValidationIssue] = []
    seen: set[tuple[str, str, str]] = set()
    for issue in issues:
        key = (issue.code, issue.location, issue.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return sorted(deduped, key=lambda item: (item.location, item.code, item.message))


def _infer_issue_location(error_message: str) -> str:
    text = str(error_message or "").strip()
    if text == "":
        return "scenario"

    at_path_match = _AT_PATH_RE.search(text)
    if at_path_match is not None:
        return at_path_match.group(1)

    missing_variable_match = _MISSING_VARIABLE_RE.search(text)
    if missing_variable_match is not None:
        return f"variables.{missing_variable_match.group(1)}.default"

    if text.startswith("Unknown profile:"):
        return "execution.active_profile"
    return "scenario"


def validate_scenario(
    scenario: Scenario,
    *,
    active_profile: str | None = None,
) -> ValidationReport:
    """Return preflight validation report for run/export."""

    report = ValidationReport()
    payload = scenario.to_dict()
    selected_profile = _selected_profile_name(payload, active_profile)
    variable_defs, variable_issues = _collect_variable_definitions(payload)
    profile_issues, profile_overrides = _collect_profile_issues(
        payload,
        selected_profile=selected_profile,
        variable_defs=variable_defs,
    )
    required_issues = _collect_required_variable_issues(
        variable_defs,
        overrides=profile_overrides,
    )
    execution_issues = _collect_execution_issues(payload)
    unresolved_placeholder_issues = _collect_unresolved_placeholder_issues(
        payload,
        variable_defs=variable_defs,
    )
    tooling_issues = _collect_tooling_issues(scenario)
    step_issues = _collect_step_exportability_issues(scenario)

    all_issues = _dedupe_issues(
        [
            *variable_issues,
            *profile_issues,
            *required_issues,
            *execution_issues,
            *unresolved_placeholder_issues,
            *tooling_issues,
            *step_issues,
        ]
    )
    if all_issues:
        report.issues.extend(all_issues)
        return report

    try:
        resolved = validate_exportable_scenario(
            scenario,
            active_profile=active_profile,
        )
    except Exception as error:
        report.issues.append(
            ValidationIssue(
                code="scenario.invalid",
                message=str(error),
                location=_infer_issue_location(str(error)),
            )
        )
        return report
    report.resolved_scenario = resolved
    return report
