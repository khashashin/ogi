import { create } from "zustand";
import type { Project } from "../types/project";
import { api } from "../api/client";

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  fetchProjects: () => Promise<void>;
  loadProjectById: (id: string) => Promise<void>;
  createProject: (name: string, description?: string, is_public?: boolean) => Promise<Project>;
  updateProject: (id: string, data: import("../types/project").ProjectUpdate) => Promise<Project>;
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

  loadProjectById: async (id) => {
    set({ loading: true, error: null });
    try {
      const project = await api.projects.get(id);
      set({ currentProject: project, loading: false });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  createProject: async (name, description, is_public) => {
    const project = await api.projects.create({ name, description, is_public });
    set((state) => ({
      projects: [project, ...state.projects],
      currentProject: project,
    }));
    return project;
  },

  updateProject: async (id, data) => {
    const project = await api.projects.update(id, data);
    set((state) => ({
      projects: state.projects.map((p) => (p.id === id ? project : p)),
      currentProject: state.currentProject?.id === id ? project : state.currentProject,
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
