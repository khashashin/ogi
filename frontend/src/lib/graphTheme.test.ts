import { describe, expect, it } from "vitest";

import { ENTITY_TYPE_META } from "../types/entity";
import {
  BASE_EDGE_COLOR,
  contrastOnLight,
  getGraphPalette,
  themedEdgeColor,
  themedEntityColor,
} from "./graphTheme";

describe("graphTheme", () => {
  it("keeps the stored edge colour in the dark theme", () => {
    const dark = getGraphPalette("dark");

    expect(themedEdgeColor(BASE_EDGE_COLOR, dark)).toBe(BASE_EDGE_COLOR);
  });

  it("swaps the stored edge colour for the light theme's", () => {
    const light = getGraphPalette("light");

    expect(themedEdgeColor(BASE_EDGE_COLOR, light)).toBe(light.edge);
    expect(themedEdgeColor(undefined, light)).toBe(light.edge);
    expect(light.edge).not.toBe(BASE_EDGE_COLOR);
  });

  it("leaves edges with their own colour alone", () => {
    expect(themedEdgeColor("#ff0000", getGraphPalette("light"))).toBe("#ff0000");
  });

  it("uses dark label text on the light canvas", () => {
    expect(getGraphPalette("light").label).not.toBe(getGraphPalette("dark").label);
  });
});

describe("themedEntityColor", () => {
  const typeColors = Object.values(ENTITY_TYPE_META).map((meta) => meta.color);

  it("leaves every colour alone in the dark theme", () => {
    typeColors.forEach((color) => expect(themedEntityColor(color, "dark")).toBe(color));
  });

  it("gives every built-in type colour at least 3:1 on the light background", () => {
    typeColors.forEach((color) => {
      expect(contrastOnLight(themedEntityColor(color, "light"))).toBeGreaterThanOrEqual(3);
    });
  });

  it("darkens pale colours only as far as needed", () => {
    const documentColor = themedEntityColor("#e2e8f0", "light");

    expect(documentColor).toMatch(/^#[0-9a-f]{6}$/);
    expect(contrastOnLight(documentColor)).toBeLessThan(3.2);
  });

  it("keeps colours that already contrast enough, and unknown formats", () => {
    expect(themedEntityColor("#6366f1", "light")).toBe("#6366f1");
    expect(themedEntityColor("rgb(1, 2, 3)", "light")).toBe("rgb(1, 2, 3)");
  });
});
