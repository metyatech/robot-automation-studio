"""Core data models for scenario recording/editing/export."""

from __future__ import annotations

import json
import uuid
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

UNITY_EXECUTION_MODE_KEY = "unity_execution_mode"
UNITY_PROJECT_PATH_KEY = "unity_project_path"
TARGET_WINDOW_HINT_KEY = "target_window_hint"
SCHEMA_VERSION = "2.0.0"
VALID_UNITY_EXECUTION_MODES = {"attach", "launch"}
VALID_TARGETS = {"unity", "web", "desktop", "hybrid"}
STEP_KINDS = {"action", "control", "group"}


def _new_step_id() -> str:
    return uuid.uuid4().hex[:10]


def _new_scenario_id() -> str:
    return f"scenario-{uuid.uuid4().hex[:8]}"


def normalize_unity_execution_mode(value: Any) -> str:
    normalized = str(value or "attach").strip().lower()
    if normalized in VALID_UNITY_EXECUTION_MODES:
        return normalized
    return "attach"


def _deepcopy_if_present(source: dict[str, Any], key: str) -> Any:
    if key not in source:
        return None
    return deepcopy(source[key])


def _selector_from_flat(prefix: str, params: dict[str, Any]) -> dict[str, Any] | None:
    selector: dict[str, Any] = {}
    for key in ("title", "automation_id", "class_name", "control_type", "index"):
        value = params.get(f"{prefix}{key}")
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        selector[key] = value
    if selector:
        return {"strategy": "uia", "uia": selector}
    return None


