import type { Project, ProjectCreate, ProjectUpdate } from "../types/project";
import type { Entity, EntityCreate, EntityUpdate, EntityTypeMeta } from "../types/entity";
import type { Edge, EdgeCreate, EdgeUpdate } from "../types/edge";
import type { GraphData } from "../types/graph";
import type { TransformInfo, TransformRun, TransformConfig, TransformSettingsResponse } from "../types/transform";
import type { RegistryIndex, RegistryTransform, PluginInfo, PluginApiKeyUsageReportItem, UpdateCheckItem } from "../types/registry";
import type { AuditLogEntry, LocationAggregate, ProjectEventsResponse } from "../types/eventing";
import type { TimelineResponse } from "../types/timeline";
import type { MapPointsResponse, MapRoutesResponse } from "../types/map";
import type { LocationSuggestResponse } from "../types/location";
import type {
  AgentModelCatalog,
  AgentRun,
  AgentSettings,
  AgentSettingsTestResult,
  AgentStep,
  StartAgentRunRequest,
} from "../types/agent";
import { supabase } from "../lib/supabase";

interface GraphStats {
  entity_count: number;
  edge_count: number;
  density: number;
  avg_degree: number;
  connected_components: number;
}

interface AnalysisResult {
  scores?: Record<string, number>;
  communities?: string[][];
}

interface ImportSummary {
  entities_added: number;
  entities_merged: number;
  entities_skipped: number;
  edges_added: number;
  edges_skipped: number;
}

interface CloudExportResponse {
  url: string;
}

interface DiscoverProject {
  id: string;
  name: string;
  description: string;
  owner_id: string | null;
  owner_name: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  is_bookmarked: boolean;
}

interface MyProjectItem extends DiscoverProject {
  source: "owned" | "member" | "bookmarked";
  role: string;
}

interface ProjectMember {
  project_id: string;
  user_id: string;
  role: string;
  display_name: string;
  email: string;
}

interface ProjectMemberCreate {
  email: string;
  role: string;
}

interface ProjectMemberUpdate {
  role: string;
}

interface InstallResult {
  slug: string;
  version: string;
  files_installed: number;
  message: string;
}

