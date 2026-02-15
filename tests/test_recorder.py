from robot_automation_studio.models import Step
from robot_automation_studio.recorder import (
    RecordedEvent,
    ScenarioRecorder,
    WindowSnapshot,
    events_to_steps,
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
    assert steps[1].action == "drag"
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
    assert [step.action for step in steps] == ["click", "drag"]
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
