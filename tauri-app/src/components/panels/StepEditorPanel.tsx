import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight, FolderOpen } from "lucide-react";
import type { StepData, ScenarioHeader } from "@/hooks/useStudio";

// ---------------------------------------------------------------------------
// Step Validation Hint
// ---------------------------------------------------------------------------

function useStepValidation(
  formData: StepData,
  selectedIndex: number | null,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  return useMemo(() => {
    const prefix = t("app.field.step_validation.label");
    if (selectedIndex === null) {
      return { text: `${prefix}: ${t("app.validation.step.none")}`, state: "none" as const };
    }

    // Check params JSON validity
    const paramsText =
      typeof formData.params === "string"
        ? (formData.params as unknown as string)
        : JSON.stringify(formData.params ?? {});
    try {
      const parsed = JSON.parse(paramsText);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        return {
          text: `${prefix}: ${t("app.validation.step.invalid", { message: t("app.error.invalid_params_object") })}`,
          state: "invalid" as const,
        };
      }
    } catch (err) {
      return {
        text: `${prefix}: ${t("app.validation.step.invalid", { message: String(err) })}`,
        state: "invalid" as const,
      };
    }

    // Basic field validation
    const kind = formData.kind ?? "action";
    if (kind === "action") {
      const action = ((formData.action as string) ?? "").trim();
      if (!action) {
        return {
          text: `${prefix}: ${t("app.validation.step.invalid", { message: "action is required" })}`,
          state: "invalid" as const,
        };
      }
    } else if (kind === "control") {
      const control = ((formData.control as string) ?? "").trim();
      if (!control) {
        return {
          text: `${prefix}: ${t("app.validation.step.invalid", { message: "control is required" })}`,
          state: "invalid" as const,
        };
      }
    }

    return { text: `${prefix}: ${t("app.validation.step.ready")}`, state: "valid" as const };
  }, [formData, selectedIndex, t]);
}

// ---------------------------------------------------------------------------
// Step Editor Tab
// ---------------------------------------------------------------------------

interface StepEditorProps {
  step: StepData | null;
  selectedIndex: number | null;
  onApplyStep: (params: StepData & { index?: number }) => void;
  onInsertParamsTemplate?: (action: string) => void;
}