def _coordinate_selector_from_flat(
    x_key: str,
    y_key: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    x_value = params.get(x_key)
    y_value = params.get(y_key)
    if x_value is None or y_value is None:
        return None
    coordinate: dict[str, Any] = {"x_ratio": x_value, "y_ratio": y_value}
    anchor = params.get("anchor_window_hint")
    if isinstance(anchor, str) and anchor.strip() != "":
        coordinate["anchor_window_hint"] = anchor
    return {"strategy": "coordinate", "coordinate": coordinate}


def _with_non_empty_string(
    target: dict[str, Any],
    key: str,
    value: Any,
) -> None:
    text = str(value or "").strip()
    if text != "":
        target[key] = text


@dataclass(slots=True)
class Step:
    action: str = "click"
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_step_id)
    title: str = ""
    kind: str = "action"
    control: str = ""
    description: str = ""
    disabled: bool = False
    condition: str = ""
    continue_on_error: bool = False
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        normalized_kind = str(self.kind or "action").strip().lower()
        if normalized_kind not in STEP_KINDS:
            normalized_kind = "action"
        self.kind = normalized_kind
        if not self.title:
            if self.kind == "action":
                self.title = self.action or "action"
            elif self.kind == "control":
                self.title = self.control or "control"
            else:
                self.title = "group"

    @staticmethod
    def _canonical_action(action: str) -> str:
        normalized = str(action or "").strip().lower()
        aliases = {
            "drag": "drag_drop",
            "type": "type_text",
            "shortcut": "press_keys",
            "keys": "press_keys",
            "menu": "open_menu",
            "wait": "wait_for",
        }
        return aliases.get(normalized, normalized)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        kind = str(data.get("kind") or "action").strip().lower()
        if kind not in STEP_KINDS:
            kind = "action"

        params: dict[str, Any] = {}
        if kind == "action":
            for key in ("target", "input", "expect", "timing", "retry", "capture"):
                if key in data:
                    params[key] = deepcopy(data[key])
            action = str(data.get("action") or "click").strip().lower()

            target = data.get("target")
            if isinstance(target, dict):
                strategy = str(target.get("strategy") or "").strip().lower()
                if strategy == "unity_hierarchy":
                    unity_hierarchy = target.get("unity_hierarchy")
                    if isinstance(unity_hierarchy, dict):
                        path = str(unity_hierarchy.get("path") or "").strip()
                        if path:
                            params["hierarchy_path"] = path
                if strategy == "uia":
                    uia = target.get("uia")
                    if isinstance(uia, dict):
                        for key in (
                            "title",
                            "automation_id",
                            "class_name",
                            "control_type",
                            "index",
                        ):
                            value = uia.get(key)
                            if value is None:
                                continue
                            if isinstance(value, str) and value.strip() == "":
                                continue
                            params[key] = value
                if strategy == "coordinate":
                    coordinate = target.get("coordinate")
                    if isinstance(coordinate, dict):
                        if "x_ratio" in coordinate:
                            params["x_ratio"] = coordinate["x_ratio"]
                        if "y_ratio" in coordinate:
                            params["y_ratio"] = coordinate["y_ratio"]
                        if "anchor_window_hint" in coordinate:
                            params["anchor_window_hint"] = coordinate["anchor_window_hint"]

            if action == "drag_drop":
                input_payload = data.get("input")
                if isinstance(input_payload, dict):
                    source = input_payload.get("source")
                    if isinstance(source, dict):
                        source_strategy = str(source.get("strategy") or "").strip().lower()
                        if source_strategy == "uia":
                            source_uia = source.get("uia")
                            if isinstance(source_uia, dict):
                                for key in (
                                    "title",
                                    "automation_id",
                                    "class_name",
                                    "control_type",
                                    "index",
                                ):
                                    value = source_uia.get(key)
                                    if value is None:
                                        continue
                                    if isinstance(value, str) and value.strip() == "":
                                        continue
                                    params[f"source_{key}"] = value
                        if source_strategy == "coordinate":
                            source_coordinate = source.get("coordinate")
                            if isinstance(source_coordinate, dict):
                                if "x_ratio" in source_coordinate:
                                    params["from_x_ratio"] = source_coordinate["x_ratio"]
                                if "y_ratio" in source_coordinate:
                                    params["from_y_ratio"] = source_coordinate["y_ratio"]
                    if "shortcut" in input_payload:
                        params["shortcut"] = input_payload["shortcut"]
                    if "keys" in input_payload:
                        params["keys"] = input_payload["keys"]
                    if "text" in input_payload:
                        params["text"] = input_payload["text"]
                    if "menu_path" in input_payload:
                        params["menu_path"] = input_payload["menu_path"]
                    if "path" in input_payload:
                        params["path"] = input_payload["path"]
                    if "seconds" in input_payload:
                        params["seconds"] = input_payload["seconds"]

                target_payload = data.get("target")
                if isinstance(target_payload, dict):
                    target_strategy = str(target_payload.get("strategy") or "").strip().lower()
                    if target_strategy == "uia":
                        target_uia = target_payload.get("uia")
                        if isinstance(target_uia, dict):
                            for key in (
                                "title",
                                "automation_id",
                                "class_name",
                                "control_type",
                                "index",
                            ):
                                value = target_uia.get(key)
                                if value is None:
                                    continue
                                if isinstance(value, str) and value.strip() == "":
                                    continue
                                params[f"target_{key}"] = value
                    if target_strategy == "coordinate":
                        target_coordinate = target_payload.get("coordinate")
                        if isinstance(target_coordinate, dict):
                            if "x_ratio" in target_coordinate:
                                params["to_x_ratio"] = target_coordinate["x_ratio"]
                            if "y_ratio" in target_coordinate:
                                params["to_y_ratio"] = target_coordinate["y_ratio"]

            timing = data.get("timing")
            if isinstance(timing, dict) and "stability_ms" in timing:
                with suppress(TypeError, ValueError):
                    params["wait_seconds"] = float(timing["stability_ms"]) / 1000.0

            return cls(
                id=str(data.get("id") or _new_step_id()),
                action=action,
                title=str(data.get("title") or action or "action"),
                kind=kind,
                control="",
                description=str(data.get("description") or ""),
                disabled=bool(data.get("disabled", False)),
                condition=str(data.get("condition") or ""),
                continue_on_error=bool(data.get("continue_on_error", False)),
                annotations=list(data.get("annotations") or []),
                params=params,
            )

        if kind == "control":
            for key in (
                "expression",
                "items_expression",
                "item_variable",
                "max_iterations",
                "branches",
                "steps",
                "catch_steps",
                "finally_steps",
            ):
                if key in data:
                    params[key] = deepcopy(data[key])
            return cls(
                id=str(data.get("id") or _new_step_id()),
                action="",
                control=str(data.get("control") or ""),
                title=str(data.get("title") or data.get("control") or "control"),
                kind=kind,
                description=str(data.get("description") or ""),
                disabled=bool(data.get("disabled", False)),
                condition=str(data.get("condition") or ""),
                continue_on_error=bool(data.get("continue_on_error", False)),
                annotations=list(data.get("annotations") or []),
                params=params,
            )

        # kind == "group"
        params["steps"] = deepcopy(data.get("steps") or [])
        return cls(
            id=str(data.get("id") or _new_step_id()),
            action="",
            control="",
            title=str(data.get("title") or "group"),
            kind="group",
            description=str(data.get("description") or ""),
            disabled=bool(data.get("disabled", False)),
            condition=str(data.get("condition") or ""),
            continue_on_error=bool(data.get("continue_on_error", False)),
            annotations=list(data.get("annotations") or []),
            params=params,
        )

    def _base_dict(self) -> dict[str, Any]:
        output: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
        }
        _with_non_empty_string(output, "description", self.description)
        if self.disabled:
            output["disabled"] = True
        _with_non_empty_string(output, "condition", self.condition)
        if self.continue_on_error:
            output["continue_on_error"] = True
        if self.annotations:
            output["annotations"] = deepcopy(self.annotations)
        return output

    def _legacy_action_payload(self, canonical_action: str) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        params = self.params

        selector_from_params = _selector_from_flat("", params)
        target_selector = _selector_from_flat("target_", params)
        source_selector = _selector_from_flat("source_", params)
        direct_target = _deepcopy_if_present(params, "target")
        direct_input = _deepcopy_if_present(params, "input")
        direct_expect = _deepcopy_if_present(params, "expect")
        direct_timing = _deepcopy_if_present(params, "timing")
        direct_retry = _deepcopy_if_present(params, "retry")
        direct_capture = _deepcopy_if_present(params, "capture")

        if isinstance(direct_target, dict):
            payload["target"] = direct_target
        if isinstance(direct_input, dict):
            payload["input"] = direct_input
        if isinstance(direct_expect, dict):
            payload["expect"] = direct_expect
        if isinstance(direct_timing, dict):
            payload["timing"] = direct_timing
        if isinstance(direct_retry, dict):
            payload["retry"] = direct_retry
        if isinstance(direct_capture, dict):
            payload["capture"] = direct_capture

        if canonical_action == "click":
            hierarchy_path = str(params.get("hierarchy_path") or "").strip()
            if hierarchy_path and "target" not in payload:
                payload["target"] = {
                    "strategy": "unity_hierarchy",
                    "unity_hierarchy": {"path": hierarchy_path, "match_mode": "exact"},
                }
            if "target" not in payload and selector_from_params is not None:
                payload["target"] = selector_from_params
            if "target" not in payload:
                coordinate_selector = _coordinate_selector_from_flat("x_ratio", "y_ratio", params)
                if coordinate_selector is not None:
                    payload["target"] = coordinate_selector

        if canonical_action == "drag_drop":
            if "target" not in payload:
                if target_selector is not None:
                    payload["target"] = target_selector
                else:
                    coordinate_target = _coordinate_selector_from_flat(
                        "to_x_ratio", "to_y_ratio", params
                    )
                    if coordinate_target is not None:
                        payload["target"] = coordinate_target
            input_payload = dict(payload.get("input") or {})
            if source_selector is not None and "source" not in input_payload:
                input_payload["source"] = source_selector
            if "source" not in input_payload:
                coordinate_source = _coordinate_selector_from_flat(
                    "from_x_ratio",
                    "from_y_ratio",
                    params,
                )
                if coordinate_source is not None:
                    input_payload["source"] = coordinate_source
            if input_payload:
                payload["input"] = input_payload

        if canonical_action == "press_keys":
            input_payload = dict(payload.get("input") or {})
            if "shortcut" not in input_payload and "shortcut" in params:
                input_payload["shortcut"] = params["shortcut"]
            if "keys" not in input_payload and "keys" in params:
                input_payload["keys"] = params["keys"]
            if input_payload:
                payload["input"] = input_payload

        if canonical_action == "open_menu":
            input_payload = dict(payload.get("input") or {})
            if "menu_path" not in input_payload and "menu_path" in params:
                input_payload["menu_path"] = params["menu_path"]
            if input_payload:
                payload["input"] = input_payload

        if canonical_action == "type_text":
            input_payload = dict(payload.get("input") or {})
            if "text" not in input_payload and "text" in params:
                input_payload["text"] = params["text"]
            if input_payload:
                payload["input"] = input_payload

        if canonical_action == "screenshot":
            input_payload = dict(payload.get("input") or {})
            if "path" not in input_payload and "path" in params:
                input_payload["path"] = params["path"]
            if input_payload:
                payload["input"] = input_payload

        if canonical_action == "wait_for":
            input_payload = dict(payload.get("input") or {})
            if "seconds" not in input_payload and "seconds" in params:
                input_payload["seconds"] = params["seconds"]
            if input_payload:
                payload["input"] = input_payload

        if "timing" not in payload and "wait_seconds" in params:
            try:
                wait_seconds = float(params.get("wait_seconds", 0.0))
                payload["timing"] = {"stability_ms": int(wait_seconds * 1000)}
            except (TypeError, ValueError):
                pass

        return payload

    def to_dict(self) -> dict[str, Any]:
        output = self._base_dict()
        if self.kind == "action":
            canonical_action = self._canonical_action(self.action)
            output["action"] = canonical_action or "click"
            output.update(self._legacy_action_payload(canonical_action))
            return output
        if self.kind == "control":
            output["control"] = str(self.control or self.params.get("control") or "")
            for key in (
                "expression",
                "items_expression",
                "item_variable",
                "max_iterations",
                "branches",
                "steps",
                "catch_steps",
                "finally_steps",
            ):
                value = self.params.get(key)
                if value in (None, "", [], {}):
                    continue
                output[key] = deepcopy(value)
            return output
        # kind == "group"
        steps = self.params.get("steps")
        output["steps"] = deepcopy(steps if isinstance(steps, list) else [])
        return output


