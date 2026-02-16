"""Centralized UI help catalog and search helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .i18n import normalize_locale


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
    "Active Profile": (
        "Choose active profile.",
        "Applies profile-specific variable overrides for export and run.",
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
    "Validate": (
        "Run validation.",
        "Checks scenario/profile/step validity before export or run.",
    ),
    "Profile Diff": (
        "Preview diff.",
        "Compare resolved scenario values between two profiles.",
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
        "Stops the running Robot process immediately. You can also use Alt+Shift+F12.",
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
    "Insert Params Template": (
        "Insert params template.",
        "Auto-fills Params (JSON) with a safe starter template for the current action.",
    ),
    "Apply Step Changes": (
        "Apply step edits.",
        "Validates and writes current Step Details values back into the model.",
    ),
    "Output Dir": (
        "Set output folder.",
        "Base directory where export/run outputs are written.",
    ),
    "Open Dir": (
        "Open output directory.",
        "Open the configured output directory in your file explorer.",
    ),
    "Export Name": (
        "Set export name.",
        "Base name used for generated .robot and .scenario.json files.",
    ),
    "Export": (
        "Export scenario files.",
        "Generates .robot and .scenario.json into the configured output directory.",
    ),
    "Copy Issue": (
        "Copy selected issue.",
        "Copy currently selected validation issue details to clipboard.",
    ),
    "Copy All": (
        "Copy all issues.",
        "Copy all validation issues as plain text for sharing.",
    ),
    "Copy Summary": (
        "Copy summary.",
        "Copy concise run diagnostics summary text to clipboard.",
    ),
    "Copy JSON": (
        "Copy diagnostics JSON.",
        "Copy raw run diagnostics JSON text to clipboard.",
    ),
    "Open Diagnostics Dir": (
        "Open diagnostics folder.",
        "Open run diagnostics folder in your file explorer.",
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
    "SubflowTimeoutEdit": (
        "Set subflow timeout.",
        "Use seconds, blank (=3600), or ${variable} for run_subflow and parallel waits.",
    ),
    "ValidateButton": (
        "Run validation.",
        "Checks scenario/profile/step validity before export or run.",
    ),
    "ProfileDiffButton": (
        "Preview profile diff.",
        "Compare resolved scenario values between two profiles.",
    ),
    "ActiveProfileCombo": (
        "Choose active profile.",
        "Applies profile-specific variable overrides for export and run.",
    ),
    "ParamsTemplateButton": (
        "Insert params template.",
        "Auto-fills Params (JSON) with a safe starter template for the current action.",
    ),
    "StepValidationLabel": (
        "Check step validity.",
        "Shows whether the current step can be exported and run, with immediate error details.",
    ),
    "LanguageCombo": (
        "Choose language.",
        "Switch UI language between English and Japanese.",
    ),
    "HotkeyButton": (
        "Set stop hotkey.",
        (
            "Open a dialog and press key combination directly "
            "to configure emergency stop for record/run."
        ),
    ),
    "VariablesButton": (
        "Edit variables.",
        "Open Variables Editor for reusable scenario variables.",
    ),
    "ProfilesButton": (
        "Edit profiles.",
        "Open Profiles Editor for profile-specific overrides.",
    ),
    "ExecutionOutputsButton": (
        "Edit execution/outputs.",
        "Open execution and outputs JSON editor.",
    ),
    "OpenOutputDirButton": (
        "Open output directory.",
        "Open the configured output directory in your file explorer.",
    ),
    "OpenSubflowLogsDirButton": (
        "Open subflow logs.",
        "Open the subflows logs directory generated by run_subflow/parallel.",
    ),
    "DeleteStepButton": (
        "Delete step.",
        "Removes the currently selected step from the scenario.",
    ),
    "MoveStepUpButton": (
        "Move step up.",
        "Changes step order by moving the selected step one position earlier.",
    ),
    "MoveStepDownButton": (
        "Move step down.",
        "Changes step order by moving the selected step one position later.",
    ),
    "DuplicateStepButton": (
        "Duplicate step.",
        "Creates a copy of the selected step and inserts it nearby.",
    ),
}

_KNOWN_TEXT_HELP_JA: dict[str, tuple[str, str]] = {
    "シナリオ名": (
        "シナリオ名を設定します。",
        "エクスポートされる Robot とシナリオ出力で使う表示名です。",
    ),
    "シナリオID": (
        "シナリオIDを設定します。",
        "シナリオのキーや出力ファイル名に使う識別子です。",
    ),
    "対象": (
        "対象プラットフォームを選択します。",
        "unity/web/desktop/hybrid の実行対象を選びます。",
    ),
    "ウィンドウヒント": (
        "ウィンドウ名のヒントを設定します。",
        "記録/実行時に対象ウィンドウを特定するために使います。",
    ),
    "実行モード": (
        "実行モードを選択します。",
        "attach は既存アプリへ接続、launch は Unity を起動して実行します。",
    ),
    "適用プロファイル": (
        "適用プロファイルを選択します。",
        "エクスポート/実行時にプロファイル別の変数上書きを適用します。",
    ),
    "Unity プロジェクトパス": (
        "Unity プロジェクトパスを設定します。",
        "bridge 設定や attach 時の自動検出フォールバックに使います。",
    ),
    "説明": (
        "説明を設定します。",
        "目的、前提条件、運用メモに使います。",
    ),
    "変数": (
        "変数を編集します。",
        "再利用できるシナリオ変数とデフォルト値を管理します。",
    ),
    "プロファイル": (
        "プロファイルを編集します。",
        "プロファイル単位の変数上書きを管理します。",
    ),
    "実行/出力": (
        "実行/出力設定を編集します。",
        "実行設定と出力メタデータを JSON で編集します。",
    ),
    "検証": (
        "事前検証を実行します。",
        "エクスポート/実行前にシナリオの妥当性を検査します。",
    ),
    "プロファイル差分": (
        "プロファイル差分を表示します。",
        "2つのプロファイル間で解決後シナリオの差分を確認します。",
    ),
    "● 記録開始": (
        "記録を開始します。",
        "現在の対象ウィンドウの操作記録を開始します。",
    ),
    "■ 記録停止": (
        "記録を停止します。",
        "記録した操作をステップとしてシナリオに追加します。",
    ),
    "▶ Robot 実行": (
        "シナリオを実行します。",
        "エクスポート後に Robot 実行を開始します。",
    ),
    "Robot 停止": (
        "Robot 実行を停止します。",
        "実行中の Robot プロセスを即時停止します。",
    ),
    "ファイル ▾": (
        "ファイルメニューを開きます。",
        "保存、読込、全体 JSON、ヘルプガイドを開きます。",
    ),
    "+ 追加 ▾": (
        "ステップを追加します。",
        "Click、Drag、Shortcut、Menu、Type、IF、Group を追加します。",
    ),
    "ステップID": (
        "ステップIDを設定します。",
        "成果物やメタデータで使う安定IDです。",
    ),
    "タイトル": (
        "ステップタイトルを設定します。",
        "一覧表示やガイド出力で使う読みやすい名前です。",
    ),
    "種別": (
        "ステップ種別を設定します。",
        "action/control/group を選択します。",
    ),
    "アクション": (
        "アクション種別を設定します。",
        "kind=action のときの実行操作を指定します。",
    ),
    "制御": (
        "制御種別を設定します。",
        "kind=control のときの制御フロー種別を指定します。",
    ),
    "条件": (
        "実行条件を設定します。",
        "制御ロジックで使う条件式です。",
    ),
    "無効": (
        "このステップをスキップします。",
        "有効化すると互換ランナーでこのステップをスキップします。",
    ),
    "エラー時も継続": (
        "エラー後も継続します。",
        "有効化すると失敗後も実行継続できる場合があります。",
    ),
    "注釈": (
        "注釈を編集します。",
        "可視化オーバーレイやガイド生成用メタデータです。",
    ),
    "パラメータ": (
        "パラメータを編集します。",
        "セレクタや座標などアクション固有データです。",
    ),
    "パラメータ雛形を挿入": (
        "パラメータ雛形を挿入します。",
        "現在のアクションに対応する Params(JSON) の初期雛形を自動入力します。",
    ),
    "ステップ変更を適用": (
        "ステップ変更を適用します。",
        "現在の項目値を検証してモデルに反映します。",
    ),
    "出力先": (
        "出力フォルダを設定します。",
        "エクスポート/実行成果物の保存先です。",
    ),
    "フォルダを開く": (
        "出力フォルダを開きます。",
        "設定中の出力フォルダをエクスプローラーで開きます。",
    ),
    "出力名": (
        "出力名を設定します。",
        ".robot / .scenario.json のベース名です。",
    ),
    "エクスポート": (
        "シナリオを出力します。",
        ".robot と .scenario.json を生成します。",
    ),
    "選択項目をコピー": (
        "選択中の検証エラーをコピーします。",
        "現在選択している検証エラーの詳細をクリップボードへコピーします。",
    ),
    "全件コピー": (
        "検証エラーを全件コピーします。",
        "検証エラー一覧を共有用テキストとしてクリップボードへコピーします。",
    ),
    "要約をコピー": (
        "診断要約をコピーします。",
        "実行診断の要約テキストをクリップボードへコピーします。",
    ),
    "JSONをコピー": (
        "診断JSONをコピーします。",
        "実行診断の生JSONテキストをクリップボードへコピーします。",
    ),
    "診断フォルダを開く": (
        "診断フォルダを開きます。",
        "実行診断ファイルの保存フォルダをエクスプローラーで開きます。",
    ),
    "出力ログ": (
        "出力ログを表示します。",
        "記録/実行の診断ログやエラーを表示します。",
    ),
    "ステップを削除": (
        "ステップを削除します。",
        "現在選択中のステップをシナリオから削除します。",
    ),
    "ステップを上へ移動": (
        "ステップを上へ移動します。",
        "選択中のステップを1つ前へ移動します。",
    ),
    "ステップを下へ移動": (
        "ステップを下へ移動します。",
        "選択中のステップを1つ後ろへ移動します。",
    ),
    "ステップを複製": (
        "ステップを複製します。",
        "選択中のステップを複製して近くに挿入します。",
    ),
    "ステップ一覧": (
        "ステップを選択します。",
        "ステップ順を表示し、選択した項目を編集できます。",
    ),
}

_KNOWN_WIDGET_ID_HELP_JA: dict[str, tuple[str, str]] = {
    "ScenarioNameEdit": (
        "シナリオ名を設定します。",
        "エクスポートされる Robot とシナリオ出力で使う表示名です。",
    ),
    "FileMenuButton": (
        "ファイルメニューを開きます。",
        "保存、読込、全体 JSON、ヘルプガイドを開きます。",
    ),
    "AddStepButton": (
        "ステップを追加します。",
        "Click、Drag、Shortcut、Menu、Type、IF、Group を追加します。",
    ),
    "StatusPill": (
        "実行状態を表示します。",
        "idle/running/stopping とスピナーの状態を表示します。",
    ),
    "RecIndicator": (
        "記録状態を表示します。",
        "記録中か待機中かを表示します。",
    ),
    "LogToggleButton": (
        "ログ表示を切り替えます。",
        "出力ログの折りたたみ/展開を切り替えます。",
    ),
    "LogText": (
        "出力ログを表示します。",
        "記録/実行の診断ログやエラーを表示します。",
    ),
    "StepList": (
        "ステップを選択します。",
        "表示順のステップを選んで編集できます。",
    ),
    "StepKindCombo": (
        "ステップ種別を設定します。",
        "action/control/group を選択します。",
    ),
    "TargetCombo": (
        "対象プラットフォームを選択します。",
        "unity/web/desktop/hybrid を選びます。",
    ),
    "ExecutionModeCombo": (
        "実行モードを選択します。",
        "attach は既存接続、launch は起動実行です。",
    ),
    "SubflowTimeoutEdit": (
        "子フロー待機秒数を設定します。",
        "run_subflow / parallel 待機のタイムアウト。秒数、空欄(=3600)、${変数} を指定できます。",
    ),
    "ValidateButton": (
        "事前検証を実行します。",
        "エクスポート/実行前にシナリオの妥当性を検査します。",
    ),
    "ProfileDiffButton": (
        "プロファイル差分を表示します。",
        "2つのプロファイル間で解決後シナリオの差分を確認します。",
    ),
    "ActiveProfileCombo": (
        "適用プロファイルを選択します。",
        "エクスポート/実行時にプロファイル別の変数上書きを適用します。",
    ),
    "ParamsTemplateButton": (
        "パラメータ雛形を挿入します。",
        "現在のアクションに対応する Params(JSON) の初期雛形を自動入力します。",
    ),
    "StepValidationLabel": (
        "ステップ妥当性を確認します。",
        "現在のステップが実行/エクスポート可能かを即時に表示し、エラー内容も確認できます。",
    ),
    "LanguageCombo": (
        "表示言語を選択します。",
        "English / 日本語 の UI 表示を切り替えます。",
    ),
    "HotkeyButton": (
        "停止ホットキーを設定します。",
        "ダイアログを開き、押したキーの組み合わせで記録/実行の緊急停止キーを設定します。",
    ),
    "VariablesButton": (
        "変数を編集します。",
        "再利用可能なシナリオ変数を編集します。",
    ),
    "ProfilesButton": (
        "プロファイルを編集します。",
        "プロファイル別の上書き設定を編集します。",
    ),
    "ExecutionOutputsButton": (
        "実行/出力設定を編集します。",
        "execution と outputs の JSON を編集します。",
    ),
    "OpenOutputDirButton": (
        "出力フォルダを開きます。",
        "設定中の出力フォルダをエクスプローラーで開きます。",
    ),
    "OpenSubflowLogsDirButton": (
        "子フローログを開きます。",
        "run_subflow/parallel で生成された subflows ログフォルダを開きます。",
    ),
    "DeleteStepButton": (
        "ステップを削除します。",
        "現在選択中のステップをシナリオから削除します。",
    ),
    "MoveStepUpButton": (
        "ステップを上へ移動します。",
        "選択中のステップを1つ前へ移動します。",
    ),
    "MoveStepDownButton": (
        "ステップを下へ移動します。",
        "選択中のステップを1つ後ろへ移動します。",
    ),
    "DuplicateStepButton": (
        "ステップを複製します。",
        "選択中のステップを複製して近くに挿入します。",
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
    "QLabel": "",
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
    "Label": "",
    "TLabel": "",
    "Frame": "Layout container.",
    "TFrame": "Layout container.",
    "Panedwindow": "Resizable split.",
    "TPanedwindow": "Resizable split.",
    "TSeparator": "Visual separator.",
}

_CLASS_FALLBACK_SUMMARY_JA: dict[str, str] = {
    "QPushButton": "この操作を実行します。",
    "QToolButton": "メニュー操作を開きます。",
    "QLineEdit": "文字列を編集します。",
    "QPlainTextEdit": "複数行テキストを編集します。",
    "QComboBox": "項目を選択します。",
    "QCheckBox": "オプションを切り替えます。",
    "QListWidget": "一覧項目を選択します。",
    "QLabel": "",
    "QSplitter": "ペインサイズを変更します。",
    "QScrollArea": "スクロール可能領域です。",
    "QScrollBar": "スクロールします。",
    "QTabWidget": "タブを切り替えます。",
    "QMenu": "メニュー項目を選択します。",
    "QWidget": "UIコンテナです。",
    "QFrame": "区切り要素です。",
    "QListView": "一覧選択ビューです。",
    "QStackedWidget": "切替表示コンテナです。",
    "QTabBar": "タブを選択します。",
    "QSplitterHandle": "ドラッグしてサイズを変更します。",
}

_STOP_ROBOT_KEY_EN = "stop robot"
_STOP_ROBOT_KEY_JA = "robot 停止"
_NORMALIZE_HELP_KEY_RE = re.compile(r"[^\w]+", re.UNICODE)


def _normalize_help_key(value: str) -> str:
    text = str(value or "").strip().casefold()
    if text == "":
        return ""
    return _NORMALIZE_HELP_KEY_RE.sub(" ", text).strip()


_KNOWN_TEXT_HELP_BY_KEY: dict[str, tuple[str, str]] = {
    _normalize_help_key(key): value for key, value in _KNOWN_TEXT_HELP.items()
}
_KNOWN_TEXT_HELP_BY_KEY_JA: dict[str, tuple[str, str]] = {
    _normalize_help_key(key): value for key, value in _KNOWN_TEXT_HELP_JA.items()
}


def build_help_entry(
    widget_id: str,
    widget_class: str,
    widget_text: str,
    explicit_summary: str | None = None,
    explicit_detail: str | None = None,
    locale: str = "en",
) -> HelpEntry:
    """Build one normalized help entry from explicit text and fallbacks."""

    title = _normalize_title(widget_text, widget_class)
    normalized_locale = normalize_locale(locale)
    known_summary, known_detail = _lookup_known_help(title, widget_id, locale=normalized_locale)

    summary = (
        _normalize_text(explicit_summary)
        or known_summary
        or _fallback_summary(widget_class, locale=normalized_locale)
    )
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


def _lookup_known_help(title: str, widget_id: str, *, locale: str) -> tuple[str, str]:
    widget_help_map = _KNOWN_WIDGET_ID_HELP if locale == "en" else _KNOWN_WIDGET_ID_HELP_JA
    text_help_map = _KNOWN_TEXT_HELP if locale == "en" else _KNOWN_TEXT_HELP_JA
    text_help_by_key_map = _KNOWN_TEXT_HELP_BY_KEY if locale == "en" else _KNOWN_TEXT_HELP_BY_KEY_JA

    widget_help = widget_help_map.get(widget_id)
    if widget_help is not None:
        return widget_help

    if title in text_help_map:
        return text_help_map[title]

    normalized_title = _normalize_help_key(title)
    normalized_match = text_help_by_key_map.get(normalized_title)
    if normalized_match is not None:
        return normalized_match

    if locale == "ja":
        if normalized_title.startswith(_normalize_help_key(_STOP_ROBOT_KEY_JA)):
            return (
                "Robot 実行を停止します。",
                "実行中の Robot プロセスを停止します。緊急停止は Alt+Shift+F12 を使用します。",
            )
    elif normalized_title.startswith(_normalize_help_key(_STOP_ROBOT_KEY_EN)):
        return (
            "Stop robot run.",
            "Stops the running Robot process immediately. Use Alt+Shift+F12 as emergency stop.",
        )
    return ("", "")


def _fallback_summary(widget_class: str, *, locale: str) -> str:
    if locale == "ja":
        return _CLASS_FALLBACK_SUMMARY_JA.get(widget_class, "操作可能な UI 要素です。")
    return _CLASS_FALLBACK_SUMMARY.get(widget_class, "Interactive UI element.")


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
