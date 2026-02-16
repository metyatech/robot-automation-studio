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
    assert steps[1].params["source_automation_id"] == "Source"
    assert steps[1].params["target_automation_id"] == "Target"


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
