from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_app_switches_to_japanese_locale() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        ja_index = studio.language_combo.findData("ja", Qt.ItemDataRole.UserRole)
        assert ja_index >= 0

        studio.language_combo.setCurrentIndex(ja_index)

        assert studio.run_button.text() == "▶ Robot 実行"
        assert studio.main_tabs.tabText(studio.step_tab_index) == "ステップ"
        assert studio.target_label.text() == "対象"
        assert studio.kind_combo.itemData(0, Qt.ItemDataRole.UserRole) == "action"

        entry = studio._help_entries_by_widget[studio.run_button]
        assert "実行" in entry.summary
        assert studio.run_button.toolTip() == entry.summary
    finally:
        studio.close()


def test_app_uses_explicit_english_locale() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        assert studio.run_button.text() == "▶ Run Robot"
        assert studio.main_tabs.tabText(studio.step_tab_index) == "Step"
        assert studio.target_label.text() == "Target"
    finally:
        studio.close()


def test_app_uses_env_locale_when_initial_locale_is_not_provided(monkeypatch) -> None:
    _ensure_qapp()
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_LOCALE", "ja")
    studio = StudioApp()
    try:
        assert studio.run_button.text() == "▶ Robot 実行"
        assert studio.main_tabs.tabText(studio.step_tab_index) == "ステップ"
        assert studio.target_label.text() == "対象"
    finally:
        studio.close()
