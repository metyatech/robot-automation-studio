from pathlib import Path

from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import (
    StudioApp,
    default_params_template_for_action,
)


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_default_params_template_for_action_click() -> None:
    template = default_params_template_for_action("click")
    assert template is not None
    assert template["target"]["strategy"] == "uia"


def test_default_params_template_for_action_alias_shortcut() -> None:
    template = default_params_template_for_action("shortcut")
    assert template is not None
    assert template["input"]["shortcut"] == "CTRL+S"


def test_insert_params_template_for_selected_action(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.action_edit.setText("click")
        studio.params_text.setPlainText("{}")

        studio.insert_params_template_for_selected_action()

        assert '"strategy": "uia"' in studio.params_text.toPlainText()
    finally:
        studio.close()


def test_insert_params_template_for_selected_action_unsupported(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        critical_calls = {"count": 0}
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.critical",
            lambda *args, **kwargs: critical_calls.__setitem__(
                "count", critical_calls["count"] + 1
            ),
        )
        studio.action_edit.setText("unknown-action")

        studio.insert_params_template_for_selected_action()

        assert critical_calls["count"] == 1
    finally:
        studio.close()
