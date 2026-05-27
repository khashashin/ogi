import { useEffect, useMemo, useState } from "react";
import { Link2, X } from "lucide-react";
import { toast } from "sonner";

import { api } from "../api/client";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { getEdgeLabelSuggestions } from "../lib/edgeLabelSuggestions";

export function CreateConnectionDialog() {
  const {
    connectionDraft,
    entities,
    edges,
    addEdge,
    selectEdge,
    cancelConnectionDraft,
  } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [label, setLabel] = useState("");
  const [weight, setWeight] = useState("1");
  const [bidirectional, setBidirectional] = useState(false);
  const [propertyKey, setPropertyKey] = useState("");
  const [propertyValue, setPropertyValue] = useState("");
  const [properties, setProperties] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const source = connectionDraft.sourceId ? entities.get(connectionDraft.sourceId) : null;
  const target = connectionDraft.targetId ? entities.get(connectionDraft.targetId) : null;
  const open = connectionDraft.dialogOpen && !!currentProject && !!source && !!target;

  const suggestions = useMemo(() => {
    if (!source || !target) return [];
    return getEdgeLabelSuggestions(source, target, edges.values(), entities);
  }, [source, target, edges, entities]);

  useEffect(() => {
    if (!open) return;
    setLabel(suggestions[0] ?? "");
    setWeight("1");
    setBidirectional(false);
    setPropertyKey("");
    setPropertyValue("");
    setProperties({});
  }, [open, suggestions]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        cancelConnectionDraft();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, cancelConnectionDraft]);

  if (!open || !currentProject || !source || !target) return null;

  const addProperty = () => {
    const key = propertyKey.trim();
    if (!key) return;
    setProperties((current) => ({ ...current, [key]: propertyValue.trim() }));
    setPropertyKey("");
    setPropertyValue("");
  };

  const removeProperty = (key: string) => {
    setProperties((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = async () => {
    const normalizedLabel = label.trim();
    if (!normalizedLabel) {
      toast.error("Connection label is required");
      return;
    }
    if (source.id === target.id) {
      toast.error("Self-connections are not supported in this version");
      return;
    }

    const duplicate = [...edges.values()].some(
      (edge) =>
        edge.source_id === source.id &&
        edge.target_id === target.id &&
        edge.label.trim().toLowerCase() === normalizedLabel.toLowerCase(),
    );
    if (duplicate) {
      toast.error("That connection already exists");
      return;
    }

    let parsedWeight = Number.parseInt(weight, 10);
    if (!Number.isFinite(parsedWeight) || parsedWeight < 1) {
      parsedWeight = 1;
    }

    setSaving(true);
    try {
      const created = await api.edges.create(currentProject.id, {
        source_id: source.id,
        target_id: target.id,
        label: normalizedLabel,
        weight: parsedWeight,
        bidirectional,
        properties,
      });
      addEdge(currentProject.id, created);
      selectEdge(created.id);
      toast.success("Connection created");
      cancelConnectionDraft();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(`Failed to create connection: ${message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55">
      <div className="w-full max-w-lg rounded-lg border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Link2 size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-text">Create Connection</h2>
          </div>
          <button onClick={cancelConnectionDraft} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Source
              </p>
              <div className="rounded border border-border bg-bg px-3 py-2 text-sm text-text">
                {source.value}
              </div>
            </div>
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Target
              </p>
              <div className="rounded border border-border bg-bg px-3 py-2 text-sm text-text">
                {target.value}
              </div>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-muted">Label</label>
            <input
              type="text"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              className="w-full rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
              placeholder="Enter connection label"
            />
            {suggestions.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {suggestions.map((item) => (
                  <button
                    key={item}
                    onClick={() => setLabel(item)}
                    className="rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:bg-surface-hover hover:text-text"
                  >
                    {item}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Weight</label>
              <input
                type="number"
                min={1}
                value={weight}
                onChange={(event) => setWeight(event.target.value)}
                className="w-24 rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
              />
            </div>
            <label className="mt-5 flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={bidirectional}
                onChange={(event) => setBidirectional(event.target.checked)}
              />
              Bidirectional
            </label>
          </div>

          <div>
            <p className="mb-2 text-xs text-text-muted">Properties</p>
            {Object.keys(properties).length > 0 && (
              <div className="mb-2 space-y-1 rounded border border-border bg-bg p-2">
                {Object.entries(properties).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-text-muted">{key}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-text">{value}</span>
                      <button
                        onClick={() => removeProperty(key)}
                        className="text-text-muted hover:text-danger"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <input
                type="text"
                value={propertyKey}
                onChange={(event) => setPropertyKey(event.target.value)}
                placeholder="Key"
                className="rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
              />
              <input
                type="text"
                value={propertyValue}
                onChange={(event) => setPropertyValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") addProperty();
                }}
                placeholder="Value"
                className="rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
              />
              <button
                onClick={addProperty}
                className="rounded border border-border px-3 py-2 text-sm text-text-muted hover:bg-surface-hover hover:text-text"
              >
                Add
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          <button
            onClick={cancelConnectionDraft}
            className="rounded border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-surface-hover hover:text-text"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="rounded bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
          >
            {saving ? "Creating..." : "Create Connection"}
          </button>
        </div>
      </div>
    </div>
  );
}
