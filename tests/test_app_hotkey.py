import threading

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.hotkey import parse_hotkey_label


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def _process_events_for(duration_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(duration_ms, loop.quit)
    loop.exec()


def test_recorder_stop_hotkey_request_from_worker_thread_stops_recording(
    monkeypatch,
) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        calls = {"count": 0}

        def _fake_stop_recording() -> None:
            calls["count"] += 1
            studio.recorder._recording = False  # keep state consistent for close

        monkeypatch.setattr(studio, "stop_recording", _fake_stop_recording)
        studio.recorder._recording = True

        worker = threading.Thread(target=studio._on_recorder_stop_hotkey)
        worker.start()
        worker.join()
        _process_events_for(100)

        assert calls["count"] == 1
    finally:
        studio.recorder._recording = False
        studio.close()


def test_automation_stop_request_from_overlay_stops_recording(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        calls = {"count": 0}

        def _fake_stop_recording() -> None:
            calls["count"] += 1
            studio.recorder._recording = False

        monkeypatch.setattr(studio, "stop_recording", _fake_stop_recording)
        studio.recorder._recording = True

        studio._on_automation_stop_requested("overlay_button")
        assert calls["count"] == 1
    finally:
        studio.recorder._recording = False
        studio.close()


class _FakeHotkeyListener:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_start_stop_hotkey_falls_back_when_primary_registration_fails(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._set_stop_hotkey_spec(parse_hotkey_label("Alt+Shift+F12"))
        fallback_listener = _FakeHotkeyListener()
        warning_calls = {"count": 0}

        def _fake_create_listener(bind: str, callback):
            _ = callback
            if bind == "<alt>+<shift>+<f12>":
                raise RuntimeError("already registered")
            return fallback_listener

        def _fake_warning(*args, **kwargs):
            _ = (args, kwargs)
            warning_calls["count"] += 1
            return 0

        monkeypatch.setattr(studio, "_create_global_hotkey_listener", _fake_create_listener)
        monkeypatch.setattr("robot_automation_studio.app.QMessageBox.warning", _fake_warning)

        started = studio._start_stop_hotkey()

        assert started is True
        assert fallback_listener.started is True
        assert studio._stop_hotkey_spec.label == "Ctrl+Shift+F12"
        assert warning_calls["count"] == 1
    finally:
        studio._stop_stop_hotkey()
        studio.close()
