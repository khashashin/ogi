import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { circular } from "graphology-layout";
import type { Entity } from "../types/entity";

export type GraphLayoutPreset =
  | "force"
  | "cose"
  | "fcose"
  | "kamada-kawai"
  | "sugiyama"
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

export type GraphLayoutTarget = "all" | "selected" | "unpinned";

const TAU = Math.PI * 2;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

export const GRAPH_LAYOUT_OPTIONS: GraphLayoutOption[] = [
  { id: "force", label: "Force-directed", description: "Balanced default for mixed investigation graphs." },
  { id: "cose", label: "CoSE", description: "Compound spring style layout with clearer component separation." },
  { id: "fcose", label: "fCoSE", description: "Faster, more compact spring layout for investigation graphs." },
  { id: "kamada-kawai", label: "Kamada-Kawai", description: "Classic spring-embedder that emphasizes graph distances." },
  { id: "sugiyama", label: "Sugiyama", description: "Layered hierarchical layout for directional relationship flows." },
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

interface GraphLayoutRunOptions {
  pinnedNodeIds?: Set<string>;
  selectedNodeIds?: Set<string>;
  target?: GraphLayoutTarget;
}

function applyDegreeSizing(graph: Graph, entities: Map<string, Entity>): void {
  const nodes = graph.nodes();
  if (nodes.length === 0) return;

  const degrees = nodeDegreeMap(graph);
  const maxDegree = Math.max(1, ...nodes.map((node) => degrees.get(node) ?? 0));
  const minDegree = Math.min(...nodes.map((node) => degrees.get(node) ?? 0));
  const minSize = 10;
  const maxSize = 28;

  nodes.forEach((node) => {
    const degree = degrees.get(node) ?? 0;
    const weight = Math.max(1, entities.get(node)?.weight ?? 1);
    const normalizedDegree =
      maxDegree === minDegree ? 0.35 : (degree - minDegree) / (maxDegree - minDegree);
    const weightedBase = Math.min(1, (weight - 1) / 6);
    const size = minSize + (normalizedDegree * 0.8 + weightedBase * 0.2) * (maxSize - minSize);
    graph.setNodeAttribute(node, "size", Number(size.toFixed(2)));
  });
}

function seedForcePositions(graph: Graph, entities: Map<string, Entity>): void {
  const nodes = sortedNodes(graph, entities);
  nodes.forEach((node, index) => {
    const radius = 28 * Math.sqrt(index + 1);
    const angle = index * GOLDEN_ANGLE;
    setNodePosition(graph, node, Math.cos(angle) * radius, Math.sin(angle) * radius);
  });
}

export function applyForceDirectedLayout(graph: Graph, entities: Map<string, Entity>): void {
  seedForcePositions(graph, entities);
  applyDegreeSizing(graph, entities);

  forceAtlas2.assign(graph, {
    iterations: graph.order > 200 ? 220 : 520,
    settings: {
      adjustSizes: true,
      gravity: 1,
      slowDown: graph.order > 200 ? 10 : 4,
      scalingRatio: graph.order > 200 ? 12 : 8,
      strongGravityMode: false,
      barnesHutOptimize: graph.order > 50,
      outboundAttractionDistribution: false,
      linLogMode: false,
    },
  });
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

function shortestPathMap(graph: Graph, start: string): Map<string, number> {
  const distances = new Map<string, number>([[start, 0]]);
  const queue = [start];
  while (queue.length > 0) {
    const node = queue.shift();
    if (!node) continue;
    const currentDistance = distances.get(node) ?? 0;
    for (const neighbor of graph.neighbors(node)) {
      if (distances.has(neighbor)) continue;
      distances.set(neighbor, currentDistance + 1);
      queue.push(neighbor);
    }
  }
  return distances;
}

function getCurrentPosition(graph: Graph, node: string) {
  const attrs = graph.getNodeAttributes(node) as { x?: number; y?: number };
  return {
    x: Number(attrs.x) || 0,
    y: Number(attrs.y) || 0,
  };
}

function applyKamadaKawai(graph: Graph, entities: Map<string, Entity>): void {
  const nodes = sortedNodes(graph, entities);
  if (nodes.length < 2) return;

  applyConcentric({ graph, entities });

  if (nodes.length > 140) {
    applyForceDirectedLayout(graph, entities);
    return;
  }

  const distances = new Map<string, Map<string, number>>();
  let maxDistance = 1;
  for (const node of nodes) {
    const dist = shortestPathMap(graph, node);
    distances.set(node, dist);
    for (const value of dist.values()) {
      if (value > maxDistance) maxDistance = value;
    }
  }

  const area = Math.max(400, nodes.length * 35);
  const idealLength = area / maxDistance;
  const iterations = Math.min(120, 20 + nodes.length * 2);

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const positions = new Map(nodes.map((node) => [node, getCurrentPosition(graph, node)]));
    const displacements = new Map<string, { x: number; y: number }>(
      nodes.map((node) => [node, { x: 0, y: 0 }]),
    );

    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      const posA = positions.get(a)!;
      const distA = distances.get(a)!;
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const posB = positions.get(b)!;
        const graphDistance = distA.get(b) ?? maxDistance + 1;
        const preferred = idealLength * graphDistance;
        const dx = posB.x - posA.x;
        const dy = posB.y - posA.y;
        const euclidean = Math.max(0.01, Math.hypot(dx, dy));
        const delta = euclidean - preferred;
        const stiffness = 1 / (graphDistance * graphDistance);
        const force = stiffness * delta * 0.015;
        const fx = (dx / euclidean) * force;
        const fy = (dy / euclidean) * force;

        const dispA = displacements.get(a)!;
        const dispB = displacements.get(b)!;
        dispA.x += fx;
        dispA.y += fy;
        dispB.x -= fx;
        dispB.y -= fy;
      }
    }

    for (const node of nodes) {
      const pos = positions.get(node)!;
      const disp = displacements.get(node)!;
      setNodePosition(graph, node, pos.x + disp.x, pos.y + disp.y);
    }
  }
}

