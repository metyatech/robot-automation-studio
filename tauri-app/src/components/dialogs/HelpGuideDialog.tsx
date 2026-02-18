import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Search, HelpCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

interface HelpEntry {
  id: string;
  title: string;
  summary: string;
  detail: string;
  category: string;
}

const HELP_ENTRIES: HelpEntry[] = [
  {
    id: "menubar.file",
    title: "File Menu",
    summary: "Access file operations: save, load, full JSON editor, and exit.",
    detail:
      "The File menu contains scenario persistence commands (Save, Load), the Full JSON editor for direct scenario editing, and Exit to close the application.",
    category: "Menu",
  },
  {
    id: "menu.file.save",
    title: "Save",
    summary: "Save the current scenario to a JSON file.",
    detail:
      "Writes the current in-memory scenario to a .scenario.json file. The scenario includes all steps, variables, profiles, and execution configuration.",
    category: "File",
  },
  {
    id: "menu.file.load",
    title: "Load",
    summary: "Load a scenario from a JSON file.",
    detail:
      "Reads a .scenario.json file and replaces the current in-memory scenario. All steps and settings are refreshed from the file.",
    category: "File",
  },
  {
    id: "menu.file.full_json",
    title: "Full JSON Editor",
    summary: "Edit the full scenario JSON directly.",
    detail:
      "Opens a dialog with the complete v2 scenario JSON. You can format, reload from the current model, or apply changes directly. Invalid JSON will be rejected with an error.",
    category: "File",
  },
  {
    id: "menubar.edit",
    title: "Edit Menu",
    summary: "Step editing operations: add, delete, move, duplicate.",
    detail:
      "The Edit menu provides step management operations. Use Add Step to insert new steps of various types. Use Delete, Move Up/Down, and Duplicate to manage existing steps.",
    category: "Menu",
  },
  {
    id: "menubar.run",
    title: "Run Menu",
    summary: "Recording and robot execution controls.",
    detail:
      "The Run menu contains Record (start capturing UI actions), Stop Recording (commit captured steps), Run Robot (execute the scenario), and Stop Robot (terminate execution).",
    category: "Menu",
  },
  {
    id: "toolbar.record",
    title: "Record Button",
    summary: "Start capturing UI interactions as steps.",
    detail:
      "Click to begin recording. The button turns red during recording. All mouse clicks, keyboard shortcuts, and menu interactions are captured as automation steps.",
    category: "Toolbar",
  },
  {
    id: "toolbar.run",
    title: "Run Robot Button",
    summary: "Execute the current scenario as a Robot Framework test.",
    detail:
      "Exports the scenario to Robot Framework format and runs it. Preflight validation runs first; if issues are found, execution is blocked. Check the Output Log for progress.",
    category: "Toolbar",
  },
  {
    id: "panel.steplist",
    title: "Step List Panel",
    summary: "List of all steps in the current scenario.",
    detail:
      "Shows all steps in order. Click to select and edit a step. Steps are numbered and show their kind (action/control/group) and title.",
    category: "Panel",
  },
  {
    id: "panel.stepeditor",
    title: "Step Editor Panel",
    summary: "Edit the currently selected step.",
    detail:
      "Shows fields for the selected step: ID, title, kind, action/control type, description, condition, params JSON, and annotations. Click Apply Step Changes to save edits.",
    category: "Panel",
  },
  {
    id: "panel.scenario",
    title: "Scenario Settings Tab",
    summary: "View and configure scenario-level settings.",
    detail:
      "Shows the scenario ID, target platform, window hint, execution mode, and Unity project path. Use the Variables, Profiles, Execution/Outputs, and Validate buttons to manage scenario configuration.",
    category: "Panel",
  },
  {
    id: "panel.export",
    title: "Export Tab",
    summary: "Configure and trigger scenario export.",
    detail:
      "Set the output directory and export name, then click Export to generate the Robot Framework .robot file and scenario JSON.",
    category: "Panel",
  },
  {
    id: "dialog.variables",
    title: "Variables Editor",
    summary: "Manage scenario variables.",
    detail:
      "Add, edit, and delete scenario variables. Each variable has an ID, type (string/int/float/bool/json), required flag, and default value. Types are validated on save.",
    category: "Dialog",
  },
  {
    id: "dialog.profiles",
    title: "Profiles Editor",
    summary: "Manage execution profiles.",
    detail:
      "Profiles allow running the same scenario with different variable values. Each profile has a name, description, and variable override map. Override values can be JSON or plain text.",
    category: "Dialog",
  },
  {
    id: "dialog.execution_outputs",
    title: "Execution / Outputs Editor",
    summary: "Edit execution and outputs configuration as JSON.",
    detail:
      "Directly edit the `execution` and `outputs` sections of the scenario JSON. The execution object controls how the robot is launched (attach/launch mode). The outputs object configures result paths.",
    category: "Dialog",
  },
  {
    id: "dialog.preflight",
    title: "Preflight Validation",
    summary: "Run validation checks before execution.",
    detail:
      "Validates the scenario for common issues: missing required variables, invalid step params, unsupported actions. Each issue shows a code, location, and message. Copy individual issues or all issues for debugging.",
    category: "Dialog",
  },
  {
    id: "dialog.hotkey",
    title: "Hotkey Settings",
    summary: "Configure the emergency stop hotkey.",
    detail:
      "Set the key combination used to stop recording or robot execution in an emergency. The hotkey works globally while the application is running.",
    category: "Dialog",
  },
  {
    id: "statusbar",
    title: "Status Bar",
    summary: "Shows current run/record state and stop hotkey.",
    detail:
      "The status bar at the bottom shows whether recording or execution is active, and displays the configured stop hotkey combination.",
    category: "UI",
  },
  {
    id: "logpanel",
    title: "Output Log",
    summary: "Real-time log of application events.",
    detail:
      "All application events are logged here: recording start/stop, robot run progress, export results, validation outcomes, and errors. Searchable by text.",
    category: "Panel",
  },
];

