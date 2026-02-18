import { useState, useCallback, useEffect, useRef } from "react";
import { useIpc } from "./useIpc";

// ---------------------------------------------------------------------------
// Additional types for dialogs
// ---------------------------------------------------------------------------

export interface VariableEntry {
  id: string;
  type: string;
  required: boolean;
  default: unknown;
  [key: string]: unknown;
}

export interface ProfileData {
  description: string;
  variables: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ProfilesMap {
  [name: string]: ProfileData;
}

export interface ValidationIssue {
  code: string;
  location: string;
  message: string;
}

export interface ValidationReport {
  valid: boolean;
  issues: ValidationIssue[];
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StepData {
  id?: string;
  title?: string;
  kind?: string;
  action?: string;
  control?: string;
  description?: string;
  condition?: string;
  disabled?: boolean;
  continue_on_error?: boolean;
  annotations?: unknown[];
  params?: Record<string, unknown>;
  target?: Record<string, unknown>;
}

export interface ProfileDiffEntry {
  path: string;
  base_value: unknown;
  compare_value: unknown;
}

export interface DiagnosticsInfo {
  diagnostics_dir: string;
  subflow_logs_dir: string;
  last_run_summary: string;
  last_run_json: Record<string, unknown> | null;
}

export interface ScenarioHeader {
  scenario_id?: string;
  name?: string;
  description?: string;
  target?: string;
  target_window_hint?: string;
  execution?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  profiles?: Record<string, unknown>;
  variables?: unknown[];
}

export type RunPhase =
  | "idle"
  | "precheck"
  | "exporting"
  | "starting_robot"
  | "attaching_unity"
  | "running"
  | "stopping";

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const DEFAULT_PORT = 8765;

function resolveServerPort(): number {
  if (typeof window === "undefined") return DEFAULT_PORT;
  // Explicit ?port= parameter takes priority
  const portParam = new URLSearchParams(window.location.search).get("port");
  if (portParam) return parseInt(portParam, 10);
  // If served from the Python server (same origin), use the current port
  const locationPort = parseInt(window.location.port, 10);
  if (locationPort && locationPort !== 1420) return locationPort;
  // Fallback (e.g., Vite dev server on port 1420)
  return DEFAULT_PORT;
}

export function useStudio() {
  const port = resolveServerPort();

  const { call, subscribe, connected } = useIpc(port);

  // --- State ---------------------------------------------------------------
  const [steps, setSteps] = useState<StepData[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [selectedStep, setSelectedStep] = useState<StepData | null>(null);
  const [runPhase, setRunPhase] = useState<RunPhase>("idle");
  const [isRecording, setIsRecording] = useState(false);
  const [scenarioHeader, setScenarioHeader] = useState<ScenarioHeader>({
    name: "Unity Editor Flow",
  });
  const [logMessages, setLogMessages] = useState<string[]>([]);
  const [locale, setLocaleState] = useState<string>("en");

  const logRef = useRef<string[]>([]);

  const appendLog = useCallback((msg: string) => {
    logRef.current = [...logRef.current.slice(-4999), msg];
    setLogMessages([...logRef.current]);
  }, []);

  // --- Server event subscriptions ------------------------------------------
  useEffect(() => {
    if (!connected) return;

    const unsubs: Array<() => void> = [];

    unsubs.push(
      subscribe("log", (data: unknown) => {
        const d = data as { message?: string } | undefined;
        if (d?.message) appendLog(d.message);
      }),
    );

    unsubs.push(
      subscribe("steps_changed", (_data: unknown) => {
        // Re-fetch steps from server
        void refreshSteps();
      }),
    );

    unsubs.push(
      subscribe("step_selected", (data: unknown) => {
        const d = data as { index?: number | null } | undefined;
        setSelectedIndex(d?.index ?? null);
      }),
    );

    unsubs.push(
      subscribe("phase_changed", (data: unknown) => {
        const d = data as { phase?: string } | undefined;
        if (d?.phase) setRunPhase(d.phase as RunPhase);
      }),
    );

    unsubs.push(
      subscribe("recording_started", (_data: unknown) => {
        setIsRecording(true);
      }),
    );

    unsubs.push(
      subscribe("recording_stopped", (_data: unknown) => {
        setIsRecording(false);
      }),
    );

    unsubs.push(
      subscribe("header_changed", (data: unknown) => {
        if (data) setScenarioHeader(data as ScenarioHeader);
      }),
    );

    unsubs.push(
      subscribe("run_finished", (data: unknown) => {
        const d = data as { error?: string; return_code?: number } | undefined;
        if (d?.error) {
          appendLog(`Run error: ${d.error}`);
        } else if (d?.return_code !== undefined) {
          appendLog(`Run finished (exit code ${d.return_code})`);
        }
      }),
    );

    // Initial data load
    void loadInitialData();

    return () => {
      for (const u of unsubs) u();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected]);

  // --- Server calls --------------------------------------------------------

  const refreshSteps = useCallback(async () => {
    try {
      const result = (await call("scenario.get_steps")) as StepData[];
      setSteps(result ?? []);
    } catch (err) {
      console.error("[useStudio] refreshSteps:", err);
    }
  }, [call]);

  const loadInitialData = useCallback(async () => {
    try {
      const [stepsResult, headerResult, settingsResult] = await Promise.all([
        call("scenario.get_steps"),
        call("scenario.get_header"),
        call("settings.get"),
      ]);
      setSteps((stepsResult as StepData[]) ?? []);
      if (headerResult) setScenarioHeader(headerResult as ScenarioHeader);
      const settings = settingsResult as { locale?: string } | undefined;
      if (settings?.locale) setLocaleState(settings.locale);
    } catch (err) {
      console.error("[useStudio] loadInitialData:", err);
    }
  }, [call]);

  const selectStep = useCallback(
    async (index: number) => {
      try {
        const result = (await call("step.select", { index })) as StepData | null;
        setSelectedIndex(index);
        setSelectedStep(result);
      } catch (err) {
        console.error("[useStudio] selectStep:", err);
      }
    },
    [call],
  );

  const applyStep = useCallback(
    async (params: StepData & { index?: number }) => {
      try {
        const result = (await call("step.apply", params)) as StepData;
        setSelectedStep(result);
        await refreshSteps();
      } catch (err) {
        console.error("[useStudio] applyStep:", err);
        appendLog(`Apply step failed: ${err}`);
      }
    },
    [call, refreshSteps, appendLog],
  );

  const addStep = useCallback(
    async (type: string) => {
      const methodMap: Record<string, string> = {
        click: "step.add_click",
        drag: "step.add_drag",
        shortcut: "step.add_shortcut",
        menu: "step.add_menu",
        type: "step.add_type",
        control: "step.add_control",
        group: "step.add_group",
      };
      const method = methodMap[type];
      if (!method) return;
      try {
        await call(method, {});
      } catch (err) {
        appendLog(`Add step failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const deleteStep = useCallback(
    async (index: number) => {
      try {
        await call("step.delete", { index });
      } catch (err) {
        appendLog(`Delete step failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const moveStepUp = useCallback(
    async (index: number) => {
      try {
        await call("step.move_up", { index });
        if (index > 0) setSelectedIndex(index - 1);
      } catch (err) {
        appendLog(`Move step up failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const moveStepDown = useCallback(
    async (index: number) => {
      try {
        await call("step.move_down", { index });
        setSelectedIndex(index + 1);
      } catch (err) {
        appendLog(`Move step down failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const duplicateStep = useCallback(
    async (index: number) => {
      try {
        await call("step.duplicate", { index });
      } catch (err) {
        appendLog(`Duplicate step failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const startRecording = useCallback(async () => {
    try {
      await call("recording.start", {
        window_hint: scenarioHeader.target_window_hint ?? "Unity",
      });
    } catch (err) {
      appendLog(`Start recording failed: ${err}`);
    }
  }, [call, appendLog, scenarioHeader.target_window_hint]);

  const stopRecording = useCallback(async () => {
    try {
      await call("recording.stop", {});
    } catch (err) {
      appendLog(`Stop recording failed: ${err}`);
    }
  }, [call, appendLog]);

  const runRobot = useCallback(async () => {
    try {
      const result = (await call("robot.run", {})) as {
        started?: boolean;
        issues?: unknown[];
      };
      if (!result?.started && result?.issues) {
        appendLog("Robot run blocked by preflight validation issues.");
      }
    } catch (err) {
      appendLog(`Run robot failed: ${err}`);
    }
  }, [call, appendLog]);

  const stopRobot = useCallback(async () => {
    try {
      await call("robot.stop", {});
    } catch (err) {
      appendLog(`Stop robot failed: ${err}`);
    }
  }, [call, appendLog]);

  const exportScenario = useCallback(
    async (outputDir?: string, exportName?: string) => {
      try {
        const params: Record<string, string> = {};
        if (outputDir) params.output_dir = outputDir;
        if (exportName) params.suite_name = exportName;
        const result = (await call("export.run", params)) as {
          robot_path?: string;
          json_path?: string;
        };
        if (result?.robot_path) {
          appendLog(`Exported: ${result.robot_path}`);
        }
      } catch (err) {
        appendLog(`Export failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const saveScenario = useCallback(
    async (path: string) => {
      try {
        await call("scenario.save", { path });
        appendLog(`Saved scenario to ${path}`);
      } catch (err) {
        appendLog(`Save failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const loadScenario = useCallback(
    async (path: string) => {
      try {
        const result = (await call("scenario.load", { path })) as ScenarioHeader;
        if (result) setScenarioHeader(result);
      } catch (err) {
        appendLog(`Load failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const saveScenarioAs = useCallback(async () => {
    try {
      const result = (await call("scenario.save_as", {})) as {
        cancelled?: boolean;
        path?: string | null;
      };
      if (!result?.cancelled && result?.path) {
        appendLog(`Saved scenario to ${result.path}`);
      }
    } catch (err) {
      appendLog(`Save As failed: ${err}`);
    }
  }, [call, appendLog]);

  const loadScenarioFrom = useCallback(async () => {
    try {
      const result = (await call("scenario.load_from", {})) as {
        cancelled?: boolean;
        path?: string | null;
        scenario?: ScenarioHeader | null;
      };
      if (!result?.cancelled && result?.scenario) {
        setScenarioHeader(result.scenario);
        appendLog(`Loaded scenario from ${result.path ?? ""}`);
      }
    } catch (err) {
      appendLog(`Load From failed: ${err}`);
    }
  }, [call, appendLog]);

  const browseDirectory = useCallback(async (): Promise<string | null> => {
    try {
      const result = (await call("dialog.browse_directory", {})) as {
        cancelled?: boolean;
        path?: string | null;
      };
      if (!result?.cancelled && result?.path) {
        return result.path;
      }
      return null;
    } catch (err) {
      appendLog(`Browse directory failed: ${err}`);
      return null;
    }
  }, [call, appendLog]);

  const openDirectory = useCallback(
    async (path: string) => {
      try {
        await call("shell.open_directory", { path });
      } catch (err) {
        appendLog(`Open directory failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const setLocale = useCallback(
    async (loc: string) => {
      try {
        await call("settings.set_locale", { locale: loc });
        setLocaleState(loc);
      } catch (err) {
        appendLog(`Set locale failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const getVariables = useCallback(async (): Promise<VariableEntry[]> => {
    try {
      const header = (await call("scenario.get_header")) as Record<string, unknown>;
      const vars = header?.variables;
      if (Array.isArray(vars)) {
        return vars as VariableEntry[];
      }
      return [];
    } catch (err) {
      appendLog(`Get variables failed: ${err}`);
      return [];
    }
  }, [call, appendLog]);

  const setVariables = useCallback(
    async (variables: VariableEntry[]) => {
      try {
        // Get current full JSON, patch variables, then set
        const current = (await call("editor.get_full_json")) as Record<string, unknown>;
        const updated = { ...current, variables };
        await call("editor.set_full_json", { scenario: updated });
        appendLog("Updated variables.");
      } catch (err) {
        appendLog(`Set variables failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const getProfiles = useCallback(async (): Promise<ProfilesMap> => {
    try {
      const header = (await call("scenario.get_header")) as Record<string, unknown>;
      const profiles = header?.profiles;
      if (profiles && typeof profiles === "object" && !Array.isArray(profiles)) {
        return profiles as ProfilesMap;
      }
      return {};
    } catch (err) {
      appendLog(`Get profiles failed: ${err}`);
      return {};
    }
  }, [call, appendLog]);

  const setProfiles = useCallback(
    async (profiles: ProfilesMap) => {
      try {
        const current = (await call("editor.get_full_json")) as Record<string, unknown>;
        const updated = { ...current, profiles };
        await call("editor.set_full_json", { scenario: updated });
        appendLog("Updated profiles.");
      } catch (err) {
        appendLog(`Set profiles failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const getExecutionOutputs = useCallback(async (): Promise<{
    execution: Record<string, unknown>;
    outputs: Record<string, unknown>;
  }> => {
    try {
      const header = (await call("scenario.get_header")) as Record<string, unknown>;
      const execution = (header?.execution as Record<string, unknown>) ?? {};
      const outputs = (header?.outputs as Record<string, unknown>) ?? {};
      return { execution, outputs };
    } catch (err) {
      appendLog(`Get execution/outputs failed: ${err}`);
      return { execution: {}, outputs: {} };
    }
  }, [call, appendLog]);

  const setExecutionOutputs = useCallback(
    async (execution: Record<string, unknown>, outputs: Record<string, unknown>) => {
      try {
        const current = (await call("editor.get_full_json")) as Record<string, unknown>;
        const updated = { ...current, execution, outputs };
        await call("editor.set_full_json", { scenario: updated });
        appendLog("Updated execution/outputs.");
      } catch (err) {
        appendLog(`Set execution/outputs failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const runPreflight = useCallback(async (): Promise<ValidationReport | null> => {
    try {
      const result = (await call("validation.preflight", {})) as ValidationReport;
      if (result.valid) {
        appendLog("Preflight validation passed.");
      } else {
        appendLog(
          `Preflight validation failed: ${result.issues.length} issue(s).`,
        );
      }
      return result;
    } catch (err) {
      appendLog(`Preflight failed: ${err}`);
      return null;
    }
  }, [call, appendLog]);

  const updateSettings = useCallback(
    async (params: Record<string, unknown>) => {
      try {
        await call("settings.set", params);
      } catch (err) {
        appendLog(`Update settings failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const updateHeader = useCallback(
    async (params: Record<string, unknown>) => {
      try {
        const result = (await call("scenario.update_header", params)) as ScenarioHeader;
        if (result) setScenarioHeader(result);
      } catch (err) {
        appendLog(`Update header failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const getParamsTemplate = useCallback(
    async (action: string): Promise<Record<string, unknown> | null> => {
      try {
        const result = (await call("scenario.get_params_template", { action })) as {
          template: Record<string, unknown> | null;
        };
        return result?.template ?? null;
      } catch (err) {
        appendLog(`Get params template failed: ${err}`);
        return null;
      }
    },
    [call, appendLog],
  );

  const getProfileDiff = useCallback(
    async (baseProfile: string, compareProfile: string): Promise<ProfileDiffEntry[]> => {
      try {
        const result = (await call("profiles.get_diff", {
          base_profile: baseProfile,
          compare_profile: compareProfile,
        })) as { entries: ProfileDiffEntry[] };
        return result?.entries ?? [];
      } catch (err) {
        appendLog(`Get profile diff failed: ${err}`);
        return [];
      }
    },
    [call, appendLog],
  );

  const getFullJson = useCallback(async () => {
    try {
      return (await call("editor.get_full_json")) as Record<string, unknown>;
    } catch (err) {
      appendLog(`Get full JSON failed: ${err}`);
      return null;
    }
  }, [call, appendLog]);

  const setFullJson = useCallback(
    async (scenario: Record<string, unknown>) => {
      try {
        await call("editor.set_full_json", { scenario });
        appendLog("Applied full JSON changes.");
      } catch (err) {
        appendLog(`Set full JSON failed: ${err}`);
      }
    },
    [call, appendLog],
  );

  const getDiagnostics = useCallback(async (): Promise<DiagnosticsInfo | null> => {
    try {
      return (await call("diagnostics.get_info", {})) as DiagnosticsInfo;
    } catch (err) {
      appendLog(`Get diagnostics failed: ${err}`);
      return null;
    }
  }, [call, appendLog]);

  return {
    // Connection
    connected,
    port,

    // State
    steps,
    selectedIndex,
    selectedStep,
    runPhase,
    isRecording,
    scenarioHeader,
    logMessages,
    locale,

    // Actions
    selectStep,
    applyStep,
    addStep,
    deleteStep,
    moveStepUp,
    moveStepDown,
    duplicateStep,
    startRecording,
    stopRecording,
    runRobot,
    stopRobot,
    exportScenario,
    saveScenario,
    loadScenario,
    saveScenarioAs,
    loadScenarioFrom,
    browseDirectory,
    openDirectory,
    setLocale,
    getFullJson,
    setFullJson,
    refreshSteps,

    // Dialog-specific actions
    getVariables,
    setVariables,
    getProfiles,
    setProfiles,
    getExecutionOutputs,
    setExecutionOutputs,
    runPreflight,
    updateSettings,
    updateHeader,
    getParamsTemplate,
    getProfileDiff,
    getDiagnostics,
  };
}
