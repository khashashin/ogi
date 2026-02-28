import { create } from "zustand";
import Graph from "graphology";
import type { Entity } from "../types/entity";
import type { Edge } from "../types/edge";
import { ENTITY_TYPE_META } from "../types/entity";
import { api } from "../api/client";
import { useUndoStore } from "./undoStore";
import type { UndoAction } from "./undoStore";

interface NodePositions {
  [nodeId: string]: { x: number; y: number };
}

function loadPositions(projectId: string): NodePositions {
  try {
    const raw = localStorage.getItem(`ogi-positions-${projectId}`);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePositions(projectId: string, graph: Graph): void {
  const positions: NodePositions = {};
  graph.forEachNode((node, attrs) => {
    if (typeof attrs.x === "number" && typeof attrs.y === "number") {
      positions[node] = { x: attrs.x, y: attrs.y };
    }
  });
  localStorage.setItem(`ogi-positions-${projectId}`, JSON.stringify(positions));
}

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
  persistPositions: (projectId: string) => void;
  performUndo: (projectId: string) => Promise<void>;
  performRedo: (projectId: string) => Promise<void>;
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
      const savedPositions = loadPositions(projectId);

      for (const entity of data.entities) {
        const meta = ENTITY_TYPE_META[entity.type];
        const pos = savedPositions[entity.id];
        graph.addNode(entity.id, {
          label: entity.value,
          x: pos?.x ?? Math.random() * 800,
          y: pos?.y ?? Math.random() * 600,
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
    const nodeAttrs = {
      label: entity.value,
      x: Math.random() * 800,
      y: Math.random() * 600,
      size: 8 + entity.weight * 2,
      color: meta?.color ?? "#6366f1",
      type: "circle" as const,
      entityType: entity.type,
    };
    if (!graph.hasNode(entity.id)) {
      graph.addNode(entity.id, nodeAttrs);
    }
    entities.set(entity.id, entity);
    useUndoStore.getState().push({ type: "add_entity", entity, nodeAttrs });
    set({ graph, entities: new Map(entities) });
  },

  removeEntity: async (projectId, entityId) => {
    const { graph, entities, edges } = get();
    const entity = entities.get(entityId);
    if (!entity) return;

    // Capture node attributes and connected edges before removal
    const nodeAttrs = graph.hasNode(entityId) ? graph.getNodeAttributes(entityId) : {};
    const connectedEdges: Edge[] = [];
    const connectedEdgeAttrs: Record<string, Record<string, unknown>> = {};
    if (graph.hasNode(entityId)) {
      graph.forEachEdge(entityId, (edgeKey, attrs) => {
        const edgeData = edges.get(edgeKey);
        if (edgeData) {
          connectedEdges.push(edgeData);
          connectedEdgeAttrs[edgeKey] = { ...attrs };
        }
      });
    }

    await api.entities.delete(projectId, entityId);
    if (graph.hasNode(entityId)) {
      graph.dropNode(entityId);
    }
    entities.delete(entityId);
    for (const e of connectedEdges) {
      edges.delete(e.id);
    }

    useUndoStore.getState().push({
      type: "remove_entity",
      entity,
      nodeAttrs,
      edges: connectedEdges,
      edgeAttrs: connectedEdgeAttrs,
    });

    set({
      graph,
      entities: new Map(entities),
      edges: new Map(edges),
      selectedNodeId: get().selectedNodeId === entityId ? null : get().selectedNodeId,
    });
  },

  addEdge: (_projectId, edge) => {
    const { graph, edges } = get();
    const edgeAttrs = { label: edge.label, size: 2, color: "#4b5563" };
    if (
      graph.hasNode(edge.source_id) &&
      graph.hasNode(edge.target_id) &&
      !graph.hasEdge(edge.id)
    ) {
      graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, edgeAttrs);
    }
    edges.set(edge.id, edge);
    useUndoStore.getState().push({ type: "add_edge", edge, edgeAttrs });
    set({ graph, edges: new Map(edges) });
  },

  removeEdge: async (projectId, edgeId) => {
    const { graph, edges } = get();
    const edge = edges.get(edgeId);
    if (!edge) return;

    const edgeAttrs = graph.hasEdge(edgeId) ? graph.getEdgeAttributes(edgeId) : {};
    await api.edges.delete(projectId, edgeId);
    if (graph.hasEdge(edgeId)) {
      graph.dropEdge(edgeId);
    }
    edges.delete(edgeId);
    useUndoStore.getState().push({ type: "remove_edge", edge, edgeAttrs });
    set({ graph, edges: new Map(edges) });
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId, selectedEdgeId: null }),
  selectEdge: (edgeId) => set({ selectedEdgeId: edgeId, selectedNodeId: null }),

  clearGraph: () => {
    useUndoStore.getState().clear();
    set({
      graph: createGraph(),
      selectedNodeId: null,
      selectedEdgeId: null,
      entities: new Map(),
      edges: new Map(),
    });
  },

  persistPositions: (projectId) => {
    const { graph } = get();
    savePositions(projectId, graph);
  },

  performUndo: async (projectId) => {
    const action = useUndoStore.getState().undo();
    if (!action) return;
    await applyReverse(get, set, projectId, action);
  },

  performRedo: async (projectId) => {
    const action = useUndoStore.getState().redo();
    if (!action) return;
    await applyForward(get, set, projectId, action);
  },
}));

