from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp

pytestmark = pytest.mark.integration


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_live_attach_bridge_smoke() -> None:
    if os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_E2E", "") != "1":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1 to run live Unity attach smoke test.")

    project_path = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH", "").strip()
    if project_path == "":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH for live Unity smoke test.")

    if not Path(project_path).exists():
        pytest.skip(f"Live Unity project path not found: {project_path}")

    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._set_combo_value(studio.execution_mode_combo, "attach")
        studio.on_execution_mode_changed()
        studio.project_path_edit.setText(project_path)
        window_hint = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_WINDOW_HINT", "Unity")
        studio.window_hint_edit.setText(window_hint)

        assert studio._ensure_unity_bridge_dependency_if_configured("run") is True
    finally:
        studio.close()


def test_live_attach_bridge_smoke_japanese_locale() -> None:
    if os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_E2E", "") != "1":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1 to run live Unity attach smoke test.")

    project_path = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH", "").strip()
    if project_path == "":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH for live Unity smoke test.")
    if not Path(project_path).exists():
        pytest.skip(f"Live Unity project path not found: {project_path}")

    _ensure_qapp()
    studio = StudioApp(initial_locale="ja")
    try:
        studio._set_combo_value(studio.execution_mode_combo, "attach")
        studio.on_execution_mode_changed()
        studio.project_path_edit.setText(project_path)
        window_hint = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_WINDOW_HINT", "Unity")
        studio.window_hint_edit.setText(window_hint)

        assert "Robot 実行" in studio.run_button.text()
        assert studio._ensure_unity_bridge_dependency_if_configured("run") is True
    finally:
        studio.close()


def test_live_launch_bridge_smoke() -> None:
    if os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_E2E", "") != "1":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1 to run live Unity launch smoke test.")

    project_path = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH", "").strip()
    if project_path == "":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH for live Unity smoke test.")
    if not Path(project_path).exists():
        pytest.skip(f"Live Unity project path not found: {project_path}")

    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._set_combo_value(studio.execution_mode_combo, "launch")
        studio.on_execution_mode_changed()
        studio.project_path_edit.setText(project_path)

        assert studio._ensure_unity_bridge_dependency_if_configured("run") is True
    finally:
        studio.close()
