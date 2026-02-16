"""Localization helpers for Studio UI."""

from __future__ import annotations

import locale
import os
from dataclasses import dataclass

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "ja")
LOCALE_ENV_VAR = "ROBOT_AUTOMATION_STUDIO_LOCALE"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "locale.en.label": {"en": "English", "ja": "英語"},
    "locale.ja.label": {"en": "Japanese", "ja": "日本語"},
    "app.name": {"en": "Robot Automation Studio", "ja": "Robot Automation Studio"},
    "app.window.title": {"en": "Robot Automation Studio", "ja": "Robot Automation Studio"},
    "app.window.title.recording": {
        "en": "Robot Automation Studio [RECORDING]",
        "ja": "Robot Automation Studio [記録中]",
    },
    "app.window.header_prefix": {
        "en": "Robot Automation Studio -",
        "ja": "Robot Automation Studio -",
    },
    "app.help.tooltip.fallback": {
        "en": "No help available for this component.",
        "ja": "このコンポーネントのヘルプはありません。",
    },
    "app.help.header": {
        "en": "Hover controls for cursor-near tips. Press F1 for full guide.",
        "ja": "各部品にカーソルを合わせるとヒントを表示します。詳細は F1 を押してください。",
    },
    "app.status.run_tooltip": {"en": "Run status", "ja": "実行状態"},
    "app.status.record_tooltip": {"en": "Recording status", "ja": "記録状態"},
    "app.status.record_idle": {"en": " IDLE ", "ja": " 待機 "},
    "app.status.recording": {"en": " ● REC ", "ja": " ● 記録中 "},
    "app.scenario.default_name": {"en": "Unity Editor Flow", "ja": "Unity Editor Flow"},
    "app.scenario.default_fallback_name": {"en": "Scenario", "ja": "シナリオ"},
    "app.button.record_start": {"en": "● Record", "ja": "● 記録開始"},
    "app.button.record_stop": {"en": "■ Stop", "ja": "■ 記録停止"},
    "app.button.run_robot": {"en": "▶ Run Robot", "ja": "▶ Robot 実行"},
    "app.button.stop_robot": {"en": "Stop Robot", "ja": "Robot 停止"},
    "app.button.hotkey_with_value": {"en": "Hotkey: {hotkey}", "ja": "停止キー: {hotkey}"},
    "app.button.file_menu": {"en": "File ▾", "ja": "ファイル ▾"},
    "app.button.language_menu": {"en": "Language", "ja": "言語"},
    "app.button.add_step": {"en": "+ Add ▾", "ja": "+ 追加 ▾"},
    "app.button.delete": {"en": "✕", "ja": "✕"},
    "app.button.move_up": {"en": "▲", "ja": "▲"},
    "app.button.move_down": {"en": "▼", "ja": "▼"},
    "app.button.duplicate": {"en": "⎘", "ja": "⎘"},
    "app.button.apply_step": {"en": "Apply Step Changes", "ja": "ステップ変更を適用"},
    "app.button.export": {"en": "Export", "ja": "エクスポート"},
    "app.button.browse": {"en": "Browse", "ja": "参照"},
    "app.button.variables": {"en": "Variables", "ja": "変数"},
    "app.button.profiles": {"en": "Profiles", "ja": "プロファイル"},
    "app.button.execution_outputs": {"en": "Execution/Outputs", "ja": "実行/出力"},
    "app.button.validate": {"en": "Validate", "ja": "検証"},
    "app.button.profile_diff": {"en": "Profile Diff", "ja": "プロファイル差分"},
    "app.button.refresh_diff": {"en": "Refresh Diff", "ja": "差分を更新"},
    "app.button.add_override": {"en": "Add Override", "ja": "上書き追加"},
    "app.button.remove_override": {"en": "Remove Override", "ja": "上書き削除"},
    "app.button.close": {"en": "Close", "ja": "閉じる"},
    "app.button.go_to_issue": {"en": "Go To Location", "ja": "該当箇所へ移動"},
    "app.button.cancel": {"en": "Cancel", "ja": "キャンセル"},
    "app.button.apply": {"en": "Apply", "ja": "適用"},
    "app.button.format": {"en": "Format", "ja": "整形"},
    "app.button.reload_model": {"en": "Reload Model", "ja": "モデル再読込"},
    "app.button.save": {"en": "Save", "ja": "保存"},
    "app.button.add": {"en": "Add", "ja": "追加"},
    "app.button.delete_word": {"en": "Delete", "ja": "削除"},
    "app.button.apply_current": {"en": "Apply Current", "ja": "現在項目を適用"},
    "app.label.steps": {"en": "Steps", "ja": "ステップ"},
    "app.label.output_log": {"en": "Output Log", "ja": "出力ログ"},
    "app.tooltip.delete_step": {"en": "Delete step", "ja": "ステップを削除"},
    "app.tooltip.move_step_up": {"en": "Move step up", "ja": "ステップを上へ移動"},
    "app.tooltip.move_step_down": {"en": "Move step down", "ja": "ステップを下へ移動"},
    "app.tooltip.duplicate_step": {"en": "Duplicate step", "ja": "ステップを複製"},
    "app.tooltip.steps_list": {"en": "Steps list", "ja": "ステップ一覧"},
    "app.tooltip.stop_hotkey": {
        "en": "Configure emergency stop hotkey.",
        "ja": "緊急停止ホットキーを設定します。",
    },
    "app.tooltip.go_to_issue": {
        "en": "Move focus to the UI field indicated by this validation issue.",
        "ja": "この検証エラーが示す UI 項目へフォーカスを移動します。",
    },
    "app.log.toggle.tooltip": {
        "en": "Collapse or expand Output Log.",
        "ja": "出力ログの表示を折りたたみ/展開します。",
    },
    "app.log.search": {"en": "Search", "ja": "検索"},
    "app.help.dialog.title": {"en": "GUI Help Guide", "ja": "GUI ヘルプガイド"},
    "app.help.dialog.summary": {
        "en": "{count} UI components are documented.",
        "ja": "{count} 個の UI コンポーネントに説明があります。",
    },
    "app.help.dialog.shown": {
        "en": "{shown} / {total} components shown.",
        "ja": "{shown} / {total} 件を表示中。",
    },
    "app.help.dialog.no_match": {
        "en": "No matching components.",
        "ja": "一致するコンポーネントはありません。",
    },
    "app.help.dialog.details": {
        "en": (
            "Title: {title}\n"
            "Widget Class: {widget_class}\n"
            "Widget ID: {widget_id}\n\n"
            "Summary:\n{summary}\n\n"
            "Details:\n{detail}\n"
        ),
        "ja": (
            "タイトル: {title}\n"
            "ウィジェット種別: {widget_class}\n"
            "ウィジェットID: {widget_id}\n\n"
            "概要:\n{summary}\n\n"
            "詳細:\n{detail}\n"
        ),
    },
    "app.tab.step": {"en": "Step", "ja": "ステップ"},
    "app.tab.scenario": {"en": "Scenario", "ja": "シナリオ"},
    "app.tab.export": {"en": "Export", "ja": "出力"},
    "app.tab.step.tooltip": {
        "en": "Edit selected step fields.",
        "ja": "選択中ステップの項目を編集します。",
    },
    "app.tab.scenario.tooltip": {
        "en": "Configure scenario settings.",
        "ja": "シナリオ設定を編集します。",
    },
    "app.tab.export.tooltip": {"en": "Configure export outputs.", "ja": "出力設定を編集します。"},
    "app.field.scenario_name.placeholder": {"en": "Scenario name", "ja": "シナリオ名"},
    "app.field.step_id.label": {"en": "Step ID", "ja": "ステップID"},
    "app.field.step_id.placeholder": {"en": "step-1", "ja": "step-1"},
    "app.field.step_title.label": {"en": "Title", "ja": "タイトル"},
    "app.field.step_title.placeholder": {"en": "Step title", "ja": "ステップタイトル"},
    "app.field.step_kind.label": {"en": "Kind", "ja": "種別"},
    "app.field.step_action.label": {"en": "Action", "ja": "アクション"},
    "app.field.step_action.placeholder": {
        "en": "click / drag_drop / type_text ...",
        "ja": "click / drag_drop / type_text ...",
    },
    "app.field.step_control.label": {"en": "Control", "ja": "制御"},
    "app.field.step_control.placeholder": {
        "en": "if / for_each / while ...",
        "ja": "if / for_each / while ...",
    },
    "app.field.step_description.label": {"en": "Description", "ja": "説明"},
    "app.field.step_description.placeholder": {"en": "Optional description", "ja": "任意の説明"},
    "app.field.step_condition.label": {"en": "Condition", "ja": "条件"},
    "app.field.step_condition.placeholder": {
        "en": "Optional condition expression",
        "ja": "任意の条件式",
    },
    "app.field.step_disabled": {"en": "Disabled", "ja": "無効"},
    "app.field.step_continue_on_error": {"en": "Continue On Error", "ja": "エラー時も継続"},
    "app.field.annotations.label": {"en": "Annotations", "ja": "注釈"},
    "app.field.params.label": {"en": "Params", "ja": "パラメータ"},
    "app.field.scenario_id.label": {"en": "Scenario ID", "ja": "シナリオID"},
    "app.field.scenario_id.placeholder": {"en": "scenario-id", "ja": "scenario-id"},
    "app.field.target.label": {"en": "Target", "ja": "対象"},
    "app.field.window_hint.label": {"en": "Window Hint", "ja": "ウィンドウヒント"},
    "app.field.window_hint.placeholder": {"en": "Unity", "ja": "Unity"},
    "app.field.execution_mode.label": {"en": "Execution Mode", "ja": "実行モード"},
    "app.field.active_profile.label": {"en": "Active Profile", "ja": "適用プロファイル"},
    "app.field.unity_project_path.label": {
        "en": "Unity Project Path",
        "ja": "Unity プロジェクトパス",
    },
    "app.field.unity_project_path.placeholder": {
        "en": "Path to Unity project root",
        "ja": "Unity プロジェクトルートのパス",
    },
    "app.field.description.label": {"en": "Description", "ja": "説明"},
    "app.field.description.placeholder": {
        "en": "Optional scenario description",
        "ja": "任意のシナリオ説明",
    },
    "app.field.output_dir.label": {"en": "Output Dir", "ja": "出力先"},
    "app.field.output_dir.placeholder": {"en": "Output directory", "ja": "出力ディレクトリ"},
    "app.field.export_name.label": {"en": "Export Name", "ja": "出力名"},
    "app.field.export_name.placeholder": {"en": "Export name", "ja": "出力名"},
    "app.field.variable_id.label": {"en": "Variable ID", "ja": "変数ID"},
    "app.field.variable_type.label": {"en": "Variable Type", "ja": "変数タイプ"},
    "app.field.variable_required.label": {"en": "Required", "ja": "必須"},
    "app.field.variable_default.label": {"en": "Default Value", "ja": "デフォルト値"},
    "app.field.profile_name.label": {"en": "Profile Name", "ja": "プロファイル名"},
    "app.field.profile_description.label": {"en": "Description", "ja": "説明"},
    "app.field.profile_overrides.label": {"en": "Variable Overrides", "ja": "変数上書き"},
    "app.field.profile_override_key.label": {"en": "Variable", "ja": "変数"},
    "app.field.profile_override_value.label": {
        "en": "Value (JSON or text)",
        "ja": "値 (JSON またはテキスト)",
    },
    "app.field.profile_diff.base.label": {"en": "Base Profile", "ja": "基準プロファイル"},
    "app.field.profile_diff.compare.label": {
        "en": "Compare Profile",
        "ja": "比較プロファイル",
    },
    "app.menu.file.save": {"en": "💾 Save", "ja": "💾 保存"},
    "app.menu.file.load": {"en": "📂 Load", "ja": "📂 読込"},
    "app.menu.file.full_json": {"en": "{} Full JSON", "ja": "{} 全体 JSON"},
    "app.menu.file.help": {"en": "Help Guide (F1)", "ja": "ヘルプガイド (F1)"},
    "app.menu.file.run_diagnostics": {
        "en": "Run Diagnostics",
        "ja": "実行診断",
    },
    "app.menu.add.click": {"en": "🖱 Click", "ja": "🖱 クリック"},
    "app.menu.add.drag": {"en": "↔ Drag", "ja": "↔ ドラッグ"},
    "app.menu.add.shortcut": {"en": "⌨ Shortcut", "ja": "⌨ ショートカット"},
    "app.menu.add.menu": {"en": "≡ Menu", "ja": "≡ メニュー"},
    "app.menu.add.type": {"en": "✎ Type", "ja": "✎ 入力"},
    "app.menu.add.if": {"en": "IF", "ja": "IF"},
    "app.menu.add.group": {"en": "[] Group", "ja": "[] グループ"},
    "app.option.target.unity": {"en": "Unity", "ja": "Unity"},
    "app.option.target.web": {"en": "Web", "ja": "Web"},
    "app.option.target.desktop": {"en": "Desktop", "ja": "デスクトップ"},
    "app.option.target.hybrid": {"en": "Hybrid", "ja": "ハイブリッド"},
    "app.option.execution.attach": {"en": "Attach", "ja": "アタッチ"},
    "app.option.execution.launch": {"en": "Launch", "ja": "起動"},
    "app.option.profile.none": {"en": "(none)", "ja": "(なし)"},
    "app.option.kind.action": {"en": "Action", "ja": "アクション"},
    "app.option.kind.control": {"en": "Control", "ja": "制御"},
    "app.option.kind.group": {"en": "Group", "ja": "グループ"},
    "app.option.help.target.unity": {
        "en": "Run steps against Unity Editor.",
        "ja": "Unity Editor を対象にステップを実行します。",
    },
    "app.option.help.target.web": {
        "en": "Run steps against a web browser target.",
        "ja": "Web ブラウザを対象にステップを実行します。",
    },
    "app.option.help.target.desktop": {
        "en": "Run steps against a desktop app target.",
        "ja": "デスクトップアプリを対象にステップを実行します。",
    },
    "app.option.help.target.hybrid": {
        "en": "Run steps across mixed app targets.",
        "ja": "複数種別のアプリをまたいでステップを実行します。",
    },
    "app.option.help.execution.attach": {
        "en": "Use an already-open target window.",
        "ja": "既に開いている対象ウィンドウに接続して実行します。",
    },
    "app.option.help.execution.launch": {
        "en": "Launch Unity project before running.",
        "ja": "実行前に Unity プロジェクトを起動します。",
    },
    "app.option.help.profile.none": {
        "en": "Use variable defaults (no profile override).",
        "ja": "変数のデフォルト値をそのまま使用します。",
    },
    "app.option.help.profile.item": {
        "en": "Use profile '{profile}' overrides.",
        "ja": "プロファイル '{profile}' の上書きを使用します。",
    },
    "app.option.help.profile.item_with_description": {
        "en": "Use profile '{profile}' overrides. {description}",
        "ja": "プロファイル '{profile}' の上書きを使用します。{description}",
    },
    "app.option.help.kind.action": {
        "en": "Execute one operation step.",
        "ja": "1つの操作ステップを実行します。",
    },
    "app.option.help.kind.control": {
        "en": "Control flow with conditions/loops.",
        "ja": "条件分岐やループなどの制御フローを定義します。",
    },
    "app.option.help.kind.group": {
        "en": "Organize nested child steps.",
        "ja": "子ステップをグループ化します。",
    },
    "app.option.help.fallback": {"en": "Select option: {option}.", "ja": "選択肢: {option}"},
    "app.help.menu.file.save.summary": {
        "en": "Save current scenario file.",
        "ja": "現在のシナリオを保存します。",
    },
    "app.help.menu.file.save.detail": {
        "en": "Write the current scenario model to a .scenario.json file.",
        "ja": "現在のシナリオモデルを .scenario.json ファイルとして保存します。",
    },
    "app.help.menu.file.load.summary": {
        "en": "Load scenario file.",
        "ja": "シナリオファイルを読み込みます。",
    },
    "app.help.menu.file.load.detail": {
        "en": "Load a .scenario.json file into the editor and refresh the UI.",
        "ja": ".scenario.json ファイルをエディタへ読み込み、UIを更新します。",
    },
    "app.help.menu.file.full_json.summary": {
        "en": "Open full JSON editor.",
        "ja": "全体 JSON エディタを開きます。",
    },
    "app.help.menu.file.full_json.detail": {
        "en": "Edit the full v2 scenario JSON directly in one dialog.",
        "ja": "v2 シナリオ JSON 全体を1つのダイアログで直接編集します。",
    },
    "app.help.menu.file.help.summary": {
        "en": "Open full help guide.",
        "ja": "ヘルプガイドを開きます。",
    },
    "app.help.menu.file.help.detail": {
        "en": "Open searchable help for all registered UI controls.",
        "ja": "登録済みUI部品の検索可能なヘルプを開きます。",
    },
    "app.help.menu.file.run_diagnostics.summary": {
        "en": "Open latest run diagnostics.",
        "ja": "直近の実行診断を開きます。",
    },
    "app.help.menu.file.run_diagnostics.detail": {
        "en": "Show the latest generated run diagnostics JSON in a dialog.",
        "ja": "直近に生成した実行診断JSONをダイアログで表示します。",
    },
    "app.info.run_diagnostics_unavailable.title": {
        "en": "Run Diagnostics",
        "ja": "実行診断",
    },
    "app.info.run_diagnostics_unavailable.message": {
        "en": "Run diagnostics are not available yet. Run Robot first.",
        "ja": "実行診断はまだありません。先に Robot を実行してください。",
    },
    "app.info.validation_navigation_unavailable.title": {
        "en": "Navigation Not Available",
        "ja": "移動先が見つかりません",
    },
    "app.info.validation_navigation_unavailable.message": {
        "en": "Could not map this issue location to an editable UI field: {location}",
        "ja": "このエラー位置を編集可能な UI 項目へ割り当てできませんでした: {location}",
    },
    "app.dialog.run_diagnostics.title": {
        "en": "Run Diagnostics",
        "ja": "実行診断",
    },
    "app.dialog.run_diagnostics.path": {
        "en": "Diagnostics file: {path}",
        "ja": "診断ファイル: {path}",
    },
    "app.help.menu.add.click.summary": {
        "en": "Add click action step.",
        "ja": "クリック操作ステップを追加します。",
    },
    "app.help.menu.add.click.detail": {
        "en": "Insert an action step that clicks one target.",
        "ja": "1つの対象をクリックするアクションステップを追加します。",
    },
    "app.help.menu.add.drag.summary": {
        "en": "Add drag/drop action step.",
        "ja": "ドラッグ操作ステップを追加します。",
    },
    "app.help.menu.add.drag.detail": {
        "en": "Insert an action step for drag-and-drop operations.",
        "ja": "ドラッグ&ドロップのアクションステップを追加します。",
    },
    "app.help.menu.add.shortcut.summary": {
        "en": "Add keyboard shortcut step.",
        "ja": "ショートカット操作ステップを追加します。",
    },
    "app.help.menu.add.shortcut.detail": {
        "en": "Insert an action step that sends shortcut keys.",
        "ja": "ショートカットキー送信のアクションステップを追加します。",
    },
    "app.help.menu.add.menu.summary": {
        "en": "Add menu navigation step.",
        "ja": "メニュー操作ステップを追加します。",
    },
    "app.help.menu.add.menu.detail": {
        "en": "Insert an action step that opens app menus.",
        "ja": "アプリのメニューを開くアクションステップを追加します。",
    },
    "app.help.menu.add.type.summary": {
        "en": "Add text input step.",
        "ja": "文字入力ステップを追加します。",
    },
    "app.help.menu.add.type.detail": {
        "en": "Insert an action step that types text input.",
        "ja": "文字を入力するアクションステップを追加します。",
    },
    "app.help.menu.add.if.summary": {
        "en": "Add control-flow step.",
        "ja": "制御ステップを追加します。",
    },
    "app.help.menu.add.if.detail": {
        "en": "Insert a control step for conditions or loops.",
        "ja": "条件分岐やループ用の制御ステップを追加します。",
    },
    "app.help.menu.add.group.summary": {
        "en": "Add group container step.",
        "ja": "グループステップを追加します。",
    },
    "app.help.menu.add.group.detail": {
        "en": "Insert a group step to organize child steps.",
        "ja": "子ステップ整理用のグループステップを追加します。",
    },
    "app.file_dialog.save.title": {"en": "Save Scenario", "ja": "シナリオを保存"},
    "app.file_dialog.load.title": {"en": "Load Scenario", "ja": "シナリオを読込"},
    "app.file_dialog.select_unity_project.title": {
        "en": "Select Unity Project Root",
        "ja": "Unity プロジェクトルートを選択",
    },
    "app.file_dialog.filter.scenario_json": {
        "en": "Scenario JSON (*.scenario.json);;JSON (*.json)",
        "ja": "シナリオ JSON (*.scenario.json);;JSON (*.json)",
    },
    "app.log.record_error": {"en": "Record error: {message}", "ja": "記録エラー: {message}"},
    "app.log.diagnostics_persist_failed": {
        "en": "[diagnostics] Failed to persist record diagnostic to {path}: {error}",
        "ja": "[diagnostics] 記録診断ログの保存に失敗しました: {path}: {error}",
    },
    "app.log.recording_already_running": {
        "en": "Recording is already running.",
        "ja": "記録は既に実行中です。",
    },
    "app.log.recording_not_running": {
        "en": "Recording is not running.",
        "ja": "記録は実行されていません。",
    },
    "app.log.recording_started": {
        "en": "Recording started. window_hint={window_hint}",
        "ja": "記録を開始しました。window_hint={window_hint}",
    },
    "app.log.recording_stopped": {
        "en": "Recording stopped. Added {count} steps.",
        "ja": "記録を停止しました。{count} ステップ追加しました。",
    },
    "app.log.record_start_failed_attach": {
        "en": "Recording start failed: attach target window not found. window_hint={window_hint}",
        "ja": (
            "記録開始に失敗しました: attach 対象ウィンドウが見つかりません。"
            "window_hint={window_hint}"
        ),
    },
    "app.log.saved_scenario": {
        "en": "Saved scenario: {path}",
        "ja": "シナリオを保存しました: {path}",
    },
    "app.log.loaded_scenario": {
        "en": "Loaded scenario: {path}",
        "ja": "シナリオを読み込みました: {path}",
    },
    "app.log.load_failed": {"en": "Load failed: {error}", "ja": "読込に失敗しました: {error}"},
    "app.log.applied_full_json": {
        "en": "Applied full scenario JSON editor changes.",
        "ja": "全体シナリオ JSON の変更を適用しました。",
    },
    "app.log.updated_variables": {
        "en": "Updated variables from Variables Editor.",
        "ja": "Variables Editor から変数を更新しました。",
    },
    "app.log.updated_profiles": {
        "en": "Updated profiles from Profiles Editor.",
        "ja": "Profiles Editor からプロファイルを更新しました。",
    },
    "app.log.validation_ok": {
        "en": "Preflight validation passed.",
        "ja": "事前検証に成功しました。",
    },
    "app.log.validation_failed": {
        "en": "Preflight validation failed.",
        "ja": "事前検証に失敗しました。",
    },
    "app.log.validation_issue": {
        "en": "[validation] {code} ({location}): {message}",
        "ja": "[検証] {code} ({location}): {message}",
    },
    "app.log.updated_execution_outputs": {
        "en": "Updated execution/outputs from editor.",
        "ja": "実行/出力設定をエディタから更新しました。",
    },
    "app.log.export_failed": {"en": "Export failed: {error}", "ja": "エクスポート失敗: {error}"},
    "app.log.exported_robot": {
        "en": "Exported robot: {path}",
        "ja": "Robot を出力しました: {path}",
    },
    "app.log.exported_json": {"en": "Exported json: {path}", "ja": "JSON を出力しました: {path}"},
    "app.log.run_stop_recording_first": {
        "en": "Stop recording before running Robot suite.",
        "ja": "Robot 実行前に記録を停止してください。",
    },
    "app.log.robot_already_running": {
        "en": "Robot suite is already running.",
        "ja": "Robot は既に実行中です。",
    },
    "app.log.prepare_export": {
        "en": "Preparing scenario export...",
        "ja": "シナリオ出力を準備しています...",
    },
    "app.log.run_export_failed": {
        "en": "Run export failed: {error}",
        "ja": "実行用エクスポートに失敗しました: {error}",
    },
    "app.log.preflight_checks": {
        "en": "Running preflight checks...",
        "ja": "実行前チェック中...",
    },
    "app.log.running_robot_suite": {
        "en": "Running Robot suite...",
        "ja": "Robot を実行しています...",
    },
    "app.log.starting_robot_process": {
        "en": "Starting Robot process...",
        "ja": "Robot プロセスを開始しています...",
    },
    "app.log.attaching_unity_wait": {
        "en": "Attaching to Unity and waiting for first actions...",
        "ja": "Unity に接続して初回アクション待機中...",
    },
    "app.log.robot_not_running": {
        "en": "Robot suite is not running.",
        "ja": "Robot は実行されていません。",
    },
    "app.log.stopping_robot_suite": {
        "en": "Stopping Robot suite... ({hotkey})",
        "ja": "Robot を停止しています... ({hotkey})",
    },
    "app.log.robot_run_failed": {
        "en": "Robot run failed: {error}",
        "ja": "Robot 実行に失敗しました: {error}",
    },
    "app.log.robot_exit": {"en": "robot exit={code}", "ja": "robot exit={code}"},
    "app.log.run_diag_output_missing": {
        "en": "Run diagnostics skipped: output.xml not found: {path}",
        "ja": "実行診断をスキップしました: output.xml が見つかりません: {path}",
    },
    "app.log.run_diag_parse_failed": {
        "en": "Run diagnostics parse failed: {error}",
        "ja": "実行診断の解析に失敗しました: {error}",
    },
    "app.log.run_diag_saved": {
        "en": "Saved run diagnostics: {path}",
        "ja": "実行診断を保存しました: {path}",
    },
    "app.log.run_diag_save_failed": {
        "en": "Failed to save run diagnostics: {error}",
        "ja": "実行診断の保存に失敗しました: {error}",
    },
    "app.log.run_diag_summary": {
        "en": "Run diagnostics summary: status={status}, keywords={total}, elapsed={elapsed}s",
        "ja": "実行診断サマリ: status={status}, keywords={total}, elapsed={elapsed}s",
    },
    "app.log.run_diag_slowest": {
        "en": "  slowest#{index}: {name} ({status}) {elapsed}s",
        "ja": "  最遅#{index}: {name} ({status}) {elapsed}s",
    },
    "app.log.run_diag_failed_keyword": {
        "en": "  failed keyword: {name} | message: {message}",
        "ja": "  失敗キーワード: {name} | メッセージ: {message}",
    },
    "app.log.run_diag_last_annotation": {
        "en": "  last annotation: {payload}",
        "ja": "  直前注釈: {payload}",
    },
    "app.log.run_diag_screenshot": {
        "en": "Captured failure screenshot: {path}",
        "ja": "失敗時スクリーンショットを保存しました: {path}",
    },
    "app.log.run_diag_screenshot_failed": {
        "en": "Failure screenshot capture failed.",
        "ja": "失敗時スクリーンショットの取得に失敗しました。",
    },
    "app.log.robot_stopped": {"en": "Robot suite stopped.", "ja": "Robot を停止しました。"},
    "app.log.failed_register_hotkey": {
        "en": "Failed to register stop hotkey: {error}",
        "ja": "停止ホットキー登録に失敗しました: {error}",
    },
    "app.log.stop_requested": {
        "en": "Stop requested via {source}.",
        "ja": "{source} で停止要求を受信しました。",
    },
    "app.log.hotkey_registered": {
        "en": "Stop hotkey registered: {hotkey}",
        "ja": "停止ホットキーを登録しました: {hotkey}",
    },
    "app.log.hotkey_fallback": {
        "en": "Configured hotkey unavailable; fallback applied: {hotkey}",
        "ja": "設定したホットキーが使えないため、代替キーを適用しました: {hotkey}",
    },
    "app.log.hotkey_updated": {
        "en": "Stop hotkey updated: {hotkey}",
        "ja": "停止ホットキーを更新しました: {hotkey}",
    },
    "app.log.settings_saved": {
        "en": "Saved UI settings: {path}",
        "ja": "UI 設定を保存しました: {path}",
    },
    "app.log.settings_save_failed": {
        "en": "Failed to save UI settings: {error}",
        "ja": "UI 設定の保存に失敗しました: {error}",
    },
    "app.log.settings_load_failed": {
        "en": "Failed to load UI settings: {error}",
        "ja": "UI 設定の読込に失敗しました: {error}",
    },
    "app.stop_source.global_hotkey": {"en": "global hotkey", "ja": "グローバルホットキー"},
    "app.stop_source.recorder_hotkey": {"en": "recorder hotkey", "ja": "記録ホットキー"},
    "app.stop_source.overlay_button": {"en": "overlay stop button", "ja": "オーバーレイ停止ボタン"},
    "app.log.failed_start_overlay": {
        "en": "Failed to start overlay: {error}",
        "ja": "オーバーレイの開始に失敗しました: {error}",
    },
    "app.log.auto_detected_project_path": {
        "en": "Auto-detected Unity Project Path: {path}",
        "ja": "Unity プロジェクトパスを自動検出しました: {path}",
    },
    "app.log.bridge_package_meta_detected": {
        "en": "Unity bridge package script metadata detected.",
        "ja": "Unity bridge package script metadata を検出しました。",
    },
    "app.log.bridge_package_meta_missing": {
        "en": (
            "Unity bridge package script metadata is missing; "
            "using legacy fallback bridge script mode."
        ),
        "ja": (
            "Unity bridge package script metadata が見つからないため、"
            "legacy fallback bridge script モードを使用します。"
        ),
    },
    "app.purpose.recording": {"en": "recording", "ja": "記録"},
    "app.purpose.run": {"en": "run", "ja": "実行"},
    "app.log.ensure_bridge_package": {
        "en": "Ensuring Unity bridge package for {purpose}: {path}",
        "ja": "{purpose} 用に Unity bridge package を確認しています: {path}",
    },
    "app.log.bridge_setup_failed": {
        "en": "Unity bridge package setup failed: {error}",
        "ja": "Unity bridge package のセットアップに失敗しました: {error}",
    },
    "app.log.bridge_dependency_updated": {
        "en": "Unity bridge UPM dependency added/updated for this project.",
        "ja": "このプロジェクトの Unity bridge UPM dependency を追加/更新しました。",
    },
    "app.log.bridge_dependency_present": {
        "en": "Unity bridge UPM dependency already present.",
        "ja": "Unity bridge UPM dependency は既に存在します。",
    },
    "app.log.fallback_bridge_installed": {
        "en": "Installed fallback bridge script: Assets/Editor/RobotFrameworkUnityBridge.cs",
        "ja": (
            "fallback bridge script をインストールしました: "
            "Assets/Editor/RobotFrameworkUnityBridge.cs"
        ),
    },
    "app.log.fallback_bridge_present": {
        "en": "Fallback bridge script already installed.",
        "ja": "fallback bridge script は既にインストール済みです。",
    },
    "app.log.fallback_install_failed": {
        "en": "Fallback bridge installation failed: {error}",
        "ja": "fallback bridge のインストールに失敗しました: {error}",
    },
    "app.log.focused_target_window": {
        "en": "Focused target Unity window for bridge startup check.",
        "ja": "bridge 起動チェックのため対象 Unity ウィンドウをフォーカスしました。",
    },
    "app.log.refocused_target_window": {
        "en": "Refocused target Unity window and retrying bridge readiness.",
        "ja": "対象 Unity ウィンドウを再フォーカスし、bridge 準備確認を再試行します。",
    },
    "app.log.check_bridge_readiness": {
        "en": "Checking Unity bridge readiness... (attempt {attempt}/{total})",
        "ja": "Unity bridge の準備状態を確認中... (試行 {attempt}/{total})",
    },
    "app.log.bridge_readiness_timeout": {
        "en": "Unity bridge readiness check timed out.",
        "ja": "Unity bridge 準備確認がタイムアウトしました。",
    },
    "app.log.triggered_assets_refresh": {
        "en": "Triggered Unity Assets Refresh (Ctrl+R) on target window. Waiting for bridge...",
        "ja": (
            "対象ウィンドウで Unity Assets Refresh (Ctrl+R) を実行しました。bridge を待機します..."
        ),
    },
    "app.log.bridge_ready_after_refresh": {
        "en": "Unity bridge is ready after refresh.",
        "ja": "リフレッシュ後に Unity bridge が準備完了しました。",
    },
    "app.log.could_not_trigger_refresh": {
        "en": "Could not trigger Unity Assets Refresh shortcut on target window.",
        "ja": "対象ウィンドウで Unity Assets Refresh ショートカットを実行できませんでした。",
    },
    "app.log.meta_missing_after_wait": {
        "en": (
            "Unity bridge package script metadata is still missing after wait. "
            "Re-installing fallback bridge script..."
        ),
        "ja": (
            "待機後も Unity bridge package script metadata が見つかりません。"
            "fallback bridge script を再インストールします..."
        ),
    },
    "app.log.fallback_bridge_exists": {
        "en": "Fallback bridge script already exists.",
        "ja": "fallback bridge script は既に存在します。",
    },
    "app.log.waiting_fallback_readiness": {
        "en": "Waiting for fallback bridge readiness...",
        "ja": "fallback bridge の準備完了を待機しています...",
    },
    "app.log.bridge_ready_fallback": {
        "en": "Unity bridge is ready (fallback bridge).",
        "ja": "Unity bridge が準備完了しました (fallback bridge)。",
    },
    "app.log.detected_compile_errors": {
        "en": "Detected Unity compile errors in Editor.log:",
        "ja": "Editor.log で Unity のコンパイルエラーを検出しました:",
    },
    "app.log.bridge_ready": {
        "en": "Unity bridge is ready.",
        "ja": "Unity bridge が準備完了しました。",
    },
    "app.error.bridge_setup.title": {
        "en": "Unity Bridge Setup Error",
        "ja": "Unity Bridge セットアップエラー",
    },
    "app.error.bridge_setup_dependency.message": {
        "en": "Failed to prepare Unity bridge UPM dependency.\nPath: {path}\nError: {error}",
        "ja": "Unity bridge UPM dependency の準備に失敗しました。\nPath: {path}\nError: {error}",
    },
    "app.error.bridge_setup_fallback.message": {
        "en": "Failed to install fallback Unity bridge script.\nPath: {path}\nError: {error}",
        "ja": (
            "fallback Unity bridge script のインストールに失敗しました。\n"
            "Path: {path}\n"
            "Error: {error}"
        ),
    },
    "app.error.bridge_not_ready.title": {
        "en": "Unity Bridge Not Ready",
        "ja": "Unity Bridge 未準備",
    },
    "app.error.bridge_not_ready.message": {
        "en": (
            "Unity bridge is not ready yet.\n"
            "Unity may still be importing packages or compiling scripts.\n"
            "Open/focus the target Unity Editor and retry {retry_action}.\n"
            "If this persists, fix Unity compile errors first.{compile_error_hint}"
        ),
        "ja": (
            "Unity bridge はまだ準備できていません。\n"
            "Unity がパッケージの取り込みやスクリプトのコンパイル中の可能性があります。\n"
            "対象 Unity Editor を開く/フォーカスして {retry_action} を再試行してください。\n"
            "解消しない場合は Unity のコンパイルエラーを修正してください。{compile_error_hint}"
        ),
    },
    "app.error.bridge_compile_hint": {
        "en": "\n\nDetected recent Unity compile errors:\n- {items}",
        "ja": "\n\n最近検出した Unity コンパイルエラー:\n- {items}",
    },
    "app.error.invalid_params_json.title": {
        "en": "Invalid Params JSON",
        "ja": "Params JSON が不正です",
    },
    "app.error.invalid_annotations_json.title": {
        "en": "Invalid Annotations JSON",
        "ja": "Annotations JSON が不正です",
    },
    "app.error.invalid_params_object": {
        "en": "Params must be a JSON object.",
        "ja": "Params は JSON オブジェクトである必要があります。",
    },
    "app.error.invalid_annotations_array": {
        "en": "Annotations must be a JSON array.",
        "ja": "Annotations は JSON 配列である必要があります。",
    },
    "app.error.attach_target_not_found.title": {
        "en": "Attach Target Not Found",
        "ja": "アタッチ対象が見つかりません",
    },
    "app.error.attach_target_not_found.message": {
        "en": (
            "Could not find a visible target window for attach mode.\n"
            "Window Hint: {window_hint}\n"
            "Open the target window and try Start Recording again."
        ),
        "ja": (
            "attach モードの対象ウィンドウが見つかりませんでした。\n"
            "Window Hint: {window_hint}\n"
            "対象ウィンドウを開いて Start Recording を再試行してください。"
        ),
    },
    "app.error.load.title": {"en": "Load Error", "ja": "読込エラー"},
    "app.error.full_json_invalid.title": {"en": "Invalid JSON", "ja": "JSON が不正です"},
    "app.error.full_json_validation.title": {"en": "Validation Error", "ja": "検証エラー"},
    "app.error.variable_json_invalid.title": {
        "en": "Invalid Variable JSON",
        "ja": "Variable JSON が不正です",
    },
    "app.error.variable_json_object": {
        "en": "Variable must be a JSON object.",
        "ja": "Variable は JSON オブジェクトである必要があります。",
    },
    "app.error.variable_id_required": {
        "en": "Variable id is required.",
        "ja": "Variable id は必須です。",
    },
    "app.error.variable_type_required": {
        "en": "Variable type is required.",
        "ja": "Variable type は必須です。",
    },
    "app.error.profile_json_invalid.title": {
        "en": "Invalid Profile JSON",
        "ja": "Profile JSON が不正です",
    },
    "app.error.profile_payload_object": {
        "en": "Profile payload must be a JSON object.",
        "ja": "Profile payload は JSON オブジェクトである必要があります。",
    },
    "app.error.profile_name_required": {
        "en": "Profile name is required.",
        "ja": "Profile name は必須です。",
    },
    "app.error.profile_field_object": {
        "en": "profile field must be a JSON object.",
        "ja": "profile フィールドは JSON オブジェクトである必要があります。",
    },
    "app.error.execution_json_invalid.title": {
        "en": "Invalid execution JSON",
        "ja": "execution JSON が不正です",
    },
    "app.error.outputs_json_invalid.title": {
        "en": "Invalid outputs JSON",
        "ja": "outputs JSON が不正です",
    },
    "app.error.execution_object": {
        "en": "execution must be object.",
        "ja": "execution はオブジェクトである必要があります。",
    },
    "app.error.outputs_object": {
        "en": "outputs must be object.",
        "ja": "outputs はオブジェクトである必要があります。",
    },
    "app.error.export.title": {"en": "Export Error", "ja": "エクスポートエラー"},
    "app.error.run.title": {"en": "Run Error", "ja": "実行エラー"},
    "app.error.validation_navigation.title": {
        "en": "Validation Navigation Error",
        "ja": "検証エラー移動に失敗しました",
    },
    "app.error.recording_in_progress.title": {"en": "Recording In Progress", "ja": "記録中です"},
    "app.error.hotkey_invalid.title": {"en": "Invalid Hotkey", "ja": "ホットキーが不正です"},
    "app.error.hotkey_register_failed.title": {
        "en": "Stop Hotkey Registration Failed",
        "ja": "停止ホットキー登録に失敗しました",
    },
    "app.error.hotkey_register_failed.message": {
        "en": (
            "Failed to register stop hotkey: {hotkey}\n\n"
            "Fallback keys were also unavailable.\n"
            "You can still stop from Stop button or overlay stop button.\n\n"
            "Details:\n{details}"
        ),
        "ja": (
            "停止ホットキーを登録できませんでした: {hotkey}\n\n"
            "代替キーも利用できませんでした。\n"
            "Stop ボタンまたはオーバーレイ停止ボタンは利用できます。\n\n"
            "詳細:\n{details}"
        ),
    },
    "app.warn.hotkey_fallback.title": {
        "en": "Stop Hotkey Changed",
        "ja": "停止ホットキーを切り替えました",
    },
    "app.warn.hotkey_fallback.message": {
        "en": (
            "Configured stop hotkey could not be registered.\n"
            "Applied fallback: {hotkey}\n"
            "Reason: {error}"
        ),
        "ja": (
            "設定した停止ホットキーを登録できませんでした。\n"
            "代替キーを適用しました: {hotkey}\n"
            "理由: {error}"
        ),
    },
    "app.action.start_recording": {"en": "Start Recording", "ja": "記録開始"},
    "app.action.run_robot": {"en": "Run Robot", "ja": "Run Robot"},
    "app.dialog.hotkey.title": {"en": "Stop Hotkey", "ja": "停止ホットキー"},
    "app.dialog.hotkey.label": {
        "en": "Press the key combination for emergency stop (example: Alt+Shift+F12).",
        "ja": "緊急停止に使うキーの組み合わせを押してください (例: Alt+Shift+F12)。",
    },
    "app.dialog.hotkey.apply": {"en": "Apply Hotkey", "ja": "ホットキーを適用"},
    "app.dialog.hotkey_conflict.title": {
        "en": "Choose Fallback Hotkey",
        "ja": "代替ホットキーを選択",
    },
    "app.dialog.hotkey_conflict.message": {
        "en": (
            "The selected hotkey could not be registered: {hotkey}\n"
            "Reason: {error}\n\n"
            "Select an available fallback key."
        ),
        "ja": (
            "選択したホットキーを登録できませんでした: {hotkey}\n"
            "理由: {error}\n\n"
            "利用可能な代替キーを選択してください。"
        ),
    },
    "app.dialog.hotkey_candidate.label": {"en": "Fallback candidates", "ja": "代替キー候補"},
    "app.dialog.hotkey_candidate.apply": {"en": "Use Selected Key", "ja": "このキーを使用"},
    "app.dialog.full_json.title": {"en": "Full Scenario JSON (v2)", "ja": "シナリオ全体 JSON (v2)"},
    "app.dialog.variables.title": {"en": "Variables Editor", "ja": "変数エディタ"},
    "app.dialog.profiles.title": {"en": "Profiles Editor", "ja": "プロファイルエディタ"},
    "app.dialog.execution_outputs.title": {
        "en": "Execution / Outputs Editor",
        "ja": "実行 / 出力エディタ",
    },
    "app.dialog.validation.title": {"en": "Preflight Validation", "ja": "事前検証"},
    "app.dialog.profile_diff.title": {
        "en": "Profile Diff Preview",
        "ja": "プロファイル差分プレビュー",
    },
    "app.dialog.execution_outputs.header": {
        "en": "Execution / Outputs JSON",
        "ja": "実行 / 出力 JSON",
    },
    "app.dialog.execution_outputs.execution": {"en": "execution", "ja": "execution"},
    "app.dialog.execution_outputs.outputs": {"en": "outputs", "ja": "outputs"},
    "app.list.item.variable": {"en": "{index}. {id} ({type})", "ja": "{index}. {id} ({type})"},
    "app.list.item.profile": {"en": "{index}. {name}", "ja": "{index}. {name}"},
    "app.validation.status.ok": {"en": "No validation issues.", "ja": "検証エラーはありません。"},
    "app.validation.status.ng": {
        "en": "Validation issues detected.",
        "ja": "検証エラーを検出しました。",
    },
    "app.validation.issue.item": {
        "en": "{index}. [{code}] {message}",
        "ja": "{index}. [{code}] {message}",
    },
    "app.validation.issue.none": {"en": "No issues.", "ja": "問題はありません。"},
    "app.validation.issue.select_prompt": {
        "en": "Select an issue to view details.",
        "ja": "詳細を表示するには項目を選択してください。",
    },
    "app.validation.issue.none_detail": {
        "en": "Validation completed without issues.",
        "ja": "問題なく検証が完了しました。",
    },
    "app.validation.issue.detail": {
        "en": "Code: {code}\nLocation: {location}\n\nMessage:\n{message}",
        "ja": "コード: {code}\n場所: {location}\n\nメッセージ:\n{message}",
    },
    "app.list.item.help_entry": {
        "en": "{title} [{widget_class}]",
        "ja": "{title} [{widget_class}]",
    },
    "app.list.item.step": {
        "en": "{index}. [{kind}] {label} - {title}",
        "ja": "{index}. [{kind}] {label} - {title}",
    },
    "app.step.label.group": {"en": "group", "ja": "group"},
    "status.phase.idle": {"en": "Idle", "ja": "待機"},
    "status.phase.precheck": {"en": "Preflight checks", "ja": "事前チェック中"},
    "status.phase.exporting": {"en": "Exporting scenario", "ja": "シナリオをエクスポート中"},
    "status.phase.starting_robot": {"en": "Starting Robot", "ja": "Robot 起動中"},
    "status.phase.attaching_unity": {"en": "Attaching to Unity", "ja": "Unity 接続中"},
    "status.phase.running": {"en": "Running", "ja": "実行中"},
    "status.phase.stopping": {"en": "Stopping...", "ja": "停止中..."},
    "overlay.progress.recording": {"en": "Recording", "ja": "記録中"},
    "overlay.progress.running": {"en": "Running", "ja": "実行中"},
    "overlay.stop_action.run": {"en": "stop", "ja": "停止"},
    "overlay.stop_action.recording": {"en": "stop recording", "ja": "記録停止"},
    "overlay.stop_button": {"en": "Stop Now", "ja": "今すぐ停止"},
    "overlay.banner": {
        "en": "{progress}  |  Press {hotkey} to {action}",
        "ja": "{progress}  |  {hotkey} で {action}",
    },
}


