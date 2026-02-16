# robot-automation-studio

Desktop application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Features

- Record desktop actions (click, drag, shortcut) with UI element selectors
- Foreground window filtering during recording (for Unity-focused capture)
- Unity hierarchy click recording via Unity bridge (`hierarchy_path`)
- v2 scenario editing support:
  - step kind/action/control fields
  - form-based editors for `variables` and `profiles` (no raw JSON required)
  - dedicated editors for `execution`, `outputs`
  - full scenario JSON editor for complete v2 coverage
- v2 Robot export coverage:
  - control flow: `if`, `for_each`, `while`, `try`, `parallel`, `break`, `continue`, `return`, `group`
  - action extensions: `open_url`, `select_hierarchy`, `double_click`, `right_click`, `assert`, `emit_annotation`, `run_subflow`, `start_video`, `stop_video`
  - subflow execution diagnostics:
    - captures subflow `stdout.txt` / `stderr.txt`
    - reports rc + log paths on failure
    - applies explicit `3600s` timeout for subflow execution/wait
- Preflight validation before export/run:
  - fail-fast with issue list dialog when scenario is invalid
  - explicit diagnostics for unresolved placeholders (with field path)
  - `start_video` scenarios fail early when `ffmpeg` is not found in `PATH`
  - execution setting checks include `subflow_timeout_seconds` range (`1..86400`)
  - live step validation hint in Step tab (immediate export/run readiness feedback)
- Profile diff preview:
  - compare resolved scenario results between two profiles
  - inspect changed paths and before/after values
- Run Robot Framework suites directly from the app
- Run diagnostics after Robot execution:
  - parses `output.xml` and logs keyword timing/failure summary
  - writes `run-diagnostics.json`
  - captures failure screenshot automatically when run fails
  - view latest diagnostics from `File -> Run Diagnostics`
- Runtime safety controls for automation execution:
  - visible running status
  - visible preflight-check status before Robot process start
  - stop button
  - configurable global emergency stop hotkey (default: `Alt+Shift+F12`)
  - automatic hotkey fallback when the configured key cannot be registered
  - dark overlay outside the active automation window with shortcut banner and `Stop Now` button
  - recording/run overlays use distinct style and banner text
- In-app universal help system:
  - cursor-near tooltip help for hovered/focused UI components
  - `Help Guide (F1)` searchable GUI help dialog
  - auto-generated explanations for all visible UI components (including editor dialogs)
- Built-in localization switch (English / Japanese) for UI, status, dialogs, logs, and tooltips
- Startup locale auto-detection (explicit `en`/`ja`, env override, then OS locale)
- Persisted UI preferences (locale, target, execution mode, window hint, project path, stop hotkey)
- Export both `.robot` suites and machine-readable scenario spec JSON files
- Designed for Unity Editor and other desktop targets on Windows

## Scenario Spec

- The app now uses `automation-scenario-spec` `2.0.0` only.
- `1.x` scenario compatibility is intentionally removed.
- Exporter fails fast with explicit errors when a step kind/action is not executable by current Robot generation logic.
- Exporter also fails fast when required variables are missing, placeholders are unresolved, or active profile is invalid.

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

Optional startup locale override:

```bash
set ROBOT_AUTOMATION_STUDIO_LOCALE=ja
```

## End-to-End Workflow

1. Set scenario name and window hint (for example `Unity`).
2. Select execution mode:
   - `attach`: run against an already opened Unity Editor.
   - `launch`: open a Unity project path and then run the scenario.
3. Set `Subflow Timeout (s)` when your `run_subflow`/`parallel` children need custom timeout.
   - valid range is `1..86400` seconds.
   - blank value uses default `3600` seconds.
4. Select `Active Profile` when you need profile-specific variable overrides.
   - `(none)` uses variable defaults.
   - Profile selection is applied during `Export` and `Run Robot`.
5. Optionally set `Unity Project Path` (recommended for Unity Hierarchy bridge).
   - When set, Studio auto-adds `com.metyatech.unity-automation-bridge` to `Packages/manifest.json` before recording and before `Run Robot`.
   - This works for both `attach` and `launch`.
   - In `attach`, when empty, Studio auto-detects the attached Unity project's `-projectPath` from the running Unity process and then auto-adds the dependency.
6. Click `● Record`, perform operations in Unity Editor, then click `■ Stop`.
   - In `attach`, `● Record` fails immediately with an error dialog if no visible window matches `Window Hint`.
   - `● Record` validates Unity bridge readiness before starting recording.
   - While recording, overlay highlight is enabled (distinct "recording" style from run mode).
   - Click/drag is recorded only when a UI Automation element selector is resolved.
   - If selector resolution fails, Studio logs a recording error and does not add the step.
   - For Unity Hierarchy pane clicks, Studio uses Unity bridge selection path when available.
