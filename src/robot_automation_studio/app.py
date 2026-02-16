"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import threading
import warnings
from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
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
    QKeySequenceEdit,
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
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .settings_store import (
    StudioUiSettings,
    load_ui_settings,
    resolve_settings_path,
    save_ui_settings,
)
from .status import SPINNER_FRAMES, format_run_status, next_spinner_index
from .ui_help import HelpEntry, build_help_entry, filter_help_entries
from .unity_bridge import UnityBridgeClient
from .unity_diagnostics import get_recent_unity_compile_errors

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

        self.title_label = QLabel()
        self.title_label.setObjectName("PanelTitle")
        header_layout.addWidget(self.title_label)

        self.name_edit = QLineEdit(self.scenario.name)
        self.name_edit.setObjectName("ScenarioNameEdit")
        self.name_edit.setMinimumWidth(260)
        header_layout.addWidget(self.name_edit)

        header_layout.addStretch()

        self.record_button = QPushButton()
        self.record_button.setObjectName("RecordButton")
        self.record_button.clicked.connect(self.start_recording)
        header_layout.addWidget(self.record_button)

        self.record_stop_button = QPushButton()
        self.record_stop_button.setObjectName("StopButton")
        self.record_stop_button.clicked.connect(self.stop_recording)
        header_layout.addWidget(self.record_stop_button)

        vline1 = QFrame()
        vline1.setFrameShape(QFrame.Shape.VLine)
        vline1.setStyleSheet(f"background: {_BG_LIGHT};")
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
        vline2.setFrameShape(QFrame.Shape.VLine)
        vline2.setStyleSheet(f"background: {_BG_LIGHT};")
        header_layout.addWidget(vline2)

        self.help_status_label = QLabel()
        self.help_status_label.setObjectName("HeaderHelpLabel")
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
        self.step_form.addRow(self.step_kind_label, self.kind_combo)

        self.action_edit = QLineEdit()
        self.action_edit.setObjectName("StepActionEdit")
        self.action_label = QLabel()
        self.step_form.addRow(self.action_label, self.action_edit)

        self.control_edit = QLineEdit()
        self.control_edit.setObjectName("StepControlEdit")
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
        self.params_label = QLabel()
        self.step_form.addRow(self.params_label, self.params_text)

        step_scroll_layout.addLayout(self.step_form)

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

        project_path_row = QHBoxLayout()
        self.project_path_edit = QLineEdit(
            str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, ""))
        )
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

        self.output_dir_edit = QLineEdit("artifacts/studio")
        self.output_dir_edit.setObjectName("OutputDirEdit")
        self.output_dir_label = QLabel()
        export_form.addRow(self.output_dir_label, self.output_dir_edit)

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

        self.on_execution_mode_changed()
        self._update_step_kind_fields_visibility()

    def _apply_localized_texts(self) -> None:
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
        self.hotkey_button.setText(
            self._t("app.button.hotkey_with_value", hotkey=self._stop_hotkey_spec.label)
        )
        self.hotkey_button.setToolTip(self._t("app.tooltip.stop_hotkey"))
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
        self.step_description_edit.setPlaceholderText(
            self._t("app.field.step_description.placeholder")
        )
        self.condition_label.setText(self._t("app.field.step_condition.label"))
        self.step_condition_edit.setPlaceholderText(self._t("app.field.step_condition.placeholder"))
        self.step_disabled_check.setText(self._t("app.field.step_disabled"))
        self.step_continue_on_error_check.setText(self._t("app.field.step_continue_on_error"))
        self.annotations_label.setText(self._t("app.field.annotations.label"))
        self.params_label.setText(self._t("app.field.params.label"))
        self.apply_step_button.setText(self._t("app.button.apply_step"))

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
        self.unity_project_path_label.setText(self._t("app.field.unity_project_path.label"))
        self.project_path_edit.setPlaceholderText(
            self._t("app.field.unity_project_path.placeholder")
        )
        self.project_path_browse_button.setText(self._t("app.button.browse"))
        self.description_label.setText(self._t("app.field.description.label"))
        self.description_edit.setPlaceholderText(self._t("app.field.description.placeholder"))
        self.variables_button.setText(self._t("app.button.variables"))
        self.profiles_button.setText(self._t("app.button.profiles"))
        self.execution_outputs_button.setText(self._t("app.button.execution_outputs"))

        self.output_dir_label.setText(self._t("app.field.output_dir.label"))
        self.output_dir_edit.setPlaceholderText(self._t("app.field.output_dir.placeholder"))
        self.export_name_label.setText(self._t("app.field.export_name.label"))
        self.export_name_edit.setPlaceholderText(self._t("app.field.export_name.placeholder"))
        self.export_button.setText(self._t("app.button.export"))

        self.log_label.setText(self._t("app.label.output_log"))
        self._log_toggle_button.setToolTip(self._t("app.log.toggle.tooltip"))

        self.on_execution_mode_changed()
        self._update_step_kind_fields_visibility()
        self._render_robot_status()
        self.refresh_steps()

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
        timestamp = datetime.now().isoformat(timespec="seconds")
        line = f"[{timestamp}] {message}\n"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("a", encoding="utf-8") as stream:
            stream.write(line)

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
        dialog.setWindowTitle(self._t("app.help.dialog.title"))
        dialog.resize(980, 640)
        self._help_dialog = dialog

        layout = QVBoxLayout(dialog)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(self._t("app.log.search")))
        search_edit = QLineEdit()
        search_edit.setMinimumWidth(340)
        top_layout.addWidget(search_edit)
        summary_label = QLabel(
            self._t("app.help.dialog.summary", count=len(self._help_entries_by_id))
        )
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
        close_button = QPushButton(self._t("app.button.close"))
        close_button.clicked.connect(self._close_help_dialog)
        footer_layout.addWidget(close_button)
        layout.addLayout(footer_layout)

        visible_entries: list[HelpEntry] = []

        def _render_details(entry: HelpEntry) -> None:
            detail_text.setPlainText(
                self._t(
                    "app.help.dialog.details",
                    title=entry.title,
                    widget_class=entry.widget_class,
                    widget_id=entry.widget_id,
                    summary=entry.summary,
                    detail=entry.detail,
                )
            )

        def _refresh_list() -> None:
            visible_entries.clear()
            listbox.clear()
            filtered = filter_help_entries(self._sorted_help_entries(), search_edit.text())
            for entry in filtered:
                visible_entries.append(entry)
                listbox.addItem(
                    self._t(
                        "app.list.item.help_entry",
                        title=entry.title,
                        widget_class=entry.widget_class,
                    )
                )
            summary_label.setText(
                self._t(
                    "app.help.dialog.shown",
                    shown=len(filtered),
                    total=len(self._help_entries_by_id),
                )
            )
            if visible_entries:
                listbox.setCurrentRow(0)
                _render_details(visible_entries[0])
            else:
                detail_text.setPlainText(self._t("app.help.dialog.no_match"))

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
            locale=self._translator.locale,
        )
        if entry.summary.strip() == "":
            return
        self._help_entries_by_widget[widget] = entry
        self._help_entries_by_id[entry.widget_id] = entry
        widget.setToolTip(build_help_tooltip_text(entry.summary, locale=self._translator.locale))
        widget.installEventFilter(self)

    def _register_help_for_widget_tree(self, root: QWidget) -> None:
        for child in root.findChildren(QWidget):
            self._register_help_for_widget(child)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        combo = self._combo_tooltip_viewports.get(obj)
        if combo is not None and event.type() == QEvent.Type.ToolTip:
            if isinstance(event, QHelpEvent):
                index = combo.view().indexAt(event.pos())
                if index.isValid():
                    tooltip = index.data(Qt.ItemDataRole.ToolTipRole)
                    if tooltip:
                        QToolTip.showText(event.globalPos(), str(tooltip), combo.view())
                        return True
            return False
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
                QMessageBox.critical(
                    dialog, self._t("app.error.full_json_invalid.title"), str(error)
                )
                return
            text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

        def _reload_model() -> None:
            self._sync_scenario_header()
            text.setPlainText(json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))

        def _apply_json() -> None:
            try:
                payload = json.loads(text.toPlainText().strip() or "{}")
            except json.JSONDecodeError as error:
                QMessageBox.critical(
                    dialog, self._t("app.error.full_json_invalid.title"), str(error)
                )
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
        execution_text.setPlainText(
            json.dumps(self.scenario.execution, ensure_ascii=False, indent=2)
        )
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
                QMessageBox.critical(
                    dialog, self._t("app.error.full_json_invalid.title"), str(error)
                )
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

    def export_scenario(self) -> None:
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
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
        self._sync_scenario_header()
        if not self._ensure_unity_bridge_dependency_if_configured("run"):
            self._set_run_phase("idle")
            return
        self._set_run_phase("exporting")
        self.log(self._t("app.log.prepare_export"))
        output_dir = Path(self.output_dir_edit.text()).resolve()
        suite_name = self.export_name_edit.text().strip() or "scenario"
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        except Exception as error:
            self.log(self._t("app.log.run_export_failed", error=error))
            QMessageBox.critical(self, self._t("app.error.run.title"), str(error))
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
        if self._stop_requested:
            self.log(self._t("app.log.robot_stopped"))
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
