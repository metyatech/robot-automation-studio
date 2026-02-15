"""Bridge readiness wait strategy helpers."""

from __future__ import annotations

from .models import normalize_unity_execution_mode


def build_recording_readiness_timeouts(
    *,
    changed: bool,
    execution_mode: str,
    changed_timeout_seconds: float = 15.0,
    quick_timeout_seconds: float = 3.0,
    attach_retry_timeout_seconds: float = 25.0,
) -> list[float]:
    mode = normalize_unity_execution_mode(execution_mode)
    initial = float(changed_timeout_seconds if changed else quick_timeout_seconds)
    if mode != "attach":
        return [max(0.1, initial)]
    retry_timeout = max(float(attach_retry_timeout_seconds), initial)
    if retry_timeout <= initial:
        return [max(0.1, initial)]
    return [max(0.1, initial), retry_timeout]
