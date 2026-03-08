import Graph from "graphology";
import { describe, expect, it } from "vitest";

import { applyGraphLayout } from "./graphLayouts";
import { EntityType, type Entity } from "../types/entity";

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

describe("applyGraphLayout", () => {
  it("keeps pinned nodes fixed when applying layout to unpinned nodes", () => {
    const graph = new Graph({ multi: true, type: "directed" });
    const entities = new Map<string, Entity>([
      ["a", makeEntity("a")],
      ["b", makeEntity("b", { type: EntityType.IPAddress })],
      ["c", makeEntity("c", { type: EntityType.Person })],
    ]);

    graph.addNode("a", { x: 10, y: 20, size: 11 });
    graph.addNode("b", { x: 80, y: 120, size: 12 });
    graph.addNode("c", { x: 140, y: 30, size: 13 });
    graph.addEdgeWithKey("e1", "a", "b");
    graph.addEdgeWithKey("e2", "b", "c");

    applyGraphLayout("grid", graph, entities, {
      pinnedNodeIds: new Set(["a"]),
      target: "unpinned",
    });

    expect(graph.getNodeAttributes("a")).toMatchObject({ x: 10, y: 20, size: 11 });
    expect(graph.getNodeAttribute("b", "x")).not.toBe(80);
  });

  it("only moves selected nodes when target is selected", () => {
    const graph = new Graph({ multi: true, type: "directed" });
    const entities = new Map<string, Entity>([
      ["a", makeEntity("a")],
      ["b", makeEntity("b", { type: EntityType.IPAddress })],
      ["c", makeEntity("c", { type: EntityType.Person })],
    ]);

    graph.addNode("a", { x: 5, y: 5 });
    graph.addNode("b", { x: 25, y: 25 });
    graph.addNode("c", { x: 50, y: 50 });
    graph.addEdgeWithKey("e1", "a", "b");
    graph.addEdgeWithKey("e2", "b", "c");

    applyGraphLayout("grid", graph, entities, {
      selectedNodeIds: new Set(["b", "c"]),
      target: "selected",
    });

    expect(graph.getNodeAttributes("a")).toMatchObject({ x: 5, y: 5 });
    expect(graph.getNodeAttribute("b", "x")).not.toBe(25);
    expect(graph.getNodeAttribute("c", "x")).not.toBe(50);
  });
});