function applyCoseLike(graph: Graph, entities: Map<string, Entity>, compact: boolean): void {
  seedForcePositions(graph, entities);
  applyComponents({ graph, entities });
  applyDegreeSizing(graph, entities);

  forceAtlas2.assign(graph, {
    iterations: compact ? 260 : 420,
    settings: {
      adjustSizes: true,
      gravity: compact ? 1.4 : 0.9,
      strongGravityMode: compact,
      slowDown: compact ? 5 : 7,
      scalingRatio: compact ? 7 : 10,
      barnesHutOptimize: graph.order > 50,
      outboundAttractionDistribution: false,
      linLogMode: compact,
    },
  });
}

function topologicalLayers(graph: Graph, orderedNodes: string[]): Map<string, number> {
  const layerByNode = new Map<string, number>();
  const indegree = new Map<string, number>();
  const queue: string[] = [];

  for (const node of orderedNodes) {
    const degree = typeof graph.inDegree === "function" ? graph.inDegree(node) : graph.degree(node);
    indegree.set(node, degree);
    if (degree === 0) {
      queue.push(node);
      layerByNode.set(node, 0);
    }
  }

  const remaining = new Set(orderedNodes);
  while (queue.length > 0) {
    const node = queue.shift()!;
    remaining.delete(node);
    const currentLayer = layerByNode.get(node) ?? 0;
    const neighbors = typeof graph.outNeighbors === "function" ? graph.outNeighbors(node) : graph.neighbors(node);
    for (const neighbor of neighbors) {
      const nextLayer = Math.max(layerByNode.get(neighbor) ?? 0, currentLayer + 1);
      layerByNode.set(neighbor, nextLayer);
      const nextIndegree = (indegree.get(neighbor) ?? 0) - 1;
      indegree.set(neighbor, nextIndegree);
      if (nextIndegree <= 0) {
        queue.push(neighbor);
      }
    }
  }

  if (remaining.size > 0) {
    const components = connectedComponents(graph);
    for (const component of components) {
      const anchor = component[0];
      if (!anchor || !remaining.has(anchor)) continue;
      const distances = shortestPathMap(graph, anchor);
      for (const node of component) {
        if (!layerByNode.has(node)) layerByNode.set(node, distances.get(node) ?? 0);
      }
    }
  }

  return layerByNode;
}

