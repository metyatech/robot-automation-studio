from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.runner import RunResult


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


class _FakeRunExportResult:
    def __init__(self, root: Path) -> None:
        self.robot_path = root / "suite.robot"
        self.json_path = root / "suite.scenario.json"


class _FakeProcess:
    def __init__(self) -> None:
        self.pid = 12345

    def poll(self):
        return None


def test_run_robot_suite_logs_preflight_and_finishes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            lambda scenario, output_dir, suite_name: _FakeRunExportResult(tmp_path),
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(studio, "_start_overlay", lambda mode, progress_text: None)
        monkeypatch.setattr(studio, "_stop_overlay", lambda: None)
        monkeypatch.setattr(studio, "_stop_stop_hotkey", lambda: None)
        monkeypatch.setattr(
            "robot_automation_studio.app.start_robot_process",
            lambda suite_path, output_dir, variable_output_dir: _FakeProcess(),
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.wait_robot_process",
            lambda process: RunResult(return_code=0, stdout="", stderr=""),
        )

        studio.run_robot_suite()

        assert studio._run_thread is not None
        studio._run_thread.join(timeout=1.0)
        _process_events_for(120)

        log_text = studio.log_text.toPlainText()
        assert "Running preflight checks..." in log_text
        assert "Starting Robot process..." in log_text
        assert studio._run_phase == "idle"
    finally:
        studio.close()


def test_run_robot_suite_preflight_failure_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: False,
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            lambda scenario, output_dir, suite_name: _FakeRunExportResult(tmp_path),
        )

        studio.run_robot_suite()

        log_text = studio.log_text.toPlainText()
        assert "Running preflight checks..." in log_text
        assert studio._run_phase == "idle"
    finally:
        studio.close()
