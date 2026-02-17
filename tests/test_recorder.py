import json
import threading
import time

from pynput import keyboard

from robot_automation_studio.models import Step
from robot_automation_studio.recorder import (
    RecordedEvent,
    ScenarioRecorder,
    WindowSnapshot,
    events_to_steps,
    has_visible_window_with_hint,
)


def test_events_to_steps_maps_mouse_and_keyboard_events() -> None:
    events = [
        RecordedEvent(
            kind="click",
            payload={
                "title": "Inspector",
                "automation_id": "Inspector",
                "class_name": "Pane",
                "control_type": "Pane",
            },
            timestamp_ms=1000,
        ),
        RecordedEvent(
            kind="drag",
            payload={
                "source_title": "TailLength",
                "source_automation_id": "TailLength",
                "target_title": "PreviewArea",
                "target_automation_id": "PreviewArea",
            },
            timestamp_ms=1500,
        ),
        RecordedEvent(kind="shortcut", payload={"shortcut": "CTRL+S"}, timestamp_ms=3000),
    ]

    steps = events_to_steps(events)

    assert len(steps) == 3
    assert isinstance(steps[0], Step)
    assert steps[0].action == "click"
    assert steps[1].action == "drag_drop"
    assert steps[2].action == "press_keys"
    assert steps[2].params["shortcut"] == "CTRL+S"


def test_recorder_does_not_insert_implicit_step_between_actions() -> None:
    recorder = ScenarioRecorder()
    recorder.start()
    recorder.append_with_timestamp(
        "click",
        {"title": "A", "automation_id": "A", "class_name": "Button", "control_type": "Button"},
        timestamp_ms=1000,
    )
    recorder.append_with_timestamp(
        "click",
        {"title": "B", "automation_id": "B", "class_name": "Button", "control_type": "Button"},
        timestamp_ms=2800,
    )
    events = recorder.stop()
    steps = events_to_steps(events)

    assert [step.action for step in steps] == ["click", "click"]


def test_recorder_click_and_drag_record_element_selectors() -> None:
    selector_by_point = {
        (100, 120): {
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        },
        (200, 220): {
            "title": "Source",
            "automation_id": "Source",
            "class_name": "Slider",
            "control_type": "Slider",
        },
        (450, 470): {
            "title": "Target",
            "automation_id": "Target",
            "class_name": "Pane",
            "control_type": "Pane",
        },
    }
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda x, y: dict(selector_by_point[(x, y)]),
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 120, None, True)
    recorder._on_click(100, 120, None, False)
    recorder._on_click(200, 220, None, True)
    recorder._on_click(450, 470, None, False)
    events = recorder.stop()

    steps = events_to_steps(events)
    assert [step.action for step in steps] == ["click", "drag_drop"]
    assert steps[0].params["automation_id"] == "MainMenuFile"
    assert steps[1].params["input"]["source"]["uia"]["automation_id"] == "Source"
    assert steps[1].params["target"]["uia"]["automation_id"] == "Target"


