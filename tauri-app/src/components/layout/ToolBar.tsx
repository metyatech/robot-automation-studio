import { useTranslation } from "react-i18next";
import {
  Circle,
  Square,
  Play,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Copy,
  MousePointerClick,
  GripHorizontal,
  Keyboard,
  Menu as MenuIcon,
  Type,
  GitBranch,
  List,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";

interface ToolBarProps {
  isRecording: boolean;
  isRunning: boolean;
  scenarioName?: string;
  onScenarioNameChange?: (name: string) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onRunRobot: () => void;
  onStopRobot: () => void;
  onExport: () => void;
  onAddStep: (type: string) => void;
  onDeleteStep: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDuplicate: () => void;
  hasSelection: boolean;
}

export function ToolBar({
  isRecording,
  isRunning,
  scenarioName,
  onScenarioNameChange,
  onStartRecording,
  onStopRecording,
  onRunRobot,
  onStopRobot,
  onExport,
  onAddStep,
  onDeleteStep,
  onMoveUp,
  onMoveDown,
  onDuplicate,
  hasSelection,
}: ToolBarProps) {
  const { t } = useTranslation();

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex items-center gap-1 border-b border-border px-2 py-1 bg-card/50">
        {/* Scenario name */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Input
              value={scenarioName ?? ""}
              onChange={(e) => onScenarioNameChange?.(e.target.value)}
              placeholder={t("app.field.scenario_name.placeholder")}
              className="h-7 text-xs w-40 min-w-[100px] max-w-[200px]"
            />
          </TooltipTrigger>
          <TooltipContent>{t("app.field.scenario_name.placeholder")}</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="h-6 mx-1" />

        {/* Record / Stop Record */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1"
              onClick={onStartRecording}
              disabled={isRecording}
            >
              <Circle className="h-4 w-4 text-green-400" />
              <span className="text-xs">{t("app.button.record_start")}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.menu.run.record")}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1"
              onClick={onStopRecording}
              disabled={!isRecording}
            >
              <Square className="h-4 w-4 text-red-400" />
              <span className="text-xs">{t("app.button.record_stop")}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.menu.run.stop_recording")}</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="h-6 mx-1" />

        {/* Run / Stop */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1"
              onClick={onRunRobot}
              disabled={isRunning || isRecording}
            >
              <Play className="h-4 w-4 text-green-400" />
              <span className="text-xs">{t("app.button.run_robot")}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.menu.run.run_robot")}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1"
              onClick={onStopRobot}
              disabled={!isRunning}
            >
              <Square className="h-4 w-4 text-red-400" />
              <span className="text-xs">{t("app.button.stop_robot")}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.menu.run.stop_robot")}</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="h-6 mx-1" />

        {/* Export */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1"
              onClick={onExport}
            >
              <Download className="h-4 w-4" />
              <span className="text-xs">{t("app.button.export")}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tab.export._self")}</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="h-6 mx-1" />

        {/* Add Step Dropdown */}
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 gap-1">
                  <Plus className="h-4 w-4 text-blue-400" />
                  <span className="text-xs">{t("app.button.add_step")}</span>
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent>{t("app.menu.edit.add_step")}</TooltipContent>
          </Tooltip>
          <DropdownMenuContent>
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
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Step manipulation buttons */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onDeleteStep}
              disabled={!hasSelection}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tooltip.delete_step")}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onMoveUp}
              disabled={!hasSelection}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tooltip.move_step_up")}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onMoveDown}
              disabled={!hasSelection}
            >
              <ArrowDown className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tooltip.move_step_down")}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onDuplicate}
              disabled={!hasSelection}
            >
              <Copy className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tooltip.duplicate_step")}</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
