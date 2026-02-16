"""Scenario editor dialog helpers for StudioApp."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import Scenario
from .preflight_validation import ValidationReport
from .profile_diff import ProfileDiffEntry, build_profile_diff


def _parse_json_or_text(raw_text: str) -> Any:
    text = str(raw_text or "").strip()
    if text == "":
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def normalize_variable_form_payload(
    *,
    variable_id: str,
    variable_type: str,
    required: bool,
    default_text: str,
) -> dict[str, Any]:
    normalized_id = str(variable_id or "").strip()
    if normalized_id == "":
        raise ValueError("Variable id is required.")
    normalized_type = str(variable_type or "").strip()
    if normalized_type == "":
        raise ValueError("Variable type is required.")
    return {
        "id": normalized_id,
        "type": normalized_type,
        "required": bool(required),
        "default": str(default_text or ""),
    }


def normalize_profile_form_payload(
    *,
    profile_name: str,
    description: str,
    override_rows: list[tuple[str, str]],
) -> dict[str, Any]:
    normalized_name = str(profile_name or "").strip()
    if normalized_name == "":
        raise ValueError("Profile name is required.")
    variables: dict[str, Any] = {}
    for raw_key, raw_value in override_rows:
        key = str(raw_key or "").strip()
        value_text = str(raw_value or "")
        if key == "":
            if value_text.strip() == "":
                continue
            raise ValueError("Profile variable key is required.")
        variables[key] = _parse_json_or_text(value_text)
    return {
        "name": normalized_name,
        "profile": {
            "description": str(description or "").strip(),
            "variables": variables,
        },
    }


def open_full_json_editor(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.full_json.title"))
    dialog.resize(960, 720)

    layout = QVBoxLayout(dialog)

    top_layout = QHBoxLayout()
    format_button = QPushButton(self._t("app.button.format"))
    top_layout.addWidget(format_button)
    reload_button = QPushButton(self._t("app.button.reload_model"))
    top_layout.addWidget(reload_button)
    top_layout.addStretch()
    cancel_button = QPushButton(self._t("app.button.cancel"))
    top_layout.addWidget(cancel_button)
    apply_button = QPushButton(self._t("app.button.apply"))
    apply_button.setObjectName("ApplyButton")
    top_layout.addWidget(apply_button)
    layout.addLayout(top_layout)

    text = QPlainTextEdit()
    text.setFont(QFont("Consolas", 9))
    text.setPlainText(json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))
    layout.addWidget(text, 1)

    def _format_json() -> None:
        try:
            payload = json.loads(text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(dialog, self._t("app.error.full_json_invalid.title"), str(error))
            return
        text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    def _reload_model() -> None:
        self._sync_scenario_header()
        text.setPlainText(json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))

    def _apply_json() -> None:
        try:
            payload = json.loads(text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(dialog, self._t("app.error.full_json_invalid.title"), str(error))
            return
        try:
            loaded = Scenario.from_dict(payload)
        except Exception as error:
            QMessageBox.critical(
                dialog, self._t("app.error.full_json_validation.title"), str(error)
            )
            return
        self._apply_loaded_scenario(loaded)
        self.log(self._t("app.log.applied_full_json"))
        dialog.accept()

    format_button.clicked.connect(_format_json)
    reload_button.clicked.connect(_reload_model)
    apply_button.clicked.connect(_apply_json)
    cancel_button.clicked.connect(dialog.reject)

    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def open_variables_editor(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.variables.title"))
    dialog.resize(980, 620)

    variables = [deepcopy(item) for item in self.scenario.variables if isinstance(item, dict)]

    layout = QVBoxLayout(dialog)

    body_layout = QHBoxLayout()
    listbox = QListWidget()
    listbox.setMinimumWidth(260)
    body_layout.addWidget(listbox)

    form_container = QWidget()
    form_layout = QFormLayout(form_container)
    form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form_layout.setSpacing(8)

    variable_id_edit = QLineEdit()
    variable_type_edit = QLineEdit()
    variable_required_check = QCheckBox()
    variable_default_edit = QLineEdit()

    form_layout.addRow(self._t("app.field.variable_id.label"), variable_id_edit)
    form_layout.addRow(self._t("app.field.variable_type.label"), variable_type_edit)
    form_layout.addRow(self._t("app.field.variable_required.label"), variable_required_check)
    form_layout.addRow(self._t("app.field.variable_default.label"), variable_default_edit)

    body_layout.addWidget(form_container, 1)
    layout.addLayout(body_layout, 1)

    def _refresh_list() -> None:
        listbox.clear()
        for index, variable in enumerate(variables):
            variable_id = str(variable.get("id") or f"var-{index + 1}")
            variable_type = str(variable.get("type") or "string")
            listbox.addItem(
                self._t(
                    "app.list.item.variable",
                    index=index + 1,
                    id=variable_id,
                    type=variable_type,
                )
            )

    def _select(index: int) -> None:
        if index < 0 or index >= len(variables):
            return
        variable = variables[index]
        listbox.setCurrentRow(index)
        variable_id_edit.setText(str(variable.get("id") or ""))
        variable_type_edit.setText(str(variable.get("type") or "string"))
        variable_required_check.setChecked(bool(variable.get("required", False)))
        default_value = variable.get("default")
        variable_default_edit.setText("" if default_value is None else str(default_value))

    def _on_select(row: int) -> None:
        if row < 0 or row >= len(variables):
            return
        _select(row)

    def _apply_current() -> bool:
        row = listbox.currentRow()
        if row < 0:
            return True
        try:
            payload = normalize_variable_form_payload(
                variable_id=variable_id_edit.text(),
                variable_type=variable_type_edit.text(),
                required=variable_required_check.isChecked(),
                default_text=variable_default_edit.text(),
            )
        except ValueError as error:
            QMessageBox.critical(
                dialog, self._t("app.error.variable_json_invalid.title"), str(error)
            )
            return False
        previous = variables[row]
        extras = {
            key: deepcopy(value)
            for key, value in previous.items()
            if key not in {"id", "type", "required", "default"}
        }
        payload.update(extras)
        variables[row] = payload
        _refresh_list()
        _select(row)
        return True

    def _add_variable() -> None:
        if not _apply_current():
            return
        next_index = len(variables) + 1
        variables.append(
            {
                "id": f"var_{next_index}",
                "type": "string",
                "required": False,
                "default": "",
            }
        )
        _refresh_list()
        _select(len(variables) - 1)

    def _delete_variable() -> None:
        row = listbox.currentRow()
        if row < 0:
            return
        variables.pop(row)
        _refresh_list()
        if variables:
            _select(min(row, len(variables) - 1))
        else:
            variable_id_edit.clear()
            variable_type_edit.setText("string")
            variable_required_check.setChecked(False)
            variable_default_edit.clear()

    def _save_and_close() -> None:
        if not _apply_current():
            return
        self.scenario.variables = variables
        self.log(self._t("app.log.updated_variables"))
        dialog.accept()

    footer_layout = QHBoxLayout()
    add_button = QPushButton(self._t("app.button.add"))
    add_button.clicked.connect(_add_variable)
    footer_layout.addWidget(add_button)
    delete_button = QPushButton(self._t("app.button.delete_word"))
    delete_button.clicked.connect(_delete_variable)
    footer_layout.addWidget(delete_button)
    apply_button = QPushButton(self._t("app.button.apply_current"))
    apply_button.setObjectName("ApplyButton")
    apply_button.clicked.connect(_apply_current)
    footer_layout.addWidget(apply_button)
    footer_layout.addStretch()
    cancel_button = QPushButton(self._t("app.button.cancel"))
    cancel_button.clicked.connect(dialog.reject)
    footer_layout.addWidget(cancel_button)
    save_button = QPushButton(self._t("app.button.save"))
    save_button.setObjectName("ApplyButton")
    save_button.clicked.connect(_save_and_close)
    footer_layout.addWidget(save_button)
    layout.addLayout(footer_layout)

    listbox.currentRowChanged.connect(_on_select)
    _refresh_list()
    if variables:
        _select(0)
    else:
        variable_type_edit.setText("string")

    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def open_profiles_editor(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.profiles.title"))
    dialog.resize(1040, 680)

    profiles = dict(self.scenario.profiles or {})
    profile_names = sorted(profiles.keys())

    layout = QVBoxLayout(dialog)

    body_layout = QHBoxLayout()
    listbox = QListWidget()
    listbox.setMinimumWidth(260)
    body_layout.addWidget(listbox)

    form_container = QWidget()
    form_layout = QVBoxLayout(form_container)

    identity_form = QFormLayout()
    identity_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    identity_form.setSpacing(8)

    profile_name_edit = QLineEdit()
    profile_description_edit = QLineEdit()
    identity_form.addRow(self._t("app.field.profile_name.label"), profile_name_edit)
    identity_form.addRow(self._t("app.field.profile_description.label"), profile_description_edit)
    form_layout.addLayout(identity_form)

    overrides_label = QLabel(self._t("app.field.profile_overrides.label"))
    overrides_label.setObjectName("PanelTitle")
    form_layout.addWidget(overrides_label)

    overrides_table = QTableWidget(0, 2)
    overrides_table.setHorizontalHeaderLabels(
        [
            self._t("app.field.profile_override_key.label"),
            self._t("app.field.profile_override_value.label"),
        ]
    )
    overrides_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    overrides_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    form_layout.addWidget(overrides_table, 1)

    override_buttons = QHBoxLayout()
    add_override_button = QPushButton(self._t("app.button.add_override"))
    remove_override_button = QPushButton(self._t("app.button.remove_override"))
    override_buttons.addWidget(add_override_button)
    override_buttons.addWidget(remove_override_button)
    override_buttons.addStretch()
    form_layout.addLayout(override_buttons)

    body_layout.addWidget(form_container, 1)
    layout.addLayout(body_layout, 1)

    def _refresh_list() -> None:
        listbox.clear()
        for index, name in enumerate(profile_names):
            listbox.addItem(self._t("app.list.item.profile", index=index + 1, name=name))

    def _read_override_rows_from_table() -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for row in range(overrides_table.rowCount()):
            key_item = overrides_table.item(row, 0)
            value_item = overrides_table.item(row, 1)
            key = "" if key_item is None else key_item.text()
            value = "" if value_item is None else value_item.text()
            rows.append((key, value))
        return rows

    def _fill_override_table(overrides: dict[str, Any]) -> None:
        overrides_table.setRowCount(0)
        for variable_id, value in sorted(overrides.items(), key=lambda item: str(item[0])):
            row = overrides_table.rowCount()
            overrides_table.insertRow(row)
            overrides_table.setItem(row, 0, QTableWidgetItem(str(variable_id)))
            value_text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            overrides_table.setItem(row, 1, QTableWidgetItem(value_text))

    def _select(index: int) -> None:
        if index < 0 or index >= len(profile_names):
            return
        name = profile_names[index]
        payload = deepcopy(profiles.get(name, {}))
        listbox.setCurrentRow(index)
        profile_name_edit.setText(name)
        profile_description_edit.setText(str(payload.get("description") or ""))
        variables_payload = payload.get("variables")
        if isinstance(variables_payload, dict):
            _fill_override_table(variables_payload)
        else:
            _fill_override_table({})

    def _on_select(row: int) -> None:
        if row < 0 or row >= len(profile_names):
            return
        _select(row)

    def _apply_current() -> bool:
        row = listbox.currentRow()
        if row < 0:
            return True
        current_name = profile_names[row]
        try:
            payload = normalize_profile_form_payload(
                profile_name=profile_name_edit.text(),
                description=profile_description_edit.text(),
                override_rows=_read_override_rows_from_table(),
            )
        except ValueError as error:
            QMessageBox.critical(
                dialog, self._t("app.error.profile_json_invalid.title"), str(error)
            )
            return False
        name = str(payload["name"])
        profile = dict(payload["profile"])
        previous_payload = profiles.get(current_name)
        previous_profile = previous_payload if isinstance(previous_payload, dict) else {}
        extras = {
            key: deepcopy(value)
            for key, value in previous_profile.items()
            if key not in {"description", "variables"}
        }
        profile.update(extras)
        profiles.pop(current_name, None)
        profiles[name] = profile
        profile_names[:] = sorted(profiles.keys())
        _refresh_list()
        _select(profile_names.index(name))
        return True

    def _add_profile() -> None:
        if not _apply_current():
            return
        next_index = len(profile_names) + 1
        name = f"profile-{next_index}"
        profiles[name] = {"description": "", "variables": {}}
        profile_names[:] = sorted(profiles.keys())
        _refresh_list()
        _select(profile_names.index(name))

    def _delete_profile() -> None:
        row = listbox.currentRow()
        if row < 0:
            return
        name = profile_names[row]
        profiles.pop(name, None)
        profile_names[:] = sorted(profiles.keys())
        _refresh_list()
        if profile_names:
            _select(min(row, len(profile_names) - 1))
        else:
            profile_name_edit.clear()
            profile_description_edit.clear()
            overrides_table.setRowCount(0)

    def _save_and_close() -> None:
        if not _apply_current():
            return
        self.scenario.profiles = profiles
        self.log(self._t("app.log.updated_profiles"))
        dialog.accept()

    footer_layout = QHBoxLayout()
    add_button = QPushButton(self._t("app.button.add"))
    add_button.clicked.connect(_add_profile)
    footer_layout.addWidget(add_button)
    delete_button = QPushButton(self._t("app.button.delete_word"))
    delete_button.clicked.connect(_delete_profile)
    footer_layout.addWidget(delete_button)
    apply_button = QPushButton(self._t("app.button.apply_current"))
    apply_button.setObjectName("ApplyButton")
    apply_button.clicked.connect(_apply_current)
    footer_layout.addWidget(apply_button)
    footer_layout.addStretch()
    cancel_button = QPushButton(self._t("app.button.cancel"))
    cancel_button.clicked.connect(dialog.reject)
    footer_layout.addWidget(cancel_button)
    save_button = QPushButton(self._t("app.button.save"))
    save_button.setObjectName("ApplyButton")
    save_button.clicked.connect(_save_and_close)
    footer_layout.addWidget(save_button)
    layout.addLayout(footer_layout)

    def _add_override_row() -> None:
        row = overrides_table.rowCount()
        overrides_table.insertRow(row)
        overrides_table.setItem(row, 0, QTableWidgetItem(""))
        overrides_table.setItem(row, 1, QTableWidgetItem(""))
        overrides_table.setCurrentCell(row, 0)

    def _remove_override_row() -> None:
        row = overrides_table.currentRow()
        if row >= 0:
            overrides_table.removeRow(row)

    add_override_button.clicked.connect(_add_override_row)
    remove_override_button.clicked.connect(_remove_override_row)

    listbox.currentRowChanged.connect(_on_select)
    _refresh_list()
    if profile_names:
        _select(0)
    else:
        _add_override_row()

    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def _format_diff_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _diff_entries_to_text(entries: list[ProfileDiffEntry]) -> str:
    if not entries:
        return "-"
    lines: list[str] = []
    for item in entries:
        lines.append(f"[{item.path}]")
        lines.append(f"  base: {_format_diff_value(item.base_value)}")
        lines.append(f"  compare: {_format_diff_value(item.compare_value)}")
        lines.append("")
    return "\n".join(lines).strip()


def open_profile_diff_preview_dialog(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.profile_diff.title"))
    dialog.resize(1040, 700)

    layout = QVBoxLayout(dialog)

    selector_layout = QFormLayout()
    selector_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    base_profile_combo = QComboBox()
    compare_profile_combo = QComboBox()
    selector_layout.addRow(self._t("app.field.profile_diff.base.label"), base_profile_combo)
    selector_layout.addRow(self._t("app.field.profile_diff.compare.label"), compare_profile_combo)
    layout.addLayout(selector_layout)

    profiles = sorted(
        {
            str(name or "").strip()
            for name in dict(self.scenario.profiles or {})
            if str(name or "").strip()
        }
    )
    for combo in (base_profile_combo, compare_profile_combo):
        combo.addItem(self._t("app.option.profile.none"), "")
        for profile_name in profiles:
            combo.addItem(profile_name, profile_name)
    active_profile = self._active_profile_value()
    active_index = base_profile_combo.findData(active_profile, Qt.ItemDataRole.UserRole)
    if active_index >= 0:
        base_profile_combo.setCurrentIndex(active_index)
    if compare_profile_combo.count() > 1:
        compare_profile_combo.setCurrentIndex(1)

    result_text = QPlainTextEdit()
    result_text.setReadOnly(True)
    result_text.setFont(QFont("Consolas", 9))
    layout.addWidget(result_text, 1)

    def _refresh_preview() -> None:
        base_profile = str(base_profile_combo.currentData(Qt.ItemDataRole.UserRole) or "").strip()
        compare_profile = str(
            compare_profile_combo.currentData(Qt.ItemDataRole.UserRole) or ""
        ).strip()
        try:
            entries = build_profile_diff(
                self.scenario,
                base_profile=base_profile,
                compare_profile=compare_profile,
            )
        except Exception as error:
            result_text.setPlainText(str(error))
            return
        result_text.setPlainText(_diff_entries_to_text(entries))

    action_layout = QHBoxLayout()
    refresh_button = QPushButton(self._t("app.button.refresh_diff"))
    refresh_button.clicked.connect(_refresh_preview)
    action_layout.addWidget(refresh_button)
    action_layout.addStretch()
    close_button = QPushButton(self._t("app.button.close"))
    close_button.clicked.connect(dialog.accept)
    action_layout.addWidget(close_button)
    layout.addLayout(action_layout)

    _refresh_preview()
    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def open_validation_report_dialog(
    self,
    report: ValidationReport,
    *,
    title: str,
) -> None:
    dialog = QDialog(self)
    dialog.setWindowTitle(title)
    dialog.resize(920, 620)

    layout = QVBoxLayout(dialog)
    status_label = QLabel(
        self._t("app.validation.status.ok")
        if report.is_valid
        else self._t("app.validation.status.ng")
    )
    status_label.setObjectName("PanelTitle")
    layout.addWidget(status_label)

    issues_list = QListWidget()
    details = QPlainTextEdit()
    details.setReadOnly(True)
    details.setFont(QFont("Consolas", 9))

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(issues_list)
    splitter.addWidget(details)
    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 3)
    layout.addWidget(splitter, 1)

    if report.issues:
        for index, issue in enumerate(report.issues, start=1):
            issues_list.addItem(
                self._t(
                    "app.validation.issue.item",
                    index=index,
                    code=issue.code,
                    message=issue.message,
                )
            )
    else:
        issues_list.addItem(self._t("app.validation.issue.none"))

    def _on_select(row: int) -> None:
        if row < 0 or row >= len(report.issues):
            if report.issues:
                details.setPlainText(self._t("app.validation.issue.select_prompt"))
            else:
                details.setPlainText(self._t("app.validation.issue.none_detail"))
            return
        issue = report.issues[row]
        details.setPlainText(
            self._t(
                "app.validation.issue.detail",
                code=issue.code,
                location=issue.location or "-",
                message=issue.message,
            )
        )

    issues_list.currentRowChanged.connect(_on_select)
    issues_list.setCurrentRow(0)
    _on_select(0)

    footer = QHBoxLayout()
    footer.addStretch()
    close_button = QPushButton(self._t("app.button.close"))
    close_button.clicked.connect(dialog.accept)
    footer.addWidget(close_button)
    layout.addLayout(footer)

    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def open_execution_outputs_editor(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.execution_outputs.title"))
    dialog.resize(980, 720)

    layout = QVBoxLayout(dialog)

    top_layout = QHBoxLayout()
    header_label = QLabel(self._t("app.dialog.execution_outputs.header"))
    header_label.setObjectName("PanelTitle")
    top_layout.addWidget(header_label)
    top_layout.addStretch()
    layout.addLayout(top_layout)

    splitter = QSplitter(Qt.Orientation.Horizontal)

    execution_widget = QWidget()
    execution_layout = QVBoxLayout(execution_widget)
    execution_layout.addWidget(QLabel(self._t("app.dialog.execution_outputs.execution")))
    execution_text = QPlainTextEdit()
    execution_text.setFont(QFont("Consolas", 9))
    execution_text.setPlainText(json.dumps(self.scenario.execution, ensure_ascii=False, indent=2))
    execution_layout.addWidget(execution_text)
    splitter.addWidget(execution_widget)

    outputs_widget = QWidget()
    outputs_layout = QVBoxLayout(outputs_widget)
    outputs_layout.addWidget(QLabel(self._t("app.dialog.execution_outputs.outputs")))
    outputs_text = QPlainTextEdit()
    outputs_text.setFont(QFont("Consolas", 9))
    outputs_text.setPlainText(json.dumps(self.scenario.outputs, ensure_ascii=False, indent=2))
    outputs_layout.addWidget(outputs_text)
    splitter.addWidget(outputs_widget)

    layout.addWidget(splitter, 1)

    def _apply() -> bool:
        try:
            execution_payload = json.loads(execution_text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(
                dialog,
                self._t("app.error.execution_json_invalid.title"),
                str(error),
            )
            return False
        try:
            outputs_payload = json.loads(outputs_text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(
                dialog,
                self._t("app.error.outputs_json_invalid.title"),
                str(error),
            )
            return False
        if not isinstance(execution_payload, dict):
            QMessageBox.critical(
                dialog,
                self._t("app.error.execution_json_invalid.title"),
                self._t("app.error.execution_object"),
            )
            return False
        if not isinstance(outputs_payload, dict):
            QMessageBox.critical(
                dialog,
                self._t("app.error.outputs_json_invalid.title"),
                self._t("app.error.outputs_object"),
            )
            return False
        self.scenario.execution = execution_payload
        self.scenario.outputs = outputs_payload
        mode = str(execution_payload.get("mode") or "").strip().lower()
        if mode in {"attach", "launch"}:
            self._set_combo_value(self.execution_mode_combo, mode)
        self.log(self._t("app.log.updated_execution_outputs"))
        return True

    def _format() -> None:
        try:
            execution_payload = json.loads(execution_text.toPlainText().strip() or "{}")
            outputs_payload = json.loads(outputs_text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(dialog, self._t("app.error.full_json_invalid.title"), str(error))
            return
        execution_text.setPlainText(json.dumps(execution_payload, ensure_ascii=False, indent=2))
        outputs_text.setPlainText(json.dumps(outputs_payload, ensure_ascii=False, indent=2))

    def _save_and_close() -> None:
        if _apply():
            dialog.accept()

    footer_layout = QHBoxLayout()
    format_button = QPushButton(self._t("app.button.format"))
    format_button.clicked.connect(_format)
    footer_layout.addWidget(format_button)
    footer_layout.addStretch()
    cancel_button = QPushButton(self._t("app.button.cancel"))
    cancel_button.clicked.connect(dialog.reject)
    footer_layout.addWidget(cancel_button)
    save_button = QPushButton(self._t("app.button.save"))
    save_button.setObjectName("ApplyButton")
    save_button.clicked.connect(_save_and_close)
    footer_layout.addWidget(save_button)
    apply_button = QPushButton(self._t("app.button.apply"))
    apply_button.setObjectName("ApplyButton")
    apply_button.clicked.connect(_apply)
    footer_layout.addWidget(apply_button)
    layout.addLayout(footer_layout)

    self._register_help_for_widget_tree(dialog)
    dialog.exec()
