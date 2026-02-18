"""UI construction/localization helpers for StudioApp."""

from __future__ import annotations

import re

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import (
    SUBFLOW_TIMEOUT_SECONDS_DEFAULT,
    UNITY_PROJECT_PATH_KEY,
    parse_subflow_timeout_seconds,
)
from .status import SPINNER_FRAMES, format_run_status

_PLACEHOLDER_COMPLETE_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_-]*\}$")
_PLACEHOLDER_BODY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


class _SubflowTimeoutValidator(QValidator):
    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        stripped = str(text).strip()
        if stripped == "":
            return QValidator.State.Acceptable, text, pos
        if _PLACEHOLDER_COMPLETE_RE.fullmatch(stripped):
            return QValidator.State.Acceptable, text, pos
        if self._is_placeholder_in_progress(stripped):
            return QValidator.State.Intermediate, text, pos
        try:
            parse_subflow_timeout_seconds(
                stripped,
                default=SUBFLOW_TIMEOUT_SECONDS_DEFAULT,
            )
        except ValueError:
            return QValidator.State.Invalid, text, pos
        return QValidator.State.Acceptable, text, pos

    @staticmethod
    def _is_placeholder_in_progress(value: str) -> bool:
        if value in {"$", "${"}:
            return True
        if not value.startswith("${"):
            return False
        if value.endswith("}"):
            return False
        body = value[2:]
        return bool(_PLACEHOLDER_BODY_RE.fullmatch(body))


