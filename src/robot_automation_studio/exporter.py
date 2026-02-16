"""Export scenarios into Robot Framework suites and JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    TARGET_WINDOW_HINT_KEY,
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
    normalize_unity_execution_mode,
)
from .variable_resolution import resolve_scenario_variables


@dataclass(slots=True)
class ExportResult:
    robot_path: Path
    json_path: Path


def _safe_suite_name(name: str) -> str:
    return name.strip().replace(" ", "-").lower()


def _scenario_execution_mode(scenario: Scenario) -> str:
    execution = dict(scenario.execution or {})
    mode = execution.get("mode")
    if mode is not None:
        return normalize_unity_execution_mode(mode)
    return normalize_unity_execution_mode(scenario.metadata.get(UNITY_EXECUTION_MODE_KEY))


def _scenario_variable_default(scenario: Scenario, variable_id: str) -> str:
    normalized_id = str(variable_id).strip()
    for variable in scenario.variables:
        if str(variable.get("id") or "").strip() != normalized_id:
            continue
        value = variable.get("default")
        return str(value if value is not None else "").strip()
    return ""


def _scenario_project_path(scenario: Scenario, execution_mode: str) -> str:
    from_metadata = str(scenario.metadata.get(UNITY_PROJECT_PATH_KEY) or "").strip()
    if from_metadata:
        return from_metadata
    if execution_mode != "launch":
        return ""
    execution = dict(scenario.execution or {})
    launch = execution.get("launch")
    if isinstance(launch, dict):
        variable_id = str(launch.get("unity_project_path_var") or "").strip()
        if variable_id != "":
            return _scenario_variable_default(scenario, variable_id)
    return _scenario_variable_default(scenario, "unity_project_path")


def _scenario_window_hint(scenario: Scenario) -> str:
    if str(scenario.target_window_hint or "").strip():
        return str(scenario.target_window_hint).strip()
    from_metadata = str(scenario.metadata.get(TARGET_WINDOW_HINT_KEY) or "").strip()
    if from_metadata:
        return from_metadata
    execution = dict(scenario.execution or {})
    attach = execution.get("attach")
    if isinstance(attach, dict):
        variable_id = str(attach.get("window_hint_var") or "").strip()
        if variable_id:
            from_variable = _scenario_variable_default(scenario, variable_id)
            if from_variable:
                return from_variable
    from_variable = _scenario_variable_default(scenario, "unity_window_hint")
    if from_variable:
        return from_variable
    return "Unity"


def _robot_safe_project_path(project_path: str) -> str:
    normalized = str(project_path or "").strip()
    if normalized == "":
        return ""
    return normalized.replace("\\", "/")


def _robot_named_args(params: dict[str, object], keys: tuple[str, ...]) -> str:
    parts: list[str] = []
    for key in keys:
        value = params.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text == "":
            continue
        parts.append(f"{key}={text}")
    if not parts:
        return ""
    return "    " + "    ".join(parts)


def _wait_seconds_from_step(step_payload: dict[str, Any]) -> float:
    timing = step_payload.get("timing")
    if not isinstance(timing, dict):
        return 0.0
    value = timing.get("stability_ms")
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value) / 1000.0)
    except (TypeError, ValueError):
        return 0.0


def _uia_selector_args(selector: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("title", "automation_id", "class_name", "control_type", "index"):
        value = selector.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        result[f"{prefix}{key}"] = value
    return result


def _require_selector(step_payload: dict[str, Any], action: str) -> dict[str, Any]:
    target = step_payload.get("target")
    if not isinstance(target, dict):
        raise ValueError(f"{action} requires target selector.")
    strategy = str(target.get("strategy") or "").strip()
    if strategy == "":
        raise ValueError(f"{action} target selector requires strategy.")
    return target


def _step_robot_lines_from_payload(step_payload: dict[str, Any], indent: str = "    ") -> list[str]:
    kind = str(step_payload.get("kind") or "").strip().lower()
    title = str(step_payload.get("title") or "").strip() or "step"
    if kind == "group":
        children = list(step_payload.get("steps") or [])
        lines: list[str] = [f"{indent}# group: {title}"]
        for child in children:
            if not isinstance(child, dict):
                raise ValueError(f"group step '{title}' has non-object child step.")
            lines.extend(_step_robot_lines_from_payload(child, indent=indent))
        return lines
    if kind == "control":
        control = str(step_payload.get("control") or "").strip()
        raise ValueError(f"Unsupported control step for Robot export: {control}")
    if kind != "action":
        raise ValueError(f"Unsupported step kind for Robot export: {kind}")

    action = str(step_payload.get("action") or "").strip().lower()
    wait_seconds = _wait_seconds_from_step(step_payload)

    if action == "click":
        target = _require_selector(step_payload, "click")
        strategy = str(target.get("strategy") or "").strip().lower()
        if strategy == "unity_hierarchy":
            unity_hierarchy = target.get("unity_hierarchy")
            if not isinstance(unity_hierarchy, dict):
                raise ValueError(
                    "click unity_hierarchy target must include unity_hierarchy object."
                )
            hierarchy_path = str(unity_hierarchy.get("path") or "").strip()
            if hierarchy_path == "":
                raise ValueError("click unity_hierarchy target requires path.")
            timeout_seconds = 4.0
            timing = step_payload.get("timing")
            if isinstance(timing, dict) and timing.get("timeout_seconds") is not None:
                try:
                    timeout_seconds = float(timing["timeout_seconds"])
                except (TypeError, ValueError):
                    timeout_seconds = 4.0
            lines = [
                f"{indent}${{annotation}}=    Wait Until Keyword Succeeds"
                "    45 sec    1 sec    Select Unity Hierarchy Object"
                f"    hierarchy_path={hierarchy_path}    timeout_seconds={timeout_seconds}",
            ]
            lines.append(f"{indent}Wait For Seconds    {wait_seconds}")
            lines.append(f"{indent}Emit Annotation Metadata    ${{annotation}}")
            return lines
        if strategy == "uia":
            uia = target.get("uia")
            if not isinstance(uia, dict):
                raise ValueError("click uia target must include uia object.")
            selector_args = _robot_named_args(
                _uia_selector_args(uia),
                ("title", "automation_id", "class_name", "control_type", "index"),
            )
            if selector_args == "":
                raise ValueError(
                    "click uia target requires selector fields "
                    "(title/automation_id/class_name/control_type)."
                )
            return [
                f"{indent}${{annotation}}=    Click Unity Element{selector_args}",
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
        if strategy == "coordinate":
            coordinate = target.get("coordinate")
            if not isinstance(coordinate, dict):
                raise ValueError("click coordinate target must include coordinate object.")
            x_ratio = coordinate.get("x_ratio")
            y_ratio = coordinate.get("y_ratio")
            if x_ratio is None or y_ratio is None:
                raise ValueError("click coordinate target requires x_ratio and y_ratio.")
            return [
                f"{indent}${{annotation}}=    Click Unity Relative    {x_ratio}    {y_ratio}",
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
        raise ValueError(f"Unsupported click target strategy: {strategy}")

    if action == "drag_drop":
        target = _require_selector(step_payload, "drag_drop")
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("drag_drop requires input payload with source selector.")
        source = input_payload.get("source")
        if not isinstance(source, dict):
            raise ValueError("drag_drop requires input.source selector.")

        target_strategy = str(target.get("strategy") or "").strip().lower()
        source_strategy = str(source.get("strategy") or "").strip().lower()
        if target_strategy == "uia" and source_strategy == "uia":
            target_uia = target.get("uia")
            source_uia = source.get("uia")
            if not isinstance(target_uia, dict) or not isinstance(source_uia, dict):
                raise ValueError(
                    "drag_drop uia strategy requires uia objects on source and target."
                )
            merged = {}
            merged.update(_uia_selector_args(source_uia, prefix="source_"))
            merged.update(_uia_selector_args(target_uia, prefix="target_"))
            source_args = _robot_named_args(
                merged,
                (
                    "source_title",
                    "source_automation_id",
                ),
            )
            target_args = _robot_named_args(
                merged,
                (
                    "target_title",
                    "target_automation_id",
                ),
            )
            if source_args == "" or target_args == "":
                raise ValueError(
                    "drag_drop uia strategy requires both source and target selector fields."
                )
            drag_keyword_line = (
                f"{indent}${{annotation}}=    Drag Unity Element To Element"
                f"{source_args}{target_args}"
            )
            return [
                drag_keyword_line,
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
        if target_strategy == "coordinate" and source_strategy == "coordinate":
            target_coordinate = target.get("coordinate")
            source_coordinate = source.get("coordinate")
            if not isinstance(target_coordinate, dict) or not isinstance(source_coordinate, dict):
                raise ValueError(
                    "drag_drop coordinate strategy requires coordinate objects "
                    "on source and target."
                )
            from_x = source_coordinate.get("x_ratio")
            from_y = source_coordinate.get("y_ratio")
            to_x = target_coordinate.get("x_ratio")
            to_y = target_coordinate.get("y_ratio")
            if None in (from_x, from_y, to_x, to_y):
                raise ValueError(
                    "drag_drop coordinate strategy requires x_ratio/y_ratio for source and target."
                )
            drag_keyword_line = (
                f"{indent}${{annotation}}=    Drag Unity Relative    {from_x}    {from_y}"
                f"    {to_x}    {to_y}"
            )
            return [
                drag_keyword_line,
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
        raise ValueError(
            "Unsupported drag_drop selector strategy pair. "
            f"source={source_strategy}, target={target_strategy}"
        )

    if action == "press_keys":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("press_keys requires input payload.")
        if "shortcut" in input_payload:
            return [f"{indent}Send Unity Shortcut    {input_payload['shortcut']}"]
        if "keys" in input_payload:
            return [f"{indent}Press Unity Keys    {input_payload['keys']}"]
        raise ValueError("press_keys requires input.shortcut or input.keys.")

    if action == "open_menu":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("open_menu requires input payload.")
        menu_path = str(input_payload.get("menu_path") or "").strip()
        if menu_path == "":
            raise ValueError("open_menu requires input.menu_path.")
        return [f"{indent}Open Unity Top Menu    {menu_path}"]

    if action == "type_text":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("type_text requires input payload.")
        text = str(input_payload.get("text") or "")
        return [f"{indent}Type Unity Text    {text}"]

    if action == "screenshot":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            input_payload = {}
        path = str(input_payload.get("path") or "")
        return [f"{indent}Capture Unity Screenshot    {path}"]

    if action == "wait_for":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("wait_for currently requires input.seconds.")
        if "seconds" not in input_payload:
            raise ValueError("wait_for currently requires input.seconds.")
        return [f"{indent}Wait For Seconds    {input_payload['seconds']}"]

    raise ValueError(f"Unsupported action for Robot export: {action}")


def _step_robot_lines(step: Step, indent: str = "    ") -> list[str]:
    step_payload = step.to_dict()
    return _step_robot_lines_from_payload(step_payload, indent=indent)


def generate_robot_suite(
    scenario: Scenario,
    suite_name: str | None = None,
    *,
    active_profile: str | None = None,
) -> str:
    resolved_scenario = resolve_scenario_variables(scenario, active_profile=active_profile)
    test_case_name = suite_name or resolved_scenario.name
    execution_mode = _scenario_execution_mode(resolved_scenario)
    unity_project_path = _robot_safe_project_path(
        _scenario_project_path(resolved_scenario, execution_mode=execution_mode)
    )
    window_hint = _scenario_window_hint(resolved_scenario)
    lines = [
        "*** Settings ***",
        "Library    Collections",
        "Library    robotframework_unity_editor.UnityEditorLibrary",
        "",
        "*** Test Cases ***",
        test_case_name,
        "    Set Unity Output Directory    ${OUTPUT DIR}",
        f"    ${{unity_mode}}=    Set Variable    {execution_mode}",
        f"    ${{unity_project_path}}=    Set Variable    {unity_project_path}",
        f"    ${{unity_window_hint}}=    Set Variable    {window_hint}",
        "    TRY",
        "        IF    '${unity_mode}' == 'launch'",
        "            IF    '${unity_project_path}' != ''",
        "                Ensure Unity Bridge UPM Package    ${unity_project_path}",
        "            END",
        "            Require Unity Project Path    ${unity_project_path}",
        "            Start Unity Editor    project_path=${unity_project_path}",
        "        ELSE",
        "            Attach To Running Unity Editor    window_hint=${unity_window_hint}",
        "        END",
    ]
    for step in resolved_scenario.steps:
        lines.append(f"        # {step.title} ({step.kind})")
        lines.extend(_step_robot_lines(step, indent="        "))
    lines.extend(
        [
            "    FINALLY",
            "        IF    '${unity_mode}' == 'launch'",
            "            Stop Unity Editor",
            "        END",
            "    END",
            "",
            "*** Keywords ***",
            "Emit Annotation Metadata",
            "    [Arguments]    ${annotation}",
            "    ${metadata}=    Create Dictionary    annotation=${annotation}",
            "    Emit DOCMETA    ${metadata}",
            "",
            "Require Unity Project Path",
            "    [Arguments]    ${project_path}",
            "    ${normalized}=    Evaluate    str($project_path).strip()",
            "    IF    '${normalized}' == ''",
            "        Fail    unity_project_path is required when unity_mode is launch.",
            "    END",
            "",
        ]
    )
    return "\n".join(lines)


def export_all(
    scenario: Scenario,
    output_dir: Path,
    suite_name: str | None = None,
    *,
    active_profile: str | None = None,
) -> ExportResult:
    resolved_scenario = resolve_scenario_variables(scenario, active_profile=active_profile)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = suite_name or _safe_suite_name(resolved_scenario.name)
    robot_path = output_dir / f"{safe_name}.robot"
    json_path = output_dir / f"{safe_name}.scenario.json"

    robot_path.write_text(
        generate_robot_suite(resolved_scenario, suite_name=safe_name),
        encoding="utf-8",
    )
    resolved_scenario.save_json(json_path)

    return ExportResult(robot_path=robot_path, json_path=json_path)
