import { beforeEach, describe, expect, it } from "vitest";

import { EntityType, type Entity } from "../types/entity";
import { DEFAULT_FILTER_STATE, useGraphStore } from "./graphStore";

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
});
