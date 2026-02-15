"""Helpers to detect Unity project path from attached Unity Editor windows."""

from __future__ import annotations

import re
import shlex
import subprocess
from collections.abc import Callable

import win32gui  # type: ignore[import-not-found]
import win32process  # type: ignore[import-not-found]


def extract_project_path_from_command_line(command_line: str) -> str | None:
    raw = str(command_line or "").strip()
    if raw == "":
        return None

    def _clean(value: str) -> str:
        return value.strip().strip('"').strip("'")

    try:
        tokens = shlex.split(raw, posix=False)
    except ValueError:
        tokens = []

    for index, token in enumerate(tokens):
        normalized = _clean(token)
        lower = normalized.lower()
        for prefix in ("-projectpath=", "/projectpath=", "-projectpath:", "/projectpath:"):
            if lower.startswith(prefix):
                value = _clean(normalized[len(prefix) :])
                return value or None
        if lower in ("-projectpath", "/projectpath"):
            if index + 1 >= len(tokens):
                return None
            value = _clean(tokens[index + 1])
            return value or None

    match = re.search(
        r"(?i)(?:-|/)projectpath(?:=|:|\s+)(?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        raw,
    )
    if not match:
        return None
    for group in match.groups():
        value = _clean(group or "")
        if value:
            return value
    return None


def get_process_command_line(process_id: int) -> str | None:
    if process_id <= 0:
        return None
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        f'(Get-CimInstance Win32_Process -Filter "ProcessId={process_id}").CommandLine',
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    return output or None


def get_window_process_id(window_handle: int) -> int | None:
    if window_handle <= 0:
        return None
    try:
        _thread_id, process_id = win32process.GetWindowThreadProcessId(window_handle)
    except Exception:
        return None
    if process_id <= 0:
        return None
    return int(process_id)


def _title_matches_window_hint(title: str, window_hint: str) -> bool:
    normalized_title = str(title or "").strip().lower()
    normalized_hint = str(window_hint or "").strip().lower()
    if normalized_hint == "":
        return normalized_title != ""
    return normalized_hint in normalized_title


def find_window_handles_by_hint(window_hint: str = "Unity") -> list[int]:
    handles: list[int] = []

    def _callback(window_handle: int, _param: int) -> bool:
        if not win32gui.IsWindowVisible(window_handle):
            return True
        title = str(win32gui.GetWindowText(window_handle) or "")
        if _title_matches_window_hint(title, window_hint):
            handles.append(int(window_handle))
        return True

    win32gui.EnumWindows(_callback, 0)
    return handles


def resolve_attached_unity_project_path(
    window_hint: str = "Unity",
    *,
    foreground_window_handle_getter: Callable[[], int] = win32gui.GetForegroundWindow,
    window_title_getter: Callable[[int], str] = win32gui.GetWindowText,
    candidate_window_handle_getter: Callable[[str], list[int]] = find_window_handles_by_hint,
    process_id_getter: Callable[[int], int | None] = get_window_process_id,
    process_command_line_getter: Callable[[int], str | None] = get_process_command_line,
) -> str | None:
    ordered_handles: list[int] = []

    foreground_handle = int(foreground_window_handle_getter() or 0)
    if foreground_handle > 0:
        foreground_title = str(window_title_getter(foreground_handle) or "")
        if _title_matches_window_hint(foreground_title, window_hint):
            ordered_handles.append(foreground_handle)

    for handle in candidate_window_handle_getter(window_hint):
        normalized = int(handle or 0)
        if normalized <= 0:
            continue
        if normalized in ordered_handles:
            continue
        ordered_handles.append(normalized)

    for window_handle in ordered_handles:
        process_id = process_id_getter(window_handle)
        if process_id is None:
            continue
        command_line = process_command_line_getter(process_id)
        project_path = extract_project_path_from_command_line(str(command_line or ""))
        if project_path:
            return project_path

    return None
