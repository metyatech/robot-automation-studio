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
from .overlay import AutomationRunOverlay
from .recorder import ScenarioRecorder, events_to_steps
from .runner import RunResult, start_robot_process, stop_robot_process, wait_robot_process
from .status import SPINNER_FRAMES, format_run_status, next_spinner_index

STOP_HOTKEY_BIND = "<ctrl>+<shift>+<f12>"
STOP_HOTKEY_LABEL = "Ctrl+Shift+F12"


class StudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Robot Automation Studio")
        self.root.geometry("1200x760")

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.recorder = ScenarioRecorder(on_record_error=self._on_record_error)
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
        self._run_phase = "idle"
        self._status_spinner_index = 0
        self._status_timer_id: str | None = None
        self._phase_promotion_timer_id: str | None = None

        self._build_ui()
        self.refresh_steps()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(top, text="Scenario Name").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.name_var, width=40).grid(
            row=0, column=1, sticky=tk.W, padx=6
        )
        ttk.Label(top, text="Window Hint").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        ttk.Entry(top, textvariable=self.window_hint_var, width=24).grid(
            row=0, column=3, sticky=tk.W, padx=6
        )
        ttk.Label(top, text="Execution Mode").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        mode_combo = ttk.Combobox(
            top,
            textvariable=self.execution_mode_var,
            values=("attach", "launch"),
            state="readonly",
            width=14,
        )
        mode_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        mode_combo.bind("<<ComboboxSelected>>", self.on_execution_mode_changed)
        ttk.Label(top, text="Unity Project Path").grid(
            row=1, column=2, sticky=tk.W, padx=(20, 0), pady=(6, 0)
        )
        self.project_path_entry = ttk.Entry(top, textvariable=self.unity_project_path_var, width=44)
        self.project_path_entry.grid(row=1, column=3, sticky=tk.W, padx=6, pady=(6, 0))
        self.project_path_browse_button = ttk.Button(
            top, text="Browse", command=self.browse_unity_project_path
        )
        self.project_path_browse_button.grid(row=1, column=4, sticky=tk.W, pady=(6, 0))

        controls = ttk.Frame(self.root)
        controls.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(controls, text="Start Recording", command=self.start_recording).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(controls, text="Stop Recording", command=self.stop_recording).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(controls, text="Add Click", command=self.add_click).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Add Drag", command=self.add_drag).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Add Shortcut", command=self.add_shortcut).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(controls, text="Add Menu", command=self.add_menu).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Add Type", command=self.add_type).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Delete Step", command=self.delete_selected).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(controls, text="Move Up", command=self.move_up).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Move Down", command=self.move_down).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Duplicate", command=self.duplicate_selected).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(controls, text="Save JSON", command=self.save_json).pack(side=tk.LEFT, padx=12)
        ttk.Button(controls, text="Load JSON", command=self.load_json).pack(side=tk.LEFT, padx=4)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        self.step_list = tk.Listbox(left, height=20)
        self.step_list.pack(fill=tk.BOTH, expand=True)
        self.step_list.bind("<<ListboxSelect>>", self.on_select_step)

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
        self.params_text = tk.Text(edit_row, width=42, height=18)
        self.params_text.grid(row=2, column=1, sticky=tk.W)

        ttk.Button(right, text="Apply Step Changes", command=self.apply_step_changes).pack(
            anchor=tk.W
        )

        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(bottom, text="Output Dir").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(bottom, textvariable=self.output_dir_var, width=48).grid(
            row=0, column=1, sticky=tk.W
        )
        ttk.Label(bottom, text="Export Name").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Entry(bottom, textvariable=self.export_name_var, width=24).grid(
            row=0, column=3, sticky=tk.W
        )
        ttk.Button(bottom, text="Export", command=self.export_scenario).grid(
            row=0, column=4, padx=8
        )
        self.run_robot_button = ttk.Button(bottom, text="Run Robot", command=self.run_robot_suite)
        self.run_robot_button.grid(row=0, column=5, padx=4)
        self.stop_robot_button = ttk.Button(
            bottom,
            text=f"Stop Robot ({STOP_HOTKEY_LABEL})",
            command=self.stop_robot_suite,
            state="disabled",
        )
        self.stop_robot_button.grid(row=0, column=6, padx=4)
        ttk.Label(bottom, text="Status").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Label(
            bottom,
            textvariable=self.robot_status_var,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        self.log_text = tk.Text(self.root, height=10)
        self.log_text.pack(fill=tk.BOTH, padx=8, pady=(0, 8))
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

    def _render_robot_status(self) -> None:
        spinner = SPINNER_FRAMES[self._status_spinner_index]
        status_text = format_run_status(self._run_phase, spinner)
        self.robot_status_var.set(status_text)
        if self._overlay is not None:
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
            self.root.after(0, self.stop_robot_suite)

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

    def _start_overlay(self) -> None:
        if self._overlay is not None:
            return
        try:
            self._overlay = AutomationRunOverlay(
                root=self.root,
                window_hint=self.window_hint_var.get().strip() or "Unity",
                stop_hotkey_label=STOP_HOTKEY_LABEL,
            )
            self._overlay.start()
            self._overlay.set_progress_text(self.robot_status_var.get())
        except Exception as error:  # pragma: no cover - integration path
            self._overlay = None
            self.log(f"Failed to start overlay: {error}")

    def _stop_overlay(self) -> None:
        if self._overlay is None:
            return
        self._overlay.stop()
        self._overlay = None

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
        is_launch_mode = execution_mode == "launch"
        self.execution_mode_var.set(execution_mode)
        next_state = "normal" if is_launch_mode else "disabled"
        self.project_path_entry.configure(state=next_state)
        self.project_path_browse_button.configure(state=next_state)

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
        self.recorder.start(window_hint=self.window_hint_var.get().strip() or "Unity")
        self.log(f"Recording started. window_hint={self.window_hint_var.get().strip() or 'Unity'}")

    def stop_recording(self) -> None:
        events = self.recorder.stop()
        steps = events_to_steps(events)
        for step in steps:
            self.scenario.steps.append(step)
        self.refresh_steps()
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
        if self._is_robot_running():
            self.log("Robot suite is already running.")
            return
        self._sync_scenario_header()
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
        self._start_overlay()

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
