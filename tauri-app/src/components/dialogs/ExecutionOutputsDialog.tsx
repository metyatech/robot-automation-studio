import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { WrapText } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface ExecutionOutputsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialExecution: Record<string, unknown>;
  initialOutputs: Record<string, unknown>;
  onSave: (execution: Record<string, unknown>, outputs: Record<string, unknown>) => void;
}

export function ExecutionOutputsDialog({
  open,
  onOpenChange,
  initialExecution,
  initialOutputs,
  onSave,
}: ExecutionOutputsDialogProps) {
  const { t } = useTranslation();

  const [executionText, setExecutionText] = useState(
    JSON.stringify(initialExecution, null, 2)
  );
  const [outputsText, setOutputsText] = useState(
    JSON.stringify(initialOutputs, null, 2)
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setExecutionText(JSON.stringify(initialExecution, null, 2));
      setOutputsText(JSON.stringify(initialOutputs, null, 2));
      setError(null);
    }
  }, [open, initialExecution, initialOutputs]);

  const parse = useCallback((): {
    execution: Record<string, unknown>;
    outputs: Record<string, unknown>;
  } | null => {
    let exec: unknown;
    let outs: unknown;
    try {
      exec = JSON.parse(executionText.trim() || "{}");
    } catch (e) {
      setError(`execution: ${e instanceof Error ? e.message : String(e)}`);
      return null;
    }
    try {
      outs = JSON.parse(outputsText.trim() || "{}");
    } catch (e) {
      setError(`outputs: ${e instanceof Error ? e.message : String(e)}`);
      return null;
    }
    if (typeof exec !== "object" || exec === null || Array.isArray(exec)) {
      setError(t("app.error.execution_object"));
      return null;
    }
    if (typeof outs !== "object" || outs === null || Array.isArray(outs)) {
      setError(t("app.error.outputs_object"));
      return null;
    }
    return {
      execution: exec as Record<string, unknown>,
      outputs: outs as Record<string, unknown>,
    };
  }, [executionText, outputsText, t]);

  const handleFormat = () => {
    const result = parse();
    if (result === null) return;
    setExecutionText(JSON.stringify(result.execution, null, 2));
    setOutputsText(JSON.stringify(result.outputs, null, 2));
    setError(null);
  };

  const handleApply = () => {
    const result = parse();
    if (result === null) return;
    onSave(result.execution, result.outputs);
    setError(null);
  };

  const handleSave = () => {
    const result = parse();
    if (result === null) return;
    onSave(result.execution, result.outputs);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle>{t("app.dialog.execution_outputs.title")}</DialogTitle>
        </DialogHeader>

        {error && (
          <div className="mx-4 mb-1 rounded bg-destructive/20 px-3 py-2 text-xs text-destructive shrink-0">
            {error}
          </div>
        )}

        <div className="flex flex-1 min-h-0 gap-2 px-4 pb-2">
          {/* Execution panel */}
          <div className="flex-1 flex flex-col space-y-1">
            <Label className="text-xs shrink-0">
              {t("app.dialog.execution_outputs.execution")}
            </Label>
            <Textarea
              value={executionText}
              onChange={(e) => {
                setExecutionText(e.target.value);
                setError(null);
              }}
              className="flex-1 font-mono text-xs resize-none min-h-0"
              spellCheck={false}
            />
          </div>
          {/* Outputs panel */}
          <div className="flex-1 flex flex-col space-y-1">
            <Label className="text-xs shrink-0">
              {t("app.dialog.execution_outputs.outputs")}
            </Label>
            <Textarea
              value={outputsText}
              onChange={(e) => {
                setOutputsText(e.target.value);
                setError(null);
              }}
              className="flex-1 font-mono text-xs resize-none min-h-0"
              spellCheck={false}
            />
          </div>
        </div>

        <DialogFooter className="px-4 pb-4 shrink-0 flex-row justify-between sm:justify-between gap-2">
          <Button variant="outline" size="sm" onClick={handleFormat}>
            <WrapText className="mr-1 h-3.5 w-3.5" />
            {t("app.button.format")}
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              {t("app.button.cancel")}
            </Button>
            <Button variant="outline" size="sm" onClick={handleApply}>
              {t("app.button.apply")}
            </Button>
            <Button size="sm" onClick={handleSave}>
              {t("app.button.save")}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
