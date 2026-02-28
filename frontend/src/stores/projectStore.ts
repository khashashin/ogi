import { create } from "zustand";
import type { Project } from "../types/project";
import { api } from "../api/client";

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  fetchProjects: () => Promise<void>;
  createProject: (name: string, description?: string) => Promise<Project>;
  selectProject: (project: Project) => void;
  deleteProject: (id: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await api.projects.list();
      set({ projects, loading: false });
      if (!get().currentProject && projects.length > 0) {
        set({ currentProject: projects[0] });
      }
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  createProject: async (name, description) => {
    const project = await api.projects.create({ name, description });
    set((state) => ({
      projects: [project, ...state.projects],
      currentProject: project,
    }));
    return project;
  },

  selectProject: (project) => set({ currentProject: project }),

  deleteProject: async (id) => {
    await api.projects.delete(id);
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      currentProject:
        state.currentProject?.id === id ? null : state.currentProject,
    }));
  },
}));
