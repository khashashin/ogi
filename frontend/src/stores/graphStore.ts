import { create } from "zustand";
import Graph from "graphology";
import type { Entity } from "../types/entity";
import type { Edge } from "../types/edge";
import { ENTITY_TYPE_META } from "../types/entity";
import { api } from "../api/client";

interface GraphState {
  graph: Graph;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  entities: Map<string, Entity>;
  edges: Map<string, Edge>;
  loading: boolean;
  error: string | null;

  loadGraph: (projectId: string) => Promise<void>;
  addEntity: (projectId: string, entity: Entity) => void;
  removeEntity: (projectId: string, entityId: string) => Promise<void>;
  addEdge: (projectId: string, edge: Edge) => void;
  removeEdge: (projectId: string, edgeId: string) => Promise<void>;
  selectNode: (nodeId: string | null) => void;
  selectEdge: (edgeId: string | null) => void;
  clearGraph: () => void;
}

function createGraph(): Graph {
  return new Graph({ multi: true, type: "directed" });
}

export const useGraphStore = create<GraphState>((set, get) => ({
  graph: createGraph(),
  selectedNodeId: null,
  selectedEdgeId: null,
  entities: new Map(),
  edges: new Map(),
  loading: false,
  error: null,

  loadGraph: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const data = await api.graph.get(projectId);
      const graph = createGraph();
      const entities = new Map<string, Entity>();
      const edges = new Map<string, Edge>();

      for (const entity of data.entities) {
        const meta = ENTITY_TYPE_META[entity.type];
        graph.addNode(entity.id, {
          label: entity.value,
          x: Math.random() * 800,
          y: Math.random() * 600,
          size: 8 + entity.weight * 2,
          color: meta?.color ?? "#6366f1",
          type: "circle",
          entityType: entity.type,
        });
        entities.set(entity.id, entity);
      }

      for (const edge of data.edges) {
        if (graph.hasNode(edge.source_id) && graph.hasNode(edge.target_id)) {
          graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, {
            label: edge.label,
            size: 2,
            color: "#4b5563",
          });
          edges.set(edge.id, edge);
        }
      }

      set({ graph, entities, edges, loading: false, selectedNodeId: null, selectedEdgeId: null });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  addEntity: (_projectId, entity) => {
    const { graph, entities } = get();
    const meta = ENTITY_TYPE_META[entity.type];
    if (!graph.hasNode(entity.id)) {
      graph.addNode(entity.id, {
        label: entity.value,
        x: Math.random() * 800,
        y: Math.random() * 600,
        size: 8 + entity.weight * 2,
        color: meta?.color ?? "#6366f1",
        type: "circle",
        entityType: entity.type,
      });
    }
    entities.set(entity.id, entity);
    set({ graph, entities: new Map(entities) });
  },

  removeEntity: async (projectId, entityId) => {
    const { graph, entities } = get();
    await api.entities.delete(projectId, entityId);
    if (graph.hasNode(entityId)) {
      graph.dropNode(entityId);
    }
    entities.delete(entityId);
    set({
      graph,
      entities: new Map(entities),
      selectedNodeId: get().selectedNodeId === entityId ? null : get().selectedNodeId,
    });
  },

  addEdge: (_projectId, edge) => {
    const { graph, edges } = get();
    if (
      graph.hasNode(edge.source_id) &&
      graph.hasNode(edge.target_id) &&
      !graph.hasEdge(edge.id)
    ) {
      graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, {
        label: edge.label,
        size: 2,
        color: "#4b5563",
      });
    }
    edges.set(edge.id, edge);
    set({ graph, edges: new Map(edges) });
  },

  removeEdge: async (projectId, edgeId) => {
    const { graph, edges } = get();
    await api.edges.delete(projectId, edgeId);
    if (graph.hasEdge(edgeId)) {
      graph.dropEdge(edgeId);
    }
    edges.delete(edgeId);
    set({ graph, edges: new Map(edges) });
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId, selectedEdgeId: null }),
  selectEdge: (edgeId) => set({ selectedEdgeId: edgeId, selectedNodeId: null }),

  clearGraph: () =>
    set({
      graph: createGraph(),
      selectedNodeId: null,
      selectedEdgeId: null,
      entities: new Map(),
      edges: new Map(),
    }),
}));
