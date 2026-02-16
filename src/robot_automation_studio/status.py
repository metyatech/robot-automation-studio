"""Run status formatting helpers for Studio UI."""

from __future__ import annotations

from .i18n import translate

SPINNER_FRAMES = ("|", "/", "-", "\\")

_PHASE_LABELS = {
    "idle": "status.phase.idle",
    "precheck": "status.phase.precheck",
    "exporting": "status.phase.exporting",
    "starting_robot": "status.phase.starting_robot",
    "attaching_unity": "status.phase.attaching_unity",
    "running": "status.phase.running",
    "stopping": "status.phase.stopping",
}


def next_spinner_index(current: int, size: int = len(SPINNER_FRAMES)) -> int:
    if size <= 0:
        return 0
    return (max(0, int(current)) + 1) % size


def format_run_status(phase: str, spinner_frame: str, *, locale: str = "en") -> str:
    normalized = str(phase or "").strip().lower()
    if normalized == "idle":
        return translate(_PHASE_LABELS["idle"], locale=locale)
    if normalized == "stopping":
        return translate(_PHASE_LABELS["stopping"], locale=locale)
    if normalized in _PHASE_LABELS:
        return f"{translate(_PHASE_LABELS[normalized], locale=locale)} {spinner_frame}"
    return f"{translate(_PHASE_LABELS['running'], locale=locale)} {spinner_frame}"