def test_recorder_click_records_uia_target_with_fallbacks() -> None:
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        },
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 120, None, True)
    recorder._on_click(100, 120, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    target = steps[0].params["target"]
    assert target["strategy"] == "uia"
    assert target["uia"]["automation_id"] == "MainMenuFile"
    fallbacks = list(target.get("fallbacks") or [])
    assert len(fallbacks) >= 2
    assert any(
        str((candidate.get("uia") or {}).get("automation_id") or "") == "MainMenuFile"
        for candidate in fallbacks
        if isinstance(candidate, dict)
    )
    coordinate_fallbacks = [
        candidate
        for candidate in fallbacks
        if isinstance(candidate, dict) and str(candidate.get("strategy") or "") == "coordinate"
    ]
    assert len(coordinate_fallbacks) == 1
    coordinate = coordinate_fallbacks[0]["coordinate"]
    assert coordinate["x_ratio"] == 0.1
    assert coordinate["y_ratio"] == 0.15
    assert coordinate["anchor_window_hint"] == "Unity"


def test_recorder_drag_records_selector_objects_with_coordinate_fallbacks() -> None:
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda x, y: (
            {
                "title": "Source",
                "automation_id": "Source",
                "class_name": "Button",
                "control_type": "Button",
            }
            if (x, y) == (250, 200)
            else {
                "title": "Target",
                "automation_id": "Target",
                "class_name": "Pane",
                "control_type": "Pane",
            }
        ),
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(250, 200, None, True)
    recorder._on_click(750, 600, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].action == "drag_drop"
    source = steps[0].params["input"]["source"]
    target = steps[0].params["target"]
    assert source["strategy"] == "uia"
    assert target["strategy"] == "uia"
    assert source["uia"]["automation_id"] == "Source"
    assert target["uia"]["automation_id"] == "Target"
    source_fallbacks = list(source.get("fallbacks") or [])
    target_fallbacks = list(target.get("fallbacks") or [])
    assert any(
        isinstance(candidate, dict) and str(candidate.get("strategy") or "") == "coordinate"
        for candidate in source_fallbacks
    )
    assert any(
        isinstance(candidate, dict) and str(candidate.get("strategy") or "") == "coordinate"
        for candidate in target_fallbacks
    )


def test_click_is_recorded_when_press_unfocused_and_release_focused() -> None:
    snapshots = iter(
        [
            WindowSnapshot(title="Unity", left=0, top=0, width=1000, height=800),
        ]
    )
    recorder = ScenarioRecorder(
        window_provider=lambda: next(snapshots),
        element_resolver=lambda _x, _y: {
            "title": "Inspector",
            "automation_id": "Inspector",
            "class_name": "Pane",
            "control_type": "Pane",
        },
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(300, 200, None, True)
    recorder._on_click(300, 200, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].action == "click"


def test_unfocused_release_does_not_carry_state_into_next_click() -> None:
    snapshots = iter(
        [
            WindowSnapshot(title="Other App", left=0, top=0, width=1000, height=800),
            WindowSnapshot(title="Unity", left=0, top=0, width=1000, height=800),
        ]
    )
    recorder = ScenarioRecorder(
        window_provider=lambda: next(snapshots),
        element_resolver=lambda _x, _y: {
            "title": "Inspector",
            "automation_id": "Inspector",
            "class_name": "Pane",
            "control_type": "Pane",
        },
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 100, None, True)
    recorder._on_click(160, 160, None, False)
    recorder._on_click(220, 220, None, True)
    recorder._on_click(220, 220, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].action == "click"


def test_recorder_reports_error_when_selector_cannot_be_resolved() -> None:
    errors: list[str] = []
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: None,
        on_record_error=errors.append,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 120, None, True)
    recorder._on_click(100, 120, None, False)
    events = recorder.stop()

    assert len(events) == 0
    assert len(errors) == 1
    assert "Could not resolve UI element selector" in errors[0]


def test_recorder_uses_bridge_for_unity_hierarchy_pane() -> None:
    class DummyBridge:
        def get_selected_hierarchy_path(self) -> str | None:
            return "AvatarRoot/Hair/Tail"

    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=DummyBridge(),
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].action == "click"
    assert steps[0].params["hierarchy_path"] == "AvatarRoot/Hair/Tail"


def test_recorder_hierarchy_click_records_wildcard_root_fallback_path() -> None:
    class DummyBridge:
        def get_selected_hierarchy_path(self) -> str | None:
            return "AvatarRoot/Hair/Tail"

    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=DummyBridge(),
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    target = steps[0].params["target"]
    assert target["strategy"] == "unity_hierarchy"
    assert target["unity_hierarchy"]["path"] == "AvatarRoot/Hair/Tail"
    fallbacks = list(target.get("fallbacks") or [])
    assert len(fallbacks) >= 1
    assert any(
        str((candidate.get("unity_hierarchy") or {}).get("path") or "") == "*/Hair/Tail"
        for candidate in fallbacks
        if isinstance(candidate, dict)
    )


def test_recorder_hierarchy_click_waits_for_selection_update_when_bridge_supports_wait() -> None:
    class LaggyBridge:
        def __init__(self) -> None:
            self.version = 10
            self.path = "ComeBody_Armature"

        def get_selected_hierarchy_path(self) -> str | None:
            # Legacy behavior: returns the previous selection.
            return self.path

        def get_selection_state(self) -> dict[str, object]:
            return {"ok": True, "hierarchy_path": self.path, "selection_version": self.version}

        def wait_for_selection_change(
            self, after_version: int, timeout_seconds: float | None = None
        ) -> dict[str, object]:
            _ = timeout_seconds
            if after_version >= self.version:
                self.version = after_version + 1
            self.path = "Main Camera"
            return {"ok": True, "hierarchy_path": self.path, "selection_version": self.version}

    bridge = LaggyBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].params["hierarchy_path"] == "Main Camera"


