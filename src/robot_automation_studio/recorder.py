"""Input recording helpers and event-to-step conversion."""

from __future__ import annotations

import json
import os
import platform
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import win32gui  # type: ignore[import-not-found]
from pynput import keyboard, mouse
from pywinauto import Desktop

from .models import Step

STOP_HOTKEY_MAIN_KEY = "F12"
STOP_HOTKEY_REQUIRED_MODIFIERS = {"ALT", "SHIFT"}
HIERARCHY_BRIDGE_ERROR_SUPPRESS_SECONDS = 1.0
RECORD_PERF_ENV_VAR = "RAS_RECORD_PERF"
RECORD_PERF_PATH_ENV_VAR = "RAS_RECORD_PERF_PATH"
RECORD_PERF_MAX_SAMPLES = 20000
_UIA_SELECTOR_KEYS = ("title", "automation_id", "class_name", "control_type", "index")


@dataclass(slots=True)
class WindowSnapshot:
    title: str
    left: int
    top: int
    width: int
    height: int


@dataclass(slots=True)
class RecordedEvent:
    kind: str
    payload: dict[str, Any]
    timestamp_ms: int


def _env_flag(name: str) -> bool:
    value = os.getenv(name, None)
    if value is None:
        return False
    normalized = str(value).strip().lower()
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return True


def resolve_selector_from_point(x: int, y: int) -> dict[str, Any] | None:
    try:
        wrapper = Desktop(backend="uia").from_point(x, y)
    except Exception:
        return None
    info = getattr(wrapper, "element_info", None)
    if info is None:
        return None

    selector: dict[str, Any] = {}
    title = str(getattr(info, "name", "") or "").strip()
    automation_id = str(getattr(info, "automation_id", "") or "").strip()
    class_name = str(getattr(info, "class_name", "") or "").strip()
    control_type = str(getattr(info, "control_type", "") or "").strip()

    if title:
        selector["title"] = title
    if automation_id:
        selector["automation_id"] = automation_id
    if class_name:
        selector["class_name"] = class_name
    if control_type:
        selector["control_type"] = control_type

    return selector or None


def _is_generic_unity_hierarchy_pane(selector: dict[str, Any]) -> bool:
    title = str(selector.get("title") or "").strip().lower()
    class_name = str(selector.get("class_name") or "").strip()
    control_type = str(selector.get("control_type") or "").strip().lower()
    if class_name != "UnityGUIViewWndClass":
        return False
    if control_type != "pane":
        return False
    return "scenehierarchywindow" in title or "hierarchy" in title


