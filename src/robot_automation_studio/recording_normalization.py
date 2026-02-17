"""Post-processing helpers to make GUI-recorded steps more reusable across projects."""

from __future__ import annotations

import re
from typing import Any

from .models import Scenario

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_recorded_hierarchy_paths_to_variables(
    scenario: Scenario,
    *,
    step_start_index: int = 0,
    root_variable_id: str = "avatar_root",
    relative_prefix: str = "hier_",
) -> None:
    """Normalize recorded Unity hierarchy selector paths into variables.

    This is intended to make recorded scenarios easier to reuse across avatars/projects:
    - Extracts the most common root segment as `${avatar_root}`.
    - Creates one variable per relative hierarchy suffix.
    - Rewrites unity_hierarchy selector paths to `${avatar_root}/${hier_*}`.
    - Rewrites wildcard fallbacks from `*/Suffix` to `*/${hier_*}`.
    """

    steps = list(scenario.steps[int(step_start_index or 0) :])
    hierarchy_paths: list[str] = []
    for step in steps:
        raw_target = step.params.get("target")
        if not isinstance(raw_target, dict):
            continue
        if str(raw_target.get("strategy") or "").strip().lower() != "unity_hierarchy":
            continue
        unity_hierarchy = raw_target.get("unity_hierarchy")
        if not isinstance(unity_hierarchy, dict):
            continue
        path = _normalize_hierarchy_path(str(unity_hierarchy.get("path") or ""))
        if path:
            hierarchy_paths.append(path)

    root_counts: dict[str, int] = {}
    for path in hierarchy_paths:
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 2:
            continue
        root = segments[0]
        root_counts[root] = root_counts.get(root, 0) + 1
    if not root_counts:
        return

    avatar_root = sorted(root_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    _upsert_variable_default(
        scenario,
        variable_id=root_variable_id,
        default=str(avatar_root),
        variable_type="string",
    )

    existing_ids = {
        str(item.get("id") or "").strip()
        for item in scenario.variables
        if isinstance(item, dict) and str(item.get("id") or "").strip() != ""
    }
    relative_vars: dict[str, str] = {}
    for path in hierarchy_paths:
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 2:
            continue
        if segments[0] != avatar_root:
            continue
        relative = "/".join(segments[1:])
        if relative in relative_vars:
            continue
        base_id = f"{relative_prefix}{_slugify_relative_path(relative)}"
        variable_id = _ensure_unique_variable_id(
            base_id,
            default_value=relative,
            existing_ids=existing_ids,
            existing_variables=scenario.variables,
        )
        relative_vars[relative] = variable_id
        existing_ids.add(variable_id)
        _upsert_variable_default(
            scenario,
            variable_id=variable_id,
            default=relative,
            variable_type="string",
        )

    for step in steps:
        target = step.params.get("target")
        if not isinstance(target, dict):
            continue
        if str(target.get("strategy") or "").strip().lower() != "unity_hierarchy":
            continue
        unity_hierarchy = target.get("unity_hierarchy")
        if not isinstance(unity_hierarchy, dict):
            continue
        current_path = _normalize_hierarchy_path(str(unity_hierarchy.get("path") or ""))
        segments = [segment for segment in current_path.split("/") if segment]
        if len(segments) < 2 or segments[0] != avatar_root:
            continue
        relative = "/".join(segments[1:])
        relative_var_id = relative_vars.get(relative)
        if not relative_var_id:
            continue
        unity_hierarchy["path"] = f"${{{root_variable_id}}}/${{{relative_var_id}}}"
        fallbacks = target.get("fallbacks")
        if not isinstance(fallbacks, list):
            continue
        wildcard_path = f"*/{relative}"
        for fallback in fallbacks:
            if not isinstance(fallback, dict):
                continue
            if str(fallback.get("strategy") or "").strip().lower() != "unity_hierarchy":
                continue
            fallback_payload = fallback.get("unity_hierarchy")
            if not isinstance(fallback_payload, dict):
                continue
            fallback_path = _normalize_hierarchy_path(str(fallback_payload.get("path") or ""))
            if fallback_path != wildcard_path:
                continue
            fallback_payload["path"] = f"*/${{{relative_var_id}}}"


def _normalize_hierarchy_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").strip("/")


def _slugify_relative_path(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("\\", "/")
    normalized = _NON_ALNUM_RE.sub("_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if normalized == "":
        return "path"
    return normalized


def _ensure_unique_variable_id(
    base_id: str,
    *,
    default_value: str,
    existing_ids: set[str],
    existing_variables: list[dict[str, Any]],
) -> str:
    """Return base_id, or a suffixed variant if it would collide."""

    normalized_base = str(base_id or "").strip()
    if normalized_base == "":
        normalized_base = "hier_path"
    if normalized_base not in existing_ids:
        return normalized_base

    for item in existing_variables:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip() != normalized_base:
            continue
        if str(item.get("default") or "").strip() == str(default_value or "").strip():
            return normalized_base

    index = 2
    while True:
        candidate = f"{normalized_base}_{index}"
        if candidate not in existing_ids:
            return candidate
        index += 1


def _upsert_variable_default(
    scenario: Scenario,
    *,
    variable_id: str,
    default: Any,
    variable_type: str,
) -> None:
    normalized_id = str(variable_id or "").strip()
    if normalized_id == "":
        return
    for item in scenario.variables:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip() != normalized_id:
            continue
        if item.get("default") in (None, ""):
            item["default"] = default
        if "type" not in item or str(item.get("type") or "").strip() == "":
            item["type"] = variable_type
        return
    scenario.variables.append(
        {
            "id": normalized_id,
            "type": variable_type,
            "default": default,
        }
    )
