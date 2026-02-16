"""Centralized UI help catalog and search helpers."""

from __future__ import annotations

import re
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
        "Set scenario name.",
        "Human-readable scenario title used in exported Robot and scenario outputs.",
    ),
    "Scenario ID": (
        "Set scenario ID.",
        "Machine-friendly ID used as the scenario key and export filename base.",
    ),
    "Target": (
        "Choose target platform.",
        "Select unity/web/desktop/hybrid to define how steps are interpreted.",
    ),
    "Window Hint": (
        "Set window title hint.",
        "Used to find and focus the target app window during recording and run.",
    ),
    "Execution Mode": (
        "Choose attach or launch.",
        "attach uses an already-open app. launch opens the configured Unity project first.",
    ),
    "Unity Project Path": (
        "Set Unity project path.",
        "Also used for bridge package setup and attach auto-detection fallback.",
    ),
    "Description": (
        "Set description.",
        "Use for intent, prerequisites, or operator notes.",
    ),
    "Variables": (
        "Edit variables.",
        "Define reusable scenario variables and defaults.",
    ),
    "Profiles": (
        "Edit profiles.",
        "Define profile-specific variable overrides.",
    ),
    "Execution/Outputs": (
        "Edit execution/outputs.",
        "Edit runtime execution settings and output metadata as JSON.",
    ),
    "● Start": (
        "Start recording.",
        "Begins capture for the current target window and appends recognized steps.",
    ),
    "■ Stop": (
        "Stop recording.",
        "Ends recording and appends captured steps into the scenario list.",
    ),
    "▶ Run Robot": (
        "Run scenario.",
        "Exports first, then starts Robot execution and writes run artifacts.",
    ),
    "Stop Robot": (
        "Stop robot run.",
        "Stops the running Robot process immediately. You can also use Ctrl+Shift+F12.",
    ),
    "File ▾": (
        "Open file menu.",
        "Provides Save, Load, Full JSON editor, and Help Guide shortcuts.",
    ),
    "+ Add ▾": (
        "Add a step.",
        "Add Click, Drag, Shortcut, Menu, Type, IF, or Group steps.",
    ),
    "🖱 Click": (
        "Add click step.",
        "Insert a click action step manually at the end of the step list.",
    ),
    "↔ Drag": (
        "Add drag step.",
        "Insert a drag/drop action step manually.",
    ),
    "⌨ Shortcut": (
        "Add shortcut step.",
        "Insert a keyboard shortcut action step manually.",
    ),
    "≡ Menu": (
        "Add menu step.",
        "Insert a top-menu navigation action step manually.",
    ),
    "✎ Type": (
        "Add type step.",
        "Insert a text input action step manually.",
    ),
    "IF": (
        "Add control step.",
        "Insert a control-flow step for conditions/loops in scenario v2.",
    ),
    "[] Group": (
        "Add group step.",
        "Insert a group container to organize nested steps.",
    ),
    "✕ Delete": (
        "Delete step.",
        "Removes the currently selected step from the scenario.",
    ),
    "▲ Up": (
        "Move step up.",
        "Changes step order by moving the selected step one position earlier.",
    ),
    "▼ Down": (
        "Move step down.",
        "Changes step order by moving the selected step one position later.",
    ),
    "⎘ Duplicate": (
        "Duplicate step.",
        "Creates a copy of the selected step and inserts it nearby.",
    ),
    "💾 Save": (
        "Save scenario file.",
        "Writes the current scenario model to a .scenario.json file.",
    ),
    "📂 Load": (
        "Load scenario file.",
        "Loads a .scenario.json file into the editor.",
    ),
    "{} Full JSON": (
        "Edit full JSON.",
        "Edit the entire v2 scenario object in one JSON document.",
    ),
    "Step ID": (
        "Set step ID.",
        "Set a stable step identifier used in artifacts and metadata.",
    ),
    "Title": (
        "Set step title.",
        "Readable step name shown in lists and generated guidebook output.",
    ),
    "Kind": (
        "Set step kind.",
        "Choose action/control/group for the selected step.",
    ),
    "Action": (
        "Set action type.",
        "Used when kind=action to determine executable operation type.",
    ),
    "Control": (
        "Set control type.",
        "Used when kind=control to define control-flow operator.",
    ),
    "Condition": (
        "Set run condition.",
        "Expression used to gate step execution when supported by control logic.",
    ),
    "Disabled": (
        "Skip this step.",
        "When enabled, the step is marked as disabled and skipped by compatible runners.",
    ),
    "Continue On Error": (
        "Continue after error.",
        "When enabled, runner may continue even if this step fails.",
    ),
    "Annotations (JSON)": (
        "Edit annotations.",
        "Metadata for visual overlays and guide generation annotations.",
    ),
    "Params (JSON)": (
        "Edit parameters.",
        "Action-specific payload such as selectors, coordinates, and options.",
    ),
    "Apply Step Changes": (
        "Apply step edits.",
        "Validates and writes current Step Details values back into the model.",
    ),
    "Output Dir": (
        "Set output folder.",
        "Base directory where export/run outputs are written.",
    ),
    "Export Name": (
        "Set export name.",
        "Base name used for generated .robot and .scenario.json files.",
    ),
    "Export": (
        "Export scenario files.",
        "Generates .robot and .scenario.json into the configured output directory.",
    ),
    "Run Robot": (
        "Run scenario.",
        "Exports first, then starts Robot execution and writes run artifacts.",
    ),
    "Output Log": (
        "View output log.",
        "Shows recording/run diagnostics, errors, and process output lines.",
    ),
    "Delete step": (
        "Delete step.",
        "Removes the currently selected step from the scenario.",
    ),
    "Move step up": (
        "Move step up.",
        "Changes step order by moving the selected step one position earlier.",
    ),
    "Move step down": (
        "Move step down.",
        "Changes step order by moving the selected step one position later.",
    ),
    "Duplicate step": (
        "Duplicate step.",
        "Creates a copy of the selected step and inserts it nearby.",
    ),
    "Scenario name": (
        "Set scenario name.",
        "Human-readable scenario title used in exported Robot and scenario outputs.",
    ),
    "scenario-id": (
        "Set scenario ID.",
        "Machine-friendly ID used as the scenario key and export filename base.",
    ),
    "Path to Unity project root": (
        "Set Unity project path.",
        "Also used for bridge package setup and attach auto-detection fallback.",
    ),
    "Optional scenario description": (
        "Set description.",
        "Use for intent, prerequisites, or operator notes.",
    ),
    "Output directory": (
        "Set output folder.",
        "Base directory where export/run outputs are written.",
    ),
    "Export name": (
        "Set export name.",
        "Base name used for generated .robot and .scenario.json files.",
    ),
    "Step title": (
        "Set step title.",
        "Readable step name shown in lists and generated guidebook output.",
    ),
    "step-1": (
        "Set step ID.",
        "Set a stable step identifier used in artifacts and metadata.",
    ),
    "click / drag_drop / type_text ...": (
        "Set action type.",
        "Used when kind=action to determine executable operation type.",
    ),
    "if / for_each / while ...": (
        "Set control type.",
        "Used when kind=control to define control-flow operator.",
    ),
    "Optional description": (
        "Set step description.",
        "Use for intent, prerequisites, or operator notes.",
    ),
    "Optional condition expression": (
        "Set run condition.",
        "Expression used to gate step execution when supported by control logic.",
    ),
    "Steps list": (
        "Select a step.",
        "Shows step order; select one item to edit it in the Step tab.",
    ),
    "Run status": (
        "Current run status.",
        "Shows idle/running/stopping state and spinner progress while Robot runs.",
    ),
    "Recording status": (
        "Current record status.",
        "Shows IDLE or REC so you can tell whether recording is active.",
    ),
    "Collapse or expand Output Log.": (
        "Toggle log panel.",
        "Use this to focus on editor controls or inspect logs while running/recording.",
    ),
}

