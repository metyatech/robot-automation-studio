"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import json
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from pynput import keyboard as pynput_keyboard

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
from .unity_bridge import UnityBridgeClient
from .unity_diagnostics import get_recent_unity_compile_errors
from .unity_project import resolve_attached_unity_project_path
from .upm import (
    ensure_unity_bridge_upm_dependency,
    has_unity_bridge_package_script_meta,
    install_legacy_unity_bridge_script,
)

STOP_HOTKEY_BIND = "<ctrl>+<shift>+<f12>"
STOP_HOTKEY_LABEL = "Ctrl+Shift+F12"
BRIDGE_READY_TIMEOUT_SECONDS = 15.0
BRIDGE_READY_CHECK_TIMEOUT_SECONDS = 3.0
BRIDGE_READY_REQUEST_TIMEOUT_SECONDS = 0.8
BRIDGE_FALLBACK_READY_TIMEOUT_SECONDS = 25.0


class StudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Robot Automation Studio")
        self.root.geometry("1200x760")

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        self.recorder = ScenarioRecorder(
            on_record_error=self._on_record_error,
            unity_bridge=self.unity_bridge,
        )
        self.current_path: Path | None = None

        self.name_var = tk.StringVar(value=self.scenario.name)
        self.window_hint_var = tk.StringVar(value=self.scenario.target_window_hint)
        self.execution_mode_var = tk.StringVar(
            value=normalize_unity_execution_mode(
                self.scenario.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach")
            )
        )
        self.unity_project_path_var = tk.StringVar(
            value=str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, ""))
        )
        self.output_dir_var = tk.StringVar(value="artifacts/studio")
        self.export_name_var = tk.StringVar(value="unity-editor-generated")
        self.log_var = tk.StringVar(value="")
        self.robot_status_var = tk.StringVar(value=format_run_status("idle", SPINNER_FRAMES[0]))

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
        self._status_timer_id: str | None = None
        self._phase_promotion_timer_id: str | None = None

        self._configure_theme()
        self._build_ui()
        self.refresh_steps()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -- Dark-theme palette (Catppuccin Mocha) --------------------------------
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
    _FONT = ("Segoe UI", 10)
    _FONT_MONO = ("Consolas", 10)
    _FONT_MONO_SM = ("Consolas", 9)

    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # Global defaults
        style.configure(".", background=self._BG, foreground=self._FG, font=self._FONT)
        style.configure("TFrame", background=self._BG)
        style.configure("TLabel", background=self._BG, foreground=self._FG, font=self._FONT)
        style.configure(
            "TLabelframe", background=self._BG, foreground=self._ACCENT_BLUE, font=self._FONT
        )
        style.configure("TLabelframe.Label", background=self._BG, foreground=self._ACCENT_BLUE)
        style.configure(
            "TEntry",
            fieldbackground=self._BG_MID,
            foreground=self._FG,
            insertcolor=self._FG,
            borderwidth=1,
        )
        style.configure(
            "TCombobox",
            fieldbackground=self._BG_MID,
            foreground=self._FG,
            background=self._BTN_BG,
            arrowcolor=self._FG,
        )
        style.configure(
            "TButton",
            background=self._BTN_BG,
            foreground=self._FG,
            borderwidth=0,
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[("active", self._BTN_HOVER), ("disabled", self._BG_LIGHT)],
            foreground=[("disabled", self._FG_DIM)],
        )
        style.configure("TSeparator", background=self._BG_LIGHT)
        style.configure(
            "TPanedwindow",
            background=self._BG,
        )
        style.configure("Sash", sashthickness=6, background=self._BG_LIGHT)
        style.configure("Vertical.TScrollbar", background=self._BTN_BG, troughcolor=self._BG_MID)

        # Colored button styles
        style.configure("Record.TButton", background="#2d5a2d", foreground=self._ACCENT_GREEN)
        style.map(
            "Record.TButton", background=[("active", "#3a7a3a"), ("disabled", self._BG_LIGHT)]
        )
        style.configure("Stop.TButton", background="#5a2d2d", foreground=self._ACCENT_RED)
        style.map("Stop.TButton", background=[("active", "#7a3a3a"), ("disabled", self._BG_LIGHT)])
        style.configure("Add.TButton", background="#2d3d5a", foreground=self._ACCENT_BLUE)
        style.map("Add.TButton", background=[("active", "#3a4d7a"), ("disabled", self._BG_LIGHT)])
        style.configure("Danger.TButton", background="#5a2d2d", foreground=self._ACCENT_RED)
        style.map(
            "Danger.TButton", background=[("active", "#7a3a3a"), ("disabled", self._BG_LIGHT)]
        )

        self.root.configure(bg=self._BG)

    def _build_ui(self) -> None:
        # ── A. Scenario Configuration ──────────────────────────────────────
        config_frame = ttk.LabelFrame(self.root, text="Scenario Configuration", padding=8)
        config_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(config_frame, text="Scenario Name").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.name_var, width=40).grid(
            row=0, column=1, sticky=tk.W, padx=6
        )
        ttk.Label(config_frame, text="Window Hint").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        ttk.Entry(config_frame, textvariable=self.window_hint_var, width=24).grid(
            row=0, column=3, sticky=tk.W, padx=6
        )
        ttk.Label(config_frame, text="Execution Mode").grid(
            row=1, column=0, sticky=tk.W, pady=(6, 0)
        )
        mode_combo = ttk.Combobox(
            config_frame,
            textvariable=self.execution_mode_var,
            values=("attach", "launch"),
            state="readonly",
            width=14,
        )
        mode_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        mode_combo.bind("<<ComboboxSelected>>", self.on_execution_mode_changed)
        ttk.Label(config_frame, text="Unity Project Path").grid(
            row=1, column=2, sticky=tk.W, padx=(20, 0), pady=(6, 0)
        )
        self.project_path_entry = ttk.Entry(
            config_frame, textvariable=self.unity_project_path_var, width=44
        )
        self.project_path_entry.grid(row=1, column=3, sticky=tk.W, padx=6, pady=(6, 0))
        self.project_path_browse_button = ttk.Button(
            config_frame, text="Browse", command=self.browse_unity_project_path
        )
        self.project_path_browse_button.grid(row=1, column=4, sticky=tk.W, pady=(6, 0))

        # ── B. Toolbar ─────────────────────────────────────────────────────
        toolbar_frame = ttk.LabelFrame(self.root, text="Toolbar", padding=(8, 4))
        toolbar_frame.pack(fill=tk.X, padx=8, pady=4)

        # Recording group
        ttk.Button(
            toolbar_frame,
            text="\u25cf Start Recording",
            command=self.start_recording,
            style="Record.TButton",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            toolbar_frame,
            text="\u25a0 Stop Recording",
            command=self.stop_recording,
            style="Stop.TButton",
        ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2
        )

        # Add steps group
        for label, cmd in [
            ("+ Click", self.add_click),
            ("+ Drag", self.add_drag),
            ("+ Shortcut", self.add_shortcut),
            ("+ Menu", self.add_menu),
            ("+ Type", self.add_type),
        ]:
            ttk.Button(toolbar_frame, text=label, command=cmd, style="Add.TButton").pack(
                side=tk.LEFT, padx=2
            )

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2
        )

        # Edit steps group
        ttk.Button(
            toolbar_frame, text="Delete", command=self.delete_selected, style="Danger.TButton"
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="\u25b2 Up", command=self.move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="\u25bc Down", command=self.move_down).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar_frame, text="Duplicate", command=self.duplicate_selected).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2
        )

        # File group
        ttk.Button(toolbar_frame, text="Save JSON", command=self.save_json).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar_frame, text="Load JSON", command=self.load_json).pack(
            side=tk.LEFT, padx=2
        )

        # REC indicator (right-aligned)
        self._rec_indicator = tk.Label(
            toolbar_frame,
            text=" IDLE ",
            font=("Segoe UI", 9, "bold"),
            bg=self._BG_LIGHT,
            fg=self._FG_DIM,
            padx=8,
            pady=2,
        )
        self._rec_indicator.pack(side=tk.RIGHT, padx=4)

        # ── C. Steps & Editor ──────────────────────────────────────────────
        steps_frame = ttk.LabelFrame(self.root, text="Steps & Editor", padding=4)
        steps_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        body = ttk.Panedwindow(steps_frame, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        # Step list with scrollbar
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)
        step_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        step_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.step_list = tk.Listbox(
            list_frame,
            height=18,
            bg=self._BG_MID,
            fg=self._FG,
            selectbackground=self._ACCENT_BLUE,
            selectforeground=self._BG,
            font=self._FONT_MONO,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=step_scroll.set,
        )
        self.step_list.pack(fill=tk.BOTH, expand=True)
        step_scroll.configure(command=self.step_list.yview)
        self.step_list.bind("<<ListboxSelect>>", self.on_select_step)

        # Step editor (right pane)
        edit_row = ttk.Frame(right)
        edit_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(edit_row, text="Title").grid(row=0, column=0, sticky=tk.W)
        self.title_var = tk.StringVar(value="")
        ttk.Entry(edit_row, textvariable=self.title_var, width=32).grid(
            row=0, column=1, sticky=tk.W
        )

        ttk.Label(edit_row, text="Action").grid(row=1, column=0, sticky=tk.W)
        self.action_var = tk.StringVar(value="")
        ttk.Entry(edit_row, textvariable=self.action_var, width=32).grid(
            row=1, column=1, sticky=tk.W
        )

        ttk.Label(edit_row, text="Params (JSON)").grid(row=2, column=0, sticky=tk.NW)
        self.params_text = tk.Text(
            edit_row,
            width=42,
            height=16,
            bg=self._BG_MID,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO,
            borderwidth=0,
            highlightthickness=0,
        )
        self.params_text.grid(row=2, column=1, sticky=tk.W)

        ttk.Button(right, text="Apply Step Changes", command=self.apply_step_changes).pack(
            anchor=tk.W
        )

        # ── D. Export & Run ────────────────────────────────────────────────
        run_frame = ttk.LabelFrame(self.root, text="Export & Run", padding=8)
        run_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(run_frame, text="Output Dir").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(run_frame, textvariable=self.output_dir_var, width=48).grid(
            row=0, column=1, sticky=tk.W
        )
        ttk.Label(run_frame, text="Export Name").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Entry(run_frame, textvariable=self.export_name_var, width=24).grid(
            row=0, column=3, sticky=tk.W
        )
        ttk.Button(run_frame, text="Export", command=self.export_scenario).grid(
            row=0, column=4, padx=8
        )
        self.run_robot_button = ttk.Button(
            run_frame, text="Run Robot", command=self.run_robot_suite, style="Record.TButton"
        )
        self.run_robot_button.grid(row=0, column=5, padx=4)
        self.stop_robot_button = ttk.Button(
            run_frame,
            text=f"Stop Robot ({STOP_HOTKEY_LABEL})",
            command=self.stop_robot_suite,
            state="disabled",
            style="Stop.TButton",
        )
        self.stop_robot_button.grid(row=0, column=6, padx=4)

        # Status row with color bar
        self._status_bar = tk.Frame(run_frame, width=6, height=18, bg=self._FG_DIM)
        self._status_bar.grid(row=1, column=0, sticky=tk.W, pady=(8, 0), padx=(0, 4))
        ttk.Label(run_frame, text="Status").grid(
            row=1, column=0, sticky=tk.W, pady=(8, 0), padx=(14, 0)
        )
        ttk.Label(
            run_frame,
            textvariable=self.robot_status_var,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        # ── E. Output Log ──────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(self.root, text="Output Log", padding=4)
        log_frame.pack(fill=tk.BOTH, padx=8, pady=(4, 8))

        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text = tk.Text(
            log_frame,
            height=8,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=log_scroll.set,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scroll.configure(command=self.log_text.yview)

        self.on_execution_mode_changed()

    def _sync_scenario_header(self) -> None:
        self.scenario.name = self.name_var.get().strip() or "Scenario"
        self.scenario.target_window_hint = self.window_hint_var.get().strip() or "Unity"
        execution_mode = normalize_unity_execution_mode(self.execution_mode_var.get())
        self.execution_mode_var.set(execution_mode)
        self.scenario.metadata[UNITY_EXECUTION_MODE_KEY] = execution_mode
        unity_project_path = self.unity_project_path_var.get().strip()
        if unity_project_path:
            self.scenario.metadata[UNITY_PROJECT_PATH_KEY] = unity_project_path
        else:
            self.scenario.metadata.pop(UNITY_PROJECT_PATH_KEY, None)

    def _on_record_error(self, message: str) -> None:
        self.root.after(0, lambda: self.log(f"Record error: {message}"))

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def _log_async(self, message: str) -> None:
        self.root.after(0, lambda: self.log(message))

    def _update_status_bar_color(self) -> None:
        phase = self._run_phase
        if phase == "idle":
            color = self._FG_DIM
        elif phase == "stopping":
            color = self._ACCENT_RED
        else:
            color = self._ACCENT_YELLOW
        self._status_bar.configure(bg=color)

    def _render_robot_status(self) -> None:
        spinner = SPINNER_FRAMES[self._status_spinner_index]
        status_text = format_run_status(self._run_phase, spinner)
        self.robot_status_var.set(status_text)
        self._update_status_bar_color()
        if self._overlay is not None and self._overlay_mode == "run":
            self._overlay.set_progress_text(status_text)

    def _tick_robot_status(self) -> None:
        if self._run_phase == "idle":
            self._status_timer_id = None
            return
        self._status_spinner_index = next_spinner_index(self._status_spinner_index)
        self._render_robot_status()
        self._status_timer_id = self.root.after(160, self._tick_robot_status)

    def _set_run_phase(self, phase: str) -> None:
        self._run_phase = phase
        self._render_robot_status()
        if phase == "idle":
            if self._status_timer_id is not None:
                self.root.after_cancel(self._status_timer_id)
                self._status_timer_id = None
            if self._phase_promotion_timer_id is not None:
                self.root.after_cancel(self._phase_promotion_timer_id)
                self._phase_promotion_timer_id = None
            return
        if self._status_timer_id is None:
            self._status_timer_id = self.root.after(160, self._tick_robot_status)

    def _set_run_phase_async(self, phase: str) -> None:
        self.root.after(0, lambda: self._set_run_phase(phase))

    def _schedule_phase_promotion(self, from_phase: str, to_phase: str, delay_ms: int) -> None:
        if self._phase_promotion_timer_id is not None:
            self.root.after_cancel(self._phase_promotion_timer_id)
            self._phase_promotion_timer_id = None

        def _promote() -> None:
            self._phase_promotion_timer_id = None
            if self._run_phase != from_phase:
                return
            self._set_run_phase(to_phase)

        self._phase_promotion_timer_id = self.root.after(delay_ms, _promote)

    def _set_run_controls(self, running: bool, stopping: bool = False) -> None:
        if running:
            self.run_robot_button.configure(state="disabled")
            self.stop_robot_button.configure(state="normal")
            if stopping:
                self._set_run_phase("stopping")
            elif self._run_phase == "idle":
                self._set_run_phase("running")
            return
        self.run_robot_button.configure(state="normal")
        self.stop_robot_button.configure(state="disabled")
        self._set_run_phase("idle")

    def _set_current_process(self, process: subprocess.Popen[str] | None) -> None:
        with self._run_lock:
            self._run_process = process

    def _get_current_process(self) -> subprocess.Popen[str] | None:
        with self._run_lock:
            return self._run_process

    def _start_stop_hotkey(self) -> None:
        def _on_hotkey() -> None:
            self.root.after(0, self._stop_active_automation)

        try:
            self._stop_hotkey_listener = pynput_keyboard.GlobalHotKeys(
                {
                    STOP_HOTKEY_BIND: _on_hotkey,
                }
            )
            self._stop_hotkey_listener.start()
        except Exception as error:  # pragma: no cover - integration path
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
                root=self.root,
                window_hint=self.window_hint_var.get().strip() or "Unity",
                stop_hotkey_label=STOP_HOTKEY_LABEL,
                mode=mode,
            )
            self._overlay_mode = mode
            self._overlay.start()
            self._overlay.set_progress_text(progress_text)
        except Exception as error:  # pragma: no cover - integration path
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
        self.step_list.delete(0, tk.END)
        for idx, step in enumerate(self.scenario.steps):
            self.step_list.insert(tk.END, f"{idx + 1}. {step.action} - {step.title}")

    def on_select_step(self, _event: Any = None) -> None:
        selection = self.step_list.curselection()
        if not selection:
            self.selected_index = None
            return
        index = int(selection[0])
        self.selected_index = index
        step = self.scenario.steps[index]
        self.title_var.set(step.title)
        self.action_var.set(step.action)
        self.params_text.delete("1.0", tk.END)
        self.params_text.insert("1.0", json.dumps(step.params, ensure_ascii=False, indent=2))

    def on_execution_mode_changed(self, _event: Any = None) -> None:
        execution_mode = normalize_unity_execution_mode(self.execution_mode_var.get())
        self.execution_mode_var.set(execution_mode)
        self.project_path_entry.configure(state="normal")
        self.project_path_browse_button.configure(state="normal")

    def _ensure_unity_bridge_dependency_if_configured(self, purpose: str) -> bool:
        project_path_raw = self.unity_project_path_var.get().strip()
        execution_mode = normalize_unity_execution_mode(self.execution_mode_var.get())

        if project_path_raw == "" and execution_mode == "attach":
            detected_path = resolve_attached_unity_project_path(
                window_hint=self.window_hint_var.get().strip() or "Unity"
            )
            if detected_path:
                self.unity_project_path_var.set(detected_path)
                project_path_raw = detected_path
                self.log(f"Auto-detected Unity Project Path: {detected_path}")

        changed = False
        if project_path_raw != "":
            self.log(f"Ensuring Unity bridge package for {purpose}: {project_path_raw}")
            try:
                changed = ensure_unity_bridge_upm_dependency(Path(project_path_raw))
            except Exception as error:
                self.log(f"Unity bridge package setup failed: {error}")
                messagebox.showerror(
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

        if purpose == "recording":
            wait_timeout = (
                BRIDGE_READY_TIMEOUT_SECONDS if changed else BRIDGE_READY_CHECK_TIMEOUT_SECONDS
            )
            self.log("Checking Unity bridge readiness...")
            if not self.unity_bridge.wait_until_available(
                timeout_seconds=wait_timeout,
                request_timeout_seconds=BRIDGE_READY_REQUEST_TIMEOUT_SECONDS,
            ):
                self.log("Unity bridge readiness check timed out.")
                if project_path_raw != "":
                    project_root = Path(project_path_raw)
                    if not has_unity_bridge_package_script_meta(project_root):
                        self.log(
                            "Unity bridge package script meta is missing in PackageCache. "
                            "Installing legacy fallback bridge script..."
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
                messagebox.showerror(
                    "Unity Bridge Not Ready",
                    (
                        "Unity bridge is not ready yet.\n"
                        "Unity may still be importing packages or compiling scripts.\n"
                        "Open/focus the target Unity Editor and retry Start Recording.\n"
                        "If this persists, fix Unity compile errors first."
                        f"{compile_error_hint}"
                    ),
                )
                return False
            self.log("Unity bridge is ready.")
        return True

    def browse_unity_project_path(self) -> None:
        selected = filedialog.askdirectory()
        if not selected:
            return
        self.unity_project_path_var.set(selected)

    def apply_step_changes(self) -> None:
        if self.selected_index is None:
            return
        try:
            params = json.loads(self.params_text.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as error:
            messagebox.showerror("Invalid JSON", str(error))
            return
        self.editor.update_step(
            self.selected_index,
            title=self.title_var.get().strip(),
            action=self.action_var.get().strip(),
            params=params,
        )
        self.refresh_steps()

    def start_recording(self) -> None:
        if self.recorder.is_recording:
            self.log("Recording is already running.")
            return
        window_hint = self.window_hint_var.get().strip() or "Unity"
        execution_mode = normalize_unity_execution_mode(self.execution_mode_var.get())
        if execution_mode == "attach" and not has_visible_window_with_hint(window_hint):
            self.log(
                f"Recording start failed: attach target window not found. window_hint={window_hint}"
            )
            messagebox.showerror(
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
        self._rec_indicator.configure(text=" \u25cf REC ", bg=self._ACCENT_RED, fg="#1e1e2e")
        self.root.title("Robot Automation Studio [RECORDING]")
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
        self._rec_indicator.configure(text=" IDLE ", bg=self._BG_LIGHT, fg=self._FG_DIM)
        self.root.title("Robot Automation Studio")
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
            "drag",
            "drag",
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
        self.editor.add_step("shortcut", "shortcut", {"shortcut": "CTRL+S"})
        self.refresh_steps()

    def add_menu(self) -> None:
        self.editor.add_step("menu", "menu", {"menu_path": "File>Save"})
        self.refresh_steps()

    def add_type(self) -> None:
        self.editor.add_step("type", "type", {"text": "sample"})
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
        self.step_list.selection_set(self.selected_index)

    def move_down(self) -> None:
        if self.selected_index is None:
            return
        self.editor.move_step_down(self.selected_index)
        self.selected_index = min(len(self.scenario.steps) - 1, self.selected_index + 1)
        self.refresh_steps()
        self.step_list.selection_set(self.selected_index)

    def duplicate_selected(self) -> None:
        if self.selected_index is None:
            return
        self.editor.duplicate_step(self.selected_index)
        self.refresh_steps()

    def save_json(self) -> None:
        self._sync_scenario_header()
        path = filedialog.asksaveasfilename(
            defaultextension=".scenario.json",
            filetypes=[("Scenario JSON", "*.scenario.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        target = Path(path)
        self.scenario.save_json(target)
        self.current_path = target
        self.log(f"Saved scenario: {target}")

    def load_json(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Scenario JSON", "*.scenario.json"), ("JSON", "*.json")]
        )
        if not path:
            return
        loaded = Scenario.load_json(Path(path))
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.name_var.set(loaded.name)
        self.window_hint_var.set(loaded.target_window_hint)
        self.execution_mode_var.set(
            normalize_unity_execution_mode(loaded.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach"))
        )
        self.unity_project_path_var.set(str(loaded.metadata.get(UNITY_PROJECT_PATH_KEY, "")))
        self.on_execution_mode_changed()
        self.current_path = Path(path)
        self.refresh_steps()
        self.log(f"Loaded scenario: {path}")

    def export_scenario(self) -> None:
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_var.get()).resolve()
        suite_name = self.export_name_var.get().strip() or "scenario"
        result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        self.log(f"Exported robot: {result.robot_path}")
        self.log(f"Exported json: {result.json_path}")

    def _is_robot_running(self) -> bool:
        return self._run_thread is not None and self._run_thread.is_alive()

    def run_robot_suite(self) -> None:
        if self.recorder.is_recording:
            self.log("Stop recording before running Robot suite.")
            messagebox.showerror(
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
        output_dir = Path(self.output_dir_var.get()).resolve()
        suite_name = self.export_name_var.get().strip() or "scenario"
        result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        artifacts_dir = output_dir / "run"
        variable_output = output_dir
        self._stop_requested = False
        self._set_run_phase("starting_robot")
        self._set_run_controls(running=True)
        self._start_stop_hotkey()
        self._start_overlay(mode="run", progress_text=self.robot_status_var.get())

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
                self.root.after(
                    0,
                    lambda: self._schedule_phase_promotion("attaching_unity", "running", 1800),
                )
                if self._stop_requested:
                    stop_robot_process(process)
                run_result = wait_robot_process(process)
            except Exception as error:  # pragma: no cover - integration path
                run_error = error
            finally:
                self._set_current_process(None)
                self.root.after(0, lambda: self._on_robot_run_finished(run_result, run_error))

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

    def on_close(self) -> None:
        if self.recorder.is_recording:
            self.stop_recording()
        if self._is_robot_running():
            self.stop_robot_suite()
            self.root.after(250, self.on_close)
            return
        self._stop_overlay()
        self._stop_stop_hotkey()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    StudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
