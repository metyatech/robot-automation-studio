from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QAction, QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from robot_automation_studio.app import StudioApp


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def _menu_actions_by_text(studio: StudioApp, menu_type: str) -> dict[str, QAction]:
    if menu_type == "file":
        menu = studio.file_menu_button.menu()
    elif menu_type == "add_step":
        menu = studio.add_step_button.menu()
    else:
        raise ValueError(f"Unknown menu type: {menu_type}")
    assert menu is not None
    return {
        action.text(): action
        for action in menu.actions()
        if not action.isSeparator() and isinstance(action, QAction)
    }


def test_file_menu_actions_have_per_action_tooltips() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        actions = _menu_actions_by_text(studio, "file")
        assert actions["💾 Save"].toolTip() == "Save current scenario file."
        assert actions["📂 Load"].toolTip() == "Load scenario file."
        assert actions["{} Full JSON"].toolTip() == "Open full JSON editor."
        assert actions["Help Guide (F1)"].toolTip() == "Open full help guide."
    finally:
        studio.close()


def test_add_step_menu_actions_have_per_action_tooltips() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        actions = _menu_actions_by_text(studio, "add_step")
        assert actions["🖱 Click"].toolTip() == "Add click action step."
        assert actions["↔ Drag"].toolTip() == "Add drag/drop action step."
        assert actions["⌨ Shortcut"].toolTip() == "Add keyboard shortcut step."
        assert actions["≡ Menu"].toolTip() == "Add menu navigation step."
        assert actions["✎ Type"].toolTip() == "Add text input step."
        assert actions["IF"].toolTip() == "Add control-flow step."
        assert actions["[] Group"].toolTip() == "Add group container step."
    finally:
        studio.close()


def test_combo_options_have_per_option_tooltips() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        expected_target = {
            "unity": "Run steps against Unity Editor.",
            "web": "Run steps against a web browser target.",
            "desktop": "Run steps against a desktop app target.",
            "hybrid": "Run steps across mixed app targets.",
        }
        for row in range(studio.target_combo.count()):
            item_text = studio.target_combo.itemData(row, Qt.ItemDataRole.UserRole)
            item_tip = studio.target_combo.itemData(row, Qt.ItemDataRole.ToolTipRole)
            assert item_tip == expected_target[item_text]

        expected_mode = {
            "attach": "Use an already-open target window.",
            "launch": "Launch Unity project before running.",
        }
        for row in range(studio.execution_mode_combo.count()):
            item_text = studio.execution_mode_combo.itemData(row, Qt.ItemDataRole.UserRole)
            item_tip = studio.execution_mode_combo.itemData(row, Qt.ItemDataRole.ToolTipRole)
            assert item_tip == expected_mode[item_text]

        expected_kind = {
            "action": "Execute one operation step.",
            "control": "Control flow with conditions/loops.",
            "group": "Organize nested child steps.",
        }
        for row in range(studio.kind_combo.count()):
            item_text = studio.kind_combo.itemData(row, Qt.ItemDataRole.UserRole)
            item_tip = studio.kind_combo.itemData(row, Qt.ItemDataRole.ToolTipRole)
            assert item_tip == expected_kind[item_text]
    finally:
        studio.close()


def test_tabs_have_per_tab_tooltips() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        tabs = studio.main_tabs
        assert tabs.tabToolTip(0) == "Edit selected step fields."
        assert tabs.tabToolTip(1) == "Configure scenario settings."
        assert tabs.tabToolTip(2) == "Configure export outputs."
    finally:
        studio.close()


def test_combo_popup_tooltip_event_shows_option_description(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        combo = studio.target_combo
        view = combo.view()
        index = combo.model().index(1, 0)
        monkeypatch.setattr(view, "indexAt", lambda _pos: index)

        event = QHelpEvent(
            QEvent.Type.ToolTip,
            QPoint(2, 3),
            QPoint(120, 240),
        )
        handled = studio.eventFilter(view.viewport(), event)

        assert handled is True
        assert captured["x"] == 120
        assert captured["y"] == 240
        assert captured["text"] == combo.itemData(1, Qt.ItemDataRole.ToolTipRole)
    finally:
        studio.close()
