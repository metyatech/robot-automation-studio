import warnings

from robot_automation_studio.recorder import _import_pywinauto_with_warning_filters


def test_import_pywinauto_with_warning_filters_suppresses_known_warnings() -> None:
    def fake_import(_module_name: str) -> None:
        warnings.warn(
            "Apply externally defined coinit_flags: 2",
            UserWarning,
            stacklevel=2,
        )
        warnings.warn("Revert to STA COM threading mode", UserWarning, stacklevel=2)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        _import_pywinauto_with_warning_filters(fake_import)

    assert captured == []
