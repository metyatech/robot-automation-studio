from robot_automation_studio.status import format_run_status, next_spinner_index


def test_next_spinner_index_wraps() -> None:
    assert next_spinner_index(0, size=4) == 1
    assert next_spinner_index(1, size=4) == 2
    assert next_spinner_index(2, size=4) == 3
    assert next_spinner_index(3, size=4) == 0


def test_format_run_status_for_known_phases() -> None:
    assert format_run_status("idle", spinner_frame="|") == "Idle"
    assert format_run_status("exporting", spinner_frame="|") == "Exporting scenario |"
    assert format_run_status("starting_robot", spinner_frame="/") == "Starting Robot /"
    assert format_run_status("attaching_unity", spinner_frame="-") == "Attaching to Unity -"
    assert format_run_status("running", spinner_frame="\\") == "Running \\"
    assert format_run_status("stopping", spinner_frame="|") == "Stopping..."


def test_format_run_status_for_unknown_phase_falls_back_to_running() -> None:
    assert format_run_status("unknown", spinner_frame="*") == "Running *"
