"""Helpers to focus desktop windows by title hint."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import win32con  # type: ignore[import-not-found]
import win32gui  # type: ignore[import-not-found]
from pywinauto import Desktop, keyboard


def focus_visible_window_with_hint(
    window_hint: str,
    *,
    enum_windows_func: Callable[[Callable[[int, Any], bool], int], Any] = win32gui.EnumWindows,
    is_window_visible_func: Callable[[int], int | bool] = win32gui.IsWindowVisible,
    get_window_text_func: Callable[[int], str] = win32gui.GetWindowText,
    get_foreground_window_func: Callable[[], int] = win32gui.GetForegroundWindow,
    show_window_func: Callable[[int, int], Any] = win32gui.ShowWindow,
    set_foreground_window_func: Callable[[int], Any] = win32gui.SetForegroundWindow,
    restore_flag: int = win32con.SW_RESTORE,
) -> bool:
    normalized_hint = str(window_hint or "").strip().lower()
    if normalized_hint == "":
        return False

    foreground = int(get_foreground_window_func() or 0)
    if foreground > 0:
        title = str(get_window_text_func(foreground) or "").strip().lower()
        if normalized_hint in title:
            try:
                show_window_func(foreground, restore_flag)
                set_foreground_window_func(foreground)
                return True
            except Exception:
                return False

    matched_handle: int | None = None

    def _collect(handle: int, _lparam: Any) -> bool:
        nonlocal matched_handle
        if not is_window_visible_func(handle):
            return True
        title = str(get_window_text_func(handle) or "").strip().lower()
        if normalized_hint in title:
            matched_handle = int(handle)
            return False
        return True

    enum_windows_func(_collect, 0)
    if matched_handle is None:
        return False

    try:
        show_window_func(matched_handle, restore_flag)
        set_foreground_window_func(matched_handle)
    except Exception:
        return False
    return True


def trigger_assets_refresh_shortcut_with_hint(
    window_hint: str,
    *,
    windows_provider: Callable[[], list[Any]] | None = None,
    send_keys_func: Callable[[str], Any] = keyboard.send_keys,
    sleep_func: Callable[[float], None] = time.sleep,
) -> bool:
    normalized_hint = str(window_hint or "").strip().lower()
    if normalized_hint == "":
        return False

    provider = windows_provider or (lambda: list(Desktop(backend="uia").windows()))
    try:
        windows = provider()
    except Exception:
        return False
    for window in windows:
        try:
            title = str(window.window_text() or "").strip().lower()
        except Exception:
            continue
        if normalized_hint not in title:
            continue
        try:
            window.set_focus()
            sleep_func(0.15)
            send_keys_func("^r")
            return True
        except Exception:
            continue
    return False