def _resolve_variable_default(variables: list[dict[str, Any]], variable_id: str) -> str:
    for variable in variables:
        if str(variable.get("id") or "").strip() != variable_id:
            continue
        default = variable.get("default")
        return str(default if default is not None else "").strip()
    return ""


def _upsert_variable_default(
    variables: list[dict[str, Any]],
    variable_id: str,
    value: str,
    variable_type: str,
) -> list[dict[str, Any]]:
    normalized_id = str(variable_id).strip()
    normalized_type = str(variable_type).strip() or "string"
    normalized_value = str(value).strip()
    updated = [deepcopy(item) for item in variables if isinstance(item, dict)]
    for variable in updated:
        if str(variable.get("id") or "").strip() != normalized_id:
            continue
        variable["type"] = normalized_type
        variable["default"] = normalized_value
        return updated
    updated.append(
        {
            "id": normalized_id,
            "type": normalized_type,
            "required": False,
            "default": normalized_value,
        }
    )
    return updated


@dataclass(slots=True)
class Scenario:
    name: str
    scenario_id: str = field(default_factory=_new_scenario_id)
    target: str = "unity"
    steps: list[Step] = field(default_factory=list)
    target_window_hint: str = "Unity"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)
    variables: list[dict[str, Any]] = field(default_factory=list)
    profiles: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    recording: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def _normalized_target(self) -> str:
        normalized = str(self.target or "unity").strip().lower()
        if normalized in VALID_TARGETS:
            return normalized
        return "unity"

    def _normalized_metadata(self) -> dict[str, Any]:
        metadata = deepcopy(self.metadata)
        metadata[TARGET_WINDOW_HINT_KEY] = self.target_window_hint
        return metadata

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "target": self._normalized_target(),
            "created_at": self.created_at,
            "metadata": self._normalized_metadata(),
            "variables": deepcopy(self.variables),
            "steps": [step.to_dict() for step in self.steps],
        }
        _with_non_empty_string(payload, "description", self.description)
        _with_non_empty_string(payload, "updated_at", self.updated_at)
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.profiles:
            payload["profiles"] = deepcopy(self.profiles)
        if self.execution:
            payload["execution"] = deepcopy(self.execution)
        if self.recording:
            payload["recording"] = deepcopy(self.recording)
        if self.outputs:
            payload["outputs"] = deepcopy(self.outputs)
        if self.extensions:
            payload["extensions"] = deepcopy(self.extensions)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        schema_version = str(data.get("schema_version") or "")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {schema_version}")

        metadata = dict(data.get("metadata") or {})
        execution = dict(data.get("execution") or {})
        variables = [
            dict(item) for item in list(data.get("variables") or []) if isinstance(item, dict)
        ]
        target_window_hint = str(metadata.get(TARGET_WINDOW_HINT_KEY) or "").strip()
        if target_window_hint == "":
            attach = execution.get("attach")
            if isinstance(attach, dict):
                window_hint_var = str(attach.get("window_hint_var") or "").strip()
                if window_hint_var:
                    target_window_hint = _resolve_variable_default(variables, window_hint_var)
        if target_window_hint == "":
            target_window_hint = "Unity"

        return cls(
            scenario_id=str(data.get("scenario_id") or _new_scenario_id()),
            target=str(data.get("target") or "unity"),
            name=str(data.get("name") or "Scenario"),
            description=str(data.get("description") or ""),
            target_window_hint=target_window_hint,
            created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
            updated_at=str(data.get("updated_at") or ""),
            tags=[str(item) for item in list(data.get("tags") or [])],
            metadata=metadata,
            variables=variables,
            profiles=dict(data.get("profiles") or {}),
            execution=execution,
            recording=dict(data.get("recording") or {}),
            outputs=dict(data.get("outputs") or {}),
            extensions=dict(data.get("extensions") or {}),
            steps=[
                Step.from_dict(item)
                for item in list(data.get("steps") or [])
                if isinstance(item, dict)
            ],
        )

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> Scenario:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def sync_runtime_metadata(self, execution_mode: str, unity_project_path: str) -> None:
        normalized_mode = normalize_unity_execution_mode(execution_mode)
        self.metadata[UNITY_EXECUTION_MODE_KEY] = normalized_mode
        normalized_project_path = str(unity_project_path or "").strip()
        if normalized_project_path:
            self.metadata[UNITY_PROJECT_PATH_KEY] = normalized_project_path
        else:
            self.metadata.pop(UNITY_PROJECT_PATH_KEY, None)

        self.execution = dict(self.execution)
        self.execution["mode"] = normalized_mode
        attach_payload = dict(self.execution.get("attach") or {})
        launch_payload = dict(self.execution.get("launch") or {})
        attach_payload["window_hint_var"] = "unity_window_hint"
        launch_payload["unity_project_path_var"] = "unity_project_path"
        self.execution["attach"] = attach_payload
        self.execution["launch"] = launch_payload

        self.variables = _upsert_variable_default(
            self.variables,
            variable_id="unity_window_hint",
            value=self.target_window_hint,
            variable_type="string",
        )
        self.variables = _upsert_variable_default(
            self.variables,
            variable_id="unity_project_path",
            value=normalized_project_path,
            variable_type="path",
        )
