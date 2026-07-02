# Changelog

## Unreleased

- Fixed a race condition/path mismatch in `test_run_robot_suite_logs_run_diagnostics_summary`
  where the output directory was not correctly set for the studio instance.
- Added automated visual accessibility checks for text and non-text boundary
  contrast ratios (WCAG 2.1 AA compliance).
- Improved UI component visibility in dark theme by adding high-contrast borders
  to buttons, inputs, and containers to satisfy 3:1 boundary contrast requirements.
- Migrated scenario model from `1.0.0` to `2.0.0` (exclusive support).
- Added v2-aware step model (`kind` / `action` / `control`) and conversion from
  recorded events.
- Updated Robot exporter to consume v2 payloads and fail fast on unsupported step
  kinds/actions.
- Expanded Robot exporter coverage for v2 control flow:
  - `if`, `for_each`, `while`, `try`, `break`, `continue`, `return`, `group`
- Expanded Robot exporter action coverage:
  - `open_url`, `select_hierarchy`, `double_click`, `right_click`, `assert`, `emit_annotation`
- Added dedicated UI editors for:
  - variables
  - profiles
  - execution/outputs
  - full scenario JSON
- Expanded tests for v2 model/editor/exporter/recorder behavior.
- Added universal in-app GUI guidance:
  - context help bar that updates from hovered/focused components
  - searchable full help dialog (`Open Guide (F1)`)
  - centralized help catalog with fallback descriptions for all GUI components

## 0.1.0

- Initial release with recording/editor/export/run desktop app.
- Added Robot and JSON export formats.
- Added Robot runner integration and verification pipeline.
