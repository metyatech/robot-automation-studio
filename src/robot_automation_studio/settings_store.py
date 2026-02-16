"""Persistent Studio UI settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .hotkey import DEFAULT_STOP_HOTKEY_LABEL
from .i18n import normalize_locale
from .models import normalize_unity_execution_mode

SETTINGS_PATH_ENV = "ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH"


@dataclass(slots=True)
class StudioUiSettings:
    locale: str = "en"
    target: str = "unity"
    window_hint: str = "Unity"
    execution_mode: str = "attach"
    unity_project_path: str = ""
    stop_hotkey_label: str = DEFAULT_STOP_HOTKEY_LABEL


def resolve_settings_path() -> Path:
    override = os.getenv(SETTINGS_PATH_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".robot-automation-studio" / "settings.json"


def load_ui_settings(path: Path | None = None) -> StudioUiSettings:
    settings_path = path or resolve_settings_path()
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return StudioUiSettings()
    if not isinstance(payload, dict):
        return StudioUiSettings()
    return StudioUiSettings(
        locale=normalize_locale(payload.get("locale")),
        target=_normalize_target(payload.get("target")),
        window_hint=_normalize_window_hint(payload.get("window_hint")),
        execution_mode=normalize_unity_execution_mode(payload.get("execution_mode", "attach")),
        unity_project_path=str(payload.get("unity_project_path") or "").strip(),
        stop_hotkey_label=str(payload.get("stop_hotkey_label") or DEFAULT_STOP_HOTKEY_LABEL).strip()
        or DEFAULT_STOP_HOTKEY_LABEL,
    )


def save_ui_settings(settings: StudioUiSettings, path: Path | None = None) -> Path:
    settings_path = path or resolve_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "locale": normalize_locale(settings.locale),
        "target": _normalize_target(settings.target),
        "window_hint": _normalize_window_hint(settings.window_hint),
        "execution_mode": normalize_unity_execution_mode(settings.execution_mode),
        "unity_project_path": str(settings.unity_project_path or "").strip(),
        "stop_hotkey_label": str(settings.stop_hotkey_label or DEFAULT_STOP_HOTKEY_LABEL).strip()
        or DEFAULT_STOP_HOTKEY_LABEL,
    }
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return settings_path


def _normalize_target(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"unity", "web", "desktop", "hybrid"}:
        return normalized
    return "unity"


def _normalize_window_hint(value: object) -> str:
    normalized = str(value or "").strip()
    return normalized or "Unity"
