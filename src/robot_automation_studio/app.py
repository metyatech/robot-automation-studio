"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import threading
import warnings
from contextlib import suppress
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import app_dialogs, app_help, app_ui
from .bridge_readiness import build_recording_readiness_timeouts
from .editor import ScenarioEditor
from .exporter import export_all, validate_step_exportability
from .hotkey import (
    DEFAULT_STOP_HOTKEY_LABEL,
    FALLBACK_STOP_HOTKEY_LABELS,
    HotkeySpec,
    parse_hotkey_label,
)
from .i18n import (
    DEFAULT_LOCALE,
    LOCALE_ENV_VAR,
    SUPPORTED_LOCALES,
    Translator,
    detect_default_locale,
    translate,
)
from .models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    normalize_unity_execution_mode,
)
from .overlay import AutomationRunOverlay, OverlayMode
from .preflight_validation import ValidationReport, validate_scenario
from .run_diagnostics import (
    RunDiagnostics,
    capture_failure_screenshot,
    parse_robot_output,
    summarize_run_diagnostics_payload,
    write_run_diagnostics_file,
)
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .settings_store import (
    StudioUiSettings,
    load_ui_settings,
    resolve_settings_path,
    save_ui_settings,
)
from .status import SPINNER_FRAMES, format_run_status, next_spinner_index
from .ui_help import HelpEntry
from .unity_bridge import UnityBridgeClient
from .unity_diagnostics import get_recent_unity_compile_errors

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QCheckBox,
        QFormLayout,
        QLineEdit,
        QListWidget,
        QPlainTextEdit,
        QTabWidget,
        QToolButton,
    )

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