def _detect_supported_locale(raw_locale: str | None) -> str | None:
    normalized = str(raw_locale or "").strip().lower().replace("_", "-")
    if not normalized:
        return None
    for locale_code in SUPPORTED_LOCALES:
        if normalized == locale_code or normalized.startswith(f"{locale_code}-"):
            return locale_code
    if normalized.startswith("japanese") or "japanese" in normalized:
        return "ja"
    if normalized.startswith("english") or "english" in normalized:
        return "en"
    return None


def detect_default_locale(preferred_locale: str | None = None) -> str:
    """Detect startup locale from explicit input, env override, then OS locale."""
    explicit = _detect_supported_locale(preferred_locale)
    if explicit is not None:
        return explicit

    from_env = _detect_supported_locale(os.getenv(LOCALE_ENV_VAR))
    if from_env is not None:
        return from_env

    try:
        system_locale = locale.getlocale()[0]
    except Exception:
        system_locale = None
    from_system = _detect_supported_locale(system_locale)
    if from_system is not None:
        return from_system

    return DEFAULT_LOCALE


def normalize_locale(locale: str | None) -> str:
    normalized = _detect_supported_locale(locale)
    if normalized is not None:
        return normalized
    return DEFAULT_LOCALE


def translate(key: str, *, locale: str | None = None, **kwargs: object) -> str:
    normalized_locale = normalize_locale(locale)
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        template = key
    else:
        template = entry.get(normalized_locale) or entry.get(DEFAULT_LOCALE) or key
    try:
        return template.format(**kwargs)
    except Exception:
        return template


@dataclass
class Translator:
    """Stateful translator that keeps current locale."""

    locale: str = DEFAULT_LOCALE

    def __post_init__(self) -> None:
        self.locale = normalize_locale(self.locale)

    def set_locale(self, locale: str) -> str:
        self.locale = normalize_locale(locale)
        return self.locale

    def t(self, key: str, **kwargs: object) -> str:
        return translate(key, locale=self.locale, **kwargs)
