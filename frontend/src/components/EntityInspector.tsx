import { useState, useEffect } from "react";
import { Trash2, Play, Loader2, Plus, X, Copy, Link2, Save } from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { ENTITY_TYPE_META } from "../types/entity";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { useIsViewer } from "../hooks/useIsViewer";

export function EntityInspector() {
  const {
    selectedNodeId,
    selectedEdgeId,
    entities,
    edges,
    removeEntity,
    removeEdge,
    updateEdge,
    selectNode,
    selectEdge,
  } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [runningTransform, setRunningTransform] = useState<string | null>(null);

  // Entity editable state
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesValue, setNotesValue] = useState("");
  const [newTag, setNewTag] = useState("");
  const [newPropKey, setNewPropKey] = useState("");
  const [newPropVal, setNewPropVal] = useState("");
  const [showAddProp, setShowAddProp] = useState(false);

  // Edge editable state
  const [edgeLabel, setEdgeLabel] = useState("");
  const [edgeWeight, setEdgeWeight] = useState("1");
  const [edgePropKey, setEdgePropKey] = useState("");
  const [edgePropVal, setEdgePropVal] = useState("");
  const [edgePropsDraft, setEdgePropsDraft] = useState<Record<string, string | number | boolean | null>>({});
  const [savingEdge, setSavingEdge] = useState(false);

  const isViewer = useIsViewer();

  const entity = selectedNodeId ? entities.get(selectedNodeId) : null;
  const edge = selectedEdgeId ? edges.get(selectedEdgeId) : null;
  const meta = entity ? ENTITY_TYPE_META[entity.type] : null;

  const connectedEdges = selectedNodeId
    ? Array.from(edges.values()).filter(
        (e) => e.source_id === selectedNodeId || e.target_id === selectedNodeId
      )
    : [];

  useEffect(() => {
    if (!entity) {
      setTransforms([]);
      return;
    }
    api.transforms.forEntity(entity.id).then(setTransforms).catch(() => setTransforms([]));
    setEditingNotes(false);
    setNotesValue(entity.notes);
  }, [entity]);

  useEffect(() => {
    if (!edge) return;
    setEdgeLabel(edge.label);
    setEdgeWeight(String(edge.weight ?? 1));
    setEdgePropsDraft(edge.properties ?? {});
    setEdgePropKey("");
    setEdgePropVal("");
  }, [edge]);

  useEffect(() => {
    const handler = (event: Event) => {
      const custom = event as CustomEvent<{ entityId?: string }>;
      const targetEntityId = custom.detail?.entityId;
      if (!targetEntityId) return;
      if (selectedNodeId !== targetEntityId) {
        selectNode(targetEntityId);
      }
      setShowAddProp(true);
    };
    window.addEventListener("ogi-edit-properties", handler as EventListener);
    return () => window.removeEventListener("ogi-edit-properties", handler as EventListener);
  }, [selectedNodeId, selectNode]);

  const updateEntity = async (data: Record<string, unknown>) => {
    if (!currentProject || !entity) return;
    try {
      const updated = await api.entities.update(currentProject.id, entity.id, data);
      const { entities: entityMap } = useGraphStore.getState();
      entityMap.set(updated.id, updated);
      useGraphStore.setState({ entities: new Map(entityMap) });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Update failed: ${msg}`);
    }
  };

  const handleAddEntityProperty = () => {
    if (!entity) return;
    const key = newPropKey.trim();
    const val = newPropVal.trim();
    if (!key) return;
    updateEntity({ properties: { ...entity.properties, [key]: val } });
    setNewPropKey("");
    setNewPropVal("");
    setShowAddProp(false);
  };

  const handleDeleteEntity = async () => {
    if (!currentProject || !entity) return;
    if (!window.confirm("Are you sure you want to delete this entity?")) return;
    await removeEntity(currentProject.id, entity.id);
  };

  const handleRunTransform = async (transformName: string) => {
    if (!currentProject || !entity) return;
    setRunningTransform(transformName);
    try {
      const run = await api.transforms.run(transformName, entity.id, currentProject.id);
      if (run.result) {
        const { addEntity, addEdge } = useGraphStore.getState();
        for (const newEntity of run.result.entities) {
          addEntity(currentProject.id, newEntity);
        }
        for (const newEdge of run.result.edges) {
          addEdge(currentProject.id, newEdge);
        }
        toast.success(`${transformName}: found ${run.result.entities.length} entities`);
      }
      if (run.error) {
        toast.error(`${transformName}: ${run.error}`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Transform failed: ${msg}`);
    } finally {
      setRunningTransform(null);
    }
  };

  const handleDeleteEdge = async () => {
    if (!currentProject || !edge) return;
    if (!window.confirm("Are you sure you want to delete this edge?")) return;
    await removeEdge(currentProject.id, edge.id);
    selectEdge(null);
  };

  const handleSaveEdge = async () => {
    if (!currentProject || !edge) return;
    setSavingEdge(true);
    try {
      const parsedWeight = Number(edgeWeight);
      await updateEdge(currentProject.id, edge.id, {
        label: edgeLabel.trim(),
        weight: Number.isFinite(parsedWeight) ? parsedWeight : edge.weight,
        properties: edgePropsDraft,
      });
      toast.success("Edge updated");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Failed to update edge: ${msg}`);
    } finally {
      setSavingEdge(false);
    }
  };

  const addEdgeProperty = () => {
    const key = edgePropKey.trim();
    const val = edgePropVal.trim();
    if (!key) return;
    setEdgePropsDraft((prev) => ({ ...prev, [key]: val }));
    setEdgePropKey("");
    setEdgePropVal("");
  };

  const removeEdgeProperty = (key: string) => {
    setEdgePropsDraft((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  if (edge) {
    const source = entities.get(edge.source_id);
    const target = entities.get(edge.target_id);
    return (
      <div className="flex flex-col h-full overflow-y-auto">
        <div className="p-3 border-b border-border">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Link2 size={12} className="text-accent" />
              <span className="text-xs text-text-muted">Edge</span>
            </div>
            {!isViewer && (
              <button
                onClick={handleDeleteEdge}
                className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-danger"
                title="Delete edge"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
          <p className="text-xs text-text-muted">
            <span className="text-text">{source?.value ?? edge.source_id.slice(0, 8)}</span>
            {" -> "}
            <span className="text-text">{target?.value ?? edge.target_id.slice(0, 8)}</span>
          </p>
          <p className="text-[10px] text-text-muted mt-1">
            Source transform: {edge.source_transform || "manual"}
          </p>
        </div>

        <div className="p-3 border-b border-border space-y-2">
          <h3 className="text-xs font-semibold text-text-muted">Label</h3>
          <input
            type="text"
            value={edgeLabel}
            disabled={isViewer}
            onChange={(e) => setEdgeLabel(e.target.value)}
            className="w-full px-2 py-1 text-xs bg-bg border border-border rounded text-text focus:outline-none focus:border-accent disabled:opacity-70"
          />
        </div>

        <div className="p-3 border-b border-border space-y-2">
          <h3 className="text-xs font-semibold text-text-muted">Weight</h3>
          <input
            type="number"
            min={1}
            value={edgeWeight}
            disabled={isViewer}
            onChange={(e) => setEdgeWeight(e.target.value)}
            className="w-full px-2 py-1 text-xs bg-bg border border-border rounded text-text focus:outline-none focus:border-accent disabled:opacity-70"
          />
        </div>

        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">Properties</h3>
          {Object.keys(edgePropsDraft).length > 0 ? (
            <div className="space-y-1 mb-2">
              {Object.entries(edgePropsDraft).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between text-xs group">
                  <span className="text-text-muted">{key}</span>
                  <div className="flex items-center gap-1">
                    <span className="text-text">{String(val)}</span>
                    {!isViewer && (
                      <button
                        onClick={() => removeEdgeProperty(key)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-text-muted hover:text-danger"
                      >
                        <X size={10} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-text-muted mb-2">No properties</p>
          )}
          {!isViewer && (
            <div className="flex gap-1">
              <input
                type="text"
                placeholder="Key"
                value={edgePropKey}
                onChange={(e) => setEdgePropKey(e.target.value)}
                className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
              />
              <input
                type="text"
                placeholder="Value"
                value={edgePropVal}
                onChange={(e) => setEdgePropVal(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addEdgeProperty()}
                className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
              />
              <button
                onClick={addEdgeProperty}
                className="px-1.5 py-1 text-[10px] bg-accent text-white rounded hover:bg-accent-hover"
              >
                Add
              </button>
            </div>
          )}
        </div>

        {!isViewer && (
          <div className="p-3 mt-auto border-t border-border">
            <button
              onClick={handleSaveEdge}
              disabled={savingEdge}
              className="w-full flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
            >
              {savingEdge ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
              Save Edge
            </button>
          </div>
        )}
      </div>
    );
  }

  if (!entity) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <p className="text-sm text-text-muted">Select an entity or edge to inspect</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: meta?.color }} />
            <span className="text-xs text-text-muted">{entity.type}</span>
          </div>
          {!isViewer && (
            <button
              onClick={handleDeleteEntity}
              className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-danger"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
        <div className="flex items-center gap-1 group">
          <p className="text-sm font-medium text-text break-all flex-1">{entity.value}</p>
          <button
            onClick={() => {
              navigator.clipboard.writeText(entity.value);
              toast.success("Copied to clipboard");
            }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text shrink-0"
            title="Copy value"
          >
            <Copy size={12} />
          </button>
        </div>
      </div>

      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-text-muted">Properties</h3>
          {!isViewer && (
            <button
              onClick={() => setShowAddProp(!showAddProp)}
              className="p-0.5 rounded hover:bg-surface-hover text-text-muted hover:text-text"
            >
              <Plus size={12} />
            </button>
          )}
        </div>
        {Object.keys(entity.properties).length > 0 && (
          <div className="space-y-1 mb-2">
            {Object.entries(entity.properties).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between text-xs group">
                <span className="text-text-muted">{key}</span>
                <div className="flex items-center gap-1">
                  <span className="text-text">{String(val)}</span>
                  {!isViewer && (
                    <button
                      onClick={() => {
                        const newProps = { ...entity.properties };
                        delete newProps[key];
                        updateEntity({ properties: newProps });
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-text-muted hover:text-danger"
                    >
                      <X size={10} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {!isViewer && showAddProp && (
          <div className="flex gap-1 mt-1">
            <input
              type="text"
              placeholder="Key"
              value={newPropKey}
              onChange={(e) => setNewPropKey(e.target.value)}
              className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            <input
              type="text"
              placeholder="Value"
              value={newPropVal}
              onChange={(e) => setNewPropVal(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddEntityProperty()}
              className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            <button
              onClick={handleAddEntityProperty}
              className="px-1.5 py-1 text-[10px] bg-accent text-white rounded hover:bg-accent-hover"
            >
              Add
            </button>
          </div>
        )}
        {!isViewer && Object.keys(entity.properties).length === 0 && !showAddProp && (
          <button
            onClick={() => setShowAddProp(true)}
            className="text-[10px] text-text-muted hover:text-accent cursor-pointer"
          >
            + Add a property
          </button>
        )}
      </div>

      <div className="p-3 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted mb-2">Tags</h3>
        <div className="flex flex-wrap gap-1 mb-2">
          {entity.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] bg-surface-hover rounded text-text-muted group"
            >
              {tag}
              {!isViewer && (
                <button
                  onClick={() => updateEntity({ tags: entity.tags.filter((t) => t !== tag) })}
                  className="opacity-0 group-hover:opacity-100 hover:text-danger"
                >
                  <X size={8} />
                </button>
              )}
            </span>
          ))}
        </div>
        {!isViewer && (
          <div className="flex gap-1">
            <input
              type="text"
              placeholder="Add tag..."
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                const tag = newTag.trim();
                if (!tag || entity.tags.includes(tag)) {
                  setNewTag("");
                  return;
                }
                updateEntity({ tags: [...entity.tags, tag] });
                setNewTag("");
              }}
              className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
          </div>
        )}
      </div>

      <div className="p-3 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted mb-2">Notes</h3>
        {isViewer ? (
          <p className="text-xs text-text-muted min-h-[1.5em] rounded px-1 py-0.5">
            {entity.notes || "No notes"}
          </p>
        ) : editingNotes ? (
          <textarea
            value={notesValue}
            onChange={(e) => setNotesValue(e.target.value)}
            onBlur={() => {
              setEditingNotes(false);
              if (notesValue !== entity.notes) updateEntity({ notes: notesValue });
            }}
            autoFocus
            rows={5}
            className="w-full px-2 py-1 text-xs bg-bg border border-border rounded text-text focus:outline-none focus:border-accent resize-y min-h-[60px]"
          />
        ) : (
          <p
            onClick={() => {
              setNotesValue(entity.notes);
              setEditingNotes(true);
            }}
            className="text-xs text-text-muted cursor-text min-h-[1.5em] hover:bg-surface-hover rounded px-1 py-0.5"
          >
            {entity.notes || "Click to add notes..."}
          </p>
        )}
      </div>

      {connectedEdges.length > 0 && (
        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">
            Connections ({connectedEdges.length})
          </h3>
          <div className="space-y-1">
            {connectedEdges.map((item) => {
              const otherId = item.source_id === entity.id ? item.target_id : item.source_id;
              const other = entities.get(otherId);
              return (
                <button
                  key={item.id}
                  onClick={() => selectEdge(item.id)}
                  className="w-full text-left text-xs text-text-muted hover:text-text"
                >
                  <span className="text-accent">{item.label || "linked"}</span>
                  {" -> "}
                  <span className="text-text">{other?.value ?? otherId}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!isViewer && transforms.length > 0 && (
        <div className="p-3">
          <h3 className="text-xs font-semibold text-text-muted mb-2">Actions</h3>
          <div className="space-y-1">
            {transforms.map((t) => (
              <button
                key={t.name}
                onClick={() => handleRunTransform(t.name)}
                disabled={runningTransform !== null}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-text hover:bg-surface-hover disabled:opacity-50"
              >
                {runningTransform === t.name ? (
                  <Loader2 size={12} className="animate-spin text-accent shrink-0" />
                ) : (
                  <Play size={12} className="text-accent shrink-0" />
                )}
                <div className="text-left">
                  <p>{t.display_name}</p>
                  <p className="text-[10px] text-text-muted">{t.description}</p>
                  {t.api_key_services.length > 0 && (
                    <p className="text-[10px] text-warning">
                      Requires API key: {t.api_key_services.join(", ")}
                    </p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="p-3 mt-auto border-t border-border">
        <div className="space-y-1 text-[10px] text-text-muted">
          <p>Origin: {entity.origin_source}</p>
          <p>{formatEntitySourceLabel(entity.source)}: {entity.source}</p>
          <p>Weight: {entity.weight}</p>
          <div className="flex items-center gap-1 group">
            <span>ID: {entity.id.slice(0, 8)}...</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(entity.id);
                toast.success("ID copied");
              }}
              className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-text"
              title="Copy full ID"
            >
              <Copy size={9} />
            </button>
          </div>
          {entity.created_at && <p>Created: {new Date(entity.created_at).toLocaleString()}</p>}
          {entity.updated_at && <p>Updated: {new Date(entity.updated_at).toLocaleString()}</p>}
        </div>
      </div>
    </div>
  );
}

function formatEntitySourceLabel(source: string): string {
  if (source.startsWith("import")) {
    return "Imported via";
  }
  return "Last updated by";
}
