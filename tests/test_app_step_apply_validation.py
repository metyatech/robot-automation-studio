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


def _build_valid_click_step() -> Step:
    return Step(
        action="click",
        title="click-menu",
        params={
            "title": "File",
            "automation_id": "MainMenuFile",
            "class_name": "MenuItem",
            "control_type": "MenuItem",
        },
    )


def test_apply_step_changes_rejects_invalid_action(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.scenario.steps = [_build_valid_click_step()]
        studio.refresh_steps()
        studio.step_list.setCurrentRow(0)
        studio.on_select_step(0)

        critical_calls = {"count": 0}
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )

        studio.action_edit.setText("invalid-action")
        studio.apply_step_changes()

        assert critical_calls["count"] == 1
        assert studio.scenario.steps[0].action == "click"
    finally:
        studio.close()


def test_apply_step_changes_rejects_invalid_params(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        original = _build_valid_click_step()
        studio.scenario.steps = [original]
        studio.refresh_steps()
        studio.step_list.setCurrentRow(0)
        studio.on_select_step(0)

        critical_calls = {"count": 0}
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )

        studio.action_edit.setText("click")
        studio.params_text.setPlainText("{}")
        studio.apply_step_changes()

        assert critical_calls["count"] == 1
        assert studio.scenario.steps[0].params == original.params
    finally:
        studio.close()
