import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRealtimeSync } from "./useRealtimeSync";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type PayloadHandler = (payload: any) => void;

const hoisted = vi.hoisted(() => {
  const handlers: Record<string, PayloadHandler> = {};
  const channelMock = {
    on: vi.fn((event: string, cfg: { table?: string }, cb: PayloadHandler) => {
      if (event === "postgres_changes" && cfg.table) {
        handlers[cfg.table] = cb;
      }
      return channelMock;
    }),
    subscribe: vi.fn(() => channelMock),
  };
  const removeChannelMock = vi.fn();
  const channelFactoryMock = vi.fn(() => channelMock);
  return {
    handlers,
    channelMock,
    removeChannelMock,
    channelFactoryMock,
    state: null as any,
  };
});

vi.mock("../lib/supabase", () => ({
  supabase: {
    channel: hoisted.channelFactoryMock,
    removeChannel: hoisted.removeChannelMock,
  },
}));

vi.mock("../stores/graphStore", () => ({
  useGraphStore: {
    getState: () => hoisted.state,
    setState: (patch: Record<string, unknown>) => {
      hoisted.state = { ...hoisted.state, ...patch };
    },
  },
}));

function createGraphStub() {
  const nodes = new Set<string>();
  const edges = new Set<string>();
  const nodeLabels = new Map<string, string>();
  const edgeLabels = new Map<string, string>();
  return {
    hasNode: (id: string) => nodes.has(id),
    dropNode: (id: string) => nodes.delete(id),
    setNodeAttribute: (id: string, attr: string, value: string) => {
      if (attr === "label") nodeLabels.set(id, value);
    },
    hasEdge: (id: string) => edges.has(id),
    dropEdge: (id: string) => edges.delete(id),
    setEdgeAttribute: (id: string, attr: string, value: string) => {
      if (attr === "label") edgeLabels.set(id, value);
    },
    __seedNode: (id: string) => nodes.add(id),
    __seedEdge: (id: string) => edges.add(id),
    __nodeLabels: nodeLabels,
    __edgeLabels: edgeLabels,
  };
}

function Harness({ projectId }: { projectId: string | null }) {
  useRealtimeSync(projectId);
  return null;
}

function renderHarness(projectId: string | null) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);
  act(() => {
    root.render(<Harness projectId={projectId} />);
  });
  return {
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe("useRealtimeSync", () => {
  beforeEach(() => {
    Object.keys(hoisted.handlers).forEach((k) => delete hoisted.handlers[k]);
    hoisted.channelFactoryMock.mockClear();
    hoisted.removeChannelMock.mockClear();
    hoisted.channelMock.on.mockClear();
    hoisted.channelMock.subscribe.mockClear();

    const graph = createGraphStub();
    const entities = new Map<string, any>();
    const edges = new Map<string, any>();

    hoisted.state = {
      graph,
      entities,
      edges,
      addEntity: vi.fn((_projectId: string, entity: any) => {
        entities.set(entity.id, entity);
        graph.__seedNode(entity.id);
      }),
      addEdge: vi.fn((_projectId: string, edge: any) => {
        edges.set(edge.id, edge);
        graph.__seedEdge(edge.id);
      }),
    };
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("subscribes and unsubscribes project channel", () => {
    const { unmount } = renderHarness("project-1");
    expect(hoisted.channelFactoryMock).toHaveBeenCalledWith("project:project-1");
    expect(hoisted.channelMock.subscribe).toHaveBeenCalledTimes(1);
    unmount();
    expect(hoisted.removeChannelMock).toHaveBeenCalledTimes(1);
  });

  it("handles entity insert idempotently and applies entity updates", () => {
    const { unmount } = renderHarness("project-1");

    const entity = { id: "e1", value: "alpha.test" };
    hoisted.handlers.entities({ eventType: "INSERT", new: entity, old: {} });
    hoisted.handlers.entities({ eventType: "INSERT", new: entity, old: {} });
    expect(hoisted.state.addEntity).toHaveBeenCalledTimes(1);

    const updated = { id: "e1", value: "beta.test" };
    hoisted.handlers.entities({ eventType: "UPDATE", new: updated, old: entity });
    expect(hoisted.state.entities.get("e1")?.value).toBe("beta.test");
    expect(hoisted.state.graph.__nodeLabels.get("e1")).toBe("beta.test");

    hoisted.handlers.entities({ eventType: "DELETE", old: { id: "e1" }, new: {} });
    expect(hoisted.state.entities.has("e1")).toBe(false);
    unmount();
  });

  it("handles edge insert idempotently and applies edge updates/deletes", () => {
    const { unmount } = renderHarness("project-1");

    const edge = { id: "edge-1", source_id: "a", target_id: "b", label: "links to" };
    hoisted.handlers.edges({ eventType: "INSERT", new: edge, old: {} });
    hoisted.handlers.edges({ eventType: "INSERT", new: edge, old: {} });
    expect(hoisted.state.addEdge).toHaveBeenCalledTimes(1);

    const updated = { ...edge, label: "related to" };
    hoisted.handlers.edges({ eventType: "UPDATE", new: updated, old: edge });
    expect(hoisted.state.edges.get("edge-1")?.label).toBe("related to");
    expect(hoisted.state.graph.__edgeLabels.get("edge-1")).toBe("related to");

    hoisted.handlers.edges({ eventType: "DELETE", old: { id: "edge-1" }, new: {} });
    expect(hoisted.state.edges.has("edge-1")).toBe(false);
    unmount();
  });
});
