import { create } from "zustand";
import type { TransformRun, TransformJobMessage } from "../types/transform";

interface TransformJob {
  runId: string;
  transformName: string;
  inputEntityId: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  error: string | null;
}

interface TransformJobState {
  activeJobs: Map<string, TransformJob>;
  recentCompleted: TransformRun[];

  submitJob: (run: TransformRun) => void;
  handleMessage: (msg: TransformJobMessage) => void;
  clearJob: (jobId: string) => void;
  clearAll: () => void;
}

const MAX_RECENT = 20;

export const useTransformJobStore = create<TransformJobState>((set, get) => ({
  activeJobs: new Map(),
  recentCompleted: [],

  submitJob: (run) => {
    const { activeJobs } = get();
    activeJobs.set(run.id, {
      runId: run.id,
      transformName: run.transform_name,
      inputEntityId: run.input_entity_id,
      status: "pending",
      error: null,
    });
    set({ activeJobs: new Map(activeJobs) });
  },

  handleMessage: (msg) => {
    const { activeJobs, recentCompleted } = get();

    const jobId = msg.job_id;
    const existing = activeJobs.get(jobId);

    switch (msg.type) {
      case "job_submitted": {
        if (!existing) {
          activeJobs.set(jobId, {
            runId: jobId,
            transformName: msg.transform_name,
            inputEntityId: msg.input_entity_id,
            status: "pending",
            error: null,
          });
        }
        set({ activeJobs: new Map(activeJobs) });
        break;
      }
      case "job_started": {
        if (existing) {
          existing.status = "running";
        }
        set({ activeJobs: new Map(activeJobs) });
        break;
      }
      case "job_completed": {
        activeJobs.delete(jobId);
        // Add to recent completed
        const completedRun: TransformRun = {
          id: jobId,
          project_id: msg.project_id,
          transform_name: msg.transform_name,
          input_entity_id: msg.input_entity_id,
          status: "completed",
          result: msg.result,
          error: null,
          started_at: msg.timestamp,
          completed_at: msg.timestamp,
        };
        const updated = [completedRun, ...recentCompleted].slice(0, MAX_RECENT);
        set({ activeJobs: new Map(activeJobs), recentCompleted: updated });
        break;
      }
      case "job_failed": {
        activeJobs.delete(jobId);
        set({ activeJobs: new Map(activeJobs) });
        break;
      }
      case "job_cancelled": {
        activeJobs.delete(jobId);
        set({ activeJobs: new Map(activeJobs) });
        break;
      }
    }
  },

  clearJob: (jobId) => {
    const { activeJobs } = get();
    activeJobs.delete(jobId);
    set({ activeJobs: new Map(activeJobs) });
  },

  clearAll: () => {
    set({ activeJobs: new Map(), recentCompleted: [] });
  },
}));

export type { TransformJob };
