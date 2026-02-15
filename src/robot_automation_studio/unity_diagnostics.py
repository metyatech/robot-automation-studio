"""Unity diagnostics helpers for actionable error reporting."""

from __future__ import annotations

import os
import re
from pathlib import Path

_CS_ERROR_PATTERN = re.compile(r"\berror\s+CS\d+\b", re.IGNORECASE)


def default_unity_editor_log_path() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        return Path(local_appdata) / "Unity" / "Editor" / "Editor.log"
    return Path("Editor.log")


def extract_recent_unity_compile_errors(log_text: str, limit: int = 3) -> list[str]:
    lines = [line.strip() for line in str(log_text or "").splitlines()]
    matched = [line for line in lines if _CS_ERROR_PATTERN.search(line)]
    if not matched:
        return []
    return matched[-max(1, int(limit)) :]


def get_recent_unity_compile_errors(
    editor_log_path: Path | None = None,
    limit: int = 3,
) -> list[str]:
    path = editor_log_path or default_unity_editor_log_path()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    return extract_recent_unity_compile_errors(text, limit=limit)
