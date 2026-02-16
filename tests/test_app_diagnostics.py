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
        diagnostics_path = (
            tmp_path / "artifacts" / "studio" / "diagnostics" / "bridge-recording.log"
        )
        timeout_ms = 5000
        poll_interval_ms = 50
        remaining_ms = timeout_ms
        while not diagnostics_path.exists() and remaining_ms > 0:
            _process_events_for(poll_interval_ms)
            remaining_ms -= poll_interval_ms

        assert diagnostics_path.exists()
        lines = diagnostics_path.read_text(encoding="utf-8").splitlines()
        assert lines
        assert "+00:00" in lines[-1]
        assert (
            "Could not resolve hierarchy path from Unity bridge for hierarchy click." in lines[-1]
        )
    finally:
        studio.close()


def test_record_error_persistence_failure_is_non_fatal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.output_dir_edit.setText(str(tmp_path / "artifacts" / "studio"))

        def _raise_oserror(*args, **kwargs):
            _ = (args, kwargs)
            raise OSError("disk full")

        monkeypatch.setattr(Path, "open", _raise_oserror)

        studio._on_record_error(
            "Could not resolve hierarchy path from Unity bridge for hierarchy click."
        )
        _process_events_for(100)

        log_text = studio.log_text.toPlainText()
        assert "[diagnostics]" in log_text
        assert "disk full" in log_text
    finally:
        studio.close()


def test_describe_subflow_logs_state_reports_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        text = studio._describe_subflow_logs_state(tmp_path / "subflows")
        assert "No subflow logs found." in text
    finally:
        studio.close()


def test_describe_subflow_logs_state_reports_count_and_latest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        logs_dir = tmp_path / "subflows"
        first = logs_dir / "a" / "stdout.txt"
        second = logs_dir / "b" / "stderr.txt"
        first.parent.mkdir(parents=True, exist_ok=True)
        second.parent.mkdir(parents=True, exist_ok=True)
        first.write_text("a", encoding="utf-8")
        second.write_text("b", encoding="utf-8")
        second.touch()

        text = studio._describe_subflow_logs_state(logs_dir)
        assert "Subflow logs: 2 files" in text
        assert "latest:" in text
        assert ("stderr.txt" in text) or ("stdout.txt" in text)
    finally:
        studio.close()
