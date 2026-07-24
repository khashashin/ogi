import { createElement, useEffect, useState } from "react";
import { ArrowRight, Hash, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import type {
  EntityType,
  EntityTypeDocumentation,
  EntityTypeTransformRef,
} from "../types/entity";
import { api } from "../api/client";
import { getEntityIconComponent, isCustomSvgIcon } from "../lib/entityIconRegistry";

interface EntityInfoDialogProps {
  open: boolean;
  entityType: EntityType | null;
  valueHint?: string;
  onClose: () => void;
}

function EntityTypeIcon({ icon, color }: { icon: string; color: string }) {
  if (!icon) return null;
  if (isCustomSvgIcon(icon)) {
    return (
      <img src={`/icons/${icon}.svg`} alt="" width={16} height={16} className="shrink-0 invert" />
    );
  }
  return createElement(getEntityIconComponent(icon) ?? Hash, {
    size: 16,
    className: "shrink-0",
    style: { color },
  });
}

function TransformList({
  transforms,
  emptyLabel,
}: {
  transforms: EntityTypeTransformRef[];
  emptyLabel: string;
}) {
  if (transforms.length === 0) {
    return <p className="text-[10px] text-text-muted">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-1.5">
      {transforms.map((t) => (
        <li key={t.name} className="flex items-start gap-1.5">
          <ArrowRight size={11} className="mt-0.5 shrink-0 text-accent" />
          <div className="min-w-0">
            <p className="text-xs text-text">{t.display_name}</p>
            <p className="text-[10px] text-text-muted">{t.description}</p>
            {t.api_key_services.length > 0 && (
              <p className="text-[10px] text-warning">
                Requires API key: {t.api_key_services.join(", ")}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function EntityInfoDialog({
  open,
  entityType,
  valueHint,
  onClose,
}: EntityInfoDialogProps) {
  const [doc, setDoc] = useState<EntityTypeDocumentation | null>(null);
  const [loading, setLoading] = useState(true);

  // Keyed by entity type at the call site, so each type mounts fresh.
  useEffect(() => {
    if (!open || !entityType) return;
    let cancelled = false;
    api.transforms
      .entityTypeDocumentation(entityType)
      .then((loaded) => {
        if (!cancelled) setDoc(loaded);
      })
      .catch((e) => {
        if (!cancelled) toast.error(`Failed to load entity info: ${String(e)}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, entityType]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !entityType) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-surface border border-border rounded-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`About ${entityType}`}
      >
        <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            {doc && <EntityTypeIcon icon={doc.icon} color={doc.color} />}
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-text">{entityType}</h2>
              {doc?.category && (
                <p className="text-[10px] text-text-muted mt-0.5">{doc.category}</p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text shrink-0" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Loader2 size={12} className="animate-spin" />
              Loading...
            </div>
          )}

          {doc?.description && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-text">What it represents</h3>
              <p className="text-xs text-text-muted">{doc.description}</p>
            </div>
          )}

          {doc?.usage && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-text">When to use it</h3>
              <p className="text-xs text-text-muted">{doc.usage}</p>
            </div>
          )}

          {valueHint && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-text">Expected value</h3>
              <p className="text-xs text-text-muted">{valueHint}</p>
            </div>
          )}

          {doc && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-text">
                Transforms you can run on it ({doc.consumed_by.length})
              </h3>
              <TransformList
                transforms={doc.consumed_by}
                emptyLabel="No transform currently accepts this entity type as input."
              />
            </div>
          )}

          {doc && doc.produced_by.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-text">
                Transforms that discover it ({doc.produced_by.length})
              </h3>
              <TransformList
                transforms={doc.produced_by}
                emptyLabel="Nothing produces this entity type automatically."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
