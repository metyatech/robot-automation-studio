from PySide6.QtWidgets import QApplication

from robot_automation_studio.app import StudioApp
from robot_automation_studio.models import Step


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if isinstance(app, QApplication):
        return app
    raise RuntimeError("A non-GUI QCoreApplication instance is already running.")


def test_focus_validation_issue_location_selects_step_and_params() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        studio.scenario.steps = [
            Step(action="click", title="step-1", params={"title": "File"}),
            Step(action="click", title="step-2", params={"title": "Edit"}),
        ]
        studio.refresh_steps()

        focused = studio.focus_validation_issue_location("steps[1].target.uia.title")

        assert focused is True
        assert studio.selected_index == 1
        assert studio.main_tabs.currentIndex() == studio.step_tab_index
    finally:
        studio.close()


def test_focus_validation_issue_location_handles_active_profile() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        focused = studio.focus_validation_issue_location("execution.active_profile")

        assert focused is True
        assert studio.main_tabs.currentIndex() == studio.scenario_tab_index
    finally:
        studio.close()


def test_focus_validation_issue_location_returns_false_for_unknown_location() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        focused = studio.focus_validation_issue_location("unsupported.path.value")

        assert focused is False
    finally:
        studio.close()


def test_focus_validation_issue_location_handles_variables_profiles_and_outputs() -> None:
    _ensure_qapp()
    studio = StudioApp(initial_locale="en")
    try:
        focused_variables = studio.focus_validation_issue_location(
            "variables.unity_project_path.default"
        )
        focused_profiles = studio.focus_validation_issue_location("profiles.vrchat.variables.foo")
        focused_outputs = studio.focus_validation_issue_location("outputs.docs.markdown")

        assert focused_variables is True
        assert focused_profiles is True
        assert focused_outputs is True
        assert studio.main_tabs.currentIndex() in {
            studio.scenario_tab_index,
            studio.export_tab_index,
        }
    finally:
        studio.close()
