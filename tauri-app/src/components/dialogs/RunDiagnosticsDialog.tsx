import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Activity, ChevronDown, ChevronRight, FolderOpen, Copy, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DiagnosticsInfo } from "@/hooks/useStudio";

interface RunDiagnosticsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  logMessages: string[];
  getDiagnostics: () => Promise<DiagnosticsInfo | null>;
  openDirectory: (path: string) => Promise<void>;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API failed silently
    }
  }, [text]);

  return (
    <Button variant="outline" size="sm" onClick={() => void handleCopy()} className="shrink-0">
      {copied ? (
        <>
          <Check className="h-3 w-3 mr-1" />
          {t("app.diagnostics.copied")}
        </>
      ) : (
        <>
          <Copy className="h-3 w-3 mr-1" />
          {label}
        </>
      )}
    </Button>
  );
}

function DirectoryRow({
  label,
  path,
  onOpen,
  openLabel,
}: {
  label: string;
  path: string;
  onOpen: () => void;
  openLabel: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground w-40 shrink-0">{label}</span>
      <span className="flex-1 font-mono text-xs truncate" title={path}>
        {path}
      </span>
      <Button variant="outline" size="sm" onClick={onOpen} className="shrink-0">
        <FolderOpen className="h-3 w-3 mr-1" />
        {openLabel}
      </Button>
    </div>
  );
}

export function RunDiagnosticsDialog({
  open,
  onOpenChange,
  logMessages,
  getDiagnostics,
  openDirectory,
}: RunDiagnosticsDialogProps) {
  const { t } = useTranslation();

  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState<DiagnosticsInfo | null>(null);
  const [jsonExpanded, setJsonExpanded] = useState(false);

  // Fetch diagnostics info when dialog opens
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setInfo(null);
    void getDiagnostics().then((result) => {
      setInfo(result);
      setLoading(false);
    });
  }, [open, getDiagnostics]);

  // Filter log messages relevant to diagnostics (run-related)
  const diagMessages = logMessages.filter(
    (m) =>
      m.includes("run_diag") ||
      m.includes("Robot") ||
      m.includes("robot") ||
      m.includes("Export") ||
      m.includes("export") ||
      m.includes("preflight") ||
      m.includes("Preflight") ||
      m.includes("validation") ||
      m.includes("Validation") ||
      m.includes("Run") ||
      m.includes("run"),
  );
  const displayMessages = diagMessages.length > 0 ? diagMessages : logMessages;

  const jsonText = info?.last_run_json ? JSON.stringify(info.last_run_json, null, 2) : "";
  const summaryText = info?.last_run_summary ?? "";
  const openLabel = t("app.diagnostics.open");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl w-full h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            {t("app.dialog.run_diagnostics.title")}
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="flex-1 min-h-0">
          <div className="px-4 pb-2 space-y-4">
            {loading && (
              <div className="text-sm text-muted-foreground py-2">
                {t("app.diagnostics.loading")}
              </div>
            )}

            {!loading && info && (
              <>
                {/* Directories */}
                <section className="space-y-2">
                  <DirectoryRow
                    label={t("app.diagnostics.diagnostics_dir")}
                    path={info.diagnostics_dir}
                    onOpen={() => void openDirectory(info.diagnostics_dir)}
                    openLabel={openLabel}
                  />
                  <DirectoryRow
                    label={t("app.diagnostics.subflow_logs_dir")}
                    path={info.subflow_logs_dir}
                    onOpen={() => void openDirectory(info.subflow_logs_dir)}
                    openLabel={openLabel}
                  />
                </section>

                {/* Last Run Summary */}
                <section className="space-y-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      {t("app.diagnostics.summary")}
                    </h3>
                    {summaryText && (
                      <CopyButton text={summaryText} label={t("app.diagnostics.copy_summary")} />
                    )}
                  </div>
                  <div className="rounded border bg-black/20 p-3 font-mono text-xs whitespace-pre-wrap">
                    {summaryText || (
                      <span className="text-muted-foreground">{t("app.diagnostics.no_data")}</span>
                    )}
                  </div>
                </section>

                {/* Raw JSON (collapsible) */}
                <section className="space-y-1">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      className="flex items-center gap-1 text-xs font-semibold text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors"
                      onClick={() => setJsonExpanded((v) => !v)}
                    >
                      {jsonExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                      {t("app.diagnostics.raw_json")}
                    </button>
                    {jsonText && (
                      <CopyButton text={jsonText} label={t("app.diagnostics.copy_json")} />
                    )}
                  </div>
                  {jsonExpanded && (
                    <div className="rounded border bg-black/20 p-3 font-mono text-xs overflow-auto max-h-64 whitespace-pre">
                      {jsonText || (
                        <span className="text-muted-foreground">
                          {t("app.diagnostics.no_data")}
                        </span>
                      )}
                    </div>
                  )}
                </section>
              </>
            )}

            {!loading && !info && (
              <div className="text-sm text-muted-foreground py-2">
                {t("app.diagnostics.no_data")}
              </div>
            )}

            {/* Log Messages */}
            <section className="space-y-1">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {t("app.diagnostics.log_messages")}
              </h3>
              <div className="rounded border bg-black/20">
                <div className="p-3 font-mono text-xs space-y-0.5 max-h-48 overflow-auto">
                  {displayMessages.length > 0 ? (
                    displayMessages.map((msg, i) => (
                      <div
                        key={i}
                        className={`leading-relaxed ${
                          msg.toLowerCase().includes("fail") ||
                          msg.toLowerCase().includes("error") ||
                          msg.toLowerCase().includes("failed")
                            ? "text-red-400"
                            : msg.toLowerCase().includes("pass") ||
                                msg.toLowerCase().includes("ok") ||
                                msg.toLowerCase().includes("success")
                              ? "text-green-400"
                              : "text-foreground/80"
                        }`}
                      >
                        {msg}
                      </div>
                    ))
                  ) : (
                    <div className="text-muted-foreground py-4 text-center">
                      {t("app.info.run_diagnostics_unavailable.message")}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        </ScrollArea>

        <DialogFooter className="px-4 pb-4 pt-2 shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("app.button.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
