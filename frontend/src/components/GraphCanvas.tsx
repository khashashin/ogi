import { useEffect, useRef, useCallback, useState } from "react";
import Sigma from "sigma";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { setSigmaRef } from "../stores/sigmaRef";
import { applyForceDirectedLayout } from "../lib/graphLayouts";

export function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
    const {
      graph,
      entities,
      selectNode,
      selectNodes,
    clearSelection,
    selectEdge,
    selectedNodeId,
    selectedNodeIds,
    selectedEdgeId,
    hiddenNodeIds,
    hiddenEdgeIds,
    nodeOverlay,
      persistPositions,
    } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [selectionBox, setSelectionBox] = useState<null | { startX: number; startY: number; x: number; y: number }>(null);
  const selectionStateRef = useRef<null | { startX: number; startY: number; mode: "replace" | "add" | "toggle" }>(null);
  const suppressStageClickRef = useRef(false);

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
      minEdgeThickness: 2,
      itemSizesReference: "screen",
      zIndex: true,
    });

    // --- Node click ---
    renderer.on("clickNode", ({ node, event }) => {
      const ds = dragStateRef.current;
      // Don't fire click if we just finished dragging
      if (ds.hasMoved) return;
      const mouseEvent = event.original as MouseEvent;
      const additive = mouseEvent.ctrlKey || mouseEvent.metaKey || mouseEvent.shiftKey;
      selectNode(node, additive ? "toggle" : "replace");
    });

    // --- Edge click ---
    renderer.on("clickEdge", ({ edge }) => {
      selectEdge(edge);
    });

    renderer.on("enterEdge", ({ edge }) => {
      setHoveredEdgeId(edge);
      if (containerRef.current) containerRef.current.style.cursor = "pointer";
    });

    renderer.on("leaveEdge", () => {
      setHoveredEdgeId(null);
      if (containerRef.current) containerRef.current.style.cursor = "default";
    });

    renderer.on("clickStage", () => {
      if (suppressStageClickRef.current) {
        suppressStageClickRef.current = false;
        return;
      }
      clearSelection();
    });

    // --- Node dragging ---
    renderer.on("downNode", ({ node, event }) => {
      // Only drag on left-click (button 0), ignore right-click
      if ((event.original as MouseEvent).button !== 0) return;

      if (currentProject?.role === "viewer") return;

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
      applyForceDirectedLayout(graph, entities);
    }
  }, [graph, entities, selectNode, clearSelection, selectEdge, currentProject, persistPositions]);

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
      if (hiddenNodeIds.has(node)) {
        return { ...data, hidden: true, label: "" };
      }

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
      if (selectedNodeIds.size > 0) {
        if (selectedNodeIds.has(node)) {
          return { ...data, highlighted: true, size: (data.size ?? 8) + 3, zIndex: 2 };
        }
        const isNeighbor =
          selectedNodeIds.size === 1 &&
          selectedNodeId &&
          graph.hasNode(selectedNodeId) &&
          graph.areNeighbors(node, selectedNodeId);
        return {
          ...data,
          color: isNeighbor ? data.color : `${data.color}44`,
          label: isNeighbor ? data.label : "",
        };
      }

      return data;
    });

    renderer.setSetting("edgeReducer", (edge, data) => {
      const src = graph.source(edge);
      const tgt = graph.target(edge);
      if (hiddenEdgeIds.has(edge) || hiddenNodeIds.has(src) || hiddenNodeIds.has(tgt)) {
        return { ...data, hidden: true };
      }

      if (selectedEdgeId && edge === selectedEdgeId) {
        return {
          ...data,
          color: "#60a5fa",
          size: Math.max((data.size ?? 2) * 2.2, 4),
          zIndex: 3,
        };
      }

      if (hoveredEdgeId && edge === hoveredEdgeId) {
        return {
          ...data,
          color: "#93c5fd",
          size: Math.max((data.size ?? 2) * 2, 3.5),
          zIndex: 2,
        };
      }

      if (selectedNodeIds.size > 0 && !nodeOverlay) {
        const connectedToSelection = selectedNodeIds.has(src) || selectedNodeIds.has(tgt);
        if (!connectedToSelection) {
          return { ...data, hidden: true };
        }
      }
      return data;
    });

    renderer.refresh();
  }, [selectedNodeId, selectedNodeIds, selectedEdgeId, hoveredEdgeId, hiddenNodeIds, hiddenEdgeIds, nodeOverlay, graph]);

  // Expose sigma ref for zoom controls and context menu
  useEffect(() => {
    setSigmaRef(sigmaRef.current);
    return () => setSigmaRef(null);
  });

  const handleMouseDownCapture = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || event.button !== 0) return;
    const isModifier = event.shiftKey || event.ctrlKey || event.metaKey;
    if (!isModifier) return;
    const rect = containerRef.current.getBoundingClientRect();
    const startX = event.clientX - rect.left;
    const startY = event.clientY - rect.top;
    selectionStateRef.current = {
      startX,
      startY,
      mode: event.ctrlKey || event.metaKey ? "toggle" : "add",
    };
    setSelectionBox({ startX, startY, x: startX, y: startY });
    sigmaRef.current?.getCamera().disable();
    event.preventDefault();
    event.stopPropagation();
  };

  useEffect(() => {
    if (!selectionBox || !containerRef.current) return;

    const handleMove = (event: MouseEvent) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || !selectionStateRef.current) return;
      setSelectionBox((current) =>
        current
          ? {
              ...current,
              x: event.clientX - rect.left,
              y: event.clientY - rect.top,
            }
          : current,
      );
    };

    const handleUp = () => {
      const box = selectionBox;
      const state = selectionStateRef.current;
      const renderer = sigmaRef.current as Sigma & {
        graphToViewport: (point: { x: number; y: number }) => { x: number; y: number };
      };
      if (box && state && renderer?.graphToViewport) {
        const minX = Math.min(box.startX, box.x);
        const maxX = Math.max(box.startX, box.x);
        const minY = Math.min(box.startY, box.y);
        const maxY = Math.max(box.startY, box.y);
        const selected: string[] = [];
        graph.forEachNode((node, attrs) => {
          if (hiddenNodeIds.has(node)) return;
          const viewport = renderer.graphToViewport({
            x: Number(attrs.x) || 0,
            y: Number(attrs.y) || 0,
          });
          if (!viewport) return;
          if (viewport.x >= minX && viewport.x <= maxX && viewport.y >= minY && viewport.y <= maxY) {
            selected.push(node);
          }
        });
        if (selected.length > 0) {
          suppressStageClickRef.current = true;
          selectNodes(selected, state.mode);
        } else if (state.mode === "add") {
          suppressStageClickRef.current = true;
          clearSelection();
        }
      }
      selectionStateRef.current = null;
      setSelectionBox(null);
      sigmaRef.current?.getCamera().enable();
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [selectionBox, graph, hiddenNodeIds, selectNodes, clearSelection]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-bg"
      style={{ minHeight: "400px" }}
      onMouseDownCapture={handleMouseDownCapture}
    >
      {selectionBox && (
        <div
          className="pointer-events-none absolute border border-accent/70 bg-accent/10"
          style={{
            left: Math.min(selectionBox.startX, selectionBox.x),
            top: Math.min(selectionBox.startY, selectionBox.y),
            width: Math.abs(selectionBox.x - selectionBox.startX),
            height: Math.abs(selectionBox.y - selectionBox.startY),
          }}
        />
      )}
    </div>
  );
}
