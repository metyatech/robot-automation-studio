"""Centralized UI help catalog and search helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpEntry:
    """Normalized help metadata for one GUI widget."""

    widget_id: str
    widget_class: str
    title: str
    summary: str
    detail: str


_KNOWN_TEXT_HELP: dict[str, tuple[str, str]] = {
    "Scenario Name": (
        "Set the scenario display name.",
        "Human-readable scenario title used in exported Robot and scenario outputs.",
    ),
    "Scenario ID": (
        "Set a stable scenario identifier.",
        "Machine-friendly ID used as the scenario key and export filename base.",
    ),
    "Target": (
        "Choose the scenario target platform.",
        "Select unity/web/desktop/hybrid to define how steps are interpreted.",
    ),
    "Window Hint": (
        "Specify the target window title hint.",
        "Used to find and focus the target app window during recording and run.",
    ),
    "Execution Mode": (
        "Select attach or launch execution.",
        "attach uses an already-open app. launch opens the configured Unity project first.",
    ),
    "Unity Project Path": (
        "Set the Unity project path for launch mode.",
        "Also used for bridge package setup and attach auto-detection fallback.",
    ),
    "Description": (
        "Add an optional scenario description.",
        "Use for intent, prerequisites, or operator notes.",
    ),
    "Variables": (
        "Open variables editor.",
        "Define reusable scenario variables and defaults.",
    ),
    "Profiles": (
        "Open profiles editor.",
        "Define profile-specific variable overrides.",
    ),
    "Execution/Outputs": (
        "Open execution/outputs editor.",
        "Edit runtime execution settings and output metadata as JSON.",
    ),
    "● Start": (
        "Start recording user actions.",
        "Begins capture for the current target window and appends recognized steps.",
    ),
    "■ Stop": (
        "Stop recording.",
        "Ends recording and appends captured steps into the scenario list.",
    ),
    "▶ Run Robot": (
        "Run the current scenario with Robot.",
        "Exports first, then starts Robot execution and writes run artifacts.",
    ),
    "Stop Robot": (
        "Stop active Robot execution.",
        "Stops the running Robot process immediately. You can also use Ctrl+Shift+F12.",
    ),
    "File ▾": (
        "Open file/help menu.",
        "Provides Save, Load, Full JSON editor, and Help Guide shortcuts.",
    ),
    "+ Add ▾": (
        "Open step-add menu.",
        "Add Click, Drag, Shortcut, Menu, Type, IF, or Group steps.",
    ),
    "🖱 Click": (
        "Add a click step.",
        "Insert a click action step manually at the end of the step list.",
    ),
    "↔ Drag": (
        "Add a drag step.",
        "Insert a drag/drop action step manually.",
    ),
    "⌨ Shortcut": (
        "Add a shortcut step.",
        "Insert a keyboard shortcut action step manually.",
    ),
    "≡ Menu": (
        "Add a menu step.",
        "Insert a top-menu navigation action step manually.",
    ),
    "✎ Type": (
        "Add a type-text step.",
        "Insert a text input action step manually.",
    ),
    "IF": (
        "Add a control step.",
        "Insert a control-flow step for conditions/loops in scenario v2.",
    ),
    "[] Group": (
        "Add a group step.",
        "Insert a group container to organize nested steps.",
    ),
    "✕ Delete": (
        "Delete the selected step.",
        "Removes the currently selected step from the scenario.",
    ),
    "▲ Up": (
        "Move selected step up.",
        "Changes step order by moving the selected step one position earlier.",
    ),
    "▼ Down": (
        "Move selected step down.",
        "Changes step order by moving the selected step one position later.",
    ),
    "⎘ Duplicate": (
        "Duplicate selected step.",
        "Creates a copy of the selected step and inserts it nearby.",
    ),
    "💾 Save": (
        "Save scenario JSON.",
        "Writes the current scenario model to a .scenario.json file.",
    ),
    "📂 Load": (
        "Load scenario JSON.",
        "Loads a .scenario.json file into the editor.",
    ),
    "{} Full JSON": (
        "Open full scenario JSON editor.",
        "Edit the entire v2 scenario object in one JSON document.",
    ),
    "Step ID": (
        "Edit selected step ID.",
        "Set a stable step identifier used in artifacts and metadata.",
    ),
    "Title": (
        "Edit selected step title.",
        "Readable step name shown in lists and generated guidebook output.",
    ),
    "Kind": (
        "Edit selected step kind.",
        "Choose action/control/group for the selected step.",
    ),
    "Action": (
        "Edit selected action name.",
        "Used when kind=action to determine executable operation type.",
    ),
    "Control": (
        "Edit selected control name.",
        "Used when kind=control to define control-flow operator.",
    ),
    "Condition": (
        "Edit optional step condition.",
        "Expression used to gate step execution when supported by control logic.",
    ),
    "Disabled": (
        "Disable selected step.",
        "When enabled, the step is marked as disabled and skipped by compatible runners.",
    ),
    "Continue On Error": (
        "Continue on error flag.",
        "When enabled, runner may continue even if this step fails.",
    ),
    "Annotations (JSON)": (
        "Edit step annotations JSON.",
        "Metadata for visual overlays and guide generation annotations.",
    ),
    "Params (JSON)": (
        "Edit step parameters JSON.",
        "Action-specific payload such as selectors, coordinates, and options.",
    ),
    "Apply Step Changes": (
        "Apply edits to selected step.",
        "Validates and writes current Step Details values back into the model.",
    ),
    "Output Dir": (
        "Set artifact output directory.",
        "Base directory where export/run outputs are written.",
    ),
    "Export Name": (
        "Set export suite name.",
        "Base name used for generated .robot and .scenario.json files.",
    ),
    "Export": (
        "Export Robot and scenario files.",
        "Generates .robot and .scenario.json into the configured output directory.",
    ),
    "Run Robot": (
        "Run the current scenario with Robot.",
        "Exports first, then starts Robot execution and writes run artifacts.",
    ),
    "Output Log": (
        "Runtime log output area.",
        "Shows recording/run diagnostics, errors, and process output lines.",
    ),
}

_CLASS_FALLBACK_SUMMARY: dict[str, str] = {
    "TButton": "Button action.",
    "Button": "Button action.",
    "TEntry": "Input field.",
    "Entry": "Input field.",
    "TCombobox": "Selectable input field.",
    "Combobox": "Selectable input field.",
    "Text": "Multi-line text editor.",
    "Listbox": "List selection view.",
    "TCheckbutton": "Toggle option.",
    "Checkbutton": "Toggle option.",
    "TScrollbar": "Scroll control.",
    "Scrollbar": "Scroll control.",
    "Label": "Display label.",
    "TLabel": "Display label.",
    "Frame": "Layout container.",
    "TFrame": "Layout container.",
    "Panedwindow": "Resizable split container.",
    "TPanedwindow": "Resizable split container.",
    "TSeparator": "Visual separator.",
}


def build_help_entry(
    widget_id: str,
    widget_class: str,
    widget_text: str,
    explicit_summary: str | None = None,
    explicit_detail: str | None = None,
) -> HelpEntry:
    """Build one normalized help entry from explicit text and fallbacks."""

    title = _normalize_title(widget_text, widget_class)
    known_summary, known_detail = _lookup_known_help(title)

    summary = _normalize_text(explicit_summary) or known_summary or _fallback_summary(widget_class)
    detail = _normalize_text(explicit_detail) or known_detail or summary

    return HelpEntry(
        widget_id=widget_id,
        widget_class=widget_class,
        title=title,
        summary=summary,
        detail=detail,
    )


def filter_help_entries(entries: list[HelpEntry], query: str) -> list[HelpEntry]:
    """Filter help entries by title/summary/detail/class text."""

    needle = _normalize_text(query).lower()
    if needle == "":
        return list(entries)

    result: list[HelpEntry] = []
    for entry in entries:
        haystack = " ".join([entry.title, entry.summary, entry.detail, entry.widget_class]).lower()
        if needle in haystack:
            result.append(entry)
    return result


def _lookup_known_help(title: str) -> tuple[str, str]:
    if title in _KNOWN_TEXT_HELP:
        return _KNOWN_TEXT_HELP[title]

    if title.startswith("Stop Robot"):
        return (
            "Stop active Robot execution.",
            "Stops the running Robot process immediately. Use Ctrl+Shift+F12 as emergency stop.",
        )
    return ("", "")


def _fallback_summary(widget_class: str) -> str:
    return _CLASS_FALLBACK_SUMMARY.get(widget_class, "UI component.")


def _normalize_title(widget_text: str, widget_class: str) -> str:
    text = _normalize_text(widget_text)
    if text != "":
        return text
    class_text = _normalize_text(widget_class)
    return class_text if class_text != "" else "Widget"


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()
