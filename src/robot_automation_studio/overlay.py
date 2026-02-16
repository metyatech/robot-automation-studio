"""Runtime overlay windows used while Robot automation is running."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import win32api  # type: ignore[import-not-found]
import win32con  # type: ignore[import-not-found]
import win32gui  # type: ignore[import-not-found]
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .i18n import translate


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

    def _collect(handle: int, _lparam: object) -> bool:
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


OverlayMode = Literal["run", "recording"]


@dataclass(frozen=True, slots=True)
class OverlayTheme:
    border_color: str
    banner_background: str
    banner_foreground: str
    default_progress_key: str
    stop_action_key: str


def _overlay_theme(mode: OverlayMode) -> OverlayTheme:
    if mode == "recording":
        return OverlayTheme(
            border_color="#1fb6ff",
            banner_background="#13293d",
            banner_foreground="#f4faff",
            default_progress_key="overlay.progress.recording",
            stop_action_key="overlay.stop_action.recording",
        )
    return OverlayTheme(
        border_color="#ff2b2b",
        banner_background="#1a1a1a",
        banner_foreground="#ffffff",
        default_progress_key="overlay.progress.running",
        stop_action_key="overlay.stop_action.run",
    )


def build_banner_text(
    progress_text: str,
    stop_hotkey_label: str,
    *,
    mode: OverlayMode = "run",
    locale: str = "en",
) -> str:
    theme = _overlay_theme(mode)
    normalized_progress = str(progress_text or "").strip() or translate(
        theme.default_progress_key,
        locale=locale,
    )
    return translate(
        "overlay.banner",
        locale=locale,
        progress=normalized_progress,
        hotkey=stop_hotkey_label,
        action=translate(theme.stop_action_key, locale=locale),
    )


_OVERLAY_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowTransparentForInput
)


def _new_overlay_widget(parent: QWidget | None, color: str, alpha: float) -> QWidget:
    w = QWidget(parent, _OVERLAY_FLAGS)
    w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    w.setStyleSheet(f"background-color: {color};")
    w.setWindowOpacity(alpha)
    return w


def _place(widget: QWidget, rect: Rect) -> None:
    width = max(1, rect.width)
    height = max(1, rect.height)
    widget.setGeometry(rect.left, rect.top, width, height)


class AutomationRunOverlay:
    """Darkens non-target screen areas and shows stop-hotkey guidance."""

    def __init__(
        self,
        parent: QWidget | None,
        window_hint: str,
        stop_hotkey_label: str,
        mode: OverlayMode = "run",
        locale: str = "en",
    ) -> None:
        self._parent = parent
        self._window_hint = window_hint
        self._stop_hotkey_label = stop_hotkey_label
        self._mode: OverlayMode = mode
        self._locale = locale
        self._theme = _overlay_theme(mode)
        self._progress_text = translate(self._theme.default_progress_key, locale=self._locale)
        self._dim_windows: list[QWidget] = []
        self._border_windows: list[QWidget] = []
        self._banner_window: QWidget | None = None
        self._banner_label: QLabel | None = None
        self._running = False
        self._timer = QTimer()
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._update)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._create_windows()
        self._update()
        self._timer.start()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        for w in [*self._dim_windows, *self._border_windows]:
            w.close()
            w.deleteLater()
        if self._banner_window is not None:
            self._banner_window.close()
            self._banner_window.deleteLater()
        self._dim_windows.clear()
        self._border_windows.clear()
        self._banner_window = None
        self._banner_label = None

    def _create_windows(self) -> None:
        self._dim_windows = [_new_overlay_widget(self._parent, "#000000", 0.45) for _ in range(4)]
        self._border_windows = [
            _new_overlay_widget(self._parent, self._theme.border_color, 0.95) for _ in range(4)
        ]
        banner = _new_overlay_widget(self._parent, self._theme.banner_background, 0.9)
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(
            build_banner_text(
                self._progress_text,
                self._stop_hotkey_label,
                mode=self._mode,
                locale=self._locale,
            )
        )
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        label.setStyleSheet(
            f"color: {self._theme.banner_foreground}; "
            f"background: {self._theme.banner_background}; "
            "padding: 6px 18px;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self._banner_window = banner
        self._banner_label = label

    def set_progress_text(self, progress_text: str) -> None:
        self._progress_text = str(progress_text or "").strip() or translate(
            self._theme.default_progress_key,
            locale=self._locale,
        )
        if self._banner_label is None:
            return
        self._banner_label.setText(
            build_banner_text(
                self._progress_text,
                self._stop_hotkey_label,
                mode=self._mode,
                locale=self._locale,
            )
        )

    def set_locale(self, locale: str) -> None:
        self._locale = locale
        self.set_progress_text(self._progress_text)

    def _update(self) -> None:
        if not self._running:
            return

        screen = _virtual_screen_rect()
        target = _target_window_rect(self._window_hint)

        if target is None:
            for dim in self._dim_windows:
                _place(dim, screen)
            for border in self._border_windows:
                _place(border, Rect(screen.left, screen.top, screen.left + 1, screen.top + 1))
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
                _place(dim, rect)

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
                _place(border_window, rect)

        for w in [*self._dim_windows, *self._border_windows]:
            w.show()

        if self._banner_window is not None:
            banner_rect = compute_banner_rect(
                screen=screen,
                target=target,
                banner_width=520,
                banner_height=44,
                margin_top=16,
            )
            _place(self._banner_window, banner_rect)
            self._banner_window.show()
            self._banner_window.raise_()
