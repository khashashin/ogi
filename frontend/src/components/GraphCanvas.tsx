import { useEffect, useRef, useCallback, useState } from "react";
import Sigma from "sigma";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { setSigmaRef } from "../stores/sigmaRef";
import { applyGraphLayout } from "../lib/graphLayouts";
import { ENTITY_TYPE_META } from "../types/entity";
import { isCustomSvgIcon, resolveEntityIconName } from "../lib/entityIconRegistry";
import { LazyLucideIcon } from "./LazyLucideIcon";
import { ProtectedMediaImage } from "./ProtectedMediaImage";

const SELECTED_LABEL_COLOR = "#111827";
const SELECTED_LABEL_BG = "#f3f4f6";
const PINNED_LABEL_COLOR = "#dbeafe";
const PINNED_LABEL_BG = "#1e3a8a";
const CONNECTION_LABEL_COLOR = "#fef3c7";
const CONNECTION_LABEL_BG = "#92400e";

type NodeVisualOverlay =
  | { id: string; x: number; y: number; size: number; kind: "icon"; icon: string; color: string }
  | { id: string; x: number; y: number; size: number; kind: "image"; imageUrl: string; projectId: string | null };

function getContrastIconColor(color?: string): string {
  const hex = (color ?? "").trim();
  if (!/^#[0-9a-fA-F]{6,8}$/.test(hex)) return "#ffffff";
  const raw = hex.slice(1, 7);
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#111827" : "#ffffff";
}

function getCustomNodeIcon(entity: { type: string; icon?: string | null }): string | null {
  const iconName = entity.icon?.trim();
  if (!iconName) return null;
  const defaultIcon = ENTITY_TYPE_META[entity.type as keyof typeof ENTITY_TYPE_META]?.icon;
  if (defaultIcon && resolveEntityIconName(defaultIcon) === resolveEntityIconName(iconName)) {
    return null;
  }
  return iconName;
}

function getPersonNodeImage(
  entity: { type: string; properties?: Record<string, unknown> | null },
): string | null {
  if (entity.type !== "Person") return null;
  const imageUrl = entity.properties?.visual_image_url;
  if (typeof imageUrl !== "string") return null;
  const trimmed = imageUrl.trim();
  return trimmed || null;
}

function drawHighlightedNodeHover(
  context: CanvasRenderingContext2D,
  data: {
    x: number;
    y: number;
    size: number;
    label?: string | null;
    color?: string;
    highlightedLabelColor?: string;
    highlightedLabelBackground?: string;
  },
  settings: {
    labelSize: number;
    labelFont: string;
    labelWeight?: string | number;
  },
) {
  if (!data.label) return;

  const fontSize = settings.labelSize ?? 12;
  const fontFamily = settings.labelFont ?? "sans-serif";
  const fontWeight = settings.labelWeight ?? 600;
  const label = data.label;
  const paddingX = 8;
  const paddingY = 4;
  const radius = 6;
  const offsetX = data.size + 8;
  const textX = data.x + offsetX;
  const textY = data.y + fontSize / 3;

  context.save();
  context.font = `${fontWeight} ${fontSize}px ${fontFamily}`;
  const textWidth = context.measureText(label).width;
  const boxX = textX - paddingX;
  const boxY = data.y - fontSize / 2 - paddingY;
  const boxWidth = textWidth + paddingX * 2;
  const boxHeight = fontSize + paddingY * 2;

  context.beginPath();
  context.moveTo(boxX + radius, boxY);
  context.lineTo(boxX + boxWidth - radius, boxY);
  context.quadraticCurveTo(
    boxX + boxWidth,
    boxY,
    boxX + boxWidth,
    boxY + radius,
  );
  context.lineTo(boxX + boxWidth, boxY + boxHeight - radius);
  context.quadraticCurveTo(
    boxX + boxWidth,
    boxY + boxHeight,
    boxX + boxWidth - radius,
    boxY + boxHeight,
  );
  context.lineTo(boxX + radius, boxY + boxHeight);
  context.quadraticCurveTo(
    boxX,
    boxY + boxHeight,
    boxX,
    boxY + boxHeight - radius,
  );
  context.lineTo(boxX, boxY + radius);
  context.quadraticCurveTo(boxX, boxY, boxX + radius, boxY);
  context.closePath();

  context.fillStyle = data.highlightedLabelBackground ?? SELECTED_LABEL_BG;
  context.shadowColor = "rgba(15, 23, 42, 0.25)";
  context.shadowBlur = 12;
  context.shadowOffsetY = 2;
  context.fill();

  context.shadowBlur = 0;
  context.shadowOffsetY = 0;
  context.fillStyle = data.highlightedLabelColor ?? SELECTED_LABEL_COLOR;
  context.fillText(label, textX, textY);
  context.restore();
}

export function GraphCanvas() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const {
    graph,
    entities,
    pinnedNodeIds,
    selectNode,
    selectNodes,
    clearSelection,
    selectEdge,
    selectedNodeIds,
    selectedEdgeId,
    hiddenNodeIds,
    hiddenEdgeIds,
    declutterState,
    nodeOverlay,
    recordNodeMove,
    connectionDraft,
  } = useGraphStore();
  const { currentProject } = useProjectStore();
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [nodeVisualOverlays, setNodeVisualOverlays] = useState<NodeVisualOverlay[]>([]);
  const [selectionBox, setSelectionBox] = useState<null | {
    startX: number;
    startY: number;
    x: number;
    y: number;
  }>(null);
  const selectionStateRef = useRef<null | {
    startX: number;
    startY: number;
    mode: "replace" | "add" | "toggle";
  }>(null);
  const suppressStageClickRef = useRef(false);
  const pinnedNodeIdsRef = useRef(pinnedNodeIds);
  const selectedNodeIdsRef = useRef(selectedNodeIds);
  const currentProjectRef = useRef(currentProject);

  useEffect(() => {
    pinnedNodeIdsRef.current = pinnedNodeIds;
  }, [pinnedNodeIds]);

  useEffect(() => {
    selectedNodeIdsRef.current = selectedNodeIds;
  }, [selectedNodeIds]);

  useEffect(() => {
    currentProjectRef.current = currentProject;
  }, [currentProject]);

  // Drag state refs (avoid re-renders during drag)
  const dragStateRef = useRef<{
    dragging: boolean;
    draggedNode: string | null;
    startX: number;
    startY: number;
    hasMoved: boolean;
    startGraphPointer: { x: number; y: number };
    initialNodePositions: Map<string, { x: number; y: number }>;
  }>({
    dragging: false,
    draggedNode: null,
    startX: 0,
    startY: 0,
    hasMoved: false,
    startGraphPointer: { x: 0, y: 0 },
    initialNodePositions: new Map(),
  });

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
      defaultDrawNodeHover: drawHighlightedNodeHover,
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
      const additive =
        mouseEvent.ctrlKey || mouseEvent.metaKey || mouseEvent.shiftKey;
      selectNode(node, additive ? "toggle" : "replace");
    });

    // --- Edge click ---
    renderer.on("clickEdge", ({ edge }) => {
      selectEdge(edge);
    });

    renderer.on("enterEdge", ({ edge }) => {
      setHoveredEdgeId(edge);
      if (wrapperRef.current) wrapperRef.current.style.cursor = "pointer";
    });

    renderer.on("leaveEdge", () => {
      setHoveredEdgeId(null);
      if (wrapperRef.current) wrapperRef.current.style.cursor = "default";
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

      if (currentProjectRef.current?.role === "viewer") return;
      if (pinnedNodeIdsRef.current.has(node)) return;

      const ds = dragStateRef.current;
      ds.dragging = true;
      ds.draggedNode = node;
      ds.hasMoved = false;
      ds.startX = event.x;
      ds.startY = event.y;
      ds.initialNodePositions = new Map();

      const dragGroup =
        selectedNodeIdsRef.current.size > 1 &&
        selectedNodeIdsRef.current.has(node)
          ? [...selectedNodeIdsRef.current].filter(
              (groupNodeId) => !pinnedNodeIdsRef.current.has(groupNodeId),
            )
          : [node];
      ds.startGraphPointer = renderer.viewportToGraph(event);

      for (const groupNodeId of dragGroup) {
        if (!graph.hasNode(groupNodeId)) continue;
        const attrs = graph.getNodeAttributes(groupNodeId) as {
          x?: number;
          y?: number;
        };
        ds.initialNodePositions.set(groupNodeId, {
          x: Number(attrs.x) || 0,
          y: Number(attrs.y) || 0,
        });
      }

      renderer.setCustomBBox(renderer.getBBox());

      // Disable camera on drag
      renderer.getCamera().disable();
    });

    renderer
      .getMouseCaptor()
      .on(
        "mousemovebody",
        (event: {
          x: number;
          y: number;
          preventSigmaDefault?: () => void;
          original?: Event;
        }) => {
        const ds = dragStateRef.current;
        if (!ds.dragging || !ds.draggedNode) return;

        event.preventSigmaDefault?.();
        event.original?.preventDefault?.();
        event.original?.stopPropagation?.();

        // Check if user has moved enough to count as drag
        const dx = event.x - ds.startX;
        const dy = event.y - ds.startY;
        if (!ds.hasMoved && Math.sqrt(dx * dx + dy * dy) > 3) {
          ds.hasMoved = true;
        }

        // Convert viewport coords to graph coords
        const pointerGraphPos = renderer.viewportToGraph(event);
        const delta = {
          x: pointerGraphPos.x - ds.startGraphPointer.x,
          y: pointerGraphPos.y - ds.startGraphPointer.y,
        };

        for (const [groupNodeId, initialPosition] of ds.initialNodePositions) {
          if (!graph.hasNode(groupNodeId)) continue;

          const targetPosition = {
            x: initialPosition.x + delta.x,
            y: initialPosition.y + delta.y,
          };
          graph.setNodeAttribute(groupNodeId, "x", targetPosition.x);
          graph.setNodeAttribute(groupNodeId, "y", targetPosition.y);
        }
      });

    renderer.getMouseCaptor().on("mouseup", () => {
      const ds = dragStateRef.current;
      if (ds.dragging && ds.hasMoved && currentProjectRef.current) {
        const positionsBefore = Object.fromEntries(ds.initialNodePositions.entries());
        const positionsAfter = Object.fromEntries(
          [...ds.initialNodePositions.keys()]
            .filter((nodeId) => graph.hasNode(nodeId))
            .map((nodeId) => {
              const attrs = graph.getNodeAttributes(nodeId) as { x?: number; y?: number };
              return [
                nodeId,
                {
                  x: Number(attrs.x) || 0,
                  y: Number(attrs.y) || 0,
                },
              ];
            }),
        );
        recordNodeMove(currentProjectRef.current.id, positionsBefore, positionsAfter);
      }
      ds.dragging = false;
      ds.draggedNode = null;
      ds.startGraphPointer = { x: 0, y: 0 };
      ds.initialNodePositions = new Map();

      renderer.setCustomBBox(null);

      // Re-enable camera
      renderer.getCamera().enable();
    });

    // --- Right-click: emit custom event for context menu ---
    renderer.on("rightClickNode", ({ node, event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: {
            type: "node",
            id: node,
            x: domEvent.clientX,
            y: domEvent.clientY,
          },
        }),
      );
    });

    renderer.on("rightClickEdge", ({ edge, event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: {
            type: "edge",
            id: edge,
            x: domEvent.clientX,
            y: domEvent.clientY,
          },
        }),
      );
    });

    renderer.on("rightClickStage", ({ event }) => {
      event.original.preventDefault();
      const domEvent = event.original as MouseEvent;
      window.dispatchEvent(
        new CustomEvent("ogi-context-menu", {
          detail: {
            type: "stage",
            id: null,
            x: domEvent.clientX,
            y: domEvent.clientY,
          },
        }),
      );
    });

    sigmaRef.current = renderer;

    // Run ForceAtlas2 layout if there are enough nodes
    if (graph.order > 1) {
      applyGraphLayout("force", graph, entities, {
        pinnedNodeIds: pinnedNodeIdsRef.current,
        target: "unpinned",
      });
    }
  }, [
    graph,
    entities,
    selectNode,
    clearSelection,
    selectEdge,
    recordNodeMove,
  ]);

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

      if (pinnedNodeIds.has(node)) {
        data = {
          ...data,
          zIndex: Math.max((data.zIndex as number | undefined) ?? 0, 1),
          highlighted: true,
          highlightedLabelColor: PINNED_LABEL_COLOR,
          highlightedLabelBackground: PINNED_LABEL_BG,
        };
      }

      if (connectionDraft.sourceId === node) {
        data = {
          ...data,
          zIndex: Math.max((data.zIndex as number | undefined) ?? 0, 2),
          highlighted: true,
          highlightedLabelColor: CONNECTION_LABEL_COLOR,
          highlightedLabelBackground: CONNECTION_LABEL_BG,
        };
      }

      // 1. Overlay takes priority when active
      if (nodeOverlay) {
        if (nodeOverlay.type === "search") {
          if (nodeOverlay.matchIds.size > 0) {
            if (node === nodeOverlay.focusId) {
              return {
                ...data,
                highlighted: true,
                zIndex: 2,
                size: (data.size ?? 8) + 4,
                highlightedLabelColor: SELECTED_LABEL_COLOR,
                highlightedLabelBackground: SELECTED_LABEL_BG,
              };
            }
            if (nodeOverlay.matchIds.has(node)) {
              return {
                ...data,
                highlighted: true,
                zIndex: 1,
                highlightedLabelColor: SELECTED_LABEL_COLOR,
                highlightedLabelBackground: SELECTED_LABEL_BG,
              };
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
          return {
            ...data,
            highlighted: true,
            size: (data.size ?? 8) + 3,
            zIndex: 2,
            highlightedLabelColor: SELECTED_LABEL_COLOR,
            highlightedLabelBackground: SELECTED_LABEL_BG,
          };
        }
        if (declutterState.fadeUnselected) {
          return {
            ...data,
            color: `${data.color}44`,
            label: "",
          };
        }
      }

      return data;
    });

    renderer.setSetting("edgeReducer", (edge, data) => {
      const src = graph.source(edge);
      const tgt = graph.target(edge);
      if (
        hiddenEdgeIds.has(edge) ||
        hiddenNodeIds.has(src) ||
        hiddenNodeIds.has(tgt)
      ) {
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

      if (
        selectedNodeIds.size > 0 &&
        declutterState.fadeUnselected &&
        !nodeOverlay
      ) {
        const connectedToSelection =
          selectedNodeIds.has(src) || selectedNodeIds.has(tgt);
        if (!connectedToSelection) {
          return { ...data, hidden: true };
        }
      }
      return data;
    });

    renderer.refresh();
  }, [
    selectedNodeIds,
    selectedEdgeId,
    hoveredEdgeId,
    hiddenNodeIds,
    hiddenEdgeIds,
    pinnedNodeIds,
    nodeOverlay,
    declutterState,
    graph,
    connectionDraft,
  ]);

  // Expose sigma ref for zoom controls and context menu
  useEffect(() => {
    setSigmaRef(sigmaRef.current);
    return () => setSigmaRef(null);
  });

  const updateNodeVisualOverlays = useCallback(() => {
    const renderer = sigmaRef.current as (Sigma & {
      getNodeDisplayData?: (key: string) => { x: number; y: number; size: number } | undefined;
      framedGraphToViewport?: (point: { x: number; y: number }) => { x: number; y: number };
      scaleSize?: (size?: number, ratio?: number) => number;
    }) | null;
    const container = wrapperRef.current;
    if (
      !renderer ||
      !container ||
      !renderer.getNodeDisplayData ||
      !renderer.framedGraphToViewport ||
      !renderer.scaleSize
    ) {
      return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;
    const overlays: NodeVisualOverlay[] = [];

    graph.forEachNode((nodeId, attrs) => {
      if (hiddenNodeIds.has(nodeId)) return;
      const entity = entities.get(nodeId);
      if (!entity) return;
      const imageUrl = getPersonNodeImage(entity);
      const customIcon = getCustomNodeIcon(entity);
      if (!imageUrl && !customIcon) return;
      const displayData = renderer.getNodeDisplayData?.(nodeId);
      if (!displayData) return;
      const point = renderer.framedGraphToViewport?.({
        x: displayData.x,
        y: displayData.y,
      });
      if (!point) return;
      if (point.x < -30 || point.y < -30 || point.x > width + 30 || point.y > height + 30) return;

      const rawNodeSize = Number(displayData.size) || Number(attrs.size) || 12;
      const nodeSize = renderer.scaleSize?.(rawNodeSize) ?? rawNodeSize;

      if (imageUrl) {
        overlays.push({
          id: nodeId,
          x: point.x,
          y: point.y,
          size: Math.max(18, nodeSize * 2),
          kind: "image",
          imageUrl,
          projectId: entity.project_id,
        });
        return;
      }

      overlays.push({
        id: nodeId,
        x: point.x,
        y: point.y,
        size: Math.max(10, nodeSize * 1.35),
        kind: "icon",
        icon: customIcon!,
        color: getContrastIconColor(String(attrs.color ?? "")),
      });
    });

    setNodeVisualOverlays(overlays);
  }, [entities, graph, hiddenNodeIds]);

  useEffect(() => {
    const renderer = sigmaRef.current as (Sigma & {
      on?: (event: string, handler: () => void) => void;
      off?: (event: string, handler: () => void) => void;
      getCamera: () => {
        on?: (event: string, handler: () => void) => void;
        off?: (event: string, handler: () => void) => void;
      };
    }) | null;
    if (!renderer) return;

    const refreshDomIcons = () => window.requestAnimationFrame(updateNodeVisualOverlays);
    const camera = renderer.getCamera();

    renderer.on?.("afterRender", refreshDomIcons);
    camera.on?.("updated", refreshDomIcons);
    window.addEventListener("resize", refreshDomIcons);
    refreshDomIcons();

    return () => {
      renderer.off?.("afterRender", refreshDomIcons);
      camera.off?.("updated", refreshDomIcons);
      window.removeEventListener("resize", refreshDomIcons);
    };
  }, [updateNodeVisualOverlays]);

  const handleMouseDownCapture = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!wrapperRef.current || event.button !== 0) return;
    const isModifier = event.shiftKey || event.ctrlKey || event.metaKey;
    if (!isModifier) return;
    const rect = wrapperRef.current.getBoundingClientRect();
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
    if (!selectionBox || !wrapperRef.current) return;

    const handleMove = (event: MouseEvent) => {
      const rect = wrapperRef.current?.getBoundingClientRect();
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
        graphToViewport: (point: { x: number; y: number }) => {
          x: number;
          y: number;
        };
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
          if (
            viewport.x >= minX &&
            viewport.x <= maxX &&
            viewport.y >= minY &&
            viewport.y <= maxY
          ) {
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
      ref={wrapperRef}
      className="relative w-full h-full bg-bg"
      style={{ minHeight: "400px" }}
      onMouseDownCapture={handleMouseDownCapture}
    >
      <div ref={containerRef} className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 z-[30]">
        {nodeVisualOverlays.map((overlay) => {
          return (
            <div
              key={overlay.id}
              className="absolute"
              style={{
                left: overlay.x,
                top: overlay.y,
                width: overlay.size,
                height: overlay.size,
                transform: "translate(-50%, -50%)",
                color: overlay.kind === "icon" ? overlay.color : undefined,
              }}
            >
              {overlay.kind === "image" ? (
                <ProtectedMediaImage
                  projectId={overlay.projectId}
                  entityId={overlay.id}
                  src={overlay.imageUrl}
                  className="h-full w-full rounded-full border border-white/20 object-cover shadow-[0_0_0_1px_rgba(15,23,42,0.25)]"
                />
              ) : isCustomSvgIcon(overlay.icon) ? (
                <img
                  src={`/icons/${overlay.icon}.svg`}
                  alt=""
                  className="h-full w-full object-contain"
                />
              ) : (
                <LazyLucideIcon name={overlay.icon} size={overlay.size} strokeWidth={2.25} />
              )}
            </div>
          );
        })}
      </div>
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
