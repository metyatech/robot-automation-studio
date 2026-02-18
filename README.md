# robot-automation-studio

Web-based application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Architecture

The application is composed of two processes:

- **Backend**: Python FastAPI WebSocket server (`robot_automation_studio.server`) that exposes all business logic over a JSON-RPC-style WebSocket at `/ws`.
- **Frontend**: React + TypeScript + Vite + shadcn/ui application that connects to the backend WebSocket. Served locally at `http://localhost:1420` during development.
- **Overlay**: PySide6 subprocess launched by the backend to display a border highlight on the target window during recording and automation runs.

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
  - fail-fast with issue list when scenario is invalid
  - explicit diagnostics for unresolved placeholders (with field path)
  - `start_video` scenarios fail early when `ffmpeg` is not found in `PATH`
  - execution setting checks include `subflow_timeout_seconds` range (`1..86400`)
  - inline `Subflow Timeout` validation status (default/fixed/variable/invalid) in Scenario tab
  - live step validation hint in Step tab (immediate export/run readiness feedback)
- Profile diff preview:
  - compare resolved scenario results between two profiles
  - inspect changed paths and before/after values
- Run Robot Framework suites directly from the app
- Run diagnostics after Robot execution:
  - parses `output.xml` and logs keyword timing/failure summary
  - writes `run-diagnostics.json`
  - captures failure screenshot automatically when run fails
- Runtime safety controls for automation execution:
  - visible running status
  - visible preflight-check status before Robot process start
  - stop button
  - configurable global emergency stop hotkey (default: `Alt+Shift+F12`)
  - automatic hotkey fallback when the configured key cannot be registered
  - dark overlay outside the active automation window with shortcut banner and `Stop Now` button
  - recording/run overlays use distinct style and banner text
- Built-in localization switch (English / Japanese) for UI, status, dialogs, logs, and tooltips
- Startup locale auto-detection (explicit `en`/`ja`, env override, then OS locale)
- Persisted UI preferences (locale, target, execution mode, window hint, project path, stop hotkey)
- Export both `.robot` suites and machine-readable scenario spec JSON files
- Designed for Unity Editor and other desktop targets on Windows

## Scenario Spec

- The app uses `automation-scenario-spec` `2.0.0` only.
- `1.x` scenario compatibility is intentionally removed.
- Exporter fails fast with explicit errors when a step kind/action is not executable by current Robot generation logic.
- Exporter also fails fast when required variables are missing, placeholders are unresolved, or active profile is invalid.

## Supported Environment

- Windows 10/11
- Python 3.11+
- Node.js 18+

## Install

### Python dependencies

```bash
pip install -e ".[dev,overlay]"
```

This installs the server dependencies (`fastapi`, `uvicorn`, `websockets`), PySide6 for the overlay subprocess, and dev tools.

### Node dependencies

```bash
cd tauri-app && npm install
```

## Usage / How to Run

### 1. Start the backend server

```bash
python -m robot_automation_studio.server --port 8765
```

Optional: override locale at startup:

```bash
python -m robot_automation_studio.server --port 8765 --locale ja
```

Or use the installed entry point:

```bash
robot-automation-studio --port 8765
```

### 2. Start the frontend (development mode)

```bash
cd tauri-app && npm run dev
```

Open `http://localhost:1420?port=8765` in your browser.

### 3. Build the frontend (production)

```bash
cd tauri-app && npm run build
```

Then open `tauri-app/dist/index.html` in your browser, or serve `tauri-app/dist/` with any static file server.

### 4. Run as a desktop app (Tauri)

To run as a native desktop window instead of a browser tab:

```bash
cd tauri-app && npx tauri dev
```

This launches the Tauri desktop shell with the React frontend embedded.
The backend server must be running separately (step 1).

To build a distributable desktop executable:

```bash
cd tauri-app && npx tauri build
```

## Dev Commands

### Python

| Command | Description |
|---|---|
| `ruff check .` | Lint Python sources |
| `ruff format --check .` | Check Python formatting |
| `ruff format .` | Auto-format Python sources |
| `pyright` | Type-check Python sources |
| `pytest tests/` | Run Python tests |
| `pip-audit -r requirements-audit.txt` | Dependency vulnerability scan |

### TypeScript / Frontend

| Command | Description |
|---|---|
| `npm run build` | Build frontend (runs `tsc && vite build`) |
| `npx tsc --noEmit` | Type-check TypeScript sources only |

### Full verification suite

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

Install commit-time hooks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-precommit.ps1
```

## End-to-End Workflow

1. Start the backend server: `python -m robot_automation_studio.server --port 8765`
2. Open the frontend at `http://localhost:1420?port=8765`.
3. Set scenario name and window hint (for example `Unity`).
4. Select execution mode:
   - `attach`: run against an already opened Unity Editor.
   - `launch`: open a Unity project path and then run the scenario.
