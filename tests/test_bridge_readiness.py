from robot_automation_studio.bridge_readiness import build_recording_readiness_timeouts


def test_build_recording_readiness_timeouts_attach_without_manifest_change() -> None:
    assert build_recording_readiness_timeouts(changed=False, execution_mode="attach") == [
        3.0,
        25.0,
    ]


def test_build_recording_readiness_timeouts_attach_with_manifest_change() -> None:
    assert build_recording_readiness_timeouts(changed=True, execution_mode="attach") == [
        15.0,
        25.0,
    ]


def test_build_recording_readiness_timeouts_launch_mode() -> None:
    assert build_recording_readiness_timeouts(changed=False, execution_mode="launch") == [3.0]
