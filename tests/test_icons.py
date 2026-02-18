"""Regression tests: buttons and actions have QIcon set (not null)."""

from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_header_buttons_have_icons() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert not studio.record_button.icon().isNull()
        assert not studio.record_stop_button.icon().isNull()
        assert not studio.run_button.icon().isNull()
        assert not studio.stop_robot_button.icon().isNull()
    finally:
        studio.close()


def test_step_toolbar_buttons_have_icons() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert not studio.delete_step_button.icon().isNull()
        assert not studio.move_up_button.icon().isNull()
        assert not studio.move_down_button.icon().isNull()
        assert not studio.duplicate_step_button.icon().isNull()
    finally:
        studio.close()


def test_file_menu_actions_have_icons() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert not studio.file_save_action.icon().isNull()
        assert not studio.file_load_action.icon().isNull()
        assert not studio.file_json_action.icon().isNull()
        assert not studio.file_help_action.icon().isNull()
        assert not studio.file_run_diagnostics_action.icon().isNull()
    finally:
        studio.close()


def test_add_step_menu_actions_have_icons() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert not studio.add_click_action.icon().isNull()
        assert not studio.add_drag_action.icon().isNull()
        assert not studio.add_shortcut_action.icon().isNull()
        assert not studio.add_menu_action.icon().isNull()
        assert not studio.add_type_action.icon().isNull()
        assert not studio.add_if_action.icon().isNull()
        assert not studio.add_group_action.icon().isNull()
    finally:
        studio.close()


def test_toolbar_buttons_have_icons() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert not studio.file_menu_button.icon().isNull()
        assert not studio.add_step_button.icon().isNull()
    finally:
        studio.close()
