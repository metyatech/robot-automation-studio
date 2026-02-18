import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";

interface VariableEntry {
  id: string;
  type: string;
  required: boolean;
  default: unknown;
  [key: string]: unknown;
}

interface VariablesEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialVariables: VariableEntry[];
  onSave: (variables: VariableEntry[]) => void;
}

function parseDefaultByType(type: string, text: string): unknown {
  const t = type.trim().toLowerCase();
  const raw = text;
  const stripped = raw.trim();
  if (["string", "str", "path", ""].includes(t)) return raw;
  if (["int", "integer"].includes(t)) {
    if (stripped === "") return "";
    const n = parseInt(stripped, 10);
    if (isNaN(n)) throw new Error(`Invalid int value: ${raw}`);
    return n;
  }
  if (["float", "double", "number"].includes(t)) {
    if (stripped === "") return "";
    const n = parseFloat(stripped);
    if (isNaN(n)) throw new Error(`Invalid float value: ${raw}`);
    return n;
  }
  if (["bool", "boolean"].includes(t)) {
    if (stripped === "") return "";
    if (["true", "1", "yes", "on"].includes(stripped.toLowerCase())) return true;
    if (["false", "0", "no", "off"].includes(stripped.toLowerCase())) return false;
    throw new Error(`Invalid bool value: ${raw}`);
  }
  if (["json", "object", "array", "list", "dict", "map"].includes(t)) {
    if (stripped === "") return "";
    try {
      return JSON.parse(stripped);
    } catch {
      throw new Error(`Invalid json value: ${raw}`);
    }
  }
  return raw;
}

