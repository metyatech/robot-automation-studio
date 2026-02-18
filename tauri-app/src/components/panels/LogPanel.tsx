import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface LogPanelProps {
  messages: string[];
}

export function LogPanel({ messages }: LogPanelProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (!collapsed) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, collapsed]);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex flex-col border-t border-border">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-1 bg-card/80">
          <h3 className="text-xs font-semibold text-foreground">
            {t("app.label.output_log")}
          </h3>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setCollapsed((prev) => !prev)}
              >
                {collapsed ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("app.log.toggle.tooltip")}</TooltipContent>
          </Tooltip>
        </div>

        {/* Log content */}
        {!collapsed && (
          <ScrollArea className="h-[160px] bg-[hsl(240,15%,6%)]">
            <div className="px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {messages.length === 0 ? (
                <span className="italic">No log messages yet.</span>
              ) : (
                messages.map((msg, i) => (
                  <div key={i} className="whitespace-pre-wrap break-all">
                    {msg}
                  </div>
                ))
              )}
              <div ref={endRef} />
            </div>
          </ScrollArea>
        )}
      </div>
    </TooltipProvider>
  );
}
