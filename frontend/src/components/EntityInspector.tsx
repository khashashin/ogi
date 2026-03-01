import { useState, useEffect } from "react";
import { Trash2, Play, Loader2, Plus, X, Copy } from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { ENTITY_TYPE_META } from "../types/entity";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { useIsViewer } from "../hooks/useIsViewer";

export function EntityInspector() {
  const { selectedNodeId, entities, edges, removeEntity } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [runningTransform, setRunningTransform] = useState<string | null>(null);

  // Editable state
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesValue, setNotesValue] = useState("");
  const [newTag, setNewTag] = useState("");
  const [newPropKey, setNewPropKey] = useState("");
  const [newPropVal, setNewPropVal] = useState("");
  const [showAddProp, setShowAddProp] = useState(false);

  const isViewer = useIsViewer();

  const entity = selectedNodeId ? entities.get(selectedNodeId) : null;
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

  if (!entity) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <p className="text-sm text-text-muted">Select an entity to inspect</p>
      </div>
    );
  }

  const handleDelete = async () => {
    if (!currentProject) return;
    await removeEntity(currentProject.id, entity.id);
  };

  const handleRunTransform = async (transformName: string) => {
    if (!currentProject) return;
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

  const updateEntity = async (data: Record<string, unknown>) => {
    if (!currentProject) return;
    try {
      const updated = await api.entities.update(currentProject.id, entity.id, data);
      // Update in the store
      const { addEntity } = useGraphStore.getState();
      addEntity(currentProject.id, updated);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Update failed: ${msg}`);
    }
  };

  const handleSaveNotes = () => {
    setEditingNotes(false);
    if (notesValue !== entity.notes) {
      updateEntity({ notes: notesValue });
    }
  };

  const handleAddTag = () => {
    const tag = newTag.trim();
    if (!tag || entity.tags.includes(tag)) {
      setNewTag("");
      return;
    }
    updateEntity({ tags: [...entity.tags, tag] });
    setNewTag("");
  };

  const handleRemoveTag = (tag: string) => {
    updateEntity({ tags: entity.tags.filter((t) => t !== tag) });
  };

  const handleAddProperty = () => {
    const key = newPropKey.trim();
    const val = newPropVal.trim();
    if (!key) return;
    updateEntity({ properties: { ...entity.properties, [key]: val } });
    setNewPropKey("");
    setNewPropVal("");
    setShowAddProp(false);
  };

  const handleRemoveProperty = (key: string) => {
    const newProps = { ...entity.properties };
    delete newProps[key];
    updateEntity({ properties: newProps });
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: meta?.color }}
            />
            <span className="text-xs text-text-muted">{entity.type}</span>
          </div>
          {!isViewer && (
            <button
              onClick={handleDelete}
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

      {/* Properties */}
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
                      onClick={() => handleRemoveProperty(key)}
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
              onKeyDown={(e) => e.key === "Enter" && handleAddProperty()}
              className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            <button
              onClick={handleAddProperty}
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

      {/* Tags */}
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
                  onClick={() => handleRemoveTag(tag)}
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
              onKeyDown={(e) => e.key === "Enter" && handleAddTag()}
              className="flex-1 px-1.5 py-1 text-[10px] bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
          </div>
        )}
      </div>

      {/* Notes */}
      <div className="p-3 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted mb-2">Notes</h3>
        {isViewer ? (
          <p className="text-xs text-text-muted min-h-[1.5em] rounded px-1 py-0.5">
            {entity.notes || "No notes"}
          </p>
        ) : editingNotes ? (
          <div>
            <textarea
              value={notesValue}
              onChange={(e) => setNotesValue(e.target.value)}
              onBlur={handleSaveNotes}
              autoFocus
              rows={5}
              className="w-full px-2 py-1 text-xs bg-bg border border-border rounded text-text focus:outline-none focus:border-accent resize-y min-h-[60px]"
            />
          </div>
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

      {/* Connected edges */}
      {connectedEdges.length > 0 && (
        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">
            Connections ({connectedEdges.length})
          </h3>
          <div className="space-y-1">
            {connectedEdges.map((edge) => {
              const otherId =
                edge.source_id === entity.id ? edge.target_id : edge.source_id;
              const other = entities.get(otherId);
              return (
                <div key={edge.id} className="text-xs text-text-muted">
                  <span className="text-accent">{edge.label || "linked"}</span>
                  {" \u2192 "}
                  <span className="text-text">{other?.value ?? otherId}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions — quick-launch transforms for this entity */}
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
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="p-3 mt-auto border-t border-border">
        <div className="space-y-1 text-[10px] text-text-muted">
          <p>Source: {entity.source}</p>
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
