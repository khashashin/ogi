import { CheckCircle2, XCircle, AlertCircle, PlusCircle } from "lucide-react";
import type { TransformRun } from "../types/transform";
import { ENTITY_TYPE_META } from "../types/entity";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";

interface TransformResultsProps {
  run: TransformRun;
}

export function TransformResults({ run }: TransformResultsProps) {
  const { loadGraph } = useGraphStore();
  const { currentProject } = useProjectStore();

  const statusIcon = {
    completed: <CheckCircle2 size={14} className="text-success" />,
    failed: <XCircle size={14} className="text-danger" />,
    running: <AlertCircle size={14} className="text-warning" />,
    pending: <AlertCircle size={14} className="text-text-muted" />,
  };

  const handleAddAll = async () => {
    if (!currentProject || !run.result) return;
    // Reload graph to pick up persisted entities
    await loadGraph(currentProject.id);
  };

  return (
    <div className="p-3">
      <div className="flex items-center gap-2 mb-3">
        {statusIcon[run.status]}
        <span className="text-xs font-medium text-text">
          {run.transform_name}
        </span>
        <span className="text-[10px] text-text-muted">
          {run.status}
        </span>
      </div>

      {run.error && (
        <div className="mb-3 p-2 bg-danger/10 border border-danger/20 rounded text-xs text-danger">
          {run.error}
        </div>
      )}

      {run.result && (
        <>
          {/* Messages */}
          {run.result.messages.length > 0 && (
            <div className="mb-3">
              <h4 className="text-[10px] uppercase text-text-muted mb-1">Messages</h4>
              <div className="space-y-0.5">
                {run.result.messages.map((msg, i) => (
                  <p key={i} className="text-xs text-text-muted">{msg}</p>
                ))}
              </div>
            </div>
          )}

          {/* Discovered entities */}
          {run.result.entities.length > 0 && (
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-[10px] uppercase text-text-muted">
                  Discovered Entities ({run.result.entities.length})
                </h4>
                <button
                  onClick={handleAddAll}
                  className="flex items-center gap-1 px-2 py-0.5 text-[10px] bg-accent text-white rounded hover:bg-accent-hover"
                >
                  <PlusCircle size={10} />
                  Reload Graph
                </button>
              </div>
              <div className="border border-border rounded overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-surface-hover">
                      <th className="text-left px-2 py-1 text-text-muted">Type</th>
                      <th className="text-left px-2 py-1 text-text-muted">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.result.entities.map((entity) => {
                      const meta = ENTITY_TYPE_META[entity.type];
                      return (
                        <tr key={entity.id} className="border-t border-border">
                          <td className="px-2 py-1">
                            <span
                              className="inline-block w-2 h-2 rounded-full mr-1.5"
                              style={{ backgroundColor: meta?.color }}
                            />
                            {entity.type}
                          </td>
                          <td className="px-2 py-1 text-text">{entity.value}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Discovered edges */}
          {run.result.edges.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase text-text-muted mb-1">
                Discovered Connections ({run.result.edges.length})
              </h4>
              <div className="space-y-0.5">
                {run.result.edges.map((edge) => (
                  <p key={edge.id} className="text-xs text-text-muted">
                    {edge.label || "linked"}
                  </p>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
