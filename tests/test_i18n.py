import locale

from robot_automation_studio.i18n import detect_default_locale


def test_detect_default_locale_normalizes_explicit_locale() -> None:
    assert detect_default_locale("ja-JP") == "ja"
    assert detect_default_locale("en_US") == "en"
    assert detect_default_locale("Japanese_Japan") == "ja"
    assert detect_default_locale("English_United States") == "en"


def test_detect_default_locale_prefers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ROBOT_AUTOMATION_STUDIO_LOCALE", "ja")
    assert detect_default_locale() == "ja"


def test_detect_default_locale_uses_system_locale(monkeypatch) -> None:
    monkeypatch.delenv("ROBOT_AUTOMATION_STUDIO_LOCALE", raising=False)
    monkeypatch.setattr(locale, "getlocale", lambda *args, **kwargs: ("ja_JP", "UTF-8"))
    assert detect_default_locale() == "ja"