const BASE_URL = "/api/v1";

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (!supabase) return {};
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
    ...options,
  });
  if (res.status === 401) {
    // Session expired or invalid — trigger sign-out
    if (supabase) {
      await supabase.auth.signOut();
    }
    throw new Error("Unauthorized — please sign in again");
  }
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
    my: () => request<MyProjectItem[]>("/projects/my"),
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
    bookmark: (id: string) =>
      request<{ status: string }>(`/projects/${id}/bookmark`, { method: "POST" }),
    unbookmark: (id: string) =>
      request<void>(`/projects/${id}/bookmark`, { method: "DELETE" }),
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
    bulkDelete: (projectId: string, entityIds: string[]) =>
      request<{ deleted_entity_ids: string[]; deleted_count: number }>(
        `/projects/${projectId}/entities/bulk-delete`,
        {
          method: "POST",
          body: JSON.stringify({ entity_ids: entityIds }),
        }
      ),
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
    get: (projectId: string, refresh = false) =>
      request<GraphData>(`/projects/${projectId}/graph${refresh ? "?refresh=true" : ""}`),
    window: (projectId: string, fromTs?: string, toTs?: string) => {
      const params = new URLSearchParams();
      if (fromTs) params.set("from", fromTs);
      if (toTs) params.set("to", toTs);
      const qs = params.toString();
      return request<GraphData>(`/projects/${projectId}/graph/window${qs ? `?${qs}` : ""}`);
    },
    neighbors: (projectId: string, entityId: string) =>
      request<GraphData>(`/projects/${projectId}/graph/neighbors/${entityId}`),
    stats: (projectId: string) =>
      request<GraphStats>(`/projects/${projectId}/graph/stats`),
    analyze: (projectId: string, algorithm: string) =>
      request<AnalysisResult>(`/projects/${projectId}/graph/analyze`, {
        method: "POST",
        body: JSON.stringify({ algorithm }),
      }),
  },

  export: {
    json: (projectId: string) =>
      `${BASE_URL}/projects/${projectId}/export/json`,
    csv: (projectId: string) =>
      `${BASE_URL}/projects/${projectId}/export/csv`,
    graphml: (projectId: string) =>
      `${BASE_URL}/projects/${projectId}/export/graphml`,
    cloud: (projectId: string, format: "json" | "csv" | "graphml") =>
      request<CloudExportResponse>(`/projects/${projectId}/export/${format}?cloud=true`),
  },

  import: {
    json: async (projectId: string, file: File) => {
      const authHeaders = await getAuthHeaders();
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${BASE_URL}/projects/${projectId}/import/json`, {
        method: "POST",
        headers: { ...authHeaders },
        body: formData,
      });
      if (!res.ok) throw new Error(`Import failed: ${res.status}`);
      return res.json() as Promise<ImportSummary>;
    },
    csv: async (projectId: string, file: File) => {
      const authHeaders = await getAuthHeaders();
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${BASE_URL}/projects/${projectId}/import/csv`, {
        method: "POST",
        headers: { ...authHeaders },
        body: formData,
      });
      if (!res.ok) throw new Error(`Import failed: ${res.status}`);
      return res.json() as Promise<ImportSummary>;
    },
    graphml: async (projectId: string, file: File) => {
      const authHeaders = await getAuthHeaders();
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${BASE_URL}/projects/${projectId}/import/graphml`, {
        method: "POST",
        headers: { ...authHeaders },
        body: formData,
      });
      if (!res.ok) throw new Error(`Import failed: ${res.status}`);
      return res.json() as Promise<ImportSummary>;
    },
    maltego: async (projectId: string, file: File) => {
      const authHeaders = await getAuthHeaders();
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${BASE_URL}/projects/${projectId}/import/maltego`, {
        method: "POST",
        headers: { ...authHeaders },
        body: formData,
      });
      if (!res.ok) throw new Error(`Import failed: ${res.status}`);
      return res.json() as Promise<ImportSummary>;
    },
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
    getSettings: (name: string) =>
      request<TransformSettingsResponse>(`/transforms/${name}/settings`),
    saveUserSettings: (name: string, settings: Record<string, string>) =>
      request<TransformSettingsResponse>(`/transforms/${name}/settings/user`, {
        method: "PUT",
        body: JSON.stringify({ settings }),
      }),
    saveGlobalSettings: (name: string, settings: Record<string, string>) =>
      request<TransformSettingsResponse>(`/transforms/${name}/settings/global`, {
        method: "PUT",
        body: JSON.stringify({ settings }),
      }),
    getRun: (runId: string) => request<TransformRun>(`/transforms/runs/${runId}`),
    cancel: (runId: string) =>
      request<{ status: string; run_id: string }>(`/transforms/runs/${runId}/cancel`, { method: "POST" }),
  },

  apiKeys: {
    list: () => request<{ service_name: string }[]>("/settings/api-keys"),
    save: (serviceName: string, key: string) =>
      request<{ service_name: string }>("/settings/api-keys", {
        method: "POST",
        body: JSON.stringify({ service_name: serviceName, key }),
      }),
    delete: (serviceName: string) =>
      request<void>(`/settings/api-keys/${serviceName}`, { method: "DELETE" }),
  },

  plugins: {
    list: () => request<PluginInfo[]>("/plugins"),
    get: (name: string) => request<PluginInfo>(`/plugins/${name}`),
    apiKeyUsageReport: () => request<PluginApiKeyUsageReportItem[]>("/plugins/api-key-usage-report"),
    enable: (name: string) =>
      request<PluginInfo>(`/plugins/${name}/enable`, { method: "POST" }),
    disable: (name: string) =>
      request<PluginInfo>(`/plugins/${name}/disable`, { method: "POST" }),
    reload: (name: string) =>
      request<PluginInfo>(`/plugins/${name}/reload`, { method: "POST" }),
  },

  members: {
    list: (projectId: string) =>
      request<ProjectMember[]>(`/projects/${projectId}/members`),
    add: (projectId: string, data: ProjectMemberCreate) =>
      request<ProjectMember>(`/projects/${projectId}/members`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (projectId: string, userId: string, data: ProjectMemberUpdate) =>
      request<ProjectMember>(`/projects/${projectId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    remove: (projectId: string, userId: string) =>
      request<void>(`/projects/${projectId}/members/${userId}`, {
        method: "DELETE",
      }),
  },

  eventing: {
    events: (projectId: string) =>
      request<ProjectEventsResponse>(`/projects/${projectId}/events`),
    locations: (projectId: string) =>
      request<LocationAggregate[]>(`/projects/${projectId}/locations`),
    auditLogs: (projectId: string) =>
      request<AuditLogEntry[]>(`/projects/${projectId}/audit-logs`),
  },

  timeline: {
    get: (projectId: string, interval: "minute" | "hour" | "day" | "week" = "day") =>
      request<TimelineResponse>(`/projects/${projectId}/timeline?interval=${interval}`),
  },

  agent: {
    getSettings: (projectId: string) =>
      request<AgentSettings>(`/projects/${projectId}/agent/settings`),
    saveSettings: (projectId: string, data: { provider: string; model: string }) =>
      request<AgentSettings>(`/projects/${projectId}/agent/settings`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    listModels: (projectId: string, provider: string) =>
      request<AgentModelCatalog>(
        `/projects/${projectId}/agent/settings/models?provider=${encodeURIComponent(provider)}`
      ),
    testSettings: (projectId: string, data: { provider: string; model: string }) =>
      request<AgentSettingsTestResult>(`/projects/${projectId}/agent/settings/test`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    start: (projectId: string, data: StartAgentRunRequest) =>
      request<AgentRun>(`/projects/${projectId}/agent/start`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    listRuns: (projectId: string, statuses?: string[]) => {
      const params = new URLSearchParams();
      if (statuses && statuses.length > 0) {
        params.set("statuses", statuses.join(","));
      }
      const qs = params.toString();
      return request<AgentRun[]>(`/projects/${projectId}/agent/runs${qs ? `?${qs}` : ""}`);
    },
    getRun: (projectId: string, runId: string) =>
      request<AgentRun>(`/projects/${projectId}/agent/runs/${runId}`),
    listSteps: (projectId: string, runId: string) =>
      request<AgentStep[]>(`/projects/${projectId}/agent/runs/${runId}/steps`),
    cancel: (projectId: string, runId: string) =>
      request<AgentRun>(`/projects/${projectId}/agent/runs/${runId}/cancel`, { method: "POST" }),
    approveStep: (projectId: string, runId: string, stepId: string, note?: string) =>
      request<AgentStep>(`/projects/${projectId}/agent/runs/${runId}/steps/${stepId}/approve`, {
        method: "POST",
        body: JSON.stringify({ note }),
      }),
    rejectStep: (projectId: string, runId: string, stepId: string, note?: string) =>
      request<AgentStep>(`/projects/${projectId}/agent/runs/${runId}/steps/${stepId}/reject`, {
        method: "POST",
        body: JSON.stringify({ note }),
      }),
  },

  map: {
    points: (projectId: string, zoom = 3, cluster = true) =>
      request<MapPointsResponse>(`/projects/${projectId}/map/points?zoom=${zoom}&cluster=${cluster}`),
    routes: (projectId: string) =>
      request<MapRoutesResponse>(`/projects/${projectId}/map/routes`),
  },

  locations: {
    suggest: (projectId: string, q: string, limit = 5) =>
      request<LocationSuggestResponse>(
        `/projects/${projectId}/locations/suggest?q=${encodeURIComponent(q)}&limit=${limit}`
      ),
  },

  discover: {
    list: (search?: string) => {
      const params = search ? `?q=${encodeURIComponent(search)}` : "";
      return request<DiscoverProject[]>(`/discover${params}`);
    },
  },

  registry: {
    index: () => request<RegistryIndex>("/registry/index"),
    checkUpdates: () => request<UpdateCheckItem[]>("/registry/check-updates"),
    search: (q?: string, category?: string, tier?: string) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (category) params.set("category", category);
      if (tier) params.set("tier", tier);
      const qs = params.toString();
      return request<RegistryTransform[]>(`/registry/search${qs ? `?${qs}` : ""}`);
    },
    install: (slug: string) =>
      request<InstallResult>(`/registry/install/${slug}`, { method: "POST" }),
    remove: (slug: string) =>
      request<{ status: string; slug: string }>(`/registry/remove/${slug}`, { method: "DELETE" }),
    update: (slug: string) =>
      request<InstallResult>(`/registry/update/${slug}`, { method: "POST" }),
  },
};

export type { DiscoverProject, MyProjectItem, ProjectMember };