def test_recorder_hierarchy_click_skips_wait_when_selection_changed_after_mouse_down() -> None:
    class NoWaitBridge:
        def __init__(self) -> None:
            self.wait_called = 0

        def get_selection_state(self) -> dict[str, object]:
            return {
                "ok": True,
                "hierarchy_path": "Main Camera",
                "selection_version": 11,
                "selection_changed_unix_ms": int(time.time() * 1000),
            }

        def wait_for_selection_change(
            self, after_version: int, timeout_seconds: float | None = None
        ):
            _ = after_version
            _ = timeout_seconds
            self.wait_called += 1
            return {"ok": False}

    bridge = NoWaitBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].params["hierarchy_path"] == "Main Camera"
    assert bridge.wait_called == 0


def test_recorder_hierarchy_click_does_not_query_selection_state_on_mouse_down() -> None:
    class CountingBridge:
        def __init__(self) -> None:
            self.selection_state_calls = 0

        def get_selection_state(self) -> dict[str, object]:
            self.selection_state_calls += 1
            return {
                "ok": True,
                "hierarchy_path": "Main Camera",
                "selection_version": 11,
                "selection_changed_unix_ms": int(time.time() * 1000),
            }

    bridge = CountingBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    assert bridge.selection_state_calls == 0
    recorder.stop()


def test_recording_perf_disabled_does_not_write_log(tmp_path, monkeypatch) -> None:
    perf_path = tmp_path / "recording-perf.jsonl"
    monkeypatch.delenv("RAS_RECORD_PERF", raising=False)
    monkeypatch.setenv("RAS_RECORD_PERF_PATH", str(perf_path))

    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        },
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    recorder.stop()

    assert not perf_path.exists()


def test_recording_perf_enabled_writes_jsonl(tmp_path, monkeypatch) -> None:
    perf_path = tmp_path / "recording-perf.jsonl"
    monkeypatch.setenv("RAS_RECORD_PERF", "1")
    monkeypatch.setenv("RAS_RECORD_PERF_PATH", str(perf_path))

    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        },
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    recorder.stop()

    raw = perf_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line.strip() != ""]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "click_release"


def test_recorder_click_does_not_block_on_element_resolver() -> None:
    resolver_started = threading.Event()
    allow_resolver = threading.Event()

    def _blocking_resolver(_x: int, _y: int) -> dict[str, object]:
        resolver_started.set()
        allow_resolver.wait(timeout=5.0)
        return {
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        }

    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="TestWindow",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=_blocking_resolver,
    )
    recorder.start(window_hint="TestWindow")
    recorder._on_click(120, 180, None, True)

    release_thread = threading.Thread(
        target=lambda: recorder._on_click(120, 180, None, False),
        daemon=True,
    )
    release_thread.start()
    release_thread.join(timeout=0.2)
    if release_thread.is_alive():
        allow_resolver.set()
        release_thread.join(timeout=5.0)
        recorder.stop()
        raise AssertionError("_on_click release must not block on element resolver")

    assert resolver_started.wait(timeout=2.0)
    allow_resolver.set()
    steps = events_to_steps(recorder.stop())
    assert [step.action for step in steps] == ["click"]


def test_recorder_hierarchy_click_does_not_block_on_bridge_wait() -> None:
    wait_started = threading.Event()
    allow_wait = threading.Event()

    class BlockingBridge:
        def __init__(self) -> None:
            self.version = 10
            self.path = "ComeBody_Armature"

        def get_selected_hierarchy_path(self) -> str | None:
            return self.path

        def get_selection_state(self) -> dict[str, object]:
            return {
                "ok": True,
                "hierarchy_path": self.path,
                "selection_version": self.version,
                "selection_changed_unix_ms": 0,
            }

        def wait_for_selection_change(
            self, after_version: int, timeout_seconds: float | None = None
        ) -> dict[str, object]:
            _ = after_version
            _ = timeout_seconds
            wait_started.set()
            allow_wait.wait(timeout=5.0)
            self.version += 1
            self.path = "Main Camera"
            return {
                "ok": True,
                "hierarchy_path": self.path,
                "selection_version": self.version,
            }

    bridge = BlockingBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="TestWindow",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
    )
    recorder.start(window_hint="TestWindow")
    recorder._on_click(120, 180, None, True)

    release_thread = threading.Thread(
        target=lambda: recorder._on_click(120, 180, None, False),
        daemon=True,
    )
    release_thread.start()
    release_thread.join(timeout=0.2)
    if release_thread.is_alive():
        allow_wait.set()
        release_thread.join(timeout=5.0)
        recorder.stop()
        raise AssertionError("_on_click release must not block on bridge wait")

    assert wait_started.wait(timeout=2.0)
    allow_wait.set()
    steps = events_to_steps(recorder.stop())
    assert [step.action for step in steps] == ["click"]
    assert steps[0].params["hierarchy_path"] == "Main Camera"


