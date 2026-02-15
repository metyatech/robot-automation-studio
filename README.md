# robot-automation-studio

Desktop application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Features

- Record desktop actions (click, drag, shortcut, wait) with relative coordinates
- Recorded click/drag steps run without extra fixed delay (timing follows recorded waits)
- Foreground window filtering during recording (for Unity-focused capture)
- Edit recorded steps (add, delete, move, modify parameters)
- Run Robot Framework suites directly from the app
- Runtime safety controls for automation execution:
  - visible running status
  - stop button
  - global emergency stop hotkey (`Ctrl+Shift+F12`)
  - dark overlay outside the active automation window with shortcut banner
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
3. If mode is `launch`, set `Unity Project Path`.
4. Click `Start Recording`, perform operations in Unity Editor, then click `Stop Recording`.
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

## Output Structure

- `<output>/<name>.robot`: Robot Framework suite
- `<output>/<name>.scenario.json`: machine-readable scenario (automation-scenario-spec)
- `<output>/run/robot/output.xml`: Robot run output (when running from app)

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