def build_help_tooltip_text(summary: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Return tooltip text for inline help near the cursor."""
    text = str(summary or "").strip()
    if text:
        return text
    return translate("app.help.tooltip.fallback", locale=locale)


def _normalize_step_action_for_template(action: str) -> str:
    normalized = str(action or "").strip().lower()
    aliases = {
        "drag": "drag_drop",
        "type": "type_text",
        "shortcut": "press_keys",
        "keys": "press_keys",
        "menu": "open_menu",
        "wait": "wait_for",
    }
    return aliases.get(normalized, normalized)


def default_params_template_for_action(action: str) -> dict[str, object] | None:
    normalized = _normalize_step_action_for_template(action)
    templates: dict[str, dict[str, object]] = {
        "click": {
            "target": {
                "strategy": "uia",
                "uia": {
                    "title": "Inspector",
                    "automation_id": "Inspector",
                    "class_name": "Pane",
                    "control_type": "Pane",
                },
            },
            "timing": {"stability_ms": 0},
        },
        "drag_drop": {
            "target": {
                "strategy": "coordinate",
                "coordinate": {"x_ratio": 0.6, "y_ratio": 0.5},
            },
            "input": {
                "source": {
                    "strategy": "coordinate",
                    "coordinate": {"x_ratio": 0.4, "y_ratio": 0.5},
                }
            },
            "timing": {"stability_ms": 0},
        },
        "press_keys": {"input": {"shortcut": "CTRL+S"}},
        "open_menu": {"input": {"menu_path": "File>Save"}},
        "type_text": {"input": {"text": "sample"}},
        "wait_for": {"input": {"seconds": 1.0}},
        "screenshot": {"input": {"path": "screenshots/step.png"}},
        "select_hierarchy": {
            "target": {
                "strategy": "unity_hierarchy",
                "unity_hierarchy": {"path": "Root/Object", "match_mode": "exact"},
            }
        },
        "assert": {"expect": {"condition": "True", "message": "Assertion failed"}},
        "open_url": {"input": {"url": "https://example.com"}},
        "double_click": {
            "target": {
                "strategy": "uia",
                "uia": {
                    "title": "Inspector",
                    "automation_id": "Inspector",
                    "class_name": "Pane",
                    "control_type": "Pane",
                },
            }
        },
        "right_click": {
            "target": {
                "strategy": "uia",
                "uia": {
                    "title": "Inspector",
                    "automation_id": "Inspector",
                    "class_name": "Pane",
                    "control_type": "Pane",
                },
            }
        },
        "start_video": {"input": {"path": "videos/run.mp4"}},
        "stop_video": {},
        "emit_annotation": {"input": {"annotation": {"type": "click", "label": "Click"}}},
        "run_subflow": {"input": {"path": "flows/subflow.scenario.json"}},
    }
    template = templates.get(normalized)
    if template is None:
        return None
    return deepcopy(template)


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
    if TYPE_CHECKING:
        title_label: QLabel
        name_edit: QLineEdit
        record_button: QPushButton
        record_stop_button: QPushButton
        run_button: QPushButton
        stop_robot_button: QPushButton
        _status_pill: QLabel
        help_status_label: QLabel
        _rec_indicator: QLabel
        file_menu_button: QToolButton
        file_save_action: QAction
        file_load_action: QAction
        file_json_action: QAction
        file_help_action: QAction
        file_run_diagnostics_action: QAction
        hotkey_button: QPushButton
        language_combo: QComboBox
        steps_label: QLabel
        add_step_button: QToolButton
        delete_step_button: QPushButton
        move_up_button: QPushButton
        move_down_button: QPushButton
        duplicate_step_button: QPushButton
        step_list: QListWidget
        main_tabs: QTabWidget
        step_form: QFormLayout
        step_id_edit: QLineEdit
        step_id_label: QLabel
        title_edit: QLineEdit
        step_title_label: QLabel
        kind_combo: QComboBox
        step_kind_label: QLabel
        action_edit: QLineEdit
        action_label: QLabel
        control_edit: QLineEdit
        control_label: QLabel
        step_description_edit: QLineEdit
        step_description_label: QLabel
        step_condition_edit: QLineEdit
        condition_label: QLabel
        step_disabled_check: QCheckBox
        step_continue_on_error_check: QCheckBox
        annotations_text: QPlainTextEdit
        annotations_label: QLabel
        params_text: QPlainTextEdit
        params_label: QLabel
        params_template_button: QPushButton
        apply_step_button: QPushButton
        step_tab_index: int
        scenario_id_edit: QLineEdit
        scenario_id_label: QLabel
        target_combo: QComboBox
        target_label: QLabel
        window_hint_edit: QLineEdit
        window_hint_label: QLabel
        execution_mode_combo: QComboBox
        execution_mode_label: QLabel
        active_profile_combo: QComboBox
        active_profile_label: QLabel
        project_path_edit: QLineEdit
        project_path_browse_button: QPushButton
        unity_project_path_label: QLabel
        description_edit: QLineEdit
        description_label: QLabel
        variables_button: QPushButton
        profiles_button: QPushButton
        execution_outputs_button: QPushButton
        validate_button: QPushButton
        profile_diff_button: QPushButton
        scenario_tab_index: int
        output_dir_edit: QLineEdit
        output_dir_label: QLabel
        export_name_edit: QLineEdit
        export_button: QPushButton
        export_name_label: QLabel
        export_tab_index: int
        log_label: QLabel
        _log_toggle_button: QToolButton
        log_text_container: QWidget
        log_text: QPlainTextEdit

    _log_signal = Signal(str)
    _phase_signal = Signal(str)
    _run_finished_signal = Signal(object, object)
    _automation_stop_requested = Signal(str)

    def __init__(self, initial_locale: str | None = None) -> None:
        super().__init__()
        self._settings_path = resolve_settings_path()
        self._settings_load_error: Exception | None = None
        try:
            self._ui_settings = load_ui_settings(self._settings_path)
        except Exception as error:
            self._ui_settings = StudioUiSettings()
            self._settings_load_error = error

        if initial_locale is not None:
            locale_hint: str | None = initial_locale
        elif os.getenv(LOCALE_ENV_VAR):
            locale_hint = None
        else:
            locale_hint = self._ui_settings.locale
        self._translator = Translator(detect_default_locale(locale_hint))
        self.setWindowTitle(self._t("app.window.title"))
        self.resize(1200, 760)
        self.setMinimumSize(960, 640)

        _prepare_pywinauto_for_qt()

        self._stop_hotkey_spec = self._parse_hotkey_or_default(self._ui_settings.stop_hotkey_label)

        self.scenario = Scenario(name=self._t("app.scenario.default_name"))
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        from .recorder import ScenarioRecorder

        self.recorder = ScenarioRecorder(
            on_record_error=self._on_record_error,
            on_stop_hotkey=self._on_recorder_stop_hotkey,
            stop_hotkey_main_key=self._stop_hotkey_spec.main_key,
            stop_hotkey_required_modifiers=set(self._stop_hotkey_spec.required_modifiers),
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
        self._last_run_output_xml_path: Path | None = None
        self._last_run_diagnostics_path: Path | None = None
        self._last_run_diagnostics: RunDiagnostics | None = None
        self._last_run_failure_screenshot_path: Path | None = None

        self._help_entries_by_widget: dict[QWidget, HelpEntry] = {}
        self._help_entries_by_id: dict[str, HelpEntry] = {}
        self._help_dialog: QDialog | None = None
        self._combo_tooltip_viewports: dict[QObject, QComboBox] = {}

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
        self._automation_stop_requested.connect(self._on_automation_stop_requested)

        self._build_ui()
        self._apply_localized_texts()
        self._apply_loaded_ui_settings()
        self._rebuild_help_entries()

        f1_shortcut = QShortcut(QKeySequence("F1"), self)
        f1_shortcut.activated.connect(self.open_help_guide)

        self.refresh_steps()
        if self._settings_load_error is not None:
            self.log(self._t("app.log.settings_load_failed", error=self._settings_load_error))

    def _t(self, key: str, **kwargs: object) -> str:
        return self._translator.t(key, **kwargs)

    def _combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData(Qt.ItemDataRole.UserRole)
        if data is None:
            return combo.currentText().strip()
        return str(data).strip()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        target = str(value or "").strip()
        index = combo.findData(target, Qt.ItemDataRole.UserRole)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_action_help(self, action: QAction, summary_key: str, detail_key: str) -> None:
        summary = self._t(summary_key)
        detail = self._t(detail_key)
        action.setToolTip(summary)
        action.setStatusTip(summary)
        action.setWhatsThis(detail)

    @staticmethod
    def _parse_hotkey_or_default(label: str) -> HotkeySpec:
        try:
            return parse_hotkey_label(label)
        except Exception:
            return parse_hotkey_label(DEFAULT_STOP_HOTKEY_LABEL)

    def _probe_hotkey_registration(self, spec: HotkeySpec) -> tuple[bool, str]:
        listener: pynput_keyboard.GlobalHotKeys | None = None
        try:
            listener = self._create_global_hotkey_listener(spec.bind, lambda: None)
            listener.start()
            return (True, "")
        except Exception as error:
            return (False, str(error))
        finally:
            if listener is not None:
                with suppress(Exception):
                    listener.stop()

    def _collect_available_hotkey_candidates(
        self,
        *,
        exclude_labels: set[str] | None = None,
    ) -> list[HotkeySpec]:
        excluded = {str(value or "").strip().lower() for value in (exclude_labels or set())}
        candidates: list[HotkeySpec] = []
        for label in FALLBACK_STOP_HOTKEY_LABELS:
            try:
                spec = parse_hotkey_label(label)
            except Exception:
                continue
            normalized = spec.label.strip().lower()
            if normalized in excluded:
                continue
            if any(existing.label == spec.label for existing in candidates):
                continue
            ok, _error_text = self._probe_hotkey_registration(spec)
            if ok:
                candidates.append(spec)
        return candidates

    def _choose_hotkey_candidate_dialog(
        self,
        *,
        requested_hotkey: str,
        conflict_error: str,
        candidates: list[HotkeySpec],
    ) -> HotkeySpec | None:
        if not candidates:
            return None
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("app.dialog.hotkey_conflict.title"))
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)

        detail = QLabel(
            self._t(
                "app.dialog.hotkey_conflict.message",
                hotkey=requested_hotkey,
                error=conflict_error or "unknown",
            )
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)

        candidate_label = QLabel(self._t("app.dialog.hotkey_candidate.label"))
        layout.addWidget(candidate_label)

        candidate_combo = QComboBox()
        for spec in candidates:
            candidate_combo.addItem(spec.label, spec)
        layout.addWidget(candidate_combo)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_button = QPushButton(self._t("app.button.cancel"))
        cancel_button.clicked.connect(dialog.reject)
        actions.addWidget(cancel_button)
        use_button = QPushButton(self._t("app.dialog.hotkey_candidate.apply"))
        use_button.setObjectName("ApplyButton")
        use_button.clicked.connect(dialog.accept)
        actions.addWidget(use_button)
        layout.addLayout(actions)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        current_data = candidate_combo.currentData(Qt.ItemDataRole.UserRole)
        if isinstance(current_data, HotkeySpec):
            return current_data
        if candidates:
            return candidates[0]
        return None

    def _set_stop_hotkey_spec(self, spec: HotkeySpec, *, persist: bool = False) -> None:
        self._stop_hotkey_spec = spec
        self.recorder.set_stop_hotkey(spec.main_key, set(spec.required_modifiers))
        if hasattr(self, "hotkey_button"):
            self.hotkey_button.setText(self._t("app.button.hotkey_with_value", hotkey=spec.label))
            self.hotkey_button.setToolTip(self._t("app.tooltip.stop_hotkey"))
        if self._overlay is not None:
            self._overlay.set_stop_hotkey_label(spec.label)
            self._overlay.set_progress_text(self._status_pill.text())
        if persist:
            self._persist_ui_settings()

    def _apply_loaded_ui_settings(self) -> None:
        settings = self._ui_settings
        self.window_hint_edit.setText(settings.window_hint)
        self.project_path_edit.setText(settings.unity_project_path)
        self._set_combo_value(self.target_combo, settings.target)
        self._set_combo_value(self.execution_mode_combo, settings.execution_mode)
        self.on_execution_mode_changed()
        self._set_stop_hotkey_spec(self._parse_hotkey_or_default(settings.stop_hotkey_label))

    def _collect_ui_settings(self) -> StudioUiSettings:
        return StudioUiSettings(
            locale=self._translator.locale,
            target=self._combo_value(self.target_combo).strip() or "unity",
            window_hint=self.window_hint_edit.text().strip()
            or self._t("app.field.window_hint.placeholder"),
            execution_mode=normalize_unity_execution_mode(
                self._combo_value(self.execution_mode_combo)
            ),
            unity_project_path=self.project_path_edit.text().strip(),
            stop_hotkey_label=self._stop_hotkey_spec.label,
        )

    def _persist_ui_settings(self) -> None:
        try:
            saved_path = save_ui_settings(self._collect_ui_settings(), self._settings_path)
            self.log(self._t("app.log.settings_saved", path=saved_path))
        except Exception as error:
            self.log(self._t("app.log.settings_save_failed", error=error))

    def _stop_source_label(self, source: str) -> str:
        key = f"app.stop_source.{str(source or '').strip().lower()}"
        localized = self._t(key)
        return localized if localized != key else source

    def _rebuild_help_entries(self) -> None:
        self._help_entries_by_widget.clear()
        self._help_entries_by_id.clear()
        self._register_help_for_widget_tree(self)

    @Slot()
    def _on_locale_changed(self) -> None:
        if not hasattr(self, "language_combo"):
            return
        locale_code = str(
            self.language_combo.currentData(Qt.ItemDataRole.UserRole) or DEFAULT_LOCALE
        ).strip()
        if locale_code not in SUPPORTED_LOCALES:
            locale_code = DEFAULT_LOCALE
        if locale_code == self._translator.locale:
            return
        self._translator.set_locale(locale_code)
        self._apply_localized_texts()
        self._rebuild_help_entries()
        if self._overlay is not None:
            self._overlay.set_locale(self._translator.locale)
            self._overlay.set_progress_text(self._status_pill.text())
        if self._help_dialog is not None:
            self._close_help_dialog()
        self._persist_ui_settings()

    def _build_ui(self) -> None:
        app_ui.build_ui(self, bg_light=_BG_LIGHT)

    def _apply_localized_texts(self) -> None:
        app_ui.apply_localized_texts(self)

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

    def _configure_combo_option_help(
        self,
        combo: QComboBox,
        option_help: dict[str, str],
    ) -> None:
        view = combo.view()
        viewport = view.viewport()
        if viewport not in self._combo_tooltip_viewports:
            viewport.installEventFilter(self)
        self._combo_tooltip_viewports[viewport] = combo
        view.setMouseTracking(True)
        viewport.setMouseTracking(True)

        for row in range(combo.count()):
            option_key = str(combo.itemData(row, Qt.ItemDataRole.UserRole) or "").strip()
            option_text = combo.itemText(row).strip()
            summary = option_help.get(
                option_key, self._t("app.option.help.fallback", option=option_text)
            )
            combo.setItemData(row, summary, Qt.ItemDataRole.ToolTipRole)
            combo.setItemData(row, summary, Qt.ItemDataRole.StatusTipRole)
            combo.setItemData(row, summary, Qt.ItemDataRole.WhatsThisRole)

    def _active_profile_value(self) -> str:
        if not hasattr(self, "active_profile_combo"):
            return ""
        return self._combo_value(self.active_profile_combo).strip()

    def _refresh_active_profile_combo(self) -> None:
        if not hasattr(self, "active_profile_combo"):
            return
        current_value = self._active_profile_value()
        execution = dict(self.scenario.execution or {})
        if current_value == "":
            current_value = str(execution.get("active_profile") or "").strip()
        profiles = dict(self.scenario.profiles or {})
        profile_names = sorted(
            {str(name or "").strip() for name in profiles if str(name or "").strip() != ""}
        )

        self.active_profile_combo.blockSignals(True)
        self.active_profile_combo.clear()
        self.active_profile_combo.addItem(self._t("app.option.profile.none"), "")
        for name in profile_names:
            self.active_profile_combo.addItem(name, name)
        self.active_profile_combo.blockSignals(False)

        self._set_combo_value(self.active_profile_combo, current_value)
        if self._active_profile_value() != current_value:
            self.active_profile_combo.setCurrentIndex(0)

        option_help: dict[str, str] = {"": self._t("app.option.help.profile.none")}
        for name in profile_names:
            profile_payload = profiles.get(name)
            description = ""
            if isinstance(profile_payload, dict):
                description = str(profile_payload.get("description") or "").strip()
            if description:
                option_help[name] = self._t(
                    "app.option.help.profile.item_with_description",
                    profile=name,
                    description=description,
                )
            else:
                option_help[name] = self._t("app.option.help.profile.item", profile=name)
        self._configure_combo_option_help(self.active_profile_combo, option_help)

    @Slot()
    def _update_step_kind_fields_visibility(self) -> None:
        visibility = step_editor_visibility_for_kind(self._combo_value(self.kind_combo))
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
        self.scenario.name = self.name_edit.text().strip() or self._t(
            "app.scenario.default_fallback_name"
        )
        self.scenario.scenario_id = (
            self.scenario_id_edit.text().strip() or self.scenario.scenario_id
        )
        self.scenario.target = self._combo_value(self.target_combo).strip() or "unity"
        self.scenario.description = self.description_edit.text().strip()
        self.scenario.target_window_hint = self.window_hint_edit.text().strip() or self._t(
            "app.field.window_hint.placeholder"
        )
        execution_mode = normalize_unity_execution_mode(
            self._combo_value(self.execution_mode_combo)
        )
        self._set_combo_value(self.execution_mode_combo, execution_mode)
        unity_project_path = self.project_path_edit.text().strip()
        self.scenario.sync_runtime_metadata(
            execution_mode=execution_mode,
            unity_project_path=unity_project_path,
        )
        active_profile = self._active_profile_value()
        self.scenario.execution = dict(self.scenario.execution or {})
        if active_profile:
            self.scenario.execution["active_profile"] = active_profile
        else:
            self.scenario.execution.pop("active_profile", None)

    def _on_record_error(self, message: str) -> None:
        def _report() -> None:
            self.log(self._t("app.log.record_error", message=message))
            self._persist_record_diagnostic(message)

        QTimer.singleShot(0, _report)

    def _diagnostics_output_dir(self) -> Path:
        output_dir_value = "artifacts/studio"
        if hasattr(self, "output_dir_edit"):
            output_dir_value = self.output_dir_edit.text().strip() or output_dir_value
        return Path(output_dir_value).resolve() / "diagnostics"

    def _persist_record_diagnostic(self, message: str) -> None:
        channel = (
            "bridge-recording"
            if "hierarchy path from unity bridge" in str(message or "").strip().lower()
            else "recording"
        )
        target_path = self._diagnostics_output_dir() / f"{channel}.log"
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        line = f"[{timestamp}] {message}\n"
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        except OSError as error:
            self.log(
                self._t(
                    "app.log.diagnostics_persist_failed",
                    path=target_path,
                    error=error,
                )
            )

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
        status_text = format_run_status(self._run_phase, spinner, locale=self._translator.locale)
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

    def _create_global_hotkey_listener(
        self,
        hotkey_bind: str,
        callback,
    ) -> pynput_keyboard.GlobalHotKeys:
        return pynput_keyboard.GlobalHotKeys({hotkey_bind: callback})

    def _start_stop_hotkey(self) -> bool:
        self._stop_stop_hotkey()

        def _on_hotkey() -> None:
            self._automation_stop_requested.emit("global_hotkey")

        candidate_specs: list[HotkeySpec] = [self._stop_hotkey_spec]
        for fallback_label in FALLBACK_STOP_HOTKEY_LABELS:
            fallback_spec = self._parse_hotkey_or_default(fallback_label)
            if all(spec.label != fallback_spec.label for spec in candidate_specs):
                candidate_specs.append(fallback_spec)

        errors: list[str] = []
        for index, spec in enumerate(candidate_specs):
            try:
                listener = self._create_global_hotkey_listener(spec.bind, _on_hotkey)
                listener.start()
            except Exception as error:
                self.log(self._t("app.log.failed_register_hotkey", error=error))
                errors.append(f"{spec.label}: {error}")
                continue

            self._stop_hotkey_listener = listener
            if index == 0:
                self.log(self._t("app.log.hotkey_registered", hotkey=spec.label))
                return True

            previous = self._stop_hotkey_spec.label
            self._set_stop_hotkey_spec(spec, persist=True)
            self.log(self._t("app.log.hotkey_fallback", hotkey=spec.label))
            QMessageBox.warning(
                self,
                self._t("app.warn.hotkey_fallback.title"),
                self._t(
                    "app.warn.hotkey_fallback.message",
                    hotkey=spec.label,
                    error=errors[-1] if errors else "unknown",
                ),
            )
            if previous != spec.label:
                self.log(self._t("app.log.hotkey_updated", hotkey=spec.label))
            return True

        self._stop_hotkey_listener = None
        details = "\n".join(errors) if errors else "unknown"
        QMessageBox.warning(
            self,
            self._t("app.error.hotkey_register_failed.title"),
            self._t(
                "app.error.hotkey_register_failed.message",
                hotkey=self._stop_hotkey_spec.label,
                details=details,
            ),
        )
        return False

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
                window_hint=self.window_hint_edit.text().strip()
                or self._t("app.field.window_hint.placeholder"),
                stop_hotkey_label=self._stop_hotkey_spec.label,
                on_stop_requested=lambda: self._automation_stop_requested.emit("overlay_button"),
                mode=mode,
                locale=self._translator.locale,
            )
            self._overlay_mode = mode
            self._overlay.start()
            self._overlay.set_progress_text(progress_text)
        except Exception as error:
            self._overlay = None
            self._overlay_mode = None
            self.log(self._t("app.log.failed_start_overlay", error=error))

    def _stop_overlay(self) -> None:
        if self._overlay is None:
            return
        self._overlay.stop()
        self._overlay = None
        self._overlay_mode = None

    def _stop_active_automation(self, source: str = "") -> None:
        if self.recorder.is_recording:
            self.stop_recording()
            return
        if self._is_robot_running():
            self.stop_robot_suite(stop_source=source)

    @Slot(str)
    def _on_automation_stop_requested(self, source: str) -> None:
        normalized_source = str(source or "").strip().lower()
        if normalized_source == "":
            normalized_source = "unknown"
        self.log(
            self._t(
                "app.log.stop_requested",
                source=self._stop_source_label(normalized_source),
            )
        )
        self._stop_active_automation(normalized_source)

    def _on_recorder_stop_hotkey(self) -> None:
        self._automation_stop_requested.emit("recorder_hotkey")

    def refresh_steps(self) -> None:
        self.step_list.clear()
        for idx, step in enumerate(self.scenario.steps):
            kind_label = (
                self._t("app.option.kind.action")
                if step.kind == "action"
                else self._t("app.option.kind.control")
                if step.kind == "control"
                else self._t("app.option.kind.group")
                if step.kind == "group"
                else step.kind
            )
            label = (
                step.action
                if step.kind == "action"
                else step.control
                if step.kind == "control"
                else self._t("app.step.label.group")
            )
            self.step_list.addItem(
                self._t(
                    "app.list.item.step",
                    index=idx + 1,
                    kind=kind_label,
                    label=label,
                    title=step.title,
                )
            )

    @Slot(int)
    def on_select_step(self, row: int) -> None:
        if row < 0 or row >= len(self.scenario.steps):
            self.selected_index = None
            self.step_id_edit.clear()
            self.title_edit.clear()
            self._set_combo_value(self.kind_combo, "action")
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
        self._set_combo_value(self.kind_combo, step.kind)
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
        execution_mode = normalize_unity_execution_mode(
            self._combo_value(self.execution_mode_combo)
        )
        self._set_combo_value(self.execution_mode_combo, execution_mode)
        self.project_path_edit.setEnabled(True)
        self.project_path_browse_button.setEnabled(True)

    def _ensure_unity_bridge_dependency_if_configured(self, purpose: str) -> bool:
        from .upm import (
            ensure_unity_bridge_upm_dependency,
            has_unity_bridge_package_script_meta,
            install_legacy_unity_bridge_script,
        )

        project_path_raw = self.project_path_edit.text().strip()
        execution_mode = normalize_unity_execution_mode(
            self._combo_value(self.execution_mode_combo)
        )
        package_script_meta_detected = False

        if project_path_raw == "" and execution_mode == "attach":
            from .unity_project import resolve_attached_unity_project_path

            detected_path = resolve_attached_unity_project_path(
                window_hint=self.window_hint_edit.text().strip()
                or self._t("app.field.window_hint.placeholder")
            )
            if detected_path:
                self.project_path_edit.setText(detected_path)
                project_path_raw = detected_path
                self.log(self._t("app.log.auto_detected_project_path", path=detected_path))

        changed = False
        if project_path_raw != "":
            project_root = Path(project_path_raw)
            package_script_meta_detected = has_unity_bridge_package_script_meta(project_root)
            if package_script_meta_detected:
                self.log(self._t("app.log.bridge_package_meta_detected"))
            else:
                self.log(self._t("app.log.bridge_package_meta_missing"))
            purpose_label = (
                self._t("app.purpose.recording")
                if purpose == "recording"
                else self._t("app.purpose.run")
                if purpose == "run"
                else purpose
            )
            self.log(
                self._t(
                    "app.log.ensure_bridge_package",
                    purpose=purpose_label,
                    path=project_path_raw,
                )
            )
            try:
                changed = ensure_unity_bridge_upm_dependency(
                    project_root,
                    remove_legacy_bridge_script=package_script_meta_detected,
                )
            except Exception as error:
                self.log(self._t("app.log.bridge_setup_failed", error=error))
                QMessageBox.critical(
                    self,
                    self._t("app.error.bridge_setup.title"),
                    self._t(
                        "app.error.bridge_setup_dependency.message",
                        path=project_path_raw,
                        error=error,
                    ),
                )
                return False
            if changed:
                self.log(self._t("app.log.bridge_dependency_updated"))
            else:
                self.log(self._t("app.log.bridge_dependency_present"))
            if not package_script_meta_detected:
                try:
                    fallback_changed = install_legacy_unity_bridge_script(project_root)
                    if fallback_changed:
                        self.log(self._t("app.log.fallback_bridge_installed"))
                    else:
                        self.log(self._t("app.log.fallback_bridge_present"))
                    changed = changed or fallback_changed
                except Exception as error:
                    self.log(self._t("app.log.fallback_install_failed", error=error))
                    QMessageBox.critical(
                        self,
                        self._t("app.error.bridge_setup.title"),
                        self._t(
                            "app.error.bridge_setup_fallback.message",
                            path=project_path_raw,
                            error=error,
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
                        self.window_hint_edit.text().strip()
                        or self._t("app.field.window_hint.placeholder")
                    )
                    if focused:
                        if attempt_number == 1:
                            self.log(self._t("app.log.focused_target_window"))
                        else:
                            self.log(self._t("app.log.refocused_target_window"))
                self.log(
                    self._t(
                        "app.log.check_bridge_readiness",
                        attempt=attempt_number,
                        total=attempt_count,
                    )
                )
                if self.unity_bridge.wait_until_available(
                    timeout_seconds=wait_timeout,
                    request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                ):
                    bridge_ready = True
                    break
            if not bridge_ready:
                self.log(self._t("app.log.bridge_readiness_timeout"))
                if execution_mode == "attach":
                    from .window_focus import trigger_assets_refresh_shortcut_with_hint

                    refreshed = trigger_assets_refresh_shortcut_with_hint(
                        self.window_hint_edit.text().strip()
                        or self._t("app.field.window_hint.placeholder")
                    )
                    if refreshed:
                        self.log(self._t("app.log.triggered_assets_refresh"))
                        if self.unity_bridge.wait_until_available(
                            timeout_seconds=BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS,
                            request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                        ):
                            self.log(self._t("app.log.bridge_ready_after_refresh"))
                            return True
                    else:
                        self.log(self._t("app.log.could_not_trigger_refresh"))
                if project_path_raw != "":
                    project_root = Path(project_path_raw)
                    if not package_script_meta_detected:
                        self.log(self._t("app.log.meta_missing_after_wait"))
                        try:
                            fallback_changed = install_legacy_unity_bridge_script(project_root)
                            if fallback_changed:
                                self.log(self._t("app.log.fallback_bridge_installed"))
                            else:
                                self.log(self._t("app.log.fallback_bridge_exists"))
                            if execution_mode == "attach":
                                from .window_focus import focus_visible_window_with_hint

                                focus_visible_window_with_hint(
                                    self.window_hint_edit.text().strip()
                                    or self._t("app.field.window_hint.placeholder")
                                )
                            self.log(self._t("app.log.waiting_fallback_readiness"))
                            if self.unity_bridge.wait_until_available(
                                timeout_seconds=BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS,
                                request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
                            ):
                                self.log(self._t("app.log.bridge_ready_fallback"))
                                return True
                        except Exception as error:
                            self.log(self._t("app.log.fallback_install_failed", error=error))
                compile_errors = get_recent_unity_compile_errors(limit=3)
                compile_error_hint = ""
                if compile_errors:
                    self.log(self._t("app.log.detected_compile_errors"))
                    for line in compile_errors:
                        self.log(f"  {line}")
                    compile_error_hint = self._t(
                        "app.error.bridge_compile_hint",
                        items="\n- ".join(compile_errors),
                    )
                retry_action = (
                    self._t("app.action.start_recording")
                    if purpose == "recording"
                    else self._t("app.action.run_robot")
                )
                QMessageBox.critical(
                    self,
                    self._t("app.error.bridge_not_ready.title"),
                    self._t(
                        "app.error.bridge_not_ready.message",
                        retry_action=retry_action,
                        compile_error_hint=compile_error_hint,
                    ),
                )
                return False
            self.log(self._t("app.log.bridge_ready"))
        return True

    def browse_unity_project_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._t("app.file_dialog.select_unity_project.title"),
        )
        if not selected:
            return
        self.project_path_edit.setText(selected)

    def open_hotkey_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("app.dialog.hotkey.title"))
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        description = QLabel(self._t("app.dialog.hotkey.label"))
        description.setWordWrap(True)
        layout.addWidget(description)

        hotkey_edit = QKeySequenceEdit()
        hotkey_edit.setObjectName("StopHotkeyEdit")
        hotkey_edit.setKeySequence(QKeySequence(self._stop_hotkey_spec.label))
        hotkey_edit.setMaximumSequenceLength(1)
        layout.addWidget(hotkey_edit)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_button = QPushButton(self._t("app.button.cancel"))
        cancel_button.clicked.connect(dialog.reject)
        actions.addWidget(cancel_button)
        apply_button = QPushButton(self._t("app.dialog.hotkey.apply"))
        apply_button.clicked.connect(dialog.accept)
        actions.addWidget(apply_button)
        layout.addLayout(actions)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        sequence_text = (
            hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
        )
        try:
            spec = parse_hotkey_label(sequence_text)
        except Exception as error:
            QMessageBox.critical(self, self._t("app.error.hotkey_invalid.title"), str(error))
            return
        ok, error_text = self._probe_hotkey_registration(spec)
        if not ok:
            candidates = self._collect_available_hotkey_candidates(exclude_labels={spec.label})
            selected_candidate = self._choose_hotkey_candidate_dialog(
                requested_hotkey=spec.label,
                conflict_error=error_text,
                candidates=candidates,
            )
            if selected_candidate is None:
                QMessageBox.critical(
                    self,
                    self._t("app.error.hotkey_register_failed.title"),
                    self._t(
                        "app.error.hotkey_register_failed.message",
                        hotkey=spec.label,
                        details=error_text or "unknown",
                    ),
                )
                return
            self.log(self._t("app.log.hotkey_fallback", hotkey=selected_candidate.label))
            spec = selected_candidate
        self._set_stop_hotkey_spec(spec, persist=True)
        if self.recorder.is_recording or self._is_robot_running():
            self._start_stop_hotkey()
        self.log(self._t("app.log.hotkey_updated", hotkey=spec.label))

    def apply_step_changes(self) -> None:
        if self.selected_index is None:
            return
        try:
            params = json.loads(self.params_text.toPlainText().strip() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.critical(self, self._t("app.error.invalid_params_json.title"), str(error))
            return
        try:
            annotations = json.loads(self.annotations_text.toPlainText().strip() or "[]")
        except json.JSONDecodeError as error:
            QMessageBox.critical(
                self, self._t("app.error.invalid_annotations_json.title"), str(error)
            )
            return
        if not isinstance(params, dict):
            QMessageBox.critical(
                self,
                self._t("app.error.invalid_params_json.title"),
                self._t("app.error.invalid_params_object"),
            )
            return
        if not isinstance(annotations, list):
            QMessageBox.critical(
                self,
                self._t("app.error.invalid_annotations_json.title"),
                self._t("app.error.invalid_annotations_array"),
            )
            return
        kind = self._combo_value(self.kind_combo).strip().lower() or "action"
        action = self.action_edit.text().strip()
        control = self.control_edit.text().strip()
        if kind == "action" and action == "":
            action = self.scenario.steps[self.selected_index].action or "click"
        if kind == "control" and control == "":
            control = self.scenario.steps[self.selected_index].control or "if"
        original_step = deepcopy(self.scenario.steps[self.selected_index])
        try:
            updated_step = self.editor.update_step(
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
                updated_step.id = step_id
            validate_step_exportability(updated_step)
        except Exception as error:
            self.scenario.steps[self.selected_index] = original_step
            self.on_select_step(self.selected_index)
            QMessageBox.critical(
                self,
                self._t("app.error.step_apply_invalid.title"),
                str(error),
            )
            return
        self.refresh_steps()

    def insert_params_template_for_selected_action(self) -> None:
        action = self.action_edit.text().strip()
        if action == "" and self.selected_index is not None:
            action = self.scenario.steps[self.selected_index].action
        template = default_params_template_for_action(action)
        if template is None:
            QMessageBox.critical(
                self,
                self._t("app.error.params_template_unsupported.title"),
                self._t(
                    "app.error.params_template_unsupported.message",
                    action=action or "-",
                ),
            )
            return
        self.params_text.setPlainText(json.dumps(template, ensure_ascii=False, indent=2))
        self.log(
            self._t(
                "app.log.params_template_inserted",
                action=_normalize_step_action_for_template(action),
            )
        )

    def start_recording(self) -> None:
        from .recorder import has_visible_window_with_hint

        if self.recorder.is_recording:
            self.log(self._t("app.log.recording_already_running"))
            return
        window_hint = self.window_hint_edit.text().strip() or self._t(
            "app.field.window_hint.placeholder"
        )
        execution_mode = normalize_unity_execution_mode(
            self._combo_value(self.execution_mode_combo)
        )
        if execution_mode == "attach" and not has_visible_window_with_hint(window_hint):
            self.log(self._t("app.log.record_start_failed_attach", window_hint=window_hint))
            QMessageBox.critical(
                self,
                self._t("app.error.attach_target_not_found.title"),
                self._t("app.error.attach_target_not_found.message", window_hint=window_hint),
            )
            return
        if not self._ensure_unity_bridge_dependency_if_configured("recording"):
            return
        self.recorder.start(window_hint=window_hint)
        self._start_stop_hotkey()
        self._start_overlay(mode="recording", progress_text=self._t("overlay.progress.recording"))
        self._rec_indicator.setStyleSheet(
            f"background: {_ACCENT_RED}; color: {_BG}; padding: 2px 8px; font-weight: bold;"
        )
        self._rec_indicator.setText(self._t("app.status.recording"))
        self.setWindowTitle(self._t("app.window.title.recording"))
        self.log(self._t("app.log.recording_started", window_hint=window_hint))

    def stop_recording(self) -> None:
        from .recorder import events_to_steps

        if not self.recorder.is_recording:
            self.log(self._t("app.log.recording_not_running"))
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
        self._rec_indicator.setText(self._t("app.status.record_idle"))
        self.setWindowTitle(self._t("app.window.title"))
        self.log(self._t("app.log.recording_stopped", count=len(steps)))

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
            self._t("app.file_dialog.save.title"),
            "",
            self._t("app.file_dialog.filter.scenario_json"),
        )
        if not path:
            return
        target = Path(path)
        self.scenario.save_json(target)
        self.current_path = target
        self.log(self._t("app.log.saved_scenario", path=target))

    def load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("app.file_dialog.load.title"),
            "",
            self._t("app.file_dialog.filter.scenario_json"),
        )
        if not path:
            return
        try:
            loaded = Scenario.load_json(Path(path))
        except Exception as error:
            QMessageBox.critical(self, self._t("app.error.load.title"), str(error))
            self.log(self._t("app.log.load_failed", error=error))
            return
        self._apply_loaded_scenario(loaded)
        self.current_path = Path(path)
        self.log(self._t("app.log.loaded_scenario", path=path))

    def _apply_loaded_scenario(self, loaded: Scenario) -> None:
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.selected_index = None
        self.name_edit.setText(loaded.name)
        self.scenario_id_edit.setText(loaded.scenario_id)
        self._set_combo_value(self.target_combo, loaded.target)
        self.description_edit.setText(loaded.description)
        self.window_hint_edit.setText(loaded.target_window_hint)
        self._set_combo_value(
            self.execution_mode_combo,
            normalize_unity_execution_mode(loaded.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach")),
        )
        self._refresh_active_profile_combo()
        self.project_path_edit.setText(str(loaded.metadata.get(UNITY_PROJECT_PATH_KEY, "")))
        self.on_execution_mode_changed()
        self.refresh_steps()
        self.on_select_step(-1)

    def open_run_diagnostics(self) -> None:
        path = self._last_run_diagnostics_path
        if path is None or not path.exists():
            QMessageBox.information(
                self,
                self._t("app.info.run_diagnostics_unavailable.title"),
                self._t("app.info.run_diagnostics_unavailable.message"),
            )
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self._t("app.dialog.run_diagnostics.title"))
        dialog.resize(920, 640)
        layout = QVBoxLayout(dialog)

        header = QLabel(self._t("app.dialog.run_diagnostics.path", path=path))
        header.setWordWrap(True)
        layout.addWidget(header)

        raw_text = path.read_text(encoding="utf-8")
        summary_text = self._t("app.dialog.run_diagnostics.summary_unavailable")
        try:
            payload = json.loads(raw_text)
            if isinstance(payload, dict):
                summary_text = summarize_run_diagnostics_payload(payload)
        except Exception:
            summary_text = self._t("app.dialog.run_diagnostics.summary_unavailable")

        summary_box = QPlainTextEdit()
        summary_box.setReadOnly(True)
        summary_box.setMaximumHeight(220)
        summary_box.setPlainText(summary_text)
        layout.addWidget(summary_box)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(raw_text)
        layout.addWidget(text, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        close_button = QPushButton(self._t("app.button.close"))
        close_button.clicked.connect(dialog.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)

        self._register_help_for_widget_tree(dialog)
        dialog.exec()

    def open_help_guide(self) -> None:
        app_help.open_help_guide(self)

    def _close_help_dialog(self) -> None:
        app_help._close_help_dialog(self)

    def _widget_text(self, widget: QWidget) -> str:
        return app_help._widget_text(self, widget)

    def _should_skip_help_widget(self, widget: QWidget) -> bool:
        return app_help._should_skip_help_widget(self, widget)

    def _register_help_for_widget(self, widget: QWidget) -> None:
        app_help._register_help_for_widget(self, widget)

    def _register_help_for_widget_tree(self, root: QWidget) -> None:
        app_help._register_help_for_widget_tree(self, root)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        return app_help.eventFilter(self, obj, event)

    def _sorted_help_entries(self) -> list[HelpEntry]:
        return app_help._sorted_help_entries(self)

    def open_full_json_editor(self) -> None:
        app_dialogs.open_full_json_editor(self)

    def open_variables_editor(self) -> None:
        app_dialogs.open_variables_editor(self)

    def open_profiles_editor(self) -> None:
        app_dialogs.open_profiles_editor(self)
        self._refresh_active_profile_combo()

    def open_execution_outputs_editor(self) -> None:
        app_dialogs.open_execution_outputs_editor(self)

    def open_preflight_validation(self) -> None:
        report = self._validate_scenario_preflight(log_issues=False)
        app_dialogs.open_validation_report_dialog(
            self,
            report,
            title=self._t("app.dialog.validation.title"),
        )

    def open_profile_diff_preview(self) -> None:
        app_dialogs.open_profile_diff_preview_dialog(self)

    def _focus_widget_in_tab(self, widget: QWidget, *, tab_index: int | None = None) -> bool:
        if tab_index is not None:
            self.main_tabs.setCurrentIndex(tab_index)
        widget.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def focus_validation_issue_location(self, location: str) -> bool:
        normalized = str(location or "").strip()
        if normalized == "":
            return False

        step_match = re.match(r"^steps\[(\d+)\](?:\.(.*))?$", normalized)
        if step_match is not None:
            step_index = int(step_match.group(1))
            if step_index < 0 or step_index >= len(self.scenario.steps):
                return False
            self.main_tabs.setCurrentIndex(self.step_tab_index)
            self.step_list.setCurrentRow(step_index)
            self.on_select_step(step_index)

            field_path = str(step_match.group(2) or "").strip().lower()
            if field_path.startswith("id"):
                return self._focus_widget_in_tab(self.step_id_edit, tab_index=self.step_tab_index)
            if field_path.startswith("title"):
                return self._focus_widget_in_tab(self.title_edit, tab_index=self.step_tab_index)
            if field_path.startswith("kind"):
                return self._focus_widget_in_tab(self.kind_combo, tab_index=self.step_tab_index)
            if field_path.startswith("action"):
                return self._focus_widget_in_tab(self.action_edit, tab_index=self.step_tab_index)
            if field_path.startswith("control"):
                return self._focus_widget_in_tab(self.control_edit, tab_index=self.step_tab_index)
            if field_path.startswith("description"):
                return self._focus_widget_in_tab(
                    self.step_description_edit, tab_index=self.step_tab_index
                )
            if field_path.startswith("condition"):
                return self._focus_widget_in_tab(
                    self.step_condition_edit, tab_index=self.step_tab_index
                )
            if field_path.startswith("disabled"):
                return self._focus_widget_in_tab(
                    self.step_disabled_check, tab_index=self.step_tab_index
                )
            if field_path.startswith("continue_on_error"):
                return self._focus_widget_in_tab(
                    self.step_continue_on_error_check, tab_index=self.step_tab_index
                )
            if field_path.startswith("annotations"):
                return self._focus_widget_in_tab(
                    self.annotations_text, tab_index=self.step_tab_index
                )
            return self._focus_widget_in_tab(self.params_text, tab_index=self.step_tab_index)

        if normalized == "name":
            self.name_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        if normalized.startswith("description"):
            return self._focus_widget_in_tab(
                self.description_edit,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("execution.active_profile"):
            return self._focus_widget_in_tab(
                self.active_profile_combo,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("execution.mode") or normalized.startswith(
            f"metadata.{UNITY_EXECUTION_MODE_KEY}"
        ):
            return self._focus_widget_in_tab(
                self.execution_mode_combo,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith(f"metadata.{UNITY_PROJECT_PATH_KEY}") or normalized.startswith(
            "variables.unity_project_path."
        ):
            return self._focus_widget_in_tab(
                self.project_path_edit,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("metadata.target_window_hint") or normalized.startswith(
            "variables.unity_window_hint."
        ):
            return self._focus_widget_in_tab(
                self.window_hint_edit,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("execution") or normalized.startswith("metadata"):
            return self._focus_widget_in_tab(
                self.execution_mode_combo,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("variables"):
            return self._focus_widget_in_tab(
                self.variables_button,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("profiles"):
            return self._focus_widget_in_tab(
                self.profiles_button,
                tab_index=self.scenario_tab_index,
            )
        if normalized.startswith("outputs"):
            return self._focus_widget_in_tab(
                self.export_name_edit,
                tab_index=self.export_tab_index,
            )
        if normalized == "scenario":
            return self._focus_widget_in_tab(
                self.scenario_id_edit,
                tab_index=self.scenario_tab_index,
            )
        return False

    def _validate_scenario_preflight(self, *, log_issues: bool) -> ValidationReport:
        self._sync_scenario_header()
        report = validate_scenario(
            self.scenario,
            active_profile=self._active_profile_value(),
        )
        if report.is_valid:
            self.log(self._t("app.log.validation_ok"))
        elif log_issues:
            self.log(self._t("app.log.validation_failed"))
            for issue in report.issues:
                self.log(
                    self._t(
                        "app.log.validation_issue",
                        code=issue.code,
                        location=issue.location or "-",
                        message=issue.message,
                    )
                )
        return report

    def export_scenario(self) -> None:
        report = self._validate_scenario_preflight(log_issues=True)
        if not report.is_valid:
            app_dialogs.open_validation_report_dialog(
                self,
                report,
                title=self._t("app.dialog.validation.title"),
            )
            return
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        active_profile = self._active_profile_value()
        try:
            result = export_all(
                self.scenario,
                output_dir=output_dir,
                suite_name=suite_name,
                active_profile=active_profile,
            )
        except Exception as error:
            self.log(self._t("app.log.export_failed", error=error))
            QMessageBox.critical(self, self._t("app.error.export.title"), str(error))
            return
        self.log(self._t("app.log.exported_robot", path=result.robot_path))
        self.log(self._t("app.log.exported_json", path=result.json_path))

    def _is_robot_running(self) -> bool:
        return self._run_thread is not None and self._run_thread.is_alive()

    def run_robot_suite(self) -> None:
        if self.recorder.is_recording:
            self.log(self._t("app.log.run_stop_recording_first"))
            QMessageBox.critical(
                self,
                self._t("app.error.recording_in_progress.title"),
                self._t("app.log.run_stop_recording_first"),
            )
            return
        if self._is_robot_running():
            self.log(self._t("app.log.robot_already_running"))
            return
        self._set_run_phase("precheck")
        self.log(self._t("app.log.preflight_checks"))
        report = self._validate_scenario_preflight(log_issues=True)
        if not report.is_valid:
            app_dialogs.open_validation_report_dialog(
                self,
                report,
                title=self._t("app.dialog.validation.title"),
            )
            self._set_run_phase("idle")
            return
        self._sync_scenario_header()
        if not self._ensure_unity_bridge_dependency_if_configured("run"):
            self._set_run_phase("idle")
            return
        self._set_run_phase("exporting")
        self.log(self._t("app.log.prepare_export"))
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        active_profile = self._active_profile_value()
        try:
            result = export_all(
                self.scenario,
                output_dir=output_dir,
                suite_name=suite_name,
                active_profile=active_profile,
            )
        except Exception as error:
            self.log(self._t("app.log.run_export_failed", error=error))
            QMessageBox.critical(self, self._t("app.error.run.title"), str(error))
            self._set_run_phase("idle")
            return
        artifacts_dir = output_dir / "run"
        variable_output = output_dir
        self._last_run_output_xml_path = artifacts_dir / "output.xml"
        self._last_run_diagnostics_path = artifacts_dir / "diagnostics" / "run-diagnostics.json"
        self._last_run_diagnostics = None
        self._last_run_failure_screenshot_path = None
        self._stop_requested = False
        self._set_run_phase("starting_robot")
        self._set_run_controls(running=True)
        self._start_stop_hotkey()
        self._start_overlay(mode="run", progress_text=self._status_pill.text())

        def _run() -> None:
            run_result: RunResult | None = None
            run_error: Exception | None = None
            try:
                self._log_async(self._t("app.log.running_robot_suite"))
                self._set_run_phase_async("starting_robot")
                self._log_async(self._t("app.log.starting_robot_process"))
                process = start_robot_process(
                    suite_path=result.robot_path,
                    output_dir=artifacts_dir,
                    variable_output_dir=variable_output,
                )
                self._set_current_process(process)
                self._set_run_phase_async("attaching_unity")
                self._log_async(self._t("app.log.attaching_unity_wait"))
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

    def stop_robot_suite(self, stop_source: str = "manual") -> None:
        if not self._is_robot_running():
            self.log(self._t("app.log.robot_not_running"))
            return
        _ = stop_source
        self._stop_requested = True
        self._set_run_controls(running=True, stopping=True)
        process = self._get_current_process()
        self.log(self._t("app.log.stopping_robot_suite", hotkey=self._stop_hotkey_spec.label))
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
            self.log(self._t("app.log.robot_run_failed", error=run_error))
        elif run_result is not None:
            self.log(self._t("app.log.robot_exit", code=run_result.return_code))
            if run_result.stdout:
                self.log(run_result.stdout.strip())
            if run_result.stderr:
                self.log(run_result.stderr.strip())
            self._collect_and_log_run_diagnostics(run_result)
        if self._stop_requested:
            self.log(self._t("app.log.robot_stopped"))
        self._stop_requested = False
        self._stop_overlay()
        self._stop_stop_hotkey()
        self._set_run_controls(running=False)

    def _collect_and_log_run_diagnostics(self, run_result: RunResult) -> None:
        output_xml_path = self._last_run_output_xml_path
        if output_xml_path is None or not output_xml_path.exists():
            self.log(
                self._t(
                    "app.log.run_diag_output_missing",
                    path=output_xml_path or "-",
                )
            )
            return
        try:
            diagnostics = parse_robot_output(output_xml_path)
        except Exception as error:
            self.log(self._t("app.log.run_diag_parse_failed", error=error))
            return

        self._last_run_diagnostics = diagnostics
        screenshot_path: Path | None = None
        is_failure = run_result.return_code != 0 or diagnostics.test_status.upper() == "FAIL"
        if is_failure:
            screenshot_path = capture_failure_screenshot(
                diagnostics_dir=output_xml_path.parent / "diagnostics"
            )
            self._last_run_failure_screenshot_path = screenshot_path
            if screenshot_path is not None:
                self.log(self._t("app.log.run_diag_screenshot", path=screenshot_path))
            else:
                self.log(self._t("app.log.run_diag_screenshot_failed"))
        target_path = self._last_run_diagnostics_path or (
            output_xml_path.parent / "diagnostics" / "run-diagnostics.json"
        )
        run_context = self._build_run_diagnostics_context(output_xml_path)
        try:
            saved = write_run_diagnostics_file(
                diagnostics,
                target_path=target_path,
                screenshot_path=screenshot_path,
                run_context=run_context,
            )
            self._last_run_diagnostics_path = saved
            self.log(self._t("app.log.run_diag_saved", path=saved))
        except Exception as error:
            self.log(self._t("app.log.run_diag_save_failed", error=error))

        self.log(
            self._t(
                "app.log.run_diag_summary",
                status=diagnostics.test_status.upper(),
                total=diagnostics.total_keyword_count,
                elapsed=f"{diagnostics.total_elapsed_seconds:.3f}",
            )
        )
        for index, item in enumerate(diagnostics.slowest_keywords[:3], start=1):
            self.log(
                self._t(
                    "app.log.run_diag_slowest",
                    index=index,
                    name=item.name or "-",
                    elapsed=f"{item.elapsed_seconds:.3f}",
                    status=item.status,
                )
            )
        if diagnostics.failed_keyword is not None:
            self.log(
                self._t(
                    "app.log.run_diag_failed_keyword",
                    name=diagnostics.failed_keyword.name or "-",
                    message=diagnostics.failed_keyword.message or "-",
                )
            )
        if diagnostics.last_annotation is not None:
            self.log(
                self._t(
                    "app.log.run_diag_last_annotation",
                    payload=json.dumps(diagnostics.last_annotation, ensure_ascii=False),
                )
            )

    def _build_run_diagnostics_context(self, output_xml_path: Path) -> dict[str, object]:
        execution_mode = normalize_unity_execution_mode(
            self._combo_value(self.execution_mode_combo)
        )
        context: dict[str, object] = {
            "scenario_name": self.scenario.name,
            "scenario_id": self.scenario.scenario_id,
            "target": self.scenario.target,
            "execution_mode": execution_mode,
            "active_profile": self._active_profile_value() or None,
            "window_hint": self.window_hint_edit.text().strip() or None,
            "unity_project_path": self.project_path_edit.text().strip() or None,
            "output_xml_path": str(output_xml_path),
            "captured_at_utc": datetime.now(UTC).isoformat(),
        }
        return context

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
        self._persist_ui_settings()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(_STYLESHEET)
    window = StudioApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
