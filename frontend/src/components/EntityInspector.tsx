import { useState, useEffect } from "react";
import { Trash2, Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { ENTITY_TYPE_META } from "../types/entity";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";

export function EntityInspector() {
  const { selectedNodeId, entities, edges, removeEntity } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);

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

  const [runningTransform, setRunningTransform] = useState<string | null>(null);

  const handleRunTransform = async (transformName: string) => {
    if (!currentProject) return;
    setRunningTransform(transformName);
    try {
      const run = await api.transforms.run(
        transformName,
        entity.id,
        currentProject.id
      );
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
          <button
            onClick={handleDelete}
            className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-danger"
          >
            <Trash2 size={14} />
          </button>
        </div>
        <p className="text-sm font-medium text-text break-all">{entity.value}</p>
      </div>

      {/* Properties */}
      {Object.keys(entity.properties).length > 0 && (
        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">Properties</h3>
          <div className="space-y-1">
            {Object.entries(entity.properties).map(([key, val]) => (
              <div key={key} className="flex justify-between text-xs">
                <span className="text-text-muted">{key}</span>
                <span className="text-text">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tags */}
      {entity.tags.length > 0 && (
        <div className="p-3 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">Tags</h3>
          <div className="flex flex-wrap gap-1">
            {entity.tags.map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 text-[10px] bg-surface-hover rounded text-text-muted"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

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
                  {" → "}
                  <span className="text-text">{other?.value ?? otherId}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions — quick-launch transforms for this entity */}
      {transforms.length > 0 && (
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
          <p>ID: {entity.id.slice(0, 8)}...</p>
        </div>
      </div>
    </div>
  );
}
