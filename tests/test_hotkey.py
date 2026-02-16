import pytest

from robot_automation_studio.hotkey import (
    DEFAULT_STOP_HOTKEY_LABEL,
    FALLBACK_STOP_HOTKEY_LABELS,
    parse_hotkey_label,
)


def test_parse_hotkey_label_normalizes_case_and_order() -> None:
    spec = parse_hotkey_label("shift+alt+f12")
    assert spec.label == "Alt+Shift+F12"
    assert spec.bind == "<alt>+<shift>+<f12>"
    assert spec.main_key == "F12"
    assert spec.required_modifiers == frozenset({"ALT", "SHIFT"})


def test_parse_hotkey_label_supports_letter_main_key() -> None:
    spec = parse_hotkey_label("ctrl+alt+k")
    assert spec.label == "Ctrl+Alt+K"
    assert spec.bind == "<ctrl>+<alt>+<k>"


def test_parse_hotkey_label_rejects_missing_modifier() -> None:
    with pytest.raises(ValueError, match="modifier"):
        parse_hotkey_label("F12")


def test_parse_hotkey_label_rejects_multiple_main_keys() -> None:
    with pytest.raises(ValueError, match="exactly one main key"):
        parse_hotkey_label("Ctrl+F12+F11")


def test_default_hotkey_is_present_in_fallback_list() -> None:
    assert DEFAULT_STOP_HOTKEY_LABEL in FALLBACK_STOP_HOTKEY_LABELS
