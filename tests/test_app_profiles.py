from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.preflight_validation import ValidationIssue, ValidationReport


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_active_profile_combo_lists_profiles_and_help() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.scenario.profiles = {
            "default": {"description": "Base settings", "variables": {}},
            "vrchat": {"description": "", "variables": {}},
        }
        studio.scenario.execution = {"active_profile": "default"}
        studio._refresh_active_profile_combo()

        assert studio.active_profile_combo.count() == 3
        assert studio.active_profile_combo.itemData(0, Qt.ItemDataRole.UserRole) == ""
        assert studio.active_profile_combo.itemData(1, Qt.ItemDataRole.UserRole) == "default"
        assert studio.active_profile_combo.itemData(2, Qt.ItemDataRole.UserRole) == "vrchat"
        assert studio.active_profile_combo.currentData(Qt.ItemDataRole.UserRole) == "default"

        no_profile_tip = studio.active_profile_combo.itemData(0, Qt.ItemDataRole.ToolTipRole)
        default_tip = studio.active_profile_combo.itemData(1, Qt.ItemDataRole.ToolTipRole)
        vrchat_tip = studio.active_profile_combo.itemData(2, Qt.ItemDataRole.ToolTipRole)
        assert no_profile_tip == "Use variable defaults (no profile override)."
        assert default_tip == "Use profile 'default' overrides. Base settings"
        assert vrchat_tip == "Use profile 'vrchat' overrides."
    finally:
        studio.close()


def test_sync_scenario_header_persists_active_profile_selection() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.scenario.profiles = {"vrchat": {"description": "", "variables": {}}}
        studio._refresh_active_profile_combo()
        studio._set_combo_value(studio.active_profile_combo, "vrchat")

        studio._sync_scenario_header()
        assert studio.scenario.execution.get("active_profile") == "vrchat"

        studio._set_combo_value(studio.active_profile_combo, "")
        studio._sync_scenario_header()
        assert "active_profile" not in studio.scenario.execution
    finally:
        studio.close()


def test_sync_scenario_header_persists_subflow_timeout_setting() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.subflow_timeout_edit.setText("120")
        studio._sync_scenario_header()
        assert studio.scenario.execution.get("subflow_timeout_seconds") == 120

        studio.subflow_timeout_edit.setText("${subflow_timeout}")
        studio._sync_scenario_header()
        assert studio.scenario.execution.get("subflow_timeout_seconds") == "${subflow_timeout}"

        studio.subflow_timeout_edit.setText("")
        studio._sync_scenario_header()
        assert "subflow_timeout_seconds" not in studio.scenario.execution
    finally:
        studio.close()


def test_subflow_timeout_edit_allows_number_or_placeholder() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        validator = studio.subflow_timeout_edit.validator()
        assert isinstance(validator, QValidator)

        number_state = cast(tuple[QValidator.State, str, int], validator.validate("120", 3))[0]
        placeholder_state = cast(
            tuple[QValidator.State, str, int],
            validator.validate("${subflow_timeout}", 18),
        )[0]
        spaced_placeholder_state = cast(
            tuple[QValidator.State, str, int],
            validator.validate(" ${subflow_timeout} ", 20),
        )[0]
        blank_state = cast(tuple[QValidator.State, str, int], validator.validate("", 0))[0]
        partial_placeholder_state = cast(
            tuple[QValidator.State, str, int],
            validator.validate("${sub", 5),
        )[0]
        zero_state = cast(tuple[QValidator.State, str, int], validator.validate("0", 1))[0]
        out_of_range_state = cast(
            tuple[QValidator.State, str, int],
            validator.validate("86401", 5),
        )[0]
        mixed_state = cast(
            tuple[QValidator.State, str, int],
            validator.validate("${subflow_timeout}s", 19),
        )[0]

        assert number_state == QValidator.State.Acceptable
        assert placeholder_state == QValidator.State.Acceptable
        assert spaced_placeholder_state == QValidator.State.Acceptable
        assert blank_state == QValidator.State.Acceptable
        assert partial_placeholder_state == QValidator.State.Intermediate
        assert zero_state == QValidator.State.Invalid
        assert out_of_range_state == QValidator.State.Invalid
        assert mixed_state == QValidator.State.Invalid
    finally:
        studio.close()


def test_subflow_timeout_validation_label_updates_for_all_input_types() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.subflow_timeout_edit.setText("")
        studio._refresh_subflow_timeout_validation_hint()
        assert "Default: 3600s." in studio.subflow_timeout_validation_label.text()

        studio.subflow_timeout_edit.setText("120")
        studio._refresh_subflow_timeout_validation_hint()
        assert "Using: 120s." in studio.subflow_timeout_validation_label.text()

        studio.subflow_timeout_edit.setText("${subflow_timeout}")
        studio._refresh_subflow_timeout_validation_hint()
        assert "Variable: ${subflow_timeout}" in studio.subflow_timeout_validation_label.text()

        studio.subflow_timeout_edit.setText("86401")
        studio._refresh_subflow_timeout_validation_hint()
        assert "Invalid. Use 1..86400, blank, or ${variable}." in (
            studio.subflow_timeout_validation_label.text()
        )
    finally:
        studio.close()


def test_subflow_timeout_validation_label_shows_rejected_hint() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._on_subflow_timeout_input_rejected()
        assert "Rejected input." in studio.subflow_timeout_validation_label.text()
    finally:
        studio.close()


def test_subflow_timeout_validation_label_is_localized_in_japanese() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="ja")
    try:
        studio.subflow_timeout_edit.setText("86401")
        studio._refresh_subflow_timeout_validation_hint()
        assert "無効です。1..86400、空欄、${変数} を使用してください。" in (
            studio.subflow_timeout_validation_label.text()
        )
    finally:
        studio.close()


def test_export_scenario_passes_active_profile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, str | None] = {"active_profile": None}

        class _FakeExportResult:
            robot_path = tmp_path / "suite.robot"
            json_path = tmp_path / "suite.scenario.json"

        def _fake_export_all(
            scenario,
            output_dir,
            suite_name,
            active_profile=None,
        ):
            _ = (scenario, output_dir, suite_name)
            captured["active_profile"] = active_profile
            return _FakeExportResult()

        studio.scenario.profiles = {"vrchat": {"description": "VRChat", "variables": {}}}
        studio.scenario.execution = {"active_profile": "vrchat"}
        studio._refresh_active_profile_combo()
        studio._set_combo_value(studio.active_profile_combo, "vrchat")
        studio.output_dir_edit.setText(str(tmp_path / "artifacts"))
        studio.export_name_edit.setText("suite")

        monkeypatch.setattr("robot_automation_studio.app.export_all", _fake_export_all)
        studio.export_scenario()

        assert captured["active_profile"] == "vrchat"
    finally:
        studio.close()


def test_export_scenario_fails_fast_when_preflight_validation_has_issues(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        report = ValidationReport(
            issues=[
                ValidationIssue(
                    code="scenario.invalid",
                    message="required variable 'unity_project_path' is missing.",
                    location="variables.unity_project_path.default",
                )
            ]
        )
        captured: dict[str, str] = {}

        monkeypatch.setattr(
            "robot_automation_studio.app.validate_scenario", lambda *args, **kwargs: report
        )
        monkeypatch.setattr(
            "robot_automation_studio.app_dialogs.open_validation_report_dialog",
            lambda _self, _report, *, title: captured.setdefault("title", title),
        )

        studio.export_scenario()

        assert captured["title"] == "Preflight Validation"
    finally:
        studio.close()
