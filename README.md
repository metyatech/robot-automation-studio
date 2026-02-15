# robot-automation-studio

Desktop application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Features

- Record desktop actions (click, drag, shortcut) with UI element selectors
- Optional per-action delay via `wait_seconds`
- Foreground window filtering during recording (for Unity-focused capture)
- Unity hierarchy click recording via Unity bridge (`hierarchy_path`)
- Edit recorded steps (add, delete, move, modify parameters)
- Run Robot Framework suites directly from the app
- Runtime safety controls for automation execution:
  - visible running status
  - stop button
  - global emergency stop hotkey (`Ctrl+Shift+F12`)
  - dark overlay outside the active automation window with shortcut banner
  - recording/run overlays use distinct style and banner text
- Export both `.robot` suites and machine-readable scenario spec JSON files
- Designed for Unity Editor and other desktop targets on Windows

## Supported Environment

- Windows 10/11
- Python 3.11+

## Install

```bash
python -m pip install -e ".[dev]"
```

## Launch

```bash
python -m robot_automation_studio.app
```

or:

```bash
robot-automation-studio
```

## End-to-End Workflow

1. Set scenario name and window hint (for example `Unity`).
2. Select execution mode:
   - `attach`: run against an already opened Unity Editor.
   - `launch`: open a Unity project path and then run the scenario.
3. Optionally set `Unity Project Path` (recommended for Unity Hierarchy bridge).
   - When set, Studio auto-adds `com.metyatech.unity-automation-bridge` to `Packages/manifest.json` before recording and before `Run Robot`.
   - This works for both `attach` and `launch`.
   - In `attach`, when empty, Studio auto-detects the attached Unity project's `-projectPath` from the running Unity process and then auto-adds the dependency.
4. Click `Start Recording`, perform operations in Unity Editor, then click `Stop Recording`.
   - In `attach`, `Start Recording` fails immediately with an error dialog if no visible window matches `Window Hint`.
   - If Unity bridge was just added or not ready, `Start Recording` waits for bridge readiness before starting recording.
   - While recording, overlay highlight is enabled (distinct "recording" style from run mode).
   - Click/drag is recorded only when a UI Automation element selector is resolved.
   - If selector resolution fails, Studio logs a recording error and does not add the step.
   - For Unity Hierarchy pane clicks, Studio uses Unity bridge selection path when available.
5. Fine-tune steps from the editor panel.
6. Choose output directory and export name.
7. Click `Export` to generate:
   - `<name>.robot`
   - `<name>.scenario.json`
8. Click `Run Robot` to execute the generated suite.
9. While running, use `Stop Robot` or press `Ctrl+Shift+F12` to stop immediately.

## Execution Mode Notes

- `attach` is the default and keeps scenarios reusable across projects.
- `launch` is useful for document generation pipelines that should open a specific project automatically.
- In `launch` mode, the generated `.robot` suite fails fast when project path is empty.
- If `Unity Project Path` is set, exported `.robot` also ensures Unity bridge UPM dependency before attach/launch.
- In `attach`, Studio also tries to auto-detect project path from the attached Unity process command line.

## Output Structure

- `<output>/<name>.robot`: Robot Framework suite
- `<output>/<name>.scenario.json`: machine-readable scenario (automation-scenario-spec)
- `<output>/run/robot/output.xml`: Robot run output (when running from app)

## Unity Hierarchy Bridge

- Unity Hierarchy rows are custom-drawn and often appear as one generic UIA pane.
- To record/replay stable hierarchy clicks, install Unity bridge as UPM dependency in each target project:
  - `com.metyatech.unity-automation-bridge`
  - `https://github.com/metyatech/robotframework-unity-editor.git?path=/unity-package#main`
- Studio can auto-install this dependency when `Unity Project Path` is set.
- Without the bridge, hierarchy row clicks cannot be resolved and recording logs an error.

## Verification

```bash
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Export Example

1. Record actions in the app
2. Save scenario as JSON
3. Export Robot suite
4. Run suite with output directory configured in app

## Links

- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- License: `LICENSE`
- Changelog: `CHANGELOG.md`
