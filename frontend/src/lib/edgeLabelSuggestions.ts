import type { Edge } from "../types/edge";
import type { Entity } from "../types/entity";

const STATIC_EDGE_LABELS: Record<string, string[]> = {
  "Person->Organization": ["works at", "member of", "represents"],
  "Organization->Person": ["employs", "managed by", "associated with"],
  "Person->Location": ["located in", "visited", "based in"],
  "Organization->Location": ["located in", "operates in", "registered in"],
  "Domain->IPAddress": ["resolves to", "hosted on", "points to"],
  "IPAddress->Domain": ["hosts", "serves", "associated with"],
  "URL->Domain": ["hosted on", "belongs to", "references"],
  "Domain->URL": ["hosts", "serves", "contains"],
  "Location->Location": ["near", "connected to", "observed between"],
};

function pairKey(sourceType: string, targetType: string): string {
  return `${sourceType}->${targetType}`;
}

export function getEdgeLabelSuggestions(
  source: Entity,
  target: Entity,
  edges: Iterable<Edge>,
  entities: Map<string, Entity>,
): string[] {
  const suggestions: string[] = [];
  const seen = new Set<string>();

  const push = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    const normalized = trimmed.toLowerCase();
    if (seen.has(normalized)) return;
    seen.add(normalized);
    suggestions.push(trimmed);
  };

  for (const edge of edges) {
    const edgeSource = entities.get(edge.source_id);
    const edgeTarget = entities.get(edge.target_id);
    if (!edgeSource || !edgeTarget) continue;
    if (edgeSource.type === source.type && edgeTarget.type === target.type) {
      push(edge.label);
    }
  }

  for (const fallback of STATIC_EDGE_LABELS[pairKey(source.type, target.type)] ?? []) {
    push(fallback);
  }

  push("related to");
  return suggestions;
}
