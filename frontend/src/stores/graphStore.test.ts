import { beforeEach, describe, expect, it } from "vitest";
import Graph from "graphology";

import { EntityType, type Entity } from "../types/entity";
import { DEFAULT_FILTER_STATE, useGraphStore } from "./graphStore";
import type { Edge } from "../types/edge";

function makeEntity(id: string, overrides: Partial<Entity> = {}): Entity {
  return {
    id,
    type: EntityType.Domain,
    value: `${id}.example.org`,
    properties: {},
    icon: "globe",
    weight: 1,
    notes: "",
    tags: [],
    source: "manual",
    origin_source: "manual",
    project_id: "p-1",
    created_at: "2026-03-03T10:00:00Z",
    updated_at: "2026-03-03T10:00:00Z",
    ...overrides,
  };
}

function makeEdge(id: string, sourceId: string, targetId: string): Edge {
  return {
    id,
    source_id: sourceId,
    target_id: targetId,
    label: "related",
    weight: 1,
    properties: {},
    bidirectional: false,
    source_transform: "manual",
    project_id: "p-1",
    created_at: "2026-03-03T10:00:00Z",
  };
}

function makeGraph(entities: Entity[], edges: Edge[] = []) {
  const graph = new Graph({ multi: true, type: "directed" });
  for (const entity of entities) {
    graph.addNode(entity.id, { x: 0, y: 0, size: 8, color: "#6366f1", label: entity.value });
  }
  for (const edge of edges) {
    graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, { label: edge.label });
  }
  return graph;
}

