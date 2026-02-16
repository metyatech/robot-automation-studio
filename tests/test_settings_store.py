from pathlib import Path

from robot_automation_studio.settings_store import (
    StudioUiSettings,
    load_ui_settings,
    save_ui_settings,
)


def test_load_ui_settings_returns_defaults_for_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing-settings.json"
    settings = load_ui_settings(path)
    assert settings.locale == "en"
    assert settings.target == "unity"
    assert settings.window_hint == "Unity"
    assert settings.execution_mode == "attach"


def test_save_and_load_ui_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_ui_settings(
        StudioUiSettings(
            locale="ja",
            target="desktop",
            window_hint="Unity 2022",
            execution_mode="launch",
            unity_project_path="D:/VRChatProjects/Ryuon",
            stop_hotkey_label="Ctrl+Alt+F12",
        ),
        path,
    )
    loaded = load_ui_settings(path)
    assert loaded.locale == "ja"
    assert loaded.target == "desktop"
    assert loaded.window_hint == "Unity 2022"
    assert loaded.execution_mode == "launch"
    assert loaded.unity_project_path == "D:/VRChatProjects/Ryuon"
    assert loaded.stop_hotkey_label == "Ctrl+Alt+F12"


def test_load_ui_settings_normalizes_invalid_payload(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"locale":"??","target":"invalid","window_hint":"","execution_mode":"???","stop_hotkey_label":""}',
        encoding="utf-8",
    )
    loaded = load_ui_settings(path)
    assert loaded.locale == "en"
    assert loaded.target == "unity"
    assert loaded.window_hint == "Unity"
    assert loaded.execution_mode == "attach"
    assert loaded.stop_hotkey_label == "Alt+Shift+F12"