interface HelpGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function HelpGuideDialog({ open, onOpenChange }: HelpGuideDialogProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<HelpEntry | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return HELP_ENTRIES;
    return HELP_ENTRIES.filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        e.summary.toLowerCase().includes(q) ||
        e.detail.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q)
    );
  }, [query]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl w-full h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4" />
            {t("app.help.dialog.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="px-4 pb-2 shrink-0">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("app.log.search")}
              className="pl-7 h-8 text-xs"
            />
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t("app.help.dialog.shown", {
              shown: filtered.length,
              total: HELP_ENTRIES.length,
            })}
          </div>
        </div>

        <div className="flex flex-1 min-h-0 gap-0">
          {/* Entry list */}
          <div className="w-60 shrink-0 border-r flex flex-col">
            <ScrollArea className="flex-1">
              <div className="p-1 space-y-0.5">
                {filtered.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`w-full text-left rounded px-2 py-2 text-xs transition-colors ${
                      selectedEntry?.id === entry.id
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="font-medium truncate">{entry.title}</div>
                    <div className="text-muted-foreground text-[10px]">{entry.category}</div>
                  </button>
                ))}
                {filtered.length === 0 && (
                  <div className="px-2 py-4 text-xs text-muted-foreground text-center">
                    {t("app.help.dialog.no_match")}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Detail panel */}
          <ScrollArea className="flex-1">
            {selectedEntry ? (
              <div className="p-4 space-y-4">
                <div>
                  <h3 className="font-semibold text-sm">{selectedEntry.title}</h3>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {selectedEntry.category}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                    Summary
                  </div>
                  <p className="text-sm">{selectedEntry.summary}</p>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                    Details
                  </div>
                  <p className="text-sm leading-relaxed">{selectedEntry.detail}</p>
                </div>
              </div>
            ) : (
              <div className="p-4 text-xs text-muted-foreground">
                {t("app.help.header")}
              </div>
            )}
          </ScrollArea>
        </div>

        <DialogFooter className="px-4 pb-4 shrink-0 border-t pt-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("app.button.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
