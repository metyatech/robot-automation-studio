"""Run status formatting helpers for Studio UI."""

from __future__ import annotations

SPINNER_FRAMES = ("|", "/", "-", "\\")

_PHASE_LABELS = {
    "idle": "Idle",
    "exporting": "Exporting scenario",
    "starting_robot": "Starting Robot",
    "attaching_unity": "Attaching to Unity",
    "running": "Running",
    "stopping": "Stopping...",
}


def next_spinner_index(current: int, size: int = len(SPINNER_FRAMES)) -> int:
    if size <= 0:
        return 0
    return (max(0, int(current)) + 1) % size


def format_run_status(phase: str, spinner_frame: str) -> str:
    normalized = str(phase or "").strip().lower()
    if normalized == "idle":
        return _PHASE_LABELS["idle"]
    if normalized == "stopping":
        return _PHASE_LABELS["stopping"]
    if normalized in _PHASE_LABELS:
        return f"{_PHASE_LABELS[normalized]} {spinner_frame}"
    return f"{_PHASE_LABELS['running']} {spinner_frame}"