_KNOWN_WIDGET_ID_HELP: dict[str, tuple[str, str]] = {
    "ScenarioNameEdit": (
        "Set scenario name.",
        "Human-readable scenario title used in exported Robot and scenario outputs.",
    ),
    "FileMenuButton": (
        "Open file menu.",
        "Provides Save, Load, Full JSON editor, and Help Guide shortcuts.",
    ),
    "AddStepButton": (
        "Add a step.",
        "Add Click, Drag, Shortcut, Menu, Type, IF, or Group steps.",
    ),
    "StatusPill": (
        "Current run status.",
        "Shows idle/running/stopping state and spinner progress while Robot runs.",
    ),
    "RecIndicator": (
        "Current record status.",
        "Shows IDLE or REC so you can tell whether recording is active.",
    ),
    "LogToggleButton": (
        "Toggle log panel.",
        "Use this to focus on editor controls or inspect logs while running/recording.",
    ),
    "LogText": (
        "View output log.",
        "Shows recording/run diagnostics, errors, and process output lines.",
    ),
    "StepList": (
        "Select a step.",
        "Shows step order; select one item to edit it in the Step tab.",
    ),
    "StepKindCombo": (
        "Set step kind.",
        "Choose action/control/group for the selected step.",
    ),
    "TargetCombo": (
        "Choose target platform.",
        "Select unity/web/desktop/hybrid to define how steps are interpreted.",
    ),
    "ExecutionModeCombo": (
        "Choose attach or launch.",
        "attach uses an already-open app. launch opens the configured Unity project first.",
    ),
}

