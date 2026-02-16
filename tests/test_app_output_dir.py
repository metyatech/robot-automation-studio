from pathlib import Path

from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_open_output_directory_creates_and_opens_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        target = (tmp_path / "artifacts" / "studio").resolve()
        studio.output_dir_edit.setText(str(target))
        captured = {"path": ""}
        monkeypatch.setattr("robot_automation_studio.app.sys.platform", "win32")

        monkeypatch.setattr(
            "robot_automation_studio.app.os.startfile",
            lambda path: captured.__setitem__("path", str(path)),
            raising=False,
        )

        studio.open_output_directory()

        assert target.exists()
        assert captured["path"] == str(target)
    finally:
        studio.close()


def test_open_output_directory_shows_error_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.output_dir_edit.setText(str(tmp_path / "artifacts"))
        critical_calls = {"count": 0}
        monkeypatch.setattr("robot_automation_studio.app.sys.platform", "win32")

        def _raise_startfile(path: str) -> None:
            _ = path
            raise RuntimeError("failed-open")

        monkeypatch.setattr(
            "robot_automation_studio.app.os.startfile",
            _raise_startfile,
            raising=False,
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )

        studio.open_output_directory()

        assert critical_calls["count"] == 1
        assert "Failed to open output directory" in studio.log_text.toPlainText()
    finally:
        studio.close()


def test_open_directory_with_feedback_returns_false_on_open_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        target = tmp_path / "diagnostics"
        monkeypatch.setattr("robot_automation_studio.app.sys.platform", "win32")
        critical_calls = {"count": 0}

        def _raise_startfile(path: str) -> None:
            _ = path
            raise RuntimeError("open-error")

        monkeypatch.setattr(
            "robot_automation_studio.app.os.startfile",
            _raise_startfile,
            raising=False,
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )

        ok = studio._open_directory_with_feedback(
            target=target,
            success_log_key="app.log.opened_diagnostics_dir",
            error_log_key="app.log.open_diagnostics_dir_failed",
            error_title_key="app.error.open_diagnostics_dir.title",
            error_message_key="app.error.open_diagnostics_dir.message",
            make_dirs=True,
        )

        assert ok is False
        assert critical_calls["count"] == 1
    finally:
        studio.close()
