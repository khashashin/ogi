import Graph from "graphology";
import Sigma from "sigma";
import { renderToStaticMarkup } from "react-dom/server";
import dynamicIconImports from "lucide-react/dynamicIconImports";

import { api } from "../api/client";
import { ENTITY_TYPE_META, type Entity } from "../types/entity";
import {
  getEntityIconComponent,
  isCustomSvgIcon,
  resolveEntityIconName,
} from "./entityIconRegistry";

const EXPORT_MAX_DIMENSION = 2800;
const EXPORT_MIN_DIMENSION = 1200;
const EXPORT_PADDING_RATIO = 0.08;
const EXPORT_PADDING_MIN = 96;

type GraphLike = {
  forEachNode: (
    callback: (node: string, attributes: Record<string, unknown>) => void,
  ) => void;
  forEachEdge: (
    callback: (
      edge: string,
      attributes: Record<string, unknown>,
      source: string,
      target: string,
    ) => void,
  ) => void;
};

interface ExportGraphImageOptions {
  graph: GraphLike;
  entities: Map<string, Entity>;
  hiddenNodeIds: Set<string>;
  hiddenEdgeIds: Set<string>;
  projectName: string;
  backgroundColor: string;
}

interface VisibleNodeInfo {
  id: string;
  x: number;
  y: number;
  size: number;
  label: string;
}

type Overlay =
  | {
      id: string;
      kind: "icon";
      x: number;
      y: number;
      size: number;
      icon: string;
      color: string;
    }
  | {
      id: string;
      kind: "image";
      x: number;
      y: number;
      size: number;
      projectId: string | null;
      imageUrl: string;
    };

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

function getCustomNodeIcon(entity: Entity): string | null {
  const iconName = entity.icon?.trim();
  if (!iconName) return null;
  const defaultIcon = ENTITY_TYPE_META[entity.type]?.icon;
  if (defaultIcon && resolveEntityIconName(defaultIcon) === resolveEntityIconName(iconName)) {
    return null;
  }
  return iconName;
}

function getPersonNodeImage(entity: Entity): string | null {
  if (entity.type !== "Person") return null;
  const imageUrl = entity.properties?.visual_image_url;
  if (typeof imageUrl !== "string") return null;
  const trimmed = imageUrl.trim();
  return trimmed || null;
}

export function sanitizeProjectName(name: string): string {
  const normalized = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return normalized.replace(/^-+|-+$/g, "") || "graph";
}

export function makeFilename(projectName: string): string {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  return `${sanitizeProjectName(projectName)}-graph-${stamp}.png`;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function waitForNextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

async function waitForStableRender(): Promise<void> {
  await waitForNextFrame();
  await waitForNextFrame();
}

export function buildVisibleGraph({
  graph,
  hiddenNodeIds,
  hiddenEdgeIds,
}: Pick<
  ExportGraphImageOptions,
  "graph" | "hiddenNodeIds" | "hiddenEdgeIds"
>): { graph: Graph; visibleNodes: VisibleNodeInfo[] } {
  const exportGraph = new Graph({ multi: true, type: "directed" });
  const visibleNodes: VisibleNodeInfo[] = [];

  graph.forEachNode((nodeId, attrs) => {
    if (hiddenNodeIds.has(nodeId)) return;
    exportGraph.addNode(nodeId, { ...attrs });
    visibleNodes.push({
      id: nodeId,
      x: Number(attrs.x) || 0,
      y: Number(attrs.y) || 0,
      size: Number(attrs.size) || 8,
      label: typeof attrs.label === "string" ? attrs.label : "",
    });
  });

  graph.forEachEdge((edgeId, attrs, source, target) => {
    if (hiddenEdgeIds.has(edgeId)) return;
    if (!exportGraph.hasNode(source) || !exportGraph.hasNode(target)) return;
    exportGraph.addDirectedEdgeWithKey(edgeId, source, target, { ...attrs });
  });

  return { graph: exportGraph, visibleNodes };
}

export function estimateLabelPadding(visibleNodes: VisibleNodeInfo[]): number {
  if (typeof document === "undefined" || visibleNodes.length === 0) {
    return 0;
  }

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return 0;

  context.font = "12px sans-serif";
  const maxLabelWidth = visibleNodes.reduce((maxWidth, node) => {
    if (!node.label) return maxWidth;
    return Math.max(maxWidth, context.measureText(node.label).width);
  }, 0);

  if (maxLabelWidth <= 0) return 0;
  return Math.ceil(maxLabelWidth + 48);
}

export function computeExportSize(visibleNodes: VisibleNodeInfo[]): { width: number; height: number } {
  if (visibleNodes.length === 0) {
    return { width: EXPORT_MIN_DIMENSION, height: EXPORT_MIN_DIMENSION };
  }

  const xs = visibleNodes.map((node) => node.x);
  const ys = visibleNodes.map((node) => node.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const widthSpan = Math.max(1, maxX - minX);
  const heightSpan = Math.max(1, maxY - minY);
  const padding = Math.max(EXPORT_PADDING_MIN, Math.max(widthSpan, heightSpan) * EXPORT_PADDING_RATIO);
  const paddedWidth = widthSpan + padding * 2;
  const paddedHeight = heightSpan + padding * 2;
  const largestSide = Math.max(paddedWidth, paddedHeight);
  const scale = EXPORT_MAX_DIMENSION / largestSide;
  const labelPadding = estimateLabelPadding(visibleNodes);

  return {
    width: Math.max(EXPORT_MIN_DIMENSION, Math.round(paddedWidth * scale) + labelPadding),
    height: Math.max(EXPORT_MIN_DIMENSION, Math.round(paddedHeight * scale)),
  };
}

async function loadImageFromSource(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    image.src = src;
  });
}

