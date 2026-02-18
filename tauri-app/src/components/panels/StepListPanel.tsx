import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  MousePointerClick,
  GripHorizontal,
  Keyboard,
  Menu as MenuIcon,
  Type,
  GitBranch,
  List,
  Zap,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { StepData } from "@/hooks/useStudio";

interface StepListPanelProps {
  steps: StepData[];
  selectedIndex: number | null;
  onSelectStep: (index: number) => void;
  onDeleteStep?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onDuplicate?: () => void;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
}

/** Map action/kind to a lucide icon component. */
function StepIcon({ step }: { step: StepData }) {
  const kind = step.kind ?? "action";
  const action = step.action ?? "";

  if (kind === "control") return <GitBranch className="h-4 w-4 shrink-0 text-yellow-400" />;
  if (kind === "group") return <List className="h-4 w-4 shrink-0 text-blue-400" />;

  // action kind -- distinguish by action name
  switch (action) {
    case "click":
      return <MousePointerClick className="h-4 w-4 shrink-0 text-muted-foreground" />;
    case "drag_drop":
      return <GripHorizontal className="h-4 w-4 shrink-0 text-muted-foreground" />;
    case "press_keys":
      return <Keyboard className="h-4 w-4 shrink-0 text-muted-foreground" />;
    case "open_menu":
      return <MenuIcon className="h-4 w-4 shrink-0 text-muted-foreground" />;
    case "type_text":
      return <Type className="h-4 w-4 shrink-0 text-muted-foreground" />;
    default:
      return <Zap className="h-4 w-4 shrink-0 text-muted-foreground" />;
  }
}

function stepLabel(step: StepData, index: number): string {
  const title = step.title?.trim();
  if (title) return title;

  const kind = step.kind ?? "action";
  if (kind === "control") return step.control ?? "control";
  if (kind === "group") return "group";
  return step.action ?? `step-${index + 1}`;
}

export function StepListPanel({
  steps,
  selectedIndex,
  onSelectStep,
  onDeleteStep,
  onMoveUp,
  onMoveDown,
  onDuplicate,
}: StepListPanelProps) {
  const { t } = useTranslation();
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
  });
  const menuRef = useRef<HTMLDivElement>(null);

  const closeMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
  }, []);

  // Close menu on click-away
  useEffect(() => {
    if (!contextMenu.visible) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };
    window.addEventListener("mousedown", handleClick);
    return () => window.removeEventListener("mousedown", handleClick);
  }, [contextMenu.visible, closeMenu]);

  const handleContextMenu = (e: React.MouseEvent, index: number) => {
    e.preventDefault();
    onSelectStep(index);
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY });
  };

  const handleMenuAction = (action: () => void) => {
    closeMenu();
    action();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="px-3 py-2">
        <h3 className="text-sm font-semibold text-foreground">
          {t("app.label.steps")}
        </h3>
      </div>
      <TooltipProvider delayDuration={400}>
        <ScrollArea className="flex-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="px-1 pb-2">
                {steps.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-muted-foreground text-center">
                    {t("app.validation.step.none")}
                  </p>
                ) : (
                  steps.map((step, index) => (
                    <button
                      key={`${index}-${step.id ?? ""}`}
                      className={`flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs transition-colors ${
                        index === selectedIndex
                          ? "bg-accent text-accent-foreground"
                          : "hover:bg-muted/50 text-muted-foreground"
                      } ${step.disabled ? "opacity-50" : ""}`}
                      onClick={() => onSelectStep(index)}
                      onContextMenu={(e) => handleContextMenu(e, index)}
                    >
                      <span className="shrink-0 w-5 text-right text-[10px] text-muted-foreground/60">
                        {index + 1}
                      </span>
                      <StepIcon step={step} />
                      <span className="truncate font-mono">
                        {stepLabel(step, index)}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </TooltipTrigger>
            <TooltipContent side="right">
              {t("app.tooltip.steps_list")}
            </TooltipContent>
          </Tooltip>
        </ScrollArea>
      </TooltipProvider>

      {/* Context menu */}
      {contextMenu.visible && (
        <div
          ref={menuRef}
          className="fixed z-50 min-w-[140px] rounded-md border border-border bg-popover py-1 shadow-md"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            className="flex w-full items-center px-3 py-1.5 text-xs hover:bg-muted/70 text-foreground"
            onClick={() => {
              if (onMoveUp) handleMenuAction(onMoveUp);
              else closeMenu();
            }}
          >
            {t("app.step_list.context.move_up")}
          </button>
          <button
            className="flex w-full items-center px-3 py-1.5 text-xs hover:bg-muted/70 text-foreground"
            onClick={() => {
              if (onMoveDown) handleMenuAction(onMoveDown);
              else closeMenu();
            }}
          >
            {t("app.step_list.context.move_down")}
          </button>
          <button
            className="flex w-full items-center px-3 py-1.5 text-xs hover:bg-muted/70 text-foreground"
            onClick={() => {
              if (onDuplicate) handleMenuAction(onDuplicate);
              else closeMenu();
            }}
          >
            {t("app.step_list.context.duplicate")}
          </button>
          <div className="my-1 border-t border-border" />
          <button
            className="flex w-full items-center px-3 py-1.5 text-xs hover:bg-muted/70 text-destructive"
            onClick={() => {
              if (onDeleteStep) handleMenuAction(onDeleteStep);
              else closeMenu();
            }}
          >
            {t("app.step_list.context.delete")}
          </button>
        </div>
      )}
    </div>
  );
}
