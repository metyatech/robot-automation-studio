"""Scenario editor dialog helpers for StudioApp."""

from __future__ import annotations

import json
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .models import Scenario


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

    text = QPlainTextEdit()
    text.setFont(QFont("Consolas", 9))
    body_layout.addWidget(text, 1)
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
        listbox.setCurrentRow(index)
        text.setPlainText(json.dumps(variables[index], ensure_ascii=False, indent=2))

    def _on_select(row: int) -> None:
        if row < 0 or row >= len(variables):
            return
        _select(row)

    def _apply_current() -> bool:
        row = listbox.currentRow()
        if row < 0:
            return True
        try:
            payload = json.loads(text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(
                dialog, self._t("app.error.variable_json_invalid.title"), str(error)
            )
            return False
        if not isinstance(payload, dict):
            QMessageBox.critical(
                dialog,
                self._t("app.error.variable_json_invalid.title"),
                self._t("app.error.variable_json_object"),
            )
            return False
        if str(payload.get("id") or "").strip() == "":
            QMessageBox.critical(
                dialog,
                self._t("app.error.variable_json_invalid.title"),
                self._t("app.error.variable_id_required"),
            )
            return False
        if str(payload.get("type") or "").strip() == "":
            QMessageBox.critical(
                dialog,
                self._t("app.error.variable_json_invalid.title"),
                self._t("app.error.variable_type_required"),
            )
            return False
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
            text.clear()

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

    self._register_help_for_widget_tree(dialog)
    dialog.exec()


def open_profiles_editor(self) -> None:
    self._sync_scenario_header()
    dialog = QDialog(self)
    dialog.setWindowTitle(self._t("app.dialog.profiles.title"))
    dialog.resize(980, 620)

    profiles = dict(self.scenario.profiles or {})
    profile_names = sorted(profiles.keys())

    layout = QVBoxLayout(dialog)

    body_layout = QHBoxLayout()
    listbox = QListWidget()
    listbox.setMinimumWidth(260)
    body_layout.addWidget(listbox)

    text = QPlainTextEdit()
    text.setFont(QFont("Consolas", 9))
    body_layout.addWidget(text, 1)
    layout.addLayout(body_layout, 1)

    def _refresh_list() -> None:
        listbox.clear()
        for index, name in enumerate(profile_names):
            listbox.addItem(self._t("app.list.item.profile", index=index + 1, name=name))

    def _select(index: int) -> None:
        if index < 0 or index >= len(profile_names):
            return
        name = profile_names[index]
        payload = deepcopy(profiles.get(name, {}))
        profile_payload = {"name": name, "profile": payload}
        listbox.setCurrentRow(index)
        text.setPlainText(json.dumps(profile_payload, ensure_ascii=False, indent=2))

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
            payload = json.loads(text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(
                dialog, self._t("app.error.profile_json_invalid.title"), str(error)
            )
            return False
        if not isinstance(payload, dict):
            QMessageBox.critical(
                dialog,
                self._t("app.error.profile_json_invalid.title"),
                self._t("app.error.profile_payload_object"),
            )
            return False
        name = str(payload.get("name") or "").strip()
        profile = payload.get("profile")
        if name == "":
            QMessageBox.critical(
                dialog,
                self._t("app.error.profile_json_invalid.title"),
                self._t("app.error.profile_name_required"),
            )
            return False
        if not isinstance(profile, dict):
            QMessageBox.critical(
                dialog,
                self._t("app.error.profile_json_invalid.title"),
                self._t("app.error.profile_field_object"),
            )
            return False
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
            text.clear()

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

    listbox.currentRowChanged.connect(_on_select)
    _refresh_list()
    if profile_names:
        _select(0)

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
