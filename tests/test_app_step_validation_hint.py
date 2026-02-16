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


def test_step_validation_hint_shows_no_selection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.on_select_step(-1)
        text = studio.step_validation_label.text()
        assert "No step selected" in text
    finally:
        studio.close()


def test_step_validation_hint_shows_ready_for_valid_step(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.editor.add_step(
            "wait_for",
            "wait_for",
            {"seconds": 0.2},
        )
        studio.refresh_steps()
        studio.step_list.setCurrentRow(0)
        studio.on_select_step(0)
        text = studio.step_validation_label.text()
        assert "Ready for export/run" in text
    finally:
        studio.close()


def test_step_validation_hint_shows_invalid_for_bad_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.editor.add_step(
            "wait_for",
            "wait_for",
            {"seconds": 0.2},
        )
        studio.refresh_steps()
        studio.step_list.setCurrentRow(0)
        studio.on_select_step(0)
        studio.params_text.setPlainText("{")
        text = studio.step_validation_label.text()
        assert "Invalid:" in text
    finally:
        studio.close()


def test_step_validation_hint_shows_invalid_for_missing_required_action_input(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.editor.add_step(
            "run_subflow",
            "run_subflow",
            {},
        )
        studio.refresh_steps()
        studio.step_list.setCurrentRow(0)
        studio.on_select_step(0)
        text = studio.step_validation_label.text()
        assert "run_subflow requires input.path" in text
    finally:
        studio.close()
