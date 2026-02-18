"""Standalone overlay process for headless server mode.

Spawned by ``server.py`` when recording or robot execution starts.
Communicates via stdin (JSON commands) and stdout (JSON events).

Commands (stdin, one JSON per line):
    {"cmd": "update_progress", "text": "Running step 3/10"}
    {"cmd": "stop"}

Events (stdout, one JSON per line):
    {"event": "started"}
    {"event": "stop_requested"}
    {"event": "stopped"}
"""

from __future__ import annotations

import json
import sys
import threading
from typing import Any


def _run_overlay(
    mode: str,
    window_hint: str,
    stop_hotkey_label: str,
    locale: str,
) -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .overlay import AutomationRunOverlay, OverlayMode

    app = QApplication.instance() or QApplication(sys.argv[:1])

    overlay_mode: OverlayMode = "recording" if mode == "recording" else "run"

    def _on_stop_requested() -> None:
        _emit_event("stop_requested")

    overlay = AutomationRunOverlay(
        parent=None,
        window_hint=window_hint,
        stop_hotkey_label=stop_hotkey_label,
        on_stop_requested=_on_stop_requested,
        mode=overlay_mode,
        locale=locale,
    )
    overlay.start()
    _emit_event("started")

    # Read commands from stdin in a background thread
    stop_timer = QTimer()
    stop_timer.setSingleShot(True)

    def _stop_and_quit() -> None:
        overlay.stop()
        _emit_event("stopped")
        app.quit()

    stop_timer.timeout.connect(_stop_and_quit)

    progress_timer = QTimer()
    progress_timer.setSingleShot(True)
    _pending_progress: list[str] = []

    def _apply_progress() -> None:
        if _pending_progress:
            overlay.set_progress_text(_pending_progress[-1])
            _pending_progress.clear()

    progress_timer.timeout.connect(_apply_progress)

    def _stdin_reader() -> None:
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError:
                    continue
                action = cmd.get("cmd", "")
                if action == "stop":
                    stop_timer.start(0)
                    return
                if action == "update_progress":
                    text = str(cmd.get("text", ""))
                    _pending_progress.append(text)
                    progress_timer.start(0)
        except Exception:
            stop_timer.start(0)

    reader_thread = threading.Thread(target=_stdin_reader, daemon=True)
    reader_thread.start()

    app.exec()


def _emit_event(event: str, **data: Any) -> None:
    payload: dict[str, Any] = {"event": event}
    if data:
        payload["data"] = data
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Overlay process for Robot Automation Studio")
    parser.add_argument("--mode", default="run", choices=["run", "recording"])
    parser.add_argument("--window-hint", default="Unity")
    parser.add_argument("--stop-hotkey-label", default="Alt+Shift+F12")
    parser.add_argument("--locale", default="en")
    args = parser.parse_args()

    _run_overlay(
        mode=args.mode,
        window_hint=args.window_hint,
        stop_hotkey_label=args.stop_hotkey_label,
        locale=args.locale,
    )


if __name__ == "__main__":
    main()
