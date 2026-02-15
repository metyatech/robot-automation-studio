"""Core data models for scenario recording/editing/export."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

UNITY_EXECUTION_MODE_KEY = "unity_execution_mode"
UNITY_PROJECT_PATH_KEY = "unity_project_path"
TARGET_WINDOW_HINT_KEY = "target_window_hint"
SCHEMA_VERSION = "1.0.0"
VALID_UNITY_EXECUTION_MODES = {"attach", "launch"}


def _new_step_id() -> str:
    return uuid.uuid4().hex[:10]


def _new_scenario_id() -> str:
    return f"scenario-{uuid.uuid4().hex[:8]}"


def normalize_unity_execution_mode(value: Any) -> str:
    normalized = str(value or "attach").strip().lower()
    if normalized in VALID_UNITY_EXECUTION_MODES:
        return normalized
    return "attach"


@dataclass(slots=True)
class Step:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_step_id)
    title: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.action

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        return cls(
            id=str(data.get("id") or _new_step_id()),
            action=str(data["action"]),
            title=str(data.get("title") or data["action"]),
            params=dict(data.get("params") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Scenario:
    name: str
    scenario_id: str = field(default_factory=_new_scenario_id)
    target: str = "unity"
    steps: list[Step] = field(default_factory=list)
    target_window_hint: str = "Unity"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        metadata = dict(self.metadata)
        metadata[TARGET_WINDOW_HINT_KEY] = self.target_window_hint
        return {
            "schema_version": SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "target": self.target if self.target in {"unity", "web"} else "unity",
            "created_at": self.created_at,
            "metadata": metadata,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        schema_version = str(data.get("schema_version") or "")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {schema_version}")

        metadata = dict(data.get("metadata") or {})
        return cls(
            scenario_id=str(data.get("scenario_id") or _new_scenario_id()),
            target=str(data.get("target") or "unity"),
            name=str(data["name"]),
            target_window_hint=str(metadata.get(TARGET_WINDOW_HINT_KEY) or "Unity"),
            created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
            metadata=metadata,
            steps=[Step.from_dict(item) for item in list(data.get("steps") or [])],
        )

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> Scenario:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
