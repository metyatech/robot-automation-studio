from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.preflight_validation import ValidationIssue, ValidationReport
from robot_automation_studio.runner import RunResult


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def _process_events_for(duration_ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(duration_ms, loop.quit)
    loop.exec()


class _FakeRunExportResult:
    def __init__(self, root: Path) -> None:
        self.robot_path = root / "suite.robot"
        self.json_path = root / "suite.scenario.json"


class _FakeProcess:
    def __init__(self) -> None:
        self.pid = 12345

    def poll(self):
        return None


def test_run_robot_suite_logs_preflight_and_finishes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            lambda scenario, output_dir, suite_name, active_profile=None: _FakeRunExportResult(
                tmp_path
            ),
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(studio, "_start_overlay", lambda mode, progress_text: None)
        monkeypatch.setattr(studio, "_stop_overlay", lambda: None)
        monkeypatch.setattr(studio, "_stop_stop_hotkey", lambda: None)
        monkeypatch.setattr(
            "robot_automation_studio.app.start_robot_process",
            lambda suite_path, output_dir, variable_output_dir: _FakeProcess(),
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.wait_robot_process",
            lambda process: RunResult(return_code=0, stdout="", stderr=""),
        )

        studio.run_robot_suite()

        assert studio._run_thread is not None
        studio._run_thread.join(timeout=1.0)
        _process_events_for(120)

        log_text = studio.log_text.toPlainText()
        assert "Running preflight checks..." in log_text
        assert "Starting Robot process..." in log_text
        assert studio._run_phase == "idle"
    finally:
        studio.close()


def test_run_robot_suite_preflight_failure_returns_to_idle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: False,
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            lambda scenario, output_dir, suite_name, active_profile=None: _FakeRunExportResult(
                tmp_path
            ),
        )

        studio.run_robot_suite()

        log_text = studio.log_text.toPlainText()
        assert "Running preflight checks..." in log_text
        assert studio._run_phase == "idle"
    finally:
        studio.close()


def test_stop_request_via_global_hotkey_stops_running_robot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(studio, "_is_robot_running", lambda: True)
        studio.recorder._recording = False
        captured = {"source": ""}

        def _fake_stop_robot_suite(stop_source: str = "manual") -> None:
            captured["source"] = stop_source

        monkeypatch.setattr(studio, "stop_robot_suite", _fake_stop_robot_suite)

        studio._on_automation_stop_requested("global_hotkey")

        assert captured["source"] == "global_hotkey"
    finally:
        studio.close()


def test_run_robot_suite_logs_run_diagnostics_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            lambda scenario, output_dir, suite_name, active_profile=None: _FakeRunExportResult(
                tmp_path
            ),
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(studio, "_start_overlay", lambda mode, progress_text: None)
        monkeypatch.setattr(studio, "_stop_overlay", lambda: None)
        monkeypatch.setattr(studio, "_stop_stop_hotkey", lambda: None)
        monkeypatch.setattr(
            "robot_automation_studio.app.start_robot_process",
            lambda suite_path, output_dir, variable_output_dir: _FakeProcess(),
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.wait_robot_process",
            lambda process: RunResult(return_code=0, stdout="", stderr=""),
        )
        run_output = tmp_path / "run" / "output.xml"
        run_output.parent.mkdir(parents=True, exist_ok=True)
        run_output.write_text(
            (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<robot generated="2026-02-16T10:00:00.000000">\n'
                '  <suite name="suite-c">\n'
                '    <test name="case-c">\n'
                '      <kw name="Click Unity Relative" owner="lib">\n'
                "        <arg>0.5</arg>\n"
                "        <arg>0.4</arg>\n"
                '        <status status="PASS" elapsed="0.200000"/>\n'
                "      </kw>\n"
                '      <status status="PASS" elapsed="0.210000"/>\n'
                "    </test>\n"
                "  </suite>\n"
                "</robot>\n"
            ),
            encoding="utf-8",
        )

        studio.run_robot_suite()

        assert studio._run_thread is not None
        studio._run_thread.join(timeout=1.0)
        _process_events_for(120)

        log_text = studio.log_text.toPlainText()
        assert "Run diagnostics summary" in log_text
    finally:
        studio.close()


