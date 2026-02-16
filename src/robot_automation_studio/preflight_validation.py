"""Scenario preflight validation before export/run."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .exporter import validate_exportable_scenario
from .models import Scenario

_AT_PATH_RE = re.compile(r"\sat\s([A-Za-z0-9_.\[\]-]+)$")
_MISSING_VARIABLE_RE = re.compile(r"required variable '([A-Za-z0-9_-]+)' is missing")


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    location: str = ""


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    resolved_scenario: Scenario | None = None

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def _infer_issue_location(error_message: str) -> str:
    text = str(error_message or "").strip()
    if text == "":
        return "scenario"

    at_path_match = _AT_PATH_RE.search(text)
    if at_path_match is not None:
        return at_path_match.group(1)

    missing_variable_match = _MISSING_VARIABLE_RE.search(text)
    if missing_variable_match is not None:
        return f"variables.{missing_variable_match.group(1)}.default"

    if text.startswith("Unknown profile:"):
        return "execution.active_profile"
    return "scenario"


def validate_scenario(
    scenario: Scenario,
    *,
    active_profile: str | None = None,
) -> ValidationReport:
    """Return preflight validation report for run/export."""

    report = ValidationReport()
    try:
        resolved = validate_exportable_scenario(
            scenario,
            active_profile=active_profile,
        )
    except Exception as error:
        report.issues.append(
            ValidationIssue(
                code="scenario.invalid",
                message=str(error),
                location=_infer_issue_location(str(error)),
            )
        )
        return report
    report.resolved_scenario = resolved
    return report
