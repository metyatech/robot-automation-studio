from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_registered_help_entries_do_not_use_ui_component_summary() -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        entries = list(studio._help_entries_by_id.values())
        assert entries
        assert all(entry.summary.strip() != "UI component." for entry in entries)
    finally:
        studio.close()


def test_key_controls_have_actionable_help_summary() -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        step_list_entry = studio._help_entries_by_widget[studio.step_list]
        target_combo_entry = studio._help_entries_by_widget[studio.target_combo]
        kind_combo_entry = studio._help_entries_by_widget[studio.kind_combo]
        delete_entry = studio._help_entries_by_widget[studio.delete_step_button]

        assert "select a step" in step_list_entry.summary.lower()
        assert "target platform" in target_combo_entry.summary.lower()
        assert "set step kind" in kind_combo_entry.summary.lower()
        assert "delete step" in delete_entry.summary.lower()
    finally:
        studio.close()