/** Apply the reverse of an action (for undo). */
async function applyReverse(
  get: () => GraphState,
  set: (partial: Partial<GraphState>) => void,
  projectId: string,
  action: UndoAction,
): Promise<void> {
  const { graph, entities, edges } = get();

  switch (action.type) {
    case "add_entity": {
      // Undo add → remove
      try { await api.entities.delete(projectId, action.entity.id); } catch { /* already gone */ }
      if (graph.hasNode(action.entity.id)) graph.dropNode(action.entity.id);
      entities.delete(action.entity.id);
      set({ graph, entities: new Map(entities) });
      break;
    }
    case "remove_entity": {
      // Undo remove → re-add entity and its edges
      const created = await api.entities.create(projectId, {
        type: action.entity.type,
        value: action.entity.value,
        properties: action.entity.properties,
      });
      // Use original ID in the graphology graph for consistency
      if (!graph.hasNode(action.entity.id)) {
        graph.addNode(action.entity.id, action.nodeAttrs);
      }
      entities.set(action.entity.id, { ...action.entity, id: created.id ?? action.entity.id });
      // Re-add connected edges
      for (const edge of action.edges) {
        if (graph.hasNode(edge.source_id) && graph.hasNode(edge.target_id)) {
          try {
            await api.edges.create(projectId, {
              source_id: edge.source_id,
              target_id: edge.target_id,
              label: edge.label,
            });
          } catch { /* skip if entities changed */ }
          if (!graph.hasEdge(edge.id)) {
            const attrs = action.edgeAttrs[edge.id] ?? { label: edge.label, size: 2, color: "#4b5563" };
            graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, attrs);
          }
          edges.set(edge.id, edge);
        }
      }
      set({ graph, entities: new Map(entities), edges: new Map(edges) });
      break;
    }
    case "add_edge": {
      // Undo add → remove
      try { await api.edges.delete(projectId, action.edge.id); } catch { /* already gone */ }
      if (graph.hasEdge(action.edge.id)) graph.dropEdge(action.edge.id);
      edges.delete(action.edge.id);
      set({ graph, edges: new Map(edges) });
      break;
    }
    case "remove_edge": {
      // Undo remove → re-add
      if (graph.hasNode(action.edge.source_id) && graph.hasNode(action.edge.target_id)) {
        try {
          await api.edges.create(projectId, {
            source_id: action.edge.source_id,
            target_id: action.edge.target_id,
            label: action.edge.label,
          });
        } catch { /* skip */ }
        if (!graph.hasEdge(action.edge.id)) {
          graph.addEdgeWithKey(action.edge.id, action.edge.source_id, action.edge.target_id, action.edgeAttrs);
        }
        edges.set(action.edge.id, action.edge);
        set({ graph, edges: new Map(edges) });
      }
      break;
    }
    case "batch": {
      // Undo batch in reverse order
      for (let i = action.actions.length - 1; i >= 0; i--) {
        await applyReverse(get, set, projectId, action.actions[i]);
      }
      break;
    }
  }
}

/** Apply an action forward (for redo). */
async function applyForward(
  get: () => GraphState,
  set: (partial: Partial<GraphState>) => void,
  projectId: string,
  action: UndoAction,
): Promise<void> {
  const { graph, entities, edges } = get();

  switch (action.type) {
    case "add_entity": {
      // Redo add → re-add
      try {
        await api.entities.create(projectId, {
          type: action.entity.type,
          value: action.entity.value,
          properties: action.entity.properties,
        });
      } catch { /* may already exist */ }
      if (!graph.hasNode(action.entity.id)) {
        graph.addNode(action.entity.id, action.nodeAttrs);
      }
      entities.set(action.entity.id, action.entity);
      set({ graph, entities: new Map(entities) });
      break;
    }
    case "remove_entity": {
      // Redo remove → remove again
      try { await api.entities.delete(projectId, action.entity.id); } catch { /* already gone */ }
      if (graph.hasNode(action.entity.id)) graph.dropNode(action.entity.id);
      entities.delete(action.entity.id);
      for (const edge of action.edges) {
        edges.delete(edge.id);
      }
      set({ graph, entities: new Map(entities), edges: new Map(edges) });
      break;
    }
    case "add_edge": {
      // Redo add → re-add
      if (graph.hasNode(action.edge.source_id) && graph.hasNode(action.edge.target_id)) {
        try {
          await api.edges.create(projectId, {
            source_id: action.edge.source_id,
            target_id: action.edge.target_id,
            label: action.edge.label,
          });
        } catch { /* may already exist */ }
        if (!graph.hasEdge(action.edge.id)) {
          graph.addEdgeWithKey(action.edge.id, action.edge.source_id, action.edge.target_id, action.edgeAttrs);
        }
        edges.set(action.edge.id, action.edge);
        set({ graph, edges: new Map(edges) });
      }
      break;
    }
    case "remove_edge": {
      // Redo remove → remove again
      try { await api.edges.delete(projectId, action.edge.id); } catch { /* already gone */ }
      if (graph.hasEdge(action.edge.id)) graph.dropEdge(action.edge.id);
      edges.delete(action.edge.id);
      set({ graph, edges: new Map(edges) });
      break;
    }
    case "batch": {
      for (const a of action.actions) {
        await applyForward(get, set, projectId, a);
      }
      break;
    }
  }
}
