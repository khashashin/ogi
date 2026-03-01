import type { Project, ProjectCreate, ProjectUpdate } from "../types/project";
import type { Entity, EntityCreate, EntityUpdate, EntityTypeMeta } from "../types/entity";
import type { Edge, EdgeCreate, EdgeUpdate } from "../types/edge";
import type { GraphData } from "../types/graph";
import type { TransformInfo, TransformRun, TransformConfig } from "../types/transform";

const BASE_URL = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Projects
export const api = {
  projects: {
    list: () => request<Project[]>("/projects"),
    get: (id: string) => request<Project>(`/projects/${id}`),
    create: (data: ProjectCreate) =>
      request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: ProjectUpdate) =>
      request<Project>(`/projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/projects/${id}`, { method: "DELETE" }),
  },

  entities: {
    list: (projectId: string) =>
      request<Entity[]>(`/projects/${projectId}/entities`),
    get: (projectId: string, entityId: string) =>
      request<Entity>(`/projects/${projectId}/entities/${entityId}`),
    create: (projectId: string, data: EntityCreate) =>
      request<Entity>(`/projects/${projectId}/entities`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (projectId: string, entityId: string, data: EntityUpdate) =>
      request<Entity>(`/projects/${projectId}/entities/${entityId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (projectId: string, entityId: string) =>
      request<void>(`/projects/${projectId}/entities/${entityId}`, {
        method: "DELETE",
      }),
  },

  edges: {
    list: (projectId: string) =>
      request<Edge[]>(`/projects/${projectId}/edges`),
    create: (projectId: string, data: EdgeCreate) =>
      request<Edge>(`/projects/${projectId}/edges`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (projectId: string, edgeId: string, data: EdgeUpdate) =>
      request<Edge>(`/projects/${projectId}/edges/${edgeId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (projectId: string, edgeId: string) =>
      request<void>(`/projects/${projectId}/edges/${edgeId}`, {
        method: "DELETE",
      }),
  },

  graph: {
    get: (projectId: string) =>
      request<GraphData>(`/projects/${projectId}/graph`),
    neighbors: (projectId: string, entityId: string) =>
      request<GraphData>(`/projects/${projectId}/graph/neighbors/${entityId}`),
  },

  transforms: {
    list: () => request<TransformInfo[]>("/transforms"),
    entityTypes: () => request<EntityTypeMeta[]>("/transforms/entity-types"),
    forEntity: (entityId: string) =>
      request<TransformInfo[]>(`/transforms/for-entity/${entityId}`),
    run: (name: string, entityId: string, projectId: string, config?: TransformConfig) =>
      request<TransformRun>(`/transforms/${name}/run`, {
        method: "POST",
        body: JSON.stringify({
          entity_id: entityId,
          project_id: projectId,
          config: config ?? { settings: {} },
        }),
      }),
    getRun: (runId: string) => request<TransformRun>(`/transforms/runs/${runId}`),
  },
};
