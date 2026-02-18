import { useState, useCallback, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ProfileDiffEntry, ScenarioHeader } from "@/hooks/useStudio";

interface ProfileDiffDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scenarioHeader: ScenarioHeader;
  onGetDiff: (baseProfile: string, compareProfile: string) => Promise<ProfileDiffEntry[]>;
}

function formatDiffValue(value: unknown): string {
  if (value === null || value === undefined) return "(undefined)";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export function ProfileDiffDialog({
  open,
  onOpenChange,
  scenarioHeader,
  onGetDiff,
}: ProfileDiffDialogProps) {
  const { t } = useTranslation();
  const [baseProfile, setBaseProfile] = useState("");
  const [compareProfile, setCompareProfile] = useState("");
  const [entries, setEntries] = useState<ProfileDiffEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const profiles = useMemo(() => {
    const profs = scenarioHeader.profiles as Record<string, unknown> | undefined;
    if (!profs || typeof profs !== "object") return [];
    return Object.keys(profs).filter((k) => k.trim() !== "").sort();
  }, [scenarioHeader.profiles]);

  // Auto-select first profile as compare when opening
  useEffect(() => {
    if (open) {
      const activeProfile = String(
        (scenarioHeader.execution as Record<string, unknown> | undefined)?.active_profile ?? ""
      );
      setBaseProfile(activeProfile);
      if (profiles.length > 0) {
        const first = profiles.find((p) => p !== activeProfile) ?? profiles[0];
        setCompareProfile(first);
      }
    }
  }, [open, profiles, scenarioHeader.execution]);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await onGetDiff(baseProfile, compareProfile);
      setEntries(result);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [baseProfile, compareProfile, onGetDiff]);

  // Auto-refresh on open or profile change
  useEffect(() => {
    if (open) {
      void handleRefresh();
    }
  }, [open, baseProfile, compareProfile, handleRefresh]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {t("app.dialog.profile_diff.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="flex gap-4 items-end">
          <div className="flex-1 space-y-1">
            <Label className="text-xs">{t("app.field.profile_diff.base.label")}</Label>
            <Select value={baseProfile || "__none__"} onValueChange={(v) => setBaseProfile(v === "__none__" ? "" : v)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">{t("app.option.profile.none")}</SelectItem>
                {profiles.map((name) => (
                  <SelectItem key={name} value={name}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1 space-y-1">
            <Label className="text-xs">{t("app.field.profile_diff.compare.label")}</Label>
            <Select value={compareProfile || "__none__"} onValueChange={(v) => setCompareProfile(v === "__none__" ? "" : v)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">{t("app.option.profile.none")}</SelectItem>
                {profiles.map((name) => (
                  <SelectItem key={name} value={name}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button size="sm" className="h-8 text-xs" onClick={() => void handleRefresh()} disabled={loading}>
            {t("app.button.refresh_diff")}
          </Button>
        </div>

        <ScrollArea className="flex-1 min-h-0 mt-2">
          <div className="font-mono text-xs whitespace-pre-wrap p-2 bg-muted/30 rounded min-h-[200px]">
            {entries.length === 0 ? (
              <span className="text-muted-foreground">-</span>
            ) : (
              entries.map((entry, i) => (
                <div key={i} className="mb-3">
                  <div className="font-semibold text-foreground">[{entry.path}]</div>
                  <div className="text-red-500 dark:text-red-400 ml-2">
                    base: {formatDiffValue(entry.base_value)}
                  </div>
                  <div className="text-green-500 dark:text-green-400 ml-2">
                    compare: {formatDiffValue(entry.compare_value)}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>

        <div className="flex justify-end mt-2">
          <Button variant="outline" size="sm" className="text-xs" onClick={() => onOpenChange(false)}>
            {t("app.button.close")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
