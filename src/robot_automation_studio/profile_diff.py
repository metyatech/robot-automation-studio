"""Profile-to-profile resolved scenario diff helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Scenario
from .variable_resolution import resolve_scenario_payload


@dataclass(slots=True)
class ProfileDiffEntry:
    path: str
    base_value: Any
    compare_value: Any


def build_profile_diff(
    scenario: Scenario,
    *,
    base_profile: str,
    compare_profile: str,
) -> list[ProfileDiffEntry]:
    payload = scenario.to_dict()
    base = resolve_scenario_payload(payload, active_profile=base_profile)
    compare = resolve_scenario_payload(payload, active_profile=compare_profile)

    entries: list[ProfileDiffEntry] = []
    _collect_differences(base, compare, path="", out=entries)
    return entries


def _collect_differences(
    base: Any,
    compare: Any,
    *,
    path: str,
    out: list[ProfileDiffEntry],
) -> None:
    if type(base) is not type(compare):
        out.append(ProfileDiffEntry(path=path, base_value=base, compare_value=compare))
        return

    if isinstance(base, dict):
        keys = sorted({*base.keys(), *compare.keys()})
        for key in keys:
            next_path = f"{path}.{key}" if path else str(key)
            if key not in base:
                out.append(
                    ProfileDiffEntry(path=next_path, base_value=None, compare_value=compare[key])
                )
                continue
            if key not in compare:
                out.append(
                    ProfileDiffEntry(path=next_path, base_value=base[key], compare_value=None)
                )
                continue
            _collect_differences(base[key], compare[key], path=next_path, out=out)
        return

    if isinstance(base, list):
        max_length = max(len(base), len(compare))
        for index in range(max_length):
            next_path = f"{path}[{index}]"
            if index >= len(base):
                out.append(
                    ProfileDiffEntry(path=next_path, base_value=None, compare_value=compare[index])
                )
                continue
            if index >= len(compare):
                out.append(
                    ProfileDiffEntry(path=next_path, base_value=base[index], compare_value=None)
                )
                continue
            _collect_differences(base[index], compare[index], path=next_path, out=out)
        return

    if base != compare:
        out.append(ProfileDiffEntry(path=path, base_value=base, compare_value=compare))
