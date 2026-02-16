from robot_automation_studio import ui_help
from robot_automation_studio.ui_help import HelpEntry, build_help_entry, filter_help_entries


def test_build_help_entry_uses_explicit_summary_and_detail() -> None:
    entry = build_help_entry(
        widget_id="root.run_button",
        widget_class="TButton",
        widget_text="Run Robot",
        explicit_summary="Run the current scenario.",
        explicit_detail="Exports then starts Robot execution.",
    )

    assert entry.summary == "Run the current scenario."
    assert entry.detail == "Exports then starts Robot execution."
    assert entry.title == "Run Robot"


def test_build_help_entry_uses_known_text_help_when_explicit_is_missing() -> None:
    entry = build_help_entry(
        widget_id="root.stop_button",
        widget_class="TButton",
        widget_text="Stop Robot (Ctrl+Shift+F12)",
    )

    assert "stop robot run" in entry.summary.lower()
    assert "Ctrl+Shift+F12" in entry.detail


def test_build_help_entry_falls_back_to_widget_class_description() -> None:
    entry = build_help_entry(
        widget_id="root.some_entry",
        widget_class="TEntry",
        widget_text="",
    )

    assert entry.title == "TEntry"
    assert entry.summary == "Input field."


def test_build_help_entry_uses_normalized_lookup_for_placeholder_like_text() -> None:
    entry = build_help_entry(
        widget_id="ScenarioIdEdit",
        widget_class="QLineEdit",
        widget_text="scenario-id",
    )

    assert "scenario id" in entry.summary.lower()


def test_build_help_entry_uses_widget_id_help_when_available() -> None:
    entry = build_help_entry(
        widget_id="LogText",
        widget_class="QPlainTextEdit",
        widget_text="",
    )

    assert "output log" in entry.summary.lower()


def test_build_help_entry_unknown_class_no_longer_uses_ui_component_text() -> None:
    entry = build_help_entry(
        widget_id="root.unknown",
        widget_class="UnknownWidget",
        widget_text="",
    )

    assert entry.summary != "UI component."
    assert "interactive ui element" in entry.summary.lower()


def test_filter_help_entries_matches_title_summary_and_detail() -> None:
    entries = [
        HelpEntry(
            widget_id="1",
            widget_class="TButton",
            title="Run Robot",
            summary="Run current scenario.",
            detail="Exports and runs Robot.",
        ),
        HelpEntry(
            widget_id="2",
            widget_class="TEntry",
            title="Scenario Name",
            summary="Set scenario display name.",
            detail="Used in exports.",
        ),
    ]

    assert [entry.widget_id for entry in filter_help_entries(entries, "run")] == ["1"]
    assert [entry.widget_id for entry in filter_help_entries(entries, "exports")] == ["1", "2"]
    assert [entry.widget_id for entry in filter_help_entries(entries, "name")] == ["2"]


def test_help_summary_texts_stay_concise_for_tooltips() -> None:
    max_len = 24
    assert all(len(summary) <= max_len for summary, _ in ui_help._KNOWN_TEXT_HELP.values())
    assert all(len(summary) <= max_len for summary, _ in ui_help._KNOWN_WIDGET_ID_HELP.values())
    assert all(len(summary) <= max_len for summary in ui_help._CLASS_FALLBACK_SUMMARY.values())


def test_build_help_entry_supports_japanese_locale() -> None:
    entry = build_help_entry(
        widget_id="StepKindCombo",
        widget_class="QComboBox",
        widget_text="種別",
        locale="ja",
    )
    assert "種別" in entry.summary
