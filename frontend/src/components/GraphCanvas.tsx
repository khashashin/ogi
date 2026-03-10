import { useEffect, useRef, useCallback } from "react";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { setSigmaRef } from "../stores/sigmaRef";

export function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const { graph, selectNode, selectEdge, selectedNodeId, nodeOverlay, persistPositions } = useGraphStore();
  const { currentProject } = useProjectStore();

  // Drag state refs (avoid re-renders during drag)
  const dragStateRef = useRef<{
    dragging: boolean;
    draggedNode: string | null;
    startX: number;
    startY: number;
    hasMoved: boolean;
  }>({ dragging: false, draggedNode: null, startX: 0, startY: 0, hasMoved: false });

  const initSigma = useCallback(() => {
    if (!containerRef.current) return;

    // Clean up previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill();
      sigmaRef.current = null;
    }

    const renderer = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: true,
      defaultEdgeType: "arrow",
      defaultNodeColor: "#6366f1",
      defaultEdgeColor: "#4b5563",
      labelColor: { color: "#e1e4ed" },
      labelSize: 12,
      labelRenderedSizeThreshold: 6,
      enableEdgeEvents: true,
    });

    // --- Node click ---
    renderer.on("clickNode", ({ node }) => {
      const ds = dragStateRef.current;
      // Don't fire click if we just finished dragging
      if (ds.hasMoved) return;
      selectNode(node);
    });

    // --- Edge click ---
    renderer.on("clickEdge", ({ edge }) => {
      selectEdge(edge);
    });

    renderer.on("clickStage", () => {
      selectNode(null);
    });

    // --- Node dragging ---
    renderer.on("downNode", ({ node, event }) => {
      // Only drag on left-click (button 0), ignore right-click
      if ((event.original as MouseEvent).button !== 0) return;

      const ds = dragStateRef.current;
      ds.dragging = true;
      ds.draggedNode = node;
      ds.hasMoved = false;
      ds.startX = event.x;
      ds.startY = event.y;

      // Disable camera on drag
      renderer.getCamera().disable();
    });

    renderer.getMouseCaptor().on("mousemovebody", (event: { x: number; y: number }) => {
      const ds = dragStateRef.current;
      if (!ds.dragging || !ds.draggedNode) return;

      // Check if user has moved enough to count as drag
      const dx = event.x - ds.startX;
      const dy = event.y - ds.startY;
      if (!ds.hasMoved && Math.sqrt(dx * dx + dy * dy) > 3) {
        ds.hasMoved = true;
      }

      // Convert viewport coords to graph coords
      const pos = renderer.viewportToGraph(event);
      graph.setNodeAttribute(ds.draggedNode, "x", pos.x);
      graph.setNodeAttribute(ds.draggedNode, "y", pos.y);
    });

    renderer.getMouseCaptor().on("mouseup", () => {
      const ds = dragStateRef.current;
      if (ds.dragging && ds.hasMoved && currentProject) {
        // Persist new position
        persistPositions(currentProject.id);
      }
      ds.dragging = false;
      ds.draggedNode = null;

      // Re-enable camera
      renderer.getCamera().enable();
    });

    // --- Right-click: emit custom event for context menu ---
    renderer.on("rightClickNode", ({ node, event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: { type: "node", id: node, x: domEvent.clientX, y: domEvent.clientY },
        })
      );
    });

    renderer.on("rightClickEdge", ({ edge, event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: { type: "edge", id: edge, x: domEvent.clientX, y: domEvent.clientY },
        })
      );
    });

    renderer.on("rightClickStage", ({ event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: { type: "stage", id: null, x: domEvent.clientX, y: domEvent.clientY },
        })
      );
    });

    sigmaRef.current = renderer;

    // Run ForceAtlas2 layout if there are enough nodes
    if (graph.order > 1) {
      forceAtlas2.assign(graph, {
        iterations: 100,
        settings: {
          gravity: 1,
          scalingRatio: 2,
          barnesHutOptimize: graph.order > 50,
        },
      });
    }
  }, [graph, selectNode, selectEdge, currentProject, persistPositions]);

  useEffect(() => {
    initSigma();
    return () => {
      if (sigmaRef.current) {
        sigmaRef.current.kill();
        sigmaRef.current = null;
      }
    };
  }, [initSigma]);

  // Unified node/edge reducer — handles selection highlight + overlays (search, analysis).
  // GraphCanvas is the sole owner of nodeReducer/edgeReducer to prevent competing overwrites.
  useEffect(() => {
    if (!sigmaRef.current) return;
    const renderer = sigmaRef.current;

    renderer.setSetting("nodeReducer", (node, data) => {
      // 1. Overlay takes priority when active
      if (nodeOverlay) {
        if (nodeOverlay.type === "search") {
          if (nodeOverlay.matchIds.size > 0) {
            if (node === nodeOverlay.focusId) {
              return { ...data, highlighted: true, zIndex: 2, size: (data.size ?? 8) + 4 };
            }
            if (nodeOverlay.matchIds.has(node)) {
              return { ...data, highlighted: true, zIndex: 1 };
            }
            return { ...data, color: `${data.color}22`, label: "" };
          }
          // Search active but no matches — pass through to selection
        }
        if (nodeOverlay.type === "analysis-scores") {
          const score = nodeOverlay.scores[node] ?? 0;
          const normalized = score / nodeOverlay.maxScore;
          return { ...data, size: 6 + normalized * 20 };
        }
        if (nodeOverlay.type === "analysis-communities") {
          return { ...data, color: nodeOverlay.colors[node] ?? data.color };
        }
      }

      // 2. Selection highlight
      if (selectedNodeId) {
        if (node === selectedNodeId) {
          return { ...data, highlighted: true, size: (data.size ?? 8) + 3 };
        }
        const isNeighbor = graph.hasNode(selectedNodeId) && graph.areNeighbors(node, selectedNodeId);
        return {
          ...data,
          color: isNeighbor ? data.color : `${data.color}44`,
          label: isNeighbor ? data.label : "",
        };
      }

      return data;
    });

    renderer.setSetting("edgeReducer", (edge, data) => {
      if (selectedNodeId && !nodeOverlay) {
        const src = graph.source(edge);
        const tgt = graph.target(edge);
        if (src !== selectedNodeId && tgt !== selectedNodeId) {
          return { ...data, hidden: true };
        }
      }
      return data;
    });

    renderer.refresh();
  }, [selectedNodeId, nodeOverlay, graph]);

  // Expose sigma ref for zoom controls and context menu
  useEffect(() => {
    setSigmaRef(sigmaRef.current);
    return () => setSigmaRef(null);
  });

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-bg"
      style={{ minHeight: "400px" }}
    />
  );
}
