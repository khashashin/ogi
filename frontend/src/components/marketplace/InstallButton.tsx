import { Download, Loader2, Check, Lock, ToggleLeft, ToggleRight } from "lucide-react";

interface InstallButtonProps {
  available: boolean;
  enabled: boolean;
  canManage: boolean;
  bundled: boolean;
  installing: boolean;
  toggling: boolean;
  onInstall: () => void;
  onEnable: () => void;
  onDisable: () => void;
}

export function InstallButton({
  available,
  enabled,
  canManage,
  bundled,
  installing,
  toggling,
  onInstall,
  onEnable,
  onDisable,
}: InstallButtonProps) {
  if (bundled) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-text-muted bg-surface rounded">
        <Check size={10} />
        Bundled
      </span>
    );
  }

  if (toggling) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-accent bg-accent/10 rounded">
        <Loader2 size={10} className="animate-spin" />
        Updating...
      </span>
    );
  }

  if (available) {
    if (enabled) {
      return (
        <button
          onClick={onDisable}
          className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-green-400 bg-green-400/10 rounded hover:bg-green-400/20 transition-colors"
          title="Disable for me"
        >
          <ToggleRight size={10} />
          Enabled
        </button>
      );
    }

    return (
      <button
        onClick={onEnable}
        className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-text-muted bg-surface rounded hover:bg-surface-hover transition-colors"
        title="Enable for me"
      >
        <ToggleLeft size={10} />
        Disabled
      </button>
    );
  }

  if (installing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-accent bg-accent/10 rounded">
        <Loader2 size={10} className="animate-spin" />
        Installing...
      </span>
    );
  }

  if (!canManage) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-text-muted bg-surface rounded">
        <Lock size={10} />
        Admin install
      </span>
    );
  }

  return (
    <button
      onClick={onInstall}
      className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-accent bg-accent/10 rounded hover:bg-accent/20 transition-colors"
    >
      <Download size={10} />
      Install
    </button>
  );
}
