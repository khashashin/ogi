import { create } from "zustand";
import Graph from "graphology";
import type { Entity } from "../types/entity";
import type { Edge } from "../types/edge";
import type { EdgeUpdate } from "../types/edge";
import { ENTITY_TYPE_META } from "../types/entity";
import { api } from "../api/client";
import { useUndoStore } from "./undoStore";
import type { UndoAction } from "./undoStore";
import { matchesEntitySearch } from "../lib/entitySearch";

export interface GraphFilterState {
  types: string[];
  tags: string[];
  sources: string[];
  dateFrom: string;
  dateTo: string;
  hideFiltered: boolean;
}

export const DEFAULT_FILTER_STATE: GraphFilterState = {
  types: [],
  tags: [],
  sources: [],
  dateFrom: "",
  dateTo: "",
  hideFiltered: true,
};

type CenterView = "graph" | "table" | "map";
export type SelectionMode = "replace" | "add" | "toggle";

interface NodePositions {
  [nodeId: string]: { x: number; y: number };
}

interface HiddenGraphState {
  entityIds: string[];
  edgeIds: string[];
}

interface PinnedGraphState {
  entityIds: string[];
}

export type GraphFocusMode = "none" | "selection" | "neighbors-1" | "neighbors-2" | "search";

export interface GraphDeclutterState {
  focusMode: GraphFocusMode;
  fadeUnselected: boolean;
  hideIsolates: boolean;
  hideLowDegree: boolean;
  lowDegreeThreshold: number;
}

const DEFAULT_DECLUTTER_STATE: GraphDeclutterState = {
  focusMode: "none",
  fadeUnselected: false,
  hideIsolates: false,
  hideLowDegree: false,
  lowDegreeThreshold: 1,
};

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

function loadFilters(projectId: string): GraphFilterState {
  try {
    const raw = localStorage.getItem(`ogi-filters-${projectId}`);
    if (!raw) return { ...DEFAULT_FILTER_STATE };
    const parsed = JSON.parse(raw) as Partial<GraphFilterState>;
    return {
      ...DEFAULT_FILTER_STATE,
      ...parsed,
      types: Array.isArray(parsed.types) ? parsed.types : [],
      tags: Array.isArray(parsed.tags) ? parsed.tags : [],
      sources: Array.isArray(parsed.sources) ? parsed.sources : [],
    };
  } catch {
    return { ...DEFAULT_FILTER_STATE };
  }
}

function saveFilters(projectId: string, filters: GraphFilterState): void {
  localStorage.setItem(`ogi-filters-${projectId}`, JSON.stringify(filters));
}

function loadHiddenGraphState(projectId: string): HiddenGraphState {
  try {
    const raw = localStorage.getItem(`ogi-hidden-${projectId}`);
    if (!raw) return { entityIds: [], edgeIds: [] };
    const parsed = JSON.parse(raw) as Partial<HiddenGraphState>;
    return {
      entityIds: Array.isArray(parsed.entityIds) ? parsed.entityIds : [],
      edgeIds: Array.isArray(parsed.edgeIds) ? parsed.edgeIds : [],
    };
  } catch {
    return { entityIds: [], edgeIds: [] };
  }
}

function saveHiddenGraphState(projectId: string, state: HiddenGraphState): void {
  localStorage.setItem(`ogi-hidden-${projectId}`, JSON.stringify(state));
}

function loadPinnedGraphState(projectId: string): PinnedGraphState {
  try {
    const raw = localStorage.getItem(`ogi-pinned-${projectId}`);
    if (!raw) return { entityIds: [] };
    const parsed = JSON.parse(raw) as Partial<PinnedGraphState>;
    return {
      entityIds: Array.isArray(parsed.entityIds) ? parsed.entityIds : [],
    };
  } catch {
    return { entityIds: [] };
  }
}

function savePinnedGraphState(projectId: string, state: PinnedGraphState): void {
  localStorage.setItem(`ogi-pinned-${projectId}`, JSON.stringify(state));
}

function loadDeclutterState(projectId: string): GraphDeclutterState {
  try {
    const raw = localStorage.getItem(`ogi-declutter-${projectId}`);
    if (!raw) return { ...DEFAULT_DECLUTTER_STATE };
    const parsed = JSON.parse(raw) as Partial<GraphDeclutterState>;
    return {
      ...DEFAULT_DECLUTTER_STATE,
      ...parsed,
      focusMode:
        parsed.focusMode === "selection" ||
        parsed.focusMode === "neighbors-1" ||
        parsed.focusMode === "neighbors-2" ||
        parsed.focusMode === "search"
          ? parsed.focusMode
          : "none",
      lowDegreeThreshold:
        typeof parsed.lowDegreeThreshold === "number" && parsed.lowDegreeThreshold >= 0
          ? parsed.lowDegreeThreshold
          : 1,
    };
  } catch {
    return { ...DEFAULT_DECLUTTER_STATE };
  }
}

