"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from copy import deepcopy
from pathlib import Path

from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .bridge_readiness import build_recording_readiness_timeouts
from .editor import ScenarioEditor
from .exporter import export_all
from .models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    normalize_unity_execution_mode,
)
from .overlay import AutomationRunOverlay, OverlayMode
from .recorder import ScenarioRecorder, events_to_steps, has_visible_window_with_hint
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .status import SPINNER_FRAMES, format_run_status, next_spinner_index
from .ui_help import HelpEntry, filter_help_entries
from .unity_bridge import UnityBridgeClient
from .unity_diagnostics import get_recent_unity_compile_errors
from .unity_project import resolve_attached_unity_project_path
from .upm import (
    ensure_unity_bridge_upm_dependency,
    has_unity_bridge_package_script_meta,
    install_legacy_unity_bridge_script,
)
from .window_focus import (
    focus_visible_window_with_hint,
    trigger_assets_refresh_shortcut_with_hint,
)

STOP_HOTKEY_BIND = "<ctrl>+<shift>+<f12>"
STOP_HOTKEY_LABEL = "Ctrl+Shift+F12"
BRIDGE_READY_TIMEOUT_SECONDS = 15.0
BRIDGE_READY_CHECK_TIMEOUT_SECONDS = 3.0
BRIDGE_READY_REQUEST_TIMEOUT_SECONDS = 0.8
BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS = 25.0

_BG = "#1e1e2e"
_BG_MID = "#282840"
_BG_LIGHT = "#313150"
_FG = "#cdd6f4"
_FG_DIM = "#a6adc8"
_ACCENT_BLUE = "#89b4fa"
_ACCENT_GREEN = "#a6e3a1"
_ACCENT_RED = "#f38ba8"
_ACCENT_YELLOW = "#f9e2af"
_BTN_BG = "#45475a"
_BTN_HOVER = "#585b70"
_LOG_BG = "#1a1a2e"


class _FlowLayout(QLayout):
    """Layout that arranges child widgets left-to-right and wraps to the next line."""

    def __init__(self, parent: QWidget | None = None, h_spacing: int = 4, v_spacing: int = 4):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            space_x = self._h_spacing
            space_y = self._v_spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + margins.bottom()


_STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {_BG};
    color: {_FG};
    font-family: "Segoe UI";
    font-size: 10pt;
}}

QPushButton {{
    background: {_BTN_BG};
    color: {_FG};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 32px;
}}

QPushButton:hover {{
    background: {_BTN_HOVER};
}}

QPushButton:disabled {{
    background: {_BG_LIGHT};
    color: {_FG_DIM};
}}

QLineEdit, QComboBox {{
    background: {_BG_MID};
    color: {_FG};
    border: 1px solid {_BG_LIGHT};
    border-radius: 3px;
    padding: 4px;
}}

QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {_ACCENT_BLUE};
}}

QComboBox::drop-down {{
    border: none;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 5px solid {_FG};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background: {_BG_MID};
    color: {_FG};
    selection-background-color: {_ACCENT_BLUE};
    selection-color: {_BG};
}}

QPlainTextEdit {{
    background: {_BG_MID};
    color: {_FG};
    border: 1px solid {_BG_LIGHT};
    border-radius: 3px;
}}

QListWidget {{
    background: {_BG_MID};
    color: {_FG};
    border: 1px solid {_BG_LIGHT};
    border-radius: 3px;
}}

QListWidget::item:selected {{
    background: {_ACCENT_BLUE};
    color: {_BG};
}}

QCheckBox {{
    color: {_FG};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {_BG_LIGHT};
    border-radius: 3px;
    background: {_BG_MID};
}}

QCheckBox::indicator:checked {{
    background: {_ACCENT_BLUE};
}}

QSplitter::handle {{
    background: {_BG_LIGHT};
}}

QSplitter::handle:horizontal {{
    width: 6px;
}}

QSplitter::handle:vertical {{
    height: 6px;
}}

QScrollBar:vertical {{
    background: {_BG_MID};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {_BTN_BG};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {_BG_MID};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {_BTN_BG};
    border-radius: 4px;
    min-width: 20px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QPushButton#RecordButton {{
    background: #2d5a2d;
    color: {_ACCENT_GREEN};
}}

QPushButton#RecordButton:hover {{
    background: #3a7a3a;
}}

QPushButton#StopButton {{
    background: #5a2d2d;
    color: {_ACCENT_RED};
}}

QPushButton#StopButton:hover {{
    background: #7a3a3a;
}}

QPushButton#AddButton {{
    background: #2d3d5a;
    color: {_ACCENT_BLUE};
}}

QPushButton#AddButton:hover {{
    background: #3a4d7a;
}}

QPushButton#DangerButton {{
    background: #5a2d2d;
    color: {_ACCENT_RED};
}}

QPushButton#DangerButton:hover {{
    background: #7a3a3a;
}}

QPushButton#ApplyButton {{
    background: #2d4a7a;
    color: {_ACCENT_BLUE};
}}

QPushButton#ApplyButton:hover {{
    background: #3a5a9a;
}}

QLabel#SectionLabel {{
    color: {_ACCENT_BLUE};
    font-size: 12pt;
    font-weight: bold;
}}

QLabel#GroupLabel {{
    color: {_FG_DIM};
    font-size: 8pt;
}}

QFrame#CardFrame {{
    background: {_BG_MID};
    border-radius: 6px;
    padding: 12px;
}}

QLabel#CardLabel {{
    background: {_BG_MID};
    color: {_FG};
}}

QLabel#CardHeaderLabel {{
    background: {_BG_MID};
    color: {_ACCENT_BLUE};
    font-weight: bold;
}}

QLabel#StatusPill {{
    background: {_BG_LIGHT};
    color: {_FG_DIM};
    padding: 4px 14px;
    font-weight: bold;
    border-radius: 10px;
}}

QLabel#RecIndicator {{
    background: {_BG_LIGHT};
    color: {_FG_DIM};
    padding: 2px 8px;
    font-weight: bold;
}}

