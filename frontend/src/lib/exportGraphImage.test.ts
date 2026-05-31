import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

let buildVisibleGraph: typeof import("./exportGraphImage").buildVisibleGraph;
let computeExportSize: typeof import("./exportGraphImage").computeExportSize;
let makeFilename: typeof import("./exportGraphImage").makeFilename;
let sanitizeProjectName: typeof import("./exportGraphImage").sanitizeProjectName;

beforeAll(async () => {
  vi.stubGlobal("WebGLRenderingContext", class WebGLRenderingContextStub {});
  vi.stubGlobal("WebGL2RenderingContext", class WebGL2RenderingContextStub {});
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
    return {
      font: "",
      measureText(text: string) {
        return { width: text.length * 7 };
      },
    } as unknown as CanvasRenderingContext2D;
  });
  const module = await import("./exportGraphImage");
  buildVisibleGraph = module.buildVisibleGraph;
  computeExportSize = module.computeExportSize;
  makeFilename = module.makeFilename;
  sanitizeProjectName = module.sanitizeProjectName;
});

describe("exportGraphImage helpers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-29T10:11:12.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("sanitizes project names for filenames", () => {
    expect(sanitizeProjectName("  My Project / Alpha  ")).toBe("my-project-alpha");
    expect(sanitizeProjectName("!!!")).toBe("graph");
  });

  it("builds a timestamped png filename", () => {
    expect(makeFilename("My Project / Alpha")).toBe(
      "my-project-alpha-graph-2026-03-29-10-11-12.png",
    );
  });

  it("builds a visible-only export graph", () => {
    const graph = {
      forEachNode(callback: (node: string, attrs: Record<string, unknown>) => void) {
        callback("visible-node", { x: 10, y: 20, size: 12, label: "Visible" });
        callback("hidden-node", { x: 30, y: 40, size: 8, label: "Hidden" });
      },
      forEachEdge(
        callback: (
          edge: string,
          attrs: Record<string, unknown>,
          source: string,
          target: string,
        ) => void,
      ) {
        callback("visible-edge", { label: "kept" }, "visible-node", "visible-node");
        callback("hidden-edge", { label: "gone" }, "visible-node", "visible-node");
        callback("edge-to-hidden-node", { label: "skip" }, "visible-node", "hidden-node");
      },
    };

    const result = buildVisibleGraph({
      graph,
      hiddenNodeIds: new Set(["hidden-node"]),
      hiddenEdgeIds: new Set(["hidden-edge"]),
    });

    expect(result.visibleNodes).toEqual([
      { id: "visible-node", x: 10, y: 20, size: 12, label: "Visible" },
    ]);
    expect(result.graph.order).toBe(1);
    expect(result.graph.size).toBe(1);
    expect(result.graph.hasNode("visible-node")).toBe(true);
    expect(result.graph.hasNode("hidden-node")).toBe(false);
    expect(result.graph.hasEdge("visible-edge")).toBe(true);
    expect(result.graph.hasEdge("hidden-edge")).toBe(false);
    expect(result.graph.hasEdge("edge-to-hidden-node")).toBe(false);
  });

  it("uses minimum export dimensions for empty input", () => {
    expect(computeExportSize([])).toEqual({ width: 1200, height: 1200 });
  });

  it("adds extra width when labels are long", () => {
    const unlabeled = computeExportSize([
      { id: "a", x: 0, y: 0, size: 8, label: "" },
      { id: "b", x: 100, y: 100, size: 8, label: "" },
    ]);
    const labeled = computeExportSize([
      { id: "a", x: 0, y: 0, size: 8, label: "" },
      { id: "b", x: 100, y: 100, size: 8, label: "A very long label that should add export padding" },
    ]);

    expect(labeled.width).toBeGreaterThan(unlabeled.width);
    expect(labeled.height).toBe(unlabeled.height);
  });
});
