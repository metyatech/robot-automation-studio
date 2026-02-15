"""Export scenarios into Robot Framework suites and JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
    normalize_unity_execution_mode,
)


@dataclass(slots=True)
class ExportResult:
    robot_path: Path
    json_path: Path


def _safe_suite_name(name: str) -> str:
    return name.strip().replace(" ", "-").lower()


def _scenario_execution_mode(scenario: Scenario) -> str:
    return normalize_unity_execution_mode(scenario.metadata.get(UNITY_EXECUTION_MODE_KEY))


def _scenario_project_path(scenario: Scenario) -> str:
    return str(scenario.metadata.get(UNITY_PROJECT_PATH_KEY) or "").strip()


def _step_robot_lines(step: Step, indent: str = "    ") -> list[str]:
    params = step.params
    lines: list[str]
    if step.action == "click":
        lines = [
            f"{indent}${{annotation}}=    Click Unity Relative"
            f"    {params.get('x_ratio', 0.5)}    {params.get('y_ratio', 0.5)}"
            f"    box_width={params.get('box_width', 180)}"
            f"    box_height={params.get('box_height', 48)}",
            f"{indent}Wait For Seconds    {params.get('wait_seconds', 0.8)}",
            f"{indent}Emit Annotation Metadata    ${{annotation}}",
        ]
        return lines
    if step.action == "drag":
        lines = [
            f"{indent}${{annotation}}=    Drag Unity Relative"
            f"    {params.get('from_x_ratio', 0.2)}    {params.get('from_y_ratio', 0.4)}"
            f"    {params.get('to_x_ratio', 0.7)}    {params.get('to_y_ratio', 0.4)}",
            f"{indent}Wait For Seconds    {params.get('wait_seconds', 0.8)}",
            f"{indent}Emit Annotation Metadata    ${{annotation}}",
        ]
        return lines
    if step.action == "wait":
        return [f"{indent}Wait For Seconds    {params.get('seconds', 1.0)}"]
    if step.action == "shortcut":
        return [f"{indent}Send Unity Shortcut    {params.get('shortcut', 'CTRL+S')}"]
    if step.action == "keys":
        return [f"{indent}Press Unity Keys    {params.get('keys', '{ENTER}')}"]
    if step.action == "menu":
        return [f"{indent}Open Unity Top Menu    {params.get('menu_path', 'File>Save')}"]
    if step.action == "type":
        return [f"{indent}Type Unity Text    {params.get('text', '')}"]
    if step.action == "screenshot":
        return [f"{indent}Capture Unity Screenshot    {params.get('path', '')}"]
    return [f"{indent}Log    Unsupported action: {step.action}"]


def generate_robot_suite(scenario: Scenario, suite_name: str | None = None) -> str:
    test_case_name = suite_name or scenario.name
    execution_mode = _scenario_execution_mode(scenario)
    unity_project_path = _scenario_project_path(scenario)
    window_hint = scenario.target_window_hint.strip() or "Unity"
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
        "            Require Unity Project Path    ${unity_project_path}",
        "            Start Unity Editor    project_path=${unity_project_path}",
        "        ELSE",
        "            Attach To Running Unity Editor    window_hint=${unity_window_hint}",
        "        END",
        "        Focus Unity Window",
    ]
    for step in scenario.steps:
        lines.append(f"        # {step.title}")
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


def export_all(scenario: Scenario, output_dir: Path, suite_name: str | None = None) -> ExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = suite_name or _safe_suite_name(scenario.name)
    robot_path = output_dir / f"{safe_name}.robot"
    json_path = output_dir / f"{safe_name}.scenario.json"

    robot_path.write_text(generate_robot_suite(scenario, suite_name=safe_name), encoding="utf-8")
    scenario.save_json(json_path)

    return ExportResult(robot_path=robot_path, json_path=json_path)