function saveDeclutterState(projectId: string, state: GraphDeclutterState): void {
  localStorage.setItem(`ogi-declutter-${projectId}`, JSON.stringify(state));
}

function computeFilteredHiddenNodeIds(
  entities: Map<string, Entity>,
  filters: GraphFilterState,
): Set<string> {
  if (!filters.hideFiltered) return new Set();

  const hidden = new Set<string>();
  const from = filters.dateFrom ? Date.parse(filters.dateFrom) : NaN;
  const to = filters.dateTo ? Date.parse(filters.dateTo) : NaN;

  for (const [id, entity] of entities.entries()) {
    let visible = true;

    if (filters.types.length > 0 && !filters.types.includes(entity.type)) visible = false;
    if (visible && filters.sources.length > 0 && !filters.sources.includes(entity.source)) visible = false;
    if (
      visible &&
      filters.tags.length > 0 &&
      !filters.tags.some((tag) => entity.tags.includes(tag))
    ) {
      visible = false;
    }

    if (visible && !Number.isNaN(from)) {
      const created = Date.parse(entity.created_at);
      if (Number.isFinite(created) && created < from) visible = false;
    }
    if (visible && !Number.isNaN(to)) {
      const created = Date.parse(entity.created_at);
      if (Number.isFinite(created) && created > to) visible = false;
    }

    if (!visible) hidden.add(id);
  }

  return hidden;
}

function computeFocusVisibleNodeIds(
  graph: Graph,
  entities: Map<string, Entity>,
  selectedNodeIds: Set<string>,
  searchQuery: string,
  focusMode: GraphFocusMode,
): Set<string> | null {
  if (focusMode === "none") return null;

  if (focusMode === "search") {
    if (!searchQuery.trim()) return null;
    const visible = new Set<string>();
    for (const [id, entity] of entities.entries()) {
      if (matchesEntitySearch(entity, searchQuery)) visible.add(id);
    }
    return visible;
  }

  if (selectedNodeIds.size === 0) return null;

  if (focusMode === "selection") {
    return new Set(selectedNodeIds);
  }

  const visible = new Set<string>(selectedNodeIds);
  const queue = [...selectedNodeIds].map((id) => ({ id, depth: 0 }));
  const maxDepth = focusMode === "neighbors-2" ? 2 : 1;

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || current.depth >= maxDepth || !graph.hasNode(current.id)) continue;
    for (const neighbor of graph.neighbors(current.id)) {
      if (!visible.has(neighbor)) {
        visible.add(neighbor);
        queue.push({ id: neighbor, depth: current.depth + 1 });
      }
    }
  }

  return visible;
}

function computeDerivedHiddenNodeIds(
  graph: Graph,
  entities: Map<string, Entity>,
  baseHiddenNodeIds: Set<string>,
  selectedNodeIds: Set<string>,
  searchQuery: string,
  declutterState: GraphDeclutterState,
): Set<string> {
  const hidden = new Set<string>();
  const focusVisibleNodeIds = computeFocusVisibleNodeIds(
    graph,
    entities,
    selectedNodeIds,
    searchQuery,
    declutterState.focusMode,
  );

  for (const id of entities.keys()) {
    if (baseHiddenNodeIds.has(id)) continue;
    if (focusVisibleNodeIds && !focusVisibleNodeIds.has(id)) hidden.add(id);
  }

  const visibleAfterFocus = new Set<string>();
  for (const id of entities.keys()) {
    if (!baseHiddenNodeIds.has(id) && !hidden.has(id)) visibleAfterFocus.add(id);
  }

  if (declutterState.hideIsolates || declutterState.hideLowDegree) {
    const threshold = declutterState.hideLowDegree ? Math.max(0, declutterState.lowDegreeThreshold) : 0;
    const preserveIds = new Set<string>(selectedNodeIds);
    if (focusVisibleNodeIds) {
      for (const id of focusVisibleNodeIds) preserveIds.add(id);
    }
    if (declutterState.focusMode === "search" && searchQuery.trim()) {
      for (const [id, entity] of entities.entries()) {
        if (matchesEntitySearch(entity, searchQuery)) preserveIds.add(id);
      }
    }

    for (const id of visibleAfterFocus) {
      if (preserveIds.has(id)) continue;
      let degree = 0;
      if (graph.hasNode(id)) {
        for (const neighbor of graph.neighbors(id)) {
          if (visibleAfterFocus.has(neighbor)) degree += 1;
        }
      }
      if (declutterState.hideIsolates && degree === 0) {
        hidden.add(id);
        continue;
      }
      if (declutterState.hideLowDegree && degree <= threshold) {
        hidden.add(id);
      }
    }
  }

  return hidden;
}

