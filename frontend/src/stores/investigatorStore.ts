import { create } from "zustand";
import { api } from "../api/client";
import type { AgentEventMessage, AgentRun, AgentRunStatus, AgentStep, ScopeConfig } from "../types/agent";

interface InvestigatorState {
  projectId: string | null;
  activeRun: AgentRun | null;
  steps: AgentStep[];
  isLoading: boolean;
  error: string | null;
  startRun: (projectId: string, prompt: string, scope: ScopeConfig) => Promise<void>;
  loadActiveRun: (projectId: string) => Promise<void>;
  refreshRun: (projectId: string, runId: string) => Promise<void>;
  cancelRun: (projectId: string, runId?: string) => Promise<void>;
  approveStep: (projectId: string, runId: string, stepId: string, note?: string) => Promise<void>;
  rejectStep: (projectId: string, runId: string, stepId: string, note?: string) => Promise<void>;
  handleMessage: (projectId: string, msg: AgentEventMessage) => Promise<void>;
  reset: () => void;
}

const ACTIVE_STATUSES: AgentRunStatus[] = ["pending", "running", "paused"];

export const useInvestigatorStore = create<InvestigatorState>((set, get) => ({
  projectId: null,
  activeRun: null,
  steps: [],
  isLoading: false,
  error: null,

  startRun: async (projectId, prompt, scope) => {
    set({ isLoading: true, error: null });
    try {
      const run = await api.agent.start(projectId, { prompt, scope });
      const steps = await api.agent.listSteps(projectId, run.id);
      set({ projectId, activeRun: run, steps, isLoading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false });
      throw error;
    }
  },

  loadActiveRun: async (projectId) => {
    set({ projectId, isLoading: true, error: null });
    try {
      const runs = await api.agent.listRuns(projectId, [...ACTIVE_STATUSES]);
      const activeRun = runs[0] ?? null;
      if (!activeRun) {
        set({ projectId, activeRun: null, steps: [], isLoading: false });
        return;
      }
      const steps = await api.agent.listSteps(projectId, activeRun.id);
      set({ projectId, activeRun, steps, isLoading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false });
    }
  },

  refreshRun: async (projectId, runId) => {
    try {
      const [run, steps] = await Promise.all([
        api.agent.getRun(projectId, runId),
        api.agent.listSteps(projectId, runId),
      ]);
      set({ projectId, activeRun: run, steps, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error) });
    }
  },

  cancelRun: async (projectId, runId) => {
    const targetRunId = runId ?? get().activeRun?.id;
    if (!targetRunId) return;
    set({ isLoading: true, error: null });
    try {
      const run = await api.agent.cancel(projectId, targetRunId);
      const steps = await api.agent.listSteps(projectId, targetRunId);
      set({ activeRun: run, steps, isLoading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false });
    }
  },

  approveStep: async (projectId, runId, stepId, note) => {
    set({ isLoading: true, error: null });
    try {
      await api.agent.approveStep(projectId, runId, stepId, note);
      await get().refreshRun(projectId, runId);
      set({ isLoading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false });
    }
  },

  rejectStep: async (projectId, runId, stepId, note) => {
    set({ isLoading: true, error: null });
    try {
      await api.agent.rejectStep(projectId, runId, stepId, note);
      await get().refreshRun(projectId, runId);
      set({ isLoading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false });
    }
  },

  handleMessage: async (projectId, msg) => {
    const state = get();
    if (state.projectId !== projectId) {
      return;
    }
    const activeRun = state.activeRun;
    if (activeRun && activeRun.id !== msg.run_id && !ACTIVE_STATUSES.includes(activeRun.status)) {
      return;
    }
    await get().refreshRun(projectId, msg.run_id);
  },

  reset: () => {
    set({
      projectId: null,
      activeRun: null,
      steps: [],
      isLoading: false,
      error: null,
    });
  },
}));
