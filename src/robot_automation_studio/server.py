"""Headless FastAPI WebSocket sidecar server for robot-automation-studio.

Exposes the same business logic as the PySide6 StudioApp without any Qt
dependency.  Communicates over a single WebSocket at ``/ws`` using a
JSON-RPC-style protocol.

Run standalone::

    python -m robot_automation_studio.server --port 0 --locale en
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import threading
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .editor import ScenarioEditor
from .exporter import export_all, validate_step_exportability
from .i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    Translator,
    detect_default_locale,
    normalize_locale,
)
from .models import (
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    normalize_unity_execution_mode,
)
from .preflight_validation import validate_scenario
from .profile_diff import build_profile_diff
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .settings_store import (
    StudioUiSettings,
    load_ui_settings,
    resolve_settings_path,
    save_ui_settings,
)
from .unity_bridge import UnityBridgeClient

logger = logging.getLogger("robot_automation_studio.server")

# ---------------------------------------------------------------------------
# Pure business logic helpers (no Qt dependency)
# ---------------------------------------------------------------------------


def build_help_tooltip_text(summary: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Return tooltip text for inline help near the cursor."""
    text = str(summary or "").strip()
    if text:
        return text
    return _t_static("app.help.tooltip.fallback", locale=locale)


def _t_static(key: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Translate a key without a Translator instance."""
    from .i18n import translate

    return translate(key, locale=locale)


def step_editor_visibility_for_kind(kind: str) -> dict[str, bool]:
    """Return Step-tab field visibility flags for a given step kind."""
    normalized = str(kind or "").strip().lower()
    if normalized == "control":
        return {
            "show_action": False,
            "show_control": True,
            "show_condition": True,
        }
    if normalized == "group":
        return {
            "show_action": False,
            "show_control": False,
            "show_condition": False,
        }
    return {
        "show_action": True,
        "show_control": False,
        "show_condition": False,
    }


def format_validation_issues_for_clipboard(
    issues: list[Any],
    *,
    no_issues_text: str = "No validation issues.",
) -> str:
    """Format a list of ValidationIssue objects as a clipboard-friendly string."""
    if not issues:
        return str(no_issues_text or "No validation issues.")
    lines: list[str] = []
    for index, issue in enumerate(issues, start=1):
        location = str(getattr(issue, "location", None) or "").strip() or "-"
        lines.append(f"{index}. [{issue.code}] {location}")
        lines.append(f"   {issue.message}")
    return "\n".join(lines)


def _parse_json_or_text(raw_text: str) -> Any:
    text = str(raw_text or "").strip()
    if text == "":
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _parse_variable_default_by_type(*, variable_type: str, default_text: str) -> Any:
    normalized_type = str(variable_type or "").strip().lower()
    raw = str(default_text or "")
    stripped = raw.strip()

    if normalized_type in {"string", "str", "path", ""}:
        return raw
    if normalized_type in {"int", "integer"}:
        if stripped == "":
            return ""
        try:
            return int(stripped)
        except ValueError as error:
            raise ValueError(f"Invalid int value: {raw}") from error
    if normalized_type in {"float", "double", "number"}:
        if stripped == "":
            return ""
        try:
            return float(stripped)
        except ValueError as error:
            raise ValueError(f"Invalid float value: {raw}") from error
    if normalized_type in {"bool", "boolean"}:
        if stripped == "":
            return ""
        lowered = stripped.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"Invalid bool value: {raw}")
    if normalized_type in {"json", "object", "array", "list", "dict", "map"}:
        if stripped == "":
            return ""
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid json value: {raw}") from error
    return raw


def normalize_variable_form_payload(
    *,
    variable_id: str,
    variable_type: str,
    required: bool,
    default_text: str,
) -> dict[str, Any]:
    """Normalize and validate a variable form payload dict."""
    normalized_id = str(variable_id or "").strip()
    if normalized_id == "":
        raise ValueError("Variable id is required.")
    normalized_type = str(variable_type or "").strip()
    if normalized_type == "":
        raise ValueError("Variable type is required.")
    return {
        "id": normalized_id,
        "type": normalized_type,
        "required": bool(required),
        "default": _parse_variable_default_by_type(
            variable_type=normalized_type,
            default_text=default_text,
        ),
    }


def normalize_profile_form_payload(
    *,
    profile_name: str,
    description: str,
    override_rows: list[tuple[str, str]],
) -> dict[str, Any]:
    """Normalize and validate a profile form payload dict."""
    normalized_name = str(profile_name or "").strip()
    if normalized_name == "":
        raise ValueError("Profile name is required.")
    variables: dict[str, Any] = {}
    for raw_key, raw_value in override_rows:
        key = str(raw_key or "").strip()
        value_text = str(raw_value or "")
        if key == "":
            if value_text.strip() == "":
                continue
            raise ValueError("Profile variable key is required.")
        variables[key] = _parse_json_or_text(value_text)
    return {
        "name": normalized_name,
        "profile": {
            "description": str(description or "").strip(),
            "variables": variables,
        },
    }


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


def _ok(request_id: str | None, result: Any = None) -> dict[str, Any]:
    return {"id": request_id, "result": result}


def _err(request_id: str | None, code: int, message: str) -> dict[str, Any]:
    return {"id": request_id, "error": {"code": code, "message": message}}


def _event(name: str, data: Any = None) -> dict[str, Any]:
    return {"event": name, "data": data}


# ---------------------------------------------------------------------------
# StudioSession  -- headless orchestration, NO Qt
# ---------------------------------------------------------------------------


class StudioSession:
    """Headless session wrapping Scenario, editor, recorder, runner, exporter."""

    def __init__(self, *, locale: str = DEFAULT_LOCALE) -> None:
        self._translator = Translator(detect_default_locale(locale))
        self._settings_path = resolve_settings_path()
        try:
            self._ui_settings = load_ui_settings(self._settings_path)
        except Exception:
            self._ui_settings = StudioUiSettings()

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        self.selected_index: int | None = None

        # Run state
        self._run_lock = threading.Lock()
        self._run_process: subprocess.Popen[str] | None = None
        self._run_phase = "idle"
        self._stop_requested = False

        # Recording state (lazy import because recorder requires win32)
        self._recorder: Any | None = None

        # Overlay process
        self._overlay_process: subprocess.Popen[str] | None = None
        self._overlay_reader_thread: threading.Thread | None = None
        self._stop_hotkey_label = "Alt+Shift+F12"

        # Output settings
        self.output_dir = "artifacts/studio"
        self.suite_name = "scenario"
        self.active_profile: str = ""

        # Event subscribers
        self._event_queues: list[asyncio.Queue[dict[str, Any]]] = []

    # -- Locale / translation -------------------------------------------------

    @property
    def locale(self) -> str:
        return self._translator.locale

    def set_locale(self, locale: str) -> str:
        new_locale = self._translator.set_locale(locale)
        self._ui_settings.locale = new_locale
        save_ui_settings(self._ui_settings, self._settings_path)
        return new_locale

    def _t(self, key: str, **kwargs: object) -> str:
        return self._translator.t(key, **kwargs)

    # -- Event dispatch -------------------------------------------------------

    def _push_event(self, name: str, data: Any = None) -> None:
        payload = _event(name, data)
        for q in list(self._event_queues):
            with suppress(asyncio.QueueFull):
                q.put_nowait(payload)

    def _log(self, message: str) -> None:
        logger.info(message)
        self._push_event("log", {"message": message})

    # -- Scenario persistence -------------------------------------------------

    def save_scenario(self, path: str) -> str:
        target = Path(path)
        self.scenario.save_json(target)
        self._log(f"Saved scenario to {target}")
        return str(target)

    def load_scenario(self, path: str) -> dict[str, Any]:
        loaded = Scenario.load_json(Path(path))
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.selected_index = None
        self._log(f"Loaded scenario from {path}")
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return self.scenario.to_dict()

    def get_steps(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self.scenario.steps]

    def get_header(self) -> dict[str, Any]:
        payload = self.scenario.to_dict()
        payload.pop("steps", None)
        return payload

    # -- Step selection -------------------------------------------------------

    def select_step(self, index: int) -> dict[str, Any] | None:
        if index < 0 or index >= len(self.scenario.steps):
            self.selected_index = None
            self._push_event("step_selected", {"index": None})
            return None
        self.selected_index = index
        step = self.scenario.steps[index]
        self._push_event("step_selected", {"index": index})
        return step.to_dict()

    # -- Step editing ---------------------------------------------------------

    def apply_step(self, params: dict[str, Any]) -> dict[str, Any]:
        index = params.get("index")
        if index is None:
            index = self.selected_index
        if index is None:
            raise ValueError("No step selected.")
        step_index = int(index)

        kind = params.get("kind")
        action = params.get("action")
        control = params.get("control")
        title = params.get("title")
        description = params.get("description")
        disabled = params.get("disabled")
        condition = params.get("condition")
        continue_on_error = params.get("continue_on_error")
        annotations = params.get("annotations")
        step_params = params.get("params")

        updated = self.editor.update_step(
            step_index,
            title=title,
            kind=kind,
            action=action if kind == "action" or (kind is None and action is not None) else None,
            control=control
            if kind == "control" or (kind is None and control is not None)
            else None,
            description=description,
            disabled=disabled,
            condition=condition,
            continue_on_error=continue_on_error,
            annotations=annotations,
            params=step_params,
        )

        step_id = params.get("id")
        if isinstance(step_id, str) and step_id.strip():
            updated.id = step_id.strip()

        validate_step_exportability(updated)
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return updated.to_dict()

    def add_click(self) -> dict[str, Any]:
        step = self.editor.add_step(
            "click",
            "click",
            {
                "title": "Inspector",
                "automation_id": "Inspector",
                "class_name": "Pane",
                "control_type": "Pane",
                "wait_seconds": 0.0,
            },
        )
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_drag(self) -> dict[str, Any]:
        step = self.editor.add_step(
            "drag_drop",
            "drag_drop",
            {
                "target": {
                    "strategy": "coordinate",
                    "coordinate": {"x_ratio": 0.6, "y_ratio": 0.5},
                },
                "input": {
                    "source": {
                        "strategy": "coordinate",
                        "coordinate": {"x_ratio": 0.4, "y_ratio": 0.5},
                    }
                },
            },
        )
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_shortcut(self) -> dict[str, Any]:
        step = self.editor.add_step("press_keys", "press_keys", {"shortcut": "CTRL+S"})
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_menu(self) -> dict[str, Any]:
        step = self.editor.add_step("open_menu", "open_menu", {"menu_path": "File>Save"})
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_type(self) -> dict[str, Any]:
        step = self.editor.add_step("type_text", "type_text", {"text": "sample"})
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_control(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        control_type = (params or {}).get("control", "if")
        step = self.editor.add_control_step(str(control_type))
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def add_group(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        title = (params or {}).get("title")
        step = self.editor.add_group_step(title=title)
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return step.to_dict()

    def delete_step(self, params: dict[str, Any]) -> dict[str, Any]:
        index = int(params.get("index", -1))
        deleted = self.editor.delete_step(index)
        if self.selected_index is not None and self.selected_index >= len(self.scenario.steps):
            self.selected_index = None
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return deleted.to_dict()

    def move_step_up(self, params: dict[str, Any]) -> bool:
        index = int(params.get("index", -1))
        self.editor.move_step_up(index)
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return True

    def move_step_down(self, params: dict[str, Any]) -> bool:
        index = int(params.get("index", -1))
        self.editor.move_step_down(index)
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return True

    def duplicate_step(self, params: dict[str, Any]) -> dict[str, Any]:
        index = int(params.get("index", -1))
        copied = self.editor.duplicate_step(index)
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return copied.to_dict()

    # -- Overlay process ------------------------------------------------------

    def _start_overlay(self, mode: str, window_hint: str = "Unity") -> None:
        self._stop_overlay()
        import sys

        cmd = [
            sys.executable,
            "-m",
            "robot_automation_studio.overlay_process",
            "--mode",
            mode,
            "--window-hint",
            window_hint,
            "--stop-hotkey-label",
            self._stop_hotkey_label,
            "--locale",
            self.locale,
        ]
        try:
            self._overlay_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            self._overlay_reader_thread = threading.Thread(
                target=self._overlay_stdout_reader, daemon=True
            )
            self._overlay_reader_thread.start()
        except Exception as exc:
            self._log(f"[overlay] Failed to start overlay process: {exc}")
            self._overlay_process = None

    def _overlay_stdout_reader(self) -> None:
        proc = self._overlay_process
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = msg.get("event", "")
            if event == "stop_requested":
                self._log("[overlay] Stop requested via overlay button")
                if self._recorder and self._recorder.is_recording:
                    threading.Thread(target=self._stop_recording_safe, daemon=True).start()
                elif self._is_running():
                    self.stop_robot()

    def _stop_recording_safe(self) -> None:
        with suppress(Exception):
            self.stop_recording()

    def _stop_overlay(self) -> None:
        proc = self._overlay_process
        if proc is None:
            return
        self._overlay_process = None
        self._overlay_reader_thread = None
        # Kill immediately so the OS destroys the overlay window at once
        with suppress(Exception):
            proc.kill()

    def _update_overlay_progress(self, text: str) -> None:
        proc = self._overlay_process
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.write(json.dumps({"cmd": "update_progress", "text": text}) + "\n")
                proc.stdin.flush()
        except Exception:
            pass

    # -- Recording ------------------------------------------------------------

    def _ensure_recorder(self) -> Any:
        if self._recorder is not None:
            return self._recorder
        from .recorder import ScenarioRecorder

        self._recorder = ScenarioRecorder(
            on_record_error=self._on_record_error,
            on_stop_hotkey=self._on_recorder_stop_hotkey,
            stop_hotkey_main_key="F12",
            stop_hotkey_required_modifiers={"ALT", "SHIFT"},
            unity_bridge=self.unity_bridge,
        )
        return self._recorder

    def _on_record_error(self, message: str) -> None:
        self._log(f"[recording-error] {message}")
        self._push_event("recording_error", {"message": message})

    def _on_recorder_stop_hotkey(self) -> None:
        self._log("[hotkey] Stop hotkey pressed — stopping recording")
        threading.Thread(target=self._stop_recording_safe, daemon=True).start()

    def start_recording(self, params: dict[str, Any] | None = None) -> bool:
        recorder = self._ensure_recorder()
        if recorder.is_recording:
            raise ValueError("Recording is already in progress.")
        window_hint = (params or {}).get("window_hint", "Unity")
        recorder.start(window_hint=str(window_hint))
        self._start_overlay("recording", window_hint=str(window_hint))
        self._log(f"Recording started (window_hint={window_hint})")
        self._push_event("recording_started", {"window_hint": window_hint})
        return True

    def stop_recording(self) -> dict[str, Any]:
        recorder = self._ensure_recorder()
        if not recorder.is_recording:
            raise ValueError("Recording is not running.")
        # Immediately stop overlay and notify frontend so UI updates instantly
        self._stop_overlay()
        self._push_event("recording_stopped", {})

        # Heavy work (recorder.stop drains pending actions, normalization)
        # runs in a background thread so the RPC response returns immediately.
        def _finalize() -> None:
            try:
                from .recorder import events_to_steps

                events = recorder.stop()
                steps = events_to_steps(events)

                try:
                    from .recording_normalization import (
                        normalize_recorded_hierarchy_paths_to_variables,
                    )

                    start_index = len(self.scenario.steps)
                    for step in steps:
                        self.scenario.steps.append(step)
                    normalize_recorded_hierarchy_paths_to_variables(
                        self.scenario, step_start_index=start_index
                    )
                except Exception as error:
                    self._log(f"[recording-normalization] {error}")
                    for step in steps:
                        if step not in self.scenario.steps:
                            self.scenario.steps.append(step)

                count = len(steps)
                self._log(f"Recording stopped, {count} step(s) captured")
                self._push_event("steps_changed", {"count": len(self.scenario.steps)})
            except Exception as exc:
                self._log(f"[stop-recording] finalize error: {exc}")

        threading.Thread(target=_finalize, daemon=True).start()
        return {"stopping": True}

    # -- Robot run ------------------------------------------------------------

    def _is_running(self) -> bool:
        with self._run_lock:
            return self._run_process is not None

    def run_robot(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._is_running():
            raise ValueError("Robot is already running.")
        p = params or {}
        output_dir = Path(p.get("output_dir", self.output_dir)).resolve()
        suite_name = p.get("suite_name", self.suite_name) or "scenario"
        active_profile = p.get("active_profile", self.active_profile) or None

        # Sync scenario header fields from params if provided
        if "name" in p:
            self.scenario.name = str(p["name"])
        if "execution_mode" in p:
            mode = normalize_unity_execution_mode(p["execution_mode"])
            self.scenario.sync_runtime_metadata(
                execution_mode=mode,
                unity_project_path=p.get("unity_project_path", ""),
            )

        # Preflight
        report = validate_scenario(self.scenario, active_profile=active_profile)
        if not report.is_valid:
            issues = [
                {"code": issue.code, "location": issue.location, "message": issue.message}
                for issue in report.issues
            ]
            return {"started": False, "issues": issues}

        # Export
        try:
            result = export_all(
                self.scenario,
                output_dir=output_dir,
                suite_name=suite_name,
                active_profile=active_profile,
            )
        except Exception as error:
            raise ValueError(f"Export failed: {error}") from error

        artifacts_dir = output_dir / "run"
        variable_output = output_dir

        self._stop_requested = False
        self._set_phase("starting_robot")
        window_hint = self.scenario.to_dict().get("target_window_hint", "Unity") or "Unity"
        self._start_overlay("run", window_hint=str(window_hint))

        run_id = uuid.uuid4().hex[:8]

        def _run_thread() -> None:
            run_result: RunResult | None = None
            run_error: Exception | None = None
            try:
                self._log("Starting robot process...")
                process = start_robot_process(
                    suite_path=result.robot_path,
                    output_dir=artifacts_dir,
                    variable_output_dir=variable_output,
                )
                with self._run_lock:
                    self._run_process = process
                self._set_phase("running")

                if self._stop_requested:
                    stop_robot_process(process)
                run_result = wait_robot_process(process)
            except Exception as error:
                run_error = error
            finally:
                with self._run_lock:
                    self._run_process = None
                self._stop_overlay()
                self._set_phase("idle")

                finished_data: dict[str, Any] = {"run_id": run_id}
                if run_error is not None:
                    finished_data["error"] = str(run_error)
                    self._log(f"Robot run failed: {run_error}")
                elif run_result is not None:
                    finished_data["return_code"] = run_result.return_code
                    finished_data["stdout"] = run_result.stdout
                    finished_data["stderr"] = run_result.stderr
                    self._log(f"Robot exited with code {run_result.return_code}")
                self._push_event("run_finished", finished_data)

        thread = threading.Thread(target=_run_thread, daemon=True)
        thread.start()
        return {"started": True, "run_id": run_id}

    def stop_robot(self) -> bool:
        if not self._is_running():
            return False
        self._stop_requested = True
        # Immediately kill overlay so the blue border disappears at once
        self._stop_overlay()
        with self._run_lock:
            process = self._run_process
        if process is not None:
            stop_robot_process(process)
        self._set_phase("stopping")
        self._log("Stop requested for robot process")
        return True

    def _set_phase(self, phase: str) -> None:
        self._run_phase = phase
        self._push_event("phase_changed", {"phase": phase})

    # -- Export ---------------------------------------------------------------

    def run_export(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        p = params or {}
        output_dir = Path(p.get("output_dir", self.output_dir)).resolve()
        suite_name = p.get("suite_name", self.suite_name) or "scenario"
        active_profile = p.get("active_profile", self.active_profile) or None

        result = export_all(
            self.scenario,
            output_dir=output_dir,
            suite_name=suite_name,
            active_profile=active_profile,
        )
        self._log(f"Exported robot suite to {result.robot_path}")
        self._log(f"Exported scenario JSON to {result.json_path}")
        return {
            "robot_path": str(result.robot_path),
            "json_path": str(result.json_path),
        }

    # -- Settings -------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        return {
            "locale": self._ui_settings.locale,
            "target": self._ui_settings.target,
            "window_hint": self._ui_settings.window_hint,
            "execution_mode": self._ui_settings.execution_mode,
            "unity_project_path": self._ui_settings.unity_project_path,
            "stop_hotkey_label": self._ui_settings.stop_hotkey_label,
        }

    def set_settings(self, params: dict[str, Any]) -> dict[str, Any]:
        if "locale" in params:
            self._ui_settings.locale = normalize_locale(params["locale"])
            self._translator.set_locale(self._ui_settings.locale)
        if "target" in params:
            self._ui_settings.target = str(params["target"]).strip().lower() or "unity"
        if "window_hint" in params:
            self._ui_settings.window_hint = str(params["window_hint"]).strip() or "Unity"
        if "execution_mode" in params:
            self._ui_settings.execution_mode = normalize_unity_execution_mode(
                params["execution_mode"]
            )
        if "unity_project_path" in params:
            self._ui_settings.unity_project_path = str(params["unity_project_path"]).strip()
        if "stop_hotkey_label" in params:
            self._ui_settings.stop_hotkey_label = str(params["stop_hotkey_label"]).strip()
        save_ui_settings(self._ui_settings, self._settings_path)
        return self.get_settings()

    def get_locale(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "supported_locales": list(SUPPORTED_LOCALES),
        }

    def set_locale_method(self, params: dict[str, Any]) -> dict[str, Any]:
        new_locale = self.set_locale(str(params.get("locale", DEFAULT_LOCALE)))
        return {"locale": new_locale, "supported_locales": list(SUPPORTED_LOCALES)}

    # -- Editor full JSON -----------------------------------------------------

    def get_full_json(self) -> dict[str, Any]:
        return self.scenario.to_dict()

    def set_full_json(self, params: dict[str, Any]) -> dict[str, Any]:
        data = params.get("scenario")
        if data is None:
            data = params
            # If caller passed the scenario dict directly at top level,
            # check for required fields
            if "schema_version" not in data and "steps" not in data:
                raise ValueError("Missing 'scenario' key or invalid payload.")
        loaded = Scenario.from_dict(data)
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.selected_index = None
        self._push_event("steps_changed", {"count": len(self.scenario.steps)})
        return self.scenario.to_dict()

    # -- Scenario header update ------------------------------------------------

    def update_header(self, params: dict[str, Any]) -> dict[str, Any]:
        if "name" in params:
            self.scenario.name = str(params["name"])
        if "description" in params:
            self.scenario.description = str(params["description"])
        if "target" in params:
            target = str(params["target"]).strip().lower()
            if target in {"unity", "web", "desktop", "hybrid"}:
                self.scenario.target = target
        if "target_window_hint" in params:
            self.scenario.target_window_hint = str(params["target_window_hint"]).strip()
        if "execution_mode" in params:
            mode = normalize_unity_execution_mode(params["execution_mode"])
            self.scenario.sync_runtime_metadata(
                execution_mode=mode,
                unity_project_path=params.get(
                    "unity_project_path",
                    str((self.scenario.metadata or {}).get(UNITY_PROJECT_PATH_KEY, "")),
                ),
            )
        if "unity_project_path" in params:
            if self.scenario.metadata is None:
                self.scenario.metadata = {}
            self.scenario.metadata[UNITY_PROJECT_PATH_KEY] = str(
                params["unity_project_path"]
            ).strip()
        if "subflow_timeout_seconds" in params:
            raw = params["subflow_timeout_seconds"]
            if self.scenario.execution is None:
                self.scenario.execution = {}
            if raw == "" or raw is None:
                self.scenario.execution.pop("subflow_timeout_seconds", None)
            else:
                self.scenario.execution["subflow_timeout_seconds"] = raw
        if "active_profile" in params:
            self.active_profile = str(params["active_profile"]).strip()
            if self.scenario.execution is None:
                self.scenario.execution = {}
            self.scenario.execution["active_profile"] = self.active_profile
        self._push_event("header_changed", self.get_header())
        return self.get_header()

    # -- Params template -------------------------------------------------------

    def get_params_template(self, params: dict[str, Any]) -> dict[str, Any]:
        from .params_template import default_params_template_for_action

        action = str(params.get("action", "")).strip()
        template = default_params_template_for_action(action)
        if template is None:
            return {"template": None, "action": action}
        return {"template": template, "action": action}

    # -- Profile diff ----------------------------------------------------------

    def get_profile_diff(self, params: dict[str, Any]) -> dict[str, Any]:
        base_profile = str(params.get("base_profile", "")).strip()
        compare_profile = str(params.get("compare_profile", "")).strip()
        entries = build_profile_diff(
            self.scenario,
            base_profile=base_profile,
            compare_profile=compare_profile,
        )
        return {
            "entries": [
                {
                    "path": entry.path,
                    "base_value": entry.base_value,
                    "compare_value": entry.compare_value,
                }
                for entry in entries
            ]
        }

    # -- Native file/directory dialogs ----------------------------------------

    def _open_file_dialog_save(self) -> str | None:
        """Open a native save-file dialog. Returns path or None."""
        result: list[str | None] = [None]

        def _run() -> None:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.asksaveasfilename(
                title="Save Scenario",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            root.destroy()
            result[0] = path if path else None

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return result[0]

    def _open_file_dialog_open(self) -> str | None:
        """Open a native open-file dialog. Returns path or None."""
        result: list[str | None] = [None]

        def _run() -> None:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Load Scenario",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            root.destroy()
            result[0] = path if path else None

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return result[0]

    def _open_directory_dialog(self) -> str | None:
        """Open a native directory picker dialog. Returns path or None."""
        result: list[str | None] = [None]

        def _run() -> None:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Select Directory")
            root.destroy()
            result[0] = path if path else None

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return result[0]

    def save_scenario_as(self) -> dict[str, Any]:
        """Open a save dialog, then save scenario to chosen path."""
        path = self._open_file_dialog_save()
        if path is None:
            return {"cancelled": True, "path": None}
        saved_path = self.save_scenario(path)
        return {"cancelled": False, "path": saved_path}

    def load_scenario_from(self) -> dict[str, Any]:
        """Open an open dialog, then load scenario from chosen path."""
        path = self._open_file_dialog_open()
        if path is None:
            return {"cancelled": True, "path": None, "scenario": None}
        scenario_data = self.load_scenario(path)
        return {"cancelled": False, "path": path, "scenario": scenario_data}

    def browse_directory(self) -> dict[str, Any]:
        """Open a directory picker dialog. Returns chosen directory or None."""
        path = self._open_directory_dialog()
        if path is None:
            return {"cancelled": True, "path": None}
        return {"cancelled": False, "path": path}

    def open_directory(self, params: dict[str, Any]) -> dict[str, Any]:
        """Open a directory in the OS file explorer."""
        import os
        import sys

        path = str(params.get("path", "")).strip()
        if not path:
            raise ValueError("path is required")
        target = Path(path)
        if not target.exists():
            raise ValueError(f"Directory does not exist: {path}")
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"opened": True, "path": str(target)}

    # -- Diagnostics ----------------------------------------------------------

    def get_diagnostics_info(self) -> dict[str, Any]:
        """Return paths and last-run diagnostics data for the Run Diagnostics dialog."""
        output_dir = Path(self.output_dir).resolve()
        diagnostics_dir = output_dir / "diagnostics"
        subflow_logs_dir = output_dir / "logs"

        last_run_json: dict[str, Any] | None = None
        last_run_summary: str = ""

        if diagnostics_dir.is_dir():
            json_files = sorted(diagnostics_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
            if json_files:
                latest = json_files[-1]
                try:
                    with latest.open(encoding="utf-8") as f:
                        last_run_json = json.load(f)
                except Exception as exc:
                    last_run_summary = f"Failed to read diagnostics file: {exc}"

                if last_run_json is not None:
                    try:
                        status = last_run_json.get("status", "unknown")
                        total = last_run_json.get("total_keywords", last_run_json.get("total", 0))
                        passed = last_run_json.get("passed", 0)
                        failed = last_run_json.get("failed", 0)
                        elapsed = last_run_json.get(
                            "elapsed_seconds", last_run_json.get("elapsed", None)
                        )
                        lines = [f"Status: {status}"]
                        if total:
                            lines.append(
                                f"Keywords: {total} total,"
                                f" {passed} passed, {failed} failed"
                            )
                        if elapsed is not None:
                            lines.append(f"Duration: {elapsed}s")
                        lines.append(f"File: {latest.name}")
                        last_run_summary = "\n".join(lines)
                    except Exception as exc:
                        last_run_summary = f"Summary unavailable: {exc}"

        return {
            "diagnostics_dir": str(diagnostics_dir),
            "subflow_logs_dir": str(subflow_logs_dir),
            "last_run_summary": last_run_summary,
            "last_run_json": last_run_json,
        }

    # -- Validation -----------------------------------------------------------

    def preflight(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        p = params or {}
        active_profile = p.get("active_profile", self.active_profile) or None
        report = validate_scenario(self.scenario, active_profile=active_profile)
        issues = [
            {"code": issue.code, "location": issue.location, "message": issue.message}
            for issue in report.issues
        ]
        return {"valid": report.is_valid, "issues": issues}


# ---------------------------------------------------------------------------
# Method dispatch table
# ---------------------------------------------------------------------------


def _build_dispatch(session: StudioSession) -> dict[str, Any]:
    """Return method-name -> handler mapping."""
    return {
        "scenario.save": lambda p: session.save_scenario(str(p.get("path", "scenario.json"))),
        "scenario.load": lambda p: session.load_scenario(str(p.get("path", "scenario.json"))),
        "scenario.save_as": lambda p: session.save_scenario_as(),
        "scenario.load_from": lambda p: session.load_scenario_from(),
        "dialog.browse_directory": lambda p: session.browse_directory(),
        "shell.open_directory": lambda p: session.open_directory(p),
        "scenario.get_steps": lambda p: session.get_steps(),
        "scenario.get_header": lambda p: session.get_header(),
        "step.select": lambda p: session.select_step(int(p.get("index", -1))),
        "step.apply": lambda p: session.apply_step(p),
        "step.add_click": lambda p: session.add_click(),
        "step.add_drag": lambda p: session.add_drag(),
        "step.add_shortcut": lambda p: session.add_shortcut(),
        "step.add_menu": lambda p: session.add_menu(),
        "step.add_type": lambda p: session.add_type(),
        "step.add_control": lambda p: session.add_control(p),
        "step.add_group": lambda p: session.add_group(p),
        "step.delete": lambda p: session.delete_step(p),
        "step.move_up": lambda p: session.move_step_up(p),
        "step.move_down": lambda p: session.move_step_down(p),
        "step.duplicate": lambda p: session.duplicate_step(p),
        "recording.start": lambda p: session.start_recording(p),
        "recording.stop": lambda p: session.stop_recording(),
        "robot.run": lambda p: session.run_robot(p),
        "robot.stop": lambda p: session.stop_robot(),
        "export.run": lambda p: session.run_export(p),
        "settings.get": lambda p: session.get_settings(),
        "settings.set": lambda p: session.set_settings(p),
        "settings.get_locale": lambda p: session.get_locale(),
        "settings.set_locale": lambda p: session.set_locale_method(p),
        "editor.get_full_json": lambda p: session.get_full_json(),
        "editor.set_full_json": lambda p: session.set_full_json(p),
        "validation.preflight": lambda p: session.preflight(p),
        "scenario.update_header": lambda p: session.update_header(p),
        "scenario.get_params_template": lambda p: session.get_params_template(p),
        "profiles.get_diff": lambda p: session.get_profile_diff(p),
        "diagnostics.get_info": lambda p: session.get_diagnostics_info(),
    }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


def create_app(*, locale: str = DEFAULT_LOCALE) -> FastAPI:
    """Build the FastAPI application with a shared StudioSession."""
    session = StudioSession(locale=locale)
    dispatch = _build_dispatch(session)

    app = FastAPI(title="Robot Automation Studio Server")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        session._event_queues.append(event_queue)

        async def _push_events() -> None:
            try:
                while True:
                    payload = await event_queue.get()
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        return
                    await websocket.send_json(payload)
            except Exception:
                pass

        push_task = asyncio.create_task(_push_events())
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json(_err(None, _PARSE_ERROR, "Invalid JSON"))
                    continue

                request_id = msg.get("id")
                method = msg.get("method")
                params = msg.get("params") or {}

                if not isinstance(method, str) or method == "":
                    await websocket.send_json(
                        _err(request_id, _INVALID_REQUEST, "Missing 'method'")
                    )
                    continue

                handler = dispatch.get(method)
                if handler is None:
                    await websocket.send_json(
                        _err(request_id, _METHOD_NOT_FOUND, f"Unknown method: {method}")
                    )
                    continue

                try:
                    result = await asyncio.get_event_loop().run_in_executor(None, handler, params)
                    await websocket.send_json(_ok(request_id, result))
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    await websocket.send_json(_err(request_id, _INVALID_PARAMS, str(exc)))
                except Exception as exc:
                    logger.exception("Unhandled error in method %s", method)
                    await websocket.send_json(_err(request_id, _INTERNAL_ERROR, str(exc)))
        except WebSocketDisconnect:
            pass
        finally:
            push_task.cancel()
            with suppress(asyncio.CancelledError):
                await push_task
            if event_queue in session._event_queues:
                session._event_queues.remove(event_queue)

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Robot Automation Studio headless server")
    parser.add_argument("--port", type=int, default=0, help="Port (0 = auto-assign)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    parser.add_argument("--locale", type=str, default=DEFAULT_LOCALE, help="UI locale (en/ja)")
    args = parser.parse_args()

    app = create_app(locale=args.locale)

    class _PortReporter(uvicorn.Server):
        """Subclass that prints PORT:<n> once the server is listening."""

        def _log_started_message(self, listeners: list[Any]) -> None:  # type: ignore[override]
            super()._log_started_message(listeners)  # type: ignore[arg-type]
            for sock in listeners:
                addr = sock.getsockname()
                if isinstance(addr, tuple) and len(addr) >= 2:
                    print(f"PORT:{addr[1]}", flush=True)

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    server = _PortReporter(config)
    server.run()


if __name__ == "__main__":
    main()
