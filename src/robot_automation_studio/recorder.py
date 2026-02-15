"""Input recording helpers and event-to-step conversion."""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import win32gui  # type: ignore[import-not-found]
from pynput import keyboard, mouse

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


def normalize_point(x: int, y: int, window: WindowSnapshot) -> tuple[float, float]:
    if window.width <= 0 or window.height <= 0:
        return (0.5, 0.5)
    x_ratio = (x - window.left) / window.width
    y_ratio = (y - window.top) / window.height
    return (max(0.0, min(1.0, x_ratio)), max(0.0, min(1.0, y_ratio)))


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


def events_to_steps(events: list[RecordedEvent], auto_wait_threshold_ms: int = 0) -> list[Step]:
    steps: list[Step] = []
    previous_ts: int | None = None
    for event in events:
        if previous_ts is not None and auto_wait_threshold_ms > 0:
            diff_ms = event.timestamp_ms - previous_ts
            if diff_ms >= auto_wait_threshold_ms:
                seconds = round(diff_ms / 1000, 2)
                steps.append(Step(action="wait", title="wait", params={"seconds": seconds}))
        previous_ts = event.timestamp_ms

        if event.kind == "click":
            steps.append(Step(action="click", title="click", params=dict(event.payload)))
            continue
        if event.kind == "drag":
            steps.append(Step(action="drag", title="drag", params=dict(event.payload)))
            continue
        if event.kind == "wait":
            steps.append(Step(action="wait", title="wait", params=dict(event.payload)))
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
    ) -> None:
        if platform.system().lower() != "windows":
            raise RuntimeError("ScenarioRecorder supports Windows only.")
        self._events: list[RecordedEvent] = []
        self._recording = False
        self._window_provider = window_provider
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

    def _window_matches(self, snapshot: WindowSnapshot | None) -> bool:
        if snapshot is None:
            return False
        if not self._window_hint:
            return True
        return self._window_hint.lower() in snapshot.title.lower()

    def _on_click(self, x: int, y: int, _button: Any, pressed: bool) -> None:
        if not self._recording:
            return
        snapshot = self._window_provider()
        if not self._window_matches(snapshot):
            return
        assert snapshot is not None

        if pressed:
            self._mouse_down_point = (x, y)
            return

        if self._mouse_down_point is None:
            return
        start_x, start_y = self._mouse_down_point
        self._mouse_down_point = None
        from_x_ratio, from_y_ratio = normalize_point(start_x, start_y, snapshot)
        to_x_ratio, to_y_ratio = normalize_point(x, y, snapshot)
        distance = abs(start_x - x) + abs(start_y - y)
        if distance >= 10:
            self.append(
                "drag",
                {
                    "from_x_ratio": round(from_x_ratio, 4),
                    "from_y_ratio": round(from_y_ratio, 4),
                    "to_x_ratio": round(to_x_ratio, 4),
                    "to_y_ratio": round(to_y_ratio, 4),
                },
            )
            return

        self.append(
            "click",
            {
                "x_ratio": round(to_x_ratio, 4),
                "y_ratio": round(to_y_ratio, 4),
                "box_width": 180,
                "box_height": 48,
            },
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
