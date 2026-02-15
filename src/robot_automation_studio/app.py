"""Desktop UI for robot-automation-studio."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .editor import ScenarioEditor
from .exporter import export_all
from .models import (
    UNITY_EXECUTION_MODE_KEY,
    UNITY_PROJECT_PATH_KEY,
    Scenario,
    normalize_unity_execution_mode,
)
from .recorder import ScenarioRecorder, events_to_steps
from .runner import run_robot


class StudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Robot Automation Studio")
        self.root.geometry("1200x760")

        self.scenario = Scenario(name="Unity Editor Flow")
        self.editor = ScenarioEditor(self.scenario)
        self.recorder = ScenarioRecorder()
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

        self.selected_index: int | None = None

        self._build_ui()
        self.refresh_steps()

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
        ttk.Button(controls, text="Add Wait", command=self.add_wait).pack(side=tk.LEFT, padx=4)
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
        ttk.Button(bottom, text="Run Robot", command=self.run_robot_suite).grid(
            row=0, column=5, padx=4
        )

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

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

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
        steps = events_to_steps(events, auto_wait_threshold_ms=500)
        for step in steps:
            self.scenario.steps.append(step)
        self.refresh_steps()
        self.log(f"Recording stopped. Added {len(steps)} steps.")

    def add_wait(self) -> None:
        self.editor.add_step("wait", "wait", {"seconds": 1.0})
        self.refresh_steps()

    def add_click(self) -> None:
        self.editor.add_step(
            "click",
            "click",
            {
                "x_ratio": 0.5,
                "y_ratio": 0.5,
                "box_width": 180,
                "box_height": 48,
                "wait_seconds": 0.8,
            },
        )
        self.refresh_steps()

    def add_drag(self) -> None:
        self.editor.add_step(
            "drag",
            "drag",
            {
                "from_x_ratio": 0.25,
                "from_y_ratio": 0.5,
                "to_x_ratio": 0.7,
                "to_y_ratio": 0.5,
                "wait_seconds": 0.8,
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
            defaultextension=".json", filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        target = Path(path)
        self.scenario.save_json(target)
        self.current_path = target
        self.log(f"Saved scenario: {target}")

    def load_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
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

    def run_robot_suite(self) -> None:
        self._sync_scenario_header()
        output_dir = Path(self.output_dir_var.get()).resolve()
        suite_name = self.export_name_var.get().strip() or "scenario"
        result = export_all(self.scenario, output_dir=output_dir, suite_name=suite_name)
        artifacts_dir = output_dir / "run"
        variable_output = output_dir

        def _run() -> None:
            self.log("Running Robot suite...")
            run_result = run_robot(
                suite_path=result.robot_path,
                output_dir=artifacts_dir,
                variable_output_dir=variable_output,
            )
            self.log(f"robot exit={run_result.return_code}")
            if run_result.stdout:
                self.log(run_result.stdout.strip())
            if run_result.stderr:
                self.log(run_result.stderr.strip())

        threading.Thread(target=_run, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    StudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