function computeHiddenNodeIds(
  graph: Graph,
  entities: Map<string, Entity>,
  filters: GraphFilterState,
  manualHiddenNodeIds: Set<string>,
  selectedNodeIds: Set<string>,
  searchQuery: string,
  declutterState: GraphDeclutterState,
): Set<string> {
  const hidden = computeFilteredHiddenNodeIds(entities, filters);
  for (const id of manualHiddenNodeIds) hidden.add(id);
  const derivedHidden = computeDerivedHiddenNodeIds(
    graph,
    entities,
    hidden,
    selectedNodeIds,
    searchQuery,
    declutterState,
  );
  for (const id of derivedHidden) hidden.add(id);
  return hidden;
}

function computeHiddenEdgeIds(
  edges: Map<string, Edge>,
  hiddenNodeIds: Set<string>,
  manualHiddenEdgeIds: Set<string>,
): Set<string> {
  const hidden = new Set<string>(manualHiddenEdgeIds);
  for (const [id, edge] of edges.entries()) {
    if (hiddenNodeIds.has(edge.source_id) || hiddenNodeIds.has(edge.target_id)) {
      hidden.add(id);
    }
  }
  return hidden;
}

/** Visual overlays that temporarily override node rendering in the graph canvas. */
interface SearchOverlay {
  type: "search";
  matchIds: Set<string>;
  focusId: string | null;
}

interface AnalysisScoresOverlay {
  type: "analysis-scores";
  scores: Record<string, number>;
  maxScore: number;
}

interface AnalysisCommunitiesOverlay {
  type: "analysis-communities";
  colors: Record<string, string>;
}

export type NodeOverlay =
  | SearchOverlay
  | AnalysisScoresOverlay
  | AnalysisCommunitiesOverlay;

export interface AnalysisResults {
  type: "scores" | "communities";
  scores?: Record<string, number>;
  communities?: string[][];
}

interface GraphState {
  graph: Graph;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  selectedNodeIds: Set<string>;
  pinnedNodeIds: Set<string>;
  entities: Map<string, Entity>;
  edges: Map<string, Edge>;
  manualHiddenNodeIds: Set<string>;
  manualHiddenEdgeIds: Set<string>;
  hiddenNodeIds: Set<string>;
  hiddenEdgeIds: Set<string>;
  filterState: GraphFilterState;
  declutterState: GraphDeclutterState;
  searchQuery: string;
  centerView: CenterView;
  currentProjectId: string | null;
  loading: boolean;
  error: string | null;
  nodeOverlay: NodeOverlay | null;
  analysisResults: AnalysisResults | null;

  loadGraph: (projectId: string) => Promise<void>;
  loadGraphWindow: (projectId: string, fromTs?: string, toTs?: string) => Promise<void>;
  addEntity: (projectId: string, entity: Entity) => void;
  removeEntity: (projectId: string, entityId: string) => Promise<void>;
  addEdge: (projectId: string, edge: Edge) => void;
  removeEdge: (projectId: string, edgeId: string) => Promise<void>;
  updateEdge: (projectId: string, edgeId: string, data: EdgeUpdate) => Promise<Edge | null>;
  selectNode: (nodeId: string | null, mode?: SelectionMode) => void;
  selectNodes: (nodeIds: string[], mode?: SelectionMode) => void;
  selectEdge: (edgeId: string | null) => void;
  clearSelection: () => void;
  pinNode: (projectId: string, nodeId: string) => void;
  unpinNode: (projectId: string, nodeId: string) => void;
  pinSelected: (projectId: string) => void;
  unpinSelected: (projectId: string) => void;
  pinVisible: (projectId: string) => void;
  unpinAll: (projectId: string) => void;
  hideNode: (projectId: string, nodeId: string) => void;
  hideEdge: (projectId: string, edgeId: string) => void;
  hideConnectedEdges: (projectId: string, nodeId: string) => void;
  hideSelected: (projectId: string) => void;
  unhideNode: (projectId: string, nodeId: string) => void;
  unhideEdge: (projectId: string, edgeId: string) => void;
  unhideAll: (projectId: string) => void;
  setFocusMode: (projectId: string, mode: GraphFocusMode) => void;
  setFadeUnselected: (projectId: string, enabled: boolean) => void;
  setHideIsolates: (projectId: string, enabled: boolean) => void;
  setHideLowDegree: (projectId: string, enabled: boolean, threshold?: number) => void;
  clearDeclutterState: (projectId: string) => void;
  setSearchQuery: (query: string) => void;
  setFilterState: (projectId: string, patch: Partial<GraphFilterState>) => void;
  resetFilters: (projectId: string) => void;
  setCenterView: (view: CenterView) => void;
  setNodeOverlay: (overlay: NodeOverlay | null) => void;
  setAnalysisResults: (results: AnalysisResults | null) => void;
  clearGraph: () => void;
  persistPositions: (projectId: string) => void;
  recordNodeMove: (
    projectId: string,
    positionsBefore: Record<string, { x: number; y: number }>,
    positionsAfter: Record<string, { x: number; y: number }>,
  ) => void;
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
  selectedNodeIds: new Set(),
  pinnedNodeIds: new Set(),
  entities: new Map(),
  edges: new Map(),
  manualHiddenNodeIds: new Set(),
  manualHiddenEdgeIds: new Set(),
  hiddenNodeIds: new Set(),
  hiddenEdgeIds: new Set(),
  filterState: { ...DEFAULT_FILTER_STATE },
  declutterState: { ...DEFAULT_DECLUTTER_STATE },
  searchQuery: "",
  centerView: "graph",
  currentProjectId: null,
  loading: false,
  error: null,
  nodeOverlay: null,
  analysisResults: null,