_CLASS_FALLBACK_SUMMARY: dict[str, str] = {
    "QPushButton": "Run this action.",
    "QToolButton": "Open menu action.",
    "QLineEdit": "Edit text value.",
    "QPlainTextEdit": "Edit multi-line text.",
    "QComboBox": "Choose one option.",
    "QCheckBox": "Toggle this option.",
    "QListWidget": "Select list item.",
    "QLabel": "Read this label.",
    "QSplitter": "Resize split panes.",
    "QScrollArea": "Scroll for controls.",
    "QScrollBar": "Scroll content.",
    "QTabWidget": "Switch tabs.",
    "QMenu": "Choose menu command.",
    "QWidget": "Control container.",
    "QFrame": "Visual separator.",
    "QListView": "List selector.",
    "QStackedWidget": "Switched page view.",
    "QTabBar": "Select a tab.",
    "QSplitterHandle": "Drag to resize panes.",
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
    "Panedwindow": "Resizable split.",
    "TPanedwindow": "Resizable split.",
    "TSeparator": "Visual separator.",
}

_STOP_ROBOT_KEY = "stop robot"
_NORMALIZE_HELP_KEY_RE = re.compile(r"[^a-z0-9]+")


def _normalize_help_key(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "":
        return ""
    return _NORMALIZE_HELP_KEY_RE.sub(" ", text).strip()


_KNOWN_TEXT_HELP_BY_KEY: dict[str, tuple[str, str]] = {
    _normalize_help_key(key): value for key, value in _KNOWN_TEXT_HELP.items()
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
    known_summary, known_detail = _lookup_known_help(title, widget_id)

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


def _lookup_known_help(title: str, widget_id: str) -> tuple[str, str]:
    widget_help = _KNOWN_WIDGET_ID_HELP.get(widget_id)
    if widget_help is not None:
        return widget_help

    if title in _KNOWN_TEXT_HELP:
        return _KNOWN_TEXT_HELP[title]

    normalized_title = _normalize_help_key(title)
    normalized_match = _KNOWN_TEXT_HELP_BY_KEY.get(normalized_title)
    if normalized_match is not None:
        return normalized_match

    if normalized_title.startswith(_STOP_ROBOT_KEY):
        return (
            "Stop robot run.",
            "Stops the running Robot process immediately. Use Ctrl+Shift+F12 as emergency stop.",
        )
    return ("", "")


def _fallback_summary(widget_class: str) -> str:
    return _CLASS_FALLBACK_SUMMARY.get(
        widget_class,
        "Interactive UI element.",
    )


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
