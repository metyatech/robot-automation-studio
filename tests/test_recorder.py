from robot_automation_studio.models import Step
from robot_automation_studio.recorder import (
    RecordedEvent,
    ScenarioRecorder,
    WindowSnapshot,
    events_to_steps,
    normalize_point,
)


def test_events_to_steps_maps_mouse_and_keyboard_events() -> None:
    events = [
        RecordedEvent(kind="click", payload={"x_ratio": 0.1, "y_ratio": 0.2}, timestamp_ms=1000),
        RecordedEvent(
            kind="drag",
            payload={
                "from_x_ratio": 0.2,
                "from_y_ratio": 0.3,
                "to_x_ratio": 0.5,
                "to_y_ratio": 0.6,
            },
            timestamp_ms=1500,
        ),
        RecordedEvent(kind="wait", payload={"seconds": 1.2}, timestamp_ms=2800),
        RecordedEvent(kind="shortcut", payload={"shortcut": "CTRL+S"}, timestamp_ms=3000),
    ]

    steps = events_to_steps(events)

    assert len(steps) == 3
    assert isinstance(steps[0], Step)
    assert steps[0].action == "click"
    assert steps[1].action == "drag"
    assert steps[2].params["shortcut"] == "CTRL+S"


def test_normalize_point_uses_window_rect() -> None:
    window = WindowSnapshot(title="Unity", left=100, top=200, width=1000, height=800)
    x_ratio, y_ratio = normalize_point(600, 600, window)
    assert round(x_ratio, 2) == 0.5
    assert round(y_ratio, 2) == 0.5


def test_recorder_does_not_insert_wait_between_actions() -> None:
    recorder = ScenarioRecorder()
    recorder.start()
    recorder.append_with_timestamp("click", {"x_ratio": 0.1, "y_ratio": 0.2}, timestamp_ms=1000)
    recorder.append_with_timestamp("click", {"x_ratio": 0.2, "y_ratio": 0.3}, timestamp_ms=2800)
    events = recorder.stop()
    steps = events_to_steps(events)

    assert [step.action for step in steps] == ["click", "click"]


def test_recorder_click_and_drag_do_not_add_fixed_wait_seconds() -> None:
    recorder = ScenarioRecorder(
        window_provider=lambda: WindowSnapshot(
            title="Unity",
            left=0,
            top=0,
            width=1000,
            height=800,
        )
    )
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 120, None, True)
    recorder._on_click(100, 120, None, False)
    recorder._on_click(200, 220, None, True)
    recorder._on_click(450, 470, None, False)
    events = recorder.stop()

    steps = events_to_steps(events)
    assert [step.action for step in steps] == ["click", "drag"]
    assert "wait_seconds" not in steps[0].params
    assert "wait_seconds" not in steps[1].params


def test_click_is_recorded_when_press_unfocused_and_release_focused() -> None:
    snapshots = iter(
        [
            WindowSnapshot(title="Unity", left=0, top=0, width=1000, height=800),
        ]
    )
    recorder = ScenarioRecorder(window_provider=lambda: next(snapshots))
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
    recorder = ScenarioRecorder(window_provider=lambda: next(snapshots))
    recorder.start(window_hint="Unity")
    recorder._on_click(100, 100, None, True)
    recorder._on_click(160, 160, None, False)
    recorder._on_click(220, 220, None, True)
    recorder._on_click(220, 220, None, False)
    steps = events_to_steps(recorder.stop())

    assert len(steps) == 1
    assert steps[0].action == "click"