5. Set `Subflow Timeout (s)` when your `run_subflow`/`parallel` children need custom timeout.
   - valid range is `1..86400` seconds.
   - blank value uses default `3600` seconds.
   - variable placeholder must be a full value (`${timeout_var}`).
   - mixed text such as `${timeout_var}s` is treated as invalid.
6. Select `Active Profile` when you need profile-specific variable overrides.
   - `(none)` uses variable defaults.
   - Profile selection is applied during `Export` and `Run Robot`.
7. Optionally set `Unity Project Path` (recommended for Unity Hierarchy bridge).
   - When set, Studio auto-adds `com.metyatech.unity-automation-bridge` to `Packages/manifest.json` before recording and before `Run Robot`.
8. Click `Record`, perform operations in Unity Editor, then click `Stop`.
   - Click/drag is recorded only when a UI Automation element selector is resolved.
   - If selector resolution fails, Studio logs a recording error and does not add the step.
   - For Unity Hierarchy pane clicks, Studio uses Unity bridge selection path when available.
9. Fine-tune steps from the editor panel.
   - update step kind/action/control and advanced params JSON.
10. Open dedicated v2 editors when needed:
    - `Variables`
    - `Profiles`
    - `Execution/Outputs`
    - `Full JSON` (full scenario object)
    - `Validate` (preflight issue check)
    - `Profile Diff` (resolved-value comparison)
11. Choose output directory and export name.
12. Click `Export` to generate:
    - `<name>.robot`
    - `<name>.scenario.json`
13. Click `Run Robot` to execute the generated suite.
    - Studio first shows `Preflight checks` status while validating execution prerequisites.
14. While running, use `Stop Robot`, the overlay `Stop Now` button, or the configured stop hotkey to stop immediately.
    - Default stop hotkey is `Alt+Shift+F12`.

## Execution Mode Notes

- `attach` is the default and keeps scenarios reusable across projects.
- `launch` is useful for document generation pipelines that should open a specific project automatically.
- In `launch` mode, the generated `.robot` suite fails fast when project path is empty.
- If `Unity Project Path` is set, exported `.robot` also ensures Unity bridge UPM dependency before attach/launch.
- `Active Profile` lets you apply profile-specific variable overrides during export and run.

## Output Structure

- `<output>/<name>.robot`: Robot Framework suite
- `<output>/<name>.scenario.json`: machine-readable scenario (automation-scenario-spec)
- `<output>/run/robot/output.xml`: Robot run output (when running from app)
- `<output>/run/robot/subflows/*/{stdout.txt,stderr.txt}`: subflow process logs (when using `run_subflow` or `parallel`)
- `<output>/run/diagnostics/run-diagnostics.json`: parsed run diagnostics summary
- `<output>/run/diagnostics/failure-YYYYMMDD-HHMMSS.png`: failure screenshot (when run fails)

## Unity Hierarchy Bridge

- Unity Hierarchy rows are custom-drawn and often appear as one generic UIA pane.
- To record/replay stable hierarchy clicks, install Unity bridge as UPM dependency in each target project:
  - `com.metyatech.unity-automation-bridge`
  - `https://github.com/metyatech/robotframework-unity-editor.git?path=/unity-package#main`
- Studio can auto-install this dependency when `Unity Project Path` is set.
- During auto-install, Studio also removes legacy `Assets/Editor/RobotFrameworkUnityBridge.cs` if present.
- Without the bridge, hierarchy row clicks cannot be resolved and recording logs an error.

## Security Checks in CI

- Dependency vulnerability scan: `pip-audit` in `scripts/verify.ps1` and CI
- Static security analysis: CodeQL workflow (`.github/workflows/codeql.yml`)
- Secret scanning: Gitleaks workflow (`.github/workflows/secret-scan.yml`)

To enforce required checks on `main`, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/set-branch-protection.ps1
```

Default required checks set by the script:
- `verify`
- `analyze (python)`
- `gitleaks`

## Unity Workflow Example

Example: increase tail length settings in an existing avatar project.

1. Start the backend and open the frontend in your browser.
2. Set `Execution Mode` to `attach`.
3. Set `Window Hint` to `Unity`.
4. Click `Record` and select the avatar object in Hierarchy.
5. Change the relevant Inspector values (for example tail length).
6. Click `Stop` and verify generated click/type steps.
7. Use `Export` to generate `.robot` and `.scenario.json`.
8. Click `Run Robot` and confirm preflight -> run status transitions.

## Links

- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- License: `LICENSE`
- Changelog: `CHANGELOG.md`
