import type { Entity } from "../types/entity";

export interface ParsedSearchQuery {
  textTerms: string[];
  typeTerms: string[];
  tagTerms: string[];
  sourceTerms: string[];
}

export function parseSearchQuery(query: string): ParsedSearchQuery {
  const parsed: ParsedSearchQuery = {
    textTerms: [],
    typeTerms: [],
    tagTerms: [],
    sourceTerms: [],
  };

  for (const rawToken of query.trim().split(/\s+/)) {
    if (!rawToken) continue;
    const token = rawToken.toLowerCase();

    if (token.startsWith("type:")) {
      const value = token.slice(5).trim();
      if (value) parsed.typeTerms.push(value);
      continue;
    }
    if (token.startsWith("tag:")) {
      const value = token.slice(4).trim();
      if (value) parsed.tagTerms.push(value);
      continue;
    }
    if (token.startsWith("source:")) {
      const value = token.slice(7).trim();
      if (value) parsed.sourceTerms.push(value);
      continue;
    }

    parsed.textTerms.push(token);
  }

  return parsed;
}

export function matchesEntitySearch(entity: Entity, query: string): boolean {
  const trimmed = query.trim();
  if (!trimmed) return true;

  const parsed = parseSearchQuery(trimmed);
  const typeValue = entity.type.toLowerCase();
  const sourceValue = entity.source.toLowerCase();
  const tagValues = entity.tags.map((tag) => tag.toLowerCase());
  const searchableText = [
    entity.value,
    entity.type,
    entity.notes,
    entity.source,
    ...entity.tags,
    ...Object.values(entity.properties).map((v) => String(v)),
  ]
    .join(" ")
    .toLowerCase();

  if (parsed.typeTerms.some((term) => !typeValue.includes(term))) return false;
  if (parsed.sourceTerms.some((term) => !sourceValue.includes(term))) return false;
  if (parsed.tagTerms.some((term) => !tagValues.some((tag) => tag.includes(term)))) return false;
  if (parsed.textTerms.some((term) => !searchableText.includes(term))) return false;

  return true;
}

