from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.exporter import export_all
from robot_automation_studio.models import Step

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


@pytest.mark.parametrize(
    ("execution_mode", "use_profile", "use_hierarchy"),
    [
        ("attach", False, False),
        ("attach", False, True),
        ("attach", True, False),
        ("attach", True, True),
        ("launch", False, False),
        ("launch", False, True),
        ("launch", True, False),
        ("launch", True, True),
    ],
)
def test_live_export_matrix_for_modes_profiles_and_hierarchy(
    tmp_path: Path,
    execution_mode: str,
    use_profile: bool,
    use_hierarchy: bool,
) -> None:
    if os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_E2E", "") != "1":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_E2E=1 to run live Unity export matrix.")

    project_path = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH", "").strip()
    if project_path == "":
        pytest.skip("Set ROBOT_AUTOMATION_STUDIO_LIVE_PROJECT_PATH for live Unity matrix test.")
    if not Path(project_path).exists():
        pytest.skip(f"Live Unity project path not found: {project_path}")

    hierarchy_path = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_HIERARCHY_PATH", "").strip()
    if use_hierarchy and hierarchy_path == "":
        pytest.skip(
            "Set ROBOT_AUTOMATION_STUDIO_LIVE_HIERARCHY_PATH "
            "to include hierarchy_path matrix cases."
        )

    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio._set_combo_value(studio.execution_mode_combo, execution_mode)
        studio.on_execution_mode_changed()
        studio.project_path_edit.setText(project_path)
        window_hint = os.getenv("ROBOT_AUTOMATION_STUDIO_LIVE_WINDOW_HINT", "Unity")
        studio.window_hint_edit.setText(window_hint)

        studio.scenario.variables = [
            {"id": "unity_window_hint", "type": "string", "required": True, "default": window_hint},
            {"id": "unity_project_path", "type": "path", "required": True, "default": project_path},
            {
                "id": "hierarchy_target",
                "type": "string",
                "required": False,
                "default": hierarchy_path or "AvatarRoot",
            },
        ]
        if use_profile:
            studio.scenario.profiles = {
                "live-profile": {
                    "description": "Live matrix profile",
                    "variables": {
                        "unity_window_hint": f"{window_hint} Live",
                        "unity_project_path": project_path,
                        "hierarchy_target": hierarchy_path or "AvatarRoot",
                    },
                }
            }
            studio.scenario.execution = {"active_profile": "live-profile"}
            studio._refresh_active_profile_combo()
            studio._set_combo_value(studio.active_profile_combo, "live-profile")
        else:
            studio.scenario.profiles = {}
            studio.scenario.execution = {}
            studio._refresh_active_profile_combo()
            studio._set_combo_value(studio.active_profile_combo, "")

        if use_hierarchy:
            studio.scenario.steps = [
                Step(
                    action="click",
                    title="Select hierarchy",
                    params={"hierarchy_path": "${hierarchy_target}", "wait_seconds": 0.1},
                )
            ]
        else:
            studio.scenario.steps = [
                Step(
                    action="click",
                    title="Click file menu",
                    params={
                        "title": "File",
                        "automation_id": "MainMenuFile",
                        "class_name": "MenuItem",
                        "control_type": "MenuItem",
                    },
                )
            ]

        assert studio._ensure_unity_bridge_dependency_if_configured("run") is True

        output_dir = (
            tmp_path / f"{execution_mode}-profile-{int(use_profile)}-hier-{int(use_hierarchy)}"
        )
        result = export_all(
            studio.scenario,
            output_dir=output_dir,
            suite_name="live-matrix",
            active_profile=studio._active_profile_value(),
        )
        text = result.robot_path.read_text(encoding="utf-8")

        if execution_mode == "launch":
            assert "Start Unity Editor" in text
        else:
            assert "Attach To Running Unity Editor" in text

        if use_hierarchy:
            assert "Select Unity Hierarchy Object" in text
        else:
            assert "Click Unity Element" in text

        if use_profile:
            assert f"${{unity_window_hint}}=    Set Variable    {window_hint} Live" in text
        else:
            assert f"${{unity_window_hint}}=    Set Variable    {window_hint}" in text
    finally:
        studio.close()
