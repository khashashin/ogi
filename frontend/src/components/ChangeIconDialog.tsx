import { useEffect, useMemo, useState } from "react";
import { Hash, Save, Search, X } from "lucide-react";
import { DynamicIcon, iconNames } from "lucide-react/dynamic";
import type { IconName } from "lucide-react/dynamic";
import { resolveEntityIconName } from "../lib/entityIconRegistry";

interface ChangeIconDialogProps {
  open: boolean;
  currentIcon: string;
  entityLabel: string;
  onClose: () => void;
  onSave: (iconName: string) => Promise<void> | void;
}

export function ChangeIconDialog({
  open,
  currentIcon,
  entityLabel,
  onClose,
  onSave,
}: ChangeIconDialogProps) {
  const [search, setSearch] = useState("");
  const [selectedIcon, setSelectedIcon] = useState<IconName>(
    resolveEntityIconName(currentIcon) as IconName,
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSearch("");
    setSelectedIcon(resolveEntityIconName(currentIcon) as IconName);
    setSaving(false);
  }, [open, currentIcon]);

  const filteredIcons = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return iconNames;
    return iconNames.filter((iconName) => iconName.includes(query));
  }, [search]);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(selectedIcon);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-4xl rounded-xl border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-text">Change Icon</h2>
            <p className="text-xs text-text-muted truncate max-w-[26rem]">{entityLabel}</p>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-3 py-2">
            <Search size={14} className="text-text-muted shrink-0" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Lucide icons..."
              className="w-full bg-transparent text-sm text-text outline-none placeholder:text-text-muted"
            />
          </div>
        </div>

        <div className="grid gap-4 px-4 py-4 md:grid-cols-[220px_1fr]">
          <div className="rounded-xl border border-border bg-bg px-4 py-5">
            <div className="mb-3 text-xs uppercase tracking-[0.18em] text-text-muted">
              Selected
            </div>
            <div className="flex items-center justify-center rounded-xl border border-border bg-surface p-6">
              <DynamicIcon name={selectedIcon} size={40} fallback={() => <Hash size={40} />} />
            </div>
            <div className="mt-3 text-center text-sm text-text">{selectedIcon}</div>
          </div>

          <div className="rounded-xl border border-border bg-bg p-3">
            <div className="mb-3 text-xs uppercase tracking-[0.18em] text-text-muted">
              Gallery
            </div>
            <div className="max-h-[26rem] overflow-y-auto">
              {filteredIcons.length === 0 ? (
                <div className="px-2 py-10 text-center text-sm text-text-muted">
                  No icons match your search.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {filteredIcons.map((iconName) => {
                    const isSelected = iconName === selectedIcon;
                    return (
                      <button
                        key={iconName}
                        type="button"
                        onClick={() => setSelectedIcon(iconName)}
                        className={`rounded-lg border px-2 py-3 text-center transition ${
                          isSelected
                            ? "border-accent bg-accent/10 text-text"
                            : "border-border bg-surface text-text-muted hover:border-accent/60 hover:text-text"
                        }`}
                      >
                        <div className="mb-2 flex justify-center">
                          <DynamicIcon
                            name={iconName}
                            size={20}
                            fallback={() => <Hash size={20} />}
                          />
                        </div>
                        <div className="text-[11px] leading-4 break-words">{iconName}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted hover:text-text"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
          >
            <Save size={14} />
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
