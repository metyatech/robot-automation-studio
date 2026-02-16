# robot-automation-studio

Desktop application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Features

- Record desktop actions (click, drag, shortcut) with UI element selectors
- Foreground window filtering during recording (for Unity-focused capture)
- Unity hierarchy click recording via Unity bridge (`hierarchy_path`)
- v2 scenario editing support:
  - step kind/action/control fields
  - dedicated editors for `variables`, `profiles`, `execution`, `outputs`
  - full scenario JSON editor for complete v2 coverage
- Run Robot Framework suites directly from the app
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
3. Optionally set `Unity Project Path` (recommended for Unity Hierarchy bridge).
   - When set, Studio auto-adds `com.metyatech.unity-automation-bridge` to `Packages/manifest.json` before recording and before `Run Robot`.
   - This works for both `attach` and `launch`.
   - In `attach`, when empty, Studio auto-detects the attached Unity project's `-projectPath` from the running Unity process and then auto-adds the dependency.
4. Click `● Record`, perform operations in Unity Editor, then click `■ Stop`.
   - In `attach`, `● Record` fails immediately with an error dialog if no visible window matches `Window Hint`.
   - `● Record` validates Unity bridge readiness before starting recording.
   - While recording, overlay highlight is enabled (distinct "recording" style from run mode).
   - Click/drag is recorded only when a UI Automation element selector is resolved.
   - If selector resolution fails, Studio logs a recording error and does not add the step.
   - For Unity Hierarchy pane clicks, Studio uses Unity bridge selection path when available.
5. Fine-tune steps from the editor panel.
   - update step kind/action/control and advanced params JSON.
6. Open dedicated v2 editors when needed:
   - `Variables`
   - `Profiles`
   - `Execution/Outputs`
   - `{} Full JSON` (full scenario object)
7. Choose output directory and export name.
8. Click `Export` to generate:
   - `<name>.robot`
   - `<name>.scenario.json`
9. Click `Run Robot` to execute the generated suite.
   - Studio first shows `Preflight checks` status while validating execution prerequisites.
10. While running, use `Stop Robot`, the overlay `Stop Now` button, or the configured stop hotkey to stop immediately.
    - Default stop hotkey is `Alt+Shift+F12`.
    - You can change it from the header `Hotkey: ...` button by pressing the target key combination directly.
    - If registration fails (for example shortcut conflict), Studio applies a fallback key and shows a warning.
11. Use in-app help:
   - hover/focus any UI component to read cursor-near tooltip help
   - press `F1` (or click `Help Guide`) to open searchable full GUI help

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
- During auto-install, Studio also removes legacy `Assets/Editor/RobotFrameworkUnityBridge.cs` if present.
- Without the bridge, hierarchy row clicks cannot be resolved and recording logs an error.

## Verification

```bash
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Live Unity Integration Smoke Test

Use this only when Unity Editor is running and a target project is available.

```bash
set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1
set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH=<your-unity-project-path>
set ROBOT_AUTOMATION_STUDIO_LIVE_WINDOW_HINT=Unity
python -m pytest tests/test_live_unity_attach_e2e.py -q
```

## Security Checks in CI

- Dependency vulnerability scan: `pip-audit` in `scripts/verify.ps1` and CI
- Static security analysis: CodeQL workflow (`.github/workflows/codeql.yml`)
- Secret scanning: Gitleaks workflow (`.github/workflows/secret-scan.yml`)

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
