"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import threading
import warnings
from copy import deepcopy
from pathlib import Path

from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QEnterEvent,
    QFont,
    QHelpEvent,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
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
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolButton,
    QToolTip,
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
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .status import SPINNER_FRAMES, format_run_status, next_spinner_index
from .ui_help import HelpEntry, build_help_entry, filter_help_entries
from .unity_bridge import UnityBridgeClient
from .unity_diagnostics import get_recent_unity_compile_errors

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
_PYWINAUTO_PREPARED = False


def _import_pywinauto_with_warning_filters(importer) -> None:
    """Import pywinauto while suppressing known non-actionable startup warnings."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Apply externally defined coinit_flags:.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r"Revert to STA COM threading mode",
            category=UserWarning,
        )
        importer("pywinauto")


def _prepare_pywinauto_for_qt() -> None:
    """Prepare pywinauto COM mode before first recorder/window-focus import."""
    global _PYWINAUTO_PREPARED
    if _PYWINAUTO_PREPARED:
        return
    if sys.platform != "win32":
        _PYWINAUTO_PREPARED = True
        return
    if not hasattr(sys, "coinit_flags"):
        sys.coinit_flags = 2  # type: ignore[attr-defined]
    _import_pywinauto_with_warning_filters(importlib.import_module)
    _PYWINAUTO_PREPARED = True


def step_editor_visibility_for_kind(kind: str) -> dict[str, bool]:
    """Return Step-tab field visibility flags for a given step kind."""
    normalized = str(kind or "").strip().lower()
    if normalized == "control":
        return {
            "show_action": False,
            "show_control": True,
            "show_condition": True,
        }
    if normalized == "group":
        return {
            "show_action": False,
            "show_control": False,
            "show_condition": False,
        }
    return {
        "show_action": True,
        "show_control": False,
        "show_condition": False,
    }


def build_help_tooltip_text(summary: str) -> str:
    """Return tooltip text for inline help near the cursor."""
    text = str(summary or "").strip()
    if text:
        return text
    return "No help available for this component."


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
    padding: 4px 10px;
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
    width: 6px;
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

QWidget#HeaderBar {{
    background: {_LOG_BG};
    border-bottom: 1px solid {_BG_LIGHT};
    min-height: 44px;
    max-height: 44px;
}}

QLineEdit#ScenarioNameEdit {{
    background: transparent;
    border: 1px solid transparent;
    font-size: 12pt;
    font-weight: bold;
    color: {_ACCENT_BLUE};
}}

QLineEdit#ScenarioNameEdit:hover {{
    border: 1px solid {_BTN_BG};
}}

QLineEdit#ScenarioNameEdit:focus {{
    background: {_BG_MID};
    border: 1px solid {_ACCENT_BLUE};
}}

QLabel#HeaderHelpLabel {{
    color: {_FG_DIM};
    font-size: 9pt;
    padding-left: 4px;
}}

QTabWidget::pane {{
    border: 1px solid {_BG_LIGHT};
    border-radius: 4px;
    background: {_BG};
}}

QTabBar::tab {{
    background: {_BG_MID};
    color: {_FG_DIM};
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background: {_BG};
    color: {_ACCENT_BLUE};
    border-bottom: 2px solid {_ACCENT_BLUE};
}}

QTabBar::tab:hover:!selected {{
    background: {_BG_LIGHT};
    color: {_FG};
}}

QToolButton {{
    background: {_BTN_BG};
    color: {_FG};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}}

QToolButton:hover {{
    background: {_BTN_HOVER};
}}

QToolButton#AddStepButton {{
    background: #2d3d5a;
    color: {_ACCENT_BLUE};
}}

QToolButton#AddStepButton:hover {{
    background: #3a4d7a;
}}

QMenu {{
    background: {_BG_MID};
    color: {_FG};
    border: 1px solid {_BTN_BG};
    border-radius: 4px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 20px 6px 12px;
    border-radius: 3px;
}}

QMenu::item:selected {{
    background: {_BTN_BG};
}}

QMenu::separator {{
    height: 1px;
    background: {_BTN_BG};
    margin: 4px 8px;
}}

QToolButton#LogToggleButton {{
    background: transparent;
}}

QToolButton#LogToggleButton:hover {{
    background: {_BG_LIGHT};
}}

QWidget#LogHeader {{
    background: {_LOG_BG};
    border-top: 1px solid {_BG_LIGHT};
}}

QLabel#PanelTitle {{
    color: {_ACCENT_BLUE};
    font-size: 10pt;
    font-weight: bold;
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

QPushButton#ApplyButton {{
    background: #2d4a7a;
    color: {_ACCENT_BLUE};
}}

QPushButton#ApplyButton:hover {{
    background: #3a5a9a;
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

QToolButton#FileMenuButton {{
    background: transparent;
}}

QToolButton#FileMenuButton:hover {{
    background: {_BG_LIGHT};
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

        _prepare_pywinauto_for_qt()

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        from .recorder import ScenarioRecorder

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

        self._log_collapsed = False

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
        self._register_help_for_widget_tree(self)

        f1_shortcut = QShortcut(QKeySequence("F1"), self)
        f1_shortcut.activated.connect(self.open_help_guide)

        self.refresh_steps()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_bar = QWidget()
        header_bar.setObjectName("HeaderBar")
        header_bar.setFixedHeight(44)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.setSpacing(8)

        title_label = QLabel("Robot Automation Studio -")
        title_label.setObjectName("PanelTitle")
        header_layout.addWidget(title_label)

        self.name_edit = QLineEdit(self.scenario.name)
        self.name_edit.setObjectName("ScenarioNameEdit")
        self.name_edit.setMinimumWidth(260)
        self.name_edit.setPlaceholderText("Scenario name")
        header_layout.addWidget(self.name_edit)

        header_layout.addStretch()

        self.record_button = QPushButton("\u25cf Record")
        self.record_button.setObjectName("RecordButton")
        self.record_button.clicked.connect(self.start_recording)
        header_layout.addWidget(self.record_button)

        self.record_stop_button = QPushButton("\u25a0 Stop")
        self.record_stop_button.setObjectName("StopButton")
        self.record_stop_button.clicked.connect(self.stop_recording)
        header_layout.addWidget(self.record_stop_button)

        vline1 = QFrame()
        vline1.setFrameShape(QFrame.Shape.VLine)
        vline1.setStyleSheet(f"background: {_BG_LIGHT};")
        header_layout.addWidget(vline1)

        self.run_button = QPushButton("\u25b6 Run Robot")
        self.run_button.setObjectName("RecordButton")
        self.run_button.clicked.connect(self.run_robot_suite)
        header_layout.addWidget(self.run_button)

        self.stop_robot_button = QPushButton("Stop Robot")
        self.stop_robot_button.setObjectName("StopButton")
        self.stop_robot_button.setEnabled(False)
        self.stop_robot_button.clicked.connect(self.stop_robot_suite)
        header_layout.addWidget(self.stop_robot_button)

        self._status_pill = QLabel(format_run_status("idle", SPINNER_FRAMES[0]))
        self._status_pill.setObjectName("StatusPill")
        self._status_pill.setToolTip("Run status")
        header_layout.addWidget(self._status_pill)

        vline2 = QFrame()
        vline2.setFrameShape(QFrame.Shape.VLine)
        vline2.setStyleSheet(f"background: {_BG_LIGHT};")
        header_layout.addWidget(vline2)

        self.help_status_label = QLabel(
            "Hover controls for cursor-near tips. Press F1 for full guide."
        )
        self.help_status_label.setObjectName("HeaderHelpLabel")
        header_layout.addWidget(self.help_status_label, 1)

        self._rec_indicator = QLabel(" IDLE ")
        self._rec_indicator.setObjectName("RecIndicator")
        self._rec_indicator.setToolTip("Recording status")
        header_layout.addWidget(self._rec_indicator)

        self.file_menu_button = QToolButton()
        self.file_menu_button.setObjectName("FileMenuButton")
        self.file_menu_button.setText("File \u25be")
        self.file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_menu = QMenu(self.file_menu_button)
        file_menu.addAction("\U0001f4be Save", self.save_json)
        file_menu.addAction("\U0001f4c2 Load", self.load_json)
        file_menu.addSeparator()
        file_menu.addAction("{} Full JSON", self.open_full_json_editor)
        file_menu.addAction("Help Guide (F1)", self.open_help_guide)
        self.file_menu_button.setMenu(file_menu)
        header_layout.addWidget(self.file_menu_button)

        main_layout.addWidget(header_bar)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setObjectName("MainSplitter")

        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_panel.setMinimumWidth(200)
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(8, 8, 8, 8)
        left_panel_layout.setSpacing(6)

        steps_label = QLabel("Steps")
        steps_label.setObjectName("PanelTitle")
        left_panel_layout.addWidget(steps_label)

        step_toolbar = QHBoxLayout()

        self.add_step_button = QToolButton()
        self.add_step_button.setObjectName("AddStepButton")
        self.add_step_button.setText("+ Add \u25be")
        self.add_step_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        add_step_menu = QMenu(self.add_step_button)
        add_step_menu.addAction("\U0001f5b1 Click", self.add_click)
        add_step_menu.addAction("\u2194 Drag", self.add_drag)
        add_step_menu.addAction("\u2328 Shortcut", self.add_shortcut)
        add_step_menu.addAction("\u2261 Menu", self.add_menu)
        add_step_menu.addAction("\u270e Type", self.add_type)
        add_step_menu.addSeparator()
        add_step_menu.addAction("IF", self.add_control)
        add_step_menu.addAction("[] Group", self.add_group)
        self.add_step_button.setMenu(add_step_menu)
        step_toolbar.addWidget(self.add_step_button)

        self.delete_step_button = QPushButton("\u2715")
        self.delete_step_button.setObjectName("DeleteStepButton")
        self.delete_step_button.setToolTip("Delete step")
        self.delete_step_button.clicked.connect(self.delete_selected)
        step_toolbar.addWidget(self.delete_step_button)

        self.move_up_button = QPushButton("\u25b2")
        self.move_up_button.setObjectName("MoveStepUpButton")
        self.move_up_button.setToolTip("Move step up")
        self.move_up_button.clicked.connect(self.move_up)
        step_toolbar.addWidget(self.move_up_button)

        self.move_down_button = QPushButton("\u25bc")
        self.move_down_button.setObjectName("MoveStepDownButton")
        self.move_down_button.setToolTip("Move step down")
        self.move_down_button.clicked.connect(self.move_down)
        step_toolbar.addWidget(self.move_down_button)

        self.duplicate_step_button = QPushButton("\u2398")
        self.duplicate_step_button.setObjectName("DuplicateStepButton")
        self.duplicate_step_button.setToolTip("Duplicate step")
        self.duplicate_step_button.clicked.connect(self.duplicate_selected)
        step_toolbar.addWidget(self.duplicate_step_button)
        step_toolbar.addStretch()

        left_panel_layout.addLayout(step_toolbar)

        self.step_list = QListWidget()
        self.step_list.setObjectName("StepList")
        self.step_list.setToolTip("Steps list")
        self.step_list.setFont(QFont("Consolas", 11))
        self.step_list.currentRowChanged.connect(self.on_select_step)
        left_panel_layout.addWidget(self.step_list)

        horizontal_splitter.addWidget(left_panel)

        right_tabs = QTabWidget()

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
        self.step_id_edit.setPlaceholderText("step-1")
        self.step_form.addRow("Step ID", self.step_id_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("StepTitleEdit")
        self.title_edit.setPlaceholderText("Step title")
        self.step_form.addRow("Title", self.title_edit)

        self.kind_combo = QComboBox()
        self.kind_combo.setObjectName("StepKindCombo")
        self.kind_combo.setToolTip("Kind")
        self.kind_combo.addItems(["action", "control", "group"])
        self.kind_combo.currentTextChanged.connect(self._update_step_kind_fields_visibility)
        self.step_form.addRow("Kind", self.kind_combo)

        self.action_edit = QLineEdit()
        self.action_edit.setObjectName("StepActionEdit")
        self.action_edit.setPlaceholderText("click / drag_drop / type_text ...")
        self.action_label = QLabel("Action")
        self.step_form.addRow(self.action_label, self.action_edit)

        self.control_edit = QLineEdit()
        self.control_edit.setObjectName("StepControlEdit")
        self.control_edit.setPlaceholderText("if / for_each / while ...")
        self.control_label = QLabel("Control")
        self.step_form.addRow(self.control_label, self.control_edit)

        self.step_description_edit = QLineEdit()
        self.step_description_edit.setObjectName("StepDescriptionEdit")
        self.step_description_edit.setPlaceholderText("Optional description")
        self.step_form.addRow("Description", self.step_description_edit)

        self.step_condition_edit = QLineEdit()
        self.step_condition_edit.setObjectName("StepConditionEdit")
        self.step_condition_edit.setPlaceholderText("Optional condition expression")
        self.condition_label = QLabel("Condition")
        self.step_form.addRow(self.condition_label, self.step_condition_edit)

        checks_layout = QHBoxLayout()
        self.step_disabled_check = QCheckBox("Disabled")
        self.step_disabled_check.setObjectName("StepDisabledCheck")
        checks_layout.addWidget(self.step_disabled_check)
        self.step_continue_on_error_check = QCheckBox("Continue On Error")
        self.step_continue_on_error_check.setObjectName("StepContinueOnErrorCheck")
        checks_layout.addWidget(self.step_continue_on_error_check)
        checks_layout.addStretch()
        self.step_form.addRow(checks_layout)

        self.annotations_text = QPlainTextEdit()
        self.annotations_text.setObjectName("StepAnnotationsText")
        self.annotations_text.setFont(QFont("Consolas", 9))
        self.annotations_text.setMaximumHeight(80)
        self.step_form.addRow("Annotations", self.annotations_text)

        self.params_text = QPlainTextEdit()
        self.params_text.setObjectName("StepParamsText")
        self.params_text.setFont(QFont("Consolas", 10))
        self.params_text.setMaximumHeight(160)
        self.step_form.addRow("Params", self.params_text)

        step_scroll_layout.addLayout(self.step_form)

        self.apply_step_button = QPushButton("Apply Step Changes")
        self.apply_step_button.setObjectName("ApplyButton")
        self.apply_step_button.clicked.connect(self.apply_step_changes)
        step_scroll_layout.addWidget(self.apply_step_button)

        step_scroll_layout.addStretch()

        step_scroll.setWidget(step_scroll_widget)
        step_tab_layout = QVBoxLayout(step_tab)
        step_tab_layout.setContentsMargins(0, 0, 0, 0)
        step_tab_layout.addWidget(step_scroll)

        right_tabs.addTab(step_tab, "Step")

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
        self.scenario_id_edit.setPlaceholderText("scenario-id")
        scenario_form.addRow("Scenario ID", self.scenario_id_edit)

        self.target_combo = QComboBox()
        self.target_combo.setObjectName("TargetCombo")
        self.target_combo.setToolTip("Target")
        self.target_combo.addItems(["unity", "web", "desktop", "hybrid"])
        self.target_combo.setCurrentText(self.scenario.target)
        scenario_form.addRow("Target", self.target_combo)

        self.window_hint_edit = QLineEdit(self.scenario.target_window_hint)
        self.window_hint_edit.setObjectName("WindowHintEdit")
        self.window_hint_edit.setPlaceholderText("Unity")
        scenario_form.addRow("Window Hint", self.window_hint_edit)

        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.setObjectName("ExecutionModeCombo")
        self.execution_mode_combo.setToolTip("Execution Mode")
        self.execution_mode_combo.addItems(["attach", "launch"])
        execution_mode = normalize_unity_execution_mode(
            self.scenario.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach")
        )
        self.execution_mode_combo.setCurrentText(execution_mode)
        self.execution_mode_combo.currentTextChanged.connect(self.on_execution_mode_changed)
        scenario_form.addRow("Execution Mode", self.execution_mode_combo)

        project_path_row = QHBoxLayout()
        self.project_path_edit = QLineEdit(
            str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, ""))
        )
        self.project_path_edit.setObjectName("ProjectPathEdit")
        self.project_path_edit.setPlaceholderText("Path to Unity project root")
        project_path_row.addWidget(self.project_path_edit, 1)
        self.project_path_browse_button = QPushButton("Browse")
        self.project_path_browse_button.setObjectName("ProjectPathBrowseButton")
        self.project_path_browse_button.clicked.connect(self.browse_unity_project_path)
        project_path_row.addWidget(self.project_path_browse_button)
        scenario_form.addRow("Unity Project Path", project_path_row)

        self.description_edit = QLineEdit(self.scenario.description)
        self.description_edit.setObjectName("ScenarioDescriptionEdit")
        self.description_edit.setPlaceholderText("Optional scenario description")
        scenario_form.addRow("Description", self.description_edit)

        scenario_tools_layout = QHBoxLayout()
        variables_button = QPushButton("Variables")
        variables_button.setObjectName("VariablesButton")
        variables_button.clicked.connect(self.open_variables_editor)
        scenario_tools_layout.addWidget(variables_button)
        profiles_button = QPushButton("Profiles")
        profiles_button.setObjectName("ProfilesButton")
        profiles_button.clicked.connect(self.open_profiles_editor)
        scenario_tools_layout.addWidget(profiles_button)
        execution_outputs_button = QPushButton("Execution/Outputs")
        execution_outputs_button.setObjectName("ExecutionOutputsButton")
        execution_outputs_button.clicked.connect(self.open_execution_outputs_editor)
        scenario_tools_layout.addWidget(execution_outputs_button)
        scenario_tools_layout.addStretch()
        scenario_form.addRow(scenario_tools_layout)

        scenario_scroll.setWidget(scenario_scroll_widget)
        scenario_tab_layout = QVBoxLayout(scenario_tab)
        scenario_tab_layout.setContentsMargins(0, 0, 0, 0)
        scenario_tab_layout.addWidget(scenario_scroll)

        right_tabs.addTab(scenario_tab, "Scenario")

        export_tab = QWidget()
        export_scroll = QScrollArea()
        export_scroll.setWidgetResizable(True)
        export_scroll.setFrameShape(QFrame.Shape.NoFrame)
        export_scroll_widget = QWidget()
        export_form = QFormLayout(export_scroll_widget)
        export_form.setSpacing(8)
        export_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.output_dir_edit = QLineEdit("artifacts/studio")
        self.output_dir_edit.setObjectName("OutputDirEdit")
        self.output_dir_edit.setPlaceholderText("Output directory")
        export_form.addRow("Output Dir", self.output_dir_edit)

        export_name_row = QHBoxLayout()
        self.export_name_edit = QLineEdit("unity-editor-generated")
        self.export_name_edit.setObjectName("ExportNameEdit")
        self.export_name_edit.setPlaceholderText("Export name")
        export_name_row.addWidget(self.export_name_edit, 1)
        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("ExportButton")
        self.export_button.clicked.connect(self.export_scenario)
        export_name_row.addWidget(self.export_button)
        export_form.addRow("Export Name", export_name_row)

        export_scroll.setWidget(export_scroll_widget)
        export_tab_layout = QVBoxLayout(export_tab)
        export_tab_layout.setContentsMargins(0, 0, 0, 0)
        export_tab_layout.addWidget(export_scroll)

        right_tabs.addTab(export_tab, "Export")

        horizontal_splitter.addWidget(right_tabs)

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

        log_label = QLabel("Output Log")
        log_label.setObjectName("PanelTitle")
        log_header_layout.addWidget(log_label)

        log_header_layout.addStretch()

        self._log_toggle_button = QToolButton()
        self._log_toggle_button.setObjectName("LogToggleButton")
        self._log_toggle_button.setToolTip("Collapse or expand Output Log.")
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

        self.on_execution_mode_changed()
        self._update_step_kind_fields_visibility()

    def _toggle_log_collapse(self) -> None:
        self._log_collapsed = not self._log_collapsed
        if self._log_collapsed:
            self.log_text_container.hide()
            self._log_toggle_button.setText("\u25b2")
        else:
            self.log_text_container.show()
            self._log_toggle_button.setText("\u25bc")

    def _set_step_row_visible(self, label: QLabel, field: QWidget, visible: bool) -> None:
        label.setVisible(visible)
        field.setVisible(visible)

    @Slot()
    def _update_step_kind_fields_visibility(self) -> None:
        visibility = step_editor_visibility_for_kind(self.kind_combo.currentText())
        self._set_step_row_visible(self.action_label, self.action_edit, visibility["show_action"])
        self._set_step_row_visible(
            self.control_label,
            self.control_edit,
            visibility["show_control"],
        )
        self._set_step_row_visible(
            self.condition_label,
            self.step_condition_edit,
            visibility["show_condition"],
        )

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
            self.run_button.setEnabled(False)
            self.stop_robot_button.setEnabled(True)
            if stopping:
                self._set_run_phase("stopping")
            elif self._run_phase == "idle":
                self._set_run_phase("running")
            return
        self.run_button.setEnabled(True)
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
            self._update_step_kind_fields_visibility()
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
        self._update_step_kind_fields_visibility()

    def on_execution_mode_changed(self) -> None:
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        self.execution_mode_combo.setCurrentText(execution_mode)
        self.project_path_edit.setEnabled(True)
        self.project_path_browse_button.setEnabled(True)

    def _ensure_unity_bridge_dependency_if_configured(self, purpose: str) -> bool:
        from .upm import (
            ensure_unity_bridge_upm_dependency,
            has_unity_bridge_package_script_meta,
            install_legacy_unity_bridge_script,
        )

        project_path_raw = self.project_path_edit.text().strip()
        execution_mode = normalize_unity_execution_mode(self.execution_mode_combo.currentText())
        package_script_meta_detected = False

        if project_path_raw == "" and execution_mode == "attach":
            from .unity_project import resolve_attached_unity_project_path

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
                    from .window_focus import focus_visible_window_with_hint

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
                    from .window_focus import trigger_assets_refresh_shortcut_with_hint

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
                                from .window_focus import focus_visible_window_with_hint

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
        from .recorder import has_visible_window_with_hint

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
        from .recorder import events_to_steps

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

    def _widget_text(self, widget: QWidget) -> str:
        if isinstance(widget, QPushButton):
            text = widget.text().strip()
            if text and any(char.isalnum() for char in text):
                return text
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            return text
        if isinstance(widget, QToolButton):
            text = widget.text().strip()
            if text:
                return text
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            return widget.objectName()
        if isinstance(widget, QLabel):
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            return widget.text()
        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText().strip()
            if placeholder:
                return placeholder
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            text = widget.text().strip()
            if text:
                return text
            return widget.objectName()
        if isinstance(widget, QComboBox):
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            text = widget.currentText().strip()
            if text:
                return text
            return widget.objectName()
        if isinstance(widget, QCheckBox):
            return widget.text()
        if isinstance(widget, QListWidget):
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            return widget.objectName()
        if isinstance(widget, QPlainTextEdit):
            tooltip = widget.toolTip().strip()
            if tooltip:
                return tooltip
            return widget.objectName()
        return ""

    def _should_skip_help_widget(self, widget: QWidget) -> bool:
        if widget is self:
            return True
        object_name = widget.objectName()
        if object_name.startswith("qt_"):
            return True
        return type(widget).__name__ in {
            "QFrame",
            "QListView",
            "QMenu",
            "QScrollArea",
            "QScrollBar",
            "QSplitter",
            "QSplitterHandle",
            "QStackedWidget",
            "QTabBar",
            "QWidget",
        }

    def _register_help_for_widget(self, widget: QWidget) -> None:
        if widget in self._help_entries_by_widget:
            return
        if self._should_skip_help_widget(widget):
            return
        widget_id = widget.objectName() or str(id(widget))
        widget_class = type(widget).__name__
        widget_text = self._widget_text(widget)
        entry = build_help_entry(
            widget_id=widget_id,
            widget_class=widget_class,
            widget_text=widget_text,
        )
        self._help_entries_by_widget[widget] = entry
        self._help_entries_by_id[entry.widget_id] = entry
        widget.setToolTip(build_help_tooltip_text(entry.summary))
        widget.installEventFilter(self)

    def _register_help_for_widget_tree(self, root: QWidget) -> None:
        for child in root.findChildren(QWidget):
            self._register_help_for_widget(child)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if isinstance(obj, QWidget) and event.type() == QEvent.Type.Enter:
            entry = self._help_entries_by_widget.get(obj)
            if entry is None:
                return False
            if isinstance(event, QEnterEvent):
                QToolTip.showText(event.globalPosition().toPoint(), obj.toolTip(), obj)
                return False
            QToolTip.showText(obj.mapToGlobal(obj.rect().center()), obj.toolTip(), obj)
            return False
        if isinstance(obj, QWidget) and event.type() == QEvent.Type.ToolTip:
            entry = self._help_entries_by_widget.get(obj)
            if entry is None:
                return False
            if isinstance(event, QHelpEvent):
                QToolTip.showText(event.globalPos(), obj.toolTip(), obj)
                return True
            return False
        if isinstance(obj, QWidget) and event.type() == QEvent.Type.FocusIn:
            entry = self._help_entries_by_widget.get(obj)
            if entry is not None:
                QToolTip.showText(obj.mapToGlobal(obj.rect().center()), obj.toolTip(), obj)
        if isinstance(obj, QWidget) and event.type() == QEvent.Type.Leave:
            QToolTip.hideText()
        return False

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

        self._register_help_for_widget_tree(dialog)
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

        self._register_help_for_widget_tree(dialog)
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

        self._register_help_for_widget_tree(dialog)
        dialog.exec()

    def open_execution_outputs_editor(self) -> None:
        self._sync_scenario_header()
        dialog = QDialog(self)
        dialog.setWindowTitle("Execution / Outputs Editor")
        dialog.resize(980, 720)

        layout = QVBoxLayout(dialog)

        top_layout = QHBoxLayout()
        header_label = QLabel("Execution / Outputs JSON")
        header_label.setObjectName("PanelTitle")
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

        self._register_help_for_widget_tree(dialog)
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