QPlainTextEdit#LogText {{
    background: {_LOG_BG};
}}
"""


class StudioApp(QMainWindow):
    _log_signal = Signal(str)
    _phase_signal = Signal(str)
    _run_finished_signal = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Robot Automation Studio")
        self.resize(1200, 760)
        self.setMinimumSize(960, 640)

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        self.recorder = ScenarioRecorder(
            on_record_error=self._on_record_error,
            unity_bridge=self.unity_bridge,
        )
        self.current_path: Path | None = None
        self.selected_index: int | None = None

        self._run_thread: threading.Thread | None = None
        self._run_process: subprocess.Popen[str] | None = None
        self._run_lock = threading.Lock()
        self._stop_requested = False
        self._stop_hotkey_listener: pynput_keyboard.GlobalHotKeys | None = None
        self._overlay: AutomationRunOverlay | None = None
        self._overlay_mode: OverlayMode | None = None
        self._run_phase = "idle"
        self._status_spinner_index = 0
        self._phase_promotion_from = ""
        self._phase_promotion_to = ""

        self._help_entries_by_widget: dict[QWidget, HelpEntry] = {}
        self._help_entries_by_id: dict[str, HelpEntry] = {}
        self._help_dialog: QDialog | None = None

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(160)
        self._status_timer.timeout.connect(self._tick_robot_status)

        self._phase_promotion_timer = QTimer(self)
        self._phase_promotion_timer.setSingleShot(True)
        self._phase_promotion_timer.timeout.connect(self._do_phase_promotion)

        self._log_signal.connect(self.log)
        self._phase_signal.connect(self._set_run_phase)
        self._run_finished_signal.connect(self._on_robot_run_finished)

        self._build_ui()

        f1_shortcut = QShortcut(QKeySequence("F1"), self)
        f1_shortcut.activated.connect(self.open_help_guide)

        self.refresh_steps()

    def _build_ui(self) -> None:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll_area)
        central = QWidget()
        scroll_area.setWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        config_header_layout = QHBoxLayout()
        config_header_layout.setContentsMargins(12, 12, 12, 0)
        config_header_label = QLabel("Scenario Configuration")
        config_header_label.setObjectName("SectionLabel")
        config_header_layout.addWidget(config_header_label)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {_BG_LIGHT}; max-height: 1px;")
        config_header_layout.addWidget(separator, 1)
        self.open_guide_button = QPushButton("Open Guide (F1)")
        self.open_guide_button.clicked.connect(self.open_help_guide)
        config_header_layout.addWidget(self.open_guide_button)
        main_layout.addLayout(config_header_layout)

        config_card = QFrame()
        config_card.setObjectName("CardFrame")
        config_card_layout = QFormLayout(config_card)
        config_card_layout.setSpacing(8)
        config_card_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name_edit = QLineEdit(self.scenario.name)
        config_card_layout.addRow("Scenario Name", self.name_edit)

        self.scenario_id_edit = QLineEdit(self.scenario.scenario_id)
        config_card_layout.addRow("Scenario ID", self.scenario_id_edit)

        self.target_combo = QComboBox()
        self.target_combo.addItems(["unity", "web", "desktop", "hybrid"])
        self.target_combo.setCurrentText(self.scenario.target)
        config_card_layout.addRow("Target", self.target_combo)

        self.window_hint_edit = QLineEdit(self.scenario.target_window_hint)
        config_card_layout.addRow("Window Hint", self.window_hint_edit)

        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.addItems(["attach", "launch"])
        execution_mode = normalize_unity_execution_mode(
            self.scenario.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach")
        )
        self.execution_mode_combo.setCurrentText(execution_mode)
        self.execution_mode_combo.currentTextChanged.connect(self.on_execution_mode_changed)
        config_card_layout.addRow("Execution Mode", self.execution_mode_combo)

        project_path_row = QHBoxLayout()
        self.project_path_edit = QLineEdit(
            str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, ""))
        )
        project_path_row.addWidget(self.project_path_edit, 1)
        self.project_path_browse_button = QPushButton("Browse")
        self.project_path_browse_button.clicked.connect(self.browse_unity_project_path)
        project_path_row.addWidget(self.project_path_browse_button)
        config_card_layout.addRow("Unity Project Path", project_path_row)

        self.description_edit = QLineEdit(self.scenario.description)
        config_card_layout.addRow("Description", self.description_edit)

        config_tools_layout = QHBoxLayout()
        config_tools_layout.setContentsMargins(0, 4, 0, 0)
        variables_button = QPushButton("Variables")
        variables_button.clicked.connect(self.open_variables_editor)
        config_tools_layout.addWidget(variables_button)
        profiles_button = QPushButton("Profiles")
        profiles_button.clicked.connect(self.open_profiles_editor)
        config_tools_layout.addWidget(profiles_button)
        execution_outputs_button = QPushButton("Execution/Outputs")
        execution_outputs_button.clicked.connect(self.open_execution_outputs_editor)
        config_tools_layout.addWidget(execution_outputs_button)
        config_tools_layout.addStretch()
        config_card_layout.addRow(config_tools_layout)

        config_card_wrapper = QWidget()
        config_card_wrapper_layout = QVBoxLayout(config_card_wrapper)
        config_card_wrapper_layout.setContentsMargins(12, 4, 12, 0)
        config_card_wrapper_layout.addWidget(config_card)
        main_layout.addWidget(config_card_wrapper)

        help_card = QFrame()
        help_card.setObjectName("CardFrame")
        help_card_layout = QHBoxLayout(help_card)
        help_header = QLabel("Context Help")
        help_header.setObjectName("CardHeaderLabel")
        help_card_layout.addWidget(help_header)
        self.help_status_label = QLabel(
            "Hover or focus any UI component to view its explanation. Press F1 for full guide."
        )
        self.help_status_label.setObjectName("CardLabel")
        self.help_status_label.setWordWrap(True)
        help_card_layout.addWidget(self.help_status_label, 1)
        help_card_wrapper = QWidget()
        help_card_wrapper_layout = QVBoxLayout(help_card_wrapper)
        help_card_wrapper_layout.setContentsMargins(12, 8, 12, 0)
        help_card_wrapper_layout.addWidget(help_card)
        main_layout.addWidget(help_card_wrapper)

        toolbar_outer = QWidget()
        toolbar_flow = _FlowLayout(toolbar_outer, h_spacing=6, v_spacing=4)
        toolbar_flow.setContentsMargins(12, 12, 12, 4)

        rec_group_layout = self._make_toolbar_group(toolbar_flow, "Recording")
        btn = QPushButton("\u25cf Start")
        btn.setObjectName("RecordButton")
        btn.setToolTip("Start recording UI actions")
        btn.clicked.connect(self.start_recording)
        rec_group_layout.addWidget(btn)
        btn = QPushButton("\u25a0 Stop")
        btn.setObjectName("StopButton")
        btn.setToolTip("Stop recording")
        btn.clicked.connect(self.stop_recording)
        rec_group_layout.addWidget(btn)

        add_group_layout = self._make_toolbar_group(toolbar_flow, "Add Step")
        for label_text, tip, callback in [
            ("\U0001f5b1 Click", "Add a click step", self.add_click),
            ("\u2194 Drag", "Add a drag step", self.add_drag),
            ("\u2328 Shortcut", "Add a keyboard shortcut step", self.add_shortcut),
            ("\u2261 Menu", "Add a menu navigation step", self.add_menu),
            ("\u270e Type", "Add a text typing step", self.add_type),
            ("IF", "Add a control step", self.add_control),
            ("[] Group", "Add a group step", self.add_group),
        ]:
            btn = QPushButton(label_text)
            btn.setObjectName("AddButton")
            btn.setToolTip(tip)
            btn.clicked.connect(callback)
            add_group_layout.addWidget(btn)

        edit_group_layout = self._make_toolbar_group(toolbar_flow, "Edit")
        btn = QPushButton("\u2715 Delete")
        btn.setObjectName("DangerButton")
        btn.setToolTip("Delete selected step")
        btn.clicked.connect(self.delete_selected)
        edit_group_layout.addWidget(btn)
        btn = QPushButton("\u25b2 Up")
        btn.setToolTip("Move step up")
        btn.clicked.connect(self.move_up)
        edit_group_layout.addWidget(btn)
        btn = QPushButton("\u25bc Down")
        btn.setToolTip("Move step down")
        btn.clicked.connect(self.move_down)
        edit_group_layout.addWidget(btn)
        btn = QPushButton("\u2398 Duplicate")
        btn.setToolTip("Duplicate selected step")
        btn.clicked.connect(self.duplicate_selected)
        edit_group_layout.addWidget(btn)

        file_group_layout = self._make_toolbar_group(toolbar_flow, "File")
        btn = QPushButton("\U0001f4be Save")
        btn.setToolTip("Save scenario as JSON")
        btn.clicked.connect(self.save_json)
        file_group_layout.addWidget(btn)
        btn = QPushButton("\U0001f4c2 Load")
        btn.setToolTip("Load scenario from JSON")
        btn.clicked.connect(self.load_json)
        file_group_layout.addWidget(btn)
        btn = QPushButton("{} Full JSON")
        btn.setToolTip("Edit full v2 scenario JSON")
        btn.clicked.connect(self.open_full_json_editor)
        file_group_layout.addWidget(btn)

        self._rec_indicator = QLabel(" IDLE ")
        self._rec_indicator.setObjectName("RecIndicator")
        toolbar_flow.addWidget(self._rec_indicator)

        main_layout.addWidget(toolbar_outer)

        steps_header_layout = QHBoxLayout()
        steps_header_layout.setContentsMargins(12, 12, 12, 0)
        steps_header_label = QLabel("Steps & Editor")
        steps_header_label.setObjectName("SectionLabel")
        steps_header_layout.addWidget(steps_header_label)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {_BG_LIGHT}; max-height: 1px;")
        steps_header_layout.addWidget(separator, 1)
        main_layout.addLayout(steps_header_layout)

        steps_body_wrapper = QWidget()
        steps_body_layout = QHBoxLayout(steps_body_wrapper)
        steps_body_layout.setContentsMargins(12, 4, 12, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.step_list = QListWidget()
        self.step_list.setFont(QFont("Consolas", 11))
        self.step_list.currentRowChanged.connect(self.on_select_step)
        splitter.addWidget(self.step_list)

        editor_card = QFrame()
        editor_card.setObjectName("CardFrame")
        editor_card_layout = QVBoxLayout(editor_card)
        editor_header = QLabel("Step Details")
        editor_header.setObjectName("CardHeaderLabel")
        editor_card_layout.addWidget(editor_header)

        edit_form = QFormLayout()
        edit_form.setSpacing(8)
        edit_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.step_id_edit = QLineEdit()
        edit_form.addRow("Step ID", self.step_id_edit)

        self.title_edit = QLineEdit()
        edit_form.addRow("Title", self.title_edit)

        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["action", "control", "group"])
        edit_form.addRow("Kind", self.kind_combo)

        self.action_edit = QLineEdit()
        edit_form.addRow("Action", self.action_edit)

        self.control_edit = QLineEdit()
        edit_form.addRow("Control", self.control_edit)

        self.step_description_edit = QLineEdit()
        edit_form.addRow("Description", self.step_description_edit)

        self.step_condition_edit = QLineEdit()
        edit_form.addRow("Condition", self.step_condition_edit)

        checks_layout = QHBoxLayout()
        self.step_disabled_check = QCheckBox("Disabled")
        checks_layout.addWidget(self.step_disabled_check)
        self.step_continue_on_error_check = QCheckBox("Continue On Error")
        checks_layout.addWidget(self.step_continue_on_error_check)
        checks_layout.addStretch()
        edit_form.addRow(checks_layout)

        self.annotations_text = QPlainTextEdit()
        self.annotations_text.setFont(QFont("Consolas", 9))
        self.annotations_text.setMaximumHeight(80)
        edit_form.addRow("Annotations (JSON)", self.annotations_text)

        self.params_text = QPlainTextEdit()
        self.params_text.setFont(QFont("Consolas", 10))
        self.params_text.setMaximumHeight(160)
        edit_form.addRow("Params (JSON)", self.params_text)

        editor_card_layout.addLayout(edit_form)

        self.apply_step_button = QPushButton("Apply Step Changes")
        self.apply_step_button.setObjectName("ApplyButton")
        self.apply_step_button.clicked.connect(self.apply_step_changes)
        editor_card_layout.addWidget(self.apply_step_button)

        splitter.addWidget(editor_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        steps_body_layout.addWidget(splitter)
        main_layout.addWidget(steps_body_wrapper, 1)

        run_header_layout = QHBoxLayout()
        run_header_layout.setContentsMargins(12, 12, 12, 0)
        run_header_label = QLabel("Export & Run")
        run_header_label.setObjectName("SectionLabel")
        run_header_layout.addWidget(run_header_label)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {_BG_LIGHT}; max-height: 1px;")
        run_header_layout.addWidget(separator, 1)
        main_layout.addLayout(run_header_layout)

        run_card = QFrame()
        run_card.setObjectName("CardFrame")
        run_card_layout = QFormLayout(run_card)
        run_card_layout.setSpacing(8)
        run_card_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.output_dir_edit = QLineEdit("artifacts/studio")
        run_card_layout.addRow("Output Dir", self.output_dir_edit)

        export_name_row = QHBoxLayout()
        self.export_name_edit = QLineEdit("unity-editor-generated")
        export_name_row.addWidget(self.export_name_edit, 1)
        export_button = QPushButton("Export")
        export_button.clicked.connect(self.export_scenario)
        export_name_row.addWidget(export_button)
        run_card_layout.addRow("Export Name", export_name_row)

        run_buttons_layout = QHBoxLayout()
        self.run_robot_button = QPushButton("Run Robot")
        self.run_robot_button.setObjectName("RecordButton")
        self.run_robot_button.clicked.connect(self.run_robot_suite)
        run_buttons_layout.addWidget(self.run_robot_button)
        self.stop_robot_button = QPushButton(f"Stop Robot ({STOP_HOTKEY_LABEL})")
        self.stop_robot_button.setObjectName("StopButton")
        self.stop_robot_button.setEnabled(False)
        self.stop_robot_button.clicked.connect(self.stop_robot_suite)
        run_buttons_layout.addWidget(self.stop_robot_button)
        self._status_pill = QLabel(format_run_status("idle", SPINNER_FRAMES[0]))
        self._status_pill.setObjectName("StatusPill")
        run_buttons_layout.addWidget(self._status_pill)
        run_buttons_layout.addStretch()
        run_card_layout.addRow(run_buttons_layout)

        run_card_wrapper = QWidget()
        run_card_wrapper_layout = QVBoxLayout(run_card_wrapper)
        run_card_wrapper_layout.setContentsMargins(12, 4, 12, 0)
        run_card_wrapper_layout.addWidget(run_card)
        main_layout.addWidget(run_card_wrapper)

        log_header_layout = QHBoxLayout()
        log_header_layout.setContentsMargins(12, 12, 12, 0)
        log_header_label = QLabel("Output Log")
        log_header_label.setObjectName("SectionLabel")
        log_header_layout.addWidget(log_header_label)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {_BG_LIGHT}; max-height: 1px;")
        log_header_layout.addWidget(separator, 1)
        main_layout.addLayout(log_header_layout)

        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("LogText")
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumBlockCount(5000)
        log_wrapper = QWidget()
        log_wrapper_layout = QVBoxLayout(log_wrapper)
        log_wrapper_layout.setContentsMargins(12, 4, 12, 12)
        log_wrapper_layout.addWidget(self.log_text)
        main_layout.addWidget(log_wrapper)

        self.on_execution_mode_changed()

    def _make_toolbar_group(self, parent_layout: QLayout, label: str) -> QHBoxLayout:
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(4, 0, 4, 0)
        group_layout.setSpacing(2)
        group_label = QLabel(label)
        group_label.setObjectName("GroupLabel")
        group_layout.addWidget(group_label, 0, Qt.AlignmentFlag.AlignLeft)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        group_layout.addLayout(btn_layout)
        parent_layout.addWidget(group_widget)
        return btn_layout

    def _sync_scenario_header(self) -> None:
        self.scenario.name = self.name_edit.text().strip() or "Scenario"
        self.scenario.scenario_id = (
            self.scenario_id_edit.text().strip() or self.scenario.scenario_id
        )
        self.scenario.target = self.target_combo.currentText().strip() or "unity"
        self.scenario.description = self.description_edit.text().strip()
        self.scenario.target_window_hint = self.window_hint_edit.text().strip() or "Unity"
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        self.execution_mode_combo.setCurrentText(execution_mode)
        unity_project_path = self.project_path_edit.text().strip()
        self.scenario.sync_runtime_metadata(
            execution_mode=execution_mode,
            unity_project_path=unity_project_path,
        )

    def _on_record_error(self, message: str) -> None:
        QTimer.singleShot(0, lambda: self.log(f"Record error: {message}"))

    @Slot(str)
    def log(self, message: str) -> None:
        self.log_text.appendPlainText(message)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.log_text.ensureCursorVisible()

    def _log_async(self, message: str) -> None:
        self._log_signal.emit(message)

    def _update_status_bar_color(self) -> None:
        phase = self._run_phase
        if phase == "idle":
            bg = _BG_LIGHT
            fg = _FG_DIM
        elif phase == "stopping":
            bg = "#5a2d2d"
            fg = _ACCENT_RED
        else:
            bg = "#4a3d1a"
            fg = _ACCENT_YELLOW
        self._status_pill.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 4px 14px; "
            f"font-weight: bold; border-radius: 10px;"
        )

    def _render_robot_status(self) -> None:
        spinner = SPINNER_FRAMES[self._status_spinner_index]
        status_text = format_run_status(self._run_phase, spinner)
        self._status_pill.setText(status_text)
        self._update_status_bar_color()
        if self._overlay is not None and self._overlay_mode == "run":
            self._overlay.set_progress_text(status_text)

    @Slot()
    def _tick_robot_status(self) -> None:
        if self._run_phase == "idle":
            self._status_timer.stop()
            return
        self._status_spinner_index = next_spinner_index(self._status_spinner_index)
        self._render_robot_status()

    @Slot(str)
    def _set_run_phase(self, phase: str) -> None:
        self._run_phase = phase
        self._render_robot_status()
        if phase == "idle":
            self._status_timer.stop()
            self._phase_promotion_timer.stop()
            return
        if not self._status_timer.isActive():
            self._status_timer.start()

    def _set_run_phase_async(self, phase: str) -> None:
        self._phase_signal.emit(phase)

    def _schedule_phase_promotion(self, from_phase: str, to_phase: str, delay_ms: int) -> None:
        self._phase_promotion_timer.stop()
        self._phase_promotion_from = from_phase
        self._phase_promotion_to = to_phase
        self._phase_promotion_timer.start(delay_ms)

    @Slot()
    def _do_phase_promotion(self) -> None:
        if self._run_phase != self._phase_promotion_from:
            return
        self._set_run_phase(self._phase_promotion_to)

    def _set_run_controls(self, running: bool, stopping: bool = False) -> None:
        if running:
            self.run_robot_button.setEnabled(False)
            self.stop_robot_button.setEnabled(True)
            if stopping:
                self._set_run_phase("stopping")
            elif self._run_phase == "idle":
                self._set_run_phase("running")
            return
        self.run_robot_button.setEnabled(True)
        self.stop_robot_button.setEnabled(False)
        self._set_run_phase("idle")

    def _set_current_process(self, process: subprocess.Popen[str] | None) -> None:
        with self._run_lock:
            self._run_process = process

    def _get_current_process(self) -> subprocess.Popen[str] | None:
        with self._run_lock:
            return self._run_process

    def _start_stop_hotkey(self) -> None:
        def _on_hotkey() -> None:
            QTimer.singleShot(0, self._stop_active_automation)

        try:
            self._stop_hotkey_listener = pynput_keyboard.GlobalHotKeys(
                {
                    STOP_HOTKEY_BIND: _on_hotkey,
                }
            )
            self._stop_hotkey_listener.start()
        except Exception as error:
            self._stop_hotkey_listener = None
            self.log(f"Failed to register stop hotkey: {error}")

    def _stop_stop_hotkey(self) -> None:
        listener = self._stop_hotkey_listener
        if listener is None:
            return
        listener.stop()
        self._stop_hotkey_listener = None

    def _start_overlay(self, mode: OverlayMode, progress_text: str) -> None:
        if self._overlay is not None and self._overlay_mode == mode:
            self._overlay.set_progress_text(progress_text)
            return
        if self._overlay is not None:
            self._stop_overlay()
        try:
            self._overlay = AutomationRunOverlay(
                parent=self,
                window_hint=self.window_hint_edit.text().strip() or "Unity",
                stop_hotkey_label=STOP_HOTKEY_LABEL,
                mode=mode,
            )
            self._overlay_mode = mode
            self._overlay.start()
            self._overlay.set_progress_text(progress_text)
        except Exception as error:
            self._overlay = None
            self._overlay_mode = None
            self.log(f"Failed to start overlay: {error}")

    def _stop_overlay(self) -> None:
        if self._overlay is None:
            return
        self._overlay.stop()
        self._overlay = None
        self._overlay_mode = None

    def _stop_active_automation(self) -> None:
        if self.recorder.is_recording:
            self.stop_recording()
            return
        if self._is_robot_running():
            self.stop_robot_suite()

    def refresh_steps(self) -> None:
        self.step_list.clear()
        for idx, step in enumerate(self.scenario.steps):
            label = (
                step.action
                if step.kind == "action"
                else step.control
                if step.kind == "control"
                else "group"
            )
            self.step_list.addItem(f"{idx + 1}. [{step.kind}] {label} - {step.title}")

    @Slot(int)
    def on_select_step(self, row: int) -> None:
        if row < 0 or row >= len(self.scenario.steps):
            self.selected_index = None
            self.step_id_edit.clear()
            self.title_edit.clear()
            self.kind_combo.setCurrentText("action")
            self.action_edit.clear()
            self.control_edit.clear()
            self.step_description_edit.clear()
            self.step_condition_edit.clear()
            self.step_disabled_check.setChecked(False)
            self.step_continue_on_error_check.setChecked(False)
            self.annotations_text.clear()
            self.params_text.clear()
            return
        self.selected_index = row
        step = self.scenario.steps[row]
        self.step_id_edit.setText(step.id)
        self.title_edit.setText(step.title)
        self.kind_combo.setCurrentText(step.kind)
        self.action_edit.setText(step.action)
        self.control_edit.setText(step.control)
        self.step_description_edit.setText(step.description)
        self.step_condition_edit.setText(step.condition)
        self.step_disabled_check.setChecked(step.disabled)
        self.step_continue_on_error_check.setChecked(step.continue_on_error)
        self.annotations_text.setPlainText(
            json.dumps(step.annotations, ensure_ascii=False, indent=2)
        )
        self.params_text.setPlainText(json.dumps(step.params, ensure_ascii=False, indent=2))

    def on_execution_mode_changed(self) -> None:
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        self.execution_mode_combo.setCurrentText(execution_mode)
        self.project_path_edit.setEnabled(True)
        self.project_path_browse_button.setEnabled(True)

    def _ensure_unity_bridge_dependency_if_configured(self, purpose: str) -> bool:
        project_path_raw = self.project_path_edit.text().strip()
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        package_script_meta_detected = False

        if project_path_raw == "" and execution_mode == "attach":
            detected_path = resolve_attached_unity_project_path(
                window_hint=self.window_hint_edit.text().strip() or "Unity"
            )
            if detected_path:
                self.project_path_edit.setText(detected_path)
                project_path_raw = detected_path
                self.log(f"Auto-detected Unity Project Path: {detected_path}")

        changed = False
        if project_path_raw != "":
            project_root = Path(project_path_raw)
            package_script_meta_detected = has_unity_bridge_package_script_meta(project_root)
            if package_script_meta_detected:
                self.log("Unity bridge package script metadata detected.")
            else:
                self.log(
                    "Unity bridge package script metadata is missing; "
                    "using legacy fallback bridge script mode."
                )
            self.log(f"Ensuring Unity bridge package for {purpose}: {project_path_raw}")
            try:
                changed = ensure_unity_bridge_upm_dependency(
                    project_root,
                    remove_legacy_bridge_script=package_script_meta_detected,
                )
            except Exception as error:
                self.log(f"Unity bridge package setup failed: {error}")
                QMessageBox.critical(
                    self,
                    "Unity Bridge Setup Error",
                    (
                        "Failed to prepare Unity bridge UPM dependency.\n"
                        f"Path: {project_path_raw}\n"
                        f"Error: {error}"
                    ),
                )
                return False
            if changed:
                self.log("Unity bridge UPM dependency added/updated for this project.")
            else:
                self.log("Unity bridge UPM dependency already present.")
            if not package_script_meta_detected:
                try:
                    fallback_changed = install_legacy_unity_bridge_script(project_root)
                    if fallback_changed:
                        self.log(
                            "Installed fallback bridge script: "
                            "Assets/Editor/RobotFrameworkUnityBridge.cs"
                        )
                    else:
                        self.log("Fallback bridge script already installed.")
                    changed = changed or fallback_changed
                except Exception as error:
                    self.log(f"Fallback bridge installation failed: {error}")
                    QMessageBox.critical(
                        self,
                        "Unity Bridge Setup Error",
                        (
                            "Failed to install fallback Unity bridge script.\n"
                            f"Path: {project_path_raw}\n"
                            f"Error: {error}"
                        ),
                    )
                    return False

        if purpose in {"recording", "run"}:
            wait_timeouts = build_recording_readiness_timeouts(
                changed=changed,
                execution_mode=execution_mode,
                changed_timeout_seconds=BRIDGE_READY_TIMEOUT_SECONDS,
                quick_timeout_seconds=BRIDGE_READY_CHECK_TIMEOUT_SECONDS,
                attach_retry_timeout_seconds=BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS,
            )
            bridge_ready = False
            attempt_count = len(wait_timeouts)
            for attempt_index, wait_timeout in enumerate(wait_timeouts):
                attempt_number = attempt_index + 1
                if execution_mode == "attach":
                    focused = focus_visible_window_with_hint(
                        self.window_hint_edit.text().strip() or "Unity"
                    )
                    if focused:
                        if attempt_number == 1:
                            self.log("Focused target Unity window for bridge startup check.")
                        else:
                            self.log("Refocused target Unity window and retrying bridge readiness.")
                self.log(
                    f"Checking Unity bridge readiness... (attempt {attempt_number}/{attempt_count})"
                )
                if self.unity_bridge.wait_until_available(
                    timeout_seconds=wait_timeout,
                    request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                ):
                    bridge_ready = True
                    break
            if not bridge_ready:
                self.log("Unity bridge readiness check timed out.")
                if execution_mode == "attach":
                    refreshed = trigger_assets_refresh_shortcut_with_hint(
                        self.window_hint_edit.text().strip() or "Unity"
                    )
                    if refreshed:
                        self.log(
                            "Triggered Unity Assets Refresh (Ctrl+R) on target window. "
                            "Waiting for bridge..."
                        )
                        if self.unity_bridge.wait_until_available(
                            timeout_seconds=BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS,
                            request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                        ):
                            self.log("Unity bridge is ready after refresh.")
                            return True
                    else:
                        self.log(
                            "Could not trigger Unity Assets Refresh shortcut on target window."
                        )
                if project_path_raw != "":
                    project_root = Path(project_path_raw)
                    if not package_script_meta_detected:
                        self.log(
                            "Unity bridge package script metadata is still missing after wait. "
                            "Re-installing fallback bridge script..."
                        )
                        try:
                            fallback_changed = install_legacy_unity_bridge_script(project_root)
                            if fallback_changed:
                                self.log(
                                    "Installed fallback bridge script: "
                                    "Assets/Editor/RobotFrameworkUnityBridge.cs"
                                )
                            else:
                                self.log("Fallback bridge script already exists.")
                            if execution_mode == "attach":
                                focus_visible_window_with_hint(
                                    self.window_hint_edit.text().strip() or "Unity"
                                )
                            self.log("Waiting for fallback bridge readiness...")
                            if self.unity_bridge.wait_until_available(
                                timeout_seconds=BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS,
                                request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                            ):
                                self.log("Unity bridge is ready (fallback bridge).")
                                return True
                        except Exception as error:
                            self.log(f"Fallback bridge installation failed: {error}")
                compile_errors = get_recent_unity_compile_errors(limit=3)
                compile_error_hint = ""
                if compile_errors:
                    self.log("Detected Unity compile errors in Editor.log:")
                    for line in compile_errors:
                        self.log(f"  {line}")
                    compile_error_hint = (
                        "\n\nDetected recent Unity compile errors:\n- "
                        + "\n- ".join(compile_errors)
                    )
                retry_action = "Start Recording" if purpose == "recording" else "Run Robot"
                QMessageBox.critical(
                    self,
                    "Unity Bridge Not Ready",
                    (
                        "Unity bridge is not ready yet.\n"
                        "Unity may still be importing packages or compiling scripts.\n"
                        f"Open/focus the target Unity Editor and retry {retry_action}.\n"
                        "If this persists, fix Unity compile errors first."
                        f"{compile_error_hint}"
                    ),
                )
                return False
            self.log("Unity bridge is ready.")
        return True

    def browse_unity_project_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Unity Project Root")
        if not selected:
            return
        self.project_path_edit.setText(selected)

    def apply_step_changes(self) -> None:
        if self.selected_index is None:
            return
        try:
            params = json.loads(self.params_text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(self, "Invalid Params JSON", str(error))
            return
        try:
            annotations = json.loads(self.annotations_text.toPlainText().strip() or "[]")
        except json.JSONDecodeError as error:
            QMessageBox.critical(self, "Invalid Annotations JSON", str(error))
            return
        if not isinstance(params, dict):
            QMessageBox.critical(self, "Invalid Params JSON", "Params must be a JSON object.")
            return
        if not isinstance(annotations, list):
            QMessageBox.critical(
                self, "Invalid Annotations JSON", "Annotations must be a JSON array."
            )
            return
        kind = self.kind_combo.currentText().strip().lower() or "action"
        action = self.action_edit.text().strip()
        control = self.control_edit.text().strip()
        if kind == "action" and action == "":
            action = self.scenario.steps[self.selected_index].action or "click"
        if kind == "control" and control == "":
            control = self.scenario.steps[self.selected_index].control or "if"
        self.editor.update_step(
            self.selected_index,
            title=self.title_edit.text().strip(),
            kind=kind,
            action=action if kind == "action" else None,
            control=control if kind == "control" else None,
            description=self.step_description_edit.text().strip(),
            condition=self.step_condition_edit.text().strip(),
            disabled=self.step_disabled_check.isChecked(),
            continue_on_error=self.step_continue_on_error_check.isChecked(),
            annotations=[dict(item) for item in annotations if isinstance(item, dict)],
            params=params,
        )
        step_id = self.step_id_edit.text().strip()
        if step_id != "":
            self.scenario.steps[self.selected_index].id = step_id
        self.refresh_steps()

    def start_recording(self) -> None:
        if self.recorder.is_recording:
            self.log("Recording is already running.")
            return
        window_hint = self.window_hint_edit.text().strip() or "Unity"
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        if execution_mode == "attach" and not has_visible_window_with_hint(window_hint):
            self.log(
                f"Recording start failed: attach target window not found. window_hint={window_hint}"
            )
            QMessageBox.critical(
                self,
                "Attach Target Not Found",
                (
                    "Could not find a visible target window for attach mode.\n"
                    f"Window Hint: {window_hint}\n"
                    "Open the target window and try Start Recording again."
                ),
            )
            return
        if not self._ensure_unity_bridge_dependency_if_configured("recording"):
            return
        self.recorder.start(window_hint=window_hint)
        self._start_stop_hotkey()
        self._start_overlay(mode="recording", progress_text="Recording")
        self._rec_indicator.setStyleSheet(
            f"background: {_ACCENT_RED}; color: {_BG}; padding: 2px 8px; font-weight: bold;"
        )
        self._rec_indicator.setText(" \u25cf REC ")
        self.setWindowTitle("Robot Automation Studio [RECORDING]")
        self.log(f"Recording started. window_hint={window_hint}")

    def stop_recording(self) -> None:
        if not self.recorder.is_recording:
            self.log("Recording is not running.")
            return
        events = self.recorder.stop()
        steps = events_to_steps(events)
        for step in steps:
            self.scenario.steps.append(step)
        self.refresh_steps()
        if not self._is_robot_running():
            self._stop_overlay()
            self._stop_stop_hotkey()
        self._rec_indicator.setStyleSheet(
            f"background: {_BG_LIGHT}; color: {_FG_DIM}; padding: 2px 8px; font-weight: bold;"
        )
        self._rec_indicator.setText(" IDLE ")
        self.setWindowTitle("Robot Automation Studio")
        self.log(f"Recording stopped. Added {len(steps)} steps.")

    def add_click(self) -> None:
        self.editor.add_step(
            "click",
            "click",
            {
                "title": "Inspector",
                "automation_id": "Inspector",
                "class_name": "Pane",
                "control_type": "Pane",
                "wait_seconds": 0.0,
            },
        )
        self.refresh_steps()

    def add_drag(self) -> None:
        self.editor.add_step(
            "drag_drop",
            "drag_drop",
            {
                "source_title": "Source",
                "source_automation_id": "Source",
                "target_title": "Target",
                "target_automation_id": "Target",
                "wait_seconds": 0.0,
            },
        )
        self.refresh_steps()

    def add_shortcut(self) -> None:
        self.editor.add_step("press_keys", "press_keys", {"shortcut": "CTRL+S"})
        self.refresh_steps()

    def add_menu(self) -> None:
        self.editor.add_step("open_menu", "open_menu", {"menu_path": "File>Save"})
        self.refresh_steps()

    def add_type(self) -> None:
        self.editor.add_step("type_text", "type_text", {"text": "sample"})
        self.refresh_steps()

    def add_control(self) -> None:
        self.editor.add_control_step(
            "if",
            "if",
            {
                "expression": "True",
                "steps": [],
            },
        )
        self.refresh_steps()

    def add_group(self) -> None:
        self.editor.add_group_step(
            title="group",
            params={
                "steps": [],
            },
        )
        self.refresh_steps()

    def delete_selected(self) -> None:
        if self.selected_index is None:
            return
        self.editor.delete_step(self.selected_index)
        self.selected_index = None
        self.refresh_steps()

    def move_up(self) -> None:
        if self.selected_index is None:
            return
        self.editor.move_step_up(self.selected_index)
        self.selected_index = max(0, self.selected_index - 1)
        self.refresh_steps()
        self.step_list.setCurrentRow(self.selected_index)

    def move_down(self) -> None:
        if self.selected_index is None:
            return
        self.editor.move_step_down(self.selected_index)
        self.selected_index = min(len(self.scenario.steps) - 1, self.selected_index + 1)
        self.refresh_steps()
        self.step_list.setCurrentRow(self.selected_index)

    def duplicate_selected(self) -> None:
        if self.selected_index is None:
            return
        self.editor.duplicate_step(self.selected_index)
        self.refresh_steps()

    def save_json(self) -> None:
        self._sync_scenario_header()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario",
            "",
            "Scenario JSON (*.scenario.json);;JSON (*.json)",
        )
        if not path:
            return
        target = Path(path)
        self.scenario.save_json(target)
        self.current_path = target
        self.log(f"Saved scenario: {target}")

    def load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scenario",
            "",
            "Scenario JSON (*.scenario.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            loaded = Scenario.load_json(Path(path))
        except Exception as error:
            QMessageBox.critical(self, "Load Error", str(error))
            self.log(f"Load failed: {error}")
            return
        self._apply_loaded_scenario(loaded)
        self.current_path = Path(path)
        self.log(f"Loaded scenario: {path}")

    def _apply_loaded_scenario(self, loaded: Scenario) -> None:
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.selected_index = None
        self.name_edit.setText(loaded.name)
        self.scenario_id_edit.setText(loaded.scenario_id)
        self.target_combo.setCurrentText(loaded.target)
        self.description_edit.setText(loaded.description)
        self.window_hint_edit.setText(loaded.target_window_hint)
        self.execution_mode_combo.setCurrentText(
            normalize_unity_execution_mode(loaded.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach"))
        )
        self.project_path_edit.setText(str(loaded.metadata.get(UNITY_PROJECT_PATH_KEY, "")))
        self.on_execution_mode_changed()
        self.refresh_steps()
        self.on_select_step(-1)

    def open_help_guide(self) -> None:
        if self._help_dialog is not None:
            self._help_dialog.raise_()
            self._help_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("GUI Help Guide")
        dialog.resize(980, 640)
        self._help_dialog = dialog

        layout = QVBoxLayout(dialog)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Search"))
        search_edit = QLineEdit()
        search_edit.setMinimumWidth(340)
        top_layout.addWidget(search_edit)
        summary_label = QLabel(f"{len(self._help_entries_by_id)} UI components are documented.")
        top_layout.addWidget(summary_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        listbox = QListWidget()
        listbox.setFont(QFont("Segoe UI", 10))
        splitter.addWidget(listbox)

        detail_text = QPlainTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setFont(QFont("Consolas", 9))
        splitter.addWidget(detail_text)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self._close_help_dialog)
        footer_layout.addWidget(close_button)
        layout.addLayout(footer_layout)

        visible_entries: list[HelpEntry] = []

        def _render_details(entry: HelpEntry) -> None:
            detail_text.setPlainText(
                f"Title: {entry.title}\n"
                f"Widget Class: {entry.widget_class}\n"
                f"Widget ID: {entry.widget_id}\n\n"
                f"Summary:\n{entry.summary}\n\n"
                f"Details:\n{entry.detail}\n"
            )

        def _refresh_list() -> None:
            visible_entries.clear()
            listbox.clear()
            filtered = filter_help_entries(self._sorted_help_entries(), search_edit.text())
            for entry in filtered:
                visible_entries.append(entry)
                listbox.addItem(f"{entry.title} [{entry.widget_class}]")
            summary_label.setText(
                f"{len(filtered)} / {len(self._help_entries_by_id)} components shown."
            )
            if visible_entries:
                listbox.setCurrentRow(0)
                _render_details(visible_entries[0])
            else:
                detail_text.setPlainText("No matching components.")

        def _on_select(row: int) -> None:
            if row < 0 or row >= len(visible_entries):
                return
            _render_details(visible_entries[row])

        search_edit.textChanged.connect(lambda: _refresh_list())
        listbox.currentRowChanged.connect(_on_select)

        dialog.finished.connect(lambda: setattr(self, "_help_dialog", None))

        _refresh_list()
        search_edit.setFocus()

        dialog.exec()

    def _close_help_dialog(self) -> None:
        if self._help_dialog is None:
            return
        self._help_dialog.close()
        self._help_dialog = None

    def _sorted_help_entries(self) -> list[HelpEntry]:
        return sorted(
            self._help_entries_by_id.values(),
            key=lambda item: (item.title.lower(), item.widget_class.lower(), item.widget_id),
        )

    def open_full_json_editor(self) -> None:
        self._sync_scenario_header()
        dialog = QDialog(self)
        dialog.setWindowTitle("Full Scenario JSON (v2)")
        dialog.resize(960, 720)

        layout = QVBoxLayout(dialog)

        top_layout = QHBoxLayout()
        format_button = QPushButton("Format")
        top_layout.addWidget(format_button)
        reload_button = QPushButton("Reload Model")
        top_layout.addWidget(reload_button)
        top_layout.addStretch()
        cancel_button = QPushButton("Cancel")
        top_layout.addWidget(cancel_button)
        apply_button = QPushButton("Apply")
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
                QMessageBox.critical(dialog, "Invalid JSON", str(error))
                return
            text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

        def _reload_model() -> None:
            self._sync_scenario_header()
            text.setPlainText(json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))

        def _apply_json() -> None:
            try:
                payload = json.loads(text.toPlainText().strip() or "{}")
            except json.JSONDecodeError as error:
                QMessageBox.critical(dialog, "Invalid JSON", str(error))
                return
            try:
                loaded = Scenario.from_dict(payload)
            except Exception as error:
                QMessageBox.critical(dialog, "Validation Error", str(error))
                return
            self._apply_loaded_scenario(loaded)
            self.log("Applied full scenario JSON editor changes.")
            dialog.accept()

        format_button.clicked.connect(_format_json)
        reload_button.clicked.connect(_reload_model)
        apply_button.clicked.connect(_apply_json)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def open_variables_editor(self) -> None:
        self._sync_scenario_header()
        dialog = QDialog(self)
        dialog.setWindowTitle("Variables Editor")
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
                listbox.addItem(f"{index + 1}. {variable_id} ({variable_type})")

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
                QMessageBox.critical(dialog, "Invalid Variable JSON", str(error))
                return False
            if not isinstance(payload, dict):
                QMessageBox.critical(
                    dialog, "Invalid Variable JSON", "Variable must be a JSON object."
                )
                return False
            if str(payload.get("id") or "").strip() == "":
                QMessageBox.critical(dialog, "Invalid Variable JSON", "Variable id is required.")
                return False
            if str(payload.get("type") or "").strip() == "":
                QMessageBox.critical(dialog, "Invalid Variable JSON", "Variable type is required.")
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
            self.log("Updated variables from Variables Editor.")
            dialog.accept()

        footer_layout = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(_add_variable)
        footer_layout.addWidget(add_button)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(_delete_variable)
        footer_layout.addWidget(delete_button)
        apply_button = QPushButton("Apply Current")
        apply_button.setObjectName("ApplyButton")
        apply_button.clicked.connect(_apply_current)
        footer_layout.addWidget(apply_button)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        footer_layout.addWidget(cancel_button)
        save_button = QPushButton("Save")
        save_button.setObjectName("ApplyButton")
        save_button.clicked.connect(_save_and_close)
        footer_layout.addWidget(save_button)
        layout.addLayout(footer_layout)

        listbox.currentRowChanged.connect(_on_select)
        _refresh_list()
        if variables:
            _select(0)

        dialog.exec()

    def open_profiles_editor(self) -> None:
        self._sync_scenario_header()
        dialog = QDialog(self)
        dialog.setWindowTitle("Profiles Editor")
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
                listbox.addItem(f"{index + 1}. {name}")

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
                QMessageBox.critical(dialog, "Invalid Profile JSON", str(error))
                return False
            if not isinstance(payload, dict):
                QMessageBox.critical(
                    dialog, "Invalid Profile JSON", "Profile payload must be a JSON object."
                )
                return False
            name = str(payload.get("name") or "").strip()
            profile = payload.get("profile")
            if name == "":
                QMessageBox.critical(dialog, "Invalid Profile JSON", "Profile name is required.")
                return False
            if not isinstance(profile, dict):
                QMessageBox.critical(
                    dialog, "Invalid Profile JSON", "profile field must be a JSON object."
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
            self.log("Updated profiles from Profiles Editor.")
            dialog.accept()

        footer_layout = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(_add_profile)
        footer_layout.addWidget(add_button)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(_delete_profile)
        footer_layout.addWidget(delete_button)
        apply_button = QPushButton("Apply Current")
        apply_button.setObjectName("ApplyButton")
        apply_button.clicked.connect(_apply_current)
        footer_layout.addWidget(apply_button)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        footer_layout.addWidget(cancel_button)
        save_button = QPushButton("Save")
        save_button.setObjectName("ApplyButton")
        save_button.clicked.connect(_save_and_close)
        footer_layout.addWidget(save_button)
        layout.addLayout(footer_layout)

        listbox.currentRowChanged.connect(_on_select)
        _refresh_list()
        if profile_names:
            _select(0)

        dialog.exec()

    def open_execution_outputs_editor(self) -> None:
        self._sync_scenario_header()
        dialog = QDialog(self)
        dialog.setWindowTitle("Execution / Outputs Editor")
        dialog.resize(980, 720)

        layout = QVBoxLayout(dialog)

        top_layout = QHBoxLayout()
        header_label = QLabel("Execution / Outputs JSON")
        header_label.setObjectName("CardHeaderLabel")
        top_layout.addWidget(header_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        execution_widget = QWidget()
        execution_layout = QVBoxLayout(execution_widget)
        execution_layout.addWidget(QLabel("execution"))
        execution_text = QPlainTextEdit()
        execution_text.setFont(QFont("Consolas", 9))
        execution_text.setPlainText(
            json.dumps(self.scenario.execution, ensure_ascii=False, indent=2)
        )
        execution_layout.addWidget(execution_text)
        splitter.addWidget(execution_widget)

        outputs_widget = QWidget()
        outputs_layout = QVBoxLayout(outputs_widget)
        outputs_layout.addWidget(QLabel("outputs"))
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
                QMessageBox.critical(dialog, "Invalid execution JSON", str(error))
                return False
            try:
                outputs_payload = json.loads(outputs_text.toPlainText().strip() or "{}")
            except json.JSONDecodeError as error:
                QMessageBox.critical(dialog, "Invalid outputs JSON", str(error))
                return False
            if not isinstance(execution_payload, dict):
                QMessageBox.critical(dialog, "Invalid execution JSON", "execution must be object.")
                return False
            if not isinstance(outputs_payload, dict):
                QMessageBox.critical(dialog, "Invalid outputs JSON", "outputs must be object.")
                return False
            self.scenario.execution = execution_payload
            self.scenario.outputs = outputs_payload
            mode = str(execution_payload.get("mode") or "").strip().lower()
            if mode in {"attach", "launch"}:
                self.execution_mode_combo.setCurrentText(mode)
            self.log("Updated execution/outputs from editor.")
            return True

        def _format() -> None:
            try:
                execution_payload = json.loads(execution_text.toPlainText().strip() or "{}")
                outputs_payload = json.loads(outputs_text.toPlainText().strip() or "{}")
            except json.JSONDecodeError as error:
                QMessageBox.critical(dialog, "Invalid JSON", str(error))
                return
            execution_text.setPlainText(json.dumps(execution_payload, ensure_ascii=False, indent=2))
            outputs_text.setPlainText(json.dumps(outputs_payload, ensure_ascii=False, indent=2))

        def _save_and_close() -> None:
            if _apply():
                dialog.accept()

        footer_layout = QHBoxLayout()
        format_button = QPushButton("Format")
        format_button.clicked.connect(_format)
        footer_layout.addWidget(format_button)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        footer_layout.addWidget(cancel_button)
        save_button = QPushButton("Save")
        save_button.setObjectName("ApplyButton")
        save_button.clicked.connect(_save_and_close)
        footer_layout.addWidget(save_button)
        apply_button = QPushButton("Apply")
        apply_button.setObjectName("ApplyButton")
        apply_button.clicked.connect(_apply)
        footer_layout.addWidget(apply_button)
        layout.addLayout(footer_layout)

        dialog.exec()

    def export_scenario(self) -> None:
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        except Exception as error:
            self.log(f"Export failed: {error}")
            QMessageBox.critical(self, "Export Error", str(error))
            return
        self.log(f"Exported robot: {result.robot_path}")
        self.log(f"Exported json: {result.json_path}")

    def _is_robot_running(self) -> bool:
        return self._run_thread is not None and self._run_thread.is_alive()

    def run_robot_suite(self) -> None:
        if self.recorder.is_recording:
            self.log("Stop recording before running Robot suite.")
            QMessageBox.critical(
                self,
                "Recording In Progress",
                "Stop recording before running Robot suite.",
            )
            return
        if self._is_robot_running():
            self.log("Robot suite is already running.")
            return
        self._sync_scenario_header()
        if not self._ensure_unity_bridge_dependency_if_configured("run"):
            return
        self._set_run_phase("exporting")
        self.log("Preparing scenario export...")
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        except Exception as error:
            self.log(f"Run export failed: {error}")
            QMessageBox.critical(self, "Run Error", str(error))
            self._set_run_phase("idle")
            return
        artifacts_dir = output_dir / "run"
        variable_output = output_dir
        self._stop_requested = False
        self._set_run_phase("starting_robot")
        self._set_run_controls(running=True)
        self._start_stop_hotkey()
        self._start_overlay(mode="run", progress_text=self._status_pill.text())

        def _run() -> None:
            run_result: RunResult | None = None
            run_error: Exception | None = None
            try:
                self._log_async("Running Robot suite...")
                self._set_run_phase_async("starting_robot")
                self._log_async("Starting Robot process...")
                process = start_robot_process(
                    suite_path=result.robot_path,
                    output_dir=artifacts_dir,
                    variable_output_dir=variable_output,
                )
                self._set_current_process(process)
                self._set_run_phase_async("attaching_unity")
                self._log_async("Attaching to Unity and waiting for first actions...")
                QTimer.singleShot(
                    0,
                    lambda: self._schedule_phase_promotion("attaching_unity", "running", 1800),
                )
                if self._stop_requested:
                    stop_robot_process(process)
                run_result = wait_robot_process(process)
            except Exception as error:
                run_error = error
            finally:
                self._set_current_process(None)
                self._run_finished_signal.emit(run_result, run_error)

        self._run_thread = threading.Thread(target=_run, daemon=True)
        self._run_thread.start()

    def stop_robot_suite(self) -> None:
        if not self._is_robot_running():
            self.log("Robot suite is not running.")
            return
        self._stop_requested = True
        self._set_run_controls(running=True, stopping=True)
        process = self._get_current_process()
        self.log(f"Stopping Robot suite... ({STOP_HOTKEY_LABEL})")
        if process is None:
            return
        stop_robot_process(process)

    @Slot(object, object)
    def _on_robot_run_finished(
        self,
        run_result: RunResult | None,
        run_error: Exception | None,
    ) -> None:
        if run_error is not None:
            self.log(f"Robot run failed: {run_error}")
        elif run_result is not None:
            self.log(f"robot exit={run_result.return_code}")
            if run_result.stdout:
                self.log(run_result.stdout.strip())
            if run_result.stderr:
                self.log(run_result.stderr.strip())
        if self._stop_requested:
            self.log("Robot suite stopped.")
        self._stop_requested = False
        self._stop_overlay()
        self._stop_stop_hotkey()
        self._set_run_controls(running=False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.recorder.is_recording:
            self.stop_recording()
        if self._is_robot_running():
            self.stop_robot_suite()
            QTimer.singleShot(250, self.close)
            event.ignore()
            return
        self._stop_overlay()
        self._stop_stop_hotkey()
        self._close_help_dialog()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(_STYLESHEET)
    window = StudioApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
