import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { AppLayout } from "@/components/layout/AppLayout";
import { MenuBar } from "@/components/layout/MenuBar";
import { ToolBar } from "@/components/layout/ToolBar";
import { StatusBar } from "@/components/layout/StatusBar";
import { StepListPanel } from "@/components/panels/StepListPanel";
import { StepEditorPanel } from "@/components/panels/StepEditorPanel";
import { LogPanel } from "@/components/panels/LogPanel";
import { useStudio } from "@/hooks/useStudio";
import type { VariableEntry, ProfilesMap } from "@/hooks/useStudio";

import { FullJsonEditorDialog } from "@/components/dialogs/FullJsonEditorDialog";
import { VariablesEditorDialog } from "@/components/dialogs/VariablesEditorDialog";
import { ProfilesEditorDialog } from "@/components/dialogs/ProfilesEditorDialog";
import { ExecutionOutputsDialog } from "@/components/dialogs/ExecutionOutputsDialog";
import { PreflightValidationDialog } from "@/components/dialogs/PreflightValidationDialog";
import { RunDiagnosticsDialog } from "@/components/dialogs/RunDiagnosticsDialog";
import { HelpGuideDialog } from "@/components/dialogs/HelpGuideDialog";
import { HotkeySettingsDialog } from "@/components/dialogs/HotkeySettingsDialog";
import { ProfileDiffDialog } from "@/components/dialogs/ProfileDiffDialog";

// ---------------------------------------------------------------------------
// Dialog open/close state
// ---------------------------------------------------------------------------

interface DialogState {
  fullJson: boolean;
  variables: boolean;
  profiles: boolean;
  executionOutputs: boolean;
  preflight: boolean;
  diagnostics: boolean;
  help: boolean;
  hotkey: boolean;
  profileDiff: boolean;
}

const CLOSED_DIALOGS: DialogState = {
  fullJson: false,
  variables: false,
  profiles: false,
  executionOutputs: false,
  preflight: false,
  diagnostics: false,
  help: false,
  hotkey: false,
  profileDiff: false,
};

