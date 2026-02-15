from __future__ import annotations

from typing import Any

from robot_automation_studio.window_focus import (
    focus_visible_window_with_hint,
    trigger_assets_refresh_shortcut_with_hint,
)


def test_focus_visible_window_with_hint_prefers_foreground_match() -> None:
    calls: list[tuple[str, int]] = []

    def _enum_windows(callback: Any, _lparam: int) -> None:
        raise AssertionError("EnumWindows should not be used when foreground window matches.")

    def _is_visible(_handle: int) -> bool:
        return True

    def _get_text(handle: int) -> str:
        return "Unity - Scene" if handle == 42 else "Other"

    def _get_foreground() -> int:
        return 42

    def _show_window(handle: int, _flag: int) -> None:
        calls.append(("show", handle))

    def _set_foreground(handle: int) -> None:
        calls.append(("foreground", handle))

    result = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=_enum_windows,
        is_window_visible_func=_is_visible,
        get_window_text_func=_get_text,
        get_foreground_window_func=_get_foreground,
        show_window_func=_show_window,
        set_foreground_window_func=_set_foreground,
    )

    assert result is True
    assert calls == [("show", 42), ("foreground", 42)]


def test_focus_visible_window_with_hint_finds_enumerated_match() -> None:
    calls: list[tuple[str, int]] = []

    def _enum_windows(callback: Any, _lparam: int) -> None:
        assert callback(10, 0) is True
        assert callback(20, 0) is False

    def _is_visible(handle: int) -> bool:
        return handle != 30

    def _get_text(handle: int) -> str:
        return {10: "Other Window", 20: "Unity Project"}.get(handle, "")

    def _get_foreground() -> int:
        return 99

    def _show_window(handle: int, _flag: int) -> None:
        calls.append(("show", handle))

    def _set_foreground(handle: int) -> None:
        calls.append(("foreground", handle))

    result = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=_enum_windows,
        is_window_visible_func=_is_visible,
        get_window_text_func=_get_text,
        get_foreground_window_func=_get_foreground,
        show_window_func=_show_window,
        set_foreground_window_func=_set_foreground,
    )

    assert result is True
    assert calls == [("show", 20), ("foreground", 20)]


def test_focus_visible_window_with_hint_returns_false_when_not_found() -> None:
    def _enum_windows(callback: Any, _lparam: int) -> None:
        assert callback(1, 0) is True

    def _is_visible(_handle: int) -> bool:
        return True

    def _get_text(_handle: int) -> str:
        return "No match"

    def _get_foreground() -> int:
        return 0

    def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    result = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=_enum_windows,
        is_window_visible_func=_is_visible,
        get_window_text_func=_get_text,
        get_foreground_window_func=_get_foreground,
        show_window_func=_noop,
        set_foreground_window_func=_noop,
    )

    assert result is False


def test_trigger_assets_refresh_shortcut_with_hint_sends_ctrl_r() -> None:
    class _Window:
        def __init__(self, title: str) -> None:
            self._title = title
            self.focused = False

        def window_text(self) -> str:
            return self._title

        def set_focus(self) -> None:
            self.focused = True

    target = _Window("Ryuon - Unity")
    sent: list[str] = []

    result = trigger_assets_refresh_shortcut_with_hint(
        "Unity",
        windows_provider=lambda: [target],
        send_keys_func=lambda keys: sent.append(keys),
        sleep_func=lambda _seconds: None,
    )

    assert result is True
    assert target.focused is True
    assert sent == ["^r"]


def test_trigger_assets_refresh_shortcut_with_hint_returns_false_when_not_found() -> None:
    class _Window:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

        def set_focus(self) -> None:
            raise AssertionError("set_focus must not be called when title does not match")

    sent: list[str] = []
    result = trigger_assets_refresh_shortcut_with_hint(
        "Unity",
        windows_provider=lambda: [_Window("Visual Studio Code"), _Window("Notepad")],
        send_keys_func=lambda keys: sent.append(keys),
        sleep_func=lambda _seconds: None,
    )

    assert result is False
    assert sent == []
