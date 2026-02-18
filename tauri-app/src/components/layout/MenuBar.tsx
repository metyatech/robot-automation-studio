import { useTranslation } from "react-i18next";
import {
  Save,
  FolderOpen,
  Braces,
  HelpCircle,
  Activity,
  LogOut,
  MousePointerClick,
  GripHorizontal,
  Keyboard,
  Menu as MenuIcon,
  Type,
  GitBranch,
  List,
  Trash2,
  ArrowUp,
  ArrowDown,
  Copy,
  Circle,
  Square,
  Play,
  Languages,
  Variable,
  Layers,
  Settings,
  CheckSquare,
  Sliders,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

interface MenuBarProps {
  onSave: () => void;
  onLoad: () => void;
  onFullJson: () => void;
  onHelp: () => void;
  onDiagnostics: () => void;
  onExit: () => void;
  onAddStep: (type: string) => void;
  onDeleteStep: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDuplicate: () => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onRunRobot: () => void;
  onStopRobot: () => void;
  onSetLocale: (locale: string) => void;
  onVariables: () => void;
  onProfiles: () => void;
  onExecutionOutputs: () => void;
  onPreflight: () => void;
  onHotkeySettings: () => void;
}

export function MenuBar({
  onSave,
  onLoad,
  onFullJson,
  onHelp,
  onDiagnostics,
  onExit,
  onAddStep,
  onDeleteStep,
  onMoveUp,
  onMoveDown,
  onDuplicate,
  onStartRecording,
  onStopRecording,
  onRunRobot,
  onStopRobot,
  onSetLocale,
  onVariables,
  onProfiles,
  onExecutionOutputs,
  onPreflight,
  onHotkeySettings,
}: MenuBarProps) {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-1 border-b border-border px-2 py-1 bg-card">
      {/* File */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.menubar.file")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={onSave}>
            <Save className="mr-2 h-4 w-4" />
            {t("app.menu.file.save")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onLoad}>
            <FolderOpen className="mr-2 h-4 w-4" />
            {t("app.menu.file.load")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onFullJson}>
            <Braces className="mr-2 h-4 w-4" />
            {t("app.menu.file.full_json")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onExit}>
            <LogOut className="mr-2 h-4 w-4" />
            {t("app.menu.file.exit")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Edit */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.menubar.edit")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              {t("app.menu.edit.add_step")}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem onClick={() => onAddStep("click")}>
                <MousePointerClick className="mr-2 h-4 w-4" />
                {t("app.menu.add.click")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAddStep("drag")}>
                <GripHorizontal className="mr-2 h-4 w-4" />
                {t("app.menu.add.drag")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAddStep("shortcut")}>
                <Keyboard className="mr-2 h-4 w-4" />
                {t("app.menu.add.shortcut")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAddStep("menu")}>
                <MenuIcon className="mr-2 h-4 w-4" />
                {t("app.menu.add.menu")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAddStep("type")}>
                <Type className="mr-2 h-4 w-4" />
                {t("app.menu.add.type")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAddStep("control")}>
                <GitBranch className="mr-2 h-4 w-4" />
                {t("app.menu.add.if")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAddStep("group")}>
                <List className="mr-2 h-4 w-4" />
                {t("app.menu.add.group")}
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onDeleteStep}>
            <Trash2 className="mr-2 h-4 w-4" />
            {t("app.menu.edit.delete")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onMoveUp}>
            <ArrowUp className="mr-2 h-4 w-4" />
            {t("app.menu.edit.move_up")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onMoveDown}>
            <ArrowDown className="mr-2 h-4 w-4" />
            {t("app.menu.edit.move_down")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onDuplicate}>
            <Copy className="mr-2 h-4 w-4" />
            {t("app.menu.edit.duplicate")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Scenario */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.tab.scenario._self")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={onVariables}>
            <Variable className="mr-2 h-4 w-4" />
            {t("app.button.variables")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onProfiles}>
            <Layers className="mr-2 h-4 w-4" />
            {t("app.button.profiles")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onExecutionOutputs}>
            <Settings className="mr-2 h-4 w-4" />
            {t("app.button.execution_outputs")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onPreflight}>
            <CheckSquare className="mr-2 h-4 w-4" />
            {t("app.button.validate")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Run */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.menubar.run")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={onStartRecording}>
            <Circle className="mr-2 h-4 w-4 text-green-400" />
            {t("app.menu.run.record")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onStopRecording}>
            <Square className="mr-2 h-4 w-4 text-red-400" />
            {t("app.menu.run.stop_recording")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onRunRobot}>
            <Play className="mr-2 h-4 w-4 text-green-400" />
            {t("app.menu.run.run_robot")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onStopRobot}>
            <Square className="mr-2 h-4 w-4 text-red-400" />
            {t("app.menu.run.stop_robot")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Tools */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.menubar.tools")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={onHotkeySettings}>
            <Sliders className="mr-2 h-4 w-4" />
            {t("app.menu.tools.hotkey_settings")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Help */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            {t("app.menubar.help")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={onHelp}>
            <HelpCircle className="mr-2 h-4 w-4" />
            {t("app.menu.file.help")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onDiagnostics}>
            <Activity className="mr-2 h-4 w-4" />
            {t("app.menu.file.run_diagnostics")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Language */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
            <Languages className="mr-1 h-4 w-4" />
            {t("app.menu.tools.language")}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={() => onSetLocale("en")}>
            {t("locale.en.label")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onSetLocale("ja")}>
            {t("locale.ja.label")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
