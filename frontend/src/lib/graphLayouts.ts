import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { circular } from "graphology-layout";
import type { Entity } from "../types/entity";

export type GraphLayoutPreset =
  | "force"
  | "circular"
  | "grid"
  | "spiral"
  | "concentric"
  | "components"
  | "type-columns"
  | "type-rings"
  | "degree-lines"
  | "timeline";

export interface GraphLayoutOption {
  id: GraphLayoutPreset;
  label: string;
  description: string;
}

const TAU = Math.PI * 2;

export const GRAPH_LAYOUT_OPTIONS: GraphLayoutOption[] = [
  { id: "force", label: "Force-directed", description: "Balanced default for mixed investigation graphs." },
  { id: "circular", label: "Circular", description: "Single ring, useful for quick overview." },
  { id: "grid", label: "Grid", description: "Even spacing for dense messy graphs." },
  { id: "spiral", label: "Spiral", description: "Unwinds nodes outward in a readable sweep." },
  { id: "concentric", label: "Concentric", description: "Places high-degree nodes near the center." },
  { id: "components", label: "Connected Components", description: "Separates disconnected subgraphs into clusters." },
  { id: "type-columns", label: "By Entity Type", description: "Groups nodes into vertical lanes by type." },
  { id: "type-rings", label: "Type Rings", description: "Places entity types on their own circular bands." },
  { id: "degree-lines", label: "By Connectivity", description: "Sorts nodes into rows by degree." },
  { id: "timeline", label: "By Created Time", description: "Orders nodes from older to newer when timestamps exist." },
];

interface LayoutContext {
  graph: Graph;
  entities: Map<string, Entity>;
}

function setNodePosition(graph: Graph, node: string, x: number, y: number): void {
  graph.setNodeAttribute(node, "x", x);
  graph.setNodeAttribute(node, "y", y);
}

function sortedNodes(graph: Graph, entities: Map<string, Entity>): string[] {
  return graph.nodes().sort((a, b) => {
    const ea = entities.get(a);
    const eb = entities.get(b);
    const typeCompare = (ea?.type ?? "").localeCompare(eb?.type ?? "");
    if (typeCompare !== 0) return typeCompare;
    return (ea?.value ?? a).localeCompare(eb?.value ?? b);
  });
}

function nodeDegreeMap(graph: Graph): Map<string, number> {
  const degrees = new Map<string, number>();
  graph.forEachNode((node) => {
    degrees.set(node, graph.degree(node));
  });
  return degrees;
}