async function loadProtectedPersonImage(entity: Entity, imageUrl: string): Promise<HTMLImageElement | null> {
  try {
    if (entity.project_id) {
      const blob = await api.entities.fetchPersonImage(entity.project_id, entity.id);
      const objectUrl = URL.createObjectURL(blob);
      try {
        return await loadImageFromSource(objectUrl);
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    }
    if (imageUrl && !imageUrl.startsWith("/api/v1/")) {
      return await loadImageFromSource(imageUrl);
    }
  } catch {
    if (imageUrl && !imageUrl.startsWith("/api/v1/")) {
      try {
        return await loadImageFromSource(imageUrl);
      } catch {
        return null;
      }
    }
  }
  return null;
}

function renderLucideIconSvg(
  iconName: string,
  size: number,
  color: string,
): Promise<string | null> | string | null {
  const normalizedName = resolveEntityIconName(iconName);
  const StaticIcon = getEntityIconComponent(normalizedName);
  if (StaticIcon) {
    return renderToStaticMarkup(
      <StaticIcon size={size} color={color} strokeWidth={2.25} />,
    );
  }

  const importer = dynamicIconImports[normalizedName as keyof typeof dynamicIconImports];
  if (!importer) return null;

  return importer()
    .then((module) => {
      const Icon = module.default;
      return renderToStaticMarkup(
        <Icon size={size} color={color} strokeWidth={2.25} />,
      );
    })
    .catch(() => null);
}

async function drawIconOverlay(
  context: CanvasRenderingContext2D,
  overlay: Extract<Overlay, { kind: "icon" }>,
): Promise<void> {
  let src: string | null = null;
  if (isCustomSvgIcon(overlay.icon)) {
    src = `/icons/${overlay.icon}.svg`;
  } else {
    const svgMarkup = await renderLucideIconSvg(overlay.icon, overlay.size, overlay.color);
    if (svgMarkup) {
      src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgMarkup)}`;
    }
  }

  if (!src) return;
  const image = await loadImageFromSource(src);
  context.drawImage(
    image,
    overlay.x - overlay.size / 2,
    overlay.y - overlay.size / 2,
    overlay.size,
    overlay.size,
  );
}

async function drawImageOverlay(
  context: CanvasRenderingContext2D,
  overlay: Extract<Overlay, { kind: "image" }>,
  entity: Entity,
): Promise<void> {
  const image = await loadProtectedPersonImage(entity, overlay.imageUrl);
  if (!image) return;

  const radius = overlay.size / 2;
  context.save();
  context.beginPath();
  context.arc(overlay.x, overlay.y, radius, 0, Math.PI * 2);
  context.closePath();
  context.clip();
  context.drawImage(
    image,
    overlay.x - radius,
    overlay.y - radius,
    overlay.size,
    overlay.size,
  );
  context.restore();

  context.save();
  context.strokeStyle = "rgba(255,255,255,0.2)";
  context.lineWidth = Math.max(1, overlay.size * 0.035);
  context.beginPath();
  context.arc(overlay.x, overlay.y, radius - context.lineWidth / 2, 0, Math.PI * 2);
  context.stroke();
  context.restore();
}

async function composeOverlays(
  exportCanvas: HTMLCanvasElement,
  renderer: Sigma,
  entities: Map<string, Entity>,
): Promise<void> {
  const context = exportCanvas.getContext("2d");
  if (!context) return;

  const overlays: Overlay[] = [];
  renderer.getGraph().forEachNode((nodeId, attrs) => {
    const entity = entities.get(nodeId);
    if (!entity) return;
    const point = renderer.graphToViewport({
      x: Number(attrs.x) || 0,
      y: Number(attrs.y) || 0,
    });
    const scaledSize = (renderer as Sigma & { scaleSize?: (size?: number) => number }).scaleSize?.(
      Number(attrs.size) || 8,
    ) ?? (Number(attrs.size) || 8);
    const imageUrl = getPersonNodeImage(entity);
    if (imageUrl) {
      overlays.push({
        id: nodeId,
        kind: "image",
        x: point.x,
        y: point.y,
        size: Math.max(18, scaledSize * 2),
        projectId: entity.project_id,
        imageUrl,
      });
      return;
    }

    const customIcon = getCustomNodeIcon(entity);
    if (customIcon) {
      overlays.push({
        id: nodeId,
        kind: "icon",
        x: point.x,
        y: point.y,
        size: Math.max(10, scaledSize * 1.35),
        icon: customIcon,
        color: getContrastIconColor(String(attrs.color ?? "")),
      });
    }
  });

  for (const overlay of overlays) {
    const entity = entities.get(overlay.id);
    if (!entity) continue;
    if (overlay.kind === "icon") {
      await drawIconOverlay(context, overlay);
    } else {
      await drawImageOverlay(context, overlay, entity);
    }
  }
}

export async function exportGraphImage({
  graph,
  entities,
  hiddenNodeIds,
  hiddenEdgeIds,
  projectName,
  backgroundColor,
}: ExportGraphImageOptions): Promise<void> {
  const { graph: exportGraph, visibleNodes } = buildVisibleGraph({
    graph,
    hiddenNodeIds,
    hiddenEdgeIds,
  });
  if (visibleNodes.length === 0) {
    throw new Error("There are no visible graph nodes to export");
  }

  const { width, height } = computeExportSize(visibleNodes);
  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.left = "-10000px";
  container.style.top = "0";
  container.style.width = `${width}px`;
  container.style.height = `${height}px`;
  container.style.pointerEvents = "none";
  document.body.appendChild(container);

  let renderer: Sigma | null = null;
  try {
    renderer = new Sigma(exportGraph, container, {
      renderEdgeLabels: true,
      defaultEdgeType: "arrow",
      defaultNodeColor: "#6366f1",
      defaultEdgeColor: "#4b5563",
      labelColor: { color: "#e1e4ed" },
      labelSize: 12,
      labelRenderedSizeThreshold: 6,
      enableEdgeEvents: false,
      minEdgeThickness: 2,
      itemSizesReference: "screen",
      zIndex: true,
    });

    renderer.getCamera().animatedReset({ duration: 0 });
    renderer.refresh();
    await waitForStableRender();

    const exportCanvas = document.createElement("canvas");
    exportCanvas.width = width;
    exportCanvas.height = height;
    const context = exportCanvas.getContext("2d");
    if (!context) {
      throw new Error("Failed to create export canvas");
    }

    context.fillStyle = backgroundColor;
    context.fillRect(0, 0, width, height);

    const canvases = Array.from(container.querySelectorAll("canvas"));
    for (const canvas of canvases) {
      context.drawImage(canvas, 0, 0, width, height);
    }

    await composeOverlays(exportCanvas, renderer, entities);

    const blob = await new Promise<Blob>((resolve, reject) => {
      exportCanvas.toBlob((value) => {
        if (!value) {
          reject(new Error("Failed to export graph image"));
          return;
        }
        resolve(value);
      }, "image/png");
    });

    downloadBlob(blob, makeFilename(projectName));
  } finally {
    renderer?.kill();
    container.remove();
  }
}
