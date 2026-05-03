import { AlertTriangle, Key, RefreshCw, ToggleLeft, ToggleRight } from "lucide-react";
import { VerificationBadge } from "./VerificationBadge";
import type { PluginInfo, PluginApiKeyUsageReportItem, VerificationTier } from "../../types/registry";
import { api } from "../../api/client";
import { useState } from "react";
import { toast } from "sonner";
import { hasNetworkAndSecretRisk } from "../../lib/pluginRisk";
import { useRegistryStore } from "../../stores/registryStore";

interface InstalledTabProps {
  plugins: PluginInfo[];
  usageReport: PluginApiKeyUsageReportItem[];
  canManage: boolean;
  onRefresh: () => Promise<void>;
}

export function InstalledTab({ plugins, usageReport, canManage, onRefresh }: InstalledTabProps) {
  const [toggling, setToggling] = useState<string | null>(null);
  const [reloading, setReloading] = useState<string | null>(null);
  const { availableUpdates, updateTransform, updating } = useRegistryStore();

  const handleToggle = async (name: string) => {
    setToggling(name);
    try {
      const current = plugins.find((plugin) => plugin.name === name);
      if (!current) return;
      if (current.enabled) {
        await api.plugins.disable(name);
      } else {
        await api.plugins.enable(name);
      }
      await onRefresh();
    } finally {
      setToggling(null);
    }
  };

  const handleReload = async (name: string) => {
    if (!canManage) return;
    setReloading(name);
    try {
      await api.plugins.reload(name);
      await onRefresh();
      toast.success(`Reloaded plugin: ${name}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Failed to reload plugin: ${msg}`);
    } finally {
      setReloading(null);
    }
  };

  const enabledPlugins = plugins.filter((plugin) => plugin.enabled);
  const usageByPlugin = new Map(usageReport.map((item) => [item.plugin_name, item]));
  const updatesByPlugin = new Map(availableUpdates.map((item) => [item.slug, item]));

  if (enabledPlugins.length === 0) {
    return (
      <p className="text-xs text-text-muted p-4">
        No transforms enabled. Use the Catalog tab to enable installed plugins.
      </p>
    );
  }

  return (
    <div className="space-y-2 p-1">
      {enabledPlugins.map((plugin) => {
        const usage = usageByPlugin.get(plugin.name);
        return (
        <div key={plugin.name} className="p-3 rounded bg-bg border border-border">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-text">
                  {plugin.display_name || plugin.name}
                </span>
                {plugin.version && (
                  <span className="text-[10px] text-text-muted bg-surface px-1.5 py-0.5 rounded">
                    v{plugin.version}
                  </span>
                )}
                <VerificationBadge tier={(plugin.verification_tier || "community") as VerificationTier} />
                {plugin.source && plugin.source !== "local" && (
                  <span className="text-[10px] text-text-muted bg-surface px-1.5 py-0.5 rounded">
                    {plugin.source}
                  </span>
                )}
              </div>
              {plugin.description && (
                <p className="text-xs text-text-muted mt-0.5">{plugin.description}</p>
              )}
              {updatesByPlugin.has(plugin.name) && (
                <p className="mt-1 text-[10px] text-accent">
                  Update available: v{updatesByPlugin.get(plugin.name)?.latest_version}
                </p>
              )}
              <div className="flex items-center gap-3 mt-1 text-[10px] text-text-muted">
                {plugin.author && <span>by {plugin.author}</span>}
                {plugin.category && <span className="capitalize">{plugin.category}</span>}
                <span>
                  {plugin.transform_count} transform{plugin.transform_count !== 1 ? "s" : ""}
                  {plugin.transform_names.length > 0 && (
                    <span>: {plugin.transform_names.join(", ")}</span>
                  )}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1 flex-wrap text-[10px]">
                <span className={plugin.permissions.network ? "text-green-400" : "text-text-muted"}>
                  Network {plugin.permissions.network ? "on" : "off"}
                </span>
                <span className={plugin.permissions.filesystem ? "text-yellow-400" : "text-text-muted"}>
                  Filesystem {plugin.permissions.filesystem ? "on" : "off"}
                </span>
                <span className={plugin.permissions.subprocess ? "text-red-400" : "text-text-muted"}>
                  Subprocess {plugin.permissions.subprocess ? "on" : "off"}
                </span>
              </div>
              {plugin.api_keys_required.length > 0 && (
                <p className="flex items-center gap-1 mt-1 text-[10px] text-yellow-400">
                  <Key size={10} />
                  Requires API key: {plugin.api_keys_required.map((item) => item.service).join(", ")}
                </p>
              )}
              {canManage && usage && usage.usage.length > 0 && (
                <div className="mt-1 text-[10px] text-text-muted">
                  {usage.usage.map((entry) => (
                    <p key={entry.service_name}>
                      {entry.service_name}: last used{" "}
                      {entry.last_used_at ? new Date(entry.last_used_at).toLocaleString() : "never"}
                    </p>
                  ))}
                </div>
              )}
              {hasNetworkAndSecretRisk(
                plugin.api_keys_required.map((item) => item.service),
                plugin.permissions
              ) && (
                <p className="flex items-center gap-1 mt-1 text-[10px] text-amber-300">
                  <AlertTriangle size={10} />
                  Privileged plugin: network access + API keys
                </p>
              )}
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {canManage && (
                <button
                  onClick={async () => {
                    try {
                      await updateTransform(plugin.name);
                      await onRefresh();
                      toast.success(`Updated plugin: ${plugin.name}`);
                    } catch (err) {
                      const msg = err instanceof Error ? err.message : String(err);
                      toast.error(`Failed to update plugin: ${msg}`);
                    }
                  }}
                  disabled={Boolean(updating) || reloading === plugin.name || toggling === plugin.name || !updatesByPlugin.has(plugin.name)}
                  className="p-1 text-text-muted hover:text-text disabled:opacity-50"
                  title={updatesByPlugin.has(plugin.name) ? `Update to v${updatesByPlugin.get(plugin.name)?.latest_version}` : "No update available"}
                >
                  <RefreshCw
                    size={14}
                    className={updating === plugin.name ? "animate-spin text-accent" : updatesByPlugin.has(plugin.name) ? "text-accent" : ""}
                  />
                </button>
              )}
              {canManage && (
                <button
                  onClick={() => handleReload(plugin.name)}
                  disabled={Boolean(updating) || reloading === plugin.name || toggling === plugin.name}
                  className="p-1 text-text-muted hover:text-text disabled:opacity-50"
                  title="Reload plugin"
                >
                  <RefreshCw
                    size={14}
                    className={reloading === plugin.name ? "animate-spin text-accent" : ""}
                  />
                </button>
              )}
              <button
                onClick={() => handleToggle(plugin.name)}
                disabled={toggling === plugin.name || reloading === plugin.name}
                className="p-1 text-text-muted hover:text-text disabled:opacity-50"
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
        );
      })}
    </div>
  );
}
