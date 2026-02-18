"""Regression tests: qdarktheme applies without error."""

from PySide6.QtWidgets import QApplication


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_qdarktheme_load_stylesheet_does_not_raise() -> None:
    _ensure_qapp()
    import qdarktheme

    stylesheet = qdarktheme.load_stylesheet("dark")
    assert isinstance(stylesheet, str)
    assert len(stylesheet) > 0


def test_studio_app_creates_with_theme() -> None:
    app = _ensure_qapp()
    import qdarktheme

    from robot_automation_studio.app import StudioApp, _build_stylesheet

    app.setStyleSheet(qdarktheme.load_stylesheet("dark") + _build_stylesheet())
    studio = StudioApp(initial_locale="en")
    try:
        assert studio.isVisible() is False  # not shown yet, just created
    finally:
        studio.close()
