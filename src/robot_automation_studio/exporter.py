"""Export scenarios into Robot Framework suites and JSON payloads."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    SUBFLOW_TIMEOUT_SECONDS_DEFAULT,
    TARGET_WINDOW_HINT_KEY,
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    Step,
    normalize_unity_execution_mode,
    parse_subflow_timeout_seconds,
)
from .variable_resolution import resolve_scenario_variables


@dataclass(slots=True)
class ExportResult:
    robot_path: Path
    json_path: Path


_ACTION_ALIASES = {
    "drag": "drag_drop",
    "type": "type_text",
    "shortcut": "press_keys",
    "keys": "press_keys",
    "menu": "open_menu",
    "wait": "wait_for",
    "select_hierarchy": "select_hierarchy",
}


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


def _scenario_subflow_timeout_seconds(scenario: Scenario) -> int:
    execution = dict(scenario.execution or {})
    return parse_subflow_timeout_seconds(
        execution.get("subflow_timeout_seconds"),
        default=SUBFLOW_TIMEOUT_SECONDS_DEFAULT,
    )


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


def _normalize_action(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized == "":
        return normalized
    return _ACTION_ALIASES.get(normalized, normalized)


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


def _timeout_seconds_from_step(step_payload: dict[str, Any], *, default: float) -> float:
    timing = step_payload.get("timing")
    if not isinstance(timing, dict):
        return default
    value = timing.get("timeout_seconds")
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


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


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if normalized == "" or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _collect_target_candidates(
    target: Any,
    *,
    output: list[dict[str, Any]],
    visited_ids: set[int],
) -> None:
    if not isinstance(target, dict):
        return
    marker = id(target)
    if marker in visited_ids:
        return
    visited_ids.add(marker)
    output.append(target)
    raw_fallbacks = target.get("fallbacks")
    if not isinstance(raw_fallbacks, list):
        return
    for fallback in raw_fallbacks:
        _collect_target_candidates(fallback, output=output, visited_ids=visited_ids)


def _target_candidates_by_strategy(
    target: dict[str, Any],
    *,
    action: str,
    allowed_strategies: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    _collect_target_candidates(target, output=candidates, visited_ids=set())
    matches = [
        candidate
        for candidate in candidates
        if str(candidate.get("strategy") or "").strip().lower() in allowed_strategies
    ]
    if matches:
        return matches
    seen = [
        str(candidate.get("strategy") or "<missing>").strip().lower() for candidate in candidates
    ]
    raise ValueError(
        f"{action} requires one of target strategies {sorted(allowed_strategies)}, seen={seen}"
    )


def _hierarchy_paths_from_targets(
    targets: list[dict[str, Any]],
    *,
    action: str,
) -> list[str]:
    paths: list[str] = []
    for target in targets:
        unity_hierarchy = target.get("unity_hierarchy")
        if not isinstance(unity_hierarchy, dict):
            raise ValueError(
                f"{action} unity_hierarchy target must include unity_hierarchy object."
            )
        path = str(unity_hierarchy.get("path") or "").strip()
        if path == "":
            raise ValueError(f"{action} unity_hierarchy target requires path.")
        paths.append(path)
    deduped = _dedupe_strings(paths)
    if not deduped:
        raise ValueError(f"{action} unity_hierarchy target requires path.")
    return deduped


def _uia_selector_payloads_from_targets(
    targets: list[dict[str, Any]],
    *,
    action: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for target in targets:
        uia = target.get("uia")
        if not isinstance(uia, dict):
            raise ValueError(f"{action} uia target must include uia object.")
        selector_payload = _uia_selector_args(uia)
        if not selector_payload:
            continue
        signature = tuple((key, str(selector_payload[key])) for key in sorted(selector_payload))
        if signature in seen:
            continue
        seen.add(signature)
        payloads.append(selector_payload)
    if payloads:
        return payloads
    raise ValueError(
        f"{action} uia target requires selector fields "
        "(title/automation_id/class_name/control_type)."
    )


def _coordinate_payloads_from_targets(
    targets: list[dict[str, Any]],
    *,
    action: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for target in targets:
        coordinate = target.get("coordinate")
        if not isinstance(coordinate, dict):
            raise ValueError(f"{action} coordinate target must include coordinate object.")
        x_ratio = coordinate.get("x_ratio")
        y_ratio = coordinate.get("y_ratio")
        if x_ratio is None or y_ratio is None:
            continue
        selector_payload: dict[str, Any] = {"x_ratio": x_ratio, "y_ratio": y_ratio}
        anchor = coordinate.get("anchor_window_hint")
        if isinstance(anchor, str) and anchor.strip() != "":
            selector_payload["anchor_window_hint"] = anchor.strip()
        signature = tuple((key, str(selector_payload[key])) for key in sorted(selector_payload))
        if signature in seen:
            continue
        seen.add(signature)
        payloads.append(selector_payload)
    return payloads


def _mixed_uia_coordinate_selector_payloads(
    target: dict[str, Any],
    *,
    action: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    _collect_target_candidates(target, output=candidates, visited_ids=set())
    payloads: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for candidate in candidates:
        strategy = str(candidate.get("strategy") or "").strip().lower()
        payload: dict[str, Any] | None = None
        if strategy == "uia":
            uia = candidate.get("uia")
            if not isinstance(uia, dict):
                raise ValueError(f"{action} uia target must include uia object.")
            selector_payload = _uia_selector_args(uia)
            if selector_payload:
                payload = {"strategy": "uia"}
                payload.update(selector_payload)
        elif strategy == "coordinate":
            coordinate_payloads = _coordinate_payloads_from_targets([candidate], action=action)
            if coordinate_payloads:
                payload = {"strategy": "coordinate"}
                payload.update(coordinate_payloads[0])
        if payload is None:
            continue
        signature = tuple((key, str(payload[key])) for key in sorted(payload))
        if signature in seen:
            continue
        seen.add(signature)
        payloads.append(payload)
    if payloads:
        return payloads
    raise ValueError(f"{action} requires target selector candidates.")


def _encode_json_base64(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return base64.b64encode(serialized.encode("utf-8")).decode("ascii")


def _menu_path_candidates(input_payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    raw_candidates = input_payload.get("menu_path_candidates")
    if isinstance(raw_candidates, list):
        candidates.extend(str(candidate).strip() for candidate in raw_candidates)
    menu_path = str(input_payload.get("menu_path") or "").strip()
    deduped = _dedupe_strings(candidates)
    if menu_path and menu_path not in deduped:
        deduped.insert(0, menu_path)
    return deduped


def _normalize_robot_scalar(value: str) -> str:
    text = str(value or "").strip()
    if text == "":
        return ""
    if text.startswith("${") and text.endswith("}"):
        return text
    if text.startswith("$"):
        return text
    if text.startswith("@{") and text.endswith("}"):
        return f"${{{text[2:-1]}}}"
    return f"${{{text}}}"


def _normalize_robot_iterable(value: str) -> str:
    text = str(value or "").strip()
    if text == "":
        return ""
    if text.startswith("@{") and text.endswith("}"):
        return text
    if text.startswith("${") and text.endswith("}"):
        return text
    if text.startswith("@") or text.startswith("$"):
        return text
    return f"@{{{text}}}"


def _validated_child_steps(value: Any, *, path: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Control steps must be a list at {path}.")
    children: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Control step child must be an object at {path}[{index}].")
        children.append(item)
    return children


def _apply_step_guards(
    *,
    step_payload: dict[str, Any],
    lines: list[str],
    indent: str,
    path: str,
    title: str,
) -> list[str]:
    if bool(step_payload.get("disabled")):
        return [f"{indent}# disabled: {title}"]

    wrapped = list(lines)

    def _indent_block(block_lines: list[str]) -> list[str]:
        indented: list[str] = []
        for line in block_lines:
            if line.startswith(indent):
                indented.append(f"{indent}    {line[len(indent) :]}")
            else:
                indented.append(f"{indent}    {line}")
        return indented

    condition = str(step_payload.get("condition") or "").strip()
    if condition != "":
        conditional_lines = [f"{indent}IF    {condition}"]
        conditional_lines.extend(_indent_block(wrapped))
        conditional_lines.append(f"{indent}END")
        wrapped = conditional_lines

    if bool(step_payload.get("continue_on_error")):
        safe_title = title.replace("    ", " ").strip() or "step"
        continue_lines = [f"{indent}TRY"]
        continue_lines.extend(_indent_block(wrapped))
        continue_lines.append(f"{indent}EXCEPT")
        continue_lines.append(
            f"{indent}    Log    continue_on_error step failed at {path}: {safe_title}"
        )
        continue_lines.append(f"{indent}END")
        wrapped = continue_lines

    return wrapped


def _hierarchy_target_from_step(step_payload: dict[str, Any], *, action: str) -> tuple[str, float]:
    target = _require_selector(step_payload, action)
    hierarchy_targets = _target_candidates_by_strategy(
        target,
        action=action,
        allowed_strategies={"unity_hierarchy"},
    )
    hierarchy_path = _hierarchy_paths_from_targets(hierarchy_targets, action=action)[0]
    timeout_seconds = _timeout_seconds_from_step(step_payload, default=4.0)
    return hierarchy_path, timeout_seconds


def _format_hierarchy_select_line(indent: str, hierarchy_path: str, timeout_seconds: float) -> str:
    return (
        f"{indent}${{annotation}}=    Wait Until Keyword Succeeds"
        "    45 sec    1 sec    Select Unity Hierarchy Object"
        f"    hierarchy_path={hierarchy_path}    timeout_seconds={timeout_seconds}"
    )


def _format_hierarchy_select_with_fallbacks_line(
    indent: str,
    hierarchy_paths: list[str],
    timeout_seconds: float,
) -> str:
    return (
        f"{indent}${{annotation}}=    Wait Until Keyword Succeeds"
        "    45 sec    1 sec    Select Unity Hierarchy Object With Fallbacks"
        f"    {timeout_seconds}    {'    '.join(hierarchy_paths)}"
    )


def _run_subflow_path_from_step_payload(step_payload: dict[str, Any], *, path: str) -> str:
    action = _normalize_action(str(step_payload.get("action") or ""))
    if action != "run_subflow":
        raise ValueError(
            "parallel control currently supports only run_subflow child steps."
            f" invalid action at {path}: {action or '<empty>'}"
        )
    input_payload = step_payload.get("input")
    if not isinstance(input_payload, dict):
        raise ValueError(f"run_subflow requires input.path at {path}.")
    subflow_path = str(input_payload.get("path") or "").strip()
    if subflow_path == "":
        raise ValueError(f"run_subflow requires input.path at {path}.")
    return subflow_path


def _step_robot_lines_from_payload(
    step_payload: dict[str, Any],
    indent: str = "    ",
    *,
    path: str = "steps[0]",
) -> list[str]:
    kind = str(step_payload.get("kind") or "").strip().lower()
    title = str(step_payload.get("title") or "").strip() or "step"
    lines: list[str]
    if kind == "group":
        children = list(step_payload.get("steps") or [])
        lines = [f"{indent}# group: {title}"]
        for index, child in enumerate(children):
            if not isinstance(child, dict):
                raise ValueError(
                    f"group step '{title}' has non-object child step at {path}.steps[{index}]."
                )
            child_path = f"{path}.steps[{index}]"
            lines.extend(_step_robot_lines_from_payload(child, indent=indent, path=child_path))
        return _apply_step_guards(
            step_payload=step_payload,
            lines=lines,
            indent=indent,
            path=path,
            title=title,
        )
    if kind == "control":
        control = str(step_payload.get("control") or "").strip().lower()
        if control == "if":
            expression = str(step_payload.get("expression") or "").strip()
            if expression == "":
                raise ValueError("if control step requires expression.")
            lines = [f"{indent}IF    {expression}"]
            for index, child in enumerate(
                _validated_child_steps(step_payload.get("steps"), path=f"{path}.steps")
            ):
                lines.extend(
                    _step_robot_lines_from_payload(
                        child,
                        indent=f"{indent}    ",
                        path=f"{path}.steps[{index}]",
                    )
                )
            branches = step_payload.get("branches")
            if branches is not None:
                if not isinstance(branches, list):
                    raise ValueError(f"if control branches must be a list at {path}.branches.")
                for branch_index, branch in enumerate(branches):
                    if not isinstance(branch, dict):
                        raise ValueError(
                            "if control branch must be an object at "
                            f"{path}.branches[{branch_index}]."
                        )
                    branch_expression = str(branch.get("expression") or "").strip()
                    if branch_expression == "":
                        lines.append(f"{indent}ELSE")
                    else:
                        lines.append(f"{indent}ELSE IF    {branch_expression}")
                    branch_children = _validated_child_steps(
                        branch.get("steps"),
                        path=f"{path}.branches[{branch_index}].steps",
                    )
                    for child_index, child in enumerate(branch_children):
                        lines.extend(
                            _step_robot_lines_from_payload(
                                child,
                                indent=f"{indent}    ",
                                path=f"{path}.branches[{branch_index}].steps[{child_index}]",
                            )
                        )
            lines.append(f"{indent}END")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if control == "for_each":
            item_variable = _normalize_robot_scalar(str(step_payload.get("item_variable") or ""))
            if item_variable == "":
                raise ValueError("for_each control step requires item_variable.")
            items_expression = _normalize_robot_iterable(
                str(step_payload.get("items_expression") or "")
            )
            if items_expression == "":
                raise ValueError("for_each control step requires items_expression.")
            lines = [f"{indent}FOR    {item_variable}    IN    {items_expression}"]
            for index, child in enumerate(
                _validated_child_steps(step_payload.get("steps"), path=f"{path}.steps")
            ):
                lines.extend(
                    _step_robot_lines_from_payload(
                        child,
                        indent=f"{indent}    ",
                        path=f"{path}.steps[{index}]",
                    )
                )
            lines.append(f"{indent}END")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if control == "while":
            expression = str(step_payload.get("expression") or "").strip()
            if expression == "":
                raise ValueError("while control step requires expression.")
            while_line = f"{indent}WHILE    {expression}"
            max_iterations = step_payload.get("max_iterations")
            if max_iterations not in (None, ""):
                while_line = f"{while_line}    limit={max_iterations}"
            lines = [while_line]
            for index, child in enumerate(
                _validated_child_steps(step_payload.get("steps"), path=f"{path}.steps")
            ):
                lines.extend(
                    _step_robot_lines_from_payload(
                        child,
                        indent=f"{indent}    ",
                        path=f"{path}.steps[{index}]",
                    )
                )
            lines.append(f"{indent}END")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if control == "try":
            lines = [f"{indent}TRY"]
            for index, child in enumerate(
                _validated_child_steps(step_payload.get("steps"), path=f"{path}.steps")
            ):
                lines.extend(
                    _step_robot_lines_from_payload(
                        child,
                        indent=f"{indent}    ",
                        path=f"{path}.steps[{index}]",
                    )
                )
            catch_steps = _validated_child_steps(
                step_payload.get("catch_steps"),
                path=f"{path}.catch_steps",
            )
            if catch_steps:
                lines.append(f"{indent}EXCEPT")
                for index, child in enumerate(catch_steps):
                    lines.extend(
                        _step_robot_lines_from_payload(
                            child,
                            indent=f"{indent}    ",
                            path=f"{path}.catch_steps[{index}]",
                        )
                    )
            finally_steps = _validated_child_steps(
                step_payload.get("finally_steps"),
                path=f"{path}.finally_steps",
            )
            if finally_steps:
                lines.append(f"{indent}FINALLY")
                for index, child in enumerate(finally_steps):
                    lines.extend(
                        _step_robot_lines_from_payload(
                            child,
                            indent=f"{indent}    ",
                            path=f"{path}.finally_steps[{index}]",
                        )
                    )
            lines.append(f"{indent}END")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if control == "parallel":
            branches = _validated_child_steps(step_payload.get("steps"), path=f"{path}.steps")
            if len(branches) < 2:
                raise ValueError("parallel control requires at least 2 run_subflow child steps.")
            lines = []
            alias_variables: list[str] = []
            for branch_index, branch in enumerate(branches):
                branch_path = f"{path}.steps[{branch_index}]"
                subflow_path = _run_subflow_path_from_step_payload(branch, path=branch_path)
                sanitized_path = path.replace("[", "_").replace("]", "").replace(".", "_")
                alias = f"parallel_{sanitized_path}_{branch_index}"
                alias_variable = f"${{parallel_alias_{branch_index}}}"
                alias_variables.append(alias_variable)
                lines.append(
                    f"{indent}{alias_variable}=    Start Robot Subflow Process"
                    f"    suite_path={subflow_path}    alias={alias}"
                )
            wait_line = f"{indent}Wait Robot Subflow Processes"
            for alias_variable in alias_variables:
                wait_line = f"{wait_line}    {alias_variable}"
            lines.append(wait_line)
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if control == "break":
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[f"{indent}BREAK"],
                indent=indent,
                path=path,
                title=title,
            )
        if control == "continue":
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[f"{indent}CONTINUE"],
                indent=indent,
                path=path,
                title=title,
            )
        if control == "return":
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[f"{indent}RETURN"],
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError(f"Unsupported control step for Robot export: {control}")
    if kind != "action":
        raise ValueError(f"Unsupported step kind for Robot export: {kind}")

    action = _normalize_action(str(step_payload.get("action") or ""))
    wait_seconds = _wait_seconds_from_step(step_payload)

    if action == "click":
        target = _require_selector(step_payload, "click")
        strategy = str(target.get("strategy") or "").strip().lower()
        if strategy == "unity_hierarchy":
            timeout_seconds = _timeout_seconds_from_step(step_payload, default=4.0)
            hierarchy_targets = _target_candidates_by_strategy(
                target,
                action="click",
                allowed_strategies={"unity_hierarchy"},
            )
            hierarchy_paths = _hierarchy_paths_from_targets(hierarchy_targets, action="click")
            select_line = (
                _format_hierarchy_select_with_fallbacks_line(
                    indent,
                    hierarchy_paths,
                    timeout_seconds,
                )
                if len(hierarchy_paths) > 1
                else _format_hierarchy_select_line(indent, hierarchy_paths[0], timeout_seconds)
            )
            lines = [
                select_line,
            ]
            lines.append(f"{indent}Wait For Seconds    {wait_seconds}")
            lines.append(f"{indent}Emit Annotation Metadata    ${{annotation}}")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if strategy == "uia":
            candidates = _mixed_uia_coordinate_selector_payloads(target, action="click")
            if len(candidates) == 1 and str(candidates[0].get("strategy") or "") == "uia":
                selector = {key: value for key, value in candidates[0].items() if key != "strategy"}
                selector_args = _robot_named_args(
                    selector,
                    ("title", "automation_id", "class_name", "control_type", "index"),
                )
                if selector_args == "":
                    raise ValueError(
                        "click uia target requires selector fields "
                        "(title/automation_id/class_name/control_type)."
                    )
                lines = [
                    f"{indent}${{annotation}}=    Click Unity Element{selector_args}",
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            else:
                selectors_b64 = _encode_json_base64(candidates)
                lines = [
                    (
                        f"{indent}${{annotation}}=    Click Unity Element With Fallbacks"
                        f"    selectors_b64={selectors_b64}"
                    ),
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if strategy == "coordinate":
            coordinate = target.get("coordinate")
            if not isinstance(coordinate, dict):
                raise ValueError("click coordinate target must include coordinate object.")
            x_ratio = coordinate.get("x_ratio")
            y_ratio = coordinate.get("y_ratio")
            if x_ratio is None or y_ratio is None:
                raise ValueError("click coordinate target requires x_ratio and y_ratio.")
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[
                    f"{indent}${{annotation}}=    Click Unity Relative    {x_ratio}    {y_ratio}",
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ],
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError(f"Unsupported click target strategy: {strategy}")

    if action == "select_hierarchy":
        target = _require_selector(step_payload, "select_hierarchy")
        timeout_seconds = _timeout_seconds_from_step(step_payload, default=4.0)
        hierarchy_targets = _target_candidates_by_strategy(
            target,
            action="select_hierarchy",
            allowed_strategies={"unity_hierarchy"},
        )
        hierarchy_paths = _hierarchy_paths_from_targets(
            hierarchy_targets, action="select_hierarchy"
        )
        select_line = (
            _format_hierarchy_select_with_fallbacks_line(
                indent,
                hierarchy_paths,
                timeout_seconds,
            )
            if len(hierarchy_paths) > 1
            else _format_hierarchy_select_line(indent, hierarchy_paths[0], timeout_seconds)
        )
        lines = [
            select_line,
            f"{indent}Wait For Seconds    {wait_seconds}",
            f"{indent}Emit Annotation Metadata    ${{annotation}}",
        ]
        return _apply_step_guards(
            step_payload=step_payload,
            lines=lines,
            indent=indent,
            path=path,
            title=title,
        )

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
            timeout_seconds = _timeout_seconds_from_step(step_payload, default=10.0)
            source_candidates: list[dict[str, Any]] = []
            target_candidates: list[dict[str, Any]] = []
            _collect_target_candidates(source, output=source_candidates, visited_ids=set())
            _collect_target_candidates(target, output=target_candidates, visited_ids=set())
            source_uia_targets = [
                candidate
                for candidate in source_candidates
                if str(candidate.get("strategy") or "").strip().lower() == "uia"
            ]
            target_uia_targets = [
                candidate
                for candidate in target_candidates
                if str(candidate.get("strategy") or "").strip().lower() == "uia"
            ]
            source_coordinate_targets = [
                candidate
                for candidate in source_candidates
                if str(candidate.get("strategy") or "").strip().lower() == "coordinate"
            ]
            target_coordinate_targets = [
                candidate
                for candidate in target_candidates
                if str(candidate.get("strategy") or "").strip().lower() == "coordinate"
            ]
            source_selectors = _uia_selector_payloads_from_targets(
                source_uia_targets, action="drag_drop"
            )
            target_selectors = _uia_selector_payloads_from_targets(
                target_uia_targets, action="drag_drop"
            )
            source_coordinates = _coordinate_payloads_from_targets(
                source_coordinate_targets,
                action="drag_drop",
            )
            target_coordinates = _coordinate_payloads_from_targets(
                target_coordinate_targets,
                action="drag_drop",
            )
            has_multiple_uia = len(source_selectors) > 1 or len(target_selectors) > 1
            has_coordinate_pair = bool(source_coordinates) and bool(target_coordinates)
            if not has_multiple_uia and not has_coordinate_pair:
                merged = {}
                merged.update(
                    _uia_selector_args(
                        source_selectors[0],
                        prefix="source_",
                    )
                )
                merged.update(
                    _uia_selector_args(
                        target_selectors[0],
                        prefix="target_",
                    )
                )
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
                    f"{source_args}{target_args}    timeout_seconds={timeout_seconds}"
                )
                return _apply_step_guards(
                    step_payload=step_payload,
                    lines=[
                        drag_keyword_line,
                        f"{indent}Wait For Seconds    {wait_seconds}",
                        f"{indent}Emit Annotation Metadata    ${{annotation}}",
                    ],
                    indent=indent,
                    path=path,
                    title=title,
                )

            candidates: list[dict[str, Any]] = []
            for source_selector in source_selectors:
                for target_selector in target_selectors:
                    candidates.append(
                        {
                            "strategy": "uia",
                            "source": dict(source_selector),
                            "target": dict(target_selector),
                        }
                    )
            if has_coordinate_pair:
                for source_coord in source_coordinates:
                    for target_coord in target_coordinates:
                        candidates.append(
                            {
                                "strategy": "coordinate",
                                "source": dict(source_coord),
                                "target": dict(target_coord),
                            }
                        )
            candidates_b64 = _encode_json_base64(candidates)
            drag_keyword_line = (
                f"{indent}${{annotation}}=    Drag Unity Target With Fallbacks"
                f"    candidates_b64={candidates_b64}    timeout_seconds={timeout_seconds}"
            )
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[
                    drag_keyword_line,
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ],
                indent=indent,
                path=path,
                title=title,
            )
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
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[
                    drag_keyword_line,
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ],
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError(
            "Unsupported drag_drop selector strategy pair. "
            f"source={source_strategy}, target={target_strategy}"
        )

    if action == "double_click":
        target = _require_selector(step_payload, "double_click")
        strategy = str(target.get("strategy") or "").strip().lower()
        if strategy == "coordinate":
            coordinate = target.get("coordinate")
            if not isinstance(coordinate, dict):
                raise ValueError("double_click coordinate target must include coordinate object.")
            x_ratio = coordinate.get("x_ratio")
            y_ratio = coordinate.get("y_ratio")
            if x_ratio is None or y_ratio is None:
                raise ValueError("double_click coordinate target requires x_ratio and y_ratio.")
            lines = [
                (
                    f"{indent}${{annotation}}=    Double Click Unity Relative"
                    f"    {x_ratio}    {y_ratio}"
                ),
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if strategy == "uia":
            timeout_seconds = _timeout_seconds_from_step(step_payload, default=10.0)
            candidates = _mixed_uia_coordinate_selector_payloads(target, action="double_click")
            if len(candidates) == 1 and str(candidates[0].get("strategy") or "") == "uia":
                args = {key: value for key, value in candidates[0].items() if key != "strategy"}
                args["timeout_seconds"] = timeout_seconds
                selector_args = _robot_named_args(
                    args,
                    (
                        "title",
                        "automation_id",
                        "class_name",
                        "control_type",
                        "index",
                        "timeout_seconds",
                    ),
                )
                if selector_args == "":
                    raise ValueError(
                        "double_click uia target requires selector fields "
                        "(title/automation_id/class_name/control_type)."
                    )
                lines = [
                    f"{indent}${{annotation}}=    Double Click Unity Element{selector_args}",
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            else:
                selectors_b64 = _encode_json_base64(candidates)
                lines = [
                    (
                        f"{indent}${{annotation}}=    Double Click Unity Element With Fallbacks"
                        f"    selectors_b64={selectors_b64}    timeout_seconds={timeout_seconds}"
                    ),
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError(f"Unsupported double_click target strategy: {strategy}")

    if action == "right_click":
        target = _require_selector(step_payload, "right_click")
        strategy = str(target.get("strategy") or "").strip().lower()
        if strategy == "coordinate":
            coordinate = target.get("coordinate")
            if not isinstance(coordinate, dict):
                raise ValueError("right_click coordinate target must include coordinate object.")
            x_ratio = coordinate.get("x_ratio")
            y_ratio = coordinate.get("y_ratio")
            if x_ratio is None or y_ratio is None:
                raise ValueError("right_click coordinate target requires x_ratio and y_ratio.")
            lines = [
                f"{indent}${{annotation}}=    Right Click Unity Relative    {x_ratio}    {y_ratio}",
                f"{indent}Wait For Seconds    {wait_seconds}",
                f"{indent}Emit Annotation Metadata    ${{annotation}}",
            ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if strategy == "uia":
            candidates = _mixed_uia_coordinate_selector_payloads(target, action="right_click")
            if len(candidates) == 1 and str(candidates[0].get("strategy") or "") == "uia":
                selector = {key: value for key, value in candidates[0].items() if key != "strategy"}
                selector_args = _robot_named_args(
                    selector,
                    ("title", "automation_id", "class_name", "control_type", "index"),
                )
                if selector_args == "":
                    raise ValueError(
                        "right_click uia target requires selector fields "
                        "(title/automation_id/class_name/control_type)."
                    )
                lines = [
                    (
                        f"{indent}${{annotation}}=    Click Unity Element{selector_args}"
                        "    button=right"
                    ),
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            else:
                selectors_b64 = _encode_json_base64(candidates)
                lines = [
                    (
                        f"{indent}${{annotation}}=    Click Unity Element With Fallbacks"
                        f"    selectors_b64={selectors_b64}    button=right"
                    ),
                    f"{indent}Wait For Seconds    {wait_seconds}",
                    f"{indent}Emit Annotation Metadata    ${{annotation}}",
                ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError(f"Unsupported right_click target strategy: {strategy}")

    if action == "press_keys":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("press_keys requires input payload.")
        if "shortcut" in input_payload:
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[f"{indent}Send Unity Shortcut    {input_payload['shortcut']}"],
                indent=indent,
                path=path,
                title=title,
            )
        if "keys" in input_payload:
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[f"{indent}Press Unity Keys    {input_payload['keys']}"],
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError("press_keys requires input.shortcut or input.keys.")

    if action == "open_menu":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("open_menu requires input payload.")
        menu_paths = _menu_path_candidates(input_payload)
        if not menu_paths:
            raise ValueError("open_menu requires input.menu_path.")
        command_line = (
            f"{indent}Open Unity Top Menu With Fallbacks    {'    '.join(menu_paths)}"
            if len(menu_paths) > 1
            else f"{indent}Open Unity Top Menu    {menu_paths[0]}"
        )
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[command_line],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "type_text":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("type_text requires input payload.")
        text = str(input_payload.get("text") or "")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Type Unity Text    {text}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "open_url":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("open_url requires input payload.")
        url = str(input_payload.get("url") or "").strip()
        if url == "":
            raise ValueError("open_url requires input.url.")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Open URL In Default Browser    {url}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "run_subflow":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("run_subflow requires input.path.")
        suite_path = str(input_payload.get("path") or "").strip()
        if suite_path == "":
            raise ValueError("run_subflow requires input.path.")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Run Robot Subflow    {suite_path}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "start_video":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("start_video requires input.path.")
        video_path = str(input_payload.get("path") or "").strip()
        if video_path == "":
            raise ValueError("start_video requires input.path.")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Start Desktop Video Capture    {video_path}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "stop_video":
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Stop Desktop Video Capture"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "assert":
        expect_payload = step_payload.get("expect")
        if isinstance(expect_payload, dict):
            condition = str(expect_payload.get("condition") or "").strip()
            if condition != "":
                message = str(expect_payload.get("message") or "").strip()
                assert_line = f"{indent}Should Be True    {condition}"
                if message != "":
                    assert_line = f"{assert_line}    {message}"
                return _apply_step_guards(
                    step_payload=step_payload,
                    lines=[assert_line],
                    indent=indent,
                    path=path,
                    title=title,
                )
        target = _require_selector(step_payload, "assert")
        strategy = str(target.get("strategy") or "").strip().lower()
        timeout_seconds = _timeout_seconds_from_step(step_payload, default=10.0)
        if strategy == "uia":
            uia_targets = _target_candidates_by_strategy(
                target,
                action="assert",
                allowed_strategies={"uia"},
            )
            selectors = _uia_selector_payloads_from_targets(uia_targets, action="assert")
            if len(selectors) == 1:
                args = dict(selectors[0])
                args["timeout_seconds"] = timeout_seconds
                selector_args = _robot_named_args(
                    args,
                    (
                        "title",
                        "automation_id",
                        "class_name",
                        "control_type",
                        "index",
                        "timeout_seconds",
                    ),
                )
                if selector_args == "":
                    raise ValueError(
                        "assert uia target requires selector fields "
                        "(title/automation_id/class_name/control_type)."
                    )
                lines = [f"{indent}Wait For Unity Element{selector_args}"]
            else:
                selectors_b64 = _encode_json_base64(selectors)
                lines = [
                    (
                        f"{indent}Wait For Unity Element With Fallbacks"
                        f"    selectors_b64={selectors_b64}    timeout_seconds={timeout_seconds}"
                    )
                ]
            return _apply_step_guards(
                step_payload=step_payload,
                lines=lines,
                indent=indent,
                path=path,
                title=title,
            )
        if strategy == "unity_hierarchy":
            hierarchy_timeout = _timeout_seconds_from_step(step_payload, default=4.0)
            hierarchy_targets = _target_candidates_by_strategy(
                target,
                action="assert",
                allowed_strategies={"unity_hierarchy"},
            )
            hierarchy_paths = _hierarchy_paths_from_targets(hierarchy_targets, action="assert")
            select_line = (
                f"{indent}Wait Until Keyword Succeeds    45 sec    1 sec    "
                "Select Unity Hierarchy Object With Fallbacks"
                f"    {hierarchy_timeout}    {'    '.join(hierarchy_paths)}"
                if len(hierarchy_paths) > 1
                else (
                    f"{indent}Wait Until Keyword Succeeds    45 sec    1 sec    "
                    "Select Unity Hierarchy Object"
                    f"    hierarchy_path={hierarchy_paths[0]}"
                    f"    timeout_seconds={hierarchy_timeout}"
                )
            )
            return _apply_step_guards(
                step_payload=step_payload,
                lines=[select_line],
                indent=indent,
                path=path,
                title=title,
            )
        raise ValueError("assert currently requires expect.condition or target selector.")

    if action == "screenshot":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            input_payload = {}
        image_path = str(input_payload.get("path") or "")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Capture Unity Screenshot    {image_path}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "wait_for":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("wait_for currently requires input.seconds.")
        if "seconds" not in input_payload:
            raise ValueError("wait_for currently requires input.seconds.")
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Wait For Seconds    {input_payload['seconds']}"],
            indent=indent,
            path=path,
            title=title,
        )

    if action == "emit_annotation":
        input_payload = step_payload.get("input")
        if not isinstance(input_payload, dict):
            raise ValueError("emit_annotation requires input payload.")
        annotation = input_payload.get("annotation")
        if annotation is None:
            metadata = input_payload.get("metadata")
            if metadata is None:
                raise ValueError("emit_annotation requires input.annotation or input.metadata.")
            serialized = json.dumps(
                metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        else:
            serialized = json.dumps(
                {"annotation": annotation},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        return _apply_step_guards(
            step_payload=step_payload,
            lines=[f"{indent}Emit DOCMETA    {serialized}"],
            indent=indent,
            path=path,
            title=title,
        )

    raise ValueError(f"Unsupported action for Robot export: {action}")


def _step_robot_lines(step: Step, indent: str = "    ", *, path: str = "step") -> list[str]:
    step_payload = step.to_dict()
    return _step_robot_lines_from_payload(step_payload, indent=indent, path=path)


def validate_step_exportability(step: Step, *, path: str = "step") -> None:
    _ = _step_robot_lines(step, path=path)


def _generate_robot_suite_from_resolved(
    resolved_scenario: Scenario,
    *,
    test_case_name: str,
) -> str:
    execution_mode = _scenario_execution_mode(resolved_scenario)
    subflow_timeout_seconds = _scenario_subflow_timeout_seconds(resolved_scenario)
    subflow_timeout_literal = f"{subflow_timeout_seconds}s"
    unity_project_path = _robot_safe_project_path(
        _scenario_project_path(resolved_scenario, execution_mode=execution_mode)
    )
    window_hint = _scenario_window_hint(resolved_scenario)
    lines = [
        "*** Settings ***",
        "Library    Collections",
        "Library    Process",
        "Library    OperatingSystem",
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
    for index, step in enumerate(resolved_scenario.steps):
        lines.append(f"        # {step.title} ({step.kind})")
        lines.extend(
            _step_robot_lines_from_payload(
                step.to_dict(),
                indent="        ",
                path=f"steps[{index}]",
            )
        )
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
            "Open Unity Top Menu With Fallbacks",
            "    [Arguments]    @{menu_paths}",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${menu_path}    IN    @{menu_paths}",
            (
                "        ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Open Unity Top Menu    ${menu_path}"
            ),
            "        IF    '${status}' == 'PASS'",
            "            RETURN",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            "    Fail    Failed to open Unity menu using candidates: ${last_error}",
            "",
            "Select Unity Hierarchy Object With Fallbacks",
            "    [Arguments]    ${timeout_seconds}=4.0    @{hierarchy_paths}",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${path}    IN    @{hierarchy_paths}",
            (
                "        ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Select Unity Hierarchy Object"
                "    hierarchy_path=${path}    timeout_seconds=${timeout_seconds}"
            ),
            "        IF    '${status}' == 'PASS'",
            "            RETURN    ${result}",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            "    Fail    Failed to select Unity hierarchy object using candidates: ${last_error}",
            "",
            "Click Unity Element With Fallbacks",
            "    [Arguments]    ${selectors_b64}    ${button}=left",
            (
                "    ${selectors_json}=    Evaluate"
                "    __import__('base64').b64decode($selectors_b64).decode('utf-8')"
            ),
            "    ${selectors}=    Evaluate    __import__('json').loads($selectors_json)",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${selector}    IN    @{selectors}",
            (
                "        ${strategy}=    Evaluate"
                "    str($selector.get('strategy', '')).strip().lower()"
                " if isinstance($selector, dict) else ''"
            ),
            "        IF    '${strategy}' == 'coordinate'",
            "            ${x_ratio}=    Evaluate    $selector.get('x_ratio')",
            "            ${y_ratio}=    Evaluate    $selector.get('y_ratio')",
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Click Unity Relative    ${x_ratio}    ${y_ratio}    button=${button}"
            ),
            "        ELSE",
            (
                "            ${selector_args}=    Evaluate"
                "    {k: v for k, v in $selector.items() if k != 'strategy'}"
            ),
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Click Unity Element    &{selector_args}    button=${button}"
            ),
            "        END",
            "        IF    '${status}' == 'PASS'",
            "            RETURN    ${result}",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            "    Fail    Failed to click Unity element using selector fallbacks: ${last_error}",
            "",
            "Drag Unity Target With Fallbacks",
            "    [Arguments]    ${candidates_b64}    ${timeout_seconds}=10.0",
            (
                "    ${candidates_json}=    Evaluate"
                "    __import__('base64').b64decode($candidates_b64).decode('utf-8')"
            ),
            "    ${candidates}=    Evaluate    __import__('json').loads($candidates_json)",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${candidate}    IN    @{candidates}",
            (
                "        ${strategy}=    Evaluate"
                "    str($candidate.get('strategy', '')).strip().lower()"
                " if isinstance($candidate, dict) else ''"
            ),
            (
                "        ${source}=    Evaluate"
                "    $candidate.get('source', {}) if isinstance($candidate, dict) else {}"
            ),
            (
                "        ${target}=    Evaluate"
                "    $candidate.get('target', {}) if isinstance($candidate, dict) else {}"
            ),
            "        IF    '${strategy}' == 'coordinate'",
            "            ${from_x_ratio}=    Evaluate    $source.get('x_ratio')",
            "            ${from_y_ratio}=    Evaluate    $source.get('y_ratio')",
            "            ${to_x_ratio}=    Evaluate    $target.get('x_ratio')",
            "            ${to_y_ratio}=    Evaluate    $target.get('y_ratio')",
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Drag Unity Relative"
                "    ${from_x_ratio}    ${from_y_ratio}    ${to_x_ratio}    ${to_y_ratio}"
            ),
            "        ELSE",
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Drag Unity Element By Selectors"
                "    ${source}    ${target}    timeout_seconds=${timeout_seconds}"
            ),
            "        END",
            "        IF    '${status}' == 'PASS'",
            "            RETURN    ${result}",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            "    Fail    Failed to drag Unity element using candidates: ${last_error}",
            "",
            "Drag Unity Element By Selectors",
            "    [Arguments]    ${source}    ${target}    ${timeout_seconds}=10.0",
            "    ${window}=    Get Unity Window Rect",
            (
                "    ${source_rect}=    Get Unity Element Rect    &{source}"
                "    timeout_seconds=${timeout_seconds}"
            ),
            (
                "    ${target_rect}=    Get Unity Element Rect    &{target}"
                "    timeout_seconds=${timeout_seconds}"
            ),
            (
                "    ${from_x_ratio}=    Evaluate"
                "    max(0.0, min(1.0,"
                " (float($source_rect['left']) + (float($source_rect['width']) / 2.0)"
                " - float($window['left'])) / max(1.0, float($window['width']))))"
            ),
            (
                "    ${from_y_ratio}=    Evaluate"
                "    max(0.0, min(1.0,"
                " (float($source_rect['top']) + (float($source_rect['height']) / 2.0)"
                " - float($window['top'])) / max(1.0, float($window['height']))))"
            ),
            (
                "    ${to_x_ratio}=    Evaluate"
                "    max(0.0, min(1.0,"
                " (float($target_rect['left']) + (float($target_rect['width']) / 2.0)"
                " - float($window['left'])) / max(1.0, float($window['width']))))"
            ),
            (
                "    ${to_y_ratio}=    Evaluate"
                "    max(0.0, min(1.0,"
                " (float($target_rect['top']) + (float($target_rect['height']) / 2.0)"
                " - float($window['top'])) / max(1.0, float($window['height']))))"
            ),
            (
                "    ${annotation}=    Drag Unity Relative"
                "    ${from_x_ratio}    ${from_y_ratio}    ${to_x_ratio}    ${to_y_ratio}"
            ),
            "    RETURN    ${annotation}",
            "",
            "Double Click Unity Element With Fallbacks",
            "    [Arguments]    ${selectors_b64}    ${timeout_seconds}=10.0",
            (
                "    ${selectors_json}=    Evaluate"
                "    __import__('base64').b64decode($selectors_b64).decode('utf-8')"
            ),
            "    ${selectors}=    Evaluate    __import__('json').loads($selectors_json)",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${selector}    IN    @{selectors}",
            (
                "        ${strategy}=    Evaluate"
                "    str($selector.get('strategy', '')).strip().lower()"
                " if isinstance($selector, dict) else ''"
            ),
            "        IF    '${strategy}' == 'coordinate'",
            "            ${x_ratio}=    Evaluate    $selector.get('x_ratio')",
            "            ${y_ratio}=    Evaluate    $selector.get('y_ratio')",
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Double Click Unity Relative    ${x_ratio}    ${y_ratio}"
            ),
            "        ELSE",
            (
                "            ${selector_args}=    Evaluate"
                "    {k: v for k, v in $selector.items() if k != 'strategy'}"
            ),
            (
                "            ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Double Click Unity Element"
                "    &{selector_args}    timeout_seconds=${timeout_seconds}"
            ),
            "        END",
            "        IF    '${status}' == 'PASS'",
            "            RETURN    ${result}",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            (
                "    Fail    Failed to double click Unity element using selector fallbacks:"
                " ${last_error}"
            ),
            "",
            "Wait For Unity Element With Fallbacks",
            "    [Arguments]    ${selectors_b64}    ${timeout_seconds}=10.0",
            (
                "    ${selectors_json}=    Evaluate"
                "    __import__('base64').b64decode($selectors_b64).decode('utf-8')"
            ),
            "    ${selectors}=    Evaluate    __import__('json').loads($selectors_json)",
            "    ${last_error}=    Set Variable    ${EMPTY}",
            "    FOR    ${selector}    IN    @{selectors}",
            (
                "        ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Wait For Unity Element    &{selector}"
                "    timeout_seconds=${timeout_seconds}"
            ),
            "        IF    '${status}' == 'PASS'",
            "            RETURN    ${TRUE}",
            "        END",
            "        ${last_error}=    Set Variable    ${result}",
            "    END",
            "    Fail    Failed to wait for Unity element using selector fallbacks: ${last_error}",
            "",
            "Double Click Unity Element",
            (
                "    [Arguments]    ${title}=${None}    ${automation_id}=${None}"
                "    ${class_name}=${None}    ${control_type}=${None}"
                "    ${index}=${None}    ${timeout_seconds}=10.0"
            ),
            (
                "    ${rect}=    Get Unity Element Rect    title=${title}"
                "    automation_id=${automation_id}    class_name=${class_name}"
                "    control_type=${control_type}    index=${index}"
                "    timeout_seconds=${timeout_seconds}"
            ),
            "    ${window}=    Get Unity Window Rect",
            (
                "    ${x_ratio}=    Evaluate"
                "    (float($rect['left']) + (float($rect['width']) / 2.0)"
                " - float($window['left'])) / max(1.0, float($window['width']))"
            ),
            (
                "    ${y_ratio}=    Evaluate"
                "    (float($rect['top']) + (float($rect['height']) / 2.0)"
                " - float($window['top'])) / max(1.0, float($window['height']))"
            ),
            "    ${annotation}=    Double Click Unity Relative    ${x_ratio}    ${y_ratio}",
            "    RETURN    ${annotation}",
            "",
            "Open URL In Default Browser",
            "    [Arguments]    ${url}",
            "    ${opened}=    Evaluate    __import__('webbrowser').open(str($url), new=2)",
            "    Should Be True    ${opened}",
            "",
            "Run Robot Subflow",
            "    [Arguments]    ${suite_path}",
            "    ${resolved}=    Resolve Robot Subflow Path    ${suite_path}",
            (
                "    ${subflow_name}=    Evaluate    __import__('os').path.splitext("
                "__import__('os').path.basename($resolved))[0]"
            ),
            "    ${subflow_output}=    Join Path    ${OUTPUT DIR}    subflows    ${subflow_name}",
            "    Create Directory    ${subflow_output}",
            "    ${py}=    Evaluate    __import__('sys').executable",
            (
                "    ${status}    ${result}=    Run Keyword And Ignore Error    Run Process"
                "    ${py}    -m    robot    --outputdir"
                "    ${subflow_output}    --variable    OUTPUT_DIR:${OUTPUT DIR}"
                "    ${resolved}    stdout=${subflow_output}${/}stdout.txt"
                "    stderr=${subflow_output}${/}stderr.txt"
                f"    timeout={subflow_timeout_literal}    on_timeout=terminate"
            ),
            "    IF    '${status}' == 'FAIL'",
            (
                f"        Fail    Subflow timed out after {subflow_timeout_literal}. "
                "stdout=${subflow_output}${/}stdout.txt "
                "stderr=${subflow_output}${/}stderr.txt"
            ),
            "    END",
            "    IF    ${result.rc} != 0",
            (
                "        Fail    Subflow failed rc=${result.rc}. "
                "stdout=${subflow_output}${/}stdout.txt "
                "stderr=${subflow_output}${/}stderr.txt"
            ),
            "    END",
            "",
            "Start Robot Subflow Process",
            "    [Arguments]    ${suite_path}    ${alias}",
            "    ${resolved}=    Resolve Robot Subflow Path    ${suite_path}",
            "    ${subflow_output}=    Join Path    ${OUTPUT DIR}    subflows    ${alias}",
            "    Create Directory    ${subflow_output}",
            "    ${py}=    Evaluate    __import__('sys').executable",
            (
                "    Start Process    ${py}    -m    robot    --outputdir"
                "    ${subflow_output}    --variable    OUTPUT_DIR:${OUTPUT DIR}"
                "    ${resolved}    stdout=${subflow_output}${/}stdout.txt"
                "    stderr=${subflow_output}${/}stderr.txt    alias=${alias}"
            ),
            "    RETURN    ${alias}",
            "",
            "Wait Robot Subflow Processes",
            "    [Arguments]    @{aliases}",
            "    FOR    ${alias}    IN    @{aliases}",
            "        ${subflow_output}=    Join Path    ${OUTPUT DIR}    subflows    ${alias}",
            (
                "        ${status}    ${result}=    Run Keyword And Ignore Error"
                f"    Wait For Process    ${{alias}}    timeout={subflow_timeout_literal}"
            ),
            "        IF    '${status}' == 'FAIL'",
            (
                "            Fail    Subflow process timed out alias=${alias}"
                f" after {subflow_timeout_literal}. "
                "stdout=${subflow_output}${/}stdout.txt "
                "stderr=${subflow_output}${/}stderr.txt"
            ),
            "        END",
            "        IF    ${result.rc} != 0",
            (
                "            Fail    Subflow process failed alias=${alias} rc=${result.rc}. "
                "stdout=${subflow_output}${/}stdout.txt "
                "stderr=${subflow_output}${/}stderr.txt"
            ),
            "        END",
            "    END",
            "",
            "Resolve Robot Subflow Path",
            "    [Arguments]    ${suite_path}",
            "    ${normalized}=    Evaluate    str($suite_path).strip()",
            "    IF    '${normalized}' == ''",
            "        Fail    run_subflow requires input.path.",
            "    END",
            "    ${is_abs}=    Evaluate    __import__('os').path.isabs($normalized)",
            "    IF    ${is_abs}",
            "        ${resolved}=    Normalize Path    ${normalized}",
            "    ELSE",
            "        ${resolved}=    Normalize Path    ${CURDIR}${/}${normalized}",
            "    END",
            "    File Should Exist    ${resolved}",
            "    ${is_robot}=    Evaluate    str($resolved).lower().endswith('.robot')",
            "    Should Be True    ${is_robot}    subflow suite_path must point to a .robot file.",
            "    RETURN    ${resolved}",
            "",
            "Start Desktop Video Capture",
            "    [Arguments]    ${video_path}",
            "    ${normalized}=    Evaluate    str($video_path).strip()",
            "    IF    '${normalized}' == ''",
            "        Fail    start_video requires input.path.",
            "    END",
            "    ${ffmpeg}=    Evaluate    __import__('shutil').which('ffmpeg')",
            "    Should Not Be Empty    ${ffmpeg}    ffmpeg is required for start_video.",
            "    ${is_abs}=    Evaluate    __import__('os').path.isabs($normalized)",
            "    IF    ${is_abs}",
            "        ${resolved}=    Normalize Path    ${normalized}",
            "    ELSE",
            "        ${resolved}=    Normalize Path    ${OUTPUT DIR}${/}${normalized}",
            "    END",
            "    ${video_dir}=    Evaluate    __import__('os').path.dirname($resolved)",
            "    IF    '${video_dir}' != ''",
            "        Create Directory    ${video_dir}",
            "    END",
            (
                "    Start Process    ${ffmpeg}    -y    -f    gdigrab"
                "    -framerate    30    -i    desktop    -pix_fmt"
                "    yuv420p    ${resolved}    alias=studio_video_capture"
            ),
            "",
            "Stop Desktop Video Capture",
            (
                "    ${status}    ${result}=    Run Keyword And Ignore Error"
                "    Terminate Process    studio_video_capture    kill=True"
            ),
            "    IF    '${status}' == 'FAIL'",
            "        Fail    No active video capture process to stop.",
            "    END",
            "",
        ]
    )
    return "\n".join(lines)


def validate_exportable_scenario(
    scenario: Scenario,
    *,
    active_profile: str | None = None,
) -> Scenario:
    resolved_scenario = resolve_scenario_variables(scenario, active_profile=active_profile)
    _ = _generate_robot_suite_from_resolved(
        resolved_scenario,
        test_case_name=resolved_scenario.name,
    )
    return resolved_scenario


def generate_robot_suite(
    scenario: Scenario,
    suite_name: str | None = None,
    *,
    active_profile: str | None = None,
) -> str:
    resolved_scenario = validate_exportable_scenario(
        scenario,
        active_profile=active_profile,
    )
    test_case_name = suite_name or resolved_scenario.name
    return _generate_robot_suite_from_resolved(
        resolved_scenario,
        test_case_name=test_case_name,
    )


def export_all(
    scenario: Scenario,
    output_dir: Path,
    suite_name: str | None = None,
    *,
    active_profile: str | None = None,
) -> ExportResult:
    resolved_scenario = validate_exportable_scenario(
        scenario,
        active_profile=active_profile,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = suite_name or _safe_suite_name(resolved_scenario.name)
    robot_path = output_dir / f"{safe_name}.robot"
    json_path = output_dir / f"{safe_name}.scenario.json"

    robot_path.write_text(
        _generate_robot_suite_from_resolved(
            resolved_scenario,
            test_case_name=safe_name,
        ),
        encoding="utf-8",
    )
    resolved_scenario.save_json(json_path)

    return ExportResult(robot_path=robot_path, json_path=json_path)
