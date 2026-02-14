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

    assert len(steps) == 4
    assert isinstance(steps[0], Step)
    assert steps[0].action == "click"
    assert steps[1].action == "drag"
    assert steps[2].params["seconds"] == 1.2
    assert steps[3].params["shortcut"] == "CTRL+S"


def test_normalize_point_uses_window_rect() -> None:
    window = WindowSnapshot(title="Unity", left=100, top=200, width=1000, height=800)
    x_ratio, y_ratio = normalize_point(600, 600, window)
    assert round(x_ratio, 2) == 0.5
    assert round(y_ratio, 2) == 0.5


def test_recorder_inserts_wait_between_actions() -> None:
    recorder = ScenarioRecorder()
    recorder.start()
    recorder.append_with_timestamp("click", {"x_ratio": 0.1, "y_ratio": 0.2}, timestamp_ms=1000)
    recorder.append_with_timestamp("click", {"x_ratio": 0.2, "y_ratio": 0.3}, timestamp_ms=2800)
    events = recorder.stop()
    steps = events_to_steps(events, auto_wait_threshold_ms=500)

    assert [step.action for step in steps] == ["click", "wait", "click"]
    assert steps[1].params["seconds"] == 1.8
