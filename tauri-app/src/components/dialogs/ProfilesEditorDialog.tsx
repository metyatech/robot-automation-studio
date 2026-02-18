import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Trash2, PlusSquare, MinusSquare } from "lucide-react";
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
import { ScrollArea } from "@/components/ui/scroll-area";

interface ProfileData {
  description: string;
  variables: Record<string, unknown>;
  [key: string]: unknown;
}

interface ProfilesMap {
  [name: string]: ProfileData;
}

interface OverrideRow {
  key: string;
  value: string;
}

interface ProfilesEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialProfiles: ProfilesMap;
  onSave: (profiles: ProfilesMap) => void;
}

function parseJsonOrText(raw: string): unknown {
  const text = raw.trim();
  if (text === "") return "";
  try {
    return JSON.parse(text);
  } catch {
    return raw;
  }
}

export function ProfilesEditorDialog({
  open,
  onOpenChange,
  initialProfiles,
  onSave,
}: ProfilesEditorDialogProps) {
  const { t } = useTranslation();

  const [profiles, setProfiles] = useState<ProfilesMap>(() => {
    const copy: ProfilesMap = {};
    for (const [k, v] of Object.entries(initialProfiles)) {
      copy[k] = { ...v, variables: { ...v.variables } };
    }
    return copy;
  });
  const [profileNames, setProfileNames] = useState<string[]>(() =>
    Object.keys(initialProfiles).sort()
  );
  const [selectedIndex, setSelectedIndex] = useState<number | null>(
    profileNames.length > 0 ? 0 : null
  );
  const [nameText, setNameText] = useState(profileNames[0] ?? "");
  const [descText, setDescText] = useState(
    profileNames.length > 0
      ? String(initialProfiles[profileNames[0]]?.description ?? "")
      : ""
  );
  const [overrideRows, setOverrideRows] = useState<OverrideRow[]>(() => {
    if (profileNames.length === 0) return [{ key: "", value: "" }];
    const vars = initialProfiles[profileNames[0]]?.variables ?? {};
    return Object.entries(vars)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => ({
        key: k,
        value: typeof v === "string" ? v : JSON.stringify(v),
      }));
  });
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(
    (index: number, names: string[], profs: ProfilesMap) => {
      if (index < 0 || index >= names.length) return;
      const name = names[index];
      const p = profs[name] ?? { description: "", variables: {} };
      setSelectedIndex(index);
      setNameText(name);
      setDescText(String(p.description ?? ""));
      const vars = p.variables ?? {};
      setOverrideRows(
        Object.entries(vars)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([k, v]) => ({
            key: k,
            value: typeof v === "string" ? v : JSON.stringify(v),
          }))
      );
      setError(null);
    },
    []
  );

  const applyCurrent = useCallback(
    (
      profs: ProfilesMap,
      names: string[],
      index: number
    ): { profiles: ProfilesMap; names: string[] } | null => {
      if (index < 0 || index >= names.length) return { profiles: profs, names };
      const currentName = names[index];
      const normalizedName = nameText.trim();
      if (normalizedName === "") {
        setError(t("app.error.profile_name_required"));
        return null;
      }
      const variables: Record<string, unknown> = {};
      for (const row of overrideRows) {
        const key = row.key.trim();
        if (key === "" && row.value.trim() === "") continue;
        if (key === "") {
          setError(t("app.error.profile_name_required"));
          return null;
        }
        variables[key] = parseJsonOrText(row.value);
      }
      const prev = profs[currentName] ?? {};
      const extras: Record<string, unknown> = {};
      for (const k of Object.keys(prev)) {
        if (!["description", "variables"].includes(k)) {
          extras[k] = prev[k];
        }
      }
      const newProfs = { ...profs };
      delete newProfs[currentName];
      newProfs[normalizedName] = {
        ...extras,
        description: descText.trim(),
        variables,
      } as ProfileData;
      const newNames = Object.keys(newProfs).sort();
      return { profiles: newProfs, names: newNames };
    },
    [nameText, descText, overrideRows, t]
  );

  const handleSelect = (index: number) => {
    if (selectedIndex !== null) {
      const result = applyCurrent(profiles, profileNames, selectedIndex);
      if (result === null) return;
      setProfiles(result.profiles);
      setProfileNames(result.names);
      const newIdx = result.names.indexOf(nameText.trim());
      loadProfile(newIdx >= 0 ? newIdx : index, result.names, result.profiles);
    } else {
      loadProfile(index, profileNames, profiles);
    }
  };

  const handleAdd = () => {
    let profs = profiles;
    let names = profileNames;
    if (selectedIndex !== null) {
      const result = applyCurrent(profs, names, selectedIndex);
      if (result === null) return;
      profs = result.profiles;
      names = result.names;
      setProfiles(profs);
      setProfileNames(names);
    }
    const nextIndex = names.length + 1;
    const newName = `profile-${nextIndex}`;
    const newProfs = { ...profs, [newName]: { description: "", variables: {} } };
    const newNames = Object.keys(newProfs).sort();
    setProfiles(newProfs);
    setProfileNames(newNames);
    const idx = newNames.indexOf(newName);
    loadProfile(idx, newNames, newProfs);
  };

  const handleDelete = () => {
    if (selectedIndex === null) return;
    const name = profileNames[selectedIndex];
    const newProfs = { ...profiles };
    delete newProfs[name];
    const newNames = Object.keys(newProfs).sort();
    setProfiles(newProfs);
    setProfileNames(newNames);
    setError(null);
    if (newNames.length === 0) {
      setSelectedIndex(null);
      setNameText("");
      setDescText("");
      setOverrideRows([{ key: "", value: "" }]);
    } else {
      const nextIdx = Math.min(selectedIndex, newNames.length - 1);
      loadProfile(nextIdx, newNames, newProfs);
    }
  };

  const handleApplyCurrent = () => {
    if (selectedIndex === null) return;
    const result = applyCurrent(profiles, profileNames, selectedIndex);
    if (result === null) return;
    setProfiles(result.profiles);
    setProfileNames(result.names);
    setError(null);
  };

  const handleAddOverrideRow = () => {
    setOverrideRows((prev) => [...prev, { key: "", value: "" }]);
  };

  const handleRemoveOverrideRow = (index: number) => {
    setOverrideRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSave = () => {
    let profs = profiles;
    let names = profileNames;
    if (selectedIndex !== null) {
      const result = applyCurrent(profs, names, selectedIndex);
      if (result === null) return;
      profs = result.profiles;
      names = result.names;
    }
    // Build final map in sorted key order
    const final: ProfilesMap = {};
    for (const n of names) {
      final[n] = profs[n];
    }
    onSave(final);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-4 pt-4 pb-2 shrink-0">
          <DialogTitle>{t("app.dialog.profiles.title")}</DialogTitle>
        </DialogHeader>

        {error && (
          <div className="mx-4 mb-1 rounded bg-destructive/20 px-3 py-2 text-xs text-destructive shrink-0">
            {error}
          </div>
        )}

        <div className="flex flex-1 min-h-0 gap-0">
          {/* Left: profile list */}
          <div className="w-56 shrink-0 border-r flex flex-col">
            <ScrollArea className="flex-1">
              <div className="p-1 space-y-0.5">
                {profileNames.map((name, i) => (
                  <button
                    key={i}
                    onClick={() => handleSelect(i)}
                    className={`w-full text-left rounded px-2 py-1.5 text-xs transition-colors ${
                      selectedIndex === i
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="font-medium truncate">{name}</div>
                  </button>
                ))}
                {profileNames.length === 0 && (
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
              <Label className="text-xs">{t("app.field.profile_name.label")}</Label>
              <Input
                value={nameText}
                onChange={(e) => setNameText(e.target.value)}
                className="h-8 text-xs"
                disabled={selectedIndex === null}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("app.field.profile_description.label")}</Label>
              <Input
                value={descText}
                onChange={(e) => setDescText(e.target.value)}
                className="h-8 text-xs"
                disabled={selectedIndex === null}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs">{t("app.field.profile_overrides.label")}</Label>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 text-xs px-2"
                    onClick={handleAddOverrideRow}
                    disabled={selectedIndex === null}
                  >
                    <PlusSquare className="mr-1 h-3 w-3" />
                    {t("app.button.add_override")}
                  </Button>
                </div>
              </div>

              <div className="border rounded">
                <div className="grid grid-cols-2 gap-0 border-b bg-muted/50 px-2 py-1 text-xs font-medium text-muted-foreground">
                  <span>{t("app.field.profile_override_key.label")}</span>
                  <span>{t("app.field.profile_override_value.label")}</span>
                </div>
                <ScrollArea className="max-h-48">
                  <div className="divide-y">
                    {overrideRows.map((row, i) => (
                      <div key={i} className="grid grid-cols-2 gap-0 items-center">
                        <Input
                          value={row.key}
                          onChange={(e) => {
                            const updated = [...overrideRows];
                            updated[i] = { ...row, key: e.target.value };
                            setOverrideRows(updated);
                          }}
                          className="h-7 text-xs rounded-none border-0 border-r"
                          disabled={selectedIndex === null}
                        />
                        <div className="flex items-center">
                          <Input
                            value={row.value}
                            onChange={(e) => {
                              const updated = [...overrideRows];
                              updated[i] = { ...row, value: e.target.value };
                              setOverrideRows(updated);
                            }}
                            className="h-7 text-xs rounded-none border-0 flex-1"
                            disabled={selectedIndex === null}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 rounded-none shrink-0"
                            onClick={() => handleRemoveOverrideRow(i)}
                            disabled={selectedIndex === null}
                          >
                            <MinusSquare className="h-3 w-3 text-muted-foreground" />
                          </Button>
                        </div>
                      </div>
                    ))}
                    {overrideRows.length === 0 && (
                      <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                        {t("app.validation.issue.none")}
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
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
