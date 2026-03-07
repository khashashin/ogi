import { useEffect } from "react";
import { X, Store, AlertTriangle } from "lucide-react";
import { InstalledTab } from "./InstalledTab";
import { BrowseTab } from "./BrowseTab";
import { useRegistryStore } from "../../stores/registryStore";

interface TransformHubProps {
  open: boolean;
  onClose: () => void;
}

export function TransformHub({ open, onClose }: TransformHubProps) {
  const {
    activeTab,
    setActiveTab,
    installedPlugins,
    canManage,
    error,
    clearError,
    fetchIndex,
    fetchInstalledPlugins,
    searchTransforms,
  } = useRegistryStore();

  useEffect(() => {
    if (open) {
      fetchIndex();
      fetchInstalledPlugins();
      searchTransforms("");
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;

  const tabs: { id: "enabled" | "catalog"; label: string; count?: number }[] = [
    { id: "enabled", label: "Enabled", count: installedPlugins.filter((p) => p.enabled).length },
    { id: "catalog", label: "Catalog" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl max-h-[80vh] bg-surface border border-border rounded-lg shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2">
            <Store size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-text">Transform Hub</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border flex-shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 ${
                activeTab === tab.id
                  ? "border-accent text-accent"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded-full bg-accent/10 text-accent">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-4 py-2 bg-red-400/10 border-b border-red-400/20 flex items-center justify-between">
            <p className="text-xs text-red-400">{error}</p>
            <button
              onClick={clearError}
              className="text-xs text-red-400 hover:text-red-300 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          <div className="mb-3 rounded border border-amber-400/20 bg-amber-400/5 px-3 py-2">
            <p className="flex items-center gap-1.5 text-xs text-amber-300 font-medium">
              <AlertTriangle size={12} />
              Plugins that use API keys should be treated as privileged code.
            </p>
            <p className="mt-1 text-[11px] text-text-muted">
              Review trust tier, permissions, and required services before install or use.
            </p>
          </div>
          {activeTab === "enabled" && (
            <InstalledTab
              plugins={installedPlugins}
              canManage={canManage}
              onRefresh={fetchInstalledPlugins}
            />
          )}
          {activeTab === "catalog" && <BrowseTab />}
        </div>
      </div>
    </div>
  );
}
