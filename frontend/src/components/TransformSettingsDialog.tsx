import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";
import type { TransformInfo, TransformSettingsResponse } from "../types/transform";
import { api } from "../api/client";

interface TransformSettingsDialogProps {
  open: boolean;
  transform: TransformInfo | null;
  onClose: () => void;
}

export function TransformSettingsDialog({ open, transform, onClose }: TransformSettingsDialogProps) {
  const [data, setData] = useState<TransformSettingsResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !transform) return;
    api.transforms
      .getSettings(transform.name)
      .then((resp) => {
        setData(resp);
        setValues(resp.user_settings);
      })
      .catch((e) => toast.error(`Failed to load settings: ${String(e)}`));
  }, [open, transform]);

  const schema = useMemo(() => data?.settings_schema ?? [], [data]);
  const visibleSchema = useMemo(
    () => schema.filter((s) => !(s.field_type === "secret" && s.name.endsWith("_api_key"))),
    [schema]
  );
  const managedApiKeyServices = useMemo(
    () =>
      schema
        .filter((s) => s.field_type === "secret" && s.name.endsWith("_api_key"))
        .map((s) => s.name.replace(/_api_key$/, "")),
    [schema]
  );

  const saveUser = async () => {
    if (!transform) return;
    setSaving(true);
    try {
      const resp = await api.transforms.saveUserSettings(transform.name, values);
      setData(resp);
      setValues(resp.user_settings);
      toast.success("User defaults saved");
    } catch (e) {
      toast.error(`Save failed: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const saveGlobal = async () => {
    if (!transform || !data?.can_manage_global) return;
    setSaving(true);
    try {
      const resp = await api.transforms.saveGlobalSettings(transform.name, values);
      setData(resp);
      toast.success("Global defaults saved");
    } catch (e) {
      toast.error(`Global save failed: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  if (!open || !transform) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl bg-surface border border-border rounded-lg shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Settings: {transform.display_name}</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>
        <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
          {visibleSchema.length === 0 && (
            <p className="text-xs text-text-muted">This transform has no configurable settings.</p>
          )}
          {managedApiKeyServices.length > 0 && (
            <div className="rounded border border-border bg-bg px-3 py-2">
              <p className="text-xs text-text-muted">
                API keys for {managedApiKeyServices.join(", ")} are managed in <span className="text-text">API Keys</span>.
              </p>
            </div>
          )}
          {visibleSchema.map((s) => {
            const value = values[s.name] ?? "";
            return (
              <div key={s.name} className="space-y-1">
                <label className="text-xs font-medium text-text">
                  {s.display_name}
                  {s.required ? " *" : ""}
                </label>
                <p className="text-[10px] text-text-muted">{s.description}</p>
                {s.field_type === "select" ? (
                  <select
                    value={value}
                    onChange={(e) => setValues((v) => ({ ...v, [s.name]: e.target.value }))}
                    className="w-full px-2 py-1.5 text-sm bg-bg border border-border rounded text-text"
                  >
                    <option value="">(default)</option>
                    {s.options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={s.field_type === "secret" ? "password" : "text"}
                    value={value}
                    onChange={(e) => setValues((v) => ({ ...v, [s.name]: e.target.value }))}
                    placeholder={s.default || "(default)"}
                    className="w-full px-2 py-1.5 text-sm bg-bg border border-border rounded text-text"
                  />
                )}
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
          <button
            onClick={saveUser}
            disabled={saving}
            className="px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
          >
            Save User Defaults
          </button>
          {data?.can_manage_global && (
            <button
              onClick={saveGlobal}
              disabled={saving}
              className="px-3 py-1.5 text-sm bg-surface-hover text-text rounded hover:bg-surface-hover/80 disabled:opacity-50"
            >
              Save Global Defaults
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