def build_ui(self) -> None:
    central = QWidget()
    self.setCentralWidget(central)
    main_layout = QVBoxLayout(central)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    header_bar = QWidget()
    header_bar.setObjectName("HeaderBar")
    header_bar.setFixedHeight(44)
    header_layout = QHBoxLayout(header_bar)
    header_layout.setContentsMargins(8, 0, 8, 0)
    header_layout.setSpacing(6)

    self.title_label = QLabel()
    self.title_label.setObjectName("PanelTitle")
    header_layout.addWidget(self.title_label)

    self.name_edit = QLineEdit(self.scenario.name)
    self.name_edit.setObjectName("ScenarioNameEdit")
    self.name_edit.setMinimumWidth(120)
    self.name_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    header_layout.addWidget(self.name_edit, 1)

    self.record_button = QPushButton()
    self.record_button.setObjectName("RecordButton")
    self.record_button.clicked.connect(self.start_recording)
    header_layout.addWidget(self.record_button)

    self.record_stop_button = QPushButton()
    self.record_stop_button.setObjectName("StopButton")
    self.record_stop_button.clicked.connect(self.stop_recording)
    header_layout.addWidget(self.record_stop_button)

    vline1 = QFrame()
    vline1.setObjectName("HeaderVLine")
    vline1.setFrameShape(QFrame.Shape.VLine)
    header_layout.addWidget(vline1)

    self.run_button = QPushButton()
    self.run_button.setObjectName("RecordButton")
    self.run_button.clicked.connect(self.run_robot_suite)
    header_layout.addWidget(self.run_button)

    self.stop_robot_button = QPushButton()
    self.stop_robot_button.setObjectName("StopButton")
    self.stop_robot_button.setEnabled(False)
    self.stop_robot_button.clicked.connect(self.stop_robot_suite)
    header_layout.addWidget(self.stop_robot_button)

    self._status_pill = QLabel(
        format_run_status("idle", SPINNER_FRAMES[0], locale=self._translator.locale)
    )
    self._status_pill.setObjectName("StatusPill")
    header_layout.addWidget(self._status_pill)

    vline2 = QFrame()
    vline2.setObjectName("HeaderVLine")
    vline2.setFrameShape(QFrame.Shape.VLine)
    header_layout.addWidget(vline2)

    self.help_status_label = QLabel()
    self.help_status_label.setObjectName("HeaderHelpLabel")
    self.help_status_label.setMinimumWidth(0)
    self.help_status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    header_layout.addWidget(self.help_status_label, 1)

    self._rec_indicator = QLabel()
    self._rec_indicator.setObjectName("RecIndicator")
    header_layout.addWidget(self._rec_indicator)

    self.file_menu_button = QToolButton()
    self.file_menu_button.setObjectName("FileMenuButton")
    self.file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    file_menu = QMenu(self.file_menu_button)
    self.file_save_action = file_menu.addAction("")
    self.file_save_action.triggered.connect(self.save_json)
    self.file_load_action = file_menu.addAction("")
    self.file_load_action.triggered.connect(self.load_json)
    file_menu.addSeparator()
    self.file_json_action = file_menu.addAction("")
    self.file_json_action.triggered.connect(self.open_full_json_editor)
    self.file_help_action = file_menu.addAction("")
    self.file_help_action.triggered.connect(self.open_help_guide)
    self.file_run_diagnostics_action = file_menu.addAction("")
    self.file_run_diagnostics_action.triggered.connect(self.open_run_diagnostics)
    self.file_menu_button.setMenu(file_menu)
    header_layout.addWidget(self.file_menu_button)

    self.hotkey_button = QPushButton()
    self.hotkey_button.setObjectName("HotkeyButton")
    self.hotkey_button.clicked.connect(self.open_hotkey_dialog)
    header_layout.addWidget(self.hotkey_button)

    self.language_combo = QComboBox()
    self.language_combo.setObjectName("LanguageCombo")
    self.language_combo.currentIndexChanged.connect(self._on_locale_changed)
    header_layout.addWidget(self.language_combo)

    main_layout.addWidget(header_bar)

    main_splitter = QSplitter(Qt.Orientation.Vertical)
    main_splitter.setObjectName("MainSplitter")

    horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)

    left_panel = QWidget()
    left_panel.setMinimumWidth(200)
    left_panel_layout = QVBoxLayout(left_panel)
    left_panel_layout.setContentsMargins(8, 8, 8, 8)
    left_panel_layout.setSpacing(6)

    self.steps_label = QLabel()
    self.steps_label.setObjectName("PanelTitle")
    left_panel_layout.addWidget(self.steps_label)

    step_toolbar = QHBoxLayout()

    self.add_step_button = QToolButton()
    self.add_step_button.setObjectName("AddStepButton")
    self.add_step_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    add_step_menu = QMenu(self.add_step_button)
    self.add_click_action = add_step_menu.addAction("")
    self.add_click_action.triggered.connect(self.add_click)
    self.add_drag_action = add_step_menu.addAction("")
    self.add_drag_action.triggered.connect(self.add_drag)
    self.add_shortcut_action = add_step_menu.addAction("")
    self.add_shortcut_action.triggered.connect(self.add_shortcut)
    self.add_menu_action = add_step_menu.addAction("")
    self.add_menu_action.triggered.connect(self.add_menu)
    self.add_type_action = add_step_menu.addAction("")
    self.add_type_action.triggered.connect(self.add_type)
    add_step_menu.addSeparator()
    self.add_if_action = add_step_menu.addAction("")
    self.add_if_action.triggered.connect(self.add_control)
    self.add_group_action = add_step_menu.addAction("")
    self.add_group_action.triggered.connect(self.add_group)
    self.add_step_button.setMenu(add_step_menu)
    step_toolbar.addWidget(self.add_step_button)

    self.delete_step_button = QPushButton()
    self.delete_step_button.setObjectName("DeleteStepButton")
    self.delete_step_button.clicked.connect(self.delete_selected)
    step_toolbar.addWidget(self.delete_step_button)

    self.move_up_button = QPushButton()
    self.move_up_button.setObjectName("MoveStepUpButton")
    self.move_up_button.clicked.connect(self.move_up)
    step_toolbar.addWidget(self.move_up_button)

    self.move_down_button = QPushButton()
    self.move_down_button.setObjectName("MoveStepDownButton")
    self.move_down_button.clicked.connect(self.move_down)
    step_toolbar.addWidget(self.move_down_button)

    self.duplicate_step_button = QPushButton()
    self.duplicate_step_button.setObjectName("DuplicateStepButton")
    self.duplicate_step_button.clicked.connect(self.duplicate_selected)
    step_toolbar.addWidget(self.duplicate_step_button)
    step_toolbar.addStretch()

    left_panel_layout.addLayout(step_toolbar)

    self.step_list = QListWidget()
    self.step_list.setObjectName("StepList")
    self.step_list.setFont(QFont("Consolas", 11))
    self.step_list.currentRowChanged.connect(self.on_select_step)
    left_panel_layout.addWidget(self.step_list)

    horizontal_splitter.addWidget(left_panel)

    self.main_tabs = QTabWidget()
    self.main_tabs.setObjectName("MainTabs")

    step_tab = QWidget()
    step_scroll = QScrollArea()
    step_scroll.setWidgetResizable(True)
    step_scroll.setFrameShape(QFrame.Shape.NoFrame)
    step_scroll_widget = QWidget()
    step_scroll_layout = QVBoxLayout(step_scroll_widget)

    self.step_form = QFormLayout()
    self.step_form.setSpacing(8)
    self.step_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    self.step_id_edit = QLineEdit()
    self.step_id_edit.setObjectName("StepIdEdit")
    self.step_id_label = QLabel()
    self.step_form.addRow(self.step_id_label, self.step_id_edit)

    self.title_edit = QLineEdit()
    self.title_edit.setObjectName("StepTitleEdit")
    self.step_title_label = QLabel()
    self.step_form.addRow(self.step_title_label, self.title_edit)

    self.kind_combo = QComboBox()
    self.kind_combo.setObjectName("StepKindCombo")
    self.step_kind_label = QLabel()
    self.kind_combo.currentTextChanged.connect(self._update_step_kind_fields_visibility)
    self.kind_combo.currentTextChanged.connect(self._refresh_step_validation_hint)
    self.step_form.addRow(self.step_kind_label, self.kind_combo)

    self.action_edit = QLineEdit()
    self.action_edit.setObjectName("StepActionEdit")
    self.action_edit.textChanged.connect(self._refresh_step_validation_hint)
    self.action_label = QLabel()
    self.step_form.addRow(self.action_label, self.action_edit)

    self.control_edit = QLineEdit()
    self.control_edit.setObjectName("StepControlEdit")
    self.control_edit.textChanged.connect(self._refresh_step_validation_hint)
    self.control_label = QLabel()
    self.step_form.addRow(self.control_label, self.control_edit)

    self.step_description_edit = QLineEdit()
    self.step_description_edit.setObjectName("StepDescriptionEdit")
    self.step_description_label = QLabel()
    self.step_form.addRow(self.step_description_label, self.step_description_edit)

    self.step_condition_edit = QLineEdit()
    self.step_condition_edit.setObjectName("StepConditionEdit")
    self.condition_label = QLabel()
    self.step_form.addRow(self.condition_label, self.step_condition_edit)

    checks_layout = QHBoxLayout()
    self.step_disabled_check = QCheckBox()
    self.step_disabled_check.setObjectName("StepDisabledCheck")
    checks_layout.addWidget(self.step_disabled_check)
    self.step_continue_on_error_check = QCheckBox()
    self.step_continue_on_error_check.setObjectName("StepContinueOnErrorCheck")
    checks_layout.addWidget(self.step_continue_on_error_check)
    checks_layout.addStretch()
    self.step_form.addRow(checks_layout)

    self.annotations_text = QPlainTextEdit()
    self.annotations_text.setObjectName("StepAnnotationsText")
    self.annotations_text.setFont(QFont("Consolas", 9))
    self.annotations_text.setMaximumHeight(80)
    self.annotations_label = QLabel()
    self.step_form.addRow(self.annotations_label, self.annotations_text)

    self.params_text = QPlainTextEdit()
    self.params_text.setObjectName("StepParamsText")
    self.params_text.setFont(QFont("Consolas", 10))
    self.params_text.setMaximumHeight(160)
    self.params_text.textChanged.connect(self._refresh_step_validation_hint)
    self.params_label = QLabel()
    self.step_form.addRow(self.params_label, self.params_text)

    step_scroll_layout.addLayout(self.step_form)

    self.params_template_button = QPushButton()
    self.params_template_button.setObjectName("ParamsTemplateButton")
    self.params_template_button.clicked.connect(self.insert_params_template_for_selected_action)
    step_scroll_layout.addWidget(self.params_template_button)

    self.step_validation_label = QLabel()
    self.step_validation_label.setObjectName("StepValidationLabel")
    self.step_validation_label.setWordWrap(True)
    step_scroll_layout.addWidget(self.step_validation_label)

    self.apply_step_button = QPushButton()
    self.apply_step_button.setObjectName("ApplyButton")
    self.apply_step_button.clicked.connect(self.apply_step_changes)
    step_scroll_layout.addWidget(self.apply_step_button)

    step_scroll_layout.addStretch()

    step_scroll.setWidget(step_scroll_widget)
    step_tab_layout = QVBoxLayout(step_tab)
    step_tab_layout.setContentsMargins(0, 0, 0, 0)
    step_tab_layout.addWidget(step_scroll)

    self.step_tab_index = self.main_tabs.addTab(step_tab, "")

    scenario_tab = QWidget()
    scenario_scroll = QScrollArea()
    scenario_scroll.setWidgetResizable(True)
    scenario_scroll.setFrameShape(QFrame.Shape.NoFrame)
    scenario_scroll_widget = QWidget()
    scenario_form = QFormLayout(scenario_scroll_widget)
    scenario_form.setSpacing(8)
    scenario_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    self.scenario_id_edit = QLineEdit(self.scenario.scenario_id)
    self.scenario_id_edit.setObjectName("ScenarioIdEdit")
    self.scenario_id_label = QLabel()
    scenario_form.addRow(self.scenario_id_label, self.scenario_id_edit)

    self.target_combo = QComboBox()
    self.target_combo.setObjectName("TargetCombo")
    self.target_label = QLabel()
    scenario_form.addRow(self.target_label, self.target_combo)

    self.window_hint_edit = QLineEdit(self.scenario.target_window_hint)
    self.window_hint_edit.setObjectName("WindowHintEdit")
    self.window_hint_label = QLabel()
    scenario_form.addRow(self.window_hint_label, self.window_hint_edit)

    self.execution_mode_combo = QComboBox()
    self.execution_mode_combo.setObjectName("ExecutionModeCombo")
    self.execution_mode_label = QLabel()
    self.execution_mode_combo.currentTextChanged.connect(self.on_execution_mode_changed)
    scenario_form.addRow(self.execution_mode_label, self.execution_mode_combo)

    self.subflow_timeout_edit = QLineEdit(
        str((self.scenario.execution or {}).get("subflow_timeout_seconds", ""))
    )
    self.subflow_timeout_edit.setObjectName("SubflowTimeoutEdit")
    self.subflow_timeout_edit.setValidator(_SubflowTimeoutValidator(self.subflow_timeout_edit))
    self.subflow_timeout_edit.textChanged.connect(self._refresh_subflow_timeout_validation_hint)
    self.subflow_timeout_edit.inputRejected.connect(self._on_subflow_timeout_input_rejected)
    self.subflow_timeout_label = QLabel()
    scenario_form.addRow(self.subflow_timeout_label, self.subflow_timeout_edit)
    self.subflow_timeout_validation_label = QLabel()
    self.subflow_timeout_validation_label.setObjectName("SubflowTimeoutValidationLabel")
    self.subflow_timeout_validation_label.setWordWrap(True)
    scenario_form.addRow("", self.subflow_timeout_validation_label)

    self.active_profile_combo = QComboBox()
    self.active_profile_combo.setObjectName("ActiveProfileCombo")
    self.active_profile_label = QLabel()
    scenario_form.addRow(self.active_profile_label, self.active_profile_combo)

    project_path_row = QHBoxLayout()
    self.project_path_edit = QLineEdit(str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, "")))
    self.project_path_edit.setObjectName("ProjectPathEdit")
    project_path_row.addWidget(self.project_path_edit, 1)
    self.project_path_browse_button = QPushButton()
    self.project_path_browse_button.setObjectName("ProjectPathBrowseButton")
    self.project_path_browse_button.clicked.connect(self.browse_unity_project_path)
    project_path_row.addWidget(self.project_path_browse_button)
    self.unity_project_path_label = QLabel()
    scenario_form.addRow(self.unity_project_path_label, project_path_row)

    self.description_edit = QLineEdit(self.scenario.description)
    self.description_edit.setObjectName("ScenarioDescriptionEdit")
    self.description_label = QLabel()
    scenario_form.addRow(self.description_label, self.description_edit)

    scenario_tools_layout = QHBoxLayout()
    self.variables_button = QPushButton()
    self.variables_button.setObjectName("VariablesButton")
    self.variables_button.clicked.connect(self.open_variables_editor)
    scenario_tools_layout.addWidget(self.variables_button)
    self.profiles_button = QPushButton()
    self.profiles_button.setObjectName("ProfilesButton")
    self.profiles_button.clicked.connect(self.open_profiles_editor)
    scenario_tools_layout.addWidget(self.profiles_button)
    self.execution_outputs_button = QPushButton()
    self.execution_outputs_button.setObjectName("ExecutionOutputsButton")
    self.execution_outputs_button.clicked.connect(self.open_execution_outputs_editor)
    scenario_tools_layout.addWidget(self.execution_outputs_button)
    self.validate_button = QPushButton()
    self.validate_button.setObjectName("ValidateButton")
    self.validate_button.clicked.connect(self.open_preflight_validation)
    scenario_tools_layout.addWidget(self.validate_button)
    self.profile_diff_button = QPushButton()
    self.profile_diff_button.setObjectName("ProfileDiffButton")
    self.profile_diff_button.clicked.connect(self.open_profile_diff_preview)
    scenario_tools_layout.addWidget(self.profile_diff_button)
    scenario_tools_layout.addStretch()
    scenario_form.addRow(scenario_tools_layout)

    scenario_scroll.setWidget(scenario_scroll_widget)
    scenario_tab_layout = QVBoxLayout(scenario_tab)
    scenario_tab_layout.setContentsMargins(0, 0, 0, 0)
    scenario_tab_layout.addWidget(scenario_scroll)

    self.scenario_tab_index = self.main_tabs.addTab(scenario_tab, "")

    export_tab = QWidget()
    export_scroll = QScrollArea()
    export_scroll.setWidgetResizable(True)
    export_scroll.setFrameShape(QFrame.Shape.NoFrame)
    export_scroll_widget = QWidget()
    export_form = QFormLayout(export_scroll_widget)
    export_form.setSpacing(8)
    export_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    output_dir_row = QHBoxLayout()
    self.output_dir_edit = QLineEdit("artifacts/studio")
    self.output_dir_edit.setObjectName("OutputDirEdit")
    output_dir_row.addWidget(self.output_dir_edit, 1)
    self.open_output_dir_button = QPushButton()
    self.open_output_dir_button.setObjectName("OpenOutputDirButton")
    self.open_output_dir_button.clicked.connect(self.open_output_directory)
    output_dir_row.addWidget(self.open_output_dir_button)
    self.output_dir_label = QLabel()
    export_form.addRow(self.output_dir_label, output_dir_row)

    export_name_row = QHBoxLayout()
    self.export_name_edit = QLineEdit("unity-editor-generated")
    self.export_name_edit.setObjectName("ExportNameEdit")
    export_name_row.addWidget(self.export_name_edit, 1)
    self.export_button = QPushButton()
    self.export_button.setObjectName("ExportButton")
    self.export_button.clicked.connect(self.export_scenario)
    export_name_row.addWidget(self.export_button)
    self.export_name_label = QLabel()
    export_form.addRow(self.export_name_label, export_name_row)

    export_scroll.setWidget(export_scroll_widget)
    export_tab_layout = QVBoxLayout(export_tab)
    export_tab_layout.setContentsMargins(0, 0, 0, 0)
    export_tab_layout.addWidget(export_scroll)

    self.export_tab_index = self.main_tabs.addTab(export_tab, "")

    horizontal_splitter.addWidget(self.main_tabs)

    horizontal_splitter.setStretchFactor(0, 2)
    horizontal_splitter.setStretchFactor(1, 3)

    main_splitter.addWidget(horizontal_splitter)

    bottom_panel = QWidget()
    bottom_panel_layout = QVBoxLayout(bottom_panel)
    bottom_panel_layout.setContentsMargins(0, 0, 0, 0)
    bottom_panel_layout.setSpacing(0)

    log_header = QWidget()
    log_header.setObjectName("LogHeader")
    log_header.setFixedHeight(32)
    log_header_layout = QHBoxLayout(log_header)
    log_header_layout.setContentsMargins(8, 4, 8, 4)

    self.log_label = QLabel()
    self.log_label.setObjectName("PanelTitle")
    log_header_layout.addWidget(self.log_label)

    log_header_layout.addStretch()

    self._log_toggle_button = QToolButton()
    self._log_toggle_button.setObjectName("LogToggleButton")
    self._log_toggle_button.setText("\u25bc")
    self._log_toggle_button.clicked.connect(self._toggle_log_collapse)
    log_header_layout.addWidget(self._log_toggle_button)

    bottom_panel_layout.addWidget(log_header)

    self.log_text_container = QWidget()
    log_text_container_layout = QVBoxLayout(self.log_text_container)
    log_text_container_layout.setContentsMargins(8, 4, 8, 8)

    self.log_text = QPlainTextEdit()
    self.log_text.setObjectName("LogText")
    self.log_text.setReadOnly(True)
    self.log_text.setFont(QFont("Consolas", 9))
    self.log_text.setMaximumBlockCount(5000)
    log_text_container_layout.addWidget(self.log_text)

    bottom_panel_layout.addWidget(self.log_text_container)

    main_splitter.addWidget(bottom_panel)

    main_splitter.setStretchFactor(0, 4)
    main_splitter.setStretchFactor(1, 1)
    main_splitter.setSizes([620, 180])

    main_layout.addWidget(main_splitter, 1)

    # --- Icons (qtawesome) ---
    _icon_fg = "#cdd6f4"
    _icon_green = "#a6e3a1"
    _icon_red = "#f38ba8"
    _icon_blue = "#89b4fa"

    self.record_button.setIcon(qta.icon("mdi6.record-circle", color=_icon_green))
    self.record_stop_button.setIcon(qta.icon("mdi6.stop", color=_icon_red))
    self.run_button.setIcon(qta.icon("mdi6.play", color=_icon_green))
    self.stop_robot_button.setIcon(qta.icon("mdi6.stop", color=_icon_red))

    self.delete_step_button.setIcon(qta.icon("mdi6.close", color=_icon_fg))
    self.move_up_button.setIcon(qta.icon("mdi6.arrow-up", color=_icon_fg))
    self.move_down_button.setIcon(qta.icon("mdi6.arrow-down", color=_icon_fg))
    self.duplicate_step_button.setIcon(qta.icon("mdi6.content-copy", color=_icon_fg))

    self.file_save_action.setIcon(qta.icon("mdi6.content-save", color=_icon_fg))
    self.file_load_action.setIcon(qta.icon("mdi6.folder-open", color=_icon_fg))
    self.file_json_action.setIcon(qta.icon("mdi6.code-json", color=_icon_fg))
    self.file_help_action.setIcon(qta.icon("mdi6.help-circle-outline", color=_icon_fg))
    self.file_run_diagnostics_action.setIcon(qta.icon("mdi6.chart-box-outline", color=_icon_fg))

    self.add_click_action.setIcon(qta.icon("mdi6.cursor-default-click", color=_icon_fg))
    self.add_drag_action.setIcon(qta.icon("mdi6.cursor-move", color=_icon_fg))
    self.add_shortcut_action.setIcon(qta.icon("mdi6.keyboard", color=_icon_fg))
    self.add_menu_action.setIcon(qta.icon("mdi6.menu", color=_icon_fg))
    self.add_type_action.setIcon(qta.icon("mdi6.form-textbox", color=_icon_fg))
    self.add_if_action.setIcon(qta.icon("mdi6.call-split", color=_icon_fg))
    self.add_group_action.setIcon(qta.icon("mdi6.view-list", color=_icon_fg))

    self.file_menu_button.setIcon(qta.icon("mdi6.file-document-outline", color=_icon_fg))
    self.file_menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    self.add_step_button.setIcon(qta.icon("mdi6.plus", color=_icon_blue))
    self.add_step_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    self.on_execution_mode_changed()
    self._update_step_kind_fields_visibility()