function applySugiyama({ graph, entities }: LayoutContext): void {
  const nodes = sortedNodes(graph, entities);
  const layerByNode = topologicalLayers(graph, nodes);
  const groups = groupNodesByKey(nodes, (node) => String(layerByNode.get(node) ?? 0))
    .sort((a, b) => Number(a[0]) - Number(b[0]));

  const layerGapY = 180;
  const nodeGapX = 180;
  groups.forEach(([layer, layerNodes]) => {
    const numericLayer = Number(layer) || 0;
    const sortedLayerNodes = layerNodes.slice().sort((a, b) => {
      const degreeDiff = graph.degree(b) - graph.degree(a);
      if (degreeDiff !== 0) return degreeDiff;
      return (entities.get(a)?.value ?? a).localeCompare(entities.get(b)?.value ?? b);
    });
    const totalWidth = Math.max(0, (sortedLayerNodes.length - 1) * nodeGapX);
    sortedLayerNodes.forEach((node, index) => {
      const x = index * nodeGapX - totalWidth / 2;
      const y = numericLayer * layerGapY;
      setNodePosition(graph, node, x, y);
    });
  });
}

export function applyGraphLayout(
  preset: GraphLayoutPreset,
  graph: Graph,
  entities: Map<string, Entity>,
  options: GraphLayoutRunOptions = {},
): void {
  if (graph.order < 2) return;

  const pinnedNodeIds = options.pinnedNodeIds ?? new Set<string>();
  const selectedNodeIds = options.selectedNodeIds ?? new Set<string>();
  const target = options.target ?? "unpinned";
  const nodes = new Set(graph.nodes());
  const effectivePinnedNodeIds = new Set<string>();

  if (target === "selected") {
    for (const node of nodes) {
      if (!selectedNodeIds.has(node)) effectivePinnedNodeIds.add(node);
    }
    for (const node of pinnedNodeIds) {
      if (!selectedNodeIds.has(node)) effectivePinnedNodeIds.add(node);
    }
  } else if (target === "unpinned") {
    for (const node of pinnedNodeIds) effectivePinnedNodeIds.add(node);
  }

  const pinnedPositions = new Map<string, { x: number; y: number; size: number | null }>();
  for (const node of effectivePinnedNodeIds) {
    if (!graph.hasNode(node)) continue;
    const attrs = graph.getNodeAttributes(node) as { x?: number; y?: number; size?: number };
    pinnedPositions.set(node, {
      x: Number(attrs.x) || 0,
      y: Number(attrs.y) || 0,
      size: typeof attrs.size === "number" ? attrs.size : null,
    });
  }

  const ctx = { graph, entities };
  switch (preset) {
    case "force":
      applyForceDirectedLayout(graph, entities);
      break;
    case "cose":
      applyCoseLike(graph, entities, false);
      break;
    case "fcose":
      applyCoseLike(graph, entities, true);
      break;
    case "kamada-kawai":
      applyKamadaKawai(graph, entities);
      break;
    case "sugiyama":
      applySugiyama(ctx);
      break;
    case "circular":
      circular.assign(graph);
      break;
    case "grid":
      applyGrid(ctx);
      break;
    case "spiral":
      applySpiral(ctx);
      break;
    case "concentric":
      applyConcentric(ctx);
      break;
    case "components":
      applyComponents(ctx);
      break;
    case "type-columns":
      applyTypeColumns(ctx);
      break;
    case "type-rings":
      applyTypeRings(ctx);
      break;
    case "degree-lines":
      applyDegreeLines(ctx);
      break;
    case "timeline":
      applyTimeline(ctx);
      break;
    default:
      break;
  }

  for (const [node, position] of pinnedPositions) {
    if (!graph.hasNode(node)) continue;
    graph.setNodeAttribute(node, "x", position.x);
    graph.setNodeAttribute(node, "y", position.y);
    if (position.size !== null) {
      graph.setNodeAttribute(node, "size", position.size);
    }
  }
}