export function VariablesEditorDialog({
  open,
  onOpenChange,
  initialVariables,
  onSave,
}: VariablesEditorDialogProps) {
  const { t } = useTranslation();

  const [variables, setVariables] = useState<VariableEntry[]>(() =>
    initialVariables.map((v) => ({ ...v }))
  );
  const [selectedIndex, setSelectedIndex] = useState<number | null>(
    initialVariables.length > 0 ? 0 : null
  );
  const [idText, setIdText] = useState(
    initialVariables.length > 0 ? String(initialVariables[0].id ?? "") : ""
  );
  const [typeText, setTypeText] = useState(
    initialVariables.length > 0 ? String(initialVariables[0].type ?? "string") : "string"
  );
  const [required, setRequired] = useState(
    initialVariables.length > 0 ? Boolean(initialVariables[0].required) : false
  );
  const [defaultText, setDefaultText] = useState(
    initialVariables.length > 0
      ? initialVariables[0].default == null
        ? ""
        : String(initialVariables[0].default)
      : ""
  );
  const [error, setError] = useState<string | null>(null);

  const loadRow = useCallback(
    (index: number, vars: VariableEntry[]) => {
      if (index < 0 || index >= vars.length) return;
      const v = vars[index];
      setSelectedIndex(index);
      setIdText(String(v.id ?? ""));
      setTypeText(String(v.type ?? "string"));
      setRequired(Boolean(v.required));
      setDefaultText(v.default == null ? "" : String(v.default));
      setError(null);
    },
    []
  );

  const applyCurrent = useCallback(
    (vars: VariableEntry[], index: number): VariableEntry[] | null => {
      if (index < 0 || index >= vars.length) return vars;
      const normalizedId = idText.trim();
      if (normalizedId === "") {
        setError(t("app.error.variable_id_required"));
        return null;
      }
      const normalizedType = typeText.trim();
      if (normalizedType === "") {
        setError(t("app.error.variable_type_required"));
        return null;
      }
      let defaultVal: unknown;
      try {
        defaultVal = parseDefaultByType(normalizedType, defaultText);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return null;
      }
      const prev = vars[index];
      const extras: Record<string, unknown> = {};
      for (const key of Object.keys(prev)) {
        if (!["id", "type", "required", "default"].includes(key)) {
          extras[key] = prev[key];
        }
      }
      const updated = [...vars];
      updated[index] = {
        ...extras,
        id: normalizedId,
        type: normalizedType,
        required,
        default: defaultVal,
      } as VariableEntry;
      return updated;
    },
    [idText, typeText, required, defaultText, t]
  );

  const handleSelect = (index: number) => {
    if (selectedIndex !== null) {
      const updated = applyCurrent(variables, selectedIndex);
      if (updated === null) return;
      setVariables(updated);
      loadRow(index, updated);
    } else {
      loadRow(index, variables);
    }
  };

  const handleAdd = () => {
    let vars = variables;
    if (selectedIndex !== null) {
      const updated = applyCurrent(vars, selectedIndex);
      if (updated === null) return;
      vars = updated;
      setVariables(vars);
    }
    const nextIndex = vars.length + 1;
    const newVar: VariableEntry = {
      id: `var_${nextIndex}`,
      type: "string",
      required: false,
      default: "",
    };
    const newVars = [...vars, newVar];
    setVariables(newVars);
    loadRow(newVars.length - 1, newVars);
  };

  const handleDelete = () => {
    if (selectedIndex === null) return;
    const newVars = variables.filter((_, i) => i !== selectedIndex);
    setVariables(newVars);
    setError(null);
    if (newVars.length === 0) {
      setSelectedIndex(null);
      setIdText("");
      setTypeText("string");
      setRequired(false);
      setDefaultText("");
    } else {
      const nextIndex = Math.min(selectedIndex, newVars.length - 1);
      loadRow(nextIndex, newVars);
    }
  };

  const handleApplyCurrent = () => {
    if (selectedIndex === null) return;
    const updated = applyCurrent(variables, selectedIndex);
    if (updated === null) return;
    setVariables(updated);
    setError(null);
  };

  const handleSave = () => {
    let vars = variables;
    if (selectedIndex !== null) {
      const updated = applyCurrent(vars, selectedIndex);
      if (updated === null) return;
      vars = updated;
    }
    onSave(vars);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl w-full h-[75vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle>{t("app.dialog.variables.title")}</DialogTitle>
        </DialogHeader>

        {error && (
          <div className="mx-4 mb-1 rounded bg-destructive/20 px-3 py-2 text-xs text-destructive shrink-0">
            {error}
          </div>
        )}

        <div className="flex flex-1 min-h-0 gap-0">
          {/* Left: variable list */}
          <div className="w-56 shrink-0 border-r flex flex-col">
            <ScrollArea className="flex-1">
              <div className="p-1 space-y-0.5">
                {variables.map((v, i) => (
                  <button
                    key={i}
                    onClick={() => handleSelect(i)}
                    className={`w-full text-left rounded px-2 py-1.5 text-xs transition-colors ${
                      selectedIndex === i
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="font-medium truncate">{v.id || `var-${i + 1}`}</div>
                    <div className="text-muted-foreground truncate">{v.type || "string"}</div>
                  </button>
                ))}
                {variables.length === 0 && (
                  <div className="px-2 py-4 text-xs text-muted-foreground text-center">
                    {t("app.validation.issue.none")}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Right: form */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.variable_id.label")}</Label>
              <Input
                value={idText}
                onChange={(e) => setIdText(e.target.value)}
                className="h-8 text-xs"
                disabled={selectedIndex === null}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.variable_type.label")}</Label>
              <Input
                value={typeText}
                onChange={(e) => setTypeText(e.target.value)}
                placeholder="string / int / bool / json ..."
                className="h-8 text-xs"
                disabled={selectedIndex === null}
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="var-required"
                checked={required}
                onCheckedChange={(c) => setRequired(c === true)}
                disabled={selectedIndex === null}
              />
              <Label htmlFor="var-required" className="text-xs">
                {t("app.field.variable_required.label")}
              </Label>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.variable_default.label")}</Label>
              <Input
                value={defaultText}
                onChange={(e) => setDefaultText(e.target.value)}
                className="h-8 text-xs"
                disabled={selectedIndex === null}
              />
            </div>
          </div>
        </div>

        <DialogFooter className="px-4 py-3 shrink-0 border-t flex-row justify-between sm:justify-between gap-2">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleAdd}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              {t("app.button.add")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              disabled={selectedIndex === null}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              {t("app.button.delete_word")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleApplyCurrent}
              disabled={selectedIndex === null}
            >
              {t("app.button.apply_current")}
            </Button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              {t("app.button.cancel")}
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
