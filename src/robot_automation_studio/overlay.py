"""Runtime overlay windows used while Robot automation is running."""

from __future__ import annotations

import tkinter as tk
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import win32api  # type: ignore[import-not-found]
import win32con  # type: ignore[import-not-found]
import win32gui  # type: ignore[import-not-found]


@dataclass(slots=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


def _virtual_screen_rect() -> Rect:
    return Rect(
        left=int(win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)),
        top=int(win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)),
        right=int(
            win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            + win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        ),
        bottom=int(
            win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            + win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        ),
    )


def _window_title(handle: int) -> str:
    return str(win32gui.GetWindowText(handle) or "")


def _target_window_rect(window_hint: str) -> Rect | None:
    normalized_hint = (window_hint or "Unity").strip().lower()
    if not normalized_hint:
        normalized_hint = "unity"

    foreground = int(win32gui.GetForegroundWindow() or 0)
    if foreground:
        title = _window_title(foreground).lower()
        if normalized_hint in title:
            left, top, right, bottom = win32gui.GetWindowRect(foreground)
            return Rect(left=int(left), top=int(top), right=int(right), bottom=int(bottom))

    matched_handle: int | None = None

    def _collect(handle: int, _lparam: Any) -> bool:
        nonlocal matched_handle
        if matched_handle is not None:
            return False
        if not win32gui.IsWindowVisible(handle):
            return True
        title = _window_title(handle).lower()
        if normalized_hint in title:
            matched_handle = int(handle)
            return False
        return True

    win32gui.EnumWindows(_collect, 0)
    if matched_handle is None:
        return None
    left, top, right, bottom = win32gui.GetWindowRect(matched_handle)
    return Rect(left=int(left), top=int(top), right=int(right), bottom=int(bottom))


def compute_banner_rect(
    screen: Rect,
    target: Rect | None,
    banner_width: int,
    banner_height: int,
    margin_top: int = 16,
) -> Rect:
    anchor = target or screen
    effective_width = max(1, min(banner_width, screen.width))
    effective_height = max(1, min(banner_height, screen.height))

    preferred_left = anchor.left + round(anchor.width / 2) - round(effective_width / 2)
    min_left = screen.left
    max_left = screen.right - effective_width
    left = max(min_left, min(preferred_left, max_left))

    preferred_top = anchor.top + margin_top
    min_top = screen.top
    max_top = screen.bottom - effective_height
    top = max(min_top, min(preferred_top, max_top))

    return Rect(
        left=left,
        top=top,
        right=left + effective_width,
        bottom=top + effective_height,
    )


def build_banner_text(progress_text: str, stop_hotkey_label: str) -> str:
    normalized_progress = str(progress_text or "").strip() or "Running"
    return f"{normalized_progress}  |  Press {stop_hotkey_label} to stop"


class AutomationRunOverlay:
    """Darkens non-target screen areas and shows stop-hotkey guidance."""

    def __init__(self, root: tk.Tk, window_hint: str, stop_hotkey_label: str) -> None:
        self._root = root
        self._window_hint = window_hint
        self._stop_hotkey_label = stop_hotkey_label
        self._progress_text = "Running"
        self._dim_windows: list[tk.Toplevel] = []
        self._border_windows: list[tk.Toplevel] = []
        self._banner_window: tk.Toplevel | None = None
        self._banner_label: tk.Label | None = None
        self._running = False
        self._timer_id: str | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._create_windows()
        self._update()

    def stop(self) -> None:
        self._running = False
        if self._timer_id is not None:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None
        windows = [*self._dim_windows, *self._border_windows]
        if self._banner_window is not None:
            windows.append(self._banner_window)
        for window in windows:
            with suppress(tk.TclError):
                window.destroy()
        self._dim_windows.clear()
        self._border_windows.clear()
        self._banner_window = None
        self._banner_label = None

    def _create_windows(self) -> None:
        self._dim_windows = [self._new_overlay_window("#000000", 0.45) for _ in range(4)]
        self._border_windows = [self._new_overlay_window("#ff2b2b", 0.95) for _ in range(4)]
        self._banner_window = self._new_overlay_window("#1a1a1a", 0.9)
        self._banner_label = tk.Label(
            self._banner_window,
            text=build_banner_text(self._progress_text, self._stop_hotkey_label),
            fg="#ffffff",
            bg="#1a1a1a",
            font=("Segoe UI", 11, "bold"),
            padx=18,
            pady=6,
        )
        self._banner_label.pack(fill=tk.BOTH, expand=True)

    def _new_overlay_window(self, color: str, alpha: float) -> tk.Toplevel:
        window = tk.Toplevel(self._root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", alpha)
        window.configure(bg=color)
        return window

    def _place(self, window: tk.Toplevel, rect: Rect) -> None:
        width = max(1, rect.width)
        height = max(1, rect.height)
        window.geometry(f"{width}x{height}+{rect.left}+{rect.top}")

    def set_progress_text(self, progress_text: str) -> None:
        self._progress_text = str(progress_text or "").strip() or "Running"
        if self._banner_label is None:
            return
        self._banner_label.configure(
            text=build_banner_text(self._progress_text, self._stop_hotkey_label)
        )

    def _update(self) -> None:
        if not self._running:
            return

        screen = _virtual_screen_rect()
        target = _target_window_rect(self._window_hint)

        if target is None:
            for dim in self._dim_windows:
                self._place(dim, screen)
            for border in self._border_windows:
                self._place(border, Rect(screen.left, screen.top, screen.left + 1, screen.top + 1))
        else:
            clamped = Rect(
                left=max(screen.left, target.left),
                top=max(screen.top, target.top),
                right=min(screen.right, target.right),
                bottom=min(screen.bottom, target.bottom),
            )
            if clamped.width < 2 or clamped.height < 2:
                clamped = target

            top_rect = Rect(screen.left, screen.top, screen.right, clamped.top)
            bottom_rect = Rect(screen.left, clamped.bottom, screen.right, screen.bottom)
            left_rect = Rect(screen.left, clamped.top, clamped.left, clamped.bottom)
            right_rect = Rect(clamped.right, clamped.top, screen.right, clamped.bottom)

            for dim, rect in zip(
                self._dim_windows,
                [top_rect, bottom_rect, left_rect, right_rect],
                strict=True,
            ):
                self._place(dim, rect)

            border = 3
            borders = [
                Rect(
                    clamped.left - border,
                    clamped.top - border,
                    clamped.right + border,
                    clamped.top,
                ),
                Rect(
                    clamped.left - border,
                    clamped.bottom,
                    clamped.right + border,
                    clamped.bottom + border,
                ),
                Rect(clamped.left - border, clamped.top, clamped.left, clamped.bottom),
                Rect(clamped.right, clamped.top, clamped.right + border, clamped.bottom),
            ]
            for border_window, rect in zip(self._border_windows, borders, strict=True):
                self._place(border_window, rect)

        if self._banner_window is not None:
            banner_rect = compute_banner_rect(
                screen=screen,
                target=target,
                banner_width=520,
                banner_height=44,
                margin_top=16,
            )
            self._place(self._banner_window, banner_rect)
            self._banner_window.lift()

        self._timer_id = self._root.after(120, self._update)
