import { useState, useEffect } from "react";
import { X, RefreshCw, ToggleLeft, ToggleRight, Puzzle } from "lucide-react";
import { api } from "../api/client";

interface PluginInfo {
  name: string;
  version: string;
  display_name: string;
  description: string;
  author: string;
  enabled: boolean;
  transform_count: number;
  transform_names: string[];
}

interface PluginManagerProps {
  open: boolean;
  onClose: () => void;
}

export function PluginManager({ open, onClose }: PluginManagerProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) loadPlugins();
  }, [open]);

  const loadPlugins = async () => {
    setLoading(true);
    try {
      const data = await api.plugins.list();
      setPlugins(data);
    } catch {
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (name: string) => {
    try {
      const current = plugins.find((p) => p.name === name);
      if (!current) return;
      const updated = current.enabled
        ? await api.plugins.disable(name)
        : await api.plugins.enable(name);
      setPlugins((prev) =>
        prev.map((p) => (p.name === name ? updated : p))
      );
    } catch { /* ignore */ }
  };

  const handleReload = async (name: string) => {
    try {
      const updated = await api.plugins.reload(name);
      setPlugins((prev) =>
        prev.map((p) => (p.name === name ? updated : p))
      );
    } catch { /* ignore */ }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg bg-surface border border-border rounded-lg shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Puzzle size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-text">Plugins</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 max-h-96 overflow-y-auto">
          {loading && (
            <p className="text-xs text-text-muted">Loading...</p>
          )}
          {!loading && plugins.length === 0 && (
            <p className="text-xs text-text-muted">
              No plugins installed. Drop a plugin folder in the <code>plugins/</code> directory and restart.
            </p>
          )}
          <div className="space-y-3">
            {plugins.map((plugin) => (
              <div
                key={plugin.name}
                className="p-3 rounded bg-bg border border-border"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text">
                        {plugin.display_name || plugin.name}
                      </span>
                      {plugin.version && (
                        <span className="text-[10px] text-text-muted bg-surface px-1.5 py-0.5 rounded">
                          v{plugin.version}
                        </span>
                      )}
                    </div>
                    {plugin.description && (
                      <p className="text-xs text-text-muted mt-0.5">{plugin.description}</p>
                    )}
                    {plugin.author && (
                      <p className="text-[10px] text-text-muted mt-0.5">by {plugin.author}</p>
                    )}
                    <p className="text-[10px] text-text-muted mt-1">
                      {plugin.transform_count} transform{plugin.transform_count !== 1 ? "s" : ""}
                      {plugin.transform_names.length > 0 && (
                        <span>: {plugin.transform_names.join(", ")}</span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleReload(plugin.name)}
                      className="p-1 text-text-muted hover:text-text"
                      title="Reload plugin"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button
                      onClick={() => handleToggle(plugin.name)}
                      className="p-1 text-text-muted hover:text-text"
                      title={plugin.enabled ? "Disable" : "Enable"}
                    >
                      {plugin.enabled ? (
                        <ToggleRight size={18} className="text-green-400" />
                      ) : (
                        <ToggleLeft size={18} className="text-text-muted" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
