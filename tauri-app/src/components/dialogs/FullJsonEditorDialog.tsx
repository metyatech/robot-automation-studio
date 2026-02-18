import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { WrapText, RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface FullJsonEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGetJson: () => Promise<Record<string, unknown> | null>;
  onSetJson: (scenario: Record<string, unknown>) => Promise<void>;
}

export function FullJsonEditorDialog({
  open,
  onOpenChange,
  onGetJson,
  onSetJson,
}: FullJsonEditorDialogProps) {
  const { t } = useTranslation();
  const [jsonText, setJsonText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadJson = useCallback(async () => {
    const data = await onGetJson();
    if (data != null) {
      setJsonText(JSON.stringify(data, null, 2));
      setError(null);
    }
  }, [onGetJson]);

  useEffect(() => {
    if (open) {
      void loadJson();
    }
  }, [open, loadJson]);

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(jsonText.trim() || "{}");
      setJsonText(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleReload = () => {
    void loadJson();
  };

  const handleApply = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonText.trim() || "{}") as Record<string, unknown>;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    try {
      await onSetJson(parsed);
      setError(null);
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle>{t("app.dialog.full_json.title")}</DialogTitle>
        </DialogHeader>

        <div className="flex items-center gap-2 px-4 pb-2 shrink-0">
          <Button variant="outline" size="sm" onClick={handleFormat}>
            <WrapText className="mr-1 h-3.5 w-3.5" />
            {t("app.button.format")}
          </Button>
          <Button variant="outline" size="sm" onClick={handleReload}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
            {t("app.button.reload_model")}
          </Button>
        </div>

        {error && (
          <div className="mx-4 mb-2 rounded bg-destructive/20 px-3 py-2 text-xs text-destructive shrink-0">
            {error}
          </div>
        )}

        <div className="flex-1 min-h-0 px-4 pb-2">
          <Textarea
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setError(null);
            }}
            className="h-full font-mono text-xs resize-none"
            spellCheck={false}
          />
        </div>

        <DialogFooter className="px-4 pb-4 shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("app.button.cancel")}
          </Button>
          <Button onClick={() => void handleApply()}>
            {t("app.button.apply")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
