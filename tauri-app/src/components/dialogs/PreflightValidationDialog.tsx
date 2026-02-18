import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, RefreshCw, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface ValidationIssue {
  code: string;
  location: string;
  message: string;
}

interface ValidationReport {
  valid: boolean;
  issues: ValidationIssue[];
}

interface PreflightValidationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRunPreflight: () => Promise<ValidationReport | null>;
}

export function PreflightValidationDialog({
  open,
  onOpenChange,
  onRunPreflight,
}: PreflightValidationDialogProps) {
  const { t } = useTranslation();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<ValidationIssue | null>(null);
  const [loading, setLoading] = useState(false);

  const runValidation = useCallback(async () => {
    setLoading(true);
    setSelectedIssue(null);
    try {
      const result = await onRunPreflight();
      setReport(result);
    } finally {
      setLoading(false);
    }
  }, [onRunPreflight]);

  const handleCopyIssue = () => {
    if (!selectedIssue) return;
    const text = `[${selectedIssue.code}] ${selectedIssue.location || "-"}\n${selectedIssue.message}`;
    void navigator.clipboard.writeText(text);
  };

  const handleCopyAll = () => {
    if (!report) return;
    if (report.issues.length === 0) {
      void navigator.clipboard.writeText(t("app.validation.issue.none_clipboard"));
      return;
    }
    const lines = report.issues.map(
      (issue, i) =>
        `${i + 1}. [${issue.code}] ${issue.location || "-"}\n   ${issue.message}`
    );
    void navigator.clipboard.writeText(lines.join("\n"));
  };

  const isValid = report?.valid ?? null;
  const issues = report?.issues ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl w-full h-[75vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle>{t("app.dialog.validation.title")}</DialogTitle>
        </DialogHeader>

        {/* Status bar */}
        {report !== null && (
          <div
            className={`mx-4 mb-2 flex items-center gap-2 rounded px-3 py-2 text-xs shrink-0 ${
              isValid
                ? "bg-green-500/20 text-green-400"
                : "bg-destructive/20 text-destructive"
            }`}
          >
            {isValid ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0" />
            )}
            {isValid
              ? t("app.validation.status.ok")
              : t("app.validation.status.ng_with_count", {
                  count: issues.length,
                })}
          </div>
        )}

        {report === null && !loading && (
          <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
            <div className="text-center space-y-3">
              <p>{t("app.validation.step.none")}</p>
              <Button onClick={() => void runValidation()} size="sm">
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                {t("app.button.validate")}
              </Button>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            {t("app.log.preflight_checks")}
          </div>
        )}

        {report !== null && !loading && (
          <div className="flex flex-1 min-h-0 gap-0">
            {/* Issues list */}
            <div className="w-64 shrink-0 border-r flex flex-col">
              <ScrollArea className="flex-1">
                <div className="p-1 space-y-0.5">
                  {issues.map((issue, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedIssue(issue)}
                      className={`w-full text-left rounded px-2 py-2 text-xs transition-colors ${
                        selectedIssue === issue
                          ? "bg-accent text-accent-foreground"
                          : "hover:bg-muted"
                      }`}
                    >
                      <div className="flex items-start gap-1.5">
                        <Badge variant="destructive" className="text-[10px] px-1 py-0 shrink-0 mt-0.5">
                          {issue.code}
                        </Badge>
                        <span className="truncate">{issue.message}</span>
                      </div>
                      {issue.location && (
                        <div className="mt-1 text-muted-foreground truncate pl-0.5">
                          {issue.location}
                        </div>
                      )}
                    </button>
                  ))}
                  {issues.length === 0 && (
                    <div className="px-2 py-4 text-xs text-green-400 text-center">
                      {t("app.validation.issue.none")}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>

            {/* Detail panel */}
            <div className="flex-1 p-4 overflow-auto">
              {selectedIssue ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="destructive">{selectedIssue.code}</Badge>
                  </div>
                  {selectedIssue.location && (
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Location
                      </div>
                      <div className="font-mono text-xs bg-muted rounded px-2 py-1">
                        {selectedIssue.location}
                      </div>
                    </div>
                  )}
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Message
                    </div>
                    <div className="text-sm">{selectedIssue.message}</div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">
                  {issues.length > 0
                    ? t("app.validation.issue.select_prompt")
                    : t("app.validation.issue.none_detail")}
                </div>
              )}
            </div>
          </div>
        )}

        <DialogFooter className="px-4 py-3 shrink-0 border-t flex-row justify-between sm:justify-between gap-2">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => void runValidation()} disabled={loading}>
              <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              {t("app.button.validate")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyIssue}
              disabled={selectedIssue === null}
            >
              <Copy className="mr-1 h-3.5 w-3.5" />
              {t("app.button.copy_issue")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyAll}
              disabled={report === null}
            >
              {t("app.button.copy_all_issues")}
            </Button>
          </div>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            {t("app.button.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
