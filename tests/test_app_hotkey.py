import threading

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp


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