def test_has_visible_window_with_hint_true_when_matching_title_exists() -> None:
    assert has_visible_window_with_hint(
        "Unity",
        window_titles=["Visual Studio Code", "Unity 2022.3 - Sample Project"],
    )


def test_has_visible_window_with_hint_false_when_no_match() -> None:
    assert not has_visible_window_with_hint(
        "Unity",
        window_titles=["Visual Studio Code", "Terminal"],
    )


def test_recorder_does_not_record_stop_hotkey_shortcut() -> None:
    recorder = ScenarioRecorder()
    recorder.start(window_hint="Unity")
    recorder._on_key_press(keyboard.Key.alt_l)
    recorder._on_key_press(keyboard.Key.shift)
    recorder._on_key_press(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.shift)
    recorder._on_key_release(keyboard.Key.alt_l)

    steps = events_to_steps(recorder.stop())

    assert steps == []


def test_recorder_invokes_stop_hotkey_callback() -> None:
    callback_count = 0

    def _on_stop_hotkey() -> None:
        nonlocal callback_count
        callback_count += 1

    recorder = ScenarioRecorder(on_stop_hotkey=_on_stop_hotkey)
    recorder.start(window_hint="Unity")
    recorder._on_key_press(keyboard.Key.alt_l)
    recorder._on_key_press(keyboard.Key.shift)
    recorder._on_key_press(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.shift)
    recorder._on_key_release(keyboard.Key.alt_l)

    steps = events_to_steps(recorder.stop())

    assert callback_count == 1
    assert steps == []


def test_recorder_stop_hotkey_callback_supports_right_side_modifiers() -> None:
    callback_count = 0

    def _on_stop_hotkey() -> None:
        nonlocal callback_count
        callback_count += 1

    recorder = ScenarioRecorder(on_stop_hotkey=_on_stop_hotkey)
    recorder.start(window_hint="Unity")
    recorder._on_key_press(keyboard.Key.alt_r)
    recorder._on_key_press(keyboard.Key.shift_r)
    recorder._on_key_press(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.f12)
    recorder._on_key_release(keyboard.Key.shift_r)
    recorder._on_key_release(keyboard.Key.alt_r)

    steps = events_to_steps(recorder.stop())

    assert callback_count == 1
    assert steps == []


def test_recorder_retries_bridge_lookup_for_hierarchy_click() -> None:
    class FlakyBridge:
        def __init__(self) -> None:
            self.calls = 0

        def get_selected_hierarchy_path(self) -> str | None:
            self.calls += 1
            if self.calls == 1:
                return None
            return "AvatarRoot/Hair/Tail"

    bridge = FlakyBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].params["hierarchy_path"] == "AvatarRoot/Hair/Tail"


def test_recorder_reports_hierarchy_bridge_error_once_during_backoff() -> None:
    class MissingBridge:
        def __init__(self) -> None:
            self.calls = 0

        def get_selected_hierarchy_path(self) -> str | None:
            self.calls += 1
            return None

    errors: list[str] = []
    bridge = MissingBridge()
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=bridge,
        on_record_error=errors.append,
    )
    recorder.start(window_hint="Unity")
    for _ in range(3):
        recorder._on_click(120, 180, None, True)
        recorder._on_click(120, 180, None, False)
    recorder.stop()

    assert len(errors) == 1


def test_recorder_hierarchy_bridge_error_includes_diagnostics() -> None:
    class MissingBridge:
        endpoint = "http://127.0.0.1:39067"

        def get_selected_hierarchy_path(self) -> str | None:
            return None

        def is_available(self, request_timeout_seconds: float | None = None) -> bool:
            _ = request_timeout_seconds
            return False

    errors: list[str] = []
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        ),
        element_resolver=lambda _x, _y: {
            "title": "UnityEditor.SceneHierarchyWindow",
            "class_name": "UnityGUIViewWndClass",
            "control_type": "Pane",
        },
        unity_bridge=MissingBridge(),
        on_record_error=errors.append,
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(120, 180, None, True)
    recorder._on_click(120, 180, None, False)
    recorder.stop()

    assert len(errors) == 1
    assert "Could not resolve hierarchy path via Unity bridge (hierarchy click)." in errors[0]
    assert "bridge_endpoint=http://127.0.0.1:39067" in errors[0]
    assert "bridge_available=False" in errors[0]
    assert "window_title=Unity" in errors[0]
