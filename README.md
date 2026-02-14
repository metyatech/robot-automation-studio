# robot-automation-studio

Desktop application for recording, editing, running, and exporting Robot Framework scenarios for browser and desktop software automation workflows.

## Features

- Record desktop actions (click, drag, shortcut, wait) with relative coordinates
- Foreground window filtering during recording (for Unity-focused capture)
- Edit recorded steps (add, delete, move, modify parameters)
- Run Robot Framework suites directly from the app
- Export both `.robot` suites and machine-readable JSON scenario files
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
2. Click `Start Recording`, perform operations in Unity Editor, then click `Stop Recording`.
3. Fine-tune steps from the editor panel.
4. Choose output directory and export name.
5. Click `Export` to generate:
   - `<name>.robot`
   - `<name>.json`
6. Click `Run Robot` to execute the generated suite.

## Output Structure

- `<output>/<name>.robot`: Robot Framework suite
- `<output>/<name>.json`: machine-readable scenario
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
