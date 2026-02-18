"""Action params template definitions (no Qt dependency)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_ACTION_ALIASES: dict[str, str] = {
    "drag": "drag_drop",
    "type": "type_text",
    "shortcut": "press_keys",
    "keys": "press_keys",
    "menu": "open_menu",
    "wait": "wait_for",
}

_TEMPLATES: dict[str, dict[str, object]] = {
    "click": {
        "target": {
            "strategy": "uia",
            "uia": {
                "title": "Inspector",
                "automation_id": "Inspector",
                "class_name": "Pane",
                "control_type": "Pane",
            },
        },
        "timing": {"stability_ms": 0},
    },
    "drag_drop": {
        "target": {
            "strategy": "coordinate",
            "coordinate": {"x_ratio": 0.6, "y_ratio": 0.5},
        },
        "input": {
            "source": {
                "strategy": "coordinate",
                "coordinate": {"x_ratio": 0.4, "y_ratio": 0.5},
            }
        },
        "timing": {"stability_ms": 0},
    },
    "press_keys": {"input": {"shortcut": "CTRL+S"}},
    "open_menu": {"input": {"menu_path": "File>Save"}},
    "type_text": {"input": {"text": "sample"}},
    "wait_for": {"input": {"seconds": 1.0}},
    "screenshot": {"input": {"path": "screenshots/step.png"}},
    "select_hierarchy": {
        "target": {
            "strategy": "unity_hierarchy",
            "unity_hierarchy": {"path": "Root/Object", "match_mode": "exact"},
        }
    },
    "assert": {"expect": {"condition": "True", "message": "Assertion failed"}},
    "open_url": {"input": {"url": "https://example.com"}},
    "double_click": {
        "target": {
            "strategy": "coordinate",
            "coordinate": {"x_ratio": 0.5, "y_ratio": 0.5},
        }
    },
    "right_click": {
        "target": {
            "strategy": "coordinate",
            "coordinate": {"x_ratio": 0.5, "y_ratio": 0.5},
        }
    },
    "start_video": {"input": {"path": "videos/run.mp4"}},
    "stop_video": {},
    "emit_annotation": {"input": {"annotation": {"type": "click", "label": "Click"}}},
    "run_subflow": {"input": {"path": "flows/subflow.robot"}},
}


def normalize_step_action_for_template(action: str) -> str:
    """Normalize action name using aliases."""
    normalized = str(action or "").strip().lower()
    return _ACTION_ALIASES.get(normalized, normalized)


def default_params_template_for_action(action: str) -> dict[str, Any] | None:
    """Return a deep-copied params template for the given action, or None."""
    normalized = normalize_step_action_for_template(action)
    template = _TEMPLATES.get(normalized)
    if template is None:
        return None
    return deepcopy(template)