export default function App() {
  const { i18n, t } = useTranslation();
  const studio = useStudio();

  // --- Dialog open/close state ---------------------------------------------
  const [dialogs, setDialogs] = useState<DialogState>(CLOSED_DIALOGS);

  const openDialog = useCallback((name: keyof DialogState) => {
    setDialogs((prev) => ({ ...prev, [name]: true }));
  }, []);

  const closeDialog = useCallback((name: keyof DialogState) => {
    setDialogs((prev) => ({ ...prev, [name]: false }));
  }, []);

  // --- Cached dialog data --------------------------------------------------
  const [variablesData, setVariablesData] = useState<VariableEntry[]>([]);
  const [profilesData, setProfilesData] = useState<ProfilesMap>({});
  const [executionData, setExecutionData] = useState<Record<string, unknown>>({});
  const [outputsData, setOutputsData] = useState<Record<string, unknown>>({});
  const [hotkeyValue, setHotkeyValue] = useState("Alt+Shift+F12");

  // --- Sync i18next language with server locale ----------------------------
  useEffect(() => {
    if (studio.locale && studio.locale !== i18n.language) {
      void i18n.changeLanguage(studio.locale);
    }
  }, [studio.locale, i18n]);

  // --- Global keyboard shortcuts -------------------------------------------
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "F1") {
        e.preventDefault();
        openDialog("help");
        return;
      }

      // Ctrl+S: save scenario (open save-as dialog)
      if (e.ctrlKey && e.key === "s") {
        e.preventDefault();
        void studio.saveScenarioAs();
        return;
      }

      // Ctrl+D: duplicate selected step
      if (e.ctrlKey && e.key === "d") {
        e.preventDefault();
        if (studio.selectedIndex !== null) {
          void studio.duplicateStep(studio.selectedIndex);
        }
        return;
      }

      // Ctrl+ArrowUp: move step up
      if (e.ctrlKey && e.key === "ArrowUp") {
        e.preventDefault();
        if (studio.selectedIndex !== null) {
          void studio.moveStepUp(studio.selectedIndex);
        }
        return;
      }

      // Ctrl+ArrowDown: move step down
      if (e.ctrlKey && e.key === "ArrowDown") {
        e.preventDefault();
        if (studio.selectedIndex !== null) {
          void studio.moveStepDown(studio.selectedIndex);
        }
        return;
      }

      // Delete: delete selected step (only when not focused on an input/textarea/select)
      if (e.key === "Delete") {
        const tag = (e.target as HTMLElement).tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
          e.preventDefault();
          if (studio.selectedIndex !== null) {
            void studio.deleteStep(studio.selectedIndex);
          }
        }
        return;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [openDialog, studio]);

  // --- Window title update based on recording/running state ----------------
  useEffect(() => {
    if (studio.isRecording) {
      document.title = "🔴 Recording — Robot Automation Studio";
    } else if (studio.runPhase !== "idle" && studio.runPhase !== "stopping") {
      document.title = "▶ Running — Robot Automation Studio";
    } else {
      document.title = "Robot Automation Studio";
    }
  }, [studio.isRecording, studio.runPhase]);

  // --- Computed state -------------------------------------------------------
  const isRunning =
    studio.runPhase !== "idle" && studio.runPhase !== "stopping";

  // --- Step handlers -------------------------------------------------------
  const handleSetLocale = (loc: string) => {
    void studio.setLocale(loc);
    void i18n.changeLanguage(loc);
  };

  const handleDeleteStep = () => {
    if (studio.selectedIndex !== null) {
      void studio.deleteStep(studio.selectedIndex);
    }
  };

  const handleMoveUp = () => {
    if (studio.selectedIndex !== null) {
      void studio.moveStepUp(studio.selectedIndex);
    }
  };

  const handleMoveDown = () => {
    if (studio.selectedIndex !== null) {
      void studio.moveStepDown(studio.selectedIndex);
    }
  };

  const handleDuplicate = () => {
    if (studio.selectedIndex !== null) {
      void studio.duplicateStep(studio.selectedIndex);
    }
  };

  // --- Open dialog handlers (load data first) ------------------------------
  const handleOpenVariables = useCallback(async () => {
    const vars = await studio.getVariables();
    setVariablesData(vars);
    openDialog("variables");
  }, [studio, openDialog]);

  const handleOpenProfiles = useCallback(async () => {
    const profs = await studio.getProfiles();
    setProfilesData(profs);
    openDialog("profiles");
  }, [studio, openDialog]);

  const handleOpenExecutionOutputs = useCallback(async () => {
    const { execution, outputs } = await studio.getExecutionOutputs();
    setExecutionData(execution);
    setOutputsData(outputs);
    openDialog("executionOutputs");
  }, [studio, openDialog]);

  // --- Save handlers from dialogs ------------------------------------------
  const handleSaveVariables = useCallback(
    (vars: VariableEntry[]) => {
      void studio.setVariables(vars);
    },
    [studio],
  );

  const handleSaveProfiles = useCallback(
    (profs: ProfilesMap) => {
      void studio.setProfiles(profs);
    },
    [studio],
  );

  const handleSaveExecutionOutputs = useCallback(
    (execution: Record<string, unknown>, outputs: Record<string, unknown>) => {
      void studio.setExecutionOutputs(execution, outputs);
    },
    [studio],
  );

  const handleApplyHotkey = useCallback(
    (hotkey: string) => {
      setHotkeyValue(hotkey);
      void studio.updateSettings({ stop_hotkey_label: hotkey });
    },
    [studio],
  );

  // --- Scenario name change from toolbar -----------------------------------
  const handleScenarioNameChange = useCallback(
    (name: string) => {
      void studio.updateHeader({ name });
    },
    [studio],
  );

  // --- Update header from scenario settings tab ----------------------------
  const handleUpdateHeader = useCallback(
    (params: Record<string, unknown>) => {
      void studio.updateHeader(params);
    },
    [studio],
  );

  // --- Insert params template -----------------------------------------------
  const handleInsertParamsTemplate = useCallback(
    async (action: string) => {
      const template = await studio.getParamsTemplate(action);
      if (template && studio.selectedStep) {
        // Check if current step already has non-empty params
        const existingParams = studio.selectedStep.params;
        const hasExistingParams =
          existingParams != null && Object.keys(existingParams).length > 0;
        if (hasExistingParams) {
          const confirmed = window.confirm(
            t("app.step_editor.confirm_overwrite_params"),
          );
          if (!confirmed) return;
        }
        // Apply the template as new params
        void studio.applyStep({
          ...studio.selectedStep,
          params: template,
          index: studio.selectedIndex ?? undefined,
        });
      }
    },
    [studio, t],
  );

  return (
    <>
      <AppLayout
        menuBar={
          <MenuBar
            onSave={() => void studio.saveScenarioAs()}
            onLoad={() => void studio.loadScenarioFrom()}
            onFullJson={() => openDialog("fullJson")}
            onHelp={() => openDialog("help")}
            onDiagnostics={() => openDialog("diagnostics")}
            onExit={() => window.close()}
            onAddStep={(type) => void studio.addStep(type)}
            onDeleteStep={handleDeleteStep}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            onDuplicate={handleDuplicate}
            onStartRecording={() => void studio.startRecording()}
            onStopRecording={() => void studio.stopRecording()}
            onRunRobot={() => void studio.runRobot()}
            onStopRobot={() => void studio.stopRobot()}
            onSetLocale={handleSetLocale}
            onVariables={() => void handleOpenVariables()}
            onProfiles={() => void handleOpenProfiles()}
            onExecutionOutputs={() => void handleOpenExecutionOutputs()}
            onPreflight={() => openDialog("preflight")}
            onHotkeySettings={() => openDialog("hotkey")}
          />
        }
        toolBar={
          <ToolBar
            isRecording={studio.isRecording}
            isRunning={isRunning}
            scenarioName={studio.scenarioHeader.name ?? ""}
            onScenarioNameChange={handleScenarioNameChange}
            onStartRecording={() => void studio.startRecording()}
            onStopRecording={() => void studio.stopRecording()}
            onRunRobot={() => void studio.runRobot()}
            onStopRobot={() => void studio.stopRobot()}
            onExport={() => void studio.exportScenario()}
            onAddStep={(type) => void studio.addStep(type)}
            onDeleteStep={handleDeleteStep}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            onDuplicate={handleDuplicate}
            hasSelection={studio.selectedIndex !== null}
          />
        }
        leftPanel={
          <StepListPanel
            steps={studio.steps}
            selectedIndex={studio.selectedIndex}
            onSelectStep={(index) => void studio.selectStep(index)}
            onDeleteStep={handleDeleteStep}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            onDuplicate={handleDuplicate}
          />
        }
        rightPanel={
          <StepEditorPanel
            step={studio.selectedStep}
            selectedIndex={studio.selectedIndex}
            scenarioHeader={studio.scenarioHeader}
            onApplyStep={(params) => void studio.applyStep(params)}
            onExport={(outputDir, exportName) =>
              void studio.exportScenario(outputDir, exportName)
            }
            onUpdateHeader={handleUpdateHeader}
            onInsertParamsTemplate={(action) => void handleInsertParamsTemplate(action)}
            onOpenVariables={() => void handleOpenVariables()}
            onOpenProfiles={() => void handleOpenProfiles()}
            onOpenExecutionOutputs={() => void handleOpenExecutionOutputs()}
            onOpenPreflight={() => openDialog("preflight")}
            onOpenProfileDiff={() => openDialog("profileDiff")}
            onBrowseDirectory={studio.browseDirectory}
            onOpenDirectory={(path) => void studio.openDirectory(path)}
          />
        }
        logPanel={<LogPanel messages={studio.logMessages} />}
        statusBar={
          <StatusBar
            runPhase={studio.runPhase}
            isRecording={studio.isRecording}
            connected={studio.connected}
            stopHotkeyLabel={hotkeyValue}
            locale={studio.locale}
            onSetLocale={handleSetLocale}
          />
        }
      />
      {/* ---- Dialogs ---- */}
      <FullJsonEditorDialog
        open={dialogs.fullJson}
        onOpenChange={(v) => (v ? openDialog("fullJson") : closeDialog("fullJson"))}
        onGetJson={studio.getFullJson}
        onSetJson={studio.setFullJson}
      />

      <VariablesEditorDialog
        open={dialogs.variables}
        onOpenChange={(v) => (v ? openDialog("variables") : closeDialog("variables"))}
        initialVariables={variablesData}
        onSave={handleSaveVariables}
      />

      <ProfilesEditorDialog
        open={dialogs.profiles}
        onOpenChange={(v) => (v ? openDialog("profiles") : closeDialog("profiles"))}
        initialProfiles={profilesData}
        onSave={handleSaveProfiles}
      />

      <ExecutionOutputsDialog
        open={dialogs.executionOutputs}
        onOpenChange={(v) =>
          v ? openDialog("executionOutputs") : closeDialog("executionOutputs")
        }
        initialExecution={executionData}
        initialOutputs={outputsData}
        onSave={handleSaveExecutionOutputs}
      />

      <PreflightValidationDialog
        open={dialogs.preflight}
        onOpenChange={(v) => (v ? openDialog("preflight") : closeDialog("preflight"))}
        onRunPreflight={studio.runPreflight}
      />

      <RunDiagnosticsDialog
        open={dialogs.diagnostics}
        onOpenChange={(v) =>
          v ? openDialog("diagnostics") : closeDialog("diagnostics")
        }
        logMessages={studio.logMessages}
        getDiagnostics={studio.getDiagnostics}
        openDirectory={studio.openDirectory}
      />

      <HelpGuideDialog
        open={dialogs.help}
        onOpenChange={(v) => (v ? openDialog("help") : closeDialog("help"))}
      />

      <HotkeySettingsDialog
        open={dialogs.hotkey}
        onOpenChange={(v) => (v ? openDialog("hotkey") : closeDialog("hotkey"))}
        currentHotkey={hotkeyValue}
        onApply={handleApplyHotkey}
      />

      <ProfileDiffDialog
        open={dialogs.profileDiff}
        onOpenChange={(v) => (v ? openDialog("profileDiff") : closeDialog("profileDiff"))}
        scenarioHeader={studio.scenarioHeader}
        onGetDiff={studio.getProfileDiff}
      />
    </>
  );
}