7. Fine-tune steps from the editor panel.
   - update step kind/action/control and advanced params JSON.
   - confirm `Step Validation` status is `Ready for export/run.` before running.
8. Open dedicated v2 editors when needed:
   - `Variables`
   - `Profiles`
   - `Execution/Outputs`
   - `{} Full JSON` (full scenario object)
   - `Validate` (preflight issue check)
   - `Profile Diff` (resolved-value comparison)
9. Choose output directory and export name.
10. Click `Export` to generate:
   - `<name>.robot`
   - `<name>.scenario.json`
11. Click `Run Robot` to execute the generated suite.
   - Studio first shows `Preflight checks` status while validating execution prerequisites.
12. While running, use `Stop Robot`, the overlay `Stop Now` button, or the configured stop hotkey to stop immediately.
    - Default stop hotkey is `Alt+Shift+F12`.
    - You can change it from the header `Hotkey: ...` button by pressing the target key combination directly.
    - If registration fails (for example shortcut conflict), Studio applies a fallback key and shows a warning.
13. Use in-app help:
   - hover/focus any UI component to read cursor-near tooltip help
   - press `F1` (or click `Help Guide`) to open searchable full GUI help

## Execution Mode Notes

- `attach` is the default and keeps scenarios reusable across projects.
- `launch` is useful for document generation pipelines that should open a specific project automatically.
- In `launch` mode, the generated `.robot` suite fails fast when project path is empty.
- If `Unity Project Path` is set, exported `.robot` also ensures Unity bridge UPM dependency before attach/launch.
- In `attach`, Studio also tries to auto-detect project path from the attached Unity process command line.
- `Active Profile` lets you apply profile-specific variable overrides during export and run.

## Output Structure

- `<output>/<name>.robot`: Robot Framework suite
- `<output>/<name>.scenario.json`: machine-readable scenario (automation-scenario-spec)
- `<output>/run/robot/output.xml`: Robot run output (when running from app)
- `<output>/run/robot/subflows/*/{stdout.txt,stderr.txt}`: subflow process logs (when using `run_subflow` or `parallel`)
- `<output>/run/diagnostics/run-diagnostics.json`: parsed run diagnostics summary
- `<output>/run/diagnostics/failure-YYYYMMDD-HHMMSS.png`: failure screenshot (when run fails)
- Run Diagnostics dialog also provides direct button to open the `subflows` log directory.
  - Run Diagnostics dialog also shows detected subflow log count and latest update.

## Unity Hierarchy Bridge

- Unity Hierarchy rows are custom-drawn and often appear as one generic UIA pane.
- To record/replay stable hierarchy clicks, install Unity bridge as UPM dependency in each target project:
  - `com.metyatech.unity-automation-bridge`
  - `https://github.com/metyatech/robotframework-unity-editor.git?path=/unity-package#main`
- Studio can auto-install this dependency when `Unity Project Path` is set.
- During auto-install, Studio also removes legacy `Assets/Editor/RobotFrameworkUnityBridge.cs` if present.
- Without the bridge, hierarchy row clicks cannot be resolved and recording logs an error.

## Verification

```bash
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

Install commit-time verification hooks:

```bash
powershell -ExecutionPolicy Bypass -File scripts/install-precommit.ps1
```

## Live Unity Integration Smoke Test

Use this only when Unity Editor is running and a target project is available.

```bash
set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1
set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH=<your-unity-project-path>
set ROBOT_AUTOMATION_STUDIO_LIVE_WINDOW_HINT=Unity
set ROBOT_AUTOMATION_STUDIO_LIVE_HIERARCHY_PATH=<hierarchy-path-for-matrix>
python -m pytest tests/test_live_unity_attach_e2e.py -q
```

The live suite covers:
- attach mode bridge readiness
- launch mode bridge readiness
- Japanese locale smoke path
- export matrix: `attach/launch × profile on/off × hierarchy_path on/off`

## Security Checks in CI

- Dependency vulnerability scan: `pip-audit` in `scripts/verify.ps1` and CI
- Static security analysis: CodeQL workflow (`.github/workflows/codeql.yml`)
- Secret scanning: Gitleaks workflow (`.github/workflows/secret-scan.yml`)

To enforce required checks on `main`, run:

```bash
powershell -ExecutionPolicy Bypass -File scripts/set-branch-protection.ps1
```

Default required checks set by the script:
- `verify`
- `analyze (python)`
- `gitleaks`

## Unity Workflow Example

Example: increase tail length settings in an existing avatar project.

1. Set `Execution Mode` to `attach`.
2. Set `Window Hint` to `Unity`.
3. Click `● Record` and select the avatar object in Hierarchy.
4. Change the relevant Inspector values (for example tail length).
5. Click `■ Stop` and verify generated click/type steps.
6. Use `Export` to generate `.robot` and `.scenario.json`.
7. Click `Run Robot` and confirm preflight -> run status transitions.

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