def _normalized_uia_selector(selector: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in _UIA_SELECTOR_KEYS:
        value = selector.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        normalized[key] = value
    return normalized


def _selector_signature(selector: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    signature: list[tuple[str, str]] = []
    for key in _UIA_SELECTOR_KEYS:
        if key not in selector:
            continue
        signature.append((key, str(selector[key])))
    return tuple(signature)


def _selector_candidates_for_fallbacks(primary: dict[str, Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = {_selector_signature(primary)}
    patterns: tuple[tuple[str, ...], ...] = (
        ("automation_id", "class_name", "control_type"),
        ("automation_id", "control_type"),
        ("automation_id",),
        ("title", "class_name", "control_type"),
        ("title", "control_type"),
        ("title",),
    )
    for pattern in patterns:
        candidate: dict[str, Any] = {}
        for key in pattern:
            value = primary.get(key)
            if value is None:
                continue
            candidate[key] = value
        if not candidate:
            continue
        if "automation_id" not in candidate and "title" not in candidate:
            continue
        signature = _selector_signature(candidate)
        if signature in seen:
            continue
        seen.add(signature)
        variants.append(candidate)
    return variants


def _build_uia_target_with_fallbacks(selector: dict[str, Any]) -> dict[str, Any]:
    primary = _normalized_uia_selector(selector)
    target: dict[str, Any] = {"strategy": "uia", "uia": primary}
    fallbacks = [
        {"strategy": "uia", "uia": candidate}
        for candidate in _selector_candidates_for_fallbacks(primary)
    ]
    if fallbacks:
        target["fallbacks"] = fallbacks
    return target


def _build_hierarchy_target_with_fallbacks(path: str) -> dict[str, Any]:
    normalized = str(path or "").strip().replace("\\", "/").strip("/")
    target: dict[str, Any] = {
        "strategy": "unity_hierarchy",
        "unity_hierarchy": {"path": normalized, "match_mode": "exact"},
    }
    segments = [segment for segment in normalized.split("/") if segment]
    if len(segments) >= 2:
        wildcard_path = f"*/{'/'.join(segments[1:])}"
        if wildcard_path != normalized:
            target["fallbacks"] = [
                {
                    "strategy": "unity_hierarchy",
                    "unity_hierarchy": {"path": wildcard_path, "match_mode": "exact"},
                }
            ]
    return target


def _title_matches_window_hint(title: str, window_hint: str) -> bool:
    normalized_title = str(title or "").strip().lower()
    if normalized_title == "":
        return False
    normalized_hint = str(window_hint or "").strip().lower()
    if normalized_hint == "":
        return True
    return normalized_hint in normalized_title


def list_visible_window_titles() -> list[str]:
    titles: list[str] = []

    def _callback(window_handle: int, _param: int) -> bool:
        if not win32gui.IsWindowVisible(window_handle):
            return True
        title = str(win32gui.GetWindowText(window_handle) or "").strip()
        if title != "":
            titles.append(title)
        return True

    win32gui.EnumWindows(_callback, 0)
    return titles


def has_visible_window_with_hint(
    window_hint: str,
    window_titles: Sequence[str] | None = None,
) -> bool:
    titles = list(window_titles) if window_titles is not None else list_visible_window_titles()
    return any(_title_matches_window_hint(str(title), window_hint) for title in titles)


def get_foreground_window_snapshot() -> WindowSnapshot | None:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    title = win32gui.GetWindowText(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return WindowSnapshot(title=title, left=left, top=top, width=width, height=height)


def events_to_steps(events: list[RecordedEvent]) -> list[Step]:
    steps: list[Step] = []
    for event in events:
        if event.kind == "click":
            steps.append(
                Step(kind="action", action="click", title="click", params=dict(event.payload))
            )
            continue
        if event.kind == "drag":
            steps.append(
                Step(
                    kind="action",
                    action="drag_drop",
                    title="drag_drop",
                    params=dict(event.payload),
                )
            )
            continue
        if event.kind == "shortcut":
            steps.append(
                Step(
                    kind="action",
                    action="press_keys",
                    title="press_keys",
                    params=dict(event.payload),
                )
            )
            continue
        steps.append(
            Step(
                kind="action",
                action="unknown",
                title=f"unknown:{event.kind}",
                params=dict(event.payload),
            )
        )
    return steps


class ScenarioRecorder:
    """Simple in-memory recorder with explicit event append API."""

    _SELECTION_WAIT_TIMEOUT_SECONDS = 0.35

    def __init__(
        self,
        window_provider: Callable[[], WindowSnapshot | None] = get_foreground_window_snapshot,
        element_resolver: Callable[[int, int], dict[str, Any] | None] = resolve_selector_from_point,
        on_record_error: Callable[[str], None] | None = None,
        on_stop_hotkey: Callable[[], None] | None = None,
        stop_hotkey_main_key: str = STOP_HOTKEY_MAIN_KEY,
        stop_hotkey_required_modifiers: set[str] | frozenset[str] = STOP_HOTKEY_REQUIRED_MODIFIERS,
        unity_bridge: Any | None = None,
    ) -> None:
        if platform.system().lower() != "windows":
            raise RuntimeError("ScenarioRecorder supports Windows only.")
        self._events: list[RecordedEvent] = []
        self._recording = False
        self._window_provider = window_provider
        self._element_resolver = element_resolver
        self._on_record_error = on_record_error
        self._on_stop_hotkey = on_stop_hotkey
        self._unity_bridge = unity_bridge
        self._stop_hotkey_main_key = str(stop_hotkey_main_key or STOP_HOTKEY_MAIN_KEY).upper()
        self._stop_hotkey_required_modifiers = {
            str(modifier).upper() for modifier in stop_hotkey_required_modifiers
        } or set(STOP_HOTKEY_REQUIRED_MODIFIERS)
        self._window_hint = "Unity"
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_down_point: tuple[int, int] | None = None
        self._mouse_down_unix_ms: int | None = None
        self._modifier_keys: set[str] = set()
        self._bridge_retry_backoff_until = 0.0
        self._hierarchy_error_suppress_until = 0.0
        self._last_hierarchy_bridge_diag = ""
        self._record_perf_enabled = False
        self._record_perf_path: Path | None = None
        self._record_perf_session_id = ""
        self._record_perf_samples: list[dict[str, Any]] = []
        self._record_perf_lock = threading.Lock()

    def set_stop_hotkey(self, main_key: str, required_modifiers: set[str] | frozenset[str]) -> None:
        self._stop_hotkey_main_key = str(main_key or STOP_HOTKEY_MAIN_KEY).upper()
        normalized_modifiers = {str(value).upper() for value in required_modifiers}
        self._stop_hotkey_required_modifiers = normalized_modifiers or set(
            STOP_HOTKEY_REQUIRED_MODIFIERS
        )

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _resolve_record_perf_path(self) -> Path:
        configured = str(os.getenv(RECORD_PERF_PATH_ENV_VAR, "") or "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path("artifacts/studio").resolve() / "diagnostics" / "recording-perf.jsonl"

    def _add_record_perf_sample(self, sample: dict[str, Any]) -> None:
        if not self._record_perf_enabled:
            return
        with self._record_perf_lock:
            if len(self._record_perf_samples) >= RECORD_PERF_MAX_SAMPLES:
                return
            self._record_perf_samples.append(dict(sample))

    def _flush_record_perf_samples(self) -> None:
        if not self._record_perf_enabled:
            return
        path = self._record_perf_path
        if path is None:
            return
        with self._record_perf_lock:
            samples = list(self._record_perf_samples)
            self._record_perf_samples.clear()
        if not samples:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                for sample in samples:
                    stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
        except OSError as error:
            self._report_record_error(
                f"[diagnostics] Failed to persist recording perf log to {path}: {error}"
            )

    def start(self, window_hint: str = "Unity") -> None:
        self._events.clear()
        self._recording = True
        self._window_hint = window_hint
        self._mouse_down_point = None
        self._mouse_down_unix_ms = None
        self._modifier_keys.clear()
        self._bridge_retry_backoff_until = 0.0
        self._hierarchy_error_suppress_until = 0.0
        self._last_hierarchy_bridge_diag = ""
        self._record_perf_enabled = _env_flag(RECORD_PERF_ENV_VAR)
        self._record_perf_path = (
            self._resolve_record_perf_path() if self._record_perf_enabled else None
        )
        self._record_perf_session_id = (
            f"{int(time.time() * 1000)}-{os.getpid()}" if self._record_perf_enabled else ""
        )
        with self._record_perf_lock:
            self._record_perf_samples.clear()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> list[RecordedEvent]:
        self._recording = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        self._mouse_listener = None
        self._keyboard_listener = None
        self._mouse_down_point = None
        self._mouse_down_unix_ms = None
        self._modifier_keys.clear()
        self._bridge_retry_backoff_until = 0.0
        self._hierarchy_error_suppress_until = 0.0
        self._last_hierarchy_bridge_diag = ""
        self._flush_record_perf_samples()
        return list(self._events)

    def append(self, kind: str, payload: dict[str, Any]) -> None:
        if not self._recording:
            return
        self._events.append(
            RecordedEvent(kind=kind, payload=dict(payload), timestamp_ms=int(time.time() * 1000))
        )

    def append_with_timestamp(self, kind: str, payload: dict[str, Any], timestamp_ms: int) -> None:
        if not self._recording:
            return
        self._events.append(
            RecordedEvent(kind=kind, payload=dict(payload), timestamp_ms=timestamp_ms)
        )

    def _report_record_error(self, message: str) -> None:
        if self._on_record_error is None:
            return
        self._on_record_error(message)

    def _window_matches(self, snapshot: WindowSnapshot | None) -> bool:
        if snapshot is None:
            return False
        return _title_matches_window_hint(snapshot.title, self._window_hint)

    def _resolve_hierarchy_path(
        self,
        snapshot: WindowSnapshot | None = None,
        mouse_down_unix_ms: int | None = None,
        perf_sample: dict[str, Any] | None = None,
    ) -> str | None:
        if time.monotonic() < self._bridge_retry_backoff_until:
            return None
        bridge = self._unity_bridge
        if bridge is None:
            return None

        # Prefer the richer selection state API when available. It lets us avoid blocking waits
        # when the selection has already changed since the click started.
        state_getter = getattr(bridge, "get_selection_state", None)
        if state_getter is not None:
            payload: Any | None
            state_started_ns: int | None = None
            if perf_sample is not None:
                state_started_ns = time.perf_counter_ns()
            try:
                payload = state_getter()
            except Exception:
                payload = None
            if perf_sample is not None and state_started_ns is not None:
                perf_sample["t_bridge_get_selection_state_ms"] = (
                    time.perf_counter_ns() - state_started_ns
                ) / 1e6

            if isinstance(payload, dict) and bool(payload.get("ok", False)):
                normalized = (
                    str(payload.get("hierarchy_path") or "").strip().replace("\\", "/").strip("/")
                )
                version_value = payload.get("selection_version", None)
                selection_version: int | None = None
                if version_value is not None and not isinstance(version_value, bool):
                    try:
                        selection_version = int(version_value)
                    except (TypeError, ValueError):
                        selection_version = None

                changed_value = payload.get("selection_changed_unix_ms", None)
                selection_changed_unix_ms: int | None = None
                if changed_value is not None and not isinstance(changed_value, bool):
                    try:
                        selection_changed_unix_ms = int(changed_value)
                    except (TypeError, ValueError):
                        selection_changed_unix_ms = None

                if (
                    normalized
                    and mouse_down_unix_ms is not None
                    and selection_changed_unix_ms is not None
                    and selection_changed_unix_ms >= mouse_down_unix_ms
                ):
                    self._last_hierarchy_bridge_diag = ""
                    return normalized

                waiter = getattr(bridge, "wait_for_selection_change", None)
                if waiter is not None and selection_version is not None:
                    waited_payload: Any | None
                    wait_started_ns: int | None = None
                    if perf_sample is not None:
                        wait_started_ns = time.perf_counter_ns()
                    try:
                        waited_payload = waiter(
                            selection_version,
                            timeout_seconds=self._SELECTION_WAIT_TIMEOUT_SECONDS,
                        )
                    except TypeError:
                        try:
                            waited_payload = waiter(selection_version)
                        except Exception:
                            waited_payload = None
                    except Exception:
                        waited_payload = None
                    if perf_sample is not None and wait_started_ns is not None:
                        perf_sample["t_bridge_wait_for_selection_change_ms"] = (
                            time.perf_counter_ns() - wait_started_ns
                        ) / 1e6
                    if isinstance(waited_payload, dict) and bool(waited_payload.get("ok", False)):
                        waited_normalized = (
                            str(waited_payload.get("hierarchy_path") or "")
                            .strip()
                            .replace("\\", "/")
                            .strip("/")
                        )
                        if waited_normalized:
                            self._last_hierarchy_bridge_diag = ""
                            return waited_normalized

                if normalized:
                    self._last_hierarchy_bridge_diag = ""
                    return normalized

        getter = getattr(bridge, "get_selected_hierarchy_path", None)
        if getter is None:
            return None
        fallback_started_ns: int | None = None
        if perf_sample is not None:
            fallback_started_ns = time.perf_counter_ns()
        for _ in range(4):
            try:
                path = getter()
            except Exception:
                path = None
            normalized = str(path or "").strip().replace("\\", "/").strip("/")
            if normalized:
                self._last_hierarchy_bridge_diag = ""
                if perf_sample is not None and fallback_started_ns is not None:
                    perf_sample["t_bridge_get_selected_hierarchy_path_ms"] = (
                        time.perf_counter_ns() - fallback_started_ns
                    ) / 1e6
                return normalized
            time.sleep(0.02)
        self._bridge_retry_backoff_until = time.monotonic() + 0.8
        self._last_hierarchy_bridge_diag = self._build_hierarchy_bridge_diagnostics(snapshot)
        if perf_sample is not None and fallback_started_ns is not None:
            perf_sample["t_bridge_get_selected_hierarchy_path_ms"] = (
                time.perf_counter_ns() - fallback_started_ns
            ) / 1e6
        return None

    def _build_hierarchy_bridge_diagnostics(self, snapshot: WindowSnapshot | None) -> str:
        bridge = self._unity_bridge
        endpoint = str(getattr(bridge, "endpoint", "unknown") or "unknown")

        bridge_available: str
        checker = getattr(bridge, "is_available", None)
        if checker is None:
            bridge_available = "unknown"
        else:
            try:
                bridge_available = str(bool(checker(request_timeout_seconds=0.2)))
            except TypeError:
                try:
                    bridge_available = str(bool(checker()))
                except Exception:
                    bridge_available = "error"
            except Exception:
                bridge_available = "error"

        window_title = ""
        if snapshot is not None:
            window_title = str(snapshot.title or "").strip()
        backoff_remaining = max(0.0, self._bridge_retry_backoff_until - time.monotonic())
        window_hint = str(self._window_hint or "").strip()
        return (
            f"window_hint={window_hint};"
            f"window_title={window_title};"
            f"bridge_endpoint={endpoint};"
            f"bridge_available={bridge_available};"
            f"backoff_remaining={backoff_remaining:.2f}s"
        )

    def _on_click(self, x: int, y: int, _button: Any, pressed: bool) -> None:
        if not self._recording:
            return

        if pressed:
            self._mouse_down_point = (x, y)
            self._mouse_down_unix_ms = int(time.time() * 1000)
            return

        start_point = self._mouse_down_point
        self._mouse_down_point = None
        start_mouse_down_unix_ms = self._mouse_down_unix_ms
        self._mouse_down_unix_ms = None
        if start_point is None:
            return

        perf_sample: dict[str, Any] | None = None
        perf_start_ns = 0
        perf_enabled = self._record_perf_enabled
        if perf_enabled:
            perf_start_ns = time.perf_counter_ns()
            start_x, start_y = start_point
            perf_sample = {
                "session_id": self._record_perf_session_id,
                "event": "click_release",
                "unix_ms": int(time.time() * 1000),
                "window_hint": self._window_hint,
                "x": x,
                "y": y,
                "start_x": start_x,
                "start_y": start_y,
                "mouse_down_unix_ms": start_mouse_down_unix_ms,
            }

        def _finalize_perf(result: str) -> None:
            if perf_sample is None:
                return
            perf_sample["result"] = result
            perf_sample["total_ms"] = (time.perf_counter_ns() - perf_start_ns) / 1e6
            self._add_record_perf_sample(perf_sample)

        snapshot_started_ns: int | None = None
        if perf_sample is not None:
            snapshot_started_ns = time.perf_counter_ns()
        snapshot = self._window_provider()
        if perf_sample is not None and snapshot_started_ns is not None:
            perf_sample["t_window_provider_ms"] = (
                time.perf_counter_ns() - snapshot_started_ns
            ) / 1e6
        if not self._window_matches(snapshot):
            if perf_sample is not None:
                perf_sample["window_matches"] = False
            _finalize_perf("ignored_window_mismatch")
            return
        if perf_sample is not None:
            perf_sample["window_matches"] = True
        assert snapshot is not None

        start_x, start_y = start_point
        distance = abs(start_x - x) + abs(start_y - y)
        if perf_sample is not None:
            perf_sample["distance"] = distance
        if distance >= 10:
            source_started_ns: int | None = None
            if perf_sample is not None:
                source_started_ns = time.perf_counter_ns()
            source_selector = self._element_resolver(start_x, start_y)
            if perf_sample is not None and source_started_ns is not None:
                perf_sample["t_source_element_resolver_ms"] = (
                    time.perf_counter_ns() - source_started_ns
                ) / 1e6

            target_started_ns: int | None = None
            if perf_sample is not None:
                target_started_ns = time.perf_counter_ns()
            target_selector = self._element_resolver(x, y)
            if perf_sample is not None and target_started_ns is not None:
                perf_sample["t_target_element_resolver_ms"] = (
                    time.perf_counter_ns() - target_started_ns
                ) / 1e6
            if source_selector is None or target_selector is None:
                self._report_record_error(
                    "Could not resolve UI element selector for drag source/target."
                )
                _finalize_perf("error_drag_selector_missing")
                return
            source_is_generic = _is_generic_unity_hierarchy_pane(source_selector)
            target_is_generic = _is_generic_unity_hierarchy_pane(target_selector)
            if source_is_generic or target_is_generic:
                self._report_record_error(
                    "Could not resolve reliable drag selector in Unity hierarchy pane."
                )
                _finalize_perf("error_drag_in_hierarchy_pane")
                return
            if not (source_selector.get("title") or source_selector.get("automation_id")):
                self._report_record_error(
                    "Drag source element needs title or automation_id for reliable execution."
                )
                _finalize_perf("error_drag_source_missing_keys")
                return
            if not (target_selector.get("title") or target_selector.get("automation_id")):
                self._report_record_error(
                    "Drag target element needs title or automation_id for reliable execution."
                )
                _finalize_perf("error_drag_target_missing_keys")
                return
            payload: dict[str, Any] = {}
            source_title = str(source_selector.get("title") or "").strip()
            if source_title:
                payload["source_title"] = source_title
            source_automation_id = str(source_selector.get("automation_id") or "").strip()
            if source_automation_id:
                payload["source_automation_id"] = source_automation_id
            target_title = str(target_selector.get("title") or "").strip()
            if target_title:
                payload["target_title"] = target_title
            target_automation_id = str(target_selector.get("automation_id") or "").strip()
            if target_automation_id:
                payload["target_automation_id"] = target_automation_id
            self.append(
                "drag",
                payload,
            )
            _finalize_perf("recorded_drag")
            return

        selector_started_ns: int | None = None
        if perf_sample is not None:
            selector_started_ns = time.perf_counter_ns()
        selector = self._element_resolver(x, y)
        if perf_sample is not None and selector_started_ns is not None:
            perf_sample["t_element_resolver_ms"] = (
                time.perf_counter_ns() - selector_started_ns
            ) / 1e6
        if selector is None:
            self._report_record_error("Could not resolve UI element selector for click.")
            _finalize_perf("error_click_selector_missing")
            return
        is_hierarchy_pane = _is_generic_unity_hierarchy_pane(selector)
        if perf_sample is not None:
            perf_sample["is_hierarchy_pane"] = is_hierarchy_pane
        if is_hierarchy_pane:
            hierarchy_started_ns: int | None = None
            if perf_sample is not None:
                hierarchy_started_ns = time.perf_counter_ns()
            hierarchy_path = self._resolve_hierarchy_path(
                snapshot,
                mouse_down_unix_ms=start_mouse_down_unix_ms,
                perf_sample=perf_sample,
            )
            if perf_sample is not None and hierarchy_started_ns is not None:
                perf_sample["t_resolve_hierarchy_path_ms"] = (
                    time.perf_counter_ns() - hierarchy_started_ns
                ) / 1e6
            if hierarchy_path is None:
                now = time.monotonic()
                if now >= self._hierarchy_error_suppress_until:
                    message = (
                        "Could not resolve hierarchy path from Unity bridge for hierarchy click."
                    )
                    diagnostics = str(self._last_hierarchy_bridge_diag or "").strip()
                    if diagnostics:
                        message = f"{message} {diagnostics}"
                    self._report_record_error(message)
                    self._hierarchy_error_suppress_until = (
                        now + HIERARCHY_BRIDGE_ERROR_SUPPRESS_SECONDS
                    )
                _finalize_perf("error_hierarchy_path_unresolved")
                return
            self.append(
                "click",
                {
                    "hierarchy_path": hierarchy_path,
                    "target": _build_hierarchy_target_with_fallbacks(hierarchy_path),
                },
            )
            _finalize_perf("recorded_click_hierarchy")
            return
        payload = dict(selector)
        payload["target"] = _build_uia_target_with_fallbacks(selector)
        self.append(
            "click",
            payload,
        )
        _finalize_perf("recorded_click_uia")

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if not self._recording or key is None:
            return
        name = self._key_to_name(key)
        if name in {"CTRL", "ALT", "SHIFT"}:
            self._modifier_keys.add(name)
            return

        if name == self._stop_hotkey_main_key and self._stop_hotkey_required_modifiers.issubset(
            self._modifier_keys
        ):
            if self._on_stop_hotkey is not None:
                self._on_stop_hotkey()
            return

        if "CTRL" in self._modifier_keys:
            shortcut = f"CTRL+{name}"
            self.append("shortcut", {"shortcut": shortcut})

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        name = self._key_to_name(key)
        self._modifier_keys.discard(name)

    @staticmethod
    def _key_to_name(key: keyboard.Key | keyboard.KeyCode) -> str:
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.upper()
            return "UNKNOWN"
        value = str(key).replace("Key.", "").upper()
        if value == "CTRL_L" or value == "CTRL_R":
            return "CTRL"
        if value in {"ALT_L", "ALT_R", "ALT_GR"}:
            return "ALT"
        if value in {"SHIFT", "SHIFT_L", "SHIFT_R"}:
            return "SHIFT"
        return value