function applyGrid({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  if (nodes.length === 0) return;

  const columns = Math.max(2, Math.ceil(Math.sqrt(nodes.length)));
  const spacingX = 180;
  const spacingY = 140;

  nodes.forEach((node, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    setNodePosition(graph, node, col * spacingX, row * spacingY);
  });
}

function applySpiral({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const radiusStep = 22;
  const angleStep = 0.55;

  nodes.forEach((node, index) => {
    const radius = 60 + index * radiusStep;
    const angle = index * angleStep;
    setNodePosition(graph, node, Math.cos(angle) * radius, Math.sin(angle) * radius);
  });
}

function applyConcentric({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const degrees = nodeDegreeMap(graph);
  const maxDegree = Math.max(1, ...nodes.map((node) => degrees.get(node) ?? 0));

  const buckets = new Map<number, string[]>();
  for (const node of nodes) {
    const degree = degrees.get(node) ?? 0;
    const bucket = Math.min(4, Math.floor(((maxDegree - degree) / maxDegree) * 4));
    const list = buckets.get(bucket) ?? [];
    list.push(node);
    buckets.set(bucket, list);
  }

  for (const [bucket, bucketNodes] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
    const radius = 90 + bucket * 140;
    bucketNodes.forEach((node, index) => {
      const angle = (index / Math.max(1, bucketNodes.length)) * TAU;
      setNodePosition(graph, node, Math.cos(angle) * radius, Math.sin(angle) * radius);
    });
  }
}

function connectedComponents(graph: Graph): string[][] {
  const visited = new Set<string>();
  const components: string[][] = [];

  for (const start of graph.nodes()) {
    if (visited.has(start)) continue;
    const queue = [start];
    visited.add(start);
    const component: string[] = [];

    while (queue.length > 0) {
      const node = queue.shift();
      if (!node) continue;
      component.push(node);
      for (const neighbor of graph.neighbors(node)) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }
    components.push(component);
  }

  return components.sort((a, b) => b.length - a.length);
}

function applyComponents({ graph, entities }: LayoutContext): void {
  const components = connectedComponents(graph);
  const clusterGapX = 420;
  const clusterGapY = 340;
  const columns = Math.max(1, Math.ceil(Math.sqrt(components.length)));

  components.forEach((component, componentIndex) => {
    const col = componentIndex % columns;
    const row = Math.floor(componentIndex / columns);
    const centerX = col * clusterGapX;
    const centerY = row * clusterGapY;
    const ordered = component.slice().sort((a, b) => (entities.get(a)?.value ?? a).localeCompare(entities.get(b)?.value ?? b));
    const radius = Math.max(80, ordered.length * 16);

    ordered.forEach((node, index) => {
      const angle = (index / Math.max(1, ordered.length)) * TAU;
      setNodePosition(graph, node, centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius);
    });
  });
}

function groupNodesByKey(nodes: string[], keyFor: (node: string) => string): [string, string[]][] {
  const groups = new Map<string, string[]>();
  for (const node of nodes) {
    const key = keyFor(node);
    const list = groups.get(key) ?? [];
    list.push(node);
    groups.set(key, list);
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function applyTypeColumns({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const groups = groupNodesByKey(nodes, (node) => entities.get(node)?.type ?? "Unknown");
  const columnGap = 260;
  const rowGap = 115;

  groups.forEach(([, groupNodes], groupIndex) => {
    const x = groupIndex * columnGap;
    groupNodes.forEach((node, rowIndex) => {
      setNodePosition(graph, node, x, rowIndex * rowGap);
    });
  });
}

function applyTypeRings({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const groups = groupNodesByKey(nodes, (node) => entities.get(node)?.type ?? "Unknown");

  groups.forEach(([, groupNodes], ringIndex) => {
    const radius = 120 + ringIndex * 120;
    groupNodes.forEach((node, index) => {
      const angle = (index / Math.max(1, groupNodes.length)) * TAU;
      setNodePosition(graph, node, Math.cos(angle) * radius, Math.sin(angle) * radius);
    });
  });
}

function applyDegreeLines({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const degrees = nodeDegreeMap(graph);
  const groups = groupNodesByKey(nodes, (node) => String(degrees.get(node) ?? 0));
  const rowGap = 130;
  const colGap = 170;

  groups
    .sort((a, b) => Number(b[0]) - Number(a[0]))
    .forEach(([, groupNodes], rowIndex) => {
      groupNodes.forEach((node, colIndex) => {
        setNodePosition(graph, node, colIndex * colGap, rowIndex * rowGap);
      });
    });
}

function applyTimeline({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities).sort((a, b) => {
    const da = Date.parse(entities.get(a)?.created_at ?? "") || 0;
    const db = Date.parse(entities.get(b)?.created_at ?? "") || 0;
    return da - db;
  });

  const colGap = 170;
  const laneGap = 120;
  const groups = groupNodesByKey(nodes, (node) => entities.get(node)?.type ?? "Unknown");
  const laneByNode = new Map<string, number>();
  groups.forEach(([, groupNodes], laneIndex) => {
    groupNodes.forEach((node) => laneByNode.set(node, laneIndex));
  });

  nodes.forEach((node, index) => {
    setNodePosition(graph, node, index * colGap, (laneByNode.get(node) ?? 0) * laneGap);
  });
}

export function applyGraphLayout(
  preset: GraphLayoutPreset,
  graph: Graph,
  entities: Map<string, Entity>,
): void {
  if (graph.order < 2) return;

  const ctx = { graph, entities };
  switch (preset) {
    case "force":
      forceAtlas2.assign(graph, {
        iterations: 220,
        settings: {
          gravity: 1,
          scalingRatio: 2,
          barnesHutOptimize: graph.order > 50,
        },
      });
      return;
    case "circular":
      circular.assign(graph);
      return;
    case "grid":
      applyGrid(ctx);
      return;
    case "spiral":
      applySpiral(ctx);
      return;
    case "concentric":
      applyConcentric(ctx);
      return;
    case "components":
      applyComponents(ctx);
      return;
    case "type-columns":
      applyTypeColumns(ctx);
      return;
    case "type-rings":
      applyTypeRings(ctx);
      return;
    case "degree-lines":
      applyDegreeLines(ctx);
      return;
    case "timeline":
      applyTimeline(ctx);
      return;
    default:
      return;
  }
}
