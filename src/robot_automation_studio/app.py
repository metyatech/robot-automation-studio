"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import json
import subprocess
import threading
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from pynput import keyboard as pynput_keyboard

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
from .ui_help import HelpEntry, build_help_entry, filter_help_entries
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


class _ToolTip:
    """Lightweight hover tooltip for any tkinter widget."""

    _DELAY_MS = 400

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add=True)
        widget.bind("<Leave>", self._cancel, add=True)

    def _schedule(self, _event: Any) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._DELAY_MS, self._show)

    def _cancel(self, _event: Any = None) -> None:
        if self._after_id is not None:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self) -> None:
        self._after_id = None
        if self._tip_window is not None:
            return
        x = self._widget.winfo_rootx() + 4
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self._text,
            background="#313150",
            foreground="#cdd6f4",
            font=("Segoe UI", 9),
            padx=6,
            pady=3,
            borderwidth=1,
            relief="solid",
        )
        label.pack()
        self._tip_window = tw

    def _hide(self) -> None:
        if self._tip_window is not None:
            self._tip_window.destroy()
            self._tip_window = None


class StudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Robot Automation Studio")
        self.root.geometry("1200x760")
        self.root.minsize(960, 640)

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.unity_bridge = UnityBridgeClient(timeout_seconds=0.1)
        self.recorder = ScenarioRecorder(
            on_record_error=self._on_record_error,
            unity_bridge=self.unity_bridge,
        )
        self.current_path: Path | None = None

        self.name_var = tk.StringVar(value=self.scenario.name)
        self.scenario_id_var = tk.StringVar(value=self.scenario.scenario_id)
        self.target_var = tk.StringVar(value=self.scenario.target)
        self.description_var = tk.StringVar(value=self.scenario.description)
        self.window_hint_var = tk.StringVar(value=self.scenario.target_window_hint)
        self.execution_mode_var = tk.StringVar(
            value=normalize_unity_execution_mode(
                self.scenario.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach")
            )
        )
        self.unity_project_path_var = tk.StringVar(
            value=str(self.scenario.metadata.get(UNITY_PROJECT_PATH_KEY, ""))
        )
        self.kind_var = tk.StringVar(value="action")
        self.control_var = tk.StringVar(value="")
        self.step_id_var = tk.StringVar(value="")
        self.step_description_var = tk.StringVar(value="")
        self.step_condition_var = tk.StringVar(value="")
        self.step_disabled_var = tk.BooleanVar(value=False)
        self.step_continue_on_error_var = tk.BooleanVar(value=False)
        self.output_dir_var = tk.StringVar(value="artifacts/studio")
        self.export_name_var = tk.StringVar(value="unity-editor-generated")
        self.log_var = tk.StringVar(value="")
        self.robot_status_var = tk.StringVar(value=format_run_status("idle", SPINNER_FRAMES[0]))
        self.help_status_var = tk.StringVar(
            value=(
                "Hover or focus any UI component to view its explanation. Press F1 for full guide."
            )
        )

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
        self._help_entries_by_widget: dict[tk.Widget, HelpEntry] = {}
        self._help_entries_by_id: dict[str, HelpEntry] = {}
        self._help_dialog: tk.Toplevel | None = None

        self._configure_theme()
        self._build_ui()
        self._register_help_for_widget_tree(self.root)
        self.root.bind("<F1>", self._on_help_hotkey, add=True)
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
        style.map(
            "TEntry",
            lightcolor=[("focus", self._ACCENT_BLUE)],
            bordercolor=[("focus", self._ACCENT_BLUE)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=self._BG_MID,
            foreground=self._FG,
            background=self._BTN_BG,
            arrowcolor=self._FG,
        )
        style.map(
            "TCombobox",
            lightcolor=[("focus", self._ACCENT_BLUE)],
            bordercolor=[("focus", self._ACCENT_BLUE)],
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

        # Section header style
        style.configure(
            "Section.TLabel",
            background=self._BG,
            foreground=self._ACCENT_BLUE,
            font=("Segoe UI", 11, "bold"),
        )

        # Toolbar group label style
        style.configure(
            "GroupLabel.TLabel",
            background=self._BG,
            foreground=self._FG_DIM,
            font=("Segoe UI", 8),
        )

        # Apply button style (accent blue)
        style.configure(
            "Apply.TButton",
            background="#2d4a7a",
            foreground=self._ACCENT_BLUE,
            padding=(8, 6),
        )
        style.map(
            "Apply.TButton",
            background=[("active", "#3a5a9a"), ("disabled", self._BG_LIGHT)],
        )

        # Card frame style
        style.configure("Card.TFrame", background=self._BG_MID)
        style.configure(
            "Card.TLabel",
            background=self._BG_MID,
            foreground=self._FG,
            font=self._FONT,
        )
        style.configure(
            "CardHeader.TLabel",
            background=self._BG_MID,
            foreground=self._ACCENT_BLUE,
            font=("Segoe UI", 10, "bold"),
        )

        self.root.configure(bg=self._BG)

    def _section_header(self, parent: tk.Misc, text: str) -> ttk.Frame:
        """Create a section header (bold label + separator) and return a content frame."""
        header_row = ttk.Frame(parent)
        header_row.pack(fill=tk.X, padx=12, pady=(12, 0))
        ttk.Label(header_row, text=text, style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Separator(header_row, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=1
        )
        content = ttk.Frame(parent)
        content.pack(fill=tk.X, padx=12, pady=(4, 0))
        return content

    def _toolbar_group(self, parent: tk.Misc, label: str, *, first: bool = False) -> ttk.Frame:
        """Create a labeled toolbar button group and return the button container."""
        if not first:
            ttk.Separator(parent, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        group = ttk.Frame(parent)
        group.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(group, text=label, style="GroupLabel.TLabel").pack(anchor=tk.W)
        btn_row = ttk.Frame(group)
        btn_row.pack()
        return btn_row

    def _on_help_hotkey(self, _event: Any = None) -> str:
        self.open_help_guide()
        return "break"

    def _set_help_status(self, message: str) -> None:
        text = str(message).strip()
        if text == "":
            text = (
                "Hover or focus any UI component to view its explanation. Press F1 for full guide."
            )
        self.help_status_var.set(text)

    def _widget_text(self, widget: tk.Widget) -> str:
        try:
            value = widget.cget("text")
            if isinstance(value, str) and value.strip() != "":
                return value.strip()
        except tk.TclError:
            pass

        try:
            value = widget.cget("label")
            if isinstance(value, str) and value.strip() != "":
                return value.strip()
        except tk.TclError:
            pass

        return ""

    def _widget_help_id(self, widget: tk.Widget) -> str:
        return str(widget)

    def _register_help_for_widget(
        self,
        widget: tk.Widget,
        *,
        widget_id: str | None = None,
        explicit_summary: str | None = None,
        explicit_detail: str | None = None,
    ) -> None:
        if widget in self._help_entries_by_widget:
            return

        actual_widget_id = widget_id or self._widget_help_id(widget)
        entry = build_help_entry(
            widget_id=actual_widget_id,
            widget_class=widget.winfo_class(),
            widget_text=self._widget_text(widget),
            explicit_summary=explicit_summary,
            explicit_detail=explicit_detail,
        )
        self._help_entries_by_widget[widget] = entry
        self._help_entries_by_id[entry.widget_id] = entry

        widget.bind(
            "<Enter>",
            lambda _event, summary=entry.summary: self._set_help_status(summary),
            add=True,
        )
        widget.bind(
            "<FocusIn>",
            lambda _event, summary=entry.summary: self._set_help_status(summary),
            add=True,
        )

    def _iter_widgets(self, root_widget: tk.Misc) -> list[tk.Widget]:
        widgets: list[tk.Widget] = []
        stack = [root_widget]
        while stack:
            current = stack.pop(0)
            if isinstance(current, tk.Widget):
                widgets.append(current)
            for child in current.winfo_children():
                stack.append(child)
        return widgets

    def _register_help_for_widget_tree(self, root_widget: tk.Misc) -> None:
        for widget in self._iter_widgets(root_widget):
            self._register_help_for_widget(widget)

    def _sorted_help_entries(self) -> list[HelpEntry]:
        return sorted(
            self._help_entries_by_id.values(),
            key=lambda item: (item.title.lower(), item.widget_class.lower(), item.widget_id),
        )

    def open_help_guide(self) -> None:
        if self._help_dialog is not None and self._help_dialog.winfo_exists():
            self._help_dialog.lift()
            self._help_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("GUI Help Guide")
        dialog.geometry("980x640")
        dialog.transient(self.root)
        self._help_dialog = dialog

        container = ttk.Frame(dialog, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(container)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="Search", style="Card.TLabel").pack(side=tk.LEFT)
        search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(top, textvariable=search_var, width=48)
        search_entry.pack(side=tk.LEFT, padx=(8, 8))

        summary_var = tk.StringVar(
            value=f"{len(self._help_entries_by_id)} UI components are documented."
        )
        ttk.Label(top, textvariable=summary_var, style="Card.TLabel").pack(side=tk.LEFT)

        body = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)

        listbox = tk.Listbox(
            left,
            bg=self._BG_MID,
            fg=self._FG,
            selectbackground=self._ACCENT_BLUE,
            selectforeground=self._BG,
            font=self._FONT,
            borderwidth=0,
            highlightthickness=0,
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=listbox.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.configure(yscrollcommand=list_scroll.set)

        detail_text = tk.Text(
            right,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.WORD,
        )
        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=detail_text.yview)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        detail_text.configure(yscrollcommand=detail_scroll.set)

        visible_entries: list[HelpEntry] = []

        def _render_details(entry: HelpEntry) -> None:
            detail_text.delete("1.0", tk.END)
            detail_text.insert(
                "1.0",
                (
                    f"Title: {entry.title}\n"
                    f"Widget Class: {entry.widget_class}\n"
                    f"Widget ID: {entry.widget_id}\n\n"
                    f"Summary:\n{entry.summary}\n\n"
                    f"Details:\n{entry.detail}\n"
                ),
            )

        def _refresh_list() -> None:
            visible_entries.clear()
            listbox.delete(0, tk.END)
            filtered = filter_help_entries(self._sorted_help_entries(), search_var.get())
            for entry in filtered:
                visible_entries.append(entry)
                listbox.insert(tk.END, f"{entry.title} [{entry.widget_class}]")
            summary_var.set(f"{len(filtered)} / {len(self._help_entries_by_id)} components shown.")
            if visible_entries:
                listbox.selection_set(0)
                listbox.activate(0)
                _render_details(visible_entries[0])
            else:
                detail_text.delete("1.0", tk.END)
                detail_text.insert("1.0", "No matching components.")

        def _on_select(_event: Any = None) -> None:
            selected = listbox.curselection()
            if not selected:
                return
            index = int(selected[0])
            if index < 0 or index >= len(visible_entries):
                return
            _render_details(visible_entries[index])

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(footer, text="Close", command=self._close_help_dialog).pack(side=tk.RIGHT)

        search_var.trace_add("write", lambda *_args: _refresh_list())
        listbox.bind("<<ListboxSelect>>", _on_select)
        dialog.bind("<Escape>", lambda _event: self._close_help_dialog())
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._close_help_dialog())

        self._register_help_for_widget_tree(dialog)
        _refresh_list()
        search_entry.focus_set()

    def _close_help_dialog(self) -> None:
        if self._help_dialog is None:
            return
        if self._help_dialog.winfo_exists():
            self._help_dialog.destroy()
        self._help_dialog = None

    def _build_ui(self) -> None:
        # ── A. Scenario Configuration ──────────────────────────────────────
        config_header_row = ttk.Frame(self.root)
        config_header_row.pack(fill=tk.X, padx=12, pady=(12, 0))
        ttk.Label(config_header_row, text="Scenario Configuration", style="Section.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Separator(config_header_row, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=1
        )
        self.open_guide_button = ttk.Button(
            config_header_row,
            text="Open Guide (F1)",
            command=self.open_help_guide,
        )
        self.open_guide_button.pack(side=tk.RIGHT)
        config_card = ttk.Frame(self.root, style="Card.TFrame", padding=12)
        config_card.pack(fill=tk.X, padx=12, pady=(4, 0))

        ttk.Label(config_card, text="Scenario Name", style="Card.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4)
        )
        ttk.Entry(config_card, textvariable=self.name_var, width=40).grid(
            row=0, column=1, sticky=tk.W, padx=6, pady=(0, 4)
        )
        ttk.Label(config_card, text="Scenario ID", style="Card.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=(20, 0), pady=(0, 4)
        )
        ttk.Entry(config_card, textvariable=self.scenario_id_var, width=24).grid(
            row=0, column=3, sticky=tk.W, padx=6, pady=(0, 4)
        )
        ttk.Label(config_card, text="Target", style="Card.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(4, 0)
        )
        target_combo = ttk.Combobox(
            config_card,
            textvariable=self.target_var,
            values=("unity", "web", "desktop", "hybrid"),
            state="readonly",
            width=14,
        )
        target_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(4, 0))
        ttk.Label(config_card, text="Window Hint", style="Card.TLabel").grid(
            row=1, column=2, sticky=tk.W, padx=(20, 0), pady=(4, 0)
        )
        ttk.Entry(config_card, textvariable=self.window_hint_var, width=24).grid(
            row=1, column=3, sticky=tk.W, padx=6, pady=(4, 0)
        )
        ttk.Label(config_card, text="Execution Mode", style="Card.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=(4, 0)
        )
        mode_combo = ttk.Combobox(
            config_card,
            textvariable=self.execution_mode_var,
            values=("attach", "launch"),
            state="readonly",
            width=14,
        )
        mode_combo.grid(row=2, column=1, sticky=tk.W, padx=6, pady=(4, 0))
        mode_combo.bind("<<ComboboxSelected>>", self.on_execution_mode_changed)
        ttk.Label(config_card, text="Unity Project Path", style="Card.TLabel").grid(
            row=2, column=2, sticky=tk.W, padx=(20, 0), pady=(4, 0)
        )
        self.project_path_entry = ttk.Entry(
            config_card, textvariable=self.unity_project_path_var, width=44
        )
        self.project_path_entry.grid(row=2, column=3, sticky=tk.W, padx=6, pady=(4, 0))
        self.project_path_browse_button = ttk.Button(
            config_card, text="Browse", command=self.browse_unity_project_path
        )
        self.project_path_browse_button.grid(row=2, column=4, sticky=tk.W, pady=(4, 0))
        ttk.Label(config_card, text="Description", style="Card.TLabel").grid(
            row=3, column=0, sticky=tk.W, pady=(4, 0)
        )
        ttk.Entry(config_card, textvariable=self.description_var, width=82).grid(
            row=3, column=1, columnspan=3, sticky=tk.W, padx=6, pady=(4, 0)
        )
        config_tools = ttk.Frame(config_card, style="Card.TFrame")
        config_tools.grid(row=4, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))
        ttk.Button(config_tools, text="Variables", command=self.open_variables_editor).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(config_tools, text="Profiles", command=self.open_profiles_editor).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            config_tools,
            text="Execution/Outputs",
            command=self.open_execution_outputs_editor,
        ).pack(side=tk.LEFT, padx=(0, 6))

        help_card = ttk.Frame(self.root, style="Card.TFrame", padding=8)
        help_card.pack(fill=tk.X, padx=12, pady=(8, 0))
        ttk.Label(help_card, text="Context Help", style="CardHeader.TLabel").pack(side=tk.LEFT)
        self.help_status_label = ttk.Label(
            help_card,
            textvariable=self.help_status_var,
            style="Card.TLabel",
        )
        self.help_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        # ── B. Toolbar ─────────────────────────────────────────────────────
        toolbar_outer = ttk.Frame(self.root)
        toolbar_outer.pack(fill=tk.X, padx=12, pady=(12, 4))

        # Recording group
        rec_group = self._toolbar_group(toolbar_outer, "Recording", first=True)
        btn = ttk.Button(
            rec_group,
            text="\u25cf Start",
            command=self.start_recording,
            style="Record.TButton",
        )
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Start recording UI actions")
        btn = ttk.Button(
            rec_group,
            text="\u25a0 Stop",
            command=self.stop_recording,
            style="Stop.TButton",
        )
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Stop recording")

        # Add steps group
        add_group = self._toolbar_group(toolbar_outer, "Add Step")
        for label, tip, cmd in [
            ("\U0001f5b1 Click", "Add a click step", self.add_click),
            ("\u2194 Drag", "Add a drag step", self.add_drag),
            ("\u2328 Shortcut", "Add a keyboard shortcut step", self.add_shortcut),
            ("\u2261 Menu", "Add a menu navigation step", self.add_menu),
            ("\u270e Type", "Add a text typing step", self.add_type),
            ("IF", "Add a control step", self.add_control),
            ("[] Group", "Add a group step", self.add_group),
        ]:
            btn = ttk.Button(add_group, text=label, command=cmd, style="Add.TButton")
            btn.pack(side=tk.LEFT, padx=2)
            _ToolTip(btn, tip)

        # Edit steps group
        edit_group = self._toolbar_group(toolbar_outer, "Edit")
        btn = ttk.Button(
            edit_group, text="\u2715 Delete", command=self.delete_selected, style="Danger.TButton"
        )
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Delete selected step")
        btn = ttk.Button(edit_group, text="\u25b2 Up", command=self.move_up)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Move step up")
        btn = ttk.Button(edit_group, text="\u25bc Down", command=self.move_down)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Move step down")
        btn = ttk.Button(edit_group, text="\u2398 Duplicate", command=self.duplicate_selected)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Duplicate selected step")

        # File group
        file_group = self._toolbar_group(toolbar_outer, "File")
        btn = ttk.Button(file_group, text="\U0001f4be Save", command=self.save_json)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Save scenario as JSON")
        btn = ttk.Button(file_group, text="\U0001f4c2 Load", command=self.load_json)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Load scenario from JSON")
        btn = ttk.Button(file_group, text="{} Full JSON", command=self.open_full_json_editor)
        btn.pack(side=tk.LEFT, padx=2)
        _ToolTip(btn, "Edit full v2 scenario JSON")

        # REC indicator (right-aligned)
        self._rec_indicator = tk.Label(
            toolbar_outer,
            text=" IDLE ",
            font=("Segoe UI", 9, "bold"),
            bg=self._BG_LIGHT,
            fg=self._FG_DIM,
            padx=8,
            pady=2,
        )
        self._rec_indicator.pack(side=tk.RIGHT, padx=4)

        # ── C. Steps & Editor ──────────────────────────────────────────────
        # Section header (non-expanding)
        steps_header_row = ttk.Frame(self.root)
        steps_header_row.pack(fill=tk.X, padx=12, pady=(12, 0))
        ttk.Label(steps_header_row, text="Steps & Editor", style="Section.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Separator(steps_header_row, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=1
        )

        steps_body = ttk.Frame(self.root)
        steps_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 0))

        body = ttk.Panedwindow(steps_body, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        # Step list with 1px border wrapper and scrollbar
        list_border = tk.Frame(left, bg=self._BG_LIGHT, padx=1, pady=1)
        list_border.pack(fill=tk.BOTH, expand=True)
        list_frame = ttk.Frame(list_border)
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
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=step_scroll.set,
        )
        self.step_list.pack(fill=tk.BOTH, expand=True)
        step_scroll.configure(command=self.step_list.yview)
        self.step_list.bind("<<ListboxSelect>>", self.on_select_step)

        # Step editor card (right pane)
        card = ttk.Frame(right, style="Card.TFrame", padding=12)
        card.pack(fill=tk.BOTH, expand=True, padx=(8, 0))
        ttk.Label(card, text="Step Details", style="CardHeader.TLabel").pack(
            anchor=tk.W, pady=(0, 8)
        )

        edit_row = ttk.Frame(card, style="Card.TFrame")
        edit_row.pack(fill=tk.X)
        ttk.Label(edit_row, text="Step ID", style="Card.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 8)
        )
        ttk.Entry(edit_row, textvariable=self.step_id_var, width=32).grid(
            row=0, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(edit_row, text="Title", style="Card.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=(0, 8)
        )
        self.title_var = tk.StringVar(value="")
        ttk.Entry(edit_row, textvariable=self.title_var, width=32).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(edit_row, text="Kind", style="Card.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=(0, 8)
        )
        ttk.Combobox(
            edit_row,
            textvariable=self.kind_var,
            values=("action", "control", "group"),
            state="readonly",
            width=29,
        ).grid(row=2, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8))
        ttk.Label(edit_row, text="Action", style="Card.TLabel").grid(
            row=3, column=0, sticky=tk.W, pady=(0, 8)
        )
        self.action_var = tk.StringVar(value="")
        ttk.Entry(edit_row, textvariable=self.action_var, width=32).grid(
            row=3, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(edit_row, text="Control", style="Card.TLabel").grid(
            row=4, column=0, sticky=tk.W, pady=(0, 8)
        )
        ttk.Entry(edit_row, textvariable=self.control_var, width=32).grid(
            row=4, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(edit_row, text="Description", style="Card.TLabel").grid(
            row=5, column=0, sticky=tk.W, pady=(0, 8)
        )
        ttk.Entry(edit_row, textvariable=self.step_description_var, width=32).grid(
            row=5, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(edit_row, text="Condition", style="Card.TLabel").grid(
            row=6, column=0, sticky=tk.W, pady=(0, 8)
        )
        ttk.Entry(edit_row, textvariable=self.step_condition_var, width=32).grid(
            row=6, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8)
        )
        ttk.Checkbutton(
            edit_row,
            text="Disabled",
            variable=self.step_disabled_var,
        ).grid(row=7, column=0, sticky=tk.W, pady=(0, 8))
        ttk.Checkbutton(
            edit_row,
            text="Continue On Error",
            variable=self.step_continue_on_error_var,
        ).grid(row=7, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8))
        ttk.Label(edit_row, text="Annotations (JSON)", style="Card.TLabel").grid(
            row=8, column=0, sticky=tk.NW, pady=(0, 8)
        )
        self.annotations_text = tk.Text(
            edit_row,
            width=42,
            height=4,
            bg=self._BG_LIGHT,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        self.annotations_text.grid(row=8, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8))
        ttk.Label(edit_row, text="Params (JSON)", style="Card.TLabel").grid(
            row=9, column=0, sticky=tk.NW, pady=(0, 8)
        )
        self.params_text = tk.Text(
            edit_row,
            width=42,
            height=8,
            bg=self._BG_LIGHT,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO,
            borderwidth=0,
            highlightthickness=0,
        )
        self.params_text.grid(row=9, column=1, sticky=tk.W, padx=(8, 0), pady=(0, 8))

        ttk.Button(
            card, text="Apply Step Changes", command=self.apply_step_changes, style="Apply.TButton"
        ).pack(fill=tk.X, pady=(4, 0))

        # ── D. Export & Run ────────────────────────────────────────────────
        # Section header
        run_header_row = ttk.Frame(self.root)
        run_header_row.pack(fill=tk.X, padx=12, pady=(12, 0))
        ttk.Label(run_header_row, text="Export & Run", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Separator(run_header_row, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=1
        )

        run_card = ttk.Frame(self.root, style="Card.TFrame", padding=12)
        run_card.pack(fill=tk.X, padx=12, pady=(4, 0))

        # Row 1: Output Dir + Export Name + Export button
        row1 = ttk.Frame(run_card, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row1, text="Output Dir", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.output_dir_var, width=48).pack(side=tk.LEFT, padx=(8, 12))
        ttk.Label(row1, text="Export Name", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.export_name_var, width=24).pack(
            side=tk.LEFT, padx=(8, 12)
        )
        ttk.Button(row1, text="Export", command=self.export_scenario).pack(side=tk.LEFT)

        # Row 2: Run / Stop buttons + Status pill
        row2 = ttk.Frame(run_card, style="Card.TFrame")
        row2.pack(fill=tk.X)
        self.run_robot_button = ttk.Button(
            row2, text="Run Robot", command=self.run_robot_suite, style="Record.TButton"
        )
        self.run_robot_button.pack(side=tk.LEFT, padx=(0, 4))
        self.stop_robot_button = ttk.Button(
            row2,
            text=f"Stop Robot ({STOP_HOTKEY_LABEL})",
            command=self.stop_robot_suite,
            state="disabled",
            style="Stop.TButton",
        )
        self.stop_robot_button.pack(side=tk.LEFT, padx=(0, 12))

        # Status pill
        self._status_pill = tk.Label(
            row2,
            textvariable=self.robot_status_var,
            font=("Segoe UI", 10, "bold"),
            bg=self._BG_LIGHT,
            fg=self._FG_DIM,
            padx=14,
            pady=3,
        )
        self._status_pill.pack(side=tk.LEFT, padx=4)

        # ── E. Output Log ──────────────────────────────────────────────────
        log_header_row = ttk.Frame(self.root)
        log_header_row.pack(fill=tk.X, padx=12, pady=(12, 0))
        ttk.Label(log_header_row, text="Output Log", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Separator(log_header_row, orient=tk.HORIZONTAL).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=1
        )
        log_outer = ttk.Frame(self.root)
        log_outer.pack(fill=tk.BOTH, padx=12, pady=(4, 12))
        log_border = tk.Frame(log_outer, bg=self._BG_LIGHT, padx=1, pady=1)
        log_border.pack(fill=tk.BOTH, expand=True)
        log_frame = ttk.Frame(log_border)
        log_frame.pack(fill=tk.BOTH, expand=True)

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
        self.scenario.scenario_id = self.scenario_id_var.get().strip() or self.scenario.scenario_id
        self.scenario.target = self.target_var.get().strip() or "unity"
        self.scenario.description = self.description_var.get().strip()
        self.scenario.target_window_hint = self.window_hint_var.get().strip() or "Unity"
        execution_mode = normalize_unity_execution_mode(self.execution_mode_var.get())
        self.execution_mode_var.set(execution_mode)
        unity_project_path = self.unity_project_path_var.get().strip()
        self.scenario.sync_runtime_metadata(
            execution_mode=execution_mode,
            unity_project_path=unity_project_path,
        )

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
            bg = self._BG_LIGHT
            fg = self._FG_DIM
        elif phase == "stopping":
            bg = "#5a2d2d"
            fg = self._ACCENT_RED
        else:
            bg = "#4a3d1a"
            fg = self._ACCENT_YELLOW
        self._status_pill.configure(bg=bg, fg=fg)

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
            label = (
                step.action
                if step.kind == "action"
                else step.control
                if step.kind == "control"
                else "group"
            )
            self.step_list.insert(tk.END, f"{idx + 1}. [{step.kind}] {label} - {step.title}")

    def on_select_step(self, _event: Any = None) -> None:
        selection = self.step_list.curselection()
        if not selection:
            self.selected_index = None
            self.step_id_var.set("")
            self.title_var.set("")
            self.kind_var.set("action")
            self.action_var.set("")
            self.control_var.set("")
            self.step_description_var.set("")
            self.step_condition_var.set("")
            self.step_disabled_var.set(False)
            self.step_continue_on_error_var.set(False)
            self.annotations_text.delete("1.0", tk.END)
            self.params_text.delete("1.0", tk.END)
            return
        index = int(selection[0])
        self.selected_index = index
        step = self.scenario.steps[index]
        self.step_id_var.set(step.id)
        self.title_var.set(step.title)
        self.kind_var.set(step.kind)
        self.action_var.set(step.action)
        self.control_var.set(step.control)
        self.step_description_var.set(step.description)
        self.step_condition_var.set(step.condition)
        self.step_disabled_var.set(step.disabled)
        self.step_continue_on_error_var.set(step.continue_on_error)
        self.annotations_text.delete("1.0", tk.END)
        self.annotations_text.insert(
            "1.0", json.dumps(step.annotations, ensure_ascii=False, indent=2)
        )
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
        package_script_meta_detected = False

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
                    messagebox.showerror(
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
                        self.window_hint_var.get().strip() or "Unity"
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
                        self.window_hint_var.get().strip() or "Unity"
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
                                    self.window_hint_var.get().strip() or "Unity"
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
                messagebox.showerror(
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
            messagebox.showerror("Invalid Params JSON", str(error))
            return
        try:
            annotations = json.loads(self.annotations_text.get("1.0", tk.END).strip() or "[]")
        except json.JSONDecodeError as error:
            messagebox.showerror("Invalid Annotations JSON", str(error))
            return
        if not isinstance(params, dict):
            messagebox.showerror("Invalid Params JSON", "Params must be a JSON object.")
            return
        if not isinstance(annotations, list):
            messagebox.showerror("Invalid Annotations JSON", "Annotations must be a JSON array.")
            return
        kind = self.kind_var.get().strip().lower() or "action"
        action = self.action_var.get().strip()
        control = self.control_var.get().strip()
        if kind == "action" and action == "":
            action = self.scenario.steps[self.selected_index].action or "click"
        if kind == "control" and control == "":
            control = self.scenario.steps[self.selected_index].control or "if"
        self.editor.update_step(
            self.selected_index,
            title=self.title_var.get().strip(),
            kind=kind,
            action=action if kind == "action" else None,
            control=control if kind == "control" else None,
            description=self.step_description_var.get().strip(),
            condition=self.step_condition_var.get().strip(),
            disabled=self.step_disabled_var.get(),
            continue_on_error=self.step_continue_on_error_var.get(),
            annotations=[dict(item) for item in annotations if isinstance(item, dict)],
            params=params,
        )
        step_id = self.step_id_var.get().strip()
        if step_id != "":
            self.scenario.steps[self.selected_index].id = step_id
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
        try:
            loaded = Scenario.load_json(Path(path))
        except Exception as error:
            messagebox.showerror("Load Error", str(error))
            self.log(f"Load failed: {error}")
            return
        self._apply_loaded_scenario(loaded)
        self.current_path = Path(path)
        self.log(f"Loaded scenario: {path}")

    def _apply_loaded_scenario(self, loaded: Scenario) -> None:
        self.scenario = loaded
        self.editor = ScenarioEditor(self.scenario)
        self.selected_index = None
        self.name_var.set(loaded.name)
        self.scenario_id_var.set(loaded.scenario_id)
        self.target_var.set(loaded.target)
        self.description_var.set(loaded.description)
        self.window_hint_var.set(loaded.target_window_hint)
        self.execution_mode_var.set(
            normalize_unity_execution_mode(loaded.metadata.get(UNITY_EXECUTION_MODE_KEY, "attach"))
        )
        self.unity_project_path_var.set(str(loaded.metadata.get(UNITY_PROJECT_PATH_KEY, "")))
        self.on_execution_mode_changed()
        self.refresh_steps()
        self.on_select_step()

    def open_full_json_editor(self) -> None:
        self._sync_scenario_header()
        dialog = tk.Toplevel(self.root)
        dialog.title("Full Scenario JSON (v2)")
        dialog.geometry("960x720")
        dialog.transient(self.root)

        top_row = ttk.Frame(dialog, padding=8)
        top_row.pack(fill=tk.X)
        body = ttk.Frame(dialog, padding=(8, 0, 8, 8))
        body.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(
            body,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.insert("1.0", json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))

        def _format_json() -> None:
            try:
                payload = json.loads(text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid JSON", str(error), parent=dialog)
                return
            text.delete("1.0", tk.END)
            text.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))

        def _reload_model() -> None:
            self._sync_scenario_header()
            text.delete("1.0", tk.END)
            text.insert("1.0", json.dumps(self.scenario.to_dict(), ensure_ascii=False, indent=2))

        def _apply_json() -> None:
            try:
                payload = json.loads(text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid JSON", str(error), parent=dialog)
                return
            try:
                loaded = Scenario.from_dict(payload)
            except Exception as error:
                messagebox.showerror("Validation Error", str(error), parent=dialog)
                return
            self._apply_loaded_scenario(loaded)
            self.log("Applied full scenario JSON editor changes.")
            dialog.destroy()

        ttk.Button(top_row, text="Format", command=_format_json).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top_row, text="Reload Model", command=_reload_model).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top_row, text="Apply", command=_apply_json, style="Apply.TButton").pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )
        ttk.Button(top_row, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        self._register_help_for_widget_tree(dialog)

    def open_variables_editor(self) -> None:
        self._sync_scenario_header()
        dialog = tk.Toplevel(self.root)
        dialog.title("Variables Editor")
        dialog.geometry("980x620")
        dialog.transient(self.root)

        variables = [deepcopy(item) for item in self.scenario.variables if isinstance(item, dict)]
        body = ttk.Frame(dialog, padding=8)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        listbox = tk.Listbox(left, width=36, height=24, bg=self._BG_MID, fg=self._FG)
        listbox.pack(fill=tk.Y, expand=True)

        text = tk.Text(
            right,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _refresh_list() -> None:
            listbox.delete(0, tk.END)
            for index, variable in enumerate(variables):
                variable_id = str(variable.get("id") or f"var-{index + 1}")
                variable_type = str(variable.get("type") or "string")
                listbox.insert(tk.END, f"{index + 1}. {variable_id} ({variable_type})")

        def _select(index: int) -> None:
            if index < 0 or index >= len(variables):
                return
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.activate(index)
            text.delete("1.0", tk.END)
            text.insert("1.0", json.dumps(variables[index], ensure_ascii=False, indent=2))

        def _on_select(_event: Any = None) -> None:
            selected = listbox.curselection()
            if not selected:
                return
            _select(int(selected[0]))

        def _apply_current() -> bool:
            selected = listbox.curselection()
            if not selected:
                return True
            index = int(selected[0])
            try:
                payload = json.loads(text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid Variable JSON", str(error), parent=dialog)
                return False
            if not isinstance(payload, dict):
                messagebox.showerror(
                    "Invalid Variable JSON",
                    "Variable must be a JSON object.",
                    parent=dialog,
                )
                return False
            if str(payload.get("id") or "").strip() == "":
                messagebox.showerror(
                    "Invalid Variable JSON",
                    "Variable id is required.",
                    parent=dialog,
                )
                return False
            if str(payload.get("type") or "").strip() == "":
                messagebox.showerror(
                    "Invalid Variable JSON",
                    "Variable type is required.",
                    parent=dialog,
                )
                return False
            variables[index] = payload
            _refresh_list()
            _select(index)
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
            selected = listbox.curselection()
            if not selected:
                return
            index = int(selected[0])
            variables.pop(index)
            _refresh_list()
            if variables:
                _select(min(index, len(variables) - 1))
            else:
                text.delete("1.0", tk.END)

        def _save_and_close() -> None:
            if not _apply_current():
                return
            self.scenario.variables = variables
            self.log("Updated variables from Variables Editor.")
            dialog.destroy()

        footer = ttk.Frame(dialog, padding=8)
        footer.pack(fill=tk.X)
        ttk.Button(footer, text="Add", command=_add_variable).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Delete", command=_delete_variable).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            footer,
            text="Apply Current",
            command=_apply_current,
            style="Apply.TButton",
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Save", command=_save_and_close, style="Apply.TButton").pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )
        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        listbox.bind("<<ListboxSelect>>", _on_select)
        _refresh_list()
        if variables:
            _select(0)
        self._register_help_for_widget_tree(dialog)

    def open_profiles_editor(self) -> None:
        self._sync_scenario_header()
        dialog = tk.Toplevel(self.root)
        dialog.title("Profiles Editor")
        dialog.geometry("980x620")
        dialog.transient(self.root)

        profiles = dict(self.scenario.profiles or {})
        profile_names = sorted(profiles.keys())
        body = ttk.Frame(dialog, padding=8)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        listbox = tk.Listbox(left, width=36, height=24, bg=self._BG_MID, fg=self._FG)
        listbox.pack(fill=tk.Y, expand=True)

        text = tk.Text(
            right,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _refresh_list() -> None:
            listbox.delete(0, tk.END)
            for index, name in enumerate(profile_names):
                listbox.insert(tk.END, f"{index + 1}. {name}")

        def _select(index: int) -> None:
            if index < 0 or index >= len(profile_names):
                return
            name = profile_names[index]
            payload = deepcopy(profiles.get(name, {}))
            profile_payload = {"name": name, "profile": payload}
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.activate(index)
            text.delete("1.0", tk.END)
            text.insert("1.0", json.dumps(profile_payload, ensure_ascii=False, indent=2))

        def _on_select(_event: Any = None) -> None:
            selected = listbox.curselection()
            if not selected:
                return
            _select(int(selected[0]))

        def _apply_current() -> bool:
            selected = listbox.curselection()
            if not selected:
                return True
            current_index = int(selected[0])
            current_name = profile_names[current_index]
            try:
                payload = json.loads(text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid Profile JSON", str(error), parent=dialog)
                return False
            if not isinstance(payload, dict):
                messagebox.showerror(
                    "Invalid Profile JSON",
                    "Profile payload must be a JSON object.",
                    parent=dialog,
                )
                return False
            name = str(payload.get("name") or "").strip()
            profile = payload.get("profile")
            if name == "":
                messagebox.showerror(
                    "Invalid Profile JSON", "Profile name is required.", parent=dialog
                )
                return False
            if not isinstance(profile, dict):
                messagebox.showerror(
                    "Invalid Profile JSON",
                    "profile field must be a JSON object.",
                    parent=dialog,
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
            selected = listbox.curselection()
            if not selected:
                return
            index = int(selected[0])
            name = profile_names[index]
            profiles.pop(name, None)
            profile_names[:] = sorted(profiles.keys())
            _refresh_list()
            if profile_names:
                _select(min(index, len(profile_names) - 1))
            else:
                text.delete("1.0", tk.END)

        def _save_and_close() -> None:
            if not _apply_current():
                return
            self.scenario.profiles = profiles
            self.log("Updated profiles from Profiles Editor.")
            dialog.destroy()

        footer = ttk.Frame(dialog, padding=8)
        footer.pack(fill=tk.X)
        ttk.Button(footer, text="Add", command=_add_profile).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Delete", command=_delete_profile).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            footer,
            text="Apply Current",
            command=_apply_current,
            style="Apply.TButton",
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Save", command=_save_and_close, style="Apply.TButton").pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )
        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        listbox.bind("<<ListboxSelect>>", _on_select)
        _refresh_list()
        if profile_names:
            _select(0)
        self._register_help_for_widget_tree(dialog)

    def open_execution_outputs_editor(self) -> None:
        self._sync_scenario_header()
        dialog = tk.Toplevel(self.root)
        dialog.title("Execution / Outputs Editor")
        dialog.geometry("980x720")
        dialog.transient(self.root)

        container = ttk.Frame(dialog, padding=8)
        container.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(container)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="Execution / Outputs JSON", style="CardHeader.TLabel").pack(
            side=tk.LEFT
        )

        splitter = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        splitter.pack(fill=tk.BOTH, expand=True)
        execution_frame = ttk.Frame(splitter)
        outputs_frame = ttk.Frame(splitter)
        splitter.add(execution_frame, weight=1)
        splitter.add(outputs_frame, weight=1)

        ttk.Label(execution_frame, text="execution", style="Card.TLabel").pack(anchor=tk.W)
        execution_text = tk.Text(
            execution_frame,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        execution_scroll = ttk.Scrollbar(
            execution_frame, orient=tk.VERTICAL, command=execution_text.yview
        )
        execution_text.configure(yscrollcommand=execution_scroll.set)
        execution_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        execution_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(outputs_frame, text="outputs", style="Card.TLabel").pack(anchor=tk.W)
        outputs_text = tk.Text(
            outputs_frame,
            bg=self._LOG_BG,
            fg=self._FG,
            insertbackground=self._FG,
            font=self._FONT_MONO_SM,
            borderwidth=0,
            highlightthickness=0,
        )
        outputs_scroll = ttk.Scrollbar(
            outputs_frame, orient=tk.VERTICAL, command=outputs_text.yview
        )
        outputs_text.configure(yscrollcommand=outputs_scroll.set)
        outputs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        outputs_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        execution_text.insert(
            "1.0", json.dumps(self.scenario.execution, ensure_ascii=False, indent=2)
        )
        outputs_text.insert("1.0", json.dumps(self.scenario.outputs, ensure_ascii=False, indent=2))

        def _apply() -> bool:
            try:
                execution_payload = json.loads(execution_text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid execution JSON", str(error), parent=dialog)
                return False
            try:
                outputs_payload = json.loads(outputs_text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid outputs JSON", str(error), parent=dialog)
                return False
            if not isinstance(execution_payload, dict):
                messagebox.showerror(
                    "Invalid execution JSON", "execution must be object.", parent=dialog
                )
                return False
            if not isinstance(outputs_payload, dict):
                messagebox.showerror(
                    "Invalid outputs JSON", "outputs must be object.", parent=dialog
                )
                return False
            self.scenario.execution = execution_payload
            self.scenario.outputs = outputs_payload
            mode = str(execution_payload.get("mode") or "").strip().lower()
            if mode in {"attach", "launch"}:
                self.execution_mode_var.set(mode)
            self.log("Updated execution/outputs from editor.")
            return True

        def _format() -> None:
            try:
                execution_payload = json.loads(execution_text.get("1.0", tk.END).strip() or "{}")
                outputs_payload = json.loads(outputs_text.get("1.0", tk.END).strip() or "{}")
            except json.JSONDecodeError as error:
                messagebox.showerror("Invalid JSON", str(error), parent=dialog)
                return
            execution_text.delete("1.0", tk.END)
            execution_text.insert(
                "1.0",
                json.dumps(execution_payload, ensure_ascii=False, indent=2),
            )
            outputs_text.delete("1.0", tk.END)
            outputs_text.insert(
                "1.0",
                json.dumps(outputs_payload, ensure_ascii=False, indent=2),
            )

        footer = ttk.Frame(dialog, padding=8)
        footer.pack(fill=tk.X)
        ttk.Button(footer, text="Format", command=_format).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Apply", command=_apply, style="Apply.TButton").pack(
            side=tk.RIGHT,
            padx=(6, 0),
        )

        def _save_and_close() -> None:
            if _apply():
                dialog.destroy()

        ttk.Button(
            footer,
            text="Save",
            command=_save_and_close,
            style="Apply.TButton",
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        self._register_help_for_widget_tree(dialog)

    def export_scenario(self) -> None:
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_var.get()).resolve()
        suite_name = self.export_name_var.get().strip() or "scenario"
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        except Exception as error:
            self.log(f"Export failed: {error}")
            messagebox.showerror("Export Error", str(error))
            return
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
        try:
            result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        except Exception as error:
            self.log(f"Run export failed: {error}")
            messagebox.showerror("Run Error", str(error))
            self._set_run_phase("idle")
            return
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
        self._close_help_dialog()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    StudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
