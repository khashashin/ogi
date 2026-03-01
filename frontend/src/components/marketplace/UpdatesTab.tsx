import { ArrowUpCircle, Loader2 } from "lucide-react";
import { useRegistryStore } from "../../stores/registryStore";

export function UpdatesTab() {
  const { updates, installing, updateTransform } = useRegistryStore();

  if (updates.length === 0) {
    return (
      <p className="text-xs text-text-muted p-4">
        All transforms are up to date.
      </p>
    );
  }

  return (
    <div className="space-y-2 p-1">
      {updates.map((u) => (
        <div
          key={u.slug}
          className="flex items-center justify-between p-3 rounded bg-bg border border-border"
        >
          <div>
            <span className="text-sm font-medium text-text">{u.slug}</span>
            <p className="text-xs text-text-muted mt-0.5">
              {u.installed_version} → {u.latest_version}
            </p>
          </div>
          <button
            onClick={() => updateTransform(u.slug)}
            disabled={installing === u.slug}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs text-accent bg-accent/10 rounded hover:bg-accent/20 disabled:opacity-50"
          >
            {installing === u.slug ? (
              <>
                <Loader2 size={12} className="animate-spin" />
                Updating...
              </>
            ) : (
              <>
                <ArrowUpCircle size={12} />
                Update
              </>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