describe("graphStore filters", () => {
  beforeEach(() => {
    localStorage.clear();
    useGraphStore.getState().clearGraph();
  });

  it("hides non-matching entities when type filter is active", () => {
    const domain = makeEntity("e-domain", { type: EntityType.Domain });
    const ip = makeEntity("e-ip", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [domain.id, domain],
        [ip.id, ip],
      ]),
    });

    useGraphStore.getState().setFilterState("p-1", { types: [EntityType.Domain] });
    const state = useGraphStore.getState();

    expect(state.hiddenNodeIds.has(domain.id)).toBe(false);
    expect(state.hiddenNodeIds.has(ip.id)).toBe(true);
  });

  it("applies tag/source/date filters together", () => {
    const matching = makeEntity("e-match", {
      tags: ["important"],
      source: "whois_lookup",
      created_at: "2026-02-01T00:00:00Z",
    });
    const wrongSource = makeEntity("e-source", {
      tags: ["important"],
      source: "manual",
      created_at: "2026-02-01T00:00:00Z",
    });
    const wrongDate = makeEntity("e-date", {
      tags: ["important"],
      source: "whois_lookup",
      created_at: "2025-01-01T00:00:00Z",
    });

    useGraphStore.setState({
      entities: new Map([
        [matching.id, matching],
        [wrongSource.id, wrongSource],
        [wrongDate.id, wrongDate],
      ]),
    });

    useGraphStore.getState().setFilterState("p-1", {
      tags: ["important"],
      sources: ["whois_lookup"],
      dateFrom: "2026-01-01",
      dateTo: "2026-12-31",
    });
    const state = useGraphStore.getState();

    expect(state.hiddenNodeIds.has(matching.id)).toBe(false);
    expect(state.hiddenNodeIds.has(wrongSource.id)).toBe(true);
    expect(state.hiddenNodeIds.has(wrongDate.id)).toBe(true);
  });

  it("shows all entities when hideFiltered is false", () => {
    const domain = makeEntity("e-domain", { type: EntityType.Domain });
    const ip = makeEntity("e-ip", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [domain.id, domain],
        [ip.id, ip],
      ]),
    });

    useGraphStore.getState().setFilterState("p-1", {
      types: [EntityType.Domain],
      hideFiltered: false,
    });

    expect(useGraphStore.getState().hiddenNodeIds.size).toBe(0);
  });

  it("resets filters to defaults and clears hidden ids", () => {
    const domain = makeEntity("e-domain", { type: EntityType.Domain });
    const ip = makeEntity("e-ip", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [domain.id, domain],
        [ip.id, ip],
      ]),
    });

    useGraphStore.getState().setFilterState("p-1", { types: [EntityType.Domain] });
    expect(useGraphStore.getState().hiddenNodeIds.size).toBe(1);

    useGraphStore.getState().resetFilters("p-1");
    const state = useGraphStore.getState();
    expect(state.hiddenNodeIds.size).toBe(0);
    expect(state.filterState).toEqual(DEFAULT_FILTER_STATE);
  });

  it("keeps manually hidden nodes hidden across filter changes", () => {
    const domain = makeEntity("e-domain", { type: EntityType.Domain });
    const ip = makeEntity("e-ip", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [domain.id, domain],
        [ip.id, ip],
      ]),
    });

    useGraphStore.getState().hideNode("p-1", domain.id);
    useGraphStore.getState().setFilterState("p-1", { types: [EntityType.IPAddress] });

    const state = useGraphStore.getState();
    expect(state.manualHiddenNodeIds.has(domain.id)).toBe(true);
    expect(state.hiddenNodeIds.has(domain.id)).toBe(true);
    expect(state.hiddenNodeIds.has(ip.id)).toBe(false);
  });

  it("can unhide nodes and edges without deleting them", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b", { type: EntityType.IPAddress });
    const edge = makeEdge("edge-1", a.id, b.id);
    useGraphStore.setState({
      entities: new Map([
        [a.id, a],
        [b.id, b],
      ]),
      edges: new Map([[edge.id, edge]]),
    });

    useGraphStore.getState().hideNode("p-1", a.id);
    useGraphStore.getState().hideEdge("p-1", edge.id);
    expect(useGraphStore.getState().hiddenNodeIds.has(a.id)).toBe(true);
    expect(useGraphStore.getState().hiddenEdgeIds.has(edge.id)).toBe(true);

    useGraphStore.getState().unhideNode("p-1", a.id);
    useGraphStore.getState().unhideEdge("p-1", edge.id);

    const state = useGraphStore.getState();
    expect(state.entities.has(a.id)).toBe(true);
    expect(state.edges.has(edge.id)).toBe(true);
    expect(state.hiddenNodeIds.has(a.id)).toBe(false);
    expect(state.hiddenEdgeIds.has(edge.id)).toBe(false);
  });

  it("pins selected nodes and can clear all pins", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [a.id, a],
        [b.id, b],
      ]),
      selectedNodeId: a.id,
      selectedNodeIds: new Set([a.id, b.id]),
    });

    useGraphStore.getState().pinSelected("p-1");
    expect(useGraphStore.getState().pinnedNodeIds.has(a.id)).toBe(true);
    expect(useGraphStore.getState().pinnedNodeIds.has(b.id)).toBe(true);

    useGraphStore.getState().unpinAll("p-1");
    expect(useGraphStore.getState().pinnedNodeIds.size).toBe(0);
  });

  it("pins only visible nodes when locking current positions", () => {
    const visible = makeEntity("e-visible");
    const hidden = makeEntity("e-hidden", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [visible.id, visible],
        [hidden.id, hidden],
      ]),
      hiddenNodeIds: new Set([hidden.id]),
    });

    useGraphStore.getState().pinVisible("p-1");

    const state = useGraphStore.getState();
    expect(state.pinnedNodeIds.has(visible.id)).toBe(true);
    expect(state.pinnedNodeIds.has(hidden.id)).toBe(false);
  });

  it("persists pins in local storage and reloads them by project", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b", { type: EntityType.IPAddress });
    useGraphStore.setState({
      entities: new Map([
        [a.id, a],
        [b.id, b],
      ]),
      selectedNodeIds: new Set([a.id]),
    });

    useGraphStore.getState().pinSelected("p-1");
    expect(JSON.parse(localStorage.getItem("ogi-pinned-p-1") || "{}")).toEqual({
      entityIds: [a.id],
    });

    useGraphStore.setState({ pinnedNodeIds: new Set() });
    const persisted = JSON.parse(localStorage.getItem("ogi-pinned-p-1") || "{}");
    useGraphStore.setState({ pinnedNodeIds: new Set(persisted.entityIds) });

    expect(useGraphStore.getState().pinnedNodeIds.has(a.id)).toBe(true);
    expect(useGraphStore.getState().pinnedNodeIds.has(b.id)).toBe(false);
  });

  it("focuses on the current selection without deleting other nodes", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b");
    const c = makeEntity("e-c");
    useGraphStore.setState({
      graph: makeGraph([a, b, c]),
      entities: new Map([
        [a.id, a],
        [b.id, b],
        [c.id, c],
      ]),
      selectedNodeId: a.id,
      selectedNodeIds: new Set([a.id]),
    });

    useGraphStore.getState().setFocusMode("p-1", "selection");

    let state = useGraphStore.getState();
    expect(state.hiddenNodeIds.has(a.id)).toBe(false);
    expect(state.hiddenNodeIds.has(b.id)).toBe(true);
    expect(state.hiddenNodeIds.has(c.id)).toBe(true);
    expect(state.entities.has(b.id)).toBe(true);

    useGraphStore.getState().clearDeclutterState("p-1");
    state = useGraphStore.getState();
    expect(state.hiddenNodeIds.size).toBe(0);
  });

  it("shows one-hop and two-hop neighborhoods around the selection", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b");
    const c = makeEntity("e-c");
    const d = makeEntity("e-d");
    const ab = makeEdge("ab", a.id, b.id);
    const bc = makeEdge("bc", b.id, c.id);
    const cd = makeEdge("cd", c.id, d.id);
    useGraphStore.setState({
      graph: makeGraph([a, b, c, d], [ab, bc, cd]),
      entities: new Map([
        [a.id, a],
        [b.id, b],
        [c.id, c],
        [d.id, d],
      ]),
      edges: new Map([
        [ab.id, ab],
        [bc.id, bc],
        [cd.id, cd],
      ]),
      selectedNodeId: b.id,
      selectedNodeIds: new Set([b.id]),
    });

    useGraphStore.getState().setFocusMode("p-1", "neighbors-1");
    let state = useGraphStore.getState();
    expect(state.hiddenNodeIds.has(a.id)).toBe(false);
    expect(state.hiddenNodeIds.has(b.id)).toBe(false);
    expect(state.hiddenNodeIds.has(c.id)).toBe(false);
    expect(state.hiddenNodeIds.has(d.id)).toBe(true);

    useGraphStore.getState().setFocusMode("p-1", "neighbors-2");
    state = useGraphStore.getState();
    expect(state.hiddenNodeIds.has(d.id)).toBe(false);
  });

  it("can hide isolates and show only current search hits as derived view state", () => {
    const alpha = makeEntity("e-alpha", { value: "alpha.example.org" });
    const beta = makeEntity("e-beta", { value: "beta.example.org" });
    const gamma = makeEntity("e-gamma", { value: "gamma.example.org" });
    const edge = makeEdge("ab", alpha.id, beta.id);
    useGraphStore.setState({
      graph: makeGraph([alpha, beta, gamma], [edge]),
      entities: new Map([
        [alpha.id, alpha],
        [beta.id, beta],
        [gamma.id, gamma],
      ]),
      edges: new Map([[edge.id, edge]]),
    });

    useGraphStore.getState().setHideIsolates("p-1", true);
    let state = useGraphStore.getState();
    expect(state.hiddenNodeIds.has(gamma.id)).toBe(true);
    expect(state.hiddenNodeIds.has(alpha.id)).toBe(false);

    useGraphStore.getState().setSearchQuery("alpha");
    useGraphStore.getState().setFocusMode("p-1", "search");
    state = useGraphStore.getState();
    expect(state.hiddenNodeIds.has(alpha.id)).toBe(false);
    expect(state.hiddenNodeIds.has(beta.id)).toBe(true);
  });
});