function StepEditor({ step, selectedIndex, onApplyStep, onInsertParamsTemplate }: StepEditorProps) {
  const { t } = useTranslation();

  const [formData, setFormData] = useState<StepData>({});
  const [targetOpen, setTargetOpen] = useState(false);

  useEffect(() => {
    if (step) {
      setFormData({
        id: step.id ?? "",
        title: step.title ?? "",
        kind: step.kind ?? "action",
        action: step.action ?? "",
        control: step.control ?? "",
        description: step.description ?? "",
        condition: step.condition ?? "",
        disabled: step.disabled ?? false,
        continue_on_error: step.continue_on_error ?? false,
        annotations: step.annotations,
        params: step.params,
        target: step.target,
      });
    } else {
      setFormData({});
    }
  }, [step]);

  const updateField = useCallback(
    <K extends keyof StepData>(field: K, value: StepData[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const handleApply = useCallback(() => {
    if (selectedIndex === null) return;

    const payload: StepData & { index?: number } = {
      ...formData,
      index: selectedIndex,
    };

    // Parse params from string if it's been edited as text
    if (typeof formData.params === "string") {
      try {
        payload.params = JSON.parse(formData.params as unknown as string);
      } catch {
        // Leave as-is; server will reject
      }
    }

    // Parse annotations from string
    if (typeof formData.annotations === "string") {
      try {
        payload.annotations = JSON.parse(formData.annotations as unknown as string);
      } catch {
        // Leave as-is
      }
    }

    onApplyStep(payload);
  }, [formData, selectedIndex, onApplyStep]);

  const handleInsertTemplate = useCallback(() => {
    const action = ((formData.action as string) ?? "").trim();
    if (onInsertParamsTemplate && action) {
      onInsertParamsTemplate(action);
    }
  }, [formData.action, onInsertParamsTemplate]);

  const validation = useStepValidation(formData, selectedIndex, t);

  const isAction = formData.kind === "action" || formData.kind === undefined;
  const isControl = formData.kind === "control";

  // Extract target info from step params
  const targetData = useMemo(() => {
    // Target data can be in step.target or step.params.target
    const target = formData.target ?? (formData.params as Record<string, unknown> | undefined)?.target;
    if (!target || typeof target !== "object") return null;
    return target as Record<string, unknown>;
  }, [formData.target, formData.params]);

  if (!step) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground p-8">
        {t("app.validation.step.none")}
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <ScrollArea className="h-full">
        <div className="space-y-4 p-4">
          {/* Step ID */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.step_id.label")}</Label>
            <Input
              value={(formData.id as string) ?? ""}
              onChange={(e) => updateField("id", e.target.value)}
              placeholder={t("app.field.step_id.placeholder")}
              className="h-8 text-xs"
            />
          </div>

          {/* Title */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.step_title.label")}</Label>
            <Input
              value={(formData.title as string) ?? ""}
              onChange={(e) => updateField("title", e.target.value)}
              placeholder={t("app.field.step_title.placeholder")}
              className="h-8 text-xs"
            />
          </div>

          {/* Kind */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.step_kind.label")}</Label>
            <Select
              value={formData.kind ?? "action"}
              onValueChange={(v) => updateField("kind", v)}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="action">
                  {t("app.option.kind.action")}
                </SelectItem>
                <SelectItem value="control">
                  {t("app.option.kind.control")}
                </SelectItem>
                <SelectItem value="group">
                  {t("app.option.kind.group")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Action (visible when kind=action) */}
          {isAction && (
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.step_action.label")}</Label>
              <Input
                value={(formData.action as string) ?? ""}
                onChange={(e) => updateField("action", e.target.value)}
                placeholder={t("app.field.step_action.placeholder")}
                className="h-8 text-xs"
              />
            </div>
          )}

          {/* Control (visible when kind=control) */}
          {isControl && (
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.step_control.label")}</Label>
              <Input
                value={(formData.control as string) ?? ""}
                onChange={(e) => updateField("control", e.target.value)}
                placeholder={t("app.field.step_control.placeholder")}
                className="h-8 text-xs"
              />
            </div>
          )}

          {/* Description */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.step_description.label")}</Label>
            <Input
              value={(formData.description as string) ?? ""}
              onChange={(e) => updateField("description", e.target.value)}
              placeholder={t("app.field.step_description.placeholder")}
              className="h-8 text-xs"
            />
          </div>

          {/* Condition */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.step_condition.label")}</Label>
            <Input
              value={(formData.condition as string) ?? ""}
              onChange={(e) => updateField("condition", e.target.value)}
              placeholder={t("app.field.step_condition.placeholder")}
              className="h-8 text-xs"
            />
          </div>

          {/* Checkboxes */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Checkbox
                id="step-disabled"
                checked={formData.disabled ?? false}
                onCheckedChange={(checked) =>
                  updateField("disabled", checked === true)
                }
              />
              <Label htmlFor="step-disabled" className="text-xs">
                {t("app.field.step_disabled")}
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="step-continue-on-error"
                checked={formData.continue_on_error ?? false}
                onCheckedChange={(checked) =>
                  updateField("continue_on_error", checked === true)
                }
              />
              <Label htmlFor="step-continue-on-error" className="text-xs">
                {t("app.field.step_continue_on_error")}
              </Label>
            </div>
          </div>

          {/* Target (collapsible) */}
          {isAction && targetData && (
            <Collapsible open={targetOpen} onOpenChange={setTargetOpen}>
              <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium hover:underline cursor-pointer">
                {targetOpen ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                {t("app.field.step_target.label")}
                {targetData.strategy ? (
                  <span className="ml-1 text-muted-foreground">
                    ({String(targetData.strategy)})
                  </span>
                ) : null}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <Textarea
                  value={JSON.stringify(targetData, null, 2)}
                  readOnly
                  className="min-h-[80px] font-mono text-xs bg-muted/50"
                />
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Annotations */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("app.field.annotations.label")}</Label>
            <Textarea
              value={
                typeof formData.annotations === "string"
                  ? (formData.annotations as unknown as string)
                  : JSON.stringify(formData.annotations ?? [], null, 2)
              }
              onChange={(e) =>
                updateField(
                  "annotations",
                  e.target.value as unknown as undefined,
                )
              }
              className="min-h-[60px] font-mono text-xs"
            />
          </div>

          {/* Params (JSON) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Label className="text-xs cursor-help">
                    {t("app.field.params.label")}
                  </Label>
                </TooltipTrigger>
                <TooltipContent>{t("app.tooltip.params_template")}</TooltipContent>
              </Tooltip>
              {isAction && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 text-[10px] px-2"
                      onClick={handleInsertTemplate}
                      disabled={!((formData.action as string) ?? "").trim()}
                    >
                      {t("app.button.params_template")}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{t("app.tooltip.params_template")}</TooltipContent>
                </Tooltip>
              )}
            </div>
            <Textarea
              value={
                typeof formData.params === "string"
                  ? (formData.params as unknown as string)
                  : JSON.stringify(formData.params ?? {}, null, 2)
              }
              onChange={(e) =>
                updateField("params", e.target.value as unknown as undefined)
              }
              className="min-h-[120px] font-mono text-xs"
            />
          </div>

          {/* Step Validation Hint */}
          <div
            className={`text-xs p-2 rounded border ${
              validation.state === "valid"
                ? "border-green-500/30 bg-green-500/5 text-green-600 dark:text-green-400"
                : validation.state === "invalid"
                  ? "border-red-500/30 bg-red-500/5 text-red-600 dark:text-red-400"
                  : "border-border bg-muted/30 text-muted-foreground"
            }`}
          >
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help">{validation.text}</span>
              </TooltipTrigger>
              <TooltipContent>{t("app.tooltip.step_validation")}</TooltipContent>
            </Tooltip>
          </div>

          {/* Apply Button */}
          <Button onClick={handleApply} className="w-full" size="sm">
            {t("app.button.apply_step")}
          </Button>
        </div>
      </ScrollArea>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Scenario Settings Tab
// ---------------------------------------------------------------------------

interface ScenarioSettingsProps {
  header: ScenarioHeader;
  onUpdateHeader?: (params: Record<string, unknown>) => void;
  onOpenVariables?: () => void;
  onOpenProfiles?: () => void;
  onOpenExecutionOutputs?: () => void;
  onOpenPreflight?: () => void;
  onOpenProfileDiff?: () => void;
  onBrowseDirectory?: () => Promise<string | null>;
}

function ScenarioSettings({
  header,
  onUpdateHeader,
  onOpenVariables,
  onOpenProfiles,
  onOpenExecutionOutputs,
  onOpenPreflight,
  onOpenProfileDiff,
  onBrowseDirectory,
}: ScenarioSettingsProps) {
  const { t } = useTranslation();

  const executionMode =
    (header.execution as Record<string, unknown> | undefined)?.mode as string | undefined ??
    (header.metadata as Record<string, unknown> | undefined)?.unity_execution_mode as string | undefined ??
    "attach";

  const projectPath =
    (header.metadata as Record<string, unknown> | undefined)?.unity_project_path as string | undefined ?? "";

  const subflowTimeout = String(
    (header.execution as Record<string, unknown> | undefined)?.subflow_timeout_seconds ?? ""
  );

  const activeProfile = String(
    (header.execution as Record<string, unknown> | undefined)?.active_profile ?? ""
  );

  const profiles = useMemo(() => {
    const profs = header.profiles as Record<string, unknown> | undefined;
    if (!profs || typeof profs !== "object") return [];
    return Object.keys(profs).filter((k) => k.trim() !== "").sort();
  }, [header.profiles]);

  const update = useCallback(
    (field: string, value: unknown) => {
      if (onUpdateHeader) {
        onUpdateHeader({ [field]: value });
      }
    },
    [onUpdateHeader],
  );

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4">
        {/* Scenario ID (read-only) */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.scenario_id.label")}</Label>
          <Input
            value={header.scenario_id ?? ""}
            readOnly
            placeholder={t("app.field.scenario_id.placeholder")}
            className="h-8 text-xs"
          />
        </div>

        {/* Scenario Name */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.scenario_name.placeholder")}</Label>
          <Input
            value={header.name ?? ""}
            onChange={(e) => update("name", e.target.value)}
            placeholder={t("app.field.scenario_name.placeholder")}
            className="h-8 text-xs"
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.description.label")}</Label>
          <Textarea
            value={header.description ?? ""}
            onChange={(e) => update("description", e.target.value)}
            placeholder={t("app.field.description.placeholder")}
            className="min-h-[60px] text-xs"
          />
        </div>

        {/* Target */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.target.label")}</Label>
          <Select
            value={header.target ?? "unity"}
            onValueChange={(v) => update("target", v)}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="unity">{t("app.option.target.unity")}</SelectItem>
              <SelectItem value="web">{t("app.option.target.web")}</SelectItem>
              <SelectItem value="desktop">{t("app.option.target.desktop")}</SelectItem>
              <SelectItem value="hybrid">{t("app.option.target.hybrid")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Window Hint */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.window_hint.label")}</Label>
          <Input
            value={header.target_window_hint ?? ""}
            onChange={(e) => update("target_window_hint", e.target.value)}
            placeholder={t("app.field.window_hint.placeholder")}
            className="h-8 text-xs"
          />
        </div>

        {/* Execution Mode */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.execution_mode.label")}</Label>
          <Select
            value={executionMode}
            onValueChange={(v) => update("execution_mode", v)}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="attach">{t("app.option.execution.attach")}</SelectItem>
              <SelectItem value="launch">{t("app.option.execution.launch")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Unity Project Path */}
        <div className="space-y-1.5">
          <Label className="text-xs">
            {t("app.field.unity_project_path.label")}
          </Label>
          <div className="flex gap-2">
            <Input
              value={projectPath}
              onChange={(e) => update("unity_project_path", e.target.value)}
              placeholder={t("app.field.unity_project_path.placeholder")}
              className="h-8 text-xs flex-1"
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs shrink-0"
                  onClick={() => {
                    if (onBrowseDirectory) {
                      void onBrowseDirectory().then((chosen) => {
                        if (chosen) update("unity_project_path", chosen);
                      });
                    }
                  }}
                >
                  <FolderOpen className="h-3 w-3 mr-1" />
                  {t("app.button.browse")}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t("app.file_dialog.select_unity_project.title")}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Subflow Timeout */}
        <div className="space-y-1.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <Label className="text-xs cursor-help">
                {t("app.field.subflow_timeout.label")}
              </Label>
            </TooltipTrigger>
            <TooltipContent>{t("app.tooltip.subflow_timeout")}</TooltipContent>
          </Tooltip>
          <Input
            value={subflowTimeout}
            onChange={(e) => update("subflow_timeout_seconds", e.target.value)}
            placeholder={t("app.field.subflow_timeout.placeholder")}
            className="h-8 text-xs"
          />
        </div>

        {/* Active Profile */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.active_profile.label")}</Label>
          <Select
            value={activeProfile || "__none__"}
            onValueChange={(v) => update("active_profile", v === "__none__" ? "" : v)}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">{t("app.option.profile.none")}</SelectItem>
              {profiles.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Tool buttons */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onOpenVariables}
            disabled={!onOpenVariables}
          >
            {t("app.button.variables")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onOpenProfiles}
            disabled={!onOpenProfiles}
          >
            {t("app.button.profiles")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onOpenExecutionOutputs}
            disabled={!onOpenExecutionOutputs}
          >
            {t("app.button.execution_outputs")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onOpenPreflight}
            disabled={!onOpenPreflight}
          >
            {t("app.button.validate")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={onOpenProfileDiff}
            disabled={!onOpenProfileDiff}
          >
            {t("app.button.profile_diff")}
          </Button>
        </div>
      </div>
    </ScrollArea>
  );
}

// ---------------------------------------------------------------------------
// Export Tab
// ---------------------------------------------------------------------------

interface ExportTabProps {
  onExport: (outputDir: string, exportName: string) => void;
  onBrowseDirectory?: () => Promise<string | null>;
  onOpenDirectory?: (path: string) => void;
}

function ExportTab({ onExport, onBrowseDirectory, onOpenDirectory }: ExportTabProps) {
  const { t } = useTranslation();
  const [outputDir, setOutputDir] = useState("artifacts/studio");
  const [exportName, setExportName] = useState("unity-editor-generated");

  const handleBrowse = useCallback(async () => {
    if (onBrowseDirectory) {
      const chosen = await onBrowseDirectory();
      if (chosen) setOutputDir(chosen);
    }
  }, [onBrowseDirectory]);

  const handleOpenDir = useCallback(() => {
    if (onOpenDirectory && outputDir.trim()) {
      onOpenDirectory(outputDir.trim());
    }
  }, [onOpenDirectory, outputDir]);

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4">
        {/* Output Dir */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.output_dir.label")}</Label>
          <div className="flex gap-2">
            <Input
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder={t("app.field.output_dir.placeholder")}
              className="h-8 text-xs flex-1"
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs shrink-0"
                  onClick={() => void handleBrowse()}
                >
                  <FolderOpen className="h-3 w-3 mr-1" />
                  {t("app.button.browse")}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t("app.tooltip.open_output_dir")}
              </TooltipContent>
            </Tooltip>
          </div>
          <p className="text-[10px] text-muted-foreground">
            {t("app.tooltip.open_output_dir")}
          </p>
        </div>

        {/* Export Name */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t("app.field.export_name.label")}</Label>
          <div className="flex gap-2">
            <Input
              value={exportName}
              onChange={(e) => setExportName(e.target.value)}
              placeholder={t("app.field.export_name.placeholder")}
              className="h-8 text-xs flex-1"
            />
            <Button
              size="sm"
              className="h-8 text-xs shrink-0"
              onClick={() => onExport(outputDir, exportName)}
            >
              {t("app.button.export")}
            </Button>
          </div>
        </div>

        {/* Open Output Directory */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs w-full"
              onClick={handleOpenDir}
              disabled={!outputDir.trim() || !onOpenDirectory}
            >
              <FolderOpen className="h-3 w-3 mr-1" />
              {t("app.button.open_output_dir")}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("app.tooltip.open_output_dir")}</TooltipContent>
        </Tooltip>
      </div>
    </ScrollArea>
  );
}

// ---------------------------------------------------------------------------
// Main StepEditorPanel (Tabbed)
// ---------------------------------------------------------------------------

interface StepEditorPanelProps {
  step: StepData | null;
  selectedIndex: number | null;
  scenarioHeader: ScenarioHeader;
  onApplyStep: (params: StepData & { index?: number }) => void;
  onExport: (outputDir: string, exportName: string) => void;
  onUpdateHeader?: (params: Record<string, unknown>) => void;
  onInsertParamsTemplate?: (action: string) => void;
  onOpenVariables?: () => void;
  onOpenProfiles?: () => void;
  onOpenExecutionOutputs?: () => void;
  onOpenPreflight?: () => void;
  onOpenProfileDiff?: () => void;
  onBrowseDirectory?: () => Promise<string | null>;
  onOpenDirectory?: (path: string) => void;
}

export function StepEditorPanel({
  step,
  selectedIndex,
  scenarioHeader,
  onApplyStep,
  onExport,
  onUpdateHeader,
  onInsertParamsTemplate,
  onOpenVariables,
  onOpenProfiles,
  onOpenExecutionOutputs,
  onOpenPreflight,
  onOpenProfileDiff,
  onBrowseDirectory,
  onOpenDirectory,
}: StepEditorPanelProps) {
  const { t } = useTranslation();

  return (
    <TooltipProvider delayDuration={300}>
      <Tabs defaultValue="step" className="flex h-full flex-col">
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent px-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="step" className="text-xs">
                {t("app.tab.step._self")}
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>{t("app.tab.step.tooltip")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="scenario" className="text-xs">
                {t("app.tab.scenario._self")}
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>{t("app.tab.scenario.tooltip")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="export" className="text-xs">
                {t("app.tab.export._self")}
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>{t("app.tab.export.tooltip")}</TooltipContent>
          </Tooltip>
        </TabsList>
        <TabsContent value="step" className="flex-1 overflow-hidden mt-0">
          <StepEditor
            step={step}
            selectedIndex={selectedIndex}
            onApplyStep={onApplyStep}
            onInsertParamsTemplate={onInsertParamsTemplate}
          />
        </TabsContent>
        <TabsContent value="scenario" className="flex-1 overflow-hidden mt-0">
          <ScenarioSettings
            header={scenarioHeader}
            onUpdateHeader={onUpdateHeader}
            onOpenVariables={onOpenVariables}
            onOpenProfiles={onOpenProfiles}
            onOpenExecutionOutputs={onOpenExecutionOutputs}
            onOpenPreflight={onOpenPreflight}
            onOpenProfileDiff={onOpenProfileDiff}
            onBrowseDirectory={onBrowseDirectory}
          />
        </TabsContent>
        <TabsContent value="export" className="flex-1 overflow-hidden mt-0">
          <ExportTab
            onExport={onExport}
            onBrowseDirectory={onBrowseDirectory}
            onOpenDirectory={onOpenDirectory}
          />
        </TabsContent>
      </Tabs>
    </TooltipProvider>
  );
}