def apply_localized_texts(self) -> None:
    self.setWindowTitle(
        self._t("app.window.title.recording")
        if self.recorder.is_recording
        else self._t("app.window.title")
    )
    self.title_label.setText(self._t("app.window.header_prefix"))
    self.name_edit.setPlaceholderText(self._t("app.field.scenario_name.placeholder"))

    self.record_button.setText(self._t("app.button.record_start"))
    self.record_stop_button.setText(self._t("app.button.record_stop"))
    self.run_button.setText(self._t("app.button.run_robot"))
    self.stop_robot_button.setText(self._t("app.button.stop_robot"))
    for _btn in (
        self.record_button,
        self.record_stop_button,
        self.run_button,
        self.stop_robot_button,
    ):
        _fm = _btn.fontMetrics()
        _btn.setMinimumWidth(_fm.horizontalAdvance(_btn.text()) + 20)
        _btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    self._status_pill.setToolTip(self._t("app.status.run_tooltip"))
    self.help_status_label.setText(self._t("app.help.header"))
    self._rec_indicator.setToolTip(self._t("app.status.record_tooltip"))
    self._rec_indicator.setText(
        self._t("app.status.recording")
        if self.recorder.is_recording
        else self._t("app.status.record_idle")
    )

    self.file_menu_button.setText(self._t("app.button.file_menu"))
    self.file_save_action.setText(self._t("app.menu.file.save"))
    self.file_load_action.setText(self._t("app.menu.file.load"))
    self.file_json_action.setText(self._t("app.menu.file.full_json"))
    self.file_help_action.setText(self._t("app.menu.file.help"))
    self.file_run_diagnostics_action.setText(self._t("app.menu.file.run_diagnostics"))
    self.hotkey_button.setText("\u22f9 " + self._stop_hotkey_spec.label)
    self.hotkey_button.setToolTip(
        self._t("app.button.hotkey_with_value", hotkey=self._stop_hotkey_spec.label)
        + "\n"
        + self._t("app.tooltip.stop_hotkey")
    )
    self._set_action_help(
        self.file_save_action,
        "app.help.menu.file.save.summary",
        "app.help.menu.file.save.detail",
    )
    self._set_action_help(
        self.file_load_action,
        "app.help.menu.file.load.summary",
        "app.help.menu.file.load.detail",
    )
    self._set_action_help(
        self.file_json_action,
        "app.help.menu.file.full_json.summary",
        "app.help.menu.file.full_json.detail",
    )
    self._set_action_help(
        self.file_help_action,
        "app.help.menu.file.help.summary",
        "app.help.menu.file.help.detail",
    )
    self._set_action_help(
        self.file_run_diagnostics_action,
        "app.help.menu.file.run_diagnostics.summary",
        "app.help.menu.file.run_diagnostics.detail",
    )

    current_locale = self._translator.locale
    self.language_combo.blockSignals(True)
    self.language_combo.clear()
    self.language_combo.addItem(self._t("locale.en.label"), "en")
    self.language_combo.addItem(self._t("locale.ja.label"), "ja")
    self._set_combo_value(self.language_combo, current_locale)
    self.language_combo.blockSignals(False)
    self.language_combo.setToolTip(self._t("app.button.language_menu"))

    self.steps_label.setText(self._t("app.label.steps"))
    self.add_step_button.setText(self._t("app.button.add_step"))
    self.add_click_action.setText(self._t("app.menu.add.click"))
    self.add_drag_action.setText(self._t("app.menu.add.drag"))
    self.add_shortcut_action.setText(self._t("app.menu.add.shortcut"))
    self.add_menu_action.setText(self._t("app.menu.add.menu"))
    self.add_type_action.setText(self._t("app.menu.add.type"))
    self.add_if_action.setText(self._t("app.menu.add.if"))
    self.add_group_action.setText(self._t("app.menu.add.group"))
    self._set_action_help(
        self.add_click_action,
        "app.help.menu.add.click.summary",
        "app.help.menu.add.click.detail",
    )
    self._set_action_help(
        self.add_drag_action,
        "app.help.menu.add.drag.summary",
        "app.help.menu.add.drag.detail",
    )
    self._set_action_help(
        self.add_shortcut_action,
        "app.help.menu.add.shortcut.summary",
        "app.help.menu.add.shortcut.detail",
    )
    self._set_action_help(
        self.add_menu_action,
        "app.help.menu.add.menu.summary",
        "app.help.menu.add.menu.detail",
    )
    self._set_action_help(
        self.add_type_action,
        "app.help.menu.add.type.summary",
        "app.help.menu.add.type.detail",
    )
    self._set_action_help(
        self.add_if_action,
        "app.help.menu.add.if.summary",
        "app.help.menu.add.if.detail",
    )
    self._set_action_help(
        self.add_group_action,
        "app.help.menu.add.group.summary",
        "app.help.menu.add.group.detail",
    )

    self.delete_step_button.setText(self._t("app.button.delete"))
    self.move_up_button.setText(self._t("app.button.move_up"))
    self.move_down_button.setText(self._t("app.button.move_down"))
    self.duplicate_step_button.setText(self._t("app.button.duplicate"))
    self.delete_step_button.setToolTip(self._t("app.tooltip.delete_step"))
    self.move_up_button.setToolTip(self._t("app.tooltip.move_step_up"))
    self.move_down_button.setToolTip(self._t("app.tooltip.move_step_down"))
    self.duplicate_step_button.setToolTip(self._t("app.tooltip.duplicate_step"))
    self.step_list.setToolTip(self._t("app.tooltip.steps_list"))

    self.step_id_label.setText(self._t("app.field.step_id.label"))
    self.step_id_edit.setPlaceholderText(self._t("app.field.step_id.placeholder"))
    self.step_title_label.setText(self._t("app.field.step_title.label"))
    self.title_edit.setPlaceholderText(self._t("app.field.step_title.placeholder"))
    self.step_kind_label.setText(self._t("app.field.step_kind.label"))
    self.action_label.setText(self._t("app.field.step_action.label"))
    self.action_edit.setPlaceholderText(self._t("app.field.step_action.placeholder"))
    self.control_label.setText(self._t("app.field.step_control.label"))
    self.control_edit.setPlaceholderText(self._t("app.field.step_control.placeholder"))
    self.step_description_label.setText(self._t("app.field.step_description.label"))
    self.step_description_edit.setPlaceholderText(self._t("app.field.step_description.placeholder"))
    self.condition_label.setText(self._t("app.field.step_condition.label"))
    self.step_condition_edit.setPlaceholderText(self._t("app.field.step_condition.placeholder"))
    self.step_disabled_check.setText(self._t("app.field.step_disabled"))
    self.step_continue_on_error_check.setText(self._t("app.field.step_continue_on_error"))
    self.annotations_label.setText(self._t("app.field.annotations.label"))
    self.params_label.setText(self._t("app.field.params.label"))
    self.params_template_button.setText(self._t("app.button.params_template"))
    self.params_template_button.setToolTip(self._t("app.tooltip.params_template"))
    self.step_validation_label.setToolTip(self._t("app.tooltip.step_validation"))
    self.apply_step_button.setText(self._t("app.button.apply_step"))
    self._refresh_step_validation_hint()

    current_step_kind = self._combo_value(self.kind_combo) or "action"
    current_target = self._combo_value(self.target_combo) or "unity"
    current_mode = self._combo_value(self.execution_mode_combo) or "attach"

    self.kind_combo.blockSignals(True)
    self.kind_combo.clear()
    self.kind_combo.addItem(self._t("app.option.kind.action"), "action")
    self.kind_combo.addItem(self._t("app.option.kind.control"), "control")
    self.kind_combo.addItem(self._t("app.option.kind.group"), "group")
    self.kind_combo.blockSignals(False)
    self._set_combo_value(self.kind_combo, current_step_kind)
    self._configure_combo_option_help(
        self.kind_combo,
        {
            "action": self._t("app.option.help.kind.action"),
            "control": self._t("app.option.help.kind.control"),
            "group": self._t("app.option.help.kind.group"),
        },
    )

    self.target_combo.blockSignals(True)
    self.target_combo.clear()
    self.target_combo.addItem(self._t("app.option.target.unity"), "unity")
    self.target_combo.addItem(self._t("app.option.target.web"), "web")
    self.target_combo.addItem(self._t("app.option.target.desktop"), "desktop")
    self.target_combo.addItem(self._t("app.option.target.hybrid"), "hybrid")
    self.target_combo.blockSignals(False)
    self._set_combo_value(self.target_combo, current_target)
    self._configure_combo_option_help(
        self.target_combo,
        {
            "unity": self._t("app.option.help.target.unity"),
            "web": self._t("app.option.help.target.web"),
            "desktop": self._t("app.option.help.target.desktop"),
            "hybrid": self._t("app.option.help.target.hybrid"),
        },
    )

    self.execution_mode_combo.blockSignals(True)
    self.execution_mode_combo.clear()
    self.execution_mode_combo.addItem(self._t("app.option.execution.attach"), "attach")
    self.execution_mode_combo.addItem(self._t("app.option.execution.launch"), "launch")
    self.execution_mode_combo.blockSignals(False)
    self._set_combo_value(self.execution_mode_combo, current_mode)
    self._configure_combo_option_help(
        self.execution_mode_combo,
        {
            "attach": self._t("app.option.help.execution.attach"),
            "launch": self._t("app.option.help.execution.launch"),
        },
    )

    self.main_tabs.setTabText(self.step_tab_index, self._t("app.tab.step"))
    self.main_tabs.setTabText(self.scenario_tab_index, self._t("app.tab.scenario"))
    self.main_tabs.setTabText(self.export_tab_index, self._t("app.tab.export"))
    self.main_tabs.setTabToolTip(self.step_tab_index, self._t("app.tab.step.tooltip"))
    self.main_tabs.setTabToolTip(self.scenario_tab_index, self._t("app.tab.scenario.tooltip"))
    self.main_tabs.setTabToolTip(self.export_tab_index, self._t("app.tab.export.tooltip"))

    self.scenario_id_label.setText(self._t("app.field.scenario_id.label"))
    self.scenario_id_edit.setPlaceholderText(self._t("app.field.scenario_id.placeholder"))
    self.target_label.setText(self._t("app.field.target.label"))
    self.window_hint_label.setText(self._t("app.field.window_hint.label"))
    self.window_hint_edit.setPlaceholderText(self._t("app.field.window_hint.placeholder"))
    self.execution_mode_label.setText(self._t("app.field.execution_mode.label"))
    self.subflow_timeout_label.setText(self._t("app.field.subflow_timeout.label"))
    self.subflow_timeout_edit.setPlaceholderText(self._t("app.field.subflow_timeout.placeholder"))
    self.subflow_timeout_edit.setToolTip(self._t("app.tooltip.subflow_timeout"))
    self.subflow_timeout_validation_label.setToolTip(self._t("app.tooltip.subflow_timeout"))
    self.active_profile_label.setText(self._t("app.field.active_profile.label"))
    self.unity_project_path_label.setText(self._t("app.field.unity_project_path.label"))
    self.project_path_edit.setPlaceholderText(self._t("app.field.unity_project_path.placeholder"))
    self.project_path_browse_button.setText(self._t("app.button.browse"))
    self.description_label.setText(self._t("app.field.description.label"))
    self.description_edit.setPlaceholderText(self._t("app.field.description.placeholder"))
    self.variables_button.setText(self._t("app.button.variables"))
    self.profiles_button.setText(self._t("app.button.profiles"))
    self.execution_outputs_button.setText(self._t("app.button.execution_outputs"))
    self.validate_button.setText(self._t("app.button.validate"))
    self.profile_diff_button.setText(self._t("app.button.profile_diff"))
    self._refresh_active_profile_combo()

    self.output_dir_label.setText(self._t("app.field.output_dir.label"))
    self.output_dir_edit.setPlaceholderText(self._t("app.field.output_dir.placeholder"))
    self.open_output_dir_button.setText(self._t("app.button.open_output_dir"))
    self.open_output_dir_button.setToolTip(self._t("app.tooltip.open_output_dir"))
    self.export_name_label.setText(self._t("app.field.export_name.label"))
    self.export_name_edit.setPlaceholderText(self._t("app.field.export_name.placeholder"))
    self.export_button.setText(self._t("app.button.export"))

    self.log_label.setText(self._t("app.label.output_log"))
    self._log_toggle_button.setToolTip(self._t("app.log.toggle.tooltip"))

    self.on_execution_mode_changed()
    self._refresh_subflow_timeout_validation_hint()
    self._update_step_kind_fields_visibility()
    self._render_robot_status()
    self.refresh_steps()
