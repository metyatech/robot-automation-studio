import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { RunPhase } from "@/hooks/useStudio";

interface StatusBarProps {
  runPhase: RunPhase;
  isRecording: boolean;
  connected: boolean;
  stopHotkeyLabel?: string;
  locale?: string;
  onSetLocale?: (locale: string) => void;
}

const PHASE_KEY_MAP: Record<string, string> = {
  idle: "status.phase.idle",
  precheck: "status.phase.precheck",
  exporting: "status.phase.exporting",
  starting_robot: "status.phase.starting_robot",
  attaching_unity: "status.phase.attaching_unity",
  running: "status.phase.running",
  stopping: "status.phase.stopping",
};

export function StatusBar({
  runPhase,
  isRecording,
  connected,
  stopHotkeyLabel,
  locale,
  onSetLocale,
}: StatusBarProps) {
  const { t } = useTranslation();
  const isActive = runPhase !== "idle";
  const phaseKey = PHASE_KEY_MAP[runPhase] ?? "status.phase.idle";

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex items-center justify-between border-t border-border px-3 py-1 bg-card/50 text-xs">
        <span className="text-muted-foreground">{t("app.help.header")}</span>

        <div className="flex items-center gap-3">
          {/* Stop hotkey label */}
          {stopHotkeyLabel && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 cursor-help"
                >
                  {t("app.statusbar.stop_hotkey", { hotkey: stopHotkeyLabel })}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>{t("app.tooltip.stop_hotkey")}</TooltipContent>
            </Tooltip>
          )}

          {/* Connection status */}
          <Badge
            variant={connected ? "outline" : "destructive"}
            className="text-[10px] px-1.5 py-0"
          >
            {connected ? "WS" : "Disconnected"}
          </Badge>

          {/* Recording indicator */}
          <Badge
            variant={isRecording ? "destructive" : "secondary"}
            className="text-[10px] px-1.5 py-0"
          >
            {isRecording ? t("app.status.recording") : t("app.status.record_idle")}
          </Badge>

          {/* Run phase */}
          <div className="flex items-center gap-1">
            {isActive && (
              <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
            )}
            <Badge
              variant={isActive ? "default" : "secondary"}
              className="text-[10px] px-1.5 py-0"
            >
              {t(phaseKey)}
            </Badge>
          </div>

          {/* Language selector */}
          {onSetLocale && (
            <Select
              value={locale ?? "en"}
              onValueChange={(v) => onSetLocale(v)}
            >
              <Tooltip>
                <TooltipTrigger asChild>
                  <SelectTrigger className="h-5 w-[70px] text-[10px] border-0 bg-transparent px-1">
                    <SelectValue />
                  </SelectTrigger>
                </TooltipTrigger>
                <TooltipContent>{t("app.button.language_menu")}</TooltipContent>
              </Tooltip>
              <SelectContent>
                <SelectItem value="en">{t("locale.en.label")}</SelectItem>
                <SelectItem value="ja">{t("locale.ja.label")}</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
