from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QEnterEvent, QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from robot_automation_studio.app import StudioApp, build_help_tooltip_text


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_build_help_tooltip_text_uses_stripped_summary() -> None:
    assert build_help_tooltip_text("  Run the selected scenario  ") == "Run the selected scenario"


def test_build_help_tooltip_text_uses_fallback_for_blank_summary() -> None:
    assert build_help_tooltip_text("   ") == "No help available for this component."


def test_registered_widget_has_standard_qt_tooltip_text() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        entry = studio._help_entries_by_widget[studio.run_button]
        assert studio.run_button.toolTip() == build_help_tooltip_text(entry.summary)
    finally:
        studio.close()


def test_event_filter_shows_tooltip_on_focus_in(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text
            captured["widget"] = args[0] if args else None

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        handled = studio.eventFilter(studio.run_button, QEvent(QEvent.Type.FocusIn))
        expected = studio.run_button.mapToGlobal(studio.run_button.rect().center())

        assert handled is False
        assert captured["x"] == expected.x()
        assert captured["y"] == expected.y()
        assert captured["text"] == studio.run_button.toolTip()
        assert captured["widget"] is studio.run_button
    finally:
        studio.close()


def test_event_filter_handles_tooltip_event_with_cursor_anchor(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text
            captured["widget"] = args[0] if args else None

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        tooltip_event = QHelpEvent(
            QEvent.Type.ToolTip,
            QPoint(7, 9),
            QPoint(120, 240),
        )
        handled = studio.eventFilter(studio.run_button, tooltip_event)

        assert handled is True
        assert captured["x"] == 120
        assert captured["y"] == 240
        assert captured["text"] == studio.run_button.toolTip()
        assert captured["widget"] is studio.run_button
    finally:
        studio.close()


def test_event_filter_handles_enter_event_with_cursor_anchor(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text
            captured["widget"] = args[0] if args else None

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        enter_event = QEnterEvent(
            QPointF(7, 9),
            QPointF(120, 240),
            QPointF(120, 240),
        )
        handled = studio.eventFilter(studio.run_button, enter_event)

        assert handled is False
        assert captured["x"] == 120
        assert captured["y"] == 240
        assert captured["text"] == studio.run_button.toolTip()
        assert captured["widget"] is studio.run_button
    finally:
        studio.close()


def test_event_filter_hides_tooltip_on_leave(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        called = {"count": 0}

        def fake_hide_text() -> None:
            called["count"] += 1

        monkeypatch.setattr(QToolTip, "hideText", fake_hide_text)
        studio.eventFilter(studio.run_button, QEvent(QEvent.Type.Leave))
        assert called["count"] == 1
    finally:
        studio.close()


def test_event_filter_handles_missing_combo_tooltip_registry(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        if hasattr(studio, "_combo_tooltip_viewports"):
            delattr(studio, "_combo_tooltip_viewports")
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text
            captured["widget"] = args[0] if args else None

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        tooltip_event = QHelpEvent(
            QEvent.Type.ToolTip,
            QPoint(4, 5),
            QPoint(140, 260),
        )
        handled = studio.eventFilter(studio.run_button, tooltip_event)

        assert handled is True
        assert captured["x"] == 140
        assert captured["y"] == 260
        assert captured["text"] == studio.run_button.toolTip()
        assert captured["widget"] is studio.run_button
    finally:
        studio.close()
