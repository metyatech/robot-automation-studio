"""Scenario preflight validation before export/run."""

from __future__ import annotations

from dataclasses import dataclass, field

from .exporter import validate_exportable_scenario
from .models import Scenario


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
                location="scenario",
            )
        )
        return report
    report.resolved_scenario = resolved
    return report
