import { Download, Trash2, Loader2, Check } from "lucide-react";

interface InstallButtonProps {
  installed: boolean;
  bundled: boolean;
  installing: boolean;
  removing: boolean;
  onInstall: () => void;
  onRemove: () => void;
}

export function InstallButton({
  installed,
  bundled,
  installing,
  removing,
  onInstall,
  onRemove,
}: InstallButtonProps) {
  if (bundled) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-text-muted bg-surface rounded">
        <Check size={10} />
        Bundled
      </span>
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

  if (removing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-red-400 bg-red-400/10 rounded">
        <Loader2 size={10} className="animate-spin" />
        Removing...
      </span>
    );
  }

  if (installed) {
    return (
      <div className="flex items-center gap-1">
        <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-green-400 bg-green-400/10 rounded">
          <Check size={10} />
          Installed
        </span>
        <button
          onClick={onRemove}
          className="p-1 text-text-muted hover:text-red-400 rounded hover:bg-red-400/10"
          title="Uninstall"
        >
          <Trash2 size={12} />
        </button>
      </div>
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
