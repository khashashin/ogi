import { useState, useEffect, useCallback } from "react";
import { Play, Loader2, Square, Settings } from "lucide-react";
import { toast } from "sonner";
import type { TransformInfo, TransformRun, TransformJobMessage } from "../types/transform";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { useTransformJobStore } from "../stores/transformJobStore";
import type { TransformJob } from "../stores/transformJobStore";
import { useTransformWebSocket } from "../hooks/useTransformWebSocket";
import { api } from "../api/client";
import { TransformResults } from "./TransformResults";
import { TransformSettingsDialog } from "./TransformSettingsDialog";

export function TransformPanel() {
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [lastRun, setLastRun] = useState<TransformRun | null>(null);
  const [settingsTransform, setSettingsTransform] = useState<TransformInfo | null>(null);
  const { selectedNodeId, entities } = useGraphStore();
  const { currentProject } = useProjectStore();
  const { activeJobs, submitJob, handleMessage, recentCompleted } = useTransformJobStore();

  const entity = selectedNodeId ? entities.get(selectedNodeId) : null;

  // WebSocket message handler
  const onWsMessage = useCallback((msg: TransformJobMessage) => {
    handleMessage(msg);

    if (msg.type === "job_completed" && msg.result) {
      const { addEntity, addEdge } = useGraphStore.getState();
      const projectId = msg.project_id;

      for (const newEntity of msg.result.entities) {
        addEntity(projectId, newEntity);
      }
      for (const newEdge of msg.result.edges) {
        addEdge(projectId, newEdge);
      }

      const entityCount = msg.result.entities.length;
      const edgeCount = msg.result.edges.length;
      toast.success(`${msg.transform_name}: found ${entityCount} entities, ${edgeCount} connections`);

      // Update lastRun for the results panel
      const completedRun: TransformRun = {
        id: msg.job_id,
        project_id: msg.project_id,
        transform_name: msg.transform_name,
        input_entity_id: msg.input_entity_id,
        status: "completed",
        result: msg.result,
        error: null,
        started_at: msg.timestamp,
        completed_at: msg.timestamp,
      };
      setLastRun(completedRun);
    }

    if (msg.type === "job_failed") {
      toast.error(`${msg.transform_name}: ${msg.error ?? "Unknown error"}`);
    }

    if (msg.type === "job_cancelled") {
      toast.info(`${msg.transform_name}: cancelled`);
    }
  }, [handleMessage]);

  const { cancelJob } = useTransformWebSocket({
    projectId: currentProject?.id ?? null,
    onMessage: onWsMessage,
  });

  useEffect(() => {
    if (!entity) return;
    api.transforms
      .forEntity(entity.id)
      .then(setTransforms)
      .catch(() => setTransforms([]));
  }, [entity]);

  const handleRun = async (name: string) => {
    if (!entity || !currentProject) return;
    try {
      const run = await api.transforms.run(name, entity.id, currentProject.id);
      submitJob(run);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Transform failed: ${msg}`);
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await api.transforms.cancel(jobId);
      cancelJob(jobId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Cancel failed: ${msg}`);
    }
  };

  // Check if a specific transform has an active job
  const isTransformActive = (name: string): boolean => {
    for (const job of activeJobs.values()) {
      if (job.transformName === name && (job.status === "pending" || job.status === "running")) {
        return true;
      }
    }
    return false;
  };

  const activeJobsList = Array.from(activeJobs.values()).filter(
    (j) => j.status === "pending" || j.status === "running"
  );

  // Use the most recent completed run if we haven't set one via WS yet
  const displayRun = lastRun ?? (recentCompleted.length > 0 ? recentCompleted[0] : null);

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

        {/* Active jobs indicator */}
        {activeJobsList.length > 0 && (
          <div className="p-2 border-b border-border bg-surface-hover/50">
            <p className="text-[10px] font-semibold text-text-muted mb-1">
              Active ({activeJobsList.length})
            </p>
            {activeJobsList.map((job) => (
              <ActiveJobItem key={job.runId} job={job} onCancel={handleCancel} />
            ))}
          </div>
        )}

        {transforms.length === 0 ? (
          <p className="p-3 text-xs text-text-muted">No transforms available</p>
        ) : (
          <div className="p-1">
            {transforms.map((t) => {
              const active = isTransformActive(t.name);
              return (
                <div key={t.name}>
                  <button
                    onClick={() => handleRun(t.name)}
                    disabled={active}
                    className="w-full flex items-center gap-2 px-2 py-2 rounded text-xs text-text hover:bg-surface-hover disabled:opacity-50"
                  >
                    {active ? (
                      <Loader2 size={12} className="animate-spin text-accent shrink-0" />
                    ) : (
                      <Play size={12} className="text-accent shrink-0" />
                    )}
                    <div className="text-left">
                      <p className="font-medium">{t.display_name}</p>
                      <p className="text-[10px] text-text-muted">{t.description}</p>
                    </div>
                  </button>
                  <div className="px-2 pb-2">
                    {t.settings && t.settings.length > 0 && (
                      <button
                        onClick={() => setSettingsTransform(t)}
                        className="text-[10px] text-text-muted hover:text-text flex items-center gap-1"
                      >
                        <Settings size={10} />
                        Settings
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {displayRun ? (
          <TransformResults run={displayRun} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-1">
            <p className="text-xs font-semibold text-text-muted">Output</p>
            <p className="text-[10px] text-text-muted">Run a transform to see discovered entities and connections</p>
          </div>
        )}
      </div>
      <TransformSettingsDialog
        open={settingsTransform !== null}
        transform={settingsTransform}
        onClose={() => setSettingsTransform(null)}
      />
    </div>
  );
}

function ActiveJobItem({ job, onCancel }: { job: TransformJob; onCancel: (id: string) => void }) {
  return (
    <div className="flex items-center gap-1.5 px-1 py-1 text-[10px]">
      <Loader2 size={10} className="animate-spin text-accent shrink-0" />
      <span className="truncate flex-1 text-text">{job.transformName}</span>
      <span className="text-text-muted">{job.status}</span>
      <button
        onClick={() => onCancel(job.runId)}
        className="p-0.5 rounded hover:bg-surface-hover text-text-muted hover:text-text"
        title="Cancel"
      >
        <Square size={8} />
      </button>
    </div>
  );
}
