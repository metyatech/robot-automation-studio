from pathlib import Path
from typing import Any, cast

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
    target = cast(dict[str, Any], template["target"])
    assert target["strategy"] == "uia"


def test_default_params_template_for_action_alias_shortcut() -> None:
    template = default_params_template_for_action("shortcut")
    assert template is not None
    input_payload = cast(dict[str, Any], template["input"])
    assert input_payload["shortcut"] == "CTRL+S"


def test_default_params_template_for_action_double_click_is_coordinate() -> None:
    template = default_params_template_for_action("double_click")
    assert template is not None
    target = cast(dict[str, Any], template["target"])
    assert target["strategy"] == "coordinate"


def test_default_params_template_for_action_run_subflow_points_to_robot_file() -> None:
    template = default_params_template_for_action("run_subflow")
    assert template is not None
    input_payload = cast(dict[str, Any], template["input"])
    path = cast(str, input_payload["path"])
    assert path.endswith(".robot")


def test_insert_params_template_for_selected_action(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.action_edit.setText("click")
        studio.params_text.setPlainText("{}")
        monkeypatch.setattr(
            "robot_automation_studio.app.QMessageBox.question",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("overwrite confirmation should not be shown for empty params")
            ),
        )

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


def test_insert_params_template_prompts_before_overwrite_and_respects_cancel(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.action_edit.setText("click")
        studio.params_text.setPlainText('{"target":{"strategy":"coordinate"}}')
        question_calls = {"count": 0}

        def _fake_question(*args, **kwargs):
            _ = (args, kwargs)
            question_calls["count"] += 1
            return 65536  # QMessageBox.StandardButton.No

        monkeypatch.setattr("robot_automation_studio.app.QMessageBox.question", _fake_question)

        studio.insert_params_template_for_selected_action()

        assert question_calls["count"] == 1
        assert studio.params_text.toPlainText() == '{"target":{"strategy":"coordinate"}}'
    finally:
        studio.close()


def test_params_template_button_enabled_only_for_action_kind(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._set_combo_value(studio.kind_combo, "action")
        studio._update_step_kind_fields_visibility()
        action_enabled = studio.params_template_button.isEnabled()

        studio._set_combo_value(studio.kind_combo, "control")
        studio._update_step_kind_fields_visibility()
        control_enabled = studio.params_template_button.isEnabled()

        studio._set_combo_value(studio.kind_combo, "group")
        studio._update_step_kind_fields_visibility()
        group_enabled = studio.params_template_button.isEnabled()

        assert action_enabled is True
        assert control_enabled is False
        assert group_enabled is False
    finally:
        studio.close()