def test_run_robot_suite_fails_fast_when_preflight_validation_has_issues(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        report = ValidationReport(
            issues=[
                ValidationIssue(
                    code="scenario.invalid",
                    message="Unresolved placeholder: ${missing} at steps[0].target.uia.title",
                    location="steps[0].target.uia.title",
                )
            ]
        )
        captured: dict[str, str] = {}

        monkeypatch.setattr(
            "robot_automation_studio.app.validate_scenario", lambda *args, **kwargs: report
        )
        monkeypatch.setattr(
            "robot_automation_studio.app_dialogs.open_validation_report_dialog",
            lambda _self, _report, *, title: captured.setdefault("title", title),
        )

        studio.run_robot_suite()

        assert captured["title"] == "Preflight Validation"
        assert studio._run_thread is None
        assert studio._run_phase == "idle"
    finally:
        studio.close()


def test_run_robot_suite_passes_active_profile_to_export(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        captured: dict[str, str | None] = {"active_profile": None}

        def _fake_export_all(
            scenario,
            output_dir,
            suite_name,
            active_profile=None,
        ):
            _ = (scenario, output_dir, suite_name)
            captured["active_profile"] = active_profile
            return _FakeRunExportResult(tmp_path)

        studio.scenario.profiles = {"vrchat": {"description": "VRChat", "variables": {}}}
        studio.scenario.execution = {"active_profile": "vrchat"}
        studio._refresh_active_profile_combo()
        studio._set_combo_value(studio.active_profile_combo, "vrchat")

        monkeypatch.setattr(
            "robot_automation_studio.app.export_all",
            _fake_export_all,
        )
        monkeypatch.setattr(
            studio,
            "_ensure_unity_bridge_dependency_if_configured",
            lambda purpose: True,
        )
        monkeypatch.setattr(studio, "_start_stop_hotkey", lambda: True)
        monkeypatch.setattr(studio, "_start_overlay", lambda mode, progress_text: None)
        monkeypatch.setattr(studio, "_stop_overlay", lambda: None)
        monkeypatch.setattr(studio, "_stop_stop_hotkey", lambda: None)
        monkeypatch.setattr(
            "robot_automation_studio.app.start_robot_process",
            lambda suite_path, output_dir, variable_output_dir: _FakeProcess(),
        )
        monkeypatch.setattr(
            "robot_automation_studio.app.wait_robot_process",
            lambda process: RunResult(return_code=0, stdout="", stderr=""),
        )

        studio.run_robot_suite()
        assert studio._run_thread is not None
        studio._run_thread.join(timeout=1.0)
        _process_events_for(120)

        assert captured["active_profile"] == "vrchat"
    finally:
        studio.close()


def test_build_run_diagnostics_context_captures_runtime_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_SETTINGS_PATH", str(tmp_path / "settings.json"))
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.scenario.name = "Unity Flow"
        studio.scenario.scenario_id = "scenario-1234"
        studio.scenario.target = "unity"
        studio.scenario.profiles = {"vrchat": {"description": "", "variables": {}}}
        studio.scenario.execution = {"active_profile": "vrchat"}
        studio._refresh_active_profile_combo()
        studio._set_combo_value(studio.active_profile_combo, "vrchat")
        studio._set_combo_value(studio.execution_mode_combo, "attach")
        studio.window_hint_edit.setText("Unity")
        studio.project_path_edit.setText("D:/VRChatProjects/Ryuon")

        context = studio._build_run_diagnostics_context(tmp_path / "run" / "output.xml")

        assert context["scenario_name"] == "Unity Flow"
        assert context["scenario_id"] == "scenario-1234"
        assert context["target"] == "unity"
        assert context["execution_mode"] == "attach"
        assert context["active_profile"] == "vrchat"
        assert context["window_hint"] == "Unity"
        assert context["unity_project_path"] == "D:/VRChatProjects/Ryuon"
        assert context["subflow_logs_dir"] == str(tmp_path / "run" / "subflows")
    finally:
        studio.close()
