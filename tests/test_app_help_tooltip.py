from PySide6.QtCore import QEvent
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
