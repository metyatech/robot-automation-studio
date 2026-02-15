# Changelog

## Unreleased

- Migrated scenario model from `1.0.0` to `2.0.0` (exclusive support).
- Added v2-aware step model (`kind` / `action` / `control`) and conversion from recorded events.
- Updated Robot exporter to consume v2 payloads and fail fast on unsupported step kinds/actions.
- Added dedicated UI editors for:
  - variables
  - profiles
  - execution/outputs
  - full scenario JSON
- Expanded tests for v2 model/editor/exporter/recorder behavior.

## 0.1.0

- Initial release with recording/editor/export/run desktop app.
- Added Robot and JSON export formats.
- Added Robot runner integration and verification pipeline.
