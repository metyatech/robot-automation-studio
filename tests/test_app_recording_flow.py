from pathlib import Path

from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.models import Step


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_start_recording_updates_recording_ui(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        overlay_call: dict[str, str] = {}

        monkeypatch.setattr(
            "robot_automation_studio.recorder.has_visible_window_with_hint",
            lambda window_hint: True,
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(
            studio,
            "_start_overlay",
            lambda mode, progress_text: overlay_call.update(
                {"mode": str(mode), "progress_text": progress_text}
            ),
        )
        monkeypatch.setattr(
            studio.recorder,
            "start",
            lambda window_hint: setattr(studio.recorder, "_recording", True),
        )

        studio.start_recording()

        assert studio.recorder.is_recording is True
        assert overlay_call["mode"] == "recording"
        assert overlay_call["progress_text"] == "Recording"
        assert "REC" in studio._rec_indicator.text()
    finally:
        studio.recorder._recording = False
        studio.close()


def test_start_recording_attach_mode_fails_without_target_window(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        ensure_calls = {"count": 0}
        critical_calls = {"count": 0}

        monkeypatch.setattr(
            "robot_automation_studio.recorder.has_visible_window_with_hint",
            lambda window_hint: False,
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: ensure_calls.__setitem__("count", ensure_calls["count"] + 1) or True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )

        studio.start_recording()

        assert ensure_calls["count"] == 0
        assert critical_calls["count"] == 1
        assert studio.recorder.is_recording is False
    finally:
        studio.close()


def test_stop_recording_appends_steps_and_restores_idle_ui(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        stop_overlay_calls = {"count": 0}
        stop_hotkey_calls = {"count": 0}

        def _fake_stop() -> list[object]:
            studio.recorder._recording = False
            return [object()]

        monkeypatch.setattr(studio.recorder, "stop", _fake_stop)
        monkeypatch.setattr(
            "robot_automation_studio.recorder.events_to_steps",
            lambda events: [
                Step(action="click", params={"x_ratio": 0.1, "y_ratio": 0.2}),
                Step(action="type_text", params={"text": "sample"}),
            ],
        )
        monkeypatch.setattr(studio, "_is_robot_running", lambda: False)
        monkeypatch.setattr(
            studio,
            "_stop_overlay",
            lambda: stop_overlay_calls.__setitem__("count", stop_overlay_calls["count"] + 1),
        )
        monkeypatch.setattr(
            studio,
            "_stop_stop_hotkey",
            lambda: stop_hotkey_calls.__setitem__("count", stop_hotkey_calls["count"] + 1),
        )
        studio.recorder._recording = True

        studio.stop_recording()

        assert studio.recorder.is_recording is False
        assert len(studio.scenario.steps) == 2
        assert stop_overlay_calls["count"] == 1
        assert stop_hotkey_calls["count"] == 1
        assert studio._rec_indicator.text().strip() == "IDLE"
    finally:
        studio.recorder._recording = False
        studio.close()


def test_toggle_log_collapse_hides_and_restores_log_panel(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert studio.log_text_container.isHidden() is False
        assert studio._log_toggle_button.text() == "▼"

        studio._toggle_log_collapse()
        assert studio.log_text_container.isHidden() is True
        assert studio._log_toggle_button.text() == "▲"

        studio._toggle_log_collapse()
        assert studio.log_text_container.isHidden() is False
        assert studio._log_toggle_button.text() == "▼"
    finally:
        studio.close()