  loadGraph: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const data = await api.graph.get(projectId, true);
      const graph = createGraph();
      const entities = new Map<string, Entity>();
      const edges = new Map<string, Edge>();
      const savedPositions = loadPositions(projectId);
      const filterState = loadFilters(projectId);
      const hiddenState = loadHiddenGraphState(projectId);
      const pinnedState = loadPinnedGraphState(projectId);
      const declutterState = loadDeclutterState(projectId);

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
            size: 3,
            color: "#4b5563",
          });
          edges.set(edge.id, edge);
        }
      }

      const manualHiddenNodeIds = new Set(hiddenState.entityIds.filter((id) => entities.has(id)));
      const manualHiddenEdgeIds = new Set(hiddenState.edgeIds.filter((id) => edges.has(id)));
      const pinnedNodeIds = new Set(pinnedState.entityIds.filter((id) => entities.has(id)));
      const hiddenNodeIds = computeHiddenNodeIds(
        graph,
        entities,
        filterState,
        manualHiddenNodeIds,
        new Set(),
        "",
        declutterState,
      );
      const hiddenEdgeIds = computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds);
      set({
        graph,
        pinnedNodeIds,
        entities,
        edges,
        manualHiddenNodeIds,
        manualHiddenEdgeIds,
        hiddenNodeIds,
        hiddenEdgeIds,
        filterState,
        declutterState,
        currentProjectId: projectId,
        loading: false,
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedNodeIds: new Set(),
        searchQuery: "",
        nodeOverlay: null,
        analysisResults: null,
      });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  loadGraphWindow: async (projectId, fromTs, toTs) => {
    set({ loading: true, error: null });
    try {
      const data = await api.graph.window(projectId, fromTs, toTs);
      const graph = createGraph();
      const entities = new Map<string, Entity>();
      const edges = new Map<string, Edge>();
      const savedPositions = loadPositions(projectId);
      const filterState = get().filterState;
      const hiddenState = loadHiddenGraphState(projectId);
      const pinnedState = loadPinnedGraphState(projectId);
      const declutterState = loadDeclutterState(projectId);

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
            size: 3,
            color: "#4b5563",
          });
          edges.set(edge.id, edge);
        }
      }

      const manualHiddenNodeIds = new Set(hiddenState.entityIds.filter((id) => entities.has(id)));
      const manualHiddenEdgeIds = new Set(hiddenState.edgeIds.filter((id) => edges.has(id)));
      const pinnedNodeIds = new Set(pinnedState.entityIds.filter((id) => entities.has(id)));
      const hiddenNodeIds = computeHiddenNodeIds(
        graph,
        entities,
        filterState,
        manualHiddenNodeIds,
        get().selectedNodeIds,
        get().searchQuery,
        declutterState,
      );
      const hiddenEdgeIds = computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds);
      set({
        graph,
        pinnedNodeIds,
        entities,
        edges,
        manualHiddenNodeIds,
        manualHiddenEdgeIds,
        hiddenNodeIds,
        hiddenEdgeIds,
        declutterState,
        currentProjectId: projectId,
        loading: false,
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedNodeIds: new Set(),
        searchQuery: "",
        nodeOverlay: null,
      });
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
    const { filterState, manualHiddenNodeIds, manualHiddenEdgeIds, edges, selectedNodeIds, searchQuery, declutterState } = get();
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      entities,
      filterState,
      manualHiddenNodeIds,
      selectedNodeIds,
      searchQuery,
      declutterState,
    );
    set({
      graph,
      entities: new Map(entities),
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds),
    });
  },

  removeEntity: async (projectId, entityId) => {
    const { graph, entities, edges, manualHiddenNodeIds, manualHiddenEdgeIds } = get();
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

    const nextPinnedNodeIds = new Set([...get().pinnedNodeIds].filter((id) => id !== entityId));
    savePinnedGraphState(projectId, { entityIds: [...nextPinnedNodeIds] });
    const nextSelectedNodeIds = new Set([...get().selectedNodeIds].filter((id) => id !== entityId));
    const nextSelectedNodeId =
      get().selectedNodeId === entityId ? (nextSelectedNodeIds.values().next().value ?? null) : get().selectedNodeId;
    set({
      graph,
      entities: new Map(entities),
      edges: new Map(edges),
      pinnedNodeIds: nextPinnedNodeIds,
      manualHiddenNodeIds: new Set([...manualHiddenNodeIds].filter((id) => id !== entityId)),
      hiddenNodeIds: computeHiddenNodeIds(
        graph,
        entities,
        get().filterState,
        new Set([...manualHiddenNodeIds].filter((id) => id !== entityId)),
        nextSelectedNodeIds,
        get().searchQuery,
        get().declutterState,
      ),
      hiddenEdgeIds: computeHiddenEdgeIds(
        edges,
        computeHiddenNodeIds(
          graph,
          entities,
          get().filterState,
          new Set([...manualHiddenNodeIds].filter((id) => id !== entityId)),
          nextSelectedNodeIds,
          get().searchQuery,
          get().declutterState,
        ),
        new Set([...manualHiddenEdgeIds].filter((id) => edges.has(id))),
      ),
      selectedNodeId: nextSelectedNodeId,
      selectedNodeIds: nextSelectedNodeIds,
    });
  },

  addEdge: (_projectId, edge) => {
    const { graph, edges } = get();
    const edgeAttrs = { label: edge.label, size: 3, color: "#4b5563" };
    if (
      graph.hasNode(edge.source_id) &&
      graph.hasNode(edge.target_id) &&
      !graph.hasEdge(edge.id)
    ) {
      graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, edgeAttrs);
    }
    edges.set(edge.id, edge);
    useUndoStore.getState().push({ type: "add_edge", edge, edgeAttrs });
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      get().entities,
      get().filterState,
      get().manualHiddenNodeIds,
      get().selectedNodeIds,
      get().searchQuery,
      get().declutterState,
    );
    set({
      graph,
      edges: new Map(edges),
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, get().manualHiddenEdgeIds),
    });
  },

  removeEdge: async (projectId, edgeId) => {
    const { graph, edges, manualHiddenEdgeIds } = get();
    const edge = edges.get(edgeId);
    if (!edge) return;

    const edgeAttrs = graph.hasEdge(edgeId) ? graph.getEdgeAttributes(edgeId) : {};
    await api.edges.delete(projectId, edgeId);
    if (graph.hasEdge(edgeId)) {
      graph.dropEdge(edgeId);
    }
    edges.delete(edgeId);
    useUndoStore.getState().push({ type: "remove_edge", edge, edgeAttrs });
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      get().entities,
      get().filterState,
      get().manualHiddenNodeIds,
      get().selectedNodeIds,
      get().searchQuery,
      get().declutterState,
    );
    set({
      graph,
      edges: new Map(edges),
      manualHiddenEdgeIds: new Set([...manualHiddenEdgeIds].filter((id) => id !== edgeId)),
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, new Set([...manualHiddenEdgeIds].filter((id) => id !== edgeId))),
    });
  },

  updateEdge: async (projectId, edgeId, data) => {
    const { graph, edges } = get();
    const existing = edges.get(edgeId);
    if (!existing) return null;

    const updated = await api.edges.update(projectId, edgeId, data);
    edges.set(edgeId, updated);

    if (graph.hasEdge(edgeId)) {
      graph.setEdgeAttribute(edgeId, "label", updated.label);
      if (typeof updated.weight === "number") {
        graph.setEdgeAttribute(edgeId, "size", Math.max(1, updated.weight));
      }
    }

    set({ graph, edges: new Map(edges) });
    return updated;
  },

  selectNode: (nodeId, mode = "replace") =>
    set((state) => {
      if (nodeId === null) {
        const selectedNodeIds = new Set<string>();
        const hiddenNodeIds = computeHiddenNodeIds(
          state.graph,
          state.entities,
          state.filterState,
          state.manualHiddenNodeIds,
          selectedNodeIds,
          state.searchQuery,
          state.declutterState,
        );
        return {
          selectedNodeId: null,
          selectedEdgeId: null,
          selectedNodeIds,
          hiddenNodeIds,
          hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
        };
      }
      const next = mode === "replace" ? new Set<string>() : new Set(state.selectedNodeIds);
      if (mode === "toggle") {
        if (next.has(nodeId)) next.delete(nodeId);
        else next.add(nodeId);
      } else {
        next.add(nodeId);
      }
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        next,
        state.searchQuery,
        state.declutterState,
      );
      return {
        selectedNodeId: next.has(nodeId) ? nodeId : (next.values().next().value ?? null),
        selectedEdgeId: null,
        selectedNodeIds: next,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  selectNodes: (nodeIds, mode = "replace") =>
    set((state) => {
      const next = mode === "replace" ? new Set<string>() : new Set(state.selectedNodeIds);
      if (mode === "toggle") {
        for (const id of nodeIds) {
          if (next.has(id)) next.delete(id);
          else next.add(id);
        }
      } else {
        for (const id of nodeIds) next.add(id);
      }
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        next,
        state.searchQuery,
        state.declutterState,
      );
      return {
        selectedNodeId: next.values().next().value ?? null,
        selectedEdgeId: null,
        selectedNodeIds: next,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  selectEdge: (edgeId) =>
    set((state) => {
      const selectedNodeIds = new Set<string>();
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        selectedNodeIds,
        state.searchQuery,
        state.declutterState,
      );
      return {
        selectedEdgeId: edgeId,
        selectedNodeId: null,
        selectedNodeIds,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  clearSelection: () =>
    set((state) => {
      const selectedNodeIds = new Set<string>();
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        selectedNodeIds,
        state.searchQuery,
        state.declutterState,
      );
      return {
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedNodeIds,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  pinNode: (projectId, nodeId) => {
    const { entities, pinnedNodeIds } = get();
    if (!entities.has(nodeId)) return;
    const next = new Set(pinnedNodeIds).add(nodeId);
    savePinnedGraphState(projectId, { entityIds: [...next] });
    set({ pinnedNodeIds: next });
  },
  unpinNode: (projectId, nodeId) => {
    const next = new Set([...get().pinnedNodeIds].filter((id) => id !== nodeId));
    savePinnedGraphState(projectId, { entityIds: [...next] });
    set({ pinnedNodeIds: next });
  },
  pinSelected: (projectId) => {
    const next = new Set(get().pinnedNodeIds);
    for (const id of get().selectedNodeIds) next.add(id);
    savePinnedGraphState(projectId, { entityIds: [...next] });
    set({ pinnedNodeIds: next });
  },
  unpinSelected: (projectId) => {
    const selected = get().selectedNodeIds;
    const next = new Set([...get().pinnedNodeIds].filter((id) => !selected.has(id)));
    savePinnedGraphState(projectId, { entityIds: [...next] });
    set({ pinnedNodeIds: next });
  },
  pinVisible: (projectId) => {
    const next = new Set(get().pinnedNodeIds);
    for (const id of get().entities.keys()) {
      if (!get().hiddenNodeIds.has(id)) next.add(id);
    }
    savePinnedGraphState(projectId, { entityIds: [...next] });
    set({ pinnedNodeIds: next });
  },
  unpinAll: (projectId) => {
    savePinnedGraphState(projectId, { entityIds: [] });
    set({ pinnedNodeIds: new Set() });
  },
  hideNode: (projectId, nodeId) => {
    const { graph, entities, edges, filterState, manualHiddenNodeIds, manualHiddenEdgeIds, searchQuery, declutterState } = get();
    if (!entities.has(nodeId)) return;
    const nextManualHiddenNodeIds = new Set(manualHiddenNodeIds).add(nodeId);
    const nextSelectedNodeIds = new Set([...get().selectedNodeIds].filter((id) => id !== nodeId));
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      entities,
      filterState,
      nextManualHiddenNodeIds,
      nextSelectedNodeIds,
      searchQuery,
      declutterState,
    );
    const hiddenEdgeIds = computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds);
    saveHiddenGraphState(projectId, {
      entityIds: [...nextManualHiddenNodeIds],
      edgeIds: [...manualHiddenEdgeIds],
    });
    const nextSelectedNodeId =
      get().selectedNodeId === nodeId ? (nextSelectedNodeIds.values().next().value ?? null) : get().selectedNodeId;
    set({
      manualHiddenNodeIds: nextManualHiddenNodeIds,
      hiddenNodeIds,
      hiddenEdgeIds,
      selectedNodeId: nextSelectedNodeId,
      selectedNodeIds: nextSelectedNodeIds,
    });
  },
  hideEdge: (projectId, edgeId) => {
    const { edges, hiddenNodeIds, manualHiddenNodeIds, manualHiddenEdgeIds } = get();
    if (!edges.has(edgeId)) return;
    const nextManualHiddenEdgeIds = new Set(manualHiddenEdgeIds).add(edgeId);
    saveHiddenGraphState(projectId, {
      entityIds: [...manualHiddenNodeIds],
      edgeIds: [...nextManualHiddenEdgeIds],
    });
    set({
      manualHiddenEdgeIds: nextManualHiddenEdgeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, nextManualHiddenEdgeIds),
      selectedEdgeId: get().selectedEdgeId === edgeId ? null : get().selectedEdgeId,
    });
  },
  hideConnectedEdges: (projectId, nodeId) => {
    const { edges, hiddenNodeIds, manualHiddenNodeIds, manualHiddenEdgeIds } = get();
    const nextManualHiddenEdgeIds = new Set(manualHiddenEdgeIds);
    for (const edge of edges.values()) {
      if (edge.source_id === nodeId || edge.target_id === nodeId) {
        nextManualHiddenEdgeIds.add(edge.id);
      }
    }
    saveHiddenGraphState(projectId, {
      entityIds: [...manualHiddenNodeIds],
      edgeIds: [...nextManualHiddenEdgeIds],
    });
    set({
      manualHiddenEdgeIds: nextManualHiddenEdgeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, nextManualHiddenEdgeIds),
    });
  },
  hideSelected: (projectId) => {
    const selectedNodeIds = [...get().selectedNodeIds];
    const { selectedEdgeId } = get();
    if (selectedNodeIds.length > 0) {
      for (const id of selectedNodeIds) {
        get().hideNode(projectId, id);
      }
      return;
    }
    if (selectedEdgeId) {
      get().hideEdge(projectId, selectedEdgeId);
    }
  },
  unhideNode: (projectId, nodeId) => {
    const { graph, entities, edges, filterState, manualHiddenNodeIds, manualHiddenEdgeIds, selectedNodeIds, searchQuery, declutterState } = get();
    const nextManualHiddenNodeIds = new Set([...manualHiddenNodeIds].filter((id) => id !== nodeId));
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      entities,
      filterState,
      nextManualHiddenNodeIds,
      selectedNodeIds,
      searchQuery,
      declutterState,
    );
    const hiddenEdgeIds = computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds);
    saveHiddenGraphState(projectId, {
      entityIds: [...nextManualHiddenNodeIds],
      edgeIds: [...manualHiddenEdgeIds],
    });
    set({
      manualHiddenNodeIds: nextManualHiddenNodeIds,
      hiddenNodeIds,
      hiddenEdgeIds,
    });
  },
  unhideEdge: (projectId, edgeId) => {
    const { edges, hiddenNodeIds, manualHiddenNodeIds, manualHiddenEdgeIds } = get();
    const nextManualHiddenEdgeIds = new Set([...manualHiddenEdgeIds].filter((id) => id !== edgeId));
    saveHiddenGraphState(projectId, {
      entityIds: [...manualHiddenNodeIds],
      edgeIds: [...nextManualHiddenEdgeIds],
    });
    set({
      manualHiddenEdgeIds: nextManualHiddenEdgeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, nextManualHiddenEdgeIds),
    });
  },
  unhideAll: (projectId) => {
    const { graph, entities, edges, filterState, selectedNodeIds, searchQuery, declutterState } = get();
    const manualHiddenNodeIds = new Set<string>();
    const manualHiddenEdgeIds = new Set<string>();
    saveHiddenGraphState(projectId, { entityIds: [], edgeIds: [] });
    const hiddenNodeIds = computeHiddenNodeIds(
      graph,
      entities,
      filterState,
      manualHiddenNodeIds,
      selectedNodeIds,
      searchQuery,
      declutterState,
    );
    set({
      manualHiddenNodeIds,
      manualHiddenEdgeIds,
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(edges, hiddenNodeIds, manualHiddenEdgeIds),
    });
  },
  setFocusMode: (projectId, mode) =>
    set((state) => {
      const declutterState = { ...state.declutterState, focusMode: mode };
      saveDeclutterState(projectId, declutterState);
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        state.selectedNodeIds,
        state.searchQuery,
        declutterState,
      );
      return {
        declutterState,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  setFadeUnselected: (projectId, enabled) =>
    set((state) => {
      const declutterState = { ...state.declutterState, fadeUnselected: enabled };
      saveDeclutterState(projectId, declutterState);
      return { declutterState };
    }),
  setHideIsolates: (projectId, enabled) =>
    set((state) => {
      const declutterState = { ...state.declutterState, hideIsolates: enabled };
      saveDeclutterState(projectId, declutterState);
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        state.selectedNodeIds,
        state.searchQuery,
        declutterState,
      );
      return {
        declutterState,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  setHideLowDegree: (projectId, enabled, threshold) =>
    set((state) => {
      const declutterState = {
        ...state.declutterState,
        hideLowDegree: enabled,
        lowDegreeThreshold:
          typeof threshold === "number" ? Math.max(0, Math.floor(threshold)) : state.declutterState.lowDegreeThreshold,
      };
      saveDeclutterState(projectId, declutterState);
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        state.selectedNodeIds,
        state.searchQuery,
        declutterState,
      );
      return {
        declutterState,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  clearDeclutterState: (projectId) =>
    set((state) => {
      const declutterState = { ...DEFAULT_DECLUTTER_STATE };
      saveDeclutterState(projectId, declutterState);
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        state.selectedNodeIds,
        state.searchQuery,
        declutterState,
      );
      return {
        declutterState,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  setSearchQuery: (query) =>
    set((state) => {
      const hiddenNodeIds = computeHiddenNodeIds(
        state.graph,
        state.entities,
        state.filterState,
        state.manualHiddenNodeIds,
        state.selectedNodeIds,
        query,
        state.declutterState,
      );
      return {
        searchQuery: query,
        hiddenNodeIds,
        hiddenEdgeIds: computeHiddenEdgeIds(state.edges, hiddenNodeIds, state.manualHiddenEdgeIds),
      };
    }),
  setFilterState: (projectId, patch) => {
    const nextFilterState = { ...get().filterState, ...patch };
    saveFilters(projectId, nextFilterState);
    const hiddenNodeIds = computeHiddenNodeIds(
      get().graph,
      get().entities,
      nextFilterState,
      get().manualHiddenNodeIds,
      get().selectedNodeIds,
      get().searchQuery,
      get().declutterState,
    );
    set({
      filterState: nextFilterState,
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(get().edges, hiddenNodeIds, get().manualHiddenEdgeIds),
    });
  },
  resetFilters: (projectId) => {
    const nextFilterState = { ...DEFAULT_FILTER_STATE };
    saveFilters(projectId, nextFilterState);
    const hiddenNodeIds = computeHiddenNodeIds(
      get().graph,
      get().entities,
      nextFilterState,
      get().manualHiddenNodeIds,
      get().selectedNodeIds,
      get().searchQuery,
      get().declutterState,
    );
    set({
      filterState: nextFilterState,
      hiddenNodeIds,
      hiddenEdgeIds: computeHiddenEdgeIds(get().edges, hiddenNodeIds, get().manualHiddenEdgeIds),
    });
  },
  setCenterView: (view) => set({ centerView: view }),
  setNodeOverlay: (overlay) => set({ nodeOverlay: overlay }),
  setAnalysisResults: (results) => set({ analysisResults: results }),

  clearGraph: () => {
    useUndoStore.getState().clear();
    set({
      graph: createGraph(),
      selectedNodeId: null,
      selectedEdgeId: null,
      selectedNodeIds: new Set(),
      pinnedNodeIds: new Set(),
      entities: new Map(),
      edges: new Map(),
      manualHiddenNodeIds: new Set(),
      manualHiddenEdgeIds: new Set(),
      hiddenNodeIds: new Set(),
      hiddenEdgeIds: new Set(),
      filterState: { ...DEFAULT_FILTER_STATE },
      declutterState: { ...DEFAULT_DECLUTTER_STATE },
      searchQuery: "",
      centerView: "graph",
      currentProjectId: null,
      nodeOverlay: null,
      analysisResults: null,
    });
  },

  persistPositions: (projectId) => {
    const { graph } = get();
    savePositions(projectId, graph);
  },

  recordNodeMove: (projectId, positionsBefore, positionsAfter) => {
    const nodeIds = Object.keys(positionsAfter);
    if (nodeIds.length === 0) return;

    const changedNodeIds = nodeIds.filter((nodeId) => {
      const before = positionsBefore[nodeId];
      const after = positionsAfter[nodeId];
      return before && after && (before.x !== after.x || before.y !== after.y);
    });

    if (changedNodeIds.length === 0) return;

    const beforeFiltered = Object.fromEntries(
      changedNodeIds.map((nodeId) => [nodeId, positionsBefore[nodeId]]),
    );
    const afterFiltered = Object.fromEntries(
      changedNodeIds.map((nodeId) => [nodeId, positionsAfter[nodeId]]),
    );

    useUndoStore.getState().push({
      type: "move_nodes",
      positionsBefore: beforeFiltered,
      positionsAfter: afterFiltered,
    });
    savePositions(projectId, get().graph);
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
    case "move_nodes": {
      for (const [nodeId, position] of Object.entries(action.positionsBefore)) {
        if (!graph.hasNode(nodeId)) continue;
        graph.setNodeAttribute(nodeId, "x", position.x);
        graph.setNodeAttribute(nodeId, "y", position.y);
      }
      savePositions(projectId, graph);
      set({ graph });
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
    case "move_nodes": {
      for (const [nodeId, position] of Object.entries(action.positionsAfter)) {
        if (!graph.hasNode(nodeId)) continue;
        graph.setNodeAttribute(nodeId, "x", position.x);
        graph.setNodeAttribute(nodeId, "y", position.y);
      }
      savePositions(projectId, graph);
      set({ graph });
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
