"""Input recording helpers and event-to-step conversion."""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import win32gui  # type: ignore[import-not-found]
from pynput import keyboard, mouse
from pywinauto import Desktop

from .models import Step


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
            steps.append(Step(action="click", title="click", params=dict(event.payload)))
            continue
        if event.kind == "drag":
            steps.append(Step(action="drag", title="drag", params=dict(event.payload)))
            continue
        if event.kind == "shortcut":
            steps.append(Step(action="shortcut", title="shortcut", params=dict(event.payload)))
            continue
        steps.append(
            Step(action="unknown", title=f"unknown:{event.kind}", params=dict(event.payload))
        )
    return steps


class ScenarioRecorder:
    """Simple in-memory recorder with explicit event append API."""

    def __init__(
        self,
        window_provider: Callable[[], WindowSnapshot | None] = get_foreground_window_snapshot,
        element_resolver: Callable[[int, int], dict[str, Any] | None] = resolve_selector_from_point,
        on_record_error: Callable[[str], None] | None = None,
    ) -> None:
        if platform.system().lower() != "windows":
            raise RuntimeError("ScenarioRecorder supports Windows only.")
        self._events: list[RecordedEvent] = []
        self._recording = False
        self._window_provider = window_provider
        self._element_resolver = element_resolver
        self._on_record_error = on_record_error
        self._window_hint = "Unity"
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_down_point: tuple[int, int] | None = None
        self._modifier_keys: set[str] = set()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, window_hint: str = "Unity") -> None:
        self._events.clear()
        self._recording = True
        self._window_hint = window_hint
        self._mouse_down_point = None
        self._modifier_keys.clear()
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
        self._modifier_keys.clear()
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
        if not self._window_hint:
            return True
        return self._window_hint.lower() in snapshot.title.lower()

    def _on_click(self, x: int, y: int, _button: Any, pressed: bool) -> None:
        if not self._recording:
            return

        if pressed:
            self._mouse_down_point = (x, y)
            return

        start_point = self._mouse_down_point
        self._mouse_down_point = None
        if start_point is None:
            return
        snapshot = self._window_provider()
        if not self._window_matches(snapshot):
            return
        assert snapshot is not None

        start_x, start_y = start_point
        distance = abs(start_x - x) + abs(start_y - y)
        if distance >= 10:
            source_selector = self._element_resolver(start_x, start_y)
            target_selector = self._element_resolver(x, y)
            if source_selector is None or target_selector is None:
                self._report_record_error(
                    "Could not resolve UI element selector for drag source/target."
                )
                return
            if not (source_selector.get("title") or source_selector.get("automation_id")):
                self._report_record_error(
                    "Drag source element needs title or automation_id for reliable execution."
                )
                return
            if not (target_selector.get("title") or target_selector.get("automation_id")):
                self._report_record_error(
                    "Drag target element needs title or automation_id for reliable execution."
                )
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
            return

        selector = self._element_resolver(x, y)
        if selector is None:
            self._report_record_error("Could not resolve UI element selector for click.")
            return
        self.append(
            "click",
            dict(selector),
        )

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if not self._recording or key is None:
            return
        name = self._key_to_name(key)
        if name in {"CTRL", "ALT", "SHIFT"}:
            self._modifier_keys.add(name)
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
        if value == "ALT_L" or value == "ALT_GR":
            return "ALT"
        if value == "SHIFT":
            return "SHIFT"
        return value
