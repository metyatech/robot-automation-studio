from pathlib import Path

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


def test_record_error_persists_diagnostic_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.output_dir_edit.setText(str(tmp_path / "artifacts" / "studio"))
        studio._on_record_error(
            "Could not resolve hierarchy path from Unity bridge for hierarchy click."
        )
        _process_events_for(120)

        diagnostics_path = (
            tmp_path / "artifacts" / "studio" / "diagnostics" / "bridge-recording.log"
        )
        assert diagnostics_path.exists()
        assert "Could not resolve hierarchy path from Unity bridge for hierarchy click." in (
            diagnostics_path.read_text(encoding="utf-8")
        )
    finally:
        studio.close()
