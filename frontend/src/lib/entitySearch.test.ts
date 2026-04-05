import { describe, expect, it } from "vitest";

import { EntityType, type Entity } from "../types/entity";
import { matchesEntitySearch, parseSearchQuery } from "./entitySearch";

function makeEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: "e-1",
    type: EntityType.Domain,
    value: "example.org",
    properties: { registrar: "example registrar" },
    icon: "globe",
    weight: 1,
    notes: "investigation note",
    tags: ["important", "whois"],
    source: "whois_lookup",
    project_id: "p-1",
    created_at: "2026-03-03T10:00:00Z",
    updated_at: "2026-03-03T10:00:00Z",
    ...overrides,
  };
}

describe("parseSearchQuery", () => {
  it("parses structured tokens and plain text terms", () => {
    const parsed = parseSearchQuery("type:domain tag:important source:whois hello world");
    expect(parsed.typeTerms).toEqual(["domain"]);
    expect(parsed.tagTerms).toEqual(["important"]);
    expect(parsed.sourceTerms).toEqual(["whois"]);
    expect(parsed.textTerms).toEqual(["hello", "world"]);
  });

  it("is case-insensitive and ignores empty tokens", () => {
    const parsed = parseSearchQuery("   TYPE:URL   tag:SECURITY   source:HTTP   ");
    expect(parsed.typeTerms).toEqual(["url"]);
    expect(parsed.tagTerms).toEqual(["security"]);
    expect(parsed.sourceTerms).toEqual(["http"]);
    expect(parsed.textTerms).toEqual([]);
  });
});

describe("matchesEntitySearch", () => {
  it("matches when all structured terms match", () => {
    const entity = makeEntity();
    expect(matchesEntitySearch(entity, "type:domain tag:important source:whois")).toBe(true);
  });

  it("matches plain text across value, notes, tags and properties", () => {
    const entity = makeEntity();
    expect(matchesEntitySearch(entity, "example.org")).toBe(true);
    expect(matchesEntitySearch(entity, "investigation")).toBe(true);
    expect(matchesEntitySearch(entity, "important")).toBe(true);
    expect(matchesEntitySearch(entity, "registrar")).toBe(true);
  });

  it("returns false when any required term does not match", () => {
    const entity = makeEntity();
    expect(matchesEntitySearch(entity, "type:url")).toBe(false);
    expect(matchesEntitySearch(entity, "tag:internal")).toBe(false);
    expect(matchesEntitySearch(entity, "source:cert")).toBe(false);
    expect(matchesEntitySearch(entity, "nonexistent")).toBe(false);
  });
});

