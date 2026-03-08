import { beforeEach, describe, expect, it } from "vitest";

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
});
