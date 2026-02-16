from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QCursor, QEnterEvent, QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from robot_automation_studio.app import (
    StudioApp,
    build_help_tooltip_position,
    build_help_tooltip_text,
)


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


def test_build_help_tooltip_position_offsets_from_cursor() -> None:
    assert build_help_tooltip_position(120, 300) == (134, 322)


def test_event_filter_shows_help_tooltip_near_cursor(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        target_widget = studio.run_button
        entry = studio._help_entries_by_widget[target_widget]
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()
            captured["text"] = text
            captured["widget"] = args[0] if args else None

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        handled = studio.eventFilter(target_widget, QEvent(QEvent.Type.Enter))

        assert handled is False
        assert captured["text"] == build_help_tooltip_text(entry.summary)
        assert captured["widget"] is target_widget
    finally:
        studio.close()


def test_event_filter_hides_tooltip_on_leave(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        called = {"count": 0}

        def fake_hide_text() -> None:
            called["count"] += 1

        monkeypatch.setattr(QToolTip, "hideText", fake_hide_text)
        studio.eventFilter(studio.run_button, QEvent(QEvent.Type.Leave))
        assert called["count"] == 1
    finally:
        studio.close()


def test_event_filter_prefers_enter_event_global_position_over_cursor(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)
        monkeypatch.setattr(QCursor, "pos", lambda: QPoint(9000, 9000))

        enter_event = QEnterEvent(
            QPointF(2, 2),
            QPointF(10, 20),
            QPointF(10, 20),
        )
        studio.eventFilter(studio.run_button, enter_event)

        assert captured["x"] == 24
        assert captured["y"] == 42
    finally:
        studio.close()


def test_event_filter_handles_tooltip_event_at_event_global_position(monkeypatch) -> None:
    _ensure_qapp()
    studio = StudioApp()
    try:
        captured: dict[str, object] = {}

        def fake_show_text(pos, text, *args, **kwargs):
            captured["x"] = pos.x()
            captured["y"] = pos.y()

        monkeypatch.setattr(QToolTip, "showText", fake_show_text)

        tooltip_event = QHelpEvent(
            QEvent.Type.ToolTip,
            QPoint(4, 4),
            QPoint(30, 50),
        )
        handled = studio.eventFilter(studio.run_button, tooltip_event)

        assert handled is True
        assert captured["x"] == 44
        assert captured["y"] == 72
    finally:
        studio.close()
