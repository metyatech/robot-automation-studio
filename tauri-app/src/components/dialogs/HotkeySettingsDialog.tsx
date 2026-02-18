import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Keyboard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface HotkeySettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentHotkey: string;
  onApply: (hotkey: string) => void;
}

export function HotkeySettingsDialog({
  open,
  onOpenChange,
  currentHotkey,
  onApply,
}: HotkeySettingsDialogProps) {
  const { t } = useTranslation();
  const [hotkeyText, setHotkeyText] = useState(currentHotkey);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setHotkeyText(currentHotkey);
      setError(null);
    }
  }, [open, currentHotkey]);

  const handleApply = () => {
    const trimmed = hotkeyText.trim();
    if (trimmed === "") {
      setError(t("app.error.hotkey_invalid.title"));
      return;
    }
    onApply(trimmed);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm w-full">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="h-4 w-4" />
            {t("app.dialog.hotkey.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="text-sm">{t("app.dialog.hotkey.label")}</Label>
            <Input
              value={hotkeyText}
              onChange={(e) => {
                setHotkeyText(e.target.value);
                setError(null);
              }}
              placeholder="Alt+Shift+F12"
              className="font-mono"
            />
          </div>

          {error && (
            <div className="rounded bg-destructive/20 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          <div className="text-xs text-muted-foreground">
            {t("app.tooltip.stop_hotkey")}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("app.button.cancel")}
          </Button>
          <Button onClick={handleApply}>
            {t("app.dialog.hotkey.apply")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
