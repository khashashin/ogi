import { useState, useEffect } from "react";
import { Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { TransformInfo, TransformRun } from "../types/transform";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { api } from "../api/client";
import { TransformResults } from "./TransformResults";

export function TransformPanel() {
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<TransformRun | null>(null);
  const { selectedNodeId, entities } = useGraphStore();
  const { currentProject } = useProjectStore();

  const entity = selectedNodeId ? entities.get(selectedNodeId) : null;

  useEffect(() => {
    if (!entity) {
      setTransforms([]);
      return;
    }
    api.transforms
      .forEntity(entity.id)
      .then(setTransforms)
      .catch(() => setTransforms([]));
  }, [entity]);

  const handleRun = async (name: string) => {
    if (!entity || !currentProject) return;
    setRunning(name);
    try {
      const run = await api.transforms.run(name, entity.id, currentProject.id);
      setLastRun(run);

      // Auto-add discovered entities and edges to the graph
      if (run.result) {
        const { addEntity, addEdge } = useGraphStore.getState();
        for (const newEntity of run.result.entities) {
          addEntity(currentProject.id, newEntity);
        }
        for (const newEdge of run.result.edges) {
          addEdge(currentProject.id, newEdge);
        }
        const entityCount = run.result.entities.length;
        const edgeCount = run.result.edges.length;
        toast.success(`${name}: found ${entityCount} entities, ${edgeCount} connections`);
      }

      if (run.error) {
        toast.error(`${name}: ${run.error}`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Transform failed: ${msg}`);
    } finally {
      setRunning(null);
    }
  };

  if (!entity) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <p className="text-xs text-text-muted">Select an entity to run transforms and see output</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-border overflow-y-auto">
        <div className="p-2 border-b border-border">
          <p className="text-xs font-semibold text-text-muted">Run Transform</p>
          <p className="text-[10px] text-text-muted mt-0.5">
            on <span className="text-text">{entity.value}</span>
          </p>
        </div>
        {transforms.length === 0 ? (
          <p className="p-3 text-xs text-text-muted">No transforms available</p>
        ) : (
          <div className="p-1">
            {transforms.map((t) => (
              <button
                key={t.name}
                onClick={() => handleRun(t.name)}
                disabled={running !== null}
                className="w-full flex items-center gap-2 px-2 py-2 rounded text-xs text-text hover:bg-surface-hover disabled:opacity-50"
              >
                {running === t.name ? (
                  <Loader2 size={12} className="animate-spin text-accent" />
                ) : (
                  <Play size={12} className="text-accent" />
                )}
                <div className="text-left">
                  <p className="font-medium">{t.display_name}</p>
                  <p className="text-[10px] text-text-muted">{t.description}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {lastRun ? (
          <TransformResults run={lastRun} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-1">
            <p className="text-xs font-semibold text-text-muted">Output</p>
            <p className="text-[10px] text-text-muted">Run a transform to see discovered entities and connections</p>
          </div>
        )}
      </div>
    </div>
  );
}
